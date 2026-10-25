from pathlib import Path
import json


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_legacy_reviewer_ui_is_removed_and_unified_modes_exist():
    text = (_root() / "main.py").read_text(encoding="utf-8")
    # Active GUI labels/control names from the dormant V0.45 reviewer workflow must be gone.
    for legacy in (
        'QRadioButton("단일 검토")',
        'QRadioButton("표준 검토',
        'QRadioButton("중복 검토")',
        'QRadioButton("정밀 검토")',
        'self.review_mode_standard',
        'self.review_mode_duplicate',
        'self.review_mode_precise',
        'self.review_model_rows',
        'self.review_scope_flagged',
        'self.review_criteria_checks',
        'self.auto_evaluation_enabled',
    ):
        assert legacy not in text
    assert 'QRadioButton("3-AI 자동 평가 (추천)")' in text
    assert 'QRadioButton("수동 평가 패키지만 생성")' in text
    assert 'QRadioButton("평가하지 않음")' in text
    assert '"auto_evaluation": mode == "auto"' in text
    assert '"legacy_multi_reviewer_ui_removed": True' in text


def test_none_mode_skips_review_exchange_and_auto_mode_is_only_external_path():
    text = (_root() / "main.py").read_text(encoding="utf-8")
    assert 'if review_cfg.get("enabled"):' in text
    assert 'if review_cfg.get("auto_evaluation"):' in text
    assert 'self._start_automatic_evaluation' in text
    # Review-only artifact generation is also gated by evaluation being enabled.
    assert 'if review_cfg.get("enabled") and req_data and review_focus == "swe1"' in text
    assert 'elif review_cfg.get("enabled") and req_data and review_focus == "swe6"' in text


def test_protected_invariant_has_single_evaluation_path_boundary():
    data = json.loads((_root() / "policy" / "protected_invariants.json").read_text(encoding="utf-8"))
    assert data["version"] == "2.0"
    inv = {x["id"]: x["rule"] for x in data["rules"]}
    assert "INV-029" in inv
    assert "Legacy standard/duplicate/precise reviewer selectors" in inv["INV-029"]
    assert "manual mode is local hand-off only" in inv["INV-029"]


def test_requirements_history_retains_rev55_and_legacy_requirement_decision():
    root = _root()
    assert (root / "history" / "requirements" / "Requirement_Studio_Requirements_Management_rev55.xlsx").is_file()
    assert not (root / "Requirement_Studio_Requirements_Management_rev55.xlsx").exists()
    decision = (root / "history" / "change_decisions" / "04_CHANGE_DECISION_V0.66_to_V0.67.txt").read_text(encoding="utf-8")
    assert "FR-316 is replaced in place" in decision
    assert "FR-362~FR-365" in decision
