from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from core.swe6_exporter import build_swe6_cases
from core.quality_audit import finalize_test_intent_coverage
from core.regression_engine import build_regression_report as build_reliable_regression_report
from core.gold_source_registry import GoldSourceRegistry


def _pct(value: Any) -> str:
    return "N/A" if value is None else f"{value}%"


class ReviewExchangeBuilder:
    """Build the local Review Exchange evidence set used by V0.74 Unified Evaluation.

    The historical manual three-file H-Chat limit is no longer an architecture constraint. The local
    package may contain Source, Review JSON, SWE.1 Word/Excel, SWE.6 Excel, Change Decision and
    human summary; the automated evaluator compacts these into one evidence graph before sending the
    same evidence snapshot independently to GPT/Gemini/Claude.
    """

    PACKAGE_SCHEMA_VERSION = "2.6"

    def __init__(self, project_root: Path, *, app_version: str):
        self.project_root = Path(project_root).resolve()
        self.base_dir = self.project_root / "review_exchange"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.baseline_dir = self.base_dir / "baseline"  # legacy compatibility only
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self.gold_registry = GoldSourceRegistry(self.project_root)
        self.app_version = str(app_version)

    def install_gold_source_package(self, source_path: Path) -> Path:
        """Register one Gold Source from a Review Package and persist it across versions."""
        return self.gold_registry.install_review_package(source_path)

    def install_baseline_package(self, source_path: Path) -> Path:
        """Legacy alias retained for compatibility; V0.65 retains it as a Gold Source contract."""
        return self.install_gold_source_package(source_path)

    def baseline_status(self) -> dict[str, Any]:
        status = self.gold_registry.status()
        sources = status.get("sources") or []
        bundled_v046 = next((x for x in sources if str(x.get("reference_version") or "").lower() in {"v0.46", "0.46"}), None)
        return {
            "available": bool(sources),
            "count": int(status.get("count") or 0),
            "path": str((bundled_v046 or {}).get("contract_abs_path") or status.get("shared_store") or ""),
            "version": str((bundled_v046 or {}).get("reference_version") or ""),
            "sources": sources,
            "shared_store": str(status.get("shared_store") or ""),
        }

    @staticmethod
    def _safe_name(value: str, *, limit: int = 72) -> str:
        text = re.sub(r'[<>:"/\\|?*]+', "_", str(value or "document"))
        text = re.sub(r"\s+", "_", text).strip("._ ")
        return (text or "document")[:limit]

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _new_run_dir(self, source_document: Path) -> tuple[str, Path]:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_id = f"{stamp}_{self._safe_name(source_document.stem, limit=44)}"
        run_dir = self.base_dir / run_id
        counter = 2
        while run_dir.exists():
            run_dir = self.base_dir / f"{run_id}_{counter}"
            counter += 1
        run_dir.mkdir(parents=True, exist_ok=False)
        return run_dir.name, run_dir

    @staticmethod
    def _evaluation_request(artifact_focus: str = "unified") -> dict[str, Any]:
        focus = str(artifact_focus or "unified").lower()
        common = {
            "knowledge_policy": {
                "KNOWN": "Directly supported by the source document.",
                "DERIVED": "Conservative restructuring of source-backed facts without adding domain facts.",
                "UNKNOWN": "Not confirmable from the source; must remain Gap/TBD/Dependency/Conflict/Review Needed/Deferred.",
            },
            "critical_rule": (
                "Do not penalize the system merely because it refused to invent missing values. "
                "Penalize explicit source facts that were lost, unsupported facts that were generated, "
                "or unknowns that were silently hidden instead of being surfaced for review."
            ),
            "reviewer_output_guidance": (
                "When uncertain, mark the item Uncertain rather than guessing. "
                "Reviewer findings are opinions and must not be treated as source evidence."
            ),
        }
        if focus == "unified":
            return {
                "purpose": (
                    "Perform a Unified End-to-End evaluation from Source through Canonical Requirement, SWE.1, "
                    "allocation/eligibility, Child Intent, SWE.6, actual exports, QA and regression. "
                    "Detect cross-output information loss or domain leakage while distinguishing source insufficiency from tool defects."
                ),
                **common,
                "artifact_focus": "UNIFIED_END_TO_END",
                "requested_checks": [
                    "Source -> Semantic Unit -> Fact Fragment -> Canonical/SRS fidelity",
                    "Canonical/SRS -> SWE.1 Word/Excel preservation and review-annex usability",
                    "Positive software allocation evidence and SWE.1/SWE.6 eligibility consistency",
                    "Fact Fragment -> Child Intent -> SWE.6 TC/deferred-intent traceability",
                    "Cross-output consistency between SWE.1 allocation and SWE.6 scope",
                    "Actual Word/Excel artifact contract and deterministic audit consistency",
                    "Unsupported generation / omitted source facts / hidden unknowns",
                    "Regression governance and release-gate interpretation",
                ],
            }
        if focus == "swe6":
            return {
                "purpose": (
                    "Evaluate the actual SWE.6 Software Qualification Test Excel against Source and the Canonical/Review JSON. "
                    "Judge eligibility correctness, Source-backed test-intent preservation, concrete testability, deferred-intent governance, and TC traceability without rewarding invented test data."
                ),
                **common,
                "artifact_focus": "SWE6_QUALIFICATION_XLSX",
                "requested_checks": [
                    "SWE.6 eligibility correctness and cross-domain over-generation check",
                    "Source -> Canonical/SRS -> Atomic Behavior/Test Intent -> TC traceability",
                    "Test Input / Execution / Expected Result source fidelity",
                    "Source-backed numeric/interface/prohibition facts preserved in TC text or explicitly deferred",
                    "Test design technique suitability without invented values",
                    "Deferred test intent reason-code governance",
                    "SWE.6-specific export preservation and actual XLSX trace consistency",
                    "PASS/FAIL and measured-result cells remain blank before execution",
                ],
            }
        return {
            "purpose": (
                "Evaluate whether Requirement Studio preserved source-backed functionality and review information "
                "into the actual engineer-facing SWE.1 outputs without rewarding unsupported invention. "
                "Distinguish program loss from source insufficiency."
            ),
            **common,
            "artifact_focus": "SWE1_REQUIREMENT_OUTPUTS",
            "requested_checks": [
                "Explicit-ID or Semantic Source Unit coverage / disposition",
                "Unsupported generation / hallucination check",
                "KNOWN-DERIVED-UNKNOWN handling",
                "System/SW/Non-SW allocation and Main SWE.1/Annex scope",
                "Atomic behavior and provenance completeness",
                "Exception / TBD / conflict / external dependency preservation",
                "Canonical-to-SWE.1 Word/Excel information loss",
                "Traceability integrity and atomicity risk without mechanical over-splitting",
            ],
        }

    @staticmethod
    def _artifact_focus_from_config(config: dict[str, Any] | None) -> str:
        focus = str((config or {}).get("evaluation_artifact") or "swe1").strip().lower()
        if focus in {"swe1", "swe6", "unified"}:
            return focus
        return "unified"

    @staticmethod
    def _verify_swe6_excel_artifact(path: Path | None, tc_cases: list[dict[str, Any]]) -> dict[str, Any]:
        """Verify the actual serialized SWE.6 workbook used as Review Exchange file 03.

        V0.69 retains exact result-cell/header findings and an artifact SHA-256 so the JSON audit can be
        tied to the same XLSX the reviewer receives.  Any non-empty Output Value / PASS-FAIL /
        Comment / Capture cell is release-blocking, including N/A, formulas, whitespace-like
        strings, or other defaults.
        """
        if not path or not Path(path).is_file():
            return {
                "status": "ARTIFACT_MISSING", "passed": False,
                "missing_tc_ids": [str(x.get("tc_id") or "") for x in tc_cases if x.get("tc_id")],
                "extra_tc_ids": [], "artifact_sha256": "", "verified_artifact": "",
            }
        artifact_path = Path(path)
        h = hashlib.sha256()
        with artifact_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        artifact_sha256 = h.hexdigest()

        wb = load_workbook(artifact_path, data_only=False, read_only=True)
        try:
            required_audit_sheets = ["2_테스트 케이스", "3_Deferred Intent", "4_Source_Intent_Audit", "5_Source_Fact_Audit"]
            missing_sheets = [name for name in required_audit_sheets if name not in wb.sheetnames]
            if "2_테스트 케이스" in missing_sheets:
                return {
                    "status": "TEST_CASE_SHEET_MISSING", "passed": False,
                    "missing_tc_ids": [str(x.get("tc_id") or "") for x in tc_cases if x.get("tc_id")],
                    "extra_tc_ids": [], "missing_audit_sheets": missing_sheets,
                    "artifact_sha256": artifact_sha256, "verified_artifact": artifact_path.name,
                }
            ws = wb["2_테스트 케이스"]
            rows: dict[str, dict[str, Any]] = {}
            result_cells: list[dict[str, Any]] = []
            result_columns = {18: "Output Value", 19: "PASS / FAIL", 20: "Comment", 21: "Capture CANoe"}
            expected_headers = {
                18: "Output Value",
                19: "PASS / FAIL",
                20: "Comment",
                21: "Capture CANoe (Optional)",
            }
            observed_headers = {
                col: str(ws.cell(3, col).value or "").replace("\n", " ").strip()
                for col in expected_headers
            }
            header_mismatches = []
            for col, expected in expected_headers.items():
                observed = observed_headers[col]
                if expected.lower() not in observed.lower():
                    header_mismatches.append({
                        "column": col,
                        "cell": ws.cell(3, col).coordinate,
                        "expected_header_contains": expected,
                        "observed_header": observed,
                    })
            for r in range(4, ws.max_row + 1):
                sid = str(ws.cell(r, 1).value or "").strip()
                tid = str(ws.cell(r, 2).value or "").strip()
                if not tid:
                    continue
                rows[tid] = {
                    "srs_id": sid,
                    "description": str(ws.cell(r, 5).value or ""),
                    "execution": str(ws.cell(r, 10).value or ""),
                    "expected": str(ws.cell(r, 14).value or ""),
                }
                for col, field in result_columns.items():
                    cell = ws.cell(r, col)
                    value = cell.value
                    # None/empty string are the only valid pre-execution states.
                    if value not in (None, ""):
                        result_cells.append({
                            "tc_id": tid, "field": field, "cell": cell.coordinate,
                            "value": str(value),
                        })
            expected_ids = {str(x.get("tc_id") or "") for x in tc_cases if x.get("tc_id")}
            actual_ids = set(rows)
            missing = sorted(expected_ids - actual_ids)
            extra = sorted(actual_ids - expected_ids)
            mismatched_srs = []
            for case in tc_cases:
                tid = str(case.get("tc_id") or "")
                row = rows.get(tid)
                if not row:
                    continue
                if row["srs_id"] != str(case.get("srs_id") or ""):
                    mismatched_srs.append({"tc_id": tid, "expected_srs": str(case.get("srs_id") or ""), "excel_srs": row["srs_id"]})
            populated_results = sorted({str(x.get("tc_id") or "") for x in result_cells if x.get("tc_id")})
            passed = not (missing or extra or mismatched_srs or result_cells or missing_sheets or header_mismatches)
            return {
                "status": "VERIFIED" if passed else "MISMATCH",
                "passed": passed,
                "artifact_sha256": artifact_sha256,
                "verified_artifact": artifact_path.name,
                "excel_tc_count": len(actual_ids),
                "case_object_tc_count": len(expected_ids),
                "missing_tc_ids": missing,
                "extra_tc_ids": extra,
                "srs_trace_mismatches": mismatched_srs,
                "prepopulated_result_tc_ids": populated_results,
                "prepopulated_result_cells": result_cells,
                "execution_result_blank_policy": "Output Value / PASS-FAIL / Comment / Capture must be physically blank in saved XLSX before execution.",
                "execution_result_field_contract": {
                    "required_columns": {"R": "Output Value", "S": "PASS / FAIL", "T": "Comment", "U": "Capture CANoe (Optional)"},
                    "capture_field_required_in_schema": True,
                    "capture_field_optional_for_user_entry": True,
                    "capture_header_present": not any(x.get("column") == 21 for x in header_mismatches),
                    "header_mismatches": header_mismatches,
                    "blank_validation_applied_to_columns": ["R", "S", "T", "U"],
                },
                "missing_audit_sheets": missing_sheets,
                "required_audit_sheets": required_audit_sheets,
            }
        finally:
            wb.close()

    @staticmethod
    def _copy_sheet(source_ws, target_ws):
        """Copy reviewer-visible workbook content/style without mutating originals."""
        target_ws.sheet_view.showGridLines = source_ws.sheet_view.showGridLines
        target_ws.freeze_panes = source_ws.freeze_panes
        for row in source_ws.iter_rows():
            for source_cell in row:
                target_cell = target_ws.cell(source_cell.row, source_cell.column, source_cell.value)
                if source_cell.has_style:
                    target_cell._style = copy.copy(source_cell._style)
                if source_cell.number_format:
                    target_cell.number_format = source_cell.number_format
                if source_cell.alignment:
                    target_cell.alignment = copy.copy(source_cell.alignment)
                if source_cell.font:
                    target_cell.font = copy.copy(source_cell.font)
                if source_cell.fill:
                    target_cell.fill = copy.copy(source_cell.fill)
                if source_cell.border:
                    target_cell.border = copy.copy(source_cell.border)
                if source_cell.protection:
                    target_cell.protection = copy.copy(source_cell.protection)
        for key, dim in source_ws.column_dimensions.items():
            target = target_ws.column_dimensions[key]
            target.width = dim.width
            target.hidden = dim.hidden
            target.bestFit = dim.bestFit
            target.outlineLevel = dim.outlineLevel
        for idx, dim in source_ws.row_dimensions.items():
            target = target_ws.row_dimensions[idx]
            target.height = dim.height
            target.hidden = dim.hidden
            target.outlineLevel = dim.outlineLevel
        for merged in source_ws.merged_cells.ranges:
            target_ws.merge_cells(str(merged))
        if source_ws.auto_filter and source_ws.auto_filter.ref:
            target_ws.auto_filter.ref = source_ws.auto_filter.ref

    @staticmethod
    def _unique_sheet_name(wb: Workbook, preferred: str) -> str:
        clean = re.sub(r"[\\/*?:\[\]]", "_", preferred)[:31] or "Sheet"
        if clean not in wb.sheetnames:
            return clean
        base = clean[:27]
        no = 2
        while True:
            candidate = f"{base}_{no}"[:31]
            if candidate not in wb.sheetnames:
                return candidate
            no += 1

    def _append_workbook(self, dest: Workbook, source_path: Path | None, prefix: str, *, note_sheet: str):
        if not source_path or not Path(source_path).is_file():
            ws = dest.create_sheet(self._unique_sheet_name(dest, note_sheet))
            ws["A1"] = "산출물 미생성 또는 파일 경로 없음"
            ws["A1"].font = Font(bold=True)
            return
        src_wb = load_workbook(source_path, data_only=False)
        try:
            for source_ws in src_wb.worksheets:
                name = self._unique_sheet_name(dest, f"{prefix}_{source_ws.title}")
                target_ws = dest.create_sheet(name)
                self._copy_sheet(source_ws, target_ws)
        finally:
            src_wb.close()

    @staticmethod
    def _regression_occurrence_key(occ: dict[str, Any]) -> tuple[str, str]:
        return (
            str(occ.get("source_req_id") or "").strip().upper(),
            str(occ.get("source_location") or occ.get("section_path") or "").strip().lower(),
        )

    def _candidate_previous_packages(self, current_run_dir: Path) -> list[Path]:
        paths: list[Path] = []
        # Same project: prior local review runs.
        for path in self.base_dir.glob("*/02_REQUIREMENT_STUDIO_REVIEW_PACKAGE.json"):
            if path.parent != current_run_dir:
                paths.append(path)
        # Optional explicit baseline folder.
        for path in (self.base_dir / "baseline").glob("*.json") if (self.base_dir / "baseline").is_dir() else []:
            paths.append(path)
        # Convenience: detect adjacent Requirement_Studio_V* folders on the user's local PC.
        parent = self.project_root.parent
        try:
            for path in parent.glob("Requirement_Studio_V*/review_exchange/*/02_REQUIREMENT_STUDIO_REVIEW_PACKAGE.json"):
                if path.parent != current_run_dir:
                    paths.append(path)
        except Exception:
            pass
        unique: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            key = str(path.resolve())
            if key not in seen and path.is_file():
                seen.add(key)
                unique.append(path)
        return unique

    @staticmethod
    def _version_key(payload: dict[str, Any]) -> str:
        return str((payload.get("run") or {}).get("requirement_studio_version") or "").strip().lower()

    def _load_previous_review_package(self, source_sha256: str, current_run_dir: Path) -> tuple[dict[str, Any] | None, str]:
        """Select only an explicitly protected regression reference.

        V0.69 never treats an ordinary prior local run as an approved baseline. Priority is:
        exact-SHA Gold Source contract -> explicit legacy baseline/V0.46 reference -> NOT_EVALUATED.
        This prevents any current/unreviewed local run from silently becoming its own Gold.
        """
        contract, contract_path = self.gold_registry.find_contract(source_sha256)
        if contract:
            return self.gold_registry.contract_to_review_payload(contract), f"Gold Source Contract: {contract_path}"

        candidates: list[tuple[int, str, Path, dict[str, Any]]] = []
        for path in self._candidate_previous_packages(current_run_dir):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            run = payload.get("run") or {}
            if str(run.get("source_sha256") or "") != source_sha256:
                continue
            version = self._version_key(payload)
            explicit = "baseline" in {part.lower() for part in path.parts}
            if explicit:
                priority = 0
            elif version in {"v0.46", "0.46"}:
                priority = 1
            else:
                # Ordinary Review Exchange history is evidence, not approval.
                continue
            generated = str(run.get("generated_at") or "")
            candidates.append((priority, generated, path, payload))
        if not candidates:
            return None, "No explicitly approved Gold Source contract or protected legacy baseline with the same source SHA-256 was found. Register an approved Review Package with [Gold Source 추가] to enable release regression."
        candidates.sort(key=lambda x: (x[0], x[1]))
        best_priority = min(x[0] for x in candidates)
        same_priority = [x for x in candidates if x[0] == best_priority]
        same_priority.sort(key=lambda x: x[1], reverse=True)
        _priority, _generated, path, payload = same_priority[0]
        return payload, str(path)


    def _create_output_review_workbook(
        self,
        output_path: Path,
        *,
        source_document: Path,
        run_id: str,
        analysis_text: str,
        evaluation: dict[str, Any],
        quality_review_config: dict[str, Any],
        requirement_data: dict[str, Any],
        artifact_paths: dict[str, str | Path | None],
    ):
        wb = Workbook()
        summary = wb.active
        summary.title = "00_Run_Summary"
        blue = "2F75B5"
        light = "D9EAF7"
        summary.append(["항목", "내용"])
        coverage = requirement_data.get("source_coverage") if isinstance(requirement_data.get("source_coverage"), dict) else {}
        integrity = requirement_data.get("reference_integrity_result") if isinstance(requirement_data.get("reference_integrity_result"), dict) else {}
        completeness = requirement_data.get("reference_completeness_result") if isinstance(requirement_data.get("reference_completeness_result"), dict) else {}
        export_audit = requirement_data.get("export_preservation_audit") if isinstance(requirement_data.get("export_preservation_audit"), dict) else {}
        regression = requirement_data.get("regression_report") if isinstance(requirement_data.get("regression_report"), dict) else {}
        intent_cov = requirement_data.get("test_intent_coverage") if isinstance(requirement_data.get("test_intent_coverage"), dict) else {}
        ug = requirement_data.get("unsupported_generation_report") if isinstance(requirement_data.get("unsupported_generation_report"), dict) else {}
        rows = [
            ["Run ID", run_id],
            ["Requirement Studio", self.app_version],
            ["Source", source_document.name],
            ["생성 시각", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ["Hand-off 파일 수", 4],
            ["Weighted Source Coverage", _pct(coverage.get("weighted_source_coverage_percent"))],
            ["Disposition Coverage", _pct(coverage.get("disposition_coverage_percent"))],
            ["Disposition Detail", f"full={coverage.get('fully_dispositioned_count',0)} / uncertain-evidence={coverage.get('uncertain_with_evidence_count',0)} / undispositioned={coverage.get('undispositioned_count',0)} / missing={coverage.get('missing_program_extraction_count',0)}"],
            ["Reference Validity", f"errors={integrity.get('error_count', 0)} / passed={integrity.get('passed', False)}"],
            ["Reference Completeness", f"passed={completeness.get('passed', False)} / unlinked_gap={completeness.get('unlinked_gap_count', 0)} / unlinked_conflict={completeness.get('unlinked_conflict_count', 0)}"],
            ["Regression Report", f"baseline={regression.get('baseline_available', False)} / findings={regression.get('regression_count', 0)} / comparison={(regression.get('comparison_coverage') or {}).get('comparison_coverage_percent', 0)}%"],
            ["Regression Gate", f"status={(regression.get('regression_gate') or {}).get('status', 'NOT_EVALUATED')} / baseline={regression.get('baseline_version', '')}"],
            ["Run Compatibility", f"mode={(regression.get('run_compatibility') or {}).get('comparison_mode','')} / provider_match={(regression.get('run_compatibility') or {}).get('provider_match','')} / model_match={(regression.get('run_compatibility') or {}).get('model_match','')}"],
            ["Test Intent Coverage", f"{intent_cov.get('intent_coverage_percent', 0)}% ({intent_cov.get('covered_intent_count', 0)}/{intent_cov.get('required_intent_count', 0)})"],
            ["Export Information Loss", export_audit.get("information_loss_count", 0)],
            ["Automatic UG Precheck", f"unsupported={ug.get('unsupported_assertion_count', 0)} / uncertain={ug.get('uncertain_assertion_count', 0)} / reviewed={ug.get('reviewed_assertion_count', 0)}"],
            ["평가 원칙", "Source에 없는 사실은 생성하지 않으며, 명시 Source 누락과 Unsupported Generation을 별도로 평가"],
            ["주의", "Summary는 아래 계산/Review Sheet를 근거로 한다. 자동 Unsupported 0건은 Hallucination 0% 보장을 의미하지 않는다."],
        ]
        for row in rows:
            summary.append(row)
        for cell in summary[1]:
            cell.fill = PatternFill("solid", fgColor=blue)
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for row in summary.iter_rows(min_row=2):
            row[0].font = Font(bold=True)
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        summary.column_dimensions["A"].width = 24
        summary.column_dimensions["B"].width = 100
        summary.freeze_panes = "A2"

        analysis = wb.create_sheet("01_Analysis")
        analysis.append(["Line", "Analysis Result"])
        for idx, line in enumerate((analysis_text or "").splitlines() or [""], start=1):
            analysis.append([idx, line])
        for cell in analysis[1]:
            cell.fill = PatternFill("solid", fgColor=blue)
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal="center")
        analysis.column_dimensions["A"].width = 10
        analysis.column_dimensions["B"].width = 120
        for row in analysis.iter_rows(min_row=2):
            row[1].alignment = Alignment(vertical="top", wrap_text=True)
        analysis.freeze_panes = "A2"

        qa = wb.create_sheet("02_Local_QA")
        qa.append(["항목", "값"])
        qa.append(["JSON/Traceability Format Score", evaluation.get("structure_score", "")])
        qa.append(["Note", evaluation.get("note", "")])
        summary_data = evaluation.get("summary") or {}
        for key, value in summary_data.items():
            qa.append([f"summary.{key}", value])
        for idx, value in enumerate(evaluation.get("errors") or [], start=1):
            qa.append([f"error.{idx}", str(value)])
        for idx, value in enumerate(evaluation.get("warnings") or [], start=1):
            qa.append([f"warning.{idx}", str(value)])
        for cell in qa[1]:
            cell.fill = PatternFill("solid", fgColor=blue)
            cell.font = Font(color="FFFFFF", bold=True)
        qa.column_dimensions["A"].width = 38
        qa.column_dimensions["B"].width = 110
        for row in qa.iter_rows():
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)

        review_cfg = wb.create_sheet("03_Review_Config")
        review_cfg.append(["항목", "값"])
        review_cfg.append(["enabled", quality_review_config.get("enabled")])
        review_cfg.append(["mode", quality_review_config.get("mode")])
        review_cfg.append(["scope", quality_review_config.get("scope")])
        review_cfg.append(["reviewers", json.dumps(quality_review_config.get("reviewers") or [], ensure_ascii=False)])
        review_cfg.append(["criteria", json.dumps(quality_review_config.get("criteria") or [], ensure_ascii=False)])
        for cell in review_cfg[1]:
            cell.fill = PatternFill("solid", fgColor=blue)
            cell.font = Font(color="FFFFFF", bold=True)
        review_cfg.column_dimensions["A"].width = 26
        review_cfg.column_dimensions["B"].width = 110
        for row in review_cfg.iter_rows():
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)

        # V0.53 reviewer evidence sheets are generated from actual calculated Canonical data.
        cov_ws = wb.create_sheet("10_Source_Coverage")
        cov_ws.append(["Occurrence ID", "Occurrence Type", "Source REQ ID", "Function/Baseline Context", "Section / Source Location", "Kind", "Coverage Status", "Candidate IDs", "SRS IDs", "Gap/Issue IDs", "Missing Disposition IDs", "Reason", "Uncertainty Reason", "Source Excerpt", "Content Hash"])
        for occ in coverage.get("source_requirement_occurrences") or []:
            if not isinstance(occ, dict):
                continue
            cov_ws.append([
                occ.get("occurrence_id"), occ.get("occurrence_type"), occ.get("source_req_id"), occ.get("function_or_baseline"), occ.get("source_location") or occ.get("section_path"), occ.get("source_kind"),
                occ.get("coverage_status"), json.dumps(occ.get("linked_candidate_ids") or [], ensure_ascii=False),
                json.dumps(occ.get("linked_srs_ids") or [], ensure_ascii=False), json.dumps(occ.get("linked_gap_issue_ids") or [], ensure_ascii=False),
                json.dumps(occ.get("linked_missing_disposition_ids") or [], ensure_ascii=False),
                occ.get("disposition_reason"), occ.get("uncertainty_reason"), occ.get("source_excerpt"), occ.get("content_hash"),
            ])

        app_ws = wb.create_sheet("11_Applicability")
        app_ws.append(["SRS ID", "Source REQ IDs", "Vehicle Lines", "Baseline Versions", "Feature Variants", "Enable Conditions", "Exclusion Conditions", "Knowledge State", "Requirement Status"])
        for req in requirement_data.get("requirements") or []:
            if not isinstance(req, dict):
                continue
            app = req.get("applicability") if isinstance(req.get("applicability"), dict) else {}
            app_ws.append([
                req.get("srs_id"), json.dumps(req.get("source_requirement_ids") or [], ensure_ascii=False),
                json.dumps(app.get("vehicle_lines") or [], ensure_ascii=False), json.dumps(app.get("baseline_versions") or [], ensure_ascii=False),
                json.dumps(app.get("feature_variants") or [], ensure_ascii=False), json.dumps(app.get("enable_conditions") or [], ensure_ascii=False),
                json.dumps(app.get("exclusion_conditions") or [], ensure_ascii=False), app.get("knowledge_state"), req.get("requirement_status"),
            ])

        issue_ws = wb.create_sheet("12_Issues_Gaps_Conflicts")
        issue_ws.append(["Type", "ID", "Related SRS", "Status", "Detail", "Must Not Assume / Dependency"])
        for gap in requirement_data.get("gaps") or []:
            if isinstance(gap, dict):
                issue_ws.append([
                    "Gap", gap.get("gap_id"), json.dumps(gap.get("related_srs_ids") or [], ensure_ascii=False),
                    "Blocked" if gap.get("blocking_for_verification") else "Review Needed",
                    str(gap.get("description") or gap.get("gap") or gap.get("reason") or ""),
                    json.dumps(gap.get("related_source_requirement_ids") or gap.get("related_source_occurrence_ids") or [], ensure_ascii=False),
                ])
        for conflict in requirement_data.get("conflict_register") or []:
            if isinstance(conflict, dict):
                issue_ws.append([
                    conflict.get("classification") or "Conflict", conflict.get("conflict_id"),
                    json.dumps(conflict.get("affected_srs_ids") or [], ensure_ascii=False), conflict.get("status") or "Open",
                    str(conflict.get("title") or conflict.get("description") or ""), conflict.get("must_not_assume") or "",
                ])
        for disp in requirement_data.get("missing_behavior_dispositions") or []:
            if isinstance(disp, dict):
                issue_ws.append([
                    "Missing Behavior Disposition", disp.get("disposition_id"), "[]", disp.get("status") or "Open",
                    f"{disp.get('classification','')} | Source={json.dumps(disp.get('source_requirement_ids') or [], ensure_ascii=False)} | Occ={json.dumps(disp.get('source_occurrence_ids') or [], ensure_ascii=False)} | {disp.get('compact_source_excerpt','')}",
                    disp.get("must_not_assume") or "",
                ])

        integrity_ws = wb.create_sheet("13_Traceability_Integrity")
        integrity_ws.append(["Metric / Error", "Value", "Source ID", "Target ID", "Message"])
        integrity_ws.append(["passed", integrity.get("passed"), "", "", ""])
        integrity_ws.append(["error_count", integrity.get("error_count", 0), "", "", ""])
        for key, value in (integrity.get("checked_reference_counts") or {}).items():
            integrity_ws.append([f"checked.{key}", value, "", "", ""])
        for err in integrity.get("errors") or []:
            if isinstance(err, dict):
                integrity_ws.append([err.get("type"), "ERROR", err.get("source_id"), err.get("target_id"), err.get("message")])
        integrity_ws.append(["--- Reference Completeness ---", "", "", "", ""])
        for key in ("passed", "unlinked_gap_count", "unlinked_conflict_count", "unlinked_open_issue_count", "unlinked_missing_disposition_count", "actual_missing_behavior_count", "actual_missing_behavior_release_blocking", "coverage_missing_without_disposition_count", "coverage_undispositioned_count"):
            integrity_ws.append([f"completeness.{key}", completeness.get(key), "", "", ""])
        for gid in completeness.get("unlinked_gap_ids") or []:
            integrity_ws.append(["unlinked_gap", "REVIEW", gid, "", "Gap has no Candidate/SRS/Source linkage."])
        for cid in completeness.get("unlinked_conflict_ids") or []:
            integrity_ws.append(["unlinked_conflict", "REVIEW", cid, "", "Conflict has no affected target linkage."])

        tc_cases = build_swe6_cases(requirement_data)
        finalize_test_intent_coverage(requirement_data, tc_cases)
        testability = requirement_data.get("testability_and_decomposition_result") if isinstance(requirement_data.get("testability_and_decomposition_result"), dict) else {}
        intent_cov = requirement_data.get("test_intent_coverage") if isinstance(requirement_data.get("test_intent_coverage"), dict) else {}
        test_ws = wb.create_sheet("14_SWE6_Testability")
        test_ws.append(["SRS ID", "Testability", "Normal Test Available", "Test Design Feasible", "Concrete TC Complete", "Full Testability Alias", "Intent Complete Status", "Reason", "Required Test Intents", "Covered Intents", "Generated TC IDs", "Deferred Intents", "Intent Coverage %"])
        for row in testability.get("by_srs") or []:
            if not isinstance(row, dict):
                continue
            test_ws.append([
                row.get("srs_id"), row.get("testability_status"), row.get("normal_test_available"), row.get("test_design_feasible"),
                row.get("concrete_tc_complete"), row.get("full_testability_available"), row.get("intent_complete_status"), row.get("testability_reason"),
                json.dumps(row.get("required_test_intents") or [], ensure_ascii=False), json.dumps(row.get("covered_test_intents") or [], ensure_ascii=False),
                json.dumps(row.get("generated_tc_ids") or [], ensure_ascii=False), json.dumps(row.get("not_generated_test_intents") or [], ensure_ascii=False),
                row.get("intent_coverage_percent"),
            ])

        conflict_ws = wb.create_sheet("15_Conflict_Evidence")
        conflict_ws.append(["Conflict ID", "Classification", "Title", "Source A Location", "Source A Text", "Source B Location", "Source B Text", "Affected SRS", "Affected Source Occurrences", "Linked Gap IDs", "Review State", "Must Not Assume", "Resolution Required From", "Evidence Status"])
        for conflict in requirement_data.get("conflict_register") or []:
            if not isinstance(conflict, dict):
                continue
            a = conflict.get("source_a") if isinstance(conflict.get("source_a"), dict) else {}
            b = conflict.get("source_b") if isinstance(conflict.get("source_b"), dict) else {}
            conflict_ws.append([
                conflict.get("conflict_id"), conflict.get("classification"), conflict.get("title"), a.get("location"), a.get("text"), b.get("location"), b.get("text"),
                json.dumps(conflict.get("affected_srs_ids") or [], ensure_ascii=False), json.dumps(conflict.get("affected_source_occurrence_ids") or [], ensure_ascii=False),
                json.dumps(conflict.get("linked_gap_ids") or [], ensure_ascii=False), conflict.get("review_state"), conflict.get("must_not_assume"), conflict.get("resolution_required_from"), conflict.get("evidence_status"),
            ])

        regression_ws = wb.create_sheet("16_Regression_Report")
        regression_ws.append(["Metric / Finding", "Classification / Type", "Baseline REQ IDs", "Baseline Evidence", "Current Occurrences", "Current Candidate/SRS", "Current Status / Decision", "Severity", "Method / Reason"])
        regression_ws.append(["baseline_available", "summary", "", "", "", "", regression.get("baseline_available"), "", regression.get("baseline_path")])
        regression_ws.append(["regression_gate", "gate", "", "", "", "", (regression.get("regression_gate") or {}).get("status"), "", (regression.get("regression_gate") or {}).get("reason")])
        regression_ws.append(["baseline_contract", regression.get("baseline_type") or "", "", regression.get("baseline_origin_version") or regression.get("baseline_version") or "", "", "", f"full_package={regression.get('baseline_is_full_review_package')}", "", regression.get("baseline_behavior_scope") or ""])
        regression_ws.append(["requirement_count_delta", "informational", "", regression.get("previous_requirement_count"), "", regression.get("current_requirement_count"), regression.get("requirement_count_delta"), "", "Requirement count alone is not a regression decision."])
        compat = regression.get("run_compatibility") or {}
        regression_ws.append(["run_compatibility", compat.get("comparison_mode"), "", f"{compat.get('baseline_provider','')} / {compat.get('baseline_model','')}", "", f"{compat.get('current_provider','')} / {compat.get('current_model','')}", f"source={compat.get('source_match')} core={compat.get('extraction_core_match')}", "", f"provider_match={compat.get('provider_match')} model_match={compat.get('model_match')}"])
        bsum = regression.get("baseline_behavior_summary") or {}
        for key in ("baseline_requirement_count", "source_backed_behavior_count", "source_backed_behavior_reconstruction_failed_count", "current_matched_behavior_count", "current_missing_behavior_count", "current_uncertain_behavior_count", "current_partial_behavior_count", "current_explicitly_dispositioned_behavior_count", "baseline_unmatchable_behavior_count"):
            regression_ws.append([f"baseline_behavior_summary.{key}", "summary", "", "", "", "", bsum.get(key, 0), "", ""])
        ccov = regression.get("comparison_coverage") or {}
        regression_ws.append(["comparison_coverage_percent", "summary", "", "", "", "", ccov.get("comparison_coverage_percent", 0), "", json.dumps(ccov.get("match_method_counts") or {}, ensure_ascii=False)])
        for finding in regression.get("findings") or []:
            if isinstance(finding, dict):
                baseline_ev = finding.get("baseline_source_evidence") or []
                regression_ws.append([
                    finding.get("finding_id"), finding.get("classification") or finding.get("type"),
                    json.dumps(finding.get("baseline_requirement_ids") or [], ensure_ascii=False),
                    json.dumps(baseline_ev, ensure_ascii=False),
                    json.dumps(finding.get("current_source_occurrence_ids") or [], ensure_ascii=False),
                    json.dumps({"candidate_ids": finding.get("current_candidate_ids") or [], "srs_ids": finding.get("current_srs_ids") or []}, ensure_ascii=False),
                    f"{finding.get('current_coverage_status','')} / {finding.get('decision','')} / behavior_present={finding.get('current_behavior_present')} / linkage_complete={finding.get('traceability_linkage_complete')}",
                    finding.get("severity"),
                    f"{finding.get('comparison_method','')} / {finding.get('reason','')}",
                ])

        ug_ws = wb.create_sheet("17_Unsupported_Generation")
        ug_ws.append(["Metric / Finding", "Classification", "Affected SRS", "Assertion", "Source Comparison"])
        for key in ("reviewed_assertion_count", "supported_assertion_count", "safe_derived_assertion_count", "unsupported_assertion_count", "uncertain_assertion_count", "unsupported_generation_rate_percent"):
            ug_ws.append([key, ug.get(key, 0), "", "", ""])
        for finding in ug.get("findings") or []:
            if isinstance(finding, dict):
                ug_ws.append([
                    finding.get("finding_id"), finding.get("classification"), json.dumps(finding.get("affected_srs_ids") or [], ensure_ascii=False),
                    finding.get("generated_assertion"), finding.get("source_comparison"),
                ])

        export_ws = wb.create_sheet("18_Export_Preservation")
        export_ws.append(["Field", "Nonempty Requirement Count", "Destination", "Status"])
        for row in export_audit.get("field_disposition") or []:
            if isinstance(row, dict):
                export_ws.append([row.get("field"), row.get("nonempty_requirement_count"), row.get("destination"), row.get("status")])

        dep_ws = wb.create_sheet("19_External_Dependencies")
        dep_ws.append(["SRS ID", "Source REQ IDs", "Dependency Type", "Name", "Purpose", "Knowledge State", "Source Evidence"])
        for req in requirement_data.get("requirements") or []:
            if not isinstance(req, dict):
                continue
            for dep in req.get("external_dependencies") or []:
                if not isinstance(dep, dict):
                    continue
                dep_ws.append([
                    req.get("srs_id"), json.dumps(req.get("source_requirement_ids") or [], ensure_ascii=False),
                    dep.get("type"), dep.get("name"), dep.get("purpose"), dep.get("knowledge_state"),
                    json.dumps(dep.get("source_evidence") or [], ensure_ascii=False),
                ])

        for evid_ws in (cov_ws, app_ws, issue_ws, integrity_ws, test_ws, conflict_ws, regression_ws, ug_ws, export_ws, dep_ws):
            for cell in evid_ws[1]:
                cell.fill = PatternFill("solid", fgColor=blue)
                cell.font = Font(color="FFFFFF", bold=True)
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            for row in evid_ws.iter_rows(min_row=2):
                for cell in row:
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
            evid_ws.freeze_panes = "A2"
            evid_ws.sheet_view.showGridLines = False
            for col in range(1, evid_ws.max_column + 1):
                evid_ws.column_dimensions[get_column_letter(col)].width = min(70, max(14, 18 if col < 5 else 34))

        self._append_workbook(
            wb,
            Path(artifact_paths["swe1_excel"]) if artifact_paths.get("swe1_excel") else None,
            "SWE1",
            note_sheet="SWE1_Not_Generated",
        )
        self._append_workbook(
            wb,
            Path(artifact_paths["swe6_excel"]) if artifact_paths.get("swe6_excel") else None,
            "SWE6",
            note_sheet="SWE6_Not_Generated",
        )

        # Make reviewer workbook self-describing when opened without the JSON.
        artifact_ws = wb.create_sheet(self._unique_sheet_name(wb, "99_Artifact_Index"))
        artifact_ws.append(["Artifact", "Original Path / Status"])
        for key in ("analysis_docx", "swe1_word", "swe1_excel", "swe6_excel"):
            value = artifact_paths.get(key)
            display = Path(value).name if value else "Not generated"
            artifact_ws.append([key, display])
        for cell in artifact_ws[1]:
            cell.fill = PatternFill("solid", fgColor=light)
            cell.font = Font(bold=True)
        artifact_ws.column_dimensions["A"].width = 24
        linkage_ws = wb.create_sheet("17_Linkage_Audit")
        linkage_ws.append(["Link Type", "Candidate ID", "SRS ID", "Source REQ ID", "Occurrence ID", "Anchor Occurrence", "Location/Envelope", "Equivalence Class", "Match Score", "Reason", "Policy Version"])
        trace_repair = coverage.get("traceability_repair") if isinstance(coverage.get("traceability_repair"), dict) else {}
        for rec in trace_repair.get("linkage_audit_records") or []:
            if not isinstance(rec, dict):
                continue
            linkage_ws.append([
                rec.get("link_type"), rec.get("candidate_id"), rec.get("srs_id"), rec.get("source_requirement_id"), rec.get("occurrence_id"),
                rec.get("matched_anchor_occurrence_id"), json.dumps(rec.get("envelopes") or rec.get("source_location") or "", ensure_ascii=False),
                rec.get("equivalence_class"), rec.get("match_score"), rec.get("match_reason") or rec.get("linkage_reason"), rec.get("policy_version"),
            ])

        artifact_ws.column_dimensions["B"].width = 100

        wb.save(output_path)

    def _write_human_review_summary(
        self,
        output_path: Path,
        *,
        source_document: Path,
        provider_metadata: Any,
        evaluation: dict[str, Any],
        requirement_data: dict[str, Any],
        artifact_focus: str = "swe1",
    ) -> None:
        coverage = requirement_data.get("source_coverage") or {}
        regression = requirement_data.get("regression_report") or {}
        gate = regression.get("regression_gate") or {}
        integrity = requirement_data.get("reference_integrity_result") or {}
        completeness = requirement_data.get("reference_completeness_result") or {}
        ug = requirement_data.get("unsupported_generation_report") or {}
        behavior_cov = coverage.get("behavior_coverage_summary") if isinstance(coverage.get("behavior_coverage_summary"), dict) else {}
        testability = requirement_data.get("testability_and_decomposition_result") if isinstance(requirement_data.get("testability_and_decomposition_result"), dict) else {}
        test_summary = testability.get("summary") if isinstance(testability.get("summary"), dict) else {}
        findings = [x for x in (regression.get("findings") or []) if isinstance(x, dict)]
        classes: dict[str, int] = {}
        for item in findings:
            key = str(item.get("classification") or "Unclassified")
            classes[key] = classes.get(key, 0) + 1
        review_findings = [x for x in (requirement_data.get("review_findings") or []) if isinstance(x, dict)]
        conflicts = [x for x in (requirement_data.get("conflict_register") or []) if isinstance(x, dict)]
        naming_issues = [x for x in (requirement_data.get("naming_issue_register") or []) if isinstance(x, dict)]
        gaps = [x for x in (requirement_data.get("gaps") or []) if isinstance(x, dict)]
        sem_cov = requirement_data.get("semantic_source_unit_coverage") if isinstance(requirement_data.get("semantic_source_unit_coverage"), dict) else {}
        sem_prov = requirement_data.get("semantic_provenance_audit") if isinstance(requirement_data.get("semantic_provenance_audit"), dict) else {}
        swe6_audit = requirement_data.get("swe6_export_preservation_audit") if isinstance(requirement_data.get("swe6_export_preservation_audit"), dict) else {}
        intent_cov = requirement_data.get("test_intent_coverage") if isinstance(requirement_data.get("test_intent_coverage"), dict) else {}
        allocation_counts: dict[str, int] = {}
        for req in [x for x in (requirement_data.get("requirements") or []) if isinstance(x, dict)]:
            key = str(req.get("allocation_status") or "UNCLASSIFIED")
            allocation_counts[key] = allocation_counts.get(key, 0) + 1
        gap_to_srs_links = sum(len(x.get("related_srs_ids") or []) for x in gaps)
        validity = str(coverage.get("coverage_validity") or "VALID")
        lines = [
            "Requirement Studio Review Summary",
            "=================================",
            "",
            f"실행 버전 : {self.app_version}",
            f"Source    : {source_document.name}",
            f"Provider  : {getattr(provider_metadata, 'display_name', '')}",
            f"Model     : {getattr(provider_metadata, 'model', '')}",
            f"평가 산출물: {'Unified End-to-End (SWE.1 + SWE.6)' if artifact_focus == 'unified' else ('SWE.6 Qualification Excel' if artifact_focus == 'swe6' else 'SWE.1 Requirement Outputs')}",
            "",
            "[최종 상태]",
            f"Regression Gate : {gate.get('status', 'NOT_EVALUATED')}",
            f"Coverage Validity: {validity}",
            f"Reference Integrity: {'PASS' if integrity.get('passed') else 'FAIL'}",
            f"Reference Completeness: {'PASS' if completeness.get('passed') else 'FAIL'}",
            "",
            "[Source Coverage]",
            f"Explicit Source Occurrences : {coverage.get('explicit_source_requirement_occurrence_count', 0)}",
            f"Covered                     : {len(coverage.get('covered') or [])}",
            f"Missing                     : {len(coverage.get('missing') or []) if coverage.get('missing_count') is not None else 'N/A'}",
            f"Uncertain                   : {len(coverage.get('uncertain') or [])}",
            f"Weighted Occurrence Coverage: {_pct(coverage.get('weighted_source_coverage_percent'))}",
            f"Coverage Mode               : {coverage.get('coverage_mode', 'EXPLICIT_ID_COVERAGE_AVAILABLE')}",
            f"Semantic Unit Linkage Coverage: {_pct(sem_cov.get('coverage_percent'))}",
            f"Semantic Disposition Coverage: {_pct(sem_cov.get('disposition_coverage_percent'))}",
            f"Semantic Uncovered/Dispositioned: {sem_cov.get('uncovered_unit_count', 0)}",
            f"Semantic Potential Extraction Loss: {(sem_cov.get('disposition_counts') or {}).get('SEMANTIC_MISSING_POTENTIAL_EXTRACTION_LOSS', 0)}",
            f"Semantic Not-SW Preserved   : {(sem_cov.get('disposition_counts') or {}).get('NOT_SW_WITH_ALLOCATION_DECISION', 0)}",
            f"Semantic Review Needed      : {(sem_cov.get('disposition_counts') or {}).get('REVIEW_NEEDED', 0)}",
            f"Semantic Provenance Blocking: {sem_prov.get('blocking_incomplete_count', 0)}",
            f"Behavior Coverage (info)    : {behavior_cov.get('behavior_coverage_percent', 0)}%",
            f"Disposition Coverage        : {_pct(coverage.get('disposition_coverage_percent'))}",
            f"Actual Missing Behaviors    : {coverage.get('actual_missing_behavior_count') if coverage.get('actual_missing_behavior_count') is not None else 'N/A'}",
            f"Missing Disposition Objects : {len(requirement_data.get('missing_behavior_dispositions') or [])}",
        ]
        if coverage.get("coverage_validity_reason"):
            lines.append(f"Validity Reason             : {coverage.get('coverage_validity_reason')}")
        lines += [
            "",
            "[Regression]",
            f"Reference Version : {regression.get('baseline_version') or '없음'}",
            f"Reference Path    : {regression.get('baseline_path') or '없음'}",
            f"Finding Count     : {regression.get('regression_count', 0)}",
        ]
        if classes:
            for key in sorted(classes):
                lines.append(f"- {key}: {classes[key]}")
        lines += [
            "",
            "[Review Objects]",
            f"Review Findings : {len(review_findings)}",
            f"Open Gaps       : {len(gaps)}",
            f"Gap-to-SRS Links: {gap_to_srs_links}",
            f"Conflicts       : {len(conflicts)}",
            f"Naming Issues   : {len(naming_issues)}",
            f"Normal Test Available : {test_summary.get('normal_test_available_srs_count', 0)}",
            f"Test Design Feasible  : {test_summary.get('test_design_feasible_srs_count', 0)}",
            f"Concrete TC Complete  : {test_summary.get('concrete_tc_complete_srs_count', 0)}",
            f"Testable Status       : {test_summary.get('testable_srs_count', 0)}",
            f"Partially Testable    : {test_summary.get('partially_testable_srs_count', 0)}",
            f"Unsupported Generation Precheck: unsupported={ug.get('unsupported_assertion_count', 0)} / uncertain={ug.get('uncertain_assertion_count', 0)} / reviewed={ug.get('reviewed_assertion_count', 0)}",
            f"Deferred Intent Reason Codes: {intent_cov.get('deferred_reason_code_counts', {})} / missing={intent_cov.get('deferred_reason_code_missing_count', 0)}",
            f"Allocation Pending Intents: {intent_cov.get('allocation_pending_intent_count', 0)} / reason completeness={intent_cov.get('allocation_pending_reason_completeness_percent')}",
            f"Intent Disposition Coverage: {_pct(intent_cov.get('intent_disposition_coverage_percent'))}",
            f"SWE.6 Export Preservation: {'PASS' if swe6_audit.get('passed') else ('N/A' if not swe6_audit else 'FAIL')} / blockers={swe6_audit.get('blocking_issue_count', 0)} / review={swe6_audit.get('review_issue_count', 0)}",
            f"SWE.6 Excel Artifact Verify: {(swe6_audit.get('actual_excel_artifact_verification') or {}).get('status', 'N/A')}",
        ]
        if allocation_counts:
            lines.append("Allocation Distribution:")
            for key in sorted(allocation_counts):
                lines.append(f"- {key}: {allocation_counts[key]}")
        lines += [
            "",
            "[주의]",
            "이 요약본은 사람이 빠르게 상태를 확인하기 위한 편의 파일입니다.",
            "Semantic Unit Linkage Coverage는 Canonical 연결 비율이며 기능 누락률이 아닙니다. Not-SW/Review Needed/Potential Extraction Loss disposition을 함께 확인하십시오.",
            (
                "통합 평가는 Source + Review Package + SWE.1 Word/Excel + SWE.6 Excel(생성된 산출물)을 하나의 End-to-End Evidence로 대조합니다."
                if artifact_focus == "unified" else
                ("원문 근거와 상세 판정은 01_SOURCE, 02_REQUIREMENT_STUDIO_REVIEW_PACKAGE.json, 03_실제 SWE.6 Excel을 함께 대조해 확인하세요."
                 if artifact_focus == "swe6" else
                 "원문 근거와 상세 판정은 01_SOURCE, 02_REQUIREMENT_STUDIO_REVIEW_PACKAGE.json, 03_실제 SWE.1 Word를 함께 대조해 확인하세요.")
            ),
        ]
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def build(
        self,
        *,
        source_document: Path,
        provider_metadata: Any,
        analysis_text: str,
        requirement_data: dict[str, Any],
        evaluation: dict[str, Any],
        normalized_summary: dict[str, Any] | None,
        quality_review_config: dict[str, Any] | None,
        artifact_paths: dict[str, str | Path | None] | None,
        evaluation_mode: str = "initial",
    ) -> dict[str, str]:
        source_document = Path(source_document).resolve()
        if not source_document.is_file():
            raise FileNotFoundError(source_document)

        run_id, run_dir = self._new_run_dir(source_document)
        source_name = f"01_SOURCE_{self._safe_name(source_document.stem)}{source_document.suffix.lower()}"
        source_copy = run_dir / source_name
        shutil.copy2(source_document, source_copy)

        json_path = run_dir / "02_REQUIREMENT_STUDIO_REVIEW_PACKAGE.json"
        decision_source = self.project_root / "04_CHANGE_DECISION_V0.73_to_V0.74.txt"
        decision_path = run_dir / "04_CHANGE_DECISION_V0.73_to_V0.74.txt"
        summary_path = run_dir / "05_REQUIREMENT_STUDIO_REVIEW_SUMMARY.txt"
        if decision_source.is_file():
            shutil.copy2(decision_source, decision_path)
        else:
            decision_path.write_text(
                "Requirement Studio V0.74 change-decision companion was not found in the project root.\n",
                encoding="utf-8",
            )

        # Complete locally derived SRS->TC evidence before serializing the Review Package.
        tc_cases = build_swe6_cases(requirement_data or {})
        finalize_test_intent_coverage(requirement_data or {}, tc_cases)
        integrity = (requirement_data or {}).get("reference_integrity_result")
        if isinstance(integrity, dict):
            req_srs = {str(r.get("srs_id") or "") for r in ((requirement_data or {}).get("requirements") or []) if isinstance(r, dict) and r.get("srs_id")}
            errors = list(integrity.get("errors") or [])
            srs_tc_checked = 0
            for case in tc_cases:
                sid = str(case.get("srs_id") or "")
                if not sid:
                    continue
                srs_tc_checked += 1
                if sid not in req_srs:
                    errors.append({"type": "srs_to_tc", "source_id": sid, "target_id": str(case.get("tc_id") or ""), "message": "TC references a missing SRS ID."})
            counts = dict(integrity.get("checked_reference_counts") or {})
            counts["srs_to_tc"] = srs_tc_checked
            integrity["checked_reference_counts"] = counts
            integrity["errors"] = errors
            integrity["error_count"] = len(errors)
            integrity["passed"] = not errors

        meta = provider_metadata
        artifact_source_paths = dict(artifact_paths or {})
        artifacts = {}
        for key, value in artifact_source_paths.items():
            artifacts[key] = Path(value).name if value else None

        artifact_focus = self._artifact_focus_from_config(quality_review_config)
        selected_copy = None
        unified_copies: dict[str, Path] = {}
        if artifact_focus == "unified":
            copy_specs = (
                ("swe1_word", "03_SWE1_WORD_"),
                ("swe1_excel", "03_SWE1_EXCEL_"),
                ("swe6_excel", "03_SWE6_EXCEL_"),
            )
            for key, prefix in copy_specs:
                value = artifact_source_paths.get(key)
                src = Path(str(value)) if value else None
                if src and src.is_file():
                    dst = run_dir / f"{prefix}{src.name}"
                    shutil.copy2(src, dst)
                    unified_copies[key] = dst
            artifact_type = "UNIFIED_END_TO_END"
            evaluation_focus = [
                "source fidelity", "SWE.1 preservation", "allocation/eligibility",
                "child-intent traceability", "SWE.6 preservation", "cross-output consistency",
                "artifact contract", "regression/release governance",
            ]
        else:
            selected_source_key = "swe6_excel" if artifact_focus == "swe6" else "swe1_word"
            selected_source = Path(str(artifact_source_paths.get(selected_source_key) or "")) if artifact_source_paths.get(selected_source_key) else None
            if selected_source and selected_source.is_file():
                selected_copy = run_dir / f"03_{selected_source.name}"
                shutil.copy2(selected_source, selected_copy)
            artifact_type = "SWE6_QUALIFICATION_XLSX" if artifact_focus == "swe6" else "SWE1_REQUIREMENT_DOCX"
            evaluation_focus = (
                ["eligibility correctness", "test intent preservation", "TC completeness", "deferred intent governance", "TC traceability", "SWE.6 export preservation"]
                if artifact_focus == "swe6" else
                ["source fidelity", "requirement completeness", "atomicity", "traceability", "allocation/eligibility", "SWE.1 export preservation"]
            )
        swe6_review_artifact = unified_copies.get("swe6_excel") if artifact_focus == "unified" else (selected_copy if artifact_focus == "swe6" else None)
        if artifact_focus in {"swe6", "unified"} and swe6_review_artifact:
            swe6_audit = (requirement_data or {}).get("swe6_export_preservation_audit")
            if not isinstance(swe6_audit, dict):
                swe6_audit = {}
                (requirement_data or {})["swe6_export_preservation_audit"] = swe6_audit
            artifact_verification = self._verify_swe6_excel_artifact(swe6_review_artifact, tc_cases)
            swe6_audit["actual_excel_artifact_verification"] = artifact_verification
            if not artifact_verification.get("passed"):
                blockers = [x for x in (swe6_audit.get("blocking_records") or []) if isinstance(x, dict)]
                artifact_blocker = {
                    "issue": "ACTUAL_XLSX_ARTIFACT_VERIFICATION_FAILED",
                    "status": artifact_verification.get("status"),
                    "verified_artifact": artifact_verification.get("verified_artifact"),
                    "artifact_sha256": artifact_verification.get("artifact_sha256"),
                    "prepopulated_result_tc_ids": artifact_verification.get("prepopulated_result_tc_ids") or [],
                    "prepopulated_result_cells": artifact_verification.get("prepopulated_result_cells") or [],
                    "missing_tc_ids": artifact_verification.get("missing_tc_ids") or [],
                    "extra_tc_ids": artifact_verification.get("extra_tc_ids") or [],
                    "severity": "RELEASE_BLOCKING",
                }
                if not any(str(x.get("issue") or "") == "ACTUAL_XLSX_ARTIFACT_VERIFICATION_FAILED" for x in blockers):
                    blockers.append(artifact_blocker)
                swe6_audit["blocking_records"] = blockers
                swe6_audit["blocking_issue_count"] = len(blockers)
                swe6_audit["passed"] = False
                swe6_audit["tool_quality_gate_passed"] = False
                swe6_audit["tool_quality_gate_status"] = "FAIL"
                swe6_audit["artifact_readiness_gate_passed"] = False
                swe6_audit["artifact_readiness_gate_status"] = "FAIL"
                swe6_audit["release_gate_passed"] = False
                swe6_audit["audit_status"] = "FAIL"
        normalized = dict(normalized_summary or {})
        # Source content/path duplication is intentionally excluded from the JSON because file 01
        # is the untouched source. Local absolute paths are also stripped from the external hand-off.
        normalized.pop("compact_text", None)
        if normalized.get("source_document"):
            normalized["source_document"] = Path(str(normalized["source_document"])).name
        if normalized.get("visual_evidence_path"):
            normalized["visual_evidence_path"] = Path(str(normalized["visual_evidence_path"])).name

        source_sha256 = self._sha256(source_copy)
        previous_payload, previous_path = self._load_previous_review_package(source_sha256, run_dir)
        current_run_context = {
            "requirement_studio_version": self.app_version,
            "source_sha256": source_sha256,
            "provider": getattr(meta, "display_name", ""),
            "provider_id": getattr(meta, "provider_id", ""),
            "model": getattr(meta, "model", ""),
            "endpoint_family": getattr(meta, "endpoint_family", ""),
            "auth_mode": getattr(meta, "auth_mode", ""),
            "project_header_enabled": bool(getattr(meta, "project_header_enabled", False)),
            "response_parsing_mode": getattr(meta, "response_parsing_mode", ""),
            "extraction_core_profile": "v0.46-compatible-1.1",
        }
        regression_report = build_reliable_regression_report(
            requirement_data or {}, previous_payload, previous_path, current_run=current_run_context
        )
        if isinstance(requirement_data, dict):
            requirement_data["regression_report"] = regression_report

        # Keep the hand-off compact: Canonical core holds requirements/gaps and lightweight refs,
        # while calculated_review_evidence owns the full audit records. This avoids duplicating the
        # large Source Occurrence matrix in the same JSON package.
        canonical_core = copy.deepcopy(requirement_data or {})
        review_fields = (
            "source_coverage", "conflict_register", "naming_issue_register", "reference_integrity_result",
            "reference_completeness_result", "export_preservation_audit", "swe6_export_preservation_audit",
            "unsupported_generation_report", "testability_and_decomposition_result",
            "test_intent_coverage", "regression_report", "review_findings", "missing_behavior_dispositions",
        )
        canonical_core["review_evidence_refs"] = {field: f"calculated_review_evidence.{field}" for field in review_fields}
        for field in review_fields:
            canonical_core.pop(field, None)

        payload = {
            "review_package_schema_version": self.PACKAGE_SCHEMA_VERSION,
            "run": {
                "run_id": run_id,
                "evaluation_mode": str(evaluation_mode or "initial"),
                "requirement_studio_version": self.app_version,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "source_file": source_copy.name,
                "source_original_name": source_document.name,
                "source_sha256": source_sha256,
                "extraction_core_profile": "v0.46-compatible-1.1",
                "provider": getattr(meta, "display_name", ""),
                "provider_id": getattr(meta, "provider_id", ""),
                "model": getattr(meta, "model", ""),
                "endpoint_family": getattr(meta, "endpoint_family", ""),
                "auth_mode": getattr(meta, "auth_mode", ""),
                "project_header_enabled": bool(getattr(meta, "project_header_enabled", False)),
                "response_parsing_mode": getattr(meta, "response_parsing_mode", ""),
                "local_endpoint_redacted": True,
            },
            "review_handoff": {
                "evaluation_artifact_focus": artifact_focus,
                "file_1_source": source_copy.name,
                "file_2_review_package": json_path.name,
                "file_3_artifact_type": artifact_type,
                "file_3_artifact": selected_copy.name if selected_copy else "",
                "file_3_swe1_word": (unified_copies.get("swe1_word").name if unified_copies.get("swe1_word") else (selected_copy.name if artifact_focus == "swe1" and selected_copy else "")),
                "file_3_swe1_excel": unified_copies.get("swe1_excel").name if unified_copies.get("swe1_excel") else "",
                "file_3_swe6_excel": (unified_copies.get("swe6_excel").name if unified_copies.get("swe6_excel") else (selected_copy.name if artifact_focus == "swe6" and selected_copy else "")),
                "unified_artifacts": {k: v.name for k, v in unified_copies.items()},
                "evaluation_focus": evaluation_focus,
                "file_4_change_decision": decision_path.name,
                "human_summary": summary_path.name,
                "instruction": (
                    "Unified End-to-End evaluation: compare Source, Review Package, SWE.1 Word/Excel, SWE.6 Excel, QA and regression as one evidence graph. Missing artifacts explicitly not selected/generated must not be treated as tool defects."
                    if artifact_focus == "unified" else
                    ("For AI evaluation, compare 01 Source + 02 Review Package + 03 actual SWE.6 Qualification Excel. Focus on eligibility, intent preservation, concrete testability, deferred governance and TC traceability. Keep 04/05 as companion artifacts."
                     if artifact_focus == "swe6" else
                     "For AI evaluation, compare 01 Source + 02 Review Package + 03 actual SWE.1 Word. Focus on source fidelity, allocation, atomicity and traceability. Keep 04/05 as companion artifacts.")
                ),
            },
            "evaluation_request": self._evaluation_request(artifact_focus),
            "normalized_summary": normalized,
            "local_qa": evaluation or {},
            "quality_review_config": quality_review_config or {},
            "canonical_requirement": canonical_core,
            "canonical_requirement_view": "core_only; full audit records are under calculated_review_evidence",
            "calculated_review_evidence": {
                "source_coverage": (requirement_data or {}).get("source_coverage") or {},
                "reference_integrity_result": (requirement_data or {}).get("reference_integrity_result") or {},
                "reference_completeness_result": (requirement_data or {}).get("reference_completeness_result") or {},
                "conflict_register": (requirement_data or {}).get("conflict_register") or [],
                "naming_issue_register": (requirement_data or {}).get("naming_issue_register") or [],
                "export_preservation_audit": (requirement_data or {}).get("export_preservation_audit") or {},
                "swe6_export_preservation_audit": (requirement_data or {}).get("swe6_export_preservation_audit") or {},
                "testability_and_decomposition_result": (requirement_data or {}).get("testability_and_decomposition_result") or {},
                "test_intent_coverage": (requirement_data or {}).get("test_intent_coverage") or {},
                "regression_report": (requirement_data or {}).get("regression_report") or {},
                "unsupported_generation_report": (requirement_data or {}).get("unsupported_generation_report") or {},
                "review_findings": (requirement_data or {}).get("review_findings") or [],
                "missing_behavior_dispositions": (requirement_data or {}).get("missing_behavior_dispositions") or [],
            },
            "artifact_index": artifacts,
            "reviewer_findings_policy": {
                "rule": "Reviewer findings are review opinions, not source evidence and must not silently overwrite Canonical Requirement.",
                "recommended_statuses": ["Open", "Confirmed", "Rejected", "Uncertain", "Human Review Needed"],
            },
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        self._write_human_review_summary(
            summary_path,
            source_document=source_document,
            provider_metadata=meta,
            evaluation=evaluation or {},
            requirement_data=requirement_data or {},
            artifact_focus=artifact_focus,
        )

        # Root-level pointer is program-internal convenience; RUN folder contains the four explicit hand-off files.
        (self.base_dir / "LATEST_RUN.txt").write_text(str(run_dir), encoding="utf-8")
        return {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "source": str(source_copy),
            "review_json": str(json_path),
            "evaluation_artifact_focus": artifact_focus,
            "evaluation_artifact": str(selected_copy) if selected_copy else "",
            "swe1_word": str(unified_copies.get("swe1_word") or (selected_copy if artifact_focus == "swe1" else "")),
            "swe1_excel": str(unified_copies.get("swe1_excel") or ""),
            "swe6_excel": str(unified_copies.get("swe6_excel") or (selected_copy if artifact_focus == "swe6" else "")),
            "change_decision": str(decision_path),
            "review_summary": str(summary_path),
            "regression_gate_status": str((regression_report.get("regression_gate") or {}).get("status") or "NOT_EVALUATED"),
            "regression_count": str(regression_report.get("regression_count", 0)),
            "baseline_version": str(regression_report.get("baseline_version") or ""),
        }
