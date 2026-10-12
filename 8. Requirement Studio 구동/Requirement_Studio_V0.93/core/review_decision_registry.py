from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "REQ-STUDIO-REVIEW-DECISIONS-1.0"
CLOSED_MODE_DISPOSITIONS = {"CONFIRMED_INTENTIONAL", "HARMONIZED", "NOT_APPLICABLE"}


def _base_dir() -> Path:
    override = str(os.environ.get("REQUIREMENT_STUDIO_REVIEW_REGISTRY_DIR") or "").strip()
    if override:
        return Path(override)
    local = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local:
        return Path(local) / "RequirementStudio" / "review_decisions"
    return Path.home() / ".requirement_studio" / "review_decisions"


def mode_transition_registry_path() -> Path:
    return _base_dir() / "mode_transition_decisions.json"


def load_mode_transition_decisions() -> dict[str, dict[str, Any]]:
    path = mode_transition_registry_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    decisions = data.get("decisions") if isinstance(data, dict) else None
    if not isinstance(decisions, dict):
        return {}
    return {str(k): v for k, v in decisions.items() if isinstance(v, dict)}


def save_mode_transition_decisions(decisions: dict[str, dict[str, Any]]) -> Path:
    path = mode_transition_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "instructions": (
            "Key by stable finding_id. Allowed disposition examples: PENDING, CONFIRMED_INTENTIONAL, "
            "HARMONIZED, NOT_APPLICABLE. Requirement Studio never auto-closes a finding."
        ),
        "decisions": decisions,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def record_mode_transition_decision(
    finding_id: str,
    *,
    disposition: str,
    owner: str = "",
    rationale: str = "",
    reviewed_at: str = "",
) -> Path:
    decisions = load_mode_transition_decisions()
    decisions[str(finding_id)] = {
        "disposition": str(disposition or "PENDING").upper(),
        "owner": str(owner or ""),
        "rationale": str(rationale or ""),
        "reviewed_at": str(reviewed_at or ""),
    }
    return save_mode_transition_decisions(decisions)
