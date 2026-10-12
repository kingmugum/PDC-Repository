from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


DECISIONS = {"YES", "NO", "CONDITIONAL", "DEFER"}
APPLIED_DECISIONS = {"YES", "NO", "CONDITIONAL"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _default_policy_home() -> Path:
    override = str(os.environ.get("REQUIREMENT_STUDIO_POLICY_HOME") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    local_appdata = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local_appdata:
        return (Path(local_appdata) / "RequirementStudio" / "human_policy").resolve()
    xdg = str(os.environ.get("XDG_CONFIG_HOME") or "").strip()
    if xdg:
        return (Path(xdg) / "RequirementStudio" / "human_policy").resolve()
    return (Path.home() / ".requirement_studio" / "human_policy").resolve()




def _sha256_text_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _selected_marker(value: str) -> bool:
    marker = str(value or "").strip().lower().replace(" ", "")
    return marker in {"o", "x", "v", "✓", "✔", "*", "●", "○"}

class HumanPolicyRegistry:
    """Persistent cross-version Human Engineering Policy registry.

    The package carries a conservative seed.  The authoritative user registry lives outside the
    extracted version directory so deleting V0.79/V0.80/V0.81 folders does not delete the user's policy
    decisions.  Package seed entries are merged only when their policy ID is missing; an existing
    local human decision is never overwritten by a newly downloaded package.
    """

    SCHEMA_VERSION = "1.0"

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.seed_json = self.project_root / "policy" / "human_policy_seed.json"
        self.seed_txt = self.project_root / "policy" / "human_policy_seed.txt"
        self.home = _default_policy_home()
        self.registry_json = self.home / "human_policy_registry.json"
        self.registry_txt = self.home / "human_policy_registry.txt"
        self.change_log = self.home / "policy_change_log.jsonl"

    @staticmethod
    def _empty_registry() -> dict[str, Any]:
        return {
            "schema_version": HumanPolicyRegistry.SCHEMA_VERSION,
            "registry_name": "Requirement Studio Human Policy Registry",
            "created_at": _now(),
            "updated_at": _now(),
            "policies": [],
            "imported_guide_decision_files": {},
        }

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def _load_seed(self) -> dict[str, Any]:
        seed = self._read_json(self.seed_json)
        if not seed:
            return self._empty_registry()
        seed.setdefault("schema_version", self.SCHEMA_VERSION)
        seed.setdefault("policies", [])
        return seed

    @staticmethod
    def _normalize_policy(policy: dict[str, Any]) -> dict[str, Any]:
        p = deepcopy(policy)
        p["policy_id"] = str(p.get("policy_id") or p.get("question_id") or "").strip()
        p["decision"] = str(p.get("decision") or "DEFER").strip().upper()
        if p["decision"] not in DECISIONS:
            p["decision"] = "DEFER"
        p["title"] = str(p.get("title") or p.get("policy_topic") or p["policy_id"]).strip()
        p["reuse_scope"] = str(p.get("reuse_scope") or "").strip()
        p["notes"] = str(p.get("notes") or p.get("conditional_rule") or "").strip()
        p["status"] = str(p.get("status") or "ACTIVE").strip().upper()
        p["source"] = str(p.get("source") or "Human Policy Registry").strip()
        p["updated_at"] = str(p.get("updated_at") or _now())
        return p

    def _merge_seed(self, registry: dict[str, Any], seed: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        out = deepcopy(registry) if registry else self._empty_registry()
        out.setdefault("policies", [])
        existing = {
            str(p.get("policy_id") or ""): p
            for p in out.get("policies") or [] if isinstance(p, dict) and str(p.get("policy_id") or "")
        }
        added: list[str] = []
        for raw in seed.get("policies") or []:
            if not isinstance(raw, dict):
                continue
            p = self._normalize_policy(raw)
            pid = p["policy_id"]
            if not pid or pid in existing:
                continue
            p.setdefault("seeded_from_package", True)
            out["policies"].append(p)
            existing[pid] = p
            added.append(pid)
        out["schema_version"] = self.SCHEMA_VERSION
        out["updated_at"] = _now()
        return out, added

    @staticmethod
    def parse_guide_person_decisions(text: str) -> list[dict[str, Any]]:
        """Parse explicit human checkbox selections from a GUIDE_PERSON TXT.

        Generated files start with all boxes blank.  A decision is imported only when exactly one
        YES/NO/CONDITIONAL/DEFER box is explicitly marked by the engineer.  AI suggestions are never
        interpreted as human approval.
        """
        lines = str(text or "").splitlines()
        decisions: list[dict[str, Any]] = []
        qre = re.compile(r"^\s*\d+\.\s+(GP-[A-Z0-9_-]+)\s+[—-]\s+(.+?)\s*$", re.I)
        i = 0
        while i < len(lines):
            m = qre.match(lines[i])
            if not m:
                i += 1
                continue
            pid = m.group(1).upper()
            title = m.group(2).strip()
            j = i + 1
            block: list[str] = []
            while j < len(lines) and not qre.match(lines[j]) and lines[j].strip() != "Governance Boundary":
                block.append(lines[j])
                j += 1
            selected: list[str] = []
            reuse_scope = ""
            notes_lines: list[str] = []
            in_notes = False
            for line in block:
                stripped = line.strip()
                if stripped.startswith("Policy Reuse Scope:"):
                    reuse_scope = stripped.split(":", 1)[1].strip()
                dm = re.match(r"^\s*\[\s*([^\]]*)\s*\]\s*(YES|NO|CONDITIONAL|DEFER)\s*$", line, re.I)
                if dm and _selected_marker(dm.group(1)):
                    selected.append(dm.group(2).upper())
                if stripped == "Conditional Rule / Notes:":
                    in_notes = True
                    continue
                if in_notes:
                    notes_lines.append(line.rstrip())
            if len(set(selected)) == 1:
                notes = "\n".join(notes_lines).strip()
                decisions.append({
                    "policy_id": pid,
                    "title": title,
                    "decision": selected[0],
                    "reuse_scope": reuse_scope,
                    "notes": notes,
                })
            i = max(j, i + 1)
        return decisions

    def _guide_decision_files(self) -> list[Path]:
        base = self.project_root / "review_exchange"
        if not base.is_dir():
            return []
        return sorted(
            [p for p in base.glob("*/automatic_evaluation/guide_person/guide_person_*.txt") if p.is_file()],
            key=lambda p: (p.stat().st_mtime_ns, str(p)),
        )

    def _ingest_completed_guide_person(self, registry: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Import explicit engineer selections from completed GUIDE_PERSON handoffs.

        This creates the missing feedback loop for V0.79: an engineer may mark one checkbox in a
        generated `guide_person_###.txt`; the *next* run imports that decision into the external
        registry before candidate questions are resolved.  Imported file hashes are tracked so an
        unchanged handoff is never re-applied.  Editing the file later creates a new auditable update.
        """
        out = deepcopy(registry) if registry else self._empty_registry()
        out.setdefault("policies", [])
        imported = out.setdefault("imported_guide_decision_files", {})
        pmap = {
            str(p.get("policy_id") or ""): p
            for p in out.get("policies") or []
            if isinstance(p, dict) and str(p.get("policy_id") or "")
        }
        events: list[dict[str, Any]] = []
        for path in self._guide_decision_files():
            try:
                digest = _sha256_text_file(path)
                rel = str(path.relative_to(self.project_root)).replace("\\", "/")
            except Exception:
                continue
            previous = imported.get(rel) if isinstance(imported, dict) else None
            if isinstance(previous, dict) and str(previous.get("sha256") or "") == digest:
                continue
            try:
                decisions = self.parse_guide_person_decisions(path.read_text(encoding="utf-8"))
            except Exception:
                decisions = []
            imported[rel] = {
                "sha256": digest,
                "processed_at": _now(),
                "decision_count": len(decisions),
            }
            for d in decisions:
                pid = d["policy_id"]
                existing = pmap.get(pid)
                before = str((existing or {}).get("decision") or "")
                if existing is None:
                    existing = self._normalize_policy({
                        **d,
                        "status": "ACTIVE",
                        "source": f"GUIDE_PERSON human decision: {rel}",
                    })
                    out["policies"].append(existing)
                    pmap[pid] = existing
                else:
                    existing["decision"] = d["decision"]
                    if d.get("title"):
                        existing["title"] = d["title"]
                    if d.get("reuse_scope"):
                        existing["reuse_scope"] = d["reuse_scope"]
                    # For CONDITIONAL, entered notes are part of the policy.  For other decisions,
                    # non-empty notes still remain useful rationale; blank text never deletes an
                    # earlier human rationale accidentally.
                    if d.get("notes"):
                        existing["notes"] = d["notes"]
                    existing["source"] = f"GUIDE_PERSON human decision: {rel}"
                    existing["updated_at"] = _now()
                events.append({
                    "event": "GUIDE_PERSON_DECISION_IMPORT",
                    "policy_id": pid,
                    "previous_decision": before,
                    "decision": d["decision"],
                    "source_file": rel,
                    "source_sha256": digest,
                })
        out["updated_at"] = _now()
        return out, events

    @staticmethod
    def render_text(registry: dict[str, Any]) -> str:
        lines = [
            "Requirement Studio Human Policy Registry",
            "=" * 72,
            f"Schema Version: {registry.get('schema_version','')}",
            f"Updated At: {registry.get('updated_at','')}",
            "",
            "Purpose",
            "-------",
            "사람이 승인한 cross-document Engineering Policy를 버전과 독립적으로 보존합니다.",
            "새 Requirement Studio 버전을 내려받아 기존 버전 폴더를 삭제해도 이 Registry는 유지됩니다.",
            "Package의 human_policy_seed는 누락된 Policy ID만 보충하며 기존 로컬 사람 결정을 덮어쓰지 않습니다.",
            "",
        ]
        policies = [x for x in (registry.get("policies") or []) if isinstance(x, dict)]
        if not policies:
            lines.append("No registered human policy.")
        for idx, p in enumerate(policies, 1):
            lines += [
                f"{idx}. {p.get('policy_id','')} — {p.get('title','')}",
                "-" * 72,
                f"Decision: {p.get('decision','')}",
                f"Status: {p.get('status','')}",
                f"Reuse Scope: {p.get('reuse_scope','')}",
                f"Source: {p.get('source','')}",
                f"Notes: {p.get('notes','') or '[NONE]'}",
                "",
            ]
        return "\n".join(lines).rstrip() + "\n"

    def save(self, registry: dict[str, Any], *, change_event: dict[str, Any] | None = None) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        registry = deepcopy(registry)
        registry["updated_at"] = _now()
        _atomic_write_text(self.registry_json, json.dumps(registry, ensure_ascii=False, indent=2) + "\n")
        _atomic_write_text(self.registry_txt, self.render_text(registry))
        if change_event:
            event = {"timestamp": _now(), **change_event}
            with self.change_log.open("a", encoding="utf-8", newline="") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def load(self) -> dict[str, Any]:
        self.home.mkdir(parents=True, exist_ok=True)
        local = self._read_json(self.registry_json)
        seed = self._load_seed()
        merged, added = self._merge_seed(local or self._empty_registry(), seed)
        merged, guide_events = self._ingest_completed_guide_person(merged)
        needs_save = bool(added or guide_events or not self.registry_json.is_file() or not self.registry_txt.is_file())
        if needs_save:
            # Persist one registry state atomically, then append individual human-decision audit events.
            self.save(merged, change_event={
                "event": "REGISTRY_REFRESH",
                "added_seed_policy_ids": added,
                "imported_guide_decision_count": len(guide_events),
                "package_seed": self.seed_json.name if self.seed_json.is_file() else "",
            })
            if guide_events:
                with self.change_log.open("a", encoding="utf-8", newline="") as f:
                    for event in guide_events:
                        f.write(json.dumps({"timestamp": _now(), **event}, ensure_ascii=False) + "\n")
        return merged

    @staticmethod
    def policy_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            str(p.get("policy_id") or ""): p
            for p in (registry.get("policies") or [])
            if isinstance(p, dict) and str(p.get("policy_id") or "") and str(p.get("status") or "ACTIVE").upper() == "ACTIVE"
        }

    def resolve_guide_report(self, report: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
        out = deepcopy(report)
        policies = self.policy_map(registry)
        candidate_questions = [q for q in (report.get("questions") or []) if isinstance(q, dict)]
        applied: list[dict[str, Any]] = []
        unresolved: list[dict[str, Any]] = []
        for q in candidate_questions:
            qid = str(q.get("question_id") or "")
            p = policies.get(qid)
            if p and str(p.get("decision") or "").upper() in APPLIED_DECISIONS:
                applied.append({
                    "policy_id": qid,
                    "title": p.get("title") or q.get("policy_topic"),
                    "decision": p.get("decision"),
                    "reuse_scope": p.get("reuse_scope") or q.get("reuse_scope"),
                    "notes": p.get("notes") or "",
                    "observed_examples": list(q.get("observed_examples") or []),
                    "application_result": "REUSED_EXISTING_HUMAN_POLICY",
                })
            else:
                unresolved.append(q)
        for core_policy_id, application_result in (
            ("HP-PRESERVE-001", "CORE_PRESERVATION_POLICY_APPLIED"),
            ("HP-E2E-001", "CORE_E2E_REQUIREMENT_POLICY_APPLIED"),
            ("HP-SYSVER-001", "CORE_SYSTEM_VERIFICATION_POLICY_APPLIED"),
        ):
            core_policy = policies.get(core_policy_id)
            if core_policy and str(core_policy.get("decision") or "").upper() in APPLIED_DECISIONS:
                applied.append({
                    "policy_id": core_policy_id,
                    "title": core_policy.get("title"),
                    "decision": core_policy.get("decision"),
                    "reuse_scope": core_policy.get("reuse_scope"),
                    "notes": core_policy.get("notes"),
                    "observed_examples": [],
                    "application_result": application_result,
                })
        out["mode"] = "POLICY_REGISTRY_REUSE"
        out["auto_policy_application"] = True
        out["candidate_question_count"] = len(candidate_questions)
        out["applied_policy_count"] = len(applied)
        out["new_question_count"] = len(unresolved)
        out["question_count"] = len(unresolved)
        out["questions"] = unresolved
        out["applied_policies"] = applied
        out["registry"] = {
            "schema_version": registry.get("schema_version"),
            "policy_count": len([x for x in registry.get("policies") or [] if isinstance(x, dict)]),
            "portable_seed_present": self.seed_json.is_file(),
            "cross_version_persistent": True,
            "storage_hint": "%LOCALAPPDATA%\\RequirementStudio\\human_policy (Windows) / ~/.requirement_studio/human_policy (fallback)",
        }
        out["governance_note"] = (
            "Current runtime reuses approved cross-document Human Policy decisions and Engineering E2E core policies. Existing local decisions are never overwritten by package seed. "
            "DEFER remains a new question; deterministic Tool defects remain code/regression work, not human-policy questions."
        )
        return out

    def write_run_snapshot(self, guide_dir: Path, report: dict[str, Any], registry: dict[str, Any]) -> tuple[Path, Path]:
        guide_dir = Path(guide_dir)
        guide_dir.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "schema_version": "1.0",
            "generated_at": _now(),
            "handoff_identity": report.get("handoff_identity") or {},
            "registry_summary": report.get("registry") or {},
            "applied_policies": report.get("applied_policies") or [],
            "new_questions": report.get("questions") or [],
            "preservation_policy": next((p for p in (registry.get("policies") or []) if isinstance(p, dict) and p.get("policy_id") == "HP-PRESERVE-001"), None),
        }
        json_path = guide_dir / "applied_policy_snapshot.json"
        txt_path = guide_dir / "applied_policy_snapshot.txt"
        _atomic_write_text(json_path, json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
        lines = [
            "Requirement Studio Applied Human Policy Snapshot",
            "=" * 72,
            f"Generated At: {snapshot['generated_at']}",
            f"Applied Policy Count: {len(snapshot['applied_policies'])}",
            f"New Question Count: {len(snapshot['new_questions'])}",
            "",
            "Applied Policies",
            "----------------",
        ]
        if not snapshot["applied_policies"]:
            lines.append("- None")
        for p in snapshot["applied_policies"]:
            lines += [
                f"- {p.get('policy_id','')} | Decision={p.get('decision','')} | {p.get('title','')}",
                f"  Scope: {p.get('reuse_scope','')}",
                f"  Notes: {p.get('notes','') or '[NONE]'}",
                f"  Examples this Run: {', '.join(p.get('observed_examples') or []) or '[NONE]'}",
            ]
        lines += [
            "",
            "New / Unresolved Questions",
            "--------------------------",
        ]
        if not snapshot["new_questions"]:
            lines.append("- None")
        for q in snapshot["new_questions"]:
            lines.append(f"- {q.get('question_id','')} | {q.get('policy_topic','')}")
        lines += [
            "",
            "Preservation Rule",
            "-----------------",
            "REVIEW_REQUIRED/HOLD 항목은 삭제하지 않고 Main Requirement Specification 및 Review View에 보존한다.",
        ]
        _atomic_write_text(txt_path, "\n".join(lines).rstrip() + "\n")
        return json_path, txt_path
