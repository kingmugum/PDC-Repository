# -*- coding: utf-8 -*-
"""
oracle_checker_replacement_rev87.py

실험용 1안(Replacement / Inline Gateway) 전용 backend.

설계 원칙
- 기존 "차량 송수신 테스트"(2안 Injection + Oracle)와 절대 import/호출 관계를 만들지 않는다.
- stable P/F observer/judge, main, report, stimulus 모듈을 import하지 않는다.
- rev87에서는 구조/전제조건 검증(Dry Run)만 제공하며 실제 CAN 송신/차단/forwarding은 수행하지 않는다.
- 이 파일과 oracle_checker_gui_replacement_rev87.py를 삭제해도 기존 PassFail은 정상 동작해야 한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ReplacementPlan:
    sender_side_can: str = ""
    vehicle_side_can: str = ""
    target_message: str = ""
    target_id: str = ""
    source_physically_isolated: bool = False
    two_segment_inline_confirmed: bool = False
    termination_checked: bool = False
    bidirectional_forwarding_reviewed: bool = False
    e2e_rules_available: bool = False


@dataclass(frozen=True)
class ReplacementCheck:
    level: str
    item: str
    message: str


def normalize_can_name(value: str) -> str:
    text = str(value or "").strip().upper().replace(" ", "")
    if text in {"1", "CAN1"}:
        return "CAN1"
    if text in {"2", "CAN2"}:
        return "CAN2"
    if text in {"3", "CAN3"}:
        return "CAN3"
    return text


def validate_replacement_plan(plan: ReplacementPlan) -> List[ReplacementCheck]:
    """실제 Bus 동작 없이 1안 구조의 전제조건만 검증한다."""
    checks: List[ReplacementCheck] = []

    sender = normalize_can_name(plan.sender_side_can)
    vehicle = normalize_can_name(plan.vehicle_side_can)

    if sender not in {"CAN1", "CAN2", "CAN3"}:
        checks.append(ReplacementCheck("BLOCK", "송신원 측 CAN", "CAN1/CAN2/CAN3 중 하나를 지정해야 합니다."))
    else:
        checks.append(ReplacementCheck("OK", "송신원 측 CAN", sender))

    if vehicle not in {"CAN1", "CAN2", "CAN3"}:
        checks.append(ReplacementCheck("BLOCK", "차량 측 CAN", "CAN1/CAN2/CAN3 중 하나를 지정해야 합니다."))
    else:
        checks.append(ReplacementCheck("OK", "차량 측 CAN", vehicle))

    if sender and vehicle and sender == vehicle:
        checks.append(ReplacementCheck(
            "BLOCK", "2-Segment 분리",
            "Replacement는 원 송신원과 차량 수신측이 서로 다른 물리/논리 CAN segment로 분리되어야 합니다."
        ))

    if not str(plan.target_message or "").strip() and not str(plan.target_id or "").strip():
        checks.append(ReplacementCheck("BLOCK", "대상 Message", "Message Name 또는 CAN ID 중 최소 하나가 필요합니다."))
    else:
        label = str(plan.target_message or "").strip() or str(plan.target_id or "").strip()
        checks.append(ReplacementCheck("OK", "대상 Message", label))

    if plan.source_physically_isolated:
        checks.append(ReplacementCheck("OK", "원 송신원 분리", "원 송신 Message가 차량 측 segment로 직접 우회하지 않는 전제를 확인했습니다."))
    else:
        checks.append(ReplacementCheck(
            "BLOCK", "원 송신원 분리",
            "원 ECU의 동일 Message가 차량 측 Bus에 그대로 남아 있으면 PassFail이 유일 송신원이 될 수 없습니다."
        ))

    if plan.two_segment_inline_confirmed:
        checks.append(ReplacementCheck("OK", "Inline 2-Segment", "CAN1↔CAN2 등 두 segment를 중간 Gateway로 연결할 전제를 확인했습니다."))
    else:
        checks.append(ReplacementCheck(
            "BLOCK", "Inline 2-Segment",
            "VN1640A 두 채널을 병렬 tap이 아니라 실제 중간 구간으로 사용할 수 있는지 확인이 필요합니다."
        ))

    if plan.termination_checked:
        checks.append(ReplacementCheck("OK", "Termination", "분리 후 각 CAN segment의 종단/저항 조건을 확인했습니다."))
    else:
        checks.append(ReplacementCheck(
            "WARN", "Termination",
            "원 배선을 분리하면 120Ω 종단 구성 및 segment별 저항 조건이 바뀔 수 있으므로 실차 연결 전 확인이 필요합니다."
        ))

    if plan.bidirectional_forwarding_reviewed:
        checks.append(ReplacementCheck("OK", "양방향 Forwarding", "대상 외 Message의 양방향 전달 필요성을 검토했습니다."))
    else:
        checks.append(ReplacementCheck(
            "WARN", "양방향 Forwarding",
            "선택 Message만 차단하고 나머지를 투명 전달하려면 CAN1→CAN2 / CAN2→CAN1 양방향 정책이 필요할 수 있습니다."
        ))

    if plan.e2e_rules_available:
        checks.append(ReplacementCheck("OK", "CRC/Alive/E2E", "Replacement frame 보호값 생성 규칙 확보로 표시되었습니다."))
    else:
        checks.append(ReplacementCheck(
            "WARN", "CRC/Alive/E2E",
            "DBC만으로 OEM CRC/Alive/E2E 규칙이 보장되지 않습니다. 실제 Replacement 구현 전 별도 확인이 필요합니다."
        ))

    checks.append(ReplacementCheck(
        "INFO", "rev87 실행 범위",
        "rev87 1안 모듈은 Dry Run 전용입니다. 실제 CAN 차단/forwarding/output은 의도적으로 구현하지 않았습니다."
    ))
    return checks


def summarize_replacement_checks(checks: List[ReplacementCheck]) -> str:
    blocks = sum(1 for c in checks if c.level == "BLOCK")
    warns = sum(1 for c in checks if c.level == "WARN")
    if blocks:
        return f"구조 검증: BLOCK {blocks} / WARN {warns} — 실차 Replacement 구현 전제 미충족"
    if warns:
        return f"구조 검증: BLOCK 0 / WARN {warns} — PoC 설계 가능, 실차 활성 전 추가 확인 필요"
    return "구조 검증: BLOCK 0 / WARN 0 — 구조 전제 확인됨 (단, rev87은 Dry Run 전용)"
