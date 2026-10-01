from pathlib import Path

from core.cross_document_semantics import build_semantic_source_units
from core.quality_audit import apply_quality_audits, build_reference_completeness, normalize_requirement_extensions
from core.swe6_exporter import build_swe6_cases


def _req(cid, srs, loc, source_text, requirement=None):
    requirement = requirement or source_text
    req = {
        "candidate_id": cid, "srs_id": srs, "scenario_candidate_id": "SCN-CAND-001",
        "category": "기능", "function_name": "Cross Document", "requirement": requirement,
        "user_input": "", "system_input_preconditions": "", "processing_action": requirement,
        "output": "", "acceptance_criteria": requirement, "failure_situations": [], "user_intervention_points": [],
        "derivation_type": "explicit", "derivation_reason": "", "clarification_needed": [],
        "source_evidence": [{"document": "system.docx", "location": loc, "text": source_text}],
        "confidence": 0.95, "classification_basis": "입력문서 명시", "activation_trigger": "",
        "preconditions": "", "behavior_flows": [], "evaluation_method": "", "exception_conditions": [],
        "related_artifacts": [],
    }
    normalize_requirement_extensions(req)
    return req


def _data(reqs, gaps=None):
    return {
        "schema_version": "REQ-STUDIO-CANONICAL-REQ-1.9",
        "source_document": "system.docx",
        "scenario_candidates": [{
            "scenario_candidate_id": "SCN-CAND-001", "scenario_name": "x", "user_goal_context": "",
            "scenario_flow": [], "expected_outcome": "",
            "source_evidence": [{"document": "system.docx", "location": "Paragraph 1", "text": "x"}],
        }],
        "requirements": reqs,
        "gaps": gaps or [],
    }


def test_classifier_excludes_history_external_reference_and_heading_from_denominator():
    compact = """[DOCUMENT] system.docx
[SRC DOC-C0001 | Table 1 / Row 2 | table]
2019.09.20 | 7차 | 차종사양서 발행
[SRC DOC-C0002 | Table 2 / Row 2 | table]
MS201-02 | 유해물질 금지 및 신고 - 부품 및 재료
[SRC DOC-C0003 | Paragraph 30 | text]
커넥터 사양
[SRC DOC-C0004 | Paragraph 40 | text]
차량 On/Off 정보를 받아 Slave LED의 On/Off, 밝기, 색상을 제어한다.
"""
    units = build_semantic_source_units(compact)
    by_loc = {u["source_location"]: u for u in units}
    assert by_loc["Table 1 / Row 2"]["coverage_eligibility"] == "review_context"
    assert by_loc["Table 1 / Row 2"]["source_unit_type"] == "revision_history_context"
    assert by_loc["Table 2 / Row 2"]["coverage_eligibility"] == "review_context"
    assert by_loc["Table 2 / Row 2"]["source_unit_type"] == "external_reference_only"
    assert by_loc["Paragraph 30"]["coverage_eligibility"] == "review_context"
    assert by_loc["Paragraph 40"]["coverage_eligibility"] == "semantic_unit"


def test_no_id_eligible_descriptive_source_gets_exact_source_backed_atom():
    src = "무드램프 밝기는 USM 설정으로만 가능하며 Rheostat level의 실내 조명 밝기와 연동되지 않는다."
    compact = f"""[DOCUMENT] system.docx
[SRC DOC-C0100 | Paragraph 100 | text]
{src}
"""
    req = _req("C1", "SRS_001", "Paragraph 100", src, "무드램프 밝기는 USM 설정만 사용하며 Rheostat level과 연동하지 않는다.")
    data = _data([req])
    apply_quality_audits(data, compact)
    assert req["swe1_eligibility"] == "Eligible"
    assert req["source_semantic_unit_ids"]
    assert req["source_backed_atomic_behaviors"]
    assert req["semantic_provenance_status"] == "COMPLETE"
    assert data["semantic_provenance_audit"]["blocking_incomplete_count"] == 0
    assert src in req["source_backed_atomic_behaviors"][0]["behavior_text"]


def test_context_linked_gap_is_reference_complete():
    data = {
        "gaps": [{
            "gap_id": "GAP_001", "gap_scope": "section",
            "related_candidate_ids": [], "related_srs_ids": [],
            "section_context_link": {"scope": "section", "reason": "No deterministic SRS anchor."},
        }],
        "conflict_register": [], "review_findings": [], "missing_behavior_dispositions": [],
        "source_coverage": {"explicit_source_requirement_occurrence_count": 0, "source_requirement_occurrences": []},
    }
    result = build_reference_completeness(data)
    assert result["passed"] is True
    assert result["unlinked_gap_count"] == 0
    assert result["context_linked_gap_count"] == 1
    assert result["context_linked_gap_ids"] == ["GAP_001"]


def test_swe6_tc_is_deferred_until_no_id_semantic_provenance_complete():
    req = _req("C1", "SRS_001", "Paragraph 1", "소프트웨어는 값을 저장해야 한다.")
    req.update({
        "requirement_level": "Software", "allocation_status": "SW_IMPLEMENTATION_REQUIREMENT",
        "swe1_eligibility": "Eligible", "swe6_eligibility": "Eligible",
        "verification_domain": "SWE.6 Software Qualification",
        "source_requirement_ids": [], "source_semantic_unit_ids": ["SRC-SEM-X"],
        "source_backed_atomic_behaviors": [], "semantic_provenance_status": "INCOMPLETE_REVIEW_REQUIRED",
    })
    assert build_swe6_cases(_data([req])) == []
    req["source_backed_atomic_behaviors"] = [{"source_semantic_unit_id": "SRC-SEM-X", "behavior_text": "소프트웨어는 값을 저장해야 한다.", "knowledge_state": "KNOWN"}]
    req["semantic_provenance_status"] = "COMPLETE"
    assert len(build_swe6_cases(_data([req]))) == 1


