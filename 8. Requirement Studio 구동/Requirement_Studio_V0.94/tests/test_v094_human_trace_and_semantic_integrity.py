from pathlib import Path
from core.basic_functional_test_design import BASIC_FUNCTIONAL_MODE, _extract_signal_assignments, _semantic_label, build_basic_functional_cases
from core.e2e_exporter import _compact_requirement_trace, _format_behavior_definition, _format_verification_criteria
from core.guideline_mining import build_guideline_mining_snapshot, is_rule_approved

def _base(sid,fids):
    return {"parent_srs_id":sid,"test_object_id":f"OBJ_{sid}","test_object_type":"SWE6_TC","source_fact_fragment_ids":fids,"verification_domain":"SWE.6 Software Qualification","swe6_eligibility":"Eligible","allocation_status":"SW_BEHAVIOR_INFERRED_REVIEW_REQUIRED","execution_readiness":"REVIEW_REQUIRED","human_review_required":True}

def _req(sid,name,facts,evidence=""):
    return {"srs_id":sid,"function_name":name,"requirement":name,"processing_action":name,"output":"Source-defined 결과","acceptance_criteria":"Source 정의와 일치해야 한다.","allocation_status":"SW_BEHAVIOR_INFERRED_REVIEW_REQUIRED","swe6_eligibility":"Eligible","source_backed_atomic_behaviors":[{"source_fact_fragment_id":fid,"source_semantic_unit_id":f"U_{sid}","source_location":"Page 1","behavior_text":text} for fid,text in facts],"fact_level_allocations":[{"source_fact_fragment_id":fid,"source_semantic_unit_id":f"U_{sid}","source_location":"Page 1","source_fact":text,"allocation_status":"SW_BEHAVIOR_INFERRED_REVIEW_REQUIRED","swe6_eligibility":"Eligible","verification_domain":"SWE.6 Software Qualification"} for fid,text in facts],"source_evidence":[{"document":"sample.pdf","location":"Page 1, 2.1","text":evidence or "\n".join(t for _,t in facts)}]}

def _build(req):
    fids=[x["source_fact_fragment_id"] for x in req["source_backed_atomic_behaviors"]]
    return build_basic_functional_cases({"requirements":[req]},[_base(req["srs_id"],fids)])

def _exec(cases): return [c for c in cases if c.get("test_design_mode")==BASIC_FUNCTIONAL_MODE]

def test_v094_behavior_definition_removes_source_dump_and_internal_step_tokens():
    raw="1. step=1; action=System wake-up한다.\n2. step=2; action=C_PreCrankReq를 0x1로 송출한다.\n[출처 기반 세부 동작]\n- SRC-SEM-ABC · Page 7: 원문 반복"
    out=_format_behavior_definition(raw)
    assert out=="1. System wake-up한다.\n2. C_PreCrankReq를 0x1로 송출한다."
    assert "step=" not in out and "action=" not in out and "SRC-SEM" not in out

def test_v094_traceability_is_location_first_and_does_not_repeat_source_prose():
    req={"source_evidence":[{"document":"spec.pdf","location":"Page 7, 2.4","text":"HU는 매우 긴 원문 요구사항을 반복한다."},{"document":"spec.pdf","location":"Page 5 그림 2","text":"동작 시나리오","modality":"visual"}],"source_backed_atomic_behaviors":[{"source_semantic_unit_id":"SRC-SEM-001","source_fact_fragment_id":"F001","source_location":"Page 7","behavior_text":"긴 원문"}]}
    out=_compact_requirement_trace(req,"fallback long prose")
    assert "[문서] spec.pdf / Page 7, 2.4" in out and "[그림] spec.pdf / Page 5 그림 2" in out and "[근거] [문서] SRC-SEM-001 / Page 7" in out
    assert "매우 긴 원문" not in out and "긴 원문" not in out

