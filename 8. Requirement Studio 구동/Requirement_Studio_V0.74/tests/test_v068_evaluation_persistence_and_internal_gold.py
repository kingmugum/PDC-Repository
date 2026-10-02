import json
import threading
import time
from pathlib import Path

from core.evaluation_orchestrator import MultiModelEvaluationOrchestrator
from core.gold_source_registry import GoldSourceRegistry


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
    root = tmp_path / "Requirement_Studio_V0.68"
    root.mkdir()
    (root / "config").mkdir()
    (root / "config" / "evaluation_api_config.json").write_text(json.dumps({
        "enabled": True,
        "transport": "hchat",
        "providers": {"gpt": {"enabled": True}, "gemini": {"enabled": True}, "claude": {"enabled": True}},
    }), encoding="utf-8")
    run = root / "review_exchange" / "RUN"
    run.mkdir(parents=True)
    source = run / "01_SOURCE_sample.txt"
    source.write_text("source fact", encoding="utf-8")
    review = {
        "run": {"source_sha256": "a" * 64, "source_original_name": "sample.txt"},
        "canonical_requirement": {"requirements": []},
    }
    (run / "02_REQUIREMENT_STUDIO_REVIEW_PACKAGE.json").write_text(json.dumps(review), encoding="utf-8")
    (run / "03_sample.txt").write_text("artifact", encoding="utf-8")
    (run / "05_REQUIREMENT_STUDIO_REVIEW_SUMMARY.txt").write_text("summary", encoding="utf-8")
    return root, run


def test_automatic_evaluation_folder_is_never_empty_while_reviewers_are_running(tmp_path, monkeypatch):
    root, run = _minimal_review_run(tmp_path)
    orchestrator = MultiModelEvaluationOrchestrator(root, app_version="v0.68", provider_config={})
    # Avoid normalizer/provider dependencies for this persistence contract test.
    monkeypatch.setattr(orchestrator, "_source_text", lambda _p: "source fact")
    started = threading.Event()
    release = threading.Event()

    def fake_call(name, evidence):
        started.set()
        assert release.wait(timeout=5)
        return _evaluation_result(name), name + "-model"

    monkeypatch.setattr(orchestrator, "_call_one", fake_call)
    holder = {}

    def runner():
        holder["result"] = orchestrator.run(run)

    t = threading.Thread(target=runner)
    t.start()
    assert started.wait(timeout=5)
    out = run / "automatic_evaluation"
    assert (out / "00_EVALUATION_STATUS.json").is_file()
    assert (out / "00_EVALUATION_STATUS.txt").is_file()
    assert (out / "06_EVALUATION_EVIDENCE.json").is_file()
    assert any(out.iterdir())
    status = json.loads((out / "00_EVALUATION_STATUS.json").read_text(encoding="utf-8"))
    assert status["status"] == "RUNNING"
    release.set()
    t.join(timeout=10)
    assert not t.is_alive()
    assert holder["result"]["status"] == "COMPLETED"
    assert (out / "99_EVALUATION_COMPLETE.ok").is_file()
    assert (out / "final_result" / "FINAL_RESULT_001.txt").is_file()
    assert holder["result"]["verified_file_count"] > 0


def test_each_reviewer_result_is_persisted_and_final_completion_is_file_verified(tmp_path, monkeypatch):
    root, run = _minimal_review_run(tmp_path)
    orchestrator = MultiModelEvaluationOrchestrator(root, app_version="v0.68", provider_config={})
    monkeypatch.setattr(orchestrator, "_source_text", lambda _p: "source fact")
    monkeypatch.setattr(orchestrator, "_call_one", lambda name, evidence: (_evaluation_result(name), name + "-model"))
    result = orchestrator.run(run)
    out = run / "automatic_evaluation"
    for prefix in ("01_GPT_EVALUATION", "02_GEMINI_EVALUATION", "03_CLAUDE_EVALUATION"):
        assert (out / f"{prefix}.json").stat().st_size > 0
        assert (out / f"{prefix}.txt").stat().st_size > 0
    assert result["verified_file_count"] >= 12
    assert json.loads((out / "00_EVALUATION_STATUS.json").read_text(encoding="utf-8"))["status"] == "COMPLETED"


def test_gold_source_registry_does_not_create_external_sibling_folder(tmp_path):
    root = tmp_path / "Requirement_Studio_V0.68"
    root.mkdir()
    external = tmp_path / "Requirement_Studio_Gold_Sources"
    registry = GoldSourceRegistry(root)
    assert not external.exists()
    assert registry.shared_root == root / "review_exchange" / "gold_sources" / "user_registered"

    review = root / "approved_review.json"
    review.write_text(json.dumps({
        "run": {
            "source_sha256": "b" * 64,
            "source_original_name": "sample.docx",
            "requirement_studio_version": "v0.67",
        },
        "canonical_requirement": {
            "requirements": [{
                "candidate_id": "REQ-CAND-001",
                "srs_id": "SRS_001",
                "requirement": "source-backed behavior",
                "source_evidence": [{"location": "Paragraph 1", "text": "source-backed behavior", "document": "sample.docx"}],
            }]
        },
    }), encoding="utf-8")
    target = registry.install_review_package(review)
    assert target.is_file()
    assert registry.user_root in target.parents
    assert not external.exists()


def test_legacy_external_gold_store_is_migrated_without_future_external_writes(tmp_path):
    root = tmp_path / "Requirement_Studio_V0.68"
    root.mkdir()
    legacy = tmp_path / "Requirement_Studio_Gold_Sources"
    (legacy / "contracts").mkdir(parents=True)
    contract_name = "gold_contract_1234.json"
    (legacy / "contracts" / contract_name).write_text(json.dumps({"source_sha256": "c" * 64}), encoding="utf-8")
    (legacy / "registry.json").write_text(json.dumps({
        "schema_version": "1.0",
        "gold_sources": [{
            "source_sha256": "c" * 64,
            "label": "legacy",
            "contract_path": f"contracts/{contract_name}",
        }],
    }), encoding="utf-8")
    registry = GoldSourceRegistry(root)
    assert (registry.user_root / "contracts" / contract_name).is_file()
    assert not legacy.exists()

def test_v046_gold_import_also_preserves_internal_legacy_baseline_path(tmp_path):
    root = tmp_path / "Requirement_Studio_V0.68"
    root.mkdir()
    registry = GoldSourceRegistry(root)
    review = root / "v046_review.json"
    review.write_text(json.dumps({
        "run": {
            "source_sha256": "d" * 64,
            "source_original_name": "legacy.docx",
            "requirement_studio_version": "v0.46",
        },
        "canonical_requirement": {
            "requirements": [{
                "candidate_id": "REQ-CAND-001",
                "srs_id": "SRS_001",
                "requirement": "legacy behavior",
                "source_evidence": [{"location": "Paragraph 1", "text": "legacy behavior", "document": "legacy.docx"}],
            }]
        },
    }), encoding="utf-8")
    registry.install_review_package(review)
    baseline = root / "review_exchange" / "baseline" / "02_REQUIREMENT_STUDIO_REVIEW_PACKAGE_v0.46.json"
    assert baseline.is_file()
    assert json.loads(baseline.read_text(encoding="utf-8"))["run"]["requirement_studio_version"] == "v0.46"
    assert not (tmp_path / "Requirement_Studio_Gold_Sources").exists()
