from __future__ import annotations

import importlib
import importlib.util
import locale
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional


@dataclass
class EnvironmentStatus:
    python_ok: bool
    pip_ok: bool
    keyring_ok: bool
    playwright_ok: bool
    chromium_ok: bool
    chromium_path: str = ""

    @property
    def ready(self) -> bool:
        return (
            self.python_ok
            and self.pip_ok
            and self.keyring_ok
            and self.playwright_ok
            and self.chromium_ok
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
    """
    Runs a child process without requiring a .bat file.
    Output is forwarded into the BoardRepo GUI log.
    """
    log("$ " + " ".join(args))
    process = subprocess.Popen(
        args,
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

    return_code = process.wait(timeout=timeout)
    return return_code


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


def check_environment() -> EnvironmentStatus:
    importlib.invalidate_caches()
    python_ok = sys.version_info >= (3, 10)
    pip_ok = _pip_available()
    keyring_ok = _module_available("keyring")
    playwright_ok = _module_available("playwright")
    chromium_path = _chromium_executable()
    chromium_ok = bool(chromium_path)

    return EnvironmentStatus(
        python_ok=python_ok,
        pip_ok=pip_ok,
        keyring_ok=keyring_ok,
        playwright_ok=playwright_ok,
        chromium_ok=chromium_ok,
        chromium_path=chromium_path,
    )


def format_status(status: EnvironmentStatus) -> str:
    def mark(ok: bool) -> str:
        return "OK" if ok else "필요"

    lines = [
        f"Python 3.10+ : {mark(status.python_ok)}",
        f"pip          : {mark(status.pip_ok)}",
        f"keyring      : {mark(status.keyring_ok)}",
        f"playwright   : {mark(status.playwright_ok)}",
        f"Chromium     : {mark(status.chromium_ok)}",
    ]
    if status.chromium_path:
        lines.append(f"Chromium 경로: {status.chromium_path}")
    lines.append("")
    lines.append("최종 상태: 사용 가능" if status.ready else "최종 상태: 설치/복구 필요")
    return "\n".join(lines)


def install_or_repair(log: Callable[[str], None]) -> EnvironmentStatus:
    """
    Installs only BoardRepo's Python dependencies and Playwright Chromium.
    Does not use a batch file and does not require Git.
    """
    status = check_environment()

    if not status.python_ok:
        raise RuntimeError(
            "Python 3.10 이상이 필요합니다. 현재 Python 자체는 BoardRepo가 설치할 수 없습니다."
        )

    if not status.pip_ok:
        raise RuntimeError(
            "현재 Python에서 pip를 사용할 수 없습니다. "
            "Python 설치 옵션 또는 회사 PC 정책을 확인해야 합니다."
        )

    missing_packages = []
    if not status.keyring_ok:
        missing_packages.append("keyring")
    if not status.playwright_ok:
        missing_packages.append("playwright")

    if missing_packages:
        log("필수 Python 모듈을 설치합니다.")
        code = _run_command(
            [sys.executable, "-m", "pip", "install", *missing_packages],
            log,
        )
        if code != 0:
            raise RuntimeError(
                f"pip 설치가 실패했습니다. 종료 코드: {code}\n"
                "회사 PC의 네트워크/설치 권한 정책을 확인하세요."
            )
    else:
        log("keyring / playwright Python 모듈은 이미 설치되어 있습니다.")

    status = check_environment()

    if not status.playwright_ok:
        raise RuntimeError("playwright 설치 확인에 실패했습니다.")

    if not status.chromium_ok:
        log("Playwright Chromium을 설치합니다.")
        code = _run_command(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            log,
        )
        if code != 0:
            raise RuntimeError(
                f"Chromium 설치가 실패했습니다. 종료 코드: {code}\n"
                "회사 PC의 네트워크/보안 정책을 확인하세요."
            )
    else:
        log("Playwright Chromium은 이미 설치되어 있습니다.")

    final_status = check_environment()
    if not final_status.ready:
        raise RuntimeError(
            "설치 명령은 종료되었지만 BoardRepo 실행 환경이 아직 준비되지 않았습니다.\n"
            + format_status(final_status)
        )

    return final_status
