from __future__ import annotations

import json
from pathlib import Path


def load_catalog(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    targets = data.get("targets") or []
    ids = [int(t["id"]) for t in targets]
    keys = [str(t["key"]) for t in targets]
    folders = [str(t["folder"]) for t in targets]
    if ids != list(range(1, len(targets) + 1)):
        raise ValueError("program_catalog target id는 1부터 연속이어야 합니다.")
    if len(set(keys)) != len(keys):
        raise ValueError("program_catalog target key가 중복됩니다.")
    if len(set(folders)) != len(folders):
        raise ValueError("program_catalog target folder가 중복됩니다.")
    return data


def target_map(catalog: dict) -> dict[str, dict]:
    return {str(t["key"]): t for t in catalog.get("targets") or []}


def boardrepo_targets_from_catalog(catalog: dict) -> dict[str, dict]:
    result = {}
    for t in catalog.get("targets") or []:
        mode = t.get("mode")
        item = {
            "display_name": t["display_name"],
            "ui_label": t["ui_label"],
            "board_url": t["board_url"],
            "folder_aliases": list(t.get("aliases") or [t["folder"]]),
            "package_aliases": list(t.get("package_prefixes") or t.get("aliases") or [t["folder"]]),
            "mode": mode,
        }
        if mode == "versioned_archive":
            item.update({
                "archive_strategy": t.get("archive_strategy", "date_counter_release"),
                "recommended_filename": t.get("recommended_filename", f"{t['key']}_YYMMDD_N.zip"),
                "revision_in_package_name": False,
            })
        elif mode == "archive_family":
            item.update({
                "upload_mode": "archive_inbox",
                "accepted_extensions": [".zip", ".7z", ".rar"],
            })
        result[t["key"]] = item
    return result
