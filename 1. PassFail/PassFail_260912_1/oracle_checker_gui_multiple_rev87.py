# -*- coding: utf-8 -*-
"""
oracle_checker_gui_multiple_rev87.py

목적
- Oracle Checker GUI에 "다중 실행" 탭을 추가하기 위한 mixin 모듈
- 단일 실행 GUI 코드는 oracle_checker_gui_onebyone_rev87.py에 유지
- front 모듈에서 MultipleExecutionMixin + OneByOne GUI를 조합하여 실행

기능
- 동일 Excel/DBC/CANoe 설정을 공유
- 여러 TC를 선택하여 동시감시 또는 순차실행 모드로 실행
- 출력 인정 기준: 입력 이후 / 세션 전체
- 동시감시는 선택된 TC들의 Message/Signal을 한 세션에서 동시에 polling
- 수행 완료 시 CANoe Measurement Stop 후 로그 재검토 시도
- rev34:
  * onebyone rev34와 정합 반영
  * input_conditions / input_results 구조 반영
  * Shift 클릭 범위 선택 지원
  * 전체 선택 / 전체 해제 유지
  * Start / 수행 완료 / 중단 버튼 가로 길이 동일 축소
- rev37:
  * rev36 기능 유지
  * 다중 실행 내부 연결도 실행 중인 CANoe/CANalyzer COM 객체 연결 방식으로 통일
- rev40:
  * onebyone rev40과 정합
  * 다중 실행 worker에서도 CANoe 15 고정 검증 제거
- rev44:
  * 목록 & 실행 탭 선택 음영 보강과 연동
  * 다중 실행 Start 버튼 카운트다운 문구를 one by one 방식으로 통일
  * 전체 선택/전체 선택 해제/중단/전체 초기화 버튼 배치 정리 및 전체 선택 토글화
  * Shift 범위 선택을 한 번 더 수행하면 해당 범위 선택 해제
  * 다중 실행 목록/결과 Treeview 열 폭 및 가운데 정렬 조정
  * 대량 선택 시 debounce 기반 갱신으로 전체 선택/해제 체감 렉 완화
- rev45:
  * [다중 TC 수행 시 로그 검토] 옵션과 연동
  * 다중 동시감시 종료 후 선택 TC 로그 일괄 재검토 결과를 최종 판정/다중 목록/결과 상세에 반영
  * 로그 재검토로 PASS 보정된 TC는 다중 목록 상태를 "로그 PASS"로 표시
  * 실시간 PASS는 로그 재검토 결과와 무관하게 최종 PASS 유지
  * 전체 선택/전체 선택 해제 버튼을 독립 동작으로 유지
  * Vector 연결은 GetActiveObject 우선 + guarded Dispatch fallback으로 통일
- rev87:
  * `전체 선택 해제` 버튼은 rev76 대비 약 30% 넓혀 width=13으로 조정
  * 초록색 실행 버튼 문구를 `선택 TC 다중 Start` → `선택 Start`로 단순화
  * Stimulus 모듈과 완전 분리; 다중 Pass/Fail 실행에는 실제 Signal write 경로 없음
  * 다중 목록의 체크 TC 하늘색 / PASS 초록색 행 음영을 명시적으로 보강
  * 다중 실행에서는 TC timeout에 의한 자동 종료/N/A 확정을 사용하지 않고, 전체 PASS 또는 사용자의 수행 완료/중단까지 감시 유지
  * rev49 기능 및 판정 정책 유지
  * Vector guarded 연결, 실시간 PASS 우선, 전체 선택/해제 독립 정책 유지
  * 다중 worker도 GUI의 자동/CANoe/CANalyzer 연결 대상 설정을 그대로 사용
  * 다중 실행 worker의 Vector CANoe/CANalyzer COM 재연결 실패 시 read-only 진단 TXT 자동 저장
  * 다중 TC 수행 탭도 onebyone 공통 X/Y scroll wrapper를 사용하여 작은 노트북에서 전체 영역 접근 가능
"""

from __future__ import annotations

import datetime as _dt
import queue
import threading
import time
import sys
import atexit
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, messagebox
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


