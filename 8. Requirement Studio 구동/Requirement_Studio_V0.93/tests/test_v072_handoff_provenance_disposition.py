import json
from pathlib import Path

from core.cross_document_semantics import attach_semantic_traceability
from core.evaluation_orchestrator import MultiModelEvaluationOrchestrator
from core.quality_audit import build_swe6_export_preservation_audit, build_testability_result, finalize_test_intent_coverage


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


def _audit(req):
    data = {"requirements": [req], "gaps": []}
    data["testability_and_decomposition_result"] = build_testability_result(data)
    finalize_test_intent_coverage(data, [])
    return data["swe6_export_preservation_audit"]


def test_v072_structured_fact_tokens_use_one_value_stream_without_false_gap():
    req = _base_req("Warn_ExtBuzzerOut=0x1 조건이 5초 유지되면 상태를 전환한다.")
    req["source_fact_fragments"] = [{
        "source_fact_fragment_id": "SRC-FRAG-1", "source_excerpt_raw": "Warn_ExtBuzzerOut=0x1 조건이 5초 유지되면 상태를 전환한다.",
        "source_excerpt": "Warn_ExtBuzzerOut=0x1 조건이 5초 유지되면 상태를 전환한다.",
    }]
    req["source_backed_atomic_behaviors"] = [{
        "source_semantic_unit_id": "SRC-SEM-1", "source_fact_fragment_id": "SRC-FRAG-1",
        "behavior_text": "Warn_ExtBuzzerOut=0x1 조건이 5초 유지되면 상태를 전환한다.", "knowledge_state": "KNOWN",
    }]
    req["fact_level_allocations"] = [{
        "source_fact_fragment_id": "SRC-FRAG-1", "source_fact": "Warn_ExtBuzzerOut=0x1 조건이 5초 유지되면 상태를 전환한다.",
        "swe6_eligibility": "Deferred pending SW allocation", "verification_domain": "System Integration / SYS.5",
        "structured_source_facts": [{
            "source_literal": "Warn_ExtBuzzerOut=0x1 / 5초", "identifiers": ["Warn_ExtBuzzerOut"],
            "numeric_values": ["0x1"], "timing_values": ["5초"], "range_values": [], "explicit_relations": [], "enum_mappings": [],
        }],
    }]
    audit = _audit(req)
    row = audit["rows"][0]
    assert row["missing_source_fact_tokens"] == []
    assert row["source_fact_linkage_ok"] is True
    assert row["critical_fact_fragment_missing_tokens"] == []


def test_v072_critical_fact_must_be_owned_by_exact_fragment_not_only_structured_rollup():
    req = _base_req("Signal_Mode=0x2 상태가 15초 유지되면 1회 재시도한다.")
    req["source_fact_fragments"] = [{
        "source_fact_fragment_id": "SRC-FRAG-1", "source_excerpt_raw": "Signal_Mode=0x2 상태를 확인한다.",
        "source_excerpt": "Signal_Mode=0x2 상태를 확인한다.",
    }]
    req["source_backed_atomic_behaviors"] = [{
        "source_semantic_unit_id": "SRC-SEM-1", "source_fact_fragment_id": "SRC-FRAG-1",
        "behavior_text": "Signal_Mode=0x2 상태를 확인한다.", "knowledge_state": "KNOWN",
    }]
    # Structured rollup knows the timing/retry facts, so provenance completeness passes; fragment ownership must still fail.
    req["fact_level_allocations"] = [{
        "source_fact_fragment_id": "SRC-FRAG-1", "source_fact": "Signal_Mode=0x2 상태를 확인한다.",
        "swe6_eligibility": "Deferred pending SW allocation", "verification_domain": "System Integration / SYS.5",
        "structured_source_facts": [{
            "source_literal": "Signal_Mode=0x2 / 15초 / 1회", "identifiers": ["Signal_Mode"], "numeric_values": ["0x2"],
            "timing_values": ["15초"], "range_values": [], "explicit_relations": [], "enum_mappings": [{"value":"1회", "meaning":"retry"}],
        }],
    }]
    audit = _audit(req)
    row = audit["rows"][0]
    assert row["source_fact_linkage_ok"] is True
    assert "15초" in row["critical_fact_fragment_missing_tokens"]
    assert any(x.get("issue") == "CANONICAL_CRITICAL_FACT_FRAGMENT_OWNERSHIP_GAP" for x in audit["tool_quality_issue_records"])


def test_v072_unlinked_semantic_unit_is_open_not_silently_terminal():
    compact = """[DOCUMENT] source.pdf\n[SRC DOC-C0001 | Page 5 | text]\nHU는 Camera_Status를 수신하여 촬영 상태를 판단해야 한다.\n"""
    data = {"requirements": [], "gaps": []}
    attach_semantic_traceability(data, compact)
    sem = data["semantic_source_unit_coverage"]
    assert sem["eligible_unit_count"] == 1
    assert sem["open_review_needed_count"] == 1
    assert sem["terminal_disposition_complete"] is False
    rec = sem["open_review_needed_records"][0]
    assert rec["review_state"] == "OPEN"
    assert rec["review_owner"] == "UNASSIGNED"
    assert rec["required_resolution"]


def test_v072_final_result_is_self_identifying_and_every_part_repeats_identity(tmp_path):
    provider_results = {
        "gpt": {"findings": [], "next_version_recommendations": [], "verdict": "PASS", "tool_quality_gate": "PASS", "artifact_readiness_gate": "PASS", "official_release": "PASS"},
        "gemini": {"findings": [], "next_version_recommendations": [], "verdict": "PASS", "tool_quality_gate": "PASS", "artifact_readiness_gate": "PASS", "official_release": "PASS"},
        "claude": {"findings": [], "next_version_recommendations": [], "verdict": "PASS", "tool_quality_gate": "PASS", "artifact_readiness_gate": "PASS", "official_release": "PASS"},
    }
    consensus = {"evaluation_completeness":"COMPLETE", "tool_quality_gate":"PASS", "artifact_readiness_gate":"PASS", "official_release":"PASS", "consensus_findings":[]}
    evidence = {
        "requirement_studio_version":"v0.72", "evaluation_mode":"unified", "run_dir":"RUN-123",
        "source":{"file":"new_gold.pdf", "sha256":"abc123"},
        "actual_artifacts":{"swe1_word":{"artifact":"swe1.docx"}, "swe1_excel":{"artifact":"swe1.xlsx"}, "swe6_excel":{"artifact":"swe6.xlsx"}},
        "evidence_package_sha256":"evidencehash",
    }
    final = MultiModelEvaluationOrchestrator._final_result(provider_results, consensus, {}, Path("06_EVALUATION_EVIDENCE.json"), evidence)
    rendered = MultiModelEvaluationOrchestrator._render_final_txt(final)
    assert "Requirement Studio Version: v0.72" in rendered
    assert "Source File: new_gold.pdf" in rendered
    assert "Evaluation Mode: unified" in rendered
    payload = "\n".join(rendered.splitlines() + [f"extra {i}" for i in range(250)])
    parts = MultiModelEvaluationOrchestrator.split_final_result(payload, tmp_path, lines_per_file=110, handoff_identity=final["handoff_identity"])
    assert len(parts) >= 3
    for idx, path in enumerate(parts, 1):
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 110
        assert "Version: v0.72" in lines[:10]
        assert "Source: new_gold.pdf" in lines[:10]
        assert any(line.startswith("Part: ") for line in lines[:10])
