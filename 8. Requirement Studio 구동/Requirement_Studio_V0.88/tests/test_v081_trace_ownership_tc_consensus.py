from core.cross_document_semantics import (
    _disambiguate_shared_semantic_unit_ownership,
    _reconcile_swe6_fact_scope,
    _software_like_behavior_terms,
    apply_allocation_gate,
)
from core.evaluation_orchestrator import MultiModelEvaluationOrchestrator
from core.swe6_exporter import build_swe6_cases


def _req(sid: str, requirement: str, uid: str, evidence_text: str, location: str):
    return {
        "srs_id": sid,
        "candidate_id": f"REQ-{sid}",
        "function_name": requirement,
        "requirement": requirement,
        "processing_action": requirement,
        "acceptance_criteria": requirement,
        "source_semantic_unit_ids": [uid],
        "source_chunk_ids": ["C1"],
        "source_evidence": [{"location": location, "text": evidence_text}],
        "source_fact_fragments": [{
            "source_fact_fragment_id": f"F-{uid}",
            "parent_source_semantic_unit_id": uid,
            "source_location": location,
            "source_excerpt": evidence_text,
        }],
        "source_backed_atomic_behaviors": [{
            "source_semantic_unit_id": uid,
            "source_fact_fragment_id": f"F-{uid}",
            "behavior_text": evidence_text,
        }],
        "source_backed_facts": [{"source_semantic_unit_id": uid, "source_fact": evidence_text}],
        "fact_level_allocations": [{"source_semantic_unit_id": uid, "source_fact_fragment_id": f"F-{uid}"}],
        "source_table_fact_matches": [],
        "source_requirement_ids": [],
        "activation_trigger": "",
        "preconditions": "",
        "output": "",
    }


def test_v081_korean_send_output_is_software_like_action():
    assert "송출" in _software_like_behavior_terms("HU는 C_PreCrankReq=0x1을 송출해야 한다.")


def test_v081_inferred_parent_promotes_send_output_child_fact_and_generates_candidate_tc():
    req = {
        "srs_id": "SRS_002",
        "requirement": "HU는 System wake-up 완료 후 C_PreCrankReq=0x1을 송출하여 B-CAN wake-up 해야 한다.",
        "function_name": "B-CAN wake-up",
        "processing_action": "C_PreCrankReq=0x1 송출",
        "acceptance_criteria": "C_PreCrankReq=0x1 송출",
        "source_evidence": [{"location": "Page 7", "text": "HU는 System wake-up 완료 후 C_PreCrankReq=0x1을 송출하여 B-CAN wake-up 해야 한다."}],
        "source_requirement_ids": [],
        "source_semantic_unit_ids": ["U1"],
        "source_fact_fragments": [{
            "source_fact_fragment_id": "F1",
            "parent_source_semantic_unit_id": "U1",
            "source_location": "Page 7",
            "source_excerpt": "HU는 System wake-up 완료 후 C_PreCrankReq=0x1을 송출하여 B-CAN wake-up 해야 한다.",
        }],
        "source_backed_atomic_behaviors": [{
            "source_semantic_unit_id": "U1",
            "source_fact_fragment_id": "F1",
            "behavior_text": "HU는 System wake-up 완료 후 C_PreCrankReq=0x1을 송출하여 B-CAN wake-up 해야 한다.",
        }],
        "semantic_provenance_status": "COMPLETE",
        "category": "기능",
        "clarification_needed": [],
        "activation_trigger": "System wake-up 완료 후",
        "preconditions": "",
        "output": "C_PreCrankReq=0x1",
    }
    apply_allocation_gate(req, [{
        "source_semantic_unit_id": "U1",
        "source_fact_fragment_id": "F1",
        "source_location": "Page 7",
        "source_excerpt": req["requirement"],
    }])
    assert req["allocation_status"] == "SW_BEHAVIOR_INFERRED_REVIEW_REQUIRED"
    assert any(x.get("swe6_eligibility") == "Eligible" for x in req["fact_level_allocations"])
    _reconcile_swe6_fact_scope(req)
    assert req["swe6_eligibility"] == "Eligible"
    cases = build_swe6_cases({"requirements": [req]})
    assert len(cases) == 1
    assert cases[0]["srs_id"] == "SRS_002"