class MultipleExecutionMixin:
    """단일 실행 GUI에 다중 실행 탭/동작을 덧붙이는 mixin."""

    def _build_ui(self):
        super()._build_ui()
        self._init_multi_state()
        self._build_multi_tab()
        self._move_detail_tab_after_multi_tab()
        self._poll_multi_queue()

    def _init_multi_state(self):
        self.multi_selected_indices = set()
        self.multi_anchor_index: Optional[int] = None
        self.multi_queue: queue.Queue = queue.Queue()
        self.multi_monitor_thread: Optional[threading.Thread] = None
        self.multi_stop_event = threading.Event()
        self.multi_done_event = threading.Event()
        self.multi_active = False
        self.multi_mode_var = tk.StringVar(value="동시감시")
        self.multi_output_rule_var = tk.StringVar(value="입력 이후")
        self.multi_selected_count_var = tk.StringVar(value="선택 TC: 0개")
        self.multi_status_var = tk.StringVar(value="대기중")
        self.multi_result_summary_var = tk.StringVar(value="PASS 0 / FAIL 0 / N/A 0 / ERROR 0 / 검토중 0")
        self.multi_result_status_by_index: Dict[int, str] = {}
        self.multi_final_result_by_index: Dict[int, Any] = {}
        self.multi_focus_index: Optional[int] = None
        self._multi_refresh_after_id = None
        self._multi_pending_status_by_index: Dict[int, str] = {}
        self._multi_signal_refresh_after_id = None
        self.multi_tc_tree = None
        self.multi_result_tree = None
        self.multi_detail_text = None
        self.multi_start_button = None
        self.multi_complete_button = None
        self.multi_abort_button = None
        self.multi_select_all_button = None
        self.multi_clear_button = None
        self.multi_reset_button = None
        self.multi_progress_var = tk.DoubleVar(value=0.0)
        self.multi_progress_text_var = tk.StringVar(value="진행도: 대기")
        self.multi_progress_bar = None

    def _move_detail_tab_after_multi_tab(self):
        """탭 순서를 설정 > 단일 TC 수행 > 다중 TC 수행 > 결과 상세 순서로 보정한다."""
        try:
            if self.notebook is not None and getattr(self, "detail_tab", None) is not None:
                self.notebook.insert("end", self.detail_tab)
        except Exception:
            pass

    def _build_multi_tab(self):
        if self.notebook is None:
            return

        self.multi_tab, self.multi_scroll_content = self._create_scrollable_notebook_tab("다중 TC 수행", padding=6)
        parent = self.multi_scroll_content
        # rev87 compact layout: left list is a constrained viewport; internal X scrollbar keeps full columns.
        parent.columnconfigure(0, weight=0, minsize=760)
        # rev87: 우측 전체 영역을 실제로 약 470px(기존 full-width 대비 약 60%)에 고정한다.
        # 이전 rev에서는 minsize만 지정하고 weight=1이라 남는 폭을 다시 먹어 체감상 줄지 않았다.
        parent.columnconfigure(1, weight=0, minsize=470)
        parent.rowconfigure(0, weight=1)

        # -----------------------------
        # 좌측: 다중 실행 TC 목록
        # -----------------------------
        left = ttk.LabelFrame(parent, text="다중 실행 TC 목록", width=760)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_propagate(False)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        columns = ("check", "tc_no", "subcategory", "input", "outputs", "timeout", "status")
        style = ttk.Style(self)
        style.configure("Multi.Treeview", background="#FFFFFF", fieldbackground="#FFFFFF")
        # Windows theme의 native selected 상태가 tag background를 덮지 않도록 선택색도 같은 계열로 고정한다.
        style.map("Multi.Treeview", background=[("selected", "#BFE3FF")], foreground=[("selected", "#0F172A")])
        self.multi_tc_tree = ttk.Treeview(
            left, columns=columns, show="headings", selectmode="none", style="Multi.Treeview"
        )
        headings = {
            "check": "선택",
            "tc_no": "TC 번호",
            "subcategory": "소분류",
            "input": "입력 조건",
            "outputs": "출력 조건",
            "timeout": "TC 대기(참고)",
            "status": "상태",
        }
        widths = {
            "check": 60,
            "tc_no": 90,
            "subcategory": 225,
            "input": 320,
            "outputs": 450,
            "timeout": 80,
            "status": 90,
        }
        anchors = {"check": "center", "tc_no": "center", "timeout": "center", "status": "center"}

        for c in columns:
            self.multi_tc_tree.heading(c, text=headings[c])
            self.multi_tc_tree.column(c, width=widths[c], anchor=anchors.get(c, "w"), stretch=False)

        self.multi_tc_tree.tag_configure("odd", background="#FFFFFF")
        self.multi_tc_tree.tag_configure("even", background="#F9FAFB")
        # rev87: 상태를 작은 화면/Windows theme에서도 한눈에 보이도록 약간 더 선명한 행 음영 사용.
        self.multi_tc_tree.tag_configure("selected", background="#BFE3FF", foreground="#0F3B66", font=("맑은 고딕", 9, "bold"))
        self.multi_tc_tree.tag_configure("pass", background="#C6F6D5", foreground="#166534", font=("맑은 고딕", 9, "bold"))
        self.multi_tc_tree.tag_configure("fail", background="#FECACA", foreground="#991B1B")
        self.multi_tc_tree.tag_configure("na", background="#FEF3C7", foreground="#92400E")
        self.multi_tc_tree.tag_configure("error", background="#FECACA", foreground="#991B1B")

        yscroll = ttk.Scrollbar(left, orient="vertical", command=self.multi_tc_tree.yview)
        xscroll = ttk.Scrollbar(left, orient="horizontal", command=self.multi_tc_tree.xview)
        self.multi_tc_tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.multi_tc_tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.multi_tc_tree.bind("<Button-1>", self._on_multi_tc_tree_click, add="+")

        # -----------------------------
        # 우측: 상단 설정 / 중간 상세 / 하단 결과
        # -----------------------------
        right = ttk.Frame(parent, width=470)
        right.grid(row=0, column=1, sticky="nsew")
        # 좌측 목록이 row 높이를 결정하므로 width propagation만 막아 우측 박스 폭을 470px로 유지한다.
        right.grid_propagate(False)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=0)
        right.rowconfigure(1, weight=0)
        right.rowconfigure(2, weight=2)
        right.rowconfigure(3, weight=3)

        control = ttk.LabelFrame(right, text="다중 실행 설정 / 상태")
        control.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        for i in range(4):
            control.columnconfigure(i, weight=0)
        control.columnconfigure(3, weight=1)

        # rev87: 내부 위젯의 폭은 대부분 유지하되, 한 줄에 몰아넣지 않고 2줄로 재배치해
        # 상위 박스 자체를 약 470px로 줄여도 잘리지 않게 한다.
        ttk.Label(control, text="실행 모드").grid(row=0, column=0, sticky="w", padx=6, pady=5)
        ttk.Combobox(
            control,
            textvariable=self.multi_mode_var,
            values=["동시감시", "순차실행"],
            state="readonly",
            width=12,
        ).grid(row=0, column=1, sticky="w", padx=6, pady=5)

        ttk.Label(control, text="출력 인정 기준").grid(row=1, column=0, sticky="w", padx=6, pady=(0, 5))
        ttk.Combobox(
            control,
            textvariable=self.multi_output_rule_var,
            values=["입력 이후", "세션 전체"],
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="w", padx=6, pady=(0, 5))

        select_row = ttk.Frame(control)
        select_row.grid(row=2, column=0, columnspan=4, sticky="w", padx=6, pady=(0, 4))
        self.multi_select_all_button = ttk.Button(select_row, text="전체 선택", width=10, command=self._multi_select_all)
        self.multi_select_all_button.pack(side=tk.LEFT)

        # rev87: '전체 선택 해제'도 '전체 선택'과 같은 버튼 폭으로 맞춘다.
        self.multi_clear_button = ttk.Button(select_row, text="전체 선택 해제", width=13, command=self._multi_clear_selection)
        self.multi_clear_button.pack(side=tk.LEFT, padx=(4, 0))

        self.multi_reset_button = ttk.Button(select_row, text="전체 초기화", width=10, command=self._multi_reset_all_history)
        self.multi_reset_button.pack(side=tk.LEFT, padx=(4, 0))

        ttk.Label(control, textvariable=self.multi_selected_count_var).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 2)
        )
        ttk.Label(control, textvariable=self.multi_result_summary_var, wraplength=430, justify="left").grid(
            row=4, column=0, columnspan=4, sticky="w", padx=6, pady=(0, 6)
        )

        action = ttk.Frame(control)
        action.grid(row=5, column=0, columnspan=4, sticky="w", padx=6, pady=(0, 6))
        for i in range(4):
            action.columnconfigure(i, weight=0)

        button_width = 11
        abort_button_width = 6
        abort_gap_px = 8

        self.multi_start_button = tk.Button(
            action,
            text="선택 Start",
            command=self._start_multi_selected_tcs,
            font=self.big_start_font,
            bg="#30D862",
            fg="black",
            activebackground="#28B854",
            activeforeground="black",
            relief="raised",
            bd=2,
            cursor="hand2",
            width=button_width,
        )
        self.multi_start_button.grid(row=0, column=0, padx=(0, 6), pady=0)

        self.multi_complete_button = tk.Button(
            action,
            text="수행 완료",
            command=self._complete_multi_monitoring,
            font=self.big_start_font,
            bg="#BAE6FD",
            fg="black",
            activebackground="#7DD3FC",
            activeforeground="black",
            relief="raised",
            bd=2,
            cursor="hand2",
            state=tk.DISABLED,
            width=button_width,
        )
        self.multi_complete_button.grid(row=0, column=1, padx=(0, 0), pady=0)

        ttk.Frame(action, width=abort_gap_px).grid(row=0, column=2, sticky="ns", padx=0, pady=0)

        self.multi_abort_button = tk.Button(
            action,
            text="중단",
            command=self._abort_multi_monitoring,
            font=("맑은 고딕", 10, "bold"),
            bg="#EF4444",
            fg="white",
            activebackground="#DC2626",
            activeforeground="white",
            relief="raised",
            bd=2,
            cursor="hand2",
            state=tk.DISABLED,
            width=abort_button_width,
            height=1,
        )
        self.multi_abort_button.grid(row=0, column=3, padx=(0, 6), pady=0, sticky="ns")

        progress = ttk.LabelFrame(right, text="수행 진행도")
        progress.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        progress.columnconfigure(0, weight=1)
        style = ttk.Style(self)
        style.configure("PassFail.Green.Horizontal.TProgressbar", troughcolor="#E5E7EB", background="#22C55E")
        ttk.Label(progress, textvariable=self.multi_progress_text_var).grid(row=0, column=0, sticky="w", padx=6, pady=(5, 2))
        self.multi_progress_bar = ttk.Progressbar(
            progress, variable=self.multi_progress_var, maximum=100.0, mode="determinate",
            style="PassFail.Green.Horizontal.TProgressbar"
        )
        self.multi_progress_bar.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))

        detail = ttk.LabelFrame(right, text="선택 TC 상세 / 보기")
        detail.grid(row=2, column=0, sticky="nsew", pady=(0, 6))
        detail.columnconfigure(0, weight=1)
        detail.rowconfigure(0, weight=1)

        self.multi_detail_text = ScrolledText(detail, height=10, width=52, wrap=tk.WORD)
        self.multi_detail_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.multi_detail_text.insert("1.0", "다중 실행할 TC를 왼쪽 목록에서 선택하세요.\n")

        result = ttk.LabelFrame(right, text="다중 실행 결과")
        result.grid(row=3, column=0, sticky="nsew")
        result.columnconfigure(0, weight=1)
        result.rowconfigure(0, weight=1)

        rcols = ("tc_no", "kind", "msg", "sig", "expected", "actual", "status", "message")
        self.multi_result_tree = ttk.Treeview(result, columns=rcols, show="headings")
        rheads = {
            "tc_no": "TC", "kind": "구분", "msg": "Message", "sig": "Signal",
            "expected": "Expected", "actual": "Actual", "status": "상태", "message": "메시지"
        }
        rwidths = {
            "tc_no": 40, "kind": 60, "msg": 160, "sig": 220,
            "expected": 90, "actual": 90, "status": 70, "message": 300
        }
        ranchors = {"tc_no": "center", "kind": "center", "expected": "center", "actual": "center", "status": "center"}
        for c in rcols:
            self.multi_result_tree.heading(c, text=rheads[c])
            self.multi_result_tree.column(c, width=rwidths[c], anchor=ranchors.get(c, "w"), stretch=False)

        self.multi_result_tree.tag_configure("pass", background="#DCFCE7", foreground="#166534")
        self.multi_result_tree.tag_configure("fail", background="#FEE2E2", foreground="#991B1B")
        self.multi_result_tree.tag_configure("na", background="#FEF3C7", foreground="#92400E")
        self.multi_result_tree.tag_configure("error", background="#FEE2E2", foreground="#991B1B")

        rscroll = ttk.Scrollbar(result, orient="vertical", command=self.multi_result_tree.yview)
        rxscroll = ttk.Scrollbar(result, orient="horizontal", command=self.multi_result_tree.xview)
        self.multi_result_tree.configure(yscrollcommand=rscroll.set, xscrollcommand=rxscroll.set)
        self.multi_result_tree.grid(row=0, column=0, sticky="nsew")
        rscroll.grid(row=0, column=1, sticky="ns")
        rxscroll.grid(row=1, column=0, sticky="ew")

        self._refresh_multi_tc_tree()

    def _after_conditions_loaded(self):
        super()._after_conditions_loaded()
        self.multi_result_status_by_index.clear()
        self.multi_final_result_by_index.clear()
        self.multi_focus_index = None
        self._set_multi_progress(0, "TC 목록 로드 완료 / 대기")
        self._refresh_multi_tc_tree()
        self._refresh_multi_signal_tree()

    def _schedule_multi_refresh(self, status_by_index: Optional[Dict[int, str]] = None, delay_ms: int = 70):
        """빠른 다중 체크/해제 시 Tree 전체 재구성을 한 번으로 묶는다."""
        if status_by_index:
            self._multi_pending_status_by_index.update(status_by_index)
        if self._multi_refresh_after_id is not None:
            try:
                self.after_cancel(self._multi_refresh_after_id)
            except Exception:
                pass
        self._multi_refresh_after_id = self.after(max(1, int(delay_ms)), self._flush_multi_refresh)

    def _flush_multi_refresh(self):
        self._multi_refresh_after_id = None
        pending = dict(self._multi_pending_status_by_index)
        self._multi_pending_status_by_index.clear()
        self._refresh_multi_tc_tree(status_by_index=pending)

    def _get_multi_display_status(self, idx: int, status_by_index: Optional[Dict[int, str]] = None) -> str:
        status_by_index = status_by_index or {}
        return status_by_index.get(idx) or self.multi_result_status_by_index.get(idx) or "대기"

    def _refresh_multi_tc_tree(self, status_by_index: Optional[Dict[int, str]] = None):
        if self.multi_tc_tree is None:
            return

        status_by_index = status_by_index or {}
        self.multi_tc_tree.delete(*self.multi_tc_tree.get_children())

        valid_indices = set()
        for idx, row in enumerate(getattr(self, "condition_rows", [])):
            if not row.is_valid or row.condition is None:
                continue
            valid_indices.add(idx)
            c = row.condition
            check = "☑" if idx in self.multi_selected_indices else "☐"

            ins = []
            for inp in c.input_conditions:
                ins.append(f"{inp.message}:{inp.signal}={inp.expected_value_raw}")
            inp_text = " / ".join(ins)

            outs = []
            for out in c.output_conditions:
                outs.append(f"{out.message}:{out.signal}={out.expected_value_raw}")
            out_text = " / ".join(outs)

            state = self._get_multi_display_status(idx, status_by_index)

            tag_list = []
            if state in ("PASS", "로그 PASS"):
                tag_list.append("pass")
            elif state in ("FAIL", "로그 FAIL"):
                tag_list.append("fail")
            elif state in ("N/A", "로그 N/A"):
                tag_list.append("na")
            elif state in ("ERROR", "로그 ERROR"):
                tag_list.append("error")
            elif idx in self.multi_selected_indices:
                tag_list.append("selected")
            else:
                tag_list.append("even" if idx % 2 == 0 else "odd")

            self.multi_tc_tree.insert(
                "",
                tk.END,
                iid=str(idx),
                tags=tuple(tag_list),
                values=(
                    check,
                    c.tc_no,
                    c.subcategory,
                    inp_text,
                    out_text,
                    c.timeout_sec,
                    state,
                ),
            )

        self.multi_selected_indices = {i for i in self.multi_selected_indices if i in valid_indices}
        if self.multi_anchor_index not in valid_indices:
            self.multi_anchor_index = None
        if self.multi_focus_index not in valid_indices:
            self.multi_focus_index = None
        self._update_multi_selected_count()

    def _update_multi_selected_count(self):
        cnt = len(self.multi_selected_indices)
        self.multi_selected_count_var.set(f"선택 TC: {cnt}개")
        if self.multi_start_button is not None:
            # 버튼 폭을 넘지 않도록 one by one 탭처럼 기본 문구는 짧게 유지한다.
            self.multi_start_button.configure(text="선택 Start")

    def _get_valid_multi_indices(self):
        return {
            idx for idx, row in enumerate(getattr(self, "condition_rows", []))
            if row.is_valid and row.condition is not None
        }

    # -----------------------------
    # Shift 범위 선택 지원
    # -----------------------------
    def _on_multi_tc_tree_click(self, event):
        row_id = self.multi_tc_tree.identify_row(event.y)
        if not row_id:
            return None

        try:
            idx = int(row_id)
        except Exception:
            return None

        shift_pressed = bool(event.state & 0x0001)
        self.multi_focus_index = idx

        if shift_pressed and self.multi_anchor_index is not None:
            start = min(self.multi_anchor_index, idx)
            end = max(self.multi_anchor_index, idx)
            range_indices = []
            for i in range(start, end + 1):
                if 0 <= i < len(self.condition_rows):
                    row = self.condition_rows[i]
                    if row.is_valid and row.condition is not None:
                        range_indices.append(i)
            # Shift 범위가 이미 모두 선택되어 있으면 같은 동작으로 범위 선택 해제한다.
            if range_indices and all(i in self.multi_selected_indices for i in range_indices):
                for i in range_indices:
                    self.multi_selected_indices.discard(i)
            else:
                for i in range_indices:
                    self.multi_selected_indices.add(i)
        else:
            if idx in self.multi_selected_indices:
                self.multi_selected_indices.remove(idx)
            else:
                self.multi_selected_indices.add(idx)
            self.multi_anchor_index = idx

        self._update_multi_selected_count()
        self._schedule_multi_refresh(delay_ms=1)
        self._show_multi_selected_detail()
        self._schedule_multi_signal_refresh()
        return "break"

    def _multi_select_all(self):
        valid_indices = self._get_valid_multi_indices()
        # B안: 전체 선택과 전체 선택 해제를 독립 버튼으로 유지한다.
        # 전체 선택 버튼은 현재 선택 상태와 무관하게 항상 유효 TC 전체를 선택한다.
        self.multi_selected_indices = set(valid_indices)

        if self.multi_selected_indices:
            self.multi_anchor_index = min(self.multi_selected_indices)
            self.multi_focus_index = self.multi_anchor_index
        else:
            self.multi_anchor_index = None
            self.multi_focus_index = None
        self._update_multi_selected_count()
        self._schedule_multi_refresh(delay_ms=1)
        self._show_multi_selected_detail()
        self._schedule_multi_signal_refresh(delay_ms=1)

    def _multi_clear_selection(self):
        self.multi_selected_indices.clear()
        self.multi_anchor_index = None
        self.multi_focus_index = None
        self._update_multi_selected_count()
        self._schedule_multi_refresh(delay_ms=1)
        self._show_multi_selected_detail()
        self._schedule_multi_signal_refresh(delay_ms=1)

    def _multi_reset_all_history(self):
        if self.multi_active:
            messagebox.showinfo("다중 실행 중", "다중 실행이 진행 중일 때는 전체 초기화를 할 수 없습니다.")
            return
        if (self.multi_result_status_by_index or self.multi_final_result_by_index) and not messagebox.askyesno(
            "전체 초기화", "다중 실행의 PASS/FAIL/중단 표시와 다중 실행 결과 목록을 초기화할까요?"
        ):
            return
        self.multi_result_status_by_index.clear()
        self.multi_final_result_by_index.clear()
        self._refresh_multi_tc_tree()
        self._refresh_multi_summary({})
        self._refresh_multi_signal_tree()
        self.multi_status_var.set("대기중")
        self._show_multi_selected_detail("다중 실행 기록을 전체 초기화했습니다.")
        self._log("[MULTI] 다중 실행 기록 전체 초기화\n")

    def _get_multi_selected_conditions(self):
        out = []
        for idx in sorted(self.multi_selected_indices):
            if 0 <= idx < len(self.condition_rows):
                row = self.condition_rows[idx]
                if row.is_valid and row.condition is not None:
                    out.append((idx, row.condition))
        return out

    def _show_multi_selected_detail(self, extra: str = ""):
        if self.multi_detail_text is None:
            return
        items = self._get_multi_selected_conditions()
        lines = []
        lines.append(f"선택 TC: {len(items)}개")
        lines.append(f"실행 모드: {self.multi_mode_var.get()}")
        lines.append(f"출력 인정 기준: {self.multi_output_rule_var.get()}")
        if extra:
            lines.append("")
            lines.append(extra)
        lines.append("")

        focus_row = None
        if self.multi_focus_index is not None and 0 <= self.multi_focus_index < len(self.condition_rows):
            focus_row = self.condition_rows[self.multi_focus_index]

        if focus_row is None or not focus_row.is_valid or focus_row.condition is None:
            lines.append("왼쪽 다중 실행 TC 목록에서 TC를 클릭하면 해당 TC의 상세 설명이 여기에 표시됩니다.")
            lines.append("여러 TC를 체크하면 아래 [다중 실행 결과] 영역에 실행해야 할 신호 리스트가 차곡차곡 표시됩니다.")
        else:
            c = focus_row.condition
            selected_text = "선택됨" if self.multi_focus_index in self.multi_selected_indices else "미선택"
            lines.extend([
                f"TC 번호: {c.tc_no}",
                f"소분류: {c.subcategory}",
                f"판정 방식: {c.judge_mode} / TC 대기값: {c.timeout_sec}s (다중 자동종료에는 미사용)",
                f"다중 선택 여부: {selected_text}",
                "",
                "[TC 내용]",
                c.tc_content or "-",
                "",
                "[TC 예상 결과]",
                c.tc_expected_result or "-",
                "",
                "[입력 조건]",
            ])
            if c.input_conditions:
                for i, inp in enumerate(c.input_conditions, start=1):
                    lines.append(f"{i}. {inp.message} / {inp.signal} / {inp.expected_value_raw}")
            else:
                lines.append("-")
            lines.append("")
            lines.append("[출력 조건]")
            if c.output_conditions:
                for i, o in enumerate(c.output_conditions, start=1):
                    lines.append(f"{i}. {o.message} / {o.signal} / {o.expected_value_raw}")
            else:
                lines.append("-")

        self.multi_detail_text.configure(state="normal")
        self.multi_detail_text.delete("1.0", tk.END)
        self.multi_detail_text.insert("1.0", "\n".join(lines))
        self.multi_detail_text.configure(state="normal")

    def _schedule_multi_signal_refresh(self, delay_ms: int = 70):
        if self._multi_signal_refresh_after_id is not None:
            try:
                self.after_cancel(self._multi_signal_refresh_after_id)
            except Exception:
                pass
        self._multi_signal_refresh_after_id = self.after(max(1, int(delay_ms)), self._flush_multi_signal_refresh)

    def _flush_multi_signal_refresh(self):
        self._multi_signal_refresh_after_id = None
        self._refresh_multi_signal_tree()

    def _find_multi_index_by_condition(self, condition):
        for idx, row in enumerate(getattr(self, "condition_rows", [])):
            if getattr(row, "condition", None) is condition:
                return idx
        return None

    def _signal_result_from_final(self, final, role: str, pos: int):
        if final is None:
            return None
        rt = getattr(final, "realtime_result", None)
        lg = getattr(final, "log_result", None)
        # 실시간 PASS가 최종 PASS 우선 근거이므로 해당 경우에는 실시간 조건 결과를 먼저 표시한다.
        # 그 외에는 로그 보정 결과를 우선 표시한다.
        checks = (rt, lg) if getattr(rt, "status", "") == "PASS" else (lg, rt)
        for check in checks:
            if check is None:
                continue
            items = getattr(check, "input_results" if role == "input" else "output_results", []) or []
            if pos < len(items):
                return items[pos]
        return None

    def _refresh_multi_signal_tree(self):
        if self.multi_result_tree is None:
            return
        self.multi_result_tree.delete(*self.multi_result_tree.get_children())

        for idx, cond in self._get_multi_selected_conditions():
            final = self.multi_final_result_by_index.get(idx)
            for role, label, exps in (("input", "입력", cond.input_conditions), ("output", "출력", cond.output_conditions)):
                for pos, exp in enumerate(exps):
                    one = self._signal_result_from_final(final, role, pos)
                    actual = getattr(one, "observed_value_raw", "") if one is not None else ""
                    status = getattr(one, "status", "") if one is not None else ""
                    message = getattr(one, "message", "") if one is not None else "실행 예정"
                    tag = ""
                    if status == "PASS":
                        tag = "pass"
                    elif status == "FAIL":
                        tag = "fail"
                    elif status == "N/A":
                        tag = "na"
                    elif status == "ERROR":
                        tag = "error"
                    iid = f"{idx}:{'I' if role == 'input' else 'O'}:{pos + 1}"
                    self.multi_result_tree.insert(
                        "",
                        tk.END,
                        iid=iid,
                        tags=(tag,) if tag else (),
                        values=(
                            cond.tc_no,
                            f"{label}{pos + 1}",
                            exp.message,
                            exp.signal,
                            exp.expected_value_raw,
                            actual,
                            status,
                            message,
                        ),
                    )

    def _clear_multi_history_for_indices(self, indices):
        for idx in list(indices):
            self.multi_result_status_by_index.pop(idx, None)
            self.multi_final_result_by_index.pop(idx, None)
        self._refresh_multi_tc_tree()
        self._refresh_multi_signal_tree()

    def _set_multi_progress(self, percent: float, text: str):
        pct = max(0.0, min(100.0, float(percent)))
        try:
            self.multi_progress_var.set(pct)
            self.multi_progress_text_var.set(f"{text}  ({pct:.0f}%)")
        except Exception:
            pass

    def _start_multi_selected_tcs(self):
        if self.multi_monitor_thread is not None and self.multi_monitor_thread.is_alive():
            messagebox.showinfo("다중 실행 중", "이미 다중 실행이 진행 중입니다.")
            return

        selected = self._get_multi_selected_conditions()
        if not selected:
            messagebox.showwarning("TC 선택 필요", "다중 실행할 TC를 1개 이상 선택하세요.")
            return

        self._set_multi_progress(3, f"선택 TC {len(selected)}개 실행 준비")
        mode = self.multi_mode_var.get().strip()
        if mode == "순차실행":
            self._start_multi_sequential(selected)
        else:
            self._start_multi_simultaneous(selected)

    def _set_multi_running_ui(self, running: bool):
        self.multi_active = running
        self.multi_start_button.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.multi_complete_button.configure(state=tk.NORMAL if running else tk.DISABLED)
        self.multi_abort_button.configure(state=tk.NORMAL if running else tk.DISABLED)
        if not running and self.multi_start_button is not None:
            self.multi_start_button.configure(text="선택 Start")
        self.multi_status_var.set("검토중" if running else "대기중")

    def _complete_multi_monitoring(self):
        if not self.multi_active:
            messagebox.showinfo("안내", "현재 진행 중인 다중 실행이 없습니다.")
            return
        self._set_multi_progress(72, "수행 완료 요청 / Measurement 정리")
        self.multi_done_event.set()
        if self.multi_mode_var.get().strip() == "순차실행":
            self.done_event.set()
        self.multi_complete_button.configure(state=tk.DISABLED)
        self.multi_start_button.configure(state=tk.DISABLED)
        self._safe_stop_measurement_for_transition("다중 수행 완료", invalidate_after=True)
        self._show_multi_selected_detail("수행 완료 요청: CANoe Measurement Stop 후 결과 확정/로그 재검토 진행 중")

    def _abort_multi_monitoring(self):
        self._set_multi_progress(0, "사용자 중단")
        self.multi_stop_event.set()
        self.multi_done_event.clear()
        self.stop_event.set()
        self.done_event.clear()
        self.multi_complete_button.configure(state=tk.DISABLED)
        self.multi_abort_button.configure(state=tk.DISABLED)
        self._active_countdown_button = None
        self._safe_stop_measurement_for_transition("다중 중단", invalidate_after=True)
        self._set_multi_running_ui(False)
        self.multi_status_var.set("중단됨")
        self._show_multi_selected_detail("사용자 중단 요청")

    def _start_multi_sequential(self, selected: List[Tuple[int, Any]]):
        self._clear_multi_history_for_indices([idx for idx, _cond in selected])
        self._set_multi_running_ui(True)
        self._active_countdown_button = self.multi_start_button
        self.multi_stop_event.clear()
        self.multi_done_event.clear()
        self.multi_sequence_items = list(selected)
        self.multi_sequence_pos = 0
        self._set_multi_progress(10, "순차실행 시작")
        self._log(f"[MULTI] 순차실행 시작: {len(selected)}개 TC\n")
        self._run_next_multi_sequence_item()

    def _run_next_multi_sequence_item(self):
        if self.multi_stop_event.is_set():
            self._set_multi_running_ui(False)
            return
        if self.multi_sequence_pos >= len(self.multi_sequence_items):
            self._set_multi_running_ui(False)
            self.multi_status_var.set("완료")
            self._set_multi_progress(100, "순차실행 완료")
            self._show_multi_selected_detail("순차실행 완료")
            return

        idx, cond = self.multi_sequence_items[self.multi_sequence_pos]
        total = max(1, len(self.multi_sequence_items))
        self._set_multi_progress(15 + 70 * (self.multi_sequence_pos / total), f"순차실행 {self.multi_sequence_pos + 1}/{total}: {cond.tc_no}")
        self.selected_condition_index = idx
        for disp in self.display_rows:
            disp["selected_overlay"] = (disp["row_index"] == idx)
        self._refresh_tc_tree()
        self._refresh_all_summary(cond, None)
        self._show_multi_selected_detail(f"순차실행 진행 중: {self.multi_sequence_pos + 1}/{len(self.multi_sequence_items)} - {cond.tc_no}")
        self._start_selected_tc()

    def _on_final_done(self, result):
        super()._on_final_done(result)
        if getattr(self, "multi_active", False) and getattr(self, "multi_mode_var", None) is not None:
            if self.multi_mode_var.get().strip() == "순차실행" and hasattr(self, "multi_sequence_items"):
                idx = self._find_multi_index_by_condition(result.condition)
                if idx is not None:
                    self.multi_result_status_by_index[idx] = result.final_status
                    self.multi_final_result_by_index[idx] = result
                    self._refresh_multi_tc_tree(status_by_index={idx: result.final_status})
                self._append_multi_result_tree([result])
                # rev87: 사용자가 [다중 수행 완료]를 눌렀다면 현재 TC 결과 확정 후 전체 순차 세션을 종료한다.
                # 자연 PASS인 경우에만 다음 선택 TC로 자동 진행한다.
                if self.multi_done_event.is_set():
                    self._set_multi_running_ui(False)
                    self.multi_status_var.set("완료")
                    self._show_multi_selected_detail("순차실행 수행 완료 - 현재 TC 결과 확정 후 세션 종료")
                    return
                self.multi_sequence_pos += 1
                total = max(1, len(self.multi_sequence_items))
                self._set_multi_progress(15 + 70 * (self.multi_sequence_pos / total), f"TC 결과 반영 {self.multi_sequence_pos}/{total}")
                self.after(500, self._run_next_multi_sequence_item)

    def _start_multi_simultaneous(self, selected: List[Tuple[int, Any]]):
        try:
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

        self._clear_multi_history_for_indices([idx for idx, _cond in selected])
        self._set_multi_progress(8, "다중감시 환경 준비")
        self.multi_stop_event.clear()
        self.multi_done_event.clear()
        self.stop_event.clear()
        self.done_event.clear()
        self._set_multi_running_ui(True)
        self._active_countdown_button = self.multi_start_button
        if self.multi_start_button is not None:
            self.multi_start_button.configure(text="Measurement 준비중...")

        try:
            self._set_multi_progress(15, "Measurement 연결/시작")
            self._start_measurement_with_optional_collector(
                [cond for _idx, cond in selected], measurement_wait_sec, label="선택 Start"
            )
        except Exception as e:
            self._active_countdown_button = None
            self._set_multi_running_ui(False)
            if self.multi_start_button is not None:
                self.multi_start_button.configure(text="선택 Start")
            if "Vector 연결 실패" not in str(e):
                messagebox.showerror("Measurement 시작 실패", str(e))
            return

        if self.stop_event.is_set() or self.multi_stop_event.is_set():
            self._active_countdown_button = None
            self._set_multi_running_ui(False)
            if self.multi_start_button is not None:
                self.multi_start_button.configure(text="선택 Start")
            self._log("[MULTI] Measurement 대기 중 중단되어 동시감시를 시작하지 않습니다.\n")
            return

        manual_log_path = self.log_file_var.get().strip() or None if self.manual_log_enabled_var.get() else None
        log_dir = self.log_dir_var.get().strip() or None
        dbc_map = self._collect_dbc_mapping()
        auto_log = bool(self.auto_log_review_var.get())
        auto_find_latest_log = bool(self.auto_find_latest_log_var.get())
        auto_stop_measurement = bool(self.auto_stop_measurement_var.get())
        multi_log_review_enabled = bool(getattr(self, "multi_log_review_var", tk.BooleanVar(value=False)).get())
        skip_log_review_on_pass = bool(getattr(self, "skip_log_review_on_pass_var", tk.BooleanVar(value=True)).get()) and not multi_log_review_enabled
        output_rule = self.multi_output_rule_var.get().strip()
        tc_start_ts = time.time()

        if self.multi_start_button is not None:
            self.multi_start_button.configure(text="검토중...")
        self._active_countdown_button = None
        self._refresh_multi_signal_tree()
        self._log(
            f"[MULTI] 동시감시 시작: TC={len(selected)}개, channels={channels}, "
            f"output_rule={output_rule}, multi_log_review={multi_log_review_enabled}, auto_timeout=OFF\n"
        )
        self._set_multi_progress(22, "실시간 입력/출력 감시 중")
        self._show_multi_selected_detail("동시감시 진행 중")

        worker_bus_name = self.bus_name_var.get().strip() or "CAN"
        worker_vector_product = self.vector_product_var.get().strip() or "자동"

        def worker():
            try:
                results = self._multi_simultaneous_worker(
                    selected=selected,
                    channels=channels,
                    poll_interval=poll_interval,
                    output_rule=output_rule,
                    manual_log_path=manual_log_path,
                    log_dir=log_dir,
                    dbc_map=dbc_map,
                    auto_log=auto_log,
                    auto_find_latest_log=auto_find_latest_log,
                    auto_stop_measurement=auto_stop_measurement,
                    skip_log_review_on_pass=skip_log_review_on_pass,
                    multi_log_review_enabled=multi_log_review_enabled,
                    log_wait_timeout=log_wait_timeout,
                    drop_first_seconds=drop_first_seconds,
                    tc_start_ts=tc_start_ts,
                    bus_name=worker_bus_name,
                    vector_product_preference=worker_vector_product,
                    collector_probe=self._collector_probe_cache if self._collector_runtime_active else None,
                    collector_measurement_start_perf=self._measurement_started_perf,
                )
                self.multi_queue.put(("DONE", results))
            except Exception as e:
                self.multi_queue.put(("ERROR", str(e)))

        self.multi_monitor_thread = threading.Thread(target=worker, daemon=True)
        self.multi_monitor_thread.start()

    def _make_condition_state(self, cond):
        return {
            "condition": cond,
            "inputs": [core.SingleExpectationCheck(expectation=x) for x in cond.input_conditions],
            "outputs": [core.SingleExpectationCheck(expectation=o) for o in cond.output_conditions],
            "status": "검토중",
            "message": "동시감시 중",
            "input_pass_times": {},
            "input_pass_measurement_ms": {},
            "started_at": _dt.datetime.now(),
        }

    def _iter_state_expectations(self, selected_states):
        for idx, st in selected_states.items():
            for i, inp in enumerate(st.get("inputs", [])):
                yield idx, "input", i, inp.expectation
            for i, out in enumerate(st.get("outputs", [])):
                yield idx, "output", i, out.expectation

    def _multi_simultaneous_worker(
        self,
        selected: List[Tuple[int, Any]],
        channels: List[int],
        poll_interval: float,
        output_rule: str,
        manual_log_path: Optional[str],
        log_dir: Optional[str],
        dbc_map: Dict[int, str],
        auto_log: bool,
        auto_find_latest_log: bool,
        auto_stop_measurement: bool,
        skip_log_review_on_pass: bool,
        multi_log_review_enabled: bool,
        log_wait_timeout: float,
        drop_first_seconds: float,
        tc_start_ts: float,
        bus_name: str = "CAN",
        vector_product_preference: str = "자동",
        collector_probe=None,
        collector_measurement_start_perf: Optional[float] = None,
    ):
        states = {idx: self._make_condition_state(cond) for idx, cond in selected}
        started_perf = time.perf_counter()
        # rev87: 다중 동시감시는 Excel TC timeout으로 자동 종료하지 않는다.
        # 종료 조건은 전체 PASS, 사용자의 [수행 완료], [중단]뿐이다.
        # Worker 스레드에서 CANoeClient로 한 번만 연결한다.
        # VectorApplicationClient 정책으로 선택 제품에 연결한다(GetActiveObject 우선, guarded fallback 조건부).
        try:
            worker_client = core.CANoeClient(bus_name=bus_name, product_preference=vector_product_preference).connect(
                expected_version_keyword=None,
                expected_exe_keyword=None,
            )
        except Exception as e:
            diag_path = ""
            try:
                diag = core.collect_vector_com_diagnostics(trigger_error=e, preference=vector_product_preference)
                diag_path = str(core.save_vector_com_diagnostic_report(self._app_dir, diag, prefix="vector_com_multi_worker_diagnostic"))
            except Exception:
                pass
            detail = f"Vector 연결 실패: {e}"
            if diag_path:
                detail += f" | 진단 파일: {diag_path}"
            raise RuntimeError(detail) from e

        self.multi_queue.put(("STAGE", 25, "Vector 연결 완료 / 실시간 감시"))
        watch_targets: Dict[Tuple[str, str], List[Tuple[int, str, int, Any]]] = {}
        for idx, role, pos, exp in self._iter_state_expectations(states):
            if exp is None:
                continue
            watch_targets.setdefault((exp.message, exp.signal), []).append((idx, role, pos, exp))

        while True:
            if self.multi_stop_event.is_set():
                break
            elapsed = time.perf_counter() - started_perf
            if self.multi_done_event.is_set():
                break

            # rev87 optional CAPL Event Collector: consume latched expected-value hits first.
            # It is additive only; COM polling below remains the fallback/secondary observer.
            if collector_probe is not None:
                for idx, role, pos, exp in self._iter_state_expectations(states):
                    st = states[idx]
                    one = st["inputs"][pos] if role == "input" else st["outputs"][pos]
                    if one.status == "PASS":
                        continue
                    min_hit_ms = 0.0
                    if role == "output" and output_rule == "입력 이후":
                        input_count = len(st.get("inputs", []))
                        input_ms = st.get("input_pass_measurement_ms", {})
                        if len(input_ms) < input_count:
                            continue
                        min_hit_ms = max([float(x) for x in input_ms.values()] or [0.0])
                    try:
                        hit = collector_probe(
                            expectation=exp, channels=channels, min_hit_ms=min_hit_ms
                        )
                    except Exception:
                        hit = None
                    if not hit:
                        continue
                    hit_ms = float(hit.get("hit_ms") or 0.0)
                    ch = hit.get("channel")
                    raw = hit.get("value", exp.expected_value_raw)
                    one.status = "PASS"
                    one.observed_value_raw = raw
                    one.observed_value_norm = core.normalize_value(raw)
                    one.observed_time = hit_ms / 1000.0 if hit_ms > 0 else elapsed
                    one.observed_channel = int(ch) if ch is not None else None
                    one.observation_source = "capl_collector"
                    one.collector_hit_ms = hit_ms if hit_ms > 0 else None
                    one.message = f"동시감시 {('입력' if role == 'input' else '출력')} 관측 | CAPL Event Collector / CAN{ch}"
                    if role == "input":
                        st["input_pass_times"][pos] = elapsed
                        st["input_pass_measurement_ms"][pos] = hit_ms

            for (msg, sig), uses in watch_targets.items():
                readings = self._multi_read_signal(worker_client, channels, msg, sig)
                for bus_name, ch, raw in readings:
                    norm = core.normalize_value(raw)
                    for idx, role, pos, exp in uses:
                        if not core.values_equal(exp.expected_value_raw, raw):
                            continue
                        st = states[idx]
                        if role == "input":
                            one = st["inputs"][pos]
                            if one.status != "PASS":
                                one.status = "PASS"
                                one.observed_value_raw = raw
                                one.observed_value_norm = norm
                                one.observed_time = elapsed
                                one.observed_channel = ch
                                one.observation_source = "com_polling"
                                one.message = f"동시감시 입력 관측 | {bus_name}/CAN{ch}"
                                st["input_pass_times"][pos] = elapsed
                                if collector_measurement_start_perf is not None:
                                    st["input_pass_measurement_ms"][pos] = max(
                                        0.0, (time.perf_counter() - float(collector_measurement_start_perf)) * 1000.0
                                    )
                        else:
                            if output_rule == "입력 이후":
                                input_count = len(st.get("inputs", []))
                                if len(st.get("input_pass_times", {})) < input_count:
                                    continue
                            one = st["outputs"][pos]
                            if one.status != "PASS":
                                one.status = "PASS"
                                one.observed_value_raw = raw
                                one.observed_value_norm = norm
                                one.observed_time = elapsed
                                one.observed_channel = ch
                                one.observation_source = "com_polling"
                                one.message = f"동시감시 출력 관측 | {bus_name}/CAN{ch}"

            self._multi_update_state_statuses(states)
            snapshot = self._multi_status_snapshot(states)
            self.multi_queue.put(("PROGRESS", snapshot))
            pass_count = sum(1 for x in snapshot.values() if x == "PASS")
            total_count = max(1, len(snapshot))
            self.multi_queue.put(("STAGE", 25 + 42 * (pass_count / total_count), f"실시간 감시: PASS {pass_count}/{total_count}"))
            if states and all(st["status"] == "PASS" for st in states.values()):
                break
            time.sleep(max(0.01, float(poll_interval)))

        self.multi_queue.put(("STAGE", 72, "Measurement 정리 / 결과 확정 준비"))
        try:
            if auto_stop_measurement:
                worker_client.stop_measurement()
        except Exception:
            pass

        self._multi_finalize_unpassed_states(states)
        self.multi_queue.put(("PROGRESS", self._multi_status_snapshot(states)))

        self.multi_queue.put(("STAGE", 78, "로그 파일 선택/안정화 확인"))
        all_realtime_pass = bool(states) and all(st.get("status") == "PASS" for st in states.values())
        if all_realtime_pass and skip_log_review_on_pass and not multi_log_review_enabled:
            log_path = None
        else:
            log_path = self._multi_pick_log_path(
                manual_log_path=manual_log_path,
                log_dir=log_dir,
                auto_find_latest_log=auto_find_latest_log,
                log_wait_timeout=log_wait_timeout,
                tc_start_ts=tc_start_ts,
            )

        if multi_log_review_enabled:
            self.multi_queue.put(("PROGRESS", self._multi_status_snapshot(states)))

        self.multi_queue.put(("STAGE", 88, "로그/최종 판정 정리"))
        results = self._multi_build_final_results(
            states=states,
            log_path=log_path,
            dbc_map=dbc_map,
            auto_log=auto_log,
            drop_first_seconds=drop_first_seconds,
            multi_log_review_enabled=multi_log_review_enabled,
        )
        return results

    def _multi_read_signal(self, client, channels, message, signal):
        """동시감시에서도 이미 연결된 CANoeClient 하나만 사용한다."""
        readings = []
        bus_name = getattr(client, "bus_name", "CAN") or "CAN"
        for ch in channels:
            try:
                raw = client.get_signal_value(int(ch), message, signal)
                readings.append((bus_name, int(ch), raw))
            except Exception:
                continue
        return readings

    def _multi_update_state_statuses(self, states):
        for st in states.values():
            ins = st.get("inputs", [])
            outs = st.get("outputs", [])
            inputs_pass = bool(ins) and all(x.status == "PASS" for x in ins)
            outputs_pass = bool(outs) and all(o.status == "PASS" for o in outs)

            if inputs_pass and outputs_pass:
                st["status"] = "PASS"
                st["message"] = "모든 입력 및 모든 출력 조건 관측"
            elif inputs_pass:
                st["status"] = "검토중"
                st["message"] = "입력 조건 관측 완료, 출력 조건 대기"
            else:
                st["status"] = "검토중"
                st["message"] = "입력 조건 대기"

    def _multi_finalize_unpassed_states(self, states):
        for st in states.values():
            if st["status"] == "PASS":
                continue
            ins = st.get("inputs", [])
            outs = st.get("outputs", [])
            inputs_pass = bool(ins) and all(x.status == "PASS" for x in ins)

            if self.multi_stop_event.is_set():
                st["status"] = "N/A"
                st["message"] = "사용자 중단"
            elif not inputs_pass:
                st["status"] = "N/A"
                st["message"] = "입력 조건 일부 또는 전체 미관측"
                for inp in ins:
                    if inp.status != "PASS":
                        inp.status = "N/A"
                        inp.message = "입력 조건 미관측"
            else:
                st["status"] = "FAIL"
                st["message"] = "입력은 충족됐으나 출력 조건 일부 미관측"
                for o in outs:
                    if o.status != "PASS":
                        o.status = "FAIL"
                        o.message = "출력 조건 미관측"

    def _multi_status_snapshot(self, states):
        return {idx: st["status"] for idx, st in states.items()}

    def _multi_pick_log_path(self, manual_log_path, log_dir, auto_find_latest_log, log_wait_timeout, tc_start_ts):
        if manual_log_path and Path(manual_log_path).exists():
            return Path(manual_log_path)
        if auto_find_latest_log and log_dir:
            try:
                latest = core.find_latest_log_file(
                    log_dir=log_dir,
                    after_ts=tc_start_ts,
                    wait_timeout=log_wait_timeout,
                    poll_interval=0.5,
                    exts=(".blf", ".asc"),
                )
                if latest is not None:
                    core.wait_until_file_stable(
                        latest,
                        stable_sec=1.0,
                        timeout=min(max(2.0, log_wait_timeout), 10.0),
                        poll_interval=0.2,
                    )
                    return latest
            except Exception:
                return None
        return None

    def _multi_build_final_results(self, states, log_path, dbc_map, auto_log, drop_first_seconds, multi_log_review_enabled: bool = False):
        final_results = []
        batch_log_result_by_cond_id = {}
        log_unavailable_message = ""

        if multi_log_review_enabled:
            if log_path is not None and dbc_map:
                try:
                    self.multi_queue.put(("STAGE", 90, "로그 읽기/일괄 재검토 중"))
                    self.multi_queue.put(("DETAIL", f"다중 TC 로그 일괄 재검토 시작: {Path(log_path).name}"))
                    log_checks = core.review_conditions_in_log_batch(
                        conditions=[st["condition"] for st in states.values()],
                        log_path=log_path,
                        dbc_path_by_channel=dbc_map,
                        drop_first_seconds=drop_first_seconds,
                        stop_event=self.multi_stop_event,
                    )
                    for log_check in log_checks:
                        batch_log_result_by_cond_id[id(log_check.condition)] = log_check
                    self.multi_queue.put(("STAGE", 97, "로그 재검토 완료 / 결과 반영"))
                    self.multi_queue.put(("DETAIL", f"다중 TC 로그 일괄 재검토 완료: {len(log_checks)}개 TC"))
                except Exception as e:
                    log_unavailable_message = f"다중 TC 로그 일괄 재검토 오류: {e}"
            else:
                log_unavailable_message = "다중 TC 로그 검토 설정됨, 그러나 로그 파일 또는 DBC 매핑이 없어 로그 검토를 수행하지 못함"

        for idx, st in states.items():
            cond = st["condition"]
            rt = core.CheckResult(
                condition=cond,
                status=st["status"],
                source="multi_realtime",
                started_at=st["started_at"],
                ended_at=_dt.datetime.now(),
                message=st["message"],
                input_results=list(st.get("inputs", [])),
                output_results=list(st.get("outputs", [])),
            )
            if rt.output_results:
                last = rt.output_results[-1]
                rt.observed_value_raw = last.observed_value_raw
                rt.observed_value_norm = last.observed_value_norm
                rt.observed_time = last.observed_time
                rt.observed_channel = last.observed_channel
            elif rt.input_results:
                last = rt.input_results[-1]
                rt.observed_value_raw = last.observed_value_raw
                rt.observed_value_norm = last.observed_value_norm
                rt.observed_time = last.observed_time
                rt.observed_channel = last.observed_channel

            final = core.FinalCheckResult(
                condition=cond,
                realtime_result=rt,
                final_status=rt.status,
                final_message=rt.message,
                final_observed_value_raw=rt.observed_value_raw,
                final_observed_value_norm=rt.observed_value_norm,
                final_observed_time=rt.observed_time,
                final_observed_channel=rt.observed_channel,
                used_log_path=str(log_path) if log_path else None,
                started_at=rt.started_at,
                ended_at=rt.ended_at,
            )

            if multi_log_review_enabled:
                log_result = batch_log_result_by_cond_id.get(id(cond))
                if log_result is not None:
                    self._apply_multi_log_result_to_final(final, log_result, strict_log_reflect=True)
                elif log_unavailable_message:
                    final.final_message = f"{final.final_message} / {log_unavailable_message}"
            elif final.final_status != "PASS" and auto_log and log_path is not None and dbc_map:
                log_result = self._multi_review_condition_in_log(cond, log_path, dbc_map, drop_first_seconds)
                self._apply_multi_log_result_to_final(final, log_result, strict_log_reflect=False)

            if final.final_status == "검토중":
                final.final_status = "FAIL"
            final_results.append(final)
        return final_results

    def _apply_multi_log_result_to_final(self, final, log_result, strict_log_reflect: bool):
        # 최종 판정 정책은 Core의 공통 함수만 사용한다.
        core.apply_log_result_to_final(
            final=final,
            log_result=log_result,
            strict_log_reflect=strict_log_reflect,
            context_label="다중 TC 로그 재검토",
        )

    def _multi_review_condition_in_log(self, cond, log_path, dbc_map, drop_first_seconds):
        log_check = core.CheckResult(
            condition=cond,
            status="검토중",
            source="multi_log_review",
            started_at=_dt.datetime.now(),
            message="다중 실행 로그 재검토 시작",
        )
        try:
            input_results = []
            for exp in cond.input_conditions:
                lr = core.review_single_expectation_in_log_robust(
                    expectation=exp,
                    log_path=str(log_path),
                    dbc_path_by_channel=dbc_map,
                    drop_first_seconds=drop_first_seconds,
                )
                one = core.SingleExpectationCheck(
                    expectation=exp,
                    status=lr.status,
                    observed_value_raw=lr.observed_value_raw,
                    observed_value_norm=lr.observed_value_norm,
                    observed_time=lr.observed_time,
                    observed_channel=lr.matched_channel,
                    message=lr.message,
                    samples=list(lr.samples),
                )
                input_results.append(one)
            log_check.input_results = input_results

            output_results = []
            for exp in cond.output_conditions:
                lr = core.review_single_expectation_in_log_robust(
                    expectation=exp,
                    log_path=str(log_path),
                    dbc_path_by_channel=dbc_map,
                    drop_first_seconds=drop_first_seconds,
                )
                one = core.SingleExpectationCheck(
                    expectation=exp,
                    status=lr.status,
                    observed_value_raw=lr.observed_value_raw,
                    observed_value_norm=lr.observed_value_norm,
                    observed_time=lr.observed_time,
                    observed_channel=lr.matched_channel,
                    message=lr.message,
                    samples=list(lr.samples),
                )
                output_results.append(one)
            log_check.output_results = output_results

            inputs_ok = bool(input_results) and all(x.status == "PASS" for x in input_results)
            outputs_ok = bool(output_results) and all(x.status == "PASS" for x in output_results)

            if inputs_ok and outputs_ok:
                log_check.status = "PASS"
                log_check.message = "로그 재검토에서 모든 입력 및 모든 출력 조건 PASS"
            elif not inputs_ok:
                log_check.status = "FAIL"
                log_check.message = "로그 재검토에서도 입력 조건 일부 또는 전체 미관측"
            else:
                log_check.status = "FAIL"
                log_check.message = "로그 재검토에서도 출력 조건 일부 미관측"
            return log_check
        except Exception as e:
            log_check.status = "ERROR"
            log_check.message = f"다중 로그 재검토 오류: {e}"
            return log_check

    def _poll_multi_queue(self):
        try:
            while True:
                item = self.multi_queue.get_nowait()
                kind = item[0]
                if kind == "PROGRESS":
                    self._schedule_multi_refresh(status_by_index=item[1], delay_ms=60)
                    self._refresh_multi_summary(item[1])
                elif kind == "STAGE":
                    self._set_multi_progress(item[1], str(item[2]))
                elif kind == "DETAIL":
                    self._show_multi_selected_detail(str(item[1]))
                    self._log(f"[MULTI] {item[1]}\n")
                elif kind == "DONE":
                    self._on_multi_done(item[1])
                elif kind == "ERROR":
                    self._on_multi_error(item[1])
        except queue.Empty:
            pass
        self.after(150, self._poll_multi_queue)

    def _refresh_multi_summary(self, status_by_index):
        merged = dict(getattr(self, "multi_result_status_by_index", {}))
        merged.update(status_by_index or {})
        counts = {"PASS": 0, "FAIL": 0, "N/A": 0, "ERROR": 0, "검토중": 0}
        for s in merged.values():
            if s in ("PASS", "로그 PASS"):
                counts["PASS"] += 1
            elif s in ("FAIL", "로그 FAIL"):
                counts["FAIL"] += 1
            elif s in ("N/A", "로그 N/A"):
                counts["N/A"] += 1
            elif s in ("ERROR", "로그 ERROR"):
                counts["ERROR"] += 1
            else:
                counts["검토중"] += 1
        self.multi_result_summary_var.set(
            f"PASS {counts['PASS']} / FAIL {counts['FAIL']} / N/A {counts['N/A']} / "
            f"ERROR {counts['ERROR']} / 검토중 {counts['검토중']}"
        )

    def _multi_display_status_from_final_result(self, result):
        rt = getattr(result, "realtime_result", None)
        lg = getattr(result, "log_result", None)
        final_status = getattr(result, "final_status", "") or ""
        if lg is not None:
            # "로그 PASS"는 실시간 미통과가 로그로 PASS 보정된 경우에만 표시한다.
            if (
                final_status == "PASS"
                and getattr(lg, "status", "") == "PASS"
                and getattr(rt, "status", "") != "PASS"
            ):
                return "로그 PASS"
            if final_status == "FAIL" and getattr(lg, "status", "") == "FAIL":
                return "로그 FAIL"
            if final_status == "N/A" and getattr(lg, "status", "") == "N/A":
                return "로그 N/A"
            if final_status == "ERROR" and getattr(lg, "status", "") == "ERROR":
                return "로그 ERROR"
        return final_status

    def _on_multi_done(self, final_results):
        self._set_multi_running_ui(False)
        self.multi_status_var.set("완료")
        self._set_multi_progress(100, "다중 실행 완료")
        status_by_index = {}
        for result in final_results:
            self.results.append(result)
            self._append_result_tree(result)
            self._set_condition_result_status(result.condition, result.final_status)
            idx = self._find_multi_index_by_condition(result.condition)
            if idx is not None:
                display_status = self._multi_display_status_from_final_result(result)
                status_by_index[idx] = display_status
                self.multi_result_status_by_index[idx] = display_status
                self.multi_final_result_by_index[idx] = result
        self._refresh_multi_tc_tree(status_by_index=status_by_index)
        self._refresh_multi_summary(status_by_index)
        self._refresh_multi_signal_tree()
        self._show_multi_selected_detail("다중 실행 완료")
        if final_results and all(r.final_status == "PASS" for r in final_results) and bool(self.auto_stop_measurement_var.get()):
            self.measurement_status_var.set("Measurement: 정지")
            self._refresh_status_badges()
        self._invalidate_canoe_client("다중 실행 종료 후 다음 Start 안정화를 위해 재연결 예정")
        self._log(f"[MULTI] 다중 실행 완료: {len(final_results)}개 결과 생성\n")

    def _on_multi_error(self, message):
        self._set_multi_running_ui(False)
        self.multi_status_var.set("ERROR")
        self._set_multi_progress(0, "다중 실행 오류")
        self._invalidate_canoe_client("다중 실행 오류 후 다음 Start 안정화를 위해 재연결 예정")
        self._log(f"[ERROR] 다중 실행 오류: {message}\n")
        messagebox.showerror("다중 실행 오류", message)

    def _append_multi_result_tree(self, final_results):
        if self.multi_result_tree is None:
            return
        for r in final_results:
            idx = self._find_multi_index_by_condition(r.condition)
            if idx is None:
                continue
            self.multi_final_result_by_index[idx] = r
            self.multi_result_status_by_index[idx] = self._multi_display_status_from_final_result(r)
        self._refresh_multi_signal_tree()
