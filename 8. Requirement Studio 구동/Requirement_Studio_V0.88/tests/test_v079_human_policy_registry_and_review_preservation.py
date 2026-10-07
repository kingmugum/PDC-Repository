import json
from pathlib import Path

from core.cross_document_semantics import _complete_explicit_cited_requirement_matches
from core.evaluation_orchestrator import MultiModelEvaluationOrchestrator
from core.human_policy import HumanPolicyRegistry
from core.quality_audit import _child_intent_disposition
from core.swe1_exporter import build_swe1_records


def test_human_policy_registry_seed_persists_outside_version_and_does_not_overwrite_local(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    (project / "policy").mkdir(parents=True)
    seed = {
        "schema_version": "1.0",
        "policies": [
            {"policy_id": "GP-ALLOC-001", "title": "Allocation", "decision": "YES", "reuse_scope": "cross-doc", "notes": "seed"},
            {"policy_id": "HP-PRESERVE-001", "title": "Preserve", "decision": "YES", "reuse_scope": "all", "notes": "keep review"},
        ],
    }
    (project / "policy" / "human_policy_seed.json").write_text(json.dumps(seed), encoding="utf-8")
    policy_home = tmp_path / "persistent_home"
    monkeypatch.setenv("REQUIREMENT_STUDIO_POLICY_HOME", str(policy_home))

    registry = HumanPolicyRegistry(project)
    first = registry.load()
    assert registry.registry_json.is_file()
    assert registry.registry_txt.is_file()
    assert registry.project_root not in registry.registry_json.parents
    assert HumanPolicyRegistry.policy_map(first)["GP-ALLOC-001"]["decision"] == "YES"

    # Simulate a later explicit local human decision. Downloading a new package seed must not overwrite it.
    first["policies"][0]["decision"] = "NO"
    first["policies"][0]["notes"] = "local human override"
    registry.save(first)
    second = HumanPolicyRegistry(project).load()
    assert HumanPolicyRegistry.policy_map(second)["GP-ALLOC-001"]["decision"] == "NO"
    assert "local human override" in HumanPolicyRegistry.policy_map(second)["GP-ALLOC-001"]["notes"]


def test_registered_policy_suppresses_repeat_question_and_snapshot_is_auditable(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    (project / "policy").mkdir(parents=True)
    seed = {
        "schema_version": "1.0",
        "policies": [
            {"policy_id": "GP-ALLOC-001", "title": "Allocation", "decision": "YES", "reuse_scope": "cross-doc"},
            {"policy_id": "GP-TC-001", "title": "Candidate TC", "decision": "YES", "reuse_scope": "cross-doc"},
            {"policy_id": "HP-PRESERVE-001", "title": "Preserve", "decision": "YES", "reuse_scope": "all", "notes": "REVIEW_REQUIRED/HOLD 보존"},
        ],
    }
    (project / "policy" / "human_policy_seed.json").write_text(json.dumps(seed), encoding="utf-8")
    monkeypatch.setenv("REQUIREMENT_STUDIO_POLICY_HOME", str(tmp_path / "persistent"))
    reg = HumanPolicyRegistry(project)
    data = reg.load()

    report = {
        "handoff_identity": {"requirement_studio_version": "v0.79", "source_file": "x.pdf"},
        "questions": [
            {"question_id": "GP-ALLOC-001", "policy_topic": "Allocation", "observed_examples": ["SRS_001"], "reuse_scope": "cross-doc"},
            {"question_id": "GP-TC-001", "policy_topic": "Candidate TC", "observed_examples": ["SRS_001"], "reuse_scope": "cross-doc"},
            {"question_id": "GP-NEW-001", "policy_topic": "New", "observed_examples": ["SRS_999"], "reuse_scope": "cross-doc"},
        ],
        "question_count": 3,
    }
    resolved = reg.resolve_guide_report(report, data)
    assert resolved["question_count"] == 1
    assert resolved["questions"][0]["question_id"] == "GP-NEW-001"
    assert {x["policy_id"] for x in resolved["applied_policies"]} >= {"GP-ALLOC-001", "GP-TC-001", "HP-PRESERVE-001"}

    json_path, txt_path = reg.write_run_snapshot(tmp_path / "run" / "guide_person", resolved, data)
    assert json_path.is_file() and txt_path.is_file()
    txt = txt_path.read_text(encoding="utf-8")
    assert "HP-PRESERVE-001" in txt
    assert "REVIEW_REQUIRED/HOLD" in txt


def test_main_requirement_records_preserve_review_required_but_compat_api_stays_eligible_only():
    eligible = {
        "srs_id": "SRS_001", "candidate_id": "C1", "category": "기능", "requirement": "SW는 값을 저장해야 한다.",
        "swe1_eligibility": "Eligible", "allocation_status": "SW_IMPLEMENTATION_REQUIREMENT", "swe6_eligibility": "Eligible",
        "source_evidence": [{"location": "Paragraph 1", "text": "SW는 값을 저장해야 한다."}],
    }
    inferred = {
        "srs_id": "SRS_002", "candidate_id": "C2", "category": "기능", "requirement": "HU는 상태를 판단해야 한다.",
        "swe1_eligibility": "Eligible", "allocation_status": "SW_BEHAVIOR_INFERRED_REVIEW_REQUIRED", "swe6_eligibility": "Eligible",
        "source_evidence": [{"location": "Paragraph 2", "text": "HU는 상태를 판단해야 한다."}],
    }
    pending = {
        "srs_id": "SRS_003", "candidate_id": "C3", "category": "기능", "requirement": "제어기는 통신 오류 시 저전력 모드로 진입한다.",
        "swe1_eligibility": "Review Needed", "allocation_status": "SYSTEM_REQUIREMENT_PENDING_SW_ALLOCATION", "swe6_eligibility": "Deferred pending SW allocation",
        "source_evidence": [{"location": "Paragraph 3", "text": "제어기는 통신 오류 시 저전력 모드로 진입한다."}],
    }
    data = {"requirements": [eligible, inferred, pending]}
    compat = build_swe1_records(data)
    assert {x["SRS ID"] for x in compat} == {"SRS_001", "SRS_002"}
    main = build_swe1_records(data, include_review_required=True)
    assert {x["SRS ID"] for x in main} == {"SRS_001", "SRS_002", "SRS_003"}
    by = {x["SRS ID"]: x for x in main}
    assert "사람의 판단 필요" in by["SRS_002"]["검토 상태"]
    assert "사람의 판단 필요" in by["SRS_003"]["검토 상태"]


def test_deferred_snapshot_counter_skips_title_and_header():
    rows = [
        ["3. Deferred Test Intent"],
        ["SW 요구사항 ID", "Test Intent", "Reason Code"],
        ["SRS_001", "Timing", "SOURCE_INSUFFICIENT"],
        ["SRS_002", "Normal", "ALLOCATION_PENDING"],
    ]
    assert MultiModelEvaluationOrchestrator._count_deferred_snapshot_rows(rows) == 2


def test_exact_cited_semantic_completion_recovers_range_unit_without_scope_widening():
    req = {
        "requirement": "제어기는 B-CAN WAKE UP 상태 또는 최초 B+ 인가 시 High Power Mode로 전환해야 한다.",
        "source_evidence": [{"location": "Paragraph 132-136", "text": "B-CAN WAKE UP 상태 / 최초 B+ 인가 시"}],
    }
    units = [
        {"source_semantic_unit_id": "U132", "source_location": "Paragraph 132", "source_excerpt": "B-CAN WAKE UP 상태이면 High Power Mode로 전환한다."},
        {"source_semantic_unit_id": "U136", "source_location": "Paragraph 136", "source_excerpt": "최초 B+ 인가 시 High Power Mode로 전환한다."},
        {"source_semantic_unit_id": "U200", "source_location": "Paragraph 200", "source_excerpt": "관계없는 규격 준수 항목"},
    ]
    out = _complete_explicit_cited_requirement_matches(req, units, [])
    ids = {x["source_semantic_unit_id"] for x in out}
    assert {"U132", "U136"}.issubset(ids)
    assert "U200" not in ids


def test_child_intent_fact_level_pending_is_not_mislabeled_source_insufficient():
    req = {
        "swe6_eligibility": "Eligible",
        "tbd_items": ["다른 parent detail TBD"],
        "fact_level_allocations": [{
            "source_fact_fragment_id": "F-JPEG",
            "swe6_eligibility": "Deferred pending SW allocation",
            "allocation_status": "INHERIT_PARENT_ALLOCATION_PENDING",
        }],
    }
    child = {"source_fact_fragment_id": "F-JPEG", "source_backed_behavior": "Format: JPEG"}
    result = _child_intent_disposition(req, child, [])
    assert result["intent_status"] == "DEFERRED"
    assert result["deferred_reason_code"] == "ALLOCATION_PENDING"


def test_edited_guide_person_checkbox_is_imported_on_next_registry_load(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    (project / "policy").mkdir(parents=True)
    (project / "policy" / "human_policy_seed.json").write_text(
        json.dumps({"schema_version": "1.0", "policies": []}), encoding="utf-8"
    )
    guide_dir = project / "review_exchange" / "run_001" / "automatic_evaluation" / "guide_person"
    guide_dir.mkdir(parents=True)
    guide = guide_dir / "guide_person_001.txt"
    guide.write_text(
        """Requirement Studio GUIDE_PERSON — Human Policy Questions

1. GP-NEW-001 — New Cross-document Rule
------------------------------------------------------------------------
Question: test?
Policy Reuse Scope: Cross-document: test scope
Human Decision:
  [ ] YES
  [ ] NO
  [ o ] CONDITIONAL
  [ ] DEFER
Conditional Rule / Notes:
  고유 normative behavior는 유지한다.
  중복 문장만 사람 승인 후 제외할 수 있다.

Governance Boundary
-------------------
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("REQUIREMENT_STUDIO_POLICY_HOME", str(tmp_path / "persistent"))
    reg = HumanPolicyRegistry(project)
    data = reg.load()
    policy = HumanPolicyRegistry.policy_map(data)["GP-NEW-001"]
    assert policy["decision"] == "CONDITIONAL"
    assert "고유 normative behavior" in policy["notes"]
    assert "guide_person_001.txt" in policy["source"]

    # Existing decision is then reused rather than re-asked.
    resolved = reg.resolve_guide_report({
        "questions": [{
            "question_id": "GP-NEW-001",
            "policy_topic": "New Cross-document Rule",
            "reuse_scope": "Cross-document: test scope",
            "observed_examples": ["SRS_100"],
        }],
        "question_count": 1,
        "handoff_identity": {},
    }, data)
    assert resolved["question_count"] == 0
    assert any(x["policy_id"] == "GP-NEW-001" for x in resolved["applied_policies"])
