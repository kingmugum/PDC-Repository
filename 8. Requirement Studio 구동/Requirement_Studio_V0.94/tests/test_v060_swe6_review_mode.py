import json
from pathlib import Path
from types import SimpleNamespace

from docx import Document
from openpyxl import load_workbook

from core.cross_document_semantics import apply_allocation_gate, build_semantic_source_units
from core.quality_audit import apply_quality_audits, finalize_test_intent_coverage, normalize_requirement_extensions
from core.review_exchange import ReviewExchangeBuilder
from core.swe6_exporter import SWE6Exporter, build_swe6_cases


def _req(srs="SRS_001", text="소프트웨어는 값을 저장해야 한다."):
    req = {
        "candidate_id": "C1", "srs_id": srs, "scenario_candidate_id": "SCN-CAND-001",
        "category": "기능", "function_name": "Feature", "requirement": text,
        "user_input": "", "system_input_preconditions": "", "processing_action": text,
        "output": text, "acceptance_criteria": text, "failure_situations": [], "user_intervention_points": [],
        "derivation_type": "explicit", "derivation_reason": "", "clarification_needed": [],
        "source_evidence": [{"document": "system.docx", "location": "Paragraph 10", "text": text}],
        "confidence": 0.95, "classification_basis": "입력문서 명시", "activation_trigger": "",
        "preconditions": "", "behavior_flows": [], "evaluation_method": "", "exception_conditions": [],
        "related_artifacts": [],
    }
    normalize_requirement_extensions(req)
    return req


def _data(req):
    return {
        "schema_version": "REQ-STUDIO-CANONICAL-REQ-1.9",
        "source_document": "system.docx",
        "scenario_candidates": [{
            "scenario_candidate_id": "SCN-CAND-001", "scenario_name": "x", "user_goal_context": "",
            "scenario_flow": [], "expected_outcome": "",
            "source_evidence": [{"document": "system.docx", "location": "Paragraph 1", "text": "x"}],
        }],
        "requirements": [req], "gaps": [],
    }


def test_review_exchange_can_use_actual_swe6_excel_as_file3(tmp_path):
    root = tmp_path / "Requirement_Studio_V0.61"
    root.mkdir()
    (root / "04_CHANGE_DECISION_V0.61_to_V0.62.txt").write_text("decision", encoding="utf-8")
    source = tmp_path / "source.docx"
    Document().save(source)

    req = _req(text="소프트웨어는 입력을 수신하면 값을 저장해야 한다.")
    req.update({
        "requirement_level": "Software", "allocation_status": "SW_IMPLEMENTATION_REQUIREMENT",
        "swe1_eligibility": "Eligible", "swe6_eligibility": "Eligible",
        "verification_domain": "SWE.6 Software Qualification",
        "source_requirement_ids": ["REQ-1"],
    })
    data = _data(req)
    data["testability_and_decomposition_result"] = {
        "summary": {},
        "by_srs": [{
            "srs_id": "SRS_001", "swe6_eligibility": "Eligible", "normal_test_available": True,
            "test_design_feasible": True, "testability_status": "Testable", "testability_reason": "Source-backed normal verification is available.",
            "required_test_intents": ["Normal / Positive"], "covered_test_intents": [], "not_generated_test_intents": [],
        }],
    }
    swe6 = SWE6Exporter(tmp_path).export_excel(source, data, source_text="")

    builder = ReviewExchangeBuilder(root, app_version="v0.61")
    meta = SimpleNamespace(display_name="H-Chat / GPT", provider_id="hchat_gpt", model="gpt-5.6-terra", endpoint_family="x", auth_mode="key", project_header_enabled=False, response_parsing_mode="text")
    result = builder.build(
        source_document=source, provider_metadata=meta, analysis_text="", requirement_data=data,
        evaluation={}, normalized_summary={}, quality_review_config={"evaluation_artifact": "swe6"},
        artifact_paths={"swe6_excel": str(swe6)}, evaluation_mode="initial",
    )
    run = Path(result["run_dir"])
    file3 = list(run.glob("03_SWE.6 적격성 평가_*.xlsx"))
    assert len(file3) == 1
    payload = json.loads((run / "02_REQUIREMENT_STUDIO_REVIEW_PACKAGE.json").read_text(encoding="utf-8"))
    handoff = payload["review_handoff"]
    assert handoff["file_3_artifact_type"] == "SWE6_QUALIFICATION_XLSX"
    assert handoff["file_3_swe6_excel"] == file3[0].name
    assert handoff["file_3_swe1_word"] == ""
    assert payload["evaluation_request"]["artifact_focus"] == "SWE6_QUALIFICATION_XLSX"
    assert payload["calculated_review_evidence"]["swe6_export_preservation_audit"]["actual_excel_artifact_verification"]["passed"] is True


