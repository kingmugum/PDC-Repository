# -*- coding: utf-8 -*-
"""
oracle_checker_gui_onebyone_rev87.py

변경 사항:
- 3탭 구성 유지
- Step D/E 선택 방식 개선
  * 체크박스 클릭 = 선택
  * 이미 선택된 같은 TC를 다시 클릭하면 선택 해제
  * 아무 TC도 선택되지 않은 상태 허용
- 결과 상세 탭 유지
- TC 내부 진행 요약 4분할 유지
- rev33:
  * oracle_checker_main_rev23/24 계열의 input_conditions / input_results 구조 반영
  * 목록을 입력/출력 모두 1조건 1행 방식으로 표시
  * 요약 탭에서 입력/출력 actual/status/reason 모두 조건 수만큼 표시
  * Vector 연결 실패 시 Measurement 자동 시작 실패 팝업 중복 제거
- rev34:
  * 실행 중인 CANoe COM 객체 연결 및 유효성 검증 반영
- rev35:
  * CANoe 오인식 방지를 위해 연결 확인 / Measurement 시작 / TC Start / Worker 재연결 모두 VectorApplicationClient의 GetActiveObject 우선 + guarded fallback 정책으로 통일
  * CANoe 미실행 시 즉시 연결 실패 팝업
- rev40:
  * 설정 탭의 CANoe 연결 확인 / Measurement 시작 / Measurement 정지 버튼 제거
  * 필요 파일 확인/설치 영역을 한 칸 위로 이동하고 주의사항 음영 문구 추가
  * CANoe 15 고정 표시/검증 제거, 연결 시 버전 번호만 표시
  * Excel/로그/DBC/논리 CAN 등 마지막 설정 저장 및 시작 시 자동 기본값 탐색 적용
- rev44:
  * 목록 & 실행 탭에서 클릭한 TC 그룹 전체의 선택 음영을 결과 색상보다 우선 표시
  * 단일/다중 Start 카운트다운 문구가 각 탭의 Start 버튼에 표시되도록 공통 처리
  * 결과 상세 탭에 [결과 레포트 출력] 버튼 추가
  * 결과 상세 탭의 결과 목록/상세 영역 확대 및 실행 로그 높이 축소
  * Oracle Checker 최종 판정 HTML 레포트 출력 지원
- rev45:
  * 로그 재검토 설정에 [다중 TC 수행 시 로그 검토] 옵션 추가
  * 다중 TC 수행 종료 후 선택 TC 로그 일괄 재검토 결과를 최종 판정/상세/레포트에 연동
  * Vector 연결은 GetActiveObject 우선 + 기존 제품 프로세스 확인 기반 guarded Dispatch fallback으로 통일
  * 실시간 PASS는 로그 재검토 결과와 무관하게 최종 PASS 유지
- rev87:
  * TC 목록 로드 worker에서 차량 송수신 DBC/입출력 사전 분석까지 함께 수행하여 최초 TC 클릭 렉 제거
  * 로드 popup에 `차량 송수신 테스트: DBC 사전 로드/자동 진단 요약 사전 분석` 단계 표시
  * rev50 기능 및 UI/판정 정책, CANoe COM 진단 기능 유지
  * Vector guarded 연결 정책과 실시간 PASS 우선 정책 유지
  * DBC 자동 설정 폴더 및 [네트워크/DBC 자동 매핑] 기능 추가
  * ASC/로그 파일명/CANoe Configuration에서 명시적인 CAN1~CAN3 ↔ XXX-CAN 근거를 탐색
  * P-CAN/P1-CAN 별칭을 동일 취급하고, DBC 파일명이 정확히 1개 후보일 때만 자동 입력
  * 근거 없음/충돌/DBC 0개/복수 후보는 기존 수동 DBC 선택값을 보존
  * rev87 Stimulus 실제 입력 로직은 본 모듈에 추가하지 않음
  * 기존 CANoeClient 호환명은 유지하되 내부 구현은 CANoe/CANalyzer 공통 VectorApplicationClient로 확장
  * 자동/CANoe/CANalyzer 연결 대상 선택, 제품별 ProgID + Registry CLSID GetActiveObject 탐색 지원
  * 구형 32-bit CANalyzer Runtime Kernel도 프로세스 ProductName/FileDescription/경로 기반 진단 대상으로 확장
  * TX/RX는 연결된 Vector client만 Stimulus 모듈에 주입
  * 설정/단일/다중/결과/TXRX 전체 탭을 공통 Canvas 기반 가로·세로 스크롤 작업면으로 구성
  * 고정 minsize 1480x780을 제거하고 모니터 해상도 기반 초기 창 + minsize 900x600 적용
- rev87:
  * 사용자 선택형 Ch1~Ch4 물리 채널 설정을 제거
  * PassFail은 CANoe 논리 네트워크 CAN1/CAN2/CAN3만 사용하고 CAN1→1, CAN2→2, CAN3→3으로 고정
  * 설정 화면은 논리 CAN과 DBC만 표시하며 VN1640A 물리 포트 매핑은 CANoe Hardware Configuration 책임으로 분리
  * 다중 순차실행에서만 realtime timeout을 0(자동 timeout OFF)으로 override; 단일 TC 수행의 기존 timeout 정책은 유지
"""

from __future__ import annotations

import datetime as _dt
import math
import queue
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import importlib.util
import re
import difflib
import sys
import subprocess
import atexit
import shutil
import json
import webbrowser

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText


# -----------------------------------------------------
# __pycache__ 생성 억제 및 기존 캐시 폴더 정리
# -----------------------------------------------------
sys.dont_write_bytecode = True

def _cleanup_pycache(base_dir=None):
    try:
        root = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent
        for p in root.glob("__pycache__"):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
    except Exception:
        pass

_cleanup_pycache()
atexit.register(_cleanup_pycache)


GUI_DEBUG_ENABLED = False

REQUIRED_FILES_RESTART_GUIDE = (
    "\n\n"
    "만약 지속적으로 설치완료가 되지 않았다고 표시될 경우\n"
    "GUI 프로그램을 종료 후 재 실행 해보세요."
)


def _hidden_subprocess_kwargs() -> Dict[str, object]:
    """Windows .pyw 실행 중 subprocess 호출 시 검은 콘솔창이 뜨지 않도록 한다."""
    if not sys.platform.startswith("win"):
        return {}

    kwargs: Dict[str, object] = {}
    try:
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if create_no_window:
            kwargs["creationflags"] = create_no_window

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        kwargs["startupinfo"] = startupinfo
    except Exception:
        pass
    return kwargs


_COUNTERPART_REV_RE = re.compile(
    r"^(?P<base>{base})"
    r"(?:(?P<sep>[_\-.])rev(?P<sep2>[_\-.])?(?P<num>\d+))?$",
    re.IGNORECASE,
)


