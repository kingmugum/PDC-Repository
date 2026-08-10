from __future__ import annotations

import time
from html import escape as html_escape
from pathlib import Path
from urllib.parse import urlparse
from typing import Callable, Iterable

from credential_store import load_credentials
from site_profile import write_url_for


class BrowserAutomationError(RuntimeError):
    pass



def _stage_stabilize(
    page,
    profile: dict,
    log: Callable[[str], None],
    stage: str,
    override_ms: int | None = None,
):
    """
    Small post-readiness settle period.

    This is intentionally NOT the primary wait mechanism. The primary mechanism
    is always a concrete readiness condition. The settle only gives a SPA/editor
    a short window to finish follow-up DOM work after the condition first becomes
    true.
    """
    cfg = profile.get("readiness") or {}
    stage_map = cfg.get("stage_stabilize_ms") or {}

    if override_ms is None:
        ms = int(stage_map.get(stage, cfg.get("default_stabilize_ms", 450)))
    else:
        ms = int(override_ms)

    if ms <= 0:
        return

    log(f"단계 안정화 대기: {stage} ({ms / 1000:.2f}초)")
    page.wait_for_timeout(ms)



def _first_visible(page_or_frame, selectors: Iterable[str]):
    for selector in selectors:
        try:
            locator = page_or_frame.locator(selector).first
            if locator.count() and locator.is_visible():
                return locator
        except Exception:
            continue
    return None


def _looks_like_login_page(page, profile: dict) -> bool:
    try:
        password = _first_visible(page, profile["login"]["password_candidates"])
        return password is not None
    except Exception:
        return "login" in page.url.lower()


def _looks_like_write_page(page, profile: dict) -> bool:
    """
    A /post/write URL alone is NOT sufficient.
    The groupware can change the URL before its SPA/editor form has finished
    rendering. We only treat the write page as ready when an actual editor
    control is present.
    """
    title = _first_visible(page, profile["editor"]["title_input_candidates"])
    if title is not None:
        return True

    try:
        file_inputs = page.locator("input[type='file']")
        if file_inputs.count() > 0:
            return True
    except Exception:
        pass

    # A visible editor iframe/contenteditable is another useful form signal.
    try:
        if page.locator("[contenteditable='true']").count() > 0:
            return True
        if page.locator("iframe").count() > 0:
            return True
    except Exception:
        pass

    return False


def _try_fill_and_submit_login(page, profile: dict, log: Callable[[str], None]) -> bool:
    """
    Best-effort login:
      - fills stored ID/PW
      - clicks normal login/submit button
      - never solves CAPTCHA/security code
    """
    try:
        creds = load_credentials()
    except Exception as exc:
        log(f"자격증명 읽기 생략: {exc}")
        return False

    if not creds:
        log("저장된 자격증명이 없습니다. 필요한 경우 브라우저에서 직접 로그인하세요.")
        return False

    username, password = creds
    login_cfg = profile["login"]

    user_input = _first_visible(page, login_cfg["username_candidates"])
    pass_input = _first_visible(page, login_cfg["password_candidates"])

    if not user_input or not pass_input:
        return False

    user_input.fill(username)
    pass_input.fill(password)
    log("저장된 ID/PW를 로그인 화면에 자동 입력했습니다.")

    submit = _first_visible(page, login_cfg["submit_candidates"])
    if submit:
        submit.click()
        log("로그인 버튼을 자동 클릭했습니다.")
        return True

    log("로그인 버튼을 자동 탐지하지 못했습니다.")
    return False


def _wait_until_logged_in(
    page,
    board_url: str,
    profile: dict,
    wait_seconds: int,
    log: Callable[[str], None],
):
    """
    Tries auto-login once, then waits for any CAPTCHA/security step to be
    completed manually. Login is considered complete when the page no longer
    presents the password field and a board page can be reached.
    """
    deadline = time.time() + wait_seconds
    auto_attempted = False

    while time.time() < deadline:
        if _looks_like_login_page(page, profile):
            if not auto_attempted:
                auto_attempted = True
                _try_fill_and_submit_login(page, profile, log)
                page.wait_for_timeout(800)

            if _looks_like_login_page(page, profile):
                if auto_attempted:
                    log("추가 인증/CAPTCHA가 있다면 브라우저에서 완료해주세요.")
                time.sleep(1)
                continue

        # Confirm by navigating to the requested board after login.
        try:
            page.goto(board_url, wait_until="domcontentloaded")
            if not _looks_like_login_page(page, profile):
                return
        except Exception:
            pass

        time.sleep(1)

    raise BrowserAutomationError(
        f"로그인 대기시간({wait_seconds}초)을 초과했습니다. "
        "CAPTCHA/추가 인증 또는 계정정보를 확인해주세요."
    )



def _find_title_input(page, profile: dict):
    """
    1) Use configured semantic selectors.
    2) Fallback to the widest visible text input on the write page while
       excluding obvious global search/login fields.

    The user's screenshot shows the title field spanning almost the full
    editor width, while the global search field is much narrower.
    """
    configured = _first_visible(page, profile["editor"]["title_input_candidates"])
    if configured is not None:
        return configured

    try:
        candidates = page.locator(
            "input[type='text'], input:not([type]), input[type='search']"
        )
        best = None
        best_width = 0

        for idx in range(candidates.count()):
            loc = candidates.nth(idx)
            try:
                if not loc.is_visible():
                    continue

                attrs = loc.evaluate(
                    """el => ({
                        type: (el.getAttribute('type') || '').toLowerCase(),
                        name: (el.getAttribute('name') || '').toLowerCase(),
                        id: (el.getAttribute('id') || '').toLowerCase(),
                        placeholder: (el.getAttribute('placeholder') || '').toLowerCase(),
                        aria: (el.getAttribute('aria-label') || '').toLowerCase()
                    })"""
                )

                joined = " ".join(str(v) for v in attrs.values())
                if any(token in joined for token in [
                    "search", "검색", "login", "user", "아이디", "password"
                ]):
                    continue

                box = loc.bounding_box()
                if not box:
                    continue

                width = float(box.get("width", 0))
                # Ignore tiny controls. The real title box in the supplied UI
                # is a long horizontal field.
                if width < 250:
                    continue

                if width > best_width:
                    best = loc
                    best_width = width
            except Exception:
                continue

        return best
    except Exception:
        return None


def _wait_for_write_form(
    page,
    profile: dict,
    log: Callable[[str], None],
):
    routing = profile["routing"]
    wait_seconds = int(routing.get("write_form_wait_seconds", 8))
    poll_ms = int(routing.get("write_form_poll_interval_ms", 300))

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        title = _find_title_input(page, profile)
        if title is not None:
            return title

        if _looks_like_write_page(page, profile):
            # The rest of the editor is present; keep waiting specifically for
            # the title input because it may render a little later.
            pass

        page.wait_for_timeout(poll_ms)

    return None


