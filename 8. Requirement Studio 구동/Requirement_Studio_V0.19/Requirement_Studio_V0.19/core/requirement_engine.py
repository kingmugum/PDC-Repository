from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


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

        if data.get("schema_version") != schema["schema_version"]:
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

            clarification = req.get("clarification_needed")
            if clarification is None:
                warnings.append(
                    f"requirements[{idx}] clarification_needed가 null입니다. "
                    "없으면 빈 list 사용을 권장합니다."
                )

        # Structure score only. This is not semantic quality.
        score = 100
        score -= min(70, len(errors) * 7)
        score -= min(20, len(warnings) * 2)
        score = max(0, score)

        return {
            "structure_score": score,
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "scenario_count": len(scenarios),
                "requirement_count": len(requirements),
                "explicit_count": explicit_count,
                "implicit_count": implicit_count,
                "gap_count": len(gaps) if isinstance(gaps, list) else 0,
                "source_evidence_count": source_evidence_count,
                "low_confidence_count": low_confidence_count,
            },
            "note": (
                "이 점수는 JSON/추적성 구조 점수입니다. "
                "의미적 완전성·환각 여부·Atomic 품질은 별도 검토가 필요합니다."
            ),
        }

    def merge_results(
        self,
        parts: list[dict[str, Any]],
        *,
        source_document: str,
    ) -> dict[str, Any]:
        """Chunk별 Canonical JSON을 하나의 결과로 결정론적으로 병합한다."""
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
            local_map: dict[str, str] = {}
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
                        local_map[old_id] = new_id

            requirements = part.get("requirements", [])
            if isinstance(requirements, list):
                for req in requirements:
                    if not isinstance(req, dict):
                        continue
                    copied = json.loads(json.dumps(req, ensure_ascii=False))
                    old_sid = str(copied.get("scenario_candidate_id") or "")
                    if old_sid in local_map:
                        copied["scenario_candidate_id"] = local_map[old_sid]
                    elif merged_scenarios:
                        copied["scenario_candidate_id"] = merged_scenarios[-1]["scenario_candidate_id"]

                    evidence = copied.get("source_evidence", [])
                    key_payload = {
                        "requirement": str(copied.get("requirement") or "").strip(),
                        "derivation_type": copied.get("derivation_type"),
                        "evidence": evidence,
                    }
                    key = json.dumps(key_payload, ensure_ascii=False, sort_keys=True)
                    if key in seen_req_keys:
                        continue
                    seen_req_keys.add(key)

                    copied["candidate_id"] = f"REQ-CAND-{requirement_no:03d}"
                    requirement_no += 1
                    merged_requirements.append(copied)

            gaps = part.get("gaps", [])
            if isinstance(gaps, list):
                for gap in gaps:
                    key = json.dumps(gap, ensure_ascii=False, sort_keys=True, default=str)
                    if key not in seen_gap_keys:
                        seen_gap_keys.add(key)
                        merged_gaps.append(gap)

        return {
            "schema_version": "REQ-STUDIO-CANONICAL-REQ-1.0",
            "source_document": source_document,
            "scenario_candidates": merged_scenarios,
            "requirements": merged_requirements,
            "gaps": merged_gaps,
        }

    def save_result(self, source_document: Path, data: dict[str, Any]) -> Path:
        stem = re.sub(r'[<>:"/\\|?*]+', "_", Path(source_document).stem)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.output_dir / f"RequirementStudio_Requirements_{stem}_{stamp}.json"
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
            f"  - Explicit    : {summary['explicit_count']}",
            f"  - Implicit    : {summary['implicit_count']}",
            f"Gaps            : {summary['gap_count']}",
            f"Source Evidence : {summary['source_evidence_count']}",
            f"Low Confidence  : {summary['low_confidence_count']}",
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
