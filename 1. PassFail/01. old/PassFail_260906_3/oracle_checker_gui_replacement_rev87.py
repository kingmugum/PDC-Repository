# -*- coding: utf-8 -*-
"""
oracle_checker_gui_replacement_rev87.py

"테스트용 P/F 차량 테스트 (1안)" 탭 전용 GUI mixin.

완전 분리 규칙
- "차량 송수신 테스트"(2안) / oracle_checker_gui_txrx_rev87.py를 import하지 않는다.
- oracle_checker_stimulus_rev87.py, main, report, collector도 import하지 않는다.
- 1안 전용 backend인 oracle_checker_replacement_rev87.py만 사용한다.
- 이 GUI 파일과 backend 파일을 삭제하면 front의 optional fallback에 의해 탭만 사라지고 기존 앱은 정상 실행된다.
- rev87은 구조 검증 Dry Run만 제공하고 실제 CAN Gateway/Replacement는 비활성이다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

import oracle_checker_replacement_rev87 as _replacement


class ReplacementVehicleTestMixin:
    """실험용 1안 Replacement / Inline Gateway 탭."""

    def _build_ui(self):
        super()._build_ui()
        self._init_replacement_state()
        self._build_replacement_tab()

    def _init_replacement_state(self):
        self.replacement_tab = None
        self.replacement_scroll_content = None
        self.replacement_sender_can_var = tk.StringVar(value="CAN1")
        self.replacement_vehicle_can_var = tk.StringVar(value="CAN2")
        self.replacement_target_message_var = tk.StringVar(value="PSS_DRV_FD_01_200ms")
        self.replacement_target_id_var = tk.StringVar(value="0x3FB")

        self.replacement_source_isolated_var = tk.BooleanVar(value=False)
        self.replacement_inline_confirmed_var = tk.BooleanVar(value=False)
        self.replacement_termination_checked_var = tk.BooleanVar(value=False)
        self.replacement_bidirectional_reviewed_var = tk.BooleanVar(value=False)
        self.replacement_e2e_available_var = tk.BooleanVar(value=False)

        self.replacement_status_var = tk.StringVar(
            value="1안은 rev87에서 구조 검증 Dry Run 전용입니다. 실제 CAN 차단/Forwarding은 실행하지 않습니다."
        )
        self.replacement_result_text = None

    def _build_replacement_tab(self):
        if self.notebook is None:
            return

        self.replacement_tab, self.replacement_scroll_content = self._create_scrollable_notebook_tab(
            "테스트용 P/F 차량 테스트 (1안)", padding=8
        )
        parent = self.replacement_scroll_content
        parent.columnconfigure(0, weight=1)

        notice = ttk.LabelFrame(parent, text="실험 트랙 / 언제든 폐기 가능한 완전 분리 모듈")
        notice.grid(row=0, column=0, sticky="ew", padx=2, pady=(2, 8))
        notice.columnconfigure(0, weight=1)
        ttk.Label(
            notice,
            text=(
                "목적: 기존 차량 ECU의 대상 Message를 차단하고 PassFail/CANoe가 선택 Message의 유일 송신원이 되는 "
                "Replacement / Inline Gateway(1안)를 별도 실험합니다.\n"
                "rev87에서는 실제 Bus를 건드리지 않고, 물리 구조와 전제조건만 검증합니다. "
                "기존 '차량 송수신 테스트'(2안)와 코드/상태/함수를 공유하지 않습니다."
            ),
            wraplength=1050,
            justify="left",
            foreground="#7C2D12",
        ).grid(row=0, column=0, sticky="w", padx=8, pady=8)

        cfg = ttk.LabelFrame(parent, text="1안 독립 구성 입력 (2안 설정을 재사용하지 않음)")
        cfg.grid(row=1, column=0, sticky="ew", padx=2, pady=(0, 8))
        for c in range(4):
            cfg.columnconfigure(c, weight=1 if c in (1, 3) else 0)

        ttk.Label(cfg, text="원 송신원 측 CAN").grid(row=0, column=0, sticky="w", padx=6, pady=5)
        ttk.Combobox(
            cfg, textvariable=self.replacement_sender_can_var,
            values=["CAN1", "CAN2", "CAN3"], state="readonly", width=16
        ).grid(row=0, column=1, sticky="w", padx=6, pady=5)

        ttk.Label(cfg, text="차량 수신측 CAN").grid(row=0, column=2, sticky="w", padx=6, pady=5)
        ttk.Combobox(
            cfg, textvariable=self.replacement_vehicle_can_var,
            values=["CAN1", "CAN2", "CAN3"], state="readonly", width=16
        ).grid(row=0, column=3, sticky="w", padx=6, pady=5)

        ttk.Label(cfg, text="Target Message").grid(row=1, column=0, sticky="w", padx=6, pady=5)
        ttk.Entry(cfg, textvariable=self.replacement_target_message_var, width=42).grid(
            row=1, column=1, sticky="ew", padx=6, pady=5
        )
        ttk.Label(cfg, text="Target CAN ID").grid(row=1, column=2, sticky="w", padx=6, pady=5)
        ttk.Entry(cfg, textvariable=self.replacement_target_id_var, width=18).grid(
            row=1, column=3, sticky="w", padx=6, pady=5
        )

        pre = ttk.LabelFrame(parent, text="실차 Replacement 구현 전 체크 포인트")
        pre.grid(row=2, column=0, sticky="ew", padx=2, pady=(0, 8))
        pre.columnconfigure(0, weight=1)

        checks = [
            ("원 송신 ECU/Message가 차량 측 Bus로 직접 들어가지 않도록 물리적으로 분리 가능",
             self.replacement_source_isolated_var),
            ("VN1640A 두 채널을 이용해 원 송신측 ↔ CANoe ↔ 차량측 2-Segment Inline 구성 가능",
             self.replacement_inline_confirmed_var),
            ("분리 후 각 CAN Segment의 termination/저항 조건 확인",
             self.replacement_termination_checked_var),
            ("Target Message 외 통신을 유지하기 위한 양방향 Forwarding 정책 검토",
             self.replacement_bidirectional_reviewed_var),
            ("Target Message의 CRC / Alive Counter / E2E 생성 규칙 확보",
             self.replacement_e2e_available_var),
        ]
        for row, (text, var) in enumerate(checks):
            ttk.Checkbutton(pre, text=text, variable=var).grid(row=row, column=0, sticky="w", padx=8, pady=3)

        actions = ttk.Frame(parent)
        actions.grid(row=3, column=0, sticky="ew", padx=2, pady=(0, 8))
        ttk.Button(actions, text="1안 구성 검증 (송신 없음)", command=self._replacement_validate_dry_run).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(actions, text="1안 입력 초기화", command=self._replacement_reset).pack(side=tk.LEFT)
        ttk.Label(actions, textvariable=self.replacement_status_var, foreground="#374151").pack(
            side=tk.LEFT, padx=12
        )

        result = ttk.LabelFrame(parent, text="1안 Dry Run 결과")
        result.grid(row=4, column=0, sticky="nsew", padx=2, pady=(0, 8))
        result.columnconfigure(0, weight=1)
        result.rowconfigure(0, weight=1)
        self.replacement_result_text = ScrolledText(result, height=17, wrap=tk.WORD)
        self.replacement_result_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.replacement_result_text.insert(
            "1.0",
            "[rev87] 1안은 아직 실제 차량 송신/차단 기능을 실행하지 않습니다.\n"
            "위 체크 항목을 확인한 뒤 '1안 구성 검증 (송신 없음)'으로 구조적 BLOCK/WARN을 확인하십시오.\n\n"
            "[삭제 규칙]\n"
            "- oracle_checker_gui_replacement_rev87.py\n"
            "- oracle_checker_replacement_rev87.py\n"
            "두 파일을 삭제하면 front의 optional fallback으로 이 탭만 사라지고 2안/기존 P/F는 그대로 실행됩니다.\n"
        )

    def _replacement_make_plan(self):
        return _replacement.ReplacementPlan(
            sender_side_can=self.replacement_sender_can_var.get(),
            vehicle_side_can=self.replacement_vehicle_can_var.get(),
            target_message=self.replacement_target_message_var.get(),
            target_id=self.replacement_target_id_var.get(),
            source_physically_isolated=bool(self.replacement_source_isolated_var.get()),
            two_segment_inline_confirmed=bool(self.replacement_inline_confirmed_var.get()),
            termination_checked=bool(self.replacement_termination_checked_var.get()),
            bidirectional_forwarding_reviewed=bool(self.replacement_bidirectional_reviewed_var.get()),
            e2e_rules_available=bool(self.replacement_e2e_available_var.get()),
        )

    def _replacement_validate_dry_run(self):
        plan = self._replacement_make_plan()
        checks = _replacement.validate_replacement_plan(plan)
        summary = _replacement.summarize_replacement_checks(checks)
        self.replacement_status_var.set(summary)

        if self.replacement_result_text is not None:
            self.replacement_result_text.delete("1.0", tk.END)
            self.replacement_result_text.insert("1.0", summary + "\n\n")
            for check in checks:
                self.replacement_result_text.insert(
                    tk.END, f"[{check.level}] {check.item}: {check.message}\n"
                )
            self.replacement_result_text.insert(
                tk.END,
                "\n※ 이 결과는 구조 전제조건 검토이며 실제 차량 기능 PASS/FAIL 판정 결과가 아닙니다.\n"
                "※ rev87에서는 실제 CAN output()/Gateway forwarding을 호출하는 함수가 없습니다.\n"
            )

    def _replacement_reset(self):
        self.replacement_sender_can_var.set("CAN1")
        self.replacement_vehicle_can_var.set("CAN2")
        self.replacement_target_message_var.set("PSS_DRV_FD_01_200ms")
        self.replacement_target_id_var.set("0x3FB")
        self.replacement_source_isolated_var.set(False)
        self.replacement_inline_confirmed_var.set(False)
        self.replacement_termination_checked_var.set(False)
        self.replacement_bidirectional_reviewed_var.set(False)
        self.replacement_e2e_available_var.set(False)
        self.replacement_status_var.set(
            "1안 입력을 초기화했습니다. 실제 CAN 차단/Forwarding은 여전히 비활성입니다."
        )
        if self.replacement_result_text is not None:
            self.replacement_result_text.delete("1.0", tk.END)
            self.replacement_result_text.insert(
                "1.0", "[rev87] 1안 입력 초기화 완료. Dry Run 검증만 가능합니다.\n"
            )
