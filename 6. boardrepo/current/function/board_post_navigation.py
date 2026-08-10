from __future__ import annotations

import re
import time
from typing import Callable
from urllib.parse import urljoin

from browser_automation import (
    BrowserAutomationError,
    _page_body_text,
    _stage_stabilize,
)


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).casefold()


def _is_post_detail_url(url: str) -> bool:
    value = str(url or "")
    return "/post/" in value and "/post/write" not in value


def _title_matches(value: str, expected_title: str) -> bool:
    expected = _compact_text(expected_title)
    actual = _compact_text(value)
    return bool(expected) and expected in actual


def _wait_for_post_detail(
    page,
    expected_title: str,
    timeout_seconds: float,
    poll_ms: int,
) -> bool:
    deadline = time.monotonic() + max(0.5, float(timeout_seconds))

    while time.monotonic() < deadline:
        if _is_post_detail_url(page.url):
            return True

        body = _page_body_text(page)
        if expected_title and _title_matches(body, expected_title):
            # Some SPA implementations can keep a non-detail URL while replacing
            # the board area with the selected post. Accept this only if list
            # column headers are no longer the dominant page state.
            compact_body = _compact_text(body)
            if not (
                "번호제목작성자작성일" in compact_body
                and "[boardrepo]" in compact_body
            ):
                return True

        page.wait_for_timeout(poll_ms)

    return _is_post_detail_url(page.url)


def _matching_rows(page, expected_title: str):
    matches = []
    try:
        rows = page.locator("tr")
        count = rows.count()
    except Exception:
        return matches

    for idx in range(count):
        row = rows.nth(idx)
        try:
            text = row.evaluate("el => (el.textContent || '')")
        except Exception:
            continue
        if _title_matches(text, expected_title):
            matches.append(row)

    return matches


def _try_row_post_link(
    page,
    row,
    expected_title: str,
    wait_seconds: float,
    poll_ms: int,
    log: Callable[[str], None],
) -> str | None:
    try:
        anchors = row.locator("a[href]")
        count = anchors.count()
    except Exception:
        return None

    for idx in range(count):
        anchor = anchors.nth(idx)
        try:
            href = anchor.get_attribute("href") or ""
        except Exception:
            continue

        if not _is_post_detail_url(href):
            continue

        absolute = urljoin(page.url, href)
        try:
            # Direct navigation is deterministic when a real detail href exists.
            page.goto(absolute, wait_until="domcontentloaded")
            if _wait_for_post_detail(
                page,
                expected_title,
                wait_seconds,
                poll_ms,
            ):
                log(f"게시글 상세 진입 성공: 실제 post href 사용 ({page.url})")
                return page.url
        except Exception:
            continue

    return None


def _try_title_cell_click(
    page,
    row,
    expected_title: str,
    wait_seconds: float,
    poll_ms: int,
    log: Callable[[str], None],
) -> str | None:
    try:
        cells = row.locator("td")
        count = cells.count()
    except Exception:
        return None

    for idx in range(count):
        cell = cells.nth(idx)
        try:
            text = cell.evaluate("el => (el.textContent || '')")
        except Exception:
            continue

        if not _title_matches(text, expected_title):
            continue

        try:
            cell.scroll_into_view_if_needed()
            cell.click()
            if _wait_for_post_detail(
                page,
                expected_title,
                wait_seconds,
                poll_ms,
            ):
                log(f"게시글 상세 진입 성공: 제목 셀 클릭 ({page.url})")
                return page.url
        except Exception:
            continue

    return None


