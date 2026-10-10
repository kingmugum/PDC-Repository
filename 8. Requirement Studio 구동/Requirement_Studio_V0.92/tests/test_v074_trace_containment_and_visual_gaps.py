from core.cross_document_semantics import (
    _critical_ownership_token_groups,
    _disambiguate_shared_fragment_ownership,
    _fragments_for_requirement,
)
from core.quality_audit import _ensure_unanalyzed_visual_asset_gaps
from core.evaluation_orchestrator import MultiModelEvaluationOrchestrator


def test_timing_token_without_whitespace_is_preserved():
    groups = _critical_ownership_token_groups("피드백 신호 5초동안 미수신 시 부저 미응답")
    assert "5초" in groups["timing"]


def test_critical_completion_can_use_exact_cited_source_location():
    req = {
        "requirement": "HU는 부저 출력 요청에 따른 피드백 신호를 5초 동안 미수신하면 부저 미응답으로 판단하고 촬영을 중단한다.",
        "acceptance_criteria": "5초 미수신 시 촬영 중단",
        "source_evidence": [{"location": "Page 9 / 2.7", "text": "부저 제어"}],
    }
    matched = [{"source_semantic_unit_id": "U1"}]
    fragments = [
        {"source_fact_fragment_id": "F1", "parent_source_semantic_unit_id": "U1", "source_location": "Page 9", "source_excerpt": "HU_Buzzer_OnOffReq를 송신한다.", "fragment_index": 1},
        {"source_fact_fragment_id": "F2", "parent_source_semantic_unit_id": "U2", "source_location": "Page 9", "source_excerpt": "부저 출력 요청에 따른 피드백 신호 5초동안 미수신 시 부저 미응답으로 판단하며, 촬영 중단한다.", "fragment_index": 2},
        {"source_fact_fragment_id": "F3", "parent_source_semantic_unit_id": "U3", "source_location": "Page 10", "source_excerpt": "다른 기능은 5초 타이머를 사용한다.", "fragment_index": 1},
    ]
    selected = _fragments_for_requirement(req, matched, fragments)
    assert any(x.get("source_fact_fragment_id") == "F2" for x in selected)
    assert not any(x.get("source_fact_fragment_id") == "F3" for x in selected)
    recovered = next(x for x in selected if x.get("source_fact_fragment_id") == "F2")
    assert recovered.get("ownership_policy") == "V0.74_SOURCE_BOUNDED_CRITICAL_FACT_COMPLETION"
    assert "5초" in recovered.get("ownership_completion_tokens", [])


def test_clear_shared_fragment_leakage_moves_to_dominant_parent_only():
    frag = {"source_fact_fragment_id": "FSTATE", "source_excerpt": "아웃사이드 미러 상태를 판단한다."}
    command = {
        "srs_id": "SRS_CMD",
        "requirement": "HU는 명령에 따라 OMUOSMirCtrl Fold/Unfold 제어 명령을 송신한다.",
        "source_fact_fragments": [dict(frag)],
        "source_backed_atomic_behaviors": [{"source_fact_fragment_id": "FSTATE"}],
        "fact_level_allocations": [{"source_fact_fragment_id": "FSTATE"}],
    }
    state = {
        "srs_id": "SRS_STATE",
        "requirement": "HU는 Mirror 상태 신호를 수신하여 아웃사이드 미러 상태를 판단한다.",
        "source_fact_fragments": [dict(frag)],
        "source_backed_atomic_behaviors": [{"source_fact_fragment_id": "FSTATE"}],
        "fact_level_allocations": [{"source_fact_fragment_id": "FSTATE"}],
    }
    records = _disambiguate_shared_fragment_ownership([command, state])
    assert records[0]["resolution"] == "DOMINANT_PARENT_ONLY"
    assert records[0]["dominant_srs_id"] == "SRS_STATE"
    assert command["source_fact_fragments"] == []
    assert state["source_fact_fragments"]


def test_unanalyzed_visual_dependency_becomes_filterable_gap_only_when_requirement_already_says_so():
    data = {
        "requirements": [
            {"srs_id": "SRS_VIS", "clarification_needed": ["그림 외 텍스트만으로 병합 위치 확인 불가"], "source_evidence": [{"location": "Page 13", "text": "병합 다이어그램"}]},
            {"srs_id": "SRS_TEXT", "clarification_needed": ["신호 주기 확인 필요"], "source_evidence": [{"location": "Page 12", "text": "text"}]},
        ],
        "gaps": [],
    }
    compact = "[VISUAL_NOTICE] 문서에 그림/미디어가 존재하지만 현재 Provider에서 Vision 분석 결과가 없습니다."
    _ensure_unanalyzed_visual_asset_gaps(data, compact)
    assert len(data["gaps"]) == 1
    gap = data["gaps"][0]
    assert gap["gap_type"] == "UNANALYZED_VISUAL_ASSET"
    assert gap["related_srs_ids"] == ["SRS_VIS"]
    assert gap["terminal_disposition"] is False


def test_evaluation_prompt_does_not_treat_open_review_needed_as_tool_defect():
    prompt = MultiModelEvaluationOrchestrator._system_prompt()
    assert "REVIEW_NEEDED" in prompt
    assert "Artifact Readiness/Release Governance" in prompt
