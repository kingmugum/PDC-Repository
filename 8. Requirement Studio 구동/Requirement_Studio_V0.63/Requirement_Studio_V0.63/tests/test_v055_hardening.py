import json
from pathlib import Path

from core.quality_audit import (
    apply_quality_audits,
    build_conflict_register,
    build_testability_result,
    finalize_test_intent_coverage,
)
from core.gold_source_registry import GoldSourceRegistry
from core.regression_engine import build_regression_report


def _compact(blocks):
    return "\n\n".join(blocks)


def test_missing_behavior_gets_explicit_disposition_without_becoming_covered():
    text = _compact([
        "[SRC DOC-C0001 | Paragraph 10 | paragraph]\n[REQ10_01] Input_A 신호로 Slave를 제어할 수 있다.",
        "[SRC DOC-C0002 | Paragraph 30 | paragraph]\n[REQ10_01] Input_A 신호로 Slave를 제어할 수 있다.",
    ])
    out = apply_quality_audits({"requirements": [], "gaps": []}, text)
    cov = out["source_coverage"]
    assert cov["missing_count"] == 2
    assert cov["actual_missing_behavior_count"] == 1
    assert len(out["missing_behavior_dispositions"]) == 1
    assert all(x.get("linked_missing_disposition_ids") for x in cov["source_requirement_occurrences"] if x["occurrence_type"] == "declaration")
    assert out["reference_completeness_result"]["passed"] is True
    assert out["reference_completeness_result"]["actual_missing_behavior_release_blocking"] is True


def test_repeated_equivalence_audit_records_exact_and_high_confidence():
    text = _compact([
        "[SRC DOC-C0001 | Paragraph 10 | paragraph]\n[REQ20_01] Input_FootLpOn == On(0x1) 이면 Foot Lamp를 On 제어한다.",
        "[SRC DOC-C0002 | Paragraph 40 | paragraph]\nREQ20_01  Input_FootLpOn == On(0x1)이면 Foot Lamp를 On 제어한다",
    ])
    data = {"requirements": [{
        "candidate_id": "C1", "srs_id": "S1", "derivation_type": "explicit",
        "requirement": "Input_FootLpOn On 시 Foot Lamp On 제어",
        "source_requirement_ids": ["REQ20_01"],
        "source_evidence": [{"location": "Paragraph 10", "text": "[REQ20_01] Input_FootLpOn == On(0x1) 이면 Foot Lamp를 On 제어한다."}],
    }], "gaps": []}
    out = apply_quality_audits(data, text)
    repair = out["source_coverage"]["traceability_repair"]
    assert repair["repeated_equivalent_link_count"] >= 1
    recs = [x for x in repair["linkage_audit_records"] if x.get("link_type") == "repeated_equivalent"]
    assert recs
    assert recs[0]["matched_anchor_occurrence_id"]
    assert recs[0]["equivalence_class"] in {"exact_normalized_equivalence", "high_confidence_semantic_equivalence"}
    assert recs[0]["match_score"] > 0


def test_same_id_different_fact_tokens_stays_uncertain():
    text = _compact([
        "[SRC DOC-C0001 | Paragraph 10 | paragraph]\n[REQ20_01] Input_A On(0x1)이면 Output_X를 On한다.",
        "[SRC DOC-C0002 | Paragraph 50 | paragraph]\n[REQ20_01] Input_B Off(0x0)이면 Output_Y를 Off한다.",
    ])
    data = {"requirements": [{
        "candidate_id": "C1", "srs_id": "S1", "derivation_type": "explicit",
        "requirement": "Input_A On 시 Output_X On",
        "source_requirement_ids": ["REQ20_01"],
        "source_evidence": [{"location": "Paragraph 10", "text": "[REQ20_01] Input_A On(0x1)이면 Output_X를 On한다."}],
    }], "gaps": []}
    out = apply_quality_audits(data, text)
    rows = {x["source_location"]: x for x in out["source_coverage"]["source_requirement_occurrences"] if x["occurrence_type"] == "declaration"}
    assert rows["Paragraph 10"]["coverage_status"] == "Covered"
    assert rows["Paragraph 50"]["coverage_status"] == "Uncertain"


