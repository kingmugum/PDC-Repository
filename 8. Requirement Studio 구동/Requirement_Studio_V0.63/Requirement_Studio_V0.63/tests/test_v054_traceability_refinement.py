from core.quality_audit import build_source_coverage, build_conflict_register, build_testability_result
from core.regression_engine import build_regression_report
from core.gold_source_registry import GoldSourceRegistry


def _compact(blocks):
    return "\n\n".join(blocks)


def test_grouped_evidence_envelope_and_repeated_occurrence_repair():
    text = _compact([
        "[SRC DOC-C0001 | Paragraph 10 | paragraph]\n[REQ10_01] Foot lamp Off",
        "[SRC DOC-C0002 | Paragraph 11 | paragraph]\n[REQ10_02] Foot lamp On",
        "[SRC DOC-C0003 | Paragraph 12 | paragraph]\n[REQ10_03] Foot lamp Dimout",
        "[SRC DOC-C0004 | Paragraph 30 | paragraph]\n[REQ10_02] Foot lamp On",
    ])
    data = {"requirements": [{
        "candidate_id": "REQ-CAND-001", "srs_id": "SRS_001", "derivation_type": "explicit",
        "requirement": "Foot lamp Off/On/Dimout 제어",
        "source_requirement_ids": ["REQ10_01", "REQ10_03"],
        "source_evidence": [
            {"location": "Paragraph 10", "text": "[REQ10_01] Foot lamp Off"},
            {"location": "Paragraph 12", "text": "[REQ10_03] Foot lamp Dimout"},
        ],
    }], "gaps": []}
    cov = build_source_coverage(data, text)
    req = data["requirements"][0]
    assert "REQ10_02" in req["source_requirement_ids"]
    assert len(req["source_requirement_occurrence_ids"]) == 4
    assert cov["traceability_repair"]["grouped_range_link_count"] >= 1
    assert cov["traceability_repair"]["repeated_equivalent_link_count"] >= 1
    assert cov["missing_count"] == 0


def test_reused_id_different_behavior_not_force_linked():
    text = _compact([
        "[SRC DOC-C0001 | Paragraph 10 | paragraph]\n[REQ20_01] Lamp shall turn On",
        "[SRC DOC-C0002 | Paragraph 50 | paragraph]\n[REQ20_01] Profile shall use fallback priority",
    ])
    data = {"requirements": [{
        "candidate_id": "REQ-CAND-001", "srs_id": "SRS_001", "derivation_type": "explicit",
        "requirement": "Lamp shall turn On", "source_requirement_ids": ["REQ20_01"],
        "source_evidence": [{"location": "Paragraph 10", "text": "[REQ20_01] Lamp shall turn On"}],
    }], "gaps": []}
    cov = build_source_coverage(data, text)
    rows = {x["source_location"]: x for x in cov["source_requirement_occurrences"] if x["occurrence_type"] == "declaration"}
    assert rows["Paragraph 10"]["coverage_status"] == "Covered"
    assert rows["Paragraph 50"]["coverage_status"] == "Uncertain"


def test_signal_table_colon_format_conflict_detected():
    text = _compact([
        "[SRC DOC-C0001 | Paragraph 188 | paragraph]\nInput_Mode On(0x1)일 때 색상 좌표를 송신한다.",
        "[SRC DOC-C0002 | Table 5 / Row 29 | table]\nInput_Mode | 0x1: Off | 0x2: On",
    ])
    data = {"requirements": [{
        "candidate_id": "REQ-CAND-001", "srs_id": "SRS_001", "requirement": "Input_Mode On(0x1) 동작",
        "source_evidence": [{"location": "Paragraph 188", "text": "Input_Mode On(0x1)"}],
        "source_requirement_ids": [],
    }], "gaps": [], "source_coverage": {"source_requirement_occurrences": []}}
    rows = build_conflict_register(data, text)
    assert any(r.get("classification") == "Value-Encoding Contradiction" and r.get("evidence_status") == "Complete" for r in rows)


