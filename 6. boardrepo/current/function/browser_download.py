from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Callable
from urllib.parse import urljoin

from archive_selector import ArchiveSelectionError, select_latest_archive
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
from duplicate_checker import _find_next_page_control, _page_signature


STATUS_DOWNLOADED = "DOWNLOADED"
STATUS_UP_TO_DATE = "UP_TO_DATE"
STATUS_LOCAL_NEWER = "LOCAL_NEWER"
STATUS_CONFLICT = "CONFLICT"
STATUS_ERROR = "ERROR"
STATUS_REMOTE_NONE = "REMOTE_NONE"


_ARCHIVE_EXTS = {".zip", ".7z", ".rar"}
_RELEASE_RE = re.compile(
    r"^(?P<family>.+?)_(?P<date>\d{6})(?:_(?P<counter>\d+))?$",
    re.IGNORECASE,
)
_LEGACY_REV_RE = re.compile(
    r"^(?P<family>.+?)[_-]rev\d+$",
    re.IGNORECASE,
)
_SHA_RE = re.compile(r"SHA-?256\s*[:：]\s*([0-9a-fA-F]{64})", re.IGNORECASE)
_SIZE_RE = re.compile(r"(?:크기|파일\s*크기)\s*[:：]\s*([\d,]+)\s*bytes?", re.IGNORECASE)
_ATTACHMENT_RE = re.compile(r"첨부\s*파일\s*[:：]\s*([^\r\n]+)", re.IGNORECASE)
_FILENAME_RE = re.compile(r"파일명\s*[:：]\s*([^\r\n]+)", re.IGNORECASE)


@dataclass(frozen=True)
class DownloadTarget:
    target_key: str
    display_name: str
    board_url: str
    folder: Path
    aliases: tuple[str, ...]
    mode: str = "versioned_archive"


@dataclass(frozen=True)
class RemotePost:
    title: str
    post_url: str
    filename: str
    kind: str
    family: str | None = None
    date_token: str | None = None
    counter: int = 0
    sha256: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True)
class DownloadResult:
    target_key: str
    display_name: str
    status: str
    filename: str | None
    reason: str
    local_version: str | None = None
    remote_version: str | None = None


def _valid_yymmdd(token: str) -> bool:
    if len(token) != 6 or not token.isdigit():
        return False

    yy = int(token[:2])
    mm = int(token[2:4])
    dd = int(token[4:6])
    if not 1 <= mm <= 12:
        return False

    year = 2000 + yy
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    month_days = {
        1: 31, 2: 29 if leap else 28, 3: 31, 4: 30,
        5: 31, 6: 30, 7: 31, 8: 31,
        9: 30, 10: 31, 11: 30, 12: 31,
    }
    return 1 <= dd <= month_days[mm]


def parse_release_identity(name: str) -> tuple[str, str, int] | None:
    """
    Parse FAMILY_YYMMDD_N from a filename or stem.
    Legacy FAMILY_revNN_YYMMDD_N is grouped under FAMILY.
    """
    stem = Path(name).stem
    match = _RELEASE_RE.match(stem)
    if not match:
        return None

    family = match.group("family")
    date_token = match.group("date")
    counter_text = match.group("counter")

    if not _valid_yymmdd(date_token):
        return None

    legacy = _LEGACY_REV_RE.match(family)
    if legacy:
        family = legacy.group("family")

    return family, date_token, int(counter_text) if counter_text else 0


def _release_key(date_token: str | None, counter: int) -> tuple[str, int]:
    return date_token or "", int(counter)


def _safe_filename(filename: str) -> str:
    value = filename.strip().strip('"').strip("'")
    if not value:
        raise ValueError("첨부파일명이 비어 있습니다.")

    if Path(value).name != value:
        raise ValueError(f"안전하지 않은 첨부파일명입니다: {filename}")

    if any(sep in value for sep in ("/", "\\", "\x00")):
        raise ValueError(f"안전하지 않은 첨부파일명입니다: {filename}")

    return value


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _extract_sha(body_text: str) -> str | None:
    match = _SHA_RE.search(body_text or "")
    return match.group(1).lower() if match else None


def _extract_size(body_text: str) -> int | None:
    match = _SIZE_RE.search(body_text or "")
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _extract_body_filename(body_text: str) -> str | None:
    for regex in (_ATTACHMENT_RE, _FILENAME_RE):
        match = regex.search(body_text or "")
        if match:
            return match.group(1).strip()
    return None


def _is_versioned_target(target: DownloadTarget) -> bool:
    return str(target.mode or "").casefold() == "versioned_archive"


def _post_prefix(target: DownloadTarget) -> str:
    if _is_versioned_target(target):
        return f"[BoardRepo] {target.display_name}_"
    if target.target_key == "Ext":
        return "[BoardRepo][Ext] "
    return "[BoardRepo] "


def _normalize_dom_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _compact_dom_text(value: str) -> str:
    # Used only for BoardRepo version-title parsing. textContent normally does
    # not contain CSS wrapping line breaks, but this also protects against
    # markup that inserts whitespace inside a visible YYMMDD token.
    return re.sub(r"\s+", "", str(value or ""))