def test_v094_verification_criteria_groups_o_x_conditions_in_same_cell():
    raw="All ACC OFF, All ACC ON (IGN OFF), EV/PHEV ACC & IGN OFF / IGN3 ON 조건은 동작 여부 O이며, All ACC ON / IGN1 ON, All START Stationary, All Monitoring, ICE/PHEV/HEV Remote 조건은 X로 정의된다."
    out=_format_verification_criteria(raw)
    assert "① 동작 가능 (O)" in out and "② 동작 불가 (X)" in out and "- All ACC OFF" in out and "- All Monitoring" in out

def test_v094_invalid_semantic_has_precedence_over_direction_keyword():
    assert _semantic_label("Invalid Value - Front fallback text")=="invalid"
    assert _semantic_label("Camera Input Error - Rear context")=="error"

def test_v094_identifier_parser_does_not_split_on_suffix_from_position():
    assert _extract_signal_assignments("HU는 icmuImagePosition 정보를 전송한다.")==[]
    parsed=_extract_signal_assignments("HU는 C_PreCrankReq를 0x1(Req on)로 송출한다.")
    assert parsed and parsed[0]["signal"]=="C_PreCrankReq" and parsed[0]["value"]=="0x1"

def test_v094_sequence_mapping_never_uses_invalid_as_front_response():
    source="""SVM_CaptureModeViewRequest 값\n0x1: Front View Printing Request\n0x2: Rear View Printing Request\n0x3: Left View Printing Request\n0x4: Right View Printing Request\n0x7: Invalid\nSVM_CaptureModeViewState 값\n0x1: Front response\n0x2: Rear response\n0x3: Left response\n0x4: Right response\n0x7: Invalid - Front text mentioned elsewhere\nHU는 Front→Rear→Left→Right 순서로 요청하고 동일 순서의 응답을 확인해야 한다."""
    req=_req("SRS_SEQ","View sequence",[("F001",source)],evidence=source); req["requirement"]="HU는 SVM_CaptureModeViewRequest와 SVM_CaptureModeViewState를 Front→Rear→Left→Right 순서로 처리해야 한다."
    cases,_,_=_build(req); seq=next(c for c in _exec(cases) if c.get("basic_case_kind")=="SEQUENCE_REQUEST_RESPONSE")
    assert [v["expected_output"] for v in seq["test_vectors"]]==["0x1","0x2","0x3","0x4"]
    assert all(v["expected_output"]!="0x7" for v in seq["test_vectors"]); assert seq.get("semantic_integrity_status")=="PASS"

def test_v094_second_timing_checkpoint_preserves_first_checkpoint_prerequisite():
    fact="OMUOSMirCtrl=0x2 송신 후 5초 이내 Mirror_UnFldCtrlSta가 0x1 또는 0x2로 수신되지 않으면 실패로 판단한다. 0x1 수신 후 15초 이내 0x2가 수신되지 않아도 실패로 판단한다."
    cases,_,_=_build(_req("SRS_TIME","미러 펼침 Timing",[("F001",fact)])); timing=[c for c in _exec(cases) if c.get("split_decision")=="SPLIT_DISTINCT_TIMING_CHECKPOINT"]
    second=next(c for c in timing if c.get("input_value")=="15초")
    assert "5초" in second.get("precondition","") and "Mirror_UnFldCtrlSta=0x1" in second.get("precondition","") and "OMUOSMirCtrl=0x2" in second.get("precondition","")

def test_v094_guideline_registry_contains_new_human_approved_presentation_rules():
    assert is_rule_approved("GR-PRES-003") and is_rule_approved("GR-PRES-004") and is_rule_approved("GR-PRES-005")
    snap=build_guideline_mining_snapshot(); assert snap["decision_example_count"]>=8 and all(c.get("auto_promoted") is False for c in snap["mined_candidates"])

def test_v094_api_keys_and_input_have_no_readme_txt():
    root=Path(__file__).resolve().parents[1]; assert list((root/"api_keys").glob("README*.txt"))==[] and list((root/"input").glob("README*.txt"))==[]
