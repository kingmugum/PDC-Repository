from __future__ import annotations

import importlib
import importlib.util
import json
import locale
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional


FUNCTION_DIR = Path(__file__).resolve().parent
APP_ROOT = FUNCTION_DIR.parent
OFFLINE_ROOT = APP_ROOT / "offline_packages"
WHEELHOUSE_DIR = OFFLINE_ROOT / "windows_x64"
VENDOR_DIR = OFFLINE_ROOT / "vendor"
VENDOR_MANIFEST = VENDOR_DIR / "vendor_manifest.json"
OFFLINE_REQUIREMENTS = APP_ROOT / "offline_requirements_windows.txt"


def _runtime_tag() -> dict:
    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "implementation": platform.python_implementation(),
        "machine": platform.machine().lower(),
        "bits": 64 if sys.maxsize > 2**32 else 32,
        "platform": sys.platform,
    }


def _vendor_compatible() -> bool:
    if not VENDOR_DIR.is_dir() or not VENDOR_MANIFEST.is_file():
        return False
    try:
        data = json.loads(VENDOR_MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return False
    current = _runtime_tag()
    expected = data.get("runtime") or {}
    return (
        expected.get("python") == current["python"]
        and int(expected.get("bits", 0)) == current["bits"]
        and str(expected.get("platform", "")).lower() == current["platform"].lower()
    )


def bootstrap_vendor_runtime() -> bool:
    """Use a home-prepared portable dependency folder when runtime-compatible."""
    if not _vendor_compatible():
        return False
    vendor = str(VENDOR_DIR)
    if vendor not in sys.path:
        sys.path.insert(0, vendor)
        importlib.invalidate_caches()
    return True


# Run before any deferred keyring/playwright import elsewhere.
VENDOR_ACTIVE = bootstrap_vendor_runtime()


@dataclass
class EnvironmentStatus:
    python_ok: bool
    pip_ok: bool
    keyring_ok: bool
    playwright_ok: bool
    chromium_ok: bool
    edge_ok: bool
    selected_browser: str = ""
    browser_control_ok: bool | None = None
    browser_control_message: str = ""
    chromium_path: str = ""
    edge_path: str = ""
    vendor_active: bool = False
    offline_wheels_ready: bool = False

    @property
    def browser_available(self) -> bool:
        return bool(self.selected_browser)

    @property
    def ready(self) -> bool:
        # pip is a repair capability, not a runtime requirement once dependencies exist.
        return (
            self.python_ok
            and self.keyring_ok
            and self.playwright_ok
            and self.browser_available
            and self.browser_control_ok is not False
        )


def _hidden_creation_flags() -> int:
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def _run_command(
    args: List[str],
    log: Callable[[str], None],
    timeout: Optional[int] = None,
) -> int:
    log("$ " + " ".join(str(x) for x in args))
    process = subprocess.Popen(
        [str(x) for x in args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding=locale.getpreferredencoding(False) or "utf-8",
        errors="replace",
        creationflags=_hidden_creation_flags(),
    )

    assert process.stdout is not None
    for line in iter(process.stdout.readline, ""):
        line = line.rstrip()
        if line:
            log(line)

    return process.wait(timeout=timeout)


def _pip_available() -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=_hidden_creation_flags(),
            timeout=20,
        )
        return result.returncode == 0
    except Exception:
        return False


def _module_available(name: str) -> bool:
    importlib.invalidate_caches()
    return importlib.util.find_spec(name) is not None


def _chromium_executable() -> str:
    if not _module_available("playwright"):
        return ""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            path = Path(p.chromium.executable_path)
            return str(path) if path.exists() else ""
    except Exception:
        return ""


def _edge_executable() -> str:
    try:
        from browser_runtime import find_edge_executable
        return find_edge_executable()
    except Exception:
        return ""


def _offline_wheels_ready() -> bool:
    if not WHEELHOUSE_DIR.is_dir():
        return False
    return any(WHEELHOUSE_DIR.glob("*.whl"))


def _selected_browser_name(chromium_ok: bool, edge_ok: bool, config: dict | None) -> str:
    browser_cfg = (config or {}).get("browser") or {}
    mode = str(browser_cfg.get("mode", "auto")).strip().lower()
    if mode in {"playwright_chromium", "chromium"}:
        return "Playwright Chromium" if chromium_ok else ""
    if mode in {"msedge", "edge"}:
        return "Microsoft Edge" if edge_ok else ""
    order = list(browser_cfg.get("auto_order") or ["playwright_chromium", "msedge"])
    for item in order:
        key = str(item).strip().lower()
        if key in {"playwright_chromium", "chromium"} and chromium_ok:
            return "Playwright Chromium"
        if key in {"msedge", "edge"} and edge_ok:
            return "Microsoft Edge"
    return ""


def check_environment(config: dict | None = None, *, probe_browser: bool = False) -> EnvironmentStatus:
    bootstrap_vendor_runtime()
    python_ok = sys.version_info >= (3, 10)
    pip_ok = _pip_available()
    keyring_ok = _module_available("keyring")
    playwright_ok = _module_available("playwright")
    chromium_path = _chromium_executable() if playwright_ok else ""
    edge_path = _edge_executable()
    chromium_ok = bool(chromium_path)
    edge_ok = bool(edge_path)
    selected_browser = _selected_browser_name(chromium_ok, edge_ok, config)

    browser_control_ok: bool | None = None
    browser_control_message = ""
    if probe_browser and playwright_ok and selected_browser:
        try:
            from browser_runtime import probe_browser_control
            browser_control_ok, _, browser_control_message = probe_browser_control(config or {})
        except Exception as exc:
            browser_control_ok = False
            browser_control_message = f"브라우저 자동 제어 진단 실패: {exc}"

    return EnvironmentStatus(
        python_ok=python_ok,
        pip_ok=pip_ok,
        keyring_ok=keyring_ok,
        playwright_ok=playwright_ok,
        chromium_ok=chromium_ok,
        edge_ok=edge_ok,
        selected_browser=selected_browser,
        browser_control_ok=browser_control_ok,
        browser_control_message=browser_control_message,
        chromium_path=chromium_path,
        edge_path=edge_path,
        vendor_active=_vendor_compatible(),
        offline_wheels_ready=_offline_wheels_ready(),
    )


def format_status(status: EnvironmentStatus) -> str:
    def mark(ok: bool) -> str:
        return "OK" if ok else "필요"

    lines = [
        f"Python 3.10+      : {mark(status.python_ok)}",
        f"pip (복구용)      : {mark(status.pip_ok)}",
        f"keyring           : {mark(status.keyring_ok)}",
        f"playwright        : {mark(status.playwright_ok)}",
        f"Chromium (기존)    : {'OK' if status.chromium_ok else '없음/미사용'}",
        f"Microsoft Edge    : {'OK' if status.edge_ok else '없음'}",
        f"선택 브라우저       : {status.selected_browser or '없음'}",
        f"Portable Vendor   : {'사용 중' if status.vendor_active else '미사용'}",
        f"Offline Wheelhouse: {'준비됨' if status.offline_wheels_ready else '비어 있음'}",
    ]
    if status.chromium_path:
        lines.append(f"Chromium 경로      : {status.chromium_path}")
    if status.edge_path:
        lines.append(f"Edge 경로          : {status.edge_path}")
    if status.browser_control_ok is not None:
        lines.append(
            "브라우저 자동 제어 : "
            + ("OK" if status.browser_control_ok else "차단/실패")
        )
        if status.browser_control_message:
            lines.append(f"자동 제어 진단     : {status.browser_control_message}")
    lines.append("")
    lines.append("최종 상태: 사용 가능" if status.ready else "최종 상태: 준비/확인 필요")
    return "\n".join(lines)


def _missing_packages() -> list[str]:
    missing = []
    if not _module_available("keyring"):
        missing.append("keyring")
    if not _module_available("playwright"):
        missing.append("playwright")
    return missing


def _install_from_wheelhouse(log: Callable[[str], None]) -> bool:
    if not _offline_wheels_ready() or not OFFLINE_REQUIREMENTS.is_file():
        return False
    log("인터넷을 사용하지 않고 로컬 Offline Wheelhouse에서 설치를 시도합니다.")
    code = _run_command(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            f"--find-links={WHEELHOUSE_DIR}",
            "-r",
            str(OFFLINE_REQUIREMENTS),
        ],
        log,
    )
    importlib.invalidate_caches()
    bootstrap_vendor_runtime()
    return code == 0


