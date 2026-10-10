from __future__ import annotations

from datetime import datetime
from pathlib import Path

OUTPUT_REVISION = "V0.0"


def dated_revision_suffix(now: datetime | None = None) -> str:
    current = now or datetime.now()
    return f"{current.strftime('%y%m%d')}_{OUTPUT_REVISION}"


def output_filename(prefix: str, source_stem: str, extension: str, *, now: datetime | None = None) -> str:
    return f"{prefix}_{source_stem}_{dated_revision_suffix(now)}.{extension.lstrip('.')}"