def _dom_anchor_snapshot(page) -> list[dict]:
    """
    Read anchors in one browser-side evaluation.

    Prefer textContent over innerText. The groupware visually wraps long titles
    in the 제목 column; innerText can therefore contain visual line breaks such
    as '26080\\n8_2', while textContent preserves the logical title string.
    """
    try:
        rows = page.evaluate(
            """() => Array.from(document.querySelectorAll('a[href]')).map(a => ({
                text: ((a.textContent || a.getAttribute('aria-label') ||
                        a.getAttribute('title') || a.innerText || '') + '').trim(),
                href: a.href || a.getAttribute('href') || ''
            }))"""
        )
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def _dom_board_row_snapshot(page) -> list[dict]:
    """
    Read board table rows title-first.

    A row is the stable unit visible to the user: 번호 / 제목 / 작성자 / 작성일.
    We specifically capture the cell containing '[BoardRepo]' and any links
    inside that cell, rather than assuming that the visible title itself is the
    direct text node of an <a>.
    """
    try:
        rows = page.evaluate(
            """() => Array.from(document.querySelectorAll('tr')).map(tr => {
                const cells = Array.from(tr.querySelectorAll('td'));
                const titleCell = cells.find(td =>
                    ((td.textContent || '') + '').includes('[BoardRepo]')
                ) || null;

                const titleAnchors = titleCell
                    ? Array.from(titleCell.querySelectorAll('a[href]')).map(a => ({
                        text: ((a.textContent || a.getAttribute('aria-label') ||
                                a.getAttribute('title') || a.innerText || '') + '').trim(),
                        href: a.href || a.getAttribute('href') || ''
                    }))
                    : [];

                const rowAnchors = Array.from(tr.querySelectorAll('a[href]')).map(a => ({
                    text: ((a.textContent || a.getAttribute('aria-label') ||
                            a.getAttribute('title') || a.innerText || '') + '').trim(),
                    href: a.href || a.getAttribute('href') || ''
                }));

                return {
                    text: ((tr.textContent || '') + '').trim(),
                    cellTexts: cells.map(td => ((td.textContent || '') + '').trim()),
                    titleText: titleCell ? ((titleCell.textContent || '') + '').trim() : '',
                    titleAnchors,
                    rowAnchors
                };
            })"""
        )
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def _postish_href(href: str) -> bool:
    href = str(href or "")
    return "/post/" in href and "/post/write" not in href


def _postish_anchor_count(anchor_rows: list[dict]) -> int:
    return sum(1 for row in anchor_rows if _postish_href(row.get("href", "")))


def _valid_release_matches(text_value: str) -> list[re.Match]:
    compact = _compact_dom_text(text_value)
    matches = []
    for match in re.finditer(r"(?<!\d)(\d{6})(?:_(\d+))?", compact):
        if _valid_yymmdd(match.group(1)):
            matches.append(match)
    return matches


def _canonical_versioned_board_title(
    target: DownloadTarget,
    value: str,
) -> str | None:
    """
    Extract one valid versioned BoardRepo title from a possibly wrapped cell.

    Example visual text:
      [BoardRepo] SignalExport_Signal_Export_V2_26080
      8_2

    becomes:
      [BoardRepo] SignalExport_Signal_Export_V2_260808_2
    """
    compact = _compact_dom_text(value)
    prefix = _compact_dom_text(f"[BoardRepo] {target.display_name}_")
    pos = compact.find(prefix)
    if pos < 0:
        return None

    tail = compact[pos:]
    matches = _valid_release_matches(tail)
    if not matches:
        return None

    # The package Release date/counter is the final valid release token in the
    # title. This mirrors the upload filename's trailing YYMMDD[_N] convention.
    match = matches[-1]
    title_compact = tail[:match.end()]
    return "[BoardRepo] " + title_compact[len("[BoardRepo]"):]



def _canonical_ext_board_title(value: str) -> str | None:
    normalized = _normalize_dom_text(value)
    prefix = "[BoardRepo][Ext]"
    pos = normalized.find(prefix)
    if pos < 0:
        return None

    tail = normalized[pos:]
    rest = tail[len(prefix):].strip()
    if not rest:
        return None

    # Prefer the exact title cell/anchor text. This intentionally does not
    # impose an extension whitelist because Ext is the general-file board.
    return f"[BoardRepo][Ext] {rest}"


def _canonical_title_from_text(
    target: DownloadTarget,
    value: str,
) -> str | None:
    if _is_versioned_target(target):
        return _canonical_versioned_board_title(target, value)
    if target.target_key == "Ext":
        return _canonical_ext_board_title(value)
    return None


def _row_title_and_href(
    target: DownloadTarget,
    row: dict,
    page_url: str,
) -> tuple[str, str] | None:
    """
    Extract a canonical title first, then resolve its post link from the same
    row. The title is authoritative for remote version selection.
    """
    candidate_texts: list[str] = []

    for anchor in row.get("titleAnchors") or []:
        candidate_texts.append(str(anchor.get("text") or ""))

    title_text = str(row.get("titleText") or "")
    if title_text:
        candidate_texts.append(title_text)

    for cell_text in row.get("cellTexts") or []:
        if "[BoardRepo]" in str(cell_text):
            candidate_texts.append(str(cell_text))

    title = None
    for value in candidate_texts:
        title = _canonical_title_from_text(target, value)
        if title:
            break

    if not title:
        return None

    href = ""
    for group_name in ("titleAnchors", "rowAnchors"):
        for anchor in row.get(group_name) or []:
            candidate_href = str(anchor.get("href") or "").strip()
            if _postish_href(candidate_href):
                href = urljoin(page_url, candidate_href)
                break
        if href:
            break

    # Keep a recognized title even if the site uses a JS click handler instead
    # of a normal href. _open_candidate_post has a row-click fallback.
    return title, href


