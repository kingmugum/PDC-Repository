
from __future__ import annotations

import copy
import hashlib
import os
import shutil
import sys
import time
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
from core.result_exporter import AnalysisResultExporter
from core.worker import ConnectionTestWorker, PipelineWorker
from providers.config_store import ProviderConfigStore
from providers.factory import create_provider

APP_TITLE = "Requirement Studio"
APP_VERSION = "v0.26"

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(5)
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

        self.setWindowTitle(APP_TITLE)
        icon_path = self.project_root / "assets" / "RequirementStudio.ico"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.resize(1280, 900)
        # Window itself may shrink; the inner dashboard keeps its readable minimum size
        # and is navigated through the outer horizontal/vertical scroll bars.
        self.setMinimumSize(720, 480)

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
        # The main window is a viewport over a dashboard with a fixed readable minimum.
        # When the window becomes smaller, Qt scroll bars appear instead of compressing
        # cards, labels, progress bars, or result areas.
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
        # This is the logical canvas. It will expand on large screens but never shrink
        # below this size; the outer scroll bars become the navigation mechanism.
        self.dashboard_content.setMinimumSize(1180, 820)
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
        top.addWidget(self._build_file_card(), 5)
        top.addWidget(self._build_ai_card(), 13)
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
        result_content_layout = QVBoxLayout(result_content_frame)
        result_content_layout.setContentsMargins(0, 0, 0, 0)
        result_content_layout.setSpacing(0)

        self.log_box = ResultContentPane(
            self.project_root,
            "result_log.png",
            "분석 & 요구사항 추출 실행 후 로그가 여기에 표시됩니다.",
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

        self.result_stack = QStackedWidget()
        self.result_stack.setObjectName("resultStack")
        self.result_stack.addWidget(self.log_box)
        self.result_stack.addWidget(self.response_box)
        self.result_stack.addWidget(self.requirement_result_box)
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


    def _build_file_card(self):
        card = self._make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

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
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(8)
        icon = self._section_icon("section_gear.png")
        title = QLabel("AI 설정")
        title.setObjectName("cardTitle")
        subtitle = QLabel("사용할 AI 공급자와 모델을 설정하고 연결을 테스트합니다.")
        subtitle.setObjectName("smallMuted")
        header.addWidget(icon)
        header.addWidget(title)
        header.addWidget(subtitle)
        header.addStretch()
        self.ai_status_label = QLabel("● AI 연결 확인 전")
        self.ai_status_label.setObjectName("aiStatus")
        self.ai_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.ai_status_label)
        layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(14)

        provider_grid = QGridLayout()
        provider_grid.setHorizontalSpacing(12)
        provider_grid.setVerticalSpacing(12)

        engine_label = QLabel("AI Engine")
        engine_label.setObjectName("fieldLabel")
        provider_grid.addWidget(engine_label, 0, 0)

        self.provider_button_group = QButtonGroup(self)
        self.radio_gpt = QRadioButton("GPT (H-Chat)")
        self.radio_gemini = QRadioButton("Gemini (H-Chat)")
        self.radio_alira = QRadioButton("ALIRA")
        for idx, btn in enumerate((self.radio_gpt, self.radio_gemini, self.radio_alira)):
            self.provider_button_group.addButton(btn, idx)
            btn.toggled.connect(self._on_provider_radio_changed)
            btn.setMinimumHeight(28)

        provider_row = QHBoxLayout()
        provider_row.setSpacing(28)
        provider_row.addWidget(self.radio_gpt)
        provider_row.addWidget(self.radio_gemini)
        provider_row.addWidget(self.radio_alira)
        provider_row.addStretch()
        provider_grid.addLayout(provider_row, 0, 1)

        model_label = QLabel("Model")
        model_label.setObjectName("fieldLabel")
        provider_grid.addWidget(model_label, 1, 0)
        self.provider_model_combo = QComboBox()
        self.provider_model_combo.setObjectName("modelCombo")
        self.provider_model_combo.currentIndexChanged.connect(self._on_provider_model_changed)
        provider_grid.addWidget(self.provider_model_combo, 1, 1)

        api_label = QLabel("API Key")
        api_label.setObjectName("fieldLabel")
        provider_grid.addWidget(api_label, 2, 0)
        self.api_key_field = QLineEdit()
        self.api_key_field.setReadOnly(True)
        self.api_key_field.setObjectName("apiKeyField")
        self.api_key_field.setPlaceholderText("API Key를 입력하세요.")
        provider_grid.addWidget(self.api_key_field, 2, 1)
        provider_grid.setColumnStretch(1, 1)

        self.ai_engine_value = QLabel("-")
        self.ai_engine_value.setVisible(False)
        body.addLayout(provider_grid, 7)

        action_col = QVBoxLayout()
        action_col.setSpacing(8)
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
            btn.setMinimumHeight(39)
            action_col.addWidget(btn)
        action_col.addStretch()
        body.addLayout(action_col, 3)

        layout.addLayout(body)
        return card

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
        checklist_layout.setSpacing(5)

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
            QLabel#aiStatus { color:#667085; font-weight:700; padding:7px 12px; background:#F2F4F7; border-radius:12px; }
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

    # Provider selection --------------------------------------------------
    def _load_provider_controls(self):
        provider_id = self.provider_config.get("selected_provider", "hchat_gpt")
        target = {
            "alira": self.radio_alira,
            "hchat_gpt": self.radio_gpt,
            "hchat_gemini": self.radio_gemini,
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

    def _provider_signature(self):
        if self.provider is None:
            return None
        meta = self.provider.metadata()
        manual_key_marker = ""
        if self.manual_api_key:
            manual_key_marker = hashlib.sha256(self.manual_api_key.encode("utf-8")).hexdigest()[:12]
        return (
            meta.provider_id,
            meta.model or "",
            meta.api_base or "",
            meta.credential_status or "",
            manual_key_marker,
        )

    def _rebuild_provider(self, provider_id: str, *, save_selection: bool = True):
        previous_connected = self.connection_state == "connected"
        previous_signature = self.connection_state_signature
        previous_detail = self.connection_state_detail
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
            key_ok = bool(meta.credential_status and "미감지" not in meta.credential_status)
            self.api_key_field.setText("••••••••••••" if key_ok else "")
            self.api_key_field.setPlaceholderText("API Key를 입력하세요.")
            self.api_key_folder_button.setEnabled(True)
            self.api_key_manual_button.setEnabled(True)
        else:
            self.api_key_field.setText("")
            self.api_key_field.setPlaceholderText("ALIRA 실행환경/라이선스 사용")
            self.api_key_folder_button.setEnabled(False)
            self.api_key_manual_button.setEnabled(False)

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
            "action": "파일을 선택/드래그하거나 input 폴더에 지원 문서를 배치한 뒤 [새로고침]을 누르세요.",
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
        self.overall_progress.setValue(0)
        self.current_progress.setValue(0)
        self.overall_progress_label.setText("전체 진행률")
        self.current_progress_label.setText("현재 단계 진행률")

    def _set_stage(self, no: int, _title: str):
        self.current_stage = no
        for idx, widgets in self.step_widgets.items():
            if idx < no:
                self._apply_step_style(widgets, "complete", idx, STEP_UI_TITLES[idx])
            elif idx == no:
                self._apply_step_style(widgets, "current", idx, STEP_UI_TITLES[idx])
            else:
                self._apply_step_style(widgets, "waiting", idx, STEP_UI_TITLES[idx])
        self.current_progress.setValue(0)
        self.current_progress_label.setText(f"현재 단계 진행률 · STEP {no} {STEP_UI_TITLES[no]}")

    def _set_stage_error(self):
        if self.current_stage in self.step_widgets:
            self._apply_step_style(self.step_widgets[self.current_stage], "error", self.current_stage, STEP_UI_TITLES[self.current_stage])

    def _on_pipeline_progress(self, overall: int, current: int, message: str):
        self.overall_progress.setValue(overall)
        self.current_progress.setValue(current)
        self.overall_progress_label.setText(f"전체 진행률")
        self.current_progress_label.setText(f"현재 단계 진행률 · {message}")

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

    def copy_log(self):
        text = self.log_box.toPlainText()
        if not text.strip():
            self.status_label.setText("복사할 진행 로그가 없습니다.")
            return
        QApplication.clipboard().setText(text)
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

        documents = list(self.current_documents)
        self._rebuild_provider(self._selected_provider_id(), save_selection=False)
        self.operation_busy = True
        self._sync_busy_state()
        self._set_start_button_mode("arming")
        self.stop_button_timer.start(1800)
        self._reset_stages()
        self.log_box.clear()
        self.response_box.clear()
        self.requirement_result_box.clear()
        self._select_result_tab(0)
        self.log_status_label.setText("실행 중")
        self.status_label.setText(f"문서 {len(documents)}개 · 분석 & 요구사항 추출 실행 중")
        self._append_log(f"Batch 작업 시작 · 문서 {len(documents)}개")
        self._append_log(f"AI Provider · {self.provider.metadata().display_name} / {self.provider.metadata().model}")

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

        meta = self.provider.metadata()
        for idx, item in enumerate(batch_results, start=1):
            document = Path(item.get("document") or item.get("source_document") or "document")
            analysis_text = item.get("analysis_text", "")
            req_data = item.get("requirement_data") or {}
            evaluation = item.get("evaluation") or {}
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
                self._append_log(f"분석 결과 DOCX 자동 저장 · {path.name}")
            except Exception as exc:
                self._append_log(f"분석 결과 DOCX 자동 저장 실패 · {document.name} · {exc}")

        self.last_analysis_text = "\n\n".join(analysis_sections)
        self.response_box.setPlainText(self.last_analysis_text)
        self.requirement_result_box.setPlainText("\n\n".join(requirement_sections))

        self.overall_progress.setValue(100)
        self.current_progress.setValue(100)
        for no, widgets in self.step_widgets.items():
            self._apply_step_style(widgets, "complete", no, STEP_UI_TITLES[no])

        success_count = len(batch_results)
        fail_count = len(batch_failures)
        avg_score = round(sum(scores) / len(scores)) if scores else "-"
        if fail_count:
            self._apply_step_style(self.step_widgets[7], "error", 7, STEP_UI_TITLES[7])
            self.log_status_label.setText("부분 완료")
            self.status_label.setText(f"부분 완료 · 성공 {success_count}개 / 실패 {fail_count}개 · Requirement {total_requirements}개")
            for failure in batch_failures:
                self._append_log(f"문서 실패 · {failure.get('document')} · {failure.get('error')}")
        else:
            self.log_status_label.setText("완료")
            self.status_label.setText(f"완료 · 문서 {success_count}개 · Requirement {total_requirements}개 · 평균 구조점수 {avg_score}/100")
        self._append_log(f"Batch 작업 완료 · 성공 {success_count}개 / 실패 {fail_count}개")
        try:
            saved_log = self._save_log_snapshot("complete" if not fail_count else "partial")
            if saved_log:
                self._append_log(f"진행 로그 자동 저장 · {saved_log.name}")
        except Exception as exc:
            self._append_log(f"진행 로그 자동 저장 실패 · {exc}")

        self.connection_state_provider = self._selected_provider_id()
        self.connection_state_signature = self._provider_signature()
        self._set_ai_connection_state("connected", "실제 분석/요구사항 추출 작업에서 선택 Provider가 정상 사용되었습니다.")
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
