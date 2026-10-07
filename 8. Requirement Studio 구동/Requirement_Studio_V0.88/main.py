
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QUrl, QTimer, Signal, QFileSystemWatcher
from PySide6.QtGui import QDesktopServices, QFont, QIcon, QPixmap, QAction
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QTextBrowser,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QRadioButton,
    QSizePolicy,
    QTabWidget,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.ai_job_runner import AIJobRunner
from core.document_manager import DocumentManager, SUPPORTED_EXTENSIONS
from core.document_normalizer import DocumentNormalizer
from core.prompt_builder import PromptBuilder
from core.requirement_engine import RequirementEngine
from core.review_exchange import ReviewExchangeBuilder
from core.evaluation_orchestrator import MultiModelEvaluationOrchestrator
from core.result_exporter import AnalysisResultExporter
from core.swe1_exporter import SWE1Exporter
from core.swe6_exporter import SWE6Exporter
from core.integrated_exporter import IntegratedExporter
from core.e2e_exporter import E2EExporter
from core.verification_single_truth import finalize_verification_single_truth
from core.alira_setup import (
    DEFAULT_API_BASE as ALIRA_DEFAULT_API_BASE,
    DEFAULT_MODEL as ALIRA_DEFAULT_MODEL,
    default_cli_path,
    inspect_setup,
    install_alira_cli_windows,
    project_license_dir,
    relative_config_path,
)
from core.worker import ConnectionTestWorker, PipelineWorker, TaskWorker
from providers.config_store import ProviderConfigStore
from providers.factory import create_provider
from providers.hchat_credentials import is_valid_hchat_api_key

APP_TITLE = "Requirement Studio"
APP_VERSION = "v0.88"

STEP_UI_TITLES = {
    1: "입력/환경 확인",
    2: "문서 정규화",
    3: "분석 요청 생성",
    4: "문서 분석",
    5: "요구사항 추출",
    6: "결과 검증",
    7: "결과 저장",
}