def _body_title_candidates(
    body_text: str,
    target: DownloadTarget,
) -> list[str]:
    """
    Last-resort title extraction from the full body.

    We scan a few neighboring lines at a time because visual wrapping can split
    one title over multiple lines. Only titles that pass the target's canonical
    parser are returned.
    """
    lines = [line.strip() for line in (body_text or "").splitlines()]
    found: list[str] = []
    seen: set[str] = set()

    for idx in range(len(lines)):
        for width in (1, 2, 3):
            chunk = "".join(lines[idx:idx + width])
            if "[BoardRepo]" not in chunk:
                continue
            title = _canonical_title_from_text(target, chunk)
            if title and title not in seen:
                seen.add(title)
                found.append(title)

    return found


def _board_readiness_snapshot(
    page,
    target: DownloadTarget,
) -> tuple[int, int, int, bool, str]:
    anchors = _dom_anchor_snapshot(page)
    rows = _dom_board_row_snapshot(page)
    body = _page_body_text(page)

    boardrepo_rows = 0
    for row in rows:
        if _row_title_and_href(target, row, page.url) is not None:
            boardrepo_rows += 1

    return (
        len(anchors),
        _postish_anchor_count(anchors),
        len(rows),
        boardrepo_rows > 0 or "[BoardRepo]" in body,
        body,
    )


def _wait_for_board_list_ready(
    page,
    target: DownloadTarget,
    config: dict,
    log: Callable[[str], None],
    page_no: int,
) -> tuple[int, int, int, bool]:
    download_cfg = config.get("download") or {}
    timeout_seconds = max(
        0.5,
        float(download_cfg.get("board_ready_timeout_seconds", 10)),
    )
    poll_ms = max(100, int(download_cfg.get("board_ready_poll_ms", 500)))
    diagnostic = bool(download_cfg.get("diagnostic_logging", True))

    import time
    started = time.monotonic()
    attempt = 0
    last_snapshot = (-1, -1, -1, False)

    while True:
        attempt += 1
        anchor_count, postish_count, row_count, boardrepo_seen, _body = (
            _board_readiness_snapshot(page, target)
        )
        snapshot = (
            anchor_count,
            postish_count,
            row_count,
            boardrepo_seen,
        )
        elapsed = time.monotonic() - started

        if diagnostic and (attempt == 1 or snapshot != last_snapshot):
            log(
                f"게시글 목록 대기 [{target.display_name}] "
                f"{page_no}페이지 {attempt}차: "
                f"link={anchor_count}, post-link={postish_count}, "
                f"row={row_count}, "
                f"BoardRepo표시={'있음' if boardrepo_seen else '없음'}"
            )

        # A real table row is the preferred ready signal. postish links remain
        # a compatibility signal for alternate board markup.
        if boardrepo_seen or postish_count > 0:
            log(
                f"게시글 목록 준비 [{target.display_name}] "
                f"{page_no}페이지: {elapsed:.1f}초 "
                f"(row={row_count}, post-link={postish_count}, "
                f"BoardRepo표시={'있음' if boardrepo_seen else '없음'})"
            )
            return anchor_count, postish_count, row_count, boardrepo_seen

        if elapsed >= timeout_seconds:
            log(
                f"게시글 목록 대기 제한시간 [{target.display_name}] "
                f"{page_no}페이지: {elapsed:.1f}초. "
                "현재 DOM 기준으로 제목 행 탐색을 계속합니다."
            )
            return anchor_count, postish_count, row_count, boardrepo_seen

        last_snapshot = snapshot
        page.wait_for_timeout(poll_ms)


def _scan_current_board_page(
    page,
    target: DownloadTarget,
    config: dict,
    log: Callable[[str], None],
    page_no: int,
) -> list[tuple[str, str]]:
    download_cfg = config.get("download") or {}
    retries = max(1, int(download_cfg.get("empty_scan_retries", 3)))
    retry_ms = max(100, int(download_cfg.get("empty_scan_retry_ms", 1000)))
    use_fallback = bool(download_cfg.get("dom_fallback_enabled", True))
    diagnostic = bool(download_cfg.get("diagnostic_logging", True))

    for attempt in range(1, retries + 1):
        rows = _dom_board_row_snapshot(page)
        direct: list[tuple[str, str]] = []
        invalid_boardrepo_rows = 0
        seen: set[tuple[str, str]] = set()

        for row in rows:
            row_text = str(row.get("text") or "")
            has_boardrepo = "[BoardRepo]" in row_text
            parsed = _row_title_and_href(target, row, page.url)

            if parsed is None:
                if has_boardrepo:
                    invalid_boardrepo_rows += 1
                continue

            title, href = parsed
            # A title alone is useful: if href is absent, detail navigation can
            # still click the matching board row later.
            key = (title, href)
            if key not in seen:
                seen.add(key)
                direct.append(key)

        fallback: list[tuple[str, str]] = []
        body_titles: list[str] = []

        if use_fallback and not direct:
            body = _page_body_text(page)
            body_titles = _body_title_candidates(body, target)
            for title in body_titles:
                key = (title, "")
                if key not in seen:
                    seen.add(key)
                    fallback.append(key)

        combined = direct + fallback

        if diagnostic:
            log(
                f"게시글 제목 탐색 [{target.display_name}] "
                f"{page_no}페이지 {attempt}/{retries}: "
                f"row={len(rows)}, 정상제목={len(combined)}, "
                f"비정상BoardRepo={invalid_boardrepo_rows}, "
                f"본문보조={len(fallback)}"
            )

        if invalid_boardrepo_rows:
            log(
                f"비정상 BoardRepo 게시글 제외 [{target.display_name}]: "
                f"{invalid_boardrepo_rows}건"
            )

        if combined:
            return combined

        if attempt < retries:
            log(
                f"정상 BoardRepo 게시글 제목 0건 [{target.display_name}] "
                f"{page_no}페이지 - {retry_ms / 1000:.1f}초 후 재확인"
            )
            page.wait_for_timeout(retry_ms)

    return []


