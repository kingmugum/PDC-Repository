from pathlib import Path

from core.cross_document_semantics import (
    _complete_explicit_cited_non_sw_matches,
    _contextualize_conflicting_shared_fragments,
)
from core.evaluation_orchestrator import MultiModelEvaluationOrchestrator
from core.quality_audit import _extract_fact_tokens, _normalize_fact_token, finalize_test_intent_coverage
from core.swe1_exporter import build_swe1_records


def test_hex_fact_token_matching_is_case_insensitive():
    tokens = {_normalize_fact_token(x) for x in _extract_fact_tokens("SVM_CaptureModeState 0X0: Default / 0x1: On")}
    assert "0x0" in tokens
    assert "0x1" in tokens


def test_finalize_deferred_summary_counts_allocation_pending_intents():
    data = {
        "requirements": [{
            "srs_id": "SRS_001",
            "swe6_eligibility": "Deferred pending SW allocation",
            "allocation_status": "SYSTEM_REQUIREMENT_PENDING_SW_ALLOCATION",
        }],
        "testability_and_decomposition_result": {
            "summary": {},
            "by_srs": [{
                "srs_id": "SRS_001",
                "swe6_eligibility": "Deferred pending SW allocation",
                "required_test_intents": ["Normal / Positive", "Exception / Recovery"],
                "source_backed_child_intents": [],
            }],
        },
    }
    finalize_test_intent_coverage(data, [])
    summary = data["testability_and_decomposition_result"]["summary"]
    assert summary["required_intent_count"] == 2
    assert summary["deferred_intent_count"] == 2


def test_guide_person_collapses_many_srs_into_stable_policy_questions(tmp_path: Path):
    reqs = []
    for i in range(1, 16):
        reqs.append({
            "srs_id": f"SRS_{i:03d}",
            "allocation_status": "SW_BEHAVIOR_INFERRED_REVIEW_REQUIRED",
            "swe1_eligibility": "Eligible",
            "swe6_eligibility": "Eligible",
        })
    review = {
        "canonical_requirement": {
            "requirements": reqs,
            "semantic_source_unit_coverage": {
                "open_review_needed_records": [{"source_semantic_unit_id": "SRC-SEM-1"}],
            },
            "shared_fragment_contextualization": [],
        },
        "calculated_review_evidence": {
            "swe6_export_preservation_audit": {
                "rows": [{"srs_id": "SRS_001", "cross_domain_bundle_review_required": True}],
            }
        },
    }
    evidence = {
        "requirement_studio_version": "v0.78",
        "evaluation_mode": "unified",
        "run_dir": "run-1",
        "source": {"file": "source.pdf", "sha256": "abc"},
        "evidence_package_sha256": "def",
    }
    situation = {"observed_counts": {"generated_tc_count": 15}}
    report = MultiModelEvaluationOrchestrator._build_guide_person(review, evidence, situation)
    ids = [x["question_id"] for x in report["questions"]]
    assert ids == ["GP-ALLOC-001", "GP-TC-001", "GP-MIX-001", "GP-OPEN-001"]
    assert report["question_count"] == 4
    assert len(report["questions"][0]["observed_examples"]) <= 8

    text = MultiModelEvaluationOrchestrator._render_guide_person(report)
    parts = MultiModelEvaluationOrchestrator.split_guide_person(
        text, tmp_path / "guide_person", lines_per_file=110,
        handoff_identity=report["handoff_identity"],
    )
    assert parts[0].name == "guide_person_001.txt"
    assert (tmp_path / "guide_person" / "manifest.json").is_file()
    assert "[ ] YES" in parts[0].read_text(encoding="utf-8")


