from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


class ExtFileError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExtFileInfo:
    path: Path
    size_bytes: int
    sha256: str


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _is_excluded(path: Path, config: dict) -> bool:
    name = path.name
    lower_name = name.casefold()

    if config.get("exclude_hidden", True) and name.startswith("."):
        return True

    for prefix in config.get("exclude_prefixes", ["~$"]):
        if name.startswith(prefix):
            return True

    excluded_names = {str(x).casefold() for x in config.get("exclude_names", [])}
    if lower_name in excluded_names:
        return True

    for suffix in config.get("exclude_suffixes", []):
        if lower_name.endswith(str(suffix).casefold()):
            return True

    return False


def list_ext_files(folder: Path, config: dict) -> list[ExtFileInfo]:
    if not folder.exists() or not folder.is_dir():
        raise ExtFileError(f"Ext 폴더를 찾지 못했습니다: {folder}")

    recursive = bool(config.get("recursive", False))
    if recursive:
        candidates = [p for p in folder.rglob("*") if p.is_file()]
    else:
        candidates = [p for p in folder.iterdir() if p.is_file()]

    included = [
        p for p in candidates
        if not _is_excluded(p, config)
    ]
    included.sort(key=lambda p: p.name.casefold())

    return [
        ExtFileInfo(
            path=p,
            size_bytes=p.stat().st_size,
            sha256=_sha256_file(p),
        )
        for p in included
    ]