def _scan_post_links(
    page,
    target: DownloadTarget,
    config: dict,
    site_profile: dict,
    log: Callable[[str], None],
) -> list[tuple[str, str]]:
    """
    Board-row/title-first discovery.

    The title shown in the 게시판의 '제목' column is the source of truth for
    deciding which remote post is latest. Only after selecting the post by its
    title do we enter the post and inspect/download the attachment.
    """
    download_cfg = config.get("download") or {}
    max_pages = max(1, int(download_cfg.get("max_board_pages", 10)))
    wait_ms = int(download_cfg.get("page_wait_ms", 500))

    page.goto(target.board_url, wait_until="domcontentloaded")
    _stage_stabilize(page, site_profile, log, "board")
    _wait_for_board_list_ready(page, target, config, log, 1)

    found: list[tuple[str, str]] = []
    seen_titles: set[tuple[str, str]] = set()
    seen_pages: set[str] = set()

    for page_no in range(1, max_pages + 1):
        signature = _page_signature(page)
        if signature in seen_pages:
            break
        seen_pages.add(signature)

        page_found = _scan_current_board_page(
            page,
            target,
            config,
            log,
            page_no,
        )

        for title, href in page_found:
            # If the same title is found through a stronger href-bearing row
            # and a weaker body fallback, keep the href-bearing copy.
            title_key = title.casefold()
            existing_index = next(
                (
                    idx
                    for idx, (t, _h) in enumerate(found)
                    if t.casefold() == title_key
                ),
                None,
            )
            if existing_index is None:
                found.append((title, href))
            elif href and not found[existing_index][1]:
                found[existing_index] = (title, href)

        if page_no >= max_pages:
            break

        next_control = _find_next_page_control(
            page,
            config.get("remote_duplicate_check") or {},
        )
        if next_control is None:
            break

        before = _page_signature(page)
        try:
            next_control.scroll_into_view_if_needed()
            next_control.click()
            page.wait_for_timeout(wait_ms)
            _wait_for_board_list_ready(
                page,
                target,
                config,
                log,
                page_no + 1,
            )
        except Exception as exc:
            log(
                f"다음 페이지 이동 실패 [{target.display_name}] "
                f"{page_no}페이지: {exc}"
            )
            break

        after = _page_signature(page)
        if after == before:
            break

    log(
        f"원격 제목 수집 [{target.display_name}]: "
        f"정상 BoardRepo 게시글 {len(found)}건"
    )
    return found


def _versioned_title_release(
    target: DownloadTarget,
    title: str,
) -> tuple[str, str, int] | None:
    canonical = _canonical_versioned_board_title(target, title)
    if not canonical:
        return None

    compact = _compact_dom_text(canonical)
    prefix = _compact_dom_text(f"[BoardRepo] {target.display_name}_")
    tail = compact[len(prefix):]
    matches = _valid_release_matches(tail)
    if not matches:
        return None

    match = matches[-1]
    date_token = match.group(1)
    counter = int(match.group(2)) if match.group(2) else 0
    family = tail[:match.start()].rstrip("_-")
    return family or target.display_name, date_token, counter


def _candidate_from_title(
    target: DownloadTarget,
    title: str,
    post_url: str,
) -> RemotePost | None:
    if _is_versioned_target(target):
        parsed = _versioned_title_release(target, title)
        if parsed is None:
            return None
        family, date_token, counter = parsed
        canonical = _canonical_versioned_board_title(target, title)
        return RemotePost(
            title=canonical or title,
            post_url=post_url,
            filename="",
            kind="versioned",
            family=family,
            date_token=date_token,
            counter=counter,
        )

    if target.target_key == "Ext":
        canonical = _canonical_ext_board_title(title)
        if not canonical:
            return None
        filename = canonical[len("[BoardRepo][Ext] "):].strip()
        if not filename:
            return None
        return RemotePost(
            title=canonical,
            post_url=post_url,
            filename=filename,
            kind="ext",
        )

    return None


def _select_remote_candidates(
    target: DownloadTarget,
    links: list[tuple[str, str]],
    log: Callable[[str], None],
) -> list[RemotePost]:
    raw: list[RemotePost] = []
    invalid = 0

    for title, url in links:
        candidate = _candidate_from_title(target, title, url)
        if candidate is None:
            invalid += 1
            continue
        raw.append(candidate)

    if invalid:
        log(
            f"원격 제목 버전 해석 제외 [{target.display_name}]: "
            f"{invalid}건"
        )

    if _is_versioned_target(target):
        if not raw:
            return []
        best = max(raw, key=lambda x: _release_key(x.date_token, x.counter))
        log(
            f"원격 최신 글 [{target.display_name}]: "
            f"{best.title} "
            f"(Release={best.date_token}_{best.counter})"
        )
        return [best]


    if target.target_key == "Ext":
        # Ext intentionally processes every valid standard Ext post. Local
        # filename + SHA comparison later decides download/skip/conflict.
        log(
            f"Ext 원격 대상: 유효한 BoardRepo Ext 게시글 전체 "
            f"{len(raw)}건"
        )
        return raw

    return []