def install_or_repair(log: Callable[[str], None], config: dict | None = None) -> EnvironmentStatus:
    """
    Company-safe repair policy:
      1) compatible portable vendor already bundled -> use it
      2) local wheelhouse + pip -> --no-index install
      3) optional online pip fallback only when config explicitly permits it
    It never runs `playwright install chromium` unless explicitly enabled.
    """
    config = config or {}
    env_cfg = config.get("environment") or {}
    status = check_environment(config)

    if not status.python_ok:
        raise RuntimeError("Python 3.10 이상이 필요합니다. Python 자체는 BoardRepo가 설치하지 않습니다.")

    if status.keyring_ok and status.playwright_ok:
        log("keyring / playwright 모듈이 이미 준비되어 있습니다.")
    else:
        if bootstrap_vendor_runtime():
            log("동봉된 Portable Vendor Runtime을 활성화했습니다.")

        if _missing_packages():
            if not status.pip_ok:
                raise RuntimeError(
                    "필수 모듈이 없고 pip도 사용할 수 없습니다.\n"
                    "집 PC에서 [회사용 오프라인 준비]를 실행하여 Portable Vendor를 만든 뒤 다시 가져오세요."
                )

            installed = _install_from_wheelhouse(log)
            if not installed and bool(env_cfg.get("allow_online_pip_fallback", False)):
                log("Offline Wheelhouse 설치가 불가능하여 설정상 허용된 온라인 pip 설치를 시도합니다.")
                code = _run_command(
                    [sys.executable, "-m", "pip", "install", "-r", str(OFFLINE_REQUIREMENTS)],
                    log,
                )
                installed = code == 0
            if not installed and _missing_packages():
                raise RuntimeError(
                    "필수 Python 모듈을 준비하지 못했습니다.\n"
                    "기본 회사 모드에서는 외부 PyPI 접속을 시도하지 않습니다.\n"
                    "인터넷이 가능한 집 PC에서 [회사용 오프라인 준비]를 먼저 실행해주세요."
                )

    final_status = check_environment(config, probe_browser=True)

    # Never auto-download Chromium in company-safe default mode.
    if not final_status.selected_browser:
        if bool(env_cfg.get("allow_playwright_browser_download", False)) and final_status.playwright_ok:
            if not final_status.pip_ok:
                raise RuntimeError("Chromium 다운로드가 허용되어 있지만 현재 pip/playwright 실행환경을 사용할 수 없습니다.")
            log("설정상 허용되어 Playwright Chromium 다운로드를 시도합니다.")
            code = _run_command([sys.executable, "-m", "playwright", "install", "chromium"], log)
            if code != 0:
                raise RuntimeError(f"Chromium 설치 실패. 종료 코드: {code}")
            final_status = check_environment(config, probe_browser=True)
        else:
            raise RuntimeError(
                "기존 Playwright Chromium도 없고 Microsoft Edge도 찾지 못했습니다.\n"
                "기본 회사 모드에서는 Chromium 외부 다운로드를 자동 시도하지 않습니다."
            )

    if not final_status.ready:
        raise RuntimeError("BoardRepo 실행 환경이 아직 준비되지 않았습니다.\n" + format_status(final_status))
    return final_status