def test_clause_level_comparator_preserves_explicit_relations_and_only_flags_ambiguous_value():
    explicit_src = "정상 동작 전압 DC 7V ~ 18V, DC 6.5V 이하 통신 disable, DC 18.5V 이상 통신 disable"
    ambiguous_src = "암전류 규제 : 0.1mA"
    compact = f"""[DOCUMENT] system.docx
[SRC DOC-C0200 | Table 10 / Row 2 | table]
{explicit_src}
[SRC DOC-C0201 | Table 10 / Row 3 | table]
{ambiguous_src}
"""
    r1 = _req("C1", "SRS_001", "Table 10 / Row 2", explicit_src, explicit_src)
    r2 = _req("C2", "SRS_002", "Table 10 / Row 3", ambiguous_src, "암전류는 0.1mA를 만족해야 한다.")
    data = _data([r1, r2])
    apply_quality_audits(data, compact)
    relations = {x["relation"] for x in r1["value_relation_status"]}
    assert "RANGE_EXPLICIT" in relations
    assert "LESS_THAN_OR_EQUAL_EXPLICIT" in relations
    assert "GREATER_THAN_OR_EQUAL_EXPLICIT" in relations
    assert all(x["relation_confirmed"] for x in r1["value_relation_status"])
    assert r1["normative_strength_status"] == "SOURCE_RELATION_EXPLICIT_OR_NOT_NUMERIC"

    assert any(x["relation"] == "UNSPECIFIED_LIMIT_OR_TARGET" and not x["relation_confirmed"] for x in r2["value_relation_status"])
    assert r2["normative_strength_status"] == "SOURCE_RELATION_AMBIGUOUS_GENERATED_STRENGTHENING_REMOVED"
    assert "Source 표기 보존" in r2["requirement"]
    assert "확인" in r2["acceptance_criteria"]


def test_broad_section_gap_without_deterministic_anchor_becomes_context_link():
    compact = """[DOCUMENT] system.docx
[SRC DOC-C0001 | Table 9 / Row 2 | table]
OFF / ACC / ON / Start / RUN / IGN3 상태별 일부 조건 TBD
[SRC DOC-C0002 | Table 10 / Row 2 | table]
최대 소비 전류 | MAX 100mA
[SRC DOC-C0003 | Table 12 / Row 2 | table]
사용 온도 범위 | -40℃ ~ +85℃
"""
    reqs = [
        _req("C1", "SRS_001", "Table 10 / Row 2", "최대 소비 전류 | MAX 100mA"),
        _req("C2", "SRS_002", "Table 12 / Row 2", "사용 온도 범위 | -40℃ ~ +85℃"),
    ]
    # add enough unrelated requirements to make the initial linkage broad
    for i in range(3, 11):
        reqs.append(_req(f"C{i}", f"SRS_{i:03d}", f"Paragraph {100+i}", f"독립 기능 {i}를 수행한다."))
    gap = {
        "gap_id": "G1", "description": "OFF / ACC / ON / Start / RUN / IGN3 상태별 TBD 조건 확인 필요", "gap_scope": "section",
        "related_candidate_ids": [r["candidate_id"] for r in reqs], "related_srs_ids": [r["srs_id"] for r in reqs],
        "source_evidence": [{"document": "system.docx", "location": "Table 9 / Row 2", "text": "OFF / ACC / ON / Start / RUN / IGN3 상태별 일부 조건 TBD"}],
    }
    data = _data(reqs, [gap])
    apply_quality_audits(data, compact)
    g = data["gaps"][0]
    assert not g.get("related_candidate_ids")
    assert not g.get("related_srs_ids")
    assert g.get("section_context_link")
    assert data["reference_completeness_result"]["passed"] is True


def test_sparse_section_gap_links_are_still_revalidated_not_trusted_by_count():
    compact = """[DOCUMENT] system.docx
[SRC DOC-C0001 | Table 9 / Row 2 | table]
OFF / ACC / ON / Start / RUN / IGN3 상태별 일부 조건 TBD
[SRC DOC-C0002 | Table 10 / Row 2 | table]
최대 소비 전류 | MAX 100mA
[SRC DOC-C0003 | Table 12 / Row 2 | table]
사용 온도 범위 | -40℃ ~ +85℃
[SRC DOC-C0004 | Table 12 / Row 3 | table]
보존 온도 범위 | -40℃ ~ +95℃
"""
    reqs = [
        _req("C1", "SRS_001", "Table 10 / Row 2", "최대 소비 전류 | MAX 100mA"),
        _req("C2", "SRS_002", "Table 12 / Row 2", "사용 온도 범위 | -40℃ ~ +85℃"),
        _req("C3", "SRS_003", "Table 12 / Row 3", "보존 온도 범위 | -40℃ ~ +95℃"),
    ]
    gap = {
        "gap_id": "G1", "description": "OFF / ACC / ON / Start / RUN / IGN3 상태별 TBD 조건 확인 필요", "gap_scope": "section",
        "related_candidate_ids": ["C1", "C2", "C3"], "related_srs_ids": ["SRS_001", "SRS_002", "SRS_003"],
        "source_evidence": [{"document": "system.docx", "location": "Table 9 / Row 2", "text": "OFF / ACC / ON / Start / RUN / IGN3 상태별 일부 조건 TBD"}],
    }
    data = _data(reqs, [gap])
    apply_quality_audits(data, compact)
    g = data["gaps"][0]
    assert g.get("related_candidate_ids") == []
    assert g.get("related_srs_ids") == []
    assert g.get("section_context_link")
