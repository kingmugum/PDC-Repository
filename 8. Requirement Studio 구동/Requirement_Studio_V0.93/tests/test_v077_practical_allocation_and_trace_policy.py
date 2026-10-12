from pathlib import Path

from core.cross_document_semantics import (
    _allocation_for_text,
    _fact_level_allocation,
    _fragments_for_requirement,
    _source_fact_fragments_for_unit,
)
from core.evaluation_orchestrator import MultiModelEvaluationOrchestrator
from core.swe1_exporter import build_swe1_records


def test_controller_behavior_without_literal_sw_is_review_required_software_candidate():
    alloc = _allocation_for_text(
        "HU는 CCS Command를 수신하면 SVM_CaptureModeCMD를 0x1로 송신하여 캡처 모드를 제어해야 한다."
    )
    assert alloc["allocation_status"] == "SW_BEHAVIOR_INFERRED_REVIEW_REQUIRED"
    assert alloc["swe1_eligibility"] == "Eligible"
    assert alloc["swe6_eligibility"] == "Eligible"
    assert alloc["software_allocation_review_required"] is True
    assert alloc["positive_sw_allocation_evidence"] == []
    assert alloc["software_behavior_inference_evidence"]


def test_high_confidence_nonsoftware_and_pure_system_context_are_not_promoted():
    connector = _allocation_for_text("커넥터 핀 간격은 2.54 mm 이어야 한다.")
    assert connector["swe1_eligibility"] == "Not Applicable"
    assert connector["allocation_status"] == "MECHANICAL_CONNECTOR_REQUIREMENT"

    system_only = _allocation_for_text("시스템은 duration 값의 1.2배로 동작해야 한다.")
    assert system_only["allocation_status"] == "SYSTEM_REQUIREMENT_PENDING_SW_ALLOCATION"
    assert system_only["swe1_eligibility"] == "Review Needed"

    interface = _allocation_for_text("CAN 통신 속도는 500 kbit/s 이다.")
    assert interface["allocation_status"] == "INTERFACE_FACT_PENDING_SW_ALLOCATION"


def test_short_software_like_child_inherits_inferred_parent_scope():
    parent = _allocation_for_text("HU는 캡처 실패 시 1회 재시도해야 한다.")
    child = {
        "source_semantic_unit_id": "SRC-SEM-1",
        "source_fact_fragment_id": "SRC-FRAG-1",
        "source_chunk_id": "DOC-C0016",
        "source_location": "Page 16",
        "source_excerpt": "캡처에 실패한 경우 1회 재시도한다.",
    }
    alloc = _fact_level_allocation(child, parent)
    assert alloc["allocation_status"] == "SW_BEHAVIOR_INFERRED_REVIEW_REQUIRED"
    assert alloc["swe6_eligibility"] == "Eligible"
    assert alloc["allocation_inheritance"] == "PARENT_INFERRED_SOFTWARE_BEHAVIOR_INHERITED"


def test_source_bounded_behavior_completion_recovers_noncritical_exception_clauses():
    units = [
        {
            "source_semantic_unit_id": "SRC-SEM-P16",
            "source_chunk_id": "DOC-C0016",
            "source_location": "Page 16",
            "source_kind": "paragraph",
            "source_excerpt": (
                "IGN on 되면 남은 과정을 생략하고 기능을 종료해야 한다. "
                "아웃사이드 미러 제어 실패 시 1회 재시도하되 캡처를 종료하지 않아야 한다."
            ),
        }
    ]
    fragment_index = [f for u in units for f in _source_fact_fragments_for_unit(u)]
    req = {
        "requirement": (
            "HU는 IGN on 되면 남은 과정을 생략하고 기능을 종료해야 하며, "
            "아웃사이드 미러 제어 실패 시 1회 재시도하되 캡처를 종료하지 않아야 한다."
        ),
        "source_evidence": [{"location": "Page 16", "text": units[0]["source_excerpt"]}],
    }
    owned = _fragments_for_requirement(req, units, fragment_index)
    blob = " ".join(str(x.get("source_excerpt") or "") for x in owned)
    assert "IGN on" in blob
    assert "캡처를 종료하지" in blob