def _log_input_diagnostics(page, log: Callable[[str], None]):
    """
    Compact diagnostics for future site changes. Does not log input values.
    """
    try:
        info = page.locator("input").evaluate_all(
            """els => els.map((el, i) => {
                const r = el.getBoundingClientRect();
                return {
                    i,
                    type: el.type || '',
                    name: el.name || '',
                    id: el.id || '',
                    placeholder: el.placeholder || '',
                    visible: !!(r.width && r.height),
                    width: Math.round(r.width)
                };
            }).filter(x => x.visible).slice(0, 20)"""
        )
        log(f"진단: 현재 URL = {page.url}")
        log(f"진단: visible input 개수 = {len(info)}")
        for item in info:
            log(
                "진단 input "
                f"#{item.get('i')} type={item.get('type')} "
                f"name={item.get('name')} id={item.get('id')} "
                f"placeholder={item.get('placeholder')} "
                f"width={item.get('width')}"
            )
    except Exception as exc:
        log(f"진단 정보 수집 실패: {exc}")




def _community_ready(page, profile: dict) -> bool:
    community = profile.get("community") or {}

    # If any configured board name is visible, the target community context
    # is already active.
    for selector in community.get("ready_candidates", []):
        try:
            loc = page.locator(selector).first
            if loc.count() and loc.is_visible():
                return True
        except Exception:
            continue

    return False


def _ensure_community_context(
    page,
    board_url: str,
    profile: dict,
    log: Callable[[str], None],
):
    """
    Suresoft groupware can show the Community Home immediately after login.
    In that state, the user must first select '모솔1팀 실차TC강건화' before
    board 374~377 behave as a normal current-community board.

    This helper reproduces that UI flow rather than relying on a direct URL.
    """
    community = profile.get("community")
    if not community:
        return

    wait_seconds = int(community.get("selection_wait_seconds", 8))
    poll_ms = int(community.get("poll_interval_ms", 300))
    community_name = community.get("name", "")

    # First open the community home. This mirrors the user's actual flow and
    # gives the SPA a chance to initialize its internal community state.
    home_url = community.get("home_url")
    if home_url:
        log(f"커뮤니티 컨텍스트 확인: {community_name}")
        page.goto(home_url, wait_until="domcontentloaded")
        page.wait_for_timeout(500)

    if _community_ready(page, profile):
        log("대상 커뮤니티가 이미 선택된 상태입니다.")
        _stage_stabilize(page, profile, log, "community")
    else:
        entry = _first_visible(page, community.get("entry_candidates", []))

        if entry is None:
            # Sometimes the page needs a little more time to render the
            # '가입커뮤니티' list.
            deadline = time.time() + wait_seconds
            while time.time() < deadline and entry is None:
                page.wait_for_timeout(poll_ms)
                entry = _first_visible(page, community.get("entry_candidates", []))

        if entry is None:
            raise BrowserAutomationError(
                f"커뮤니티 홈에서 '{community_name}' 항목을 찾지 못했습니다."
            )

        entry.scroll_into_view_if_needed()
        entry.click()
        log(f"커뮤니티 자동 선택: {community_name}")

        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if _community_ready(page, profile):
                log("커뮤니티 130 게시판 메뉴가 표시된 것을 확인했습니다.")
                _stage_stabilize(page, profile, log, "community")
                break
            page.wait_for_timeout(poll_ms)
        else:
            raise BrowserAutomationError(
                "커뮤니티를 클릭했지만 게시판 메뉴가 준비된 것을 확인하지 못했습니다."
            )

    # Now move to the exact target board inside the initialized community.
    page.goto(board_url, wait_until="domcontentloaded")
    log(f"대상 게시판 진입: {board_url}")
    _stage_stabilize(page, profile, log, "board")




def _normalized_path(url: str) -> str:
    try:
        path = urlparse(url).path.rstrip("/")
    except Exception:
        path = url.rstrip("/")
    return path


def _expected_write_url(board_url: str, profile: dict) -> str:
    return write_url_for(board_url, profile).rstrip("/")


def _is_exact_target_write_url(current_url: str, board_url: str, profile: dict) -> bool:
    """
    Exact board-specific validation:
      target board: .../board/374
      valid write:  .../board/374/post/write

    Invalid examples:
      .../board/post/write
      .../board/349/post/write
    """
    return _normalized_path(current_url) == _normalized_path(
        _expected_write_url(board_url, profile)
    )


def _wait_for_exact_new_post_button(
    page,
    profile: dict,
    log: Callable[[str], None],
):
    routing = profile["routing"]
    wait_seconds = int(routing.get("new_post_button_wait_seconds", 6))
    poll_ms = int(routing.get("new_post_button_poll_interval_ms", 300))

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        btn = _first_visible(page, profile["board"]["write_button_candidates"])
        if btn is not None:
            return btn
        page.wait_for_timeout(poll_ms)

    log(
        f"정확한 '새글쓰기' 버튼을 {wait_seconds}초 동안 찾지 못했습니다. "
        "일반 '글쓰기' 버튼은 안전상 사용하지 않습니다."
    )
    return None


def _wait_for_exact_target_write_url(
    page,
    board_url: str,
    profile: dict,
    wait_seconds: int,
):
    deadline = time.time() + wait_seconds
    poll_ms = int(profile["routing"].get("write_form_poll_interval_ms", 300))

    while time.time() < deadline:
        if _is_exact_target_write_url(page.url, board_url, profile):
            return True
        page.wait_for_timeout(poll_ms)

    return False