def prepare_offline_packages(log: Callable[[str], None], config: dict | None = None) -> Path:
    """
    Run on an Internet-connected Windows PC before taking the package to a locked-down PC.
    Downloads Windows x64 wheels for CPython 3.10~3.14 into one wheelhouse and builds a
    current-runtime portable vendor folder so the destination may run even if pip is blocked.
    """
    if os.name != "nt":
        raise RuntimeError("회사용 오프라인 패키지 준비는 Windows PC에서 실행해주세요.")
    if not _pip_available():
        raise RuntimeError("오프라인 패키지를 준비하려면 인터넷 가능한 PC에서 pip가 필요합니다.")
    if not OFFLINE_REQUIREMENTS.is_file():
        raise RuntimeError(f"오프라인 요구사항 파일이 없습니다: {OFFLINE_REQUIREMENTS}")
    if sys.maxsize <= 2**32:
        raise RuntimeError("현재 준비 기능은 회사 환경 기준 Windows 64-bit용으로 구성되어 있습니다.")

    WHEELHOUSE_DIR.mkdir(parents=True, exist_ok=True)
    versions = ["310", "311", "312", "313", "314"]
    for pyver in versions:
        abi = f"cp{pyver}"
        log(f"Windows x64 CPython {pyver[0]}.{pyver[1:]} wheel 준비 중...")
        code = _run_command(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "--dest",
                str(WHEELHOUSE_DIR),
                "--only-binary=:all:",
                "--platform",
                "win_amd64",
                "--implementation",
                "cp",
                "--python-version",
                pyver,
                "--abi",
                abi,
                "-r",
                str(OFFLINE_REQUIREMENTS),
            ],
            log,
        )
        if code != 0:
            raise RuntimeError(f"CPython {pyver}용 오프라인 wheel 다운로드 실패. 종료 코드: {code}")

    # Build a zero-pip portable runtime for the current Python version as an extra fallback.
    if VENDOR_DIR.exists():
        import shutil
        shutil.rmtree(VENDOR_DIR)
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    log("현재 PC Python과 호환되는 Portable Vendor Runtime을 생성합니다.")
    code = _run_command(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            f"--find-links={WHEELHOUSE_DIR}",
            "--target",
            str(VENDOR_DIR),
            "-r",
            str(OFFLINE_REQUIREMENTS),
        ],
        log,
    )
    if code != 0:
        raise RuntimeError(f"Portable Vendor Runtime 생성 실패. 종료 코드: {code}")

    manifest = {
        "prepared_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "runtime": _runtime_tag(),
        "wheelhouse": "windows_x64 / CPython 3.10~3.14",
        "requirements": OFFLINE_REQUIREMENTS.name,
        "purpose": "locked-down company PC offline BoardRepo dependencies",
    }
    VENDOR_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    bootstrap_vendor_runtime()
    log(f"회사 PC용 오프라인 준비 완료: {OFFLINE_ROOT}")
    return OFFLINE_ROOT
