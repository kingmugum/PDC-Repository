# -*- coding: utf-8 -*-
"""
oracle_checker_gui_front_rev85.pyw

Oracle Checker GUI front launcher
- oracle_checker_gui_onebyone_rev85.py : 단일 TC 실행 GUI 본체
- oracle_checker_gui_multiple_rev85.py : 다중 실행 탭/동작 mixin
- oracle_checker_gui_txrx_rev85.py     : 차량 송수신 테스트 탭/진단 mixin (2안, 기존 Injection + Oracle)
- oracle_checker_gui_replacement_rev85.py : 테스트용 P/F 차량 테스트 (1안) 탭 mixin (완전 분리/삭제 가능)
- oracle_checker_replacement_rev85.py  : 1안 Replacement/Inline Gateway 전용 backend (rev85 Dry Run)
- oracle_checker_main_rev85.py         : 판정 core (자동 최신 rev 로드)
- oracle_checker_stimulus_rev85.py     : 실험용 입력 자극 엔진(선택 모듈, TX/RX에서만 호출)
- oracle_checker_collector_rev85.py    : 읽기 전용 CAPL Event Collector 생성/연동(선택 모듈)

같은 폴더에 위 파일들을 두고 이 front 파일을 실행합니다.

rev85:
- 1안 Replacement/Inline Gateway 실험 트랙을 별도 optional 모듈로 추가
  * 새 탭: `테스트용 P/F 차량 테스트 (1안)` — 기존 `차량 송수신 테스트`(2안) 오른쪽에 추가
  * 1안 GUI/backend는 txrx/stimulus/main/report/collector를 import하지 않으며 상태/함수도 공유하지 않음
  * front는 optional import + no-op fallback을 사용하여 1안 파일 2개를 삭제해도 기존 앱이 정상 실행
  * rev85 1안은 Dry Run 구조 검증만 제공하고 실제 CAN 차단/forwarding/output은 비활성
- 단일/다중 TC 실시간 관측에 읽기 전용 CAPL Event Collector 선택 레이어 추가(기본 ON)
  * CANoe/CANalyzer 내부 `on signal_update` 이벤트로 짧은 Expected Value 진입 이벤트를 포착
  * Python 최종 PASS/FAIL Judge는 그대로 유지하고 Collector는 관측 증거만 제공
  * Collector OFF/모듈 없음/.can 미삽입·미Compile/signature 불일치 시 기존 COM polling + ASC/BLF 재검토로 자동 fallback
  * Collector CAPL에는 output()/setSignal()/Signal.Value write가 없으며 TX/RX Stimulus Bridge와 완전히 분리
- CANoe Write 01-0083(no signal driver) 현장 피드백 반영: CANoe 실제 역송신 기본을 CAPL Frame output() 권장으로 전환
- 상단 TX/RX TC 클릭 시 입력 조건 1개를 CAN/Message/Signal/Expected 4열 후보로 자동 채움
- Stimulus 완료/원복 후 Measurement Stop 기본 ON
- Vector CAPL Bridge를 CANoe/CANalyzer 공통으로 생성하며 DBC 기반 CAN/CAN FD 1~64 byte payload chunk 전달 지원
- 기존 단일/다중/차량 송수신 및 COM 진단 기능 유지
- 다중 TC 체크 행 하늘색 / PASS 행 초록색 음영을 Windows/소형 화면에서 더 명확하게 보강
- 다중 수행은 30초 등 TC timeout으로 자동 N/A 종료하지 않고 전체 PASS 또는 사용자의 수행 완료/중단까지 감시
- 모든 Notebook 탭에 공통 가로/세로 전체 스크롤 적용 및 작은 노트북 해상도 대응
- 구성 모듈명을 rev85으로 동기화
- CAN 네트워크명 근거 기반 DBC 자동 매핑 기능 연동
- PassFail 채널 모델을 CANoe 논리 CAN1/CAN2/CAN3 고정으로 단순화하고 사용자 Ch1~Ch4 선택 제거
- 실험용 실제 입력 기능은 oracle_checker_stimulus_rev85.py로 완전 분리
  * Stimulus 모듈이 없어도 기존 단일/다중 Pass/Fail GUI는 정상 실행
  * TX/RX 실제 Stimulus worker가 자기 스레드에서 Vector COM에 재연결하여 선택 TC 단일 Signal 또는 수동 후보 Signal 1~8개 묶음 1회 테스트만 호출
  * 회사 Excel의 CAN/Message/Signal/Value 4열을 수동 후보 입력창에 복사/붙여넣기 가능
  * 후보 묶음은 전체 사전검증 후 실행하고 실제 write된 Signal을 시작 전 값으로 원복
  * CANoe Configuration / ASC / 로그 파일명에서 CAN1~CAN3 ↔ XXX-CAN 명시 근거 탐색
  * DBC 자동 설정 폴더에서 유일 후보만 자동 적용
  * 미식별/충돌/0개/복수 후보는 기존 수동 DBC 값 보존
"""

from __future__ import annotations

import sys
import atexit
import shutil
from pathlib import Path

# __pycache__ 생성 억제 및 기존 캐시 폴더 정리
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


# Windows에서 .py로 잘못 실행해도 가능하면 콘솔 노출을 줄이기 위한 시도
# .pyw 실행이 가장 권장됩니다.
def _try_hide_console():
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


_try_hide_console()

from oracle_checker_gui_onebyone_rev85 import OracleCheckerOneByOneGui, CORE_MODULE_PATH
from oracle_checker_gui_multiple_rev85 import MultipleExecutionMixin
from oracle_checker_gui_txrx_rev85 import TxRxTestMixin

# rev85: 1안 Replacement 탭은 완전 optional이다.
# 두 파일을 통째로 삭제해도 fallback mixin이 super()._build_ui()만 호출하므로 기존 앱은 정상 실행한다.
try:
    from oracle_checker_gui_replacement_rev85 import ReplacementVehicleTestMixin
    REPLACEMENT_EXPERIMENT_AVAILABLE = True
    REPLACEMENT_EXPERIMENT_IMPORT_ERROR = ""
except Exception as _replacement_import_error:
    REPLACEMENT_EXPERIMENT_AVAILABLE = False
    REPLACEMENT_EXPERIMENT_IMPORT_ERROR = f"{type(_replacement_import_error).__name__}: {_replacement_import_error}"

    class ReplacementVehicleTestMixin:
        def _build_ui(self):
            super()._build_ui()


class OracleCheckerFrontGui(ReplacementVehicleTestMixin, TxRxTestMixin, MultipleExecutionMixin, OracleCheckerOneByOneGui):
    def __init__(self):
        super().__init__()
        self.title(f"Oracle Checker - 단일/다중/차량 송수신/실험 1안 TC 수행 | core={CORE_MODULE_PATH.name}")


def main():
    app = OracleCheckerFrontGui()

    def _on_close():
        try:
            # rev85: 창 종료 중 Stimulus가 실행 중이면 먼저 stop_event를 보내
            # worker finally의 original value 원복 기회를 보장한다.
            try:
                if hasattr(app, "_txrx_stop_auto_pf"):
                    app._txrx_stop_auto_pf()
                if hasattr(app, "_txrx_stop_stimulus"):
                    app._txrx_stop_stimulus()
                auto_th = getattr(app, "txrx_auto_thread", None)
                if auto_th is not None and auto_th.is_alive():
                    auto_th.join(timeout=1.5)
                th = getattr(app, "txrx_stimulus_thread", None)
                if th is not None and th.is_alive():
                    th.join(timeout=1.0)
            except Exception:
                pass
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
