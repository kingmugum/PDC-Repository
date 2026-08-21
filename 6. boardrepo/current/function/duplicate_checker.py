from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import time
from typing import Callable
from urllib.parse import urljoin

from board_post_navigation import open_board_post_by_title
from browser_runtime import launch_persistent_context_auto
from browser_automation import (
    BrowserAutomationError,
    _ensure_community_context,
    _looks_like_login_page,
    _page_body_text,
    _stage_stabilize,
    _wait_until_logged_in,
)


STATUS_NEW = "NEW"
STATUS_DUPLICATE = "DUPLICATE"
STATUS_CONFLICT = "CONFLICT"
STATUS_ERROR = "ERROR"


@dataclass(frozen=True)
class RemoteCheckItem:
    target_key: str
    display_name: str
    board_url: str
    file_path: Path
    exact_title: str
    kind: str  # "versioned" | "ext"
    sha256: str | None = None


@dataclass(frozen=True)
class RemoteCheckResult:
    item: RemoteCheckItem
    status: str
    evidence: str
    existing_sha256: str | None = None


@dataclass(frozen=True)
class BoardRowMatch:
    title_match: bool
    filename_match: bool
    post_url: str | None
    row_text: str


_SHA_RE = re.compile(r"\b[0-9a-fA-F]{64}\b")


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _compact_text(value: str) -> str:
    """
    Whitespace-insensitive comparison used only for board-row identity matching.

    This protects duplicate checking from visual title wrapping such as
    '26080\\n8_2' while the logical title is '260808_2'.
    """
    return re.sub(r"\s+", "", str(value or "")).casefold()


def _visible_exact_text(page, text: str):
    try:
        locators = page.get_by_text(text, exact=True)
        count = locators.count()
    except Exception:
        return None

    for idx in range(count):
        try:
            loc = locators.nth(idx)
            if loc.is_visible():
                return loc
        except Exception:
            continue

    return None


def _visible_exact_title_link(page, title: str):
    # Prefer a real link so clicking a post title is less ambiguous.
    try:
        locators = page.get_by_role("link", name=title, exact=True)
        for idx in range(locators.count()):
            loc = locators.nth(idx)
            if loc.is_visible():
                return loc
    except Exception:
        pass

    return _visible_exact_text(page, title)


def _extract_sha256(body_text: str) -> str | None:
    if not body_text:
        return None

    labeled = re.search(
        r"SHA-?256\s*[:：]\s*([0-9a-fA-F]{64})",
        body_text,
        flags=re.IGNORECASE,
    )
    if labeled:
        return labeled.group(1).lower()

    generic = _SHA_RE.search(body_text)
    return generic.group(0).lower() if generic else None


def _locator_is_disabled(locator) -> bool:
    try:
        if locator.is_disabled():
            return True
    except Exception:
        pass

    try:
        aria = locator.get_attribute("aria-disabled")
        if aria and aria.lower() == "true":
            return True
    except Exception:
        pass

    try:
        cls = (locator.get_attribute("class") or "").casefold()
        if "disabled" in cls:
            return True
    except Exception:
        pass

    return False


def _find_next_page_control(page, config: dict):
    texts = config.get("next_page_text_candidates", ["다음"])

    for text in texts:
        for role in ["link", "button"]:
            try:
                locators = page.get_by_role(role, name=text, exact=True)
                for idx in range(locators.count()):
                    loc = locators.nth(idx)
                    if loc.is_visible() and not _locator_is_disabled(loc):
                        return loc
            except Exception:
                continue

    for selector in [
        '[aria-label="다음"]',
        '[title="다음"]',
        'a[rel="next"]',
        'button[rel="next"]',
    ]:
        try:
            loc = page.locator(selector).first
            if loc.count() and loc.is_visible() and not _locator_is_disabled(loc):
                return loc
        except Exception:
            continue

    return None


def _page_signature(page) -> str:
    body = _page_body_text(page)
    return f"{page.url}\n{body[:4000]}"


