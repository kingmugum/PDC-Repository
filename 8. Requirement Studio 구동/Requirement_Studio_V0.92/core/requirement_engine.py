from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from core.quality_audit import (
    apply_quality_audits,
    normalize_gap_references,
    normalize_requirement_extensions,
)


class RequirementEngine:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.output_dir = self.project_root / "output"
        self.policy_path = self.project_root / "policy" / "requirement_judgment_policy.json"
        self.schema_path = self.project_root / "contracts" / "canonical_requirement_schema.json"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def extract_json(text: str) -> dict[str, Any]:
        raw = (text or "").strip()
        if not raw:
            raise ValueError("AI 요구사항 추출 응답이 비어 있습니다.")

        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            first = raw.find("{")
            last = raw.rfind("}")
            if first < 0 or last <= first:
                raise ValueError("AI 응답에서 JSON 객체를 찾을 수 없습니다.")
            try:
                data = json.loads(raw[first:last + 1])
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"AI 요구사항 추출 JSON 파싱 실패: {exc}"
                ) from exc

        if not isinstance(data, dict):
            raise ValueError("요구사항 추출 결과의 최상위 값은 JSON object여야 합니다.")
        return data

    def load_schema(self) -> dict[str, Any]:
        return json.loads(self.schema_path.read_text(encoding="utf-8"))

    def evaluate_structure(self, data: dict[str, Any]) -> dict[str, Any]:
        schema = self.load_schema()
        errors: list[str] = []
        warnings: list[str] = []

        for key in schema["top_level_required"]:
            if key not in data:
                errors.append(f"최상위 필드 누락: {key}")

        accepted_schema_versions = {str(schema.get("schema_version") or "")}
        accepted_schema_versions.update(str(x) for x in (schema.get("compatible_input_schema_versions") or []) if str(x))
        if str(data.get("schema_version") or "") not in accepted_schema_versions:
            errors.append(
                f"schema_version 불일치: {data.get('schema_version')!r}"
            )

        scenarios = data.get("scenario_candidates", [])
        requirements = data.get("requirements", [])
        gaps = data.get("gaps", [])

        if not isinstance(scenarios, list):
            errors.append("scenario_candidates는 list여야 합니다.")
            scenarios = []
        if not isinstance(requirements, list):
            errors.append("requirements는 list여야 합니다.")
            requirements = []
        if not isinstance(gaps, list):
            errors.append("gaps는 list여야 합니다.")

        scenario_ids = set()
        for idx, scenario in enumerate(scenarios, start=1):
            if not isinstance(scenario, dict):
                errors.append(f"scenario_candidates[{idx}]가 object가 아닙니다.")
                continue
            for key in schema["scenario_candidate_required"]:
                if key not in scenario:
                    errors.append(
                        f"scenario_candidates[{idx}] 필드 누락: {key}"
                    )
            sid = scenario.get("scenario_candidate_id")
            if sid:
                scenario_ids.add(sid)

        source_fields = schema["source_evidence_required"]
        allowed_types = set(schema["allowed_derivation_type"])
        allowed_knowledge = set(schema.get("allowed_knowledge_state") or ["KNOWN", "DERIVED", "UNKNOWN"])
        allowed_status = set(schema.get("allowed_requirement_status") or ["Draft", "Review Needed", "Blocked", "Approved"])

        explicit_count = 0
        implicit_count = 0
        source_evidence_count = 0
        low_confidence_count = 0

        for idx, req in enumerate(requirements, start=1):
            if not isinstance(req, dict):
                errors.append(f"requirements[{idx}]가 object가 아닙니다.")
                continue

            for key in schema["requirement_required"]:
                if key not in req:
                    errors.append(f"requirements[{idx}] 필드 누락: {key}")

            dtype = req.get("derivation_type")
            if dtype not in allowed_types:
                errors.append(
                    f"requirements[{idx}] derivation_type 오류: {dtype!r}"
                )
            elif dtype == "explicit":
                explicit_count += 1
            elif dtype == "implicit":
                implicit_count += 1

            sid = req.get("scenario_candidate_id")
            if sid and scenario_ids and sid not in scenario_ids:
                errors.append(
                    f"requirements[{idx}]가 존재하지 않는 scenario ID를 참조: {sid}"
                )

            evidence = req.get("source_evidence", [])
            if not isinstance(evidence, list) or not evidence:
                errors.append(f"requirements[{idx}] source_evidence 없음")
            else:
                for eidx, item in enumerate(evidence, start=1):
                    if not isinstance(item, dict):
                        errors.append(
                            f"requirements[{idx}] source_evidence[{eidx}] object 아님"
                        )
                        continue
                    missing = [
                        key for key in source_fields
                        if not str(item.get(key, "")).strip()
                    ]
                    if missing:
                        errors.append(
                            f"requirements[{idx}] source_evidence[{eidx}] 누락: "
                            + ", ".join(missing)
                        )
                    else:
                        source_evidence_count += 1

            confidence = req.get("confidence")
            if not isinstance(confidence, (int, float)):
                errors.append(f"requirements[{idx}] confidence 숫자 아님")
            elif not 0.0 <= float(confidence) <= 1.0:
                errors.append(
                    f"requirements[{idx}] confidence 범위 오류: {confidence}"
                )
            elif float(confidence) < 0.70:
                low_confidence_count += 1

            if dtype == "implicit" and not str(req.get("derivation_reason", "")).strip():
                errors.append(
                    f"requirements[{idx}] implicit인데 derivation_reason 없음"
                )

            knowledge_state = str(req.get("knowledge_state") or "").strip()
            if knowledge_state not in allowed_knowledge:
                errors.append(f"requirements[{idx}] knowledge_state 오류: {knowledge_state!r}")

            req_status = str(req.get("requirement_status") or "").strip()
            if req_status not in allowed_status:
                warnings.append(f"requirements[{idx}] requirement_status 비표준 값: {req_status!r}")

            applicability = req.get("applicability")
            if not isinstance(applicability, dict):
                errors.append(f"requirements[{idx}] applicability는 object여야 합니다.")
            else:
                for app_key in schema.get("applicability_fields") or []:
                    if app_key not in applicability:
                        warnings.append(f"requirements[{idx}] applicability 필드 누락: {app_key}")

            clarification = req.get("clarification_needed")
            if clarification is None:
                warnings.append(
                    f"requirements[{idx}] clarification_needed가 null입니다. "
                    "없으면 빈 list 사용을 권장합니다."
                )

            # V0.65 preserves the V0.59 semantic provenance invariant for no-ID sources.
            source_ids = req.get("source_requirement_ids") if isinstance(req.get("source_requirement_ids"), list) else []
            if not source_ids:
                eligibility = str(req.get("swe1_eligibility") or "Eligible")
                sem_ids = req.get("source_semantic_unit_ids") if isinstance(req.get("source_semantic_unit_ids"), list) else []
                atoms = req.get("source_backed_atomic_behaviors") if isinstance(req.get("source_backed_atomic_behaviors"), list) else []
                facts = req.get("source_backed_facts") if isinstance(req.get("source_backed_facts"), list) else []
                if eligibility == "Eligible" and (not sem_ids or not atoms):
                    errors.append(f"requirements[{idx}] no-ID SWE.1 Eligible인데 Semantic provenance/Atomic Behavior 불완전")
                elif eligibility == "Review Needed" and (not sem_ids or not (atoms or facts)):
                    warnings.append(f"requirements[{idx}] allocation pending인데 Semantic provenance/Source fact 불완전")
                elif eligibility == "Not Applicable" and (not sem_ids or not str(req.get("verification_domain") or "").strip()):
                    warnings.append(f"requirements[{idx}] Not-SW item의 Semantic provenance/Verification Domain 불완전")

            # V0.65 allocation hierarchy / bundle invariants.
            fact_allocs = [x for x in (req.get("fact_level_allocations") or []) if isinstance(x, dict)]
            parent_pending = str(req.get("swe6_eligibility") or "").startswith("Deferred") or "PENDING_SW_ALLOCATION" in str(req.get("allocation_status") or "")
            for fact in fact_allocs:
                if parent_pending and str(fact.get("swe6_eligibility") or "") == "Eligible" and not fact.get("allocation_override") and not fact.get("allocation_override_evidence"):
                    errors.append(f"requirements[{idx}] PARENT_CHILD_ALLOCATION_CONFLICT: Pending Parent인데 fact-level SWE.6 Eligible override evidence 없음")
                    break
            domains = {
                str(x.get("verification_domain") or "").strip()
                for x in fact_allocs
                if str(x.get("verification_domain") or "").strip()
                and str(x.get("allocation_status") or "") != "EXTERNAL_STANDARD_REFERENCE"
            }
            if len(domains) >= 2 and not bool(req.get("cross_domain_bundle_review_required")):
                errors.append(f"requirements[{idx}] CROSS_DOMAIN_BUNDLE_FLAG_MISMATCH: 복수 verification domain인데 review flag=false")

        fragment_conflicts = [x for x in (data.get("source_fact_multi_srs_allocation_conflicts") or []) if isinstance(x, dict)]
        if fragment_conflicts:
            warnings.append(f"SOURCE_FACT_MULTI_SRS_ALLOCATION_CONFLICT: {len(fragment_conflicts)}건 - Release Review 필요")

        coverage = data.get("source_coverage") if isinstance(data.get("source_coverage"), dict) else {}
        if str(coverage.get("coverage_validity") or "VALID") == "INVALID":
            errors.append(str(coverage.get("coverage_validity_reason") or "TRACEABILITY_BINDING_EMPTY"))

        # Structure score only. This is not semantic quality.
        score = 100
        score -= min(70, len(errors) * 7)
        score -= min(20, len(warnings) * 2)
        score = max(0, score)

        integrity = data.get("reference_integrity_result") if isinstance(data.get("reference_integrity_result"), dict) else {}
        completeness = data.get("reference_completeness_result") if isinstance(data.get("reference_completeness_result"), dict) else {}
        export_audit = data.get("export_preservation_audit") if isinstance(data.get("export_preservation_audit"), dict) else {}
        unsupported = data.get("unsupported_generation_report") if isinstance(data.get("unsupported_generation_report"), dict) else {}
        testability = data.get("testability_and_decomposition_result") if isinstance(data.get("testability_and_decomposition_result"), dict) else {}

        return {
            "structure_score": score,
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "scenario_count": len(scenarios),
                "requirement_count": len(requirements),
                "explicit_statement_candidate_count": explicit_count,
                "implicit_statement_candidate_count": implicit_count,
                "gap_count": len(gaps) if isinstance(gaps, list) else 0,
                "source_evidence_count": source_evidence_count,
                "low_confidence_count": low_confidence_count,
                "source_occurrence_count": coverage.get("explicit_source_requirement_occurrence_count", 0),
                "source_coverage_validity": coverage.get("coverage_validity", "VALID"),
                "source_coverage_percent": coverage.get("weighted_source_coverage_percent", 0.0),
                "disposition_coverage_percent": coverage.get("disposition_coverage_percent", 0.0),
                "reference_integrity_error_count": integrity.get("error_count", 0),
                "reference_completeness_passed": completeness.get("passed", False),
                "unlinked_gap_count": completeness.get("unlinked_gap_count", 0),
                "unlinked_conflict_count": completeness.get("unlinked_conflict_count", 0),
                "export_information_loss_count": export_audit.get("information_loss_count", 0),
                "unsupported_detected_count": unsupported.get("unsupported_assertion_count", 0),
                "unsupported_uncertain_count": unsupported.get("uncertain_assertion_count", 0),
                "review_needed_srs_count": (testability.get("summary") or {}).get("review_needed_srs_count", 0),
            },
            "data_integrity": integrity,
            "source_coverage": coverage,
            "reference_completeness_result": completeness,
            "export_preservation_audit": export_audit,
            "unsupported_generation_report": unsupported,
            "testability_and_decomposition_result": testability,
            "note": (
                "Structure Score는 JSON/추적성 형식 점수이며 의미적 완전성 점수가 아닙니다. "
                "V0.92은 Canonical Engineering Requirement를 SYS.1/SWE.1/native/review를 포함한 E2E 요구사항 명세서로 보존하고, SYS.5/SWE.6/Deferred/Allocation Pending/External/native 검증을 SWE.6 스타일 E2E 평가 명세서로 투영합니다. Eligibility를 존재 필터로 사용하지 않으며 애매한 Source-backed Engineering Fact는 Human Review 경로로 남깁니다."
            ),
        }

    def merge_results(
        self,
        parts: list[dict[str, Any]],
        *,
        source_document: str,
    ) -> dict[str, Any]:
        """Chunk별 Canonical JSON을 하나의 결과로 결정론적으로 병합한다.

        V0.56 preserves/remaps Candidate references in Gap records and fills
        extension fields with empty/UNKNOWN values rather than inventing missing facts.
        """
        if not parts:
            raise ValueError("병합할 Requirement 결과가 없습니다.")

        merged_scenarios: list[dict[str, Any]] = []
        merged_requirements: list[dict[str, Any]] = []
        merged_gaps: list[Any] = []
        scenario_no = 1
        requirement_no = 1
        seen_req_keys: set[str] = set()
        seen_gap_keys: set[str] = set()

        for part in parts:
            scenario_map: dict[str, str] = {}
            candidate_map: dict[str, str] = {}

            scenarios = part.get("scenario_candidates", [])
            if isinstance(scenarios, list):
                for scenario in scenarios:
                    if not isinstance(scenario, dict):
                        continue
                    old_id = str(scenario.get("scenario_candidate_id") or "")
                    new_id = f"SCN-CAND-{scenario_no:03d}"
                    scenario_no += 1
                    copied = json.loads(json.dumps(scenario, ensure_ascii=False))
                    copied["scenario_candidate_id"] = new_id
                    merged_scenarios.append(copied)
                    if old_id:
                        scenario_map[old_id] = new_id

            requirements = part.get("requirements", [])
            if isinstance(requirements, list):
                for req in requirements:
                    if not isinstance(req, dict):
                        continue
                    copied = json.loads(json.dumps(req, ensure_ascii=False))
                    old_candidate_id = str(copied.get("candidate_id") or "").strip()
                    old_sid = str(copied.get("scenario_candidate_id") or "")
                    if old_sid in scenario_map:
                        copied["scenario_candidate_id"] = scenario_map[old_sid]
                    elif merged_scenarios:
                        copied["scenario_candidate_id"] = merged_scenarios[-1]["scenario_candidate_id"]

                    normalize_requirement_extensions(copied)
                    evidence = copied.get("source_evidence", [])
                    app = copied.get("applicability") or {}
                    key_payload = {
                        "requirement": str(copied.get("requirement") or "").strip(),
                        "derivation_type": copied.get("derivation_type"),
                        "evidence": evidence,
                        # V0.56: do not silently collapse same wording across different applicability.
                        "applicability": app,
                        "exception_conditions": copied.get("exception_conditions") or [],
                    }
                    key = json.dumps(key_payload, ensure_ascii=False, sort_keys=True)
                    if key in seen_req_keys:
                        continue
                    seen_req_keys.add(key)

                    new_candidate_id = f"REQ-CAND-{requirement_no:03d}"
                    copied["candidate_id"] = new_candidate_id
                    copied["srs_id"] = f"SRS_{requirement_no:03d}"
                    requirement_no += 1
                    merged_requirements.append(copied)
                    if old_candidate_id:
                        candidate_map[old_candidate_id] = new_candidate_id
                        candidate_map[old_candidate_id.upper()] = new_candidate_id
                    # Common legacy aliases are mapped conservatively by numeric suffix.
                    m = re.search(r"(\d+)$", old_candidate_id) if old_candidate_id else None
                    if m:
                        n = int(m.group(1))
                        for alias in (f"CAND_{n:03d}", f"CAND-{n:03d}", f"REQ-CAND-{n:03d}"):
                            candidate_map.setdefault(alias, new_candidate_id)
                            candidate_map.setdefault(alias.upper(), new_candidate_id)

            gaps = part.get("gaps", [])
            if isinstance(gaps, list):
                for gap in gaps:
                    if not isinstance(gap, dict):
                        continue
                    copied_gap = normalize_gap_references(gap, candidate_map)
                    if not copied_gap.get("gap_id"):
                        copied_gap["gap_id"] = f"GAP_{len(merged_gaps)+1:03d}"
                    # Fill SRS refs when the referenced candidate is known after merge.
                    srs_by_candidate = {str(r.get("candidate_id")): str(r.get("srs_id")) for r in merged_requirements if r.get("candidate_id") and r.get("srs_id")}
                    for cid in copied_gap.get("related_candidate_ids") or []:
                        sid = srs_by_candidate.get(str(cid))
                        if sid and sid not in copied_gap["related_srs_ids"]:
                            copied_gap["related_srs_ids"].append(sid)
                    key = json.dumps(copied_gap, ensure_ascii=False, sort_keys=True, default=str)
                    if key not in seen_gap_keys:
                        seen_gap_keys.add(key)
                        merged_gaps.append(copied_gap)

        return {
            "schema_version": "REQ-STUDIO-CANONICAL-REQ-2.0",
            "source_document": source_document,
            "scenario_candidates": merged_scenarios,
            "requirements": merged_requirements,
            "gaps": merged_gaps,
            "source_coverage": {},
            "conflict_register": [],
            "reference_integrity_result": {},
            "reference_completeness_result": {},
            "export_preservation_audit": {},
            "unsupported_generation_report": {},
            "testability_and_decomposition_result": {},
            "test_intent_coverage": {},
            "regression_report": {},
            "review_findings": [],
        }

    def apply_quality_audits(self, data: dict[str, Any], *, source_text: str) -> dict[str, Any]:
        """Apply deterministic V0.80 quality gates without adding unsupported domain facts."""
        return apply_quality_audits(data, source_text or "")

    def save_result(self, source_document: Path, data: dict[str, Any]) -> Path:
        source_path = Path(source_document)
        stem = re.sub(r'[<>:"/\\|?*]+', "_", source_path.stem)
        source_type = re.sub(r"[^A-Za-z0-9]+", "", source_path.suffix.lstrip(".")) or "doc"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self.output_dir / f"RequirementStudio_Requirements_{stem}_{source_type}_{stamp}.json"
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def format_for_display(
        data: dict[str, Any],
        evaluation: dict[str, Any],
        saved_path: Path | None = None,
    ) -> str:
        summary = evaluation["summary"]
        lines = [
            "=== Requirement Candidate Evaluation ===",
            f"Structure Score : {evaluation['structure_score']}/100",
            f"Scenario        : {summary['scenario_count']}",
            f"Requirements    : {summary['requirement_count']}",
            f"  - Explicit stmt candidates: {summary['explicit_statement_candidate_count']}",
            f"  - Implicit stmt candidates: {summary['implicit_statement_candidate_count']}",
            f"Gaps            : {summary['gap_count']}",
            f"Source Evidence : {summary['source_evidence_count']}",
            f"Low Confidence  : {summary['low_confidence_count']}",
            f"Source Coverage : {summary.get('source_coverage_percent', 0)}%",
            f"Disposition     : {summary.get('disposition_coverage_percent', 0)}%",
            f"Integrity Error : {summary.get('reference_integrity_error_count', 0)}",
            f"Ref Completeness: {'PASS' if summary.get('reference_completeness_passed') else 'REVIEW'}",
            f"Export Loss     : {summary.get('export_information_loss_count', 0)}",
            f"UG Uncertain    : {summary.get('unsupported_uncertain_count', 0)}",
        ]

        if saved_path:
            lines.append(f"Saved JSON      : {saved_path}")

        if evaluation["errors"]:
            lines.append("")
            lines.append("[Structure Errors]")
            lines.extend(f"- {x}" for x in evaluation["errors"])

        if evaluation["warnings"]:
            lines.append("")
            lines.append("[Warnings]")
            lines.extend(f"- {x}" for x in evaluation["warnings"])

        lines.extend([
            "",
            evaluation["note"],
            "",
            "=== Canonical Requirement JSON ===",
            json.dumps(data, ensure_ascii=False, indent=2),
        ])
        return "\n".join(lines)