def test_testability_allows_normal_test_with_dependency():
    data = {"requirements": [{
        "srs_id": "SRS_001", "category": "기능", "requirement": "ACC On이면 밝기를 송신한다.",
        "activation_trigger": "ACC On", "output": "Brightness output", "acceptance_criteria": "출력이 송신된다.",
        "external_dependencies": [{"name": "CAN DB"}], "clarification_needed": "주기값은 CAN DB 참조",
    }], "conflict_register": []}
    result = build_testability_result(data)
    row = result["by_srs"][0]
    assert row["testability_status"] == "Partially Testable"
    assert row["normal_test_available"] is True
    assert row["full_testability_available"] is False


def test_regression_semantic_anchor_is_traceability_not_absent():
    previous = {
        "run": {"requirement_studio_version": "v0.46", "source_sha256": "abc", "provider_id": "hchat_gpt", "model": "gpt"},
        "canonical_requirement": {"requirements": [{
            "candidate_id": "OLD", "srs_id": "OLD-SRS", "requirement": "Foot lamp Off On Dimout 제어",
            "source_requirement_ids": ["REQ10_01", "REQ10_02", "REQ10_03"],
            "source_evidence": [{"location": "Paragraph 10-12", "text": "Foot lamp Off On Dimout 제어"}],
        }]},
    }
    current = {
        "source_coverage": {"coverage_validity": "VALID", "source_requirement_occurrences": [{
            "occurrence_type": "declaration", "occurrence_id": "SRC-1", "source_req_id": "REQ10_02",
            "source_location": "Paragraph 11", "source_excerpt": "Foot lamp On", "coverage_status": "Missing",
            "linked_candidate_ids": [], "linked_srs_ids": [], "disposition_reason": "No link",
        }]},
        "requirements": [{
            "candidate_id": "CUR", "srs_id": "SRS_001", "requirement": "Foot lamp Off On Dimout 제어",
            "source_requirement_ids": ["REQ10_01", "REQ10_03"],
            "source_evidence": [{"location": "Paragraph 10-12", "text": "Foot lamp Off On Dimout 제어"}],
        }],
    }
    report = build_regression_report(current, previous, "baseline", current_run={
        "requirement_studio_version": "v0.55", "source_sha256": "abc", "provider_id": "hchat_gpt", "model": "gpt",
    })
    assert report["findings"]
    assert report["findings"][0]["classification"] == "Traceability linkage regression"


def test_gold_contract_v11_metadata(tmp_path):
    root = tmp_path / "Requirement_Studio_V0.55"
    root.mkdir()
    registry = GoldSourceRegistry(root)
    payload = {
        "run": {"source_sha256": "a" * 64, "source_original_name": "gold.docx", "requirement_studio_version": "v0.46"},
        "canonical_requirement": {"requirements": [{
            "candidate_id": "C1", "srs_id": "S1", "requirement": "behavior",
            "source_requirement_ids": ["REQ01_01"], "source_evidence": [{"location": "Paragraph 1", "text": "[REQ01_01] behavior"}],
        }]},
    }
    import json
    src = tmp_path / "review.json"
    src.write_text(json.dumps(payload), encoding="utf-8")
    target = registry.install_review_package(src)
    contract = json.loads(target.read_text(encoding="utf-8"))
    assert contract["contract_schema_version"] == "1.3"
    assert contract["baseline_type"] == "compact_gold_regression_contract"
    assert contract["baseline_origin_version"] == "v0.46"
    assert contract["is_full_review_package"] is False
    assert contract["behaviors"][0]["evidence_fingerprints"]


def test_finalize_preserves_source_level_normal_testability():
    from core.quality_audit import finalize_test_intent_coverage
    data = {"testability_and_decomposition_result": {
        "summary": {},
        "by_srs": [{
            "srs_id": "SRS_001", "normal_test_available": True,
            "required_test_intents": ["Normal / Positive", "Timing"],
            "testability_status": "Partially Testable",
        }],
    }}
    finalize_test_intent_coverage(data, [])
    row = data["testability_and_decomposition_result"]["by_srs"][0]
    assert row["normal_test_available"] is True
    assert row["normal_test_generated"] is False
