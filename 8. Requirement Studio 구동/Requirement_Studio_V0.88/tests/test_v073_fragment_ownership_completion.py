from core.cross_document_semantics import _fragments_for_requirement
from core.quality_audit import build_swe6_export_preservation_audit, build_testability_result, finalize_test_intent_coverage


def _audit(req):
    data = {"requirements": [req], "gaps": []}
    data["testability_and_decomposition_result"] = build_testability_result(data)
    finalize_test_intent_coverage(data, [])
    return data["swe6_export_preservation_audit"]


def _base_req(text: str):
    return {
        "candidate_id": "REQ-CAND-001", "srs_id": "SRS_001", "requirement": text,
        "acceptance_criteria": text, "output": text, "processing_action": text,
        "source_requirement_ids": [], "source_semantic_unit_ids": ["SRC-SEM-1"],
        "requirement_level": "System", "allocation_status": "SYSTEM_REQUIREMENT_PENDING_SW_ALLOCATION",
        "swe1_eligibility": "Review Needed", "swe6_eligibility": "Deferred pending SW allocation",
        "verification_domain": "System Integration / SYS.5", "semantic_provenance_status": "COMPLETE",
        "source_backed_atomic_behaviors": [], "source_backed_facts": [], "source_fact_fragments": [],
        "fact_level_allocations": [], "source_table_fact_matches": [],
        "activation_trigger": "", "preconditions": "", "exception_conditions": [], "external_dependencies": [],
        "clarification_needed": [], "category": "기능", "function_name": "Feature",
    }


def test_v073_fragment_selector_completes_timing_retry_facts_inside_matched_unit():
    req = _base_req("OMUOSMirCtrl=0x2 송출 후 5초 이내 0x1 응답이 없거나 15초 이내 0x2가 없으면 1회 retry한다.")
    matched = [{"source_semantic_unit_id": "SRC-SEM-1"}]
    fragments = [
        {"source_fact_fragment_id":"SRC-FRAG-A","parent_source_semantic_unit_id":"SRC-SEM-1","source_location":"Page 16","fragment_index":1,"source_excerpt":"OMUOSMirCtrl ==0x2 Unfold) 송출 후,"},
        {"source_fact_fragment_id":"SRC-FRAG-B","parent_source_semantic_unit_id":"SRC-SEM-1","source_location":"Page 16","fragment_index":2,"source_excerpt":"5초 이내 0x1 응답이 없으면 미러 제어 실패로 판단한다."},
        {"source_fact_fragment_id":"SRC-FRAG-C","parent_source_semantic_unit_id":"SRC-SEM-1","source_location":"Page 16","fragment_index":3,"source_excerpt":"15초 이내 0x2 응답이 없으면 1회 retry한다."},
    ]
    selected = _fragments_for_requirement(req, matched, fragments)
    ids = {x["source_fact_fragment_id"] for x in selected}
    assert {"SRC-FRAG-B", "SRC-FRAG-C"}.issubset(ids)
    assert any(x.get("ownership_policy") == "V0.73_CRITICAL_FACT_COMPLETION" for x in selected)


def test_v073_exact_ownership_aggregates_tokens_across_multiple_owned_fragments():
    req = _base_req("HU_Buzzer_OnOffReq 명령 후 5초 이내 응답을 확인한다.")
    req["source_fact_fragments"] = [
        {"source_fact_fragment_id":"SRC-FRAG-A", "source_excerpt":"HU_Buzzer_OnOffReq 명령을 송신한다."},
        {"source_fact_fragment_id":"SRC-FRAG-B", "source_excerpt":"5초 이내 응답을 확인한다."},
    ]
    req["source_backed_atomic_behaviors"] = [
        {"source_fact_fragment_id":"SRC-FRAG-A", "source_semantic_unit_id":"SRC-SEM-1", "behavior_text":"HU_Buzzer_OnOffReq 명령을 송신한다."},
        {"source_fact_fragment_id":"SRC-FRAG-B", "source_semantic_unit_id":"SRC-SEM-1", "behavior_text":"5초 이내 응답을 확인한다."},
    ]
    req["fact_level_allocations"] = [
        {"source_fact_fragment_id":"SRC-FRAG-A", "source_fact":"HU_Buzzer_OnOffReq 명령을 송신한다."},
        {"source_fact_fragment_id":"SRC-FRAG-B", "source_fact":"5초 이내 응답을 확인한다."},
    ]
    row = _audit(req)["rows"][0]
    assert row["critical_fact_fragment_missing_tokens"] == []
    assert row["critical_fact_fragment_ownership_ok"] is True
    assert row["owned_fragment_fact_token_sources"]["hu_buzzer_onoffreq"] == ["SRC-FRAG-A"]
    assert row["owned_fragment_fact_token_sources"]["5초"] == ["SRC-FRAG-B"]


def test_v073_structured_rollup_cannot_claim_token_absent_from_exact_fragment():
    req = _base_req("Signal_Mode=0x2 상태가 15초 유지되면 1회 재시도한다.")
    req["source_fact_fragments"] = [{"source_fact_fragment_id":"SRC-FRAG-A", "source_excerpt":"Signal_Mode=0x2 상태를 확인한다."}]
    req["fact_level_allocations"] = [{
        "source_fact_fragment_id":"SRC-FRAG-A", "source_fact":"Signal_Mode=0x2 상태를 확인한다.",
        "structured_source_facts":[{"source_literal":"Signal_Mode=0x2 / 15초 / 1회", "identifiers":["Signal_Mode"], "numeric_values":["0x2"], "timing_values":["15초"], "enum_mappings":[{"value":"1회","meaning":"retry"}]}],
    }]
    row = _audit(req)["rows"][0]
    assert "15초" in row["critical_fact_fragment_missing_tokens"]
