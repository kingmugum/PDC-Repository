from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re


def next_boardrepo_release_id(
    directory: Path,
    date_token: str | None = None,
) -> str:
    """
    Return YYMMDD_N for the next BoardRepo distribution ZIP.

    Example:
      existing:
        BoardRepo_260808_1.zip
        BoardRepo_260808_3.zip
      result:
        260808_4

    A new date naturally starts at _1 because only files matching that date are
    considered.
    """
    token = date_token or datetime.now().strftime("%y%m%d")
    pattern = re.compile(
        rf"^BoardRepo_{re.escape(token)}_(\d+)\.zip$",
        re.IGNORECASE,
    )

    counters: list[int] = []
    for path in directory.glob(f"BoardRepo_{token}_*.zip"):
        match = pattern.match(path.name)
        if match:
            counters.append(int(match.group(1)))

    return f"{token}_{max(counters, default=0) + 1}"


def distribution_filename(release_id: str) -> str:
    return f"BoardRepo_{release_id}.zip"
