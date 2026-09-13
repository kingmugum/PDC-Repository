# -*- coding: utf-8 -*-
"""
oracle_checker_gui_txrx_rev87.py

목적
- Oracle Checker GUI에 "차량 송수신 테스트" 탭(2안: Injection + Oracle)을 추가한다.
- rev87 GUI는 전문가용 수동 옵션을 숨기고, 여러 TC 체크 -> 테스트 실행 준비 -> 순차 Stimulus -> 출력 Signal 자동 관측 -> PASS/FAIL로 단순화한다.
- 상세 진단/CRC/Alive/원 송신원 간섭/Bridge 정보는 GUI 옵션 대신 AI 분석용 자동 로그에 남긴다.
- 실제 write는 계속 독립 Stimulus 모듈에서만 수행하고 기존 단일/다중 P/F observer/judge는 read-only로 유지한다.

기능
- 기존 Excel/DBC 및 CANoe 논리 CAN 설정과 condition_rows를 재사용
- 선택 TC의 입력 조건을 "송신 대상"으로 Preview
- 출력 조건을 "차량 반응 수신/감시 대상"으로 Preview
- DBC 기준 Message/Signal 존재 여부 검사
- CAN1/CAN2/CAN3 채널 매핑 확인
- CRC/Alive/Counter류 Signal 포함 여부를 탐지하여 "확인 필요"로 표시
- 일반 송신/Replay 버튼은 안전상 비활성화 상태로 유지한다.
- rev87: Stimulus 완료 후 최신 BLF/ASC에서 대상 Message의 Tx/Rx 및 Signal 변화, CRC/Alive/Counter 변화를 자동 디버깅 표시한다.
- 실제 입력 PoC는 명시적 Stimulus 활성화 + 확인 팝업을 통과한 제한 경로로만 제공한다.

rev87:
- TC 목록 로드 단계에서 DBC를 1회 로드하고 모든 유효 TC의 입력 송신 대상/출력 감시 대상/자동 진단 요약을 사전 계산
- 사전 계산 cache가 있으면 TX/RX TC 최초 클릭 시 분석 popup 없이 즉시 Preview 표시
- TX/RX TC 목록 선택 개선: 행 전체 클릭으로 체크 toggle, Shift+click은 anchor 상태를 범위 전체에 복제하여 선택/해제
- Windows ttk theme에서 Treeview tag background가 덮이는 문제를 보정하여 체크/PASS/FAIL/N/A 행 음영을 실제 화면에 강제 반영
- checked=옅은 파랑 / PASS=옅은 초록 / FAIL=옅은 빨강 / N/A=옅은 주황, 결과 상태가 체크 상태보다 우선
- rev49 차량 송수신 테스트 탭/실험 관리 기능을 그대로 유지
- 일반 CANoe 송신/Replay 자동화는 계속 비활성
- 실험용 입력 1회 테스트만 oracle_checker_stimulus_rev87.py 독립 모듈을 선택적으로 호출
- Stimulus 모듈 부재/오류가 기존 단일/다중 Pass/Fail 기능에 영향을 주지 않도록 optional import
- 기존 선택-TC 입력은 단일 Signal 1회 PoC로 유지하며 원래 Signal 값으로 반드시 원복
- rev87은 회사 Excel 등에서 복사한 후보 Signal 1~8개를 수동 붙여넣기하여 묶음 1회 테스트하는 기능을 추가
- 수동 후보 묶음은 모든 Signal을 사전검증한 뒤 적용하고, 실제 write된 모든 Signal을 finally에서 원래 값으로 복원
- CRC/Alive/Counter는 자동 계산하지 않으며, DBC에서 감지되면 기본 차단하고 사용자가 경고 허용을 명시한 경우에만 정적 값 시험을 허용
- Vector CANoe/CANalyzer COM 진단 기능은 공통 onebyone/main rev87에서 제공
- TX/RX 탭은 rev87 공통 Notebook X/Y scroll wrapper를 사용하여 가로/세로 전체 스크롤을 지원한다.
- rev60 전용 TX/RX bind_all은 제거하고 공통 active-tab wheel handler를 사용하여 중복 스크롤을 방지한다.
- rev87 compact UI: 자동화 방식 추천/프리테스트 적합성/수동 실험기록 GUI를 제거하고 PASS/FAIL 열 및 multi-select 자동 P/F를 제공한다.
- rev87 ACTIVE Bridge: CANoe Network Node에 *_ACTIVE.can을 최초 1회 연결하면 이후 bridge 내용 생성/덮어쓰기/CAPL Compile/Measurement binding을 자동화한다.
- rev87 DBC 식별 Bridge: 로컬 DBC 파일명에서 ID를 추출해 `PF_Stimulus_Bridge_CANx_<DBC_ID>_ACTIVE.can`을 자동 생성하고 SHA256을 내장한다. 고정 `CANx_ACTIVE.can`은 패키지 밖 `PF_Stimulus_Runtime` 폴더에 두어 버전 변경 후에도 CANoe 최초 1회 연결을 유지한다.
- rev87 TC별 Measurement Log 이름 자동화: 자동 P/F는 TC마다 Measurement를 명시적으로 Stop하여 CANoe Logging 파일을 닫고, 설정 탭 자동 로그 폴더의 새/변경 ASC·BLF를 `시트_005-3_CAN1_B1_CAN2_M_HHMMSS.ext` 형식으로 rename한다.
"""

from __future__ import annotations

import atexit
import csv
import datetime as _dt
import json
import hashlib
import queue
import re
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText

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

import oracle_checker_gui_onebyone_rev87 as _onebyone

core = _onebyone.core

# rev87: 실험용 실제 입력 엔진은 선택 모듈이다.
# import 실패가 전체 GUI/기존 PassFail을 깨지 않도록 반드시 optional로 유지한다.
try:
    import oracle_checker_stimulus_rev87 as _stimulus
    STIMULUS_AVAILABLE = True
    STIMULUS_IMPORT_ERROR = ""
except Exception as _stimulus_import_error:
    _stimulus = None
    STIMULUS_AVAILABLE = False
    STIMULUS_IMPORT_ERROR = f"{type(_stimulus_import_error).__name__}: {_stimulus_import_error}"