def _row_contains_candidate_title(row_text: str, candidate_title: str) -> bool:
    compact_row = _compact_dom_text(row_text)
    compact_title = _compact_dom_text(candidate_title)
    return compact_title in compact_row


def _open_candidate_post(
    page,
    target: DownloadTarget,
    candidate: RemotePost,
    config: dict,
    site_profile: dict,
    log: Callable[[str], None],
) -> str:
    """
    Shared board-row navigation used by both download and Ext upload duplicate
    verification.
    """
    return open_board_post_by_title(
        page,
        board_url=target.board_url,
        expected_title=candidate.title,
        config=config.get("download") or {},
        site_profile=site_profile,
        log=log,
        display_name=target.display_name,
        known_post_url=candidate.post_url or None,
    )


def _validate_attachment_against_title(
    target: DownloadTarget,
    candidate: RemotePost,
    filename: str,
) -> None:
    if _is_versioned_target(target):
        if Path(filename).suffix.casefold() not in _ARCHIVE_EXTS:
            raise BrowserAutomationError(
                f"최신 글의 첨부파일이 압축파일이 아닙니다: {filename}"
            )

        parsed = parse_release_identity(filename)
        if parsed is None:
            raise BrowserAutomationError(
                "최신 글 제목은 Release 형식이지만 첨부파일명에서 "
                f"YYMMDD/_N을 해석할 수 없습니다: {filename}"
            )

        _family, date_token, counter = parsed
        if (
            date_token != candidate.date_token
            or counter != candidate.counter
        ):
            raise BrowserAutomationError(
                "최신 글 제목과 첨부파일 Release가 일치하지 않습니다. "
                f"제목={candidate.date_token}_{candidate.counter}, "
                f"첨부={date_token}_{counter}, 파일={filename}"
            )
        return


    if target.target_key == "Ext":
        if filename.casefold() != candidate.filename.casefold():
            raise BrowserAutomationError(
                "Ext 게시글 제목의 파일명과 실제 첨부파일명이 다릅니다. "
                f"제목={candidate.filename}, 첨부={filename}"
            )



def _visible_attachment_filename(
    page,
    target: DownloadTarget,
    candidate: RemotePost,
) -> str | None:
    """Best-effort filename from rendered attachment/download elements."""
    expected = (candidate.filename or "").strip()

    try:
        rows = page.evaluate(
            """() => Array.from(document.querySelectorAll(
                'a, button, [role="button"], [title]'
            )).map(el => ({
                text: ((el.textContent || el.getAttribute('aria-label') ||
                        el.getAttribute('title') || '') + '').trim(),
                title: (el.getAttribute('title') || '').trim()
            }))"""
        )
    except Exception:
        rows = []

    values: list[str] = []
    for row in rows if isinstance(rows, list) else []:
        for raw in (row.get("text", ""), row.get("title", "")):
            value = _normalize_dom_text(raw)
            if value and value not in values:
                values.append(value)

    if expected:
        for value in values:
            if value.casefold() == expected.casefold():
                return value
            if expected.casefold() in value.casefold():
                # Some groupware attachment widgets combine filename and size.
                return expected

    if _is_versioned_target(target):
        for value in values:
            # Use only a filename-like token. Release validation later ensures
            # that it matches the selected post title.
            for token in re.split(r"\s+", value):
                token = token.strip("()[]{}<>,;\"'")
                if Path(token).suffix.casefold() in _ARCHIVE_EXTS:
                    return token

    return None


def _wait_for_detail_metadata(
    page,
    target: DownloadTarget,
    candidate: RemotePost,
    config: dict,
    log: Callable[[str], None],
) -> tuple[str | None, str, str | None, int | None]:
    """
    Wait for async detail content after the post URL has already opened.

    The groupware can update /post/<id> before the body and attachment area is
    rendered. Treat URL navigation and detail-content readiness as separate.
    """
    import time

    download_cfg = config.get("download") or {}
    timeout_seconds = max(
        0.5,
        float(download_cfg.get("detail_ready_timeout_seconds", 8)),
    )
    poll_ms = max(
        100,
        int(download_cfg.get("detail_ready_poll_ms", 250)),
    )
    ext_sha_grace_ms = max(
        0,
        int(download_cfg.get("ext_sha_ready_grace_ms", 1000)),
    )
    diagnostic = bool(download_cfg.get("diagnostic_logging", True))

    deadline = time.monotonic() + timeout_seconds
    first_filename_at: float | None = None
    attempt = 0
    last_state = None
    body = ""
    filename: str | None = None
    sha_value: str | None = None
    size_value: int | None = None

    while True:
        attempt += 1
        body = _page_body_text(page)

        # candidate.filename comes from the title for Ext. It is not
        # proof of the actual attachment. Observe body/attachment DOM first.
        body_filename = _extract_body_filename(body)
        visible_filename = _visible_attachment_filename(page, target, candidate)
        filename = body_filename or visible_filename
        sha_value = _extract_sha(body)
        size_value = _extract_size(body)

        if filename and first_filename_at is None:
            first_filename_at = time.monotonic()

        sha_needed = (
            target.target_key == "Ext"
            and bool(download_cfg.get("verify_ext_sha256", True))
        )
        sha_grace_done = (
            not sha_needed
            or sha_value is not None
            or (
                first_filename_at is not None
                and (time.monotonic() - first_filename_at) * 1000
                >= ext_sha_grace_ms
            )
        )
        ready = bool(filename) and sha_grace_done

        state = (bool(filename), bool(sha_value), len(body))
        if diagnostic and (attempt == 1 or state != last_state or ready):
            log(
                f"상세 콘텐츠 대기 [{target.display_name}] {attempt}차: "
                f"첨부명={'있음' if filename else '없음'}, "
                f"SHA={'있음' if sha_value else '없음'}, "
                f"본문길이={len(body)}"
            )

        if ready:
            log(
                f"상세 콘텐츠 Ready [{target.display_name}]: "
                f"첨부={filename}"
                + (f", SHA={sha_value[:12]}..." if sha_value else "")
            )
            return filename, body, sha_value, size_value

        if time.monotonic() >= deadline:
            log(
                f"상세 콘텐츠 대기 종료 [{target.display_name}]: "
                f"{timeout_seconds:.1f}초, "
                f"첨부명={'있음' if filename else '없음'}, "
                f"SHA={'있음' if sha_value else '없음'}"
            )
            return filename, body, sha_value, size_value

        last_state = state
        page.wait_for_timeout(poll_ms)


