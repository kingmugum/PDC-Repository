from pathlib import Path

from core.evaluation_orchestrator import MultiModelEvaluationOrchestrator


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _req(idx: int, eligible: bool):
    sid = f"SRS_{idx:03d}"
    if eligible:
        return {
            "srs_id": sid,
            "requirement": f"SW shall perform behavior {idx}",
            "allocation_status": "SW_IMPLEMENTATION_REQUIREMENT",
            "swe1_eligibility": "Eligible",
            "swe6_eligibility": "Eligible",
            "verification_domain": "SWE.6 Software Qualification",
            "positive_sw_allocation_evidence": ["SW implementation"],
            "allocation_rationale": "Positive software evidence exists.",
            "source_evidence": [{"location": f"Paragraph {idx}", "text": "SW implementation"}],
        }
    return {
        "srs_id": sid,
        "requirement": f"Controller shall perform behavior {idx}",
        "allocation_status": "SYSTEM_REQUIREMENT_PENDING_SW_ALLOCATION",
        "swe1_eligibility": "Review Needed",
        "swe6_eligibility": "Deferred pending SW allocation",
        "verification_domain": "System Integration / SYS.5",
        "positive_sw_allocation_evidence": [],
        "allocation_rationale": "Source states controller/system behavior, but no positive Source-backed software allocation evidence is present.",
        "source_evidence": [{"location": f"Paragraph {idx}", "text": "Controller behavior"}],
    }


def test_situation_check_identifies_allocation_policy_as_primary_driver():
    reqs = [_req(i, i <= 2) for i in range(1, 18)]
    review = {
        "canonical_requirement": {
            "requirements": reqs,
            "semantic_source_unit_coverage": {
                "eligible_unit_count": 17,
                "covered_unit_count": 17,
                "open_review_needed_count": 0,
                "terminal_disposition_complete": True,
                "disposition_counts": {"COVERED_BY_CANONICAL": 17},
                "open_review_needed_records": [],
            },
        },
        "calculated_review_evidence": {
            "testability_and_decomposition_result": {
                "summary": {"total_generated_tc_count": 2, "deferred_intent_count": 15}
            },
            "swe6_export_preservation_audit": {"generated_tc_count": 2},
            "conflict_register": [],
        },
    }
    evidence = {
        "requirement_studio_version": "v0.76",
        "evaluation_mode": "unified",
        "run_dir": "run-1",
        "source": {"file": "source.docx", "sha256": "abc"},
        "evidence_package_sha256": "def",
    }
    report = MultiModelEvaluationOrchestrator._build_situation_check(review, evidence)
    counts = report["observed_counts"]
    assert counts["canonical_srs_count"] == 17
    assert counts["main_swe1_eligible_count"] == 2
    assert counts["pending_swe1_annex_count"] == 15
    assert counts["policy_held_no_positive_sw_count"] == 15
    assert report["hypothesis_verdict"] == "SUPPORTED"
    assert report["policy_interpretation"]["hypothetical_main_swe1_upper_bound_if_only_allocation_gate_relaxed"] == 17


def test_situation_check_split_is_self_identifying_and_uses_requested_names(tmp_path):
    ident = {
        "requirement_studio_version": "v0.76",
        "evaluation_mode": "unified",
        "source_file": "source.pdf",
        "source_sha256": "abc",
        "run_id": "run-2",
        "evidence_package_sha256": "def",
    }
    text = "\n".join(f"line-{i:03d}" for i in range(1, 221)) + "\n"
    paths = MultiModelEvaluationOrchestrator.split_situation_check(
        text, tmp_path / "check_situation", lines_per_file=110, handoff_identity=ident
    )
    assert len(paths) >= 2
    assert paths[0].name == "check_situation_001.txt"
    body = paths[0].read_text(encoding="utf-8")
    assert "[Requirement Studio CHECK_SITUATION Handoff]" in body
    assert "Version: v0.76" in body
    assert "Source: source.pdf" in body
    assert (tmp_path / "check_situation" / "manifest.json").is_file()


def test_package_root_is_clean_and_history_is_preserved():
    root = _root()
    assert (root / "md" / "ARCHITECTURE.md").is_file()
    assert (root / "md" / "README.md").is_file()
    assert not (root / "ARCHITECTURE.md").exists()
    assert not list(root.glob("04_CHANGE_DECISION_*.txt"))
    assert (root / "history" / "change_decisions" / "04_CHANGE_DECISION_V0.74_to_V0.75.txt").is_file()
    assert (root / "history" / "requirements" / "Requirement_Studio_Requirements_Management_rev59.xlsx").is_file()
    assert (root / "history" / "requirements" / "Requirement_Studio_Requirements_Management_rev60.xlsx").is_file()
    assert (root / "history" / "requirements" / "Requirement_Studio_Requirements_Management_rev64.xlsx").is_file()
    root_baselines = sorted(root.glob("Requirement_Studio_Requirements_Management_rev*.xlsx"))
    assert [p.name for p in root_baselines] == ["Requirement_Studio_Requirements_Management_rev76.xlsx"]
    assert (root / "history" / "requirements" / "Requirement_Studio_Requirements_Management_rev66.xlsx").is_file()