class TxRxTestMixin:
    """차량 송수신 테스트 탭/동작을 추가하는 mixin."""

    TXRX_STATUS_UNCHECKED = "미검사"
    TXRX_STATUS_OK = "가능"
    TXRX_STATUS_WARN = "확인 필요"
    TXRX_STATUS_BAD = "불가"

    TXRX_METHOD_CAN = "CAN Signal 송신 후보"
    TXRX_METHOD_REPLAY = "로그 Replay 후보"
    TXRX_METHOD_PHYSICAL = "물리 입력/릴레이 필요"
    TXRX_METHOD_MANUAL = "수동 확인 필요"
    TXRX_METHOD_EXCLUDE = "초기 자동화 제외"
    TXRX_METHOD_UNKNOWN = "미분류"

    def _build_ui(self):
        super()._build_ui()
        self._init_txrx_state()
        self._build_txrx_tab()
        if not self._txrx_async_poll_started:
            self._txrx_async_poll_started = True
            self.after(100, self._poll_txrx_async_queue)

    def _init_txrx_state(self):
        self.txrx_tab = None
        self.txrx_tree = None
        self.txrx_preview_text = None
        self.txrx_status_text = None
        self.txrx_result_tree = None
        self.txrx_log_text = None
        self.txrx_experiment_tree = None
        self.txrx_experiment_memo_text = None
        self.txrx_scroll_canvas = None
        self.txrx_outer_scrollbar = None
        self.txrx_outer_hscrollbar = None
        self.txrx_scroll_content = None
        self.txrx_scroll_window = None
        self.txrx_inner_scroll_widgets = []
        self.txrx_status_var = tk.StringVar(value="대기중")
        self.txrx_selected_tc_var = tk.StringVar(value="선택 TC: -")
        self.txrx_summary_var = tk.StringVar(value="송신 가능성: 미검사")
        self.txrx_tx_enable_var = tk.BooleanVar(value=False)
        self.txrx_tx_mode_var = tk.StringVar(value="주기 송신")
        self.txrx_period_ms_var = tk.StringVar(value="100")
        self.txrx_duration_mode_var = tk.StringVar(value="수행 완료/중단까지")
        self.txrx_duration_sec_var = tk.StringVar(value="3.0")
        self.txrx_confirm_before_send_var = tk.BooleanVar(value=True)
        self.txrx_auto_stop_var = tk.BooleanVar(value=True)
        self.txrx_wait_sec_var = tk.StringVar(value="30")
        self.txrx_between_tc_delay_var = tk.StringVar(value="1.0")
        self.txrx_fail_policy_var = tk.StringVar(value="Fail 후 다음 TC 진행")
        # rev87: 실제 자동화 가능성을 한땀한땀 검증하기 위한 실험 기록 상태
        self.txrx_experiment_method_var = tk.StringVar(value="수동 기록")
        self.txrx_vehicle_reaction_var = tk.StringVar(value="미확인")
        self.txrx_output_judge_var = tk.StringVar(value="미확인")
        self.txrx_experiment_result_var = tk.StringVar(value="분석필요")
        self.txrx_cause_vars: Dict[str, tk.BooleanVar] = {
            "입력 Signal 부족 의심": tk.BooleanVar(value=False),
            "CRC/Alive 의심": tk.BooleanVar(value=False),
            "사전조건 부족 의심": tk.BooleanVar(value=False),
            "채널/DBC 매핑 의심": tk.BooleanVar(value=False),
            "실제 ECU 중복 송신 의심": tk.BooleanVar(value=False),
            "물리 버튼/릴레이 필요 의심": tk.BooleanVar(value=False),
            "출력 조건 재검토 필요": tk.BooleanVar(value=False),
        }
        self.txrx_experiment_records: List[Dict[str, Any]] = []
        self.txrx_selected_index: Optional[int] = None
        self.txrx_analysis_by_index: Dict[int, Dict[str, Any]] = {}
        # rev87 isolated experimental stimulus state
        self.txrx_stimulus_enable_var = tk.BooleanVar(value=False)
        self.txrx_stimulus_hold_sec_var = tk.StringVar(value="2.2")
        self.txrx_stimulus_status_var = tk.StringVar(
            value="Stimulus: 사용 가능" if STIMULUS_AVAILABLE else "Stimulus: 모듈 없음(기존 P/F 영향 없음)"
        )
        self.txrx_stimulus_stop_event = threading.Event()
        self.txrx_stimulus_thread: Optional[threading.Thread] = None
        # rev87: 현장 Excel에서 후보 Signal을 그대로 복사/붙여넣기하여 시험하기 위한 상태
        self.txrx_manual_candidate_text = None
        self.txrx_manual_candidate_status_var = tk.StringVar(value="수동 후보: 미검증")
        self.txrx_manual_crc_override_var = tk.BooleanVar(value=False)
        # rev87 CAPL frame backend safety gate: actual injection only after user confirms original sender is isolated/disabled.
        self.txrx_canalyzer_source_isolated_var = tk.BooleanVar(value=False)
        # rev87: CANoe direct Signal.Value requires an Interaction Layer signal driver.
        # Actual reverse-send tests default to CAPL frame output so a missing signal driver does not create a false success.
        self.txrx_canoe_backend_var = tk.StringVar(value="CAPL Frame (권장)")
        self.txrx_stop_measurement_after_stimulus_var = tk.BooleanVar(value=True)
        self.txrx_autofill_manual_from_selection_var = tk.BooleanVar(value=True)
        # rev87: 하나의 Message/Signal이 CAN1~CAN3 여러 DBC에 존재할 수 있으므로
        # 복수 논리 CAN은 오류가 아니라 OR 후보군으로 유지하고 실제 송신 시 1개를 선택한다.
        self.txrx_selected_can_candidate_var = tk.StringVar(value="")
        self.txrx_selected_can_candidate_values: List[str] = []
        self.txrx_selected_can_candidate_status_var = tk.StringVar(value="송신 CAN 후보: TC 선택 필요")
        self.txrx_selected_can_combobox = None
        # rev87: DBC 분석 캐시 / 비동기 전체검사 / 수동 후보 검증 캐시
        self.txrx_dbc_cache_signature = None
        self.txrx_dbc_cache_by_ch: Dict[int, Any] = {}
        self.txrx_all_check_thread: Optional[threading.Thread] = None
        self.txrx_check_all_button = None
        self.txrx_manual_validation_cache: Optional[Dict[str, Any]] = None
        # rev87: Stimulus 실행 뒤 최신 BLF/ASC에서 실제 Message/Signal 변화가 기록됐는지 자동 확인한다.
        # 이 기능은 디버깅/증적 표시 전용이며 차량 기능 PASS/FAIL 판정에는 사용하지 않는다.
        self.txrx_log_verify_enabled_var = tk.BooleanVar(value=True)
        self.txrx_log_verify_status_var = tk.StringVar(value="로그 검증: 대기")
        self.txrx_log_verify_text = None
        self.txrx_log_verify_thread: Optional[threading.Thread] = None
        self.txrx_last_stimulus_result = None
        self.txrx_async_queue: queue.Queue = queue.Queue()
        self._txrx_async_poll_started = False

        # rev87 simplified 2안: multi-select Injection + Oracle auto P/F
        self.txrx_test_ready_var = tk.BooleanVar(value=False)
        self.txrx_auto_selected_indices = set()
        self.txrx_auto_anchor_index: Optional[int] = None
        self.txrx_auto_result_by_index: Dict[int, str] = {}
        self.txrx_auto_detail_by_index: Dict[int, Dict[str, Any]] = {}
        # rev87: per-TC live/final observed Signal values shown in the second row of the TX/RX tree.
        self.txrx_live_observation_by_index: Dict[int, Dict[str, Any]] = {}
        self.txrx_auto_progress_var = tk.DoubleVar(value=0.0)
        self.txrx_auto_progress_text_var = tk.StringVar(value="진행도: 대기")
        self.txrx_auto_selected_count_var = tk.StringVar(value="선택 TC: 0개")
        # rev87: 자동 Stimulus가 허용되는 물리 작동 TC(예: 시트)는 BLOCK 대신 동적 안전 경고를 표시한다.
        self.txrx_safety_warning_var = tk.StringVar(value="안전 경고 대상 TC가 선택되면 이곳에 표시됩니다.")
        self.txrx_auto_run_button = None
        self.txrx_auto_stop_button = None
        self.txrx_auto_progress_bar = None
        self.txrx_auto_thread: Optional[threading.Thread] = None
        self.txrx_auto_stop_event = threading.Event()
        self.txrx_session_log_path = ""
        self.txrx_selection_load_after_id = None
        self.txrx_selection_popup_after_id = None

    def _build_txrx_tab(self):
        """rev87 compact 2안 UI.

        사람이 해석해야 하는 저수준 옵션은 화면에서 제거하고 자동 로그로 남긴다.
        상단은 multi-select + PASS/FAIL + 실제 관측 2행 표시, 하단은 실행 준비 + 자동 P/F + 진행률 + AI 분석 로그만 유지한다.
        """
        if self.notebook is None:
            return

        self.txrx_tab, self.txrx_scroll_content = self._create_scrollable_notebook_tab(
            "차량 송수신 테스트", padding=6
        )
        _scroll_info = self._tab_scroll_registry.get(str(self.txrx_tab), {})
        self.txrx_scroll_canvas = _scroll_info.get("canvas")
        self.txrx_outer_scrollbar = _scroll_info.get("vbar")
        self.txrx_outer_hscrollbar = _scroll_info.get("hbar")
        self.txrx_scroll_window = _scroll_info.get("window")

        parent = self.txrx_scroll_content
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=0)
        parent.rowconfigure(2, weight=1)

        # -----------------------------
        # 1) TC multi-select + auto PASS/FAIL
        # -----------------------------
        list_frame = ttk.LabelFrame(parent, text="TC 목록 / 자동 차량 P/F")
        list_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        columns = ("check", "tc_no", "subcategory", "input", "output", "pf", "reason")

        # rev87: Windows ttk(Treeview) 일부 theme는 정상/비선택 상태의 style map이
        # item tag background를 덮어써서 checked/PASS/FAIL/N/A 음영이 보이지 않을 수 있다.
        # Treeview 기본 map에서 해당 강제 normal-state 항목만 제거한 전용 style을 사용한다.
        txrx_style = ttk.Style(self)

        def _txrx_fixed_tree_map(option: str):
            try:
                return [
                    item for item in txrx_style.map("Treeview", query_opt=option)
                    if tuple(item[:2]) != ("!disabled", "!selected")
                ]
            except Exception:
                return []

        txrx_style.configure(
            "TxRx.Treeview",
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
            foreground="#111827",
        )
        fixed_bg = _txrx_fixed_tree_map("background")
        fixed_fg = _txrx_fixed_tree_map("foreground")
        if fixed_bg:
            txrx_style.map("TxRx.Treeview", background=fixed_bg)
        else:
            txrx_style.map("TxRx.Treeview", background=[])
        if fixed_fg:
            txrx_style.map("TxRx.Treeview", foreground=fixed_fg)
        else:
            txrx_style.map("TxRx.Treeview", foreground=[])

        self.txrx_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            selectmode="none",
            # rev87: expected/actual 2행 구조 기준으로 약 10개 TC(20행)가 한 화면에 보이도록 축소.
            height=20,
            style="TxRx.Treeview",
            takefocus=False,
        )
        heads = {
            "check": "선택", "tc_no": "TC 번호", "subcategory": "소분류",
            "input": "입력 송신 대상", "output": "출력 감시 대상",
            "pf": "PASS/FAIL", "reason": "원인 분석",
        }
        widths = {
            "check": 55, "tc_no": 90, "subcategory": 170,
            "input": 360, "output": 360, "pf": 82, "reason": 360,
        }
        centers = {"check", "tc_no", "pf"}
        for c in columns:
            self.txrx_tree.heading(c, text=heads[c])
            self.txrx_tree.column(c, width=widths[c], anchor="center" if c in centers else "w", stretch=False)

        self.txrx_tree.tag_configure("idle", background="#FFFFFF", foreground="#111827")
        self.txrx_tree.tag_configure("checked", background="#D6EAFE", foreground="#0F3B66")
        self.txrx_tree.tag_configure("pass", background="#D9F7DF", foreground="#166534", font=("맑은 고딕", 9, "bold"))
        self.txrx_tree.tag_configure("fail", background="#FADDDD", foreground="#991B1B", font=("맑은 고딕", 9, "bold"))
        self.txrx_tree.tag_configure("na", background="#FFE7C2", foreground="#9A3412", font=("맑은 고딕", 9, "bold"))
        self.txrx_tree.tag_configure("error", background="#FADDDD", foreground="#991B1B", font=("맑은 고딕", 9, "bold"))
        self.txrx_tree.tag_configure("block", background="#E5E7EB", foreground="#4B5563", font=("맑은 고딕", 9, "bold"))
        self.txrx_tree.tag_configure("selected", background="#E0F2FE", foreground="#0F172A")
        self.txrx_tree.tag_configure("actual", background="#F8FAFC", foreground="#475569", font=("맑은 고딕", 9))
        yscroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.txrx_tree.yview)
        xscroll = ttk.Scrollbar(list_frame, orient="horizontal", command=self.txrx_tree.xview)
        self.txrx_tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.txrx_tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.txrx_tree.bind("<Button-1>", self._on_txrx_tree_click, add="+")

        # -----------------------------
        # 2) Full-width compact execution control + one-line safety warning
        # rev87: the old selected-TC Preview box is removed. The TC list itself now carries
        # expected values (first row) and live/final observed values (second row).
        # -----------------------------
        middle = ttk.Frame(parent)
        middle.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        middle.columnconfigure(0, weight=1)

        control = ttk.LabelFrame(middle, text="테스트 실행")
        control.grid(row=0, column=0, sticky="ew")
        control.columnconfigure(0, weight=1)

        row0 = ttk.Frame(control)
        row0.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 3))
        ttk.Button(row0, text="TC 목록 새로고침", command=self._txrx_refresh_compact_list).pack(side=tk.LEFT)
        ttk.Button(row0, text="전체 선택", command=self._txrx_auto_select_all).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(row0, text="선택 해제", command=self._txrx_auto_clear_selection).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(
            row0, text="Runtime Bridge 사전 생성/갱신",
            command=self._txrx_prepare_runtime_bridges_without_run,
        ).pack(side=tk.LEFT, padx=(10, 0))

        ready_text = (
            "테스트 실행 준비  (후보검증 + 실험 Stimulus + CRC/Alive 경고 인지 + "
            "CAPL 실제 Frame 송신 인지)"
        )
        ttk.Checkbutton(
            control, text=ready_text, variable=self.txrx_test_ready_var,
            command=self._on_txrx_test_ready_changed,
        ).grid(row=1, column=0, sticky="w", padx=6, pady=(3, 2))

        runrow = ttk.Frame(control)
        runrow.grid(row=2, column=0, sticky="ew", padx=6, pady=(1, 3))
        ttk.Label(runrow, text="Stimulus Hold(sec)").pack(side=tk.LEFT)
        ttk.Entry(runrow, textvariable=self.txrx_stimulus_hold_sec_var, width=8).pack(side=tk.LEFT, padx=(6, 12))
        ttk.Label(runrow, textvariable=self.txrx_auto_selected_count_var).pack(side=tk.LEFT, padx=(0, 12))
        self.txrx_auto_run_button = tk.Button(
            runrow, text="선택 TC 자동 P/F 실행", command=self._txrx_auto_run_selected,
            bg="#30D862", activebackground="#28B854", fg="black", relief="raised", bd=2,
            font=("맑은 고딕", 11, "bold"), state=tk.DISABLED, cursor="hand2", width=20,
        )
        self.txrx_auto_run_button.pack(side=tk.LEFT)
        self.txrx_auto_stop_button = tk.Button(
            runrow, text="중단/원복", command=self._txrx_stop_auto_pf,
            bg="#EF4444", activebackground="#DC2626", fg="white", activeforeground="white",
            font=("맑은 고딕", 9, "bold"), state=tk.DISABLED, width=10,
        )
        self.txrx_auto_stop_button.pack(side=tk.LEFT, padx=(6, 0))

        style = ttk.Style(self)
        style.configure("PassFail.Green.Horizontal.TProgressbar", troughcolor="#E5E7EB", background="#22C55E")
        progress_row = ttk.Frame(control)
        progress_row.grid(row=3, column=0, sticky="ew", padx=6, pady=(2, 5))
        progress_row.columnconfigure(1, weight=1)
        ttk.Label(progress_row, textvariable=self.txrx_auto_progress_text_var, width=38).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.txrx_auto_progress_bar = ttk.Progressbar(
            progress_row, variable=self.txrx_auto_progress_var, maximum=100.0, mode="determinate",
            style="PassFail.Green.Horizontal.TProgressbar",
        )
        self.txrx_auto_progress_bar.grid(row=0, column=1, sticky="ew")

        ttk.Label(
            control,
            text=(
                "※ 2안 Injection / 원 차량 송신원은 살아 있을 수 있음 / 모든 입력은 DBC cycle의 1/10(최소 10ms) 반복 / "
                "CRC·Alive·E2E 자동계산 없음 / CAPL Bridge는 최초 1회 Network Node 연결 후 재사용"
            ),
            foreground="#92400E", wraplength=1250, justify="left",
        ).grid(row=4, column=0, sticky="w", padx=6, pady=(0, 5))

        # Safety warning is deliberately outside the execution box and rendered as one concise line.
        self.txrx_safety_warning_label = tk.Label(
            middle, textvariable=self.txrx_safety_warning_var,
            fg="#B91C1C", bg="#FFF7F7", font=("맑은 고딕", 10, "bold"),
            justify="left", anchor="w", padx=8, pady=4,
        )
        self.txrx_safety_warning_label.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        # legacy helpers use a Text widget internally for candidate parsing/autofill. Keep it hidden so
        # the backend remains regression-compatible without exposing manual expert controls in the GUI.
        self.txrx_manual_candidate_text = tk.Text(parent, width=1, height=1)
        self.txrx_manual_candidate_text.grid_remove()
        self.txrx_stimulus_enable_var.set(True)
        self.txrx_manual_crc_override_var.set(True)
        self.txrx_canoe_backend_var.set("CAPL Frame (권장)")

        # -----------------------------
        # 3) Always-on AI diagnosis log
        # -----------------------------
        logf = ttk.LabelFrame(parent, text="실행 로그 / AI 분석용 (자동 저장)")
        logf.grid(row=2, column=0, sticky="nsew")
        logf.columnconfigure(0, weight=1)
        logf.rowconfigure(0, weight=1)
        self.txrx_log_text = ScrolledText(logf, height=14, wrap=tk.WORD)
        self.txrx_log_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self._txrx_begin_session_log()
        self._refresh_txrx_tree()

    def _txrx_widget_is_descendant(self, widget, ancestor) -> bool:
        current = widget
        while current is not None:
            if current is ancestor:
                return True
            current = getattr(current, "master", None)
        return False

    def _txrx_tab_is_active(self) -> bool:
        try:
            return self.notebook is not None and self.txrx_tab is not None and self.notebook.select() == str(self.txrx_tab)
        except Exception:
            return False

    def _txrx_mousewheel_units(self, event) -> int:
        # Windows/macOS: <MouseWheel> delta. X11/Linux: Button-4/5.
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

    def _scroll_txrx_outer(self, units: int):
        if units == 0 or self.txrx_scroll_canvas is None:
            return
        try:
            self.txrx_scroll_canvas.yview_scroll(int(units), "units")
        except Exception:
            pass

    def _on_txrx_inner_mousewheel(self, event, widget=None):
        if not self._txrx_tab_is_active():
            return None
        target = widget or getattr(event, "widget", None)
        units = self._txrx_mousewheel_units(event)
        if target is None or units == 0:
            return "break"

        # yview()=(first,last). 해당 방향으로 내부에 더 볼 내용이 있으면 내부를 우선한다.
        try:
            first, last = target.yview()
            direction_down = units > 0
            can_scroll_inner = (last < 0.999999) if direction_down else (first > 0.000001)
        except Exception:
            can_scroll_inner = False

        if can_scroll_inner:
            try:
                target.yview_scroll(units, "units")
            except Exception:
                pass
        else:
            self._scroll_txrx_outer(units)
        return "break"

    def _on_txrx_outer_mousewheel(self, event):
        if not self._txrx_tab_is_active() or self.txrx_tab is None:
            return None
        widget = getattr(event, "widget", None)
        if widget is None or not self._txrx_widget_is_descendant(widget, self.txrx_tab):
            return None
        units = self._txrx_mousewheel_units(event)
        if units == 0:
            return None
        self._scroll_txrx_outer(units)
        return "break"

    def _bind_txrx_mousewheel(self):
        """rev87: 공통 Notebook wheel handler가 모든 탭을 담당한다.

        기존 rev60 전용 bind_all을 중복 등록하면 TX/RX에서 outer가 두 번 움직일 수 있으므로
        이 호환 메서드는 의도적으로 별도 binding을 추가하지 않는다.
        """
        return

    def _poll_txrx_async_queue(self):
        try:
            while True:
                item = self.txrx_async_queue.get_nowait()
                kind = item[0]
                if kind == "ALL_CHECK_DONE":
                    self._finish_txrx_all_check(*item[1:])
                elif kind == "ALL_CHECK_ERROR":
                    self._finish_txrx_all_check_error(item[1])
                elif kind == "MANUAL_DONE":
                    self._finish_txrx_manual_stimulus(item[1])
                elif kind == "MANUAL_ERROR":
                    self._finish_txrx_manual_stimulus_error(item[1])
                elif kind == "SINGLE_DONE":
                    self._finish_txrx_stimulus(item[1])
                elif kind == "SINGLE_ERROR":
                    self._finish_txrx_stimulus_worker_error(item[1])
                elif kind == "LOG_VERIFY_DONE":
                    self._finish_txrx_stimulus_log_verification(item[1])
                elif kind == "LOG_VERIFY_ERROR":
                    self._finish_txrx_stimulus_log_verification_error(item[1])
                elif kind == "AUTO_LOG":
                    self._txrx_log(str(item[1]))
                elif kind == "AUTO_PROGRESS":
                    self._set_txrx_auto_progress(item[1], str(item[2]))
                elif kind == "AUTO_LIVE":
                    self._finish_txrx_live_observation(item[1], item[2])
                elif kind == "AUTO_RESULT":
                    self._finish_txrx_auto_one_result(item[1], item[2], item[3])
                elif kind == "AUTO_DONE":
                    self._finish_txrx_auto_run(item[1])
                elif kind == "AUTO_ERROR":
                    self._finish_txrx_auto_error(str(item[1]))
        except queue.Empty:
            pass
        try:
            self.after(100, self._poll_txrx_async_queue)
        except Exception:
            pass

    # -------------------------------------------------
    # rev87: TC 목록 로드와 함께 TX/RX DBC/입출력 위치 사전 계산
    # -------------------------------------------------
    def _prepare_txrx_preload_context(self):
        """Tk 변수 접근은 main thread에서 끝내고 worker에는 plain dict만 넘긴다."""
        mapping = self._collect_dbc_mapping()
        return {
            "mapping": dict(mapping or {}),
            "signature": self._txrx_dbc_mapping_signature(mapping or {}),
        }

    def _precompute_txrx_for_loaded_rows(self, rows, context=None, progress_callback=None):
        """TC load worker에서 DBC를 1회 로드하고 모든 유효 TC의 입력/출력/summary를 선계산한다."""
        context = context or {}
        mapping = dict(context.get("mapping") or {})
        signature = context.get("signature") or self._txrx_dbc_mapping_signature(mapping)
        db_by_ch = core.load_dbc_map(mapping) if mapping else {}

        targets = [
            (idx, row.condition)
            for idx, row in enumerate(list(rows or []))
            if getattr(row, "is_valid", False) and getattr(row, "condition", None) is not None
        ]
        results: Dict[int, Dict[str, Any]] = {}
        counts = {"ok": 0, "warn": 0, "bad": 0}
        total = len(targets)
        if progress_callback is not None:
            progress_callback(0, total or 1, "입력/출력 DBC 위치 사전 분석")

        for pos, (idx, cond) in enumerate(targets, start=1):
            analysis = self._analyze_condition_txrx(cond, db_by_ch=db_by_ch, dbc_mapping=mapping)
            results[idx] = analysis
            status = analysis.get("status")
            if status == self.TXRX_STATUS_OK:
                counts["ok"] += 1
            elif status == self.TXRX_STATUS_WARN:
                counts["warn"] += 1
            elif status == self.TXRX_STATUS_BAD:
                counts["bad"] += 1
            if progress_callback is not None and (pos == 1 or pos % 10 == 0 or pos == total):
                progress_callback(pos, total or 1, "입력/출력 DBC 위치 사전 분석")

        return {
            "results": results,
            "counts": counts,
            "db_by_ch": db_by_ch,
            "signature": signature,
            "mapping": mapping,
            "total": total,
        }

    def _apply_txrx_preload_results(self, payload):
        payload = payload or {}
        if payload.get("error"):
            self.txrx_status_var.set("TC 로드 완료 / 차량 송수신 사전 분석 경고")
            self._txrx_log(f"[TXRX][PRELOAD][WARN] {payload.get('error')}\n")
            self._refresh_txrx_tree()
            return

        self.txrx_analysis_by_index.update(payload.get("results") or {})
        self.txrx_dbc_cache_signature = payload.get("signature") or ()
        self.txrx_dbc_cache_by_ch = payload.get("db_by_ch") or {}
        counts = payload.get("counts") or {}
        total = int(payload.get("total") or 0)
        ok = int(counts.get("ok") or 0)
        warn = int(counts.get("warn") or 0)
        bad = int(counts.get("bad") or 0)
        self.txrx_status_var.set(f"사전 분석 완료: 전체 {total} / 가능 {ok} / 확인 필요 {warn} / 불가 {bad}")
        self._set_txrx_auto_progress(0, "TC 목록 로드 + 차량 송수신 사전 분석 완료 / 대기")
        self._refresh_txrx_tree()
        self._txrx_log(
            f"[TXRX][PRELOAD] TC 목록 로드 시 사전 분석 완료: total={total}, ok={ok}, warn={warn}, bad={bad}, "
            f"DBC load={'1회' if payload.get('mapping') else '0회(DBC 설정 없음)'}\n"
        )

    def _after_conditions_loaded(self):
        super()._after_conditions_loaded()
        self.txrx_selected_index = None
        self.txrx_auto_anchor_index = None
        self.txrx_analysis_by_index.clear()
        self.txrx_live_observation_by_index.clear()
        self.txrx_manual_validation_cache = None
        self.txrx_auto_selected_indices.clear()
        self.txrx_auto_result_by_index.clear()
        self.txrx_auto_detail_by_index.clear()
        self.txrx_test_ready_var.set(False)
        self._set_txrx_auto_progress(0, "TC 목록 로드 완료 / 대기")
        self._refresh_txrx_tree()
        self._show_txrx_preview(None)
        self._update_txrx_auto_run_state()

    def _short_expectations_text(self, expectations: List[Any], max_items: int = 2) -> str:
        items = []
        for exp in expectations or []:
            items.append(f"{exp.message}:{exp.signal}={exp.expected_value_raw}")
        if len(items) > max_items:
            return " / ".join(items[:max_items]) + f" / ... +{len(items) - max_items}"
        return " / ".join(items) if items else "-"

    def _latest_txrx_experiment_record(self, idx: int) -> Optional[Dict[str, Any]]:
        for record in reversed(self.txrx_experiment_records):
            if record.get("row_index") == idx:
                return record
        return None

    def _latest_txrx_experiment_result_text(self, idx: int) -> str:
        record = self._latest_txrx_experiment_record(idx)
        if not record:
            return "-"
        return str(record.get("final_result") or "-")

    @staticmethod
    def _txrx_format_observed_value(value: Any, expected_raw: Any = None) -> str:
        if value is None:
            return "미감지"
        exp = str(expected_raw or "").strip()
        try:
            numeric = float(value)
            if exp.lower().startswith("0x") and numeric.is_integer():
                width = max(2, len(exp[2:]))
                return f"0x{int(numeric):0{width}X}"
            if numeric.is_integer():
                return str(int(numeric))
            return f"{numeric:g}"
        except Exception:
            return str(value)

    def _txrx_cause_analysis_text(self, idx: int, pf: str) -> str:
        pf = str(pf or "-")
        detail = self.txrx_auto_detail_by_index.get(idx, {}) or {}
        raw = str(detail.get("cause") or detail.get("summary") or "")
        low = raw.lower()
        if pf == "PASS" or pf in ("-", "실행중"):
            return "-"
        if pf == "FAIL":
            return "목표 Signal 값 미 관측"
        if pf == "N/A":
            return "Signal 값 미 감지"
        if pf == "BLOCK":
            if "dbc" in low and ("찾지 못" in raw or "위치" in raw or "미설정" in raw or "매핑" in raw):
                return "해당 Signal이 DBC에 미 존재/매핑 불가"
            if "입력 조건 1개" in raw or "입력=" in raw:
                return "복합 입력 TC 자동 수행 미지원"
            if "출력 조건" in raw:
                return "출력 PASS 조건 미정의"
            if "안전핵심" in raw or "제동" in raw or "조향" in raw or "에어백" in raw or "고전압" in raw or "adas" in low:
                return "안전핵심 TC 자동 Stimulus 차단"
            if "정합성" in raw or "bridge" in low:
                return "DBC-Bridge 정합성/연결 확인 필요"
            return raw or "자동 수행 준비 조건 미충족"
        if pf == "ERROR":
            return raw or "실행/통신 오류"
        return raw or "-"

    def _txrx_expected_row_values_and_tag(self, idx: int):
        row = self.condition_rows[idx]
        c = row.condition
        check = "☑" if idx in self.txrx_auto_selected_indices else "☐"
        pf = self.txrx_auto_result_by_index.get(idx, "-")
        pf_display = "N/A(미 감지)" if pf == "N/A" else pf
        reason = self._txrx_cause_analysis_text(idx, pf)
        if pf == "PASS":
            tag = "pass"
        elif pf == "FAIL":
            tag = "fail"
        elif pf == "N/A":
            tag = "na"
        elif pf == "BLOCK":
            tag = "block"
        elif pf == "ERROR":
            tag = "error"
        elif idx in self.txrx_auto_selected_indices:
            tag = "checked"
        elif idx == self.txrx_selected_index:
            tag = "selected"
        else:
            tag = "idle"
        values = (
            check, c.tc_no, c.subcategory,
            self._short_expectations_text(c.input_conditions, max_items=2),
            self._short_expectations_text(c.output_conditions, max_items=2),
            pf_display, reason,
        )
        return values, tag

    def _txrx_actual_row_values(self, idx: int):
        row = self.condition_rows[idx]
        c = row.condition
        obs = self.txrx_live_observation_by_index.get(idx, {}) or {}
        inp = list(c.input_conditions or [])
        outs = list(c.output_conditions or [])
        in_values = obs.get("input_values") or {}
        out_values = obs.get("output_values") or {}
        input_texts = []
        for exp in inp[:2]:
            key = (str(exp.message), str(exp.signal))
            actual = self._txrx_format_observed_value(in_values.get(key), exp.expected_value_raw)
            input_texts.append(f"{exp.message}:{exp.signal}={actual}")
        output_texts = []
        for exp in outs[:2]:
            key = (str(exp.message), str(exp.signal))
            actual = self._txrx_format_observed_value(out_values.get(key), exp.expected_value_raw)
            output_texts.append(f"{exp.message}:{exp.signal}=={actual}")
        if len(inp) > 2:
            input_texts.append(f"... +{len(inp)-2}")
        if len(outs) > 2:
            output_texts.append(f"... +{len(outs)-2}")
        has_obs = bool(obs)
        return (
            "", "", "실제 관측값" if has_obs else "",
            " / ".join(input_texts) if has_obs else "-",
            " / ".join(output_texts) if has_obs else "-",
            "", "",
        )

    def _refresh_txrx_tree(self):
        if self.txrx_tree is None:
            return
        self.txrx_tree.delete(*self.txrx_tree.get_children())
        for idx, row in enumerate(getattr(self, "condition_rows", [])):
            if not row.is_valid or row.condition is None:
                continue
            values, tag = self._txrx_expected_row_values_and_tag(idx)
            self.txrx_tree.insert("", tk.END, iid=str(idx), tags=(tag,), values=values)
            self.txrx_tree.insert("", tk.END, iid=f"actual:{idx}", tags=("actual",), values=self._txrx_actual_row_values(idx))
        self.txrx_auto_selected_count_var.set(f"선택 TC: {len(self.txrx_auto_selected_indices)}개")
        self._update_txrx_safety_warning()
        self._update_txrx_auto_run_state()

    def _update_txrx_tree_row(self, idx: int):
        if self.txrx_tree is None or not self.txrx_tree.exists(str(idx)):
            return
        try:
            values, tag = self._txrx_expected_row_values_and_tag(idx)
            self.txrx_tree.item(str(idx), values=values, tags=(tag,))
            actual_iid = f"actual:{idx}"
            if self.txrx_tree.exists(actual_iid):
                self.txrx_tree.item(actual_iid, values=self._txrx_actual_row_values(idx), tags=("actual",))
            # rev87: native selection/theme state가 tag 색을 덮지 않도록 제거하고 즉시 redraw.
            try:
                selected = self.txrx_tree.selection()
                if selected:
                    self.txrx_tree.selection_remove(*selected)
                self.txrx_tree.focus("")
                self.txrx_tree.update_idletasks()
            except Exception:
                pass
        except Exception:
            pass
        self.txrx_auto_selected_count_var.set(f"선택 TC: {len(self.txrx_auto_selected_indices)}개")
        self._update_txrx_safety_warning()
        self._update_txrx_auto_run_state()

    def _on_txrx_tree_select(self, event=None):
        # browse selection is intentionally disabled in rev87 compact tree; Button-1 is authoritative.
        return None

    def _txrx_visible_range_indices(self, anchor_idx: int, target_idx: int) -> List[int]:
        """Treeview에 실제 보이는 행 기준으로 anchor~target 연속 범위를 반환한다."""
        if self.txrx_tree is None:
            return []
        try:
            visible = [int(iid) for iid in self.txrx_tree.get_children("") if str(iid).isdigit()]
            a = visible.index(int(anchor_idx))
            b = visible.index(int(target_idx))
        except Exception:
            return []
        lo, hi = sorted((a, b))
        return visible[lo:hi + 1]

    @staticmethod
    def _txrx_shift_pressed(event) -> bool:
        try:
            return bool(int(getattr(event, "state", 0) or 0) & 0x0001)
        except Exception:
            return False

    def _on_txrx_tree_click(self, event=None):
        if self.txrx_tree is None or event is None:
            return
        row_id = self.txrx_tree.identify_row(getattr(event, "y", 0))
        if not row_id:
            return
        actual_row = str(row_id).startswith("actual:")
        try:
            idx = int(str(row_id).split(":", 1)[1]) if actual_row else int(row_id)
        except Exception:
            return
        shift = self._txrx_shift_pressed(event)

        # rev87: 기준행의 체크박스/TC번호/소분류/입력/출력/결과 영역뿐 아니라
        # 바로 아래 실제 관측행을 클릭해도 해당 TC의 체크 상태를 토글한다.
        # 즉 Treeview의 '행 클릭' 자체가 체크박스 클릭과 동일한 선택 동작이다.
        if shift and self.txrx_auto_anchor_index is not None:
            range_indices = self._txrx_visible_range_indices(self.txrx_auto_anchor_index, idx)
            if range_indices:
                # rev87: Shift 범위 동작은 anchor의 현재 체크 상태를 범위 전체에 복제한다.
                # 예) 1~5 체크 상태에서 2를 일반 클릭해 해제(anchor=False)한 뒤
                #     Shift+4 클릭 -> 2~4 전체 해제. 반대로 anchor=True이면 전체 선택.
                range_should_be_checked = self.txrx_auto_anchor_index in self.txrx_auto_selected_indices
                if range_should_be_checked:
                    self.txrx_auto_selected_indices.update(range_indices)
                    action = "선택"
                else:
                    self.txrx_auto_selected_indices.difference_update(range_indices)
                    action = "해제"
                self.txrx_test_ready_var.set(False)
                self.txrx_selected_index = idx
                self._refresh_txrx_tree()
                self._show_txrx_selection_loading(idx)
                self._txrx_log(
                    f"[TXRX][SELECT] Shift 범위 {action}: anchor={self.txrx_auto_anchor_index}, "
                    f"target={idx}, range={len(range_indices)}, total_selected={len(self.txrx_auto_selected_indices)}\n"
                )
                return "break"

        # rev87: 일반 클릭은 열 위치와 무관하게 해당 TC의 체크를 즉시 toggle하고
        # 그 결과 상태를 다음 Shift 범위 동작의 anchor 상태로 사용한다.
        old_idx = self.txrx_selected_index
        if idx in self.txrx_auto_selected_indices:
            self.txrx_auto_selected_indices.discard(idx)
            toggled_checked = False
        else:
            self.txrx_auto_selected_indices.add(idx)
            toggled_checked = True
        self.txrx_selected_index = idx
        self.txrx_auto_anchor_index = idx
        self.txrx_test_ready_var.set(False)
        if old_idx is not None and old_idx != idx:
            self._update_txrx_tree_row(old_idx)
        self._update_txrx_tree_row(idx)
        self._show_txrx_selection_loading(idx)
        self._txrx_log(
            f"[TXRX][SELECT] TC {idx} {'선택' if toggled_checked else '해제'} (행 클릭 toggle)\n"
        )
        return "break"

    # -------------------------------------------------
    # rev87 compact 2안 selection / auto P/F helpers
    # -------------------------------------------------
    def _show_txrx_selection_loading(self, idx: int):
        # rev87: TC 목록 로드 시 이미 분석된 행은 팝업 없이 즉시 Preview/자동 진단 요약을 사용한다.
        if idx in self.txrx_analysis_by_index:
            try:
                self._show_txrx_preview(idx)
                self._update_txrx_tree_row(idx)
            except Exception as e:
                self._txrx_log(f"[TXRX][SELECT][CACHE-ERROR] idx={idx}: {type(e).__name__}: {e}\n")
            return

        # DBC 설정이 로드 이후 변경됐거나 사전분석이 실패한 경우에만 기존 fallback popup을 사용한다.
        self._show_operation_progress("TC 상세 준비", "사전 분석 캐시 없음 / 선택 TC 분석 준비", 10)
        def _work():
            try:
                if not (0 <= idx < len(self.condition_rows)):
                    return
                row = self.condition_rows[idx]
                if row.is_valid and row.condition is not None and idx not in self.txrx_analysis_by_index:
                    self._show_operation_progress("TC 상세 준비", "DBC/입출력 위치 분석", 55)
                    self.txrx_analysis_by_index[idx] = self._analyze_condition_txrx(row.condition)
                self._show_operation_progress("TC 상세 준비", "Preview 구성", 85)
                self._show_txrx_preview(idx)
                self._update_txrx_tree_row(idx)
                self._show_operation_progress("TC 상세 준비", "완료", 100)
                self._close_operation_progress(100)
            except Exception as e:
                self._close_operation_progress(0)
                self._txrx_log(f"[TXRX][SELECT][ERROR] idx={idx}: {type(e).__name__}: {e}\n")
        self.after(25, _work)

    def _txrx_refresh_compact_list(self):
        self.txrx_analysis_by_index.clear()
        self.txrx_live_observation_by_index.clear()
        self.txrx_manual_validation_cache = None
        self._refresh_txrx_tree()
        if self.txrx_selected_index is not None:
            self._show_txrx_selection_loading(self.txrx_selected_index)
        self._txrx_log("[TXRX] TC 목록/DBC 분석 캐시 새로고침\n")

    def _txrx_auto_select_all(self):
        for idx, row in enumerate(getattr(self, "condition_rows", [])):
            if row.is_valid and row.condition is not None and not self._is_safety_excluded_tc(row.condition):
                self.txrx_auto_selected_indices.add(idx)
        self.txrx_test_ready_var.set(False)
        self._refresh_txrx_tree()

    def _txrx_auto_clear_selection(self):
        self.txrx_auto_selected_indices.clear()
        self.txrx_auto_anchor_index = None
        self.txrx_test_ready_var.set(False)
        self._refresh_txrx_tree()

    @staticmethod
    def _txrx_observation_verdict(hits: Dict[Any, bool], seen: Dict[Any, bool]) -> str:
        """출력 관측 증거만으로 PASS/FAIL/N/A를 분리한다. 실행 인프라 ERROR는 호출부에서 우선 처리한다."""
        if hits and all(bool(v) for v in hits.values()):
            return "PASS"
        if any(not bool(seen.get(k, False)) for k in hits):
            return "N/A"
        return "FAIL"

    def _set_txrx_auto_progress(self, percent: float, text: str):
        pct = max(0.0, min(100.0, float(percent)))
        try:
            self.txrx_auto_progress_var.set(pct)
            self.txrx_auto_progress_text_var.set(f"{text}  ({pct:.0f}%)")
        except Exception:
            pass

    def _update_txrx_auto_run_state(self):
        ready_var = getattr(self, "txrx_test_ready_var", None)
        ready = bool(ready_var.get()) if ready_var is not None else False
        selected = bool(getattr(self, "txrx_auto_selected_indices", set()))
        busy = bool(self.txrx_auto_thread is not None and self.txrx_auto_thread.is_alive())
        if self.txrx_auto_run_button is not None:
            self.txrx_auto_run_button.configure(state=tk.NORMAL if (ready and selected and not busy) else tk.DISABLED)
        if self.txrx_auto_stop_button is not None:
            self.txrx_auto_stop_button.configure(state=tk.NORMAL if busy else tk.DISABLED)

    def _txrx_make_auto_plan(self, idx: int, db_by_ch: Dict[int, Any], mapping: Dict[int, str]) -> Dict[str, Any]:
        row = self.condition_rows[idx]
        if not row.is_valid or row.condition is None:
            raise ValueError("유효하지 않은 TC")
        cond = row.condition
        if self._is_safety_excluded_tc(cond):
            raise ValueError("제동/조향/구동/에어백/고전압/ADAS 등 안전핵심 TC는 자동 Stimulus에서 제외됩니다.")
        inputs = list(cond.input_conditions or [])
        outputs = list(cond.output_conditions or [])
        if len(inputs) != 1:
            raise ValueError(f"rev87 자동 2안은 입력 조건 1개 TC부터 지원합니다. 현재 입력={len(inputs)}개")
        if not outputs:
            raise ValueError("출력 조건이 없어 자동 PASS/FAIL을 판정할 수 없습니다.")

        analysis = self._analyze_condition_txrx(cond, db_by_ch=db_by_ch, dbc_mapping=mapping)
        self.txrx_analysis_by_index[idx] = analysis
        in_row = (analysis.get("input_rows") or [{}])[0]
        in_found = [x for x in (in_row.get("locations") or []) if x.get("signal_found")]
        if not in_found:
            raise ValueError(f"입력 DBC 위치를 찾지 못했습니다: {inputs[0].message}:{inputs[0].signal}")
        # OR 후보는 UI 복잡도를 줄이기 위해 논리 CAN 번호가 가장 작은 유효 위치를 자동 선택하고 로그에 남긴다.
        in_found.sort(key=lambda x: int(x.get("channel") or 999))
        chosen = in_found[0]
        ch = int(chosen["channel"])
        logical = str(chosen.get("channel_label") or f"CAN{ch}").split("/", 1)[0].upper()
        inp = inputs[0]
        hold = self._effective_stimulus_hold_sec([(str(inp.message), str(inp.signal))])

        output_specs = []
        for pos, out in enumerate(outputs, start=1):
            ra = self._find_row_analysis(analysis, "output_rows", pos)
            found = [x for x in (ra.get("locations") or []) if x.get("signal_found")]
            if not found:
                raise ValueError(f"출력 DBC 위치를 찾지 못했습니다: {out.message}:{out.signal}")
            found.sort(key=lambda x: int(x.get("channel") or 999))
            output_specs.append({
                "pos": pos,
                "message": str(out.message),
                "signal": str(out.signal),
                "expected": out.expected_value_raw,
                "locations": [int(x["channel"]) for x in found],
            })
        return {
            "idx": idx,
            "tc_no": str(cond.tc_no),
            "subcategory": str(cond.subcategory),
            "condition": cond,
            "profile": {
                "tc_no": str(cond.tc_no), "channel": ch, "logical_can": logical,
                "message": str(inp.message), "signal": str(inp.signal),
                "active_value": inp.expected_value_raw, "hold_sec": hold,
            },
            "outputs": output_specs,
            "analysis_summary": str(analysis.get("summary") or "-"),
            "crc_alive": list(in_row.get("crc_alive") or []),
            "or_candidates": [int(x.get("channel")) for x in in_found],
        }

    def _txrx_preflight_selected_auto(self) -> List[Dict[str, Any]]:
        selected = sorted(self.txrx_auto_selected_indices)
        if not selected:
            raise ValueError("자동 수행할 TC를 1개 이상 체크하세요.")
        mapping, db_by_ch, _sig, _cached = self._get_txrx_cached_dbc_map()
        if not mapping or not db_by_ch:
            raise ValueError("설정 탭의 CAN1~CAN3 DBC 매핑을 먼저 확인하세요.")
        plans = []
        errors = []
        total = max(1, len(selected))
        for pos, idx in enumerate(selected, start=1):
            try:
                self._show_operation_progress("테스트 실행 준비", f"후보 검증 {pos}/{total}", 15 + 70 * pos / total)
                plan = self._txrx_make_auto_plan(idx, db_by_ch, mapping)
                plans.append(plan)
                self._update_txrx_tree_row(idx)
            except Exception as e:
                errors.append(f"TC index {idx}: {e}")
                self.txrx_auto_result_by_index[idx] = "BLOCK"
                self.txrx_auto_detail_by_index[idx] = {"summary": str(e), "cause": str(e), "lines": [str(e)]}
                self._update_txrx_tree_row(idx)
        if errors:
            raise ValueError("자동 수행 준비 차단:\n- " + "\n- ".join(errors[:12]))
        return plans

    def _on_txrx_test_ready_changed(self):
        if not bool(self.txrx_test_ready_var.get()):
            self._update_txrx_auto_run_state()
            self._txrx_log("[TXRX][READY] 테스트 실행 준비 해제\n")
            return
        self._show_operation_progress("테스트 실행 준비", "후보/DBC/출력 조건 검증 시작", 5)
        def _work():
            try:
                plans = self._txrx_preflight_selected_auto()
                crc_items = [p for p in plans if p.get("crc_alive")]
                self._txrx_log(
                    f"[TXRX][READY] OK selected={len(plans)}, backend=CAPL Frame, "
                    f"original_sender_may_remain_active=True, crc/e2e_auto_calc=False\n"
                )
                for p in plans:
                    self._txrx_log(
                        f"[TXRX][READY][TC] {p['tc_no']} input={p['profile']['logical_can']}/"
                        f"{p['profile']['message']}.{p['profile']['signal']}={p['profile']['active_value']} "
                        f"hold={p['profile']['hold_sec']}s OR_CAN={p['or_candidates']} CRC/Alive={p['crc_alive'] or '-'}\n"
                    )
                if crc_items:
                    self._txrx_log("[TXRX][READY][WARN] CRC/Alive/Counter 후보가 있으나 사용자가 통합 준비 체크로 경고를 인지했습니다. 자동 계산은 하지 않습니다.\n")
                self._show_operation_progress("테스트 실행 준비", "준비 완료", 100)
                self._close_operation_progress(120)
                self._set_txrx_auto_progress(0, f"준비 완료: {len(plans)}개 TC")
                self._update_txrx_auto_run_state()
            except Exception as e:
                self.txrx_test_ready_var.set(False)
                self._close_operation_progress(0)
                self._update_txrx_auto_run_state()
                self._txrx_log(f"[TXRX][READY][BLOCK] {e}\n")
                messagebox.showerror("테스트 실행 준비 불가", str(e))
        self.after(30, _work)

    def _txrx_runtime_bridge_dir(self) -> Path:
        """rev87: package-version-independent runtime directory shared by all PassFail releases.

        Example:
          .../PassFail/PassFail_260826_7/  (application)
          .../PassFail/PF_Stimulus_Runtime/ (stable CANoe node source directory)
        """
        app_dir = Path(getattr(self, "_app_dir", Path.cwd())).resolve()
        base_dir = app_dir.parent
        runtime_dir = base_dir / "PF_Stimulus_Runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        return runtime_dir

    def _txrx_active_bridge_path(self, logical_can: str) -> Path:
        """Stable runtime mirror path that survives PassFail package/version changes."""
        token = str(logical_can or "CAN1").strip().upper().replace(" ", "_")
        return self._txrx_runtime_bridge_dir() / f"PF_Stimulus_Bridge_{token}_ACTIVE.can"

    @staticmethod
    def _txrx_dbc_id_from_path(raw_path: str) -> str:
        """rev87: prefer a short vehicle/DBC identifier (B1/C/M/E/...) from the local DBC filename.

        The DBC itself stays local. If no short standalone token can be inferred safely,
        fall back to the sanitized filename stem rather than guessing.
        """
        stem = Path(str(raw_path or "")).stem.strip() or "DBC"
        # Typical company names contain tokens such as ..._FD_B1_v25.11.01.
        # Prefer B<number> first, then single-letter project identifiers.
        matches = re.findall(r"(?:^|[_.-])(B\d+|C|M|E|T)(?=[_.-]|$)", stem, flags=re.IGNORECASE)
        if matches:
            # The right-most token is normally the most specific project/vehicle discriminator.
            return str(matches[-1]).upper()
        token = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-") or "DBC"
        return token[:48]

    def _txrx_named_active_bridge_path(self, logical_can: str, dbc_id: str) -> Path:
        token = str(logical_can or "CAN1").strip().upper().replace(" ", "_")
        dbc_token = re.sub(r"[^A-Za-z0-9._-]+", "_", str(dbc_id or "DBC")).strip("._-") or "DBC"
        return Path(getattr(self, "_app_dir", Path.cwd())) / f"PF_Stimulus_Bridge_{token}_{dbc_token}_ACTIVE.can"

    @staticmethod
    def _txrx_dbc_sha256(raw_path: str) -> str:
        path = Path(str(raw_path or ""))
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _txrx_stamp_bridge_identity(self, source: Path, logical_can: str, channel: int, dbc_path: str) -> str:
        """Embed local DBC identity/hash in generated CAPL text so stale/mismatched bridges are detectable."""
        dbc_id = self._txrx_dbc_id_from_path(dbc_path)
        digest = self._txrx_dbc_sha256(dbc_path)
        text = source.read_text(encoding="cp1252", errors="replace")
        marker = "/* PassFail rev87 Bridge Identity */"
        header = "\n".join([
            marker,
            f"/* Logical CAN: {str(logical_can).upper()} / Physical Channel: CAN{int(channel)} */",
            f"/* Source DBC ID: {dbc_id} */",
            f"/* Source DBC SHA256: {digest} */",
            f"/* Runtime Mirror: {self._txrx_active_bridge_path(logical_can).name} */",
            "",
        ])
        if marker not in text:
            text = header + text
        source.write_text(text, encoding="cp1252", errors="replace")
        return digest

    def _txrx_verify_active_bridge_identity(self, active_path: Path, logical_can: str, channel: int, dbc_path: str) -> None:
        """Hard-block compile when ACTIVE content is not from the currently selected local DBC."""
        expected_id = self._txrx_dbc_id_from_path(dbc_path)
        expected_sha = self._txrx_dbc_sha256(dbc_path)
        text = active_path.read_text(encoding="cp1252", errors="replace")
        required = [
            f"Source DBC ID: {expected_id}",
            f"Source DBC SHA256: {expected_sha}",
            f"Physical Channel: CAN{int(channel)}",
        ]
        missing = [x for x in required if x not in text]
        if missing:
            raise RuntimeError(
                f"DBC-Bridge 정합성 검증 실패: {active_path.name}가 현재 CAN{int(channel)} DBC({expected_id}) 기준으로 생성된 파일이 아닙니다. "
                "ACTIVE Bridge를 재생성한 뒤 Compile해야 합니다. 누락=" + ", ".join(missing)
            )

    def _txrx_write_active_bridges(self, plans: List[Dict[str, Any]], db_by_ch: Dict[int, Any], dbc_mapping: Dict[int, str]) -> Tuple[List[str], Any]:
        candidates = []
        for p in plans:
            pr = p["profile"]
            candidates.append(_stimulus.StimulusCandidate(
                logical_can=pr["logical_can"], channel=int(pr["channel"]),
                message=pr["message"], signal=pr["signal"], active_value=pr["active_value"], bus_name="CAN",
            ))
        group = _stimulus.StimulusGroupProfile(
            name="rev87 Auto P/F Bridge Set", candidates=candidates,
            hold_sec=max(float(p["profile"]["hold_sec"]) for p in plans), source="TXRX auto P/F selected TCs",
        )
        def resolver(channel: int, message_name: str):
            db = db_by_ch.get(int(channel))
            if db is None:
                return None
            try:
                return db.get_message_by_name(str(message_name))
            except Exception:
                return None
        gen_dir = Path(getattr(self, "_app_dir", Path.cwd())) / "vector_capl_bridge"
        generated = _stimulus.generate_vector_capl_bridges(group, resolver, gen_dir, revision="rev87")
        active_paths = []
        channel_by_logical: Dict[str, int] = {}
        for p in plans:
            pr = p["profile"]
            channel_by_logical[str(pr["logical_can"]).strip().upper()] = int(pr["channel"])
        for gp in generated:
            src = Path(gp)
            m = re.search(r"PF_Stimulus_Bridge_(CAN\d+)_rev87\.can$", src.name, re.IGNORECASE)
            if not m:
                continue
            logical = m.group(1).upper()
            channel = int(channel_by_logical.get(logical, int(re.sub(r"\D", "", logical) or "1")))
            dbc_path = str((dbc_mapping or {}).get(channel) or "").strip()
            if not dbc_path or not Path(dbc_path).is_file():
                raise RuntimeError(f"{logical}/CAN{channel}의 DBC 파일 경로가 유효하지 않아 Bridge ID를 만들 수 없습니다: {dbc_path or '-'}")
            dbc_id = self._txrx_dbc_id_from_path(dbc_path)
            self._txrx_stamp_bridge_identity(src, logical, channel, dbc_path)

            # Human-auditable canonical file: CAN + local DBC identity are explicit in the filename.
            named_active = self._txrx_named_active_bridge_path(logical, dbc_id)
            shutil.copyfile(src, named_active)

            # Stable runtime mirror: keeps the one-time CANoe/CANalyzer node association from rev78.
            active = self._txrx_active_bridge_path(logical)
            shutil.copyfile(named_active, active)
            self._txrx_verify_active_bridge_identity(active, logical, channel, dbc_path)
            active_paths.append(str(active))
            self.txrx_async_queue.put((
                "AUTO_LOG",
                f"[TXRX][BRIDGE][IDENTITY] {logical}=CAN{channel}, DBC_ID={dbc_id}, canonical={named_active.name}, runtime={active.name}\n",
            ))
        if not active_paths:
            raise RuntimeError("ACTIVE CAPL Bridge 파일을 생성하지 못했습니다.")
        return active_paths, resolver

    def _txrx_auto_run_selected(self):
        if self.txrx_auto_thread is not None and self.txrx_auto_thread.is_alive():
            messagebox.showinfo("실행 중", "이미 차량 송수신 자동 P/F가 진행 중입니다.")
            return
        if not bool(self.txrx_test_ready_var.get()):
            messagebox.showwarning("준비 필요", "먼저 '테스트 실행 준비'를 체크하세요.")
            return
        try:
            self._show_operation_progress("자동 P/F 실행", "선택 TC 재검증", 5)
            plans = self._txrx_preflight_selected_auto()
            mapping = self._collect_dbc_mapping()
            delay_sec = max(0.0, float(self.txrx_between_tc_delay_var.get() or "1.0"))
            # rev87: Tk variables are snapshotted on the GUI thread. The worker only uses plain values.
            auto_measurement_log_dir = str(self.log_dir_var.get() or "").strip()
            auto_measurement_sheet_name = str(self.sheet_var.get() or "").strip()
            auto_measurement_dbc_mapping = dict(mapping)
            self._show_operation_progress("자동 P/F 실행", "실행 스레드 준비", 100)
            self._close_operation_progress(80)
        except Exception as e:
            self._close_operation_progress(0)
            messagebox.showerror("자동 P/F 실행 불가", str(e))
            return

        self.txrx_auto_stop_event.clear()
        for p in plans:
            self.txrx_auto_result_by_index[p["idx"]] = "실행중"
            self._update_txrx_tree_row(p["idx"])
        self._set_txrx_auto_progress(2, "자동 P/F 시작")
        if self.txrx_auto_run_button is not None:
            self.txrx_auto_run_button.configure(state=tk.DISABLED)
        if self.txrx_auto_stop_button is not None:
            self.txrx_auto_stop_button.configure(state=tk.NORMAL)
        self._txrx_log(
            f"\n[TXRX][AUTO] START count={len(plans)}, backend=CANoe CAPL output(), "
            f"ready_ack=True, original_sender_may_remain_active=True, crc_alive_e2e_auto_calc=False, "
            f"per_tc_measurement=True, auto_log_rename={bool(auto_measurement_log_dir)}\n"
        )

        worker_bus = self.bus_name_var.get().strip() or "CAN"
        worker_product = self.vector_product_var.get().strip() or "자동"
        def worker():
            client = None
            summary = {"PASS": 0, "FAIL": 0, "N/A": 0, "ERROR": 0, "total": len(plans)}
            try:
                self.txrx_async_queue.put(("AUTO_PROGRESS", 5, "DBC 로드 / ACTIVE Bridge 생성"))
                db_by_ch = core.load_dbc_map(mapping)
                active_paths, resolver = self._txrx_write_active_bridges(plans, db_by_ch, mapping)
                self.txrx_async_queue.put(("AUTO_LOG", "[TXRX][BRIDGE] ACTIVE files: " + " | ".join(active_paths) + "\n"))

                client = core.CANoeClient(bus_name=worker_bus, product_preference=worker_product).connect(
                    expected_version_keyword=None, expected_exe_keyword=None
                )
                if client.is_measurement_running():
                    client.stop_measurement()
                self.txrx_async_queue.put(("AUTO_PROGRESS", 12, "기존 CAPL Node 자동 Compile"))
                client.compile_existing_capl_nodes()

                total = max(1, len(plans))
                for order, p in enumerate(plans, start=1):
                    if self.txrx_auto_stop_event.is_set():
                        break
                    idx = p["idx"]
                    pr = p["profile"]
                    base_pct = 15 + 78 * (order - 1) / total
                    self.txrx_async_queue.put(("AUTO_PROGRESS", base_pct, f"{order}/{total} TC {p['tc_no']} 준비"))
                    profile = _stimulus.StimulusProfile(
                        tc_no=pr["tc_no"], channel=int(pr["channel"]), logical_can=pr["logical_can"],
                        message=pr["message"], signal=pr["signal"], active_value=pr["active_value"],
                        hold_sec=float(pr["hold_sec"]), bus_name="CAN", source="TXRX auto P/F",
                    )
                    fn_names = _stimulus.capl_function_names_for_single(profile, resolver)
                    # rev87: one selected TC = one Measurement session = one CANoe logging file boundary.
                    measurement_log_snapshot = self._txrx_snapshot_measurement_logs(auto_measurement_log_dir)
                    measurement_wall_start = time.time()
                    try:
                        registry = client.start_measurement_with_capl_bindings(fn_names, restart_if_running=True)
                    except Exception as e:
                        active = self._txrx_active_bridge_path(pr["logical_can"])
                        raise RuntimeError(
                            f"CAPL 함수 bind 실패. 최초 1회 CANoe Simulation Setup의 {pr['logical_can']} Network Node를 "
                            f"다음 고정 파일에 연결/Compile해야 합니다: {active}\n원인: {e}"
                        ) from e

                    hits = {}
                    seen = {}
                    last_values = {}
                    first_hit_time = {}
                    input_seen = False
                    input_hit = False
                    input_last_value = None
                    live_last_emit = 0.0
                    started_perf = time.monotonic()
                    for out in p["outputs"]:
                        key = (out["message"], out["signal"], str(out["expected"]))
                        hits[key] = False
                        seen[key] = False
                        last_values[key] = None

                    def observer():
                        nonlocal input_seen, input_hit, input_last_value, live_last_emit
                        if not input_hit:
                            try:
                                raw_input = client.get_signal_value(
                                    int(pr["channel"]), pr["message"], pr["signal"]
                                )
                                input_seen = True
                                input_last_value = raw_input
                                if core.values_equal(pr["active_value"], raw_input):
                                    input_hit = True
                            except Exception:
                                pass
                        for out in p["outputs"]:
                            key = (out["message"], out["signal"], str(out["expected"]))
                            if not hits[key]:
                                for ch in out["locations"]:
                                    try:
                                        raw = client.get_signal_value(int(ch), out["message"], out["signal"])
                                        seen[key] = True
                                        last_values[key] = raw
                                        if core.values_equal(out["expected"], raw):
                                            hits[key] = True
                                            first_hit_time[key] = time.monotonic() - started_perf
                                            break
                                    except Exception:
                                        continue
                        now = time.monotonic()
                        if now - live_last_emit >= 0.15:
                            live_last_emit = now
                            self.txrx_async_queue.put((
                                "AUTO_LIVE", idx, {
                                    "input_values": {(pr["message"], pr["signal"]): input_last_value if input_seen else None},
                                    "output_values": {
                                        (out["message"], out["signal"]): last_values.get((out["message"], out["signal"], str(out["expected"])))
                                        for out in p["outputs"]
                                    },
                                }
                            ))

                    executor = _stimulus.StimulusExecutor(
                        trace_dir=Path(getattr(self, "_app_dir", Path.cwd())) / "stimulus_logs",
                        dbc_resolver=resolver, canoe_backend_mode="capl", capl_function_registry=registry,
                    )
                    self.txrx_async_queue.put((
                        "AUTO_LOG",
                        f"[TXRX][AUTO][TC] START {p['tc_no']} input={pr['logical_can']}/{pr['message']}.{pr['signal']}="
                        f"{pr['active_value']} hold={pr['hold_sec']}s outputs={len(p['outputs'])}\n"
                    ))
                    result = executor.execute_once(
                        client, profile, stop_event=self.txrx_auto_stop_event,
                        observer_callback=observer, observer_interval_sec=0.04,
                    )
                    # Small post-release observation window catches outputs that arrive just after the final active frame.
                    post_deadline = time.monotonic() + 0.35
                    while not all(hits.values()) and time.monotonic() < post_deadline and not self.txrx_auto_stop_event.is_set():
                        observer()
                        time.sleep(0.04)

                    # rev87: explicitly close this TC's Measurement before naming the generated CANoe log.
                    self.txrx_async_queue.put((
                        "AUTO_PROGRESS", min(98.0, base_pct + (78.0 / total) * 0.82),
                        f"{order}/{total} Measurement Stop / 로그 이름 정리"
                    ))
                    measurement_stop_error = ""
                    measurement_log_path = ""
                    measurement_log_note = ""
                    try:
                        client.stop_measurement()
                    except Exception as e:
                        measurement_stop_error = f"{type(e).__name__}: {e}"
                    if not measurement_stop_error and auto_measurement_log_dir:
                        try:
                            measurement_log_path, measurement_log_note = self._txrx_rename_measurement_log_for_tc(
                                log_dir=auto_measurement_log_dir,
                                before_snapshot=measurement_log_snapshot,
                                after_ts=measurement_wall_start,
                                plan_index=idx,
                                sheet_name=auto_measurement_sheet_name,
                                dbc_mapping=auto_measurement_dbc_mapping,
                            )
                        except Exception as e:
                            measurement_log_note = f"로그 자동명명 WARN: {type(e).__name__}: {e}"
                    elif not auto_measurement_log_dir:
                        measurement_log_note = "자동 로그 폴더 미지정: CANoe 로그 자동명명 생략"

                    lines = []
                    for out in p["outputs"]:
                        key = (out["message"], out["signal"], str(out["expected"]))
                        if hits[key]:
                            lines.append(
                                f"PASS 조건 관측: {out['message']}:{out['signal']} == {out['expected']} "
                                f"({first_hit_time.get(key, 0):.3f}s)"
                            )
                        elif seen.get(key):
                            lines.append(
                                f"FAIL 후보(값 불일치): {out['message']}:{out['signal']} expected={out['expected']} last={last_values.get(key)}"
                            )
                        else:
                            lines.append(
                                f"N/A 미 감지: {out['message']}:{out['signal']} expected={out['expected']} (유효 sample 없음)"
                            )
                    if measurement_log_path:
                        lines.append(f"CANoe 로그: {measurement_log_path}")
                    if measurement_log_note:
                        lines.append(measurement_log_note)
                    if self.txrx_auto_stop_event.is_set():
                        pf = "ERROR"
                        lines.append("사용자 중단")
                    elif measurement_stop_error:
                        pf = "ERROR"
                        lines.append(f"Measurement Stop 오류: {measurement_stop_error}")
                    elif not result.ok or not result.restore_ok:
                        pf = "ERROR"
                        lines.append(f"Stimulus/원복 오류: {result.error or '-'} / restore_ok={result.restore_ok}")
                    else:
                        # 출력 Signal 자체를 한 번도 읽지 못한 경우 기능 FAIL로 단정하지 않고 N/A로 분리한다.
                        pf = self._txrx_observation_verdict(hits, seen)
                    summary[pf] = summary.get(pf, 0) + 1
                    if pf == "FAIL":
                        cause = "목표 Signal 값 미 관측"
                    elif pf == "N/A":
                        cause = "Signal 값 미 감지"
                    elif pf == "ERROR":
                        cause = measurement_stop_error or result.error or "실행/통신 오류"
                    else:
                        cause = "-"
                    detail = {
                        "summary": f"{pf}: 출력 {sum(1 for v in hits.values() if v)}/{len(hits)} 조건 관측",
                        "cause": cause,
                        "lines": lines,
                        "frames": int(getattr(result, "frame_count", 0) or 0),
                        "backend": str(getattr(result, "backend", "") or ""),
                        "measurement_log": measurement_log_path,
                        "measurement_log_note": measurement_log_note,
                        "observed": {
                            "input_values": {(pr["message"], pr["signal"]): input_last_value if input_seen else None},
                            "output_values": {
                                (out["message"], out["signal"]): last_values.get((out["message"], out["signal"], str(out["expected"])))
                                for out in p["outputs"]
                            },
                        },
                    }
                    self.txrx_async_queue.put(("AUTO_RESULT", idx, pf, detail))
                    self.txrx_async_queue.put((
                        "AUTO_LOG",
                        f"[TXRX][AUTO][TC] END {p['tc_no']} result={pf}, observed={sum(1 for v in hits.values() if v)}/{len(hits)}, "
                        f"frames={getattr(result,'frame_count',0)}, restore_ok={getattr(result,'restore_ok',False)}, "
                        f"measurement_log={measurement_log_path or '-'}\n"
                        + "".join(f"  - {line}\n" for line in lines)
                    ))
                    self.txrx_async_queue.put((
                        "AUTO_PROGRESS", 15 + 78 * order / total,
                        f"{order}/{total} 완료: {p['tc_no']} = {pf}"
                    ))
                    if delay_sec > 0 and order < total and not self.txrx_auto_stop_event.is_set():
                        time.sleep(min(delay_sec, 5.0))

                # rev87: each TC already stops Measurement for one-log-per-TC boundaries.
                # Keep a defensive final stop only for abnormal paths.
                if client is not None:
                    try:
                        if client.is_measurement_running():
                            client.stop_measurement()
                    except Exception:
                        pass
                self.txrx_async_queue.put(("AUTO_DONE", summary))
            except Exception as e:
                try:
                    if client is not None and client.is_measurement_running():
                        client.stop_measurement()
                except Exception:
                    pass
                self.txrx_async_queue.put(("AUTO_ERROR", f"{type(e).__name__}: {e}"))

        self.txrx_auto_thread = threading.Thread(target=worker, daemon=True)
        self.txrx_auto_thread.start()
        self._update_txrx_auto_run_state()

    def _txrx_stop_auto_pf(self):
        self.txrx_auto_stop_event.set()
        self._set_txrx_auto_progress(self.txrx_auto_progress_var.get(), "중단 요청 / 현재 TC 원복 대기")
        self._txrx_log("[TXRX][AUTO] 사용자 중단 요청 - Stimulus finally 원복 대기\n")

    def _finish_txrx_live_observation(self, idx: int, observed: Dict[str, Any]):
        self.txrx_live_observation_by_index[int(idx)] = dict(observed or {})
        self._update_txrx_tree_row(int(idx))

    def _finish_txrx_auto_one_result(self, idx: int, pf: str, detail: Dict[str, Any]):
        self.txrx_auto_result_by_index[int(idx)] = str(pf)
        self.txrx_auto_detail_by_index[int(idx)] = dict(detail or {})
        observed = (detail or {}).get("observed")
        if observed is not None:
            self.txrx_live_observation_by_index[int(idx)] = dict(observed or {})
        self._update_txrx_tree_row(int(idx))

    def _finish_txrx_auto_run(self, summary: Dict[str, Any]):
        self.txrx_auto_thread = None
        self.txrx_auto_stop_event.clear()
        for idx in list(self.txrx_auto_selected_indices):
            if self.txrx_auto_result_by_index.get(idx) == "실행중":
                self.txrx_auto_result_by_index[idx] = "ERROR"
                self.txrx_auto_detail_by_index[idx] = {"summary": "중단/미수행", "lines": ["자동 순차 실행이 완료되기 전에 중단되어 미수행 처리"]}
                summary["ERROR"] = int(summary.get("ERROR", 0) or 0) + 1
                self._update_txrx_tree_row(idx)
        self._set_txrx_auto_progress(
            100,
            f"완료: PASS {summary.get('PASS',0)} / FAIL {summary.get('FAIL',0)} / "
            f"N/A {summary.get('N/A',0)} / ERROR {summary.get('ERROR',0)}"
        )
        self._txrx_log(
            f"[TXRX][AUTO] DONE total={summary.get('total',0)}, PASS={summary.get('PASS',0)}, "
            f"FAIL={summary.get('FAIL',0)}, N/A={summary.get('N/A',0)}, ERROR={summary.get('ERROR',0)}\n"
        )
        self._update_txrx_auto_run_state()

    def _finish_txrx_auto_error(self, message: str):
        self.txrx_auto_thread = None
        self.txrx_auto_stop_event.clear()
        for idx in list(self.txrx_auto_selected_indices):
            if self.txrx_auto_result_by_index.get(idx) == "실행중":
                self.txrx_auto_result_by_index[idx] = "ERROR"
                self.txrx_auto_detail_by_index[idx] = {"summary": message, "lines": [message]}
                self._update_txrx_tree_row(idx)
        self._set_txrx_auto_progress(0, "자동 P/F 오류")
        self._txrx_log(f"[TXRX][AUTO][ERROR] {message}\n")
        self._update_txrx_auto_run_state()
        messagebox.showerror("차량 송수신 자동 P/F 오류", message)

    def _get_txrx_selected_condition(self):
        idx = self.txrx_selected_index
        if idx is None:
            return None, None
        if 0 <= idx < len(getattr(self, "condition_rows", [])):
            row = self.condition_rows[idx]
            if row.is_valid and row.condition is not None:
                return idx, row.condition
        return None, None

    def _txrx_begin_session_log(self):
        try:
            log_dir = Path(getattr(self, "_app_dir", Path.cwd())) / "txrx_logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.txrx_session_log_path = str(log_dir / f"txrx_auto_{stamp}_rev87.log")
            Path(self.txrx_session_log_path).write_text(
                "PassFail rev87 차량 송수신 테스트(2안) 실행/원인 분석 로그\n"
                "원 차량 송신원은 유지될 수 있음 / CRC·Alive·E2E 자동계산 없음 / 실제 write는 stimulus 모듈만 수행\n\n",
                encoding="utf-8",
            )
            self._txrx_log(f"[LOG] AI 분석용 자동 로그: {self.txrx_session_log_path}\n")
        except Exception:
            self.txrx_session_log_path = ""

    def _txrx_log(self, text: str):
        msg = str(text or "")
        if self.txrx_log_text is not None:
            try:
                self.txrx_log_text.insert(tk.END, msg)
                self.txrx_log_text.see(tk.END)
            except Exception:
                pass
        if self.txrx_session_log_path:
            try:
                with open(self.txrx_session_log_path, "a", encoding="utf-8") as f:
                    f.write(msg)
            except Exception:
                pass
        try:
            self._log(msg)
        except Exception:
            pass

    @staticmethod
    def _txrx_filename_token(value: Any, fallback: str = "X", max_len: int = 36) -> str:
        """Return a Windows-safe compact filename token without changing the source data."""
        text = str(value or "").strip()
        text = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "_", text)
        text = re.sub(r"\s+", "_", text)
        text = re.sub(r"_+", "_", text).strip(" ._")
        if not text:
            text = str(fallback or "X")
        return text[:max(4, int(max_len))].rstrip(" ._") or str(fallback or "X")

    def _txrx_sheet_log_token(self, sheet_name: str) -> str:
        # Example requested by user: `1. 시트 및 안전장치` -> `시트`.
        text = str(sheet_name or "").strip()
        text = re.sub(r"^\s*\d+\s*[.)_\-:]?\s*", "", text)
        text = re.split(r"\s+및\s+|\s*&\s*|\s*/\s*", text, maxsplit=1)[0].strip()
        return self._txrx_filename_token(text, fallback="Sheet", max_len=28)

    def _txrx_tc_number_token(self, tc_no: Any) -> str:
        text = str(tc_no or "").strip()
        if re.fullmatch(r"\d+(?:[.]0+)?", text):
            try:
                return f"{int(float(text)):03d}"
            except Exception:
                pass
        return self._txrx_filename_token(text, fallback="TC", max_len=18)

    def _txrx_tc_occurrence(self, plan_index: int) -> int:
        rows = list(getattr(self, "condition_rows", []) or [])
        idx = int(plan_index)
        if not (0 <= idx < len(rows)):
            return 1
        target = str(getattr(rows[idx], "tc_no", "") or "").strip()
        if getattr(rows[idx], "condition", None) is not None:
            target = str(getattr(rows[idx].condition, "tc_no", target) or target).strip()
        count = 0
        for pos in range(0, idx + 1):
            row = rows[pos]
            tc = str(getattr(row, "tc_no", "") or "").strip()
            if getattr(row, "condition", None) is not None:
                tc = str(getattr(row.condition, "tc_no", tc) or tc).strip()
            if tc == target:
                count += 1
        return max(1, count)

    def _txrx_dbc_log_token(self, dbc_mapping: Dict[int, str]) -> str:
        parts: List[str] = []
        for channel in sorted((dbc_mapping or {}).keys()):
            path = str((dbc_mapping or {}).get(channel) or "").strip()
            if not path:
                continue
            # Use both slash styles so Windows DBC paths remain correct even in offline/unit environments.
            leaf = re.split(r"[\\/]", path)[-1]
            stem_raw = leaf.rsplit(".", 1)[0] if "." in leaf else leaf
            stem = self._txrx_filename_token(stem_raw, fallback="DBC", max_len=28)
            parts.append(f"CAN{int(channel)}_{stem}")
        return "_".join(parts) if parts else "DBC_NONE"

    def _txrx_measurement_log_basename(
        self,
        plan_index: int,
        sheet_name: str,
        dbc_mapping: Dict[int, str],
        measurement_start_ts: float,
        extension: str,
    ) -> str:
        rows = list(getattr(self, "condition_rows", []) or [])
        tc_no = "TC"
        if 0 <= int(plan_index) < len(rows):
            row = rows[int(plan_index)]
            tc_no = str(getattr(row, "tc_no", "") or "TC")
            if getattr(row, "condition", None) is not None:
                tc_no = str(getattr(row.condition, "tc_no", tc_no) or tc_no)
        sheet_token = self._txrx_sheet_log_token(sheet_name)
        tc_token = self._txrx_tc_number_token(tc_no)
        occurrence = self._txrx_tc_occurrence(plan_index)
        dbc_token = self._txrx_dbc_log_token(dbc_mapping)
        stamp = _dt.datetime.fromtimestamp(float(measurement_start_ts)).strftime("%H%M%S")
        ext = str(extension or "").lower()
        if ext not in (".asc", ".blf"):
            ext = ".log"
        return f"{sheet_token}_{tc_token}-{occurrence}_{dbc_token}_{stamp}{ext}"

    @staticmethod
    def _txrx_snapshot_measurement_logs(log_dir: str) -> Dict[str, Tuple[float, int]]:
        folder = Path(str(log_dir or "").strip())
        out: Dict[str, Tuple[float, int]] = {}
        if not folder.is_dir():
            return out
        try:
            for p in folder.iterdir():
                if not p.is_file() or p.suffix.lower() not in (".asc", ".blf"):
                    continue
                try:
                    st = p.stat()
                    out[str(p.resolve())] = (float(st.st_mtime), int(st.st_size))
                except Exception:
                    continue
        except Exception:
            return {}
        return out

    def _txrx_find_measurement_log_after_stop(
        self,
        log_dir: str,
        before_snapshot: Dict[str, Tuple[float, int]],
        after_ts: float,
        wait_timeout: float = 2.5,
    ) -> Tuple[Optional[Path], int]:
        """Find the newest ASC/BLF newly created or changed by this Measurement session."""
        folder = Path(str(log_dir or "").strip())
        if not folder.is_dir():
            return None, 0
        deadline = time.time() + max(0.2, float(wait_timeout))
        last_candidates: List[Path] = []
        while time.time() <= deadline:
            candidates: List[Path] = []
            try:
                for p in folder.iterdir():
                    if not p.is_file() or p.suffix.lower() not in (".asc", ".blf"):
                        continue
                    try:
                        st = p.stat()
                    except Exception:
                        continue
                    key = str(p.resolve())
                    old = (before_snapshot or {}).get(key)
                    changed = old is None or float(st.st_mtime) > float(old[0]) + 0.001 or int(st.st_size) != int(old[1])
                    if changed and float(st.st_mtime) >= float(after_ts) - 1.5:
                        candidates.append(p)
                if candidates:
                    candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    last_candidates = candidates
                    # Once Measurement has stopped, wait briefly for the newest file to become stable.
                    newest = candidates[0]
                    try:
                        if core.wait_until_file_stable(newest, stable_sec=0.35, timeout=1.0, poll_interval=0.1):
                            return newest, len(candidates)
                    except Exception:
                        return newest, len(candidates)
            except Exception:
                pass
            time.sleep(0.15)
        if last_candidates:
            return last_candidates[0], len(last_candidates)
        return None, 0

    @staticmethod
    def _txrx_unique_log_target(path: Path) -> Path:
        if not path.exists():
            return path
        for n in range(2, 100):
            candidate = path.with_name(f"{path.stem}_{n:02d}{path.suffix}")
            if not candidate.exists():
                return candidate
        stamp = _dt.datetime.now().strftime("%f")
        return path.with_name(f"{path.stem}_{stamp}{path.suffix}")

    def _txrx_rename_measurement_log_for_tc(
        self,
        log_dir: str,
        before_snapshot: Dict[str, Tuple[float, int]],
        after_ts: float,
        plan_index: int,
        sheet_name: str,
        dbc_mapping: Dict[int, str],
    ) -> Tuple[str, str]:
        latest, candidate_count = self._txrx_find_measurement_log_after_stop(
            log_dir, before_snapshot, after_ts, wait_timeout=2.5
        )
        if latest is None:
            return "", "CANoe Logging 새 ASC/BLF 미탐지: 로그 자동명명 생략(P/F 결과에는 영향 없음)"
        target_name = self._txrx_measurement_log_basename(
            plan_index, sheet_name, dbc_mapping, after_ts, latest.suffix
        )
        target = self._txrx_unique_log_target(latest.parent / target_name)
        if latest.resolve() != target.resolve():
            latest.replace(target)
        note = f"로그 자동명명 완료: {target.name}"
        if candidate_count > 1:
            note += f" / 주의: 이 Measurement에서 변경된 로그 {candidate_count}개 중 최신 1개를 이름 변경"
        return str(target), note

    def _txrx_log_verify(self, text: str, mirror_summary: bool = False):
        if self.txrx_log_verify_text is not None:
            try:
                self.txrx_log_verify_text.insert(tk.END, text)
                self.txrx_log_verify_text.see(tk.END)
            except Exception:
                pass
        if mirror_summary:
            self._txrx_log(text)

    def _txrx_log_verify_targets_from_result(self, result) -> List[Dict[str, Any]]:
        targets: List[Dict[str, Any]] = []
        items = getattr(result, "items", None)
        if items is not None:
            for item in items or []:
                targets.append({
                    "logical_can": str(getattr(item, "logical_can", "") or f"CAN{int(getattr(item, 'channel', 0) or 0)}"),
                    "channel": int(getattr(item, "channel", 0) or 0),
                    "message": str(getattr(item, "message", "") or ""),
                    "signal": str(getattr(item, "signal", "") or ""),
                    "active_value": getattr(item, "active_value", None),
                    "original_value": getattr(item, "original_value", None),
                    "baseline_payload_hex": str(getattr(item, "baseline_payload_hex", "") or ""),
                    "active_payload_hex": str(getattr(item, "active_payload_hex", "") or ""),
                    "cycle_ms": float(getattr(item, "cycle_ms", 0) or 0),
                    "tx_interval_ms": float(getattr(item, "tx_interval_ms", 0) or 0),
                    "hold_mode": str(getattr(item, "hold_mode", "") or ""),
                })
        else:
            ch = int(getattr(result, "channel", 0) or 0)
            targets.append({
                "logical_can": f"CAN{ch}",
                "channel": ch,
                "message": str(getattr(result, "message", "") or ""),
                "signal": str(getattr(result, "signal", "") or ""),
                "active_value": getattr(result, "active_value", None),
                "original_value": getattr(result, "original_value", None),
                "baseline_payload_hex": str(getattr(result, "baseline_payload_hex", "") or ""),
                "active_payload_hex": str(getattr(result, "active_payload_hex", "") or ""),
                "cycle_ms": float(getattr(result, "cycle_ms", 0) or 0),
                "tx_interval_ms": float(getattr(result, "tx_interval_ms", 0) or 0),
                "hold_mode": str(getattr(result, "hold_mode", "") or ""),
            })
        return [x for x in targets if x.get("channel") and x.get("message") and x.get("signal")]

    def _txrx_build_log_verify_response_groups(self, condition: Any) -> List[Dict[str, Any]]:
        """Build OR-channel output expectations for post-Stimulus diagnostic correlation."""
        groups: List[Dict[str, Any]] = []
        if condition is None:
            return groups
        try:
            db_by_ch = self._get_txrx_cached_dbc_map()
        except Exception:
            db_by_ch = {}
        for exp in list(getattr(condition, "output_conditions", []) or []):
            try:
                locations = self._find_expectation_locations(db_by_ch, exp)
            except Exception:
                locations = []
            candidates = [
                {
                    "channel": int(x.get("channel", 0) or 0),
                    "logical_can": str(x.get("channel_label") or f"CAN{int(x.get('channel',0) or 0)}"),
                }
                for x in locations
                if x.get("signal_found") and int(x.get("channel", 0) or 0) > 0
            ]
            if not candidates:
                continue
            groups.append({
                "role": "output",
                "message": str(getattr(exp, "message", "") or ""),
                "signal": str(getattr(exp, "signal", "") or ""),
                "expected_value": getattr(exp, "expected_value_raw", None),
                "candidates": candidates,
            })
        return groups

    def _txrx_diag_value_text(self, value: Any) -> str:
        if value is None:
            return "-"
        try:
            if isinstance(value, bool):
                return str(int(value))
            if isinstance(value, int):
                return f"{value} (0x{value:X})"
            if isinstance(value, float) and value.is_integer():
                iv = int(value)
                return f"{iv} (0x{iv:X})"
        except Exception:
            pass
        return str(value)

    def _txrx_diag_sequence_text(self, sequence, max_items: int = 12) -> str:
        items = []
        for t, direction, value in list(sequence or [])[:max_items]:
            items.append(f"{float(t):.6f}s {direction}:{self._txrx_diag_value_text(value)}")
        if not items:
            return "미관측"
        if len(sequence or []) > max_items:
            items.append("...")
        return " → ".join(items)

    def _start_txrx_stimulus_log_verification(self, result, force_latest: bool = False):
        if result is None:
            return
        if self.txrx_log_verify_thread is not None and self.txrx_log_verify_thread.is_alive():
            self.txrx_log_verify_status_var.set("로그 검증: 이전 분석 중")
            return
        if not force_latest and not bool(self.txrx_log_verify_enabled_var.get()):
            self.txrx_log_verify_status_var.set("로그 검증: 자동 OFF")
            return

        targets = self._txrx_log_verify_targets_from_result(result)
        if not targets:
            self.txrx_log_verify_status_var.set("로그 검증: 대상 없음")
            return
        try:
            mapping = dict(getattr(result, "log_verify_mapping", None) or self._collect_dbc_mapping())
        except Exception:
            mapping = {}
        try:
            log_dir = str(getattr(result, "log_verify_dir", "") or self.log_dir_var.get() or "").strip()
        except Exception:
            log_dir = ""
        after_ts = None if force_latest else getattr(result, "stimulus_wall_start_ts", None)
        response_groups = list(getattr(result, "log_verify_response_groups", None) or [])
        stimulus_wall_end_ts = getattr(result, "stimulus_wall_end_ts", None)
        measurement_restarted = bool(getattr(result, "stimulus_measurement_restarted", False))
        hold_sec = float(getattr(result, "hold_sec", 0) or 0)
        source_isolation_confirmed = bool(getattr(result, "log_verify_source_isolation_confirmed", False))
        if not log_dir:
            self.txrx_log_verify_status_var.set("로그 검증: 자동 로그 폴더 미지정")
            self._txrx_log_verify("[LOG-VERIFY][SKIP] 설정 탭의 자동 로그 폴더가 비어 있습니다.\n", mirror_summary=True)
            return
        if not mapping:
            self.txrx_log_verify_status_var.set("로그 검증: DBC 미지정")
            self._txrx_log_verify("[LOG-VERIFY][SKIP] CAN1~CAN3 DBC 매핑이 없어 로그를 decode할 수 없습니다.\n", mirror_summary=True)
            return

        self.txrx_log_verify_status_var.set("로그 검증: 최신 로그 탐색 중")
        self._txrx_log_verify(
            f"\n[LOG-VERIFY] 시작: folder={log_dir}, targets={len(targets)}, mode={'최신 로그 강제' if force_latest else 'Stimulus 이후 로그'}\n",
            mirror_summary=False,
        )

        def worker():
            try:
                latest = core.find_latest_log_file(
                    log_dir,
                    after_ts=(float(after_ts) - 2.0) if after_ts is not None else None,
                    wait_timeout=8.0,
                    poll_interval=0.4,
                    exts=(".blf", ".asc"),
                )
                if latest is None:
                    raise FileNotFoundError("조건에 맞는 최신 BLF/ASC 로그를 찾지 못했습니다.")
                stable = core.wait_until_file_stable(latest, stable_sec=0.8, timeout=6.0, poll_interval=0.2)
                if not stable:
                    raise TimeoutError("최신 로그 파일이 아직 쓰기 중이라 안정화되지 않았습니다. Measurement Stop 후 [마지막 Stimulus 로그 다시 검증]을 눌러주세요.")
                report = core.inspect_stimulus_transitions_in_log(
                    latest,
                    mapping,
                    targets,
                    response_groups=response_groups,
                    stimulus_wall_start_ts=getattr(result, "stimulus_wall_start_ts", None),
                    stimulus_wall_end_ts=stimulus_wall_end_ts,
                    measurement_restarted_for_stimulus=measurement_restarted,
                    hold_sec=hold_sec,
                )
                report["file_stable"] = True
                report["stimulus_frame_count"] = int(getattr(result, "frame_count", 0) or 0)
                report["stimulus_backend"] = str(getattr(result, "backend", "") or "")
                report["source_isolation_confirmed"] = source_isolation_confirmed
                self.txrx_async_queue.put(("LOG_VERIFY_DONE", report))
            except Exception as e:
                self.txrx_async_queue.put(("LOG_VERIFY_ERROR", f"{type(e).__name__}: {e}"))

        self.txrx_log_verify_thread = threading.Thread(target=worker, daemon=True)
        self.txrx_log_verify_thread.start()

    def _txrx_reverify_last_stimulus_log(self):
        result = self.txrx_last_stimulus_result
        if result is None:
            messagebox.showinfo("로그 재검증", "아직 이 실행에서 완료된 Stimulus 결과가 없습니다.")
            return
        self._start_txrx_stimulus_log_verification(result, force_latest=True)

    def _finish_txrx_stimulus_log_verification_error(self, message: str):
        self.txrx_log_verify_status_var.set("로그 검증: 실패/확인 필요")
        self._txrx_log_verify(f"[LOG-VERIFY][ERROR] {message}\n", mirror_summary=True)
        self.txrx_log_verify_thread = None

    def _txrx_diag_payload_diff_text(self, diffs) -> str:
        parts = []
        for item in list(diffs or [])[:16]:
            idx = int(item.get("index", 0) or 0)
            b = item.get("baseline")
            a = item.get("active")
            btxt = "--" if b is None else f"{int(b):02X}"
            atxt = "--" if a is None else f"{int(a):02X}"
            parts.append(f"B{idx}:{btxt}->{atxt}")
        return ", ".join(parts) if parts else "없음"

    def _txrx_diag_stats_for_channel(self, stats: Dict[str, Any], channel: int) -> Dict[str, int]:
        try:
            by_ch = dict(stats.get("by_channel") or {})
            row = by_ch.get(int(channel)) or by_ch.get(str(int(channel))) or {}
        except Exception:
            row = {}
        return {
            "total": int(row.get("total", 0) or 0),
            "tx": int(row.get("tx", 0) or 0),
            "rx": int(row.get("rx", 0) or 0),
        }

    def _txrx_auto_diag_lines_for_target(self, report: Dict[str, Any], row: Dict[str, Any]) -> Tuple[str, List[str]]:
        lines: List[str] = []
        ch = int(row.get("channel", 0) or 0)
        logical = str(row.get("logical_can") or f"CAN{ch}")
        msg = str(row.get("message") or "-")
        sig = str(row.get("signal") or "-")
        whole_stats = dict((report.get("direction_stats") or {}).get("whole") or {})
        window_stats = dict((report.get("direction_stats") or {}).get("window") or {})
        whole_ch = self._txrx_diag_stats_for_channel(whole_stats, ch)
        window_ch = self._txrx_diag_stats_for_channel(window_stats, ch)
        whole_tx = int(whole_stats.get("tx", 0) or 0)
        backend = str(report.get("stimulus_backend") or "")
        capl_frames = int(report.get("stimulus_frame_count", 0) or 0)
        source_isolation_confirmed = bool(report.get("source_isolation_confirmed", False))

        lines.append(
            f"[AUTO-DIAG][1/CALL] backend={backend or '-'} / PassFail 호출 frames={capl_frames} "
            f"→ {'호출 단계 성공 증거 있음' if capl_frames > 0 else '호출 frame 증거 없음'}"
        )

        if whole_tx <= 0:
            lines.append(
                "[AUTO-DIAG][2/LOGGER] ASC 전체에서 Tx 레코드가 0개입니다. "
                "현재 Logging이 Rx만 기록하는 구성일 수 있어 target Tx=0만으로 실제 버스 송신 실패를 단정할 수 없습니다."
            )
            logger_state = "tx_logging_unknown"
        elif whole_ch["tx"] <= 0:
            lines.append(
                f"[AUTO-DIAG][2/LOGGER] ASC 전체에는 Tx={whole_tx}개가 있으나 {logical}에는 Tx가 없습니다. "
                f"{logical} Logging/send branch 또는 실제 송신 채널을 우선 확인하세요."
            )
            logger_state = "channel_tx_missing"
        else:
            lines.append(
                f"[AUTO-DIAG][2/LOGGER] Tx 기록 능력 확인: ASC 전체 Tx={whole_tx}, "
                f"{logical} Tx={whole_ch['tx']} (분석창 {logical} Tx={window_ch['tx']})"
            )
            logger_state = "tx_logging_available"

        frame_count = int(row.get("frame_count", 0) or 0)
        tx_count = int(row.get("tx_count", 0) or 0)
        rx_count = int(row.get("rx_count", 0) or 0)
        if frame_count <= 0:
            lines.append(
                f"[AUTO-DIAG][3/TARGET] 분석 시간창에서 {logical} {msg} 자체가 0 frame입니다. "
                "로그 파일/채널/Logging filter/DBC/분석 window를 확인하세요."
            )
        else:
            lines.append(
                f"[AUTO-DIAG][3/TARGET] {logical} {msg}: window frames={frame_count} (Tx={tx_count}, Rx={rx_count})"
            )

        active_seen = bool(row.get("active_seen"))
        if active_seen:
            dirs = sorted(set(str(x[1]) for x in list(row.get("active_hits") or [])))
            lines.append(
                f"[AUTO-DIAG][4/ACTIVE] {sig}={self._txrx_diag_value_text(row.get('active_value'))} "
                f"로그 관측=YES / 방향={','.join(dirs) or '-'}"
            )
        else:
            lines.append(
                f"[AUTO-DIAG][4/ACTIVE] {sig}={self._txrx_diag_value_text(row.get('active_value'))} "
                "로그 관측=NO"
            )

        if rx_count > 0:
            if source_isolation_confirmed:
                lines.append(
                    f"[AUTO-DIAG][5/SOURCE] 동일 ID Rx={rx_count}개가 Stimulus 시간창에 계속 존재합니다. "
                    "'기존 송신원 분리·비활성 확인' 체크와 실제 버스 관측이 맞지 않을 수 있으므로 "
                    "원 ECU/Generator가 정말 중지됐는지 또는 CANoe 방향 표기가 어떻게 기록되는지 확인하세요."
                )
            else:
                lines.append(
                    f"[AUTO-DIAG][5/SOURCE] 동일 ID Rx={rx_count}개가 Stimulus 시간창에 존재합니다. "
                    "기존 ECU/Generator 송신원과 CAPL 송신이 겹칠 가능성을 확인하세요."
                )
        else:
            lines.append("[AUTO-DIAG][5/SOURCE] 분석 시간창의 동일 ID Rx 지속은 관측되지 않았습니다.")

        intended = dict(row.get("intended_suspicious") or {})
        if intended:
            static_names = []
            changed_names = []
            for name, info in intended.items():
                if bool(info.get("changed")):
                    changed_names.append(name)
                else:
                    static_names.append(name)
            if static_names:
                lines.append(
                    "[AUTO-DIAG][6/INTENDED-E2E] PassFail이 만들려고 한 Active payload에서 "
                    "CRC/Alive/Counter가 baseline과 동일한 항목: " + ", ".join(static_names)
                )
            if changed_names:
                lines.append(
                    "[AUTO-DIAG][6/INTENDED-E2E] Active payload에서 함께 변경된 E2E류 항목: "
                    + ", ".join(changed_names)
                )
        else:
            lines.append("[AUTO-DIAG][6/INTENDED-E2E] intended payload 기준 CRC/Alive/Counter 비교 정보 없음")

        baseline_diffs = list(row.get("baseline_vs_observed_diff_bytes") or [])
        observed_raw = str(row.get("observed_baseline_raw_hex") or "")
        observed_dir = str(row.get("observed_baseline_direction") or "")
        if baseline_diffs:
            lines.append(
                f"[AUTO-DIAG][7/BASELINE] PassFail 재구성 baseline과 실제 {observed_dir or '-'} raw frame이 "
                f"{len(baseline_diffs)} byte 다릅니다: {self._txrx_diag_payload_diff_text(baseline_diffs)}. "
                "현재 COM/DBC 재구성 baseline이 실제 버스 frame을 그대로 대표하지 않을 수 있습니다."
            )
        elif observed_raw and row.get("baseline_payload_hex"):
            lines.append("[AUTO-DIAG][7/BASELINE] 재구성 baseline과 관측 raw frame이 byte 기준 일치합니다.")
        else:
            lines.append("[AUTO-DIAG][7/BASELINE] baseline/raw 비교 증거 없음")

        # Verdict prioritizes evidence quality. It never claims vehicle functional PASS.
        if frame_count <= 0:
            if logger_state == "tx_logging_unknown":
                verdict = "로그가 Rx-only일 가능성 + target frame 미관측 → 먼저 Tx가 로그에 남는 구성인지 확인"
            else:
                verdict = "target Message가 Stimulus 시간창에 없음 → Bridge/send branch/논리 CAN/Logging 경로 확인"
        elif not active_seen:
            if tx_count > 0:
                verdict = "target Tx는 로그에 있으나 Active 값이 decode되지 않음 → intended payload/Bridge setter/DBC 정합성 확인"
            elif logger_state == "tx_logging_unknown":
                verdict = "target은 Rx로만 보이고 Active 미관측, 로그 전체 Tx=0 → Tx Logging 설정 확인 후 재검증"
            elif rx_count > 0:
                verdict = "target은 Rx만 지속되고 Active 미관측 → 기존 송신원 지속 또는 CAPL target Tx 미발생 가능성"
            else:
                verdict = "Active 미관측 → 실제 송신 경로/채널/로그 필터 확인"
        else:
            if tx_count > 0:
                verdict = "Active 값의 실제 로그 Tx 증거 확보. 다음은 ECU 수용/출력 반응 및 CRC/Alive 유효성 확인"
            else:
                verdict = "Active 값은 로그에 있으나 Tx 방향 증거 없음 → Logging 방향/실제 송신원 구분 후 ECU 반응 확인"

        lines.append(f"[AUTO-DIAG][VERDICT] {verdict}")
        return verdict, lines

    def _finish_txrx_stimulus_log_verification(self, report: Dict[str, Any]):
        rows = list(report.get("targets") or [])
        responses = list(report.get("response_groups") or [])
        active_ok = sum(1 for x in rows if x.get("active_seen"))
        total = len(rows)
        log_path = str(report.get("log_path") or "-")
        stable = bool(report.get("file_stable", False))
        whole_stats = dict((report.get("direction_stats") or {}).get("whole") or {})
        window_stats = dict((report.get("direction_stats") or {}).get("window") or {})
        window = dict(report.get("analysis_window") or {})

        # High-level status is evidence-oriented, not vehicle PASS/FAIL.
        if active_ok > 0 and any(x.get("seen_after_active") is True for x in responses):
            status_text = "로그 진단: Active + TC 출력반응 관측"
        elif active_ok > 0:
            status_text = f"로그 진단: Active 관측 {active_ok}/{total}"
        elif int(whole_stats.get("tx", 0) or 0) <= 0:
            status_text = "로그 진단: Tx 기록 설정 확인 필요"
        else:
            status_text = f"로그 진단: Active 미관측 {active_ok}/{total}"
        self.txrx_log_verify_status_var.set(status_text)

        self._txrx_log_verify(f"[LOG-VERIFY] 최신 로그: {log_path} / stable={stable}\n")
        start_sec = window.get("start_sec")
        end_sec = window.get("end_sec")
        if start_sec is None or end_sec is None:
            window_text = f"mode={window.get('mode','whole_log_fallback')} / 전체 로그"
        else:
            window_text = (
                f"mode={window.get('mode','-')} / {float(start_sec):.3f}s ~ {float(end_sec):.3f}s"
            )
        self._txrx_log_verify(f"[LOG-VERIFY][WINDOW] {window_text}\n")
        self._txrx_log_verify(
            f"[LOG-VERIFY][DIRECTION] ASC 전체 Tx={int(whole_stats.get('tx',0) or 0)}, "
            f"Rx={int(whole_stats.get('rx',0) or 0)} / 분석창 Tx={int(window_stats.get('tx',0) or 0)}, "
            f"Rx={int(window_stats.get('rx',0) or 0)}\n"
        )
        self._txrx_log_verify(
            f"[LOG-VERIFY] PassFail CAPL/Stimulus 호출 frames={report.get('stimulus_frame_count', 0)} / "
            "아래 로그 증거와 별도로 비교합니다.\n"
        )

        overall_verdicts = []
        for row in rows:
            logical = str(row.get("logical_can") or f"CAN{row.get('channel')}")
            msg = str(row.get("message") or "-")
            sig = str(row.get("signal") or "-")
            if row.get("error"):
                self._txrx_log_verify(f"[LOG-VERIFY][TARGET][ERROR] {logical} {msg}.{sig}: {row.get('error')}\n")
                continue

            self._txrx_log_verify(
                f"\n[LOG-VERIFY][MESSAGE] {logical} {msg}: window frames={row.get('frame_count',0)} "
                f"(Tx={row.get('tx_count',0)}, Rx={row.get('rx_count',0)}) / whole={row.get('whole_frame_count',0)} "
                f"(Tx={row.get('whole_tx_count',0)}, Rx={row.get('whole_rx_count',0)})\n"
            )
            self._txrx_log_verify(
                f"[LOG-VERIFY][SIGNAL] {sig}: Active={self._txrx_diag_value_text(row.get('active_value'))} / "
                f"Original={self._txrx_diag_value_text(row.get('original_value'))}\n"
            )
            self._txrx_log_verify(
                f"[LOG-VERIFY][SEQUENCE] {sig}: {self._txrx_diag_sequence_text(row.get('compact_sequence') or [])}\n"
            )

            baseline_hex = str(row.get("baseline_payload_hex") or "")
            active_hex = str(row.get("active_payload_hex") or "")
            if baseline_hex or active_hex:
                self._txrx_log_verify(
                    f"[LOG-VERIFY][INTENDED-PAYLOAD] baseline={baseline_hex or '-'}\n"
                    f"[LOG-VERIFY][INTENDED-PAYLOAD] active  ={active_hex or '-'}\n"
                    f"[LOG-VERIFY][INTENDED-DIFF] {self._txrx_diag_payload_diff_text(row.get('payload_diff_bytes') or [])}\n"
                )
            observed_baseline_raw = str(row.get("observed_baseline_raw_hex") or "")
            if observed_baseline_raw:
                self._txrx_log_verify(
                    f"[LOG-VERIFY][OBSERVED-BASELINE] {row.get('observed_baseline_direction','-')} raw={observed_baseline_raw}\n"
                    f"[LOG-VERIFY][BASELINE-DIFF] "
                    f"{self._txrx_diag_payload_diff_text(row.get('baseline_vs_observed_diff_bytes') or [])}\n"
                )

            if row.get("active_seen"):
                active_dirs = sorted(set(str(x[1]) for x in (row.get("active_hits") or [])))
                restore_text = "YES" if row.get("restore_seen_after_active") else "미확인"
                self._txrx_log_verify(
                    f"[LOG-VERIFY][RESULT] Active 값 로그 관측=YES / 방향={','.join(active_dirs) or '-'} / "
                    f"Active 이후 Original 원복 관측={restore_text}\n"
                )
            else:
                self._txrx_log_verify(
                    "[LOG-VERIFY][RESULT] Active 값 로그 관측=NO\n"
                )

            for sig_name, info in (row.get("intended_suspicious") or {}).items():
                change_note = "변경됨" if info.get("changed") else "정적 유지"
                self._txrx_log_verify(
                    f"[LOG-VERIFY][INTENDED-CRC/ALIVE] {sig_name}: "
                    f"{self._txrx_diag_value_text(info.get('baseline'))} -> "
                    f"{self._txrx_diag_value_text(info.get('active'))} / {change_note}\n"
                )

            for sig_name, seq in (row.get("suspicious_sequences") or {}).items():
                if seq:
                    change_note = "변화 있음" if len(seq) >= 2 else "변화 없음"
                    self._txrx_log_verify(
                        f"[LOG-VERIFY][OBSERVED-CRC/ALIVE] {sig_name}: "
                        f"{self._txrx_diag_sequence_text(seq)} / {change_note}\n"
                    )

            changed = list(row.get("changed_signals") or [])
            if changed:
                self._txrx_log_verify("[LOG-VERIFY][CHANGED-SIGNALS] 분석창의 동일 Message 내 변화 Signal:\n")
                for chg in changed:
                    self._txrx_log_verify(
                        f"  - {chg.get('signal')}: "
                        f"{self._txrx_diag_sequence_text(chg.get('sequence') or [], max_items=8)}\n"
                    )

            raw_frames = list(row.get("raw_active_frames") or [])
            for raw in raw_frames[:3]:
                self._txrx_log_verify(
                    f"[LOG-VERIFY][RAW-ACTIVE] {float(raw.get('time',0)):.6f}s "
                    f"{raw.get('direction','-')} data={raw.get('data_hex','-')}\n"
                )
            if not raw_frames:
                for raw in list(row.get("raw_message_frames") or [])[:3]:
                    self._txrx_log_verify(
                        f"[LOG-VERIFY][RAW-MESSAGE] {float(raw.get('time',0)):.6f}s "
                        f"{raw.get('direction','-')} data={raw.get('data_hex','-')}\n"
                    )

            verdict, diag_lines = self._txrx_auto_diag_lines_for_target(report, row)
            overall_verdicts.append(verdict)
            for line in diag_lines:
                self._txrx_log_verify(line + "\n")

        if responses:
            self._txrx_log_verify("\n[LOG-VERIFY][TC-OUTPUT] 선택 TC의 Expected 출력 반응 상관분석:\n")
            for group in responses:
                msg = str(group.get("message") or "-")
                sig = str(group.get("signal") or "-")
                expected = self._txrx_diag_value_text(group.get("expected_value"))
                candidate_labels = []
                for candidate in list(group.get("candidates") or []):
                    label = str(candidate.get("logical_can") or f"CAN{candidate.get('channel')}")
                    candidate_labels.append(label)
                    self._txrx_log_verify(
                        f"  - {label} {msg}.{sig}: frames={candidate.get('frame_count',0)} "
                        f"(Tx={candidate.get('tx_count',0)}, Rx={candidate.get('rx_count',0)}), "
                        f"seq={self._txrx_diag_sequence_text(candidate.get('compact_sequence') or [], max_items=8)}\n"
                    )
                after_active = group.get("seen_after_active")
                after_text = "YES" if after_active is True else "NO" if after_active is False else "판단불가(Active 미관측)"
                self._txrx_log_verify(
                    f"[LOG-VERIFY][TC-OUTPUT][RESULT] {'|'.join(candidate_labels) or '-'} "
                    f"{msg}.{sig} Expected={expected}: 관측={'YES' if group.get('seen') else 'NO'}, "
                    f"Active 이후 관측={after_text}\n"
                )

        # Next-action guide uses observed evidence, not implementation assumptions.
        if rows:
            first = rows[0]
            whole_tx = int(whole_stats.get("tx", 0) or 0)
            if not first.get("active_seen") and whole_tx <= 0:
                next_action = (
                    "현재 ASC 전체에 Tx 레코드가 없습니다. 먼저 CANoe Logging branch/filter가 Tx를 기록하도록 되어 있는지 "
                    "확인한 뒤 같은 시험을 재수행하세요. 그 다음에도 target Active가 없으면 CAPL SEND branch/논리 CAN을 확인하세요."
                )
            elif not first.get("active_seen") and int(first.get("tx_count", 0) or 0) <= 0:
                next_action = (
                    "로그가 Tx를 기록할 수 있는 상태인데 target Active/Tx가 없다면 CAPL Bridge가 실제 CAN에 연결된 SEND/Simulation branch인지, "
                    "선택 논리 CAN과 Message가 맞는지 확인하세요."
                )
            elif first.get("active_seen") and any(
                not bool(x.get("changed")) for x in (first.get("intended_suspicious") or {}).values()
            ):
                next_action = (
                    "Active 로그 증거는 있으나 intended payload에서 CRC/Alive/Counter가 정적으로 유지됩니다. "
                    "ECU가 Frame을 무효 처리할 수 있으므로 해당 Message의 E2E/CRC/Alive 계산 규칙과 기존 송신원 분리 상태를 다음으로 확인하세요."
                )
            elif first.get("active_seen") and responses and not any(x.get("seen_after_active") is True for x in responses):
                next_action = (
                    "Active 입력은 로그에서 보였지만 선택 TC의 Expected 출력 반응이 Active 이후 관측되지 않았습니다. "
                    "ECU 수용 조건, CRC/Alive/E2E, enable 조건 및 기존 송신원 충돌을 확인하세요."
                )
            else:
                next_action = (
                    "로그 증거와 TC 출력 반응을 함께 확인했습니다. 실제 시트가 움직이지 않는다면 다음 단계는 "
                    "하위 제어/모터 출력, 물리 enable 조건 및 차량 상태 조건을 확인하는 것입니다."
                )
            self._txrx_log_verify(f"\n[AUTO-DIAG][NEXT] {next_action}\n")

        self._txrx_log_verify(
            "[LOG-VERIFY][NOTE] rev87 진단은 CAPL 호출 성공, 로그의 실제 Tx/Rx 증거, ECU/차량 기능 반응을 서로 다른 단계로 취급합니다. "
            "Active 로그 관측=YES도 그 자체로 차량 기능 PASS를 의미하지 않습니다.\n"
        )
        self._txrx_log(
            f"[LOG-VERIFY] 완료: Active 관측 {active_ok}/{total}, log={Path(log_path).name if log_path != '-' else '-'}, "
            f"status={status_text}\n"
        )
        self.txrx_log_verify_thread = None

    def _ch_label_for_int(self, ch: int) -> str:
        return f"CAN{int(ch)}"

    def _txrx_dbc_mapping_signature(self, mapping: Dict[int, str]) -> Tuple[Any, ...]:
        parts = []
        for ch, raw_path in sorted((mapping or {}).items(), key=lambda x: int(x[0])):
            path = Path(str(raw_path))
            try:
                stat = path.stat()
                parts.append((int(ch), str(path.resolve()), int(stat.st_mtime_ns), int(stat.st_size)))
            except Exception:
                parts.append((int(ch), str(path), None, None))
        return tuple(parts)

    def _get_txrx_cached_dbc_map(self):
        """rev87: 동일 DBC를 TC마다 재로딩하지 않고 mapping signature 기준으로 재사용한다."""
        mapping = self._collect_dbc_mapping()
        signature = self._txrx_dbc_mapping_signature(mapping)
        if signature and signature == self.txrx_dbc_cache_signature and self.txrx_dbc_cache_by_ch:
            return mapping, self.txrx_dbc_cache_by_ch, signature, True
        db_by_ch = core.load_dbc_map(mapping) if mapping else {}
        self.txrx_dbc_cache_signature = signature
        self.txrx_dbc_cache_by_ch = db_by_ch
        return mapping, db_by_ch, signature, False

    def _txrx_pf_worker_busy_reason(self) -> str:
        """Stimulus 실제 송신 전 기존 단일/다중 판정 worker가 완전히 종료되었는지 확인한다."""
        checks = [
            ("단일 TC", getattr(self, "monitor_thread", None)),
            ("다중 TC", getattr(self, "multi_monitor_thread", None)),
        ]
        busy = [name for name, thread in checks if thread is not None and getattr(thread, "is_alive", lambda: False)()]
        if busy:
            return ", ".join(busy) + " 종료 처리 중"
        return ""

    def _manual_profile_fingerprint(self, profile) -> str:
        try:
            payload = profile.to_dict()
        except Exception:
            payload = str(profile)
        try:
            mapping = self._collect_dbc_mapping()
            signature = self._txrx_dbc_mapping_signature(mapping)
        except Exception:
            signature = ()
        try:
            product_pref = self.vector_product_var.get().strip()
            bus_name = self.bus_name_var.get().strip()
        except Exception:
            product_pref, bus_name = "", ""
        return json.dumps(
            {"profile": payload, "dbc": signature, "vector_product": product_pref, "bus_name": bus_name,
             "canoe_backend": self._canoe_backend_mode_key()},
            ensure_ascii=False, sort_keys=True, default=str
        )

    def _find_expectation_locations(self, db_by_ch: Dict[int, Any], expectation: Any) -> List[Dict[str, Any]]:
        matches: List[Dict[str, Any]] = []
        msg_name = str(getattr(expectation, "message", "") or "").strip()
        sig_name = str(getattr(expectation, "signal", "") or "").strip()
        if not msg_name or not sig_name:
            return matches
        for ch, db in sorted((db_by_ch or {}).items(), key=lambda x: int(x[0])):
            try:
                msg_obj = db.get_message_by_name(msg_name)
            except Exception:
                continue
            signal_obj = None
            try:
                signal_obj = msg_obj.get_signal_by_name(sig_name)
            except Exception:
                try:
                    signal_obj = next((s for s in getattr(msg_obj, "signals", []) if getattr(s, "name", "") == sig_name), None)
                except Exception:
                    signal_obj = None
            matches.append({
                "channel": int(ch),
                "channel_label": self._ch_label_for_int(int(ch)),
                "message": msg_obj,
                "signal": signal_obj,
                "signal_found": signal_obj is not None,
            })
        return matches

    def _message_cycle_ms(self, msg_obj: Any, msg_name: str) -> Optional[int]:
        try:
            cycle = getattr(msg_obj, "cycle_time", None)
            if cycle is not None:
                cycle_int = int(cycle)
                if cycle_int > 0:
                    return cycle_int
        except Exception:
            pass
        m = re.search(r"(?:^|[_\-])(?P<ms>\d{1,5})\s*ms(?:$|[_\-])", str(msg_name or ""), re.IGNORECASE)
        if m:
            try:
                return int(m.group("ms"))
            except Exception:
                pass
        return None

    def _detect_crc_alive_signals(self, msg_obj: Any) -> List[str]:
        suspicious: List[str] = []
        keywords = ("crc", "checksum", "chksum", "alive", "alv", "counter", "rolling")
        try:
            for sig in getattr(msg_obj, "signals", []) or []:
                name = str(getattr(sig, "name", "") or "")
                low = name.lower()
                if any(k in low for k in keywords):
                    suspicious.append(name)
        except Exception:
            pass
        return suspicious

    def _condition_text_blob(self, condition: Any) -> str:
        parts: List[str] = [
            str(getattr(condition, "tc_no", "") or ""),
            str(getattr(condition, "subcategory", "") or ""),
            str(getattr(condition, "tc_content", "") or ""),
            str(getattr(condition, "tc_expected_result", "") or ""),
        ]
        for exp in list(getattr(condition, "input_conditions", []) or []) + list(getattr(condition, "output_conditions", []) or []):
            parts.extend([
                str(getattr(exp, "message", "") or ""),
                str(getattr(exp, "signal", "") or ""),
                str(getattr(exp, "expected_value_raw", "") or ""),
            ])
        return " ".join(parts).lower()

    def _is_safety_excluded_tc(self, condition: Any) -> bool:
        """자동 Stimulus에서 계속 차단해야 하는 안전핵심 영역만 판정한다.

        이전 revision의 `str`/`tq`/`hv` 단순 부분문자열 검사는 일반 Signal명까지 BLOCK할 수 있어
        rev87부터 짧은 약어는 token 단위로만 판정한다. 시트/등받이/윈도우 등 body-comfort
        작동은 이 함수에서 차단하지 않고 별도 적색 경고로 운용한다.
        """
        text = self._condition_text_blob(condition)
        critical_keywords = (
            "brake", "brk", "steer", "eps", "airbag", "srs", "torque", "accel", "throttle",
            "shift", "gear", "sbw", "highvoltage", "charging", "charge", "adas", "aeb", "lkas", "scc",
            "제동", "브레이크", "조향", "스티어", "에어백", "토크", "구동", "가속", "변속", "기어", "고전압", "충전", "운전자보조",
        )
        if any(k in text for k in critical_keywords):
            return True
        tokens = {x for x in re.split(r"[^a-z0-9가-힣]+", text) if x}
        return any(k in tokens for k in ("str", "tq", "hv"))

    def _txrx_physical_warning_item(self, condition: Any) -> str:
        text = self._condition_text_blob(condition)
        mappings = (
            (("seat", "backrest", "recline", "slide", "시트", "등받이", "좌석"), "시트"),
            (("window", "윈도우"), "윈도우"),
            (("sunroof", "선루프"), "선루프"),
            (("tailgate", "테일게이트"), "테일게이트"),
            (("door", "도어"), "도어"),
            (("mirror", "미러"), "미러"),
            (("wiper", "와이퍼"), "와이퍼"),
        )
        for keys, label in mappings:
            if any(k in text for k in keys):
                return label
        if self._is_physical_or_switch_tc(condition):
            return "차량 작동"
        return ""

    def _update_txrx_safety_warning(self):
        var = getattr(self, "txrx_safety_warning_var", None)
        if var is None:
            return
        warning_items = []
        blocked = False
        for idx in sorted(getattr(self, "txrx_auto_selected_indices", set())):
            try:
                row = self.condition_rows[idx]
                cond = row.condition if row.is_valid else None
            except Exception:
                cond = None
            if cond is None:
                continue
            if self._is_safety_excluded_tc(cond):
                blocked = True
                continue
            item = self._txrx_physical_warning_item(cond)
            if item and item not in warning_items:
                warning_items.append(item)
        lines = []
        if warning_items:
            label = "/".join(warning_items)
            lines.append(f"{label} 자동 테스트 수행 시, 반드시 하차하여 진행하세요")
        if blocked:
            lines.append("제동/조향/구동/에어백/고전압/ADAS 등 안전핵심 TC는 자동 Stimulus에서 계속 제외됩니다.")
        if not lines:
            lines.append("안전 경고 대상 TC가 선택되면 이곳에 표시됩니다.")
        var.set("  |  ".join(lines))

    def _is_physical_or_switch_tc(self, condition: Any) -> bool:
        text = self._condition_text_blob(condition)
        physical_keywords = (
            "seat", "switch", "sw", "button", "btn", "window", "wiper", "mirror", "sunroof", "door", "tailgate",
            "시트", "스위치", "버튼", "윈도우", "와이퍼", "미러", "선루프", "도어", "테일게이트", "물리", "접점",
        )
        return any(k in text for k in physical_keywords)

    def _classify_txrx_method(self, condition: Any, analysis: Dict[str, Any]) -> Tuple[str, str]:
        """차량 송수신 테스트를 전체 자동화가 아닌 예비 프리테스트 관점으로 분류한다."""
        if self._is_safety_excluded_tc(condition):
            return self.TXRX_METHOD_EXCLUDE, "제동/조향/구동/에어백/충전/ADAS 등 안전 영향 가능성이 있어 초기 자동 송신/Replay 대상에서 제외 권장"

        if analysis.get("errors"):
            return self.TXRX_METHOD_MANUAL, "입력 Message/Signal 또는 DBC/채널 정보가 부족하여 자동 자극 구성이 어려움"

        all_input_rows = analysis.get("input_rows", []) or []
        has_crc_alive = any(row.get("crc_alive") for row in all_input_rows)
        has_physical = self._is_physical_or_switch_tc(condition)

        if has_physical and has_crc_alive:
            return self.TXRX_METHOD_PHYSICAL, "버튼/스위치류 물리 입력 가능성과 CRC/Alive 포함 가능성이 있어 릴레이/VT System 또는 실제 조작 로그 Replay 우선 권장"
        if has_physical:
            return self.TXRX_METHOD_PHYSICAL, "버튼/스위치류 TC는 CAN 일부 Signal 송신만으로 실제 조작을 대체하기 어려울 수 있어 물리 입력 자동화 또는 로그 Replay 권장"
        if has_crc_alive:
            return self.TXRX_METHOD_REPLAY, "CRC/Alive/Counter 포함 가능성이 있어 직접 Signal 합성보다 실제 조작 로그 Replay 또는 CAPL 계산 로직 필요"

        if analysis.get("warnings"):
            return self.TXRX_METHOD_REPLAY, "정적 검사상 확인 필요 항목이 있어 우선 로그 Replay 후보로 분류"

        return self.TXRX_METHOD_CAN, "입력 Message/Signal이 DBC에서 확인되며 CRC/Alive 의심 항목이 없어 제한적 CAN Signal 송신 프리테스트 후보"

    def _analyze_condition_txrx(
        self, condition: Any, db_by_ch: Optional[Dict[int, Any]] = None, dbc_mapping: Optional[Dict[int, str]] = None
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "status": self.TXRX_STATUS_UNCHECKED,
            "summary": "",
            "input_rows": [],
            "output_rows": [],
            "details": [],
            "warnings": [],
            "bus_warning": "",
            "errors": [],
            "recommended_period_ms": None,
            "method": self.TXRX_METHOD_UNKNOWN,
            "method_reason": "",
            "pretest_meaning": "자동 예비 프리테스트는 가능한 TC만 선별하기 위한 참고 결과이며, 자동 FAIL은 기능 FAIL 확정이 아닙니다.",
        }

        if dbc_mapping is None:
            try:
                dbc_mapping = self._collect_dbc_mapping()
            except Exception as e:
                result["status"] = self.TXRX_STATUS_BAD
                result["summary"] = f"DBC/논리 CAN 설정 수집 실패: {e}"
                result["errors"].append(result["summary"])
                result["method"] = self.TXRX_METHOD_MANUAL
                result["method_reason"] = "DBC 설정을 먼저 보완해야 합니다."
                return result

        if not dbc_mapping:
            result["status"] = self.TXRX_STATUS_BAD
            result["summary"] = "유효한 DBC/논리 CAN 매핑이 없습니다. 설정 탭에서 CAN1/2/3의 DBC를 지정하세요."
            result["errors"].append(result["summary"])
            result["method"] = self.TXRX_METHOD_MANUAL
            result["method_reason"] = "DBC/논리 CAN 매핑이 없어 자동 프리테스트 분류가 불가합니다."
            return result

        if db_by_ch is None:
            try:
                _mapping, db_by_ch, _sig, _cached = self._get_txrx_cached_dbc_map()
            except Exception as e:
                result["status"] = self.TXRX_STATUS_BAD
                result["summary"] = f"DBC 로드 실패: {type(e).__name__}: {e}"
                result["errors"].append(result["summary"])
                result["method"] = self.TXRX_METHOD_MANUAL
                result["method_reason"] = "DBC 로드 실패로 자동 프리테스트 분류가 불가합니다."
                return result

        if not db_by_ch:
            result["status"] = self.TXRX_STATUS_BAD
            result["summary"] = "유효한 DBC를 1개도 로드하지 못했습니다."
            result["errors"].append(result["summary"])
            result["method"] = self.TXRX_METHOD_MANUAL
            result["method_reason"] = "유효 DBC가 없어 자동 프리테스트 분류가 불가합니다."
            return result

        recommended_cycles: List[int] = []

        # 입력 조건: 향후 송신 대상
        for pos, exp in enumerate(getattr(condition, "input_conditions", []) or [], start=1):
            locations = self._find_expectation_locations(db_by_ch, exp)
            row = {
                "role": "입력",
                "pos": pos,
                "expectation": exp,
                "status": self.TXRX_STATUS_UNCHECKED,
                "channel": "-",
                "reason": "",
                "locations": locations,
                "cycle_ms": None,
                "crc_alive": [],
            }
            if not locations:
                row["status"] = self.TXRX_STATUS_BAD
                row["reason"] = f"DBC에서 Message를 찾지 못함: {exp.message}"
                result["errors"].append(row["reason"])
            elif not any(x.get("signal_found") for x in locations):
                row["status"] = self.TXRX_STATUS_BAD
                row["channel"] = ", ".join(x.get("channel_label", "") for x in locations)
                row["reason"] = f"DBC Message는 있으나 Signal을 찾지 못함: {exp.signal}"
                result["errors"].append(row["reason"])
            else:
                found = [x for x in locations if x.get("signal_found")]
                row["channel"] = ", ".join(x.get("channel_label", "") for x in found)
                first_msg = found[0].get("message")
                cycle = self._message_cycle_ms(first_msg, exp.message)
                row["cycle_ms"] = cycle
                if cycle:
                    recommended_cycles.append(cycle)
                crc_alive = self._detect_crc_alive_signals(first_msg)
                row["crc_alive"] = crc_alive
                candidate_labels = [
                    str(x.get("channel_label") or f"CAN{x.get('channel')}").split("/", 1)[0].upper()
                    for x in found
                ]
                # rev87: 복수 CAN 자체는 오류/경고가 아니다. 같은 신호가 여러 DBC에 있으면
                # CAN1 OR CAN2 OR CAN3 후보군으로 유지하고 실제 송신 시 사용자가 1개를 선택한다.
                or_note = ""
                if len(candidate_labels) >= 2:
                    or_note = (
                        f"송신 가능 논리 CAN OR 후보 {len(candidate_labels)}개("
                        + " | ".join(candidate_labels)
                        + ") - 실제 실행 시 1개 선택"
                    )
                warnings = []
                if crc_alive:
                    warnings.append("CRC/Alive/Counter류 Signal 포함 가능성: " + ", ".join(crc_alive[:6]))
                if warnings:
                    row["status"] = self.TXRX_STATUS_WARN
                    row["reason"] = " / ".join(([or_note] if or_note else []) + warnings)
                    result["warnings"].extend(warnings)
                else:
                    row["status"] = self.TXRX_STATUS_OK
                    row["reason"] = or_note or "DBC Message/Signal 확인 OK"
            result["input_rows"].append(row)

        # 출력 조건: 향후 수신/감시 대상 Preview. 수신 자체는 기존 P/F 로직을 재사용하지만 DBC 존재 여부도 같이 확인한다.
        for pos, exp in enumerate(getattr(condition, "output_conditions", []) or [], start=1):
            locations = self._find_expectation_locations(db_by_ch, exp)
            row = {
                "role": "출력",
                "pos": pos,
                "expectation": exp,
                "status": self.TXRX_STATUS_UNCHECKED,
                "channel": "-",
                "reason": "",
                "locations": locations,
            }
            if not locations:
                row["status"] = self.TXRX_STATUS_WARN
                row["reason"] = f"DBC에서 출력 Message를 찾지 못함: {exp.message}"
                result["warnings"].append(row["reason"])
            elif not any(x.get("signal_found") for x in locations):
                row["status"] = self.TXRX_STATUS_WARN
                row["channel"] = ", ".join(x.get("channel_label", "") for x in locations)
                row["reason"] = f"출력 Message는 있으나 Signal을 찾지 못함: {exp.signal}"
                result["warnings"].append(row["reason"])
            else:
                found = [x for x in locations if x.get("signal_found")]
                row["channel"] = ", ".join(x.get("channel_label", "") for x in found)
                row["status"] = self.TXRX_STATUS_OK
                row["reason"] = "수신/로그 검토용 DBC Message/Signal 확인 OK"
            result["output_rows"].append(row)

        if recommended_cycles:
            # 가장 빠른 주기를 기본 추천값으로 사용한다.
            result["recommended_period_ms"] = min(recommended_cycles)

        # 실제 버스 중복 송신 여부는 정적 DBC 검사만으로 확정할 수 없다.
        if result["input_rows"] and not result["errors"]:
            # rev87: 공통 버스 주의문은 정적 적합성 상태를 '확인 필요'로 강등하지 않는다.
            # 실제 CAPL 송신 전 source-isolation 확인 gate는 별도로 유지한다.
            result["bus_warning"] = "실제 차량 버스에 동일 Message ID가 이미 송신 중인지 별도 로그/버스 상태 확인 필요"

        if result["errors"]:
            result["status"] = self.TXRX_STATUS_BAD
            result["summary"] = result["errors"][0]
        elif result["warnings"]:
            result["status"] = self.TXRX_STATUS_WARN
            result["summary"] = result["warnings"][0]
        else:
            result["status"] = self.TXRX_STATUS_OK
            result["summary"] = "입력 Message/Signal 송신 Preview 가능"

        method, method_reason = self._classify_txrx_method(condition, result)
        result["method"] = method
        result["method_reason"] = method_reason
        if method in (self.TXRX_METHOD_MANUAL, self.TXRX_METHOD_PHYSICAL, self.TXRX_METHOD_EXCLUDE):
            if result["status"] == self.TXRX_STATUS_OK:
                result["status"] = self.TXRX_STATUS_WARN
            if result.get("summary") in ("입력 Message/Signal 송신 Preview 가능", ""):
                result["summary"] = method_reason

        return result

    def _check_txrx_selected(self):
        idx, cond = self._get_txrx_selected_condition()
        if cond is None:
            messagebox.showwarning("TC 선택 필요", "차량 송수신 테스트할 TC를 먼저 선택하세요.")
            return
        analysis = self._analyze_condition_txrx(cond)
        self.txrx_analysis_by_index[idx] = analysis
        self._refresh_txrx_tree()
        self._show_txrx_preview(idx)
        self._txrx_log(f"[TXRX] 선택 TC 검사 완료: TC={cond.tc_no}, status={analysis.get('status')}, reason={analysis.get('summary')}\n")

    def _check_txrx_all(self):
        """rev87: 전체 가능성 검사는 GUI thread를 점유하지 않고 DBC를 1회만 로드한다."""
        if self.txrx_all_check_thread is not None and self.txrx_all_check_thread.is_alive():
            messagebox.showinfo("전체 검사 진행 중", "이미 전체 가능성 검사가 진행 중입니다.")
            return
        try:
            mapping = self._collect_dbc_mapping()
        except Exception as e:
            messagebox.showerror("전체 검사 불가", f"DBC/논리 CAN 설정 수집 실패: {e}")
            return
        if not mapping:
            messagebox.showwarning("DBC 설정 필요", "설정 탭에서 CAN1/2/3의 DBC를 먼저 지정하세요.")
            return

        targets = [(idx, row.condition) for idx, row in enumerate(getattr(self, "condition_rows", []))
                   if row.is_valid and row.condition is not None]
        if not targets:
            return
        signature = self._txrx_dbc_mapping_signature(mapping)
        cached_db = self.txrx_dbc_cache_by_ch if signature == self.txrx_dbc_cache_signature else None
        self.txrx_status_var.set(f"전체 가능성 검사 중: 0/{len(targets)}")
        if self.txrx_check_all_button is not None:
            self.txrx_check_all_button.configure(state=tk.DISABLED, text="전체 검사 중...")
        self._txrx_log(f"[TXRX] 전체 가능성 검사 시작: total={len(targets)}, DBC cache={'HIT' if cached_db else 'MISS'}\n")

        def worker():
            try:
                db_by_ch = cached_db or core.load_dbc_map(mapping)
                results = {}
                counts = {"ok": 0, "warn": 0, "bad": 0}
                for pos, (idx, cond) in enumerate(targets, start=1):
                    analysis = self._analyze_condition_txrx(cond, db_by_ch=db_by_ch, dbc_mapping=mapping)
                    results[idx] = analysis
                    status = analysis.get("status")
                    if status == self.TXRX_STATUS_OK:
                        counts["ok"] += 1
                    elif status == self.TXRX_STATUS_WARN:
                        counts["warn"] += 1
                    elif status == self.TXRX_STATUS_BAD:
                        counts["bad"] += 1
                    if pos == 1 or pos % 20 == 0 or pos == len(targets):
                        self.txrx_async_queue.put(("ALL_PROGRESS", pos, len(targets)))
                self.txrx_async_queue.put(("ALL_DONE", results, counts, db_by_ch, signature, len(targets)))
            except Exception as e:
                self.txrx_async_queue.put(("ALL_ERROR", str(e)))

        self.txrx_all_check_thread = threading.Thread(target=worker, daemon=True)
        self.txrx_all_check_thread.start()

    def _finish_txrx_all_check(self, results, counts, db_by_ch, signature, total):
        self.txrx_analysis_by_index.update(results or {})
        self.txrx_dbc_cache_signature = signature
        self.txrx_dbc_cache_by_ch = db_by_ch or {}
        self._refresh_txrx_tree()
        if self.txrx_selected_index is not None:
            self._show_txrx_preview(self.txrx_selected_index)
        ok, warn, bad = counts.get("ok", 0), counts.get("warn", 0), counts.get("bad", 0)
        self.txrx_status_var.set(f"검사 완료: 전체 {total}개 / 가능 {ok} / 확인 필요 {warn} / 불가 {bad}")
        self._txrx_log(f"[TXRX] 전체 가능성 검사 완료: total={total}, ok={ok}, warn={warn}, bad={bad}, DBC load=1회\n")
        if self.txrx_check_all_button is not None:
            self.txrx_check_all_button.configure(state=tk.NORMAL, text="전체 가능성 검사")
        self.txrx_all_check_thread = None

    def _finish_txrx_all_check_error(self, message: str):
        self.txrx_status_var.set("전체 가능성 검사 오류")
        self._txrx_log(f"[TXRX][ERROR] 전체 가능성 검사 실패: {message}\n")
        if self.txrx_check_all_button is not None:
            self.txrx_check_all_button.configure(state=tk.NORMAL, text="전체 가능성 검사")
        self.txrx_all_check_thread = None
        messagebox.showerror("전체 가능성 검사 실패", message)

    def _txrx_result_tag(self, result: str) -> str:
        s = str(result or "").upper()
        if s == "OK":
            return "ok"
        if s == "NG":
            return "ng"
        if s in ("PARTIAL", "수동필요", "REPLAY권장", "릴레이필요", "분석필요"):
            return "warn"
        return "neutral"

    def _selected_txrx_causes(self) -> List[str]:
        return [label for label, var in self.txrx_cause_vars.items() if bool(var.get())]

    def _clear_txrx_experiment_inputs(self):
        self.txrx_vehicle_reaction_var.set("미확인")
        self.txrx_output_judge_var.set("미확인")
        self.txrx_experiment_result_var.set("분석필요")
        for var in self.txrx_cause_vars.values():
            var.set(False)
        if self.txrx_experiment_memo_text is not None:
            self.txrx_experiment_memo_text.configure(state="normal")
            self.txrx_experiment_memo_text.delete("1.0", tk.END)
        self._txrx_log("[TXRX][EXP] 실험 결과 입력값 초기화\n")

    def _save_txrx_experiment_record(self):
        idx, cond = self._get_txrx_selected_condition()
        if cond is None or idx is None:
            messagebox.showwarning("TC 선택 필요", "실험 결과를 기록할 TC를 먼저 선택하세요.")
            return

        memo = ""
        if self.txrx_experiment_memo_text is not None:
            try:
                memo = self.txrx_experiment_memo_text.get("1.0", tk.END).strip()
            except Exception:
                memo = ""

        analysis = self.txrx_analysis_by_index.get(idx, {})
        now = _dt.datetime.now()
        record = {
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "time_short": now.strftime("%H:%M:%S"),
            "row_index": idx,
            "tc_no": getattr(cond, "tc_no", ""),
            "subcategory": getattr(cond, "subcategory", ""),
            "experiment_method": self.txrx_experiment_method_var.get(),
            "vehicle_reaction": self.txrx_vehicle_reaction_var.get(),
            "output_judge": self.txrx_output_judge_var.get(),
            "final_result": self.txrx_experiment_result_var.get(),
            "causes": "; ".join(self._selected_txrx_causes()),
            "memo": memo,
            "analysis_status": analysis.get("status", "미검사"),
            "analysis_method": analysis.get("method", "미분류"),
            "analysis_summary": analysis.get("summary", ""),
        }
        self.txrx_experiment_records.append(record)
        self._refresh_txrx_experiment_tree()
        self._refresh_txrx_tree()
        self._txrx_log(
            f"[TXRX][EXP] 실험 기록 저장: TC={record['tc_no']}, result={record['final_result']}, "
            f"reaction={record['vehicle_reaction']}, judge={record['output_judge']}\n"
        )
        self.txrx_status_var.set(f"실험 기록 저장: {record['tc_no']} / {record['final_result']}")

    def _refresh_txrx_experiment_tree(self):
        if self.txrx_experiment_tree is None:
            return
        self.txrx_experiment_tree.delete(*self.txrx_experiment_tree.get_children())
        for i, record in enumerate(self.txrx_experiment_records[-200:], start=1):
            result = str(record.get("final_result", ""))
            self.txrx_experiment_tree.insert(
                "",
                tk.END,
                iid=f"exp:{i}",
                tags=(self._txrx_result_tag(result),),
                values=(
                    record.get("time_short", ""),
                    record.get("tc_no", ""),
                    record.get("experiment_method", ""),
                    record.get("vehicle_reaction", ""),
                    record.get("output_judge", ""),
                    result,
                ),
            )

    def _reset_txrx_experiment_records(self):
        if not self.txrx_experiment_records:
            messagebox.showinfo("기록 없음", "초기화할 실험 기록이 없습니다.")
            return
        if not messagebox.askyesno("실험 기록 초기화", "현재 세션의 차량 송수신 실험 기록을 모두 초기화할까요?"):
            return
        self.txrx_experiment_records.clear()
        self._refresh_txrx_experiment_tree()
        self._refresh_txrx_tree()
        self._txrx_log("[TXRX][EXP] 실험 기록 전체 초기화\n")

    def _export_txrx_experiment_csv(self):
        if not self.txrx_experiment_records:
            messagebox.showwarning("기록 없음", "CSV로 저장할 실험 기록이 없습니다.")
            return
        default_name = f"txrx_experiment_records_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        try:
            initial_dir = str(getattr(self, "_app_dir", Path.cwd()))
        except Exception:
            initial_dir = str(Path.cwd())
        path = filedialog.asksaveasfilename(
            title="차량 송수신 실험 기록 CSV 저장",
            defaultextension=".csv",
            initialdir=initial_dir,
            initialfile=default_name,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        fields = [
            "created_at", "tc_no", "subcategory", "experiment_method", "vehicle_reaction",
            "output_judge", "final_result", "causes", "memo", "analysis_status", "analysis_method", "analysis_summary",
        ]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                for record in self.txrx_experiment_records:
                    writer.writerow({k: record.get(k, "") for k in fields})
            messagebox.showinfo("CSV 저장 완료", f"실험 기록을 저장했습니다.\n{path}")
            self._txrx_log(f"[TXRX][EXP] CSV 저장 완료: {path}\n")
        except Exception as e:
            messagebox.showerror("CSV 저장 실패", str(e))
            self._txrx_log(f"[TXRX][EXP][ERROR] CSV 저장 실패: {e}\n")

    def _txrx_or_can_candidates_from_found(self, found: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """rev87: deduplicate/sort logical CAN candidates while preserving each DBC location."""
        by_channel: Dict[int, Dict[str, Any]] = {}
        for item in found or []:
            try:
                ch = int(item.get("channel"))
            except Exception:
                continue
            if ch not in by_channel:
                by_channel[ch] = item
        return [by_channel[ch] for ch in sorted(by_channel)]

    def _set_txrx_or_can_candidates(self, found: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        candidates = self._txrx_or_can_candidates_from_found(found)
        labels = [
            str(x.get("channel_label") or f"CAN{int(x['channel'])}").split("/", 1)[0].upper()
            for x in candidates
        ]
        self.txrx_selected_can_candidate_values = labels
        if self.txrx_selected_can_combobox is not None:
            try:
                self.txrx_selected_can_combobox.configure(values=labels)
            except Exception:
                pass
        current = str(self.txrx_selected_can_candidate_var.get() or "").strip().upper()
        if current not in labels:
            current = labels[0] if labels else ""
            self.txrx_selected_can_candidate_var.set(current)
        if not labels:
            self.txrx_selected_can_candidate_status_var.set("송신 CAN 후보: 없음")
        elif len(labels) == 1:
            self.txrx_selected_can_candidate_status_var.set(f"송신 CAN 후보: {labels[0]} (1개)")
        else:
            self.txrx_selected_can_candidate_status_var.set(
                "송신 CAN OR 후보: " + " | ".join(labels) + f" / 현재 {current}"
            )
        return candidates

    def _selected_txrx_or_can_location(self, found: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        candidates = self._set_txrx_or_can_candidates(found)
        if not candidates:
            return None
        selected = str(self.txrx_selected_can_candidate_var.get() or "").strip().upper()
        for item in candidates:
            label = str(item.get("channel_label") or f"CAN{int(item['channel'])}").split("/", 1)[0].upper()
            if label == selected:
                return item
        return candidates[0]

    def _on_txrx_selected_can_candidate_changed(self, event=None):
        """OR 후보 중 실제 1회 송신할 CAN을 바꾸면 자동 후보 한 줄도 같은 CAN으로 동기화한다."""
        self.txrx_manual_validation_cache = None
        selected = str(self.txrx_selected_can_candidate_var.get() or "").strip().upper()
        if selected:
            self._txrx_log(f"[STIMULUS][OR-CAN] 실제 송신 CAN 선택: {selected}\n")
        self._txrx_autofill_manual_candidate_from_selected(silent=True)

    def _txrx_autofill_manual_candidate_from_selected(self, silent: bool = False) -> bool:
        """rev87: selected TC -> one-line manual candidate with CAN1~CAN3 OR-candidate support.

        Multiple logical CAN locations are not an error. All are retained as OR candidates,
        while the combobox selects exactly one CAN for the actual one-shot Stimulus.
        This method only prepares text and never starts Measurement/Vector COM/write/output.
        """
        if not bool(self.txrx_autofill_manual_from_selection_var.get()):
            return False
        if self.txrx_manual_candidate_text is None:
            return False
        idx, cond = self._get_txrx_selected_condition()
        if cond is None or idx is None:
            return False
        inputs = list(getattr(cond, "input_conditions", []) or [])
        if len(inputs) != 1:
            reason = f"입력 조건 {len(inputs)}개 - 자동 한 줄 후보는 입력 1개 TC만 지원"
            self.txrx_manual_candidate_status_var.set(f"수동 후보: 자동 적용 불가({reason})")
            self.txrx_selected_can_candidate_values = []
            self.txrx_selected_can_candidate_var.set("")
            self.txrx_selected_can_candidate_status_var.set("송신 CAN 후보: 입력 조건 1개 TC만 지원")
            if self.txrx_selected_can_combobox is not None:
                self.txrx_selected_can_combobox.configure(values=[])
            self._txrx_log(f"[STIMULUS][AUTO-FILL][BLOCK] TC={getattr(cond,'tc_no','-')}: {reason}\n")
            if not silent:
                messagebox.showwarning("선택 TC 자동 적용 불가", reason)
            return False
        exp = inputs[0]
        try:
            analysis = self.txrx_analysis_by_index.get(idx)
            if not analysis:
                analysis = self._analyze_condition_txrx(cond)
                self.txrx_analysis_by_index[idx] = analysis
            rows = list(analysis.get("input_rows") or [])
            row = rows[0] if len(rows) == 1 else {}
            found = [x for x in (row.get("locations") or []) if x.get("signal_found")]
        except Exception as e:
            reason = f"DBC 정적 분석 실패: {type(e).__name__}: {e}"
            self.txrx_manual_candidate_status_var.set("수동 후보: 자동 적용 실패")
            self._txrx_log(f"[STIMULUS][AUTO-FILL][ERROR] {reason}\n")
            if not silent:
                messagebox.showerror("선택 TC 자동 적용 실패", reason)
            return False

        candidates = self._set_txrx_or_can_candidates(found)
        if not candidates:
            reason = "논리 CAN 후보 0개"
            self.txrx_manual_candidate_status_var.set(f"수동 후보: 자동 적용 불가({reason})")
            self._txrx_log(f"[STIMULUS][AUTO-FILL][BLOCK] TC={getattr(cond,'tc_no','-')}: {reason}\n")
            if not silent:
                messagebox.showwarning(
                    "선택 TC 자동 적용 불가",
                    f"TC {getattr(cond,'tc_no','-')}의 {exp.message}.{exp.signal}을 DBC에서 찾지 못했습니다.\n"
                    f"{reason}\n[선택 TC 검사] 결과의 Channel/사유를 확인하세요.",
                )
            return False

        chosen = self._selected_txrx_or_can_location(candidates)
        if chosen is None:
            return False
        ch = int(chosen["channel"])
        logical_can = str(chosen.get("channel_label") or f"CAN{ch}").split("/", 1)[0].upper()
        line = (
            f"{logical_can}\t{str(getattr(exp,'message','') or '').strip()}\t"
            f"{str(getattr(exp,'signal','') or '').strip()}\t{getattr(exp,'expected_value_raw','')}"
        )
        self.txrx_manual_candidate_text.delete("1.0", tk.END)
        self.txrx_manual_candidate_text.insert("1.0", line)
        self.txrx_manual_validation_cache = None
        labels = list(self.txrx_selected_can_candidate_values)
        if len(labels) >= 2:
            status = f"수동 후보: TC {getattr(cond,'tc_no','-')} OR 후보 {' | '.join(labels)} / 현재 {logical_can} / 검증 필요"
            self._txrx_log(
                f"[STIMULUS][AUTO-FILL][OR] TC={getattr(cond,'tc_no','-')}: candidates={'|'.join(labels)}, selected={logical_can}, line={line}\n"
            )
        else:
            status = f"수동 후보: TC {getattr(cond,'tc_no','-')} 자동 적용 / {logical_can} / 검증 필요"
            self._txrx_log(f"[STIMULUS][AUTO-FILL] TC={getattr(cond,'tc_no','-')}: {line}\n")
        self.txrx_manual_candidate_status_var.set(status)
        return True

    def _txrx_manual_candidate_example(self):
        if self.txrx_manual_candidate_text is None:
            return
        example = (
            "CAN1\tSeat_Message_01\tSeatForwardReq\t1\n"
            "CAN1\tSeat_Message_01\tSeatEnable\t1\n"
        )
        self.txrx_manual_candidate_text.delete("1.0", tk.END)
        self.txrx_manual_candidate_text.insert("1.0", example)
        self.txrx_manual_candidate_status_var.set("수동 후보: 예시 입력됨")

    def _manual_candidate_logical_to_channel(self, token: str) -> Tuple[str, int]:
        text = str(token or "").strip().upper().replace(" ", "")
        if text in getattr(self, "can_names", []):
            return text, int(self._logical_can_to_channel(text))
        # rev87 backward compatibility: 과거 붙여넣기 CH1/1도 CAN1로 해석하되 GUI에서는 노출하지 않는다.
        m = re.fullmatch(r"CH([1-9]\d*)", text)
        if m:
            ch = int(m.group(1))
            return f"CAN{ch}", ch
        if text.isdigit() and int(text) > 0:
            ch = int(text)
            return f"CAN{ch}", ch
        raise ValueError(f"CAN 열은 CAN1/CAN2/CAN3 형식이어야 합니다: {token}")

    def _stimulus_requires_two_second_hold(self, message: str, signal: str) -> bool:
        """Known seat slide Fwd/Bwd button requests require a long press."""
        blob = f"{message} {signal}".lower().replace("_", "")
        return ("sldfwdmvbtn" in blob) or ("sldbwdmvbtn" in blob)

    def _effective_stimulus_hold_sec(self, targets: Optional[List[Tuple[str, str]]] = None) -> float:
        """Return GUI Hold with seat-slide long-press protection.

        rev87 changes the displayed default to 2.2 s. Only known seat slide
        Fwd/Bwd button requests are *clamped* to at least 2.0 s; other generic
        Stimulus candidates keep the user's requested Hold so this seat-specific
        requirement does not silently alter unrelated commands.
        """
        raw = str(self.txrx_stimulus_hold_sec_var.get() or "").strip() or "2.2"
        try:
            requested = float(raw)
        except Exception as e:
            raise ValueError(f"Hold(sec)는 숫자여야 합니다: {raw}") from e
        if requested <= 0:
            raise ValueError("Hold(sec)는 0보다 커야 합니다.")
        require_two = any(self._stimulus_requires_two_second_hold(m, sig) for m, sig in list(targets or []))
        effective = max(2.0, requested) if require_two else requested
        if effective != requested:
            try:
                self.txrx_stimulus_hold_sec_var.set(f"{effective:.1f}")
                self._txrx_log(
                    f"[STIMULUS][HOLD] 좌석 Slide Fwd/Bwd 버튼: 요청 {requested:g}s -> 최소 유지 {effective:.1f}s로 보정\n"
                )
            except Exception:
                pass
        return effective

    def _parse_manual_stimulus_candidates(self):
        if not STIMULUS_AVAILABLE or _stimulus is None:
            raise RuntimeError(
                "oracle_checker_stimulus_rev87.py를 사용할 수 없습니다. "
                f"기존 Pass/Fail은 정상 사용 가능합니다. import={STIMULUS_IMPORT_ERROR or '-'}"
            )
        if self.txrx_manual_candidate_text is None:
            raise ValueError("수동 후보 입력창이 없습니다.")
        raw = self.txrx_manual_candidate_text.get("1.0", tk.END)
        lines = [x.strip() for x in raw.splitlines() if x.strip() and not x.lstrip().startswith("#")]
        if not lines:
            raise ValueError("수동 후보 Signal을 입력하세요. Excel 4열(CAN, Message, Signal, Value)을 그대로 붙여넣을 수 있습니다.")
        if len(lines) > _stimulus.StimulusExecutor.MAX_GROUP_ITEMS:
            raise ValueError(
                f"rev87 수동 후보 묶음은 최대 {_stimulus.StimulusExecutor.MAX_GROUP_ITEMS}행만 허용합니다. 현재={len(lines)}행"
            )

        candidates = []
        safety_keywords = (
            "brake", "brk", "steer", "eps", "airbag", "srs", "torque", "accel", "throttle",
            "shift", "gear", "sbw", "highvoltage", "charging", "charge", "adas", "aeb", "lkas", "scc",
            "제동", "브레이크", "조향", "스티어", "에어백", "토크", "구동", "가속", "변속", "기어", "고전압", "충전", "운전자보조",
        )
        for lineno, line in enumerate(lines, start=1):
            if "\t" in line:
                parts = [x.strip() for x in line.split("\t")]
            elif "," in line:
                parts = [x.strip() for x in line.split(",")]
            elif ";" in line:
                parts = [x.strip() for x in line.split(";")]
            else:
                parts = re.split(r"\s+", line, maxsplit=3)
                parts = [x.strip() for x in parts]
            if len(parts) != 4:
                raise ValueError(
                    f"{lineno}행 형식 오류: CAN / Message / Signal / ActiveValue 4개 열이 필요합니다. 입력={line}"
                )
            can_token, message, signal, value = parts
            logical_can, channel = self._manual_candidate_logical_to_channel(can_token)
            blob = f"{message} {signal}".lower()
            tokens = {x for x in re.split(r"[^a-z0-9가-힣]+", blob) if x}
            if any(k in blob for k in safety_keywords) or any(k in tokens for k in ("str", "tq", "hv")):
                raise ValueError(f"{lineno}행은 rev87 안전핵심 키워드가 포함되어 수동 Stimulus 대상에서 제외합니다: {message}.{signal}")
            candidates.append(
                _stimulus.StimulusCandidate(
                    logical_can=logical_can,
                    channel=channel,
                    message=message,
                    signal=signal,
                    active_value=value,
                    bus_name="CAN",
                )
            )
        hold_sec = self._effective_stimulus_hold_sec([(str(x.message), str(x.signal)) for x in candidates])
        name = "Manual Candidate Set"
        idx, cond = self._get_txrx_selected_condition()
        if cond is not None:
            name = f"{str(getattr(cond, 'tc_no', '') or 'Selected TC')} manual candidates"
        return _stimulus.StimulusGroupProfile(
            name=name,
            candidates=candidates,
            hold_sec=hold_sec,
            source="Manual pasted candidates / rev87",
        )

    def _build_stimulus_dbc_resolver(self):
        """Return a strict in-memory DBC resolver for the isolated Stimulus module."""
        mapping, db_by_ch, _signature, _cached = self._get_txrx_cached_dbc_map()
        if not mapping:
            return None

        def resolver(channel: int, message_name: str):
            db = db_by_ch.get(int(channel))
            if db is None:
                return None
            try:
                return db.get_message_by_name(str(message_name))
            except Exception:
                return None

        return resolver

    def _canoe_backend_mode_key(self) -> str:
        try:
            raw = str(self.txrx_canoe_backend_var.get() or "")
        except Exception:
            raw = ""
        return "signal" if raw.lower().startswith("signal") else "capl"

    def _make_stimulus_executor(self):
        trace_dir = Path(getattr(self, "_app_dir", Path.cwd())) / "stimulus_logs"
        resolver = None
        try:
            resolver = self._build_stimulus_dbc_resolver()
        except Exception as e:
            self._txrx_log(f"[STIMULUS][DBC][WARN] DBC resolver 생성 실패: {e}\n")
        return _stimulus.StimulusExecutor(
            trace_dir=trace_dir, dbc_resolver=resolver, canoe_backend_mode=self._canoe_backend_mode_key()
        )

    def _vector_product_name(self, client) -> str:
        try:
            info = client.get_application_info() if hasattr(client, "get_application_info") else {}
            return str((info or {}).get("product") or "").strip()
        except Exception:
            return ""

    def _require_canalyzer_source_isolated(self, client):
        """Compatibility name: rev87 gate applies to any CAPL Frame backend (CANoe/CANalyzer)."""
        product = self._vector_product_name(client)
        uses_capl = product.lower() == "canalyzer" or (product.lower() == "canoe" and self._canoe_backend_mode_key() == "capl")
        if uses_capl and not bool(self.txrx_canalyzer_source_isolated_var.get()):
            raise ValueError(
                f"{product or 'Vector'} CAPL output()은 실제 CAN Frame을 송신합니다. 동일 CAN ID를 원래 ECU/Generator가 계속 송신 중이면 "
                "중복 송신 충돌 위험이 있습니다. 실제 송신 전에 원래 송신원을 분리/비활성했음을 확인한 뒤 "
                "[CAPL Frame 실제 송신 전: 동일 Message 기존 송신원 분리·비활성 확인]을 직접 체크하세요."
            )

    def _profile_for_capl_bridge_generation(self):
        text = ""
        try:
            text = self.txrx_manual_candidate_text.get("1.0", tk.END).strip() if self.txrx_manual_candidate_text else ""
        except Exception:
            text = ""
        if text:
            return self._parse_manual_stimulus_candidates()
        _, _, _, _, single = self._build_selected_stimulus_profile()
        logical = str(single.logical_can or f"CAN{single.channel}")
        return _stimulus.StimulusGroupProfile(
            name=f"{single.tc_no or 'Selected TC'} CAPL bridge",
            candidates=[_stimulus.StimulusCandidate(
                logical_can=logical,
                channel=int(single.channel),
                message=str(single.message),
                signal=str(single.signal),
                active_value=single.active_value,
                bus_name=single.bus_name,
            )],
            hold_sec=float(single.hold_sec),
            source="Selected TC / CAPL bridge generation",
        )

    def _txrx_build_all_input_bridge_profile(self):
        """Build a read-only bridge-generation profile from every valid TC input in the loaded Excel.

        This method never starts Measurement and never calls CAPL/output. It only inspects already-loaded
        TC conditions and local DBCs so a fresh PC can prepare the stable Runtime Bridge before any test run.
        Multiple-input TCs are intentionally included because pre-generation is not an execution approval.
        Existing runtime safety gates still decide whether a TC may actually transmit later.
        """
        if not STIMULUS_AVAILABLE or _stimulus is None:
            raise RuntimeError(f"Stimulus 모듈 없음: {STIMULUS_IMPORT_ERROR or '-'}")
        rows = list(getattr(self, "condition_rows", []) or [])
        if not rows:
            raise ValueError("TC 목록이 비어 있습니다. 먼저 Oracle Excel/TC 목록을 로드하세요.")
        mapping, db_by_ch, _signature, _cached = self._get_txrx_cached_dbc_map()
        if not mapping or not db_by_ch:
            raise ValueError("설정 탭에서 CAN1/CAN2/CAN3 DBC를 먼저 지정하세요.")

        candidates = []
        seen = set()
        scanned_tc = 0
        input_count = 0
        unresolved = []
        for idx, row in enumerate(rows):
            if not bool(getattr(row, "is_valid", False)) or getattr(row, "condition", None) is None:
                continue
            cond = row.condition
            scanned_tc += 1
            for exp in list(getattr(cond, "input_conditions", []) or []):
                input_count += 1
                found = [x for x in self._find_expectation_locations(db_by_ch, exp) if x.get("signal_found")]
                if not found:
                    unresolved.append(
                        f"TC {getattr(cond,'tc_no',idx+1)}: {getattr(exp,'message','')}.{getattr(exp,'signal','')}"
                    )
                    continue
                for loc in found:
                    ch = int(loc.get("channel") or 0)
                    if ch <= 0:
                        continue
                    label = str(loc.get("channel_label") or f"CAN{ch}")
                    logical = label.split("/", 1)[0].strip().upper() if label else f"CAN{ch}"
                    msg = str(getattr(exp, "message", "") or "").strip()
                    sig = str(getattr(exp, "signal", "") or "").strip()
                    key = (logical, ch, msg, sig)
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append(_stimulus.StimulusCandidate(
                        logical_can=logical, channel=ch, message=msg, signal=sig,
                        active_value=getattr(exp, "expected_value_raw", None), bus_name="CAN",
                    ))
        if not candidates:
            detail = ("\n미해결 예: " + " | ".join(unresolved[:5])) if unresolved else ""
            raise ValueError("전체 TC 입력 조건에서 Bridge 생성 후보를 찾지 못했습니다." + detail)
        profile = _stimulus.StimulusGroupProfile(
            name="rev87 Pre-generated Runtime Bridge Set",
            candidates=candidates,
            hold_sec=0.1,
            source="Loaded Oracle TC input conditions / read-only pre-generation",
        )
        return profile, mapping, db_by_ch, {
            "scanned_tc": scanned_tc,
            "input_count": input_count,
            "candidate_count": len(candidates),
            "unresolved": unresolved,
        }

    def _txrx_prepare_runtime_bridges_without_run(self):
        """Create/update canonical + stable Runtime Bridge without executing any TC or sending CAN frames."""
        if not STIMULUS_AVAILABLE or _stimulus is None:
            messagebox.showerror("Runtime Bridge 준비 불가", f"Stimulus 모듈 없음: {STIMULUS_IMPORT_ERROR or '-'}")
            return
        try:
            profile, mapping, db_by_ch, stats = self._txrx_build_all_input_bridge_profile()
            def resolver(channel: int, message_name: str):
                db = db_by_ch.get(int(channel))
                if db is None:
                    return None
                try:
                    return db.get_message_by_name(str(message_name))
                except Exception:
                    return None

            out_dir = Path(getattr(self, "_app_dir", Path.cwd())) / "vector_capl_bridge"
            generated = _stimulus.generate_vector_capl_bridges(profile, resolver, out_dir, revision="rev87")
            channel_by_logical = {}
            for item in profile.candidates:
                channel_by_logical[str(item.logical_can).strip().upper()] = int(item.channel)

            canonical_paths = []
            runtime_paths = []
            for raw in generated:
                src = Path(raw)
                m = re.search(r"PF_Stimulus_Bridge_(CAN\d+)_rev87\.can$", src.name, re.IGNORECASE)
                if not m:
                    continue
                logical = m.group(1).upper()
                channel = int(channel_by_logical.get(logical, int(re.sub(r"\D", "", logical) or "1")))
                dbc_path = str((mapping or {}).get(channel) or "").strip()
                if not dbc_path or not Path(dbc_path).is_file():
                    raise ValueError(f"{logical}/CAN{channel}의 DBC 경로가 유효하지 않습니다: {dbc_path or '-'}")
                dbc_id = self._txrx_dbc_id_from_path(dbc_path)
                self._txrx_stamp_bridge_identity(src, logical, channel, dbc_path)
                canonical = self._txrx_named_active_bridge_path(logical, dbc_id)
                runtime = self._txrx_active_bridge_path(logical)
                shutil.copyfile(src, canonical)
                shutil.copyfile(canonical, runtime)
                self._txrx_verify_active_bridge_identity(runtime, logical, channel, dbc_path)
                canonical_paths.append(str(canonical))
                runtime_paths.append(str(runtime))
                self._txrx_log(
                    f"[TXRX][BRIDGE][PREPARE] {logical}=CAN{channel}, DBC_ID={dbc_id}, "
                    f"canonical={canonical}, runtime={runtime}\n"
                )

            if not runtime_paths:
                raise RuntimeError("Runtime Bridge 파일을 생성하지 못했습니다.")
            unresolved = list(stats.get("unresolved") or [])
            self._txrx_log(
                f"[TXRX][BRIDGE][PREPARE][DONE] no_measurement=True, no_can_output=True, "
                f"TC={stats.get('scanned_tc',0)}, inputs={stats.get('input_count',0)}, "
                f"candidates={stats.get('candidate_count',0)}, unresolved={len(unresolved)}\n"
            )
            msg = [
                "실제 TC 실행/Measurement 시작/CAN 송신 없이 Runtime Bridge 준비가 완료되었습니다.",
                "",
                f"검토 TC: {stats.get('scanned_tc',0)}개 / 입력 조건: {stats.get('input_count',0)}개",
                f"Bridge 후보: {stats.get('candidate_count',0)}개 / 미해결 입력: {len(unresolved)}개",
                "",
                "Runtime 파일:",
                *runtime_paths,
                "",
                "새 PC에서는 CANoe/CANalyzer Network Node에 위 Runtime 파일을 최초 1회 연결한 뒤 Compile하세요.",
                "이 준비 기능 자체는 CAN Frame을 송신하지 않습니다.",
            ]
            if unresolved:
                msg += ["", "미해결 입력 예:", *unresolved[:5]]
            messagebox.showinfo("Runtime Bridge 사전 생성 완료", "\n".join(msg))
        except Exception as e:
            self._txrx_log(f"[TXRX][BRIDGE][PREPARE][ERROR] {type(e).__name__}: {e}\n")
            messagebox.showerror("Runtime Bridge 사전 생성 실패", str(e))

    def _txrx_generate_canalyzer_capl_bridge(self):
        if not STIMULUS_AVAILABLE or _stimulus is None:
            messagebox.showerror("CAPL Bridge 생성 불가", f"Stimulus 모듈 없음: {STIMULUS_IMPORT_ERROR or '-'}")
            return
        try:
            profile = self._profile_for_capl_bridge_generation()
            resolver = self._build_stimulus_dbc_resolver()
            if resolver is None:
                raise ValueError("Vector CAPL Bridge 생성에는 대상 CAN의 DBC 설정이 필요합니다.")
            out_dir = Path(getattr(self, "_app_dir", Path.cwd())) / "vector_capl_bridge"
            paths = _stimulus.generate_vector_capl_bridges(profile, resolver, out_dir, revision="rev87")
            mapping, _db_by_ch, _signature, _cached = self._get_txrx_cached_dbc_map()
            channel_by_logical = {str(x.logical_can).strip().upper(): int(x.channel) for x in profile.candidates}
            identified_paths: List[str] = []
            for raw in paths:
                src = Path(raw)
                m = re.search(r"PF_Stimulus_Bridge_(CAN\d+)_rev87\.can$", src.name, re.IGNORECASE)
                if not m:
                    identified_paths.append(str(src))
                    continue
                logical = m.group(1).upper()
                channel = int(channel_by_logical.get(logical, int(re.sub(r"\D", "", logical) or "1")))
                dbc_path = str((mapping or {}).get(channel) or "").strip()
                if not dbc_path or not Path(dbc_path).is_file():
                    raise ValueError(f"{logical}/CAN{channel}의 DBC 경로가 유효하지 않습니다: {dbc_path or '-'}")
                dbc_id = self._txrx_dbc_id_from_path(dbc_path)
                self._txrx_stamp_bridge_identity(src, logical, channel, dbc_path)
                named = self._txrx_named_active_bridge_path(logical, dbc_id)
                runtime = self._txrx_active_bridge_path(logical)
                shutil.copyfile(src, named)
                shutil.copyfile(named, runtime)
                self._txrx_verify_active_bridge_identity(runtime, logical, channel, dbc_path)
                identified_paths.extend([str(named), str(runtime)])
            self.txrx_manual_candidate_status_var.set(f"CAPL Bridge 생성 {len(paths)} CAN")
            self._txrx_log("[STIMULUS][CAPL] DBC 식별 Bridge 생성: " + " | ".join(identified_paths) + "\n")
            messagebox.showinfo(
                "Vector CAPL Bridge 생성 완료",
                "\n".join([
                    f"대상 CAN {len(paths)}개 Bridge 생성 완료",
                    *[f"- {x}" for x in identified_paths],
                    "",
                    "rev87은 로컬 DBC 파일명에서 DBC ID를 자동 추출하여 CANx_<DBC_ID>_ACTIVE.can을 생성합니다.",
                    "CANoe/CANalyzer Network Node는 패키지 밖 PF_Stimulus_Runtime의 CANx_ACTIVE.can에 최초 1회만 연결하면 이후 버전에서도 유지됩니다.",
                    "두 파일에는 현재 DBC의 SHA256이 기록되며 Compile 전 정합성을 확인합니다.",
                    "PassFail은 Vector Configuration을 자동 수정하지 않습니다.",
                ]),
            )
        except Exception as e:
            self.txrx_manual_candidate_status_var.set("CAPL Bridge 생성 실패")
            self._txrx_log(f"[STIMULUS][CAPL][BLOCK] {e}\n")
            messagebox.showerror("Vector CAPL Bridge 생성 실패", str(e))

    def _manual_candidate_dbc_preflight(self, profile):
        """DBC가 있으면 후보 존재/CRC·Alive sibling을 확인한다. DBC가 없으면 COM validate가 최종 존재검사를 담당한다."""
        notes: List[str] = []
        crc_messages: List[str] = []
        missing: List[str] = []
        try:
            mapping, db_by_ch, _signature, _cached = self._get_txrx_cached_dbc_map()
        except Exception as e:
            notes.append(f"DBC 사전검사 생략: {type(e).__name__}: {e}")
            return notes, crc_messages, missing

        for item in profile.candidates:
            db = db_by_ch.get(int(item.channel))
            if db is None:
                notes.append(f"{item.logical_can}: DBC 없음 - Vector COM에서 직접 확인")
                continue
            try:
                msg = db.get_message_by_name(str(item.message))
            except Exception:
                missing.append(f"{item.logical_can}: Message 없음 {item.message}")
                continue
            try:
                sig = msg.get_signal_by_name(str(item.signal))
            except Exception:
                sig = None
            if sig is None:
                missing.append(f"{item.logical_can}: Signal 없음 {item.message}.{item.signal}")
            suspicious = self._detect_crc_alive_signals(msg)
            if suspicious:
                crc_messages.append(
                    f"{item.logical_can} {item.message}: " + ", ".join(sorted(set(suspicious)))
                )
        return notes, sorted(set(crc_messages)), missing

    def _prepare_manual_candidate_static_validation(self):
        """rev87 후보 검증: DBC 정적 검사 전용. Vector COM/Measurement/GetFunction을 호출하지 않는다."""
        profile = self._parse_manual_stimulus_candidates()
        notes, crc_messages, missing = self._manual_candidate_dbc_preflight(profile)
        if missing:
            raise ValueError("DBC 후보 검증 실패:\n- " + "\n- ".join(missing))
        if crc_messages and not bool(self.txrx_manual_crc_override_var.get()):
            raise ValueError(
                "DBC에서 CRC/Alive/Counter류 Signal이 같은 Message에 존재합니다.\n"
                "rev87은 이를 자동 계산하지 않습니다. 우선 현재 후보만 시험하려면 "
                "[CRC/Alive/Counter 경고가 있어도 시험 허용]을 직접 체크해야 합니다.\n\n- "
                + "\n- ".join(crc_messages)
            )
        resolver = self._build_stimulus_dbc_resolver()
        backend_mode = self._canoe_backend_mode_key()
        function_names = []
        if backend_mode == "capl":
            if resolver is None:
                raise ValueError("CAPL Frame 정적 검증에는 대상 CAN의 DBC 설정이 필요합니다.")
            function_names = _stimulus.capl_function_names_for_group(profile, resolver)
        checked_items = []
        for item in profile.candidates:
            checked_items.append({
                "logical_can": item.logical_can,
                "channel": int(item.channel),
                "message": item.message,
                "signal": item.signal,
                "active_value": _stimulus.coerce_numeric_value(item.active_value),
                "original_value": "실행 직전 확인",
            })
        checked = {
            "backend": "CAPL Frame (실행 시 Measurement.OnInit binding)" if backend_mode == "capl" else "CANoe Signal.Value (IL driver 필요)",
            "backend_kind": backend_mode,
            "product": "Vector",
            "hold_sec": float(profile.hold_sec),
            "items": checked_items,
            "capl_function_names": function_names,
        }
        return profile, checked, notes, crc_messages

    def _txrx_validate_manual_candidates_ui(self):
        try:
            profile, checked, notes, crc_messages = self._prepare_manual_candidate_static_validation()
            lines = [
                f"후보 {len(checked.get('items', []))}개 / Hold {checked.get('hold_sec')} sec "
                f"(전체 CAPL 입력: DBC nominal cycle의 1/10 반복, 최소 10ms)",
                "※ rev87 후보 검증은 DBC 정적 검사만 수행합니다. Measurement/COM/CAPL GetFunction은 시작하지 않습니다.",
                "※ 예: 200ms Message는 20ms로 반복 송신합니다. 기존 차량 송신원을 차단하지 않으며 CRC/Alive/E2E를 자동 계산하지 않습니다.",
            ]
            for item in checked.get("items", []):
                lines.append(
                    f"- {item['logical_can']} {item['message']}.{item['signal']}: "
                    f"현재=실행 직전 확인 → 입력={item['active_value']}"
                )
            if checked.get("backend_kind") == "capl":
                lines.append(f"CAPL OnInit 함수 준비 대상: {len(checked.get('capl_function_names') or [])}개")
            if crc_messages:
                lines.append("CRC/Alive/Counter 경고(자동 계산 안 함):")
                lines.extend(f"- {x}" for x in crc_messages)
            lines.extend(notes)
            self.txrx_manual_validation_cache = {
                "fingerprint": self._manual_profile_fingerprint(profile),
                "checked": checked,
                "notes": notes,
                "crc_messages": crc_messages,
                "product": "Vector",
            }
            self.txrx_manual_candidate_status_var.set(f"수동 후보: 정적 검증 OK ({len(checked.get('items', []))}개)")
            self._txrx_log("[STIMULUS][MANUAL][STATIC-CHECK] " + " | ".join(lines) + "\n")
            messagebox.showinfo("수동 후보 정적 검증 완료", "\n".join(lines))
        except Exception as e:
            self.txrx_manual_validation_cache = None
            self.txrx_manual_candidate_status_var.set("수동 후보: 검증 실패")
            self._txrx_log(f"[STIMULUS][MANUAL][BLOCK] {e}\n")
            messagebox.showerror("수동 후보 검증 실패", str(e))

    def _txrx_manual_candidate_test_once(self):
        """rev87: 무거운 재검증은 UI thread에서 반복하지 않고, 실제 COM은 worker-owned connection으로 수행한다."""
        if not bool(self.txrx_stimulus_enable_var.get()):
            messagebox.showwarning("Stimulus 비활성", "[실험용 Stimulus 사용]을 먼저 체크하세요.")
            return
        if self.txrx_stimulus_thread is not None and self.txrx_stimulus_thread.is_alive():
            messagebox.showinfo("Stimulus 실행 중", "이미 Stimulus 입력 테스트가 진행 중입니다.")
            return
        busy_reason = self._txrx_pf_worker_busy_reason()
        if busy_reason:
            self.txrx_manual_candidate_status_var.set("수동 후보: 이전 판정 종료 대기")
            messagebox.showinfo(
                "이전 판정 종료 대기",
                f"{busy_reason}입니다.\n다중/단일 판정 worker가 완전히 종료된 뒤 다시 실행하세요. "
                "rev87에서는 COM 충돌을 피하기 위해 실제 Stimulus를 동시에 시작하지 않습니다.",
            )
            return
        try:
            profile = self._parse_manual_stimulus_candidates()
            fingerprint = self._manual_profile_fingerprint(profile)
        except Exception as e:
            messagebox.showerror("후보 묶음 테스트 실행 불가", str(e))
            return
        cache = self.txrx_manual_validation_cache or {}
        if cache.get("fingerprint") != fingerprint:
            self.txrx_manual_candidate_status_var.set("수동 후보: 재검증 필요")
            messagebox.showwarning(
                "후보 검증 필요",
                "후보 내용/DBC/Hold 값이 마지막 검증 이후 변경되었거나 검증 기록이 없습니다.\n"
                "[후보 검증]을 한 번 실행한 뒤 다시 눌러주세요. rev87에서는 실행 버튼에서 무거운 검증을 다시 반복하지 않습니다.",
            )
            return
        checked = cache.get("checked") or {}
        crc_messages = cache.get("crc_messages") or []
        product = str(cache.get("product") or checked.get("product") or "")
        if crc_messages and not bool(self.txrx_manual_crc_override_var.get()):
            messagebox.showerror(
                "CRC/Alive 경고 확인 필요",
                "DBC에 CRC/Alive/Counter류 Signal이 있습니다. [CRC/Alive/Counter 경고가 있어도 시험 허용]을 직접 체크하세요.",
            )
            return
        if "CAPL" in str(checked.get("backend") or "") and not bool(self.txrx_canalyzer_source_isolated_var.get()):
            messagebox.showerror(
                "CAPL Frame 송신원 분리 확인 필요",
                "CAPL 실제 송신 전 동일 Message의 기존 ECU/Generator 송신원 분리·비활성 확인을 체크하세요.",
            )
            return

        detail = [
            f"{item['logical_can']}  {item['message']}.{item['signal']}  {item['original_value']} → {item['active_value']}"
            for item in checked.get('items', [])
        ]
        crc_note = ""
        if crc_messages:
            crc_note = (
                "\n\n※ DBC에 CRC/Alive/Counter가 감지되었지만 사용자가 경고를 허용했습니다. "
                "rev87는 CRC/Alive를 계산하거나 갱신하지 않으므로 ECU가 이 입력을 무시할 수 있습니다."
            )
        backend = str(checked.get("backend") or "")
        backend_note = (
            f"\n\nBackend: {backend}\n실제 CAN Frame을 송신하며 Hold 종료/중단 시 baseline release Frame을 송신합니다."
            if "CAPL" in backend else
            "\n\nBackend: CANoe Signal.Value (IL driver 필요)\n실행 worker가 Signal.Value를 적용하지만 Interaction Layer signal driver가 없으면 실제 Frame은 송신되지 않습니다."
        )
        confirm = (
            "[rev87 수동 후보 Signal 묶음 1회 테스트]\n\n"
            + "\n".join(detail)
            + f"\n\nHold: {checked.get('hold_sec')} sec"
            + backend_note + crc_note
            + "\n\n※ 후보 검증은 정적 검사만 수행했습니다. 현재값/CAPL 함수는 실제 실행 worker가 Measurement.OnInit/실행 직전에 확인합니다.\n\n실행할까요?"
        )
        if not messagebox.askyesno("수동 후보 묶음 입력 확인", confirm):
            self._txrx_log("[STIMULUS][MANUAL] 사용자 취소\n")
            return

        mapping = self._collect_dbc_mapping()
        worker_bus_name = self.bus_name_var.get().strip() or "CAN"
        worker_product = self.vector_product_var.get().strip() or "자동"
        worker_canoe_backend_mode = self._canoe_backend_mode_key()
        auto_stop_after = bool(self.txrx_stop_measurement_after_stimulus_var.get())
        source_isolation_confirmed = bool(self.txrx_canalyzer_source_isolated_var.get())
        log_verify_response_groups: List[Dict[str, Any]] = []
        try:
            _, selected_cond_for_log = self._get_txrx_selected_condition()
            input_pairs = {
                (str(getattr(x, "message", "") or ""), str(getattr(x, "signal", "") or ""))
                for x in list(getattr(selected_cond_for_log, "input_conditions", []) or [])
            } if selected_cond_for_log is not None else set()
            manual_pairs = {(str(x.message), str(x.signal)) for x in list(profile.candidates or [])}
            if selected_cond_for_log is not None and input_pairs.intersection(manual_pairs):
                log_verify_response_groups = self._txrx_build_log_verify_response_groups(selected_cond_for_log)
        except Exception:
            log_verify_response_groups = []
        stimulus_wall_start_ts = time.time()
        try:
            log_verify_dir = str(self.log_dir_var.get() or "").strip()
        except Exception:
            log_verify_dir = ""
        self.txrx_stimulus_stop_event.clear()
        self.txrx_stimulus_status_var.set("Stimulus: worker 연결/실행 준비 중")
        self.txrx_manual_candidate_status_var.set("수동 후보: 실행 준비 중")
        self.txrx_status_var.set("수동 후보 Stimulus 준비 중")
        self._txrx_log(
            f"[STIMULUS][MANUAL] PREPARE name={profile.name}, items={len(profile.candidates)}, hold={profile.hold_sec}s, worker-owned COM=ON\n"
        )

        def worker():
            worker_client = None
            result = None
            worker_error = None
            stop_ok = None
            stop_error = ""
            measurement_restarted_for_stimulus = False
            try:
                worker_client = core.CANoeClient(bus_name=worker_bus_name, product_preference=worker_product).connect(
                    expected_version_keyword=None, expected_exe_keyword=None
                )
                db_by_ch = core.load_dbc_map(mapping) if mapping else {}
                def resolver(channel: int, message_name: str):
                    db = db_by_ch.get(int(channel))
                    if db is None:
                        return None
                    try:
                        return db.get_message_by_name(str(message_name))
                    except Exception:
                        return None
                product = self._vector_product_name(worker_client).lower()
                use_capl = product == "canalyzer" or (product == "canoe" and worker_canoe_backend_mode == "capl")
                measurement_restarted_for_stimulus = bool(use_capl)
                capl_registry = {}
                if use_capl:
                    names = _stimulus.capl_function_names_for_group(profile, resolver)
                    capl_registry = worker_client.start_measurement_with_capl_bindings(names, restart_if_running=True)
                elif not worker_client.is_measurement_running():
                    worker_client.start_measurement(wait_sec=0.0)
                trace_dir = Path(getattr(self, "_app_dir", Path.cwd())) / "stimulus_logs"
                executor = _stimulus.StimulusExecutor(
                    trace_dir=trace_dir, dbc_resolver=resolver, canoe_backend_mode=worker_canoe_backend_mode,
                    capl_function_registry=capl_registry,
                )
                result = executor.execute_group_once(worker_client, profile, stop_event=self.txrx_stimulus_stop_event)
            except Exception as e:
                worker_error = f"{type(e).__name__}: {e}"
            finally:
                if auto_stop_after and worker_client is not None:
                    try:
                        worker_client.stop_measurement()
                        stop_ok = True
                    except Exception as e:
                        stop_ok = False
                        stop_error = f"{type(e).__name__}: {e}"
                if result is not None:
                    setattr(result, "measurement_stop_requested", auto_stop_after)
                    setattr(result, "measurement_stop_ok", stop_ok)
                    setattr(result, "measurement_stop_error", stop_error)
                    setattr(result, "stimulus_wall_start_ts", stimulus_wall_start_ts)
                    setattr(result, "stimulus_wall_end_ts", time.time())
                    setattr(result, "stimulus_measurement_restarted", measurement_restarted_for_stimulus)
                    setattr(result, "log_verify_dir", log_verify_dir)
                    setattr(result, "log_verify_mapping", dict(mapping))
                    setattr(result, "log_verify_response_groups", list(log_verify_response_groups))
                    setattr(result, "log_verify_source_isolation_confirmed", source_isolation_confirmed)
                    self.txrx_async_queue.put(("MANUAL_DONE", result))
                else:
                    suffix = f" / Measurement Stop 실패: {stop_error}" if stop_error else ""
                    self.txrx_async_queue.put(("MANUAL_ERROR", f"{worker_error or 'Stimulus worker 실패'}{suffix}"))

        self.txrx_stimulus_thread = threading.Thread(target=worker, daemon=True)
        self.txrx_stimulus_thread.start()

    def _finish_txrx_manual_stimulus_error(self, message: str):
        try:
            self.txrx_stimulus_status_var.set("Stimulus: 오류")
            self.txrx_manual_candidate_status_var.set("수동 후보: 오류")
            self.txrx_status_var.set("수동 후보 테스트 오류")
            self._txrx_log(f"[STIMULUS][MANUAL][ERROR] {message}\n")
            messagebox.showerror("후보 묶음 테스트 오류", message)
        finally:
            self.txrx_stimulus_thread = None
            self.txrx_stimulus_stop_event.clear()

    def _finish_txrx_manual_stimulus(self, result):
        try:
            restored = all(x.restore_ok for x in (result.items or []) if x.write_ok)
            if result.ok and restored:
                status = "중단 후 원복" if result.stopped_early else "완료/원복"
                if "Signal.Value" in str(getattr(result, "backend", "") or ""):
                    status += " (실제 TX 별도확인)"
                self.txrx_stimulus_status_var.set(f"Stimulus: {status}")
                self.txrx_manual_candidate_status_var.set(f"수동 후보: {status}")
                self.txrx_status_var.set(f"수동 후보 테스트 {status}")
            else:
                self.txrx_stimulus_status_var.set("Stimulus: 오류")
                self.txrx_manual_candidate_status_var.set("수동 후보: 오류/원복 확인")
                self.txrx_status_var.set("수동 후보 테스트 오류")
            for item in result.items or []:
                self._txrx_log(
                    f"[STIMULUS][MANUAL][ITEM] {item.logical_can} "
                    f"{item.message}.{item.signal}: original={item.original_value}, active={item.active_value}, "
                    f"readback={item.active_readback}, restored={item.restored_value}, "
                    f"hold_mode={getattr(item, 'hold_mode', '-') or '-'}, "
                    f"tx_interval_ms={getattr(item, 'tx_interval_ms', 0) or 0:g}, "
                    f"write_ok={item.write_ok}, restore_ok={item.restore_ok}, error={item.error or '-'}\n"
                )
            stop_req = bool(getattr(result, "measurement_stop_requested", False))
            stop_ok = getattr(result, "measurement_stop_ok", None)
            stop_err = str(getattr(result, "measurement_stop_error", "") or "")
            if stop_req and stop_ok is True:
                try:
                    self.measurement_status_var.set("Measurement: 정지")
                    self._refresh_status_badges()
                except Exception:
                    pass
            self._txrx_log(
                f"[STIMULUS][MANUAL] END ok={result.ok}, stopped={result.stopped_early}, "
                f"backend={getattr(result, 'backend', '-')}, frames={getattr(result, 'frame_count', 0)}, "
                f"hold_mode={getattr(result, 'hold_mode', '-') or '-'}, "
                f"tx_interval_ms={getattr(result, 'tx_interval_ms', 0) or 0:g}, restore_ok={result.restore_ok}, "
                f"measurement_stop={stop_ok if stop_req else '미요청'}, stop_error={stop_err or '-'}, error={result.error or '-'}, trace={result.trace_path or '-'}\n"
            )
            self.txrx_last_stimulus_result = result
            if bool(self.txrx_log_verify_enabled_var.get()):
                self._start_txrx_stimulus_log_verification(result)
            if stop_req and stop_ok is False:
                messagebox.showwarning("Measurement Stop 확인 필요", f"Stimulus 원복 후 Measurement Stop에 실패했습니다.\n{stop_err or '-'}")
            if not restored:
                messagebox.showerror(
                    "수동 후보 원복 확인 필요",
                    "후보 묶음 입력 후 일부 Signal의 시작 전 값 복원이 확인되지 않았습니다.\n"
                    "Vector Trace와 실제 차량 상태를 즉시 확인하세요.\n\n"
                    f"{result.error or '-'}",
                )
            elif result.error:
                messagebox.showwarning("후보 묶음 테스트 완료(오류 있음)", result.error)
        finally:
            self.txrx_stimulus_thread = None
            self.txrx_stimulus_stop_event.clear()

    def _txrx_send_not_implemented(self):
        messagebox.showinfo(
            "일반 송신 비활성",
            "rev87에서도 일반 CAN 송신/로그 Replay 자동화는 활성화하지 않습니다.\n\n"
            "실제 입력 PoC는 별도 oracle_checker_stimulus_rev87.py 모듈의 [입력 1회 테스트] 또는 "
            "[수동 후보 Signal 묶음 테스트]만 허용합니다.",
        )

    def _txrx_stop_stimulus(self):
        """현재 1회 Stimulus hold를 중단시킨다. worker의 finally에서 원래 값으로 복원된다."""
        try:
            self.txrx_stimulus_stop_event.set()
            self.txrx_stimulus_status_var.set("Stimulus: 중단/원복 요청")
            self._txrx_log("[STIMULUS] 즉시 중단/원복 요청\n")
        except Exception as e:
            self._txrx_log(f"[STIMULUS][WARN] 중단 요청 실패: {e}\n")

    def _build_selected_stimulus_profile(self):
        if not STIMULUS_AVAILABLE or _stimulus is None:
            raise RuntimeError(
                "oracle_checker_stimulus_rev87.py를 사용할 수 없습니다. "
                f"기존 Pass/Fail은 정상 사용 가능합니다. import={STIMULUS_IMPORT_ERROR or '-'}"
            )
        idx, cond = self._get_txrx_selected_condition()
        if cond is None or idx is None:
            raise ValueError("차량 송수신 테스트할 TC를 먼저 선택하세요.")
        if self._is_safety_excluded_tc(cond):
            raise ValueError("rev87 Stimulus PoC에서는 제동/조향/구동/에어백/충전/ADAS 등 안전 영향 TC 입력을 차단합니다.")

        inputs = list(getattr(cond, "input_conditions", []) or [])
        if len(inputs) != 1:
            raise ValueError(f"rev87 Stimulus PoC는 입력 조건이 정확히 1개인 TC만 허용합니다. 현재={len(inputs)}개")

        analysis = self.txrx_analysis_by_index.get(idx)
        if analysis is None:
            analysis = self._analyze_condition_txrx(cond)
            self.txrx_analysis_by_index[idx] = analysis
            self._refresh_txrx_tree()

        input_rows = analysis.get("input_rows", []) or []
        if len(input_rows) != 1:
            raise ValueError("입력 조건 정적 분석 결과가 1개가 아니어서 실행을 차단합니다.")
        row = input_rows[0]
        if row.get("status") == self.TXRX_STATUS_BAD:
            raise ValueError(f"입력 정적 분석이 불가 상태입니다: {row.get('reason', '-')}")
        if row.get("crc_alive"):
            raise ValueError("CRC/Alive/Counter류 Signal이 포함된 Message는 rev87 직접 Signal 입력 대상에서 제외합니다.")
        found = [x for x in (row.get("locations") or []) if x.get("signal_found")]
        candidates = self._set_txrx_or_can_candidates(found)
        if not candidates:
            raise ValueError("Message/Signal을 송신할 CANoe 논리 CAN 후보가 없습니다.")
        chosen = self._selected_txrx_or_can_location(candidates)
        if chosen is None:
            raise ValueError("송신할 논리 CAN 후보를 선택하지 못했습니다.")

        exp = inputs[0]
        hold_sec = self._effective_stimulus_hold_sec([(str(getattr(exp, "message", "") or ""), str(getattr(exp, "signal", "") or ""))])
        channel_value = int(chosen["channel"])
        channel_label = str(chosen.get("channel_label") or self._ch_label_for_int(channel_value))
        logical_can = channel_label.split("/", 1)[0] if channel_label.upper().startswith("CAN") else f"CAN{channel_value}"
        profile = _stimulus.StimulusProfile(
            tc_no=str(getattr(cond, "tc_no", "") or ""),
            channel=channel_value,
            message=str(getattr(exp, "message", "") or "").strip(),
            signal=str(getattr(exp, "signal", "") or "").strip(),
            active_value=getattr(exp, "expected_value_raw", None),
            hold_sec=hold_sec,
            bus_name="CAN",
            source="Oracle input condition / TXRX selected TC",
            logical_can=logical_can,
        )
        return idx, cond, analysis, row, profile

    def _txrx_stimulus_test_once(self):
        if not bool(self.txrx_stimulus_enable_var.get()):
            messagebox.showwarning(
                "Stimulus 비활성",
                "실험용 입력은 기본 OFF입니다.\n[실험용 Stimulus 사용]을 직접 체크한 뒤 다시 실행하세요.",
            )
            return
        if self.txrx_stimulus_thread is not None and self.txrx_stimulus_thread.is_alive():
            messagebox.showinfo("Stimulus 실행 중", "이미 입력 1회 테스트가 진행 중입니다.")
            return
        busy_reason = self._txrx_pf_worker_busy_reason()
        if busy_reason:
            messagebox.showinfo(
                "이전 판정 종료 대기",
                f"{busy_reason}입니다.\n다중/단일 판정 worker가 완전히 종료된 뒤 다시 실행하세요. "
                "rev87에서는 COM 충돌을 피하기 위해 실제 Stimulus를 동시에 시작하지 않습니다.",
            )
            return

        try:
            idx, cond, analysis, input_row, profile = self._build_selected_stimulus_profile()
            active = _stimulus.coerce_numeric_value(profile.active_value)
            checked = {
                "original_value": "실행 직전 확인",
                "active_value": active,
                "hold_sec": float(profile.hold_sec),
                "backend": "CAPL Frame (실행 시 Measurement.OnInit binding)" if self._canoe_backend_mode_key() == "capl" else "CANoe Signal.Value (IL driver 필요)",
            }
            if self._canoe_backend_mode_key() == "capl" and not bool(self.txrx_canalyzer_source_isolated_var.get()):
                raise ValueError("CAPL 실제 송신 전 동일 Message 기존 ECU/Generator 송신원 분리·비활성 확인을 체크하세요.")
        except Exception as e:
            self.txrx_stimulus_status_var.set("Stimulus: 실행 차단")
            self._txrx_log(f"[STIMULUS][BLOCK] {e}\n")
            messagebox.showerror("입력 1회 테스트 실행 불가", str(e))
            return

        physical_note = ""
        if self._is_physical_or_switch_tc(cond):
            physical_note = (
                "\n\n※ 이 TC는 Seat/Switch/Button 등 물리 입력 가능성이 있는 항목입니다. "
                "CAN Signal/CAPL 입력만으로 실제 물리 조작이 재현되지 않을 수 있습니다."
            )
        confirm_text = (
            "[rev87 실험용 Stimulus 1회 테스트]\n\n"
            f"TC: {profile.tc_no}\n"
            f"대상: CAN{profile.channel} / {profile.message} / {profile.signal}\n"
            f"시작 전 값: {checked.get('original_value')}\n"
            f"입력 값: {checked.get('active_value')}\n"
            f"Hold: {checked.get('hold_sec')} sec\n\n"
            f"Backend: {checked.get('backend', '-')}\n"
            "실행 후 성공/오류/중단 여부와 무관하게 시작 전 상태로 복원을 시도합니다.\n"
            "CAPL backend는 실제 Frame을 송신하므로 동일 Message ID의 기존 ECU/Generator 송신원이 반드시 분리/비활성되어야 합니다. "
            "CANoe Signal.Value 모드는 Interaction Layer signal driver가 없으면 Write 창 01-0083 경고와 함께 실제 Frame이 송신되지 않을 수 있습니다."
            + physical_note
            + "\n\n실행할까요?"
        )
        if not messagebox.askyesno("실험용 입력 확인", confirm_text):
            self._txrx_log("[STIMULUS] 사용자 취소\n")
            return

        self.txrx_stimulus_stop_event.clear()
        self.txrx_stimulus_status_var.set("Stimulus: 실행 중")
        self.txrx_status_var.set(f"입력 1회 테스트: {profile.tc_no}")
        self._txrx_log(
            f"[STIMULUS] START TC={profile.tc_no}, Ch={profile.channel}, "
            f"{profile.message}.{profile.signal}={checked.get('active_value')}, hold={checked.get('hold_sec')}s, "
            f"original={checked.get('original_value')}\n"
        )

        worker_bus_name = self.bus_name_var.get().strip() or "CAN"
        worker_product = self.vector_product_var.get().strip() or "자동"
        worker_canoe_backend_mode = self._canoe_backend_mode_key()
        auto_stop_after = bool(self.txrx_stop_measurement_after_stimulus_var.get())
        stimulus_wall_start_ts = time.time()
        try:
            log_verify_dir = str(self.log_dir_var.get() or "").strip()
        except Exception:
            log_verify_dir = ""
        mapping = self._collect_dbc_mapping()
        source_isolation_confirmed = bool(self.txrx_canalyzer_source_isolated_var.get())
        try:
            log_verify_response_groups = self._txrx_build_log_verify_response_groups(cond)
        except Exception:
            log_verify_response_groups = []

        def worker():
            worker_client = None
            result = None
            worker_error = None
            stop_ok = None
            stop_error = ""
            measurement_restarted_for_stimulus = False
            try:
                # rev87: pywin32 COM 객체는 생성 스레드에서만 사용한다. 실제 Stimulus worker가 자체 재연결한다.
                worker_client = core.CANoeClient(bus_name=worker_bus_name, product_preference=worker_product).connect(
                    expected_version_keyword=None, expected_exe_keyword=None
                )
                db_by_ch = core.load_dbc_map(mapping) if mapping else {}
                def resolver(channel: int, message_name: str):
                    db = db_by_ch.get(int(channel))
                    if db is None:
                        return None
                    try:
                        return db.get_message_by_name(str(message_name))
                    except Exception:
                        return None
                product = self._vector_product_name(worker_client).lower()
                use_capl = product == "canalyzer" or (product == "canoe" and worker_canoe_backend_mode == "capl")
                measurement_restarted_for_stimulus = bool(use_capl)
                capl_registry = {}
                if use_capl:
                    names = _stimulus.capl_function_names_for_single(profile, resolver)
                    capl_registry = worker_client.start_measurement_with_capl_bindings(names, restart_if_running=True)
                elif not worker_client.is_measurement_running():
                    worker_client.start_measurement(wait_sec=0.0)
                trace_dir = Path(getattr(self, "_app_dir", Path.cwd())) / "stimulus_logs"
                worker_executor = _stimulus.StimulusExecutor(
                    trace_dir=trace_dir, dbc_resolver=resolver, canoe_backend_mode=worker_canoe_backend_mode,
                    capl_function_registry=capl_registry,
                )
                result = worker_executor.execute_once(worker_client, profile, stop_event=self.txrx_stimulus_stop_event)
            except Exception as e:
                worker_error = f"{type(e).__name__}: {e}"
            finally:
                if auto_stop_after and worker_client is not None:
                    try:
                        worker_client.stop_measurement()
                        stop_ok = True
                    except Exception as e:
                        stop_ok = False
                        stop_error = f"{type(e).__name__}: {e}"
                if result is not None:
                    setattr(result, "measurement_stop_requested", auto_stop_after)
                    setattr(result, "measurement_stop_ok", stop_ok)
                    setattr(result, "measurement_stop_error", stop_error)
                    setattr(result, "stimulus_wall_start_ts", stimulus_wall_start_ts)
                    setattr(result, "stimulus_wall_end_ts", time.time())
                    setattr(result, "stimulus_measurement_restarted", measurement_restarted_for_stimulus)
                    setattr(result, "log_verify_dir", log_verify_dir)
                    setattr(result, "log_verify_mapping", dict(mapping))
                    setattr(result, "log_verify_response_groups", list(log_verify_response_groups))
                    setattr(result, "log_verify_source_isolation_confirmed", source_isolation_confirmed)
                    self.txrx_async_queue.put(("SINGLE_DONE", result))
                else:
                    suffix = f" / Measurement Stop 실패: {stop_error}" if stop_error else ""
                    self.txrx_async_queue.put(("SINGLE_ERROR", f"{worker_error or 'Stimulus worker 실패'}{suffix}"))

        self.txrx_stimulus_thread = threading.Thread(target=worker, daemon=True)
        self.txrx_stimulus_thread.start()

    def _finish_txrx_stimulus_worker_error(self, message: str):
        try:
            self.txrx_stimulus_status_var.set("Stimulus: 오류")
            self.txrx_status_var.set("입력 1회 테스트 오류")
            self._txrx_log(f"[STIMULUS][ERROR] worker-owned COM 실행 실패: {message}\n")
            messagebox.showerror("입력 1회 테스트 오류", message)
        finally:
            self.txrx_stimulus_thread = None
            self.txrx_stimulus_stop_event.clear()

    def _finish_txrx_stimulus(self, result):
        try:
            if result.ok and result.restore_ok:
                status = "중단 후 원복" if result.stopped_early else "완료/원복"
                if "Signal.Value" in str(getattr(result, "backend", "") or ""):
                    status += " (실제 TX 별도확인)"
                self.txrx_stimulus_status_var.set(f"Stimulus: {status}")
                self.txrx_status_var.set(f"입력 1회 테스트 {status}")
            else:
                self.txrx_stimulus_status_var.set("Stimulus: 오류")
                self.txrx_status_var.set("입력 1회 테스트 오류")
            stop_req = bool(getattr(result, "measurement_stop_requested", False))
            stop_ok = getattr(result, "measurement_stop_ok", None)
            stop_err = str(getattr(result, "measurement_stop_error", "") or "")
            if stop_req and stop_ok is True:
                try:
                    self.measurement_status_var.set("Measurement: 정지")
                    self._refresh_status_badges()
                except Exception:
                    pass
            self._txrx_log(
                f"[STIMULUS] END ok={result.ok}, stopped={result.stopped_early}, "
                f"active_readback={result.active_readback}, restored={result.restored_value}, "
                f"backend={getattr(result, 'backend', '-')}, frames={getattr(result, 'frame_count', 0)}, restore_ok={result.restore_ok}, "
                f"measurement_stop={stop_ok if stop_req else '미요청'}, stop_error={stop_err or '-'}, error={result.error or '-'}, trace={result.trace_path or '-'}\n"
            )
            self.txrx_last_stimulus_result = result
            if bool(self.txrx_log_verify_enabled_var.get()):
                self._start_txrx_stimulus_log_verification(result)
            if stop_req and stop_ok is False:
                messagebox.showwarning("Measurement Stop 확인 필요", f"Stimulus 원복 후 Measurement Stop에 실패했습니다.\n{stop_err or '-'}")
            if not result.restore_ok:
                messagebox.showerror(
                    "Stimulus 원복 확인 필요",
                    "입력 테스트 후 시작 전 값 자동 복원이 확인되지 않았습니다.\n"
                    "Vector Trace/실제 차량 상태를 즉시 확인하세요.\n\n"
                    f"{result.error or '-'}",
                )
            elif result.error:
                messagebox.showwarning("입력 테스트 완료(오류 있음)", result.error)
        finally:
            self.txrx_stimulus_thread = None
            self.txrx_stimulus_stop_event.clear()

    def _show_txrx_preview(self, idx: Optional[int]):
        if self.txrx_preview_text is None:
            return
        if idx is None or not (0 <= idx < len(getattr(self, "condition_rows", []))):
            self.txrx_selected_tc_var.set("선택 TC: -")
            self._write_txrx_preview([
                "TC를 선택하면 이곳에 자동 Stimulus와 PASS 조건을 표시합니다.",
                "상단 체크박스로 여러 TC를 선택한 뒤 '테스트 실행 준비' → '선택 TC 자동 P/F 실행' 순서로 사용합니다.",
            ])
            return
        row = self.condition_rows[idx]
        if not row.is_valid or row.condition is None:
            self.txrx_selected_tc_var.set("선택 TC: 유효하지 않음")
            self._write_txrx_preview([row.error_reason or "유효한 TC가 아닙니다."])
            return
        cond = row.condition
        self.txrx_selected_tc_var.set(f"선택 TC: {cond.tc_no} / {cond.subcategory}")
        analysis = self.txrx_analysis_by_index.get(idx)
        if analysis is None:
            try:
                analysis = self._analyze_condition_txrx(cond)
                self.txrx_analysis_by_index[idx] = analysis
            except Exception as e:
                analysis = {"summary": f"분석 오류: {e}", "input_rows": [], "output_rows": []}
        lines = [
            f"TC 번호: {cond.tc_no}",
            f"소분류: {cond.subcategory}",
            "",
            "[자동 송신 입력]",
        ]
        for i, exp in enumerate(cond.input_conditions or [], start=1):
            ra = self._find_row_analysis(analysis, "input_rows", i)
            lines.append(f"{i}. {exp.message}:{exp.signal} = {exp.expected_value_raw}  | CAN 후보 {ra.get('channel','-')}")
        if not cond.input_conditions:
            lines.append("-")
        lines += ["", "[PASS 조건 - 모두 한 번 이상 관측되어야 PASS]"]
        for i, exp in enumerate(cond.output_conditions or [], start=1):
            ra = self._find_row_analysis(analysis, "output_rows", i)
            lines.append(f"{i}. {exp.message}:{exp.signal} == {exp.expected_value_raw}  | CAN 후보 {ra.get('channel','-')}")
        if not cond.output_conditions:
            lines.append("- (자동 P/F 불가)")
        lines += [
            "",
            "[2안 의미]",
            "- PassFail이 외부 CAN Stimulus를 넣고 실제 차량 출력 Signal을 관찰하여 자동 PASS/FAIL을 판정합니다.",
            "- 기존 물리 스위치 ECU의 동일 Message 송신은 차단하지 않습니다.",
            "- 모든 CAPL 입력은 Hold 동안 DBC nominal cycle의 1/10 주기(최소 10ms)로 반복 송신합니다.",
            "- CRC/Alive/Counter/E2E는 자동 계산하지 않으며 관련 정보는 GUI 대신 AI 분석용 로그에 기록합니다.",
            f"- 분석: {analysis.get('summary','-')}",
            f"- 최근 자동 결과: {self.txrx_auto_result_by_index.get(idx, '-')}",
        ]
        detail = self.txrx_auto_detail_by_index.get(idx)
        if detail:
            lines += ["", "[최근 자동 판정 상세]"] + list(detail.get("lines") or [])
        self._write_txrx_preview(lines)

    def _find_row_analysis(self, analysis: Dict[str, Any], key: str, pos: int) -> Dict[str, Any]:
        for item in analysis.get(key, []) or []:
            if item.get("pos") == pos:
                return item
        return {}

    def _tag_for_txrx_status(self, status: str) -> str:
        if status == self.TXRX_STATUS_OK:
            return "ok"
        if status == self.TXRX_STATUS_WARN:
            return "warn"
        if status == self.TXRX_STATUS_BAD:
            return "bad"
        return ""

    def _write_txrx_preview(self, lines: List[str]):
        self.txrx_preview_text.configure(state="normal")
        self.txrx_preview_text.delete("1.0", tk.END)
        self.txrx_preview_text.insert("1.0", "\n".join(lines))
        self.txrx_preview_text.configure(state="normal")

    def _refresh_txrx_result_tree(self, rows: List[Tuple[str, str, str, str, str, str, str, str]]):
        if self.txrx_result_tree is None:
            return
        self.txrx_result_tree.delete(*self.txrx_result_tree.get_children())
        for i, (kind, msg, sig, exp, ch, status, reason, tag) in enumerate(rows, start=1):
            self.txrx_result_tree.insert(
                "",
                tk.END,
                iid=f"txrx:{i}",
                tags=(tag,) if tag else (),
                values=(kind, msg, sig, exp, ch, status, reason),
            )

    def _write_txrx_status_text(self, cond: Any, analysis: Dict[str, Any]):
        if self.txrx_status_text is None:
            return
        lines = [
            f"상태: {analysis.get('status', self.TXRX_STATUS_UNCHECKED)}",
            f"현재 송신 TC: {cond.tc_no}",
            f"송신 시작 시각: -",
            f"마지막 송신 시각: -",
            f"송신 횟수: -",
            "",
            "[자동화 방식 추천]",
            analysis.get("method") or self.TXRX_METHOD_UNKNOWN,
            analysis.get("method_reason") or "-",
            "",
            "[권장 프리테스트 정책 Preview]",
            f"출력 대기시간(sec): {self.txrx_wait_sec_var.get()}",
            f"TC 간 대기(sec): {self.txrx_between_tc_delay_var.get()}",
            f"Fail 처리: {self.txrx_fail_policy_var.get()}",
            f"송신 방식 후보: {self.txrx_tx_mode_var.get()}",
            f"송신 주기(ms) 후보: {self.txrx_period_ms_var.get()}",
            "",
            "[결과 해석]",
            "OK: 현재 자극 가설로 반응 확인 / NG: 기능 FAIL 확정이 아니라 입력조건·자극방식 보완 또는 수동 확인 필요",
            "",
            "[진단 요약]",
            analysis.get("summary") or "-",
            "",
            "[Stimulus 모듈]",
            self.txrx_stimulus_status_var.get(),
            "실제 Stimulus 동작은 독립 oracle_checker_stimulus_rev87.py에서만 수행",
        ]
        if analysis.get("errors"):
            lines.append("")
            lines.append("[불가 사유]")
            for item in analysis.get("errors", [])[:10]:
                lines.append(f"- {item}")
        if analysis.get("warnings"):
            lines.append("")
            lines.append("[확인 필요]")
            for item in analysis.get("warnings", [])[:10]:
                lines.append(f"- {item}")
        if analysis.get("bus_warning"):
            lines.append("")
            lines.append("[버스 주의 - 적합성 상태 강등 없음]")
            lines.append(f"- {analysis.get('bus_warning')}")

        self.txrx_status_text.configure(state="normal")
        self.txrx_status_text.delete("1.0", tk.END)
        self.txrx_status_text.insert("1.0", "\n".join(lines))
        self.txrx_status_text.configure(state="normal")