def _inspect_post_detail(
    page,
    target: DownloadTarget,
    candidate: RemotePost,
    config: dict,
    site_profile: dict,
    log: Callable[[str], None],
) -> RemotePost:
    detail_url = _open_candidate_post(
        page,
        target,
        candidate,
        config,
        site_profile,
        log,
    )

    filename, body, sha_value, size_value = _wait_for_detail_metadata(
        page,
        target,
        candidate,
        config,
        log,
    )

    if not filename:
        raise BrowserAutomationError(
            f"{target.display_name} 선택 게시글의 상세 콘텐츠가 준비된 뒤에도 "
            f"첨부파일명을 확인하지 못했습니다: {candidate.title}"
        )

    filename = _safe_filename(filename)

    if (config.get("download") or {}).get(
        "validate_attachment_against_title",
        True,
    ):
        _validate_attachment_against_title(
            target,
            candidate,
            filename,
        )

    log(
        f"게시글 상세 확인 [{target.display_name}]: "
        f"{candidate.title} → 실제 첨부 {filename}"
    )

    return RemotePost(
        title=candidate.title,
        post_url=detail_url,
        filename=filename,
        kind=candidate.kind,
        family=candidate.family,
        date_token=candidate.date_token,
        counter=candidate.counter,
        sha256=sha_value,
        size_bytes=size_value,
    )

def _local_versioned_latest(
    target: DownloadTarget,
    config: dict,
):
    allowed = {
        ext.casefold() if ext.startswith(".") else f".{ext.casefold()}"
        for ext in config.get("archive_selection", {}).get(
            "extensions", [".zip", ".7z", ".rar"]
        )
    }

    try:
        selection = select_latest_archive(
            folder=target.folder,
            target_name=target.display_name,
            aliases=target.aliases,
            extensions=allowed,
            strategy="date_counter_release",
        )
        return selection.selected
    except ArchiveSelectionError as exc:
        # An empty local folder is a normal first-download case. Other parsing
        # ambiguity must remain a conflict instead of being silently ignored.
        if "없습니다" in exc.reason:
            return None
        raise