def _open_write_page(
    page,
    board_url: str,
    profile: dict,
    log: Callable[[str], None],
):
    """
    v0.9 strict routing:
      1) Stay on the exact target board.
      2) Click ONLY exact '새글쓰기'. Never the global generic '글쓰기'.
      3) Verify the resulting URL is exactly /board/{target_id}/post/write.
      4) If the exact button is unavailable/misroutes, use the exact board-specific
         direct write URL only after community context has already been initialized.
      5) Never enter title/body/file data on a mismatched board.
    """
    routing = profile["routing"]
    wait_seconds = int(routing.get("write_form_wait_seconds", 8))
    expected_write_url = _expected_write_url(board_url, profile)

    if routing.get("prefer_write_button", True):
        log("대상 게시판에서 정확한 '새글쓰기' 버튼만 탐색합니다.")
        page.goto(board_url, wait_until="domcontentloaded")
        page.wait_for_timeout(500)

        write_btn = _wait_for_exact_new_post_button(page, profile, log)
        if write_btn is not None:
            write_btn.scroll_into_view_if_needed()
            write_btn.click()
            log("정확한 '새글쓰기' 버튼을 클릭했습니다.")

            # The prior bug clicked a generic left-side 글쓰기 and reached
            # /board/post/write. Reject that immediately.
            if _wait_for_exact_target_write_url(
                page,
                board_url,
                profile,
                min(wait_seconds, 5),
            ):
                log(f"대상 게시판 작성 URL 검증 성공: {page.url}")

                title_input = _wait_for_write_form(page, profile, log)
                if title_input is not None:
                    log("정확한 대상 게시판의 실제 작성 폼 진입을 확인했습니다.")
                    _stage_stabilize(page, profile, log, "write_form")
                    return title_input

                log("URL은 정확하지만 실제 제목 입력창을 확인하지 못했습니다.")
            else:
                log(
                    "새글쓰기 클릭 후 대상 게시판 작성 URL이 일치하지 않습니다. "
                    f"현재={page.url} / 기대={expected_write_url}"
                )
                log("잘못된 게시판에 내용을 입력하지 않고 직접 URL fallback으로 전환합니다.")

    if routing.get("fallback_to_direct_write_url", True):
        log(f"Fallback: 정확한 대상 작성 URL로 이동합니다: {expected_write_url}")
        page.goto(expected_write_url, wait_until="domcontentloaded")

        if routing.get("validate_exact_write_url", True):
            if not _is_exact_target_write_url(page.url, board_url, profile):
                raise BrowserAutomationError(
                    "직접 작성 URL 이동 후에도 대상 board 번호가 일치하지 않습니다.\n"
                    f"현재 URL: {page.url}\n"
                    f"기대 URL: {expected_write_url}"
                )

        # Detect the known bad community-context state if it appears.
        body_text = _page_body_text(page)
        if "생성된 커뮤니티가 없습니다" in body_text:
            raise BrowserAutomationError(
                "대상 작성 URL은 맞지만 그룹웨어가 '생성된 커뮤니티가 없습니다.' 상태를 표시했습니다. "
                "커뮤니티 선택 상태를 다시 확인해야 합니다."
            )

        log(f"Fallback 대상 작성 URL 검증 성공: {page.url}")
        title_input = _wait_for_write_form(page, profile, log)
        if title_input is not None:
            log("Fallback에서 정확한 대상 게시판 작성 폼을 확인했습니다.")
            _stage_stabilize(page, profile, log, "write_form")
            return title_input

    _log_input_diagnostics(page, log)
    raise BrowserAutomationError(
        "정확한 '새글쓰기' 또는 대상 board 전용 작성 URL에서 제목 입력창을 확인하지 못했습니다."
    )


def _fill_title_with_retry(
    page,
    title: str,
    profile: dict,
    log: Callable[[str], None],
):
    """
    The real groupware title field was observed as:
        <input type="text" id="subject" class="txt w_max">

    The page can re-render the form shortly after entry, detaching an earlier
    locator. Re-acquire the locator on every attempt rather than holding a stale
    locator object.
    """
    editor = profile["editor"]
    retry_count = int(editor.get("title_fill_retry_count", 4))
    wait_ms = int(editor.get("title_fill_retry_wait_ms", 300))

    last_error = None

    for attempt in range(1, retry_count + 1):
        try:
            # Strongest, screenshot/log-confirmed selector.
            subject = page.locator("#subject").first
            if subject.count():
                subject.wait_for(state="visible", timeout=3000)
                subject.fill(title)
                if subject.input_value() == title:
                    log(f"제목 자동 입력 완료 (#subject, 시도 {attempt}/{retry_count})")
                    return True

            # If #subject is temporarily absent, re-run the generic finder.
            candidate = _find_title_input(page, profile)
            if candidate is not None:
                candidate.fill(title)
                try:
                    value = candidate.input_value()
                except Exception:
                    value = ""
                if value == title:
                    log(f"제목 자동 입력 완료 (fallback, 시도 {attempt}/{retry_count})")
                    return True

        except Exception as exc:
            last_error = exc
            log(
                f"제목 입력 시도 {attempt}/{retry_count} 재시도: "
                f"{type(exc).__name__}: {exc}"
            )

        page.wait_for_timeout(wait_ms)

    if last_error:
        log(f"제목 입력 최종 실패 원인: {type(last_error).__name__}: {last_error}")
    return False




def _plain_text_to_dext5_html(text: str) -> str:
    """
    Convert BoardRepo's plain-text description into simple DEXT5-safe body HTML.
    Keep formatting intentionally minimal so the editor/server has little to normalize.
    """
    escaped = html_escape(text, quote=False)
    lines = escaped.splitlines()

    html_lines = []
    for line in lines:
        if line.strip():
            html_lines.append(f"<p>{line}</p>")
        else:
            html_lines.append("<p><br></p>")

    return "".join(html_lines) if html_lines else "<p><br></p>"


def _normalize_editor_text(value: str) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def _dext5_api_status(frame) -> dict:
    try:
        result = frame.evaluate(
            """() => {
                const d = window.DEXT5;
                return {
                    exists: !!d,
                    setBodyValue: !!(d && typeof d.setBodyValue === 'function'),
                    getBodyTextValue: !!(d && typeof d.getBodyTextValue === 'function'),
                    getBodyValue: !!(d && typeof d.getBodyValue === 'function'),
                    setEditor: !!(d && typeof d.setEditor === 'function'),
                    getEditor: !!(d && typeof d.getEditor === 'function')
                };
            }"""
        )
        return result or {}
    except Exception:
        return {}


def _find_dext5_execution_context(
    page,
    profile: dict,
    log: Callable[[str], None],
):
    cfg = profile.get("dext5") or {}
    wait_seconds = int(cfg.get("detect_wait_seconds", 8))
    poll_ms = int(cfg.get("poll_interval_ms", 250))

    deadline = time.time() + wait_seconds

    while time.time() < deadline:
        # DEXT5 is normally exposed on the main groupware page.
        status = _dext5_api_status(page.main_frame)
        if (
            status.get("exists")
            and status.get("setBodyValue")
            and (status.get("getBodyTextValue") or status.get("getBodyValue"))
        ):
            log(
                "DEXT5 API 감지: main frame "
                f"(setBodyValue={status.get('setBodyValue')}, "
                f"getBodyTextValue={status.get('getBodyTextValue')}, "
                f"getBodyValue={status.get('getBodyValue')})"
            )
            return page.main_frame

        # Defensive fallback: some deployments may load API objects in a child frame.
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            status = _dext5_api_status(frame)
            if (
                status.get("exists")
                and status.get("setBodyValue")
                and (status.get("getBodyTextValue") or status.get("getBodyValue"))
            ):
                log(
                    f"DEXT5 API 감지: child frame name={frame.name or '(없음)'}"
                )
                return frame

        page.wait_for_timeout(poll_ms)

    return None


def _discover_dext5_editor_ids(frame, profile: dict):
    configured = list(
        (profile.get("dext5") or {}).get("candidate_editor_ids", [])
    )

    try:
        discovered = frame.evaluate(
            """() => {
                const ids = new Set();

                // Common element ids associated with editor containers/iframes.
                document.querySelectorAll('[id]').forEach(el => {
                    const id = el.id || '';
                    if (/dext|editor/i.test(id)) ids.add(id);
                });

                // Inline creation pattern: new Dext5editor('editor1')
                document.querySelectorAll('script:not([src])').forEach(script => {
                    const text = script.textContent || '';
                    const re = /new\\s+Dext5editor\\s*\\(\\s*['"]([^'"]+)['"]/ig;
                    let m;
                    while ((m = re.exec(text)) !== null) {
                        if (m[1]) ids.add(m[1]);
                    }
                });

                return Array.from(ids).slice(0, 30);
            }"""
        )
    except Exception:
        discovered = []

    ordered = []
    for item in [*configured, *(discovered or [])]:
        if item and item not in ordered:
            ordered.append(item)
    return ordered