def _find_latest_rev_file(base_dir: Path, base_name: str) -> Path:
    pattern = _COUNTERPART_REV_RE.pattern.format(base=re.escape(base_name))
    rx = re.compile(pattern, re.IGNORECASE)
    candidates: List[Tuple[int, Path]] = []

    for p in base_dir.glob(f"{base_name}*.py"):
        if not p.is_file():
            continue
        m = rx.match(p.stem)
        if not m:
            continue
        num = m.group("num")
        rev = int(num) if num is not None else -1
        candidates.append((rev, p))

    if not candidates:
        raise FileNotFoundError(
            f"{base_name} 계열 파일을 찾지 못했습니다. 예: {base_name}.py / {base_name}_rev02.py"
        )

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _load_module_by_file(module_file: Path, unique_name_hint: str):
    module_name = f"_dyn_{unique_name_hint}_{module_file.stem}".replace(".", "_").replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, str(module_file))
    if spec is None or spec.loader is None:
        raise ImportError(f"spec 생성 실패: {module_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise

    return module


def _load_latest_core_module():
    gui_dir = Path(__file__).resolve().parent
    selected = _find_latest_rev_file(gui_dir, "oracle_checker_main")
    module = _load_module_by_file(selected, unique_name_hint="oracle_checker_main")
    return module, selected


def _load_latest_report_module():
    gui_dir = Path(__file__).resolve().parent
    selected = _find_latest_rev_file(gui_dir, "oracle_checker_report")
    module = _load_module_by_file(selected, unique_name_hint="oracle_checker_report")
    return module, selected


try:
    core, CORE_MODULE_PATH = _load_latest_core_module()
except Exception as e:
    raise ImportError(
        "oracle_checker_main*.py를 자동으로 불러오지 못했습니다. "
        "oracle_checker_gui*.py와 같은 폴더에 두었는지 확인하세요. "
        f"원인: {e}"
    ) from e


try:
    report_module, REPORT_MODULE_PATH = _load_latest_report_module()
except Exception:
    report_module = None
    REPORT_MODULE_PATH = None


def _load_latest_collector_module():
    gui_dir = Path(__file__).resolve().parent
    selected = _find_latest_rev_file(gui_dir, "oracle_checker_collector")
    module = _load_module_by_file(selected, unique_name_hint="oracle_checker_collector")
    return module, selected


try:
    collector_module, COLLECTOR_MODULE_PATH = _load_latest_collector_module()
    COLLECTOR_AVAILABLE = True
    COLLECTOR_IMPORT_ERROR = ""
except Exception as e:
    collector_module = None
    COLLECTOR_MODULE_PATH = None
    COLLECTOR_AVAILABLE = False
    COLLECTOR_IMPORT_ERROR = f"{type(e).__name__}: {e}"


class OracleCheckerGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Oracle Checker - 입력/출력 다중 조건 판정 | core={CORE_MODULE_PATH.name}")
        # rev87: 고정 1760x930 / 최소 1480x780 강제를 제거한다.
        # 작은 노트북에서도 창 자체가 화면 밖으로 밀려나지 않도록 현재 모니터 크기에 맞춰 시작 크기를 결정하고,
        # 모든 Notebook 탭의 가로/세로 전체 스크롤로 부족한 작업영역을 탐색한다.
        try:
            screen_w = max(900, int(self.winfo_screenwidth()))
            screen_h = max(650, int(self.winfo_screenheight()))
        except Exception:
            screen_w, screen_h = 1366, 768
        target_w = min(1760, max(900, screen_w - 80))
        target_h = min(930, max(600, screen_h - 120))
        pos_x = max(0, min(40, (screen_w - target_w) // 2))
        pos_y = max(0, min(30, (screen_h - target_h) // 2))
        self.geometry(f"{target_w}x{target_h}+{pos_x}+{pos_y}")
        self.minsize(900, 600)

        self.big_start_font = ("맑은 고딕", 15, "bold")
        self.status_badge_font = ("맑은 고딕", 10, "bold")
        self.summary_header_font = ("맑은 고딕", 8, "bold")
        self.summary_text_font = ("맑은 고딕", 8)

        self.log_queue: queue.Queue = queue.Queue()

        self._app_dir = Path(__file__).resolve().parent
        self._settings_path = self._app_dir / "oracle_checker_gui_settings.json"
        self._settings_data = self._load_user_settings()
        self.last_canoe_diag_path = ""

        self.excel_path_var = tk.StringVar(value="")
        self.sheet_var = tk.StringVar(value="")
        self.bus_name_var = tk.StringVar(value="CAN")
        self.vector_product_var = tk.StringVar(value="자동")
        self.poll_interval_var = tk.StringVar(value="0.05")
        self.measurement_wait_var = tk.StringVar(value="8.0")
        self.default_timeout_var = tk.StringVar(value="30")

        self.log_file_var = tk.StringVar(value="")
        self.log_dir_var = tk.StringVar(value="")
        # rev87: CAN 네트워크명 근거 기반 DBC 자동 매핑 설정
        self.dbc_auto_dir_var = tk.StringVar(value="")
        self.dbc_auto_status_var = tk.StringVar(value="자동 매핑: 미실행")

        self.default_drop_seconds = "0.0"
        self.default_log_wait_seconds = "5.0"
        self.drop_first_seconds_var = tk.StringVar(value=self.default_drop_seconds)
        self.log_wait_timeout_var = tk.StringVar(value=self.default_log_wait_seconds)

        self.auto_log_review_var = tk.BooleanVar(value=True)
        self.auto_find_latest_log_var = tk.BooleanVar(value=True)
        self.auto_stop_measurement_var = tk.BooleanVar(value=True)
        self.skip_log_review_on_pass_var = tk.BooleanVar(value=True)
        # rev45 도입 / rev87 유지: 다중 TC 수행 전용 로그 재검토 옵션. 대용량 로그 부담을 고려해 기본값은 OFF.
        self.multi_log_review_var = tk.BooleanVar(value=False)
        self.manual_log_enabled_var = tk.BooleanVar(value=False)
        self.manual_timing_enabled_var = tk.BooleanVar(value=False)

        self.can_names = ["CAN1", "CAN2", "CAN3"]
        # rev87: PassFail은 Vector HW 물리 포트(CH1~CH4)를 관리하지 않는다.
        # CANoe/CANalyzer Configuration에 노출된 논리 CAN 이름을 그대로 사용한다.
        # CAN1 -> COM/ASC channel 1, CAN2 -> 2, CAN3 -> 3 으로 고정한다.
        self.can_logical_channel_by_name: Dict[str, int] = {
            name: int(name[3:]) for name in self.can_names
        }
        self.can_dbc_vars: Dict[str, tk.StringVar] = {
            "CAN1": tk.StringVar(value=""),
            "CAN2": tk.StringVar(value=""),
            "CAN3": tk.StringVar(value=""),
        }
        self.can_network_vars: Dict[str, tk.StringVar] = {
            "CAN1": tk.StringVar(value="-"),
            "CAN2": tk.StringVar(value="-"),
            "CAN3": tk.StringVar(value="-"),
        }

        # rev87: optional read-only CAPL Event Collector. Default ON; if unavailable it must
        # transparently fall back to the existing COM polling + ASC/BLF review path.
        self.collector_enabled_var = tk.BooleanVar(value=True)

        self._apply_saved_or_auto_defaults()

        self.status_var = tk.StringVar(value="대기중")
        self.canoe_status_var = tk.StringVar(value="Vector 연결 : -")
        self.measurement_status_var = tk.StringVar(value="Measurement: 확인 전")
        self.pywin32_status_var = tk.StringVar(value="필요 파일: 확인 전")
        self.selected_tc_status_var = tk.StringVar(value="선택 TC: -")
        self.collector_status_var = tk.StringVar(
            value=("CAPL Collector: 사용(기본) / .can 생성·Compile 필요" if COLLECTOR_AVAILABLE else "CAPL Collector: 모듈 없음 → 기존 방식")
        )

        self.pywin32_status_label = None
        self.pywin32_install_button = None
        self.pywin32_check_button = None

        self.condition_rows: List[core.OracleRowLoadResult] = []
        self.results: List[core.FinalCheckResult] = []
        self.current_result: Optional[core.FinalCheckResult] = None
        self.client: Optional[core.CANoeClient] = None
        self.monitor_thread: Optional[threading.Thread] = None

        self._collector_lock = threading.RLock()
        self._collector_hit_cache: Dict[str, Dict[str, Any]] = {}
        self._collector_functions: Dict[str, Any] = {}
        self._collector_runtime_targets_by_id: Dict[int, Any] = {}
        self._collector_poll_after_id = None
        self._collector_runtime_active = False
        self._collector_catalog_cache = None
        self._collector_catalog_cache_key = None
        self._collector_last_bind_failed_signature = None
        self._measurement_started_perf: Optional[float] = None

        self.stop_event = threading.Event()
        self.done_event = threading.Event()

        self.notebook: Optional[ttk.Notebook] = None
        self.settings_tab = None
        self.run_tab = None
        self.detail_tab = None
        # rev87: Notebook 각 탭 전체를 양방향으로 탐색하기 위한 공통 scroll registry.
        # key=str(tab widget), value={canvas, content, window, vbar, hbar}.
        self._tab_scroll_registry: Dict[str, Dict[str, Any]] = {}
        self._tab_scroll_wheel_bound = False

        self.drop_entry: Optional[ttk.Entry] = None
        self.log_wait_entry: Optional[ttk.Entry] = None
        self.log_text: Optional[ScrolledText] = None

        self.display_rows: List[Dict] = []
        self.tc_display_map: Dict[str, List[str]] = {}
        self.tc_sort_column: Optional[str] = None
        self.tc_sort_reverse: bool = False
        self.tc_result_status_by_index: Dict[int, str] = {}
        self._dbc_choice_cache_key = None
        self._dbc_choice_db_by_ch = {}

        self.selected_condition_index: Optional[int] = None

        self.tc_tree = None
        self.result_tree = None
        self.report_button = None
        self.current_status_label = None
        self.current_detail = None
        self.tc_preview_detail = None
        self.start_button = None
        self.complete_button = None
        self.abort_button = None
        self.canoe_status_label = None
        self.measurement_status_label = None

        self.summary_input_canoe_inner = None
        self.summary_input_log_inner = None
        self.summary_output_canoe_inner = None
        self.summary_output_log_inner = None

        self._countdown_running = False

        # rev87 UI responsiveness / staged progress feedback
        self.ui_async_queue: queue.Queue = queue.Queue()
        self._conditions_load_thread: Optional[threading.Thread] = None
        self._operation_popup = None
        self._operation_popup_title_var = tk.StringVar(value="")
        self._operation_popup_stage_var = tk.StringVar(value="")
        self._operation_popup_percent_var = tk.StringVar(value="0%")
        self._operation_popup_canvas = None
        self._operation_popup_fill = None
        self._operation_popup_pct = 0.0
        self._tab_change_after_id = None
        self._tab_loading_after_id = None
        # rev87: Windows maximize/resize 중 ttk.Notebook이 마지막 추가 탭(1안)으로
        # 비의도 전환되는 현상을 막기 위해 사용자가 명시적으로 선택한 탭을 별도 보존한다.
        self._notebook_intended_tab = None
        self._notebook_resize_restore_after_id = None
        self._notebook_selection_change_armed = False

        self._build_ui()
        try:
            self.after_idle(self._remember_current_notebook_tab)
        except Exception:
            pass
        self._initialize_excel_sheet_combo_from_current_path()
        self._refresh_required_files_status(show_popup=False)
        self._poll_log_queue()

    def _debug(self, text: str):
        if not GUI_DEBUG_ENABLED:
            return
        msg = f"[DEBUG][GUI] {text}"
        try:
            print(msg, flush=True)
        except Exception:
            pass
        if hasattr(self, "log_text") and self.log_text is not None:
            self._log(msg + "\n")

    # -------------------------------------------------
    # 설정 저장 / 시작 시 자동 기본값 탐색
    # -------------------------------------------------
    def _load_user_settings(self) -> Dict:
        try:
            if self._settings_path.exists():
                with open(self._settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    def _save_current_user_settings(self) -> None:
        """현재 GUI 입력값을 같은 폴더의 json 파일에 저장한다."""
        try:
            data = {
                "excel_path": self.excel_path_var.get().strip(),
                "sheet_name": self.sheet_var.get().strip(),
                "log_dir": self.log_dir_var.get().strip(),
                "log_file": self.log_file_var.get().strip(),
                "dbc_auto_dir": self.dbc_auto_dir_var.get().strip(),
                "can_network": {name: var.get().strip() for name, var in self.can_network_vars.items()},
                "channel_model": "CANoeLogicalFixed",
                "can_dbc": {name: var.get().strip() for name, var in self.can_dbc_vars.items()},
                "bus_name": self.bus_name_var.get().strip(),
                "vector_product_preference": self.vector_product_var.get().strip(),
                "poll_interval": self.poll_interval_var.get().strip(),
                "measurement_wait": self.measurement_wait_var.get().strip(),
                "default_timeout": self.default_timeout_var.get().strip(),
                "drop_first_seconds": self.drop_first_seconds_var.get().strip(),
                "log_wait_timeout": self.log_wait_timeout_var.get().strip(),
                "auto_log_review": bool(self.auto_log_review_var.get()),
                "auto_find_latest_log": bool(self.auto_find_latest_log_var.get()),
                "auto_stop_measurement": bool(self.auto_stop_measurement_var.get()),
                "skip_log_review_on_pass": bool(self.skip_log_review_on_pass_var.get()),
                "multi_log_review": bool(self.multi_log_review_var.get()),
                "manual_log_enabled": bool(self.manual_log_enabled_var.get()),
                "manual_timing_enabled": bool(self.manual_timing_enabled_var.get()),
                "collector_enabled": bool(self.collector_enabled_var.get()),
            }
            with open(self._settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._settings_data = data
        except Exception:
            pass

    @staticmethod
    def _existing_file(path_text: str) -> str:
        try:
            p = Path(path_text).expanduser()
            return str(p) if p.is_file() else ""
        except Exception:
            return ""

    @staticmethod
    def _existing_dir(path_text: str) -> str:
        try:
            p = Path(path_text).expanduser()
            return str(p) if p.is_dir() else ""
        except Exception:
            return ""

    @staticmethod
    def _natural_path_key(path: Path):
        nums = [int(x) for x in re.findall(r"\d+", path.stem)]
        try:
            mtime = path.stat().st_mtime
        except Exception:
            mtime = 0
        # 파일명에 숫자/날짜가 있으면 그것을 먼저, 없으면 수정시각을 보조로 사용
        return (1 if nums else 0, nums, mtime, path.name.lower())

    def _pick_latest_file(self, patterns: List[str], preferred_keywords: Optional[List[str]] = None) -> str:
        preferred_keywords = [x.lower() for x in (preferred_keywords or [])]
        candidates: List[Path] = []
        for pat in patterns:
            candidates.extend(p for p in self._app_dir.glob(pat) if p.is_file())
        clean: List[Path] = []
        for p in candidates:
            name_low = p.name.lower()
            if p.name.startswith("~$"):
                continue
            if any(skip in name_low for skip in ("oracle_final_result", "final_result", "result_")):
                continue
            clean.append(p)
        if not clean:
            return ""
        preferred = [p for p in clean if any(k in p.name.lower() for k in preferred_keywords)]
        pool = preferred or clean
        try:
            return str(max(pool, key=self._natural_path_key))
        except Exception:
            return str(pool[0])

    def _pick_latest_log_dir(self) -> str:
        candidates: List[Path] = []
        try:
            # 현재 폴더 자체에 로그가 있으면 후보에 포함
            if any(self._app_dir.glob("*.blf")) or any(self._app_dir.glob("*.asc")):
                candidates.append(self._app_dir)
            for p in self._app_dir.iterdir():
                if not p.is_dir() or p.name == "__pycache__":
                    continue
                low = p.name.lower()
                has_log_name = any(k in low for k in ("log", "로그", "blf", "asc", "canoe"))
                has_log_file = any(p.glob("*.blf")) or any(p.glob("*.asc"))
                if has_log_name or has_log_file:
                    candidates.append(p)
        except Exception:
            return ""
        if not candidates:
            return ""
        try:
            return str(max(candidates, key=self._natural_path_key))
        except Exception:
            return str(candidates[0])

    def _auto_detect_dbc_map(self) -> Dict[str, str]:
        candidates: List[Path] = []
        try:
            candidates.extend(p for p in self._app_dir.glob("*.dbc") if p.is_file())
            for folder in self._app_dir.iterdir():
                if folder.is_dir() and folder.name != "__pycache__":
                    candidates.extend(p for p in folder.glob("*.dbc") if p.is_file())
        except Exception:
            return {}
        unique = sorted(set(candidates), key=self._natural_path_key)
        # DBC가 3개 이상이면 CAN1/2/3에 임의 매핑하지 않음
        if len(unique) >= 3:
            return {}
        out: Dict[str, str] = {}
        for can_name, p in zip(self.can_names, unique):
            out[can_name] = str(p)
        return out

    def _apply_saved_or_auto_defaults(self) -> None:
        data = self._settings_data if isinstance(self._settings_data, dict) else {}

        saved_excel = self._existing_file(str(data.get("excel_path", "")))
        auto_excel = self._pick_latest_file(
            ["*.xlsx", "*.xlsm"],
            preferred_keywords=["모음", "testcase", "oracle", "tc"],
        )
        self.excel_path_var.set(saved_excel or auto_excel or "")
        if data.get("sheet_name"):
            self.sheet_var.set(str(data.get("sheet_name", "")))

        saved_log_dir = self._existing_dir(str(data.get("log_dir", "")))
        self.log_dir_var.set(saved_log_dir or self._pick_latest_log_dir() or "")

        saved_log_file = self._existing_file(str(data.get("log_file", "")))
        if saved_log_file:
            self.log_file_var.set(saved_log_file)

        saved_dbc_auto_dir = self._existing_dir(str(data.get("dbc_auto_dir", "")))
        if saved_dbc_auto_dir:
            self.dbc_auto_dir_var.set(saved_dbc_auto_dir)

        saved_network = data.get("can_network") if isinstance(data.get("can_network"), dict) else {}
        for name, value in saved_network.items():
            if name in self.can_network_vars and str(value).strip():
                self.can_network_vars[name].set(str(value).strip())

        # rev87: 과거 can_ch(물리 채널) 저장값은 의도적으로 무시한다.

        saved_dbc = data.get("can_dbc") if isinstance(data.get("can_dbc"), dict) else {}
        any_saved_dbc = False
        for name, value in saved_dbc.items():
            path = self._existing_file(str(value))
            if name in self.can_dbc_vars and path:
                self.can_dbc_vars[name].set(path)
                any_saved_dbc = True
        if not any_saved_dbc:
            for name, path in self._auto_detect_dbc_map().items():
                if name in self.can_dbc_vars:
                    self.can_dbc_vars[name].set(path)

        simple_string_vars = {
            "bus_name": self.bus_name_var,
            "vector_product_preference": self.vector_product_var,
            "poll_interval": self.poll_interval_var,
            "measurement_wait": self.measurement_wait_var,
            "default_timeout": self.default_timeout_var,
            "drop_first_seconds": self.drop_first_seconds_var,
            "log_wait_timeout": self.log_wait_timeout_var,
        }
        for key, var in simple_string_vars.items():
            value = str(data.get(key, "")).strip()
            if value:
                var.set(value)

        simple_bool_vars = {
            "auto_log_review": self.auto_log_review_var,
            "auto_find_latest_log": self.auto_find_latest_log_var,
            "auto_stop_measurement": self.auto_stop_measurement_var,
            "skip_log_review_on_pass": self.skip_log_review_on_pass_var,
            "multi_log_review": self.multi_log_review_var,
            "manual_log_enabled": self.manual_log_enabled_var,
            "manual_timing_enabled": self.manual_timing_enabled_var,
            "collector_enabled": self.collector_enabled_var,
        }
        for key, var in simple_bool_vars.items():
            if key in data:
                try:
                    var.set(bool(data[key]))
                except Exception:
                    pass

    def _initialize_excel_sheet_combo_from_current_path(self) -> None:
        path = self.excel_path_var.get().strip()
        if not path:
            return
        try:
            sheets = core.list_excel_sheets(path)
            if hasattr(self, "sheet_combo"):
                self.sheet_combo.configure(values=sheets)
            if sheets:
                current = self.sheet_var.get().strip()
                if current not in sheets:
                    preferred = next((s for s in sheets if s.upper() not in ("TEMPLATE", "README", "공통")), sheets[0])
                    self.sheet_var.set(preferred)
        except Exception:
            pass

    def _bind_save_on_focusout(self, widget) -> None:
        try:
            widget.bind("<FocusOut>", lambda _event: self._save_current_user_settings(), add="+")
        except Exception:
            pass

    @staticmethod
    def _format_canoe_version(version_text: str) -> str:
        text = str(version_text or "").strip()
        if not text:
            return "-"
        return text.splitlines()[0].strip() or "-"

    def _short_reason(self, status: str, message: str) -> str:
        s = (status or "").strip().upper()
        m = (message or "").strip()

        if s == "PASS":
            return ""

        low = m.lower()

        if "사용자 중지" in m:
            return "사용자 중지"
        if "사용자 중단" in m:
            return "사용자 중단"
        if "로그 파일을 찾지 못함" in m:
            return "로그 없음"
        if "dbc" in low and ("찾지 못" in m or "미지정" in m or "로드" in m):
            return "DBC 오류"
        if "signal 읽기 실패" in m or "읽기 실패" in m:
            return "읽기 오류"
        if "신호 미관측" in m:
            return "미관측"
        if "미관측" in m:
            return "미관측"
        if "값 불일치" in m:
            return "값 불일치"
        if "제한시간" in m and "미관측" in m:
            return "미관측"
        if "입력 조건 미충족" in m:
            return "입력 미충족"
        if "출력 조건 미충족" in m:
            return "출력 미충족"
        if "오류" in m:
            return "오류"

        if s == "ERROR":
            return "오류"
        if s in ("FAIL", "N/A"):
            return "미관측"

        return m[:20] if m else ""

    def _format_actual_value(self, raw) -> str:
        if raw is None:
            return "-"
        return str(raw)

    def _format_log_actual_value(self, check) -> str:
        """로그 재검토 결과의 Actual 표시 전용.

        로그 파일/DBC 오류/사용자 중단처럼 '관측 시도 자체가 유효하게 완료되지 않은'
        경우에는 기존 '-' 표시를 유지한다. 반면 로그 재검토가 정상 수행됐지만
        기대 Signal 값이 한 번도 관측되지 않아 FAIL이고 observed_value_raw가 None이면
        사용자가 결과 의미를 즉시 알 수 있도록 '미관측'으로 표시한다.
        """
        if check is None:
            return "-"
        raw = getattr(check, "observed_value_raw", None)
        if raw is not None:
            return str(raw)
        status = str(getattr(check, "status", "") or "").strip().upper()
        message = str(getattr(check, "message", "") or "")
        if status == "FAIL" and ("미관측" in message or "예상 결과값" in message):
            return "미관측"
        return "-"

    # -------------------------------------------------
    # rev87 공통 Notebook 탭 양방향 스크롤
    # -------------------------------------------------
    def _create_scrollable_notebook_tab(self, text: str, padding: int = 6):
        """Notebook 탭을 Canvas 기반 X/Y 작업면으로 만든다.

        rev87 성능 개선: 과거에는 content/canvas <Configure>마다 즉시 winfo_reqwidth/height를
        반복 계산해 탭 전환 시 레이아웃 연쇄가 발생했다. 이제 35ms debounce + active-tab 우선
        동기화로 불필요한 재계산을 줄인다.
        """
        if self.notebook is None:
            raise RuntimeError("Notebook이 생성되기 전에 scrollable tab을 만들 수 없습니다.")

        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=text)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)

        host = ttk.Frame(tab)
        host.grid(row=0, column=0, sticky="nsew")
        host.columnconfigure(0, weight=1)
        host.rowconfigure(0, weight=1)

        canvas = tk.Canvas(host, highlightthickness=0, borderwidth=0)
        vbar = ttk.Scrollbar(host, orient="vertical", command=canvas.yview)
        hbar = ttk.Scrollbar(host, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        ttk.Frame(host, width=16, height=16).grid(row=1, column=1, sticky="nsew")

        content = ttk.Frame(canvas, padding=padding)
        window = canvas.create_window((0, 0), window=content, anchor="nw")
        info = {
            "tab": tab, "canvas": canvas, "content": content, "window": window,
            "vbar": vbar, "hbar": hbar, "text": text, "sync_after_id": None,
        }
        self._tab_scroll_registry[str(tab)] = info

        def _sync_now(tab_key=str(tab)):
            current = self._tab_scroll_registry.get(tab_key)
            if not current:
                return
            current["sync_after_id"] = None
            c, inner, win = current["canvas"], current["content"], current["window"]
            try:
                c.update_idletasks()
                view_w = max(1, int(c.winfo_width()))
                view_h = max(1, int(c.winfo_height()))
                req_w = max(1, int(inner.winfo_reqwidth()))
                req_h = max(1, int(inner.winfo_reqheight()))
                work_w, work_h = max(view_w, req_w), max(view_h, req_h)
                c.itemconfigure(win, width=work_w, height=work_h)
                c.configure(scrollregion=(0, 0, work_w, work_h))
            except Exception:
                try:
                    bbox = c.bbox("all")
                    if bbox:
                        c.configure(scrollregion=bbox)
                except Exception:
                    pass

        def _schedule_sync(_event=None, tab_key=str(tab), delay=35):
            current = self._tab_scroll_registry.get(tab_key)
            if not current:
                return
            prior = current.get("sync_after_id")
            if prior is not None:
                try:
                    self.after_cancel(prior)
                except Exception:
                    pass
            current["sync_after_id"] = self.after(max(1, int(delay)), lambda: _sync_now(tab_key))

        info["sync_now"] = _sync_now
        info["schedule_sync"] = _schedule_sync
        content.bind("<Configure>", _schedule_sync, add="+")
        canvas.bind("<Configure>", _schedule_sync, add="+")
        try:
            self.after_idle(lambda: _schedule_sync(delay=1))
        except Exception:
            pass
        return tab, content

    def _scroll_widget_is_descendant(widget, ancestor) -> bool:
        current = widget
        while current is not None:
            if current is ancestor:
                return True
            current = getattr(current, "master", None)
        return False

    @staticmethod
    def _tab_mousewheel_units(event) -> int:
        num = getattr(event, "num", None)
        if num == 4:
            return -3
        if num == 5:
            return 3
        delta = int(getattr(event, "delta", 0) or 0)
        if delta == 0:
            return 0
        notches = max(1, min(4, abs(delta) // 120 if abs(delta) >= 120 else 1))
        return (-3 if delta > 0 else 3) * notches

    def _find_inner_scroll_widget(self, widget, tab, axis: str = "y"):
        """포인터 아래에서 자체 scroll 가능한 Text/Treeview/Listbox/Canvas 조상을 찾는다."""
        outer = self._tab_scroll_registry.get(str(tab), {}).get("canvas")
        current = widget
        method_name = "yview" if axis == "y" else "xview"
        while current is not None and current is not tab:
            if current is not outer and callable(getattr(current, method_name, None)):
                # Frame/Label 등의 우연한 속성은 제외하고 실제 view tuple을 주는 위젯만 인정.
                try:
                    view = getattr(current, method_name)()
                    if isinstance(view, (tuple, list)) and len(view) == 2:
                        return current
                except Exception:
                    pass
            current = getattr(current, "master", None)
        return None

    # -------------------------------------------------
    # rev87 lightweight operation progress popup
    # -------------------------------------------------
    def _ensure_operation_popup(self, title: str = "처리 중"):
        if self._operation_popup is not None:
            try:
                if self._operation_popup.winfo_exists():
                    self._operation_popup.title(title)
                    return self._operation_popup
            except Exception:
                pass
        pop = tk.Toplevel(self)
        pop.title(title)
        pop.resizable(False, False)
        pop.transient(self)
        pop.protocol("WM_DELETE_WINDOW", lambda: None)
        body = ttk.Frame(pop, padding=14)
        body.pack(fill=tk.BOTH, expand=True)
        ttk.Label(body, textvariable=self._operation_popup_title_var, font=("맑은 고딕", 10, "bold")).pack(anchor="w")
        ttk.Label(body, textvariable=self._operation_popup_stage_var, foreground="#374151").pack(anchor="w", pady=(5, 8))
        row = ttk.Frame(body)
        row.pack(fill=tk.X)
        self._operation_popup_canvas = tk.Canvas(row, width=360, height=15, highlightthickness=1, highlightbackground="#D1D5DB")
        self._operation_popup_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._operation_popup_fill = self._operation_popup_canvas.create_rectangle(0, 0, 0, 15, fill="#22C55E", outline="")
        ttk.Label(row, textvariable=self._operation_popup_percent_var, width=6, anchor="e").pack(side=tk.LEFT, padx=(8, 0))
        self._operation_popup = pop
        try:
            self.update_idletasks()
            w, h = 445, 110
            x = self.winfo_rootx() + max(0, (self.winfo_width() - w) // 2)
            y = self.winfo_rooty() + max(0, (self.winfo_height() - h) // 2)
            pop.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass
        return pop

    def _show_operation_progress(self, title: str, stage: str, percent: float):
        pct = max(0.0, min(100.0, float(percent)))
        pop = self._ensure_operation_popup(title)
        self._operation_popup_title_var.set(title)
        self._operation_popup_stage_var.set(stage)
        self._operation_popup_percent_var.set(f"{pct:.0f}%")
        self._operation_popup_pct = pct
        try:
            pop.deiconify()
            pop.lift()
            c = self._operation_popup_canvas
            if c is not None and self._operation_popup_fill is not None:
                c.update_idletasks()
                width = max(1, int(c.winfo_width()))
                c.coords(self._operation_popup_fill, 0, 0, width * pct / 100.0, 15)
        except Exception:
            pass

    def _close_operation_progress(self, delay_ms: int = 120):
        target = self._operation_popup
        def _close():
            if target is not None:
                try:
                    target.destroy()
                except Exception:
                    pass
            if self._operation_popup is target:
                self._operation_popup = None
                self._operation_popup_canvas = None
                self._operation_popup_fill = None
        try:
            self.after(max(0, int(delay_ms)), _close)
        except Exception:
            _close()

    def _on_notebook_pointer_press(self, event):
        """사용자가 실제로 탭 헤더를 눌렀을 때만 의도 탭을 갱신한다."""
        if self.notebook is None:
            return None
        try:
            idx = self.notebook.index(f"@{int(event.x)},{int(event.y)}")
            tabs = self.notebook.tabs()
            if 0 <= idx < len(tabs):
                self._notebook_intended_tab = str(tabs[idx])
                self._notebook_selection_change_armed = True
        except Exception:
            pass
        return None

    def _select_notebook_tab_stable(self, tab):
        """프로그램이 의도적으로 탭을 바꿀 때도 resize 보호 기준을 함께 갱신한다."""
        if self.notebook is None or tab is None:
            return
        try:
            self._notebook_intended_tab = str(tab)
            self._notebook_selection_change_armed = True
            self.notebook.select(tab)
        except Exception:
            pass

    def _remember_current_notebook_tab(self):
        if self.notebook is None:
            return
        try:
            selected = str(self.notebook.select() or "")
            if selected:
                self._notebook_intended_tab = selected
        except Exception:
            pass

    def _on_root_configure_preserve_notebook(self, event=None):
        """창 최대화/복원/리사이즈만으로 선택 탭이 바뀌지 않도록 debounce 복원한다.

        Windows ttk에서 여러 Canvas 기반 탭이 동시에 <Configure>되는 순간 마지막으로 추가된
        탭이 선택되는 현장 증상을 방어한다. 사용자의 탭 클릭이나 명시적 programmatic select는
        `_notebook_intended_tab`을 먼저 갱신하므로 정상 탭 전환은 방해하지 않는다.
        """
        if event is not None and getattr(event, "widget", None) is not self:
            return None
        if self.notebook is None:
            return None
        if not self._notebook_intended_tab:
            self._remember_current_notebook_tab()
        prior = self._notebook_resize_restore_after_id
        if prior is not None:
            try:
                self.after_cancel(prior)
            except Exception:
                pass
        def _restore():
            self._notebook_resize_restore_after_id = None
            intended = self._notebook_intended_tab
            if not intended or self.notebook is None:
                return
            try:
                tabs = {str(t) for t in self.notebook.tabs()}
                current = str(self.notebook.select() or "")
                if intended in tabs and current != intended:
                    self.notebook.select(intended)
            except Exception:
                pass
        try:
            self._notebook_resize_restore_after_id = self.after(80, _restore)
        except Exception:
            _restore()
        return None

    def _on_notebook_tab_changed(self, _event=None):
        """Active tab만 debounce 동기화하고 짧은 중앙 로딩 표시를 제공한다.

        Tk layout 계산 자체는 main thread에서 수행되므로 계산이 시작된 뒤에는 새 after callback이
        그 사이에 끼어들 수 없다. 따라서 rev87는 팝업을 *계산 직전* 먼저 그린 뒤 sync를 수행하고
        완료 즉시 자동으로 닫는다. 동시에 content/canvas Configure sync는 35ms debounce되어
        탭 전환 때 불필요한 reqwidth/reqheight 연쇄 계산을 줄인다.
        """
        if self.notebook is None:
            return
        try:
            selected = self.notebook.select()
            if self._notebook_selection_change_armed:
                self._notebook_intended_tab = str(selected)
                self._notebook_selection_change_armed = False
            elif not self._notebook_intended_tab:
                self._notebook_intended_tab = str(selected)
            info = self._tab_scroll_registry.get(selected)
        except Exception:
            info = None
        if not info:
            return
        if self._tab_loading_after_id is not None:
            try:
                self.after_cancel(self._tab_loading_after_id)
            except Exception:
                pass
            self._tab_loading_after_id = None

        # 먼저 표시를 그려 둔 다음 레이아웃 계산을 수행한다. 빠른 탭에서도 약 0.1초 이내 자동 소멸한다.
        self._show_operation_progress("화면 준비 중", f"{info.get('text','탭')} 레이아웃 정리", 35)

        def _finish():
            try:
                fn = info.get("sync_now")
                if callable(fn):
                    fn()
                self._show_operation_progress("화면 준비 중", "완료", 100)
            finally:
                self._tab_loading_after_id = None
                self._close_operation_progress(70)
        self._tab_loading_after_id = self.after(8, _finish)

    def _on_global_tab_mousewheel(self, event):
        if self.notebook is None:
            return None
        try:
            selected = self.notebook.select()
            info = self._tab_scroll_registry.get(selected)
        except Exception:
            info = None
        if not info:
            return None

        widget = getattr(event, "widget", None)
        tab = info["tab"]
        if widget is None or not self._scroll_widget_is_descendant(widget, tab):
            return None

        units = self._tab_mousewheel_units(event)
        if units == 0:
            return None

        # Shift+Wheel은 가로, 일반 Wheel은 세로.
        horizontal = bool(int(getattr(event, "state", 0) or 0) & 0x0001)
        axis = "x" if horizontal else "y"
        inner = self._find_inner_scroll_widget(widget, tab, axis=axis)
        if inner is not None:
            try:
                first, last = (inner.xview() if horizontal else inner.yview())
                toward_end = units > 0
                can_scroll = (last < 0.999999) if toward_end else (first > 0.000001)
            except Exception:
                can_scroll = False
            if can_scroll:
                # class binding이 이 bind_all보다 먼저 실행되어 내부 위젯을 움직인다.
                # outer는 움직이지 않는다.
                return "break"

        try:
            if horizontal:
                info["canvas"].xview_scroll(int(units), "units")
            else:
                info["canvas"].yview_scroll(int(units), "units")
        except Exception:
            return None
        return "break"

    def _bind_global_tab_mousewheel(self):
        if self._tab_scroll_wheel_bound:
            return
        self.bind_all("<MouseWheel>", self._on_global_tab_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_global_tab_mousewheel, add="+")
        self.bind_all("<Button-5>", self._on_global_tab_mousewheel, add="+")
        self._tab_scroll_wheel_bound = True

    def _build_ui(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style(self)
        style.configure("TNotebook.Tab", padding=(18, 8), font=("맑은 고딕", 11, "bold"))

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<ButtonPress-1>", self._on_notebook_pointer_press, add="+")
        self.notebook.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed, add="+")
        self.bind("<Configure>", self._on_root_configure_preserve_notebook, add="+")

        self.settings_tab, self.settings_scroll_content = self._create_scrollable_notebook_tab("설정", padding=6)
        self.run_tab, self.run_scroll_content = self._create_scrollable_notebook_tab("단일 TC 수행", padding=6)
        self.detail_tab, self.detail_scroll_content = self._create_scrollable_notebook_tab("결과 상세", padding=6)

        self._build_settings_tab(self.settings_scroll_content)
        self._build_run_tab(self.run_scroll_content)
        self._build_detail_tab(self.detail_scroll_content)
        self._bind_global_tab_mousewheel()

    def _build_settings_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        self._build_top_frame(parent).pack(fill=tk.X, anchor=tk.W)
        self._build_canoe_frame(parent).pack(fill=tk.X, pady=(8, 0))

    def _build_run_tab(self, parent):
        # rev87: 목록 viewport를 좁게 고정하고 내부 X scrollbar로 원래 열 폭을 그대로 탐색한다.
        parent.columnconfigure(0, weight=0, minsize=760)
        parent.columnconfigure(1, weight=1, minsize=480)
        parent.rowconfigure(0, weight=12)
        parent.rowconfigure(1, weight=1)

        left_top = ttk.Frame(parent, width=760)
        left_top.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 6))
        left_top.grid_propagate(False)
        left_top.columnconfigure(0, weight=1)
        left_top.rowconfigure(0, weight=1)

        right_top = ttk.Frame(parent, width=500)
        right_top.grid(row=0, column=1, sticky="nsew", pady=(0, 6))
        right_top.columnconfigure(0, weight=1)
        right_top.rowconfigure(0, weight=1)

        bottom_full = ttk.Frame(parent, height=240)
        bottom_full.grid(row=1, column=0, columnspan=2, sticky="nsew")
        bottom_full.grid_propagate(False)
        bottom_full.columnconfigure(0, weight=1)
        bottom_full.rowconfigure(0, weight=1)

        self._build_tc_frame(left_top).grid(row=0, column=0, sticky="nsew")
        self._build_action_frame(right_top).grid(row=0, column=0, sticky="nsew")
        self._build_summary_frame(bottom_full).grid(row=0, column=0, sticky="nsew")

    def _build_detail_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=2)
        parent.rowconfigure(1, weight=1)

        top = ttk.Frame(parent)
        top.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        top.columnconfigure(0, weight=2, uniform="detail_top")
        top.columnconfigure(1, weight=1, uniform="detail_top")
        top.rowconfigure(0, weight=1)

        result_frame = self._build_result_frame(top)
        result_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        detail_frame = ttk.LabelFrame(top, text="선택 TC / 최종 판정 상세")
        detail_frame.grid(row=0, column=1, sticky="nsew")
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(0, weight=1)

        self.current_detail = ScrolledText(detail_frame, height=10, wrap=tk.WORD)
        self.current_detail.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.current_detail.insert("1.0", "선택 TC의 최종 판정 결과가 여기에 표시됩니다.\n")

        log_frame = self._build_log_frame(parent)
        log_frame.grid(row=1, column=0, sticky="nsew")

    def _build_top_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Step A/B. 테스트 오라클 엑셀 및 차종 시트 선택")
        frame.columnconfigure(1, weight=0)

        ttk.Label(frame, text="Oracle Excel").grid(row=0, column=0, sticky="w", padx=6, pady=5)
        excel_entry = ttk.Entry(frame, textvariable=self.excel_path_var, width=90)
        excel_entry.grid(row=0, column=1, sticky="w", padx=6, pady=5)
        self._bind_save_on_focusout(excel_entry)
        ttk.Button(frame, text="찾아보기", command=self._browse_excel).grid(row=0, column=2, sticky="ew", padx=6, pady=5)

        ttk.Label(frame, text="차종 시트").grid(row=1, column=0, sticky="w", padx=6, pady=5)
        self.sheet_combo = ttk.Combobox(frame, textvariable=self.sheet_var, state="readonly", values=[], width=88)
        self.sheet_combo.grid(row=1, column=1, sticky="w", padx=6, pady=5)
        self.sheet_combo.bind("<<ComboboxSelected>>", lambda _event: self._save_current_user_settings(), add="+")

        self.load_tc_button = tk.Button(
            frame,
            text="TC 목록 로드",
            command=self._load_conditions,
            bg="#F59E0B",
            fg="black",
            activebackground="#D97706",
            activeforeground="black",
            relief="raised",
            bd=1,
            font=("맑은 고딕", 10),
            cursor="hand2",
            padx=6,
            pady=1,
        )
        self.load_tc_button.grid(row=1, column=2, sticky="ew", padx=6, pady=5)

        return frame

    def _build_canoe_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Step C. Vector 연결 / Measurement / 로그 설정")
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=0)
        frame.columnconfigure(2, weight=1)

        can_frame = ttk.LabelFrame(frame, text="DBC 설정 (차량 CAN 기준)")
        can_frame.grid(row=0, column=0, sticky="nw", padx=6, pady=(4, 6))
        can_frame.columnconfigure(3, weight=0)

        # rev87: 네트워크명 식별 후 DBC 폴더에서 엄격하게 1개 후보만 자동 선택한다.
        ttk.Label(can_frame, text="DBC 자동 설정 폴더").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        dbc_auto_entry = ttk.Entry(can_frame, textvariable=self.dbc_auto_dir_var, width=62)
        dbc_auto_entry.grid(row=0, column=1, columnspan=2, sticky="w", padx=6, pady=4)
        self._bind_save_on_focusout(dbc_auto_entry)
        ttk.Button(can_frame, text="폴더 선택", command=self._browse_dbc_auto_dir).grid(
            row=0, column=3, sticky="ew", padx=6, pady=4
        )
        ttk.Button(can_frame, text="네트워크/DBC 자동 매핑", command=self._auto_map_dbc_from_network_names).grid(
            row=0, column=4, sticky="ew", padx=(0, 6), pady=4
        )

        ttk.Label(
            can_frame,
            textvariable=self.dbc_auto_status_var,
            foreground="#374151",
        ).grid(row=1, column=0, columnspan=5, sticky="w", padx=6, pady=(0, 4))

        ttk.Label(can_frame, text="논리 CAN").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Label(can_frame, text="DBC").grid(row=2, column=1, sticky="w", padx=6, pady=4)

        for row, can_name in enumerate(self.can_names, start=3):
            ttk.Label(can_frame, text=can_name, width=12).grid(row=row, column=0, sticky="w", padx=6, pady=4)
            dbc_entry = ttk.Entry(can_frame, textvariable=self.can_dbc_vars[can_name], width=74)
            dbc_entry.grid(row=row, column=1, columnspan=3, sticky="w", padx=6, pady=4)
            self._bind_save_on_focusout(dbc_entry)
            ttk.Button(can_frame, text="...", width=3, command=lambda name=can_name: self._browse_dbc(name)).grid(
                row=row, column=4, sticky="w", padx=6, pady=4
            )

        right_top = ttk.Frame(frame)
        right_top.grid(row=0, column=1, sticky="nw", padx=(10, 6), pady=(4, 6))

        setting_frame = ttk.LabelFrame(right_top, text="감시 설정")
        setting_frame.pack(fill=tk.X, anchor="n", pady=(0, 6))
        setting_frame.columnconfigure(1, weight=0)

        ttk.Label(setting_frame, text="신호 확인 간격(sec)").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(setting_frame, textvariable=self.poll_interval_var, width=10).grid(row=0, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(setting_frame, text="Measurement 시작 후 대기시간(sec)").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(setting_frame, textvariable=self.measurement_wait_var, width=10).grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(setting_frame, text="Vector 연결 대상").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        vector_combo = ttk.Combobox(
            setting_frame,
            textvariable=self.vector_product_var,
            values=["자동", "CANoe", "CANalyzer"],
            state="readonly",
            width=12,
        )
        vector_combo.grid(row=2, column=1, sticky="w", padx=6, pady=4)
        vector_combo.bind("<<ComboboxSelected>>", lambda _event: self._save_current_user_settings(), add="+")

        collector_check = ttk.Checkbutton(
            setting_frame,
            text="CAPL Event Collector 사용 (권장)",
            variable=self.collector_enabled_var,
            command=self._on_collector_enabled_changed,
        )
        collector_check.grid(row=3, column=0, columnspan=2, sticky="w", padx=6, pady=(5, 2))
        if not COLLECTOR_AVAILABLE:
            collector_check.configure(state=tk.DISABLED)

        collector_button = ttk.Button(
            setting_frame, text="CAPL Collector 생성/갱신", command=lambda: self._generate_capl_collector(show_popup=True)
        )
        collector_button.grid(row=4, column=0, sticky="w", padx=6, pady=(2, 4))
        if not COLLECTOR_AVAILABLE:
            collector_button.configure(state=tk.DISABLED)
        ttk.Label(setting_frame, textvariable=self.collector_status_var, foreground="#374151", wraplength=360).grid(
            row=4, column=1, sticky="w", padx=6, pady=(2, 4)
        )

        debug_frame = ttk.LabelFrame(right_top, text="필요 파일 및 주의사항")
        debug_frame.pack(fill=tk.X, anchor="n")
        debug_frame.columnconfigure(0, weight=1)
        debug_frame.columnconfigure(1, weight=1)
        debug_frame.columnconfigure(2, weight=1)
        debug_frame.columnconfigure(3, weight=1)

        self.pywin32_status_label = tk.Label(
            debug_frame,
            textvariable=self.pywin32_status_var,
            anchor="center",
            relief="solid",
            bd=1,
            padx=6,
            pady=4,
            bg="#E5E7EB",
            fg="#111827",
            font=("맑은 고딕", 9, "bold"),
        )
        self.pywin32_status_label.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 3))

        self.pywin32_check_button = ttk.Button(
            debug_frame,
            text="필요 파일 확인",
            command=lambda: self._refresh_required_files_status(show_popup=True),
        )
        self.pywin32_check_button.grid(row=0, column=1, sticky="ew", padx=6, pady=(6, 3))

        self.pywin32_install_button = ttk.Button(
            debug_frame,
            text="필요 파일 설치",
            command=self._install_required_files,
        )
        self.pywin32_install_button.grid(row=0, column=2, sticky="ew", padx=6, pady=(6, 3))

        self.canoe_diag_button = ttk.Button(
            debug_frame,
            text="Vector 연결 진단",
            command=lambda: self._run_canoe_connection_diagnostic(
                trigger_error=None, show_popup=True, reason="사용자 수동 진단"
            ),
        )
        self.canoe_diag_button.grid(row=0, column=3, sticky="ew", padx=6, pady=(6, 3))

        caution_text = (
            "[주의사항]\n"
            "※ CANoe/CANalyzer를 자동 탐지합니다. 둘 다 실행 중이면 [Vector 연결 대상]을 직접 선택하세요\n"
            "※ GetActiveObject 실패 시, 해당 Vector 메인 프로세스가 이미 실행 중일 때만 guarded COM activation fallback을 시도합니다\n"
            "※ COM activation 전후 새 Vector 메인 PID가 생기면 자동 시험/Stimulus를 차단합니다\n"
            "※ CANalyzer는 관측/PASS-FAIL과 CAPL Bridge 기반 Stimulus를 지원합니다 (direct Signal.Value는 CANoe only)\n"
            "※ Measurement Start는 별도로 누를 필요가 없습니다 (자동 시작)\n"
            "※ CAPL Event Collector는 단일/다중 관측 보강 전용입니다. 미설치/불일치 시 기존 COM polling + 로그 재검토로 자동 fallback합니다\n"
            "※ Collector .can은 [CAPL Collector 생성/갱신] 후 CANoe/CANalyzer Configuration에 수동 삽입/Compile해야 합니다\n"
            "※ \"필요 파일: 설치됨\" 이 잘 되어있는지 확인하세요\n"
            "※ [Vector 연결 진단]은 read-only이며 Dispatch를 실행하지 않습니다"
        )
        tk.Label(
            debug_frame,
            text=caution_text,
            anchor="w",
            justify="left",
            bg="#F3F4F6",
            fg="#111827",
            padx=8,
            pady=7,
            bd=0,
            relief="flat",
            font=("맑은 고딕", 9),
        ).grid(row=1, column=0, columnspan=4, sticky="ew", padx=6, pady=(3, 6))

        log_frame = ttk.LabelFrame(frame, text="로그 재검토 설정")
        log_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=6, pady=(2, 4))
        for i in range(12):
            log_frame.columnconfigure(i, weight=0)

        ttk.Label(log_frame, text="자동 로그 폴더").grid(row=0, column=0, sticky="w", padx=(6, 4), pady=4)
        log_dir_entry = ttk.Entry(log_frame, textvariable=self.log_dir_var, width=68)
        log_dir_entry.grid(row=0, column=1, columnspan=3, sticky="w", padx=(2, 4), pady=4)
        self._bind_save_on_focusout(log_dir_entry)
        ttk.Button(log_frame, text="폴더 선택", command=self._browse_log_dir).grid(
            row=0, column=4, sticky="w", padx=(4, 4), pady=4
        )
        ttk.Checkbutton(
            log_frame,
            text="최신 로그 자동 탐색",
            variable=self.auto_find_latest_log_var,
        ).grid(row=0, column=5, sticky="w", padx=(4, 12), pady=4)

        ttk.Checkbutton(
            log_frame,
            text="다중 TC 수행 시 로그 검토",
            variable=self.multi_log_review_var,
            command=self._save_current_user_settings,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=(6, 8), pady=4)
        ttk.Checkbutton(
            log_frame,
            text="실시간 Fail 시 자동 로그 재검토",
            variable=self.auto_log_review_var,
            command=self._save_current_user_settings,
        ).grid(row=1, column=2, columnspan=2, sticky="w", padx=(0, 8), pady=4)
        ttk.Checkbutton(
            log_frame,
            text="TC Pass 시, 로그 검토과정 생략(추천)",
            variable=self.skip_log_review_on_pass_var,
            command=self._save_current_user_settings,
        ).grid(row=1, column=4, columnspan=3, sticky="w", padx=(0, 8), pady=4)
        ttk.Checkbutton(
            log_frame,
            text="로그 재검토 전 Measurement 자동 정지",
            variable=self.auto_stop_measurement_var,
            command=self._save_current_user_settings,
        ).grid(row=1, column=7, columnspan=4, sticky="w", padx=(0, 8), pady=4)

        ttk.Label(log_frame, text="Drop(sec)").grid(row=2, column=0, sticky="w", padx=(6, 3), pady=4)
        self.drop_entry = ttk.Entry(log_frame, textvariable=self.drop_first_seconds_var, width=8)
        self.drop_entry.grid(row=2, column=1, sticky="w", padx=(0, 14), pady=4)

        ttk.Label(log_frame, text="로그 대기(sec)").grid(row=2, column=2, sticky="w", padx=(0, 3), pady=4)
        self.log_wait_entry = ttk.Entry(log_frame, textvariable=self.log_wait_timeout_var, width=8)
        self.log_wait_entry.grid(row=2, column=3, sticky="w", padx=(0, 8), pady=4)

        self.manual_timing_check = ttk.Checkbutton(
            log_frame,
            text="수동 설정",
            variable=self.manual_timing_enabled_var,
            command=self._toggle_timing_manual_state,
        )
        self.manual_timing_check.grid(row=2, column=4, columnspan=2, sticky="w", padx=(4, 10), pady=4)

        self.manual_log_check = ttk.Checkbutton(
            log_frame,
            text="수동 로그 파일 직접 선택",
            variable=self.manual_log_enabled_var,
            command=self._toggle_manual_log_file_state,
        )
        self.manual_log_check.grid(row=3, column=0, sticky="w", padx=(6, 4), pady=3)
        self.manual_log_entry = ttk.Entry(log_frame, textvariable=self.log_file_var, width=68)
        self.manual_log_entry.grid(row=3, column=1, columnspan=3, sticky="w", padx=(2, 4), pady=3)
        self._bind_save_on_focusout(self.manual_log_entry)
        self.manual_log_button = ttk.Button(log_frame, text="로그 선택", command=self._browse_log_file)
        self.manual_log_button.grid(row=3, column=4, sticky="w", padx=(4, 4), pady=3)
        ttk.Label(log_frame, text="※ 기본은 자동 로그 폴더/최신 로그 탐색 사용").grid(
            row=3, column=5, columnspan=4, sticky="w", padx=(4, 6), pady=3
        )

        self._toggle_manual_log_file_state()
        self._toggle_timing_manual_state()
        return frame

    def _build_tc_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Step D/E. TC 목록 - 입력/출력 조건 보기 및 선택")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        style = ttk.Style(self)
        style.configure(
            "Oracle.Treeview",
            rowheight=24,
            borderwidth=1,
            relief="solid",
            background="white",
            fieldbackground="white",
        )
        style.configure(
            "Oracle.Treeview.Heading",
            relief="solid",
            borderwidth=1,
            background="#E5E7EB",
            foreground="#111827",
        )
        style.map("Oracle.Treeview", background=[("selected", "#DBEAFE")])

        columns = (
            "check",
            "status",
            "tc_no",
            "kind",
            "msg",
            "sig",
            "exp",
            "exp_desc",
            "error_reason",
            "view",
        )
        self.tc_tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            selectmode="none",
            style="Oracle.Treeview",
        )

        headings = {
            "check": "선택",
            "status": "상태",
            "tc_no": "TC 번호",
            "kind": "구분",
            "msg": "Message",
            "sig": "Signal",
            "exp": "예상 결과값",
            "exp_desc": "DBC 값 정보",
            "error_reason": "오류 사유",
            "view": "보기",
        }
        widths = {
            "check": 60,
            "status": 70,
            "tc_no": 90,
            "kind": 80,
            "msg": 200,
            "sig": 300,
            "exp": 120,
            "exp_desc": 120,
            "error_reason": 320,
            "view": 60,
        }
        anchors = {
            "check": "center",
            "status": "center",
            "kind": "center",
            "view": "center",
        }


        for c in columns:
            self.tc_tree.heading(c, text=headings[c], command=lambda col=c: self._sort_tc_tree_by_column(col))
            self.tc_tree.column(c, width=widths[c], anchor=anchors.get(c, "w"), stretch=False)

        self.tc_tree_headings = headings

        self.tc_tree.tag_configure("group_light", background="#FFFFFF", foreground="#111827")
        self.tc_tree.tag_configure("group_dark", background="#F8FAFC", foreground="#111827")
        self.tc_tree.tag_configure("error_row", background="#FEE2E2", foreground="#991B1B")
        self.tc_tree.tag_configure("pass_row", background="#DCFCE7", foreground="#166534")
        self.tc_tree.tag_configure("na_row", background="#FEF3C7", foreground="#92400E")
        self.tc_tree.tag_configure("selected_row", background="#DBEAFE", foreground="#111827")

        yscroll = ttk.Scrollbar(frame, orient="vertical", command=self.tc_tree.yview)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=self.tc_tree.xview)
        self.tc_tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.tc_tree.grid(row=0, column=0, sticky="nsew", pady=(2, 0))
        yscroll.grid(row=0, column=1, sticky="ns", pady=(2, 0))
        xscroll.grid(row=1, column=0, sticky="ew")

        self.tc_tree.bind("<Button-1>", self._on_tc_tree_click, add="+")

        return frame

    def _build_action_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Step F/G/H. 단일 TC 최종 판정")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(3, weight=1)

        timeout_row = ttk.Frame(frame)
        timeout_row.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=4)
        timeout_row.columnconfigure(0, weight=0)
        timeout_row.columnconfigure(1, weight=0)
        timeout_row.columnconfigure(2, weight=1)
        ttk.Label(timeout_row, text="1개 TC 당 대기 시간(sec)").grid(row=0, column=0, sticky="w")
        ttk.Entry(timeout_row, textvariable=self.default_timeout_var, width=10).grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.abort_button = tk.Button(
            timeout_row,
            text="중단",
            command=self._abort_monitoring,
            font=("맑은 고딕", 10, "bold"),
            bg="#EF4444",
            fg="white",
            activebackground="#DC2626",
            activeforeground="white",
            relief="raised",
            bd=2,
            height=1,
            cursor="hand2",
            state=tk.DISABLED,
        )
        self.abort_button.grid(row=0, column=2, sticky="e")

        control_grid = ttk.Frame(frame)
        control_grid.grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=(2, 4))
        control_grid.columnconfigure(0, weight=1, uniform="control")
        control_grid.columnconfigure(1, weight=1, uniform="control")

        self.canoe_status_label = tk.Label(
            control_grid,
            textvariable=self.canoe_status_var,
            anchor="center",
            relief="solid",
            bd=1,
            padx=8,
            pady=5,
            height=1,
            bg="#E5E7EB",
            fg="#111827",
            font=self.status_badge_font,
        )
        self.canoe_status_label.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=(0, 5))

        self.measurement_status_label = tk.Label(
            control_grid,
            textvariable=self.measurement_status_var,
            anchor="center",
            relief="solid",
            bd=1,
            padx=8,
            pady=5,
            height=1,
            bg="#E5E7EB",
            fg="#111827",
            font=self.status_badge_font,
        )
        self.measurement_status_label.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=(0, 5))

        self.start_button = tk.Button(
            control_grid,
            text="선택 TC Start",
            command=self._start_selected_tc,
            font=self.big_start_font,
            bg="#30D862",
            fg="black",
            activebackground="#28B854",
            activeforeground="black",
            relief="raised",
            bd=2,
            height=1,
            cursor="hand2",
        )
        self.start_button.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=(5, 0))

        self.complete_button = tk.Button(
            control_grid,
            text="수행 완료",
            command=self._complete_monitoring,
            font=self.big_start_font,
            bg="#BAE6FD",
            fg="black",
            activebackground="#7DD3FC",
            activeforeground="black",
            relief="raised",
            bd=2,
            height=1,
            cursor="hand2",
            state=tk.DISABLED,
        )
        self.complete_button.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=(5, 0))

        self.current_status_label = tk.Label(
            frame,
            text="대기중",
            anchor="center",
            relief="solid",
            bd=1,
            padx=10,
            pady=6,
            bg="#E5E7EB",
            fg="#111827",
            font=("맑은 고딕", 15, "bold"),
        )
        self.current_status_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=(2, 3))

        preview_frame = ttk.LabelFrame(frame, text="선택 TC 상세 / 보기")
        preview_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=6, pady=(2, 3))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.tc_preview_detail = ScrolledText(preview_frame, height=13, wrap=tk.WORD)
        self.tc_preview_detail.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.tc_preview_detail.insert(
            "1.0",
            "TC 목록에서 아무 위치나 클릭하면 해당 TC의 상세 설명이 여기에 표시됩니다.\n"
        )
        self.tc_preview_detail.configure(state="disabled")

        self._refresh_status_badges()
        return frame

    def _build_result_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="결과 목록")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        columns = ("tc_no", "final_status", "rt_status", "log_status", "observed", "message")
        self.result_tree = ttk.Treeview(frame, columns=columns, show="headings", height=10)

        labels = {
            "tc_no": "TC",
            "final_status": "최종",
            "rt_status": "실시간",
            "log_status": "로그",
            "observed": "Observed",
            "message": "최종 메시지",
        }
        widths = {
            "tc_no": 80,
            "final_status": 70,
            "rt_status": 70,
            "log_status": 70,
            "observed": 100,
            "message": 520,
        }

        for c in columns:
            self.result_tree.heading(c, text=labels[c])
            self.result_tree.column(c, width=widths[c], anchor="w", stretch=False)

        self.result_tree.tag_configure("result_pass", background="#DCFCE7", foreground="#166534")
        self.result_tree.tag_configure("result_fail", background="#FEE2E2", foreground="#991B1B")
        self.result_tree.tag_configure("result_na", background="#FEF3C7", foreground="#92400E")

        yscroll = ttk.Scrollbar(frame, orient="vertical", command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=yscroll.set)
        self.result_tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        result_button_row = ttk.Frame(frame)
        result_button_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=(4, 3))
        result_button_row.columnconfigure(0, weight=1)
        result_button_row.columnconfigure(1, weight=1)
        result_button_row.columnconfigure(2, weight=1)

        button_font = ("맑은 고딕", 10, "bold")
        self.report_button = tk.Button(
            result_button_row,
            text="결과 레포트 출력",
            command=self._export_report,
            font=button_font,
            bg="#DBEAFE",
            fg="#1E3A8A",
            activebackground="#BFDBFE",
            activeforeground="#1E3A8A",
            relief="raised",
            bd=1,
            height=2,
            cursor="hand2",
        )
        self.report_button.grid(row=0, column=0, sticky="ew", padx=(0, 5), ipady=2)

        tk.Button(
            result_button_row,
            text="결과 Excel 저장",
            command=self._save_results,
            font=button_font,
            bg="#E5E7EB",
            fg="#111827",
            activebackground="#D1D5DB",
            activeforeground="#111827",
            relief="raised",
            bd=1,
            height=2,
            cursor="hand2",
        ).grid(row=0, column=1, sticky="ew", padx=5, ipady=2)

        tk.Button(
            result_button_row,
            text="결과 초기화",
            command=self._clear_results,
            font=button_font,
            bg="#FEE2E2",
            fg="#991B1B",
            activebackground="#FECACA",
            activeforeground="#991B1B",
            relief="raised",
            bd=1,
            height=2,
            cursor="hand2",
        ).grid(row=0, column=2, sticky="ew", padx=(5, 0), ipady=2)

        return frame

    def _build_summary_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="TC 내부 진행 요약", padding=(2, 1, 2, 1), height=220)
        frame.grid_propagate(False)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        box1 = ttk.LabelFrame(frame, text="입력 - Vector 실시간 읽기", padding=(1, 1, 1, 1))
        box1.grid(row=0, column=0, sticky="nsew", padx=(2, 1), pady=(1, 1))
        box1.columnconfigure(0, weight=1)
        box1.rowconfigure(1, weight=1)

        box2 = ttk.LabelFrame(frame, text="출력 - Vector 실시간 읽기", padding=(1, 1, 1, 1))
        box2.grid(row=0, column=1, sticky="nsew", padx=(1, 2), pady=(1, 1))
        box2.columnconfigure(0, weight=1)
        box2.rowconfigure(1, weight=1)

        box3 = ttk.LabelFrame(frame, text="입력 - 로그 확인", padding=(1, 1, 1, 1))
        box3.grid(row=1, column=0, sticky="nsew", padx=(2, 1), pady=(1, 1))
        box3.columnconfigure(0, weight=1)
        box3.rowconfigure(1, weight=1)

        box4 = ttk.LabelFrame(frame, text="출력 - 로그 확인", padding=(1, 1, 1, 1))
        box4.grid(row=1, column=1, sticky="nsew", padx=(1, 2), pady=(1, 1))
        box4.columnconfigure(0, weight=1)
        box4.rowconfigure(1, weight=1)

        self._build_summary_section(box1, key="input_canoe")
        self._build_summary_section(box2, key="output_canoe")
        self._build_summary_section(box3, key="input_log")
        self._build_summary_section(box4, key="output_log")
        return frame

    def _build_summary_section(self, parent, key: str):
        header_wrap = ttk.Frame(parent)
        header_wrap.grid(row=0, column=0, sticky="ew", padx=1, pady=(0, 1))
        header_wrap.columnconfigure(0, weight=1)
        header_wrap.columnconfigure(1, minsize=17)

        header = ttk.Frame(header_wrap)
        header.grid(row=0, column=0, sticky="ew")

        for col, weight in enumerate((24, 24, 14, 14, 10, 14)):
            header.columnconfigure(col, weight=weight, uniform=f"{key}_cols")

        labels = ["Message", "Signal", "예상 결과값", "실제 결과값", "상태", "Fail 사유"]
        for i, txt in enumerate(labels):
            tk.Label(
                header,
                text=txt,
                font=self.summary_header_font,
                anchor="w" if i < 4 or i == 5 else "center",
                bg="#E5E7EB",
                pady=1
            ).grid(row=0, column=i, sticky="ew", padx=(0, 1) if i < 5 else 0)

        tk.Label(header_wrap, text="", bg="#E5E7EB").grid(row=0, column=1, sticky="nsew")

        body = ttk.Frame(parent)
        body.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 1))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        canvas = tk.Canvas(body, highlightthickness=0, bd=0, height=70)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.columnconfigure(0, weight=1)

        inner.bind(
            "<Configure>",
            lambda e, c=canvas: c.configure(scrollregion=c.bbox("all"))
        )

        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _sync_width(event, c=canvas, w=window_id):
            c.itemconfigure(w, width=event.width)

        canvas.bind("<Configure>", _sync_width)

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        if key == "input_canoe":
            self.summary_input_canoe_inner = inner
        elif key == "input_log":
            self.summary_input_log_inner = inner
        elif key == "output_canoe":
            self.summary_output_canoe_inner = inner
        elif key == "output_log":
            self.summary_output_log_inner = inner

    def _build_log_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="실행 로그")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.log_text = ScrolledText(frame, height=9, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        return frame

    def _refresh_status_badges(self):
        if self.canoe_status_label is not None:
            text = self.canoe_status_var.get()
            if ("연결됨" in text) or ("연결 버전" in text and not text.strip().endswith("-") and "실패" not in text):
                self.canoe_status_label.configure(bg="#DCFCE7", fg="#166534")
            elif "실패" in text or "없음" in text:
                self.canoe_status_label.configure(bg="#FEE2E2", fg="#991B1B")
            else:
                self.canoe_status_label.configure(bg="#E5E7EB", fg="#111827")

        if self.measurement_status_label is not None:
            text = self.measurement_status_var.get()
            if "실행 중" in text:
                self.measurement_status_label.configure(bg="#DCFCE7", fg="#166534")
            elif "정지" in text:
                self.measurement_status_label.configure(bg="#FEF3C7", fg="#92400E")
            elif "실패" in text or "오류" in text:
                self.measurement_status_label.configure(bg="#FEE2E2", fg="#991B1B")
            else:
                self.measurement_status_label.configure(bg="#E5E7EB", fg="#111827")

    def _browse_excel(self):
        path = filedialog.askopenfilename(
            title="TestCase_Oracle.xlsx 선택",
            filetypes=[("Excel files", "*.xlsx *.xlsm"), ("All files", "*.*")],
        )
        if not path:
            return

        self.excel_path_var.set(path)
        self._save_current_user_settings()
        try:
            sheets = core.list_excel_sheets(path)
            self.sheet_combo.configure(values=sheets)
            if sheets:
                preferred = next((s for s in sheets if s.upper() not in ("TEMPLATE", "README", "공통")), sheets[0])
                self.sheet_var.set(preferred)
            self._log(f"[OK] Excel 선택: {path}\n")
            self._save_current_user_settings()
            self._log(f"[OK] 시트 목록: {', '.join(sheets)}\n")
        except Exception as e:
            messagebox.showerror("Excel 오류", str(e))
            self._log(f"[ERROR] Excel 시트 읽기 실패: {e}\n")

    def _after_conditions_loaded(self):
        """MRO 확장 hook. multiple/txrx는 이 메서드만 override하여 비동기 로드 완료 후 갱신한다."""
        return None

    def _load_conditions(self):
        excel = self.excel_path_var.get().strip()
        sheet = self.sheet_var.get().strip()
        if not excel or not sheet:
            messagebox.showwarning("입력 필요", "Oracle Excel과 차종 시트를 선택하세요.")
            return
        if self._conditions_load_thread is not None and self._conditions_load_thread.is_alive():
            self._show_operation_progress("TC 목록 로드", "이미 Excel을 읽는 중입니다.", max(10, self._operation_popup_pct))
            return
        try:
            default_timeout = float(self.default_timeout_var.get().strip() or "30")
        except Exception as e:
            messagebox.showerror("설정 오류", str(e))
            return

        # rev87: 차량 송수신 탭의 DBC/입출력 분석을 최초 클릭 시점이 아니라
        # TC 목록 로드 단계에서 함께 선계산한다. Tk StringVar 접근은 main thread에서만 수행한다.
        txrx_preload_context = None
        if hasattr(self, "_prepare_txrx_preload_context"):
            try:
                txrx_preload_context = self._prepare_txrx_preload_context()
            except Exception as e:
                self._log(f"[WARN] TX/RX 사전분석 context 준비 실패: {e}\n")

        self.load_tc_button.configure(state=tk.DISABLED)
        self._show_operation_progress("TC 목록 로드", "1/7 Excel 조건 읽기 준비", 5)

        def worker():
            try:
                self.ui_async_queue.put(("TC_LOAD_PROGRESS", 15, "2/7 Excel/TC 조건 읽는 중"))
                rows = core.load_oracle_conditions_with_diagnostics(
                    excel, sheet, default_timeout_sec=default_timeout,
                )

                txrx_preload = None
                if hasattr(self, "_precompute_txrx_for_loaded_rows"):
                    try:
                        self.ui_async_queue.put(("TC_LOAD_PROGRESS", 58, "3/7 차량 송수신 테스트: DBC 사전 로드"))

                        def txrx_progress(done, total, message="차량 송수신 테스트 사전 분석"):
                            total = max(1, int(total or 1))
                            done = max(0, min(int(done or 0), total))
                            pct = 60.0 + (18.0 * done / total)
                            self.ui_async_queue.put((
                                "TC_LOAD_PROGRESS",
                                pct,
                                f"4/7 차량 송수신 테스트: {message} ({done}/{total})",
                            ))

                        txrx_preload = self._precompute_txrx_for_loaded_rows(
                            rows, txrx_preload_context, txrx_progress
                        )
                    except Exception as e:
                        txrx_preload = {"error": f"{type(e).__name__}: {e}"}
                        self.ui_async_queue.put((
                            "TC_LOAD_PROGRESS", 78,
                            f"4/7 차량 송수신 테스트 사전 분석 경고: {type(e).__name__}",
                        ))

                self.ui_async_queue.put(("TC_LOAD_DONE", rows, sheet, txrx_preload))
            except Exception as e:
                self.ui_async_queue.put(("TC_LOAD_ERROR", f"{type(e).__name__}: {e}"))

        self._conditions_load_thread = threading.Thread(target=worker, daemon=True)
        self._conditions_load_thread.start()
        self._poll_ui_async_queue()

    def _poll_ui_async_queue(self):
        try:
            while True:
                item = self.ui_async_queue.get_nowait()
                kind = item[0]
                if kind == "TC_LOAD_PROGRESS":
                    self._show_operation_progress("TC 목록 로드", str(item[2]), float(item[1]))
                elif kind == "TC_LOAD_DONE":
                    self._finish_conditions_load(item[1], item[2], item[3] if len(item) > 3 else None)
                elif kind == "TC_LOAD_ERROR":
                    self._finish_conditions_load_error(str(item[1]))
        except queue.Empty:
            pass
        if self._conditions_load_thread is not None and self._conditions_load_thread.is_alive():
            # core Excel parser는 내부 row progress를 노출하지 않으므로 15~55%는 '읽는 단계'의 시각적 진행치다.
            # rev87 TX/RX 사전분석이 58% 이후를 사용하므로 진행률이 다시 55%로 역행하지 않게 한다.
            if self._operation_popup_pct < 55.0:
                pct = min(55.0, max(15.0, self._operation_popup_pct + 1.5))
                self._show_operation_progress("TC 목록 로드", "2/7 Excel/TC 조건 읽는 중 (단계 기준)", pct)
            self.after(120, self._poll_ui_async_queue)

    def _finish_conditions_load(self, rows, sheet: str, txrx_preload=None):
        try:
            self._show_operation_progress("TC 목록 로드", "5/7 화면용 TC 목록 구성", 82)
            self.condition_rows = list(rows or [])
            self._invalidate_dbc_choice_cache()
            self.tc_result_status_by_index.clear()
            self._build_display_rows()
            self._show_operation_progress("TC 목록 로드", "5/7 TC 목록 표시", 86)
            self._refresh_tc_tree()
            self.selected_condition_index = None
            ready_count = sum(1 for r in self.condition_rows if r.is_valid)
            err_count = sum(1 for r in self.condition_rows if not r.is_valid)
            self._log(f"[OK] 조건 로드 완료: sheet={sheet}, total={len(self.condition_rows)}, ready={ready_count}, error={err_count}\n")
            self._refresh_all_summary(None, None)
            self._show_tc_detail_panel(None)
            self._after_conditions_loaded()

            # rev87: MRO hook들이 기존 state를 초기화한 뒤 TX/RX 선계산 결과를 적용해
            # 입력 송신 대상/자동 진단 요약이 탭 최초 클릭 전에 이미 준비되게 한다.
            self._show_operation_progress("TC 목록 로드", "6/7 차량 송수신 테스트: 사전 분석 결과 적용", 92)
            if txrx_preload is not None and hasattr(self, "_apply_txrx_preload_results"):
                try:
                    self._apply_txrx_preload_results(txrx_preload)
                except Exception as e:
                    self._log(f"[WARN] TX/RX 사전분석 결과 적용 실패: {e}\n")

            self._show_operation_progress("TC 목록 로드", "7/7 후속 캐시/Collector 준비", 96)
            if bool(self.collector_enabled_var.get()):
                try:
                    self._generate_capl_collector(show_popup=False)
                except Exception as e:
                    self._log(f"[WARN] CAPL Collector 생성 건너뜀: {e}\n")
            if self.notebook is not None and self.run_tab is not None:
                self._select_notebook_tab_stable(self.run_tab)
            if len(self.condition_rows) == 0:
                messagebox.showwarning("로드 결과", "표시할 TC 행이 없습니다. 엑셀 구조를 확인하세요.")
            self._show_operation_progress("TC 목록 로드", "완료", 100)
            self._close_operation_progress(180)
        finally:
            self._conditions_load_thread = None
            try:
                self.load_tc_button.configure(state=tk.NORMAL)
            except Exception:
                pass

    def _finish_conditions_load_error(self, message: str):
        self._conditions_load_thread = None
        try:
            self.load_tc_button.configure(state=tk.NORMAL)
        except Exception:
            pass
        self._close_operation_progress(0)
        self._log(f"[ERROR] TC 로드 실패: {message}\n")
        messagebox.showerror("TC 로드 오류", message)

    def _build_display_rows(self):
        self.display_rows.clear()
        self.tc_display_map.clear()

        valid_group_counter = 0

        for idx, row in enumerate(self.condition_rows):
            tc_key = str(idx)
            iids: List[str] = []

            if row.is_valid and row.condition is not None:
                cond = row.condition
                group_kind = valid_group_counter % 2
                valid_group_counter += 1

                seq = 0

                for in_idx, inp in enumerate(cond.input_conditions, start=1):
                    iid = f"{idx}:I:{in_idx}"
                    iids.append(iid)
                    self.display_rows.append({
                        "iid": iid,
                        "tc_key": tc_key,
                        "row_index": idx,
                        "is_first": (seq == 0),
                        "row_result": row,
                        "condition": cond,
                        "condition_type": "input",
                        "condition_seq": in_idx,
                        "expectation": inp,
                        "pass_overlay": False,
                        "selected_overlay": False,
                        "group_kind": group_kind,
                        "kind": f"입력{in_idx}",
                        "display_message": inp.message,
                        "display_signal": inp.signal,
                        "display_expected": inp.expected_value_raw,
                        "display_expected_desc": self._get_dbc_value_description(inp.message, inp.signal, inp.expected_value_raw),
                    })
                    seq += 1

                for out_idx, out in enumerate(cond.output_conditions, start=1):
                    iid = f"{idx}:O:{out_idx}"
                    iids.append(iid)
                    self.display_rows.append({
                        "iid": iid,
                        "tc_key": tc_key,
                        "row_index": idx,
                        "is_first": (seq == 0),
                        "row_result": row,
                        "condition": cond,
                        "condition_type": "output",
                        "condition_seq": out_idx,
                        "expectation": out,
                        "pass_overlay": False,
                        "selected_overlay": False,
                        "group_kind": group_kind,
                        "kind": f"출력{out_idx}",
                        "display_message": out.message,
                        "display_signal": out.signal,
                        "display_expected": out.expected_value_raw,
                        "display_expected_desc": self._get_dbc_value_description(out.message, out.signal, out.expected_value_raw),
                    })
                    seq += 1

            else:
                iid = f"{idx}:0"
                iids.append(iid)
                self.display_rows.append({
                    "iid": iid,
                    "tc_key": tc_key,
                    "row_index": idx,
                    "is_first": True,
                    "row_result": row,
                    "condition": None,
                    "condition_type": "error",
                    "condition_seq": 0,
                    "expectation": None,
                    "pass_overlay": False,
                    "selected_overlay": False,
                    "group_kind": valid_group_counter % 2,
                    "kind": "오류",
                    "display_message": row.input_message or "",
                    "display_signal": row.input_signal or "",
                    "display_expected": row.input_expected_value_raw or "",
                    "display_expected_desc": "-",
                })
                valid_group_counter += 1

            self.tc_display_map[tc_key] = iids

    @staticmethod
    def _natural_sort_key(value):
        text = "" if value is None else str(value)
        parts = re.split(r"(\d+)", text)
        return tuple(int(x) if x.isdigit() else x.lower() for x in parts)

    def _get_row_current_status(self, row_index: int) -> str:
        status = self.tc_result_status_by_index.get(row_index)
        if status:
            return status
        if 0 <= row_index < len(self.condition_rows):
            row = self.condition_rows[row_index]
            return row.status or ("Ready" if row.is_valid else "ERROR")
        return ""


    def _tc_sort_primary_value(self, row_index: int, column: str):
        row = self.condition_rows[row_index]
        if column == "check":
            return 0 if row_index == self.selected_condition_index else 1
        if column == "status":
            status = self._get_row_current_status(row_index)
            status_rank = {
                "ERROR": 0,
                "FAIL": 1,
                "N/A": 2,
                "Ready": 3,
                "PASS": 4,
            }
            return (status_rank.get(status, 10), self._natural_sort_key(status))
        if column == "tc_no":
            return self._natural_sort_key(row.tc_no)
        if column == "kind":
            return self._natural_sort_key("입력")
        if column == "msg":
            return self._natural_sort_key(row.input_message)
        if column == "sig":
            return self._natural_sort_key(row.input_signal)
        if column == "exp":
            return self._natural_sort_key(row.input_expected_value_raw)
        if column == "exp_desc":
            return self._natural_sort_key(self._get_display_row_dbc_desc_for_sort(row_index))
        if column == "error_reason":
            return self._natural_sort_key(row.error_reason)
        if column == "view":
            return self._natural_sort_key("보기" if row.is_valid else "")
        return self._natural_sort_key(row.tc_no)

    def _invalidate_dbc_choice_cache(self):
        self._dbc_choice_cache_key = None
        self._dbc_choice_db_by_ch = {}

    def _load_dbc_choice_db_by_ch(self):
        mapping = self._collect_dbc_mapping()
        key = tuple(sorted((int(ch), str(path)) for ch, path in mapping.items()))
        if key == self._dbc_choice_cache_key:
            return self._dbc_choice_db_by_ch
        self._dbc_choice_cache_key = key
        self._dbc_choice_db_by_ch = {}
        if not mapping:
            return self._dbc_choice_db_by_ch
        try:
            self._dbc_choice_db_by_ch = core.load_dbc_map(mapping)
        except Exception:
            self._dbc_choice_db_by_ch = {}
        return self._dbc_choice_db_by_ch

    def _get_dbc_value_description(self, message: str, signal: str, expected_value: str) -> str:
        try:
            db_by_ch = self._load_dbc_choice_db_by_ch()
            return core.lookup_dbc_choice_text(db_by_ch, message, signal, expected_value, max_len=24)
        except Exception:
            return "-"

    def _get_display_row_dbc_desc_for_sort(self, row_index: int) -> str:
        for d in self.display_rows:
            if d.get("row_index") == row_index and d.get("display_expected_desc"):
                return d.get("display_expected_desc", "-")
        return "-"

    def _apply_tc_sort(self):
        if not self.tc_sort_column:
            return
        if not self.display_rows:
            return

        grouped: Dict[int, List[Dict]] = {}
        original_order: List[int] = []
        for d in self.display_rows:
            idx = d["row_index"]
            if idx not in grouped:
                grouped[idx] = []
                original_order.append(idx)
            grouped[idx].append(d)

        def key_fn(idx: int):
            return (
                self._tc_sort_primary_value(idx, self.tc_sort_column),
                self._natural_sort_key(self.condition_rows[idx].tc_no),
                idx,
            )

        if self.tc_sort_reverse:
            primary_groups: Dict[str, List[int]] = {}
            ordered = sorted(original_order, key=key_fn)
            for idx in ordered:
                primary = repr(self._tc_sort_primary_value(idx, self.tc_sort_column))
                primary_groups.setdefault(primary, []).append(idx)
            primary_order = []
            seen = set()
            for idx in ordered:
                primary = repr(self._tc_sort_primary_value(idx, self.tc_sort_column))
                if primary not in seen:
                    seen.add(primary)
                    primary_order.append(primary)
            sorted_indices = []
            for primary in reversed(primary_order):
                sorted_indices.extend(primary_groups[primary])
        else:
            sorted_indices = sorted(original_order, key=key_fn)

        self.display_rows = [d for idx in sorted_indices for d in grouped[idx]]

    def _sort_tc_tree_by_column(self, column: str):
        if self.tc_sort_column == column:
            self.tc_sort_reverse = not self.tc_sort_reverse
        else:
            self.tc_sort_column = column
            self.tc_sort_reverse = False
        self._refresh_tc_tree()

    def _update_tc_tree_heading_arrows(self):
        if not hasattr(self, "tc_tree_headings") or self.tc_tree is None:
            return
        for col, label in self.tc_tree_headings.items():
            suffix = ""
            if self.tc_sort_column == col:
                suffix = " ▼" if self.tc_sort_reverse else " ▲"
            self.tc_tree.heading(col, text=label + suffix, command=lambda c=col: self._sort_tc_tree_by_column(c))

    def _find_condition_index(self, condition) -> Optional[int]:
        for idx, row in enumerate(self.condition_rows):
            if row.condition is condition:
                return idx
        return None

    def _clear_condition_result_overlay(self, condition):
        target_index = self._find_condition_index(condition)
        if target_index is None:
            return
        self.tc_result_status_by_index.pop(target_index, None)
        for d in self.display_rows:
            if d["row_index"] == target_index:
                d["pass_overlay"] = False
        self._refresh_tc_tree()

    def _set_condition_result_status(self, condition, status: str):
        target_index = self._find_condition_index(condition)
        if target_index is None:
            return
        final_status = (status or "").strip() or "대기중"
        self.tc_result_status_by_index[target_index] = final_status
        for d in self.display_rows:
            if d["row_index"] == target_index:
                d["pass_overlay"] = (final_status == "PASS")
        self._refresh_tc_tree()

    def _refresh_tc_tree(self):
        self._apply_tc_sort()
        self._update_tc_tree_heading_arrows()
        self.tc_tree.delete(*self.tc_tree.get_children())

        for d in self.display_rows:
            row = d["row_result"]
            iid = d["iid"]
            row_result_status = self.tc_result_status_by_index.get(d["row_index"], "")

            if d["selected_overlay"]:
                # 선택 TC는 결과 색상보다 선택 음영을 우선 적용한다.
                # PASS/FAIL/N/A 상태값은 상태 열에 유지되므로, 사용자는 현재 클릭한 TC를 더 빠르게 인식할 수 있다.
                tags = ("selected_row",)
            elif row_result_status == "PASS" or d["pass_overlay"]:
                tags = ("pass_row",)
            elif row_result_status in ("FAIL", "ERROR"):
                tags = ("error_row",)
            elif row_result_status == "N/A":
                tags = ("na_row",)
            elif not row.is_valid:
                tags = ("error_row",)
            else:
                tags = ("group_light",) if d.get("group_kind", 0) % 2 == 0 else ("group_dark",)

            if d["is_first"]:
                check_mark = "☑" if d["selected_overlay"] else "☐"
                status_text = self._get_row_current_status(d["row_index"])
                tc_no = row.tc_no
                error_reason = row.error_reason
                view_text = "보기"
            else:
                check_mark = ""
                status_text = ""
                tc_no = ""
                error_reason = ""
                view_text = ""

            self.tc_tree.insert(
                "",
                tk.END,
                iid=iid,
                tags=tags,
                values=(
                    check_mark,
                    status_text,
                    tc_no,
                    d.get("kind", ""),
                    d.get("display_message", ""),
                    d.get("display_signal", ""),
                    d.get("display_expected", ""),
                    d.get("display_expected_desc", "-"),
                    error_reason,
                    view_text,
                ),
            )

        ready_count = sum(1 for r in self.condition_rows if r.is_valid)
        err_count = sum(1 for r in self.condition_rows if not r.is_valid)
        selected_text = "-"
        if self.selected_condition_index is not None and 0 <= self.selected_condition_index < len(self.condition_rows):
            rr = self.condition_rows[self.selected_condition_index]
            selected_text = rr.tc_no if rr.is_valid else f"ERROR ROW {rr.row_index}"
        self.selected_tc_status_var.set(
            f"선택 TC: {selected_text} / 전체 {len(self.condition_rows)}개 (정상 {ready_count}, 오류 {err_count})"
        )

    def _get_selected_condition_row(self):
        if self.selected_condition_index is None:
            return None
        if 0 <= self.selected_condition_index < len(self.condition_rows):
            return self.condition_rows[self.selected_condition_index]
        return None

    def _on_tc_tree_click(self, event):
        region = self.tc_tree.identify_region(event.x, event.y)
        row_id = self.tc_tree.identify_row(event.y)

        if region == "cell" and row_id:
            self._select_tc_by_row_id(row_id)
            return "break"

        return None

    def _select_tc_by_row_id(self, row_id: str):
        d = next((x for x in self.display_rows if x["iid"] == row_id), None)
        if d is None:
            return

        idx = d["row_index"]
        row = self.condition_rows[idx]

        if not row.is_valid:
            messagebox.showwarning("선택 불가", f"이 행은 로드 오류가 있어 선택할 수 없습니다.\n사유: {row.error_reason}")
            self._show_tc_detail_panel(row)
            return

        if self.selected_condition_index == idx:
            self.selected_condition_index = None
            for disp in self.display_rows:
                disp["selected_overlay"] = False

            self._refresh_tc_tree()
            self.selected_tc_status_var.set(f"선택 TC: - / 전체 {len(self.condition_rows)}개")
            self._refresh_all_summary(None, None)
            self._show_tc_detail_panel(None)
            return

        self.selected_condition_index = idx

        for disp in self.display_rows:
            disp["selected_overlay"] = (disp["row_index"] == self.selected_condition_index)

        self._refresh_tc_tree()

        selected_row = self._get_selected_condition_row()
        if selected_row is not None and selected_row.condition is not None:
            self.selected_tc_status_var.set(f"선택 TC: {selected_row.condition.tc_no}")
            self._refresh_all_summary(selected_row.condition, None)
            self._show_tc_detail_panel(selected_row)
        else:
            self.selected_tc_status_var.set(f"선택 TC: - / 전체 {len(self.condition_rows)}개")
            self._refresh_all_summary(None, None)
            self._show_tc_detail_panel(None)

    def _show_tc_detail_panel(self, row):
        if self.tc_preview_detail is None:
            return

        self.tc_preview_detail.configure(state="normal")
        self.tc_preview_detail.delete("1.0", tk.END)

        if row is None:
            self.tc_preview_detail.insert(
                "1.0",
                "TC 목록에서 아무 위치나 클릭하면 해당 TC의 상세 설명이 여기에 표시됩니다.\n"
            )
            self.tc_preview_detail.configure(state="disabled")
            return

        if not row.is_valid or row.condition is None:
            text = [
                f"TC 번호: {row.tc_no or '-'}",
                f"소분류: {row.subcategory or '-'}",
                "",
                "[로드 오류]",
                row.error_reason or "-",
                "",
                "[TC 내용]",
                row.tc_content or "-",
                "",
                "[TC 예상 결과]",
                row.tc_expected_result or "-",
            ]
        else:
            c = row.condition
            text = [
                f"TC 번호: {c.tc_no}",
                f"소분류: {c.subcategory}",
                f"판정 방식: {c.judge_mode} / 대기 시간: {c.timeout_sec}s",
                "",
                "[TC 내용]",
                c.tc_content or "-",
                "",
                "[TC 예상 결과]",
                c.tc_expected_result or "-",
                "",
                "[입력 조건]",
            ]
            if c.input_conditions:
                for i, inp in enumerate(c.input_conditions, start=1):
                    text.append(f"{i}. {inp.message} / {inp.signal} / {inp.expected_value_raw}")
            else:
                text.append("-")
            text.append("")
            text.append("[출력 조건]")
            if c.output_conditions:
                for i, o in enumerate(c.output_conditions, start=1):
                    text.append(f"{i}. {o.message} / {o.signal} / {o.expected_value_raw}")
            else:
                text.append("-")

        self.tc_preview_detail.insert("1.0", "\n".join(text))
        self.tc_preview_detail.configure(state="disabled")

    def _clear_summary_frame(self, inner: ttk.Frame):
        for child in inner.winfo_children():
            child.destroy()

    def _build_summary_rows(self, inner: ttk.Frame, items: List[Tuple[str, str, str, str, str, str]], key: str):
        self._clear_summary_frame(inner)

        if not items:
            ttk.Label(inner, text="표시할 내용이 없습니다.", foreground="#6B7280").grid(
                row=0, column=0, sticky="w", padx=2, pady=1
            )
            return

        for i, (msg, sig, exp, actual, status, reason) in enumerate(items):
            row_frame = ttk.Frame(inner)
            row_frame.grid(row=i, column=0, sticky="ew", padx=1, pady=0)

            row_frame.columnconfigure(0, weight=24, uniform=f"{key}_cols")
            row_frame.columnconfigure(1, weight=24, uniform=f"{key}_cols")
            row_frame.columnconfigure(2, weight=14, uniform=f"{key}_cols")
            row_frame.columnconfigure(3, weight=14, uniform=f"{key}_cols")
            row_frame.columnconfigure(4, weight=10, uniform=f"{key}_cols")
            row_frame.columnconfigure(5, weight=14, uniform=f"{key}_cols")

            bg = "#FFFFFF" if i % 2 == 0 else "#F9FAFB"

            tk.Label(row_frame, text=msg, anchor="w", bg=bg, font=self.summary_text_font, pady=0).grid(
                row=0, column=0, sticky="ew", padx=(0, 1), pady=0
            )
            tk.Label(row_frame, text=sig, anchor="w", bg=bg, font=self.summary_text_font, pady=0).grid(
                row=0, column=1, sticky="ew", padx=(0, 1), pady=0
            )
            tk.Label(row_frame, text=exp, anchor="w", bg=bg, font=self.summary_text_font, pady=0).grid(
                row=0, column=2, sticky="ew", padx=(0, 1), pady=0
            )
            tk.Label(row_frame, text=actual, anchor="w", bg=bg, font=self.summary_text_font, pady=0).grid(
                row=0, column=3, sticky="ew", padx=(0, 1), pady=0
            )

            status_bg = "#DCFCE7" if status == "PASS" else "#FEE2E2" if status in ("FAIL", "ERROR") else "#FEF3C7" if status == "N/A" else bg
            status_fg = "#166534" if status == "PASS" else "#991B1B" if status in ("FAIL", "ERROR") else "#92400E" if status == "N/A" else "#111827"

            tk.Label(row_frame, text=status, anchor="center", bg=status_bg, fg=status_fg, font=self.summary_text_font, pady=0).grid(
                row=0, column=4, sticky="ew", padx=(0, 1), pady=0
            )
            tk.Label(row_frame, text=reason, anchor="w", bg=bg, font=self.summary_text_font, pady=0).grid(
                row=0, column=5, sticky="ew", pady=0
            )

    def _refresh_all_summary(self, condition: Optional[core.OracleCondition], result: Optional[core.FinalCheckResult]):
        input_canoe_rows: List[Tuple[str, str, str, str, str, str]] = []
        input_log_rows: List[Tuple[str, str, str, str, str, str]] = []
        output_canoe_rows: List[Tuple[str, str, str, str, str, str]] = []
        output_log_rows: List[Tuple[str, str, str, str, str, str]] = []

        if condition is not None:
            if result is None:
                for inp in condition.input_conditions:
                    input_canoe_rows.append((inp.message, inp.signal, inp.expected_value_raw, "-", "", ""))
                    input_log_rows.append((inp.message, inp.signal, inp.expected_value_raw, "-", "", ""))

                for out_exp in condition.output_conditions:
                    output_canoe_rows.append((out_exp.message, out_exp.signal, out_exp.expected_value_raw, "-", "", ""))
                    output_log_rows.append((out_exp.message, out_exp.signal, out_exp.expected_value_raw, "-", "", ""))
            else:
                rt = result.realtime_result
                lg = result.log_result

                rt_inputs = rt.input_results if (rt is not None and getattr(rt, "input_results", None) is not None) else []
                lg_inputs = lg.input_results if (lg is not None and getattr(lg, "input_results", None) is not None) else []

                for i, inp in enumerate(condition.input_conditions):
                    rt_one = rt_inputs[i] if i < len(rt_inputs) else None
                    lg_one = lg_inputs[i] if i < len(lg_inputs) else None

                    input_canoe_rows.append((
                        inp.message,
                        inp.signal,
                        inp.expected_value_raw,
                        self._format_actual_value(rt_one.observed_value_raw if rt_one else None),
                        rt_one.status if rt_one else "",
                        self._short_reason(rt_one.status if rt_one else "", rt_one.message if rt_one else ""),
                    ))
                    input_log_rows.append((
                        inp.message,
                        inp.signal,
                        inp.expected_value_raw,
                        self._format_log_actual_value(lg_one),
                        lg_one.status if lg_one else "",
                        self._short_reason(lg_one.status if lg_one else "", lg_one.message if lg_one else ""),
                    ))

                rt_outputs = rt.output_results if (rt is not None and getattr(rt, "output_results", None) is not None) else []
                lg_outputs = lg.output_results if (lg is not None and getattr(lg, "output_results", None) is not None) else []

                for i, out_exp in enumerate(condition.output_conditions):
                    rt_one = rt_outputs[i] if i < len(rt_outputs) else None
                    lg_one = lg_outputs[i] if i < len(lg_outputs) else None

                    output_canoe_rows.append((
                        out_exp.message,
                        out_exp.signal,
                        out_exp.expected_value_raw,
                        self._format_actual_value(rt_one.observed_value_raw if rt_one else None),
                        rt_one.status if rt_one else "",
                        self._short_reason(rt_one.status if rt_one else "", rt_one.message if rt_one else ""),
                    ))
                    output_log_rows.append((
                        out_exp.message,
                        out_exp.signal,
                        out_exp.expected_value_raw,
                        self._format_log_actual_value(lg_one),
                        lg_one.status if lg_one else "",
                        self._short_reason(lg_one.status if lg_one else "", lg_one.message if lg_one else ""),
                    ))

        if self.summary_input_canoe_inner is not None:
            self._build_summary_rows(self.summary_input_canoe_inner, input_canoe_rows, "input_canoe")
        if self.summary_input_log_inner is not None:
            self._build_summary_rows(self.summary_input_log_inner, input_log_rows, "input_log")
        if self.summary_output_canoe_inner is not None:
            self._build_summary_rows(self.summary_output_canoe_inner, output_canoe_rows, "output_canoe")
        if self.summary_output_log_inner is not None:
            self._build_summary_rows(self.summary_output_log_inner, output_log_rows, "output_log")

    def _refresh_summary_with_partial_result(self, result):
        self._refresh_all_summary(result.condition, self._wrap_partial_as_final(result))

    def _wrap_partial_as_final(self, rt_result):
        fake = core.FinalCheckResult(condition=rt_result.condition)
        fake.realtime_result = rt_result
        fake.log_result = None
        return fake

    def _browse_log_file(self):
        path = filedialog.askopenfilename(
            title="BLF 또는 ASC 로그 선택",
            filetypes=[("CAN log", "*.blf *.asc"), ("All files", "*.*")],
        )
        if path:
            self.log_file_var.set(path)
            self._save_current_user_settings()
            self._log(f"[OK] 수동 로그 파일 선택: {path}\n")

    def _browse_log_dir(self):
        path = filedialog.askdirectory(title="CANoe 로그 폴더 선택")
        if path:
            self.log_dir_var.set(path)
            self._save_current_user_settings()
            self._log(f"[OK] 자동 로그 폴더 선택: {path}\n")

    def _toggle_manual_log_file_state(self):
        state = "normal" if self.manual_log_enabled_var.get() else "disabled"
        if hasattr(self, "manual_log_entry"):
            self.manual_log_entry.configure(state=state)
        if hasattr(self, "manual_log_button"):
            self.manual_log_button.configure(state=state)
        self._save_current_user_settings()

    def _toggle_timing_manual_state(self):
        enabled = self.manual_timing_enabled_var.get()
        state = "normal" if enabled else "disabled"

        if not enabled:
            self.drop_first_seconds_var.set(self.default_drop_seconds)
            self.log_wait_timeout_var.set(self.default_log_wait_seconds)

        if self.drop_entry is not None:
            self.drop_entry.configure(state=state)
        if self.log_wait_entry is not None:
            self.log_wait_entry.configure(state=state)
        self._save_current_user_settings()

    @staticmethod
    def _ch_text_to_int(ch_text: str):
        """Legacy parser for old pasted CH1 text only; GUI no longer exposes physical-channel selection."""
        s = (ch_text or "").strip().lower()
        if s in ("", "n/a", "na", "none"):
            return None
        if s.startswith("ch"):
            s = s[2:]
        try:
            return int(s)
        except Exception:
            return None

    def _logical_can_to_channel(self, can_name: str) -> int:
        name = str(can_name or "").strip().upper()
        if name not in self.can_logical_channel_by_name:
            raise ValueError(f"지원하지 않는 논리 CAN입니다: {can_name}")
        return int(self.can_logical_channel_by_name[name])

    def _channel_to_logical_can(self, channel: int) -> str:
        try:
            ch = int(channel)
        except Exception as e:
            raise ValueError(f"잘못된 CANoe 논리 채널 번호: {channel}") from e
        name = f"CAN{ch}"
        return name if name in self.can_logical_channel_by_name else name

    def _browse_dbc(self, can_name: str):
        path = filedialog.askopenfilename(
            title=f"{can_name} DBC 선택",
            filetypes=[("DBC files", "*.dbc"), ("All files", "*.*")],
        )
        if path:
            self.can_dbc_vars[can_name].set(path)
            self._invalidate_dbc_choice_cache()
            if getattr(self, "condition_rows", None):
                self._build_display_rows()
                self._refresh_tc_tree()
            self._save_current_user_settings()
            self._log(f"[OK] {can_name} DBC 선택: {path}\n")
            if bool(self.collector_enabled_var.get()) and getattr(self, "condition_rows", None):
                self._generate_capl_collector(show_popup=False)

    # -------------------------------------------------
    # rev87: CAN 네트워크명 기반 DBC 자동 매핑
    # -------------------------------------------------
    def _browse_dbc_auto_dir(self):
        path = filedialog.askdirectory(title="DBC 자동 설정 폴더 선택")
        if path:
            self.dbc_auto_dir_var.set(path)
            self.dbc_auto_status_var.set("자동 매핑: 폴더 선택 완료 / 실행 전")
            self._save_current_user_settings()
            self._log(f"[OK] DBC 자동 설정 폴더 선택: {path}\n")

    def _collect_network_detection_source_paths(self) -> List[str]:
        """네트워크명 식별 근거가 될 ASC/로그 파일만 수집한다.

        BLF는 변환 과정에서 원래 헤더/네트워크명이 보존되지 않을 수 있으므로 네트워크명
        자동 식별 근거로 직접 사용하지 않는다. 수동 ASC와 로그 폴더의 최신 ASC를 우선한다.
        """
        paths: List[Path] = []
        manual = self.log_file_var.get().strip()
        if manual:
            p = Path(manual)
            if p.is_file() and p.suffix.lower() == ".asc":
                paths.append(p)

        log_dir = self.log_dir_var.get().strip()
        if log_dir:
            folder = Path(log_dir)
            if folder.is_dir():
                try:
                    asc_files = [x for x in folder.glob("*.asc") if x.is_file()]
                    asc_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    paths.extend(asc_files[:3])
                except Exception:
                    pass

        out: List[str] = []
        for p in paths:
            sp = str(p)
            if sp not in out:
                out.append(sp)
        return out

    def _auto_map_dbc_from_network_names(self):
        dbc_dir = self.dbc_auto_dir_var.get().strip()
        if not dbc_dir or not Path(dbc_dir).is_dir():
            messagebox.showwarning("DBC 자동 설정 폴더 필요", "먼저 DBC 자동 설정 폴더를 선택하세요.")
            return

        source_paths = self._collect_network_detection_source_paths()
        try:
            result = core.auto_map_dbc_by_network_sources(
                dbc_dir=dbc_dir,
                source_paths=source_paths,
                source_texts=None,
                include_active_canoe_config=True,
            )
        except Exception as e:
            self.dbc_auto_status_var.set("자동 매핑: 오류")
            self._log(f"[ERROR] CAN 네트워크/DBC 자동 매핑 실패: {type(e).__name__}: {e}\n")
            messagebox.showerror("DBC 자동 매핑 실패", f"{type(e).__name__}: {e}")
            return

        networks = result.get("network_by_can") or {}
        conflicts = result.get("conflicts") or {}
        selected = result.get("selected_dbc_by_can") or {}
        candidates = result.get("dbc_candidates_by_can") or {}
        unresolved = result.get("unresolved") or {}

        applied = 0
        lines = []
        for can_name in self.can_names:
            if can_name in conflicts:
                self.can_network_vars[can_name].set("충돌")
                lines.append(f"{can_name}: 네트워크 근거 충돌 ({', '.join(conflicts[can_name])}) - 기존 DBC 유지")
                continue

            network = str(networks.get(can_name) or "").strip()
            self.can_network_vars[can_name].set(network or "-")
            dbc = str(selected.get(can_name) or "").strip()
            if dbc:
                self.can_dbc_vars[can_name].set(dbc)
                applied += 1
                lines.append(f"{can_name}: {network} -> {Path(dbc).name} [자동 적용]")
            else:
                cand_count = len(candidates.get(can_name) or [])
                reason = unresolved.get(can_name) or "자동 매핑 불가"
                if cand_count > 1:
                    reason += f" / 후보={cand_count}개"
                lines.append(f"{can_name}: {network or '-'} -> {reason} [기존 DBC 유지]")

        self._invalidate_dbc_choice_cache()
        if getattr(self, "condition_rows", None):
            self._build_display_rows()
            self._refresh_tc_tree()
        self._save_current_user_settings()

        self.dbc_auto_status_var.set(f"자동 매핑: {applied}/{len(self.can_names)}개 적용")
        self._log("[DBC-AUTO] 네트워크/DBC 자동 매핑 결과\n")
        for line in lines:
            self._log(f"[DBC-AUTO] {line}\n")
        active = result.get("active_canoe_config") or {}
        if active.get("configuration"):
            self._log(f"[DBC-AUTO] CANoe Configuration 근거 탐색: {active.get('configuration')}\n")
        for sp in source_paths:
            self._log(f"[DBC-AUTO] ASC 근거 탐색: {sp}\n")
        if bool(self.collector_enabled_var.get()) and getattr(self, "condition_rows", None):
            self._generate_capl_collector(show_popup=False)

        popup = "\n".join(lines)
        popup += (
            "\n\n※ 네트워크명 근거가 없거나 서로 충돌하거나 DBC 후보가 0개/2개 이상이면 "
            "자동으로 덮어쓰지 않고 기존 수동 DBC 설정을 유지합니다."
        )
        messagebox.showinfo("네트워크/DBC 자동 매핑", popup)

    REQUIRED_FILE_PACKAGES = [
        {"pip": "openpyxl", "imports": ("openpyxl",), "label": "openpyxl", "purpose": "Oracle Excel 읽기/결과 Excel 저장"},
        {"pip": "pywin32", "imports": ("pythoncom", "win32com.client"), "label": "pywin32", "purpose": "Vector CANoe/CANalyzer COM 연결"},
        {"pip": "cantools", "imports": ("cantools",), "label": "cantools", "purpose": "DBC 로드 및 ASC 로그 디코딩"},
        {"pip": "python-can", "imports": ("can",), "label": "python-can", "purpose": "BLF → ASC 변환"},
    ]

    @staticmethod
    def _import_module_safely(module_name: str) -> Tuple[bool, str]:
        try:
            import importlib
            importlib.import_module(module_name)
            return True, ""
        except Exception as e:
            return False, str(e)

    def _check_required_files_available(self) -> Tuple[bool, List[Dict[str, str]]]:
        details: List[Dict[str, str]] = []
        all_ok = True
        for item in self.REQUIRED_FILE_PACKAGES:
            import_errors = []
            for module_name in item["imports"]:
                ok, err = self._import_module_safely(module_name)
                if not ok:
                    import_errors.append(f"{module_name}: {err}")
            installed = not import_errors
            if not installed:
                all_ok = False
            details.append({
                "label": item["label"],
                "pip": item["pip"],
                "purpose": item["purpose"],
                "status": "설치됨" if installed else "설치 안됨",
                "detail": "" if installed else " / ".join(import_errors),
            })
        return all_ok, details

    def _required_files_popup_text(self, details: List[Dict[str, str]], include_restart_guide: bool = False) -> str:
        lines = ["필요 파일 확인 결과", ""]
        for d in details:
            mark = "OK" if d["status"] == "설치됨" else "NG"
            lines.append(f"[{mark}] {d['label']} - {d['status']}")
            lines.append(f"    용도: {d['purpose']}")
            if d["detail"]:
                lines.append(f"    상세: {d['detail']}")
            lines.append("")
        text = "\n".join(lines).rstrip()
        if include_restart_guide:
            text += REQUIRED_FILES_RESTART_GUIDE
        return text

    def _refresh_required_files_status(self, show_popup: bool = False) -> bool:
        ok, details = self._check_required_files_available()
        if ok:
            self.pywin32_status_var.set("필요 파일: 설치됨")
            if self.pywin32_status_label is not None:
                self.pywin32_status_label.configure(bg="#DCFCE7", fg="#166534")
            if self.pywin32_install_button is not None:
                self.pywin32_install_button.configure(state=tk.DISABLED)
            if show_popup:
                messagebox.showinfo(
                    "필요 파일 확인",
                    self._required_files_popup_text(details, include_restart_guide=True)
                )
            return True

        self.pywin32_status_var.set("필요 파일: 설치 안됨")
        if self.pywin32_status_label is not None:
            self.pywin32_status_label.configure(bg="#FEF3C7", fg="#92400E")
        if self.pywin32_install_button is not None:
            self.pywin32_install_button.configure(state=tk.NORMAL)
        if show_popup:
            messagebox.showwarning(
                "필요 파일 확인",
                self._required_files_popup_text(details, include_restart_guide=True)
            )
        return False

    def _install_required_files(self):
        package_lines = [f"- {item['label']} : {item['purpose']}" for item in self.REQUIRED_FILE_PACKAGES]
        if not messagebox.askyesno(
            "필요 파일 설치",
            "현재 GUI를 실행 중인 Python 환경에 아래 필요 파일을 설치할까요?\n\n"
            + "\n".join(package_lines)
            + "\n\n[예]를 누르면 설치에 동의한 것으로 간주하고 순서대로 진행합니다.\n"
            + "회사 PC 보안 정책 또는 인터넷 연결 상태에 따라 실패할 수 있습니다."
        ):
            return
        if self.pywin32_install_button is not None:
            self.pywin32_install_button.configure(state=tk.DISABLED)
        if self.pywin32_check_button is not None:
            self.pywin32_check_button.configure(state=tk.DISABLED)
        self.pywin32_status_var.set("필요 파일: 설치 중...")
        if self.pywin32_status_label is not None:
            self.pywin32_status_label.configure(bg="#DBEAFE", fg="#1D4ED8")
        self._log("[GUI] 필요 파일 설치 시작\n")

        def worker():
            try:
                summary = []
                for item in self.REQUIRED_FILE_PACKAGES:
                    cmd = [sys.executable, "-m", "pip", "install", item["pip"]]
                    self.log_queue.put(("REQUIRED_FILES_INSTALL_PROGRESS", item["label"], "START", "", ""))
                    proc = subprocess.run(
                        cmd,
                        input="y\n",
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=600,
                        **_hidden_subprocess_kwargs(),
                    )
                    summary.append({
                        "label": item["label"],
                        "cmd": " ".join(cmd),
                        "return_code": proc.returncode,
                        "stdout": proc.stdout,
                        "stderr": proc.stderr
                    })
                    self.log_queue.put(("REQUIRED_FILES_INSTALL_PROGRESS", item["label"], proc.returncode, proc.stdout, proc.stderr))
                self.log_queue.put(("REQUIRED_FILES_INSTALL_DONE", summary))
            except Exception as e:
                self.log_queue.put(("REQUIRED_FILES_INSTALL_ERROR", str(e)))
        threading.Thread(target=worker, daemon=True).start()

    def _on_required_files_install_progress(self, label: str, return_code, stdout: str, stderr: str):
        if return_code == "START":
            self._log(f"[GUI] 설치 시작: {label}\n")
            return
        self._log(f"[GUI] 설치 종료: {label} / return_code={return_code}\n")
        if stdout:
            self._log(f"[pip stdout - {label}]\n{stdout}\n")
        if stderr:
            self._log(f"[pip stderr - {label}]\n{stderr}\n")

    def _on_required_files_install_done(self, summary: List[Dict[str, str]]):
        if self.pywin32_check_button is not None:
            self.pywin32_check_button.configure(state=tk.NORMAL)

        failed = [x for x in summary if x.get("return_code") != 0]
        ok = self._refresh_required_files_status(show_popup=False)

        if ok and not failed:
            messagebox.showinfo(
                "필요 파일 설치 완료",
                "필요 파일 설치 및 import 확인이 완료되었습니다.\n"
                "Vector CANoe/CANalyzer 연결이 계속 실패하면 프로그램을 재시작한 뒤 다시 시도하세요."
                + REQUIRED_FILES_RESTART_GUIDE
            )
            return

        if failed:
            failed_names = ", ".join(x.get("label", "-") for x in failed)
            messagebox.showerror(
                "필요 파일 설치 실패",
                f"일부 파일 설치에 실패했습니다: {failed_names}\n\n"
                "실행 로그의 pip stderr 내용을 확인하세요.\n"
                "회사 보안망/인터넷 차단/권한 문제일 수 있습니다."
                + REQUIRED_FILES_RESTART_GUIDE
            )
        else:
            messagebox.showwarning(
                "설치 후 확인 필요",
                "pip 설치 명령은 완료되었지만 현재 프로세스에서 일부 파일 import 확인이 실패했습니다.\n"
                "프로그램을 재시작한 뒤 [필요 파일 확인]을 다시 눌러주세요."
                + REQUIRED_FILES_RESTART_GUIDE
            )

    def _on_required_files_install_error(self, error_message: str):
        if self.pywin32_check_button is not None:
            self.pywin32_check_button.configure(state=tk.NORMAL)
        self._refresh_required_files_status(show_popup=False)
        self._log(f"[ERROR] 필요 파일 설치 실행 오류: {error_message}\n")
        messagebox.showerror(
            "필요 파일 설치 오류",
            error_message + REQUIRED_FILES_RESTART_GUIDE
        )

    def _reset_run_session_state(self):
        self._countdown_running = False
        self.stop_event.clear()
        self.done_event.clear()

    def _sleep_with_ui_updates(self, duration_sec: float, step_sec: float = 0.05) -> bool:
        """GUI 화면 갱신을 유지하면서 짧게 대기한다.

        기존 time.sleep()만 사용하면 카운트다운 마지막 구간에서 Tk 이벤트가 밀려
        화면이 순간적으로 멈춘 것처럼 보일 수 있어, 작은 단위로 나눠 이벤트를 처리한다.
        """
        try:
            duration_sec = max(0.0, float(duration_sec))
        except Exception:
            duration_sec = 0.0

        deadline = time.perf_counter() + duration_sec
        while time.perf_counter() < deadline:
            if self.stop_event.is_set():
                return False
            try:
                self.update()
            except tk.TclError:
                return False
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                break
            time.sleep(min(max(0.01, float(step_sec)), remaining))
        return True

    def _get_countdown_button(self):
        """단일/다중 실행에서 같은 카운트다운 문구를 각 탭의 Start 버튼에 표시한다."""
        return getattr(self, "_active_countdown_button", None) or self.start_button

    def _show_measurement_wait_countdown(self, wait_sec: float) -> None:
        try:
            wait_sec = max(0.0, float(wait_sec))
        except Exception:
            wait_sec = 0.0

        self._countdown_running = True
        countdown_button = self._get_countdown_button()

        if wait_sec <= 0:
            if countdown_button is not None:
                countdown_button.configure(text="작동을 시작하세요")
            self._sleep_with_ui_updates(0.15)
            self._countdown_running = False
            return

        total = int(math.ceil(wait_sec))
        try:
            if countdown_button is not None:
                countdown_button.configure(state=tk.DISABLED)
        except Exception:
            pass
        self._set_status_box("Measurement 시작 대기중", "#DBEAFE", "#1D4ED8")
        self.status_var.set("Measurement 시작 대기중")

        for remain in range(total, 0, -1):
            if self.stop_event.is_set():
                break
            if countdown_button is not None:
                countdown_button.configure(text=f"{remain}초 기다리세요")
            self.current_detail.configure(state="normal")
            self.current_detail.delete("1.0", tk.END)
            self.current_detail.insert(
                "1.0",
                "Vector Measurement가 시작되었습니다.\n"
                f"설정된 대기시간 후 TC 감시를 시작합니다.\n\n"
                f"남은 시간: {remain}초\n",
            )
            self.current_detail.configure(state="normal")
            if not self._sleep_with_ui_updates(1.0):
                break

        if self.stop_event.is_set():
            try:
                if countdown_button is not None:
                    countdown_button.configure(text="중단 처리중...")
            except Exception:
                pass
            self._set_status_box("중단 처리중", "#FEF3C7", "#92400E")
            self.status_var.set("중단 처리중")
            self._countdown_running = False
            return

        if countdown_button is not None:
            countdown_button.configure(text="작동을 시작하세요")
        self._set_status_box("작동을 시작하세요", "#DCFCE7", "#166534")
        self.status_var.set("작동을 시작하세요")
        self._sleep_with_ui_updates(0.15)
        self._countdown_running = False

    def _invalidate_canoe_client(self, reason: str = ""):
        self.client = None
        self.canoe_status_var.set("Vector 연결 : -")
        self._refresh_status_badges()

    # -----------------------------
    # rev87: Vector CANoe/CANalyzer COM 연결 현장 진단 (read-only)
    # -----------------------------
    def _run_canoe_connection_diagnostic(
        self,
        trigger_error=None,
        show_popup: bool = True,
        reason: str = "Vector 연결 진단",
    ):
        diag_path = None
        try:
            self._log(f"[DIAG] Vector CANoe/CANalyzer COM 진단 시작: {reason}\n")
            diag = core.collect_vector_com_diagnostics(trigger_error=trigger_error, preference=self.vector_product_var.get())
            diag_path = core.save_vector_com_diagnostic_report(self._app_dir, diag)
            self.last_canoe_diag_path = str(diag_path)

            active = diag.get("active_object_probe") or {}
            processes = (diag.get("vector_processes") or {}).get("items") or []
            registry = diag.get("registry") or []
            registered = any((x.get("clsid") or x.get("local_server32") or x.get("versioned_progids")) for x in registry)
            summary = (
                f"GetActiveObject 재확인: {'성공' if active.get('success') else '실패'}\n"
                f"Vector 관련 프로세스: {len(processes)}개 감지\n"
                f"COM Registry 정보: {'감지' if registered else '미감지/조회실패'}\n"
                f"Python 관리자 권한: {(diag.get('python') or {}).get('is_admin', '-')}\n\n"
                f"진단 파일:\n{diag_path}"
            )
            self._log(
                f"[DIAG] Vector COM 진단 완료: active={active.get('success')}, "
                f"processes={len(processes)}, file={diag_path}\n"
            )
            if show_popup:
                messagebox.showinfo(
                    "Vector 연결 진단",
                    summary + "\n\n현장 재현 후 이 TXT 파일을 그대로 업로드하면 추가 분석할 수 있습니다.",
                )
            return diag_path
        except Exception as e:
            self._log(f"[WARN] Vector COM 진단 정보 저장 실패: {type(e).__name__}: {e}\n")
            if show_popup:
                messagebox.showwarning(
                    "Vector 연결 진단 실패",
                    f"진단 정보를 수집/저장하지 못했습니다.\n{type(e).__name__}: {e}",
                )
            return None

    # -----------------------------
    # rev87 핵심: GetActiveObject 우선 + 기존 프로세스 확인 기반 guarded Dispatch fallback, 제품/버전 하드코딩 금지
    # -----------------------------
    def _connect_canoe(self, show_popup: bool = True):
        if not self._refresh_required_files_status(show_popup=False):
            if show_popup:
                messagebox.showwarning(
                    "필요 파일 설치 필요",
                    "Vector CANoe/CANalyzer 연결 및 로그 재검토에 필요한 파일 설치가 필요합니다.\n"
                    "[설정] 탭의 필요 파일 및 주의사항 영역에서 [필요 파일 설치]를 눌러주세요."
                )
            return False

        try:
            # GetActiveObject 우선. 실패 시 이미 실행 중인 제품 메인 프로세스가 확인된 경우에만 guarded Dispatch fallback.
            self.client = core.CANoeClient(
                bus_name=self.bus_name_var.get().strip() or "CAN",
                product_preference=self.vector_product_var.get(),
            ).connect(
                expected_version_keyword=None,
                expected_exe_keyword=None,
            )

            info = {}
            try:
                info = self.client.get_application_info()
            except Exception:
                info = {}
            version_text = self._format_canoe_version(info.get("version", ""))
            product_text = info.get("product", "Vector") or "Vector"
            self.canoe_status_var.set(f"Vector 연결 : {product_text} {version_text}")

            running = self.client.is_measurement_running()
            self.measurement_status_var.set(f"Measurement: {'실행 중' if running else '정지'}")
            self._refresh_status_badges()
            self._log(f"[OK] Vector COM 연결 성공: {info.get('product', '-')}\n")
            if str(info.get('product') or '').strip().lower() == 'canalyzer':
                self._log("[INFO] CANalyzer 연결: 관측/PASS-FAIL 지원. Stimulus는 direct Signal.Value 대신 TX/RX 탭의 CAPL Bridge backend를 사용합니다.\n")
            try:
                self._log(f"[OK] Vector 연결 정보: method={info.get('connected_by', '-')}, version={info.get('version', '-')}, exe={info.get('fullname', '-')}, cfg={info.get('configuration', '-')}\n")
            except Exception:
                pass
            return True
        except Exception as e:
            self.client = None
            self.canoe_status_var.set("Vector 연결 : 실패")
            self.measurement_status_var.set("Measurement: 확인 불가")
            self._refresh_status_badges()
            self._log(f"[ERROR] Vector 연결 실패: {e}\n")

            # rev87: 연결 정책은 바꾸지 않고, 실패 원인 분석용 정보만 자동 수집한다.
            diag_path = self._run_canoe_connection_diagnostic(
                trigger_error=e,
                show_popup=False,
                reason="Vector COM 연결 실패 자동 진단",
            )
            if show_popup:
                popup_text = str(e)
                if diag_path is not None:
                    popup_text += (
                        "\n\nVector COM 진단 파일을 자동 저장했습니다.\n"
                        f"{diag_path}\n\n"
                        "현장 재현 후 이 TXT 파일을 함께 업로드해주세요."
                    )
                messagebox.showerror("Vector 연결 실패", popup_text)
            return False

    def _ensure_client(self, force_reconnect: bool = False, show_popup: bool = True):
        if force_reconnect:
            self.client = None

        if self.client is None or not self.client.is_connected():
            ok = self._connect_canoe(show_popup=show_popup)
            if not ok:
                raise RuntimeError("Vector 연결 실패")

        if self.client is None or not self.client.is_connected():
            raise RuntimeError("Vector 연결 실패")

        return self.client

    # -------------------------------------------------
    # rev87 Optional CAPL Event Collector (read-only observation layer)
    # -------------------------------------------------
    def _on_collector_enabled_changed(self):
        self._save_current_user_settings()
        if bool(self.collector_enabled_var.get()):
            if COLLECTOR_AVAILABLE:
                self.collector_status_var.set("CAPL Collector: 사용(기본) / 준비 확인 전")
                self._generate_capl_collector(show_popup=False)
            else:
                self.collector_status_var.set("CAPL Collector: 모듈 없음 → 기존 COM/로그 방식")
        else:
            self._collector_stop_polling(keep_cache=False)
            self.collector_status_var.set("CAPL Collector: OFF → 기존 COM polling + 로그 재검토")

    def _collector_conditions_all(self):
        out = []
        for row in list(getattr(self, "condition_rows", []) or []):
            if getattr(row, "is_valid", False) and getattr(row, "condition", None) is not None:
                out.append(row.condition)
        return out

    def _collector_catalog_key(self):
        dbc_map = self._collect_dbc_mapping()
        dbc_key = []
        for ch, raw in sorted(dbc_map.items()):
            p = Path(raw)
            try:
                stat = p.stat()
                dbc_key.append((int(ch), str(p.resolve()), int(stat.st_mtime_ns), int(stat.st_size)))
            except Exception:
                dbc_key.append((int(ch), str(p), 0, 0))
        cond_key = []
        for cond in self._collector_conditions_all():
            for role, seq in (("I", getattr(cond, "input_conditions", [])), ("O", getattr(cond, "output_conditions", []))):
                for exp in list(seq or []):
                    cond_key.append((str(getattr(cond, "tc_no", "")), role, str(exp.message), str(exp.signal), str(exp.expected_value_raw)))
        return (tuple(dbc_key), tuple(cond_key))

    def _get_collector_catalog(self, force: bool = False):
        if not COLLECTOR_AVAILABLE or collector_module is None:
            return None
        key = self._collector_catalog_key()
        if not force and self._collector_catalog_cache is not None and key == self._collector_catalog_cache_key:
            return self._collector_catalog_cache
        dbc_map = self._collect_dbc_mapping()
        if not dbc_map or not self._collector_conditions_all():
            self._collector_catalog_cache = None
            self._collector_catalog_cache_key = key
            return None
        catalog = collector_module.build_catalog(self._collector_conditions_all(), dbc_map)
        self._collector_catalog_cache = catalog
        self._collector_catalog_cache_key = key
        return catalog

    def _generate_capl_collector(self, show_popup: bool = True):
        if not COLLECTOR_AVAILABLE or collector_module is None:
            msg = "oracle_checker_collector_rev87.py를 사용할 수 없습니다. 기존 COM polling/로그 재검토는 그대로 사용 가능합니다."
            self.collector_status_var.set("CAPL Collector: 모듈 없음 → 기존 방식")
            if show_popup:
                messagebox.showwarning("CAPL Collector", msg)
            return None
        try:
            conditions = self._collector_conditions_all()
            dbc_map = self._collect_dbc_mapping()
            if not conditions:
                raise RuntimeError("먼저 Oracle TC를 불러오세요.")
            if not dbc_map:
                raise RuntimeError("Collector 생성용 CAN1~CAN3 DBC가 지정되지 않았습니다.")
            capl_path = self._app_dir / "PF_Observer_Collector_rev87.can"
            manifest_path = self._app_dir / "PF_Observer_Collector_rev87.manifest.json"
            catalog = collector_module.generate_collector_files(conditions, dbc_map, capl_path, manifest_path)
            self._collector_catalog_cache = catalog
            self._collector_catalog_cache_key = self._collector_catalog_key()
            self._collector_last_bind_failed_signature = None
            summary = collector_module.short_catalog_summary(catalog)
            self.collector_status_var.set(f"CAPL Collector: 생성됨 / {len(catalog.targets)} target / sig=0x{catalog.signature_hex}")
            self._log(f"[COLLECTOR] rev87 CAPL 생성: {capl_path} | {summary}\n")
            if catalog.skipped:
                self._log(f"[COLLECTOR] 비숫자 Expected/CAPL 식별자 등 제외 {len(catalog.skipped)}건 - 해당 항목은 기존 COM/로그로 판정\n")
            if show_popup:
                messagebox.showinfo(
                    "CAPL Collector 생성 완료",
                    f"생성 파일:\n{capl_path}\n\nTarget: {len(catalog.targets)}개\nSignature: 0x{catalog.signature_hex}\n\n"
                    "이 .can을 CANoe/CANalyzer Configuration의 관측용 CAPL Node에 수동 삽입/Compile하세요.\n"
                    "Collector가 없거나 오래된 경우에도 실행은 중단되지 않고 기존 COM polling + ASC/BLF 재검토로 자동 fallback합니다.",
                )
            return catalog
        except Exception as e:
            self.collector_status_var.set(f"CAPL Collector: 생성 보류 / {e}")
            self._log(f"[COLLECTOR] 생성 보류: {e}\n")
            if show_popup:
                messagebox.showwarning("CAPL Collector 생성 보류", str(e))
            return None

    def _collector_stop_polling(self, keep_cache: bool = True):
        try:
            if self._collector_poll_after_id is not None:
                self.after_cancel(self._collector_poll_after_id)
        except Exception:
            pass
        self._collector_poll_after_id = None
        self._collector_runtime_active = False
        self._collector_functions = {}
        self._collector_runtime_targets_by_id = {}
        if not keep_cache:
            with self._collector_lock:
                self._collector_hit_cache.clear()

    def _collector_drain_events(self, max_events: int = 1000):
        if not self._collector_runtime_active:
            return 0
        funcs = self._collector_functions
        try:
            count_fn = funcs.get("PF_OBS_COUNT")
            pop_fn = funcs.get("PF_OBS_POP_ID")
            ms_fn = funcs.get("PF_OBS_LAST_MS")
            if count_fn is None or pop_fn is None or ms_fn is None:
                return 0
            count = max(0, int(count_fn.Call() or 0))
            drained = 0
            while count > 0 and drained < max(1, int(max_events)):
                target_id = int(pop_fn.Call() or 0)
                hit_ms = float(ms_fn.Call() or 0.0)
                target = self._collector_runtime_targets_by_id.get(target_id)
                if target is not None and target_id > 0 and hit_ms > 0:
                    hit = {
                        "target_id": target_id,
                        "key": target.key,
                        "channel": int(target.channel),
                        "logical_can": target.logical_can,
                        "message": target.message,
                        "signal": target.signal,
                        "value": target.expected_raw,
                        "hit_ms": hit_ms,
                        "source": "capl_collector",
                    }
                    with self._collector_lock:
                        prev = self._collector_hit_cache.get(target.key)
                        if prev is None or float(prev.get("hit_ms") or 0.0) <= hit_ms:
                            self._collector_hit_cache[target.key] = hit
                drained += 1
                count -= 1
            return drained
        except Exception as e:
            self._log(f"[COLLECTOR] runtime poll 오류 → 기존 COM polling 계속 사용: {e}\n")
            self.collector_status_var.set("CAPL Collector: runtime 오류 → 기존 COM/로그 fallback")
            self._collector_stop_polling(keep_cache=True)
            return 0

    def _collector_poll_tick(self):
        if not self._collector_runtime_active:
            self._collector_poll_after_id = None
            return
        self._collector_drain_events(max_events=600)
        if not self._collector_runtime_active:
            return
        try:
            overflow_fn = self._collector_functions.get("PF_OBS_OVERFLOW")
            overflow = int(overflow_fn.Call() or 0) if overflow_fn is not None else 0
            if overflow > 0:
                self.collector_status_var.set(f"CAPL Collector: 활성 / queue overflow={overflow} (로그 재검토 권장)")
        except Exception:
            pass
        self._collector_poll_after_id = self.after(50, self._collector_poll_tick)

    def _collector_probe_cache(self, expectation, channels, min_hit_ms: float = 0.0):
        # The main-thread CAPL polling can be stopped before the worker finishes (e.g. 수행 완료).
        # Keep already-drained hit evidence usable from the thread-safe cache until finalization.
        if collector_module is None:
            return None
        best = None
        for ch in channels or []:
            key = collector_module.target_key(int(ch), expectation.message, expectation.signal, expectation.expected_value_raw)
            if not key:
                continue
            with self._collector_lock:
                hit = dict(self._collector_hit_cache.get(key) or {})
            if not hit:
                continue
            hit_ms = float(hit.get("hit_ms") or 0.0)
            if hit_ms + 1e-9 < float(min_hit_ms or 0.0):
                continue
            if best is None or hit_ms < float(best.get("hit_ms") or 1e30):
                best = hit
        return best

    def _start_measurement_with_optional_collector(self, conditions, wait_sec: float, label: str):
        """Start Measurement; when possible bind the read-only CAPL collector, otherwise exact legacy fallback."""
        self._collector_stop_polling(keep_cache=False)
        if not bool(self.collector_enabled_var.get()) or not COLLECTOR_AVAILABLE or collector_module is None:
            self.collector_status_var.set("CAPL Collector: OFF/미사용 → 기존 COM polling + 로그 재검토")
            return self._safe_start_measurement_for_new_run(wait_sec, label=label)

        try:
            catalog = self._get_collector_catalog(force=False)
            if catalog is None or not catalog.targets:
                raise RuntimeError("Collector target catalog가 비어 있습니다. TC/DBC 설정을 확인하세요.")

            capl_path = self._app_dir / "PF_Observer_Collector_rev87.can"
            manifest_path = self._app_dir / "PF_Observer_Collector_rev87.manifest.json"
            if not capl_path.is_file() or not manifest_path.is_file():
                self.collector_status_var.set("CAPL Collector: 생성 파일 없음 → 기존 COM/로그 fallback")
                self._log("[COLLECTOR] 생성된 PF_Observer_Collector_rev87.can/manifest가 없어 runtime binding을 생략합니다.\n")
                return self._safe_start_measurement_for_new_run(wait_sec, label=label)
            try:
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest_sig = int(manifest_data.get("signature_u32")) & 0xFFFFFFFF
            except Exception:
                manifest_sig = -1
            if manifest_sig != (int(catalog.signature_u32) & 0xFFFFFFFF):
                self.collector_status_var.set("CAPL Collector: 로컬 manifest 불일치 → 생성/Compile 후 사용")
                self._log("[COLLECTOR] 현재 TC/DBC와 생성 manifest가 달라 runtime binding을 생략합니다. [CAPL Collector 생성/갱신] 후 Compile하세요.\n")
                return self._safe_start_measurement_for_new_run(wait_sec, label=label)
            if self._collector_last_bind_failed_signature == int(catalog.signature_u32):
                self.collector_status_var.set("CAPL Collector: 이전 binding 실패 → 이번 세션 기존 방식")
                self._log("[COLLECTOR] 같은 signature에서 이전 binding 실패가 있어 재시도 지연을 피하고 기존 방식으로 즉시 fallback합니다. Collector Compile 후 [생성/갱신]을 다시 누르세요.\n")
                return self._safe_start_measurement_for_new_run(wait_sec, label=label)

            channels = self._collect_selected_channels()
            selected_targets = collector_module.select_targets_for_conditions(catalog, conditions, channels=channels)
            if not selected_targets:
                raise RuntimeError("선택 TC에서 CAPL Collector가 지원하는 숫자형 Expected/DBC target을 찾지 못했습니다.")

            client = self._ensure_client(force_reconnect=False, show_popup=True)
            self.measurement_status_var.set("Measurement: Collector 준비 중")
            self._refresh_status_badges()
            self._log(
                f"[COLLECTOR] {label}: CAPL Event Collector 우선 시도 / selected_targets={len(selected_targets)}, signature=0x{catalog.signature_hex}\n"
            )
            self.update_idletasks()
            started_perf = time.perf_counter()
            funcs = client.start_measurement_with_capl_bindings(
                collector_module.COLLECTOR_CAPL_FUNCTIONS,
                start_timeout_sec=2.0,
                restart_if_running=True,
            )
            self._measurement_started_perf = started_perf
            self._collector_last_bind_failed_signature = None
            actual_sig = int(funcs["PF_OBS_SIGNATURE"].Call() or 0) & 0xFFFFFFFF
            expected_sig = int(catalog.signature_u32) & 0xFFFFFFFF
            if actual_sig != expected_sig:
                self.collector_status_var.set(
                    f"CAPL Collector: signature 불일치(실행=0x{actual_sig:08X}, 현재=0x{expected_sig:08X}) → 기존 방식"
                )
                self._log(
                    f"[COLLECTOR] signature 불일치 → Collector 증거 무시, 기존 COM polling + 로그 fallback 사용. "
                    f"실행=0x{actual_sig:08X}, 현재=0x{expected_sig:08X}. [CAPL Collector 생성/갱신] 후 Compile하세요.\n"
                )
            else:
                active_fn = funcs.get("PF_OBS_SET_ACTIVE")
                if active_fn is None:
                    raise RuntimeError("PF_OBS_SET_ACTIVE 함수를 찾지 못했습니다.")
                active_count = 0
                for target in selected_targets:
                    ok = int(active_fn.Call(int(target.target_id), 1) or 0)
                    if ok:
                        active_count += 1
                self._collector_functions = funcs
                self._collector_runtime_targets_by_id = {int(t.target_id): t for t in selected_targets}
                self._collector_runtime_active = active_count > 0
                with self._collector_lock:
                    self._collector_hit_cache.clear()
                if self._collector_runtime_active:
                    self.collector_status_var.set(
                        f"CAPL Collector: 활성 / {active_count} target / sig=0x{catalog.signature_hex}"
                    )
                    self._log(
                        f"[COLLECTOR] 활성화 성공: {active_count} target. CAPL event hit + 기존 COM polling을 병행합니다.\n"
                    )
                    self._collector_poll_after_id = self.after(20, self._collector_poll_tick)

            self.measurement_status_var.set("Measurement: 실행 중")
            self._refresh_status_badges()
            self._log("[OK] Measurement 자동 시작 완료 - 대기 카운트다운 시작\n")
            self._show_measurement_wait_countdown(wait_sec)
            if not self.stop_event.is_set():
                self._log("[OK] Measurement 시작 후 대기시간 완료 - TC 감시 시작\n")
            return client
        except Exception as e:
            try:
                if 'catalog' in locals() and catalog is not None:
                    self._collector_last_bind_failed_signature = int(catalog.signature_u32)
            except Exception:
                pass
            self._collector_stop_polling(keep_cache=False)
            self.collector_status_var.set("CAPL Collector: 준비 실패 → 기존 COM polling + 로그 fallback")
            self._log(f"[COLLECTOR] 준비 실패/미설치 → 기존 방식으로 자동 fallback: {e}\n")
            return self._safe_start_measurement_for_new_run(wait_sec, label=label)

    def _safe_start_measurement_for_new_run(self, wait_sec: float, label: str = "선택 TC Start"):
        last_error = None
        had_connection_failure = False

        for attempt in range(2):
            try:
                # 실행 계열도 VectorApplicationClient 정책 사용: 제품 메인 프로세스 미실행 시 Dispatch fallback 금지
                client = self._ensure_client(
                    force_reconnect=(attempt > 0),
                    show_popup=(attempt == 0),
                )
                if client.is_measurement_running():
                    self.measurement_status_var.set("Measurement: 재시작 중")
                    self._refresh_status_badges()
                    self._log(
                        f"[INFO] {label} 시점에 Measurement가 이미 실행 중이므로 "
                        "TC 시작 기준을 맞추기 위해 Stop 후 재시작합니다.\n"
                    )
                    self.update_idletasks()
                    client.stop_measurement()
                    time.sleep(0.5)
                    if self.stop_event.is_set():
                        return client

                self.measurement_status_var.set("Measurement: 시작 중")
                self._refresh_status_badges()
                self._log(
                    f"[INFO] {label} 요청에 따라 CANoe Measurement 자동 시작 "
                    f"(Measurement 시작 후 대기시간={wait_sec}초)\n"
                )
                self.update_idletasks()
                self._measurement_started_perf = time.perf_counter()
                client.start_measurement(wait_sec=0.0)
                self.measurement_status_var.set("Measurement: 실행 중")
                self._refresh_status_badges()
                self._log("[OK] Measurement 자동 시작 완료 - 대기 카운트다운 시작\n")
                self._show_measurement_wait_countdown(wait_sec)
                if not self.stop_event.is_set():
                    self._log("[OK] Measurement 시작 후 대기시간 완료 - TC 감시 시작\n")
                return client
            except Exception as e:
                last_error = e
                if "Vector 연결 실패" in str(e):
                    had_connection_failure = True
                    break
                self._log(f"[WARN] Measurement 자동 시작 시도 {attempt + 1}/2 실패: {e}\n")
                self._invalidate_canoe_client(str(e))
                time.sleep(0.4)

        self.measurement_status_var.set("Measurement: 시작 실패")
        self._refresh_status_badges()

        if had_connection_failure:
            raise RuntimeError("Vector 연결 실패")

        raise RuntimeError(f"Measurement 자동 시작 실패: {last_error}")

    def _safe_stop_measurement_for_transition(self, label: str, invalidate_after: bool = True) -> bool:
        # rev87: drain latched CAPL events once before Measurement Stop, then keep the Python hit cache
        # available to the worker while it finalizes.
        try:
            self._collector_drain_events(max_events=2000)
        except Exception:
            pass
        self._collector_stop_polling(keep_cache=True)
        last_error = None
        for attempt in range(2):
            try:
                client = self._ensure_client(force_reconnect=(attempt > 0), show_popup=False)
                client.stop_measurement()
                self.measurement_status_var.set("Measurement: 정지")
                self._refresh_status_badges()
                self._log(f"[OK] {label} 요청에 따라 CANoe Measurement 정지 완료\n")
                time.sleep(0.5)
                if invalidate_after:
                    self._invalidate_canoe_client(f"{label} 후 다음 실행 안정화를 위해 재연결 예정")
                return True
            except Exception as e:
                last_error = e
                self._log(f"[WARN] {label} 중 Measurement 정지 시도 {attempt + 1}/2 실패: {e}\n")
                self._invalidate_canoe_client(str(e))
                time.sleep(0.4)

        self.measurement_status_var.set("Measurement: 정지 실패")
        self._refresh_status_badges()
        self._log(f"[ERROR] {label} 중 Measurement 정지 실패: {last_error}\n")
        return False

    def _start_measurement(self):
        try:
            # VectorApplicationClient guarded 연결 정책
            client = self._ensure_client()
            wait_sec = float(self.measurement_wait_var.get().strip() or "0")
            client.start_measurement(wait_sec=wait_sec)
            self.measurement_status_var.set("Measurement: 실행 중")
            self._refresh_status_badges()
            self._log(f"[OK] Measurement 시작 완료. 대기={wait_sec}초\n")
        except Exception as e:
            self._log(f"[ERROR] Measurement 시작 실패: {e}\n")
            messagebox.showerror("Measurement 시작 실패", str(e))

    def _stop_measurement(self):
        try:
            client = self._ensure_client()
            client.stop_measurement()
            self.measurement_status_var.set("Measurement: 정지")
            self._refresh_status_badges()
            self._log("[OK] Measurement 정지 완료\n")
        except Exception as e:
            self._log(f"[ERROR] Measurement 정지 실패: {e}\n")
            messagebox.showerror("Measurement 정지 실패", str(e))

    def _collect_selected_channels(self) -> List[int]:
        """rev87: DBC가 지정된 CANoe 논리 CAN만 감시 후보로 사용한다."""
        channels = [
            self._logical_can_to_channel(name)
            for name in self.can_names
            if self.can_dbc_vars[name].get().strip()
        ]
        # 기존 realtime-only 사용성을 위해 DBC가 하나도 없을 때만 CAN1~CAN3을 방어적으로 사용한다.
        return channels or [self._logical_can_to_channel(name) for name in self.can_names]

    def _collect_dbc_mapping(self) -> Dict[int, str]:
        """DBC는 CAN1->1, CAN2->2, CAN3->3 논리 채널에만 매핑한다."""
        out: Dict[int, str] = {}
        for can_name in self.can_names:
            p = self.can_dbc_vars[can_name].get().strip()
            if p:
                out[self._logical_can_to_channel(can_name)] = p
        return out

    def _start_selected_tc(self):
        if self.monitor_thread is not None and self.monitor_thread.is_alive():
            messagebox.showinfo("감시 중", "이미 감시가 진행 중입니다.")
            return

        selected_row = self._get_selected_condition_row()
        if selected_row is None:
            messagebox.showwarning("TC 선택 필요", "왼쪽 체크박스를 체크하여 감시할 TC를 선택하세요.")
            return

        row = selected_row
        if not row.is_valid or row.condition is None:
            messagebox.showerror("실행 불가", f"이 행은 로드 오류가 있어 실행할 수 없습니다.\n사유: {row.error_reason}")
            return

        condition = row.condition
        self._reset_run_session_state()
        self._clear_condition_result_overlay(condition)
        self._refresh_all_summary(condition, None)

        try:
            client = None
            channels = self._collect_selected_channels()
            if not channels:
                raise ValueError("감시할 CANoe 논리 CAN을 구성하지 못했습니다.")

            poll_interval = float(self.poll_interval_var.get().strip() or "0.05")
            measurement_wait_sec = float(self.measurement_wait_var.get().strip() or "0")
            drop_first_seconds = float(self.drop_first_seconds_var.get().strip() or self.default_drop_seconds)
            log_wait_timeout = float(self.log_wait_timeout_var.get().strip() or self.default_log_wait_seconds)
        except Exception as e:
            messagebox.showerror("설정 오류", str(e))
            return

        self.stop_event.clear()
        self.done_event.clear()
        try:
            is_multi_sequential = (
                bool(getattr(self, "multi_active", False))
                and getattr(getattr(self, "multi_mode_var", None), "get", lambda: "")().strip() == "순차실행"
                and getattr(self, "multi_start_button", None) is not None
            )
        except Exception:
            is_multi_sequential = False
        self._active_countdown_button = self.multi_start_button if is_multi_sequential else self.start_button
        countdown_button = self._get_countdown_button()
        if countdown_button is not None:
            countdown_button.configure(state=tk.DISABLED, text="Measurement 준비중...")
        self.start_button.configure(state=tk.DISABLED)
        self.complete_button.configure(state=tk.DISABLED)
        self.abort_button.configure(state=tk.NORMAL)

        try:
            client = self._start_measurement_with_optional_collector([condition], measurement_wait_sec, label="선택 TC Start")
        except Exception as e:
            self.measurement_status_var.set("Measurement: 시작 실패")
            self._refresh_status_badges()
            failed_countdown_button = self._get_countdown_button()
            self._active_countdown_button = None
            self.start_button.configure(state=tk.NORMAL, text="선택 TC Start")
            if failed_countdown_button is not None and failed_countdown_button is not self.start_button:
                failed_countdown_button.configure(state=tk.NORMAL, text="선택 TC 다중 Start")
            self.complete_button.configure(state=tk.DISABLED)
            self.abort_button.configure(state=tk.DISABLED)
            self._log(f"[ERROR] Measurement 자동 시작 실패: {e}\n")
            if "Vector 연결 실패" not in str(e):
                messagebox.showerror("Measurement 자동 시작 실패", str(e))
            return

        if self.stop_event.is_set():
            self._log("[GUI] Measurement 대기 중 중단되어 TC 감시를 시작하지 않습니다.\n")
            return

        manual_log_path = self.log_file_var.get().strip() or None if self.manual_log_enabled_var.get() else None
        log_dir = self.log_dir_var.get().strip() or None
        dbc_map = self._collect_dbc_mapping()
        auto_log = bool(self.auto_log_review_var.get())
        auto_find_latest_log = bool(self.auto_find_latest_log_var.get())
        auto_stop_measurement = bool(self.auto_stop_measurement_var.get())

        running_countdown_button = self._get_countdown_button()
        if running_countdown_button is not None:
            running_countdown_button.configure(state=tk.DISABLED, text="검토중...")
        self.start_button.configure(state=tk.DISABLED)
        self.complete_button.configure(state=tk.NORMAL)
        self.abort_button.configure(state=tk.NORMAL)
        self._set_status_box("검토중", "#FEF3C7", "#92400E")
        self.status_var.set("검토중")

        tc_start_ts = time.time()
        self._log(
            f"[START] 최종 판정 시작: {condition.tc_no} | outputs={len(condition.output_conditions)} "
            f"| channels={channels} | drop={drop_first_seconds}s | log_wait={log_wait_timeout}s\n"
        )

        worker_bus_name = self.bus_name_var.get().strip() or "CAN"
        worker_vector_product = self.vector_product_var.get().strip() or "자동"

        def worker():
            try:
                try:
                    # Worker 스레드도 VectorApplicationClient guarded 연결 정책으로 재연결
                    worker_client = core.CANoeClient(bus_name=worker_bus_name, product_preference=worker_vector_product).connect(
                        expected_version_keyword=None,
                        expected_exe_keyword=None,
                    )
                except Exception as e:
                    diag_path = ""
                    try:
                        diag = core.collect_vector_com_diagnostics(trigger_error=e, preference=worker_vector_product)
                        diag_path = str(core.save_vector_com_diagnostic_report(self._app_dir, diag, prefix="vector_com_worker_diagnostic"))
                    except Exception:
                        pass
                    detail = f"Vector 연결 실패: {e}"
                    if diag_path:
                        detail += f"\n진단 파일: {diag_path}"
                    self.log_queue.put(("FINAL_ERROR", detail))
                    return
                result = core.check_condition_with_log_fallback(
                    client=worker_client,
                    condition=condition,
                    channel=channels,
                    stop_event=self.stop_event,
                    done_event=self.done_event,
                    poll_interval_sec=poll_interval,
                    progress_callback=lambda status, res: self.log_queue.put(("PROGRESS", status, res)),
                    log_progress_callback=lambda msg: self.log_queue.put(("LOG_PROGRESS", msg)),
                    log_path=manual_log_path,
                    log_dir=log_dir,
                    tc_start_ts=tc_start_ts,
                    dbc_path_by_channel=dbc_map,
                    auto_log_review=auto_log,
                    auto_find_latest_log=auto_find_latest_log,
                    auto_stop_measurement=auto_stop_measurement,
                    skip_log_review_on_pass=bool(self.skip_log_review_on_pass_var.get()),
                    log_wait_timeout=log_wait_timeout,
                    drop_first_seconds=drop_first_seconds,
                    realtime_timeout_override_sec=0.0 if is_multi_sequential else None,
                    collector_probe=self._collector_probe_cache if self._collector_runtime_active else None,
                    collector_measurement_start_perf=self._measurement_started_perf,
                )
                self.log_queue.put(("FINAL_DONE", result))
            except Exception as e:
                self.log_queue.put(("FINAL_ERROR", str(e)))

        self.monitor_thread = threading.Thread(target=worker, daemon=True)
        self.monitor_thread.start()

    def _complete_monitoring(self):
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            messagebox.showinfo("안내", "현재 진행 중인 감시가 없습니다.")
            return

        self.done_event.set()
        self.complete_button.configure(state=tk.DISABLED)
        self.start_button.configure(state=tk.DISABLED, text="종료 처리중...")
        self._log("[GUI] 수행 완료 요청 - Vector Measurement를 정지하고 로그 재검토 단계로 진행합니다.\n")

        self._safe_stop_measurement_for_transition("수행 완료", invalidate_after=True)

        self._set_status_box("수행 완료 처리중", "#DBEAFE", "#1D4ED8")
        self.status_var.set("수행 완료 처리중")

    def _abort_monitoring(self):
        self.stop_event.set()
        self.done_event.clear()
        self.start_button.configure(state=tk.DISABLED, text="중단 처리중...")
        self.complete_button.configure(state=tk.DISABLED)
        self.abort_button.configure(state=tk.DISABLED)
        self._log("[GUI] 중단 요청 - Python 감시 중지 + CANoe Measurement Stop 시도\n")

        self._safe_stop_measurement_for_transition("중단", invalidate_after=True)

        self._set_status_box("중단 처리중", "#FEF3C7", "#92400E")
        self.status_var.set("중단 처리중")
        self._finish_abort_when_thread_exits()

    def _finish_abort_when_thread_exits(self):
        if self.monitor_thread is not None and self.monitor_thread.is_alive():
            self.after(150, self._finish_abort_when_thread_exits)
            return
        self.monitor_thread = None
        self._collector_stop_polling(keep_cache=False)
        self.start_button.configure(state=tk.NORMAL, text="선택 TC Start")
        self.complete_button.configure(state=tk.DISABLED)
        self.abort_button.configure(state=tk.DISABLED)
        self.status_var.set("대기중")
        self._set_status_box("대기중", "#E5E7EB", "#111827")
        self._log("[GUI] 중단 처리 완료 - 다음 TC Start 가능\n")

    def _on_final_done(self, result):
        self.current_result = result
        self.results.append(result)
        self._append_result_tree(result)
        self._show_result_detail(result)
        self._refresh_all_summary(result.condition, result)
        self._set_condition_result_status(result.condition, result.final_status)

        if result.final_status == "PASS":
            self._set_status_box("최종 PASS", "#DCFCE7", "#166534")
        elif result.final_status == "FAIL":
            self._set_status_box("최종 FAIL", "#FEE2E2", "#991B1B")
        elif result.final_status == "ERROR":
            self._set_status_box("ERROR", "#FEE2E2", "#991B1B")
        elif result.final_status == "N/A":
            self._set_status_box("중단됨", "#FEF3C7", "#92400E")
        else:
            self._set_status_box(result.final_status, "#E5E7EB", "#111827")

        self.status_var.set(result.final_status)
        self.monitor_thread = None
        self._collector_stop_polling(keep_cache=False)
        self.start_button.configure(state=tk.NORMAL, text="선택 TC Start")
        self.complete_button.configure(state=tk.DISABLED)
        self.abort_button.configure(state=tk.DISABLED)
        if result.final_status == "PASS" and bool(self.auto_stop_measurement_var.get()):
            self.measurement_status_var.set("Measurement: 정지")
            self._refresh_status_badges()
        self._invalidate_canoe_client("TC 종료 후 다음 Start 안정화를 위해 재연결 예정")

        rt_status = result.realtime_result.status if result.realtime_result else "-"
        lg_status = result.log_result.status if result.log_result else "-"
        self._log(
            f"[END] 최종 판정 종료: final={result.final_status}, realtime={rt_status}, log={lg_status}, "
            f"used_log={result.used_log_path or '-'}, msg={result.final_message}\n"
        )

        # rev40: 최종 결과가 나와도 결과 상세 탭으로 자동 이동하지 않는다.

    def _append_result_tree(self, result):
        c = result.condition
        rt_status = result.realtime_result.status if result.realtime_result else ""
        log_status = result.log_result.status if result.log_result else ""
        tag = "result_pass" if result.final_status == "PASS" else "result_na" if result.final_status == "N/A" else "result_fail" if result.final_status in ("FAIL", "ERROR") else ""

        self.result_tree.insert(
            "",
            tk.END,
            tags=(tag,) if tag else (),
            values=(
                c.tc_no,
                result.final_status,
                rt_status,
                log_status,
                result.final_observed_value_raw,
                result.final_message,
            ),
        )

    def _iter_loaded_signal_candidates(self):
        """현재 로드된 Oracle Excel 안에서 유사 신호 힌트 후보를 만든다.

        실제 로그 전체에서 비슷한 신호를 자동 추출하는 것은 Step 1~5 수준의 별도 분석이 필요하다.
        여기서는 사용자가 Fail 원인을 빠르게 좁힐 수 있도록, 현재 Oracle 시트에 이미 정의된
        Message/Signal/Expected 후보를 우선순위로 보여준다.
        """
        seen = set()
        for idx, row in enumerate(getattr(self, "condition_rows", [])):
            if not getattr(row, "is_valid", False) or row.condition is None:
                continue
            cond = row.condition
            for role, exps in (("입력", cond.input_conditions), ("출력", cond.output_conditions)):
                for exp in exps:
                    key = (cond.tc_no, role, exp.message, exp.signal, exp.expected_value_raw)
                    if key in seen:
                        continue
                    seen.add(key)
                    yield {
                        "row_index": idx,
                        "tc_no": cond.tc_no,
                        "role": role,
                        "message": exp.message,
                        "signal": exp.signal,
                        "expected": exp.expected_value_raw,
                    }

    def _collect_failed_expectations_for_hint(self, result):
        failed = []
        condition = result.condition

        def _collect(source_name, checks):
            for one in checks or []:
                status = (getattr(one, "status", "") or "").upper()
                if status == "PASS":
                    continue
                exp = getattr(one, "expectation", None)
                if exp is None:
                    continue
                failed.append({
                    "source": source_name,
                    "message": exp.message,
                    "signal": exp.signal,
                    "expected": exp.expected_value_raw,
                    "actual": getattr(one, "observed_value_raw", None),
                    "status": getattr(one, "status", ""),
                    "reason": getattr(one, "message", ""),
                })

        rt = getattr(result, "realtime_result", None)
        lg = getattr(result, "log_result", None)
        if rt is not None:
            _collect("실시간 입력", getattr(rt, "input_results", []))
            _collect("실시간 출력", getattr(rt, "output_results", []))
        if lg is not None:
            _collect("로그 입력", getattr(lg, "input_results", []))
            _collect("로그 출력", getattr(lg, "output_results", []))

        if not failed and getattr(result, "final_status", "") != "PASS":
            for exp in list(condition.input_conditions) + list(condition.output_conditions):
                failed.append({
                    "source": "최종",
                    "message": exp.message,
                    "signal": exp.signal,
                    "expected": exp.expected_value_raw,
                    "actual": None,
                    "status": getattr(result, "final_status", ""),
                    "reason": getattr(result, "final_message", ""),
                })
        return failed

    def _build_fail_signal_hint_lines(self, result, max_items_per_signal: int = 6):
        if result is None or getattr(result, "final_status", "") == "PASS":
            return []

        candidates = list(self._iter_loaded_signal_candidates())
        failed_items = self._collect_failed_expectations_for_hint(result)
        if not failed_items:
            return []

        lines = []
        lines.append("[Fail 분석 힌트 - 유사 신호 후보]")
        lines.append("※ 현재 Oracle Excel에 로드된 조건 안에서만 찾은 후보입니다. 전체 로그 기반 후보 추출은 기존 Step 1~5 분석이 더 정확합니다.")

        for failed in failed_items[:6]:
            target_sig = str(failed.get("signal", "") or "")
            target_msg = str(failed.get("message", "") or "")
            target_exp = str(failed.get("expected", "") or "")
            lines.append("")
            lines.append(
                f"- 미충족 조건: {failed.get('source', '-')} | {target_msg}:{target_sig} == {target_exp} "
                f"/ Actual={failed.get('actual', '-')}, Status={failed.get('status', '-')}"
            )

            scored = []
            for cand in candidates:
                cand_sig = str(cand.get("signal", "") or "")
                cand_msg = str(cand.get("message", "") or "")
                cand_exp = str(cand.get("expected", "") or "")
                if cand_sig == target_sig and cand_msg == target_msg and cand_exp == target_exp:
                    continue
                sig_score = difflib.SequenceMatcher(None, target_sig.lower(), cand_sig.lower()).ratio()
                same_msg = (cand_msg == target_msg)
                same_exp = (cand_exp == target_exp)
                contains = bool(target_sig and cand_sig and (target_sig.lower() in cand_sig.lower() or cand_sig.lower() in target_sig.lower()))
                if same_msg or same_exp or sig_score >= 0.55 or contains:
                    score = sig_score + (0.35 if same_msg else 0.0) + (0.20 if same_exp else 0.0) + (0.15 if contains else 0.0)
                    scored.append((score, same_msg, same_exp, cand))

            scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
            if not scored:
                lines.append("  · 유사 후보 없음: Message/Signal/DBC/논리 CAN 매핑 또는 로그 분석 결과를 별도 확인하세요.")
                continue

            for score, same_msg, same_exp, cand in scored[:max_items_per_signal]:
                flags = []
                if same_msg:
                    flags.append("동일 Message")
                if same_exp:
                    flags.append("동일 Expected")
                if not flags:
                    flags.append(f"이름 유사도 {score:.2f}")
                lines.append(
                    f"  · [{cand['tc_no']}/{cand['role']}] {cand['message']}:{cand['signal']} == {cand['expected']} "
                    f"({', '.join(flags)})"
                )
        return lines

    def _show_result_detail(self, result):
        c = result.condition
        rt = result.realtime_result
        lg = result.log_result

        text = []
        text.append(f"TC 번호: {c.tc_no}")
        text.append(f"소분류: {c.subcategory}")
        text.append(f"TC 내용: {c.tc_content}")
        text.append(f"TC 예상 결과: {c.tc_expected_result}")

        text.append("")
        text.append("[입력 조건]")
        for i, inp in enumerate(c.input_conditions, start=1):
            text.append(f"  ({i}) {inp.message} / {inp.signal} / {inp.expected_value_raw}")

        text.append("")
        text.append("[출력 조건]")
        for i, o in enumerate(c.output_conditions, start=1):
            text.append(f"  ({i}) {o.message} / {o.signal} / {o.expected_value_raw}")

        text.append("")
        text.append(f"사용 로그 파일: {result.used_log_path or '-'}")

        if rt:
            text.append("")
            text.append("[실시간 결과]")
            text.append(f"  Status: {rt.status}")
            text.append(f"  Message: {rt.message}")
            for i, one in enumerate(rt.input_results, start=1):
                text.append(f"  Input({i}) Actual: {one.observed_value_raw} / Status={one.status}")
            for i, one in enumerate(rt.output_results, start=1):
                text.append(f"  Output({i}) Actual: {one.observed_value_raw} / Status={one.status}")

        if lg:
            text.append("")
            text.append("[로그 재검토 결과]")
            text.append(f"  Status: {lg.status}")
            text.append(f"  Message: {lg.message}")
            for i, one in enumerate(lg.input_results, start=1):
                text.append(f"  Input({i}) Actual: {one.observed_value_raw} / Status={one.status}")
            for i, one in enumerate(lg.output_results, start=1):
                text.append(f"  Output({i}) Actual: {one.observed_value_raw} / Status={one.status}")

        text.append("")
        text.append("[최종 결과]")
        text.append(f"  Final Status: {result.final_status}")
        text.append(f"  Final Observed Raw: {result.final_observed_value_raw}")
        text.append(f"  Final Observed Norm: {result.final_observed_value_norm}")
        text.append(f"  Final Observed Time: {result.final_observed_time}")
        text.append(f"  Final Message: {result.final_message}")
        text.append(f"  Elapsed Sec: {result.elapsed_sec}")

        hint_lines = self._build_fail_signal_hint_lines(result)
        if hint_lines:
            text.append("")
            text.extend(hint_lines)

        self.current_detail.configure(state="normal")
        self.current_detail.delete("1.0", tk.END)
        self.current_detail.insert("1.0", "\n".join(text))
        self.current_detail.configure(state="normal")

    def _build_report_settings(self) -> Dict[str, str]:
        dbc_lines = []
        for can_name in self.can_names:
            dbc = self.can_dbc_vars[can_name].get().strip()
            dbc_lines.append(f"{can_name} / DBC={dbc or '-'}")

        option_lines = [
            f"poll={self.poll_interval_var.get().strip() or '-'}s",
            f"measurement_wait={self.measurement_wait_var.get().strip() or '-'}s",
            f"default_timeout={self.default_timeout_var.get().strip() or '-'}s",
            f"drop_first={self.drop_first_seconds_var.get().strip() or '-'}s",
            f"log_wait={self.log_wait_timeout_var.get().strip() or '-'}s",
            f"auto_log_review={bool(self.auto_log_review_var.get())}",
            f"latest_log_auto_find={bool(self.auto_find_latest_log_var.get())}",
            f"auto_stop_measurement={bool(self.auto_stop_measurement_var.get())}",
            f"skip_log_review_on_pass={bool(self.skip_log_review_on_pass_var.get())}",
            f"multi_log_review={bool(self.multi_log_review_var.get())}",
        ]

        return {
            "excel_path": self.excel_path_var.get().strip(),
            "sheet_name": self.sheet_var.get().strip(),
            "bus_name": self.bus_name_var.get().strip() or "CAN",
            "channels": " / ".join(self.can_names) + " (CANoe 논리 CAN 고정)",
            "dbc_mapping": "\n".join(dbc_lines) if dbc_lines else "-",
            "log_dir": self.log_dir_var.get().strip(),
            "log_file": self.log_file_var.get().strip() if self.manual_log_enabled_var.get() else "-",
            "options": " / ".join(option_lines),
        }

    def _export_report(self):
        if not self.results:
            messagebox.showinfo("출력할 결과 없음", "아직 레포트로 출력할 결과가 없습니다.")
            return
        if report_module is None:
            messagebox.showerror(
                "레포트 모듈 없음",
                "oracle_checker_report*.py 파일을 찾지 못했습니다.\n"
                "front/onebyone/multiple 파일과 같은 폴더에 oracle_checker_report_rev87.py를 두세요."
            )
            return

        default_name = f"Oracle_Checker_Report_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        path = filedialog.asksaveasfilename(
            title="결과 레포트 출력",
            defaultextension=".html",
            initialfile=default_name,
            filetypes=[("HTML report", "*.html"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            out = report_module.export_final_results_to_html(
                self.results,
                path,
                settings=self._build_report_settings(),
                title="Oracle Checker 최종 판정 레포트",
            )
            self._log(f"[OK] 결과 레포트 출력 완료: {out}\n")
            try:
                webbrowser.open(Path(out).resolve().as_uri())
            except Exception:
                pass
            messagebox.showinfo("레포트 출력 완료", f"결과 레포트를 출력했습니다.\n{out}")
        except Exception as e:
            messagebox.showerror("레포트 출력 실패", str(e))
            self._log(f"[ERROR] 결과 레포트 출력 실패: {e}\n")

    def _save_results(self):
        if not self.results:
            messagebox.showinfo("저장할 결과 없음", "아직 저장할 결과가 없습니다.")
            return

        default_name = f"Oracle_Final_Result_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = filedialog.asksaveasfilename(
            title="결과 Excel 저장",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel files", "*.xlsx")],
        )
        if not path:
            return

        try:
            out = core.export_final_results_to_excel(self.results, path)
            self._log(f"[OK] 결과 저장 완료: {out}\n")
            messagebox.showinfo("저장 완료", f"결과를 저장했습니다.\n{out}")
        except Exception as e:
            messagebox.showerror("저장 실패", str(e))
            self._log(f"[ERROR] 결과 저장 실패: {e}\n")

    def _clear_results(self):
        if self.results and not messagebox.askyesno("결과 초기화", "현재 결과 목록을 초기화할까요?"):
            return

        self.results.clear()
        self.current_result = None
        self.tc_result_status_by_index.clear()
        self.result_tree.delete(*self.result_tree.get_children())

        for d in self.display_rows:
            d["pass_overlay"] = False
        self._refresh_tc_tree()

        self.start_button.configure(text="선택 TC Start")
        self.complete_button.configure(state=tk.DISABLED)
        self.abort_button.configure(state=tk.DISABLED)
        self._set_status_box("대기중", "#E5E7EB", "#111827")
        self.status_var.set("대기중")
        self.current_detail.delete("1.0", tk.END)
        self.current_detail.insert("1.0", "결과가 초기화되었습니다.\n")
        self._refresh_all_summary(None, None)
        self._log("[GUI] 결과 초기화\n")

    def _set_status_box(self, text: str, bg: str, fg: str):
        self.current_status_label.configure(text=text, bg=bg, fg=fg)

    def _log(self, text: str):
        if not hasattr(self, "log_text") or self.log_text is None:
            print(text, end="", flush=True)
            return
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)

    def _poll_log_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                kind = item[0]

                if kind == "PROGRESS":
                    _status, result = item[1], item[2]
                    if result is not None:
                        self.status_var.set("검토중")
                        self._set_status_box("검토중", "#FEF3C7", "#92400E")
                        self._show_progress_result(result)
                        self._refresh_summary_with_partial_result(result)

                elif kind == "FINAL_DONE":
                    self._on_final_done(item[1])

                elif kind == "FINAL_ERROR":
                    self.monitor_thread = None
                    self.start_button.configure(state=tk.NORMAL, text="선택 TC Start")
                    self.complete_button.configure(state=tk.DISABLED)
                    self.abort_button.configure(state=tk.DISABLED)
                    self.status_var.set("ERROR")
                    self._set_status_box("ERROR", "#FEE2E2", "#991B1B")
                    self._invalidate_canoe_client("실행 오류 후 다음 Start 안정화를 위해 재연결 예정")
                    self._log(f"[ERROR] 최종 판정 스레드 오류: {item[1]}\n")
                    messagebox.showerror("실행 오류", item[1])

                elif kind == "LOG_PROGRESS":
                    self.status_var.set("로그 확인중")
                    self._set_status_box("로그 확인중", "#DBEAFE", "#1D4ED8")
                    self._log(f"[LOG] {item[1]}\n")

                elif kind == "LOG_TEXT":
                    self._log(item[1])

                elif kind == "REQUIRED_FILES_INSTALL_PROGRESS":
                    self._on_required_files_install_progress(item[1], item[2], item[3], item[4])

                elif kind == "REQUIRED_FILES_INSTALL_DONE":
                    self._on_required_files_install_done(item[1])

                elif kind == "REQUIRED_FILES_INSTALL_ERROR":
                    self._on_required_files_install_error(item[1])

                else:
                    self._log(str(item) + "\n")

        except queue.Empty:
            pass

        self.after(100, self._poll_log_queue)

    def _show_progress_result(self, result):
        c = result.condition
        text = []
        text.append(f"TC 번호: {c.tc_no}")
        text.append(f"소분류: {c.subcategory}")
        text.append(f"TC 내용: {c.tc_content}")
        text.append(f"TC 예상 결과: {c.tc_expected_result}")
        text.append("")

        text.append("[입력 조건]")
        for i, inp in enumerate(c.input_conditions, start=1):
            line = f"  ({i}) {inp.message}:{inp.signal} == {inp.expected_value_raw}"
            if i - 1 < len(result.input_results):
                rr = result.input_results[i - 1]
                line += f" | 실제 결과값: {rr.observed_value_raw} / 상태: {rr.status}"
            text.append(line)

        text.append("")
        text.append("[출력 조건]")
        for i, o in enumerate(c.output_conditions, start=1):
            line = f"  ({i}) {o.message}:{o.signal} == {o.expected_value_raw}"
            if i - 1 < len(result.output_results):
                rr = result.output_results[i - 1]
                line += f" | 실제 결과값: {rr.observed_value_raw} / 상태: {rr.status}"
            text.append(line)

        text.append("")
        text.append("[실시간 진행 상태]")
        text.append(f"Status: {result.status}")
        text.append(f"Message: {result.message}")

        self.current_detail.configure(state="normal")
        self.current_detail.delete("1.0", tk.END)
        self.current_detail.insert("1.0", "\n".join(text))
        self.current_detail.configure(state="normal")


def _detach_console_if_possible():
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass


OracleCheckerOneByOneGui = OracleCheckerGui


def main():
    _detach_console_if_possible()
    app = OracleCheckerGui()

    def _on_close():
        try:
            if hasattr(app, "_save_current_user_settings"):
                app._save_current_user_settings()
            app.destroy()
        finally:
            _cleanup_pycache()

    try:
        app.protocol("WM_DELETE_WINDOW", _on_close)
    except Exception:
        pass

    try:
        app.mainloop()
    finally:
        _cleanup_pycache()


if __name__ == "__main__":
    main()

