from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import platform
import shutil
from typing import Callable


class BrowserLaunchError(RuntimeError):
    pass


@dataclass(frozen=True)
class BrowserCandidate:
    key: str
    display_name: str
    executable_path: str = ""
    channel: str | None = None


def _existing_playwright_chromium(p) -> BrowserCandidate | None:
    try:
        path = Path(p.chromium.executable_path)
        if path.exists():
            return BrowserCandidate(
                key="playwright_chromium",
                display_name="Playwright Chromium",
                executable_path=str(path),
            )
    except Exception:
        pass
    return None


def find_edge_executable() -> str:
    """Find installed Microsoft Edge without downloading anything."""
    if os.name != "nt":
        return shutil.which("msedge") or ""

    candidates: list[Path] = []
    for env_name in ["PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"]:
        base = os.environ.get(env_name)
        if base:
            candidates.append(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")

    which = shutil.which("msedge")
    if which:
        candidates.insert(0, Path(which))

    seen = set()
    for path in candidates:
        key = str(path).casefold()
        if key in seen:
            continue
        seen.add(key)
        if path.is_file():
            return str(path)
    return ""


def _edge_candidate(config: dict) -> BrowserCandidate | None:
    edge_path = find_edge_executable()
    if not edge_path:
        return None
    browser_cfg = config.get("browser") or {}
    return BrowserCandidate(
        key="msedge",
        display_name="Microsoft Edge",
        executable_path=edge_path,
        channel=str(browser_cfg.get("msedge_channel", "msedge")),
    )


def list_available_candidates(p, config: dict) -> list[BrowserCandidate]:
    browser_cfg = config.get("browser") or {}
    mode = str(browser_cfg.get("mode", "auto")).strip().lower()
    order = list(browser_cfg.get("auto_order") or ["playwright_chromium", "msedge"])

    chromium = _existing_playwright_chromium(p)
    edge = _edge_candidate(config)
    mapping = {
        "playwright_chromium": chromium,
        "chromium": chromium,
        "msedge": edge,
        "edge": edge,
    }

    if mode in {"playwright_chromium", "chromium"}:
        return [chromium] if chromium else []
    if mode in {"msedge", "edge"}:
        return [edge] if edge else []

    result: list[BrowserCandidate] = []
    seen = set()
    for key in order:
        candidate = mapping.get(str(key).strip().lower())
        if candidate and candidate.key not in seen:
            seen.add(candidate.key)
            result.append(candidate)
    return result


def _legacy_profile_has_data(base: Path) -> bool:
    if not base.is_dir():
        return False
    ignored = {"chromium", "edge"}
    try:
        return any(child.name not in ignored for child in base.iterdir())
    except Exception:
        return False


def profile_dir_for_engine(base_profile: Path, engine_key: str, config: dict) -> Path:
    browser_cfg = config.get("browser") or {}
    preserve_legacy = bool(browser_cfg.get("preserve_legacy_chromium_profile", True))
    base_profile = Path(base_profile)

    if engine_key == "playwright_chromium":
        if preserve_legacy and _legacy_profile_has_data(base_profile):
            return base_profile
        return base_profile / "chromium"
    return base_profile / "edge"


def _launch_candidate(
    p,
    candidate: BrowserCandidate,
    profile_dir: Path,
    browser_cfg: dict,
    *,
    accept_downloads: bool,
):
    kwargs = {
        "user_data_dir": str(profile_dir),
        "headless": bool(browser_cfg.get("headless", False)),
        "viewport": {"width": 1440, "height": 900},
    }
    if accept_downloads:
        kwargs["accept_downloads"] = True

    if candidate.key == "msedge":
        strategy = str(browser_cfg.get("edge_launch_strategy", "channel_then_executable"))
        if strategy in {"channel_then_executable", "channel"}:
            try:
                return p.chromium.launch_persistent_context(
                    channel=candidate.channel or "msedge",
                    **kwargs,
                )
            except Exception:
                if strategy == "channel":
                    raise
        return p.chromium.launch_persistent_context(
            executable_path=candidate.executable_path,
            **kwargs,
        )

    return p.chromium.launch_persistent_context(**kwargs)


def launch_persistent_context_auto(
    p,
    browser_profile: Path,
    config: dict,
    log: Callable[[str], None],
    *,
    purpose: str,
    accept_downloads: bool = False,
):
    """
    Existing Playwright Chromium remains first priority. If it is unavailable or
    cannot be launched, AUTO mode falls back to installed Microsoft Edge.
    No browser download is performed here.
    """
    browser_cfg = config.get("browser") or {}
    mode = str(browser_cfg.get("mode", "auto")).strip().lower()
    candidates = list_available_candidates(p, config)

    if not candidates:
        raise BrowserLaunchError(
            "사용 가능한 브라우저를 찾지 못했습니다. "
            "기존 Playwright Chromium 또는 설치된 Microsoft Edge가 필요합니다. "
            "BoardRepo는 실행 중 브라우저를 자동 다운로드하지 않습니다."
        )

    errors = []
    for idx, candidate in enumerate(candidates, start=1):
        profile_dir = profile_dir_for_engine(browser_profile, candidate.key, config)
        profile_dir.mkdir(parents=True, exist_ok=True)
        log(
            f"브라우저 선택 [{purpose}] {idx}/{len(candidates)}: "
            f"{candidate.display_name} / profile={profile_dir}"
        )
        try:
            context = _launch_candidate(
                p,
                candidate,
                profile_dir,
                browser_cfg,
                accept_downloads=accept_downloads,
            )
            log(f"브라우저 실행 성공 [{purpose}]: {candidate.display_name}")
            return context, candidate
        except Exception as exc:
            errors.append(f"{candidate.display_name}: {type(exc).__name__}: {exc}")
            log(f"브라우저 실행 실패 [{purpose}]: {errors[-1]}")
            if mode not in {"auto", ""}:
                break
            if idx < len(candidates):
                log(f"다음 브라우저 후보로 자동 전환합니다: {candidates[idx].display_name}")

    raise BrowserLaunchError(
        "브라우저 자동 제어를 시작하지 못했습니다.\n" + "\n".join(errors)
    )


def probe_browser_control(config: dict) -> tuple[bool, str, str]:
    """Return (ok, selected_key, message) without touching the groupware."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "", "playwright 모듈이 없습니다."

    try:
        with sync_playwright() as p:
            candidates = list_available_candidates(p, config)
            if not candidates:
                return False, "", "기존 Chromium과 Microsoft Edge를 모두 찾지 못했습니다."
            errors = []
            browser_cfg = config.get("browser") or {}
            for candidate in candidates:
                try:
                    kwargs = {"headless": True}
                    if candidate.key == "msedge":
                        try:
                            browser = p.chromium.launch(
                                channel=candidate.channel or "msedge",
                                **kwargs,
                            )
                        except Exception:
                            browser = p.chromium.launch(
                                executable_path=candidate.executable_path,
                                **kwargs,
                            )
                    else:
                        browser = p.chromium.launch(**kwargs)
                    try:
                        page = browser.new_page()
                        page.goto("about:blank")
                    finally:
                        browser.close()
                    return True, candidate.key, f"{candidate.display_name} 자동 제어 가능"
                except Exception as exc:
                    errors.append(f"{candidate.display_name}: {type(exc).__name__}: {exc}")
                    if str(browser_cfg.get("mode", "auto")).lower() != "auto":
                        break
            return False, "", " / ".join(errors)
    except Exception as exc:
        return False, "", f"브라우저 제어 진단 실패: {type(exc).__name__}: {exc}"