def _probe_dext5_dom(frame, editor_id):
    """
    DEXT5.getDext5Dom() returns the design area's documentElement DOM.
    We never return that DOM object through Playwright serialization; instead
    inspect it inside the page and return small readiness metadata.
    """
    try:
        return frame.evaluate(
            """({editorId}) => {
                const d = window.DEXT5;
                if (!d || typeof d.getDext5Dom !== 'function') {
                    return {
                        ready: false,
                        reason: 'getDext5Dom unavailable',
                        editorId: editorId || ''
                    };
                }

                try {
                    const dom = editorId
                        ? d.getDext5Dom(editorId)
                        : d.getDext5Dom();

                    const doc = dom && dom.ownerDocument ? dom.ownerDocument : null;
                    const body = doc && doc.body ? doc.body : null;

                    return {
                        ready: !!(dom && doc && body),
                        editorId: editorId || '',
                        nodeName: dom && dom.nodeName ? dom.nodeName : '',
                        bodyExists: !!body,
                        bodyChildCount: body ? body.childNodes.length : 0,
                        bodyTextLength: body
                            ? ((body.innerText || body.textContent || '').trim().length)
                            : 0
                    };
                } catch (e) {
                    return {
                        ready: false,
                        reason: String(e),
                        editorId: editorId || ''
                    };
                }
            }""",
            {"editorId": editor_id},
        )
    except Exception as exc:
        return {
            "ready": False,
            "reason": f"{type(exc).__name__}: {exc}",
            "editorId": editor_id or "",
        }


def _wait_for_dext5_editor_ready(
    page,
    profile: dict,
    log: Callable[[str], None],
):
    """
    Wait for a REAL DEXT5 editor instance, not merely the global DEXT5 library.

    Readiness = getDext5Dom(editor_id) returns a design DOM with ownerDocument/body.
    For a single editor, the official API allows editor_id to be omitted, so that
    probe is always first.
    """
    cfg = profile.get("dext5") or {}
    frame = _find_dext5_execution_context(page, profile, log)
    if frame is None:
        return None

    wait_seconds = int(cfg.get("editor_ready_wait_seconds", 12))
    poll_ms = int(cfg.get("editor_ready_poll_interval_ms", 250))
    allow_no_id = bool(cfg.get("allow_no_editor_id", True))

    log(
        f"DEXT5 실제 Editor DOM 준비 상태를 최대 {wait_seconds}초 확인합니다 "
        "(getDext5Dom 기반)."
    )

    deadline = time.time() + wait_seconds
    probed_ids = []

    while time.time() < deadline:
        attempts = []
        if allow_no_id:
            attempts.append(None)
        attempts.extend(_discover_dext5_editor_ids(frame, profile))

        unique_attempts = []
        for editor_id in attempts:
            if editor_id not in unique_attempts:
                unique_attempts.append(editor_id)

        for editor_id in unique_attempts:
            label = editor_id if editor_id else "(editor_id 생략)"
            if label not in probed_ids:
                probed_ids.append(label)

            result = _probe_dext5_dom(frame, editor_id)
            if result.get("ready"):
                log(
                    "DEXT5 Editor 준비 완료 "
                    f"{label}: node={result.get('nodeName') or '-'} "
                    f"bodyChildCount={result.get('bodyChildCount')} "
                    f"bodyTextLength={result.get('bodyTextLength')}"
                )
                _stage_stabilize(page, profile, log, "dext5")
                return {
                    "frame": frame,
                    "editor_id": editor_id,
                    "probe": result,
                }

        page.wait_for_timeout(poll_ms)

    log(
        "DEXT5 API는 감지됐지만 실제 Editor DOM이 준비되지 않았습니다. "
        f"확인한 editor 후보: {', '.join(probed_ids) if probed_ids else '(없음)'}"
    )
    return False



def _set_and_verify_dext5_body(
    frame,
    text: str,
    html_value: str,
    editor_id,
    profile: dict,
):
    """
    Use DEXT5's own API and read the value back from DEXT5 itself.
    Returning visible iframe text is intentionally NOT enough.
    """
    ratio_threshold = float(
        (profile.get("dext5") or {}).get("minimum_text_match_ratio", 0.80)
    )

    return frame.evaluate(
        """({text, htmlValue, editorId, ratioThreshold}) => {
            const d = window.DEXT5;
            if (!d || typeof d.setBodyValue !== 'function') {
                return {ok:false, reason:'DEXT5.setBodyValue unavailable'};
            }

            const normalize = value =>
                (value || '')
                    .replace(/\\u00a0/g, ' ')
                    .replace(/\\s+/g, ' ')
                    .trim();

            const stripHtml = html => {
                const holder = document.createElement('div');
                holder.innerHTML = html || '';
                return holder.innerText || holder.textContent || '';
            };

            try {
                if (editorId) {
                    d.setBodyValue(htmlValue, editorId);
                } else {
                    d.setBodyValue(htmlValue);
                }
            } catch (e) {
                return {
                    ok:false,
                    reason:'setBodyValue error',
                    error:String(e),
                    editorId: editorId || ''
                };
            }

            let actualText = '';
            let actualHtml = '';
            let textReadError = '';
            let htmlReadError = '';

            if (typeof d.getBodyTextValue === 'function') {
                try {
                    actualText = editorId
                        ? d.getBodyTextValue(editorId)
                        : d.getBodyTextValue();
                } catch (e) {
                    textReadError = String(e);
                }
            }

            if (typeof d.getBodyValue === 'function') {
                try {
                    actualHtml = editorId
                        ? d.getBodyValue(editorId)
                        : d.getBodyValue();
                } catch (e) {
                    htmlReadError = String(e);
                }
            }

            if (!actualText && actualHtml) {
                actualText = stripHtml(actualHtml);
            }

            const expected = normalize(text);
            const actual = normalize(actualText);

            let ratio = 0;
            if (expected.length > 0) {
                ratio = Math.min(actual.length, expected.length) /
                        Math.max(actual.length, expected.length);
            }

            const marker = normalize(text.split(/\\r?\\n/)[0] || '');
            const markerOk = !!marker && actual.includes(marker);
            const lengthOk = actual.length > 0 && ratio >= ratioThreshold;

            return {
                ok: markerOk && lengthOk,
                editorId: editorId || '',
                expectedLength: expected.length,
                actualLength: actual.length,
                ratio,
                markerOk,
                textReadError,
                htmlReadError,
                htmlLength: (actualHtml || '').length
            };
        }""",
        {
            "text": text,
            "htmlValue": html_value,
            "editorId": editor_id,
            "ratioThreshold": ratio_threshold,
        },
    )