def test_multiline_table_value_contradiction_is_detected_and_linked():
    text = _compact([
        "[SRC DOC-C0001 | Paragraph 188 | paragraph]\n[REQ03_16] Input_MoodLpDrivemodeNvalue 신호가 On(0x1)일 때 색상 좌표를 송신한다.",
        "[SRC DOC-C0002 | Table 5 / Row 29 | table]\nInput_MoodLPDrivemodeNvalue\n0x1: Off\n0x2: On",
    ])
    data = {"requirements": [{
        "candidate_id": "REQ-CAND-022", "srs_id": "SRS_022",
        "requirement": "Input_MoodLpDrivemodeNvalue On(0x1) 시 색상 좌표 송신",
        "preconditions": "Input_MoodLpDrivemodeNvalue == On(0x1)",
        "source_evidence": [{"location": "Paragraph 188", "text": "[REQ03_16] Input_MoodLpDrivemodeNvalue On(0x1)"}],
        "source_requirement_ids": ["REQ03_16"],
    }], "gaps": [], "source_coverage": {"source_requirement_occurrences": [
        {"occurrence_id": "SRC-OCC-0041", "source_location": "Paragraph 188", "source_req_id": "REQ03_16"},
        {"occurrence_id": "SRC-OCC-0083", "source_location": "Table 5 / Row 29", "source_req_id": "REQ03_16"},
    ]}}
    rows = build_conflict_register(data, text)
    c = next(x for x in rows if x.get("classification") == "Value-Encoding Contradiction")
    assert c["source_a"]["text"] and c["source_b"]["text"]
    assert c["evidence_status"] == "Complete"
    assert c["review_state"] == "Clarification Needed"
    assert "SRS_022" in c["affected_srs_ids"]
    assert "REQ-CAND-022" in c["affected_candidate_ids"]


def test_gold_contract_v12_keeps_bounded_source_evidence(tmp_path):
    root = tmp_path / "Requirement_Studio_V0.55"
    root.mkdir()
    registry = GoldSourceRegistry(root)
    payload = {
        "run": {"source_sha256": "a" * 64, "source_original_name": "gold.docx", "requirement_studio_version": "v0.46"},
        "canonical_requirement": {"requirements": [{
            "candidate_id": "C1", "srs_id": "S1", "requirement": "controller behavior",
            "source_requirement_ids": ["REQ01_01"],
            "source_evidence": [{"document": "gold.docx", "location": "Paragraph 1", "text": "[REQ01_01] controller shall perform behavior"}],
        }]},
    }
    src = tmp_path / "review.json"
    src.write_text(json.dumps(payload), encoding="utf-8")
    contract_path = registry.install_review_package(src)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["contract_schema_version"] == "1.3"
    b = contract["behaviors"][0]
    assert b["compact_excerpt"]
    assert b["compact_excerpt_kind"] == "source_excerpt"
    assert b["excerpt_fingerprint"].startswith("sha256:")
    review = registry.contract_to_review_payload(contract)
    ev = review["canonical_requirement"]["requirements"][0]["source_evidence"][0]
    assert ev["text"]
    assert ev["evidence_text_kind"] == "source_excerpt"


def test_testability_invariant_full_alias_requires_complete_intents():
    data = {"requirements": [{
        "srs_id": "SRS_001", "category": "기능", "requirement": "Invalid 입력이면 기존 값을 유지하고 정상 입력이면 출력한다.",
        "activation_trigger": "Input_A", "output": "Output_A", "acceptance_criteria": "정상/Invalid 동작 확인",
    }], "conflict_register": []}
    result = build_testability_result(data)
    data["testability_and_decomposition_result"] = result
    finalize_test_intent_coverage(data, [{"srs_id": "SRS_001", "tc_id": "TC_001"}])
    row = data["testability_and_decomposition_result"]["by_srs"][0]
    assert row["intent_complete_status"] == "Partial"
    assert row["concrete_tc_complete"] is False
    assert row["full_testability_available"] is False
    assert row["test_design_feasible"] is True


def test_regression_finding_exposes_behavior_vs_linkage_semantics():
    previous = {
        "run": {"requirement_studio_version": "v0.46", "source_sha256": "abc", "provider_id": "hchat_gpt", "model": "gpt"},
        "canonical_requirement": {"requirements": [{
            "candidate_id": "OLD", "srs_id": "OLD-SRS", "requirement": "Lamp control",
            "source_requirement_ids": ["REQ10_01"], "source_evidence": [{"location": "Paragraph 10", "text": "Lamp control"}],
        }]},
        "gold_source_contract": {"baseline_type": "compact_gold_regression_contract", "baseline_origin_version": "v0.46", "is_full_review_package": False, "behavior_scope": "source-backed compact behavior contract"},
    }
    current = {
        "source_coverage": {"coverage_validity": "VALID", "source_requirement_occurrences": []},
        "requirements": [{
            "candidate_id": "CUR", "srs_id": "SRS_001", "requirement": "Lamp control",
            "source_requirement_ids": ["REQ10_01"], "source_evidence": [{"location": "Paragraph 10", "text": "Lamp control"}],
        }],
    }
    report = build_regression_report(current, previous, "gold", current_run={
        "requirement_studio_version": "v0.55", "source_sha256": "abc", "provider_id": "hchat_gpt", "model": "gpt",
    })
    assert report["baseline_type"] == "compact_gold_regression_contract"
    assert report["baseline_is_full_review_package"] is False
    f = report["findings"][0]
    assert f["classification"] == "Traceability linkage regression"
    assert f["current_behavior_present"] is True
    assert f["traceability_linkage_complete"] is False
