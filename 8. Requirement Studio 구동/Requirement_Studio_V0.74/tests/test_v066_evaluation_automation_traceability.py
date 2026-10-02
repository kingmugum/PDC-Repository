import json
from pathlib import Path

from openpyxl import load_workbook

from core.cross_document_semantics import _augment_atomic_behaviors_from_fragments
from core.evaluation_orchestrator import MultiModelEvaluationOrchestrator
from core.quality_audit import _source_backed_child_intents, build_swe6_export_preservation_audit, normalize_requirement_extensions
from core.review_exchange import ReviewExchangeBuilder
from core.swe6_exporter import SWE6Exporter, build_swe6_cases


def _req(text: str, *, srs: str = "SRS_001") -> dict:
    row = {
        "candidate_id": f"C-{srs}",
        "srs_id": srs,
        "category": "기능",
        "function_name": "Feature",
        "requirement": text,
        "activation_trigger": "",
        "preconditions": "",
        "processing_action": text,
        "output": text,
        "acceptance_criteria": text,
        "source_evidence": [{"document": "x.docx", "location": "Paragraph 1", "text": text}],
        "source_requirement_ids": [],
        "confidence": 0.95,
    }
    normalize_requirement_extensions(row)
    return row


def _evaluation(provider: str, finding_key: str = "TRACE_CHILD_FRAGMENT_MISSING") -> dict:
    return {
        "schema_version": "1.0",
        "provider": provider,
        "model": f"{provider}-model",
        "verdict": "PASS_WITH_REVIEW_ITEMS",
        "tool_quality_gate": "PASS_WITH_REVIEW_ITEMS",
        "artifact_readiness_gate": "REVIEW_REQUIRED",
        "official_release": "HOLD",
        "executive_summary": ["review"],
        "positive_checks": ["blank results"],
        "findings": [{
            "finding_key": finding_key,
            "severity": "RELEASE_REVIEW",
            "gate_scope": "TOOL_QUALITY",
            "category": "TRACEABILITY",
            "title": "Child intent fragment link",
            "affected_ids": ["SRS_015-ATOM-01"],
            "source_references": ["Paragraph 186"],
            "evidence": ["fragment link review"],
            "problem": "fragment link is incomplete",
            "recommendation": "preserve fragment id",
            "confidence": "HIGH",
        }],
        "release_gates": [{"gate": "Trace", "result": "REVIEW", "evidence": "fragment"}],
        "next_version_recommendations": [{"priority": "P0", "title": "Trace", "detail": "preserve link"}],
        "limitations": [],
    }


def test_existing_watchdog_atom_inherits_fragment_id_and_child_intent_keeps_it():
    req = _req("Watchdog Timer는 인터럽트 서비스 루틴내에 있을 수 없다.", srs="SRS_015")
    req["source_fact_fragments"] = [{
        "source_fact_fragment_id": "SRC-FRAG-WDG",
        "parent_source_semantic_unit_id": "SRC-SEM-WDG",
        "source_chunk_id": "DOC-C0186",
        "source_location": "Paragraph 186",
        "source_excerpt": "Watchdog Timer는 인터럽트 서비스 루틴내에 있을 수 없다.",
        "source_excerpt_raw": "Watchdog Timer는 인터럽트 서비스 루틴내에 있을 수 없다. )",
    }]
    req["source_backed_atomic_behaviors"] = [{
        "source_semantic_unit_id": "SRC-SEM-WDG",
        "source_location": "Paragraph 186",
        "behavior_text": "Watchdog Timer는 인터럽트 서비스 루틴내에 있을 수 없다.",
        "knowledge_state": "KNOWN",
    }]

    _augment_atomic_behaviors_from_fragments(req)
    atom = req["source_backed_atomic_behaviors"][0]
    assert atom["source_fact_fragment_id"] == "SRC-FRAG-WDG"
    assert atom["fragment_link_backfilled"] is True
    children = _source_backed_child_intents(req)
    assert children[0]["source_fact_fragment_id"] == "SRC-FRAG-WDG"


