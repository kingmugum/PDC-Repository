from pathlib import Path

from core.basic_functional_test_design import BASIC_FUNCTIONAL_MODE, build_basic_functional_cases
from core.e2e_exporter import _display_review_reason, _number_requirement_meaning_units
from core.guideline_mining import build_guideline_mining_snapshot, mine_candidate_rules, is_rule_approved


def _base(sid: str, fids: list[str]):
    return {
        "parent_srs_id": sid,
        "test_object_id": f"OBJ_{sid}",
        "test_object_type": "SWE6_TC",
        "source_fact_fragment_ids": fids,
        "verification_domain": "SWE.6 Software Qualification",
        "swe6_eligibility": "Eligible",
        "allocation_status": "SW_BEHAVIOR_INFERRED_REVIEW_REQUIRED",
        "execution_readiness": "REVIEW_REQUIRED",
        "human_review_required": True,
    }


def _req(sid: str, name: str, facts: list[tuple[str,str]], *, evidence: str = ""):
    return {
        "srs_id": sid,
        "function_name": name,
        "requirement": name,
        "processing_action": name,
        "output": "Source-defined 결과",
        "acceptance_criteria": "Source 정의와 일치해야 한다.",
        "allocation_status": "SW_BEHAVIOR_INFERRED_REVIEW_REQUIRED",
        "swe6_eligibility": "Eligible",
        "source_backed_atomic_behaviors": [
            {"source_fact_fragment_id":fid,"source_semantic_unit_id":f"U_{sid}","source_location":"Page 1","behavior_text":text}
            for fid,text in facts
        ],
        "fact_level_allocations": [
            {"source_fact_fragment_id":fid,"source_semantic_unit_id":f"U_{sid}","source_location":"Page 1","source_fact":text,
             "allocation_status":"SW_BEHAVIOR_INFERRED_REVIEW_REQUIRED","swe6_eligibility":"Eligible","verification_domain":"SWE.6 Software Qualification"}
            for fid,text in facts
        ],
        "source_evidence": [{"location":"Page 1","text": evidence or "\n".join(t for _,t in facts)}],
    }


def _build(req):
    fids=[x["source_fact_fragment_id"] for x in req["source_backed_atomic_behaviors"]]
    return build_basic_functional_cases({"requirements":[req]},[_base(req["srs_id"],fids)])


def _exec(cases):
    return [c for c in cases if c.get("test_design_mode")==BASIC_FUNCTIONAL_MODE]


def test_v093_review_reason_is_korean_in_human_main_but_raw_can_remain_english():
    case={
        "human_review_required":True,
        "required_resolution":"Approve System qualification scope, controllable conditions, observations, and acceptance criteria before execution.",
    }
    text=_display_review_reason(case)
    assert "실행 전 시스템 적격성 평가 범위" in text
    assert "Approve System qualification" not in text


def test_v093_requirement_detail_is_numbered_by_meaning_unit_in_same_cell():
    raw=("HU는 CCS로부터 내 차 주변 영상 전송 요청을 수신하면 System wake-up하여 요청을 처리할 수 있도록 해야 한다. "
         "System wake-up 완료 후 C_PreCrankReq를 0x1(Req on)으로 송출하여 B-CAN wake-up해야 한다. "
         "HU는 HEV/PHEV/EV 차종인 경우 IGN3 On 해야 한다.")
    out=_number_requirement_meaning_units(raw)
    assert "① HU는 CCS로부터" in out
    assert "② System wake-up 완료 후" in out
    assert "③ HU는 HEV/PHEV/EV" in out
    assert out.count("\n")==2


def test_v093_user_semantic_branch_rule_splits_folding_possible_impossible():
    req=_req("SRS_MIRROR","미러 Folding 가능 여부",[
        ("F001","Mirror_MirFldOpt=0x1은 Folding 가능, 0x0은 Folding 불가능으로 판단한다.")
    ])
    cases,_,audit=_build(req)
    cases=_exec(cases)
    branch=[c for c in cases if c.get("basic_case_kind")=="SEMANTIC_BRANCH"]
    assert len(branch)==2
    assert {(c["input_value"],c["output_value"]) for c in branch}=={("0x1","Folding 가능"),("0x0","Folding 불가능")}
    assert all(c["split_decision"]=="SPLIT_SEMANTIC_BRANCH" for c in branch)
    assert all("HR-TC-002" in c.get("guideline_rule_ids",[]) for c in branch)
    assert audit["guideline_mining"]["approved_rule_count"]>=5


def test_v093_distinct_timing_checkpoints_become_separate_cases():
    req=_req("SRS_TIME","미러 펼침 Timing",[
        ("F001","OMUOSMirCtrl=0x2 송신 후 5초 이내 Mirror_UnFldCtrlSta가 0x1 또는 0x2로 수신되지 않으면 실패로 판단한다. 0x1 수신 후 15초 이내 0x2가 수신되지 않아도 실패로 판단한다.")
    ])
    cases,_,_= _build(req)
    cases=_exec(cases)
    timing=[c for c in cases if c.get("split_decision")=="SPLIT_DISTINCT_TIMING_CHECKPOINT"]
    assert len(timing)==2
    assert {c["input_value"] for c in timing}=={"5초","15초"}
    assert all("GR-TC-001" in c.get("guideline_rule_ids",[]) for c in timing)
    assert all("실패" in c.get("expected_state","") for c in timing)


def test_v093_exact_trace_does_not_false_pass_when_one_grouped_property_vector_has_no_fact():
    # Source evidence contains JPEG, but finalized Fact Fragment exists only for Resolution.
    req=_req("SRS_PROP","저장 이미지",[
        ("F001","Resolution: 4290*720")
    ], evidence="Format: JPEG; Resolution: 4290*720; Size: 0.25 MB 이하")
    cases,reviews,_=_build(req)
    cases=_exec(cases)
    prop=next(c for c in cases if c.get("basic_case_kind")=="OUTPUT_ARTIFACT_PROPERTIES")
    assert prop["exact_field_trace_status"]=="REVIEW_REQUIRED"
    assert prop["human_review_required"] is True
    assert any(r.get("review_type")=="EXACT_FIELD_FACT_TRACE_REQUIRED" for r in reviews)


def test_v093_guideline_mining_generates_candidates_but_does_not_auto_promote():
    snap=build_guideline_mining_snapshot()
    assert snap["schema_version"].endswith("0.93")
    assert snap["decision_example_count"]>=5
    assert snap["candidate_rule_count"]>=1
    assert all(c["auto_promoted"] is False for c in snap["mined_candidates"])
    assert is_rule_approved("GR-TC-001") is True
    assert is_rule_approved("HR-TC-002") is True


def test_v093_mojibake_readmes_removed_from_api_keys_and_input():
    root=Path(__file__).resolve().parents[1]
    api_txt=list((root/"api_keys").glob("README*.txt"))
    input_txt=list((root/"input").glob("README*.txt"))
    assert api_txt==[]
    assert input_txt==[]
    assert (root/"api_keys"/".gitkeep").exists()
    assert (root/"input"/".gitkeep").exists()