def test_adjacent_paragraph_continuation_can_recover_first_bplus_condition():
    matched = [
        {
            "source_semantic_unit_id": "SRC-SEM-135",
            "source_chunk_id": "DOC-C0103",
            "source_location": "Paragraph 135",
            "source_kind": "paragraph",
            "source_excerpt": "TRANSCEIVER의 ERR PIN HIGH에서 LOW 상태 변환 시 High Power Mode로 전환한다.",
        }
    ]
    adjacent = {
        "source_semantic_unit_id": "SRC-SEM-136",
        "source_chunk_id": "DOC-C0104",
        "source_location": "Paragraph 136",
        "source_kind": "paragraph",
        "source_excerpt": "최초 B+ 인가 시 High Power Mode로 전환한다.",
    }
    all_units = matched + [adjacent]
    fragment_index = [f for u in all_units for f in _source_fact_fragments_for_unit(u)]
    req = {
        "requirement": "무드램프 마스터 제어기는 ERR PIN 조건 또는 최초 B+ 인가 시 High Power Mode로 전환해야 한다.",
        "source_evidence": [{"location": "Paragraph 132-135", "text": "High Power Mode 전환 조건"}],
    }
    owned = _fragments_for_requirement(req, matched, fragment_index)
    assert any("최초 B+" in str(x.get("source_excerpt") or "") for x in owned)


def test_main_swe1_view_does_not_present_pending_fact_as_software_scope():
    req = {
        "srs_id": "SRS_007",
        "candidate_id": "REQ-CAND-007",
        "swe1_eligibility": "Eligible",
        "swe6_eligibility": "Eligible",
        "category": "기능",
        "requirement": "SW 오류 시 Reset 복귀하고 복귀 상태는 최초 B+ 상태와 동일해야 한다.",
        "source_evidence": [{"document": "source.docx", "location": "Paragraph 184-185", "text": "..."}],
        "source_backed_atomic_behaviors": [
            {"source_fact_fragment_id": "F1", "behavior_text": "의도하지 않은 SW 오류 발생 시 MCU Reset으로 정상 상태로 복귀해야 한다."},
            {"source_fact_fragment_id": "F2", "behavior_text": "복귀 상태는 최초 B+ 전원 인가 상태와 동일해야 한다."},
        ],
        "fact_level_allocations": [
            {"source_fact_fragment_id": "F1", "swe1_eligibility": "Eligible"},
            {"source_fact_fragment_id": "F2", "swe1_eligibility": "Review Needed"},
        ],
    }
    records = build_swe1_records({"requirements": [req]})
    assert len(records) == 1
    assert "MCU Reset" in records[0]["요구사항 내역"]
    assert "최초 B+" not in records[0]["요구사항 내역"]
    assert "최초 B+" in records[0]["기타"]


def test_situation_check_uses_actual_deferred_sheet_when_review_summary_is_stale():
    reqs = [{
        "srs_id": "SRS_001",
        "requirement": "HU는 신호를 송신해야 한다.",
        "allocation_status": "SYSTEM_REQUIREMENT_PENDING_SW_ALLOCATION",
        "swe1_eligibility": "Review Needed",
        "swe6_eligibility": "Deferred pending SW allocation",
        "positive_sw_allocation_evidence": [],
        "source_evidence": [{"location": "Page 1", "text": "HU는 신호를 송신해야 한다."}],
    }]
    review = {
        "canonical_requirement": {
            "requirements": reqs,
            "semantic_source_unit_coverage": {
                "eligible_unit_count": 1, "covered_unit_count": 1, "open_review_needed_count": 0,
                "terminal_disposition_complete": True, "disposition_counts": {"COVERED_BY_CANONICAL": 1},
                "open_review_needed_records": [],
            },
        },
        "calculated_review_evidence": {
            "testability_and_decomposition_result": {"summary": {"total_generated_tc_count": 0, "deferred_intent_count": 0}},
            "swe6_export_preservation_audit": {"generated_tc_count": 0},
            "conflict_register": [],
        },
    }
    evidence = {
        "requirement_studio_version": "v0.78", "evaluation_mode": "unified", "run_dir": "run",
        "source": {"file": "source.pdf", "sha256": "abc"}, "evidence_package_sha256": "def",
        "actual_artifacts": {"swe6_excel": {"sheets": {"3_Deferred Intent": [
            ["SRS ID", "Intent", "Reason"],
            ["SRS_001", "Normal", "ALLOCATION_PENDING"],
            ["SRS_001", "Exception", "ALLOCATION_PENDING"],
        ]}}},
    }
    report = MultiModelEvaluationOrchestrator._build_situation_check(review, evidence)
    counts = report["observed_counts"]
    assert counts["deferred_intent_count"] == 2
    assert counts["deferred_intent_count_review_summary"] == 0
    assert counts["deferred_intent_count_actual_xlsx"] == 2
