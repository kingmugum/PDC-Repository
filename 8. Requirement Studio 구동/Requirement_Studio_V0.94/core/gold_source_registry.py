from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
import shutil
from typing import Any


class GoldSourceRegistry:
    """Multi-Gold-Source registry for deterministic regression selection.

    V0.68 keeps Gold Source contracts entirely inside the Requirement Studio project.
    The contract intentionally keeps only the minimum regression identity/evidence needed
    for same-source comparison. User registrations are stored under
    review_exchange/gold_sources/user_registered; no sibling Requirement_Studio_Gold_Sources
    directory is created.
    """

    REGISTRY_SCHEMA_VERSION = "1.0"
    CONTRACT_SCHEMA_VERSION = "1.4"

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.bundled_root = self.project_root / "review_exchange" / "gold_sources"
        self.user_root = self.bundled_root / "user_registered"
        # Compatibility name retained for callers/status payloads, but V0.68 never points
        # outside the application directory.
        self.shared_root = self.user_root
        self.legacy_external_root = self.project_root.parent / "Requirement_Studio_Gold_Sources"
        self.bundled_root.mkdir(parents=True, exist_ok=True)
        self.user_root.mkdir(parents=True, exist_ok=True)
        (self.bundled_root / "contracts").mkdir(parents=True, exist_ok=True)
        (self.user_root / "contracts").mkdir(parents=True, exist_ok=True)
        self._migrate_legacy_external_store()

    def _migrate_legacy_external_store(self) -> None:
        """Move the old sibling Gold store into the project without losing contracts.

        Only the known registry.json + contracts/*.json layout is removed automatically.
        If an unexpected user file exists, it is left untouched; V0.68 still never writes
        to that external folder again.
        """
        legacy = self.legacy_external_root
        if not legacy.is_dir():
            return
        registry_path = legacy / "registry.json"
        legacy_registry = self._load_registry_file(registry_path)
        target_registry_path = self.user_root / "registry.json"
        target_registry = self._load_registry_file(target_registry_path)
        records = [x for x in (target_registry.get("gold_sources") or []) if isinstance(x, dict)]
        by_sha = {str(x.get("source_sha256") or "").strip().lower(): dict(x) for x in records if str(x.get("source_sha256") or "").strip()}
        for item in legacy_registry.get("gold_sources") or []:
            if not isinstance(item, dict):
                continue
            sha = str(item.get("source_sha256") or "").strip().lower()
            rel = str(item.get("contract_path") or "").strip()
            if not sha or not rel:
                continue
            source_contract = (legacy / rel).resolve()
            if not source_contract.is_file():
                continue
            target_contract = self.user_root / "contracts" / source_contract.name
            if not target_contract.exists():
                shutil.copy2(source_contract, target_contract)
            migrated = dict(item)
            migrated["contract_path"] = f"contracts/{target_contract.name}"
            migrated["migrated_from_legacy_external_store"] = True
            by_sha[sha] = migrated
        if by_sha:
            payload = {"schema_version": self.REGISTRY_SCHEMA_VERSION, "gold_sources": list(by_sha.values())}
            target_registry_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        # Remove the obsolete external store only when it contains the known program-owned layout.
        unexpected = []
        for path in legacy.rglob("*"):
            if path.is_dir():
                continue
            rel = path.relative_to(legacy).as_posix()
            if rel == "registry.json" or (rel.startswith("contracts/") and rel.endswith(".json")):
                continue
            unexpected.append(rel)
        if not unexpected:
            shutil.rmtree(legacy, ignore_errors=True)

    @staticmethod
    def _normalize_space(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @staticmethod
    def _fingerprint(value: str) -> str:
        return hashlib.sha256((value or "").encode("utf-8", errors="ignore")).hexdigest()[:20]

    @classmethod
    def _stable_source_key(cls, location: str, text: str) -> str:
        loc = cls._normalize_space(location).lower()
        body = cls._normalize_space(text).lower()
        return f"SRCKEY-{cls._fingerprint(f'{loc}|{body}').upper()}" if (loc or body) else ""

    @staticmethod
    def _explicit_ids(text: str) -> list[str]:
        patterns = [
            re.compile(r"(?<![A-Za-z0-9_])REQ[A-Z0-9]*[-_.][A-Z0-9][A-Z0-9_.-]*(?![A-Za-z0-9_.-])", re.IGNORECASE),
            re.compile(r"(?<![A-Za-z0-9_])REQ\d+[A-Z0-9_.-]*(?![A-Za-z0-9_.-])", re.IGNORECASE),
            re.compile(r"(?<![A-Za-z0-9_])SW[_-]?REQ[-_.A-Z0-9]*\d[A-Z0-9_.-]*(?![A-Za-z0-9_.-])", re.IGNORECASE),
            re.compile(r"(?<![A-Za-z0-9_])SWR[-_.A-Z0-9]*\d[A-Z0-9_.-]*(?![A-Za-z0-9_.-])", re.IGNORECASE),
        ]
        out: list[str] = []
        seen: set[str] = set()
        for pattern in patterns:
            for m in pattern.finditer(text or ""):
                value = m.group(0).strip()
                key = value.upper()
                if key and key not in seen:
                    seen.add(key)
                    out.append(value)
        return out

    def _registry_paths(self) -> list[Path]:
        return [self.bundled_root / "registry.json", self.user_root / "registry.json"]

    def _load_registry_file(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {"schema_version": self.REGISTRY_SCHEMA_VERSION, "gold_sources": []}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"schema_version": self.REGISTRY_SCHEMA_VERSION, "gold_sources": []}
        if not isinstance(data, dict):
            return {"schema_version": self.REGISTRY_SCHEMA_VERSION, "gold_sources": []}
        if not isinstance(data.get("gold_sources"), list):
            data["gold_sources"] = []
        return data

    def list_sources(self) -> list[dict[str, Any]]:
        by_sha: dict[str, dict[str, Any]] = {}
        for root, registry_path, origin in (
            (self.bundled_root, self.bundled_root / "registry.json", "bundled"),
            (self.user_root, self.user_root / "registry.json", "user_registered"),
        ):
            data = self._load_registry_file(registry_path)
            for item in data.get("gold_sources") or []:
                if not isinstance(item, dict):
                    continue
                sha = str(item.get("source_sha256") or "").strip().lower()
                rel = str(item.get("contract_path") or "").strip()
                if not sha or not rel:
                    continue
                path = (root / rel).resolve()
                if not path.is_file():
                    continue
                record = dict(item)
                record["origin"] = origin
                record["contract_abs_path"] = str(path)
                # Shared registrations intentionally override a bundled contract with the same SHA.
                if sha not in by_sha or origin == "user_registered":
                    by_sha[sha] = record
        return sorted(by_sha.values(), key=lambda x: (str(x.get("label") or ""), str(x.get("source_sha256") or "")))

    def status(self) -> dict[str, Any]:
        sources = self.list_sources()
        return {
            "available": bool(sources),
            "count": len(sources),
            "sources": sources,
            "shared_store": str(self.user_root),
        }

    def find_contract(self, source_sha256: str) -> tuple[dict[str, Any] | None, str]:
        target = str(source_sha256 or "").strip().lower()
        if not target:
            return None, ""
        for record in self.list_sources():
            if str(record.get("source_sha256") or "").strip().lower() != target:
                continue
            path = Path(str(record.get("contract_abs_path") or ""))
            try:
                contract = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(contract, dict):
                return contract, str(path)
        return None, ""

    @staticmethod
    def contract_to_review_payload(contract: dict[str, Any]) -> dict[str, Any]:
        """Adapt a compact Gold Source contract to the existing regression engine input."""
        reqs: list[dict[str, Any]] = []
        behavior_rows: list[dict[str, Any]] = []
        for parent in contract.get("behaviors") or []:
            if not isinstance(parent, dict):
                continue
            atomic = [x for x in (parent.get("atomic_behaviors") or []) if isinstance(x, dict)]
            if atomic:
                for child in atomic:
                    merged = dict(parent)
                    merged.update(child)
                    merged["parent_behavior_id"] = parent.get("behavior_id")
                    behavior_rows.append(merged)
            else:
                behavior_rows.append(parent)
        for idx, behavior in enumerate(behavior_rows, start=1):
            source_locations = [str(x) for x in (behavior.get("source_locations") or []) if str(x).strip()]
            compact_excerpt = str(behavior.get("compact_excerpt") or "").strip()
            excerpt_kind = str(behavior.get("compact_excerpt_kind") or "source_excerpt" if compact_excerpt else "").strip()
            source_document = str(behavior.get("source_document_name") or contract.get("source_original_name") or contract.get("label") or "")
            compact_rows = [x for x in (behavior.get("compact_source_evidence") or []) if isinstance(x, dict)]
            if compact_rows:
                source_evidence = [{
                    "location": str(x.get("location") or ""),
                    "text": str(x.get("text") or ""),
                    "document": str(x.get("document") or source_document),
                    "excerpt_fingerprint": str(x.get("excerpt_fingerprint") or ""),
                    "evidence_text_kind": str(x.get("evidence_text_kind") or "source_excerpt"),
                } for x in compact_rows]
            else:
                # Bundled legacy compact contracts may not retain source excerpts. A clearly labelled
                # behavior-summary fallback improves reviewer auditability without pretending it is verbatim source text.
                display_text = compact_excerpt or str(behavior.get("expected_behavior_summary") or "").strip()
                display_kind = excerpt_kind or ("behavior_summary_fallback" if display_text else "location_only")
                source_evidence = [{
                    "location": loc, "text": display_text, "document": source_document,
                    "excerpt_fingerprint": str(behavior.get("excerpt_fingerprint") or ""),
                    "evidence_text_kind": display_kind,
                } for loc in source_locations]
            stable_source_keys = [str(x) for x in (behavior.get("stable_source_keys") or []) if str(x).strip()]
            if not stable_source_keys:
                stable_source_keys = [GoldSourceRegistry._stable_source_key(str(x.get("location") or ""), str(x.get("text") or "")) for x in source_evidence]
                stable_source_keys = [x for x in stable_source_keys if x]
            reqs.append({
                "candidate_id": str(behavior.get("baseline_candidate_id") or f"GOLD-CAND-{idx:03d}"),
                "srs_id": str(behavior.get("baseline_srs_id") or f"GOLD-SRS-{idx:03d}"),
                "requirement": str(behavior.get("expected_behavior_summary") or "Gold Source behavior"),
                "source_requirement_ids": list(behavior.get("source_requirement_ids") or []),
                "source_evidence": source_evidence,
                "gold_evidence_fingerprints": list(behavior.get("evidence_fingerprints") or []),
                "gold_stable_source_keys": stable_source_keys,
            })
        return {
            "run": {
                "requirement_studio_version": str(contract.get("reference_version") or "gold-reference"),
                "source_sha256": str(contract.get("source_sha256") or ""),
                "source_original_name": str(contract.get("source_original_name") or contract.get("label") or ""),
                "provider": str((contract.get("reference_run") or {}).get("provider") or ""),
                "provider_id": str((contract.get("reference_run") or {}).get("provider_id") or ""),
                "model": str((contract.get("reference_run") or {}).get("model") or ""),
                "extraction_core_profile": str((contract.get("reference_run") or {}).get("extraction_core_profile") or "v0.46-compatible-1.1"),
            },
            "canonical_requirement": {"requirements": reqs},
            "gold_source_contract": {
                "contract_id": contract.get("contract_id"),
                "label": contract.get("label"),
                "contract_schema_version": contract.get("contract_schema_version"),
                "baseline_type": contract.get("baseline_type") or "compact_gold_regression_contract",
                "baseline_origin_version": contract.get("baseline_origin_version") or contract.get("reference_version"),
                "is_full_review_package": bool(contract.get("is_full_review_package", False)),
                "behavior_scope": contract.get("behavior_scope") or "source-backed compact behavior contract",
                "approval_status": contract.get("approval_status") or ("APPROVED_FOR_REGRESSION" if str(contract.get("reference_version") or "").lower() in {"v0.46", "0.46"} else "UNSPECIFIED"),
                "approval_method": contract.get("approval_method") or "",
                "approved_at": contract.get("approved_at") or "",
            },
        }

    def _contract_from_review_package(self, payload: dict[str, Any]) -> dict[str, Any]:
        run = payload.get("run") or {}
        sha = str(run.get("source_sha256") or "").strip().lower()
        if not sha:
            raise ValueError("Review Package에 source_sha256이 없습니다.")
        canonical = payload.get("canonical_requirement") or {}
        reqs = [x for x in (canonical.get("requirements") or []) if isinstance(x, dict)]
        if not reqs:
            raise ValueError("Review Package에 Canonical Requirement가 없습니다.")

        behaviors: list[dict[str, Any]] = []
        for idx, req in enumerate(reqs, start=1):
            source_ids: list[str] = []
            seen: set[str] = set()
            for value in req.get("source_requirement_ids") or []:
                text = str(value).strip()
                if text and text.upper() not in seen:
                    seen.add(text.upper()); source_ids.append(text)
            locations: list[str] = []
            evidence_fingerprints: list[str] = []
            compact_source_evidence: list[dict[str, str]] = []
            first_excerpt = ""
            for ev in req.get("source_evidence") or []:
                if not isinstance(ev, dict):
                    continue
                loc = self._normalize_space(ev.get("location"))
                text = self._normalize_space(ev.get("text"))
                document = self._normalize_space(ev.get("document") or run.get("source_original_name") or run.get("source_file") or "")
                if loc and loc not in locations:
                    locations.append(loc)
                for sid in self._explicit_ids(f"{loc} {text}"):
                    if sid.upper() not in seen:
                        seen.add(sid.upper()); source_ids.append(sid)
                if loc or text:
                    fp = self._fingerprint(f"{loc}|{text}")
                    evidence_fingerprints.append(fp)
                    excerpt = text[:320]
                    if excerpt and not first_excerpt:
                        first_excerpt = excerpt
                    compact_source_evidence.append({
                        "document": document,
                        "location": loc,
                        "text": excerpt,
                        "excerpt_fingerprint": f"sha256:{fp}",
                        "evidence_text_kind": "source_excerpt",
                    })
            behavior_summary = self._normalize_space(req.get("requirement"))[:900]
            excerpt_basis = first_excerpt or behavior_summary
            atomic_behaviors: list[dict[str, Any]] = []

            # V0.65: no-ID Gold contracts preserve Source Fact Fragment identity. This gives
            # regression a record-level key even when Source Requirement Occurrence IDs do not exist.
            source_fragments = [x for x in (req.get("source_fact_fragments") or []) if isinstance(x, dict)]
            for frag_idx, frag in enumerate(source_fragments, start=1):
                frag_loc = self._normalize_space(frag.get("source_location"))
                frag_text = self._normalize_space(frag.get("source_excerpt_raw") or frag.get("source_excerpt"))
                if not frag_text:
                    continue
                stable_key = self._stable_source_key(frag_loc, frag_text)
                atomic_behaviors.append({
                    "behavior_id": f"GOLD-BHV-{idx:03d}-F{frag_idx:02d}",
                    "source_requirement_ids": self._explicit_ids(f"{frag_loc} {frag_text}"),
                    "source_locations": [frag_loc] if frag_loc else [],
                    "source_document_name": str(run.get("source_original_name") or run.get("source_file") or ""),
                    "compact_source_evidence": [{
                        "document": str(run.get("source_original_name") or run.get("source_file") or ""),
                        "location": frag_loc,
                        "text": frag_text[:320],
                        "excerpt_fingerprint": f"sha256:{self._fingerprint(frag_text)}",
                        "evidence_text_kind": "source_fact_fragment",
                    }],
                    "compact_excerpt": frag_text[:320],
                    "compact_excerpt_kind": "source_fact_fragment",
                    "expected_behavior_summary": frag_text[:900],
                    "excerpt_fingerprint": f"sha256:{self._fingerprint(frag_text)}",
                    "stable_source_keys": [stable_key] if stable_key else [],
                })

            # Explicit-ID legacy path remains supported when no fragment-level records exist.
            if not atomic_behaviors:
                for ev_idx, ev in enumerate(req.get("source_evidence") or [], start=1):
                    if not isinstance(ev, dict):
                        continue
                    ev_loc = self._normalize_space(ev.get("location"))
                    ev_text = self._normalize_space(ev.get("text"))
                    ev_ids = self._explicit_ids(f"{ev_loc} {ev_text}")
                    if not ev_ids:
                        continue
                    stable_key = self._stable_source_key(ev_loc, ev_text)
                    atomic_behaviors.append({
                        "behavior_id": f"GOLD-BHV-{idx:03d}-A{ev_idx:02d}",
                        "source_requirement_ids": ev_ids,
                        "source_locations": [ev_loc] if ev_loc else [],
                        "source_document_name": self._normalize_space(ev.get("document") or run.get("source_original_name") or run.get("source_file") or ""),
                        "compact_source_evidence": [{
                            "document": self._normalize_space(ev.get("document") or run.get("source_original_name") or run.get("source_file") or ""),
                            "location": ev_loc,
                            "text": ev_text[:320],
                            "excerpt_fingerprint": f"sha256:{self._fingerprint(ev_text)}" if ev_text else "",
                            "evidence_text_kind": "source_excerpt",
                        }],
                        "compact_excerpt": ev_text[:320],
                        "compact_excerpt_kind": "source_excerpt",
                        "expected_behavior_summary": ev_text[:900] or behavior_summary,
                        "excerpt_fingerprint": f"sha256:{self._fingerprint(ev_text)}" if ev_text else "",
                        "stable_source_keys": [stable_key] if stable_key else [],
                    })
            behaviors.append({
                "behavior_id": f"GOLD-BHV-{idx:03d}",
                "baseline_candidate_id": str(req.get("candidate_id") or ""),
                "baseline_srs_id": str(req.get("srs_id") or ""),
                "source_requirement_ids": source_ids,
                "source_locations": locations,
                "source_document_name": str(run.get("source_original_name") or run.get("source_file") or ""),
                "evidence_fingerprints": evidence_fingerprints,
                "compact_source_evidence": compact_source_evidence,
                "compact_excerpt": excerpt_basis[:320],
                "compact_excerpt_kind": "source_excerpt" if first_excerpt else "behavior_summary_fallback",
                "excerpt_fingerprint": f"sha256:{self._fingerprint(excerpt_basis)}" if excerpt_basis else "",
                "expected_behavior_summary": behavior_summary,
                "stable_source_keys": list(dict.fromkeys(
                    [self._stable_source_key(str(x.get("location") or ""), str(x.get("text") or "")) for x in compact_source_evidence if isinstance(x, dict)]
                    + [k for a in atomic_behaviors for k in (a.get("stable_source_keys") or [])]
                )),
                "atomic_behaviors": atomic_behaviors,
            })

        source_name = str(run.get("source_original_name") or run.get("source_file") or "Gold Source")
        version = str(run.get("requirement_studio_version") or "reference")
        contract_id = f"GOLD-{sha[:12]}"
        return {
            "contract_schema_version": self.CONTRACT_SCHEMA_VERSION,
            "contract_id": contract_id,
            "label": source_name,
            "source_original_name": source_name,
            "source_sha256": sha,
            "reference_version": version,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "approval_status": "APPROVED_FOR_REGRESSION",
            "approval_method": "explicit_user_gold_source_registration",
            "approved_at": datetime.now().isoformat(timespec="seconds"),
            "reference_run": {
                "provider": str(run.get("provider") or ""),
                "provider_id": str(run.get("provider_id") or ""),
                "model": str(run.get("model") or ""),
                "extraction_core_profile": str(run.get("extraction_core_profile") or ("v0.46-native" if version.lower() in {"v0.46", "0.46"} else "")),
            },
            "baseline_type": "compact_gold_regression_contract",
            "baseline_origin_version": version,
            "is_full_review_package": False,
            "behavior_scope": "source-backed compact behavior contract",
            "evidence_policy": "Source locations, short source-backed excerpts (max 320 chars when present), and fingerprints are retained. When a legacy bundled contract lacks the excerpt, behavior_summary_fallback is explicitly labelled and is never represented as verbatim source evidence.",
            "privacy_note": "Compact regression contract. Original source file and full source excerpts are not stored here; only bounded audit evidence is retained.",
            "behaviors": behaviors,
        }

    def install_review_package(self, source_path: Path, *, label: str | None = None) -> Path:
        source_path = Path(source_path).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"Review Package JSON을 읽을 수 없습니다: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Review Package JSON 형식이 올바르지 않습니다.")
        contract = self._contract_from_review_package(payload)
        if label:
            contract["label"] = str(label).strip() or contract["label"]
        sha = str(contract["source_sha256"]).lower()
        filename = f"gold_contract_{sha[:16]}.json"
        target = self.user_root / "contracts" / filename
        target.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")

        registry_path = self.user_root / "registry.json"
        registry = self._load_registry_file(registry_path)
        records = [x for x in (registry.get("gold_sources") or []) if isinstance(x, dict)]
        records = [x for x in records if str(x.get("source_sha256") or "").strip().lower() != sha]
        records.append({
            "source_sha256": sha,
            "label": contract.get("label"),
            "reference_version": contract.get("reference_version"),
            "approval_status": contract.get("approval_status"),
            "contract_path": f"contracts/{filename}",
            "registered_at": datetime.now().isoformat(timespec="seconds"),
        })
        registry = {"schema_version": self.REGISTRY_SCHEMA_VERSION, "gold_sources": records}
        registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

        # Rev55 FR-339 compatibility: when the explicitly imported package is an actual
        # V0.46 Review Package, also preserve the full approved package at the historical
        # internal baseline path.  This stays inside the project and does not recreate the
        # removed external Gold directory.
        version = str((payload.get("run") or {}).get("requirement_studio_version") or "").strip().lower()
        if version in {"v0.46", "0.46"}:
            baseline_dir = self.project_root / "review_exchange" / "baseline"
            baseline_dir.mkdir(parents=True, exist_ok=True)
            baseline_target = baseline_dir / "02_REQUIREMENT_STUDIO_REVIEW_PACKAGE_v0.46.json"
            baseline_target.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        return target