def _dom_board_row_snapshot(page) -> list[dict]:
    """
    Return data rows using textContent, not visual innerText.

    The groupware may visually wrap a long title in the 제목 column. Reading
    textContent allows the duplicate checker to compare the logical title even
    when the browser paints it on two lines.
    """
    try:
        rows = page.evaluate(
            """() => Array.from(document.querySelectorAll('tr'))
                .map(tr => {
                    const cells = Array.from(tr.querySelectorAll('td'));
                    if (!cells.length) return null;

                    const titleCell = cells.find(td => {
                        const t = ((td.textContent || '') + '').trim();
                        return t.includes('[BoardRepo]');
                    }) || null;

                    const toLink = a => ({
                        text: ((a.textContent || a.getAttribute('aria-label') ||
                                a.getAttribute('title') || a.innerText || '') + '').trim(),
                        href: a.href || a.getAttribute('href') || ''
                    });

                    return {
                        text: ((tr.textContent || '') + '').trim(),
                        cellTexts: cells.map(td => ((td.textContent || '') + '').trim()),
                        titleText: titleCell ? ((titleCell.textContent || '') + '').trim() : '',
                        titleAnchors: titleCell
                            ? Array.from(titleCell.querySelectorAll('a[href]')).map(toLink)
                            : [],
                        rowAnchors: Array.from(tr.querySelectorAll('a[href]')).map(toLink)
                    };
                })
                .filter(Boolean)"""
        )
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def _post_url_from_row(row: dict, page_url: str) -> str | None:
    for group_name in ("titleAnchors", "rowAnchors"):
        for anchor in row.get(group_name) or []:
            href = str(anchor.get("href") or "").strip()
            if "/post/" in href and "/post/write" not in href:
                return urljoin(page_url, href)
    return None


def _find_board_row_match(page, item: RemoteCheckItem) -> BoardRowMatch | None:
    exact_compact = _compact_text(item.exact_title)
    filename_compact = _compact_text(item.file_path.name)

    filename_only: BoardRowMatch | None = None

    for row in _dom_board_row_snapshot(page):
        title_text = str(row.get("titleText") or "")
        row_text = str(row.get("text") or "")
        title_anchor_texts = [
            str(a.get("text") or "")
            for a in row.get("titleAnchors") or []
        ]

        searchable_title = "\n".join([title_text, *title_anchor_texts])
        title_compact = _compact_text(searchable_title)
        row_compact = _compact_text(row_text)

        title_match = (
            bool(exact_compact)
            and (
                exact_compact in title_compact
                or exact_compact in row_compact
            )
        )
        filename_match = (
            bool(filename_compact)
            and (
                filename_compact in title_compact
                or filename_compact in row_compact
            )
        )

        match = BoardRowMatch(
            title_match=title_match,
            filename_match=filename_match,
            post_url=_post_url_from_row(row, page.url),
            row_text=_normalize_text(row_text),
        )

        if title_match:
            return match

        if filename_match and filename_only is None:
            filename_only = match

    return filename_only


def _explicit_empty_board(body_text: str, duplicate_cfg: dict) -> bool:
    candidates = duplicate_cfg.get(
        "empty_board_text_candidates",
        [
            "게시글이 없습니다",
            "등록된 게시글이 없습니다",
            "검색된 게시물이 없습니다",
            "등록된 글이 없습니다",
        ],
    )
    body = body_text or ""
    return any(text and text in body for text in candidates)


def _board_readiness_snapshot(
    page,
    item: RemoteCheckItem,
    duplicate_cfg: dict,
) -> tuple[int, bool, bool, bool]:
    rows = _dom_board_row_snapshot(page)
    body = _page_body_text(page)
    row_match = _find_board_row_match(page, item) if rows else None

    return (
        len(rows),
        bool(row_match and row_match.title_match),
        bool(row_match and row_match.filename_match),
        _explicit_empty_board(body, duplicate_cfg),
    )