def _fill_body_with_dext5_api(
    page,
    text: str,
    profile: dict,
    log: Callable[[str], None],
):
    """
    Return:
      True  -> DEXT5 editor was ready AND internal value was verified
      False -> DEXT5 exists/editor readiness or internal verification failed
      None  -> DEXT5 API itself could not be found

    v0.12 intentionally separates:
      Library available != Editor instance ready.
    """
    dext_cfg = profile.get("dext5") or {}
    if not dext_cfg.get("enabled", True):
        return None

    ready = _wait_for_dext5_editor_ready(page, profile, log)
    if ready is None:
        log("DEXT5 API를 감지하지 못했습니다.")
        return None
    if ready is False:
        return False

    frame = ready["frame"]
    editor_id = ready["editor_id"]
    label = editor_id if editor_id else "(editor_id 생략)"
    html_value = _plain_text_to_dext5_html(text)

    retry_count = int(dext_cfg.get("set_retry_count", 3))
    retry_wait_ms = int(dext_cfg.get("set_retry_wait_ms", 400))

    for attempt in range(1, retry_count + 1):
        # Re-confirm DOM readiness before every write attempt because some
        # editors rebuild their iframe during initialization.
        probe = _probe_dext5_dom(frame, editor_id)
        if not probe.get("ready"):
            log(
                f"DEXT5 본문 입력 전 Editor DOM 재확인 실패 "
                f"{label} (시도 {attempt}/{retry_count})"
            )
            page.wait_for_timeout(retry_wait_ms)
            continue

        try:
            result = _set_and_verify_dext5_body(
                frame,
                text,
                html_value,
                editor_id,
                profile,
            )
        except Exception as exc:
            log(
                f"DEXT5 본문 입력 시도 실패 {label} "
                f"({attempt}/{retry_count}): {type(exc).__name__}: {exc}"
            )
            page.wait_for_timeout(retry_wait_ms)
            continue

        if result.get("ok"):
            log(
                "DEXT5 내부 본문 입력/검증 성공 "
                f"{label} (시도 {attempt}/{retry_count}): "
                f"textLength={result.get('actualLength')} "
                f"matchRatio={result.get('ratio', 0):.2f}"
            )
            _stage_stabilize(page, profile, log, "body")
            return True

        log(
            "DEXT5 본문 입력 검증 미통과 "
            f"{label} (시도 {attempt}/{retry_count}): "
            f"expectedLength={result.get('expectedLength')} "
            f"actualLength={result.get('actualLength')} "
            f"matchRatio={result.get('ratio', 0):.2f} "
            f"markerOk={result.get('markerOk')} "
            f"textReadError={result.get('textReadError') or '-'} "
            f"htmlReadError={result.get('htmlReadError') or '-'}"
        )

        page.wait_for_timeout(retry_wait_ms)

    return False



def _verify_dext5_body_after_fallback(
    page,
    text: str,
    profile: dict,
    log: Callable[[str], None],
):
    """
    If DEXT5 exists, a visual/keyboard fallback is not accepted until the
    DEXT5 internal text can be read back and matched.
    """
    frame = _find_dext5_execution_context(page, profile, log)
    if frame is None:
        return None

    html_value = _plain_text_to_dext5_html(text)
    # We do NOT set again here. This helper only reads current internal state.
    ids = [None, *_discover_dext5_editor_ids(frame, profile)]

    seen = []
    for editor_id in ids:
        if editor_id in seen:
            continue
        seen.append(editor_id)

        try:
            result = frame.evaluate(
                """({text, editorId, ratioThreshold}) => {
                    const d = window.DEXT5;
                    if (!d) return {ok:false, reason:'DEXT5 missing'};

                    const normalize = value =>
                        (value || '')
                            .replace(/\\u00a0/g, ' ')
                            .replace(/\\s+/g, ' ')
                            .trim();

                    const stripHtml = html => {
                        const holder = document.createElement('div');
                        holder.innerHTML = html || '';
                        return holder.innerText || holder.textContent || '';
                    };

                    let actualText = '';
                    try {
                        if (typeof d.getBodyTextValue === 'function') {
                            actualText = editorId
                                ? d.getBodyTextValue(editorId)
                                : d.getBodyTextValue();
                        }
                    } catch (_) {}

                    if (!actualText && typeof d.getBodyValue === 'function') {
                        try {
                            const html = editorId
                                ? d.getBodyValue(editorId)
                                : d.getBodyValue();
                            actualText = stripHtml(html);
                        } catch (_) {}
                    }

                    const expected = normalize(text);
                    const actual = normalize(actualText);
                    const marker = normalize(text.split(/\\r?\\n/)[0] || '');
                    const ratio = expected.length
                        ? Math.min(actual.length, expected.length) /
                          Math.max(actual.length, expected.length)
                        : 0;

                    return {
                        ok: !!marker &&
                            actual.includes(marker) &&
                            ratio >= ratioThreshold,
                        actualLength: actual.length,
                        ratio
                    };
                }""",
                {
                    "text": text,
                    "editorId": editor_id,
                    "ratioThreshold": float(
                        (profile.get("dext5") or {}).get(
                            "minimum_text_match_ratio",
                            0.80,
                        )
                    ),
                },
            )

            if result.get("ok"):
                log(
                    "Fallback 입력 후 DEXT5 내부값 검증 성공: "
                    f"textLength={result.get('actualLength')} "
                    f"matchRatio={result.get('ratio', 0):.2f}"
                )
                return True
        except Exception:
            continue

    log("Fallback 화면 입력은 보이지만 DEXT5 내부값 검증에는 실패했습니다.")
    return False


def _fill_body_with_keyboard_fallback(
    page,
    text: str,
    profile: dict,
    log: Callable[[str], None],
) -> bool:
    """
    Secondary route: imitate actual keyboard input into an editable region.
    If DEXT5 exists, visual success is still not enough; internal DEXT5 value
    must be verified afterwards.
    """
    # Main page editable controls.
    selectors = [
        "textarea:visible",
        "[contenteditable='true']:visible",
    ]

    for selector in selectors:
        try:
            locators = page.locator(selector)
            for idx in range(locators.count()):
                loc = locators.nth(idx)
                if not loc.is_visible():
                    continue
                try:
                    loc.click(force=True)
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    page.keyboard.insert_text(text)
                    page.wait_for_timeout(300)

                    verification = _verify_dext5_body_after_fallback(
                        page, text, profile, log
                    )
                    if verification is True:
                        return True
                    if verification is None:
                        # No DEXT5 API: verify visible text as best effort.
                        current = ""
                        try:
                            current = loc.input_value()
                        except Exception:
                            try:
                                current = loc.inner_text()
                            except Exception:
                                current = ""
                        if _normalize_editor_text(text) in _normalize_editor_text(current):
                            log("키보드 fallback 본문 입력 확인 (DEXT5 API 미감지)")
                            return True
                except Exception:
                    continue
        except Exception:
            continue

    # Child editor frames.
    for frame in page.frames:
        if frame == page.main_frame:
            continue

        try:
            editable = frame.locator(
                "body[contenteditable='true'], [contenteditable='true'], body"
            ).first
            if not editable.count():
                continue

            editable.click(force=True)
            editable.press("Control+A")
            editable.press("Backspace")
            editable.press_sequentially(text, delay=1)
            page.wait_for_timeout(300)

            verification = _verify_dext5_body_after_fallback(
                page, text, profile, log
            )
            if verification is True:
                return True
            if verification is None:
                try:
                    current = editable.inner_text()
                except Exception:
                    current = ""
                if _normalize_editor_text(text) in _normalize_editor_text(current):
                    log("iframe 키보드 fallback 본문 입력 확인 (DEXT5 API 미감지)")
                    return True
        except Exception:
            continue

    return False



