from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

_VERSION_RE = re.compile(r"^> \*\*Document Version:\*\*\s*(v\d+(?:\.\d+)*)\s*$", re.MULTILINE)

@dataclass(frozen=True)
class GovernanceStatus:
    path: Path
    exists: bool
    version: str | None
    sha256: str | None
    ok: bool
    message: str


def check_governance(root: Path, catalog: dict) -> GovernanceStatus:
    cfg = catalog.get("governance") or {}
    rel = str(cfg.get("path") or "00_AI_DEVELOPMENT_GOVERNANCE.md")
    path = Path(root) / rel
    if not path.is_file():
        return GovernanceStatus(path, False, None, None, False, f"Governance 누락: {rel}")
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    m = _VERSION_RE.search(text)
    version = m.group(1) if m else None
    digest = sha256(data).hexdigest()
    min_ver = str(cfg.get("minimum_document_version") or "").strip()
    if not version:
        return GovernanceStatus(path, True, None, digest, False, "Governance Document Version을 확인하지 못했습니다.")
    if min_ver and version != min_ver:
        return GovernanceStatus(path, True, version, digest, False, f"Governance Version 확인 필요: 현재 {version}, 기준 {min_ver}")
    return GovernanceStatus(path, True, version, digest, True, f"Governance {version} / SHA-256 {digest[:12]}...")
