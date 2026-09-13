from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

_RELEASE_RE = re.compile(r"(?:^|[_\-\s])(\d{6})(?:[_\-\s](\d+))?(?=$|[_\-\s])")
_SEMVER_RE = re.compile(r"(?:^|[_\-\s])V(?P<version>\d+(?:\.\d+){1,3})(?=$|[_\-\s])", re.IGNORECASE)


@dataclass(frozen=True, order=True)
class Release:
    date: str
    counter: int
    filename: str = ""

    @property
    def label(self) -> str:
        return f"{self.date}_{self.counter}"


@dataclass(frozen=True, order=True)
class SemanticRelease:
    version: tuple[int, int, int, int]
    raw_parts: tuple[int, ...]
    filename: str = ""

    @property
    def label(self) -> str:
        return "V" + ".".join(str(x) for x in self.raw_parts)


def parse_semantic_release_name(name: str) -> SemanticRelease | None:
    stem = Path(name).stem
    matches = list(_SEMVER_RE.finditer(stem))
    if not matches:
        return None
    match = matches[-1]
    raw_parts = tuple(int(x) for x in match.group("version").split("."))
    if len(raw_parts) < 2 or len(raw_parts) > 4:
        return None
    padded = raw_parts + (0,) * (4 - len(raw_parts))
    return SemanticRelease(padded, raw_parts, Path(name).name)


def latest_semantic_release(names: list[str], prefixes: list[str] | None = None) -> SemanticRelease | None:
    prefixes_cf = [p.casefold() for p in (prefixes or [])]
    found = []
    for name in names:
        base = Path(name).name
        stem_cf = Path(base).stem.casefold()
        if prefixes_cf and not any(stem_cf.startswith(p) for p in prefixes_cf):
            continue
        rel = parse_semantic_release_name(base)
        if rel:
            found.append(rel)
    return max(found) if found else None


def parse_release_name(name: str) -> Release | None:
    stem = Path(name).stem
    matches = list(_RELEASE_RE.finditer(stem))
    if not matches:
        return None
    m = matches[-1]
    token = m.group(1)
    yy, mm, dd = int(token[:2]), int(token[2:4]), int(token[4:6])
    try:
        import datetime as _dt
        _dt.date(2000 + yy, mm, dd)
    except ValueError:
        return None
    return Release(token, int(m.group(2) or 0), Path(name).name)


def latest_release(names: list[str], prefixes: list[str] | None = None) -> Release | None:
    prefixes_cf = [p.casefold() for p in (prefixes or [])]
    found = []
    for name in names:
        base = Path(name).name
        if prefixes_cf and not any(Path(base).stem.casefold().startswith(p) for p in prefixes_cf):
            continue
        rel = parse_release_name(base)
        if rel:
            found.append(rel)
    return max(found) if found else None
