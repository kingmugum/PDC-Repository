from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from core.evaluation_orchestrator import MultiModelEvaluationOrchestrator
from core.integrated_exporter import IntegratedExporter
from core.review_exchange import ReviewExchangeBuilder
from core.swe1_exporter import SWE1Exporter
from core.swe6_exporter import SWE6Exporter
from core.verification_single_truth import finalize_verification_single_truth
from tests.test_v082_integrated_specs_single_truth import _mode_fixture


def _meta():
    return SimpleNamespace(
        display_name="H-Chat / GPT", provider_id="hchat_gpt", model="gpt-5.6-terra",
        endpoint_family="hchat", auth_mode="key", project_header_enabled=False,
        response_parsing_mode="text",
    )


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "history" / "change_decisions").mkdir(parents=True)
    (root / "history" / "change_decisions" / "04_CHANGE_DECISION_V0.82_to_V0.83.txt").write_text("decision", encoding="utf-8")
    (root / "config").mkdir(parents=True)
    (root / "config" / "evaluation_api_config.json").write_text("{}", encoding="utf-8")
    return root


def _artifacts(tmp_path: Path, data: dict):
    out = tmp_path / "out"
    source = tmp_path / "MLM.docx"
    source.write_text("source placeholder", encoding="utf-8")
    swe1 = SWE1Exporter(out)
    swe6 = SWE6Exporter(out)
    integrated = IntegratedExporter(out)
    return source, {
        "swe1_word": swe1.export_word(source, data),
        "swe1_excel": swe1.export_excel(source, data),
        "swe6_excel": swe6.export_excel(source, data, source_text="Low Power Mode High Power Mode"),
        "integrated_requirements_excel": integrated.export_requirements_excel(source, data),
        "integrated_tests_excel": integrated.export_tests_excel(source, data),
    }


def test_v083_unified_ai_evidence_contains_legacy_and_both_integrated_artifacts(tmp_path: Path):
    data = _mode_fixture()
    finalize_verification_single_truth(data)
    source, artifacts = _artifacts(tmp_path, data)
    root = _project(tmp_path)
    result = ReviewExchangeBuilder(root, app_version="v0.83").build(
        source_document=source,
        provider_metadata=_meta(), analysis_text="", requirement_data=data, evaluation={}, normalized_summary={},
        quality_review_config={"enabled": True, "evaluation_artifact": "unified", "selected_outputs": {k: True for k in artifacts}},
        artifact_paths=artifacts, evaluation_mode="initial",
    )
    run_dir = Path(result["run_dir"])
    payload = json.loads((run_dir / "02_REQUIREMENT_STUDIO_REVIEW_PACKAGE.json").read_text(encoding="utf-8"))
    contract = payload["review_handoff"]["unified_artifact_contract"]
    assert contract["status"] == "PASS"
    assert set(contract["required_artifacts"]) == set(artifacts)
    assert not contract["missing_artifacts"]

    evidence, _ = MultiModelEvaluationOrchestrator(root, app_version="v0.83").build_evidence_package(run_dir)
    assert set(evidence["actual_artifacts"]) == set(artifacts)
    assert evidence["actual_artifacts"]["integrated_requirements_excel"]["profile"] == "integrated_requirements"
    assert evidence["actual_artifacts"]["integrated_tests_excel"]["profile"] == "integrated_tests"
    assert evidence["unified_artifact_contract"]["status"] == "PASS"


def test_v083_missing_integrated_artifact_is_deterministic_release_blocker(tmp_path: Path):
    data = _mode_fixture()
    finalize_verification_single_truth(data)
    source, artifacts = _artifacts(tmp_path, data)
    artifacts.pop("integrated_tests_excel")
    root = _project(tmp_path)
    result = ReviewExchangeBuilder(root, app_version="v0.83").build(
        source_document=source,
        provider_metadata=_meta(), analysis_text="", requirement_data=data, evaluation={}, normalized_summary={},
        quality_review_config={"enabled": True, "evaluation_artifact": "unified", "selected_outputs": {k: True for k in artifacts}},
        artifact_paths=artifacts, evaluation_mode="initial",
    )
    run_dir = Path(result["run_dir"])
    evidence, _ = MultiModelEvaluationOrchestrator(root, app_version="v0.83").build_evidence_package(run_dir)
    assert evidence["unified_artifact_contract"]["status"] == "FAIL"
    assert "integrated_tests_excel" in evidence["unified_artifact_contract"]["missing_artifacts"]

    consensus = {
        "reviewer_count": 3, "evaluation_completeness": "COMPLETE",
        "tool_quality_gate": "PASS", "artifact_readiness_gate": "PASS", "official_release": "PASS",
        "consensus_findings": [],
    }
    gated = MultiModelEvaluationOrchestrator._apply_unified_artifact_contract(consensus, evidence)
    assert gated["tool_quality_gate"] == "FAIL"
    assert gated["official_release"] == "HOLD"
    assert gated["consensus_findings"][0]["category"] == "UNIFIED_ARTIFACT_CONTRACT"


def test_v083_hchat_context_pack_is_versioned_curated_and_bounded():
    root = Path(__file__).resolve().parents[1]
    script = root / "tools" / "build_hchat_context.py"
    spec = importlib.util.spec_from_file_location("build_hchat_context_v083", script)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    recent, context, readme = module.build()
    assert recent.is_file() and context.is_file() and readme.is_file()
    text = context.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert f"Version: {module._version()}" in text
    assert "[CURRENT VERSION DELTA]" in text
    assert "finalize_verification_single_truth" in text
    assert "build_evidence_package" in text
    assert "_apply_unified_artifact_contract" in text
    assert "[INCLUDED FILE HASHES]" in text
    assert len(lines) <= module.MAX_CONTEXT_LINES
    # Security/scope guard: no known credential/config source files are dumped.
    assert "api_keys/" not in text
    assert "evaluation_api_config.json" not in text
    assert "hchat_credentials.py" not in text
    assert "NOT a complete source dump" in text
