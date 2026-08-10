from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable, Tuple


EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "browser_profile",
    "snapshots",
}

EXCLUDE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".tmp",
}


def _should_include(path: Path, source_root: Path) -> bool:
    rel_parts = path.relative_to(source_root).parts
    if any(part in EXCLUDE_DIRS for part in rel_parts):
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    return True


def iter_source_files(source_root: Path) -> Iterable[Path]:
    for path in sorted(source_root.rglob("*")):
        if path.is_file() and _should_include(path, source_root):
            yield path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def next_version(snapshot_dir: Path, target_key: str, now: datetime | None = None) -> str:
    now = now or datetime.now()
    date_token = now.strftime("%y%m%d")
    prefix = f"{target_key}_{date_token}_rev"

    highest = 0
    for path in snapshot_dir.glob(f"{prefix}*.zip"):
        tail = path.stem.split("_rev")[-1]
        if tail.isdigit():
            highest = max(highest, int(tail))

    return f"{date_token}_rev{highest + 1:02d}"


def create_snapshot(source_root: Path, snapshot_dir: Path, target_key: str) -> Tuple[Path, str]:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    version = next_version(snapshot_dir, target_key)
    zip_path = snapshot_dir / f"{target_key}_{version}.zip"

    manifest_lines = [
        "BoardRepo Snapshot",
        f"Target: {target_key}",
        f"Version: {version}",
        f"Created: {datetime.now().isoformat(timespec='seconds')}",
        f"Source: {source_root}",
        "",
        "[Files]",
    ]

    files = list(iter_source_files(source_root))
    if not files:
        raise RuntimeError(f"백업할 파일이 없습니다: {source_root}")

    for path in files:
        rel = path.relative_to(source_root)
        manifest_lines.append(f"{rel}\tSHA256={sha256_file(path)}")

    manifest_text = "\n".join(manifest_lines) + "\n"

    import zipfile
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            rel = Path(source_root.name) / path.relative_to(source_root)
            zf.write(path, rel.as_posix())
        zf.writestr("VERSION_INFO.txt", manifest_text)

    return zip_path, version