class FileDropZone(QFrame):
    filesSelected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        # Keep the file-drop panel dimensions stable when its ready-state text becomes shorter.
        # V0.44: reduce only the drop-zone height so the middle section can move upward,
        # while preserving the approved AI Settings / Execution layout.
        self.setMinimumSize(276, 138)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel("▤")
        self.icon_label.setObjectName("dropZoneIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        self.title_label = QLabel("분석할 문서 파일을 여기에 드래그하거나")
        self.title_label.setObjectName("dropZoneTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.link_button = QPushButton("파일을 선택하세요")
        self.link_button.setObjectName("dropZoneLink")
        self.link_button.clicked.connect(self._browse_files)
        self.link_button.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.link_button, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_document_count(self, count: int):
        self.setProperty("ready", count > 0)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        if count <= 0:
            self.title_label.setText("분석할 문서 파일을 여기에 드래그하거나")
            self.link_button.setText("파일을 선택하세요")
        elif count == 1:
            self.title_label.setText("문서 1개가 준비되었습니다.")
            self.link_button.setText("파일 다시 선택")
        else:
            self.title_label.setText(f"문서 {count}개가 준비되었습니다.")
            self.link_button.setText("파일 다시 선택")

    def _browse_files(self):
        filters = "문서 파일 (*.pdf *.docx *.pptx *.xlsx *.xlsm)"
        paths, _ = QFileDialog.getOpenFileNames(self, "문서 선택", "", filters)
        if paths:
            self.filesSelected.emit(paths)

    def dragEnterEvent(self, event):
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        valid = [p for p in paths if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
        if valid and len(valid) == len(paths):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event):
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        valid = [str(p) for p in paths if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
        if valid and len(valid) == len(paths):
            self.filesSelected.emit(valid)
            event.acceptProposedAction()
            return
        event.ignore()


class LoadingDotsIndicator(QWidget):
    """Small three-dot activity indicator used for the current pipeline step.

    It intentionally communicates "working" rather than a fabricated model-internal percentage.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._index = 0
        self._labels = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        for _ in range(3):
            label = QLabel("●")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedWidth(14)
            self._labels.append(label)
            layout.addWidget(label)
        self._timer = QTimer(self)
        self._timer.setInterval(320)
        self._timer.timeout.connect(self._advance)
        self._render()

    def _render(self):
        palette = ("#2563EB", "#93C5FD", "#BFDBFE")
        for i, label in enumerate(self._labels):
            distance = (i - self._index) % 3
            color = palette[distance]
            label.setStyleSheet(f"color:{color}; font-size:18px; background:transparent;")

    def _advance(self):
        self._index = (self._index + 1) % 3
        self._render()

    def start(self):
        if not self._timer.isActive():
            self._timer.start()
        self.show()

    def stop(self):
        self._timer.stop()
        self._index = 0
        self._render()
        self.hide()


class ConnectionTestDialog(QDialog):
    def __init__(self, metadata, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 연결 테스트")
        self.setModal(False)
        self.resize(620, 470)
        self.setMinimumSize(560, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel("AI 연결 테스트")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        subtitle = QLabel("선택한 Provider에 실제 최소 요청을 보내 연결 상태를 확인합니다.")
        subtitle.setObjectName("dialogSubtitle")
        layout.addWidget(subtitle)

        meta_card = QFrame()
        meta_card.setObjectName("dialogCard")
        meta_grid = QGridLayout(meta_card)
        meta_grid.setContentsMargins(16, 14, 16, 14)
        meta_grid.setHorizontalSpacing(16)
        meta_grid.setVerticalSpacing(8)

        rows = [
            ("Provider", metadata.display_name),
            ("Model", metadata.model or "-"),
            ("API Base", metadata.api_base or "-"),
            ("Credential", metadata.credential_status or "미확인"),
        ]
        for row, (key, value) in enumerate(rows):
            key_label = QLabel(key)
            key_label.setObjectName("dialogMetaKey")
            value_label = QLabel(value)
            value_label.setObjectName("dialogMetaValue")
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value_label.setWordWrap(True)
            meta_grid.addWidget(key_label, row, 0)
            meta_grid.addWidget(value_label, row, 1)
        meta_grid.setColumnStretch(1, 1)
        layout.addWidget(meta_card)

        self.status_label = QLabel("● 연결 확인 준비")
        self.status_label.setObjectName("dialogStatus")
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        layout.addWidget(self.progress)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setObjectName("dialogLog")
        layout.addWidget(self.log_box, 1)

        self._started_monotonic = time.monotonic()
        self._last_percent = 0
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._refresh_elapsed_status)
        self._elapsed_timer.start()

        button_row = QHBoxLayout()
        button_row.addStretch()
        self.close_button = QPushButton("닫기")
        self.close_button.setObjectName("secondaryButton")
        self.close_button.clicked.connect(self.close)
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

        self.setStyleSheet(
            """
            QDialog { background:#F5F7FB; color:#172033; font-family:'Segoe UI','Malgun Gothic'; font-size:13px; }
            QLabel#dialogTitle { font-size:20px; font-weight:700; color:#111827; }
            QLabel#dialogSubtitle { color:#667085; }
            QFrame#dialogCard { background:#FFFFFF; border:1px solid #E4E7EC; border-radius:12px; }
            QLabel#dialogMetaKey { color:#667085; font-weight:600; }
            QLabel#dialogMetaValue { color:#1D2939; }
            QLabel#dialogStatus { font-weight:700; color:#667085; padding:4px 0; }
            QProgressBar { border:1px solid #D0D5DD; border-radius:8px; height:18px; text-align:center; background:#EEF2F6; color:#1D2939; font-weight:700; }
            QProgressBar::chunk { background:#3B82F6; border-radius:7px; }
            QPlainTextEdit#dialogLog { background:#0F172A; color:#D9E5F5; border:1px solid #1E293B; border-radius:10px; padding:10px; font-family:'Consolas','Malgun Gothic'; font-size:12px; }
            QPushButton#secondaryButton { min-height:34px; padding:0 18px; border:1px solid #D0D5DD; border-radius:8px; background:#FFFFFF; color:#344054; font-weight:600; }
            QPushButton#secondaryButton:hover { background:#F8FAFC; }
            """
        )

    def append_log(self, text: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.appendPlainText(f"[{stamp}] {text}")

    def _refresh_elapsed_status(self):
        elapsed = max(0, int(time.monotonic() - self._started_monotonic))
        self.status_label.setText(f"● 연결 확인 중... {elapsed}초 경과 ({self._last_percent}% 진행 중)")
        self.status_label.setStyleSheet("color:#D97706; font-weight:700;")

    def set_progress(self, percent: int, message: str):
        pct = max(0, min(99, int(percent)))
        self._last_percent = pct
        self.progress.setValue(pct)
        self._refresh_elapsed_status()
        self.append_log(message)

    def finish_success(self, message: str):
        self._elapsed_timer.stop()
        elapsed = max(0, int(time.monotonic() - self._started_monotonic))
        self._last_percent = 100
        self.progress.setValue(100)
        self.status_label.setText(f"● AI 연결 정상 · {elapsed}초 경과 (100%)")
        self.status_label.setStyleSheet("color:#15803D; font-weight:700;")
        self.append_log("연결 테스트 완료")
        if message:
            self.append_log(f"응답: {message[:300]}")

    def finish_error(self, message: str):
        self._elapsed_timer.stop()
        self.progress.setValue(100)
        self.status_label.setText("● AI 연결 실패")
        self.status_label.setStyleSheet("color:#DC2626; font-weight:700;")
        self.append_log(f"실패: {message}")


class AuthoringGuideDialog(QDialog):
    def __init__(self, guide_path: Path, parent=None, extra_guide_path: Path | None = None):
        super().__init__(parent)
        self.guide_path = Path(guide_path)
        self.extra_guide_path = Path(extra_guide_path) if extra_guide_path else None
        self.setWindowTitle("산출물 작성 기준 및 설계 원칙")
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(860, 720)
        self.setMinimumSize(680, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(10)

        title = QLabel("산출물 작성 기준 및 설계 원칙")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Requirement Studio가 SWE.1/SWE.6를 왜 이런 구조로 작성하는지 확인하는 설명 기준입니다. "
            "이 창을 열어둔 상태에서도 메인 Dashboard를 계속 조작할 수 있습니다."
        )
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.browser = QTextBrowser()
        self.browser.setObjectName("guideText")
        self.browser.setOpenExternalLinks(False)
        self.browser.setReadOnly(True)
        layout.addWidget(self.browser, 1)

        button_row = QHBoxLayout()
        self.reload_button = QPushButton("기준 다시 읽기")
        self.reload_button.setObjectName("secondaryButton")
        self.reload_button.clicked.connect(self.reload_guide)
        button_row.addWidget(self.reload_button)
        button_row.addStretch()
        close_button = QPushButton("닫기")
        close_button.setObjectName("secondaryButton")
        close_button.clicked.connect(self.close)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        self.setStyleSheet(
            """
            QDialog { background:#F5F7FB; color:#172033; font-family:'Segoe UI','Malgun Gothic'; font-size:13px; }
            QLabel#dialogTitle { font-size:20px; font-weight:700; color:#111827; }
            QLabel#dialogSubtitle { color:#667085; }
            QTextBrowser#guideText { background:#FFFFFF; border:1px solid #E4E7EC; border-radius:10px; padding:14px; color:#1D2939; }
            QPushButton#secondaryButton { min-height:34px; padding:0 16px; border:1px solid #D0D5DD; border-radius:8px; background:#FFFFFF; color:#344054; font-weight:600; }
            QPushButton#secondaryButton:hover { background:#F8FAFC; }
            """
        )
        self.reload_guide()

    def reload_guide(self):
        if not self.guide_path.is_file():
            self.browser.setPlainText(f"작성 기준 파일을 찾을 수 없습니다.\n\n{self.guide_path}")
            return
        try:
            text = self.guide_path.read_text(encoding="utf-8")
            if self.extra_guide_path and self.extra_guide_path.is_file():
                extra = self.extra_guide_path.read_text(encoding="utf-8")
                text = text.rstrip() + "\n\n---\n\n" + extra.lstrip()
        except Exception as exc:
            self.browser.setPlainText(f"작성 기준을 읽지 못했습니다.\n\n{exc}")
            return
        self.browser.setMarkdown(text)


class CustomApiSettingsDialog(QDialog):
    PROFILE_ITEMS = [
        ("OpenAI 호환 Chat Completions", "openai_compatible"),
        ("OpenAI Responses", "openai_responses"),
        ("Anthropic Messages", "anthropic_messages"),
        ("Gemini generateContent", "gemini_generate_content"),
    ]
    AUTH_ITEMS = [
        ("자동 (Profile 기본값)", "auto"),
        ("Bearer", "bearer"),
        ("x-api-key Header", "x-api-key"),
        ("Query API Key", "query_key"),
        ("인증 없음", "none"),
    ]

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("기타 API 설정")
        self.resize(690, 610)
        self.setMinimumWidth(640)
        self.saved_config = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel("기타 API 설정")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        subtitle = QLabel(
            "회사별 API가 아래 지원 형식과 호환되는 경우 코드 수정 없이 Base/Model/API Key 정보만으로 연결할 수 있습니다. "
            "완전히 다른 요청/응답 규격은 별도 Adapter가 필요합니다."
        )
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("dialogCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)

        self.profile_combo = QComboBox()
        profile_flags = dict(config.get("profile_flags") or {})
        for label, value in self.PROFILE_ITEMS:
            if profile_flags.get(value, True):
                self.profile_combo.addItem(label, value)
        self.base_edit = QLineEdit()
        self.base_edit.setPlaceholderText("예: https://api.example.com/v1")
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("회사에서 제공한 기본 Model ID")
        self.model_options_edit = QLineEdit()
        self.model_options_edit.setPlaceholderText("선택 가능한 Model ID를 쉼표로 구분 (선택)")
        self.auth_combo = QComboBox()
        for label, value in self.AUTH_ITEMS:
            self.auth_combo.addItem(label, value)
        self.key_name_edit = QLineEdit()
        self.key_name_edit.setPlaceholderText("선택: Authorization / x-api-key / key")
        self.version_header_name_edit = QLineEdit()
        self.version_header_name_edit.setPlaceholderText("선택: API Version Header Name")
        self.version_header_value_edit = QLineEdit()
        self.version_header_value_edit.setPlaceholderText("선택: API Version Header Value")
        self.key_required = QCheckBox("API Key 사용")
        self.key_required.setChecked(True)
        self.image_support = QCheckBox("이미지 입력 사용 (선택한 모델이 지원하는 경우)")

        labels = [
            "API 형식", "API Base / Endpoint", "기본 Model", "Model 목록", "인증 방식",
            "API Key 이름", "Version Header", "Version Value", "인증", "Vision",
        ]
        widgets = [
            self.profile_combo, self.base_edit, self.model_edit, self.model_options_edit,
            self.auth_combo, self.key_name_edit, self.version_header_name_edit,
            self.version_header_value_edit, self.key_required, self.image_support,
        ]
        for row, (label, widget) in enumerate(zip(labels, widgets)):
            key = QLabel(label)
            key.setObjectName("dialogMetaKey")
            grid.addWidget(key, row, 0)
            grid.addWidget(widget, row, 1)
        grid.setColumnStretch(1, 1)
        layout.addWidget(card)

        note = QLabel(
            "API Key 값은 이 창에 저장하지 않습니다. 설정 저장 후 메인 화면의 [API Key 수동 입력]을 사용하며, "
            "Key 평문은 config/log에 기록하지 않습니다."
        )
        note.setWordWrap(True)
        note.setObjectName("dialogSubtitle")
        layout.addWidget(note)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("취소")
        cancel.setObjectName("secondaryButton")
        cancel.clicked.connect(self.reject)
        save = QPushButton("설정 저장")
        save.setObjectName("outlinePrimaryButton")
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

        profile = str(config.get("profile") or "openai_compatible")
        idx = self.profile_combo.findData(profile)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)
        self.base_edit.setText(str(config.get("base_url") or ""))
        self.model_edit.setText(str(config.get("model") or ""))
        options = list(config.get("model_options") or [])
        self.model_options_edit.setText(", ".join(str(x) for x in options if str(x).strip()))
        auth_mode = str(config.get("auth_mode") or "auto")
        auth_idx = self.auth_combo.findData(auth_mode)
        if auth_idx >= 0:
            self.auth_combo.setCurrentIndex(auth_idx)
        self.key_name_edit.setText(str(config.get("api_key_name") or ""))
        self.version_header_name_edit.setText(str(config.get("version_header_name") or ""))
        self.version_header_value_edit.setText(str(config.get("version_header_value") or ""))
        self.key_required.setChecked(bool(config.get("api_key_required", True)))
        self.image_support.setChecked(bool(config.get("supports_images", False)))

        self.setStyleSheet(
            """
            QDialog { background:#F5F7FB; color:#172033; font-family:'Segoe UI','Malgun Gothic'; font-size:13px; }
            QLabel#dialogTitle { font-size:20px; font-weight:700; color:#111827; }
            QLabel#dialogSubtitle { color:#667085; }
            QFrame#dialogCard { background:#FFFFFF; border:1px solid #E4E7EC; border-radius:12px; }
            QLabel#dialogMetaKey { color:#475467; font-weight:700; }
            QLineEdit, QComboBox { min-height:36px; border:1px solid #D0D5DD; border-radius:8px; background:#FFFFFF; padding:0 10px; }
            QCheckBox { min-height:30px; }
            QPushButton#secondaryButton, QPushButton#outlinePrimaryButton { min-height:34px; padding:0 16px; border-radius:8px; font-weight:700; }
            QPushButton#secondaryButton { border:1px solid #D0D5DD; background:#FFFFFF; color:#344054; }
            QPushButton#outlinePrimaryButton { border:1px solid #84ADFF; background:#FFFFFF; color:#2563EB; }
            """
        )

    def _save(self):
        base = self.base_edit.text().strip()
        model = self.model_edit.text().strip()
        if not base or not model:
            QMessageBox.warning(self, "기타 API 설정", "API Base / Endpoint와 Model을 모두 입력해주세요.")
            return
        options = [x.strip() for x in self.model_options_edit.text().split(",") if x.strip()]
        if model not in options:
            options.insert(0, model)
        self.saved_config = {
            "profile": str(self.profile_combo.currentData()),
            "base_url": base,
            "model": model,
            "model_options": options,
            "api_key_required": self.key_required.isChecked(),
            "auth_mode": str(self.auth_combo.currentData()),
            "api_key_name": self.key_name_edit.text().strip(),
            "version_header_name": self.version_header_name_edit.text().strip(),
            "version_header_value": self.version_header_value_edit.text().strip(),
            "supports_images": self.image_support.isChecked(),
        }
        self.accept()


class ChecklistDetailDialog(QDialog):
    def __init__(self, checks: dict[str, dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("상태 상세 원인 확인")
        self.resize(620, 480)
        self.setMinimumSize(560, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel("상태 상세 원인 확인")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        unresolved = sum(1 for item in checks.values() if item["state"] != "confirmed")
        summary = QLabel(
            "현재 확인된 문제는 없습니다."
            if unresolved == 0
            else f"현재 {unresolved}개 항목이 미확인 상태입니다. 아래 원인과 조치 내용을 확인해주세요."
        )
        summary.setWordWrap(True)
        summary.setObjectName("summary")
        layout.addWidget(summary)

        box = QPlainTextEdit()
        box.setReadOnly(True)
        lines = []
        for name, item in checks.items():
            status = "확인됨" if item["state"] == "confirmed" else "미확인"
            lines.append(f"[{status}] {name}")
            lines.append(f"  원인/상태 : {item.get('detail') or '-'}")
            if item.get("action"):
                lines.append(f"  확인 방법  : {item['action']}")
            lines.append("")
        box.setPlainText("\n".join(lines).rstrip())
        layout.addWidget(box, 1)

        row = QHBoxLayout()
        row.addStretch()
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.close)
        row.addWidget(close_btn)
        layout.addLayout(row)

        self.setStyleSheet(
            """
            QDialog { background:#F5F7FB; color:#172033; font-family:'Segoe UI','Malgun Gothic'; font-size:13px; }
            QLabel#dialogTitle { font-size:20px; font-weight:700; }
            QLabel#summary { color:#475467; }
            QPlainTextEdit { background:#FFFFFF; border:1px solid #DDE3EA; border-radius:10px; padding:12px; font-family:'Consolas','Malgun Gothic'; font-size:12px; }
            QPushButton { min-height:34px; padding:0 18px; border:1px solid #D0D5DD; border-radius:8px; background:#FFFFFF; font-weight:600; }
            """
        )



class ResultContentPane(QFrame):
    """Result panel with a centered empty state and a text view after data arrives."""

    def __init__(self, project_root: Path, icon_name: str, empty_title: str, empty_subtitle: str, parent=None):
        super().__init__(parent)
        self.setObjectName("resultContentPane")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.empty_widget = QWidget()
        self.empty_widget.setObjectName("resultEmptyState")
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setContentsMargins(24, 18, 24, 18)
        empty_layout.setSpacing(7)
        empty_layout.addStretch()

        icon = QLabel()
        icon.setObjectName("resultEmptyIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedHeight(44)
        icon_path = project_root / "assets" / icon_name
        if icon_path.is_file():
            pm = QPixmap(str(icon_path)).scaled(
                34, 34,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            icon.setPixmap(pm)
        empty_layout.addWidget(icon)

        title = QLabel(empty_title)
        title.setObjectName("resultEmptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        empty_layout.addWidget(title)

        subtitle = QLabel(empty_subtitle)
        subtitle.setObjectName("resultEmptySubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        empty_layout.addWidget(subtitle)
        empty_layout.addStretch()

        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setObjectName("resultTextEdit")
        self.text_edit.hide()

        layout.addWidget(self.empty_widget, 1)
        layout.addWidget(self.text_edit, 1)

    def _show_text(self):
        self.empty_widget.hide()
        self.text_edit.show()

    def _show_empty(self):
        self.text_edit.hide()
        self.empty_widget.show()

    def appendPlainText(self, text: str):
        if not text:
            return
        self._show_text()
        self.text_edit.appendPlainText(text)

    def setPlainText(self, text: str):
        value = text or ""
        self.text_edit.setPlainText(value)
        if value.strip():
            self._show_text()
        else:
            self._show_empty()

    def clear(self):
        self.text_edit.clear()
        self._show_empty()

    def toPlainText(self) -> str:
        return self.text_edit.toPlainText()


def _wrap_result_pane(pane: QWidget) -> QWidget:
    wrapper = QWidget()
    wrapper.setObjectName("resultTabWrapper")
    layout = QVBoxLayout(wrapper)
    # Deliberate gap between tabs/actions and the content card.
    layout.setContentsMargins(0, 10, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(pane, 1)
    return wrapper


class AliraSetupDialog(QDialog):
    """Provider-aware setup assistant for the local ALIRA CLI + remote Qwen connection.

    Requirement Studio keeps the license in the project-local alira_license folder and passes it
    to the ALIRA CLI through ALIRA_LICENSE_PATH.  The remote Qwen model is not installed locally.
    """

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.project_root = main_window.project_root
        self.thread_pool = main_window.thread_pool
        self.install_worker = None
        self.connection_worker = None
        self._install_prompt_shown = False
        self._connection_started_for_signature = ""
        self._applied_license = ""

        self.setWindowTitle("ALIRA 연결 설정")
        self.setModal(False)
        self.resize(650, 520)
        self.setMinimumSize(600, 470)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel("ALIRA 연결 설정")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "라이선스 파일을 Requirement Studio의 alira_license 폴더에 넣으면, "
            "로컬 ALIRA CLI와 원격 Qwen 연결 설정을 순서대로 확인합니다."
        )
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        note = QLabel(
            "※ ALIRA CLI는 이 PC에 준비되며, 실제 Qwen 모델은 로컬에 설치하지 않고 사내 vLLM 서버에 연결합니다."
        )
        note.setStyleSheet("color:#667085; font-size:12px; background:#F8FAFC; padding:8px 10px; border-radius:8px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        card = QFrame()
        card.setObjectName("dialogCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        self.setup_rows = {}
        for row, (key, label) in enumerate((
            ("cli", "ALIRA CLI"),
            ("license", "License"),
            ("model", "Model"),
            ("api", "API Server"),
            ("connection", "Connection Test"),
        )):
            name = QLabel(label)
            name.setObjectName("dialogMetaKey")
            status = QLabel("○ 확인 중")
            status.setWordWrap(True)
            status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(name, row, 0)
            grid.addWidget(status, row, 1)
            self.setup_rows[key] = status
        grid.setColumnStretch(1, 1)
        layout.addWidget(card)

        self.summary_label = QLabel("라이선스 폴더를 확인하는 중입니다.")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("color:#344054; font-weight:700;")
        layout.addWidget(self.summary_label)

        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail_label.setStyleSheet("color:#667085; font-size:12px;")
        layout.addWidget(self.detail_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.open_folder_button = QPushButton("라이선스 폴더 열기")
        self.open_folder_button.setObjectName("secondaryButton")
        self.open_folder_button.clicked.connect(self.open_license_folder)
        self.install_button = QPushButton("ALIRA CLI 자동 설치")
        self.install_button.setObjectName("secondaryButton")
        self.install_button.clicked.connect(self.confirm_and_install_cli)
        self.retry_button = QPushButton("다시 확인")
        self.retry_button.setObjectName("outlinePrimaryButton")
        self.retry_button.clicked.connect(self.refresh_status)
        self.close_button = QPushButton("닫기")
        self.close_button.setObjectName("secondaryButton")
        self.close_button.clicked.connect(self.close)
        buttons.addWidget(self.open_folder_button)
        buttons.addWidget(self.install_button)
        buttons.addStretch()
        buttons.addWidget(self.retry_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(900)
        self.poll_timer.timeout.connect(self.refresh_status)
        self.poll_timer.start()

        self.setStyleSheet("""
            QDialog { background:#FFFFFF; }
            QLabel#dialogTitle { font-size:20px; font-weight:800; color:#101828; }
            QLabel#dialogSubtitle { color:#667085; font-size:12px; }
            QFrame#dialogCard { background:#F8FAFC; border:1px solid #E4EAF3; border-radius:12px; }
            QLabel#dialogMetaKey { color:#475467; font-weight:700; min-width:112px; }
            QPushButton { min-height:36px; padding:0 14px; border-radius:9px; font-weight:700; }
            QPushButton#secondaryButton { background:#FFFFFF; color:#344054; border:1px solid #D0D5DD; }
            QPushButton#secondaryButton:hover { background:#F8FAFC; }
            QPushButton#secondaryButton:disabled { color:#98A2B3; background:#F2F4F7; }
            QPushButton#outlinePrimaryButton { background:#FFFFFF; color:#2563EB; border:1px solid #B9D3FF; }
            QPushButton#outlinePrimaryButton:hover { background:#EFF6FF; }
        """)

        QTimer.singleShot(120, self.open_license_folder)
        QTimer.singleShot(180, self.refresh_status)

    def closeEvent(self, event):
        self.poll_timer.stop()
        super().closeEvent(event)

    def _set_row(self, key: str, ok: bool | None, text: str):
        label = self.setup_rows[key]
        if ok is True:
            label.setText(f"✓ {text}")
            label.setStyleSheet("color:#15803D; font-weight:700;")
        elif ok is False:
            label.setText(f"○ {text}")
            label.setStyleSheet("color:#B45309; font-weight:700;")
        else:
            label.setText(f"● {text}")
            label.setStyleSheet("color:#2563EB; font-weight:700;")

    def open_license_folder(self):
        folder = project_license_dir(self.project_root)
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def refresh_status(self):
        cfg = self.main_window.provider_config.get("alira") or {}
        status = inspect_setup(self.project_root, cfg)
        self._set_row("cli", status.cli_exists, str(status.cli_path) if status.cli_exists else "로컬 CLI 미설치")
        self._set_row(
            "license",
            bool(status.license_path),
            str(status.license_path) if status.license_path else "alira_license 폴더에 *.lic 파일을 넣어주세요",
        )
        self._set_row("model", bool(status.model), status.model or "Model 미설정")
        self._set_row("api", bool(status.api_base), status.api_base or "API Base 미설정")
        self.install_button.setVisible(not status.cli_exists)

        if status.license_path:
            license_text = str(status.license_path.resolve())
            if license_text != self._applied_license:
                self._applied_license = license_text
                self.main_window._apply_alira_connection_config(status.license_path)
                self.main_window._append_log(
                    f"ALIRA License 확인 · {status.license_path.name} · ALIRA_LICENSE_PATH로 연결"
                )

        if status.license_path and not status.cli_exists and not self._install_prompt_shown and self.install_worker is None:
            self._install_prompt_shown = True
            QTimer.singleShot(0, self.confirm_and_install_cli)
            return

        if status.ready_for_test and self.install_worker is None and self.connection_worker is None:
            signature = f"{status.cli_path}|{status.license_path}|{status.model}|{status.api_base}"
            if signature != self._connection_started_for_signature:
                self._connection_started_for_signature = signature
                QTimer.singleShot(120, self.start_connection_test)
                return

        if not status.license_path:
            self.summary_label.setText("라이선스 파일을 기다리는 중입니다.")
            self.detail_label.setText("열린 alira_license 폴더에 발급받은 *.lic 파일을 넣으면 자동으로 다음 단계를 확인합니다.")
        elif not status.cli_exists:
            self.summary_label.setText("라이선스 확인 완료 · 로컬 ALIRA CLI 준비가 필요합니다.")
            self.detail_label.setText("[ALIRA CLI 자동 설치]는 사용자의 확인 후 사내 공식 Windows 설치 스크립트를 실행합니다.")
        elif self.connection_worker is None and self.main_window.connection_state == "connected":
            self.summary_label.setText("ALIRA 연결 완료")
            self.detail_label.setText("Requirement Studio는 로컬 ALIRA CLI를 사용해 사내 원격 Qwen vLLM 서버에 연결합니다.")
        else:
            self.summary_label.setText("ALIRA 연결 구성을 확인하고 있습니다.")

    def confirm_and_install_cli(self):
        if self.install_worker is not None:
            return
        if default_cli_path().is_file():
            self.refresh_status()
            return
        answer = QMessageBox.question(
            self,
            "ALIRA CLI 자동 설치",
            "이 PC에서 ALIRA CLI를 찾지 못했습니다.\n\n"
            "사내 공식 Windows 설치 스크립트를 실행하여 로컬 ALIRA CLI를 설치할까요?\n"
            "실제 Qwen 모델은 설치하지 않으며 원격 vLLM 서버를 사용합니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.summary_label.setText("ALIRA CLI 자동 설치가 취소되었습니다.")
            return
        self.start_install_cli()

    def start_install_cli(self):
        self.install_button.setEnabled(False)
        self.summary_label.setText("ALIRA CLI 설치 중...")
        self.detail_label.setText("사내 공식 install.bat을 다운로드하여 실행하고 있습니다.")
        worker = TaskWorker(lambda: install_alira_cli_windows())
        self.install_worker = worker
        worker.signals.success.connect(self._on_install_success)
        worker.signals.error.connect(self._on_install_error)
        worker.signals.finished.connect(self._on_install_finished)
        self.thread_pool.start(worker)

    def _on_install_success(self, output: str):
        self.main_window._append_log("ALIRA CLI 자동 설치 완료")
        self.summary_label.setText("ALIRA CLI 설치 완료 · 연결 확인을 계속합니다.")
        self.detail_label.setText((output or "").strip()[-900:])

    def _on_install_error(self, error_text: str):
        self.summary_label.setText("ALIRA CLI 자동 설치 실패")
        self.detail_label.setText(error_text)
        self.main_window._append_log(f"ALIRA CLI 자동 설치 실패 · {error_text}")

    def _on_install_finished(self):
        self.install_worker = None
        self.install_button.setEnabled(True)
        QTimer.singleShot(250, self.refresh_status)

    def start_connection_test(self):
        if self.connection_worker is not None:
            return
        status = inspect_setup(self.project_root, self.main_window.provider_config.get("alira") or {})
        if not status.ready_for_test:
            self.refresh_status()
            return
        self.main_window._apply_alira_connection_config(status.license_path)
        provider = self.main_window.provider
        self._set_row("connection", None, "연결 요청 전송 중")
        self.summary_label.setText("사내 Qwen 연결을 확인하고 있습니다.")
        self.main_window._set_ai_connection_state("checking", "ALIRA 연결 설정에서 실제 최소 요청을 전송 중입니다.")
        worker = ConnectionTestWorker(provider)
        self.connection_worker = worker
        worker.signals.progress.connect(self._on_connection_progress)
        worker.signals.success.connect(self._on_connection_success)
        worker.signals.error.connect(self._on_connection_error)
        worker.signals.finished.connect(self._on_connection_finished)
        self.thread_pool.start(worker)

    def _on_connection_progress(self, percent: int, message: str):
        self._set_row("connection", None, message)

    def _on_connection_success(self, text: str):
        self._set_row("connection", True, "ALIRA / Qwen 연결 정상")
        self.summary_label.setText("ALIRA 연결 완료")
        self.detail_label.setText((text or "").strip()[-700:])
        self.main_window._set_ai_connection_state("connected", "ALIRA 연결 설정을 통해 실제 Qwen 요청이 정상 완료되었습니다.")
        self.main_window.connection_state_provider = "alira"
        self.main_window.connection_state_signature = self.main_window._provider_signature()
        self.main_window._append_log("ALIRA 연결 설정 완료 · 로컬 CLI + License + 원격 Qwen 연결 정상")
        self.main_window.refresh_all_checks()

    def _on_connection_error(self, error_text: str):
        self._set_row("connection", False, "연결 실패")
        self.summary_label.setText("ALIRA 연결 확인 실패")
        self.detail_label.setText(error_text)
        self.main_window._set_ai_connection_state("failed", error_text)
        self.main_window.connection_state_provider = "alira"
        self.main_window.connection_state_signature = None
        self.main_window._append_log(f"ALIRA 연결 설정 실패 · {error_text}")
        self.main_window.refresh_all_checks()

    def _on_connection_finished(self):
        self.connection_worker = None



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project_root = Path(__file__).resolve().parent
        self.documents = DocumentManager(self.project_root / "input")
        self.output_dir = self.project_root / "output"
        self.api_key_dir = self.project_root / "api_keys"
        self.alira_license_dir = project_license_dir(self.project_root)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.api_key_dir.mkdir(parents=True, exist_ok=True)
        self.alira_license_dir.mkdir(parents=True, exist_ok=True)

        self.thread_pool = QThreadPool.globalInstance()
        self.result_exporter = AnalysisResultExporter(self.output_dir)
        self.swe1_exporter = SWE1Exporter(self.output_dir)
        self.swe6_exporter = SWE6Exporter(self.output_dir)
        self.integrated_exporter = IntegratedExporter(self.output_dir)
        self.e2e_exporter = E2EExporter(self.output_dir)
        self.requirement_engine = RequirementEngine(self.project_root)
        self.review_exchange_builder = ReviewExchangeBuilder(self.project_root, app_version=APP_VERSION)
        self.document_normalizer = DocumentNormalizer(self.project_root)
        self.prompt_builder = PromptBuilder(self.project_root)
        self.provider_store = ProviderConfigStore(self.project_root)
        self.provider_config = self.provider_store.load()

        self.manual_api_key = ""
        self.custom_api_key = ""
        self.provider = None
        self.vision_provider = None
        self.job_runner = None
        self.connection_worker = None
        self.pipeline_worker = None
        self.evaluation_workers = []

        self.current_documents: list[Path] = []
        self.document_error = None
        self.operation_busy = False
        self.connection_state = "unchecked"
        self.connection_state_detail = "아직 연결 테스트를 실행하지 않았습니다."
        self.connection_state_provider = ""
        self.connection_state_signature = None
        self.current_stage = 0
        self.check_items: dict[str, dict] = {}

        self.last_analysis_text = ""
        self.last_analysis_document = None
        self.last_requirement_data = None
        self.last_requirement_evaluation = None
        self.last_analysis_output_path = None
        self.start_button_mode = "start"
        self.authoring_guide_dialog = None
        self.alira_setup_dialog = None
        self._copy_feedback_token = 0
        self.current_output_selection = {"swe1_word": True, "swe1_excel": True, "swe6_excel": True, "e2e_requirements_word": True, "e2e_requirements_excel": True, "e2e_evaluation_excel": True}
        self.quality_review_config = {}
        self.last_review_package_dir = None
        self.current_evaluation_run_dir = None

        self.setWindowTitle(APP_TITLE)
        icon_path = self.project_root / "assets" / "RequirementStudio.ico"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.resize(1200, 900)
        # V0.88: allow the dashboard to shrink meaningfully before falling back to
        # outer horizontal/vertical scrolling.
        self.setMinimumSize(720, 480)

        self.stop_button_timer = QTimer(self)
        self.stop_button_timer.setSingleShot(True)
        self.stop_button_timer.timeout.connect(self._arm_stop_button)

        self._build_ui()
        self.evaluation_status_timer = QTimer(self)
        self.evaluation_status_timer.setInterval(750)
        self.evaluation_status_timer.timeout.connect(self._refresh_automatic_evaluation_progress)
        self._reset_automatic_evaluation_progress("대기 중")
        self._apply_style()
        self._load_provider_controls()
        self._rebuild_provider(self._selected_provider_id(), save_selection=False)
        self._reset_stages()
        self.refresh_all_checks(initial=True)
        self._setup_filesystem_watchers()

    # UI -----------------------------------------------------------------
    def _build_ui(self):
        # The main window is a viewport over a bounded-responsive dashboard.
        # Cards may compress down to the readable logical minimum; below that,
        # Qt scroll bars protect labels/progress/result areas from destructive clipping.
        self.main_scroll_area = QScrollArea()
        self.main_scroll_area.setObjectName("mainScrollArea")
        self.main_scroll_area.setWidgetResizable(True)
        self.main_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.main_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.main_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.main_scroll_area.horizontalScrollBar().setObjectName("mainHorizontalScrollBar")
        self.main_scroll_area.verticalScrollBar().setObjectName("mainVerticalScrollBar")
        self.main_scroll_area.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setCentralWidget(self.main_scroll_area)

        self.dashboard_content = QWidget()
        self.dashboard_content.setObjectName("dashboardContent")
        # V0.88 logical canvas: smaller than V0.87 so the top cards can shrink
        # naturally; this remains the readability floor before horizontal scrolling.
        self.dashboard_content.setMinimumSize(1100, 820)
        self.main_scroll_area.setWidget(self.dashboard_content)

        layout = QVBoxLayout(self.dashboard_content)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)
        logo = QLabel()
        logo.setObjectName("logoHolder")
        logo.setFixedSize(48, 48)
        logo_path = self.project_root / "assets" / "RequirementStudio.png"
        if logo_path.is_file():
            pm = QPixmap(str(logo_path)).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo.setPixmap(pm)
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel(APP_TITLE)
        title.setObjectName("title")
        subtitle = QLabel("문서를 이해하고, 더 나은 요구사항으로")
        subtitle.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addWidget(logo)
        header.addLayout(title_box)
        header.addStretch()
        layout.addLayout(header)

        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(self._build_file_card(), 3)
        top.addWidget(self._build_ai_card(), 6)
        top.addWidget(self._build_execution_card(), 3)
        layout.addLayout(top)

        middle = QHBoxLayout()
        middle.setSpacing(14)
        middle.addWidget(self._build_pipeline_card(), 9)
        middle.addWidget(self._build_checklist_card(), 4)
        layout.addLayout(middle)

        # Result area: left tabs are visually attached to the result panel,
        # while utility actions float slightly above on the right.
        result_card = QWidget()
        result_card.setObjectName("resultArea")
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_layout.setSpacing(0)

        result_header = QWidget()
        result_header.setObjectName("resultHeader")
        result_header.setFixedHeight(48)
        result_header_layout = QHBoxLayout(result_header)
        result_header_layout.setContentsMargins(14, 0, 14, 0)
        result_header_layout.setSpacing(0)

        tab_group_widget = QWidget()
        tab_group_widget.setObjectName("resultTabGroup")
        tab_group_layout = QHBoxLayout(tab_group_widget)
        tab_group_layout.setContentsMargins(0, 10, 0, 0)
        tab_group_layout.setSpacing(0)

        self.result_tab_group = QButtonGroup(self)
        self.result_tab_group.setExclusive(True)
        self.result_tab_buttons = []
        result_tab_specs = [
            ("result_log.png", "진행 로그"),
            ("result_analysis.png", "문서 분석 결과"),
            ("result_requirements.png", "요구사항 후보"),
            ("result_analysis.png", "결과 품질 검토"),
        ]
        for index, (icon_name, label_text) in enumerate(result_tab_specs):
            button = QPushButton(label_text)
            button.setObjectName("resultTabButton")
            button.setCheckable(True)
            button.setFixedHeight(38)
            button.setMinimumWidth(150)
            icon_path = self.project_root / "assets" / icon_name
            if icon_path.is_file():
                button.setIcon(QIcon(str(icon_path)))
            button.clicked.connect(lambda checked=False, i=index: self._select_result_tab(i))
            self.result_tab_group.addButton(button, index)
            self.result_tab_buttons.append(button)
            tab_group_layout.addWidget(button)

        result_header_layout.addWidget(tab_group_widget, 0, Qt.AlignmentFlag.AlignBottom)
        result_header_layout.addStretch()

        result_actions = QWidget()
        result_actions.setObjectName("resultActions")
        action_row = QHBoxLayout(result_actions)
        action_row.setContentsMargins(0, 2, 0, 8)
        action_row.setSpacing(10)

        self.copy_log_button = QPushButton("로그 복사")
        self.copy_log_button.setObjectName("resultActionButton")
        copy_icon = self.project_root / "assets" / "action_copy.png"
        if copy_icon.is_file():
            self.copy_log_button.setIcon(QIcon(str(copy_icon)))
        self.copy_log_button.clicked.connect(self.copy_log)

        self.clear_log_button = QPushButton("로그 지우기")
        self.clear_log_button.setObjectName("resultActionButton")
        trash_icon = self.project_root / "assets" / "action_trash.png"
        if trash_icon.is_file():
            self.clear_log_button.setIcon(QIcon(str(trash_icon)))
        self.clear_log_button.clicked.connect(self.clear_log)

        self.open_output_button = QPushButton("output 폴더 열기")
        self.open_output_button.setObjectName("resultActionButton")
        folder_icon = self.project_root / "assets" / "action_folder.png"
        if folder_icon.is_file():
            self.open_output_button.setIcon(QIcon(str(folder_icon)))
        self.open_output_button.clicked.connect(self.open_output_folder)

        for btn in (self.copy_log_button, self.clear_log_button, self.open_output_button):
            btn.setFixedHeight(36)
            btn.setMinimumWidth(126)
            action_row.addWidget(btn)
        result_header_layout.addWidget(result_actions, 0, Qt.AlignmentFlag.AlignTop)
        result_layout.addWidget(result_header)

        result_content_frame = QFrame()
        result_content_frame.setObjectName("resultContentFrame")
        self.result_content_frame = result_content_frame
        self.result_tab_connector = QFrame(result_content_frame)
        self.result_tab_connector.setObjectName("resultTabConnector")
        self.result_tab_connector.setFixedHeight(3)
        self.result_tab_connector.raise_()
        result_content_layout = QVBoxLayout(result_content_frame)
        result_content_layout.setContentsMargins(0, 0, 0, 0)
        result_content_layout.setSpacing(0)

        self.log_box = ResultContentPane(
            self.project_root,
            "result_log.png",
            "분석 및 요구사항 추출 실행 후 로그가 여기에 표시됩니다.",
            "진행 상황은 실시간으로 업데이트됩니다.",
        )
        self.response_box = ResultContentPane(
            self.project_root,
            "result_analysis.png",
            "문서 분석 결과가 여기에 표시됩니다.",
            "분석이 완료되면 문서별 요약, 주요 내용, 추출 결과가 표시됩니다.",
        )
        self.requirement_result_box = ResultContentPane(
            self.project_root,
            "result_requirements.png",
            "요구사항 후보가 여기에 표시됩니다.",
            "AI가 추출한 요구사항 후보와 구조화된 평가 결과가 표시됩니다.",
        )
        self.quality_review_box = self._build_quality_review_box()

        self.result_stack = QStackedWidget()
        self.result_stack.setObjectName("resultStack")
        self.result_stack.addWidget(self.log_box)
        self.result_stack.addWidget(self.response_box)
        self.result_stack.addWidget(self.requirement_result_box)
        self.result_stack.addWidget(self.quality_review_box)
        result_content_layout.addWidget(self.result_stack, 1)
        result_layout.addWidget(result_content_frame, 1)
        layout.addWidget(result_card, 1)
        self._select_result_tab(0)

        footer = QHBoxLayout()
        self.status_label = QLabel("준비")
        self.status_label.setObjectName("footerText")
        self.log_status_label = QLabel("대기 중")
        self.log_status_label.setObjectName("footerText")
        self.footer_provider_label = QLabel("")
        self.footer_provider_label.setObjectName("footerText")
        footer.addWidget(self.status_label)
        footer.addStretch()
        footer.addWidget(self.log_status_label)
        footer.addSpacing(14)
        footer.addWidget(self.footer_provider_label)
        layout.addLayout(footer)


    def _fixed_evaluation_reviewers(self) -> list[dict]:
        hchat = self.provider_config.get("hchat", {}) if isinstance(self.provider_config, dict) else {}
        eval_cfg = {}
        try:
            cfg_path = self.project_root / "config" / "evaluation_api_config.json"
            if cfg_path.is_file():
                eval_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            eval_cfg = {}
        transport = str(eval_cfg.get("transport") or "hchat").lower()
        providers = eval_cfg.get("providers") or {}
        rows = []
        for index, provider in enumerate(("gpt", "gemini", "claude"), start=1):
            pcfg = providers.get(provider) or {}
            enabled = bool(pcfg.get("enabled", True))
            if transport == "direct":
                defaults = {"gpt": "gpt-6.1-sol", "gemini": "gemini-3.8-flash", "claude": "claude-sonnet-5-5"}
                model = str(pcfg.get("direct_model") or defaults[provider])
            else:
                defaults = {"gpt": "gpt-5.6-terra", "gemini": "gemini-3.7-flash", "claude": "claude-sonnet-5"}
                model = str(hchat.get(f"{provider}_model") or defaults[provider])
            rows.append({"index": index, "provider": provider, "model": model, "enabled": enabled, "transport": transport})
        return rows

    def _build_quality_review_box(self):
        pane = QFrame()
        pane.setObjectName("resultContentPane")
        root = QVBoxLayout(pane)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("AI 품질 평가")
        title.setObjectName("cardTitle")
        header.addWidget(title)
        header.addStretch()

        self.review_reset_button = QPushButton("기본값")
        self.review_reset_button.setObjectName("detailButton")
        self.review_reset_button.setToolTip("평가 모드와 평가 산출물을 추천 기본값으로 되돌립니다.")
        self.review_reset_button.clicked.connect(self._reset_quality_review_defaults)
        header.addWidget(self.review_reset_button)

        self.import_baseline_button = QPushButton("Gold Source 추가")
        self.import_baseline_button.setObjectName("outlinePrimaryButton")
        self.import_baseline_button.setToolTip("승인된 Review Package를 Gold Source Contract로 등록합니다.")
        self.import_baseline_button.setMinimumWidth(130)
        self.import_baseline_button.setFixedHeight(32)
        self.import_baseline_button.clicked.connect(self.import_gold_source_package)
        header.addWidget(self.import_baseline_button)

        self.open_review_package_button = QPushButton("AI 평가 패키지 열기")
        self.open_review_package_button.setObjectName("outlinePrimaryButton")
        self.open_review_package_button.setToolTip("가장 최근 생성된 Review Exchange / 자동평가 결과 폴더를 엽니다.")
        self.open_review_package_button.setMinimumWidth(145)
        self.open_review_package_button.setFixedHeight(32)
        self.open_review_package_button.clicked.connect(self.open_review_package_folder)
        header.addWidget(self.open_review_package_button)
        root.addLayout(header)

        selector_row = QHBoxLayout()
        selector_row.setSpacing(10)

        mode_card = self._make_card()
        mode_layout = QVBoxLayout(mode_card)
        mode_layout.setContentsMargins(12, 10, 12, 10)
        mode_layout.setSpacing(5)
        mode_title = QLabel("평가 모드")
        mode_title.setObjectName("sectionTitle")
        mode_layout.addWidget(mode_title)
        self.review_mode_group = QButtonGroup(self)
        self.review_mode_auto = QRadioButton("3-AI 자동 평가 (추천)")
        self.review_mode_auto.setToolTip("GPT/Gemini/Claude가 동일 Evidence를 독립 평가하고 결과를 자동 수렴합니다.")
        self.review_mode_manual = QRadioButton("수동 평가 패키지만 생성")
        self.review_mode_manual.setToolTip("Review Package까지만 생성하고 AI Reviewer 호출은 하지 않습니다.")
        self.review_mode_none = QRadioButton("평가하지 않음")
        self.review_mode_none.setToolTip("Review Exchange와 자동평가를 생략합니다.")
        for idx, btn in enumerate((self.review_mode_auto, self.review_mode_manual, self.review_mode_none)):
            self.review_mode_group.addButton(btn, idx)
            btn.toggled.connect(self._update_quality_review_ui_state)
            mode_layout.addWidget(btn)
        self.review_mode_auto.setChecked(True)
        selector_row.addWidget(mode_card, 1)

        artifact_card = self._make_card()
        artifact_layout = QVBoxLayout(artifact_card)
        artifact_layout.setContentsMargins(12, 10, 12, 10)
        artifact_layout.setSpacing(5)
        artifact_title = QLabel("평가 산출물")
        artifact_title.setObjectName("sectionTitle")
        artifact_layout.addWidget(artifact_title)
        self.review_artifact_unified = QRadioButton("통합 E2E 평가 (요구사항 + 평가 명세서, 추천)")
        self.review_artifact_unified.setToolTip("SWE.1/SWE.6 + E2E 요구사항 Word/Excel + E2E 평가 Excel 전체를 함께 평가합니다.")
        self.review_artifact_swe1 = QRadioButton("SWE.1 중심 평가 (디버깅용)")
        self.review_artifact_swe1.setToolTip("SWE.1 Word/Excel 중심의 빠른 디버깅 평가입니다.")
        self.review_artifact_swe6 = QRadioButton("SWE.6 중심 평가 (디버깅용)")
        self.review_artifact_swe6.setToolTip("SWE.6 Excel 중심의 빠른 디버깅 평가입니다.")
        self.review_artifact_unified.setChecked(True)
        for btn in (self.review_artifact_unified, self.review_artifact_swe1, self.review_artifact_swe6):
            btn.toggled.connect(self._update_quality_review_ui_state)
            artifact_layout.addWidget(btn)
        selector_row.addWidget(artifact_card, 2)
        root.addLayout(selector_row)

        progress_card = self._make_card()
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(12, 9, 12, 9)
        progress_layout.setSpacing(5)
        progress_head = QHBoxLayout()
        progress_title = QLabel("자동 평가 진행 상황")
        # Legacy regression token: QLabel("자동 평가 진행상황")
        progress_title.setObjectName("sectionTitle")
        progress_head.addWidget(progress_title)
        progress_head.addStretch()
        self.eval_progress_state_label = QLabel("대기 중")
        self.eval_progress_state_label.setObjectName("smallMuted")
        progress_head.addWidget(self.eval_progress_state_label)
        progress_layout.addLayout(progress_head)

        self.eval_progress_stage_label = QLabel("")
        self.eval_progress_stage_label.setObjectName("smallMuted")
        self.eval_progress_stage_label.setWordWrap(True)
        self.eval_progress_stage_label.setVisible(False)
        progress_layout.addWidget(self.eval_progress_stage_label)

        self.eval_progress_bar = QProgressBar()
        self.eval_progress_bar.setRange(0, 100)
        self.eval_progress_bar.setValue(0)
        self.eval_progress_bar.setFormat("자동 평가 %p%")
        progress_layout.addWidget(self.eval_progress_bar)

        reviewer_row = QHBoxLayout()
        reviewer_row.setSpacing(18)
        self.eval_provider_progress_labels = {}
        for provider in ("gpt", "gemini", "claude"):
            block = QVBoxLayout()
            block.setSpacing(1)
            name = QLabel(provider.upper())
            name.setObjectName("fieldLabel")
            state = QLabel("○ 대기")
            state.setObjectName("smallMuted")
            block.addWidget(name)
            block.addWidget(state)
            reviewer_row.addLayout(block, 1)
            self.eval_provider_progress_labels[provider] = state

        self.open_final_result_button = QPushButton("평가 진행 결과 열기")
        self.open_final_result_button.setObjectName("detailButton")
        self.open_final_result_button.setMinimumWidth(145)
        self.open_final_result_button.setEnabled(False)
        self.open_final_result_button.clicked.connect(self._open_current_final_result_folder)
        reviewer_row.addWidget(self.open_final_result_button, 0, Qt.AlignmentFlag.AlignBottom)
        progress_layout.addLayout(reviewer_row)

        # Keep gate/final status objects for backend status updates without adding UI clutter.
        self.eval_gate_summary_label = QLabel("")
        self.eval_gate_summary_label.setVisible(False)
        self.eval_final_result_label = QLabel("")
        self.eval_final_result_label.setVisible(False)
        root.addWidget(progress_card)

        self._reset_quality_review_defaults(initial=True)
        return pane

    def _reset_quality_review_defaults(self, checked: bool = False, initial: bool = False):
        self.review_mode_auto.setChecked(True)
        self.review_artifact_unified.setChecked(True)
        self._update_quality_review_ui_state()
        if (not initial) and hasattr(self, "status_label"):
            self.status_label.setText("AI 품질 평가 설정을 기본값으로 되돌렸습니다.")

    def _selected_review_mode_id(self) -> str:
        if self.review_mode_none.isChecked():
            return "none"
        if self.review_mode_manual.isChecked():
            return "manual"
        return "auto"

    def _collect_quality_review_config(self) -> dict:
        mode = self._selected_review_mode_id()
        reviewers = []
        if mode == "auto":
            reviewers = self._fixed_evaluation_reviewers()
        criteria = [
            "원문 충실성 (Source Fidelity)",
            "완전성 (Completeness)",
            "원자성 (Atomicity)",
            "추적성 (Traceability)",
            "검증 가능성 (Verifiability)",
            "산출물 간 일관성 (Consistency)",
        ]
        return {
            "enabled": mode != "none",
            "mode": mode,
            "scope": "all",
            "evaluation_artifact": ("unified" if self.review_artifact_unified.isChecked() else ("swe6" if self.review_artifact_swe6.isChecked() else "swe1")),
            "selected_outputs": dict(getattr(self, "current_output_selection", {}) or {}),
            "reviewers": reviewers,
            "criteria": criteria,
            "auto_evaluation": mode == "auto",
            "legacy_multi_reviewer_ui_removed": True,
        }

    def _update_quality_review_ui_state(self):
        mode = self._selected_review_mode_id()
        review_enabled = mode != "none"
        self.review_artifact_unified.setEnabled(review_enabled)
        self.review_artifact_swe1.setEnabled(review_enabled)
        self.review_artifact_swe6.setEnabled(review_enabled)
        if hasattr(self, "review_reset_button"):
            self.review_reset_button.setEnabled(True)
        self.quality_review_config = self._collect_quality_review_config()

    def _reset_automatic_evaluation_progress(self, message: str = "대기 중"):
        if hasattr(self, "eval_progress_bar"):
            self.eval_progress_bar.setValue(0)
        if hasattr(self, "eval_progress_state_label"):
            self.eval_progress_state_label.setText(message)
        if hasattr(self, "eval_progress_stage_label"):
            self.eval_progress_stage_label.setText("STEP 7 이후 자동평가가 시작되면 Unified Evidence → 3-AI → Consensus → Completeness Audit → Final Result → 파일 검증 순서로 표시됩니다.")
        for provider, label in getattr(self, "eval_provider_progress_labels", {}).items():
            label.setText("○ 대기")
        if hasattr(self, "eval_gate_summary_label"):
            self.eval_gate_summary_label.setText("Tool Quality: -  ·  Artifact Readiness: -  ·  Official Release: -")
        if hasattr(self, "eval_final_result_label"):
            self.eval_final_result_label.setText("Final Result: 아직 생성되지 않음")
        if hasattr(self, "open_final_result_button"):
            self.open_final_result_button.setEnabled(False)

    @staticmethod
    def _evaluation_stage_text(stage: str) -> str:
        return {
            "BUILD_EVIDENCE": "Evidence Package 생성 중",
            "PROVIDER_REVIEW": "GPT / Gemini / Claude 독립 평가 진행 중",
            "CONSENSUS": "3개 Reviewer 결과 Consensus 정리 중",
            "FINAL_RESULT": "최종 종합 결과/Completeness Audit 및 110줄 분할 파일 생성 중",
            "OUTPUT_VERIFY": "생성 파일 존재/크기/Manifest 검증 중",
            "OUTPUT_VERIFIED": "자동 평가 완료 · 결과 파일 검증 완료",
            "ERROR": "자동 평가 실패",
        }.get(str(stage or "").upper(), str(stage or "상태 확인 중"))

    @staticmethod
    def _evaluation_provider_text(state: str) -> str:
        return {
            "WAITING": "○ 대기",
            "RUNNING": "… 진행 중",
            "COMPLETED": "✓ 완료",
            "FAILED": "✕ 실패",
            "DISABLED": "— 비활성",
            "UNKNOWN": "? 확인 필요",
        }.get(str(state or "UNKNOWN").upper(), str(state or "?"))

    def _apply_automatic_evaluation_status(self, data: dict):
        status = str(data.get("status") or "").upper()
        stage = str(data.get("stage") or "")
        progress = max(0, min(100, int(data.get("progress_percent") or 0)))
        if hasattr(self, "eval_progress_bar"):
            self.eval_progress_bar.setValue(progress)
        if hasattr(self, "eval_progress_state_label"):
            state_text = {"RUNNING": "진행 중", "COMPLETED": "완료", "FAILED": "실패"}.get(status, status or "상태 확인 중")
            self.eval_progress_state_label.setText(f"{state_text} · {progress}%")
        if hasattr(self, "eval_progress_stage_label"):
            message = str(data.get("message") or "").strip()
            stage_text = self._evaluation_stage_text(stage)
            self.eval_progress_stage_label.setText(stage_text + (f" · {message}" if message and message not in stage_text else ""))
        provider_status = data.get("provider_status") or {}
        completed = set(data.get("providers_completed") or [])
        failures = data.get("provider_failures") or {}
        requested = set(data.get("providers_requested") or [])
        for provider, label in getattr(self, "eval_provider_progress_labels", {}).items():
            p_state = str(provider_status.get(provider) or "")
            if not p_state:
                if provider in completed:
                    p_state = "COMPLETED"
                elif provider in failures:
                    p_state = "FAILED"
                elif requested:
                    p_state = "RUNNING" if provider in requested else "DISABLED"
                else:
                    p_state = "WAITING"
            label.setText(self._evaluation_provider_text(p_state))
        tool_gate = data.get("tool_quality_gate") or "-"
        artifact_gate = data.get("artifact_readiness_gate") or "-"
        release_gate = data.get("official_release") or "-"
        if hasattr(self, "eval_gate_summary_label"):
            self.eval_gate_summary_label.setText(f"Tool Quality: {tool_gate}  ·  Artifact Readiness: {artifact_gate}  ·  Official Release: {release_gate}")
        part_count = int(data.get("final_result_part_count") or ((data.get("verification") or {}).get("final_result_part_count") or 0))
        if hasattr(self, "eval_final_result_label"):
            if part_count > 0:
                self.eval_final_result_label.setText(f"Final Result: {part_count}개 TXT part 생성 완료 · 각 최대 110줄")
            elif status == "COMPLETED":
                self.eval_final_result_label.setText("Final Result: 완료 상태이나 part 수 확인 필요")
            else:
                self.eval_final_result_label.setText("Final Result: 생성 대기 중")
        final_dir = None
        if self.current_evaluation_run_dir:
            final_dir = Path(self.current_evaluation_run_dir) / "automatic_evaluation" / "final_result"
        if hasattr(self, "open_final_result_button"):
            self.open_final_result_button.setEnabled(bool(final_dir and final_dir.is_dir() and any(final_dir.glob("FINAL_RESULT_*.txt"))))
        if status in {"COMPLETED", "FAILED"} and hasattr(self, "evaluation_status_timer"):
            self.evaluation_status_timer.stop()

    def _refresh_automatic_evaluation_progress(self):
        if not self.current_evaluation_run_dir:
            return
        status_path = Path(self.current_evaluation_run_dir) / "automatic_evaluation" / "00_EVALUATION_STATUS.json"
        if not status_path.is_file():
            if hasattr(self, "eval_progress_state_label"):
                self.eval_progress_state_label.setText("시작 준비 · 1%")
            if hasattr(self, "eval_progress_bar"):
                self.eval_progress_bar.setValue(1)
            if hasattr(self, "eval_progress_stage_label"):
                self.eval_progress_stage_label.setText("자동평가 Worker 시작 및 상태 파일 생성 대기 중")
            return
        try:
            data = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception as exc:
            if hasattr(self, "eval_progress_stage_label"):
                self.eval_progress_stage_label.setText(f"상태 파일 읽기 재시도 중 · {exc}")
            return
        self._apply_automatic_evaluation_status(data)

    def _open_current_final_result_folder(self):
        if not self.current_evaluation_run_dir:
            return
        folder = Path(self.current_evaluation_run_dir) / "automatic_evaluation" / "final_result"
        if folder.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _build_file_card(self):
        card = self._make_card()
        # Preserve the pre-load card footprint after the ready-state labels change.
        card.setMinimumWidth(270)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        icon = self._section_icon("section_folder.png")
        title = QLabel("파일 및 옵션 설정")
        title.setObjectName("cardTitle")
        title_row.addWidget(icon)
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        self.drop_zone = FileDropZone()
        self.drop_zone.filesSelected.connect(self.import_input_files)
        layout.addWidget(self.drop_zone, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.open_input_button = QPushButton("입력 폴더 열기")
        self.open_input_button.setObjectName("secondaryButton")
        self.open_input_button.clicked.connect(self.open_input_folder)
        self.refresh_button = QPushButton("새로고침")
        self.refresh_button.setObjectName("secondaryButton")
        self.refresh_button.clicked.connect(self.refresh_all_checks)
        buttons.addWidget(self.open_input_button)
        buttons.addWidget(self.refresh_button)
        layout.addLayout(buttons)
        return card

    def _section_icon(self, asset_name: str) -> QLabel:
        label = QLabel()
        label.setObjectName("sectionIcon")
        label.setFixedSize(26, 26)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_path = self.project_root / "assets" / asset_name
        if icon_path.is_file():
            pm = QPixmap(str(icon_path)).scaled(
                22,
                22,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            label.setPixmap(pm)
        return label

    def _help_label(self, tooltip: str) -> QLabel:
        label = QLabel("?")
        label.setObjectName("helpIcon")
        label.setToolTip(tooltip)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(17, 17)
        return label

    def _provider_option(self, radio: QRadioButton, description: str) -> QWidget:
        # Legacy helper retained for compatibility; provider descriptions are no longer shown.
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(radio)
        return wrap

    def _build_ai_card(self):
        card = self._make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # V0.43 final layout: keep the header compact and let unused vertical
        # space fall below the content instead of stretching the status badge.
        header = QHBoxLayout()
        header.setSpacing(8)
        icon = self._section_icon("section_gear.png")
        title = QLabel("AI 설정")
        title.setObjectName("cardTitle")
        header.addWidget(icon)
        header.addWidget(title)
        header.addStretch()
        self.ai_status_label = QLabel("● AI 연결 확인 전")
        self.ai_status_label.setObjectName("aiStatus")
        self.ai_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ai_status_label.setFixedHeight(34)
        self.ai_status_label.setMinimumWidth(118)
        self.ai_status_label.setMaximumWidth(150)
        self.ai_status_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header.addWidget(self.ai_status_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(14)

        provider_grid = QGridLayout()
        provider_grid.setHorizontalSpacing(10)
        provider_grid.setVerticalSpacing(10)

        engine_label = QLabel("AI Engine")
        engine_label.setObjectName("fieldLabel")
        provider_grid.addWidget(engine_label, 0, 0)

        self.provider_button_group = QButtonGroup(self)
        self.radio_gpt = QRadioButton("GPT")
        self.radio_gpt.setToolTip("GPT (H-Chat)")
        self.radio_gemini = QRadioButton("Gemini")
        self.radio_gemini.setToolTip("Gemini (H-Chat)")
        self.radio_claude = QRadioButton("Claude")
        self.radio_claude.setToolTip("Claude (H-Chat) · 연결 상세는 config에서 교체 가능")
        self.radio_alira = QRadioButton("ALIRA")
        self.radio_custom = QRadioButton("기타")
        self.radio_custom.setToolTip("외부/사내 Custom API")
        for idx, btn in enumerate((self.radio_gpt, self.radio_gemini, self.radio_claude, self.radio_alira, self.radio_custom)):
            self.provider_button_group.addButton(btn, idx)
            btn.toggled.connect(self._on_provider_radio_changed)
            btn.setMinimumHeight(26)

        # V0.88 responsive provider selector: keep the common engines on the
        # first line and move ALIRA/Custom to a second line.  This reduces the
        # AI card's horizontal size hint and lets the whole dashboard shrink
        # without hiding providers or forcing a wide fixed canvas.
        provider_row_primary = QHBoxLayout()
        provider_row_primary.setSpacing(12)
        provider_row_primary.addWidget(self.radio_gpt)
        provider_row_primary.addWidget(self.radio_gemini)
        provider_row_primary.addWidget(self.radio_claude)
        provider_row_primary.addStretch()
        provider_grid.addLayout(provider_row_primary, 0, 1)

        provider_row_secondary = QHBoxLayout()
        provider_row_secondary.setSpacing(12)
        provider_row_secondary.addWidget(self.radio_alira)
        provider_row_secondary.addWidget(self.radio_custom)
        provider_row_secondary.addStretch()
        provider_grid.addLayout(provider_row_secondary, 1, 1)

        # The second provider row already provides visual separation, so the
        # old 28px fixed spacer is replaced by a compact responsive gap.
        spacer = QWidget()
        spacer.setFixedHeight(8)
        provider_grid.addWidget(spacer, 2, 0, 1, 2)

        model_label = QLabel("Model")
        model_label.setObjectName("fieldLabel")
        provider_grid.addWidget(model_label, 3, 0)
        self.provider_model_combo = QComboBox()
        self.provider_model_combo.setObjectName("modelCombo")
        self.provider_model_combo.setMinimumWidth(172)
        self.provider_model_combo.setMaximumWidth(360)
        self.provider_model_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.provider_model_combo.currentIndexChanged.connect(self._on_provider_model_changed)
        provider_grid.addWidget(self.provider_model_combo, 3, 1)

        api_label = QLabel("API Key")
        api_label.setObjectName("fieldLabel")
        provider_grid.addWidget(api_label, 4, 0)
        self.api_key_field = QLineEdit()
        self.api_key_field.setReadOnly(True)
        self.api_key_field.setObjectName("apiKeyField")
        self.api_key_field.setMinimumWidth(172)
        self.api_key_field.setMaximumWidth(360)
        self.api_key_field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.api_key_field.setPlaceholderText("API Key를 입력하세요.")
        provider_grid.addWidget(self.api_key_field, 4, 1)
        provider_grid.setColumnStretch(1, 1)
        body.addLayout(provider_grid, 1)

        self.ai_engine_value = QLabel("-")
        self.ai_engine_value.setVisible(False)

        action_panel = QWidget()
        action_panel.setObjectName("providerActionPanel")
        action_col = QVBoxLayout(action_panel)
        action_col.setSpacing(8)
        action_col.setContentsMargins(0, 0, 0, 0)
        action_col.addStretch(1)
        self.api_key_folder_button = QPushButton("API Key 폴더 열기")
        self.api_key_folder_button.setObjectName("secondaryButton")
        self.api_key_folder_button.clicked.connect(self._on_provider_action_primary)
        self.api_key_manual_button = QPushButton("API Key 수동 입력")
        self.api_key_manual_button.setObjectName("secondaryButton")
        self.api_key_manual_button.clicked.connect(self._on_provider_action_secondary)
        self.connection_test_button = QPushButton("AI 연결 테스트")
        self.connection_test_button.setObjectName("outlinePrimaryButton")
        self.connection_test_button.clicked.connect(self.run_connection_test)
        for btn in (self.api_key_folder_button, self.api_key_manual_button, self.connection_test_button):
            btn.setMinimumHeight(38)
            btn.setMinimumWidth(132)
            btn.setMaximumWidth(152)
            action_col.addWidget(btn)
        action_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        body.addWidget(action_panel, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(body)

        # Critical: absorb any extra card height below the content.  Without this
        # stretch Qt can expand the header row and make the connection badge tall.
        layout.addStretch(1)
        return card


    def _build_execution_card(self):
        card = self._make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(7)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self._section_icon("section_check.png"))
        title = QLabel("실행")
        title.setObjectName("cardTitle")
        header.addWidget(title)
        header.addStretch()
        self.authoring_guide_button = QPushButton("작성 기준 보기")
        self.authoring_guide_button.setObjectName("runGuideButton")
        self.authoring_guide_button.setToolTip("SWE.1/SWE.6 및 V0.88 E2E 요구사항/E2E 평가 산출물의 작성 기준을 확인합니다.")
        self.authoring_guide_button.clicked.connect(self.show_authoring_guide)
        self.authoring_guide_button.setFixedHeight(30)
        header.addWidget(self.authoring_guide_button)
        layout.addLayout(header)

        # V0.88: four human-facing output choices. Bundled choices still map to the
        # legacy individual Word/Excel flags internally to preserve exporter contracts.
        self.output_swe1_word = QCheckBox("SWE.1 문서 (Word 파일 & 엑셀 양식)")
        self.output_swe1_excel = self.output_swe1_word
        self.output_swe6_excel = QCheckBox("SWE.6 문서 (엑셀 양식)")
        self.output_e2e_requirements_word = QCheckBox("E2E 요구사항 명세서 (Word 파일 & 엑셀 양식)")
        self.output_e2e_requirements_excel = self.output_e2e_requirements_word
        self.output_e2e_evaluation = QCheckBox("E2E 평가 명세서 (엑셀 양식)")
        self.output_choice_widgets = (
            self.output_swe1_word,
            self.output_swe6_excel,
            self.output_e2e_requirements_word,
            self.output_e2e_evaluation,
        )
        for check in self.output_choice_widgets:
            check.setObjectName("outputChoice")
            check.setMinimumHeight(24)
            check.setChecked(True)
            layout.addWidget(check)

        self.start_button = QPushButton("분석 및 요구사항\n추출 시작")
        self.start_button.setObjectName("primaryButton")
        self.start_button.setMinimumHeight(42)
        self.start_button.setMaximumHeight(46)
        self.start_button.clicked.connect(self._on_start_stop_clicked)
        layout.addWidget(self.start_button)
        return card

    def show_authoring_guide(self):
        guide_path = self.project_root / "reference" / "OUTPUT_AUTHORING_GUIDE.md"
        swe6_guide_path = self.project_root / "reference" / "SWE6_AUTHORING_GUIDE.md"
        if self.authoring_guide_dialog is None:
            self.authoring_guide_dialog = AuthoringGuideDialog(guide_path, self, swe6_guide_path)
        else:
            self.authoring_guide_dialog.reload_guide()
        self.authoring_guide_dialog.show()
        self.authoring_guide_dialog.raise_()
        self.authoring_guide_dialog.activateWindow()

    def _selected_output_ui_labels(self) -> list[str]:
        labels = []
        if self.output_swe1_word.isChecked():
            labels.append("SWE.1 Word+Excel")
        if self.output_swe6_excel.isChecked():
            labels.append("SWE.6 Excel")
        if self.output_e2e_requirements_word.isChecked():
            labels.append("E2E 요구사항 Word+Excel")
        if self.output_e2e_evaluation.isChecked():
            labels.append("E2E 평가 Excel")
        return labels

    def _create_step_widget(self, no: int, title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("stepCard")
        frame.setMinimumWidth(92)
        frame.setMinimumHeight(78)
        frame.setMaximumHeight(78)

        col = QVBoxLayout(frame)
        col.setContentsMargins(8, 6, 8, 6)
        col.setSpacing(1)
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("○")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(20, 20)

        step = QLabel(f"STEP {no}")
        step.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step.setObjectName("stepNumber")

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        title_label.setObjectName("stepTitle")

        status = QLabel("대기")
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setObjectName("stepStatus")

        col.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)
        col.addWidget(step)
        col.addWidget(title_label)
        col.addWidget(status)

        self.step_widgets[no] = {
            "frame": frame,
            "icon": icon,
            "step": step,
            "title": title_label,
            "status": status,
        }
        return frame

    def _build_pipeline_card(self):
        card = self._make_card()
        card.setFixedHeight(228)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        icon = self._section_icon("section_list.png")
        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title = QLabel("분석 진행 상황")
        title.setObjectName("cardTitle")
        subtitle = QLabel("문서 분석 및 요구사항 추출이 진행되는 단계를 확인합니다.")
        subtitle.setObjectName("smallMuted")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        title_row.addWidget(icon)
        title_row.addLayout(title_col)
        title_row.addStretch()
        layout.addLayout(title_row)

        step_grid = QGridLayout()
        step_grid.setContentsMargins(0, 0, 0, 0)
        step_grid.setHorizontalSpacing(7)
        step_grid.setVerticalSpacing(0)
        self.step_widgets = {}
        for no in range(1, 8):
            step_col = (no - 1) * 2
            frame = self._create_step_widget(no, STEP_UI_TITLES[no])
            step_grid.addWidget(frame, 0, step_col)
            step_grid.setColumnStretch(step_col, 1)
            if no < 7:
                arrow_col = step_col + 1
                arrow = QLabel("›")
                arrow.setObjectName("stepArrow")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                arrow.setFixedWidth(16)
                step_grid.addWidget(arrow, 0, arrow_col, alignment=Qt.AlignmentFlag.AlignCenter)
                step_grid.setColumnMinimumWidth(arrow_col, 16)
                step_grid.setColumnStretch(arrow_col, 0)
        layout.addLayout(step_grid)

        progress_grid = QGridLayout()
        progress_grid.setHorizontalSpacing(10)
        progress_grid.setVerticalSpacing(7)
        self.overall_progress_label = QLabel("전체 진행률")
        self.overall_progress_label.setObjectName("progressLabel")
        self.current_progress_label = QLabel("현재 단계 상태")
        self.current_progress_label.setObjectName("progressLabel")
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 100)
        self.overall_progress.setValue(0)
        self.overall_progress.setFormat("%p%")
        self.overall_progress.setObjectName("overallProgress")

        self.current_status_panel = QFrame()
        self.current_status_panel.setObjectName("currentStatusPanel")
        current_status_layout = QHBoxLayout(self.current_status_panel)
        current_status_layout.setContentsMargins(14, 0, 14, 0)
        current_status_layout.setSpacing(10)
        self.current_status_text = QLabel("대기 중")
        self.current_status_text.setObjectName("currentStatusText")
        self.current_status_text.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.current_loading_dots = LoadingDotsIndicator()
        self.current_loading_dots.stop()
        current_status_layout.addWidget(self.current_status_text, 1)
        current_status_layout.addWidget(self.current_loading_dots, 0, alignment=Qt.AlignmentFlag.AlignVCenter)

        progress_grid.addWidget(self.overall_progress_label, 0, 0)
        progress_grid.addWidget(self.overall_progress, 0, 1)
        progress_grid.addWidget(self.current_progress_label, 1, 0)
        progress_grid.addWidget(self.current_status_panel, 1, 1)
        progress_grid.setColumnStretch(1, 1)
        layout.addLayout(progress_grid)

        return card

    def _build_checklist_card(self):
        card = self._make_card()
        card.setFixedHeight(228)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(7)

        title_row = QHBoxLayout()
        icon = self._section_icon("section_check.png")
        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title = QLabel("필수 항목 확인")
        title.setObjectName("cardTitle")
        subtitle = QLabel("분석을 위해 다음 항목들이 모두 준비되어야 합니다.")
        subtitle.setObjectName("smallMuted")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        title_row.addWidget(icon)
        title_row.addLayout(title_col)
        title_row.addStretch()
        layout.addLayout(title_row)

        self.check_rows = {}
        self.checklist_scroll = QScrollArea()
        self.checklist_scroll.setObjectName("checklistScrollArea")
        self.checklist_scroll.setWidgetResizable(True)
        self.checklist_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.checklist_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.checklist_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.checklist_scroll.verticalScrollBar().setObjectName("checklistVerticalScrollBar")

        checklist_content = QWidget()
        checklist_content.setObjectName("checklistScrollContent")
        checklist_layout = QVBoxLayout(checklist_content)
        checklist_layout.setContentsMargins(0, 0, 3, 0)
        checklist_layout.setSpacing(4)

        check_specs = (
            ("입력 문서", "▧"),
            ("AI Provider", "⚙"),
            ("Model", "◇"),
            ("API Key / 실행환경", "⌕"),
            ("AI 연결", "↔"),
            ("출력 폴더", "□"),
            ("내부 설정", "⚙"),
        )
        for name, icon_text in check_specs:
            row_frame = QFrame()
            row_frame.setObjectName("checkRow")
            row_frame.setMinimumHeight(32)
            row = QHBoxLayout(row_frame)
            row.setContentsMargins(8, 4, 8, 4)
            row.setSpacing(7)
            icon_label = QLabel(icon_text)
            icon_label.setObjectName("checkItemIcon")
            icon_label.setFixedWidth(18)
            name_label = QLabel(name)
            name_label.setObjectName("checkName")
            status = QLabel("미확인")
            status.setObjectName("checkStatus")
            status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status.setMinimumWidth(64)
            row.addWidget(icon_label)
            row.addWidget(name_label)
            row.addStretch()
            row.addWidget(status)
            checklist_layout.addWidget(row_frame)
            self.check_rows[name] = status

        checklist_layout.addStretch()
        self.checklist_scroll.setWidget(checklist_content)
        layout.addWidget(self.checklist_scroll, 1)

        bottom = QHBoxLayout()
        bottom.addStretch()
        self.detail_reason_button = QPushButton("상세 원인 확인")
        self.detail_reason_button.setObjectName("detailButton")
        self.detail_reason_button.clicked.connect(self.show_checklist_details)
        bottom.addWidget(self.detail_reason_button)
        layout.addLayout(bottom)
        return card

    def _make_card(self):
        card = QFrame()
        card.setObjectName("card")
        return card

    # Styling -------------------------------------------------------------
    def _apply_style(self):
        dropdown_arrow = (self.project_root / "assets" / "dropdown_arrow.png").as_posix()
        style = """
            QMainWindow { background:#F5F7FB; }
            QWidget#dashboardContent { background:#F5F7FB; }
            QScrollArea#mainScrollArea { background:#F5F7FB; border:none; }
            QScrollArea#mainScrollArea > QWidget > QWidget { background:#F5F7FB; }

            /* Main viewport scrollbars: intentionally large and easy to drag. */
            QScrollBar#mainVerticalScrollBar {
                background:#E8EDF4; width:18px; margin:0; border:none;
            }
            QScrollBar#mainVerticalScrollBar::handle {
                background:#8193AA; min-height:64px; border-radius:8px; margin:2px;
            }
            QScrollBar#mainVerticalScrollBar::handle:hover { background:#647991; }
            QScrollBar#mainVerticalScrollBar::add-line, QScrollBar#mainVerticalScrollBar::sub-line { height:0px; }
            QScrollBar#mainVerticalScrollBar::add-page, QScrollBar#mainVerticalScrollBar::sub-page { background:transparent; }
            QScrollBar#mainHorizontalScrollBar {
                background:#E8EDF4; height:18px; margin:0; border:none;
            }
            QScrollBar#mainHorizontalScrollBar::handle {
                background:#8193AA; min-width:64px; border-radius:8px; margin:2px;
            }
            QScrollBar#mainHorizontalScrollBar::handle:hover { background:#647991; }
            QScrollBar#mainHorizontalScrollBar::add-line, QScrollBar#mainHorizontalScrollBar::sub-line { width:0px; }
            QScrollBar#mainHorizontalScrollBar::add-page, QScrollBar#mainHorizontalScrollBar::sub-page { background:transparent; }

            /* Checklist owns its own vertical viewport; narrower than the main bars. */
            QScrollArea#checklistScrollArea { background:transparent; border:none; }
            QWidget#checklistScrollContent { background:transparent; }
            QScrollBar#checklistVerticalScrollBar {
                background:#F0F3F7; width:12px; border:none;
            }
            QScrollBar#checklistVerticalScrollBar::handle {
                background:#A6B4C5; min-height:36px; border-radius:5px; margin:1px;
            }
            QScrollBar#checklistVerticalScrollBar::handle:hover { background:#8395AA; }
            QScrollBar#checklistVerticalScrollBar::add-line, QScrollBar#checklistVerticalScrollBar::sub-line { height:0px; }
            QScrollBar#checklistVerticalScrollBar::add-page, QScrollBar#checklistVerticalScrollBar::sub-page { background:transparent; }

            QWidget {
                color:#162033;
                font-family:'Segoe UI','Malgun Gothic';
                font-size:13px;
            }
            QLabel, QRadioButton { background:transparent; }
            QLabel#title { font-size:28px; font-weight:760; color:#0F172A; }
            QLabel#subtitle { color:#667085; font-size:13px; font-weight:500; }
            QLabel#cardTitle { font-size:18px; font-weight:760; color:#0F172A; }
            QLabel#sectionTitle { font-size:16px; font-weight:700; color:#101828; }
            QLabel#smallMuted, QLabel#infoText, QLabel#footerText { color:#667085; font-size:12px; }
            QLabel#cardIcon { color:#3B82F6; font-size:20px; font-weight:700; min-width:20px; }
            QLabel#sectionIcon { background:transparent; border:none; }
            QLabel#helpIcon { color:#526780; border:1px solid #9FB0C3; border-radius:8px; font-size:11px; font-weight:700; background:transparent; }
            QLabel#documentName { font-size:14px; font-weight:650; color:#1D2939; }
            QLabel#fieldLabel { color:#344054; font-weight:700; min-width:74px; }
            QLabel#fieldValue { color:#1D2939; padding:6px 10px; border:1px solid #D8DEE8; border-radius:10px; background:#FFFFFF; }
            QLabel#aiStatus { color:#667085; font-weight:700; padding:0px 12px; background:#F2F4F7; border-radius:12px; }
            QLabel#progressLabel { color:#344054; font-size:12px; font-weight:700; }
            QLabel#checkName { color:#344054; }
            QLabel#checkDot { color:#98A2B3; font-size:18px; }
            QLabel#checkConfirmed { color:#15803D; font-weight:700; }
            QLabel#checkPending { color:#DC2626; font-weight:700; }
            QFrame#checkRow { background:#FFFFFF; border:1px solid #E7EBF1; border-radius:7px; }
            QLabel#checkItemIcon { color:#60758E; font-size:12px; }
            QLabel#checkStatus { font-size:11px; font-weight:700; padding:3px 8px; border-radius:10px; }
            QWidget#resultActions { background:transparent; }
            QLabel#stepArrow { color:#98A2B3; font-size:24px; min-width:12px; }
            QLabel#logoHolder { background:transparent; }

            QFrame#card, QFrame#actionCard {
                background:#FFFFFF;
                border:1px solid #E4EAF3;
                border-radius:18px;
            }
            QFrame#dropZone {
                background:#F8FBFF;
                border:1.5px dashed #C9D6EA;
                border-radius:16px;
            }
            QFrame#dropZone[ready="true"] {
                background:#ECFDF3;
                border:1.5px dashed #A7E2BA;
            }
            QFrame#dropZone[ready="true"] QLabel#dropZoneTitle { color:#15803D; }
            QLabel#dropZoneIcon { color:#B5C3D6; font-size:28px; }
            QLabel#dropZoneTitle { color:#667085; font-weight:600; }
            QLabel#dropZoneMeta { color:#98A2B3; font-size:12px; }
            QPushButton#dropZoneLink {
                background:transparent;
                color:#2563EB;
                border:none;
                font-weight:700;
                padding:0;
                min-height:22px;
            }
            QPushButton#dropZoneLink:hover { color:#1D4ED8; text-decoration: underline; }

            QPushButton {
                min-height:38px;
                padding:0 16px;
                border-radius:11px;
                font-weight:700;
                border:1px solid transparent;
            }
            QPushButton#primaryButton { background:#2563EB; color:#FFFFFF; border-color:#2563EB; font-size:15px; }
            QPushButton#primaryButton:hover { background:#1D4ED8; }
            QPushButton#primaryButton:disabled { background:#AFC2EA; border-color:#AFC2EA; color:#FFFFFF; }
            QPushButton#stopButton { background:#FCE9D6; color:#B45309; border-color:#F6C48B; }
            QPushButton#stopButton:hover { background:#FADDB9; }
            QPushButton#secondaryButton { background:#FFFFFF; color:#344054; border-color:#D0D5DD; }
            QPushButton#secondaryButton:hover { background:#F8FAFC; border-color:#B8C1CD; }
            QPushButton#secondaryButton:disabled { color:#98A2B3; background:#F2F4F7; }
            QPushButton#outlinePrimaryButton { background:#FFFFFF; color:#2563EB; border-color:#B9D3FF; }
            QPushButton#outlinePrimaryButton:hover { background:#EFF6FF; }
            QPushButton#detailButton { background:#FFFFFF; color:#475467; border-color:#D0D5DD; min-height:36px; }
            QPushButton#detailButton:hover { background:#F8FAFC; }

            QComboBox {
                min-height:42px;
                border:1px solid #D0D5DD;
                border-radius:11px;
                background:#FFFFFF;
                padding:0 12px;
                color:#101828;
                font-weight:600;
            }
            QComboBox:hover { border-color:#B8C1CD; }
            QComboBox:focus { border-color:#84B6FF; }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width:36px;
                border-left:none;
                background:transparent;
            }
            QComboBox::down-arrow {
                image:url("__DROPDOWN_ARROW__");
                width:12px;
                height:8px;
                margin-right:10px;
            }
            QLineEdit#apiKeyField {
                min-height:40px;
                border:1px solid #D0D5DD;
                border-radius:11px;
                background:#FFFFFF;
                padding:0 12px;
                color:#667085;
                font-weight:600;
            }

            QRadioButton {
                color:#344054;
                font-weight:700;
                spacing:8px;
            }
            QRadioButton::indicator {
                width:17px; height:17px;
                border-radius:9px;
                border:2px solid #A8B7CA;
                background:#FFFFFF;
            }
            QRadioButton::indicator:checked {
                border:2px solid #2563EB;
                background:#2563EB;
            }

            QPushButton#runGuideButton {
                min-width:116px; padding:0 12px; border:1px solid #B9CCE8; border-radius:7px;
                background:#F7FAFF; color:#245FA8; font-weight:700;
            }
            QPushButton#runGuideButton:hover { background:#EEF5FF; border-color:#8FB3E3; }
            QCheckBox#outputChoice {
                color:#344054;
                font-weight:700;
                spacing:9px;
                background:transparent;
            }
            QCheckBox#outputChoice::indicator {
                width:17px; height:17px;
                border-radius:9px;
                border:2px solid #A8B7CA;
                background:#FFFFFF;
            }
            QCheckBox#outputChoice::indicator:checked {
                border:2px solid #2563EB;
                background:#2563EB;
            }

            QProgressBar {
                height:18px;
                border:1px solid #D0D5DD;
                border-radius:9px;
                background:#EFF3F8;
                color:#0F172A;
                text-align:center;
                font-weight:700;
            }
            QProgressBar#overallProgress::chunk { background:#3B82F6; border-radius:8px; }
            QFrame#currentStatusPanel {
                min-height:32px;
                border:1px solid #DBEAFE;
                border-radius:10px;
                background:#EFF6FF;
            }
            QLabel#currentStatusText {
                color:#2563EB;
                background:transparent;
                font-weight:700;
            }

            QWidget#resultArea { background:transparent; }
            QWidget#resultHeader { background:transparent; }
            QWidget#resultTabGroup { background:transparent; }
            QPushButton#resultTabButton {
                background:#F4F6FA;
                color:#475467;
                border:1px solid #D5DCE7;
                border-bottom:1px solid #D5DCE7;
                border-top-left-radius:9px;
                border-top-right-radius:9px;
                border-bottom-left-radius:0px;
                border-bottom-right-radius:0px;
                padding:0 18px;
                margin-right:-1px;
                font-weight:600;
            }
            QPushButton#resultTabButton:hover {
                background:#F8FAFC;
                color:#344054;
            }
            QPushButton#resultTabButton:checked {
                background:#FFFFFF;
                color:#1D4ED8;
                border-top:2px solid #2563EB;
                border-bottom:1px solid #FFFFFF;
                font-weight:700;
            }
            QFrame#resultTabConnector { background:#FFFFFF; border:none; }
            QWidget#resultActions { background:transparent; }
            QPushButton#resultActionButton {
                background:#FFFFFF;
                color:#344054;
                border:1px solid #D5DCE7;
                border-radius:10px;
                padding:0 14px;
                font-weight:700;
            }
            QPushButton#resultActionButton:hover {
                background:#F8FAFC;
                border-color:#BFC9D8;
            }
            QFrame#resultContentFrame {
                background:#FFFFFF;
                border:1px solid #DDE3EA;
                border-radius:12px;
            }
            QStackedWidget#resultStack { background:transparent; border:none; }
            QFrame#resultContentPane {
                background:#FFFFFF;
                border:none;
                border-radius:11px;
            }
            QWidget#resultEmptyState { background:transparent; }
            QLabel#resultEmptyIcon { background:transparent; }
            QLabel#resultEmptyTitle {
                background:transparent;
                color:#61728D;
                font-size:13px;
                font-weight:700;
            }
            QLabel#resultEmptySubtitle {
                background:transparent;
                color:#98A2B3;
                font-size:12px;
            }
            QPlainTextEdit#resultTextEdit {
                background:#FFFFFF;
                color:#172033;
                border:none;
                border-radius:11px;
                padding:14px;
                font-family:'Consolas','Malgun Gothic';
                font-size:12px;
            }
            QPlainTextEdit {
                background:#FBFCFE;
                border:1px solid #DDE3EA;
                border-radius:12px;
                padding:11px;
                font-family:'Consolas','Malgun Gothic';
                font-size:12px;
            }
            """
        self.setStyleSheet(style.replace("__DROPDOWN_ARROW__", dropdown_arrow))

    def _select_result_tab(self, index: int):
        if not hasattr(self, "result_stack"):
            return
        index = max(0, min(index, self.result_stack.count() - 1))
        self.result_stack.setCurrentIndex(index)
        if hasattr(self, "result_tab_buttons"):
            for i, button in enumerate(self.result_tab_buttons):
                button.setChecked(i == index)
        QTimer.singleShot(0, lambda: self._update_result_tab_connector(index))
        if index == 3:
            QTimer.singleShot(0, self._refresh_automatic_evaluation_progress)

    def _update_result_tab_connector(self, index: int):
        """Bridge the selected tab to the content frame by masking only its top-border span.

        The tab buttons and the content frame live under different sibling widgets.  Mapping a
        button point directly to the content frame can produce an incorrect x offset on some
        Windows/Qt layouts.  Convert both widgets through global coordinates instead, then place
        the small white bridge in the content-frame coordinate system.
        """
        if not hasattr(self, "result_tab_connector") or not hasattr(self, "result_tab_buttons"):
            return
        if not (0 <= index < len(self.result_tab_buttons)):
            return
        button = self.result_tab_buttons[index]
        try:
            button_global = button.mapToGlobal(button.rect().topLeft())
            content_global = self.result_content_frame.mapToGlobal(self.result_content_frame.rect().topLeft())
            x = int(button_global.x() - content_global.x())
            width = max(8, int(button.width()))
            # Cover the content frame's top border only under the selected tab.  Extending one
            # pixel on each side hides antialiasing seams without erasing neighbouring borders.
            self.result_tab_connector.setGeometry(x - 1, 0, width + 2, 3)
            self.result_tab_connector.show()
            self.result_tab_connector.raise_()
        except Exception:
            self.result_tab_connector.hide()

    # Provider selection --------------------------------------------------
    def _load_provider_controls(self):
        provider_id = self.provider_config.get("selected_provider", "hchat_gpt")
        target = {
            "alira": self.radio_alira,
            "hchat_gpt": self.radio_gpt,
            "hchat_gemini": self.radio_gemini,
            "hchat_claude": self.radio_claude,
            "custom_api": self.radio_custom,
        }.get(provider_id, self.radio_gpt)
        target.blockSignals(True)
        target.setChecked(True)
        target.blockSignals(False)
        self._populate_model_combo(provider_id)

    def _selected_provider_id(self) -> str:
        if self.radio_gpt.isChecked():
            return "hchat_gpt"
        if self.radio_gemini.isChecked():
            return "hchat_gemini"
        if self.radio_claude.isChecked():
            return "hchat_claude"
        if self.radio_alira.isChecked():
            return "alira"
        return "custom_api"

    def _model_options_for_provider(self, provider_id: str) -> tuple[str, list[str]]:
        hchat = self.provider_config.get("hchat", {})
        if provider_id == "hchat_gpt":
            current = str(hchat.get("gpt_model") or "gpt-5.6-terra")
            options = list(hchat.get("gpt_model_options") or [current])
        elif provider_id == "hchat_gemini":
            current = str(hchat.get("gemini_model") or "gemini-3.7-flash")
            options = list(hchat.get("gemini_model_options") or [current])
        elif provider_id == "hchat_claude":
            current = str(hchat.get("claude_model") or "claude-sonnet-5")
            options = list(hchat.get("claude_model_options") or [current])
        elif provider_id == "alira":
            cfg = self.provider_config.get("alira", {})
            current = str(cfg.get("model") or "hosted_vllm/Qwen/Qwen3.6-27B")
            options = list(cfg.get("model_options") or [current])
        else:
            cfg = self.provider_config.get("custom", {})
            current = str(cfg.get("model") or "")
            options = list(cfg.get("model_options") or ([current] if current else []))
        options = [str(x) for x in options if str(x).strip()]
        if current and current not in options:
            options.insert(0, current)
        return current, options

    def _populate_model_combo(self, provider_id: str):
        self.provider_model_combo.blockSignals(True)
        self.provider_model_combo.clear()
        current, options = self._model_options_for_provider(provider_id)
        if not options:
            placeholder = "기타 API 설정에서 Model을 입력하세요" if provider_id == "custom_api" else "Model 설정 필요"
            self.provider_model_combo.addItem(placeholder)
        else:
            for item in options:
                self.provider_model_combo.addItem(item)
            idx = self.provider_model_combo.findText(current)
            if idx >= 0:
                self.provider_model_combo.setCurrentIndex(idx)
        self.provider_model_combo.blockSignals(False)

    def _provider_config_for_runtime(self) -> dict:
        data = copy.deepcopy(self.provider_config)
        if self.manual_api_key:
            data.setdefault("hchat", {})["manual_api_key"] = self.manual_api_key
        if self.custom_api_key:
            data.setdefault("custom", {})["manual_api_key"] = self.custom_api_key
        return data

    def _provider_signature(self):
        if self.provider is None:
            return None
        meta = self.provider.metadata()
        manual_key_marker = ""
        if self.manual_api_key:
            manual_key_marker = hashlib.sha256(self.manual_api_key.encode("utf-8")).hexdigest()[:12]
        if meta.provider_id == "custom_api" and self.custom_api_key:
            manual_key_marker = hashlib.sha256(self.custom_api_key.encode("utf-8")).hexdigest()[:12]
        return (
            meta.provider_id,
            meta.model or "",
            meta.api_base or "",
            meta.credential_status or "",
            bool(meta.supports_images),
            manual_key_marker,
        )

    def _rebuild_provider(self, provider_id: str, *, save_selection: bool = True):
        previous_connected = self.connection_state == "connected"
        previous_signature = self.connection_state_signature
        previous_detail = self.connection_state_detail
        if save_selection:
            selected_model = self.provider_model_combo.currentText().strip()
            if selected_model.startswith("Model ") or selected_model.startswith("기타 API 설정"):
                selected_model = ""
            self.provider_config = self.provider_store.update_selection(provider_id, model=selected_model or None)
        runtime_config = self._provider_config_for_runtime()
        self.provider = create_provider(self.project_root, provider_id, runtime_config)

        # V0.33 Vision policy: prefer the selected Provider's native image path.
        # If the selected Provider cannot accept images yet, optionally fall back to a configured
        # dedicated Vision Provider. Text/Table analysis always continues even when Vision is unavailable.
        vision_cfg = copy.deepcopy(runtime_config.get("vision") or {})
        vision_mode = str(vision_cfg.get("mode") or "selected_provider_native")
        fallback_enabled = bool(vision_cfg.get("fallback_enabled", True))
        self.vision_provider = self.provider
        if vision_mode == "dedicated_provider":
            fallback_enabled = True
        custom_blocks_cross_provider_fallback = provider_id == "custom_api"
        if (vision_mode == "dedicated_provider") or (not self.provider.metadata().supports_images and fallback_enabled and not custom_blocks_cross_provider_fallback):
            vision_provider_id = str(vision_cfg.get("fallback_provider_id") or vision_cfg.get("provider_id") or "hchat_gpt")
            vision_runtime = copy.deepcopy(runtime_config)
            if vision_provider_id == "hchat_gpt":
                vision_runtime.setdefault("hchat", {})["gpt_model"] = str(vision_cfg.get("model") or "gpt-5.6-terra")
            try:
                self.vision_provider = create_provider(self.project_root, vision_provider_id, vision_runtime)
            except Exception:
                self.vision_provider = self.provider

        self.job_runner = AIJobRunner(
            self.project_root,
            self.provider,
            self.document_normalizer,
            self.prompt_builder,
            self.requirement_engine,
            vision_provider=self.vision_provider,
        )
        new_signature = self._provider_signature()
        self.connection_state_provider = provider_id
        self._refresh_provider_display()
        if previous_connected and previous_signature == new_signature:
            self.connection_state_signature = new_signature
            self._set_ai_connection_state("connected", previous_detail)
        else:
            self.connection_state_signature = None
            self.connection_state_detail = "Provider/Model 선택 후 필요 시 AI 연결 테스트를 실행해주세요."
            self._set_ai_connection_state("unchecked")

    def _setup_filesystem_watchers(self):
        """Watch input/API-Key folders so the GUI reflects file changes without polling."""
        self.fs_watcher = QFileSystemWatcher(self)
        self.fs_refresh_timer = QTimer(self)
        self.fs_refresh_timer.setSingleShot(True)
        self.fs_refresh_timer.setInterval(250)
        self.fs_refresh_timer.timeout.connect(self._refresh_from_filesystem_watch)
        watch_paths = [str(self.documents.input_dir), str(self.api_key_dir)]
        existing = [path for path in watch_paths if Path(path).is_dir()]
        if existing:
            self.fs_watcher.addPaths(existing)
        self.fs_watcher.directoryChanged.connect(self._on_watched_directory_changed)
        self.fs_watcher.fileChanged.connect(self._on_watched_directory_changed)
        self._refresh_api_key_file_watchers()

    def _refresh_api_key_file_watchers(self):
        if not hasattr(self, "fs_watcher"):
            return
        desired = []
        try:
            desired = [str(p.resolve()) for p in self.api_key_dir.iterdir() if p.is_file()]
        except Exception:
            desired = []
        current = set(self.fs_watcher.files())
        for path in desired:
            if path not in current:
                self.fs_watcher.addPath(path)

    def _on_watched_directory_changed(self, _path: str):
        if hasattr(self, "fs_refresh_timer"):
            self.fs_refresh_timer.start()

    def _refresh_from_filesystem_watch(self):
        self._refresh_api_key_file_watchers()
        self.refresh_all_checks(initial=True)
        if hasattr(self, "status_label"):
            self.status_label.setText("입력/API KEY 폴더 변경 자동 감지 완료")

    def _set_api_key_folder_button_status(self, key_ok: bool):
        self.api_key_folder_button.setMinimumHeight(46)
        if key_ok:
            self.api_key_folder_button.setText("API KEY 확인 됨\n(폴더 열기)")
            self.api_key_folder_button.setStyleSheet(
                "QPushButton { background:#ECFDF3; color:#027A48; border:1px solid #A6F4C5; "
                "border-radius:8px; font-weight:700; padding:4px 14px; } "
                "QPushButton:hover { background:#D1FADF; }"
            )
        else:
            self.api_key_folder_button.setText("API KEY 없음\n(폴더 열기)")
            self.api_key_folder_button.setStyleSheet(
                "QPushButton { background:#FFF4ED; color:#B54708; border:1px solid #FDBA74; "
                "border-radius:8px; font-weight:700; padding:4px 14px; } "
                "QPushButton:hover { background:#FFFAEB; }"
            )

    def _clear_api_key_folder_button_status_style(self):
        self.api_key_folder_button.setStyleSheet("")
        self.api_key_folder_button.setMinimumHeight(38)

    def _on_provider_radio_changed(self, checked: bool):
        if not checked:
            return
        provider_id = self._selected_provider_id()
        self._populate_model_combo(provider_id)
        self._rebuild_provider(provider_id, save_selection=True)
        self._append_log(f"AI Provider 변경: {self.provider.metadata().display_name}")
        self.refresh_all_checks()

    def _on_provider_model_changed(self, _index: int):
        provider_id = self._selected_provider_id()
        model = self.provider_model_combo.currentText().strip()
        if not model or model.startswith("Model ") or model.startswith("기타 API 설정"):
            return
        self.provider_config = self.provider_store.update_selection(provider_id, model=model)
        self._rebuild_provider(provider_id, save_selection=False)
        self._append_log(f"AI Model 변경: {model}")
        self.refresh_all_checks()

    def _refresh_provider_display(self):
        meta = self.provider.metadata()
        self.ai_engine_value.setText(meta.display_name)
        self.footer_provider_label.setText(f"{meta.display_name} · {meta.model}")
        if meta.provider_id.startswith("hchat"):
            key_ok = bool(meta.credential_status and "미감지" not in meta.credential_status)
            self.api_key_field.setText("••••••••••••" if key_ok else "")
            self.api_key_field.setPlaceholderText("API Key를 입력하세요.")
            self._set_api_key_folder_button_status(key_ok)
            self.api_key_folder_button.setToolTip("Requirement Studio의 api_keys 폴더를 엽니다. 파일 추가/삭제는 자동 감지됩니다.")
            self.api_key_manual_button.setText("API Key 수동 입력")
            self.api_key_manual_button.setToolTip("현재 실행 메모리에만 API Key를 입력합니다.")
            self.api_key_folder_button.setEnabled(True)
            self.api_key_manual_button.setEnabled(True)
        elif meta.provider_id == "custom_api":
            self._clear_api_key_folder_button_status_style()
            custom_cfg = self.provider_config.get("custom", {})
            key_required = bool(custom_cfg.get("api_key_required", True))
            key_ok = (not key_required) or ("미입력" not in (meta.credential_status or ""))
            self.api_key_field.setText("••••••••••••" if (key_required and key_ok) else "")
            self.api_key_field.setPlaceholderText("API Key 미사용" if not key_required else "API Key를 입력하세요.")
            self.api_key_folder_button.setText("기타 API 설정")
            self.api_key_folder_button.setToolTip("Protocol / API Base / Model / Auth 설정을 엽니다.")
            self.api_key_manual_button.setText("API Key 수동 입력")
            self.api_key_folder_button.setEnabled(True)
            self.api_key_manual_button.setEnabled(key_required)
        else:
            self._clear_api_key_folder_button_status_style()
            self.api_key_field.setText("")
            self.api_key_field.setPlaceholderText("ALIRA CLI / License / 원격 Qwen")
            self.api_key_folder_button.setText("ALIRA 연결 설정")
            self.api_key_folder_button.setToolTip("라이선스 폴더, 로컬 ALIRA CLI, 원격 Qwen 연결을 한 번에 구성합니다.")
            self.api_key_manual_button.setText("설정 폴더 열기")
            self.api_key_manual_button.setToolTip("Requirement Studio의 alira_license 폴더를 엽니다.")
            self.api_key_folder_button.setEnabled(True)
            self.api_key_manual_button.setEnabled(True)

    def _on_provider_action_primary(self):
        provider_id = self._selected_provider_id()
        if provider_id == "alira":
            self.open_alira_setup()
        elif provider_id == "custom_api":
            self.open_custom_api_settings()
        else:
            self.open_api_key_folder()

    def _on_provider_action_secondary(self):
        if self._selected_provider_id() == "alira":
            self.open_alira_license_folder()
        else:
            self.input_manual_api_key()

    def open_alira_license_folder(self):
        self.alira_license_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.alira_license_dir)))

    def _apply_alira_connection_config(self, license_path: Path | None = None):
        alira_cfg = copy.deepcopy(self.provider_config.get("alira") or {})
        model = str(alira_cfg.get("model") or ALIRA_DEFAULT_MODEL)
        api_base = str(alira_cfg.get("api_base") or ALIRA_DEFAULT_API_BASE)
        stored_license = None
        if license_path is not None:
            stored_license = relative_config_path(self.project_root, Path(license_path))
        self.provider_config = self.provider_store.update_alira_connection(
            license_path=stored_license if stored_license is not None else alira_cfg.get("license_path"),
            model=model,
            api_base=api_base,
        )
        self._populate_model_combo("alira")
        self._rebuild_provider("alira", save_selection=False)
        self.refresh_all_checks()

    def open_alira_setup(self):
        if self._selected_provider_id() != "alira":
            return
        if self.alira_setup_dialog is not None and self.alira_setup_dialog.isVisible():
            self.alira_setup_dialog.raise_()
            self.alira_setup_dialog.activateWindow()
            return
        self.alira_setup_dialog = AliraSetupDialog(self)
        self.alira_setup_dialog.finished.connect(lambda _=0: setattr(self, "alira_setup_dialog", None))
        self.alira_setup_dialog.show()
        self.alira_setup_dialog.raise_()
        self.alira_setup_dialog.activateWindow()

    # Input / output ------------------------------------------------------

    def import_input_files(self, path_list):
        sources = [Path(p) for p in (path_list or [])]
        valid = [p for p in sources if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
        if not valid:
            QMessageBox.warning(self, "파일 가져오기", "지원되는 문서 파일을 선택해주세요.")
            return
        try:
            self.documents.ensure_input_dir()
            # 파일 선택/Drag & Drop은 현재 Batch 입력 세트를 새로 정의한다.
            for existing in self.documents.list_documents():
                existing.unlink(missing_ok=True)
            for source in valid:
                target = self.documents.input_dir / source.name
                if source.resolve() != target.resolve():
                    shutil.copy2(source, target)
        except Exception as exc:
            QMessageBox.critical(self, "파일 가져오기 실패", str(exc))
            return
        self._append_log(f"입력 문서 배치 · {len(valid)}개")
        self.refresh_all_checks()

    def open_input_folder(self):
        self.documents.ensure_input_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.documents.input_dir)))

    def open_output_folder(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_dir)))

    def import_gold_source_package(self):
        start_dir = self.project_root.parent
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Gold Source용 Review Package 선택",
            str(start_dir),
            "Review Package JSON (02_REQUIREMENT_STUDIO_REVIEW_PACKAGE*.json);;JSON Files (*.json)",
        )
        if not filename:
            return
        try:
            target = self.review_exchange_builder.install_gold_source_package(Path(filename))
            status = self.review_exchange_builder.baseline_status()
            self.status_label.setText(f"Gold Source 등록 완료 · 총 {status.get('count', 0)}개")
            self._append_log(
                "Gold Source 등록 · "
                + f"contract={Path(target).name} · total={status.get('count', 0)} · store={status.get('shared_store', '')}"
            )
            QMessageBox.information(
                self,
                "Gold Source 등록 완료",
                "Review Package를 compact Gold Source Contract로 등록했습니다.\n"
                "앞으로 동일 Source SHA-256이 입력되면 별도 Baseline 선택 없이 자동 Regression 비교됩니다.\n"
                "추가 Gold Source도 같은 방식으로 계속 등록할 수 있습니다.",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Gold Source 등록 실패", str(exc))

    def import_v046_baseline_package(self):
        # Legacy callable retained for old shortcuts/tests.
        self.import_gold_source_package()

    def open_review_package_folder(self):
        base_dir = self.project_root / "review_exchange"
        base_dir.mkdir(parents=True, exist_ok=True)
        target = Path(self.last_review_package_dir) if self.last_review_package_dir else None
        if target is None or not target.is_dir():
            latest = base_dir / "LATEST_RUN.txt"
            if latest.is_file():
                try:
                    candidate = Path(latest.read_text(encoding="utf-8").strip())
                    if candidate.is_dir():
                        target = candidate
                except Exception:
                    target = None
        if target is None or not target.is_dir():
            run_dirs = sorted([p for p in base_dir.iterdir() if p.is_dir()], key=lambda x: x.name, reverse=True)
            target = run_dirs[0] if run_dirs else base_dir
            if target == base_dir:
                self.status_label.setText("아직 생성된 AI 평가 패키지가 없습니다. 분석 실행 후 자동 생성됩니다.")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def open_api_key_folder(self):
        self.api_key_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.api_key_dir)))

    def input_manual_api_key(self):
        provider_id = self._selected_provider_id()
        if not (provider_id.startswith("hchat") or provider_id == "custom_api"):
            return
        provider_label = "기타 API" if provider_id == "custom_api" else "H-Chat"
        text, ok = QInputDialog.getText(
            self,
            "API Key 수동 입력",
            f"{provider_label} API Key를 입력하세요.\n이 값은 현재 실행 메모리에만 보관되며 파일에 저장하지 않습니다.",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        text = (text or "").strip()
        if not text:
            QMessageBox.warning(self, "API Key 입력", "API Key가 비어 있습니다.")
            return
        if provider_id == "custom_api":
            self.custom_api_key = text
        else:
            if not is_valid_hchat_api_key(text):
                QMessageBox.warning(
                    self,
                    "API Key 입력",
                    "H-Chat API Key 형식이 올바르지 않습니다.\n"
                    "공백/한글/설명 문장이 아닌 실제 API Key 한 줄을 입력해주세요.",
                )
                return
            self.manual_api_key = text
        self._rebuild_provider(provider_id, save_selection=False)
        self._append_log(f"{provider_label} API Key 수동 입력 완료 · 값은 화면/로그에 표시하지 않음")
        self.refresh_all_checks()


    def open_custom_api_settings(self):
        current = copy.deepcopy(self.provider_config.get("custom") or {})
        dialog = CustomApiSettingsDialog(current, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.saved_config:
            return
        self.provider_config = self.provider_store.update_custom(**dialog.saved_config)
        self._populate_model_combo("custom_api")
        self._rebuild_provider("custom_api", save_selection=False)
        self._append_log(
            "기타 API 설정 저장 · "
            f"형식={dialog.saved_config['profile']} · Model={dialog.saved_config['model']} · "
            f"Vision={'On' if dialog.saved_config['supports_images'] else 'Off'}"
        )
        self.refresh_all_checks()


    def refresh_input_document(self):
        documents = self.documents.list_documents()
        self.current_documents = documents
        self.document_error = None if documents else "입력 문서가 없습니다."
        if hasattr(self, "drop_zone"):
            self.drop_zone.set_document_count(len(documents))
        return bool(documents)

    def refresh_all_checks(self, initial: bool = False):
        self.refresh_input_document()
        self._refresh_provider_display()
        meta = self.provider.metadata()
        provider_id = self._selected_provider_id()

        checks: dict[str, dict] = {}
        checks["입력 문서"] = {
            "state": "confirmed" if self.current_documents else "pending",
            "detail": (f"문서 {len(self.current_documents)}개 준비됨" if self.current_documents else (self.document_error or "입력 문서 없음")),
            "action": "파일을 선택/드래그하거나 input 폴더에 지원 문서를 배치하세요. 폴더 변경은 자동 감지되며 [새로고침]은 수동 재확인용입니다.",
        }
        checks["AI Provider"] = {
            "state": "confirmed" if meta.display_name else "pending",
            "detail": meta.display_name or "Provider 미선택",
            "action": "GPT / Gemini / Claude / ALIRA / 기타 중 하나를 선택하세요.",
        }
        checks["Model"] = {
            "state": "confirmed" if meta.model else "pending",
            "detail": meta.model or "Model 정보 없음",
            "action": "AI 설정 영역에서 Model을 확인하세요.",
        }
        if provider_id.startswith("hchat"):
            credential_ok = bool(meta.credential_status and "미감지" not in meta.credential_status)
            cred_detail = meta.credential_status
            cred_action = "api_keys 폴더에 API_Key류 TXT를 두거나 [API Key 수동 입력]을 사용하세요."
        elif provider_id == "custom_api":
            custom_cfg = self.provider_config.get("custom", {})
            key_required = bool(custom_cfg.get("api_key_required", True))
            credential_ok = bool(meta.api_base and meta.model and ((not key_required) or ("미입력" not in (meta.credential_status or ""))))
            cred_detail = meta.credential_status
            cred_action = "[기타 API 설정]에서 API 형식/Base/Model을 입력하고, 필요한 경우 [API Key 수동 입력]을 사용하세요."
        else:
            alira_status = meta.credential_status or ""
            credential_ok = (
                "확인" in alira_status
                and "미설치" not in alira_status
                and "미감지" not in alira_status
                and "없음" not in alira_status
            )
            cred_detail = alira_status
            cred_action = "[ALIRA 연결 설정]에서 라이선스 폴더, 로컬 CLI, Model/API Server를 자동 확인하세요."
        checks["API Key / 실행환경"] = {
            "state": "confirmed" if credential_ok else "pending",
            "detail": cred_detail or "미확인",
            "action": cred_action,
        }
        connected_for_current = self.connection_state == "connected" and self.connection_state_provider == provider_id
        checks["AI 연결"] = {
            "state": "confirmed" if connected_for_current else "pending",
            "detail": self.connection_state_detail,
            "action": "필요 시 [AI 연결 테스트]를 눌러 실제 연결을 확인하세요. 작업 실행 자체가 성공하면 Provider도 정상 사용된 것입니다.",
        }
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            output_ok = self.output_dir.is_dir() and os.access(self.output_dir, os.W_OK)
        except Exception:
            output_ok = False
        checks["출력 폴더"] = {
            "state": "confirmed" if output_ok else "pending",
            "detail": str(self.output_dir) if output_ok else "output 폴더 쓰기 불가",
            "action": "프로젝트 output 폴더의 생성/쓰기 권한을 확인하세요.",
        }
        required = [
            self.project_root / "policy" / "requirement_judgment_policy.json",
            self.project_root / "policy" / "protected_invariants.json",
            self.project_root / "contracts" / "canonical_requirement_schema.json",
            self.project_root / "reference_library" / "reference_examples.json",
        ]
        missing = [p.name for p in required if not p.is_file()]
        checks["내부 설정"] = {
            "state": "confirmed" if not missing else "pending",
            "detail": "정책/Contract/Reference 확인됨" if not missing else "누락: " + ", ".join(missing),
            "action": "배포 패키지의 policy/contracts/reference_library 파일 구성을 확인하세요.",
        }

        self.check_items = checks
        self._render_checklist()
        if not initial:
            self.status_label.setText("상태 새로고침 완료")

    def _render_checklist(self):
        unresolved = 0
        for name, item in self.check_items.items():
            label = self.check_rows.get(name)
            if not label:
                continue
            if item["state"] == "confirmed":
                label.setText("●  확인됨")
                label.setStyleSheet("color:#15803D; background:#E8F8EE; border:1px solid #B9E7C7; border-radius:10px; font-weight:700; padding:3px 8px;")
            else:
                unresolved += 1
                label.setText("●  미확인")
                label.setStyleSheet("color:#D95F0E; background:#FFF1E6; border:1px solid #FFD2B3; border-radius:10px; font-weight:700; padding:3px 8px;")
        if unresolved:
            self.detail_reason_button.setText(f"상세 원인 확인 ({unresolved})")
            self.detail_reason_button.setStyleSheet("background:#FFF7ED; color:#B45309; border:1px solid #F6C48B; border-radius:11px; font-weight:700;")
        else:
            self.detail_reason_button.setText("모든 항목 확인됨")
            self.detail_reason_button.setStyleSheet("background:#ECFDF3; color:#15803D; border:1px solid #A7E2BA; border-radius:11px; font-weight:700;")

    def show_checklist_details(self):
        dialog = ChecklistDetailDialog(self.check_items, self)
        dialog.exec()

    # State / connection --------------------------------------------------
    def _set_ai_connection_state(self, state: str, detail: str | None = None):
        self.connection_state = state
        if detail is not None:
            self.connection_state_detail = detail
        if state == "connected":
            self.ai_status_label.setText("● AI 연결 정상")
            self.ai_status_label.setStyleSheet("color:#15803D; background:#EAF8EF; font-weight:700; padding:0px 12px; border-radius:12px;")
        elif state == "checking":
            self.ai_status_label.setText("● AI 연결 확인 중")
            self.ai_status_label.setStyleSheet("color:#B45309; background:#FFF7E6; font-weight:700; padding:0px 12px; border-radius:12px;")
        elif state == "failed":
            self.ai_status_label.setText("● AI 연결 실패")
            self.ai_status_label.setStyleSheet("color:#B42318; background:#FEECEC; font-weight:700; padding:0px 12px; border-radius:12px;")
        else:
            self.ai_status_label.setText("● AI 연결 확인 전")
            self.ai_status_label.setStyleSheet("color:#667085; background:#F2F4F7; font-weight:700; padding:0px 12px; border-radius:12px;")

    def run_connection_test(self):
        if self.connection_worker is not None:
            return
        self._rebuild_provider(self._selected_provider_id(), save_selection=False)
        meta = self.provider.metadata()
        self.connection_dialog = ConnectionTestDialog(meta, self)
        self.connection_dialog.show()
        self.connection_dialog.raise_()
        self.connection_dialog.activateWindow()
        self._set_ai_connection_state("checking", "실제 최소 연결 요청을 전송 중입니다.")
        self.connection_dialog.append_log("연결 테스트 시작")

        worker = ConnectionTestWorker(self.provider)
        self.connection_worker = worker
        worker.signals.progress.connect(self._on_connection_progress)
        worker.signals.success.connect(self._on_connection_success)
        worker.signals.error.connect(self._on_connection_error)
        worker.signals.finished.connect(self._on_connection_finished)
        self.thread_pool.start(worker)

    def _on_connection_progress(self, percent: int, message: str):
        if getattr(self, "connection_dialog", None):
            self.connection_dialog.set_progress(percent, message)

    def _on_connection_success(self, text: str):
        self._set_ai_connection_state("connected", "선택 Provider에 대한 실제 연결 요청이 정상 완료되었습니다.")
        self.connection_state_provider = self._selected_provider_id()
        self.connection_state_signature = self._provider_signature()
        if getattr(self, "connection_dialog", None):
            self.connection_dialog.finish_success(text)
        self._append_log(f"AI 연결 테스트 성공 · {self.provider.metadata().display_name}")
        self.refresh_all_checks()

    def _on_connection_error(self, error_text: str):
        self._set_ai_connection_state("failed", error_text)
        self.connection_state_provider = self._selected_provider_id()
        self.connection_state_signature = None
        if getattr(self, "connection_dialog", None):
            self.connection_dialog.finish_error(error_text)
        self._append_log(f"AI 연결 테스트 실패 · {error_text}")
        self.refresh_all_checks()

    def _on_connection_finished(self):
        self.connection_worker = None

    # Stages / progress / log --------------------------------------------
    def _step_text(self, no: int, title: str, status: str) -> str:
        return f"STEP {no} · {title} · {status}"

    def _apply_step_style(self, widgets: dict, mode: str, no: int, title: str):
        frame = widgets["frame"]
        icon = widgets["icon"]
        step = widgets["step"]
        title_label = widgets["title"]
        status = widgets["status"]

        step.setText(f"STEP {no}")
        title_label.setText(title)

        if mode == "complete":
            frame.setStyleSheet("QFrame#stepCard { background:#EAF8F1; border:1px solid #A7E2C3; border-radius:12px; }")
            icon.setText("✓")
            icon.setStyleSheet("background:#20B486; color:#FFFFFF; border-radius:10px; font-weight:800;")
            step.setStyleSheet("color:#167A5A; font-size:10px; font-weight:800;")
            title_label.setStyleSheet("color:#167A5A; font-size:10px; font-weight:700;")
            status.setText("완료")
            status.setStyleSheet("color:#16815E; font-size:10px; font-weight:800;")
        elif mode == "current":
            frame.setStyleSheet("QFrame#stepCard { background:#EDF6FF; border:1px solid #86C5FF; border-radius:12px; }")
            icon.setText("◔")
            icon.setStyleSheet("background:transparent; color:#2F80ED; border:2px solid #70B7FF; border-radius:10px; font-weight:800;")
            step.setStyleSheet("color:#2563EB; font-size:10px; font-weight:800;")
            title_label.setStyleSheet("color:#2563EB; font-size:10px; font-weight:700;")
            status.setText("진행 중")
            status.setStyleSheet("color:#2563EB; font-size:10px; font-weight:800;")
        elif mode == "error":
            frame.setStyleSheet("QFrame#stepCard { background:#FFF3E8; border:1px solid #F6BE82; border-radius:12px; }")
            icon.setText("!")
            icon.setStyleSheet("background:#F97316; color:#FFFFFF; border-radius:10px; font-weight:900;")
            step.setStyleSheet("color:#EA580C; font-size:10px; font-weight:800;")
            title_label.setStyleSheet("color:#EA580C; font-size:10px; font-weight:700;")
            status.setText("실패")
            status.setStyleSheet("color:#EA580C; font-size:10px; font-weight:800;")
        else:
            frame.setStyleSheet("QFrame#stepCard { background:#F7F9FC; border:1px solid #DDE3EC; border-radius:12px; }")
            icon.setText("○")
            icon.setStyleSheet("background:transparent; color:#60758E; border:none; font-size:18px; font-weight:700;")
            step.setStyleSheet("color:#53657D; font-size:10px; font-weight:700;")
            title_label.setStyleSheet("color:#53657D; font-size:10px; font-weight:600;")
            status.setText("대기")
            status.setStyleSheet("color:#7C8DA3; font-size:10px; font-weight:700;")

    def _reset_stages(self):
        self.current_stage = 0
        for no, widgets in self.step_widgets.items():
            self._apply_step_style(widgets, "waiting", no, STEP_UI_TITLES[no])
        self.overall_progress.setRange(0, 100)
        self.overall_progress.setFormat("%p%")
        self.overall_progress.setValue(0)
        self.overall_progress_label.setText("전체 진행률")
        self.current_progress_label.setText("현재 단계 상태")
        self.current_status_text.setText("대기 중")
        self.current_loading_dots.stop()

    def _set_stage(self, no: int, _title: str):
        self.current_stage = no
        for idx, widgets in self.step_widgets.items():
            if idx < no:
                self._apply_step_style(widgets, "complete", idx, STEP_UI_TITLES[idx])
            elif idx == no:
                self._apply_step_style(widgets, "current", idx, STEP_UI_TITLES[idx])
            else:
                self._apply_step_style(widgets, "waiting", idx, STEP_UI_TITLES[idx])
        self.current_progress_label.setText("현재 단계 상태")
        self.current_status_text.setText(f"{STEP_UI_TITLES[no]} 진행 중")
        self.current_loading_dots.start()

    def _set_stage_error(self):
        if self.current_stage in self.step_widgets:
            self._apply_step_style(self.step_widgets[self.current_stage], "error", self.current_stage, STEP_UI_TITLES[self.current_stage])
        self.current_status_text.setText("현재 단계 처리 중 오류 발생")
        self.current_loading_dots.stop()

    def _compact_pipeline_status(self, message: str) -> str:
        text = (message or "").strip()
        # Prefer the local pipeline stage title to remote-provider implementation details.
        if self.current_stage in STEP_UI_TITLES:
            title = STEP_UI_TITLES[self.current_stage]
            if "완료" in text:
                return f"{title} 완료"
            if "오류" in text or "실패" in text:
                return f"{title} 확인 필요"
            if any(token in text for token in ("응답 대기", "요청 전송", "응답 수신", "구조", "정리", "진행")):
                return f"{title} 진행 중"
        # Strip diagnostic suffixes that are useful in logs but noisy in the status panel.
        for sep in (" · ", " (", "["):
            if sep in text:
                text = text.split(sep, 1)[0].strip()
        return text[:42] if text else "처리 중"

    def _on_pipeline_progress(self, overall: int, current: int, message: str):
        # Overall progress is deterministic because it is derived from local pipeline stages.
        self.overall_progress.setRange(0, 100)
        self.overall_progress.setValue(overall)
        self.overall_progress_label.setText("전체 진행률")

        # Current-step UI intentionally uses a lightweight three-dot activity indicator instead
        # of a fabricated model-internal percentage or an indeterminate spinning progress bar.
        self.current_progress_label.setText("현재 단계 상태")
        self.current_status_text.setText(self._compact_pipeline_status(message))
        if overall >= 100:
            self.current_loading_dots.stop()
        else:
            self.current_loading_dots.start()

    def _append_log(self, message: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.appendPlainText(f"[{stamp}] {message}")

    def _save_log_snapshot(self, reason: str = "manual"):
        text = self.log_box.toPlainText().strip()
        if not text:
            return None
        log_dir = self.output_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = log_dir / f"RequirementStudio_Log_{reason}_{stamp}.txt"
        path.write_text(text + "\n", encoding="utf-8")
        return path

    def _show_copy_feedback(self, text: str, success: bool = True, duration_ms: int = 1900):
        self._copy_feedback_token += 1
        token = self._copy_feedback_token
        self.copy_log_button.setText(text)
        if success:
            self.copy_log_button.setStyleSheet(
                "QPushButton#resultActionButton { background:#ECFDF3; color:#15803D; "
                "border:1px solid #A7E2BA; border-radius:9px; font-weight:700; }"
            )
        else:
            self.copy_log_button.setStyleSheet(
                "QPushButton#resultActionButton { background:#FFF4ED; color:#B54708; "
                "border:1px solid #FED7AA; border-radius:9px; font-weight:700; }"
            )

        def reset():
            if token != self._copy_feedback_token:
                return
            self.copy_log_button.setText("로그 복사")
            copy_icon = self.project_root / "assets" / "action_copy.png"
            if copy_icon.is_file():
                self.copy_log_button.setIcon(QIcon(str(copy_icon)))
            self.copy_log_button.setStyleSheet("")

        QTimer.singleShot(max(800, int(duration_ms)), reset)

    def copy_log(self):
        text = self.log_box.toPlainText()
        if not text.strip():
            self.status_label.setText("복사할 진행 로그가 없습니다.")
            self.copy_log_button.setIcon(QIcon())
            self._show_copy_feedback("! 복사할 로그 없음", success=False, duration_ms=1700)
            return
        QApplication.clipboard().setText(text)
        self.copy_log_button.setIcon(QIcon())
        self._show_copy_feedback("✓ 복사 완료", success=True, duration_ms=1900)
        try:
            saved = self._save_log_snapshot("copy")
            self.status_label.setText(f"진행 로그 복사 완료 · {saved.name if saved else ''}")
        except Exception as exc:
            self.status_label.setText(f"진행 로그는 복사했으나 TXT 저장 실패 · {exc}")

    def clear_log(self):
        self.log_box.clear()
        self.log_status_label.setText("대기 중")

    # Start / stop --------------------------------------------------------
    def _set_start_button_mode(self, mode: str):
        self.start_button_mode = mode
        if mode == "start":
            self.start_button.setText("분석 및 요구사항\n추출 시작")
            self.start_button.setObjectName("primaryButton")
            self.start_button.setEnabled(not self.operation_busy)
        elif mode == "arming":
            self.start_button.setText("실행 준비 중...")
            self.start_button.setObjectName("primaryButton")
            self.start_button.setEnabled(False)
        else:
            self.start_button.setText("중지")
            self.start_button.setObjectName("stopButton")
            self.start_button.setEnabled(True)
        self.start_button.style().unpolish(self.start_button)
        self.start_button.style().polish(self.start_button)
        self.start_button.update()

    def _arm_stop_button(self):
        if self.operation_busy:
            self._set_start_button_mode("stop")

    def _on_start_stop_clicked(self):
        if self.operation_busy:
            self.request_stop_pipeline()
        else:
            self.run_combined_pipeline()

    def request_stop_pipeline(self):
        if not self.operation_busy or self.pipeline_worker is None:
            return
        self.pipeline_worker.cancel()
        self.status_label.setText("사용자 중지 요청 접수 · 현재 단계 안전 종료 대기")
        self._append_log("사용자 중지 요청 접수 · 현재 실행 중인 AI 호출이 끝난 뒤 가능한 지점에서 중지합니다.")
        self.start_button.setEnabled(False)

    # Pipeline ------------------------------------------------------------
    def _critical_check_errors(self) -> list[str]:
        errors = []
        for name in ("입력 문서", "AI Provider", "Model", "API Key / 실행환경", "출력 폴더", "내부 설정"):
            item = self.check_items.get(name, {})
            if item.get("state") != "confirmed":
                errors.append(f"{name}: {item.get('detail') or '미확인'}")
        return errors

    def run_combined_pipeline(self):
        if self.operation_busy:
            return
        self.refresh_all_checks()
        errors = self._critical_check_errors()
        if errors:
            self.show_checklist_details()
            QMessageBox.warning(self, "실행 준비 확인", "분석을 시작하기 전에 아래 항목을 확인해주세요.\n\n" + "\n".join(f"- {x}" for x in errors))
            return

        documents = list(self.current_documents)
        self._rebuild_provider(self._selected_provider_id(), save_selection=False)
        self.operation_busy = True
        self._sync_busy_state()
        self._set_start_button_mode("arming")
        self.stop_button_timer.start(1800)
        self._reset_stages()
        self.current_evaluation_run_dir = None
        if hasattr(self, "evaluation_status_timer"):
            self.evaluation_status_timer.stop()
        self._reset_automatic_evaluation_progress("STEP 1~7 진행 중 · 자동평가 대기")
        self.log_box.clear()
        self.response_box.clear()
        self.requirement_result_box.clear()
        self._select_result_tab(0)
        self.log_status_label.setText("실행 중")
        self.status_label.setText(f"문서 {len(documents)}개 · 분석 및 요구사항 추출 실행 중")
        self._append_log(f"Batch 작업 시작 · 문서 {len(documents)}개")
        self._append_log(f"AI Provider · {self.provider.metadata().display_name} / {self.provider.metadata().model}")
        if self.vision_provider is not None:
            vmeta = self.vision_provider.metadata()
            self._append_log(f"Vision Engine · {vmeta.display_name} / {vmeta.model}")
        self.current_output_selection = {
            "swe1_word": self.output_swe1_word.isChecked(),
            "swe1_excel": self.output_swe1_excel.isChecked(),
            "swe6_excel": self.output_swe6_excel.isChecked(),
            "e2e_requirements_word": self.output_e2e_requirements_word.isChecked(),
            "e2e_requirements_excel": self.output_e2e_requirements_excel.isChecked(),
            "e2e_evaluation_excel": self.output_e2e_evaluation.isChecked(),
        }
        selected_ui = self._selected_output_ui_labels()
        self._append_log(
            "산출물 선택 · " + (", ".join(selected_ui) if selected_ui else "추가 산출물 선택 없음")
            + " · 선택한 산출물만 생성"
        )
        review_cfg = self._collect_quality_review_config() if hasattr(self, "review_mode_group") else {"enabled": False, "mode": "none", "scope": "all", "reviewers": [], "criteria": [], "auto_evaluation": False}
        enabled_reviewers = [item["model"] for item in review_cfg.get("reviewers", []) if item.get("enabled")]
        if review_cfg.get("enabled") or review_cfg.get("mode") == "manual":
            self._append_log(
                "AI 품질 평가 설정 · "
                f"mode={review_cfg.get('mode')} / artifact={review_cfg.get('evaluation_artifact','swe1')} / scope={review_cfg.get('scope')} / reviewers="
                + (", ".join(enabled_reviewers) if enabled_reviewers else "없음")
                + f" / criteria={len(review_cfg.get('criteria', []))}"
            )
        else:
            self._append_log("AI 품질 평가 설정 · 비활성")

        worker = PipelineWorker(
            lambda stage_callback, progress_callback, log_callback, cancel_callback: self.job_runner.run_batch_analysis_and_requirements(
                documents,
                stage_callback=stage_callback,
                progress_callback=progress_callback,
                log_callback=log_callback,
                cancel_callback=cancel_callback,
            )
        )
        self.pipeline_worker = worker
        worker.signals.stage.connect(self._set_stage)
        worker.signals.progress.connect(self._on_pipeline_progress)
        worker.signals.log.connect(self._append_log)
        worker.signals.success.connect(self._on_pipeline_success)
        worker.signals.error.connect(self._on_pipeline_error)
        worker.signals.finished.connect(self._on_pipeline_finished)
        self.thread_pool.start(worker)


    def _on_pipeline_success(self, result: dict):
        batch_results = result.get("batch_results") or [result]
        batch_failures = result.get("batch_failures") or []

        analysis_sections = []
        requirement_sections = []
        total_requirements = 0
        scores = []
        output_export_failures: set[tuple[str, str]] = set()
        self._apply_step_style(self.step_widgets[7], "active", 7, STEP_UI_TITLES[7])
        self._append_log("STEP 7B 시작 · 선택 산출물 및 평가용 Artifact Export")

        meta = self.provider.metadata()
        for idx, item in enumerate(batch_results, start=1):
            document = Path(item.get("document") or item.get("source_document") or "document")
            analysis_text = item.get("analysis_text", "")
            req_data = item.get("requirement_data") or {}
            evaluation = item.get("evaluation") or {}
            artifact_paths = {
                "analysis_docx": None,
                "swe1_word": None,
                "swe1_excel": None,
                "swe6_excel": None,
                "e2e_requirements_word": None,
                "e2e_requirements_excel": None,
                "e2e_evaluation_excel": None,
                # backward-compatible aliases populated with E2E Excel paths for older Review Package readers
                "integrated_requirements_excel": None,
                "integrated_tests_excel": None,
            }
            if req_data:
                # V0.85 retains V0.82 Single Truth: finalize SWE.6 cases, SYS.5 candidates, Deferred intents,
                # integrated test objects and deterministic consistency audit exactly once before
                # any engineer-facing exporter consumes the data.
                finalize_verification_single_truth(req_data)
            total_requirements += len(req_data.get("requirements", []))
            if isinstance(evaluation.get("structure_score"), (int, float)):
                scores.append(evaluation["structure_score"])

            analysis_sections.append(f"=== {idx}. {document.name} ===\n{analysis_text}")
            saved_req_path = Path(item.get("saved_path")) if item.get("saved_path") else None
            if req_data and evaluation:
                requirement_sections.append(
                    f"=== {idx}. {document.name} ===\n" +
                    self.requirement_engine.format_for_display(req_data, evaluation, saved_req_path)
                )

            try:
                path = self.result_exporter.export_docx(
                    document,
                    analysis_text,
                    model=meta.model,
                    api_base=meta.api_base,
                )
                artifact_paths["analysis_docx"] = str(path)
                self._append_log(f"분석 결과 DOCX 자동 저장 · {path.name}")
            except Exception as exc:
                self._append_log(f"분석 결과 DOCX 자동 저장 실패 · {document.name} · {exc}")

            if req_data and self.current_output_selection.get("swe1_word"):
                try:
                    path = self.swe1_exporter.export_word(document, req_data)
                    artifact_paths["swe1_word"] = str(path)
                    self._append_log(f"SWE.1 Word 자동 저장 · {path.name}")
                except Exception as exc:
                    output_export_failures.add((str(document), "swe1_word"))
                    self._append_log(f"SWE.1 Word 저장 실패 · {document.name} · {exc}")

            if req_data and self.current_output_selection.get("swe1_excel"):
                try:
                    path = self.swe1_exporter.export_excel(document, req_data)
                    artifact_paths["swe1_excel"] = str(path)
                    self._append_log(f"SWE.1 Excel 자동 저장 · {path.name}")
                except Exception as exc:
                    output_export_failures.add((str(document), "swe1_excel"))
                    self._append_log(f"SWE.1 Excel 저장 실패 · {document.name} · {exc}")

            if req_data and self.current_output_selection.get("swe6_excel"):
                try:
                    normalized = item.get("normalized") or {}
                    source_text = str(normalized.get("compact_text") or "")
                    path = self.swe6_exporter.export_excel(document, req_data, source_text=source_text)
                    artifact_paths["swe6_excel"] = str(path)
                    self._append_log(f"SWE.6 Excel 자동 저장 · {path.name}")
                except Exception as exc:
                    output_export_failures.add((str(document), "swe6_excel"))
                    self._append_log(f"SWE.6 Excel 저장 실패 · {document.name} · {exc}")

            if req_data and self.current_output_selection.get("e2e_requirements_word"):
                try:
                    path = self.e2e_exporter.export_requirements_word(document, req_data)
                    artifact_paths["e2e_requirements_word"] = str(path)
                    self._append_log(f"E2E 요구사항 Word 자동 저장 · {path.name}")
                except Exception as exc:
                    output_export_failures.add((str(document), "e2e_requirements_word"))
                    self._append_log(f"E2E 요구사항 Word 저장 실패 · {document.name} · {exc}")

            if req_data and self.current_output_selection.get("e2e_requirements_excel"):
                try:
                    path = self.e2e_exporter.export_requirements_excel(document, req_data)
                    artifact_paths["e2e_requirements_excel"] = str(path)
                    artifact_paths["integrated_requirements_excel"] = str(path)
                    self._append_log(f"E2E 요구사항 Excel 자동 저장 · {path.name}")
                except Exception as exc:
                    output_export_failures.add((str(document), "e2e_requirements_excel"))
                    self._append_log(f"E2E 요구사항 Excel 저장 실패 · {document.name} · {exc}")

            if req_data and self.current_output_selection.get("e2e_evaluation_excel"):
                try:
                    path = self.e2e_exporter.export_evaluation_excel(document, req_data)
                    artifact_paths["e2e_evaluation_excel"] = str(path)
                    artifact_paths["integrated_tests_excel"] = str(path)
                    self._append_log(f"E2E 평가 명세서 자동 저장 · {path.name}")
                except Exception as exc:
                    output_export_failures.add((str(document), "e2e_evaluation_excel"))
                    self._append_log(f"E2E 평가 명세서 저장 실패 · {document.name} · {exc}")

            # V0.68 Review Exchange can evaluate either the actual SWE.1 Word or the actual
            # SWE.6 Qualification Excel as file 03. Generate review-only artifacts only when
            # evaluation is enabled (auto or manual hand-off).
            review_cfg = self._collect_quality_review_config() if hasattr(self, "review_mode_group") else {"enabled": False, "mode": "none", "evaluation_artifact": "unified", "auto_evaluation": False}
            review_focus = str(review_cfg.get("evaluation_artifact") or "unified").lower()
            # Backward-compatible explicit SWE.1 gate retained for regression visibility.
            # if review_cfg.get("enabled") and req_data and review_focus == "swe1":
            if review_cfg.get("enabled") and req_data and review_focus in {"swe1", "unified"}:
                if not artifact_paths.get("swe1_word") and (str(document), "swe1_word") not in output_export_failures:
                    try:
                        path = self.swe1_exporter.export_word(document, req_data)
                        artifact_paths["swe1_word"] = str(path)
                        self._append_log(f"SWE.1 Word 리뷰용 자동 저장 · {path.name}")
                    except Exception as exc:
                        output_export_failures.add((str(document), "swe1_word"))
                        self._append_log(f"SWE.1 Word 리뷰용 저장 실패 · {document.name} · {exc}")
                if review_focus == "unified" and not artifact_paths.get("swe1_excel") and (str(document), "swe1_excel") not in output_export_failures:
                    try:
                        path = self.swe1_exporter.export_excel(document, req_data)
                        artifact_paths["swe1_excel"] = str(path)
                        self._append_log(f"SWE.1 Excel 통합리뷰용 자동 저장 · {path.name}")
                    except Exception as exc:
                        output_export_failures.add((str(document), "swe1_excel"))
                        self._append_log(f"SWE.1 Excel 통합리뷰용 저장 실패 · {document.name} · {exc}")
            # elif review_cfg.get("enabled") and req_data and review_focus == "swe6":
            if review_cfg.get("enabled") and req_data and review_focus in {"swe6", "unified"} and not artifact_paths.get("swe6_excel") and (str(document), "swe6_excel") not in output_export_failures:
                try:
                    normalized = item.get("normalized") or {}
                    source_text = str(normalized.get("compact_text") or "")
                    path = self.swe6_exporter.export_excel(document, req_data, source_text=source_text)
                    artifact_paths["swe6_excel"] = str(path)
                    self._append_log(f"SWE.6 Excel 리뷰용 자동 저장 · {path.name}")
                except Exception as exc:
                    output_export_failures.add((str(document), "swe6_excel"))
                    self._append_log(f"SWE.6 Excel 리뷰용 저장 실패 · {document.name} · {exc}")

            if review_cfg.get("enabled") and req_data and review_focus == "unified":
                if not artifact_paths.get("e2e_requirements_word") and (str(document), "e2e_requirements_word") not in output_export_failures:
                    try:
                        path = self.e2e_exporter.export_requirements_word(document, req_data)
                        artifact_paths["e2e_requirements_word"] = str(path)
                        self._append_log(f"E2E 요구사항 Word 리뷰용 자동 저장 · {path.name}")
                    except Exception as exc:
                        output_export_failures.add((str(document), "e2e_requirements_word"))
                        self._append_log(f"E2E 요구사항 Word 리뷰용 저장 실패 · {document.name} · {exc}")
                if not artifact_paths.get("e2e_requirements_excel") and (str(document), "e2e_requirements_excel") not in output_export_failures:
                    try:
                        path = self.e2e_exporter.export_requirements_excel(document, req_data)
                        artifact_paths["e2e_requirements_excel"] = str(path); artifact_paths["integrated_requirements_excel"] = str(path)
                        self._append_log(f"E2E 요구사항 Excel 리뷰용 자동 저장 · {path.name}")
                    except Exception as exc:
                        output_export_failures.add((str(document), "e2e_requirements_excel"))
                        self._append_log(f"E2E 요구사항 Excel 리뷰용 저장 실패 · {document.name} · {exc}")
                if not artifact_paths.get("e2e_evaluation_excel") and (str(document), "e2e_evaluation_excel") not in output_export_failures:
                    try:
                        path = self.e2e_exporter.export_evaluation_excel(document, req_data)
                        artifact_paths["e2e_evaluation_excel"] = str(path); artifact_paths["integrated_tests_excel"] = str(path)
                        self._append_log(f"E2E 평가 명세서 리뷰용 자동 저장 · {path.name}")
                    except Exception as exc:
                        output_export_failures.add((str(document), "e2e_evaluation_excel"))
                        self._append_log(f"E2E 평가 명세서 리뷰용 저장 실패 · {document.name} · {exc}")

            # Build deterministic Review Exchange only when evaluation is enabled.
            # V0.68 retains the consolidated reviewer path; auto mode then runs
            # the real independent GPT/Gemini/Claude evaluation orchestrator.
            if review_cfg.get("enabled"):
                try:
                    review_package = self.review_exchange_builder.build(
                        source_document=document,
                        provider_metadata=meta,
                        analysis_text=analysis_text,
                        requirement_data=req_data,
                        evaluation=evaluation,
                        normalized_summary=item.get("normalized") or {},
                        quality_review_config=review_cfg,
                        artifact_paths=artifact_paths,
                        evaluation_mode="initial",
                    )
                    self.last_review_package_dir = review_package.get("run_dir")
                    gate_status = str(review_package.get("regression_gate_status") or "NOT_EVALUATED")
                    baseline_version = str(review_package.get("baseline_version") or "")
                    regression_count = str(review_package.get("regression_count") or "0")
                    self._append_log(
                        "AI 평가 패키지 생성 완료 · "
                        + ("통합 E2E 평가 (요구사항 + 평가 명세서)" if review_package.get("evaluation_artifact_focus") == "unified" else ("SWE.6 평가" if review_package.get("evaluation_artifact_focus") == "swe6" else "SWE.1 평가"))
                        + " · Unified Evidence + 실제 산출물 + 사람용 요약본 · "
                        + Path(str(review_package.get("run_dir"))).name
                        + f" · Regression Gate={gate_status} · Baseline={baseline_version or '없음'} · Findings={regression_count}"
                    )
                    if gate_status == "FAIL":
                        self._append_log("⚠ Gold Source 기준 Source-backed 기능 회귀가 탐지되었습니다. 16_Regression_Report 및 Review Package의 Reference/Current Evidence를 확인하세요.")
                    elif gate_status == "HUMAN_REVIEW_NEEDED":
                        self._append_log("⚠ Regression Gate 자동 PASS 보류 · Baseline behavior 재구성/Traceability/Run Compatibility 근거가 충분하지 않습니다. 16_Regression_Report를 검토하세요.")
                    elif gate_status == "NOT_EVALUATED":
                        self._append_log("⚠ Regression Gate 미평가 · 이 문서를 Gold Source로 관리하려면 승인된 Review Package를 [Gold Source 추가]로 한 번 등록하세요. 이후 동일 Source는 자동 비교됩니다.")
                    if review_cfg.get("auto_evaluation"):
                        contract = review_package.get("unified_artifact_contract") if isinstance(review_package.get("unified_artifact_contract"), dict) else {}
                        if review_focus == "unified" and str(contract.get("status") or "").upper() == "FAIL":
                            missing = ", ".join(contract.get("missing_artifacts") or []) or "unknown"
                            self._append_log(
                                "⚠ Unified Artifact 사전검증 실패 · 누락=" + missing
                                + " · 외부 GPT/Gemini/Claude 호출은 생략하고 deterministic Tool FAIL / Release HOLD 결과만 생성합니다."
                            )
                        self._start_automatic_evaluation(Path(str(review_package.get("run_dir"))))
                except Exception as exc:
                    output_export_failures.add((str(document), "review_package"))
                    self._append_log(f"AI 평가 패키지 생성 실패 · {document.name} · {exc}")

        self.last_analysis_text = "\n\n".join(analysis_sections)
        self.response_box.setPlainText(self.last_analysis_text)
        self.requirement_result_box.setPlainText("\n\n".join(requirement_sections))

        self.overall_progress.setValue(100)
        self.current_status_text.setText("분석 및 요구사항 추출 완료")
        self.current_loading_dots.stop()
        for no, widgets in self.step_widgets.items():
            self._apply_step_style(widgets, "complete", no, STEP_UI_TITLES[no])

        success_count = len(batch_results)
        fail_count = len(batch_failures)
        avg_score = round(sum(scores) / len(scores)) if scores else "-"
        output_export_failure_count = len(output_export_failures)
        if output_export_failure_count:
            self._append_log(f"STEP 7B 실패 · 선택/평가 산출물 Export 실패 {output_export_failure_count}건")
        else:
            self._append_log("STEP 7B 완료 · 선택/평가 산출물 Export 및 Review Package 준비 완료")

        if fail_count or output_export_failure_count:
            self._apply_step_style(self.step_widgets[7], "error", 7, STEP_UI_TITLES[7])
            self.log_status_label.setText("부분 완료")
            self.status_label.setText(
                f"부분 완료 · 문서 성공 {success_count}개 / 실패 {fail_count}개 · "
                f"산출물 실패 {output_export_failure_count}건 · Requirement {total_requirements}개"
            )
            for failure in batch_failures:
                self._append_log(f"문서 실패 · {failure.get('document')} · {failure.get('error')}")
        else:
            self.log_status_label.setText("완료")
            self.status_label.setText(f"완료 · 문서 {success_count}개 · Requirement {total_requirements}개 · 평균 구조점수 {avg_score}/100")
        self._append_log(
            f"Batch 작업 완료 · 성공 {success_count}개 / 실패 {fail_count}개 / 산출물 실패 {output_export_failure_count}건"
        )
        try:
            saved_log = self._save_log_snapshot("complete" if not fail_count and not output_export_failure_count else "partial")
            if saved_log:
                self._append_log(f"진행 로그 자동 저장 · {saved_log.name}")
        except Exception as exc:
            self._append_log(f"진행 로그 자동 저장 실패 · {exc}")

        self.connection_state_provider = self._selected_provider_id()
        self.connection_state_signature = self._provider_signature()
        self._set_ai_connection_state("connected", "실제 분석/요구사항 추출 작업에서 선택 Provider가 정상 사용되었습니다.")
        self.refresh_all_checks()

    def _start_automatic_evaluation(self, run_dir: Path):
        run_dir = Path(run_dir).resolve()
        self.current_evaluation_run_dir = run_dir
        self._reset_automatic_evaluation_progress("자동평가 시작 · 1%")
        if hasattr(self, "eval_progress_bar"):
            self.eval_progress_bar.setValue(1)
        if hasattr(self, "eval_progress_stage_label"):
            self.eval_progress_stage_label.setText("Review Package 완료 · 자동평가 Worker 시작 중")
        if hasattr(self, "evaluation_status_timer"):
            self.evaluation_status_timer.start()
        QTimer.singleShot(50, self._refresh_automatic_evaluation_progress)
        provider_snapshot = copy.deepcopy(self.provider_config)
        self._append_log(f"3-AI 자동 평가 시작 · {run_dir.name} · GPT/Gemini/Claude 독립 검토")

        def _task():
            orchestrator = MultiModelEvaluationOrchestrator(
                self.project_root,
                app_version=APP_VERSION,
                provider_config=provider_snapshot,
            )
            if not bool(orchestrator.config.get("run_after_review_package", True)):
                return json.dumps({
                    "status": "SKIPPED_CONFIG",
                    "output_dir": str(run_dir / "automatic_evaluation"),
                    "tool_quality_gate": "NOT_EVALUATED",
                    "artifact_readiness_gate": "NOT_EVALUATED",
                    "official_release": "NOT_EVALUATED",
                    "providers_completed": [],
                    "provider_failures": {},
                }, ensure_ascii=False)
            result = orchestrator.run(run_dir)
            return json.dumps(result, ensure_ascii=False)

        worker = TaskWorker(_task)
        self.evaluation_workers.append(worker)
        worker.signals.success.connect(lambda payload, rd=run_dir: self._on_automatic_evaluation_success(rd, payload))
        worker.signals.error.connect(lambda message, rd=run_dir: self._on_automatic_evaluation_error(rd, message))
        worker.signals.finished.connect(lambda w=worker: self._on_automatic_evaluation_finished(w))
        self.thread_pool.start(worker)

    def _on_automatic_evaluation_success(self, run_dir: Path, payload: str):
        try:
            result = json.loads(payload)
        except Exception:
            result = {"status": "COMPLETED", "output_dir": str(run_dir / "automatic_evaluation")}
        completed = ", ".join(result.get("providers_completed") or []) or "없음"
        failures = result.get("provider_failures") or {}
        self._append_log(
            "3-AI 자동 평가 완료 · "
            f"Providers={completed} · Tool={result.get('tool_quality_gate','NOT_EVALUATED')} · "
            f"Artifact={result.get('artifact_readiness_gate','NOT_EVALUATED')} · "
            f"Release={result.get('official_release','NOT_EVALUATED')} · "
            f"Files={result.get('verified_file_count', 0)} · FinalParts={result.get('final_result_part_count', 0)}"
        )
        if failures:
            self._append_log("⚠ 일부 평가 모델 실패 · " + " / ".join(f"{k}: {v}" for k, v in failures.items()))
        self._append_log(f"자동 평가 결과 폴더 · {result.get('output_dir') or (run_dir / 'automatic_evaluation')}")
        self.current_evaluation_run_dir = run_dir
        self._refresh_automatic_evaluation_progress()

    def _on_automatic_evaluation_error(self, run_dir: Path, message: str):
        status_path = run_dir / "automatic_evaluation" / "00_EVALUATION_STATUS.txt"
        self._append_log(f"3-AI 자동 평가 실패 · {run_dir.name} · {message}")
        self._append_log(f"자동 평가 상태 파일 · {status_path}")
        self.current_evaluation_run_dir = run_dir
        self._refresh_automatic_evaluation_progress()
        if hasattr(self, "evaluation_status_timer"):
            self.evaluation_status_timer.stop()

    def _on_automatic_evaluation_finished(self, worker):
        try:
            self.evaluation_workers.remove(worker)
        except ValueError:
            pass

    def _on_pipeline_error(self, error_text: str):
        self._set_stage_error()
        self.log_status_label.setText("실패")
        if "사용자 중지 요청" in error_text:
            self.status_label.setText("작업 중지됨")
            self._append_log(f"작업 중지 · {error_text}")
            QMessageBox.information(self, "작업 중지", error_text)
        else:
            self.status_label.setText("분석 및 요구사항 추출 실패")
            self._append_log(f"작업 실패 · {error_text}")
            QMessageBox.critical(self, "작업 실패", error_text)
        try:
            saved_log = self._save_log_snapshot("failure")
            if saved_log:
                self.status_label.setText(self.status_label.text() + f" · 로그 저장: {saved_log.name}")
        except Exception:
            pass
        self.refresh_all_checks()

    def _on_pipeline_finished(self):
        self.operation_busy = False
        self.pipeline_worker = None
        self.stop_button_timer.stop()
        self._sync_busy_state()
        self._set_start_button_mode("start")

    def _sync_busy_state(self):
        enabled = not self.operation_busy
        for widget in (
            self.open_input_button,
            self.refresh_button,
            self.radio_alira,
            self.radio_gpt,
            self.radio_gemini,
            self.provider_model_combo,
            self.connection_test_button,
            self.api_key_folder_button,
            self.api_key_manual_button,
            self.output_swe1_word,
            self.output_swe1_excel,
            self.output_swe6_excel,
            self.output_e2e_requirements_word,
            self.output_e2e_requirements_excel,
            self.output_e2e_evaluation,
        ):
            widget.setEnabled(enabled)
        if enabled:
            self._refresh_provider_display()


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    icon_path = Path(__file__).resolve().parent / "assets" / "RequirementStudio.ico"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
