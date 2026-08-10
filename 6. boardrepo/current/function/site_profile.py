from __future__ import annotations

import json
from pathlib import Path


class SiteProfileError(RuntimeError):
    pass


def load_site_profile(path: Path) -> dict:
    if not path.exists():
        raise SiteProfileError(f"사이트 프로필 파일이 없습니다: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            profile = json.load(f)
    except Exception as exc:
        raise SiteProfileError(f"site_profile.json 읽기 실패: {exc}") from exc

    required = ["routing", "login", "board", "editor", "verification"]
    missing = [key for key in required if key not in profile]
    if missing:
        raise SiteProfileError(
            "site_profile.json 필수 항목 누락: " + ", ".join(missing)
        )
    return profile


def write_url_for(board_url: str, profile: dict) -> str:
    template = profile["routing"].get(
        "write_url_template",
        "{board_url}/post/write",
    )
    return template.format(board_url=board_url.rstrip("/"))
