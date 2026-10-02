import json
from pathlib import Path

from core.cross_document_semantics import _fragments_for_requirement
from core.evaluation_orchestrator import MultiModelEvaluationOrchestrator
from core.swe6_exporter import build_swe6_cases


def _evaluation_result(provider: str):
    return {
        "schema_version": "1.0",
        "provider": provider,
        "model": provider + "-model",
        "verdict": "PASS_WITH_REVIEW_ITEMS",
        "tool_quality_gate": "PASS_WITH_REVIEW_ITEMS",
        "artifact_readiness_gate": "REVIEW_REQUIRED",
        "official_release": "HOLD",
        "executive_summary": ["review"],
        "positive_checks": [],
        "findings": [],
        "release_gates": [],
        "next_version_recommendations": [],
        "limitations": [],
    }


def _minimal_review_run(tmp_path: Path):
    root = tmp_path / "Requirement_Studio_V0.69"
    root.mkdir()
    (root / "config").mkdir()
    (root / "config" / "evaluation_api_config.json").write_text(json.dumps({
        "enabled": True,
        "transport": "hchat",
        "providers": {"gpt": {"enabled": True}, "gemini": {"enabled": True}, "claude": {"enabled": True}},
    }), encoding="utf-8")
    run = root / "review_exchange" / "RUN"
    run.mkdir(parents=True)
    (run / "01_SOURCE_sample.txt").write_text("source fact", encoding="utf-8")
    (run / "02_REQUIREMENT_STUDIO_REVIEW_PACKAGE.json").write_text(json.dumps({
        "run": {"source_sha256": "a" * 64, "source_original_name": "sample.txt"},
        "canonical_requirement": {"requirements": []},
    }), encoding="utf-8")
    (run / "03_sample.txt").write_text("artifact", encoding="utf-8")
    (run / "05_REQUIREMENT_STUDIO_REVIEW_SUMMARY.txt").write_text("summary", encoding="utf-8")
    return root, run


def test_evaluation_status_exposes_stage_progress_and_provider_completion(tmp_path, monkeypatch):
    root, run = _minimal_review_run(tmp_path)
    orchestrator = MultiModelEvaluationOrchestrator(root, app_version="v0.69", provider_config={})
    monkeypatch.setattr(orchestrator, "_source_text", lambda _p: "source fact")
    monkeypatch.setattr(orchestrator, "_call_one", lambda name, evidence: (_evaluation_result(name), name + "-model"))
    recorded = []
    original = orchestrator._write_status

    def capture(output_dir, payload):
        recorded.append(dict(payload))
        original(output_dir, payload)

    monkeypatch.setattr(orchestrator, "_write_status", capture)
    orchestrator.run(run)
    stages = [x.get("stage") for x in recorded]
    for required in ("BUILD_EVIDENCE", "PROVIDER_REVIEW", "CONSENSUS", "FINAL_RESULT", "OUTPUT_VERIFY", "OUTPUT_VERIFIED"):
        assert required in stages
    assert recorded[-1]["status"] == "COMPLETED"
    assert recorded[-1]["progress_percent"] == 100
    assert recorded[-1]["provider_status"] == {"gpt": "COMPLETED", "gemini": "COMPLETED", "claude": "COMPLETED"}
    assert recorded[-1]["final_result_part_count"] >= 1


def test_quality_review_tab_contains_dedicated_automatic_evaluation_progress_ui():
    main_text = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    for token in (
        'QLabel("자동 평가 진행상황")',
        'self.eval_progress_bar = QProgressBar()',
        'self.eval_provider_progress_labels',
        'self._refresh_automatic_evaluation_progress',
        'self.open_final_result_button',
        'Final Result: {part_count}개 TXT part 생성 완료',
    ):
        assert token in main_text


def test_first_bplus_fragment_is_not_dropped_when_source_joins_korean_and_ascii_tokens():
    req = {
        "function_name": "High Power Mode",
        "requirement": "ON 명령 수신, B-CAN WAKE UP 상태, ERR PIN HIGH에서 LOW 상태 변환, 최초 B+ 인가 조건 중 하나라도 참이면 High Power Mode로 진입한다.",
        "activation_trigger": "4개 조건 중 하나",
        "preconditions": "",
        "processing_action": "High Power Mode 진입",
        "output": "",
        "acceptance_criteria": "",
    }
    units = []
    fragments = []
    texts = [
        "ON 명령 수신 시",
        "B-CAN WAKE UP 상태",
        "ERR PIN HIGH에서 LOW 상태 변환 시",
        "최초B+ 인가 시",
    ]
    for i, text in enumerate(texts, 1):
        uid = f"SEM{i}"
        units.append({"source_semantic_unit_id": uid})
        fragments.append({
            "source_fact_fragment_id": f"FRAG{i}",
            "parent_source_semantic_unit_id": uid,
            "source_location": f"Paragraph {132+i}",
            "fragment_index": 1,
            "source_excerpt": text,
        })
    owned = _fragments_for_requirement(req, units, fragments)
    assert {x["source_fact_fragment_id"] for x in owned} == {"FRAG1", "FRAG2", "FRAG3", "FRAG4"}


def test_mixed_domain_parent_expected_text_is_not_echoed_back_into_tc_description():
    req = {
        "srs_id": "SRS_006",
        "function_name": "SW 오류 복구",
        "requirement": "SW 오류 시 복구하며 최종 상태는 최초 B+ 인가 상태와 동일해야 한다.",
        "allocation_status": "SW_IMPLEMENTATION_REQUIREMENT",
        "swe6_eligibility": "Eligible",
        "verification_domain": "SWE.6 Software Qualification",
        "semantic_provenance_status": "COMPLETE",
        "source_semantic_unit_ids": ["SEM184", "SEM185"],
        "source_backed_atomic_behaviors": [
            {"source_semantic_unit_id": "SEM184", "source_fact_fragment_id": "F-SW", "behavior_text": "의도하지 않은 SW 오류 발생 시 MCU Reset 등을 통해 정상 상태로 복귀한다.", "knowledge_state": "KNOWN"},
            {"source_semantic_unit_id": "SEM185", "source_fact_fragment_id": "F-SYS", "behavior_text": "강제 Reset 복귀 상태는 최초 B+ 전원 인가 상태와 동일하다.", "knowledge_state": "KNOWN"},
        ],
        "fact_level_allocations": [
            {"source_fact_fragment_id": "F-SW", "source_fact": "의도하지 않은 SW 오류 발생 시 MCU Reset 등을 통해 정상 상태로 복귀한다.", "swe6_eligibility": "Eligible", "verification_domain": "SWE.6 Software Qualification"},
            {"source_fact_fragment_id": "F-SYS", "source_fact": "강제 Reset 복귀 상태는 최초 B+ 전원 인가 상태와 동일하다.", "swe6_eligibility": "Deferred pending SW allocation", "verification_domain": "System Integration / SYS.5"},
        ],
        "activation_trigger": "SW 오류 발생",
        "processing_action": "MCU Reset 등을 통한 복구",
        "output": "최초 B+ 전원 인가 상태와 동일한 정상 복귀 상태",
        "acceptance_criteria": "최초 B+ 전원 인가 상태와 동일",
    }
    cases = build_swe6_cases({"requirements": [req]})
    assert len(cases) == 1
    case = cases[0]
    assert case["mixed_fact_scope_limited"] is True
    assert "최초 B+ 전원 인가 상태와 동일" not in case["expected_desc"]
    assert "기대 결과 기본 표현" not in case["description"]
