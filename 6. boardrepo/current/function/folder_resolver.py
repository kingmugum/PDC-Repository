from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List


class FolderResolutionError(RuntimeError):
    pass


def runtime_root() -> Path:
    """
    Returns the directory containing the actual BoardRepo runtime.

    Integrated layout:
      <Repository Root>/6. boardrepo/current/

    Standalone fallback:
      directory containing BoardRepo.pyw
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def app_root() -> Path:
    """
    Returns the shared repository/data root used for 1~4 target folders.

    Integrated layout:
      <Repository Root>/
        1. PassFail/
        2. SignalExport/
        3. Ext/
        4. Backup/
        6. boardrepo/current/

    When the runtime is not under '6. boardrepo/current', keep legacy
    standalone behavior and use the runtime directory itself.
    """
    runtime = runtime_root()

    if runtime.name.casefold() == "current":
        boardrepo_dir = runtime.parent
        normalized = re.sub(r"[^0-9a-zA-Z가-힣]+", "", boardrepo_dir.name).lower()
        if normalized == "6boardrepo":
            return boardrepo_dir.parent

    return runtime

def normalize_name(value: str) -> str:
    """
    Normalizes a folder/command alias:
      - lowercase
      - removes spaces, underscores, hyphens and other non-alphanumerics
      - keeps Korean characters
    """
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", value).lower()


def resolve_target_folder(root: Path, aliases: Iterable[str]) -> Path:
    """
    Searches immediate child directories of root and matches them against
    configured aliases after normalization.

    Safety behavior:
      - zero matches -> error
      - one match -> use it
      - multiple matches -> error (never guesses)
    """
    alias_set = {normalize_name(a) for a in aliases}
    matches: List[Path] = []

    if not root.exists():
        raise FolderResolutionError(f"BoardRepo 기준 폴더가 없습니다: {root}")

    for child in root.iterdir():
        if not child.is_dir():
            continue
        if child.name.startswith("."):
            continue
        if child.name in {"snapshots", "browser_profile", "__pycache__"}:
            continue
        if normalize_name(child.name) in alias_set:
            matches.append(child)

    if not matches:
        raise FolderResolutionError(
            "대상 폴더를 찾지 못했습니다.\n"
            f"BoardRepo 위치: {root}\n"
            f"허용 별칭: {', '.join(aliases)}"
        )

    if len(matches) > 1:
        names = "\n".join(f" - {p.name}" for p in matches)
        raise FolderResolutionError(
            "동일 대상으로 판단되는 폴더가 2개 이상 발견되었습니다.\n"
            "안전을 위해 임의 선택하지 않습니다.\n"
            f"{names}"
        )

    return matches[0]