def _download_attachment(
    page,
    remote: RemotePost,
    folder: Path,
    config: dict,
    log: Callable[[str], None],
) -> Path:
    filename = _safe_filename(remote.filename)
    destination = folder / filename
    download_cfg = config.get("download") or {}

    if destination.exists() and not download_cfg.get("overwrite_existing", False):
        raise FileExistsError(
            f"기존 파일을 자동 덮어쓰지 않습니다: {destination.name}"
        )

    temp_suffix = str(download_cfg.get("temporary_suffix", ".part"))
    temp_path = folder / f"{filename}{temp_suffix}"
    if temp_path.exists():
        temp_path.unlink()

    page.goto(remote.post_url, wait_until="domcontentloaded")
    page.wait_for_timeout(int(download_cfg.get("post_wait_ms", 500)))

    import time

    ready_timeout_seconds = max(
        0.5,
        float(download_cfg.get("download_control_ready_timeout_seconds", 8)),
    )
    ready_poll_ms = max(
        100,
        int(download_cfg.get("download_control_ready_poll_ms", 250)),
    )
    deadline = time.monotonic() + ready_timeout_seconds
    attempt = 0
    locators = []

    while True:
        attempt += 1
        locators = []

        for role in ("link", "button"):
            try:
                group = page.get_by_role(role, name=filename, exact=True)
                for idx in range(group.count()):
                    loc = group.nth(idx)
                    if loc.is_visible():
                        locators.append(loc)
            except Exception:
                pass

        try:
            group = page.locator("a").filter(has_text=filename)
            for idx in range(group.count()):
                loc = group.nth(idx)
                if loc.is_visible():
                    locators.append(loc)
        except Exception:
            pass

        if not locators:
            try:
                group = page.get_by_text(filename, exact=True)
                for idx in range(group.count()):
                    loc = group.nth(idx)
                    if loc.is_visible():
                        locators.append(loc)
            except Exception:
                pass

        if locators:
            log(
                f"다운로드 요소 Ready: {filename} "
                f"({attempt}차, 후보={len(locators)})"
            )
            break

        if time.monotonic() >= deadline:
            raise BrowserAutomationError(
                "게시글 상세 URL은 열렸지만 첨부파일 다운로드 요소가 "
                f"{ready_timeout_seconds:.1f}초 안에 준비되지 않았습니다: "
                f"{filename}"
            )

        if attempt == 1 or attempt % 4 == 0:
            log(f"다운로드 요소 대기: {filename} ({attempt}차)")
        page.wait_for_timeout(ready_poll_ms)

    timeout_ms = int(download_cfg.get("download_timeout_ms", 30000))
    last_error = None

    for loc in locators:
        try:
            loc.scroll_into_view_if_needed()
            with page.expect_download(timeout=timeout_ms) as info:
                loc.click()
            download = info.value
            download.save_as(str(temp_path))
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            if temp_path.exists():
                temp_path.unlink()

    if last_error is not None or not temp_path.exists():
        raise BrowserAutomationError(
            f"첨부파일 다운로드를 시작/저장하지 못했습니다: {filename} / {last_error}"
        )

    if temp_path.stat().st_size <= 0:
        temp_path.unlink(missing_ok=True)
        raise BrowserAutomationError(f"다운로드 파일 크기가 0입니다: {filename}")

    if (
        download_cfg.get("verify_known_size", True)
        and remote.size_bytes is not None
        and temp_path.stat().st_size != remote.size_bytes
    ):
        actual = temp_path.stat().st_size
        temp_path.unlink(missing_ok=True)
        raise BrowserAutomationError(
            f"다운로드 크기 검증 실패: {filename} "
            f"(원격={remote.size_bytes}, 로컬={actual})"
        )

    if (
        download_cfg.get("verify_ext_sha256", True)
        and remote.sha256 is not None
    ):
        actual_sha = _sha256_file(temp_path)
        if actual_sha.lower() != remote.sha256.lower():
            temp_path.unlink(missing_ok=True)
            raise BrowserAutomationError(
                f"다운로드 SHA-256 검증 실패: {filename}"
            )

    temp_path.rename(destination)
    log(f"다운로드 저장 완료: {destination}")
    return destination


def _version_text(date_token: str | None, counter: int) -> str | None:
    if not date_token:
        return None
    return f"{date_token}_{counter}" if counter else date_token


def _sync_versioned_target(
    page,
    target: DownloadTarget,
    remote: RemotePost,
    config: dict,
    log: Callable[[str], None],
) -> DownloadResult:
    try:
        local = _local_versioned_latest(target, config)
    except (ArchiveSelectionError, Exception) as exc:
        return DownloadResult(
            target.target_key,
            target.display_name,
            STATUS_CONFLICT,
            remote.filename,
            f"로컬 최신 Release를 안전하게 판단할 수 없습니다: {exc}",
            remote_version=_version_text(remote.date_token, remote.counter),
        )

    remote_key = _release_key(remote.date_token, remote.counter)
    remote_text = _version_text(remote.date_token, remote.counter)

    if local is None:
        try:
            _download_attachment(page, remote, target.folder, config, log)
            return DownloadResult(
                target.target_key,
                target.display_name,
                STATUS_DOWNLOADED,
                remote.filename,
                "로컬 파일이 없어 원격 최신 Release를 다운로드했습니다.",
                local_version=None,
                remote_version=remote_text,
            )
        except Exception as exc:
            return DownloadResult(
                target.target_key,
                target.display_name,
                STATUS_ERROR,
                remote.filename,
                str(exc),
                remote_version=remote_text,
            )

    local_key = _release_key(local.date_token, local.counter)
    local_text = _version_text(local.date_token, local.counter)

    if remote_key == local_key:
        return DownloadResult(
            target.target_key,
            target.display_name,
            STATUS_UP_TO_DATE,
            remote.filename,
            "로컬과 원격의 최신 Release가 동일합니다.",
            local_version=local_text,
            remote_version=remote_text,
        )

    if remote_key < local_key:
        return DownloadResult(
            target.target_key,
            target.display_name,
            STATUS_LOCAL_NEWER,
            remote.filename,
            "로컬 Release가 원격보다 더 최신이므로 다운로드하지 않았습니다.",
            local_version=local_text,
            remote_version=remote_text,
        )

    try:
        _download_attachment(page, remote, target.folder, config, log)
        return DownloadResult(
            target.target_key,
            target.display_name,
            STATUS_DOWNLOADED,
            remote.filename,
            "원격 Release가 더 최신이므로 다운로드했습니다.",
            local_version=local_text,
            remote_version=remote_text,
        )
    except Exception as exc:
        return DownloadResult(
            target.target_key,
            target.display_name,
            STATUS_ERROR,
            remote.filename,
            str(exc),
            local_version=local_text,
            remote_version=remote_text,
        )