def _fill_body(
    page,
    text: str,
    profile: dict,
    log: Callable[[str], None] | None = None,
) -> bool:
    """
    v0.11 policy:
      1) DEXT5.setBodyValue() as primary route.
      2) Verify with DEXT5.getBodyTextValue()/getBodyValue().
      3) If API is unavailable or fails, keyboard fallback may be attempted.
      4) When DEXT5 exists, visible DOM text alone is NEVER considered success.
    """
    log = log or (lambda _msg: None)
    dext_cfg = profile.get("dext5") or {}

    if dext_cfg.get("prefer_api", True):
        api_result = _fill_body_with_dext5_api(
            page,
            text,
            profile,
            log,
        )

        if api_result is True:
            return True

        if api_result is False:
            log(
                "DEXT5 API는 존재하지만 내부 본문 검증에 실패했습니다. "
                "화면 DOM 표시만으로 성공 처리하지 않습니다."
            )

        if dext_cfg.get("keyboard_fallback", True):
            log("DEXT5 키보드 입력 fallback을 시도합니다.")
            if _fill_body_with_keyboard_fallback(
                page,
                text,
                profile,
                log,
            ):
                return True

        # If DEXT5 exists and internal verification is required, do not fall
        # through to old DOM-injection logic.
        if (
            api_result is False
            and dext_cfg.get("require_internal_verification", True)
        ):
            return False

    # Generic editors only: this route is for deployments where DEXT5 is absent.
    candidates = profile["editor"]["body_input_candidates"]

    for selector in candidates:
        if selector == "iframe":
            continue
        try:
            locators = page.locator(selector)
            for idx in range(locators.count()):
                loc = locators.nth(idx)
                if not loc.is_visible():
                    continue

                tag = loc.evaluate("(el) => el.tagName.toLowerCase()")
                if tag == "textarea":
                    loc.fill(text)
                    current = loc.input_value()
                else:
                    loc.click(force=True)
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    page.keyboard.insert_text(text)
                    current = loc.inner_text()

                if _normalize_editor_text(text) in _normalize_editor_text(current):
                    log("일반 편집기 본문 입력 확인 (DEXT5 미감지 환경)")
                    return True
        except Exception:
            continue

    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            editable = frame.locator(
                "body[contenteditable='true'], [contenteditable='true'], body"
            ).first
            if not editable.count():
                continue

            editable.click(force=True)
            editable.press("Control+A")
            editable.press("Backspace")
            editable.press_sequentially(text, delay=1)
            current = editable.inner_text()

            if _normalize_editor_text(text) in _normalize_editor_text(current):
                log("일반 iframe 편집기 본문 입력 확인 (DEXT5 미감지 환경)")
                return True
        except Exception:
            continue

    log("본문 편집기의 실제 내부 입력 상태를 확인하지 못했습니다.")
    return False


def _wait_for_attachment_ready(
    page,
    zip_path: Path,
    profile: dict,
    log: Callable[[str], None],
) -> bool:
    """
    Prefer a concrete UI readiness condition (uploaded filename appears).
    If the site does not render the filename, fall back to the historical
    attachment settle time rather than falsely failing.
    """
    verification = profile.get("verification") or {}
    wait_seconds = int(verification.get("attachment_wait_seconds", 8))
    poll_ms = int(verification.get("attachment_poll_interval_ms", 300))

    log(
        f"첨부파일 UI 반영을 최대 {wait_seconds}초 확인합니다: {zip_path.name}"
    )

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if zip_path.name in _page_body_text(page):
            log(f"첨부파일 Readiness 확인: {zip_path.name}")
            _stage_stabilize(page, profile, log, "attachment")
            return True
        page.wait_for_timeout(poll_ms)

    settle_ms = int(verification.get("attachment_settle_ms", 2500))
    log(
        "화면에서 첨부 파일명을 확인하지 못했습니다. "
        f"사이트 UI 비표시 가능성을 고려해 기존 안정화 대기 {settle_ms / 1000:.1f}초를 적용합니다."
    )
    page.wait_for_timeout(settle_ms)
    return False



def _set_file(page, zip_path: Path, profile: dict, log) -> None:
    editor = profile["editor"]

    # Playwright can directly set a hidden file input without opening the
    # Windows file picker. This is the preferred route for the user's page.
    for selector in editor["file_input_candidates"]:
        try:
            inputs = page.locator(selector)
            count = inputs.count()
            for idx in range(count):
                loc = inputs.nth(idx)
                try:
                    loc.set_input_files(str(zip_path))
                    log(f"파일 직접 첨부: {zip_path.name}")
                    return
                except Exception:
                    continue
        except Exception:
            continue

    # If input is created only after pressing "파일선택", click that control.
    file_button = _first_visible(page, editor["file_button_candidates"])
    if file_button:
        file_button.click()
        page.wait_for_timeout(500)

        for selector in editor["file_input_candidates"]:
            try:
                inputs = page.locator(selector)
                for idx in range(inputs.count()):
                    loc = inputs.nth(idx)
                    try:
                        loc.set_input_files(str(zip_path))
                        log(f"파일 첨부: {zip_path.name}")
                        return
                    except Exception:
                        continue
            except Exception:
                continue

    raise BrowserAutomationError(
        "파일 첨부 요소를 찾지 못했습니다. "
        "site_profile.json의 editor.file_input_candidates를 확인하세요."
    )




def _first_present(page_or_frame, selectors: Iterable[str]):
    """
    Unlike _first_visible, returns an element that exists in DOM even when it is
    currently below the viewport. Useful for the bottom '등록' button.
    """
    for selector in selectors:
        try:
            locator = page_or_frame.locator(selector).first
            if locator.count():
                return locator
        except Exception:
            continue
    return None




def _register_text_candidates(page, exact_text: str):
    """
    Returns visible elements whose rendered text is exactly `exact_text`,
    regardless of tag name. get_by_text(exact=True) lets us handle span/div
    based button implementations as well as normal buttons.
    """
    try:
        locators = page.get_by_text(exact_text, exact=True)
    except Exception:
        return []

    result = []
    try:
        count = locators.count()
    except Exception:
        return []

    for idx in range(count):
        loc = locators.nth(idx)
        try:
            if not loc.is_visible():
                continue
            box = loc.bounding_box()
            if not box:
                continue
            result.append((loc, box))
        except Exception:
            continue

    return result