def _try_visible_title_click(
    page,
    expected_title: str,
    wait_seconds: float,
    poll_ms: int,
    log: Callable[[str], None],
) -> str | None:
    groups = []

    try:
        groups.append(page.get_by_role("link", name=expected_title, exact=True))
    except Exception:
        pass

    try:
        groups.append(page.get_by_text(expected_title, exact=True))
    except Exception:
        pass

    for group in groups:
        try:
            count = group.count()
        except Exception:
            continue

        for idx in range(count):
            loc = group.nth(idx)
            try:
                if not loc.is_visible():
                    continue
                loc.scroll_into_view_if_needed()
                loc.click()
                if _wait_for_post_detail(
                    page,
                    expected_title,
                    wait_seconds,
                    poll_ms,
                ):
                    log(f"게시글 상세 진입 성공: 정확 제목 요소 클릭 ({page.url})")
                    return page.url
            except Exception:
                continue

    return None


def open_board_post_by_title(
    page,
    *,
    board_url: str,
    expected_title: str,
    config: dict,
    site_profile: dict,
    log: Callable[[str], None],
    display_name: str,
    known_post_url: str | None = None,
) -> str:
    """
    Open a board post by the exact logical BoardRepo title.

    Navigation order:
      1. known /post/ URL, if available
      2. matching board row -> real /post/ href
      3. matching board row -> title cell click
      4. exact visible title element click

    The row/title matching ignores visual whitespace wrapping. This is the same
    behavior needed by both board-to-local download and Ext upload duplicate
    SHA verification.
    """
    wait_seconds = float(
        config.get(
            "detail_navigation_timeout_seconds",
            config.get("board_ready_timeout_seconds", 8),
        )
    )
    poll_ms = max(
        100,
        int(
            config.get(
                "detail_navigation_poll_ms",
                config.get("board_ready_poll_ms", 250),
            )
        ),
    )
    page_wait_ms = max(
        0,
        int(config.get("post_wait_ms", config.get("page_wait_ms", 500))),
    )

    if known_post_url and _is_post_detail_url(known_post_url):
        try:
            page.goto(known_post_url, wait_until="domcontentloaded")
            page.wait_for_timeout(page_wait_ms)
            _stage_stabilize(page, site_profile, log, "board")
            if _wait_for_post_detail(
                page,
                expected_title,
                wait_seconds,
                poll_ms,
            ):
                log(
                    f"게시글 상세 진입 [{display_name}]: "
                    f"기존 post URL 사용 ({page.url})"
                )
                return page.url
        except Exception as exc:
            log(
                f"기존 post URL 진입 실패 [{display_name}]: "
                f"{type(exc).__name__}: {exc}"
            )

    # Re-enter the board before row/cell fallback so the DOM is predictable.
    page.goto(board_url, wait_until="domcontentloaded")
    _stage_stabilize(page, site_profile, log, "board")

    deadline = time.monotonic() + max(0.5, wait_seconds)
    attempt = 0

    while time.monotonic() < deadline:
        attempt += 1
        rows = _matching_rows(page, expected_title)

        log(
            f"게시글 상세 탐색 [{display_name}] {attempt}차: "
            f"제목 일치 행={len(rows)}"
        )

        for row in rows:
            opened = _try_row_post_link(
                page,
                row,
                expected_title,
                wait_seconds,
                poll_ms,
                log,
            )
            if opened:
                return opened

            # A failed attempt may have changed the page. If so, restore the board
            # before trying the cell-click fallback on a fresh locator.
            if not page.url.startswith(board_url):
                page.goto(board_url, wait_until="domcontentloaded")
                _stage_stabilize(page, site_profile, log, "board")
                rows = _matching_rows(page, expected_title)
                if not rows:
                    break
                row = rows[0]

            opened = _try_title_cell_click(
                page,
                row,
                expected_title,
                wait_seconds,
                poll_ms,
                log,
            )
            if opened:
                return opened

            if not page.url.startswith(board_url):
                page.goto(board_url, wait_until="domcontentloaded")
                _stage_stabilize(page, site_profile, log, "board")

        opened = _try_visible_title_click(
            page,
            expected_title,
            wait_seconds,
            poll_ms,
            log,
        )
        if opened:
            return opened

        page.wait_for_timeout(poll_ms)

    raise BrowserAutomationError(
        f"게시판에서 정확한 제목의 상세 글을 열지 못했습니다: {expected_title}"
    )