def _wait_for_board_list_ready(
    page,
    item: RemoteCheckItem,
    duplicate_cfg: dict,
    log: Callable[[str], None],
    page_no: int,
) -> bool:
    timeout_seconds = max(
        0.5,
        float(duplicate_cfg.get("board_ready_timeout_seconds", 10)),
    )
    poll_ms = max(
        100,
        int(duplicate_cfg.get("board_ready_poll_ms", 500)),
    )
    diagnostic = bool(duplicate_cfg.get("diagnostic_logging", True))

    started = time.monotonic()
    attempt = 0
    last_snapshot = None

    while True:
        attempt += 1
        row_count, title_seen, filename_seen, explicit_empty = (
            _board_readiness_snapshot(page, item, duplicate_cfg)
        )
        snapshot = (row_count, title_seen, filename_seen, explicit_empty)
        elapsed = time.monotonic() - started

        if diagnostic and (attempt == 1 or snapshot != last_snapshot):
            log(
                f"중복검사 목록 대기 [{item.display_name}] "
                f"{page_no}페이지 {attempt}차: "
                f"row={row_count}, "
                f"정확제목={'있음' if title_seen else '없음'}, "
                f"파일명={'있음' if filename_seen else '없음'}, "
                f"빈게시판={'확인' if explicit_empty else '아님'}"
            )

        # Any real data row means the list has rendered. Target-specific
        # matching is retried separately after readiness.
        if row_count > 0 or explicit_empty:
            log(
                f"중복검사 목록 준비 [{item.display_name}] "
                f"{page_no}페이지: {elapsed:.1f}초 "
                f"(row={row_count})"
            )
            return True

        if elapsed >= timeout_seconds:
            log(
                f"중복검사 목록 준비 실패 [{item.display_name}] "
                f"{page_no}페이지: {elapsed:.1f}초"
            )
            return False

        last_snapshot = snapshot
        page.wait_for_timeout(poll_ms)


