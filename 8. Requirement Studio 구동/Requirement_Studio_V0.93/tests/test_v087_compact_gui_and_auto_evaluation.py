from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_v087_execution_card_has_exactly_four_human_facing_output_choices():
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    method = text.split("def _build_execution_card",1)[1].split("def show_authoring_guide",1)[0]
    for label in (
        'SWE.1 문서 (Word 파일 & 엑셀 양식)',
        'SWE.6 문서 (엑셀 양식)',
        'E2E 요구사항 명세서 (Word 파일 & 엑셀 양식)',
        'E2E 평가 명세서 (엑셀 양식)',
    ):
        assert label in method
    assert 'SYS.1 + SWE.1' not in method
    assert 'SYS.5 + SWE.6 + Deferred/Native' not in method
    assert 'self.output_swe1_excel = self.output_swe1_word' in method
    assert 'self.output_e2e_requirements_excel = self.output_e2e_requirements_word' in method


def test_v087_quality_tab_is_compact_but_keeps_mode_artifact_and_progress():
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    method = text.split("def _build_quality_review_box",1)[1].split("def _reset_quality_review_defaults",1)[0]
    for token in (
        'QLabel("평가 모드")',
        'QLabel("평가 산출물")',
        'QLabel("자동 평가 진행 상황")',
        'QRadioButton("3-AI 자동 평가 (추천)")',
        'QRadioButton("통합 E2E 평가 (요구사항 + 평가 명세서, 추천)")',
        'QPushButton("평가 진행 결과 열기")',
    ):
        assert token in method
    assert 'QLabel("자동 평가 Reviewer")' not in method
    assert 'QLabel("평가 계약")' not in method
    assert 'Reviewer 선택은 별도' not in method


def test_v087_auto_triad_backend_remains_enabled_after_ui_simplification():
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'for index, provider in enumerate(("gpt", "gemini", "claude"), start=1)' in text
    assert 'self._start_automatic_evaluation(Path(str(review_package.get("run_dir"))))' in text
    assert 'GPT/Gemini/Claude 독립 검토' in text
    assert 'orchestrator = MultiModelEvaluationOrchestrator(' in text
    cfg = json.loads((ROOT / "config" / "evaluation_api_config.json").read_text(encoding="utf-8"))
    assert cfg["enabled"] is True and cfg["run_after_review_package"] is True
    assert all(cfg["providers"][p]["enabled"] for p in ("gpt","gemini","claude"))
    assert cfg["default_evaluation_mode"] == "unified"


def test_v087_unified_label_explicitly_means_requirements_plus_evaluation_specification():
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert '통합 E2E 평가 (요구사항 + 평가 명세서, 추천)' in text
    assert 'SWE.1/SWE.6 + E2E 요구사항 Word/Excel + E2E 평가 Excel 전체를 함께 평가합니다.' in text


def test_v087_preserves_analysis_progress_and_required_items_panels():
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'QLabel("분석 진행 상황")' in text
    assert 'QLabel("필수 항목 확인")' in text
    assert "for no in range(1, 8):" in text
    assert "self._create_step_widget(no, STEP_UI_TITLES[no])" in text