def test_v081_shared_semantic_unit_dominant_owner_removes_unrelated_claim_and_evidence():
    uid = "U-SOLDER"
    unit = {
        "source_semantic_unit_id": uid,
        "source_chunk_id": "C208",
        "source_location": "Paragraph 208",
        "source_excerpt": "자동납땜 적용 할 것.",
        "linked_candidate_ids": ["REQ-SRS_002", "REQ-SRS_022"],
        "linked_srs_ids": ["SRS_002", "SRS_022"],
    }
    brightness = _req(
        "SRS_002",
        "무드램프 밝기는 USM 설정에 의해서만 가능하고 Rheostat level과 연동되지 않아야 한다.",
        uid,
        "자동납땜 적용 할 것.",
        "Paragraph 208",
    )
    solder = _req(
        "SRS_022",
        "제어기는 자동납땜을 적용해야 한다.",
        uid,
        "자동납땜 적용 할 것.",
        "Paragraph 208",
    )
    records = _disambiguate_shared_semantic_unit_ownership([brightness, solder], [unit])
    assert records
    assert records[0]["dominant_srs_id"] == "SRS_022"
    assert uid not in brightness["source_semantic_unit_ids"]
    assert brightness["source_fact_fragments"] == []
    assert brightness["source_backed_atomic_behaviors"] == []
    assert brightness["source_evidence"] == []
    assert uid in solder["source_semantic_unit_ids"]
    assert "SRS_002" not in unit["linked_srs_ids"]


def test_v081_parent_eligible_with_zero_eligible_fact_scope_is_explicitly_deferred():
    req = {
        "srs_id": "SRS_X",
        "swe6_eligibility": "Eligible",
        "fact_level_allocations": [
            {"source_fact_fragment_id": "F1", "swe6_eligibility": "Deferred pending SW allocation"}
        ],
        "human_decision_required": False,
        "review_status": "SOURCE_BACKED",
        "official_release_eligible": True,
        "hold_reason": "",
    }
    _reconcile_swe6_fact_scope(req)
    assert req["swe6_eligibility"] == "Deferred - Fact Allocation Review"
    assert req["swe6_scope_consistency_status"] == "DEFERRED_NO_ELIGIBLE_FACT_SCOPE"
    assert req["human_decision_required"] is True
    assert req["official_release_eligible"] is False


def _finding(category: str, title: str, problem: str, *, gate="TOOL_QUALITY"):
    return {
        "finding_key": "",
        "severity": "RELEASE_BLOCKING",
        "gate_scope": gate,
        "category": category,
        "title": title,
        "affected_ids": ["SRS_002"],
        "source_references": ["Page 7"],
        "problem": problem,
        "recommendation": "Generate a candidate TC or make the deferral explicit.",
        "evidence": ["SRS_002 swe6_eligibility=Eligible and generated_tc_ids=[]"],
    }


def test_v081_cross_category_equivalent_zero_tc_findings_cluster_as_strong_consensus():
    results = {
        "gpt": {"findings": [_finding("CROSS_OUTPUT", "Eligible SRS has no generated TC", "SRS_002 is SWE.6 Eligible but zero TC was generated.")], "tool_quality_gate": "FAIL", "artifact_readiness_gate": "FAIL", "official_release": "HOLD"},
        "gemini": {"findings": [_finding("SWE6", "SWE.6 Eligible 요구사항 테스트 케이스 미생성", "SRS_002는 적격이지만 테스트 케이스가 생성되지 않았다.")], "tool_quality_gate": "FAIL", "artifact_readiness_gate": "FAIL", "official_release": "HOLD"},
        "claude": {"findings": [_finding("TRACEABILITY", "SRS_002 eligible with zero TC", "Eligible SRS_002 has no test case and missing TC is blocking.")], "tool_quality_gate": "FAIL", "artifact_readiness_gate": "REVIEW_REQUIRED", "official_release": "HOLD"},
    }
    consensus = MultiModelEvaluationOrchestrator._consensus(results)
    assert len(consensus["consensus_findings"]) == 1
    assert consensus["consensus_findings"][0]["strength"] == "STRONG_CONSENSUS"
    assert set(consensus["consensus_findings"][0]["reviewers"]) == {"gpt", "gemini", "claude"}


def test_v081_same_srs_but_different_failure_concept_does_not_merge():
    zero_tc = _finding("SWE6", "Eligible SRS has no generated TC", "SRS_002 is Eligible but no TC was generated.")
    allocation = {
        **_finding("ALLOCATION", "Inferred software allocation requires human approval", "SRS_002 allocation is inferred and needs human sign-off.", gate="ARTIFACT_READINESS"),
        "severity": "RELEASE_REVIEW",
    }
    results = {
        "gpt": {"findings": [zero_tc, allocation], "tool_quality_gate": "FAIL", "artifact_readiness_gate": "REVIEW_REQUIRED", "official_release": "HOLD"},
    }
    consensus = MultiModelEvaluationOrchestrator._consensus(results)
    assert len(consensus["consensus_findings"]) == 2