def _describe_register_candidates(
    page,
    exact_text: str,
    log: Callable[[str], None],
):
    """
    Diagnostic metadata only. Never logs user-entered input values.
    """
    try:
        data = page.locator("*").evaluate_all(
            """(els, exactText) => {
                const norm = s => (s || '').replace(/\\s+/g, ' ').trim();
                return els
                    .filter(el => norm(el.innerText) === exactText)
                    .map(el => {
                        const r = el.getBoundingClientRect();
                        const p = el.parentElement;
                        return {
                            tag: el.tagName.toLowerCase(),
                            id: el.id || '',
                            cls: typeof el.className === 'string' ? el.className : '',
                            role: el.getAttribute('role') || '',
                            onclick: !!el.onclick || el.hasAttribute('onclick'),
                            visible: !!(r.width && r.height),
                            x: Math.round(r.x),
                            y: Math.round(r.y),
                            width: Math.round(r.width),
                            height: Math.round(r.height),
                            parentTag: p ? p.tagName.toLowerCase() : '',
                            parentId: p ? (p.id || '') : '',
                            parentClass: p && typeof p.className === 'string' ? p.className : '',
                            parentRole: p ? (p.getAttribute('role') || '') : ''
                        };
                    })
                    .slice(0, 30);
            }""",
            exact_text,
        )
        log(f"진단: 정확한 '{exact_text}' 텍스트 DOM 후보 = {len(data)}개")
        for idx, item in enumerate(data, start=1):
            log(
                f"진단 등록후보 #{idx}: "
                f"tag={item.get('tag')} id={item.get('id')} "
                f"class={item.get('cls')} role={item.get('role')} "
                f"onclick={item.get('onclick')} visible={item.get('visible')} "
                f"xy=({item.get('x')},{item.get('y')}) "
                f"size=({item.get('width')}x{item.get('height')}) "
                f"parent={item.get('parentTag')}#{item.get('parentId')} "
                f"class={item.get('parentClass')} role={item.get('parentRole')}"
            )
    except Exception as exc:
        log(f"등록 후보 DOM 진단 실패: {exc}")


def _find_exact_register_element(
    page,
    profile: dict,
    log: Callable[[str], None],
):
    editor = profile["editor"]
    exact_text = editor.get("register_exact_text", "등록")
    wait_seconds = int(editor.get("register_search_wait_seconds", 5))
    poll_ms = int(editor.get("register_search_poll_interval_ms", 250))

    deadline = time.time() + wait_seconds

    while time.time() < deadline:
        candidates = _register_text_candidates(page, exact_text)

        if candidates:
            # The actual registration control is visually at the bottom of the
            # form. Choosing the lowest visible exact-text candidate avoids
            # unrelated header/tool elements if the same word is ever reused.
            candidates.sort(
                key=lambda pair: (
                    float(pair[1].get("y", 0)),
                    float(pair[1].get("x", 0)),
                ),
                reverse=True,
            )
            chosen, box = candidates[0]
            log(
                f"정확한 '{exact_text}' 텍스트 요소 발견: "
                f"후보 {len(candidates)}개 중 가장 아래 요소 선택 "
                f"(x={box.get('x'):.0f}, y={box.get('y'):.0f})"
            )
            return chosen

        # Also try explicit configured selectors, in case the visible text
        # engine cannot see a custom control.
        explicit = _first_present(page, editor.get("submit_button_candidates", []))
        if explicit is not None:
            log("site_profile의 정확한 등록 selector로 요소를 찾았습니다.")
            return explicit

        page.wait_for_timeout(poll_ms)

    _describe_register_candidates(page, exact_text, log)
    return None


def _click_register_element(
    register_element,
    log: Callable[[str], None],
) -> bool:
    """
    First click the exact '등록' text element itself. If the text sits inside a
    custom div/span and direct clicking does not work, click the nearest
    clickable ancestor. The ancestor is only reached from an exact '등록'
    descendant, so '공지로 등록' or '임시 저장된 글' are not candidates.
    """
    try:
        register_element.scroll_into_view_if_needed()
    except Exception:
        pass

    try:
        register_element.click(timeout=4000)
        log("정확한 '등록' 텍스트 요소를 직접 클릭했습니다.")
        return True
    except Exception as direct_exc:
        log(f"등록 텍스트 직접 클릭 재시도 필요: {type(direct_exc).__name__}")

    try:
        result = register_element.evaluate(
            """el => {
                const clickableTags = new Set(['button', 'a']);
                let node = el;

                while (node && node !== document.body) {
                    const tag = node.tagName.toLowerCase();
                    const role = (node.getAttribute('role') || '').toLowerCase();
                    const style = window.getComputedStyle(node);
                    const clickable =
                        clickableTags.has(tag) ||
                        role === 'button' ||
                        node.hasAttribute('onclick') ||
                        typeof node.onclick === 'function' ||
                        style.cursor === 'pointer';

                    if (clickable) {
                        node.scrollIntoView({block:'center', inline:'nearest'});
                        node.click();
                        return {
                            clicked: true,
                            tag,
                            id: node.id || '',
                            cls: typeof node.className === 'string' ? node.className : '',
                            role
                        };
                    }
                    node = node.parentElement;
                }

                el.scrollIntoView({block:'center', inline:'nearest'});
                el.click();
                return {
                    clicked: true,
                    tag: el.tagName.toLowerCase(),
                    id: el.id || '',
                    cls: typeof el.className === 'string' ? el.className : '',
                    role: (el.getAttribute('role') || '').toLowerCase()
                };
            }"""
        )
        if result and result.get("clicked"):
            log(
                "정확한 '등록' 텍스트의 클릭 가능 요소를 JS로 클릭했습니다: "
                f"tag={result.get('tag')} id={result.get('id')} "
                f"class={result.get('cls')} role={result.get('role')}"
            )
            return True
    except Exception as exc:
        log(f"등록 클릭 가능 부모 탐색 실패: {exc}")

    return False



def _page_body_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=3000)
    except Exception:
        return ""


def _contains_any(text: str, candidates) -> str:
    for candidate in candidates or []:
        if candidate and candidate in text:
            return candidate
    return ""


def _title_visible_on_page(page, title: str) -> bool:
    """
    Best-effort exact-title verification. Board posts use unique versioned titles,
    so finding the full title in the rendered page is a strong success signal.
    """
    try:
        exact = page.get_by_text(title, exact=True)
        if exact.count() > 0:
            return True
    except Exception:
        pass

    body = _page_body_text(page)
    return title in body


def _verify_title_on_board(
    page,
    board_url: str,
    title: str,
    profile: dict,
    log: Callable[[str], None],
) -> bool:
    verification = profile["verification"]
    wait_seconds = int(verification.get("verify_board_wait_seconds", 8))
    poll_ms = int(verification.get("poll_interval_ms", 500))

    log("실제 게시판 목록에서 방금 작성한 제목을 재확인합니다.")
    page.goto(board_url, wait_until="domcontentloaded")

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if _title_visible_on_page(page, title):
            log(f"게시판에서 작성 제목 확인: {title}")
            return True
        page.wait_for_timeout(poll_ms)

    return False


