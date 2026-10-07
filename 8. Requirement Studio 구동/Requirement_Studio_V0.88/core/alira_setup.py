from __future__ import annotations

import os
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ALIRA_INSTALL_BAT_URL = "http://10.10.10.200:19690/alira/install.bat"
DEFAULT_MODEL = "hosted_vllm/Qwen/Qwen3.6-27B"
DEFAULT_API_BASE = "http://10.10.10.200:19640/v1"


def default_cli_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    return Path(local_app_data) / "Programs" / "alira" / "alira.exe"


def project_license_dir(project_root: Path) -> Path:
    return Path(project_root).resolve() / "alira_license"


def find_project_license(project_root: Path) -> Path | None:
    folder = project_license_dir(project_root)
    folder.mkdir(parents=True, exist_ok=True)
    candidates = sorted(
        (p for p in folder.glob("*.lic") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def default_installed_license() -> Path | None:
    path = default_cli_path().with_name("license.lic")
    return path if path.is_file() else None


def resolve_license_path(project_root: Path, configured_path: str | None = None) -> Path | None:
    value = str(configured_path or "").strip()
    if value:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = Path(project_root).resolve() / path
        if path.is_file():
            return path.resolve()
    project_license = find_project_license(project_root)
    if project_license:
        return project_license.resolve()
    installed = default_installed_license()
    return installed.resolve() if installed else None


def build_alira_env(project_root: Path, configured_path: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    license_path = resolve_license_path(project_root, configured_path)
    if license_path:
        env["ALIRA_LICENSE_PATH"] = str(license_path)
    return env


def relative_config_path(project_root: Path, path: Path) -> str:
    root = Path(project_root).resolve()
    try:
        return path.resolve().relative_to(root).as_posix()
    except Exception:
        return str(path.resolve())


def _decode_output(data: bytes | None) -> str:
    if not data:
        return ""
    for encoding in ("utf-8", "cp949", "mbcs"):
        try:
            return data.decode(encoding)
        except Exception:
            continue
    return data.decode("utf-8", errors="replace")


def install_alira_cli_windows(timeout_seconds: int = 240) -> str:
    """Install the local ALIRA CLI using the corporate Windows install script.

    The user must explicitly approve this action in the GUI before this function is called.
    Requirement Studio does not install the remote Qwen model; it only prepares the local CLI
    which then connects to the configured remote vLLM API.
    """
    if os.name != "nt":
        raise RuntimeError("ALIRA CLI 자동 설치는 현재 Windows에서만 지원합니다.")

    temp_dir = Path(tempfile.mkdtemp(prefix="requirement_studio_alira_"))
    installer = temp_dir / "install_alira.bat"
    try:
        urllib.request.urlretrieve(ALIRA_INSTALL_BAT_URL, installer)
    except Exception as exc:
        raise RuntimeError(f"ALIRA 설치 스크립트 다운로드에 실패했습니다: {exc}") from exc

    try:
        process = subprocess.run(
            ["cmd.exe", "/c", str(installer)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=max(30, int(timeout_seconds)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("ALIRA CLI 자동 설치 시간이 초과되었습니다.") from exc
    except Exception as exc:
        raise RuntimeError(f"ALIRA 설치 스크립트 실행에 실패했습니다: {exc}") from exc

    stdout = _decode_output(process.stdout).strip()
    stderr = _decode_output(process.stderr).strip()
    combined = "\n".join(x for x in (stdout, stderr) if x).strip()
    if process.returncode != 0:
        raise RuntimeError(
            "ALIRA CLI 자동 설치가 실패했습니다.\n"
            f"Exit code: {process.returncode}\n"
            f"{combined or '세부 출력이 없습니다.'}"
        )
    if not default_cli_path().is_file():
        raise RuntimeError(
            "설치 스크립트는 종료되었지만 ALIRA 실행 파일을 찾지 못했습니다.\n"
            f"예상 위치: {default_cli_path()}"
        )
    return combined or "ALIRA CLI 설치가 완료되었습니다."


@dataclass
class AliraSetupStatus:
    cli_path: Path
    cli_exists: bool
    license_path: Path | None
    model: str
    api_base: str

    @property
    def ready_for_test(self) -> bool:
        return bool(self.cli_exists and self.license_path and self.model and self.api_base)


def inspect_setup(project_root: Path, alira_config: dict) -> AliraSetupStatus:
    cfg = alira_config or {}
    cli = default_cli_path()
    license_path = resolve_license_path(project_root, cfg.get("license_path"))
    return AliraSetupStatus(
        cli_path=cli,
        cli_exists=cli.is_file(),
        license_path=license_path,
        model=str(cfg.get("model") or DEFAULT_MODEL),
        api_base=str(cfg.get("api_base") or DEFAULT_API_BASE),
    )