def _inspect_ext_existing_post(
    page,
    item: RemoteCheckItem,
    config: dict,
    site_profile: dict,
    log: Callable[[str], None],
    post_url: str | None = None,
) -> RemoteCheckResult:
    expected_sha = (item.sha256 or "").lower()

    try:
        detail_url = open_board_post_by_title(
            page,
            board_url=item.board_url,
            expected_title=item.exact_title,
            config=config,
            site_profile=site_profile,
            log=log,
            display_name=item.display_name,
            known_post_url=post_url,
        )
        log(
            f"Ext 기존 게시글 상세 진입 [{item.file_path.name}]: "
            f"{detail_url}"
        )
    except Exception as exc:
        return RemoteCheckResult(
            item=item,
            status=STATUS_CONFLICT,
            evidence=(
                "동일한 Ext 표준 제목은 확인했지만 기존 게시글 상세로 "
                "진입하지 못해 SHA-256을 검증할 수 없습니다. "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    wait_seconds = int(config.get("ext_post_detail_wait_seconds", 5))
    poll_ms = int(config.get("ext_post_detail_poll_ms", 300))
    deadline = time.monotonic() + wait_seconds

    body_text = _page_body_text(page)
    existing_sha = _extract_sha256(body_text)

    while existing_sha is None and time.monotonic() < deadline:
        page.wait_for_timeout(poll_ms)
        body_text = _page_body_text(page)
        existing_sha = _extract_sha256(body_text)

    if existing_sha:
        log(
            f"Ext 기존 SHA 확인 [{item.file_path.name}]: "
            f"{existing_sha[:12]}..."
        )
    else:
        log(
            f"Ext 기존 SHA 확인 실패 [{item.file_path.name}]: "
            "게시글 본문에서 SHA-256을 찾지 못함"
        )

    if existing_sha and expected_sha and existing_sha == expected_sha:
        return RemoteCheckResult(
            item=item,
            status=STATUS_DUPLICATE,
            evidence=(
                "동일 파일명 Ext 게시글의 SHA-256이 현재 파일과 일치합니다. "
                "기존 게시글을 유지하고 신규 업로드를 생략합니다."
            ),
            existing_sha256=existing_sha,
        )

    if existing_sha and expected_sha and existing_sha != expected_sha:
        return RemoteCheckResult(
            item=item,
            status=STATUS_CONFLICT,
            evidence=(
                "동일 파일명 Ext 게시글이 존재하지만 SHA-256이 다릅니다. "
                "같은 이름의 다른 내용으로 판단합니다."
            ),
            existing_sha256=existing_sha,
        )

    return RemoteCheckResult(
        item=item,
        status=STATUS_CONFLICT,
        evidence=(
            "동일 파일명 Ext 게시글이 존재하지만 기존 게시글에서 SHA-256을 "
            "확인할 수 없어 동일 파일 여부를 자동 판정할 수 없습니다."
        ),
        existing_sha256=existing_sha,
    )



def _scan_current_page_for_item(
    page,
    item: RemoteCheckItem,
    duplicate_cfg: dict,
    site_profile: dict,
    log: Callable[[str], None],
    page_no: int,
) -> RemoteCheckResult | None:
    retries = max(
        1,
        int(duplicate_cfg.get("empty_scan_retries", 3)),
    )
    retry_ms = max(
        100,
        int(duplicate_cfg.get("empty_scan_retry_ms", 1000)),
    )
    diagnostic = bool(duplicate_cfg.get("diagnostic_logging", True))

    for attempt in range(1, retries + 1):
        body_text = _page_body_text(page)
        row_match = _find_board_row_match(page, item)

        # Existing accessibility/text locators remain useful as a compatibility
        # fallback, but row textContent is the first source of truth.
        title_locator = _visible_exact_title_link(page, item.exact_title)
        title_seen = bool(
            (row_match and row_match.title_match)
            or title_locator is not None
        )
        filename_seen = bool(
            (row_match and row_match.filename_match)
            or item.file_path.name in body_text
        )

        if diagnostic:
            log(
                f"중복검사 탐색 [{item.display_name}] "
                f"{page_no}페이지 {attempt}/{retries}: "
                f"정확제목={'있음' if title_seen else '없음'}, "
                f"파일명={'있음' if filename_seen else '없음'}, "
                f"행링크={'있음' if row_match and row_match.post_url else '없음'}"
            )

        if item.kind == "versioned":
            if (
                duplicate_cfg.get("standard_match_exact_title", True)
                and title_seen
            ):
                return RemoteCheckResult(
                    item=item,
                    status=STATUS_DUPLICATE,
                    evidence=(
                        f"게시판 {page_no}페이지에서 BoardRepo 정확한 제목이 "
                        f"이미 존재합니다: {item.exact_title}"
                    ),
                )

            if (
                duplicate_cfg.get("standard_match_exact_filename_text", True)
                and filename_seen
            ):
                return RemoteCheckResult(
                    item=item,
                    status=STATUS_DUPLICATE,
                    evidence=(
                        f"게시판 {page_no}페이지에서 동일 첨부파일명 텍스트가 "
                        f"확인됩니다: {item.file_path.name}"
                    ),
                )

        elif item.kind == "ext":
            if title_seen:
                post_url = row_match.post_url if row_match else None
                return _inspect_ext_existing_post(
                    page,
                    item,
                    duplicate_cfg,
                    site_profile,
                    log,
                    post_url=post_url,
                )

            # Same filename is visible but not under the standard BoardRepo Ext
            # title. Do not guess that it is safe to upload.
            if filename_seen:
                return RemoteCheckResult(
                    item=item,
                    status=STATUS_CONFLICT,
                    evidence=(
                        "게시판 목록에서 동일 파일명은 확인되지만 "
                        "BoardRepo 표준 Ext 제목의 게시글이 아니어서 "
                        "SHA-256을 자동 검증할 수 없습니다."
                    ),
                )

        if attempt < retries:
            log(
                f"중복 대상 미발견 [{item.display_name}] "
                f"{page_no}페이지 - {retry_ms / 1000:.1f}초 후 재확인"
            )
            page.wait_for_timeout(retry_ms)

    return None


def _scan_one_item(
    page,
    item: RemoteCheckItem,
    duplicate_cfg: dict,
    site_profile: dict,
    log: Callable[[str], None],
) -> RemoteCheckResult:
    max_pages = max(1, int(duplicate_cfg.get("max_board_pages", 10)))
    page_wait_ms = int(duplicate_cfg.get("page_wait_ms", 500))

    page.goto(item.board_url, wait_until="domcontentloaded")
    _stage_stabilize(page, site_profile, log, "board")

    if not _wait_for_board_list_ready(
        page,
        item,
        duplicate_cfg,
        log,
        1,
    ):
        raise BrowserAutomationError(
            "게시판 목록이 실제로 준비되었는지 확인할 수 없어 "
            "안전하게 NEW 판정을 할 수 없습니다."
        )

    seen_signatures: set[str] = set()

    for page_no in range(1, max_pages + 1):
        signature = _page_signature(page)
        if signature in seen_signatures:
            break
        seen_signatures.add(signature)

        result = _scan_current_page_for_item(
            page,
            item,
            duplicate_cfg,
            site_profile,
            log,
            page_no,
        )
        if result is not None:
            return result

        if page_no >= max_pages:
            break

        next_control = _find_next_page_control(page, duplicate_cfg)
        if next_control is None:
            break

        before = _page_signature(page)
        try:
            next_control.scroll_into_view_if_needed()
            next_control.click()
            page.wait_for_timeout(page_wait_ms)
        except Exception:
            break

        if not _wait_for_board_list_ready(
            page,
            item,
            duplicate_cfg,
            log,
            page_no + 1,
        ):
            raise BrowserAutomationError(
                f"게시판 {page_no + 1}페이지 목록 준비를 확인하지 못해 "
                "안전하게 NEW 판정을 할 수 없습니다."
            )

        after = _page_signature(page)
        if after == before:
            break

    return RemoteCheckResult(
        item=item,
        status=STATUS_NEW,
        evidence=(
            f"게시판 목록 준비를 확인한 뒤 최대 {max_pages}페이지 범위에서 "
            f"각 페이지를 재확인했지만 동일 제목/파일명을 찾지 못했습니다."
        ),
    )


def check_remote_items(
    items: list[RemoteCheckItem],
    browser_profile: Path,
    config: dict,
    site_profile: dict,
    log: Callable[[str], None],
) -> list[RemoteCheckResult]:
    if not items:
        return []

    duplicate_cfg = config.get("remote_duplicate_check") or {}
    if not duplicate_cfg.get("enabled", True):
        return [
            RemoteCheckResult(
                item=item,
                status=STATUS_NEW,
                evidence="원격 중복검사가 설정에서 비활성화되어 있습니다.",
            )
            for item in items
        ]

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserAutomationError(
            "playwright가 설치되지 않았습니다. GUI의 필수 모듈 설치/복구를 실행하세요."
        ) from exc

    browser_profile.mkdir(parents=True, exist_ok=True)
    browser_cfg = config["browser"]

    results: list[RemoteCheckResult] = []

    with sync_playwright() as p:
        log("원격 중복검사용 BoardRepo 브라우저를 실행합니다.")
        context, browser_choice = launch_persistent_context_auto(
            p,
            browser_profile,
            config,
            log,
            purpose="duplicate-check",
            accept_downloads=False,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(int(browser_cfg.get("operation_timeout_ms", 15000)))

        try:
            first = items[0]
            page.goto(first.board_url, wait_until="domcontentloaded")

            if _looks_like_login_page(page, site_profile):
                log("원격 중복검사 전 로그인이 필요한 상태를 확인했습니다.")
                _wait_until_logged_in(
                    page,
                    first.board_url,
                    site_profile,
                    int(browser_cfg.get("login_wait_seconds", 180)),
                    log,
                )
                log("원격 중복검사 로그인 완료 상태를 확인했습니다.")
                _stage_stabilize(page, site_profile, log, "login")
            else:
                log("원격 중복검사에서 기존 로그인 세션을 사용합니다.")
                _stage_stabilize(page, site_profile, log, "login")

            current_board = None
            for item in items:
                try:
                    if current_board != item.board_url:
                        _ensure_community_context(
                            page,
                            item.board_url,
                            site_profile,
                            log,
                        )
                        current_board = item.board_url

                    result = _scan_one_item(
                        page,
                        item,
                        duplicate_cfg,
                        site_profile,
                        log,
                    )
                except Exception as exc:
                    result = RemoteCheckResult(
                        item=item,
                        status=STATUS_ERROR,
                        evidence=(
                            "이 항목의 게시판 중복검사 중 오류가 발생했습니다. "
                            "게시판 목록 준비 또는 중복 여부를 확신할 수 없어 "
                            "해당 항목만 확인 필요 Skip 처리합니다. "
                            f"{type(exc).__name__}: {exc}"
                        ),
                    )
                    current_board = None

                results.append(result)
                log(
                    f"원격 중복검사 [{item.display_name}] {item.file_path.name}: "
                    f"{result.status} - {result.evidence}"
                )

                try:
                    page.goto(item.board_url, wait_until="domcontentloaded")
                    _stage_stabilize(page, site_profile, log, "board")
                except Exception as exc:
                    log(
                        f"중복검사 후 게시판 복귀 실패 [{item.display_name}]: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    current_board = None

        finally:
            context.close()

    return results