def _wait_for_submit_result(
    page,
    board_url: str,
    title: str,
    profile: dict,
    log: Callable[[str], None],
) -> bool:
    """
    Waits for redirect/success state after clicking 등록.

    Important:
      - Temporary-save messages are informational, not failure.
      - We do not fail merely because /post/write remains for a few seconds.
      - If the write page remains after the wait, the board list is checked for
        the exact versioned title before declaring failure.
    """
    verification = profile["verification"]
    write_marker = verification.get("write_url_contains", "/post/write")
    success_marker = verification.get("success_url_contains", "/board/")
    wait_seconds = int(verification.get("submit_wait_seconds", 15))
    poll_ms = int(verification.get("poll_interval_ms", 500))
    success_texts = verification.get("success_text_candidates", [])
    draft_texts = verification.get("draft_text_candidates", [])

    deadline = time.time() + wait_seconds
    last_logged_draft = ""
    saw_success_text = ""

    while time.time() < deadline:
        current_url = page.url
        body_text = _page_body_text(page)

        draft_text = _contains_any(body_text, draft_texts)
        if draft_text and draft_text != last_logged_draft:
            log(
                f"편집기 상태 문구 확인: '{draft_text}' "
                "(임시저장/자동저장 상태로 보고 계속 대기합니다.)"
            )
            last_logged_draft = draft_text

        success_text = _contains_any(body_text, success_texts)
        if success_text and not saw_success_text:
            saw_success_text = success_text
            log(f"등록 성공 관련 문구 감지: '{success_text}'")

        # Redirect away from the write form is the strongest success signal.
        if write_marker not in current_url and success_marker in current_url:
            log(f"등록 후 작성 페이지 이탈 확인: {current_url}")
            return True

        page.wait_for_timeout(poll_ms)

    # Some groupware implementations can save asynchronously while leaving the
    # editor URL unchanged. Verify the actual board contents before failing.
    if verification.get("verify_title_on_board", True):
        if _verify_title_on_board(page, board_url, title, profile, log):
            return True

    if saw_success_text:
        log(
            "성공 관련 문구는 확인했지만 게시판에서 제목을 확인하지 못했습니다. "
            "False PASS 방지를 위해 실패로 처리합니다."
        )

    return False



def upload_snapshot(
    board_url: str,
    zip_path: Path,
    title: str,
    body: str,
    browser_profile: Path,
    config: dict,
    site_profile: dict,
    log: Callable[[str], None],
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserAutomationError(
            "playwright가 설치되지 않았습니다. GUI의 필수 모듈 설치/복구를 실행하세요."
        ) from exc

    browser_profile.mkdir(parents=True, exist_ok=True)
    browser_cfg = config["browser"]

    with sync_playwright() as p:
        log("BoardRepo 전용 브라우저를 실행합니다.")
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(browser_profile),
            headless=bool(browser_cfg.get("headless", False)),
            viewport={"width": 1440, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(int(browser_cfg.get("operation_timeout_ms", 15000)))

        try:
            log(f"게시판 접속: {board_url}")
            page.goto(board_url, wait_until="domcontentloaded")

            if _looks_like_login_page(page, site_profile):
                log("로그인이 필요한 상태를 확인했습니다.")
                _wait_until_logged_in(
                    page,
                    board_url,
                    site_profile,
                    int(browser_cfg.get("login_wait_seconds", 180)),
                    log,
                )
                log("로그인 완료 상태를 확인했습니다.")
                _stage_stabilize(page, site_profile, log, "login")
            else:
                log("기존 로그인 세션을 사용합니다.")
                _stage_stabilize(page, site_profile, log, "login")

            _ensure_community_context(
                page,
                board_url,
                site_profile,
                log,
            )

            title_input = _open_write_page(
                page,
                board_url,
                site_profile,
                log,
            )

            editor = site_profile["editor"]

            if title_input is None:
                _log_input_diagnostics(page, log)
                raise BrowserAutomationError(
                    "실제 글쓰기 폼 대기 및 Fallback 후에도 제목 입력창을 찾지 못했습니다."
                )

            if not _fill_title_with_retry(
                page,
                title,
                site_profile,
                log,
            ):
                _log_input_diagnostics(page, log)
                raise BrowserAutomationError(
                    "실제 제목 입력창(#subject 포함)에 제목을 안정적으로 입력하지 못했습니다."
                )
            log(f"제목 자동 입력: {title}")
            _stage_stabilize(page, site_profile, log, "title")

            if _fill_body(page, body, site_profile, log):
                log("본문 설명문 자동 입력 완료")
            else:
                raise BrowserAutomationError(
                    "본문 편집기에 설명문을 입력하지 못했습니다. "
                    "빈 본문으로 등록을 시도하지 않고 중지합니다."
                )

            _set_file(page, zip_path, site_profile, log)

            verification = site_profile["verification"]
            _wait_for_attachment_ready(
                page,
                zip_path,
                site_profile,
                log,
            )

            # The supplied UI shows a teal '등록' control at the bottom, but
            # its actual HTML tag is not yet known. Search by exact rendered
            # text regardless of tag and choose the lowest visible candidate.
            if editor.get("scroll_before_submit", True):
                log("글쓰기 화면의 페이지 최하단으로 자동 스크롤합니다.")
                page.evaluate(
                    "window.scrollTo(0, "
                    "(document.scrollingElement || document.documentElement).scrollHeight)"
                )
                page.wait_for_timeout(
                    int(editor.get("scroll_bottom_wait_ms", 500))
                )
                _stage_stabilize(page, site_profile, log, "before_submit")

            submit_btn = _find_exact_register_element(
                page,
                site_profile,
                log,
            )

            if submit_btn is None:
                raise BrowserAutomationError(
                    "페이지 하단에서 텍스트가 정확히 '등록'인 요소를 찾지 못했습니다. "
                    "DOM 진단 정보를 실행 로그에 기록했습니다."
                )

            # Handle JavaScript confirm/alert dialogs that can appear immediately
            # after clicking 등록. CAPTCHA/security challenges are still never bypassed.
            if verification.get("auto_accept_dialogs", True):
                def _dialog_handler(dialog):
                    try:
                        msg = dialog.message or ""
                        log(f"등록 확인창 자동 처리: {msg if msg else '(메시지 없음)'}")
                        dialog.accept()
                    except Exception as exc:
                        log(f"확인창 처리 실패: {exc}")

                page.on("dialog", _dialog_handler)

            if not _click_register_element(submit_btn, log):
                _describe_register_candidates(
                    page,
                    editor.get("register_exact_text", "등록"),
                    log,
                )
                raise BrowserAutomationError(
                    "정확한 '등록' 요소는 찾았지만 클릭 동작을 완료하지 못했습니다."
                )
            log("등록 버튼 클릭 동작을 완료했습니다.")

            wait_seconds = int(verification.get("submit_wait_seconds", 15))
            log(
                f"등록 결과를 최대 {wait_seconds}초 동안 기다립니다. "
                "임시저장 문구가 보여도 즉시 실패 처리하지 않습니다."
            )

            if not _wait_for_submit_result(
                page,
                board_url,
                title,
                site_profile,
                log,
            ):
                raise BrowserAutomationError(
                    "등록 후 대기 및 게시판 제목 재확인을 수행했지만 "
                    "작성한 게시글을 확인하지 못했습니다."
                )

            log("업로드 성공으로 판정합니다.")

        finally:
            context.close()
