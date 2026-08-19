from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List


class FolderResolutionError(RuntimeError):
    pass


def app_root() -> Path:
    """
    Returns the directory containing BoardRepo itself.

    - Normal Python execution: directory containing this .py file
    - Packaged executable (e.g. PyInstaller): directory containing the .exe

    This intentionally does NOT use the current working directory because a
    shortcut or another agent may start the program from another directory.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


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