def test_mixed_domain_swe6_case_is_scoped_only_to_eligible_source_fact():
    req = _req("SW 오류 시 복구하며 최종 상태는 최초 B+ 인가 상태와 동일해야 한다.", srs="SRS_007")
    req.update({
        "allocation_status": "SW_IMPLEMENTATION_REQUIREMENT",
        "swe6_eligibility": "Eligible",
        "verification_domain": "SWE.6 Software Qualification",
        "semantic_provenance_status": "COMPLETE",
        "source_semantic_unit_ids": ["SRC-SEM-184", "SRC-SEM-185"],
        "source_backed_atomic_behaviors": [
            {"source_semantic_unit_id": "SRC-SEM-184", "source_fact_fragment_id": "F-SW", "behavior_text": "의도하지 않은 SW 오류 발생 시 MCU Reset 등을 통해 정상 상태로 복귀한다.", "knowledge_state": "KNOWN"},
            {"source_semantic_unit_id": "SRC-SEM-185", "source_fact_fragment_id": "F-SYS", "behavior_text": "강제 Reset 복귀 상태는 최초 B+ 전원 인가 상태와 동일하다.", "knowledge_state": "KNOWN"},
        ],
        "fact_level_allocations": [
            {"source_fact_fragment_id": "F-SW", "source_fact": "의도하지 않은 SW 오류 발생 시 MCU Reset 등을 통해 정상 상태로 복귀한다.", "swe6_eligibility": "Eligible", "verification_domain": "SWE.6 Software Qualification"},
            {"source_fact_fragment_id": "F-SYS", "source_fact": "강제 Reset 복귀 상태는 최초 B+ 전원 인가 상태와 동일하다.", "swe6_eligibility": "Deferred pending SW allocation", "verification_domain": "System Integration / SYS.5"},
        ],
    })
    cases = build_swe6_cases({"requirements": [req]})
    assert len(cases) == 1
    case = cases[0]
    assert case["mixed_fact_scope_limited"] is True
    assert case["swe6_scope_fragment_ids"] == ["F-SW"]
    assert "SW 오류" in case["exec_desc"]
    assert "최초 B+ 전원 인가 상태와 동일" not in case["expected_desc"]
    assert case["excluded_non_swe6_source_facts"]


def test_missing_child_fragment_link_is_tool_quality_finding():
    req = _req("Watchdog Timer는 ISR 내부에 있을 수 없다.", srs="SRS_015")
    req.update({
        "allocation_status": "SW_IMPLEMENTATION_REQUIREMENT",
        "swe6_eligibility": "Eligible",
        "verification_domain": "SWE.6 Software Qualification",
        "semantic_provenance_status": "COMPLETE",
        "source_semantic_unit_ids": ["SEM1"],
        "source_fact_fragments": [{"source_fact_fragment_id": "FRAG1", "source_excerpt": "Watchdog Timer는 ISR 내부에 있을 수 없다."}],
        "source_backed_atomic_behaviors": [{"source_semantic_unit_id": "SEM1", "source_fact_fragment_id": "", "behavior_text": "Watchdog Timer는 ISR 내부에 있을 수 없다."}],
    })
    child = _source_backed_child_intents(req)
    data = {
        "requirements": [req],
        "testability_and_decomposition_result": {"by_srs": [{
            "srs_id": "SRS_015", "swe6_eligibility": "Eligible", "verification_domain": "SWE.6 Software Qualification",
            "required_test_intents": ["Normal / Positive"], "not_generated_test_intents": [], "source_backed_child_intents": child,
        }]},
    }
    case = {
        "srs_id": "SRS_015", "tc_id": "TC_001", "description": "intent", "prep_desc": "", "prep_var": "", "prep_compare": "", "prep_value": "",
        "exec_desc": "Watchdog Timer는 ISR 내부에 있을 수 없다.", "exec_var": "", "exec_compare": "", "exec_value": "",
        "expected_desc": "Watchdog Timer는 ISR 내부에 있을 수 없다.", "expected_var": "", "expected_compare": "", "expected_value": "",
    }
    audit = build_swe6_export_preservation_audit(data, [case])
    assert audit["tool_quality_gate_passed"] is False
    assert any(x.get("issue") == "CHILD_INTENT_SOURCE_FACT_FRAGMENT_LINK_MISSING" for x in audit["release_review_issue_records"])


def test_capture_column_is_explicit_required_schema_field_and_blank_checked(tmp_path):
    req = _req("S/W는 Input_A를 수신하면 Output_B를 송신한다.")
    req.update({
        "allocation_status": "SW_IMPLEMENTATION_REQUIREMENT", "swe6_eligibility": "Eligible", "verification_domain": "SWE.6 Software Qualification",
        "semantic_provenance_status": "COMPLETE", "source_semantic_unit_ids": ["SEM1"],
        "source_backed_atomic_behaviors": [{"source_semantic_unit_id": "SEM1", "source_fact_fragment_id": "FRAG1", "behavior_text": "S/W는 Input_A를 수신하면 Output_B를 송신한다."}],
        "fact_level_allocations": [],
    })
    data = {"schema_version": "REQ-STUDIO-CANONICAL-REQ-2.0", "source_document": "x.docx", "requirements": [req], "gaps": []}
    out = SWE6Exporter(tmp_path).export_excel(tmp_path / "x.docx", data, source_text="S/W는 Input_A를 수신하면 Output_B를 송신한다.")
    cases = build_swe6_cases(data)
    check = ReviewExchangeBuilder._verify_swe6_excel_artifact(out, cases)
    assert check["execution_result_field_contract"]["capture_field_required_in_schema"] is True
    assert check["execution_result_field_contract"]["capture_header_present"] is True
    assert "U" in check["execution_result_field_contract"]["blank_validation_applied_to_columns"]
    assert check["prepopulated_result_cells"] == []
    assert check["passed"] is True


