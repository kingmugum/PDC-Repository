from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v088_provider_selector_is_two_rows_but_one_exclusive_group():
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    method = text.split("def _build_ai_card", 1)[1].split("def _build_execution_card", 1)[0]
    assert "provider_row_primary" in method
    assert "provider_row_secondary" in method
    primary = method.split("provider_row_primary =", 1)[1].split("provider_row_secondary =", 1)[0]
    secondary = method.split("provider_row_secondary =", 1)[1].split("# The second provider row", 1)[0]
    for token in ("self.radio_gpt", "self.radio_gemini", "self.radio_claude"):
        assert token in primary
    for token in ("self.radio_alira", "self.radio_custom"):
        assert token in secondary
    assert "for idx, btn in enumerate((self.radio_gpt, self.radio_gemini, self.radio_claude, self.radio_alira, self.radio_custom))" in method


def test_v088_ai_fields_and_actions_allow_compact_width():
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    method = text.split("def _build_ai_card", 1)[1].split("def _build_execution_card", 1)[0]
    assert "self.provider_model_combo.setMinimumWidth(172)" in method
    assert "self.api_key_field.setMinimumWidth(172)" in method
    assert "QSizePolicy.Policy.Expanding" in method
    assert "btn.setMinimumWidth(132)" in method
    assert "btn.setMaximumWidth(152)" in method
    assert "spacer.setFixedHeight(8)" in method
    assert "spacer.setFixedHeight(28)" not in method


def test_v088_top_dashboard_shrinks_before_horizontal_scroll():
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "self.resize(1200, 900)" in text
    assert "self.dashboard_content.setMinimumSize(1100, 820)" in text
    top = text.split("top = QHBoxLayout()", 1)[1].split("middle = QHBoxLayout()", 1)[0]
    assert "top.addWidget(self._build_file_card(), 3)" in top
    assert "top.addWidget(self._build_ai_card(), 6)" in top
    assert "top.addWidget(self._build_execution_card(), 3)" in top
    assert "card.setMinimumWidth(270)" in text
    assert 'QLabel("분석 진행 상황")' in text
    assert 'QLabel("필수 항목 확인")' in text


def test_v088_runtime_version_and_non_gui_semantics_are_not_reworked():
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "v0.88"' in text
    # E2E outputs and automatic triad remain present; V0.88 is a GUI-only runtime refinement.
    assert 'E2E 요구사항 명세서 (Word 파일 & 엑셀 양식)' in text
    assert 'E2E 평가 명세서 (엑셀 양식)' in text
    assert 'for index, provider in enumerate(("gpt", "gemini", "claude"), start=1)' in text
