from pathlib import Path

from core.quality_audit import apply_quality_audits, finalize_test_intent_coverage
from core.requirement_engine import RequirementEngine
from core.swe1_exporter import build_swe1_records
from core.swe6_exporter import build_swe6_cases


def _base_req(cid, srs, location, text, requirement):
    return {
        "candidate_id": cid, "srs_id": srs, "scenario_candidate_id": "SCN-CAND-001",
        "category": "비기능", "function_name": "Cross Document", "requirement": requirement,
        "user_input": "", "system_input_preconditions": "", "processing_action": requirement,
        "output": "", "acceptance_criteria": text, "failure_situations": [], "user_intervention_points": [],
        "derivation_type": "explicit", "derivation_reason": "", "clarification_needed": [],
        "source_evidence": [{"document": "system.docx", "location": location, "text": text}],
        "confidence": 0.95, "classification_basis": "입력문서 명시", "activation_trigger": "",
        "preconditions": "", "behavior_flows": [], "evaluation_method": "", "exception_conditions": [],
        "related_artifacts": [],
    }


def test_no_explicit_id_uses_semantic_mode_and_allocation(tmp_path: Path):
    compact = """[DOCUMENT] system.docx
[SRC DOC-C0001 | Paragraph 205 | text]
커넥터는 DIP 타입을 적용하고 LEAD-WIRE 적용을 금지한다.
[SRC DOC-C0002 | Paragraph 210 | text]
B+ 인가 또는 LIN Bus wake-up signal 송신 후 Slave node 초기화 시간 60ms를 대기한다.
[SRC DOC-C0003 | Table 10 / Row 2 | table]
최대 소비 전류는 MAX 100mA이다.
"""
    reqs = [
        _base_req("REQ-CAND-001", "SRS_001", "Paragraph 205", "커넥터는 DIP 타입을 적용하고 LEAD-WIRE 적용을 금지한다.", "DIP 커넥터를 적용한다."),
        _base_req("REQ-CAND-002", "SRS_002", "Paragraph 210", "B+ 인가 또는 LIN Bus wake-up signal 송신 후 Slave node 초기화 시간 60ms를 대기한다.", "Wake-up 후 60ms를 대기한다."),
        _base_req("REQ-CAND-003", "SRS_003", "Table 10 / Row 2", "최대 소비 전류는 MAX 100mA이다.", "최대 소비 전류는 100mA이다."),
    ]
    data = {
        "schema_version": "REQ-STUDIO-CANONICAL-REQ-1.6", "source_document": "system.docx",
        "scenario_candidates": [{"scenario_candidate_id":"SCN-CAND-001","scenario_name":"x","user_goal_context":"","scenario_flow":[],"expected_outcome":"","source_evidence":[{"document":"system.docx","location":"Paragraph 205","text":"x"}]}],
        "requirements": reqs,
        "gaps": [
            {"gap_id":"G1","description":"참조문서 목록의 외부 규격 본문이 제공되지 않음","related_candidate_ids":["REQ-CAND-001","REQ-CAND-002","REQ-CAND-003"]},
            {"gap_id":"G2","description":"참조문서 목록의 외부 규격 본문이 제공되지 않음","related_candidate_ids":["REQ-CAND-001","REQ-CAND-002","REQ-CAND-003"]},
        ],
    }
    apply_quality_audits(data, compact)
    cov=data["source_coverage"]
    assert cov["coverage_validity"] == "NOT_APPLICABLE"
    assert cov["weighted_source_coverage_percent"] is None
    assert cov["actual_missing_behavior_count"] is None
    assert cov["actual_missing_behavior_evaluation_status"] == "NOT_EVALUATED"
    assert cov["coverage_mode"] == "EXPLICIT_ID_COVERAGE_NOT_APPLICABLE"
    assert data["semantic_source_units"]
    for r in reqs:
        assert r["source_semantic_unit_ids"]
        assert r["source_chunk_ids"]
    assert reqs[0]["allocation_status"] == "MECHANICAL_CONNECTOR_REQUIREMENT"
    assert reqs[0]["swe1_eligibility"] == "Not Applicable"
    assert reqs[1]["allocation_status"] == "SYSTEM_REQUIREMENT_PENDING_SW_ALLOCATION"
    assert reqs[1]["source_backed_atomic_behaviors"]
    assert reqs[2]["allocation_status"] == "ELECTRICAL_REQUIREMENT"
    assert len(data["gaps"]) == 1
    assert data["gaps"][0]["gap_scope"] == "document"
    assert not data["gaps"][0]["related_candidate_ids"]

    swe1=build_swe1_records(data)
    assert swe1 == []  # V0.58 physically separates Review Needed from the Main SWE.1 body.
    cases=build_swe6_cases(data)
    assert cases == []  # SRS_002 is deferred pending SW allocation; others are Not Applicable.
    finalize_test_intent_coverage(data, cases)
    by={x["srs_id"]:x for x in data["testability_and_decomposition_result"]["by_srs"]}
    assert by["SRS_001"]["intent_complete_status"] == "Not Applicable"
    assert by["SRS_002"]["intent_complete_status"] == "Deferred pending SW allocation"

    engine=RequirementEngine(tmp_path)
    # Point the engine to the real contract for a structure-only regression check.
    engine.schema_path=Path(__file__).resolve().parents[1]/"contracts"/"canonical_requirement_schema.json"
    result=engine.evaluate_structure(data)
    assert result["errors"] == []