def _sync_ext_target(
    page,
    target: DownloadTarget,
    remotes: list[RemotePost],
    config: dict,
    log: Callable[[str], None],
) -> list[DownloadResult]:
    results: list[DownloadResult] = []

    for remote in remotes:
        destination = target.folder / remote.filename

        if destination.exists():
            if remote.sha256:
                local_sha = _sha256_file(destination)
                if local_sha.lower() == remote.sha256.lower():
                    results.append(
                        DownloadResult(
                            target.target_key,
                            target.display_name,
                            STATUS_UP_TO_DATE,
                            remote.filename,
                            "파일명과 SHA-256이 동일하여 이미 최신 상태입니다.",
                        )
                    )
                else:
                    results.append(
                        DownloadResult(
                            target.target_key,
                            target.display_name,
                            STATUS_CONFLICT,
                            remote.filename,
                            "같은 파일명이 로컬에 있지만 SHA-256이 달라 자동 덮어쓰지 않습니다.",
                        )
                    )
            else:
                results.append(
                    DownloadResult(
                        target.target_key,
                        target.display_name,
                        STATUS_CONFLICT,
                        remote.filename,
                        "같은 파일명이 로컬에 있으나 원격 SHA-256이 없어 자동 비교/덮어쓰지 않습니다.",
                    )
                )
            continue

        try:
            _download_attachment(page, remote, target.folder, config, log)
            results.append(
                DownloadResult(
                    target.target_key,
                    target.display_name,
                    STATUS_DOWNLOADED,
                    remote.filename,
                    "로컬에 없는 Ext 파일을 다운로드했습니다.",
                )
            )
        except Exception as exc:
            results.append(
                DownloadResult(
                    target.target_key,
                    target.display_name,
                    STATUS_ERROR,
                    remote.filename,
                    str(exc),
                )
            )

    return results


def _discover_detailed_remotes(
    page,
    target: DownloadTarget,
    config: dict,
    site_profile: dict,
    log: Callable[[str], None],
) -> tuple[list[RemotePost], list[DownloadResult]]:
    links = _scan_post_links(page, target, config, site_profile, log)
    selected = _select_remote_candidates(target, links, log)

    detailed: list[RemotePost] = []
    issues: list[DownloadResult] = []

    for candidate in selected:
        try:
            detailed.append(
                _inspect_post_detail(
                    page,
                    target,
                    candidate,
                    config,
                    site_profile,
                    log,
                )
            )
        except Exception as exc:
            reason = (
                f"선택한 게시글은 찾았지만 상세/첨부 확인에 실패했습니다: {exc}"
            )
            issues.append(
                DownloadResult(
                    target.target_key,
                    target.display_name,
                    STATUS_CONFLICT,
                    candidate.filename or candidate.title,
                    reason,
                    remote_version=_version_text(
                        candidate.date_token,
                        candidate.counter,
                    ),
                )
            )
            log(
                f"원격 게시글 상세 확인 필요 [{target.display_name}] "
                f"{candidate.title}: {exc}"
            )

    return detailed, issues


def sync_selected_downloads(
    targets: list[DownloadTarget],
    browser_profile: Path,
    config: dict,
    site_profile: dict,
    log: Callable[[str], None],
) -> list[DownloadResult]:
    if not targets:
        return []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserAutomationError(
            "playwright가 설치되지 않았습니다. GUI의 필수 모듈 설치/복구를 실행하세요."
        ) from exc

    browser_profile.mkdir(parents=True, exist_ok=True)
    browser_cfg = config["browser"]
    results: list[DownloadResult] = []

    with sync_playwright() as p:
        log("BoardRepo 다운로드 브라우저를 실행합니다.")
        context, browser_choice = launch_persistent_context_auto(
            p,
            browser_profile,
            config,
            log,
            purpose="download",
            accept_downloads=True,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(int(browser_cfg.get("operation_timeout_ms", 15000)))

        try:
            first = targets[0]
            page.goto(first.board_url, wait_until="domcontentloaded")

            if _looks_like_login_page(page, site_profile):
                log("다운로드 전 로그인이 필요한 상태를 확인했습니다.")
                _wait_until_logged_in(
                    page,
                    first.board_url,
                    site_profile,
                    int(browser_cfg.get("login_wait_seconds", 180)),
                    log,
                )
                log("다운로드 로그인 완료 상태를 확인했습니다.")
                _stage_stabilize(page, site_profile, log, "login")
            else:
                log("다운로드에서 기존 로그인 세션을 사용합니다.")
                _stage_stabilize(page, site_profile, log, "login")

            for target in targets:
                try:
                    _ensure_community_context(
                        page,
                        target.board_url,
                        site_profile,
                        log,
                    )
                    remotes, discovery_issues = _discover_detailed_remotes(
                        page,
                        target,
                        config,
                        site_profile,
                        log,
                    )
                    results.extend(discovery_issues)

                    if not remotes:
                        if not discovery_issues:
                            results.append(
                                DownloadResult(
                                    target.target_key,
                                    target.display_name,
                                    STATUS_REMOTE_NONE,
                                    None,
                                    "검색 범위에서 유효한 BoardRepo 게시글 제목을 찾지 못했습니다.",
                                )
                            )
                        continue

                    if _is_versioned_target(target):
                        results.append(
                            _sync_versioned_target(
                                page,
                                target,
                                remotes[0],
                                config,
                                log,
                            )
                        )

                    elif target.target_key == "Ext":
                        results.extend(
                            _sync_ext_target(
                                page,
                                target,
                                remotes,
                                config,
                                log,
                            )
                        )
                except Exception as exc:
                    results.append(
                        DownloadResult(
                            target.target_key,
                            target.display_name,
                            STATUS_ERROR,
                            None,
                            f"{type(exc).__name__}: {exc}",
                        )
                    )
                    log(
                        f"다운로드 항목 오류 [{target.display_name}]: "
                        f"{type(exc).__name__}: {exc}"
                    )

        finally:
            context.close()

    return results