def test_interface_fact_without_sw_allocation_is_deferred():
    req = _req(text="CAN : 500 Kbit/s, B-CAN NM 지원. LIN : 19.2 Kbit/s.")
    req["source_requirement_ids"] = []
    apply_allocation_gate(req)
    assert req["allocation_status"] == "INTERFACE_FACT_PENDING_SW_ALLOCATION"
    assert req["swe1_eligibility"] == "Review Needed"
    assert req["swe6_eligibility"].startswith("Deferred")
    assert "Interface Allocation Review" in req["verification_domain"]


def test_external_standard_title_without_pipe_and_connector_titles_are_context():
    compact = """[DOCUMENT] system.docx
[SRC DOC-C1 | Paragraph 1 | text]
MS201-02 유해물질 금지 및 신고 - 부품 및 재료
[SRC DOC-C2 | Paragraph 2 | text]
커넥터 사양 및 납땜방식
[SRC DOC-C3 | Paragraph 3 | text]
그림 2 커넥터 사양
[SRC DOC-C4 | Paragraph 4 | text]
핀 간격은 5.5mm 이상이어야 한다.
"""
    units = build_semantic_source_units(compact)
    by_loc = {x["source_location"]: x for x in units}
    assert by_loc["Paragraph 1"]["source_unit_type"] == "external_reference_only"
    assert by_loc["Paragraph 1"]["coverage_eligibility"] == "review_context"
    assert by_loc["Paragraph 2"]["coverage_eligibility"] == "review_context"
    assert by_loc["Paragraph 3"]["coverage_eligibility"] == "review_context"
    assert by_loc["Paragraph 4"]["coverage_eligibility"] == "semantic_unit"


def test_deferred_intents_have_causal_reason_codes_and_swe6_audit():
    src = "SW 오류 발생 시 정상 상태로 복귀한다."
    req = _req(text=src)
    req.update({
        "requirement_level": "Software", "allocation_status": "SW_IMPLEMENTATION_REQUIREMENT",
        "swe1_eligibility": "Eligible", "swe6_eligibility": "Eligible",
        "verification_domain": "SWE.6 Software Qualification",
        "source_requirement_ids": [], "source_semantic_unit_ids": ["SRC-SEM-X"],
        "source_backed_atomic_behaviors": [{"source_semantic_unit_id": "SRC-SEM-X", "behavior_text": src, "knowledge_state": "KNOWN"}],
        "semantic_provenance_status": "COMPLETE",
        "activation_trigger": "SW 오류 발생 시", "processing_action": "정상 상태로 복귀한다.", "output": "정상 상태 복귀",
    })
    data = _data(req)
    data["testability_and_decomposition_result"] = {
        "summary": {},
        "by_srs": [{
            "srs_id": "SRS_001", "swe6_eligibility": "Eligible", "normal_test_available": True,
            "test_design_feasible": True, "testability_status": "Testable", "testability_reason": "Source-backed normal verification is available.",
            "required_test_intents": ["Normal / Positive", "State Transition"],
            "source_backed_child_intents": [{"child_intent_id": "SRS_001-ATOM-01", "source_backed_behavior": src}],
            "covered_test_intents": [], "not_generated_test_intents": [],
        }],
    }
    cases = build_swe6_cases(data)
    finalize_test_intent_coverage(data, cases)
    row = data["testability_and_decomposition_result"]["by_srs"][0]
    deferred = row["not_generated_test_intents"]
    assert deferred and deferred[0]["reason_code"] == "EXPORTER_CAPABILITY_PENDING"
    assert data["test_intent_coverage"]["deferred_reason_code_missing_count"] == 0
    assert data["swe6_export_preservation_audit"]["passed"] is True


def test_expected_description_preserves_source_backed_key_facts(tmp_path):
    src = "Watchdog Timer는 lowest task 이후 동작하며 ISR 내 존재할 수 없다."
    req = _req(text=src)
    req.update({
        "requirement_level": "Software", "allocation_status": "SW_IMPLEMENTATION_REQUIREMENT",
        "swe1_eligibility": "Eligible", "swe6_eligibility": "Eligible",
        "verification_domain": "SWE.6 Software Qualification",
        "source_requirement_ids": ["REQ-1"],
        "source_backed_atomic_behaviors": [{"behavior_text": src, "knowledge_state": "KNOWN"}],
        "output": "Watchdog Timer 동작", "acceptance_criteria": "Watchdog Timer가 요구된 위치에서 동작한다.",
    })
    data = _data(req)
    cases = build_swe6_cases(data)
    assert len(cases) == 1
    case = cases[0]
    assert "lowest task" in case["expected_desc"]
    assert "ISR" in case["expected_desc"]
    assert "정적 분석" in case["method"]