def test_mixed_domain_scope_scrubs_excluded_fact_from_acceptance_fields():
    req = {
        "srs_id": "SRS_001",
        "candidate_id": "REQ-CAND-001",
        "swe1_eligibility": "Eligible",
        "swe6_eligibility": "Eligible",
        "category": "기능",
        "requirement": "HU는 SW 오류 시 Reset하고 B-CAN Wakeup 상태를 확인해야 한다.",
        "activation_trigger": "SW 오류 또는 B-CAN Wakeup 상태",
        "processing_action": "SW 오류 시 MCU Reset하고 B-CAN Wakeup 상태를 확인한다.",
        "acceptance_criteria": "MCU Reset 복귀 및 B-CAN Wakeup 상태 확인",
        "source_evidence": [{"document": "source.docx", "location": "Paragraph 1-2", "text": "..."}],
        "source_backed_atomic_behaviors": [
            {"source_fact_fragment_id": "F1", "behavior_text": "SW 오류 시 MCU Reset으로 정상 상태로 복귀한다."},
            {"source_fact_fragment_id": "F2", "behavior_text": "B-CAN Wakeup 상태를 확인한다."},
        ],
        "fact_level_allocations": [
            {"source_fact_fragment_id": "F1", "swe1_eligibility": "Eligible"},
            {"source_fact_fragment_id": "F2", "swe1_eligibility": "Review Needed"},
        ],
    }
    row = build_swe1_records({"requirements": [req]})[0]
    assert "B-CAN" not in row["요구사항 내역"]
    assert "B-CAN" not in row["작동 명세 정의"]
    assert "B-CAN" not in row["검증 기준"]
    assert "B-CAN" in row["기타"]


def test_shared_fragment_divergent_parent_allocation_gets_contextual_aliases():
    base_frag = {
        "source_fact_fragment_id": "SRC-FRAG-ONE",
        "source_excerpt": "캡처에 실패한 경우 1회 재시도한다.",
        "source_location": "Page 16",
    }
    reqs = [
        {
            "srs_id": "SRS_A",
            "source_fact_fragments": [dict(base_frag)],
            "source_backed_atomic_behaviors": [{**base_frag, "behavior_text": base_frag["source_excerpt"]}],
            "fact_level_allocations": [{
                "source_fact_fragment_id": "SRC-FRAG-ONE",
                "allocation_status": "SW_BEHAVIOR_INFERRED_REVIEW_REQUIRED",
                "verification_domain": "SWE.6 Software Qualification (Allocation Review Required)",
            }],
        },
        {
            "srs_id": "SRS_B",
            "source_fact_fragments": [dict(base_frag)],
            "source_backed_atomic_behaviors": [{**base_frag, "behavior_text": base_frag["source_excerpt"]}],
            "fact_level_allocations": [{
                "source_fact_fragment_id": "SRC-FRAG-ONE",
                "allocation_status": "INHERIT_PARENT_ALLOCATION_PENDING",
                "verification_domain": "System Integration / SYS.5",
            }],
        },
    ]
    index = [dict(base_frag)]
    records = _contextualize_conflicting_shared_fragments(reqs, index)
    assert len(records) == 1
    ids = [r["source_fact_fragments"][0]["source_fact_fragment_id"] for r in reqs]
    assert ids[0] != ids[1]
    assert all(x.startswith("SRC-FRAGCTX-") for x in ids)
    assert all(r["source_fact_fragments"][0]["contextual_alias_of"] == "SRC-FRAG-ONE" for r in reqs)


def test_explicit_cited_non_sw_trace_completion_recovers_second_location():
    req = {
        "requirement": "커넥터는 DIP 타입이어야 하며 커넥터 납땜에는 자동납땜을 적용해야 한다.",
        "source_evidence": [
            {"location": "Paragraph 205", "text": "커넥터(DIP) 타입 적용 할 것"},
            {"location": "Paragraph 208", "text": "자동납땜 적용 할 것"},
        ],
    }
    units = [
        {"source_semantic_unit_id": "U205", "source_location": "Paragraph 205", "source_excerpt": "커넥터(DIP) 타입 적용 할 것"},
        {"source_semantic_unit_id": "U208", "source_location": "Paragraph 208", "source_excerpt": "자동납땜 적용 할 것"},
    ]
    completed = _complete_explicit_cited_non_sw_matches(req, units, [units[0]])
    assert {x["source_semantic_unit_id"] for x in completed} == {"U205", "U208"}
