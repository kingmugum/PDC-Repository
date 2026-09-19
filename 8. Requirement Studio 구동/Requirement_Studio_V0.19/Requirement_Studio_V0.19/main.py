
from __future__ import annotations

import copy
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QUrl, QTimer, Signal
from PySide6.QtGui import QDesktopServices, QFont, QIcon, QPixmap, QAction
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
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
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.ai_job_runner import AIJobRunner
from core.document_manager import DocumentManager, SUPPORTED_EXTENSIONS
from core.document_normalizer import DocumentNormalizer
from core.prompt_builder import PromptBuilder
from core.requirement_engine import RequirementEngine
from core.result_exporter import AnalysisResultExporter
from core.worker import ConnectionTestWorker, PipelineWorker
from providers.config_store import ProviderConfigStore
from providers.factory import create_provider

APP_TITLE = "Requirement Studio"
APP_VERSION = "v0.19"

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
    fileSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel("📄")
        self.icon_label.setObjectName("dropZoneIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        self.title_label = QLabel("분석할 문서 파일을 여기에 드래그하거나")
        self.title_label.setObjectName("dropZoneTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.link_button = QPushButton("파일을 선택하세요")
        self.link_button.setObjectName("dropZoneLink")
        self.link_button.clicked.connect(self._browse_file)
        self.link_button.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.link_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.meta_label = QLabel("지원 형식: .pdf, .docx, .pptx, .xlsx, .xlsm")
        self.meta_label.setObjectName("dropZoneMeta")
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.meta_label)

    def _browse_file(self):
        filters = "문서 파일 (*.pdf *.docx *.pptx *.xlsx *.xlsm)"
        path, _ = QFileDialog.getOpenFileName(self, "문서 선택", "", filters)
        if path:
            self.fileSelected.emit(path)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            path = Path(urls[0].toLocalFile())
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            path = Path(urls[0].toLocalFile())
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                self.fileSelected.emit(str(path))
                event.acceptProposedAction()
                return
        event.ignore()


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

    def set_progress(self, percent: int, message: str):
        pct = max(0, min(99, int(percent)))
        self.progress.setValue(pct)
        self.status_label.setText(f"● 연결 확인 중... ({pct}%)")
        self.status_label.setStyleSheet("color:#D97706; font-weight:700;")
        self.append_log(message)

    def finish_success(self, message: str):
        self.progress.setValue(100)
        self.status_label.setText("● AI 연결 정상 (100%)")
        self.status_label.setStyleSheet("color:#15803D; font-weight:700;")
        self.append_log("연결 테스트 완료")
        if message:
            self.append_log(f"응답: {message[:300]}")

    def finish_error(self, message: str):
        self.progress.setValue(100)
        self.status_label.setText("● AI 연결 실패")
        self.status_label.setStyleSheet("color:#DC2626; font-weight:700;")
        self.append_log(f"실패: {message}")


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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project_root = Path(__file__).resolve().parent
        self.documents = DocumentManager(self.project_root / "input")
        self.output_dir = self.project_root / "output"
        self.api_key_dir = self.project_root / "api_keys"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.api_key_dir.mkdir(parents=True, exist_ok=True)

        self.thread_pool = QThreadPool.globalInstance()
        self.result_exporter = AnalysisResultExporter(self.output_dir)
        self.requirement_engine = RequirementEngine(self.project_root)
        self.document_normalizer = DocumentNormalizer(self.project_root)
        self.prompt_builder = PromptBuilder(self.project_root)
        self.provider_store = ProviderConfigStore(self.project_root)
        self.provider_config = self.provider_store.load()

        self.manual_api_key = ""
        self.provider = None
        self.job_runner = None
        self.connection_worker = None
        self.pipeline_worker = None

        self.current_document = None
        self.document_error = None
        self.operation_busy = False
        self.connection_state = "unchecked"
        self.connection_state_detail = "아직 연결 테스트를 실행하지 않았습니다."
        self.connection_state_provider = ""
        self.current_stage = 0
        self.check_items: dict[str, dict] = {}

        self.last_analysis_text = ""
        self.last_analysis_document = None
        self.last_requirement_data = None
        self.last_requirement_evaluation = None
        self.last_analysis_output_path = None
        self.start_button_mode = "start"

        self.setWindowTitle(APP_TITLE)
        icon_path = self.project_root / "assets" / "RequirementStudio.ico"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.resize(1280, 900)
        self.setMinimumSize(1120, 780)

        self.stop_button_timer = QTimer(self)
        self.stop_button_timer.setSingleShot(True)
        self.stop_button_timer.timeout.connect(self._arm_stop_button)

        self._build_ui()
        self._apply_style()
        self._load_provider_controls()
        self._rebuild_provider(self._selected_provider_id(), save_selection=False)
        self._reset_stages()
        self.refresh_all_checks(initial=True)

    # UI -----------------------------------------------------------------
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
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
        top.addWidget(self._build_file_card(), 5)
        top.addWidget(self._build_ai_card(), 9)
        layout.addLayout(top)

        middle = QHBoxLayout()
        middle.setSpacing(14)
        middle.addWidget(self._build_pipeline_card(), 9)
        middle.addWidget(self._build_checklist_card(), 4)
        layout.addLayout(middle)

        result_card = self._make_card()
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(14, 14, 14, 14)
        result_layout.setSpacing(10)

        result_header = QHBoxLayout()
        result_header.addStretch()
        self.clear_log_button = QPushButton("로그 지우기")
        self.clear_log_button.setObjectName("secondaryButton")
        self.clear_log_button.clicked.connect(self.clear_log)
        self.open_output_button = QPushButton("output 폴더 열기")
        self.open_output_button.setObjectName("secondaryButton")
        self.open_output_button.clicked.connect(self.open_output_folder)
        result_header.addWidget(self.clear_log_button)
        result_header.addWidget(self.open_output_button)
        result_layout.addLayout(result_header)

        self.result_tabs = QTabWidget()
        self.result_tabs.setObjectName("resultTabs")

        self.log_tab = QWidget()
        log_layout = QVBoxLayout(self.log_tab)
        log_layout.setContentsMargins(0, 0, 0, 0)
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setObjectName("runtimeLog")
        self.log_box.setPlaceholderText("분석 & 요구사항 추출 실행 후 로그가 여기에 표시됩니다.")
        log_layout.addWidget(self.log_box)

        analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(analysis_tab)
        analysis_layout.setContentsMargins(0, 0, 0, 0)
        analysis_title = QLabel("Analysis Result")
        analysis_title.setObjectName("sectionTitle")
        analysis_layout.addWidget(analysis_title)
        self.response_box = QPlainTextEdit()
        self.response_box.setReadOnly(True)
        self.response_box.setPlaceholderText("분석 & 요구사항 추출 실행 후 문서 분석 결과가 표시됩니다.")
        analysis_layout.addWidget(self.response_box, 1)

        req_tab = QWidget()
        req_layout = QVBoxLayout(req_tab)
        req_layout.setContentsMargins(0, 0, 0, 0)
        req_title = QLabel("Requirement Candidates")
        req_title.setObjectName("sectionTitle")
        req_layout.addWidget(req_title)
        self.requirement_result_box = QPlainTextEdit()
        self.requirement_result_box.setReadOnly(True)
        self.requirement_result_box.setPlaceholderText("Canonical Requirement 후보와 구조 평가가 표시됩니다.")
        req_layout.addWidget(self.requirement_result_box, 1)

        self.result_tabs.addTab(self.log_tab, "진행 로그")
        self.result_tabs.addTab(analysis_tab, "문서 분석 결과")
        self.result_tabs.addTab(req_tab, "요구사항 후보")
        result_layout.addWidget(self.result_tabs, 1)
        layout.addWidget(result_card, 1)

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

    def _build_file_card(self):
        card = self._make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        icon = QLabel("📁")
        icon.setObjectName("cardIcon")
        title = QLabel("파일 및 옵션 설정")
        title.setObjectName("cardTitle")
        title_row.addWidget(icon)
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        self.drop_zone = FileDropZone()
        self.drop_zone.fileSelected.connect(self.import_input_file)
        layout.addWidget(self.drop_zone)

        self.document_name_label = QLabel("입력 문서를 확인해주세요.")
        self.document_name_label.setObjectName("documentName")
        self.document_name_label.setWordWrap(True)
        layout.addWidget(self.document_name_label)

        self.document_meta_label = QLabel("지원 형식: PDF / DOCX / PPTX / XLSX / XLSM")
        self.document_meta_label.setObjectName("infoText")
        self.document_meta_label.setWordWrap(True)
        layout.addWidget(self.document_meta_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.open_input_button = QPushButton("폴더 열기")
        self.open_input_button.setObjectName("secondaryButton")
        self.open_input_button.clicked.connect(self.open_input_folder)
        self.refresh_button = QPushButton("새로고침")
        self.refresh_button.setObjectName("secondaryButton")
        self.refresh_button.clicked.connect(self.refresh_all_checks)
        buttons.addWidget(self.open_input_button)
        buttons.addWidget(self.refresh_button)
        layout.addLayout(buttons)
        return card

    def _build_ai_card(self):
        card = self._make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        left = QHBoxLayout()
        icon = QLabel("⚙️")
        icon.setObjectName("cardIcon")
        title = QLabel("AI 설정")
        title.setObjectName("cardTitle")
        desc = QLabel("사용할 AI 공급자와 모델을 설정하고 연결을 테스트합니다.")
        desc.setObjectName("smallMuted")
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.addWidget(title)
        title_col.addWidget(desc)
        left.addWidget(icon)
        left.addLayout(title_col)
        header.addLayout(left)
        header.addStretch()
        self.ai_status_label = QLabel("● AI 연결 확인 전")
        self.ai_status_label.setObjectName("aiStatus")
        header.addWidget(self.ai_status_label)
        layout.addLayout(header)

        provider_row = QHBoxLayout()
        provider_row.setSpacing(26)
        self.provider_button_group = QButtonGroup(self)
        self.radio_alira = QRadioButton("ALIRA")
        self.radio_gpt = QRadioButton("GPT")
        self.radio_gemini = QRadioButton("Gemini")
        for idx, btn in enumerate((self.radio_alira, self.radio_gpt, self.radio_gemini)):
            self.provider_button_group.addButton(btn, idx)
            provider_row.addWidget(btn)
            btn.toggled.connect(self._on_provider_radio_changed)
        provider_row.addStretch()
        layout.addLayout(provider_row)

        body = QHBoxLayout()
        body.setSpacing(14)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        for row, label_text in enumerate(("AI Engine", "Model", "API Key")):
            label = QLabel(label_text)
            label.setObjectName("fieldLabel")
            grid.addWidget(label, row, 0)

        self.ai_engine_value = QLabel("-")
        self.ai_engine_value.setObjectName("fieldValue")
        grid.addWidget(self.ai_engine_value, 0, 1)

        self.provider_model_combo = QComboBox()
        self.provider_model_combo.currentIndexChanged.connect(self._on_provider_model_changed)
        grid.addWidget(self.provider_model_combo, 1, 1)

        self.api_key_value = QLabel("-")
        self.api_key_value.setObjectName("fieldValue")
        self.api_key_value.setWordWrap(True)
        grid.addWidget(self.api_key_value, 2, 1)
        grid.setColumnStretch(1, 1)
        body.addLayout(grid, 5)

        action_col = QVBoxLayout()
        action_col.setSpacing(10)
        self.api_key_folder_button = QPushButton("API Key 폴더 열기")
        self.api_key_folder_button.setObjectName("secondaryButton")
        self.api_key_folder_button.clicked.connect(self.open_api_key_folder)
        self.api_key_manual_button = QPushButton("API Key 수동 입력")
        self.api_key_manual_button.setObjectName("secondaryButton")
        self.api_key_manual_button.clicked.connect(self.input_manual_api_key)
        self.connection_test_button = QPushButton("AI 연결 테스트")
        self.connection_test_button.setObjectName("outlinePrimaryButton")
        self.connection_test_button.clicked.connect(self.run_connection_test)
        self.start_button = QPushButton("분석 & 요구사항 추출 시작")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self._on_start_stop_clicked)
        for btn in (self.api_key_folder_button, self.api_key_manual_button, self.connection_test_button, self.start_button):
            btn.setMinimumHeight(42)
            action_col.addWidget(btn)
        action_col.addStretch()
        body.addLayout(action_col, 3)

        layout.addLayout(body)
        return card

    def _build_pipeline_card(self):
        card = self._make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        icon = QLabel("☰")
        icon.setObjectName("cardIcon")
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
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

        step_row = QHBoxLayout()
        step_row.setSpacing(8)
        self.step_labels = {}
        for no in range(1, 8):
            card_label = QLabel()
            card_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_label.setMinimumHeight(92)
            card_label.setMinimumWidth(96)
            card_label.setWordWrap(True)
            self.step_labels[no] = card_label
            step_row.addWidget(card_label, 1)
            if no < 7:
                arrow = QLabel("›")
                arrow.setObjectName("stepArrow")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                step_row.addWidget(arrow)
        layout.addLayout(step_row)

        progress_grid = QGridLayout()
        progress_grid.setHorizontalSpacing(10)
        progress_grid.setVerticalSpacing(10)
        self.overall_progress_label = QLabel("전체 진행률")
        self.overall_progress_label.setObjectName("progressLabel")
        self.current_progress_label = QLabel("현재 단계 진행률")
        self.current_progress_label.setObjectName("progressLabel")
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 100)
        self.overall_progress.setValue(0)
        self.overall_progress.setFormat("%p%")
        self.overall_progress.setObjectName("overallProgress")
        self.current_progress = QProgressBar()
        self.current_progress.setRange(0, 100)
        self.current_progress.setValue(0)
        self.current_progress.setFormat("%p%")
        self.current_progress.setObjectName("currentProgress")
        progress_grid.addWidget(self.overall_progress_label, 0, 0)
        progress_grid.addWidget(self.overall_progress, 0, 1)
        progress_grid.addWidget(self.current_progress_label, 1, 0)
        progress_grid.addWidget(self.current_progress, 1, 1)
        progress_grid.setColumnStretch(1, 1)
        layout.addLayout(progress_grid)

        return card

    def _build_checklist_card(self):
        card = self._make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        icon = QLabel("☑")
        icon.setObjectName("cardIcon")
        title_col = QVBoxLayout()
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
        for name in (
            "입력 문서",
            "AI Provider",
            "Model",
            "API Key / 실행환경",
            "AI 연결",
            "출력 폴더",
            "내부 설정",
        ):
            row = QHBoxLayout()
            row.setSpacing(8)
            icon_label = QLabel("•")
            icon_label.setObjectName("checkDot")
            name_label = QLabel(name)
            name_label.setObjectName("checkName")
            status = QLabel("미확인")
            status.setObjectName("checkPending")
            status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(icon_label)
            row.addWidget(name_label)
            row.addStretch()
            row.addWidget(status)
            layout.addLayout(row)
            self.check_rows[name] = status

        layout.addStretch()
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
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background:#F5F7FB;
                color:#162033;
                font-family:'Segoe UI','Malgun Gothic';
                font-size:13px;
            }
            QLabel#title { font-size:28px; font-weight:760; color:#0F172A; }
            QLabel#subtitle { color:#667085; font-size:13px; font-weight:500; }
            QLabel#cardTitle { font-size:18px; font-weight:760; color:#0F172A; }
            QLabel#sectionTitle { font-size:16px; font-weight:700; color:#101828; }
            QLabel#smallMuted, QLabel#infoText, QLabel#footerText { color:#667085; font-size:12px; }
            QLabel#cardIcon { color:#3B82F6; font-size:20px; font-weight:700; min-width:20px; }
            QLabel#documentName { font-size:14px; font-weight:650; color:#1D2939; }
            QLabel#fieldLabel { color:#344054; font-weight:700; min-width:74px; }
            QLabel#fieldValue { color:#1D2939; padding:6px 10px; border:1px solid #D8DEE8; border-radius:10px; background:#FFFFFF; }
            QLabel#aiStatus { color:#667085; font-weight:700; padding:7px 12px; background:#F2F4F7; border-radius:12px; }
            QLabel#progressLabel { color:#344054; font-size:12px; font-weight:700; }
            QLabel#checkName { color:#344054; }
            QLabel#checkDot { color:#98A2B3; font-size:18px; }
            QLabel#checkConfirmed { color:#15803D; font-weight:700; }
            QLabel#checkPending { color:#DC2626; font-weight:700; }
            QLabel#stepArrow { color:#98A2B3; font-size:24px; min-width:12px; }
            QLabel#logoHolder { background:transparent; }

            QFrame#card {
                background:#FFFFFF;
                border:1px solid #E4EAF3;
                border-radius:18px;
            }
            QFrame#dropZone {
                background:#F8FBFF;
                border:1.5px dashed #C9D6EA;
                border-radius:16px;
            }
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
            QPushButton#primaryButton { background:#2563EB; color:#FFFFFF; border-color:#2563EB; }
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
                width:32px;
                border-left:1px solid #E5E7EB;
                background:#F8FAFC;
                border-top-right-radius:10px;
                border-bottom-right-radius:10px;
            }

            QRadioButton {
                color:#344054;
                font-weight:700;
                spacing:8px;
            }
            QRadioButton::indicator {
                width:16px; height:16px;
                border-radius:8px;
                border:2px solid #98A2B3;
                background:#FFFFFF;
            }
            QRadioButton::indicator:checked {
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
            QProgressBar#currentProgress::chunk { background:#60A5FA; border-radius:8px; }

            QTabWidget#resultTabs::pane {
                border:1px solid #E4E7EC;
                border-radius:12px;
                background:#FFFFFF;
                top:-1px;
            }
            QTabWidget#resultTabs QTabBar::tab {
                background:#F4F6FA;
                color:#475467;
                border:1px solid #D5DCE7;
                border-bottom:none;
                padding:10px 20px;
                min-width:118px;
                border-top-left-radius:8px;
                border-top-right-radius:8px;
            }
            QTabWidget#resultTabs QTabBar::tab:selected {
                background:#FFFFFF;
                color:#1D4ED8;
                font-weight:700;
            }

            QPlainTextEdit {
                background:#FBFCFE;
                border:1px solid #DDE3EA;
                border-radius:12px;
                padding:11px;
                font-family:'Consolas','Malgun Gothic';
                font-size:12px;
            }
            QPlainTextEdit#runtimeLog { background:#FBFCFE; color:#172033; }
            """
        )

    # Provider selection --------------------------------------------------
    def _load_provider_controls(self):
        provider_id = self.provider_config.get("selected_provider", "alira")
        target = {
            "alira": self.radio_alira,
            "hchat_gpt": self.radio_gpt,
            "hchat_gemini": self.radio_gemini,
        }.get(provider_id, self.radio_alira)
        target.blockSignals(True)
        target.setChecked(True)
        target.blockSignals(False)
        self._populate_model_combo(provider_id)

    def _selected_provider_id(self) -> str:
        if self.radio_gpt.isChecked():
            return "hchat_gpt"
        if self.radio_gemini.isChecked():
            return "hchat_gemini"
        return "alira"

    def _populate_model_combo(self, provider_id: str):
        self.provider_model_combo.blockSignals(True)
        self.provider_model_combo.clear()
        if provider_id == "alira":
            model = self.provider_config.get("alira", {}).get("model", "hosted_vllm/Qwen/Qwen3.6-27B")
            self.provider_model_combo.addItem(model)
        elif provider_id == "hchat_gpt":
            hchat = self.provider_config.get("hchat", {})
            current = hchat.get("gpt_model", "gpt-5.6-terra")
            options = list(hchat.get("gpt_model_options") or [current])
            if current not in options:
                options.insert(0, current)
            for item in options:
                self.provider_model_combo.addItem(str(item))
            idx = self.provider_model_combo.findText(str(current))
            if idx >= 0:
                self.provider_model_combo.setCurrentIndex(idx)
        else:
            model = self.provider_config.get("hchat", {}).get("gemini_model", "gemini-3.1-pro-preview")
            self.provider_model_combo.addItem(model)
        self.provider_model_combo.blockSignals(False)

    def _provider_config_for_runtime(self) -> dict:
        data = copy.deepcopy(self.provider_config)
        if self.manual_api_key:
            data.setdefault("hchat", {})["manual_api_key"] = self.manual_api_key
        return data

    def _rebuild_provider(self, provider_id: str, *, save_selection: bool = True):
        if save_selection:
            gpt_model = self.provider_model_combo.currentText() if provider_id == "hchat_gpt" else None
            self.provider_config = self.provider_store.update_selection(provider_id, gpt_model=gpt_model)
        runtime_config = self._provider_config_for_runtime()
        self.provider = create_provider(self.project_root, provider_id, runtime_config)
        self.job_runner = AIJobRunner(
            self.project_root,
            self.provider,
            self.document_normalizer,
            self.prompt_builder,
            self.requirement_engine,
        )
        self.connection_state = "unchecked"
        self.connection_state_provider = provider_id
        self.connection_state_detail = "Provider/Model 선택 후 필요 시 AI 연결 테스트를 실행해주세요."
        self._refresh_provider_display()
        self._set_ai_connection_state("unchecked")

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
        if provider_id == "hchat_gpt" and self.provider_model_combo.currentText():
            self.provider_config = self.provider_store.update_selection(provider_id, gpt_model=self.provider_model_combo.currentText())
            self._rebuild_provider(provider_id, save_selection=False)
            self._append_log(f"AI Model 변경: {self.provider_model_combo.currentText()}")
            self.refresh_all_checks()

    def _refresh_provider_display(self):
        meta = self.provider.metadata()
        self.ai_engine_value.setText(meta.display_name)
        self.footer_provider_label.setText(f"{meta.display_name} · {meta.model}")
        if meta.provider_id.startswith("hchat"):
            self.api_key_value.setText(meta.credential_status)
            self.api_key_folder_button.setEnabled(True)
            self.api_key_manual_button.setEnabled(True)
        else:
            self.api_key_value.setText("해당 없음 · ALIRA 실행환경/라이선스 사용")
            self.api_key_folder_button.setEnabled(False)
            self.api_key_manual_button.setEnabled(False)

    # Input / output ------------------------------------------------------
    def import_input_file(self, path_str: str):
        source = Path(path_str)
        if not source.is_file():
            QMessageBox.warning(self, "파일 가져오기", "선택한 파일을 찾을 수 없습니다.")
            return
        if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
            QMessageBox.warning(self, "파일 가져오기", "지원하지 않는 형식입니다.")
            return
        try:
            self.documents.ensure_input_dir()
            for existing in self.documents.list_documents():
                if existing.resolve() != source.resolve():
                    existing.unlink(missing_ok=True)
            target = self.documents.input_dir / source.name
            if source.resolve() != target.resolve():
                shutil.copy2(source, target)
        except Exception as exc:
            QMessageBox.critical(self, "파일 가져오기 실패", str(exc))
            return
        self._append_log(f"입력 문서 배치 · {source.name}")
        self.refresh_all_checks()

    def open_input_folder(self):
        self.documents.ensure_input_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.documents.input_dir)))

    def open_output_folder(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_dir)))

    def open_api_key_folder(self):
        self.api_key_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.api_key_dir)))

    def input_manual_api_key(self):
        if not self._selected_provider_id().startswith("hchat"):
            return
        text, ok = QInputDialog.getText(
            self,
            "API Key 수동 입력",
            "H-Chat API Key를 입력하세요.\n이 값은 현재 실행 메모리에만 보관되며 파일에 저장하지 않습니다.",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        text = (text or "").strip()
        if not text:
            QMessageBox.warning(self, "API Key 입력", "API Key가 비어 있습니다.")
            return
        self.manual_api_key = text
        self._rebuild_provider(self._selected_provider_id(), save_selection=False)
        self._append_log("H-Chat API Key 수동 입력 완료 · 값은 화면/로그에 표시하지 않음")
        self.refresh_all_checks()

    def refresh_input_document(self):
        result = self.documents.get_single_document()
        self.current_document = result.document
        self.document_error = result.error
        if result.error:
            self.document_name_label.setText(f"⚠ {result.error}")
            self.document_meta_label.setText("지원 형식: PDF / DOCX / PPTX / XLSX / XLSM · input 폴더에는 1개만 유지")
            return False
        doc = result.document
        self.document_name_label.setText(f"✓ {doc.name}")
        self.document_meta_label.setText(f"형식: {doc.suffix.upper().lstrip('.')} · 크기: {self.documents.format_size(doc.stat().st_size)}")
        return True

    def refresh_all_checks(self, initial: bool = False):
        self.refresh_input_document()
        self._refresh_provider_display()
        meta = self.provider.metadata()
        provider_id = self._selected_provider_id()

        checks: dict[str, dict] = {}
        checks["입력 문서"] = {
            "state": "confirmed" if self.current_document else "pending",
            "detail": self.current_document.name if self.current_document else (self.document_error or "input 문서 없음"),
            "action": "input 폴더에 지원 문서 1개만 배치한 뒤 [새로고침]을 누르세요.",
        }
        checks["AI Provider"] = {
            "state": "confirmed" if meta.display_name else "pending",
            "detail": meta.display_name or "Provider 미선택",
            "action": "ALIRA / GPT / Gemini 중 하나를 선택하세요.",
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
        else:
            credential_ok = "없음" not in (meta.credential_status or "")
            cred_detail = meta.credential_status
            cred_action = "ALIRA 실행파일/라이선스/설치환경을 확인하세요."
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
                label.setText("확인됨")
                label.setStyleSheet("color:#15803D; font-weight:700;")
            else:
                unresolved += 1
                label.setText("미확인")
                label.setStyleSheet("color:#DC2626; font-weight:700;")
        if unresolved:
            self.detail_reason_button.setText(f"상세 원인 확인 ({unresolved})")
            self.detail_reason_button.setStyleSheet("background:#FFF7ED; color:#B45309; border:1px solid #F6C48B; border-radius:11px; font-weight:700;")
        else:
            self.detail_reason_button.setText("상세 원인 확인")
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
            self.ai_status_label.setStyleSheet("color:#15803D; background:#EAF8EF; font-weight:700; padding:7px 12px; border-radius:12px;")
        elif state == "checking":
            self.ai_status_label.setText("● AI 연결 확인 중")
            self.ai_status_label.setStyleSheet("color:#B45309; background:#FFF7E6; font-weight:700; padding:7px 12px; border-radius:12px;")
        elif state == "failed":
            self.ai_status_label.setText("● AI 연결 실패")
            self.ai_status_label.setStyleSheet("color:#B42318; background:#FEECEC; font-weight:700; padding:7px 12px; border-radius:12px;")
        else:
            self.ai_status_label.setText("● AI 연결 확인 전")
            self.ai_status_label.setStyleSheet("color:#667085; background:#F2F4F7; font-weight:700; padding:7px 12px; border-radius:12px;")

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
        if getattr(self, "connection_dialog", None):
            self.connection_dialog.finish_success(text)
        self._append_log(f"AI 연결 테스트 성공 · {self.provider.metadata().display_name}")
        self.refresh_all_checks()

    def _on_connection_error(self, error_text: str):
        self._set_ai_connection_state("failed", error_text)
        self.connection_state_provider = self._selected_provider_id()
        if getattr(self, "connection_dialog", None):
            self.connection_dialog.finish_error(error_text)
        self._append_log(f"AI 연결 테스트 실패 · {error_text}")
        self.refresh_all_checks()

    def _on_connection_finished(self):
        self.connection_worker = None

    # Stages / progress / log --------------------------------------------
    def _step_text(self, no: int, title: str, status: str) -> str:
        return f"STEP {no}\n{title}\n{status}"

    def _apply_step_style(self, label: QLabel, mode: str, no: int, title: str):
        if mode == "complete":
            label.setText(self._step_text(no, title, "완료"))
            label.setStyleSheet("background:#ECFDF3; color:#15803D; border:1px solid #A7E2BA; border-radius:14px; padding:10px; font-size:11px; font-weight:700;")
        elif mode == "current":
            label.setText(self._step_text(no, title, "진행 중"))
            label.setStyleSheet("background:#EFF6FF; color:#2563EB; border:1px solid #B9D3FF; border-radius:14px; padding:10px; font-size:11px; font-weight:700;")
        elif mode == "error":
            label.setText(self._step_text(no, title, "실패"))
            label.setStyleSheet("background:#FFF7ED; color:#B45309; border:1px solid #F6C48B; border-radius:14px; padding:10px; font-size:11px; font-weight:700;")
        else:
            label.setText(self._step_text(no, title, "대기"))
            label.setStyleSheet("background:#F8FAFC; color:#667085; border:1px solid #E4E7EC; border-radius:14px; padding:10px; font-size:11px; font-weight:600;")

    def _reset_stages(self):
        self.current_stage = 0
        for no, label in self.step_labels.items():
            self._apply_step_style(label, "waiting", no, STEP_UI_TITLES[no])
        self.overall_progress.setValue(0)
        self.current_progress.setValue(0)
        self.overall_progress_label.setText("전체 진행률")
        self.current_progress_label.setText("현재 단계 진행률")

    def _set_stage(self, no: int, _title: str):
        self.current_stage = no
        for idx, label in self.step_labels.items():
            if idx < no:
                self._apply_step_style(label, "complete", idx, STEP_UI_TITLES[idx])
            elif idx == no:
                self._apply_step_style(label, "current", idx, STEP_UI_TITLES[idx])
            else:
                self._apply_step_style(label, "waiting", idx, STEP_UI_TITLES[idx])
        self.current_progress.setValue(0)
        self.current_progress_label.setText(f"현재 단계 진행률 · STEP {no} {STEP_UI_TITLES[no]}")

    def _set_stage_error(self):
        if self.current_stage in self.step_labels:
            self._apply_step_style(self.step_labels[self.current_stage], "error", self.current_stage, STEP_UI_TITLES[self.current_stage])

    def _on_pipeline_progress(self, overall: int, current: int, message: str):
        self.overall_progress.setValue(overall)
        self.current_progress.setValue(current)
        self.overall_progress_label.setText(f"전체 진행률")
        self.current_progress_label.setText(f"현재 단계 진행률 · {message}")

    def _append_log(self, message: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.appendPlainText(f"[{stamp}] {message}")

    def clear_log(self):
        self.log_box.clear()
        self.log_status_label.setText("대기 중")

    # Start / stop --------------------------------------------------------
    def _set_start_button_mode(self, mode: str):
        self.start_button_mode = mode
        if mode == "start":
            self.start_button.setText("분석 & 요구사항 추출 시작")
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

        document = self.current_document
        self._rebuild_provider(self._selected_provider_id(), save_selection=False)
        self.operation_busy = True
        self._sync_busy_state()
        self._set_start_button_mode("arming")
        self.stop_button_timer.start(1800)
        self._reset_stages()
        self.log_box.clear()
        self.response_box.clear()
        self.requirement_result_box.clear()
        self.result_tabs.setCurrentIndex(0)
        self.log_status_label.setText("실행 중")
        self.status_label.setText(f"{document.name} · 분석 & 요구사항 추출 실행 중")
        self._append_log(f"작업 시작 · {document.name}")
        self._append_log(f"AI Provider · {self.provider.metadata().display_name} / {self.provider.metadata().model}")

        worker = PipelineWorker(
            lambda stage_callback, progress_callback, log_callback, cancel_callback: self.job_runner.run_analysis_and_requirements(
                document,
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
        self.last_analysis_text = result.get("analysis_text", "")
        self.last_analysis_document = self.current_document
        self.last_requirement_data = result.get("requirement_data")
        self.last_requirement_evaluation = result.get("evaluation")

        self.response_box.setPlainText(self.last_analysis_text)
        if self.last_requirement_data and self.last_requirement_evaluation:
            saved_req_path = Path(result.get("saved_path")) if result.get("saved_path") else None
            self.requirement_result_box.setPlainText(self.requirement_engine.format_for_display(self.last_requirement_data, self.last_requirement_evaluation, saved_req_path))

        self.last_analysis_output_path = None
        try:
            meta = self.provider.metadata()
            self.last_analysis_output_path = self.result_exporter.export_docx(
                self.last_analysis_document,
                self.last_analysis_text,
                model=meta.model,
                api_base=meta.api_base,
            )
            self._append_log(f"분석 결과 DOCX 자동 저장 · {self.last_analysis_output_path.name}")
        except Exception as exc:
            self._append_log(f"분석 결과 DOCX 자동 저장 실패 · {exc}")

        self.overall_progress.setValue(100)
        self.current_progress.setValue(100)
        for no, label in self.step_labels.items():
            self._apply_step_style(label, "complete", no, STEP_UI_TITLES[no])
        self.log_status_label.setText("완료")
        req_count = len((self.last_requirement_data or {}).get("requirements", []))
        score = (self.last_requirement_evaluation or {}).get("structure_score", "-")
        saved_json = Path(result.get("saved_path")).name if result.get("saved_path") else "-"
        self.status_label.setText(f"완료 · Requirement 후보 {req_count}개 · 구조점수 {score}/100")
        self._append_log(f"작업 완료 · Requirement 후보 {req_count}개 · 구조점수 {score}/100")
        self._append_log(f"요구사항 JSON 저장 · {saved_json}")

        self.connection_state_provider = self._selected_provider_id()
        self._set_ai_connection_state("connected", "실제 분석/요구사항 추출 작업이 정상 완료되었습니다.")
        self.refresh_all_checks()

    def _on_pipeline_error(self, error_text: str):
        self._set_stage_error()
        self.log_status_label.setText("실패")
        if "사용자 중지 요청" in error_text:
            self.status_label.setText("작업 중지됨")
            self._append_log(f"작업 중지 · {error_text}")
            QMessageBox.information(self, "작업 중지", error_text)
        else:
            self.status_label.setText("분석 & 요구사항 추출 실패")
            self._append_log(f"작업 실패 · {error_text}")
            QMessageBox.critical(self, "작업 실패", error_text)
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