def test_consensus_requires_all_three_reviewers_for_release_pass():
    one = _evaluation("gpt")
    one["tool_quality_gate"] = "PASS"
    one["artifact_readiness_gate"] = "PASS"
    one["official_release"] = "PASS"
    consensus = MultiModelEvaluationOrchestrator._consensus({"gpt": one})
    assert consensus["reviewer_count"] == 1
    assert consensus["official_release"] == "HOLD"
    assert consensus["evaluation_completeness"] == "PARTIAL"


def test_three_reviewer_consensus_and_150_line_final_result_split(tmp_path):
    results = {name: _evaluation(name) for name in ("gpt", "gemini", "claude")}
    consensus = MultiModelEvaluationOrchestrator._consensus(results)
    assert consensus["evaluation_completeness"] == "COMPLETE"
    assert consensus["consensus_findings"][0]["strength"] == "STRONG_CONSENSUS"

    text = "\n".join(f"line-{i:03d}" for i in range(1, 321)) + "\n"
    paths = MultiModelEvaluationOrchestrator.split_final_result(text, tmp_path / "final_result", lines_per_file=150)
    assert [len(p.read_text(encoding="utf-8").splitlines()) for p in paths] == [150, 150, 20]
    manifest = json.loads((tmp_path / "final_result" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["line_limit_per_file"] == 150
    assert manifest["part_count"] == 3


def test_orchestrator_writes_five_result_groups_and_final_result_folder_without_network(tmp_path, monkeypatch):
    run_dir = tmp_path / "review_exchange" / "run1"
    run_dir.mkdir(parents=True)
    (run_dir / "01_SOURCE_x.txt").write_text("S/W는 Input_A를 수신하면 Output_B를 송신한다.", encoding="utf-8")
    (run_dir / "02_REQUIREMENT_STUDIO_REVIEW_PACKAGE.json").write_text(json.dumps({"run": {"requirement_studio_version": "v0.66"}}, ensure_ascii=False), encoding="utf-8")
    (run_dir / "04_CHANGE_DECISION_V0.65_to_V0.66.txt").write_text("change", encoding="utf-8")
    (run_dir / "05_REQUIREMENT_STUDIO_REVIEW_SUMMARY.txt").write_text("summary", encoding="utf-8")

    orch = MultiModelEvaluationOrchestrator(tmp_path, app_version="v0.66", provider_config={"hchat": {}})
    orch.config["providers"] = {name: {"enabled": True} for name in ("gpt", "gemini", "claude")}
    monkeypatch.setattr(orch, "_call_one", lambda name, evidence: (_evaluation(name), f"{name}-model"))
    result = orch.run(run_dir)
    out = Path(result["output_dir"])
    for name in ("01_GPT_EVALUATION", "02_GEMINI_EVALUATION", "03_CLAUDE_EVALUATION"):
        assert (out / f"{name}.txt").is_file()
        assert (out / f"{name}.json").is_file()
    assert (out / "04_EVALUATION_CONSENSUS.txt").is_file()
    assert (out / "04_EVALUATION_CONSENSUS.json").is_file()
    assert (out / "05_EVALUATION_RESULT.json").is_file()
    assert (out / "final_result" / "FINAL_RESULT_001.txt").is_file()
    assert (out / "final_result" / "manifest.json").is_file()
    assert result["providers_completed"] == ["claude", "gemini", "gpt"]


def test_raw_fragment_preserves_detached_closing_punctuation_and_recovery_is_not_prohibition():
    from core.cross_document_semantics import _source_fact_fragments_for_unit, _structured_source_facts

    unit = {
        "source_semantic_unit_id": "SEM-WDG",
        "source_chunk_id": "C186",
        "source_location": "Paragraph 186",
        "source_kind": "text",
        "source_excerpt": "Watchdog Timer는 인터럽트 서비스 루틴내에 있을 수 없다. )",
    }
    fragments = _source_fact_fragments_for_unit(unit)
    assert len(fragments) == 1
    assert fragments[0]["source_excerpt_raw"].endswith(". )")

    recovery = _structured_source_facts(
        "의도하지 않은 SW 오류 발생 시 MCU Reset 등을 통하여 정상 상태로 복귀한다.",
        unit_id="U1",
        location="Paragraph 184",
    )[0]
    assert recovery["prohibition"] is False
    assert recovery["failure_handling"] is True
    assert recovery["fact_type"] == "FAILURE_HANDLING_REQUIREMENT"

    explicit = _structured_source_facts(
        "Rheostat과 연동되지 않아야 한다.", unit_id="U2", location="Paragraph 82"
    )[0]
    assert explicit["prohibition"] is True
    assert explicit["fact_type"] == "PROHIBITION"
