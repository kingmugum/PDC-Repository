from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

_RELEASE_RE = re.compile(r"(?:^|[_\-\s])(\d{6})(?:[_\-\s](\d+))?(?=$|[_\-\s])")


@dataclass(frozen=True, order=True)
class Release:
    date: str
    counter: int
    filename: str = ""

    @property
    def label(self) -> str:
        return f"{self.date}_{self.counter}"


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
