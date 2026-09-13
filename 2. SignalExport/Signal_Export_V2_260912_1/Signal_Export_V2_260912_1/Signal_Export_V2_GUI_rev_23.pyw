# -*- coding: utf-8 -*-
"""
[V2 GUI REV 23 변경점]
- Main CATEGORIES에 추가된 CONNECT 카테고리를 일반 카테고리 콤보박스에서 자동 노출
- ASC/BLF 파일명 선두 토큰 커넥트 / UX / Connect / connect를 CONNECT로 자동감지
- 기존 BLUELINK_CCS의 connected 별칭은 유지하되, 선두 토큰 connect는 신규 CONNECT로 명시 재배정하여 별칭 충돌 제거
- 기존 1~11 카테고리 자동감지/CAN-DBC 일괄 검증/부분 적용 금지 정책은 유지

[V2 GUI REV 22 변경점]
- 실행 로그 영역을 약 15행이 안정적으로 보이는 고정 요청 높이로 구성
- 실행 로그 영역은 전체 페이지 Canvas의 세로 스크롤 대상에 포함하고, 우측 고정 세로 스크롤바를 아래로 내리면 로그 영역 전체를 확인 가능
- 로그 자체의 ScrolledText 내부 스크롤바는 유지하여 긴 실행 로그도 기존처럼 탐색 가능
- 기존 Step/AI/Report/설정/서브프로세스/로그 판정 기능은 변경하지 않음

[V2 GUI REV 21 변경점]
- subprocess stderr의 Python Warning(FutureWarning/DeprecationWarning 등)과 실제 오류를 구분
- Python Warning은 로그에 남기되 GUI 상태를 stderr 오류/주의 상태로 바꾸지 않고 실행을 계속
- 실제 Traceback/Exception/Error 또는 기타 stderr만 기존 경고/오류 상태 정책 적용

[V2 GUI REV 20 변경점]
- 메인 GUI 전체를 세로 스크롤 가능한 Canvas에 배치하고 우측에 고정 세로 스크롤바 추가
- 화면 아래 실행 로그가 작게 보일 때 스크롤바를 내려 로그 영역을 충분히 확인 가능
- TestCase Excel이 OLE2 보호/권한 문서로 의심되어 Workbook을 찾지 못할 때 전용 경고 팝업 표시
- 경고는 동일 실행 중 1회만 표시하며 기존 Step/설정/로그 기능은 유지

[V2 GUI REV 19 변경점]
- 필요 패키지 확인/설치에 xlrd>=2.0.1 추가
- xlrd가 설치되어 있어도 2.0.1 미만이면 누락으로 판정하여 재설치 대상에 포함
- TestCase Excel 도움말을 .xls/.xlsx/.xlsm 호환 입력으로 갱신

[V2 GUI REV 18 변경점]
- 실행 단계 영역 하단에 있던 'Step 2 AI 후보 보강 사용' 체크를 우측 하단의 별도 옵션 영역으로 이동
- 유효 CAN 시그널 설정 & 출력 txt 파일 설정 박스는 Step 6 시간별 상세 변화 생성 옵션까지만 표시
- Step 2 AI 옵션의 기본값 OFF/비저장/실행 동작은 유지

[V2 GUI REV 17 변경점]
- Step 2 AI 후보 보강 체크 옵션 추가
- 기본값 OFF이며 GUI 자동 저장/복원 대상에서 제외하여 프로그램을 새로 열 때 항상 OFF
- 옵션 ON + Step 2 실행 시 TestCase Excel/API Key 사전검사 추가
- 옵션 OFF에서는 기존 Step 2 동작에 개입하지 않음

[V2 GUI REV 16 변경점]
- GPT 기본 모델을 gpt-5.6-terra로 변경
- GPT 모델 선택 목록에 gpt-5.6-terra를 추가하고 기존 gpt-5.4 / gpt-5.2 선택 기능 유지
- GUI 모델 목록/기본값은 Main의 GPT_MODEL_OPTIONS / GPT_MODEL을 우선 사용하여 상호 불일치 방지

[V2 GUI REV 15 변경점]
- CAN1~CAN4 사용 체크박스의 신규/초기 기본값을 모두 체크 상태로 변경
- 과거 CH→CAN 설정 변수·저장·복원·Main 전달 경로를 완전히 제거
- 자동감지 중단 팝업 하단에 중단 사유와 기존 설정 보존 여부를 별도 표시
- VN1640A 물리 채널 선택란 제거, 로그의 CAN1~CAN4를 DBC와 직접 매핑
- CAN1~CAN4별 활성/비활성 체크 추가, 비활성 CAN은 분석에서 제외
- CANx당 DBC 1개만 선택 가능하도록 GUI/Main 이중 검증
- 자동감지는 파일명 규칙이 완전할 때만 일괄 적용하며, 미인식/형식오류/충돌/복수 DBC 후보가 있으면 아무 값도 변경하지 않음
- 자동감지 성공 시 감지된 CAN만 활성화하고 미감지 CAN은 비활성/N/A 처리
- 로그 내용 기반 또는 유사도 기반 임의 추정은 수행하지 않음

Signal_Export_V2_GUI_rev_23.pyw

[V2 REV 12 변경점]
- BLUELINK_CCS 자동감지 한글 단축 별칭에 "블루", "링크" 추가
- 블루_... ASC 및 링크_... BLF의 선두 토큰을 7. 블루링크, CCS 카테고리로 자동 선택
- 기존 블루링크/bluelink/blue/ccs/connected 별칭 유지 (connect는 V2 GUI rev23부터 CONNECT로 재배정)

Signal_Export_V2_GUI_rev_11.pyw

목적
- main*.py / step_1~step_7 + Report 파이프라인을 Tkinter GUI에서 실행
- GUI와 main/step 파일은 같은 폴더 배치 전제
- 최신 rev main 파일 자동 선택
- subprocess 기반 실행으로 강제 종료 가능
- GPT/Gemini 선택 시 우측 AI 표시 즉시 반영
- 상태 1줄 표시 지원
- 독립 Report 생성 및 결과 레포트 생성 버튼 지원

[로그 CAN 직접 매핑 구조]
- CAN1~CAN4 각각에 대해 사용 여부와 DBC 1개를 선택
- 비활성 CAN은 분석에서 제외
- 실행 시 로그 채널 번호 기반 can_config + dbc_name_by_ch 동적 생성
- 물리 채널 선택 및 CH→CAN 파일명 변경 기능 제거

[GPT 모델 선택 관련 변경]
- GPT 선택 시 기본 모델은 gpt-5.6-terra
- 사용자는 필요 시 gpt-5.4 또는 기존 gpt-5.2도 선택 가능
- GUI는 Main의 GPT_MODEL / GPT_MODEL_OPTIONS를 우선 사용하여 모델 정책을 동기화
- Gemini 선택 기능은 그대로 유지

[REV 17 변경점]
- 시간별 옵션을 2개로 분리
  1) step 1 ~ 4 시간 별 txt 파일 생성 (추천)
     - 기본값: 체크됨(True)
  2) step 5 시간 별 txt 파일 생성
     - step_5_enable_time_folder
     - 기본값: 체크 해제(False)
- Report 생성 기능 유지
- step 5 시간 별 txt 파일 생성 옵션을 AI 영역에서 유효 CAN 시그널/출력 txt 설정 영역으로 이동
- 설정 미리보기 로그에서 API Key를 마스킹 처리
- Report 단독 생성 시 DBC/채널 미선택 상태에서도 샘플/기존 결과 레포트 생성 가능

[REV 18 변경점]
- 실행 단계 영역에서 Report 체크박스를 분리하고, 그 자리에 실패파일만 재실행 옵션을 복구
- Report 결과 레포트 생성 체크박스는 우측 AI 박스와 로그 텍스트 분할 옵션 사이의 별도 Report 옵션 박스로 이동
- GUI 실행 파일 위치에 signal_auto_gui_settings.json을 자동 저장/자동 복원하여 마지막 선택 옵션을 유지

[REV 19 변경점]
- 레포트 옵션 안내 문구 삭제
- 레포트 옵션 체크박스 문구를 "실행 완료 시 결과 레포트 생성"으로 변경

[REV 20 변경점]
- 완료된 답변파일 Pass 옵션 추가
  * 기존 AI답변 split/병합본을 검증 후 재사용
  * 누락 또는 불완전 split만 추가 처리하도록 Step 5에 전달

[REV 26 변경점]
- Step 6 DBC 근거/AI 판단 설명 실행 옵션 추가
- Step 5 AI답변 결과 중 연관 있는 Message:Signal에 대해 DBC 상세 근거를 AI결과판단 폴더로 생성

[REV 21 변경점]
- 진행률 표시를 전체 진행률 / 현재 Step 진행률 2줄 막대바로 분리
- 전체 진행률은 체크된 실행 Step 기준 현재 Step 위치를 표시
- Step 5 진행률은 메세지별 + 시간별 대상 CASE 전체 수 기준으로 별도 표시
- Step 5 내부 split 진행률은 하단 막대바에 반영하지 않음

[REV 23 변경점]
- 레포트 상태 표시 영역을 절반 폭 중앙 정렬 구조로 변경
- 시작 시 로그 CAN-DBC 매칭 상태를 즉시 경고로 표시하지 않고 대기중으로 유지
- 새로고침 버튼으로 base/log 폴더, DBC, API Key, 상태 재스캔 지원
- 자동감지 버튼으로 ASC/BLF 파일명 CAN 매핑을 기준으로 CAN1~CAN4 DBC 자동 선택 지원
- 자동감지 시 ASC/BLF 파일명 맨 앞 카테고리 토큰을 감지하여 카테고리 자동 선택/충돌/미인식 경고 지원
- 로그 폴더명 감지를 log파일/로그파일/log file/로그폴더/로그 폴더/로그 파일 등으로 확장
- ASC CAN 코드 P→P1, B→B1 기본 보정 및 DBC 코드 B1/B2/C/E/M/P1/P2/BDC 인식 지원

[REV 31 변경점]
- 상단의 파일 찾기/새로고침/도움말 버튼을 프로젝트 폴더 입력창 우측 동일 행에 순서대로 배치
- 자동감지 버튼을 상단에서 제거하고 DBC 설정 영역 우측 상단으로 이동
- 자동감지의 기존 기능/색상 및 나머지 GUI 기능 계약은 변경하지 않음


[V2 REV 11 변경점]
- 자동감지 대상을 ASC/BLF 파일명에서 ASC+BLF 파일명으로 확장
- 로그 폴더 안의 BLF만 있는 경우에도 CAN/DBC/카테고리 자동감지를 수행
- 자동감지/매칭 상태 문구를 ASC 기준에서 로그 파일(ASC/BLF) 기준으로 보정

[V2 REV 10 변경점]
- GLOBAL을 카테고리 콤보박스에서 제거
- 카테고리 선택란 오른쪽에 별도 "글로벌 사용" 체크박스 추가
- 글로벌 사용 체크 시 카테고리 콤보 및 Step/AI/Drop 옵션 비활성화, 실행 JSON은 active_category 유지 + global_mode=True 전달

[REV 33 변경점]
- 기존 Step 7 DBC 근거/AI 판단 기능을 Step 6으로 변경
- GUI 실행 단계 문구를 'Step 6  DBC 근거/AI 판단 출력'으로 변경
- Report는 단계 번호에서 제외하고 레포트 옵션 영역에서 독립 실행/상태 표시 유지
- 기존 실행/자동감지/API/Report/산출물 기능은 변경하지 않음

[REV 34 변경점]
- 도움말 내용을 사용자 실행 절차 중심으로 전면 교체
- 도움말 기본 가로 폭은 지정 기준 문장이 한 줄로 표시될 수 있도록 폰트 실측값으로 계산
- 기준보다 긴 도움말 문장은 단어 단위 자동 줄바꿈
- 그 외 GUI/실행/자동감지/API/Report/산출물 기능은 변경하지 않음

[REV 36 변경점]
- Step 6 표시명을 "입력/출력/제외 시그널 분류"로 변경
- 유효 CAN 설정 영역에 "asc 파일 내 ch 이름을 CAN으로 변경" 옵션 추가(기본 해제)
- 전체/현재 진행률은 진행 중 항목을 완료 처리하지 않고, 완료된 이전 항목 수 기준으로 표시
- 최종 종료 시에만 전체/현재 막대바를 100% 완료로 표시

[REV 39 변경점]
- 도움말에 90,000자 초과 시 내부 예외 안전 분할 정책을 반영
- 실패파일만 재실행의 Step 5 → Step 6 → Step 7 연계 설명을 갱신

[V2 REV 05 변경점]
- 자동감지 카테고리 별칭에 "보조" 추가
- 보조_042_... ASC 파일을 ADAS(6. 운전자 보조)로 자동 인식

[V2 REV 04 변경점]
- 유효 CAN 설정의 CH→CAN 체크박스를 제거하고 즉시 실행 버튼으로 변경
- 도움말 4번에 자동감지 파일명 정상/오류 예시 추가
- 완료 결과 폴더를 AI_문의용_출력/AI답변_결과/메세지별로 수정

[V2 REV 03 변경점]
- 자동감지 결과 팝업의 가로 폭 936px 유지, 기본 세로 높이를 650px에서 325px로 축소
- 자동감지 결과 팝업을 항상 메인 창 중앙에 배치
- 상태 행의 상태 문구와 ASC-DBC 상태 버튼 사이에 "완료 결과 폴더 열기" 버튼 추가
- 파이프라인 정상 완료 후 가장 마지막으로 수행한 단계의 결과 폴더를 Windows 탐색기로 열 수 있도록 지원

[V2 REV 06 변경점]
- ASC 파일명 CH → CAN 변경 버튼 문구를 "로그파일명 CH → CAN"으로 단축

[V2 GUI REV 08 변경점]
- Step 3 ASC 프레임 방향 기본값을 자동(Rx 우선)으로 변경
- 자동 모드는 기본 Rx 분석을 수행하되, Rx가 매우 적고 Tx가 충분히 많을 때만 Rx+Tx로 자동 전환
- 사용자는 자동 / Rx만 / Tx만 / Rx+Tx 중 하나를 직접 선택 가능

[V2 GUI REV 07 변경점]
- Step 3 ASC 프레임 방향 선택 추가: Rx만(일반 Real bus) / Tx만(Simulated bus) / Rx+Tx(전체)
- CH1 선택 옵션 추가: simulated bus 재로깅 ASC의 CH1/2/3 매핑 지원
- 로그파일명 CH→CAN 버튼 내부 설정 생성 함수명을 최신 함수로 수정
- 버튼을 결과 레포트 생성 버튼과 동일한 ttk 기본 스타일로 변경
- 버튼 폭은 새 문구가 잘리지 않는 수준으로 고정
- 배포 ZIP에는 각 모듈의 최신 REV 파일만 포함

[V2 REV 02 변경점]
- 자동감지 결과 팝업을 전용 창으로 변경하고 가로/세로 크기를 각각 30% 확대
- 자동감지 결과에서 CAN1/CAN2/CAN3/CAN4 토큰은 있으나 CAN 코드 형식을 해석하지 못한 경우를 별도 감지
- 해당 CAN의 DBC가 자동 설정되지 않았을 때 빨간색 경고 문구 표시
- 기존에 선택된 DBC 값은 임의로 지우지 않고 사용자가 확인하도록 유지

[REV 38 변경점]
- 실행 단계를 Step 1~7로 확장
- Step 6: 관련 시그널 상세 변화 추출
- Step 7: 입력/출력/제외 시그널 분류
- 그룹형 상세 TXT는 항상 생성하므로 선택 체크박스 제거
- 일반 로그 텍스트 split/병합 옵션 UI 제거
- 기존 Step 5 시간별 옵션을 Step 6 시간별 상세 변화 생성 옵션으로 변경

"""

from __future__ import annotations

import os
import sys
import re
import json
import queue
import threading
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from tkinter import font as tkfont
import importlib.util
import importlib.metadata as importlib_metadata


def _handoff_to_latest_gui_revision() -> None:
    """오래된 GUI rev를 직접 실행해도 같은 폴더의 최신 GUI rev로 인계한다."""
    code_dir = Path(__file__).resolve().parent
    base = "Signal_Export_V2_GUI"
    rx = re.compile(rf"^{re.escape(base)}(?:[_\-.])rev(?:[_\-.])?(\d+)\.pyw$", re.IGNORECASE)
    best = None
    for path in code_dir.glob(f"{base}*.pyw"):
        match = rx.match(path.name)
        if not match:
            continue
        rev = int(match.group(1))
        if best is None or rev > best[0]:
            best = (rev, path)
    if best is None:
        return
    latest = best[1].resolve()
    current = Path(__file__).resolve()
    if latest == current:
        return
    print(f"[INFO] Newer V2 GUI detected: {latest.name}")
    os.execv(sys.executable, [sys.executable, str(latest), *sys.argv[1:]])


if __name__ == "__main__":
    _handoff_to_latest_gui_revision()


# =========================================================
# Signal Export V2 Main 로딩
# =========================================================
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


def find_v2_main_file(base_dir: Path) -> Path:
    """Signal_Export_V2_Main_rev_xx.py 중 가장 높은 rev를 선택한다."""
    base = "Signal_Export_V2_Main"
    rx = re.compile(rf"^{re.escape(base)}(?:[_\-.])rev(?:[_\-.])?(\d+)\.py$", re.IGNORECASE)
    best = None
    for path in base_dir.glob(f"{base}*.py"):
        match = rx.match(path.name)
        if not match:
            continue
        rev = int(match.group(1))
        if best is None or rev > best[0]:
            best = (rev, path)
    selected = best[1] if best else base_dir / f"{base}.py"
    if selected.is_file():
        return selected
    raise FileNotFoundError(
        "Signal_Export_V2_Main_rev_xx.py를 찾지 못했습니다.\n"
        "GUI와 Main 파일을 같은 폴더에 두세요."
    )


def _load_pipeline_module(main_file: Path):
    return _load_module_by_file(main_file, unique_name_hint="signal_export_v2_main")


def load_pipeline_module_from_gui_dir():
    gui_dir = Path(__file__).resolve().parent
    selected = find_v2_main_file(gui_dir)
    print(f"[INFO] GUI selected pipeline main: {selected.name}")
    return _load_pipeline_module(selected), selected


try:
    pipeline, pipeline_main_path = load_pipeline_module_from_gui_dir()
except Exception as e:
    raise ImportError(
        "Signal Export V2 Main을 로드하지 못했습니다.\n"
        "GUI와 Signal_Export_V2_Main_rev_xx.py를 같은 폴더에 두었는지 확인하세요.\n"
        f"원인: {e}"
    ) from e


# =========================================================
# 유틸
# =========================================================
CAN_NAMES = ["CAN1", "CAN2", "CAN3", "CAN4"]

# GPT 모델 정책은 Main을 단일 기준으로 우선 사용한다.
# 구 Main과 함께 실행되는 경우에도 신규 GUI 자체 fallback은 gpt-5.6-terra를 기본으로 한다.
DEFAULT_GPT_MODEL = str(getattr(pipeline, "GPT_MODEL", "gpt-5.6-terra") or "gpt-5.6-terra").strip()
_raw_gpt_model_options = getattr(
    pipeline,
    "GPT_MODEL_OPTIONS",
    ("gpt-5.6-terra", "gpt-5.4", "gpt-5.2"),
)
GPT_MODEL_OPTIONS = tuple(
    dict.fromkeys(
        [DEFAULT_GPT_MODEL]
        + [str(item).strip() for item in _raw_gpt_model_options if str(item).strip()]
        + ["gpt-5.6-terra", "gpt-5.4", "gpt-5.2"]
    )
)

ASC_FRAME_DIRECTION_OPTIONS = [
    ("auto", "자동(Rx 우선, Tx 많으면 Rx+Tx)"),
    ("rx", "Rx만(일반 Real bus)"),
    ("tx", "Tx만(Simulated bus)"),
    ("both", "Rx+Tx(전체)"),
]
ASC_FRAME_DIRECTION_VALUE_TO_LABEL = {value: label for value, label in ASC_FRAME_DIRECTION_OPTIONS}
ASC_FRAME_DIRECTION_LABEL_TO_VALUE = {label: value for value, label in ASC_FRAME_DIRECTION_OPTIONS}


def asc_frame_direction_value_to_label(value: str) -> str:
    text = str(value or "auto").strip().lower()
    if text in ("자동", "auto", "rxauto", "autofallback", "rxpriority"):
        text = "auto"
    if text in ("all", "rxtx", "txrx", "rx+tx", "tx+rx"):
        text = "both"
    return ASC_FRAME_DIRECTION_VALUE_TO_LABEL.get(text, ASC_FRAME_DIRECTION_VALUE_TO_LABEL["auto"])


def asc_frame_direction_label_to_value(label: str) -> str:
    text = str(label or "").strip()
    if text in ASC_FRAME_DIRECTION_LABEL_TO_VALUE:
        return ASC_FRAME_DIRECTION_LABEL_TO_VALUE[text]
    lower = text.lower()
    if lower in ASC_FRAME_DIRECTION_VALUE_TO_LABEL:
        return lower
    if "자동" in text or "auto" in lower or "우선" in text:
        return "auto"
    if "tx" in lower and "rx" in lower:
        return "both"
    if "tx" in lower or "sim" in lower:
        return "tx"
    if "rx" in lower or "real" in lower:
        return "rx"
    return "auto"

REQUIRED_PYTHON_PACKAGES = [
    ("python-can", "can"),
    ("cantools", "cantools"),
    ("pandas", "pandas"),
    ("openpyxl", "openpyxl"),
    ("xlrd>=2.0.1", "xlrd"),
    ("requests", "requests"),
    ("openai", "openai"),
]




PYTHON_WARNING_RE = re.compile(
    r"\b(?:FutureWarning|DeprecationWarning|PendingDeprecationWarning|UserWarning|RuntimeWarning|"
    r"SyntaxWarning|ResourceWarning|ImportWarning|UnicodeWarning|BytesWarning|EncodingWarning):"
)
STDERR_ERROR_RE = re.compile(
    r"Traceback \(most recent call last\):|"
    r"\b(?:RuntimeError|ImportError|ModuleNotFoundError|ValueError|TypeError|KeyError|IndexError|"
    r"OSError|IOError|FileNotFoundError|PermissionError|XLRDError|AssertionError|SystemError|"
    r"MemoryError|TimeoutError|ConnectionError|Exception):"
)


def classify_stderr_line(line: str, warning_continuation_lines: int = 0) -> tuple[str, int]:
    """Classify one stderr line without treating normal Python warnings as pipeline errors."""
    text = str(line or "")
    if PYTHON_WARNING_RE.search(text):
        # Python warnings normally print one following source-code line.
        return "python_warning", 1
    if warning_continuation_lines > 0 and text.strip() and not STDERR_ERROR_RE.search(text):
        return "python_warning_continuation", max(0, warning_continuation_lines - 1)
    if not text.strip():
        return "blank", 0
    if "[ERROR]" in text or STDERR_ERROR_RE.search(text):
        return "error", 0
    return "stderr", 0


# =========================================================
# subprocess 로그 리더
# =========================================================
class StreamReaderThread(threading.Thread):
    def __init__(self, stream, q: queue.Queue, tag: str):
        super().__init__(daemon=True)
        self.stream = stream
        self.q = q
        self.tag = tag

    def run(self):
        try:
            for line in iter(self.stream.readline, ""):
                if line == "":
                    break
                self.q.put((self.tag, line))
        except Exception as e:
            self.q.put(("STDERR", f"[GUI][StreamReaderError] {e}\n"))
        finally:
            try:
                self.stream.close()
            except Exception:
                pass


# =========================================================
# GUI
# =========================================================
class PipelineGui(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Signal Export V2")

        self.default_window_width = 1100
        self.default_window_height = 790
        self.left_area_default_width = 640
        self.right_area_default_width = 430
        self.left_area_min_width = self.left_area_default_width // 2
        self.right_area_min_width = self.right_area_default_width // 2
        self.middle_gap_width = 10
        self.outer_padding_width = 20

        self.geometry(f"{self.default_window_width}x{self.default_window_height}+80+90")
        self.minsize(
            self.left_area_min_width + self.right_area_min_width + self.middle_gap_width + self.outer_padding_width,
            self.default_window_height,
        )

        self.log_queue: queue.Queue = queue.Queue()
        self.process: Optional[subprocess.Popen] = None
        self.stdout_reader: Optional[StreamReaderThread] = None
        self.stderr_reader: Optional[StreamReaderThread] = None
        self.is_running = False
        self.selected_main_file = pipeline_main_path
        self.stop_requested_by_user = False
        self.help_window: Optional[tk.Toplevel] = None
        self._pending_report_open_once = False
        self._last_match_detail_lines: list[str] = []
        self._global_mode_active = False
        self._pre_global_state: dict = {}
        self._excel_security_warning_shown = False
        self._stderr_warning_continuation_lines = 0
        self._python_warning_notice_shown = False

        # GUI 옵션 자동 저장 파일은 GUI 파이썬 파일과 같은 폴더에 둔다.
        self._gui_settings_path = Path(__file__).resolve().with_name("signal_auto_gui_settings.json")
        self._settings_save_after_id = None
        self._settings_restore_in_progress = False

        self._create_variables()
        self._create_fonts()
        self._build_ui()
        self._load_defaults_from_pipeline()
        self._load_saved_gui_settings()
        self._refresh_project_status()
        self._toggle_drop_first_seconds_state()
        self._toggle_change_threshold_visibility()
        self._update_ai_provider_ui()
        self._apply_category_mode()
        self._reset_step_statuses()
        self._refresh_can_row_states()
        self._bind_settings_autosave()
        self._refresh_required_packages_status(show_popup=False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_log_queue()

    # =========================================================
    # 변수
    # =========================================================
    def _create_variables(self) -> None:
        self.project_dir_var = tk.StringVar(value=str(Path(__file__).resolve().parent))

        self.run_step_1_var = tk.BooleanVar(value=True)
        self.run_step_2_var = tk.BooleanVar(value=True)
        # 명시적으로 체크한 현재 실행에서만 사용. 설정 파일에 저장/복원하지 않는다.
        self.step_2_ai_enhancement_var = tk.BooleanVar(value=False)
        self.run_step_3_var = tk.BooleanVar(value=True)
        self.run_step_4_var = tk.BooleanVar(value=True)
        self.run_step_5_var = tk.BooleanVar(value=True)
        self.run_step_6_var = tk.BooleanVar(value=bool(getattr(pipeline, "RUN_STEP_6_EXTRACT_DETAILS", False)))
        self.run_step_7_var = tk.BooleanVar(value=bool(getattr(pipeline, "RUN_STEP_7_CLASSIFY_SIGNALS", False)))
        self.run_step_report_var = tk.BooleanVar(value=False)
        self.retry_failed_only_var = tk.BooleanVar(value=False)

        self.category_var = tk.StringVar(value="CONVENIENCE")
        self.global_mode_enabled_var = tk.BooleanVar(value=False)

        # 로그 CAN별 사용 여부 및 단일 DBC 선택
        self.can1_enabled_var = tk.BooleanVar(value=True)
        self.can2_enabled_var = tk.BooleanVar(value=True)
        self.can3_enabled_var = tk.BooleanVar(value=True)
        self.can4_enabled_var = tk.BooleanVar(value=True)

        self.can1_dbc_var = tk.StringVar(value="N/A")
        self.can2_dbc_var = tk.StringVar(value="N/A")
        self.can3_dbc_var = tk.StringVar(value="N/A")
        self.can4_dbc_var = tk.StringVar(value="N/A")

        self.drop_first_seconds_enabled_var = tk.BooleanVar(value=True)
        self.drop_first_seconds_var = tk.StringVar(value="8.0")
        self.asc_frame_direction_var = tk.StringVar(value=ASC_FRAME_DIRECTION_VALUE_TO_LABEL["auto"])
        self.change_threshold_var = tk.StringVar(value="100")
        self.skip_high_frequency_var = tk.BooleanVar(value=True)
        self.global_exclude_crc_alv_var = tk.BooleanVar(value=True)

        # step 5 시간별 처리 옵션
        self.step_5_enable_time_folder_var = tk.BooleanVar(value=False)

        self.ai_provider_var = tk.StringVar(value="gpt")
        self.gpt_model_var = tk.StringVar(value=DEFAULT_GPT_MODEL)
        self.gemini_model_var = tk.StringVar(value="gemini-3.1-pro-preview")
        self.api_key_var = tk.StringVar(value="")  # 실제 Key는 GUI에 보관하지 않고 main에서 파일 로드
        self.api_key_display_var = tk.StringVar(value="API KEY 미감지")
        self.base_url_var = tk.StringVar(value="")
        self.project_id_var = tk.StringVar(value="N/A")
        self.api_version_var = tk.StringVar(value="2025-04-01-preview")
        self.gemini_stream_option_var = tk.StringVar(value="generateContent")
        self.max_retry_var = tk.StringVar(value="3")
        self.skip_if_output_exists_var = tk.BooleanVar(value=True)
        self.completed_answer_file_pass_var = tk.BooleanVar(value=False)

        self.merge_split_answer_files_var = tk.BooleanVar(value=True)
        self.keep_split_answer_files_after_merge_var = tk.BooleanVar(value=False)

        self.status_var = tk.StringVar(value="대기 중")
        self.package_status_var = tk.StringVar(value="필요 패키지: 확인 필요")
        self.input_status_var = tk.StringVar(value="입력 상태: -")
        self.warning_status_var = tk.StringVar(value="실행 대기중")
        self.match_status_var = tk.StringVar(value="대기중")
        self.report_status_var = tk.StringVar(value="대기중")
        self.last_completed_output_dir: Optional[Path] = None
        self._last_run_config_data: dict = {}
        self.selected_main_status_var = tk.StringVar(value=f"실행 main: {self.selected_main_file.name}")

        self.step_status_vars = {
            1: tk.StringVar(value="대기중"),
            2: tk.StringVar(value="대기중"),
            3: tk.StringVar(value="대기중"),
            4: tk.StringVar(value="대기중"),
            5: tk.StringVar(value="대기중"),
            6: tk.StringVar(value="대기중"),
            7: tk.StringVar(value="대기중"),
        }
        self.step_status_labels = {}

        self.progress_percent_var = tk.IntVar(value=0)
        self.current_progress_percent_var = tk.IntVar(value=0)

        self.ai_provider_var.trace_add("write", lambda *args: self._update_ai_provider_ui())
        self.category_var.trace_add("write", lambda *args: self._on_category_changed())


    def _create_fonts(self) -> None:
        default_font = tkfont.nametofont("TkDefaultFont")
        self.big_button_font = tkfont.Font(
            family=default_font.cget("family"),
            size=max(11, int(default_font.cget("size")) + 2),
            weight="bold",
        )

    # =========================================================
    # UI
    # =========================================================
    def _build_ui(self) -> None:
        self.configure(bg="#F0F0F0")
        try:
            style = ttk.Style(self)
            for style_name in ("TFrame", "TLabelframe", "TLabelframe.Label", "TLabel", "TCheckbutton", "TRadiobutton"):
                style.configure(style_name, background="#F0F0F0")
        except Exception:
            pass

        # rev20: 전체 GUI를 하나의 세로 스크롤 영역으로 감싼다.
        # 기존 각 내부 위젯의 자체 스크롤(예: 실행 로그)은 그대로 유지한다.
        page_shell = ttk.Frame(self)
        page_shell.pack(fill=tk.BOTH, expand=True)

        self.page_canvas = tk.Canvas(
            page_shell,
            bg="#F0F0F0",
            highlightthickness=0,
            bd=0,
        )
        self.page_scrollbar = ttk.Scrollbar(
            page_shell,
            orient=tk.VERTICAL,
            command=self.page_canvas.yview,
        )
        self.page_canvas.configure(yscrollcommand=self.page_scrollbar.set)
        self.page_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.page_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        root = ttk.Frame(self.page_canvas, padding=10)
        self._page_canvas_window = self.page_canvas.create_window((0, 0), window=root, anchor="nw")

        def _sync_page_scrollregion(_event=None):
            try:
                self.page_canvas.configure(scrollregion=self.page_canvas.bbox("all"))
            except Exception:
                pass

        def _sync_page_width(event):
            try:
                self.page_canvas.itemconfigure(self._page_canvas_window, width=max(1, event.width))
            except Exception:
                pass

        root.bind("<Configure>", _sync_page_scrollregion)
        self.page_canvas.bind("<Configure>", _sync_page_width)

        top = ttk.Frame(root)
        top.pack(fill=tk.X)
        top.columnconfigure(1, weight=1)
        top.columnconfigure(2, weight=0)
        top.columnconfigure(3, weight=0)
        top.columnconfigure(4, weight=0)

        ttk.Label(top, text="프로젝트 폴더").grid(row=0, column=0, sticky=tk.W)
        self.project_entry = ttk.Entry(top, textvariable=self.project_dir_var)
        self.project_entry.grid(row=0, column=1, sticky="EW", padx=8)

        self.browse_button = ttk.Button(
            top,
            text="파일 찾기",
            command=self._browse_project_dir,
            width=12,
        )
        self.browse_button.grid(row=0, column=2, sticky="EW")

        self.refresh_button = ttk.Button(
            top,
            text="새로고침",
            command=self._on_refresh_clicked,
            width=12,
        )
        self.refresh_button.grid(row=0, column=3, sticky="EW", padx=(6, 0))

        self.help_button = ttk.Button(
            top,
            text="도움말",
            command=self._open_help_text,
            width=12,
        )
        self.help_button.grid(row=0, column=4, sticky="EW", padx=(6, 0))

        ttk.Label(root, textvariable=self.selected_main_status_var).pack(anchor=tk.W, pady=(3, 1))
        ttk.Label(root, textvariable=self.input_status_var).pack(anchor=tk.W, pady=(1, 4))

        body = ttk.Frame(root)
        body.pack(fill=tk.BOTH, expand=False)

        body.columnconfigure(0, weight=3, minsize=self.left_area_min_width)
        body.columnconfigure(1, weight=2, minsize=self.right_area_min_width)

        left_area = ttk.Frame(body)
        left_area.grid(row=0, column=0, sticky="NSEW", padx=(0, 10))
        left_area.columnconfigure(0, weight=0)
        left_area.columnconfigure(1, weight=1)

        self.right_area = ttk.Frame(body)
        self.right_area.grid(row=0, column=1, sticky="NSEW")
        self.right_area.columnconfigure(0, weight=1)

        self._build_category_frame(left_area).grid(row=0, column=0, sticky="EW", padx=(0, 8), pady=(0, 5))
        self._build_global_mode_frame(left_area).grid(row=0, column=1, sticky="NW", pady=(0, 5))
        self._build_dbc_frame(left_area).grid(row=1, column=0, columnspan=2, sticky="EW", pady=(0, 6))
        self._build_step_frame(left_area).grid(row=2, column=0, sticky="NSEW", padx=(0, 8))
        self._build_valid_signal_frame(left_area).grid(row=2, column=1, sticky="NEW")
        self._build_step2_ai_option_frame(left_area).grid(row=3, column=1, sticky="EW", pady=(6, 0))
        # rev38: 일반 split 옵션은 제거하고 Report 옵션을 좌측 전체 폭에 배치한다.
        self._build_report_option_frame(left_area).grid(row=4, column=0, columnspan=2, sticky="NSEW", pady=(6, 0))
        # 우측은 필요 패키지/주의사항 영역과 AI 설정 영역만 담당한다.
        self._build_required_package_frame(self.right_area).grid(row=0, column=0, sticky="NSEW", pady=(0, 6))
        self._build_ai_frame(self.right_area).grid(row=1, column=0, sticky="NSEW")

        action = ttk.Frame(root)
        action.pack(fill=tk.X, pady=(4, 3))

        self.run_button = tk.Button(
            action,
            text="실행",
            command=self._on_run_clicked,
            font=self.big_button_font,
            bg="#30D862",
            fg="black",
            activebackground="#28B854",
            activeforeground="black",
            relief="raised",
            bd=2,
            padx=24,
            pady=8,
            cursor="hand2",
        )
        self.run_button.pack(side=tk.LEFT)

        self.stop_button = tk.Button(
            action,
            text="중지",
            command=self._on_stop_clicked,
            font=self.big_button_font,
            bg="#F59E0B",
            fg="black",
            activebackground="#D97706",
            activeforeground="black",
            relief="raised",
            bd=2,
            padx=24,
            pady=8,
            cursor="hand2",
            state=tk.DISABLED,
        )
        self.stop_button.pack(side=tk.LEFT, padx=8)

        ttk.Button(action, text="로그 지우기", command=self._clear_log).pack(side=tk.LEFT, padx=(8, 6))
        ttk.Button(action, text="설정 미리보기", command=self._preview_config).pack(side=tk.LEFT, padx=6)

        progress_frame = ttk.Frame(action)
        progress_frame.pack(side=tk.LEFT, padx=(18, 10))

        progress_width = 300
        progress_height = 14

        self.progress_canvas = tk.Canvas(
            progress_frame,
            width=progress_width,
            height=progress_height,
            highlightthickness=1,
            highlightbackground="#BDBDBD",
            bg="white",
        )
        self.progress_canvas.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        self.progress_bar_rect = self.progress_canvas.create_rectangle(
            0, 0, 0, progress_height,
            fill="#16A34A",
            outline="",
        )
        self.progress_text = self.progress_canvas.create_text(
            progress_width // 2, progress_height // 2,
            text="전체 0%",
            fill="#111827",
            font=("맑은 고딕", 7),
        )
        self.progress_canvas.bind(
            "<Configure>",
            lambda _event: self._set_progress_percent(self.progress_percent_var.get())
        )

        self.current_progress_canvas = tk.Canvas(
            progress_frame,
            width=progress_width,
            height=progress_height,
            highlightthickness=1,
            highlightbackground="#BDBDBD",
            bg="white",
        )
        self.current_progress_canvas.grid(row=1, column=0, sticky="ew")
        self.current_progress_bar_rect = self.current_progress_canvas.create_rectangle(
            0, 0, 0, progress_height,
            fill="#16A34A",
            outline="",
        )
        self.current_progress_text = self.current_progress_canvas.create_text(
            progress_width // 2, progress_height // 2,
            text="현재 0%",
            fill="#111827",
            font=("맑은 고딕", 7),
        )
        self.current_progress_canvas.bind(
            "<Configure>",
            lambda _event: self._set_current_progress_percent(self.current_progress_percent_var.get())
        )

        ttk.Label(action, textvariable=self.status_var).pack(side=tk.LEFT, padx=(4, 0))

        status_line_frame = ttk.Frame(root)
        status_line_frame.pack(fill=tk.X, pady=(0, 3))

        ttk.Label(status_line_frame, text="상태", width=8).pack(side=tk.LEFT)

        self.warning_status_label = tk.Label(
            status_line_frame,
            textvariable=self.warning_status_var,
            anchor="w",
            relief="solid",
            bd=1,
            padx=8,
            pady=5,
            bg="#ECFDF5",
            fg="#065F46",
        )
        self.warning_status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.match_status_button = tk.Button(
            status_line_frame,
            textvariable=self.match_status_var,
            command=self._on_match_status_clicked,
            width=8,
            relief="raised",
            bd=1,
            padx=4,
            pady=4,
            cursor="hand2",
        )
        self.match_status_button.pack(side=tk.RIGHT, padx=(8, 0))

        self.open_completed_folder_button = tk.Button(
            status_line_frame,
            text="완료 결과 폴더 열기",
            command=self._on_open_completed_results_clicked,
            width=16,
            relief="raised",
            bd=1,
            padx=6,
            pady=4,
            cursor="hand2",
            state=tk.DISABLED,
        )
        self.open_completed_folder_button.pack(side=tk.RIGHT, padx=(8, 0))

        # rev22: 실행 로그는 전체 페이지 스크롤의 하단에 약 15행 높이를 안정적으로 확보한다.
        # 외부 우측 page_scrollbar로 이 영역까지 내려오고, 내부 ScrolledText 스크롤은 기존대로 유지한다.
        self.log_visible_lines = 15
        log_frame = ttk.LabelFrame(root, text="실행 로그")
        log_frame.pack(fill=tk.X, expand=False)

        self.log_text = ScrolledText(log_frame, height=self.log_visible_lines, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    def _available_category_values(self) -> list[str]:
        return [name for name in list(getattr(pipeline, "CATEGORIES", {}).keys()) if str(name).upper() != "GLOBAL"]

    def _build_category_frame(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="카테고리")
        self.category_combo = ttk.Combobox(
            frame,
            textvariable=self.category_var,
            values=self._available_category_values(),
            state="readonly",
            width=38,
        )
        self.category_combo.pack(fill=tk.X, padx=6, pady=6)
        self.category_combo.bind("<<ComboboxSelected>>", lambda _event: self._apply_category_mode())
        return frame

    def _build_global_mode_frame(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="글로벌 사용")
        self.global_mode_check = ttk.Checkbutton(
            frame,
            text="사용",
            variable=self.global_mode_enabled_var,
            command=self._on_global_mode_toggled,
        )
        self.global_mode_check.pack(fill=tk.X, padx=6, pady=6)
        return frame

    def _build_dbc_frame(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="DBC 설정 (로그 CAN 기준)")
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)

        ttk.Label(frame, text="사용").grid(row=0, column=0, sticky=tk.W, padx=6, pady=4)
        ttk.Label(frame, text="로그 CAN").grid(row=0, column=1, sticky=tk.W, padx=6, pady=4)
        ttk.Label(frame, text="DBC (CAN당 1개)").grid(row=0, column=2, sticky=tk.W, padx=6, pady=4)

        self.auto_detect_button = tk.Button(
            frame,
            text="자동감지",
            command=self._on_auto_detect_clicked,
            bg="#DBEAFE",
            fg="#1E3A8A",
            activebackground="#BFDBFE",
            activeforeground="#1E3A8A",
            relief="flat",
            bd=1,
            padx=0,
            pady=1,
            width=12,
            cursor="hand2",
        )
        self.auto_detect_button.grid(row=0, column=3, sticky="E", padx=(6, 6), pady=2)

        row_specs = [
            (1, "CAN1", self.can1_enabled_var, self.can1_dbc_var, "can1_combo"),
            (2, "CAN2", self.can2_enabled_var, self.can2_dbc_var, "can2_combo"),
            (3, "CAN3", self.can3_enabled_var, self.can3_dbc_var, "can3_combo"),
            (4, "CAN4", self.can4_enabled_var, self.can4_dbc_var, "can4_combo"),
        ]
        self.can_enable_checks = {}
        for row, can_name, enabled_var, dbc_var, combo_attr in row_specs:
            check = ttk.Checkbutton(
                frame,
                variable=enabled_var,
                command=self._on_can_enabled_changed,
            )
            check.grid(row=row, column=0, sticky=tk.W, padx=10, pady=4)
            self.can_enable_checks[can_name] = check
            ttk.Label(frame, text=can_name, width=10).grid(row=row, column=1, sticky=tk.W, padx=6, pady=4)
            combo = ttk.Combobox(frame, textvariable=dbc_var, state="disabled", width=56)
            combo.grid(row=row, column=2, columnspan=2, sticky="EW", padx=6, pady=4)
            combo.bind("<<ComboboxSelected>>", self._on_dbc_selection_changed)
            setattr(self, combo_attr, combo)

        return frame

    def _build_step_frame(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="실행 단계 (전체 체크 추천)")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=0)

        self.step_checkbuttons = {}
        step_rows = [
            (1, "Step 1  BLF → ASC", self.run_step_1_var),
            (2, "Step 2  Group Message Export", self.run_step_2_var),
            (3, "Step 3  ASC → TXT", self.run_step_3_var),
            (4, "Step 4  TXT → AI 문의용", self.run_step_4_var),
            (5, "Step 5  AI 응답 생성", self.run_step_5_var),
            (6, "Step 6  관련 시그널 상세 변화 추출", self.run_step_6_var),
            (7, "Step 7  입력/출력/제외 시그널 분류", self.run_step_7_var),
        ]

        for row, (step_no, text, var) in enumerate(step_rows):
            pady = (8, 3) if row == 0 else 3

            cb = ttk.Checkbutton(frame, text=text, variable=var)
            cb.grid(row=row, column=0, sticky=tk.W, padx=6, pady=pady)
            self.step_checkbuttons[step_no] = cb

            status = tk.Label(
                frame,
                textvariable=self.step_status_vars[step_no],
                width=9,
                relief="sunken",
                bd=1,
                padx=4,
                pady=2,
                bg="#E5E7EB",
                fg="#111827",
            )
            status.grid(row=row, column=1, sticky=tk.E, padx=(8, 6), pady=pady)
            self.step_status_labels[step_no] = status

        return frame

    def _build_valid_signal_frame(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="유효 CAN 시그널 설정 & 출력 txt 파일 설정")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        self.drop_first_seconds_check = ttk.Checkbutton(
            frame,
            text="CAN 신호 확인 시작 시점(초)",
            variable=self.drop_first_seconds_enabled_var,
            command=self._toggle_drop_first_seconds_state,
        )
        self.drop_first_seconds_check.grid(row=0, column=0, sticky=tk.W, padx=6, pady=4)

        self.drop_first_seconds_entry = ttk.Entry(frame, textvariable=self.drop_first_seconds_var, width=12)
        self.drop_first_seconds_entry.grid(row=0, column=1, sticky="EW", padx=6, pady=4)

        ttk.Label(frame, text="ASC 프레임 방향", width=28).grid(row=1, column=0, sticky=tk.W, padx=6, pady=4)
        self.asc_frame_direction_combo = ttk.Combobox(
            frame,
            textvariable=self.asc_frame_direction_var,
            values=[label for _value, label in ASC_FRAME_DIRECTION_OPTIONS],
            state="readonly",
            width=30,
        )
        self.asc_frame_direction_combo.grid(row=1, column=1, sticky="EW", padx=6, pady=4)

        self.skip_high_frequency_check = ttk.Checkbutton(
            frame,
            text="자주 변경되는 CAN 신호를 분석 대상에서 제외",
            variable=self.skip_high_frequency_var,
            command=self._toggle_change_threshold_visibility,
        )
        self.skip_high_frequency_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=6, pady=3)

        self.global_exclude_crc_alv_check = ttk.Checkbutton(
            frame,
            text="GLOBAL 전용: CRC/ALV 신호 제외",
            variable=self.global_exclude_crc_alv_var,
        )
        self.global_exclude_crc_alv_check.grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=6, pady=3)

        self.change_threshold_label = ttk.Label(frame, text="제외 기준 (신호 변경 횟수)", width=28)
        self.change_threshold_entry = ttk.Entry(frame, textvariable=self.change_threshold_var, width=12)
        self.change_threshold_label.grid(row=4, column=0, sticky=tk.W, padx=24, pady=4)
        self.change_threshold_entry.grid(row=4, column=1, sticky="EW", padx=6, pady=4)


        self.step6_time_detail_check = ttk.Checkbutton(
            frame,
            text="Step 6 시간별 상세 변화도 생성",
            variable=self.step_5_enable_time_folder_var,
        )
        self.step6_time_detail_check.grid(row=5, column=0, columnspan=2, sticky=tk.W, padx=6, pady=(3, 8))

        return frame

    def _build_step2_ai_option_frame(self, parent: ttk.Frame) -> ttk.Frame:
        frame = ttk.Frame(parent)
        frame.columnconfigure(0, weight=1)

        sep = ttk.Separator(frame, orient=tk.HORIZONTAL)
        sep.grid(row=0, column=0, sticky="EW", pady=(0, 6))

        self.step2_ai_enhancement_check = ttk.Checkbutton(
            frame,
            text="Step 2 AI 후보 보강 사용 (실행 시에만, 기본 OFF)",
            variable=self.step_2_ai_enhancement_var,
        )
        self.step2_ai_enhancement_check.grid(row=1, column=0, sticky=tk.W, padx=(6, 0), pady=(0, 0))

        return frame


    def _build_required_package_frame(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="필요 패키지 및 주의사항")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=0)
        frame.columnconfigure(2, weight=0)

        self.package_status_label = tk.Label(
            frame,
            textvariable=self.package_status_var,
            width=18,
            relief="solid",
            bd=1,
            padx=6,
            pady=4,
            bg="#DCFCE7",
            fg="#166534",
            anchor="center",
            font=("맑은 고딕", 9, "bold"),
        )
        self.package_status_label.grid(row=0, column=0, sticky="EW", padx=(6, 6), pady=(6, 3))

        self.package_check_button = ttk.Button(
            frame,
            text="필요 패키지 확인",
            command=self._on_check_required_packages_clicked,
            width=16,
        )
        self.package_check_button.grid(row=0, column=1, sticky="EW", padx=(0, 6), pady=(6, 3))

        self.package_install_button = ttk.Button(
            frame,
            text="필요 패키지 설치",
            command=self._on_install_required_packages_clicked,
            width=16,
        )
        self.package_install_button.grid(row=0, column=2, sticky="EW", padx=(0, 6), pady=(6, 3))

        notice = ttk.Label(
            frame,
            text='※ "필요 패키지: 설치됨" 이 잘 되어있는지 확인하세요',
            foreground="#111827",
        )
        notice.grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=8, pady=(0, 6))

        return frame



    def _build_report_option_frame(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="레포트 옵션")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=0)

        self.report_auto_check = ttk.Checkbutton(
            frame,
            text="실행 완료 시 결과 레포트 자동 생성",
            variable=self.run_step_report_var,
        )
        self.report_auto_check.grid(row=0, column=0, sticky=tk.W, padx=6, pady=5)

        self.report_button = ttk.Button(
            frame,
            text="결과 레포트 생성",
            command=self._on_report_clicked,
        )
        self.report_button.grid(row=0, column=1, sticky=tk.E, padx=(8, 6), pady=5)

        report_status_row = ttk.Frame(frame)
        report_status_row.grid(row=1, column=0, columnspan=2, sticky="EW", padx=6, pady=(0, 6))
        report_status_row.columnconfigure(0, weight=1)
        report_status_row.columnconfigure(1, weight=2)
        report_status_row.columnconfigure(2, weight=1)

        report_status = tk.Label(
            report_status_row,
            textvariable=self.report_status_var,
            relief="sunken",
            bd=1,
            padx=4,
            pady=2,
            bg="#E5E7EB",
            fg="#111827",
            anchor="center",
            justify="center",
        )
        report_status.grid(row=0, column=1, sticky="EW")

        return frame

    def _build_split_option_frame(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="로그 텍스트 분할 옵션")

        ttk.Checkbutton(
            frame,
            text="분할 후 답변 텍스트 파일 병합 (추천)",
            variable=self.merge_split_answer_files_var,
        ).pack(anchor=tk.W, padx=6, pady=3)
        ttk.Checkbutton(
            frame,
            text="텍스트 병합 후 쪼개진 파일 삭제 안함",
            variable=self.keep_split_answer_files_after_merge_var,
        ).pack(anchor=tk.W, padx=6, pady=3)

        return frame

    def _build_ai_frame(self, parent: ttk.Frame) -> ttk.Frame:
        outer = ttk.Frame(parent)
        outer.columnconfigure(0, weight=1)

        self.ai_frame = ttk.LabelFrame(outer, text="AI")
        self.ai_frame.grid(row=0, column=0, sticky="NEW")

        provider_row = ttk.Frame(self.ai_frame)
        provider_row.pack(fill=tk.X, pady=(4, 6), padx=6)
        self.ai_provider_gpt_radio = ttk.Radiobutton(provider_row, text="GPT", variable=self.ai_provider_var, value="gpt")
        self.ai_provider_gpt_radio.pack(side=tk.LEFT)
        self.ai_provider_gemini_radio = ttk.Radiobutton(provider_row, text="Gemini", variable=self.ai_provider_var, value="gemini")
        self.ai_provider_gemini_radio.pack(side=tk.LEFT, padx=10)

        self.gpt_section = ttk.Frame(self.ai_frame)
        self.gpt_section.pack(fill=tk.X, padx=6, pady=2)

        self._add_labeled_combobox(
            self.gpt_section,
            "GPT 모델",
            self.gpt_model_var,
            values=list(GPT_MODEL_OPTIONS),
            state="readonly",
        )
        self._add_labeled_entry(self.gpt_section, "API Version", self.api_version_var, show=None, state="readonly")

        self.gemini_section = ttk.Frame(self.ai_frame)
        self.gemini_section.pack(fill=tk.X, padx=6, pady=2)


        self._add_labeled_combobox(
            self.gemini_section,
            "Gemini 모델",
            self.gemini_model_var,
            values=[getattr(pipeline, "GEMINI_MODEL", "gemini-3.1-pro-preview")],
            state="readonly",
        )
        self._add_labeled_entry(
            self.gemini_section,
            "Stream Option",
            self.gemini_stream_option_var,
            show=None,
            state="readonly",
        )

        self.common_ai_section = ttk.Frame(self.ai_frame)
        self.common_ai_section.pack(fill=tk.X, padx=6, pady=(2, 4))

        self._add_labeled_entry(self.common_ai_section, "API Key", self.api_key_display_var, show=None, state="readonly")
        self._add_labeled_entry(self.common_ai_section, "Base URL", self.base_url_var, show=None, state="readonly")
        self._add_labeled_entry(self.common_ai_section, "Project ID", self.project_id_var, show=None, state="readonly")
        self._add_labeled_entry(self.common_ai_section, "API 실패 시 재시도", self.max_retry_var, show=None, state="normal")

        self.skip_if_output_exists_check = ttk.Checkbutton(
            self.ai_frame,
            text="이미 있는 파일 건너뛰기",
            variable=self.skip_if_output_exists_var,
        )
        self.skip_if_output_exists_check.pack(anchor=tk.W, padx=6, pady=3)

        self.completed_answer_file_pass_check = ttk.Checkbutton(
            self.ai_frame,
            text="완료된 답변파일 Pass",
            variable=self.completed_answer_file_pass_var,
        )
        self.completed_answer_file_pass_check.pack(anchor=tk.W, padx=6, pady=(0, 3))

        self.retry_failed_only_check = ttk.Checkbutton(
            self.ai_frame,
            text="실패파일만 재실행",
            variable=self.retry_failed_only_var,
        )
        self.retry_failed_only_check.pack(anchor=tk.W, padx=6, pady=(0, 5))

        return outer

    def _add_labeled_entry(
        self,
        parent: ttk.Frame,
        label: str,
        var: tk.StringVar,
        show: Optional[str],
        state: str = "normal",
    ) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=3)
        ttk.Label(row, text=label, width=18).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=var, show=show, state=state).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _add_labeled_combobox(
        self,
        parent: ttk.Frame,
        label: str,
        var: tk.StringVar,
        values: list[str],
        state: str = "readonly",
    ) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=3)
        ttk.Label(row, text=label, width=18).pack(side=tk.LEFT)
        ttk.Combobox(row, textvariable=var, values=values, state=state).pack(side=tk.LEFT, fill=tk.X, expand=True)

    # =========================================================
    # 상태 표시
    # =========================================================
    def _set_warning_status(self, text: str, level: str = "info") -> None:
        self.warning_status_var.set(text)

        if not hasattr(self, "warning_status_label"):
            return

        palette = {
            "info": ("#F3F4F6", "#111827"),
            "ok": ("#ECFDF5", "#065F46"),
            "warn": ("#FFF7ED", "#9A3412"),
            "error": ("#FEF2E2", "#B91C1C"),
        }
        bg, fg = palette.get(level, ("#F3F4F6", "#111827"))
        self.warning_status_label.configure(bg=bg, fg=fg)

    def _set_match_status(self, text: str, level: str = "info") -> None:
        self.match_status_var.set(text)
        if not hasattr(self, "match_status_button"):
            return
        palette = {
            "ok": ("#ECFDF5", "#065F46"),
            "warn": ("#FFF7ED", "#9A3412"),
            "error": ("#FEF2E2", "#B91C1C"),
            "info": ("#F3F4F6", "#111827"),
        }
        bg, fg = palette.get(level, ("#F3F4F6", "#111827"))
        self.match_status_button.configure(bg=bg, fg=fg, activebackground=bg, activeforeground=fg)

    def _refresh_api_key_display(self, base_dir: Path | None = None) -> None:
        try:
            base = base_dir or Path(self.project_dir_var.get()).expanduser()
            if hasattr(pipeline, "resolve_external_api_key"):
                key, _path, display = pipeline.resolve_external_api_key(base)
                self.api_key_display_var.set(display if key else "API KEY 미감지")
            else:
                self.api_key_display_var.set("API KEY 미감지")
        except Exception:
            self.api_key_display_var.set("API KEY 미감지")

    def _has_detected_api_key_file(self, base_dir: Path) -> bool:
        try:
            if hasattr(pipeline, "resolve_external_api_key"):
                key, _path, _display = pipeline.resolve_external_api_key(base_dir)
                return bool(str(key or "").strip())
        except Exception:
            return False
        return False

    @staticmethod
    def _canonical_bus_code(code: str | None) -> str:
        s = (code or "").strip().upper()
        if s == "P":
            return "P1"
        if s == "B":
            return "B1"
        return s

    @staticmethod
    def _infer_can_map_from_asc_name(name: str) -> dict[str, str]:
        stem = Path(name).stem
        pattern = re.compile(
            r"(?<![A-Za-z0-9])CAN[_\-\s]*(?P<num>[1234])[_\-\s]*(?P<code>B1|B2|BDC|P1|P2|P|B|C|E|M)(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
        out: dict[str, str] = {}
        for m in pattern.finditer(stem):
            out[f"CAN{m.group('num')}"] = m.group("code").upper()
        return out

    @staticmethod
    def _find_declared_can_names_from_asc_name(name: str) -> set[str]:
        """
        ASC/BLF 파일명에 CAN1/CAN2/CAN3/CAN4 토큰이 명시되어 있는지 확인한다.

        정상 매핑 정규식보다 느슨하게 CAN 번호만 확인하므로,
        CAN3_M2026처럼 CAN3 토큰은 있지만 뒤쪽 CAN 코드 구분자가 잘못된
        파일도 감지할 수 있다.
        """
        stem = Path(name).stem
        pattern = re.compile(
            r"(?<![A-Za-z0-9])CAN[_\-\s]*(?P<num>[1234])(?![0-9])",
            re.IGNORECASE,
        )
        return {f"CAN{m.group('num')}" for m in pattern.finditer(stem)}

    @staticmethod
    def _infer_dbc_bus_from_name(name: str) -> str | None:
        stem = Path(name).stem.upper()
        # DBC 표준명 예: ..._FD_B1_..., ..._FD_P1_...
        target_codes = "B1|B2|BDC|P1|P2|P|B|C|E|M"
        m = re.search(rf"(?:^|[_\-\s])FD[_\-\s]*(?P<code>{target_codes})(?=$|[_\-\s\.])", stem, flags=re.IGNORECASE)
        if m:
            return m.group("code").upper()
        # 예: B1-CAN, C_CAN, P1 CAN 같은 이름도 허용하되 STD/FD/DB/CAR 같은 일반 토큰은 제외
        m = re.search(rf"(?:^|[_\-\s])(?P<code>{target_codes})(?:[_\-\s]*CAN)?(?=$|[_\-\s\.])", stem, flags=re.IGNORECASE)
        if m:
            return m.group("code").upper()
        return None

    @staticmethod
    def _normalize_folder_name_for_scan(s: str) -> str:
        return re.sub(r"[\s_\-]+", "", (s or "").strip().lower())

    @staticmethod
    def _normalize_category_token(token: str | None) -> str:
        return re.sub(r"[\s_\-]+", "", (token or "").strip().lower())

    @staticmethod
    def _category_alias_map() -> dict[str, str]:
        aliases = {
            "SEAT": ["시트", "seat", "safety", "safe", "seatsafety"],
            "CLUSTER": ["클러스터", "클러", "cluster", "clu"],
            "CONVENIENCE": ["편의", "편의장치", "convenience", "conv", "comfort"],
            "INFOTAINMENT": ["인포", "인포테인먼트", "infotainment", "info", "avn", "hu"],
            "DRIVE": ["시동", "주행", "drive", "driving", "start", "ignition", "powertrain", "pt"],
            "ADAS": ["운전자", "운전자보조", "보조", "adas", "driverassist", "driver_assist"],
            "BLUELINK_CCS": ["블루링크", "블루", "링크", "bluelink", "blue", "ccs", "connected"],
            "EV": ["환경차", "ev", "eco", "hev", "phev", "xev"],
            "SCENARIO": ["시나리오", "scenario", "scene", "scn"],
            "AVP": ["avp", "과거차문제", "oldcar", "legacy", "pastcar"],
            "NEWSPEC": ["신사양", "임시", "newspec", "new_spec", "temp", "temporary"],
            "CONNECT": ["커넥트", "ux", "connect", "connectux"],
        }
        out: dict[str, str] = {}
        for category, tokens in aliases.items():
            for token in tokens:
                norm = PipelineGui._normalize_category_token(token)
                if norm:
                    out[norm] = category
        return out

    @staticmethod
    def _extract_leading_category_token_from_asc_name(name: str) -> str:
        stem = Path(name).stem.strip()
        m = re.match(r"^\s*(?P<token>[A-Za-z0-9가-힣]+)", stem)
        if not m:
            return ""
        return m.group("token")

    @classmethod
    def _infer_category_from_asc_name(cls, name: str) -> tuple[str | None, str]:
        token = cls._extract_leading_category_token_from_asc_name(name)
        norm = cls._normalize_category_token(token)
        if not norm:
            return None, token
        category = cls._category_alias_map().get(norm)
        return category, token

    def _collect_log_dirs(self, base_dir: Path) -> list[Path]:
        targets = {
            self._normalize_folder_name_for_scan("log파일"),
            self._normalize_folder_name_for_scan("log file"),
            self._normalize_folder_name_for_scan("로그파일"),
            self._normalize_folder_name_for_scan("로그폴더"),
            self._normalize_folder_name_for_scan("로그 파일"),
            self._normalize_folder_name_for_scan("로그 폴더"),
        }
        found: list[Path] = []
        try:
            for child in base_dir.iterdir():
                if child.is_dir() and self._normalize_folder_name_for_scan(child.name) in targets:
                    found.append(child)
        except Exception:
            pass
        return sorted(found, key=lambda x: x.name)

    def _collect_current_asc_files(self, base_dir: Path) -> list[Path]:
        candidates = list(base_dir.glob("*.asc"))
        for log_dir in self._collect_log_dirs(base_dir):
            candidates += list(log_dir.glob("*.asc"))
        # 동일 파일명은 최신 수정본 1개만 확인
        best: dict[str, Path] = {}
        for p in candidates:
            prev = best.get(p.name)
            if prev is None or p.stat().st_mtime > prev.stat().st_mtime:
                best[p.name] = p
        return sorted(best.values(), key=lambda x: x.name)

    def _collect_current_blf_files(self, base_dir: Path) -> list[Path]:
        candidates = list(base_dir.glob("*.blf"))
        for log_dir in self._collect_log_dirs(base_dir):
            candidates += list(log_dir.glob("*.blf"))
        return sorted(candidates, key=lambda x: (str(x.parent), x.name))

    def _collect_current_log_files_for_auto_detect(self, base_dir: Path) -> list[Path]:
        """자동감지 기준 파일: base/log 폴더의 ASC + BLF.

        - Step 1 실행 전에는 ASC가 없고 BLF만 있을 수 있으므로 BLF 파일명도 자동감지에 사용한다.
        - 동일 파일명이 base/log 폴더에 중복 존재하면 최신 수정본 1개만 확인한다.
        - ASC/BLF 확장자는 모두 유지하므로 같은 stem의 .asc와 .blf는 각각 표시된다.
        """
        candidates: list[Path] = []
        candidates += list(base_dir.glob("*.asc"))
        candidates += list(base_dir.glob("*.blf"))
        for log_dir in self._collect_log_dirs(base_dir):
            candidates += list(log_dir.glob("*.asc"))
            candidates += list(log_dir.glob("*.blf"))

        best: dict[str, Path] = {}
        for p in candidates:
            prev = best.get(p.name)
            if prev is None or p.stat().st_mtime > prev.stat().st_mtime:
                best[p.name] = p
        return sorted(best.values(), key=lambda x: (x.suffix.lower(), x.name))

    def _collect_current_dbc_files(self, base_dir: Path) -> list[Path]:
        return sorted(base_dir.glob("*.dbc"), key=lambda x: x.name)

    def _collect_current_xlsx_files(self, base_dir: Path) -> list[Path]:
        return sorted(base_dir.glob("*.xlsx"), key=lambda x: x.name)

    def _find_dbc_for_bus_code(self, base_dir: Path, canonical_code: str) -> tuple[str | None, list[str]]:
        matches: list[Path] = []
        for dbc_path in self._collect_current_dbc_files(base_dir):
            raw = self._infer_dbc_bus_from_name(dbc_path.name)
            if raw is None:
                continue
            if self._canonical_bus_code(raw) == canonical_code:
                matches.append(dbc_path)
        matches = sorted(matches, key=lambda p: p.name)
        if len(matches) != 1:
            return None, [p.name for p in matches]
        return matches[0].name, [matches[0].name]

    @staticmethod
    def _extract_can_pairs_from_name(name: str) -> list[tuple[str, str]]:
        stem = Path(name).stem
        pattern = re.compile(
            r"(?<![A-Za-z0-9])CAN[_\-\s]*(?P<num>[1234])[_\-\s]*(?P<code>B1|B2|BDC|P1|P2|P|B|C|E|M)(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
        return [(f"CAN{m.group('num')}", m.group("code").upper()) for m in pattern.finditer(stem)]

    def _analyze_asc_can_maps(self, base_dir: Path):
        log_files = self._collect_current_log_files_for_auto_detect(base_dir)
        parsed_by_file: dict[str, dict[str, str]] = {}
        values_by_can: dict[str, set[str]] = {name: set() for name in CAN_NAMES}
        unparsed_files: list[str] = []
        malformed_by_can: dict[str, list[str]] = {name: [] for name in CAN_NAMES}
        duplicate_by_file: dict[str, list[str]] = {}

        for log_path in log_files:
            raw_pairs = self._extract_can_pairs_from_name(log_path.name)
            raw_map = self._infer_can_map_from_asc_name(log_path.name)
            declared_can_names = self._find_declared_can_names_from_asc_name(log_path.name)

            for can_name in sorted(declared_can_names):
                if can_name not in raw_map and can_name in malformed_by_can:
                    malformed_by_can[can_name].append(log_path.name)

            per_can_codes: dict[str, list[str]] = {name: [] for name in CAN_NAMES}
            for can_name, raw_code in raw_pairs:
                if can_name in per_can_codes:
                    per_can_codes[can_name].append(self._canonical_bus_code(raw_code))
            duplicate_items = [
                f"{can_name}={','.join(codes)}"
                for can_name, codes in per_can_codes.items()
                if len(codes) > 1
            ]
            if duplicate_items:
                duplicate_by_file[log_path.name] = duplicate_items

            if not raw_map:
                unparsed_files.append(log_path.name)
                continue

            canon_map = {can: self._canonical_bus_code(code) for can, code in raw_map.items()}
            parsed_by_file[log_path.name] = canon_map
            for can_name, code in canon_map.items():
                if can_name in values_by_can and code:
                    values_by_can[can_name].add(code)

        conflicts = {can: sorted(vals) for can, vals in values_by_can.items() if len(vals) > 1}
        consensus = {can: next(iter(vals)) for can, vals in values_by_can.items() if len(vals) == 1}
        malformed_by_can = {can: files for can, files in malformed_by_can.items() if files}
        return (
            log_files,
            parsed_by_file,
            values_by_can,
            conflicts,
            consensus,
            unparsed_files,
            malformed_by_can,
            duplicate_by_file,
        )

    def _analyze_asc_categories(self, base_dir: Path):
        asc_files = self._collect_current_log_files_for_auto_detect(base_dir)
        parsed_by_file: dict[str, tuple[str, str]] = {}
        unknown_files: list[tuple[str, str]] = []
        values: set[str] = set()

        for asc_path in asc_files:
            category, token = self._infer_category_from_asc_name(asc_path.name)
            if category is None:
                unknown_files.append((asc_path.name, token or "<없음>"))
                continue
            parsed_by_file[asc_path.name] = (token, category)
            values.add(category)

        conflicts = sorted(values) if len(values) > 1 else []
        consensus = next(iter(values)) if len(values) == 1 else None
        return asc_files, parsed_by_file, conflicts, consensus, unknown_files

    def _evaluate_asc_dbc_mapping(self) -> tuple[str, str, list[str]]:
        base_dir = Path(self.project_dir_var.get()).expanduser()
        if not base_dir.exists() or not base_dir.is_dir():
            return "error", "오류", ["프로젝트 폴더가 존재하지 않습니다."]

        enabled_by_can = {
            "CAN1": bool(self.can1_enabled_var.get()),
            "CAN2": bool(self.can2_enabled_var.get()),
            "CAN3": bool(self.can3_enabled_var.get()),
            "CAN4": bool(self.can4_enabled_var.get()),
        }
        can_to_dbc_name = {
            "CAN1": self.can1_dbc_var.get().strip(),
            "CAN2": self.can2_dbc_var.get().strip(),
            "CAN3": self.can3_dbc_var.get().strip(),
            "CAN4": self.can4_dbc_var.get().strip(),
        }
        selected_codes: dict[str, tuple[str, str]] = {}
        unknown_dbc = []
        missing_enabled_dbc = []
        for can_name, dbc_name in can_to_dbc_name.items():
            if not enabled_by_can.get(can_name, False):
                continue
            if not dbc_name or dbc_name == "N/A":
                missing_enabled_dbc.append(can_name)
                continue
            raw_code = self._infer_dbc_bus_from_name(dbc_name)
            if raw_code is None:
                unknown_dbc.append(f"{can_name}: {dbc_name}")
                continue
            selected_codes[can_name] = (raw_code, self._canonical_bus_code(raw_code))

        if missing_enabled_dbc:
            return "error", "오류", ["활성 CAN에 DBC가 지정되지 않았습니다."] + [f"- {name}" for name in missing_enabled_dbc]

        log_files = self._collect_current_log_files_for_auto_detect(base_dir)
        if not log_files:
            return "warn", "경고", ["ASC/BLF 파일이 없어 로그 파일명 기준 CAN 매핑을 확인할 수 없습니다."]

        mismatch_lines = []
        malformed_lines = []
        parsed_count = 0
        for log_path in log_files:
            log_map = self._infer_can_map_from_asc_name(log_path.name)
            declared = self._find_declared_can_names_from_asc_name(log_path.name)
            if not log_map:
                malformed_lines.append(f"- 파일명 CAN 매핑 미인식: {log_path.name}")
                continue
            missing_declared = sorted(declared - set(log_map))
            if missing_declared:
                malformed_lines.append(f"- 파일명 형식 오류: {log_path.name} ({', '.join(missing_declared)})")
                continue
            parsed_count += 1
            for can_name, log_raw in sorted(log_map.items()):
                if not enabled_by_can.get(can_name, False):
                    continue
                if can_name not in selected_codes:
                    continue
                dbc_raw, dbc_canon = selected_codes[can_name]
                log_canon = self._canonical_bus_code(log_raw)
                if log_canon != dbc_canon:
                    mismatch_lines.append(
                        f"- {log_path.name}: {can_name} LOG={log_raw} / 선택 DBC={dbc_raw} ({can_to_dbc_name.get(can_name)})"
                    )

        if malformed_lines:
            return "warn", "경고", ["일부 ASC/BLF 파일명이 자동감지 규칙에 맞지 않습니다."] + malformed_lines[:30]
        if mismatch_lines:
            return "warn", "경고", ["DBC 파일의 CAN과 로그 파일명의 CAN이 일치하지 않습니다."] + mismatch_lines[:30]
        if unknown_dbc:
            return "warn", "경고", ["선택된 DBC 파일명에서 CAN 종류를 판별하지 못했습니다."] + unknown_dbc[:30]
        if parsed_count == 0:
            return "warn", "경고", ["ASC/BLF 파일명에서 CAN1~CAN4 매핑을 추출하지 못했습니다.", "예: CAN1_B1_CAN2_M_CAN3_P1_CAN4_C"]
        if not any(enabled_by_can.values()):
            return "warn", "경고", ["활성화된 로그 CAN이 없습니다."]

        return "ok", "정상", [f"로그 파일명 CAN 매핑과 활성 DBC가 일치합니다. (확인 로그 {parsed_count}개)"]

    def _refresh_match_status(self) -> None:
        level, text, details = self._evaluate_asc_dbc_mapping()
        self._last_match_detail_lines = details
        self._set_match_status(text, level)

    def _on_match_status_clicked(self) -> None:
        level, text, details = self._evaluate_asc_dbc_mapping()
        self._last_match_detail_lines = details
        self._set_match_status(text, level)
        title = "로그 CAN-DBC 매칭 상태"
        body = "\n".join(details) if details else "확인 결과가 없습니다."
        if level == "ok":
            messagebox.showinfo(title, body)
        elif level == "error":
            messagebox.showerror(title, body)
        else:
            messagebox.showwarning(title, body)

    # =========================================================
    # 필요 패키지 확인/설치
    # =========================================================
    @staticmethod
    def _version_at_least(current: str, minimum: str) -> bool:
        def parts(value: str) -> tuple[int, ...]:
            nums = []
            for token in re.findall(r"\d+", str(value or "")):
                nums.append(int(token))
            return tuple(nums or [0])
        cur = parts(current)
        req = parts(minimum)
        size = max(len(cur), len(req))
        cur += (0,) * (size - len(cur))
        req += (0,) * (size - len(req))
        return cur >= req

    def _get_missing_required_packages(self) -> list[tuple[str, str]]:
        missing: list[tuple[str, str]] = []
        for install_name, import_name in REQUIRED_PYTHON_PACKAGES:
            try:
                if importlib.util.find_spec(import_name) is None:
                    missing.append((install_name, import_name))
                    continue
                if import_name == "xlrd":
                    try:
                        current = importlib_metadata.version("xlrd")
                    except Exception:
                        current = "0"
                    if not self._version_at_least(current, "2.0.1"):
                        missing.append((install_name, import_name))
            except Exception:
                missing.append((install_name, import_name))
        return missing

    def _set_package_status_visual(self, installed: bool, checking: bool = False) -> None:
        if not hasattr(self, "package_status_label"):
            return
        if checking:
            bg, fg = "#E5E7EB", "#374151"
        elif installed:
            bg, fg = "#DCFCE7", "#166534"
        else:
            bg, fg = "#FEF3C7", "#92400E"
        self.package_status_label.configure(bg=bg, fg=fg)

    def _refresh_required_packages_status(self, show_popup: bool = False) -> bool:
        missing = self._get_missing_required_packages()
        self._missing_required_packages = missing

        if missing:
            names = ", ".join(name for name, _import_name in missing)
            self.package_status_var.set("필요 패키지: 설치 안됨")
            self._set_package_status_visual(installed=False)
            if hasattr(self, "package_install_button"):
                self.package_install_button.configure(state=tk.NORMAL)
            msg = f"누락 패키지: {names}"
            self._log(f"[GUI] {msg}\n")
            if show_popup:
                messagebox.showwarning("필요 패키지 확인", msg)
            return False

        self.package_status_var.set("필요 패키지: 설치됨")
        self._set_package_status_visual(installed=True)
        if hasattr(self, "package_install_button"):
            self.package_install_button.configure(state=tk.DISABLED)
        if show_popup:
            messagebox.showinfo("필요 패키지 확인", "필요 패키지가 모두 설치되어 있습니다.")
        return True

    def _on_check_required_packages_clicked(self) -> None:
        self._refresh_required_packages_status(show_popup=True)

    def _on_install_required_packages_clicked(self) -> None:
        if self.is_running:
            messagebox.showinfo("실행 중", "파이프라인 실행 중에는 패키지 설치를 시작하지 않는 것을 권장합니다.")
            return

        missing = self._get_missing_required_packages()
        if not missing:
            self._refresh_required_packages_status(show_popup=True)
            return

        install_targets = [name for name, _import_name in missing]
        cmd = [sys.executable, "-m", "pip", "install"] + install_targets

        self.package_status_var.set("필요 패키지: 설치 중")
        self._set_package_status_visual(installed=False, checking=True)
        if hasattr(self, "package_install_button"):
            self.package_install_button.configure(state=tk.DISABLED)
        if hasattr(self, "package_check_button"):
            self.package_check_button.configure(state=tk.DISABLED)

        self._log("[GUI] 필요 패키지 설치 시작: " + " ".join(install_targets) + "\n")

        def worker():
            kwargs = dict(
                cwd=str(Path(self.project_dir_var.get()).expanduser()),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if sys.platform.startswith("win"):
                try:
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                except Exception:
                    pass
            try:
                proc = subprocess.run(cmd, **kwargs)
                output = (proc.stdout or "") + (proc.stderr or "")
                self.log_queue.put(("STDOUT", output if output.endswith("\n") else output + "\n"))
                self.after(0, lambda: self._on_required_package_install_done(proc.returncode))
            except Exception as e:
                self.after(0, lambda err=e: self._on_required_package_install_error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_required_package_install_done(self, return_code: int) -> None:
        if hasattr(self, "package_check_button"):
            self.package_check_button.configure(state=tk.NORMAL)

        ok = self._refresh_required_packages_status(show_popup=False)
        if return_code == 0 and ok:
            messagebox.showinfo("필요 패키지 설치", "필요 패키지 설치가 완료되었습니다.")
            self._log("[GUI] 필요 패키지 설치 완료\n")
        else:
            if hasattr(self, "package_install_button") and not ok:
                self.package_install_button.configure(state=tk.NORMAL)
            messagebox.showwarning(
                "필요 패키지 설치",
                "패키지 설치가 완료되지 않았거나 일부 패키지가 아직 누락되어 있습니다. 실행 로그를 확인하세요.",
            )
            self._log(f"[GUI] 필요 패키지 설치 확인 필요: return_code={return_code}\n")

    def _on_required_package_install_error(self, error: Exception) -> None:
        if hasattr(self, "package_check_button"):
            self.package_check_button.configure(state=tk.NORMAL)
        if hasattr(self, "package_install_button"):
            self.package_install_button.configure(state=tk.NORMAL)
        self.package_status_var.set("필요 패키지: 설치 실패")
        self._set_package_status_visual(installed=False)
        self._log(f"[GUI][ERROR] 필요 패키지 설치 실패: {error}\n")
        messagebox.showerror("필요 패키지 설치", str(error))


    # =========================================================
    # 기본값 로드
    # =========================================================
    def _load_defaults_from_pipeline(self) -> None:
        self.run_step_1_var.set(True)
        self.run_step_2_var.set(True)
        self.step_2_ai_enhancement_var.set(False)
        self.run_step_3_var.set(True)
        self.run_step_4_var.set(True)
        self.run_step_5_var.set(True)
        self.run_step_6_var.set(bool(getattr(pipeline, "RUN_STEP_6_EXTRACT_DETAILS", False)))
        self.run_step_7_var.set(bool(getattr(pipeline, "RUN_STEP_7_CLASSIFY_SIGNALS", False)))
        self.run_step_report_var.set(bool(getattr(pipeline, "RUN_REPORT_GENERATE", getattr(pipeline, "RUN_STEP_REPORT", False))))
        self.retry_failed_only_var.set(bool(getattr(pipeline, "RETRY_FAILED_ONLY", False)))

        default_category = getattr(pipeline, "ACTIVE_CATEGORY", "CONVENIENCE")
        if default_category not in self._available_category_values():
            default_category = "CONVENIENCE"
        self.category_var.set(default_category)
        self.global_mode_enabled_var.set(bool(getattr(pipeline, "GLOBAL_MODE_ENABLED", False)))

        dbc_map = getattr(pipeline, "DBC_NAME_BY_CH", {})
        default_specs = [
            (1, self.can1_enabled_var, self.can1_dbc_var),
            (2, self.can2_enabled_var, self.can2_dbc_var),
            (3, self.can3_enabled_var, self.can3_dbc_var),
            (4, self.can4_enabled_var, self.can4_dbc_var),
        ]
        for logical_channel, enabled_var, dbc_var in default_specs:
            dbc_name = dbc_map.get(logical_channel)
            enabled_var.set(True)
            dbc_var.set(dbc_name or "N/A")

        self.drop_first_seconds_enabled_var.set(True)
        self.drop_first_seconds_var.set(str(getattr(pipeline, "DROP_FIRST_SECONDS", 8.0)))
        self.asc_frame_direction_var.set(asc_frame_direction_value_to_label(getattr(pipeline, "ASC_FRAME_DIRECTION", "auto")))
        self.change_threshold_var.set(str(getattr(pipeline, "CHANGE_THRESHOLD", 100)))
        self.skip_high_frequency_var.set(bool(getattr(pipeline, "SKIP_HIGH_FREQUENCY", True)))
        self.step_5_enable_time_folder_var.set(bool(getattr(pipeline, "STEP_6_ENABLE_TIME_DETAIL", False)))

        self.ai_provider_var.set(getattr(pipeline, "AI_PROVIDER", "gpt"))

        loaded_gpt_model = str(getattr(pipeline, "GPT_MODEL", DEFAULT_GPT_MODEL) or DEFAULT_GPT_MODEL).strip()
        if loaded_gpt_model not in GPT_MODEL_OPTIONS:
            loaded_gpt_model = DEFAULT_GPT_MODEL
        self.gpt_model_var.set(loaded_gpt_model)

        self.gemini_model_var.set(getattr(pipeline, "GEMINI_MODEL", "gemini-3.1-pro-preview"))
        self.api_key_var.set("")
        self._refresh_api_key_display()
        self.base_url_var.set(getattr(pipeline, "BASE_URL", ""))
        self.project_id_var.set(getattr(pipeline, "PROJECT_ID", "") or "N/A")
        self.api_version_var.set(getattr(pipeline, "API_VERSION", "2025-04-01-preview"))
        self.gemini_stream_option_var.set(getattr(pipeline, "GEMINI_STREAM_OPTION", "generateContent"))
        self.max_retry_var.set(str(getattr(pipeline, "MAX_RETRY", 3)))
        self.skip_if_output_exists_var.set(bool(getattr(pipeline, "SKIP_IF_OUTPUT_EXISTS", True)))
        self.completed_answer_file_pass_var.set(bool(getattr(pipeline, "COMPLETED_ANSWER_FILE_PASS", False)))
        self.merge_split_answer_files_var.set(bool(getattr(pipeline, "MERGE_SPLIT_ANSWER_FILES", True)))
        self.keep_split_answer_files_after_merge_var.set(bool(getattr(pipeline, "KEEP_SPLIT_ANSWER_FILES_AFTER_MERGE", False)))

    # =========================================================
    # GUI 옵션 자동 저장 / 복원
    # =========================================================
    def _collect_gui_settings(self) -> dict:
        return {
            "project_dir": self.project_dir_var.get().strip(),
            "run_steps": {
                "step_1": bool(self.run_step_1_var.get()),
                "step_2": bool(self.run_step_2_var.get()),
                "step_3": bool(self.run_step_3_var.get()),
                "step_4": bool(self.run_step_4_var.get()),
                "step_5": bool(self.run_step_5_var.get()),
                "step_6": bool(self.run_step_6_var.get()),
                "step_7": bool(self.run_step_7_var.get()),
                "report": bool(self.run_step_report_var.get()),
            },
            "retry_failed_only": bool(self.retry_failed_only_var.get()),
            "category": self.category_var.get().strip(),
            "global_mode_enabled": bool(self.global_mode_enabled_var.get()),
            "can": {
                "CAN1": {"enabled": bool(self.can1_enabled_var.get()), "dbc": self.can1_dbc_var.get().strip()},
                "CAN2": {"enabled": bool(self.can2_enabled_var.get()), "dbc": self.can2_dbc_var.get().strip()},
                "CAN3": {"enabled": bool(self.can3_enabled_var.get()), "dbc": self.can3_dbc_var.get().strip()},
                "CAN4": {"enabled": bool(self.can4_enabled_var.get()), "dbc": self.can4_dbc_var.get().strip()},
            },
            "analysis": {
                "drop_first_seconds_enabled": bool(self.drop_first_seconds_enabled_var.get()),
                "drop_first_seconds": self.drop_first_seconds_var.get().strip(),
                "asc_frame_direction": asc_frame_direction_label_to_value(self.asc_frame_direction_var.get()),
                "change_threshold": self.change_threshold_var.get().strip(),
                "skip_high_frequency": bool(self.skip_high_frequency_var.get()),
                "global_exclude_crc_alv": bool(self.global_exclude_crc_alv_var.get()),
                "step_5_enable_time_folder": bool(self.step_5_enable_time_folder_var.get()),
            },
            "ai": {
                "provider": self.ai_provider_var.get().strip(),
                "gpt_model": self.gpt_model_var.get().strip(),
                "gemini_model": self.gemini_model_var.get().strip(),
                "max_retry": self.max_retry_var.get().strip(),
                "skip_if_output_exists": bool(self.skip_if_output_exists_var.get()),
                "completed_answer_file_pass": bool(self.completed_answer_file_pass_var.get()),
            },
        }

    def _load_saved_gui_settings(self) -> None:
        path = getattr(self, "_gui_settings_path", None)
        if path is None or not Path(path).exists():
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
        except Exception as e:
            print(f"[WARN] GUI 설정 파일 읽기 실패: {e}")
            return

        self._settings_restore_in_progress = True
        try:
            project_dir = str(data.get("project_dir") or "").strip()
            if project_dir:
                self.project_dir_var.set(project_dir)

            run_steps = data.get("run_steps") if isinstance(data.get("run_steps"), dict) else {}
            if "step_1" in run_steps: self.run_step_1_var.set(bool(run_steps.get("step_1")))
            if "step_2" in run_steps: self.run_step_2_var.set(bool(run_steps.get("step_2")))
            if "step_3" in run_steps: self.run_step_3_var.set(bool(run_steps.get("step_3")))
            if "step_4" in run_steps: self.run_step_4_var.set(bool(run_steps.get("step_4")))
            if "step_5" in run_steps: self.run_step_5_var.set(bool(run_steps.get("step_5")))
            if "step_6" in run_steps:
                self.run_step_6_var.set(bool(run_steps.get("step_6")))
            if "step_7" in run_steps:
                self.run_step_7_var.set(bool(run_steps.get("step_7")))
            elif "step_6" in run_steps:
                self.run_step_7_var.set(bool(run_steps.get("step_6")))
            if "report" in run_steps: self.run_step_report_var.set(bool(run_steps.get("report")))

            if "retry_failed_only" in data:
                self.retry_failed_only_var.set(bool(data.get("retry_failed_only")))

            category = str(data.get("category") or "").strip()
            if category.strip().upper() == "GLOBAL":
                # 구버전 GUI 저장값 호환: GLOBAL 카테고리는 별도 체크박스로 이관한다.
                self.global_mode_enabled_var.set(True)
            elif category in self._available_category_values():
                self.category_var.set(category)
            if "global_mode_enabled" in data:
                self.global_mode_enabled_var.set(bool(data.get("global_mode_enabled")))

            can = data.get("can") if isinstance(data.get("can"), dict) else {}
            can_specs = [
                ("CAN1", self.can1_enabled_var, self.can1_dbc_var),
                ("CAN2", self.can2_enabled_var, self.can2_dbc_var),
                ("CAN3", self.can3_enabled_var, self.can3_dbc_var),
                ("CAN4", self.can4_enabled_var, self.can4_dbc_var),
            ]
            for name, enabled_var, dbc_var in can_specs:
                item = can.get(name) if isinstance(can.get(name), dict) else {}
                dbc = str(item.get("dbc") or "").strip()
                if "enabled" in item:
                    enabled = bool(item.get("enabled"))
                else:
                    # 구버전 설정 호환: physical channel 값은 무시하고 DBC 존재 여부로 활성 상태만 복원
                    enabled = bool(dbc and dbc.upper() != "N/A")
                enabled_var.set(enabled)
                if dbc:
                    dbc_var.set(dbc)

            analysis = data.get("analysis") if isinstance(data.get("analysis"), dict) else {}
            if "drop_first_seconds_enabled" in analysis:
                self.drop_first_seconds_enabled_var.set(bool(analysis.get("drop_first_seconds_enabled")))
            if analysis.get("drop_first_seconds") not in (None, ""):
                self.drop_first_seconds_var.set(str(analysis.get("drop_first_seconds")))
            if analysis.get("asc_frame_direction") not in (None, ""):
                self.asc_frame_direction_var.set(asc_frame_direction_value_to_label(str(analysis.get("asc_frame_direction"))))
            if analysis.get("change_threshold") not in (None, ""):
                self.change_threshold_var.set(str(analysis.get("change_threshold")))
            if "skip_high_frequency" in analysis:
                self.skip_high_frequency_var.set(bool(analysis.get("skip_high_frequency")))
            if "global_exclude_crc_alv" in analysis:
                self.global_exclude_crc_alv_var.set(bool(analysis.get("global_exclude_crc_alv")))
            if "step_5_enable_time_folder" in analysis:
                self.step_5_enable_time_folder_var.set(bool(analysis.get("step_5_enable_time_folder")))

            ai = data.get("ai") if isinstance(data.get("ai"), dict) else {}
            provider = str(ai.get("provider") or "").strip().lower()
            if provider in ("gpt", "gemini"):
                self.ai_provider_var.set(provider)
            gpt_model = str(ai.get("gpt_model") or "").strip()
            if gpt_model in GPT_MODEL_OPTIONS:
                self.gpt_model_var.set(gpt_model)
            gemini_model = str(ai.get("gemini_model") or "").strip()
            if gemini_model:
                self.gemini_model_var.set(gemini_model)
            if ai.get("max_retry") not in (None, ""):
                self.max_retry_var.set(str(ai.get("max_retry")))
            if "skip_if_output_exists" in ai:
                self.skip_if_output_exists_var.set(bool(ai.get("skip_if_output_exists")))
            if "completed_answer_file_pass" in ai:
                self.completed_answer_file_pass_var.set(bool(ai.get("completed_answer_file_pass")))

        finally:
            self._settings_restore_in_progress = False

    def _save_current_gui_settings(self) -> None:
        if getattr(self, "_settings_restore_in_progress", False):
            return
        try:
            path = self._gui_settings_path
            path.write_text(json.dumps(self._collect_gui_settings(), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[WARN] GUI 설정 저장 실패: {e}")

    def _schedule_settings_save(self, *args) -> None:
        if getattr(self, "_settings_restore_in_progress", False):
            return
        if getattr(self, "_settings_save_after_id", None) is not None:
            try:
                self.after_cancel(self._settings_save_after_id)
            except Exception:
                pass
        self._settings_save_after_id = self.after(300, self._flush_settings_save)

    def _flush_settings_save(self) -> None:
        self._settings_save_after_id = None
        self._save_current_gui_settings()

    def _bind_settings_autosave(self) -> None:
        vars_to_watch = [
            self.project_dir_var,
            self.run_step_1_var, self.run_step_2_var, self.run_step_3_var, self.run_step_4_var, self.run_step_5_var,
            self.run_step_6_var, self.run_step_7_var, self.run_step_report_var, self.retry_failed_only_var,
            self.category_var, self.global_mode_enabled_var,
            self.can1_enabled_var, self.can2_enabled_var, self.can3_enabled_var, self.can4_enabled_var,
            self.can1_dbc_var, self.can2_dbc_var, self.can3_dbc_var, self.can4_dbc_var,
            self.drop_first_seconds_enabled_var, self.drop_first_seconds_var, self.asc_frame_direction_var,
            self.change_threshold_var, self.skip_high_frequency_var,
            self.step_5_enable_time_folder_var,
            self.ai_provider_var, self.gpt_model_var, self.gemini_model_var,
            self.max_retry_var, self.skip_if_output_exists_var, self.completed_answer_file_pass_var,
        ]
        for var in vars_to_watch:
            try:
                var.trace_add("write", self._schedule_settings_save)
            except Exception:
                pass
        self._save_current_gui_settings()

    def _on_close(self) -> None:
        self._save_current_gui_settings()
        try:
            if self.is_running and self.process is not None and self.process.poll() is None:
                if messagebox.askyesno("종료 확인", "파이프라인이 실행 중입니다. 중지 후 종료할까요?"):
                    self._on_stop_clicked()
                else:
                    return
        except Exception:
            pass
        self.destroy()

    # =========================================================
    # UI 동작
    # =========================================================
    def _browse_project_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.project_dir_var.get() or str(Path.cwd()))
        if selected:
            self.project_dir_var.set(selected)
            self._refresh_project_status()
            self._schedule_settings_save()

    def _open_help_text(self) -> None:
        if self.help_window is not None:
            try:
                if self.help_window.winfo_exists():
                    self.help_window.deiconify()
                    self.help_window.lift()
                    self.help_window.focus_force()
                    return
            except Exception:
                self.help_window = None

        self.help_window = tk.Toplevel(self)
        self.help_window.title("도움말")
        self.help_window.transient(self)

        help_font = tkfont.Font(family="맑은 고딕", size=10)
        width_reference = (
            "9. API Key는 프로젝트 폴더의 API_Key류 txt 파일에서 자동 감지되며 "
            "실제 Key는 GUI에 표시하지 않습니다."
        )
        default_width = max(900, help_font.measure(width_reference) + 110)
        default_height = 650

        self.update_idletasks()
        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()
        parent_w = max(self.winfo_width(), 1)
        parent_h = max(self.winfo_height(), 1)
        pos_x = max(0, parent_x + (parent_w - default_width) // 2)
        pos_y = max(0, parent_y + (parent_h - default_height) // 2)

        self.help_window.geometry(f"{default_width}x{default_height}+{pos_x}+{pos_y}")
        self.help_window.minsize(default_width, 500)

        frame = ttk.Frame(self.help_window, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(frame, text="도움말", font=("맑은 고딕", 12, "bold"))
        title_label.pack(anchor="w", pady=(0, 8))

        text_widget = ScrolledText(
            frame,
            wrap=tk.WORD,
            height=25,
            font=help_font,
            padx=8,
            pady=8,
        )
        text_widget.pack(fill=tk.BOTH, expand=True)

        help_text = (
            "1. 우측 상단에 필요 패키지가 잘 설치되어있는지 확인하세요\n"
            "    └ 필요 패키지: 설치됨으로 되어야 정상입니다\n"
            "    └ 필요 패키지 설치 버튼 클릭만으로 자동으로 설치가 진행 및 완료됩니다.\n"
            "        (필요 패키지가 잘 설치되지 않으면 관리자에게 문의하세요)\n\n"
            "2. 프로젝트 폴더는 항상 모든 파일이 배치되어야 합니다. 경로가 맞는지 확인하세요\n"
            "    └ 프로젝트 폴더에는 다음의 것들이 있어야 합니다\n"
            "        ▶ dbc 파일\n"
            "        ▶ main, gui, step1~7 등 파이썬 파일\n"
            "        ▶ TestCase_모음 엑셀 파일 (.xls / .xlsx / .xlsm, 내부 형식 자동 판별)\n"
            "        ▶ 로그 폴더(이 폴더 안에는 asc 또는 blf의 로그 파일이 있어야 합니다)\n\n"
            "3. 수행하고자 하는 로그 파일에 맞는 카테고리 설정을 잊지마세요\n\n"
            "4. 로그의 CAN1~CAN4에 각각 알맞은 DBC 1개를 매칭하세요\n"
            "    └ VN1640A의 실제 Ch1~Ch4 연결 순서는 이 화면에서 사용하지 않습니다\n"
            "    └ 사용 체크를 해제한 CAN은 분석에서 완전히 제외됩니다\n"
            "    └ 자동감지는 파일명만 사용하며 로그 내용으로 임의 추정하지 않습니다\n"
            "    └ 모든 로그 파일명이 CAN1_B1_CAN2_M_CAN3_P1_CAN4_C 형태로 정확해야 합니다\n"
            "    └ 미인식/형식 오류/충돌/복수 DBC 후보가 하나라도 있으면 아무 설정도 적용하지 않습니다\n"
            "    └ CANx당 DBC는 반드시 1개만 선택할 수 있습니다\n\n"
            "5. 실행 단계를 체크하세요\n"
            "    └ 기본적으로 1~7단계 모두 사용을 추천합니다\n\n"
            "6. 나머지 옵션은 디폴트 상태로 사용해도 무방합니다\n\n"
            "※ Step 4/5는 기본적으로 TC당 단일 후보 프롬프트를 사용하며, 90,000자를 초과하는 예외 케이스만 내부 안전 분할합니다.\n\n"
            "<사용 노하우>\n"
            "1) 만약 사용 중 긴급하게 종료하거나 중단되었다면, \"중지\"버튼을 누릅니다\n"
            "    └ 추후 작업을 재개할 때, 실행 단계 중 \"완료됨\" 이었던 단계를 체크 해제합니다\n"
            "    └ \"이미 있는 파일 건너뛰기\"가 체크되어있는 상태인지 다시 확인합니다\n"
            "    └ \"완료된 답변파일 Pass\"를 체크하고, 실행버튼을 눌러 실행합니다\n\n"
            "2) 완료되었는데 실패파일이 나온 경우, \"실패파일만 재실행\" 항목을 체크 후 실행합니다.\n"
            "    └ Step 5 실패·누락 대상을 먼저 재실행한 뒤, 갱신된 케이스와 각 후속 Step 자체 .error를 합쳐 Step 6과 Step 7을 순차 재처리합니다.\n"
            "    └ .warning.txt는 확인용 상태이므로 실패파일 재실행 대상에는 포함하지 않습니다.\n"
            "    └ Step 6은 로컬 상세 추출이며, Step 7은 고신뢰 로컬 분류 후 애매한 신호만 API를 사용합니다.\n"
        )
        text_widget.insert("1.0", help_text)
        text_widget.configure(state="disabled")

        button_row = ttk.Frame(frame)
        button_row.pack(fill=tk.X, pady=(8, 0))

        def _on_close():
            try:
                if self.help_window is not None and self.help_window.winfo_exists():
                    self.help_window.destroy()
            except Exception:
                pass
            self.help_window = None

        ttk.Button(button_row, text="닫기", command=_on_close).pack(side=tk.RIGHT)
        self.help_window.protocol("WM_DELETE_WINDOW", _on_close)

    def _is_global_mode_enabled(self) -> bool:
        return bool(getattr(self, "global_mode_enabled_var", tk.BooleanVar(value=False)).get())

    def _set_widget_state_safe(self, widget, state: str) -> None:
        try:
            widget.configure(state=state)
        except Exception:
            pass

    def _set_children_state_safe(self, parent, state: str) -> None:
        try:
            children = list(parent.winfo_children())
        except Exception:
            return
        for child in children:
            self._set_widget_state_safe(child, state)
            self._set_children_state_safe(child, state)

    def _on_category_changed(self) -> None:
        try:
            self._apply_category_mode()
            self._schedule_settings_save()
        except Exception:
            pass

    def _on_global_mode_toggled(self) -> None:
        try:
            self._apply_category_mode()
            self._schedule_settings_save()
        except Exception:
            pass

    def _apply_category_mode(self) -> None:
        if not hasattr(self, "run_step_1_var"):
            return

        is_global = self._is_global_mode_enabled()

        if is_global and not self._global_mode_active:
            self._pre_global_state = {
                "run_steps": [
                    self.run_step_1_var.get(), self.run_step_2_var.get(), self.run_step_3_var.get(),
                    self.run_step_4_var.get(), self.run_step_5_var.get(), self.run_step_6_var.get(), self.run_step_7_var.get(),
                ],
                "run_report": self.run_step_report_var.get(),
                "retry_failed_only": self.retry_failed_only_var.get(),
                "drop_enabled": self.drop_first_seconds_enabled_var.get(),
                "drop_value": self.drop_first_seconds_var.get(),
                "asc_frame_direction": self.asc_frame_direction_var.get(),
                "skip_high_frequency": self.skip_high_frequency_var.get(),
                "step6_time_detail": self.step_5_enable_time_folder_var.get(),
            }
        elif (not is_global) and self._global_mode_active:
            old = self._pre_global_state or {}
            steps = old.get("run_steps") or []
            if len(steps) == 7:
                for var, val in zip(
                    [self.run_step_1_var, self.run_step_2_var, self.run_step_3_var, self.run_step_4_var, self.run_step_5_var, self.run_step_6_var, self.run_step_7_var],
                    steps,
                ):
                    var.set(bool(val))
            self.run_step_report_var.set(bool(old.get("run_report", self.run_step_report_var.get())))
            self.retry_failed_only_var.set(bool(old.get("retry_failed_only", self.retry_failed_only_var.get())))
            self.drop_first_seconds_enabled_var.set(bool(old.get("drop_enabled", True)))
            self.drop_first_seconds_var.set(str(old.get("drop_value", getattr(pipeline, "DROP_FIRST_SECONDS", 8.0))))
            self.asc_frame_direction_var.set(str(old.get("asc_frame_direction", ASC_FRAME_DIRECTION_VALUE_TO_LABEL["auto"])))
            self.skip_high_frequency_var.set(bool(old.get("skip_high_frequency", True)))
            self.step_5_enable_time_folder_var.set(bool(old.get("step6_time_detail", False)))

        self._global_mode_active = is_global

        if is_global:
            for var in [self.run_step_1_var, self.run_step_2_var, self.run_step_3_var, self.run_step_4_var, self.run_step_5_var, self.run_step_6_var, self.run_step_7_var]:
                var.set(False)
            self.run_step_report_var.set(False)
            self.retry_failed_only_var.set(False)
            self.drop_first_seconds_enabled_var.set(False)
            self.drop_first_seconds_var.set("0")
            self.asc_frame_direction_var.set(ASC_FRAME_DIRECTION_VALUE_TO_LABEL.get("both", "Rx+Tx(전체)"))
            self.skip_high_frequency_var.set(False)
            self.step_5_enable_time_folder_var.set(False)
            self._set_warning_status("GLOBAL 모드: BLF→ASC 후 전체 ASC 디코딩만 수행합니다. Step/AI/Drop 옵션은 잠금 처리됩니다.", "info")

        if hasattr(self, "category_combo"):
            self._set_widget_state_safe(self.category_combo, "disabled" if is_global else "readonly")

        step_state = "disabled" if is_global else "normal"
        for cb in getattr(self, "step_checkbuttons", {}).values():
            self._set_widget_state_safe(cb, step_state)
        for widget_name in [
            "report_auto_check", "report_button", "drop_first_seconds_check", "drop_first_seconds_entry",
            "asc_frame_direction_combo", "skip_high_frequency_check", "change_threshold_label", "change_threshold_entry",
            "step6_time_detail_check",
        ]:
            if hasattr(self, widget_name):
                self._set_widget_state_safe(getattr(self, widget_name), step_state)

        # GLOBAL 전용 옵션만 GLOBAL에서 활성화한다.
        if hasattr(self, "global_exclude_crc_alv_check"):
            self._set_widget_state_safe(self.global_exclude_crc_alv_check, "normal" if is_global else "disabled")

        if hasattr(self, "ai_frame"):
            self._set_children_state_safe(self.ai_frame, "disabled" if is_global else "normal")
            if not is_global:
                self._update_ai_provider_ui()

        if not is_global:
            self._toggle_drop_first_seconds_state()
            self._toggle_change_threshold_visibility()


    def _toggle_drop_first_seconds_state(self) -> None:
        if not hasattr(self, "drop_first_seconds_entry"):
            return

        if self.drop_first_seconds_enabled_var.get():
            self.drop_first_seconds_entry.configure(state="normal")
            if self.drop_first_seconds_var.get().strip() in ("", "0", "0.0"):
                self.drop_first_seconds_var.set(str(getattr(pipeline, "DROP_FIRST_SECONDS", 8.0)))
        else:
            self.drop_first_seconds_var.set("0")
            self.drop_first_seconds_entry.configure(state="disabled")

    def _toggle_change_threshold_visibility(self) -> None:
        if not hasattr(self, "change_threshold_entry"):
            return

        if self.skip_high_frequency_var.get():
            self.change_threshold_entry.configure(state="normal")
        else:
            self.change_threshold_entry.configure(state="disabled")

    def _update_ai_provider_ui(self) -> None:
        provider = self.ai_provider_var.get().strip().lower()

        if provider == "gemini":
            self.gpt_section.pack_forget()
            self.gemini_section.pack(fill=tk.X, padx=6, pady=2, before=self.common_ai_section)
        else:
            self.gemini_section.pack_forget()
            self.gpt_section.pack(fill=tk.X, padx=6, pady=2, before=self.common_ai_section)

    def _set_dbc_values(self, dbc_files: list[str]) -> None:
        values = ["N/A"] + dbc_files
        for combo in (self.can1_combo, self.can2_combo, self.can3_combo, self.can4_combo):
            combo.configure(values=values)

        for var in (self.can1_dbc_var, self.can2_dbc_var, self.can3_dbc_var, self.can4_dbc_var):
            cur = var.get().strip() or "N/A"
            if cur not in values:
                var.set("N/A")
        self._refresh_can_row_states()

    def _refresh_project_status(self, evaluate_mapping: bool = False) -> None:
        base = Path(self.project_dir_var.get()).expanduser()

        if not base.exists() or not base.is_dir():
            self.input_status_var.set("입력 상태: 프로젝트 폴더가 존재하지 않음")
            self._set_dbc_values([])
            self._refresh_api_key_display(base)
            self._set_warning_status("프로젝트 폴더가 존재하지 않음", "error")
            self._set_match_status("대기중", "info")
            self._last_match_detail_lines = ["프로젝트 폴더가 존재하지 않습니다."]
            return

        blf_count = len(self._collect_current_blf_files(base))
        asc_count = len(self._collect_current_asc_files(base))
        dbc_files = [p.name for p in self._collect_current_dbc_files(base)]
        xlsx_count = len(self._collect_current_xlsx_files(base))
        log_dir_count = len(self._collect_log_dirs(base))

        self.input_status_var.set(
            f"입력 상태: BLF {blf_count}개 / ASC {asc_count}개 / DBC {len(dbc_files)}개 / XLSX {xlsx_count}개 / 로그폴더 {log_dir_count}개"
        )
        self._set_dbc_values(dbc_files)
        self._refresh_can_row_states()
        self._refresh_api_key_display(base)

        if evaluate_mapping:
            self._refresh_match_status()
        else:
            self._set_match_status("대기중", "info")
            self._last_match_detail_lines = ["실행 또는 새로고침/자동감지 전 대기 상태입니다."]

        warning_messages = []
        if len(dbc_files) == 0:
            warning_messages.append("DBC 파일 없음")
        if xlsx_count == 0:
            warning_messages.append("TestCase 모음 엑셀파일 없음")

        if warning_messages:
            self._set_warning_status(" / ".join(warning_messages), "warn")
        else:
            self._set_warning_status("실행 대기중", "info")

    def _on_refresh_clicked(self) -> None:
        self._refresh_project_status(evaluate_mapping=True)
        self._log("[GUI] 새로고침 완료: base/log 폴더, DBC, API Key, 로그 CAN-DBC 상태를 다시 확인했습니다.\n")
        self._schedule_settings_save()

    def _show_auto_detect_popup(
        self,
        title: str,
        lines: list[str],
        *,
        level: str = "info",
        red_lines: list[str] | None = None,
        footer_lines: list[str] | None = None,
    ) -> None:
        """자동감지 전용 결과 창. 가로 936px, 세로 325px로 메인 창 중앙에 표시한다."""
        popup = tk.Toplevel(self)
        popup.title(title)
        popup.transient(self)
        popup.grab_set()

        # V2 REV03: 가로 길이는 기존 936px을 유지하고 세로 길이는 650px의 절반으로 축소.
        width, height = 936, 325

        self.update_idletasks()
        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()
        parent_w = max(self.winfo_width(), 1)
        parent_h = max(self.winfo_height(), 1)
        pos_x = max(0, parent_x + (parent_w - width) // 2)
        pos_y = max(0, parent_y + (parent_h - height) // 2)
        popup.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
        popup.minsize(720, 260)

        color_by_level = {
            "info": "#1f4e79",
            "warn": "#b45f06",
            "error": "#c00000",
        }
        header_text = {
            "info": "자동감지 결과",
            "warn": "자동감지 확인 필요",
            "error": "자동감지 오류",
        }.get(level, "자동감지 결과")

        body_frame = ttk.Frame(popup, padding=(18, 16, 18, 12))
        body_frame.pack(fill=tk.BOTH, expand=True)

        header = tk.Label(
            body_frame,
            text=header_text,
            anchor="w",
            font=("Malgun Gothic", 13, "bold"),
            fg=color_by_level.get(level, "#1f4e79"),
        )
        header.pack(fill=tk.X, pady=(0, 10))

        text_widget = ScrolledText(
            body_frame,
            wrap=tk.WORD,
            font=("Malgun Gothic", 10),
            padx=12,
            pady=10,
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.tag_configure("normal", foreground="#202020")
        text_widget.tag_configure("section", foreground="#1f4e79", font=("Malgun Gothic", 10, "bold"))
        text_widget.tag_configure("red_warning", foreground="#c00000", font=("Malgun Gothic", 10, "bold"))

        red_set = {str(line) for line in (red_lines or [])}
        for line in lines:
            line = str(line)
            if line in red_set:
                tag = "red_warning"
            elif line.startswith("[") and line.endswith("]"):
                tag = "section"
            else:
                tag = "normal"
            text_widget.insert(tk.END, line + "\n", tag)
        text_widget.configure(state=tk.DISABLED)

        if footer_lines:
            footer_frame = tk.Frame(
                body_frame,
                bg="#fff4e5",
                bd=1,
                relief=tk.SOLID,
                padx=10,
                pady=6,
            )
            footer_frame.pack(fill=tk.X, pady=(8, 0))
            for footer_line in footer_lines:
                tk.Label(
                    footer_frame,
                    text=str(footer_line),
                    anchor="w",
                    justify=tk.LEFT,
                    bg="#fff4e5",
                    fg="#9c5700",
                    font=("Malgun Gothic", 9, "bold"),
                ).pack(fill=tk.X)

        button_frame = ttk.Frame(body_frame)
        button_frame.pack(fill=tk.X, pady=(12, 0))
        ok_button = ttk.Button(button_frame, text="확인", command=popup.destroy, width=14)
        ok_button.pack(side=tk.RIGHT)
        popup.bind("<Escape>", lambda _e: popup.destroy())
        popup.protocol("WM_DELETE_WINDOW", popup.destroy)
        ok_button.focus_set()
        self.wait_window(popup)

    def _on_auto_detect_clicked(self) -> None:
        base = Path(self.project_dir_var.get()).expanduser()
        if not base.exists() or not base.is_dir():
            self._show_auto_detect_popup(
                "자동감지",
                ["프로젝트 폴더가 존재하지 않습니다."],
                level="error",
                red_lines=["프로젝트 폴더가 존재하지 않습니다."],
            )
            self._set_warning_status("프로젝트 폴더가 존재하지 않음", "error")
            return

        (
            log_files,
            parsed_by_file,
            _values_by_can,
            conflicts,
            consensus,
            unparsed_files,
            malformed_by_can,
            duplicate_by_file,
        ) = self._analyze_asc_can_maps(base)
        (_cat_files, category_by_file, category_conflicts, category_consensus, unknown_category_files) = self._analyze_asc_categories(base)

        if not log_files:
            msg = "ASC/BLF 파일이 없어 자동감지를 수행할 수 없습니다."
            self._show_auto_detect_popup("자동감지", [msg], level="warn")
            self._set_match_status("대기중", "info")
            self._last_match_detail_lines = [msg]
            return

        blocking_lines: list[str] = []
        red_lines: list[str] = []

        if unparsed_files:
            blocking_lines += ["[파일명 CAN 매핑 미인식]"] + [f"- {name}" for name in unparsed_files[:30]]
        if malformed_by_can:
            blocking_lines += ["", "[파일명 형식 오류]"]
            for can_name, names in sorted(malformed_by_can.items()):
                for name in names[:20]:
                    blocking_lines.append(f"- {name}: {can_name} 뒤의 x-CAN 코드/구분자 확인")
        if duplicate_by_file:
            blocking_lines += ["", "[한 파일에서 동일 CANx 중복 선언]"]
            for name, items in sorted(duplicate_by_file.items()):
                blocking_lines.append(f"- {name}: {' / '.join(items)}")
        if conflicts:
            blocking_lines += [
                "",
                "다른 로그가 감지되었습니다",
                "[로그 간 CAN 매핑 충돌]",
            ]
            for can_name, values in sorted(conflicts.items()):
                blocking_lines.append(f"- {can_name}: {', '.join(values)}")
        if category_conflicts:
            blocking_lines += ["", "[카테고리 충돌]"]
            for name, (token, category) in sorted(category_by_file.items()):
                blocking_lines.append(f"- {name}: {token} → {category}")
        if unknown_category_files:
            blocking_lines += ["", "[카테고리 명칭 미인식]"]
            for name, token in unknown_category_files[:30]:
                blocking_lines.append(f"- {name}: '{token}'")
        if not consensus:
            blocking_lines += ["", "[CAN 매핑 없음]", "- 예: 편의_001_CAN1_B1_CAN2_M_CAN3_P1_CAN4_C.asc"]

        # 먼저 모든 DBC 후보를 검증하고, 하나라도 누락/복수이면 어떤 GUI 값도 변경하지 않는다.
        proposed_dbc: dict[str, str] = {}
        for can_name in CAN_NAMES:
            code = consensus.get(can_name)
            if not code:
                continue
            dbc_name, matches = self._find_dbc_for_bus_code(base, code)
            if len(matches) == 0:
                blocking_lines += ["", f"[DBC 없음] {can_name}: LOG={code}"]
            elif len(matches) > 1:
                blocking_lines += ["", f"[복수 DBC 후보] {can_name}: LOG={code}"] + [f"- {name}" for name in matches[:20]]
            elif dbc_name:
                proposed_dbc[can_name] = dbc_name

        if blocking_lines:
            intro = [
                "자동감지를 중단했습니다.",
                "파일명 규칙 또는 DBC 후보가 명확하지 않아 기존 CAN/DBC 설정은 변경하지 않았습니다.",
                "로그 내용이나 메시지 유사도로 임의 추정하지 않습니다.",
                "",
            ]
            red_lines = [line for line in blocking_lines if line.startswith("[") or "오류" in line or "충돌" in line or "복수" in line]
            lines = intro + blocking_lines
            filename_blocked = bool(
                unparsed_files
                or malformed_by_can
                or duplicate_by_file
                or conflicts
                or category_conflicts
                or unknown_category_files
                or not consensus
            )
            if filename_blocked:
                footer_lines = [
                    "※ 잘못된 파일명 또는 서로 충돌하는 로그 명칭이 포함되어 자동감지를 중단했습니다.",
                    "※ CAN1~CAN4 사용/DBC/카테고리의 기존 선택값은 변경하지 않았습니다.",
                ]
            else:
                footer_lines = [
                    "※ DBC 후보가 명확하지 않아 자동감지를 중단했습니다.",
                    "※ CAN1~CAN4 사용/DBC/카테고리의 기존 선택값은 변경하지 않았습니다.",
                ]
            self._show_auto_detect_popup(
                "자동감지",
                lines[:150],
                level="warn",
                red_lines=red_lines,
                footer_lines=footer_lines,
            )
            self._set_warning_status("자동감지 중단 - 파일명/DBC 확인 필요", "warn")
            self._set_match_status("경고", "warn")
            self._last_match_detail_lines = lines
            return

        # 검증이 전부 끝난 뒤에만 일괄 적용한다.
        dbc_files = [p.name for p in self._collect_current_dbc_files(base)]
        self._set_dbc_values(dbc_files)
        enabled_vars = {
            "CAN1": self.can1_enabled_var,
            "CAN2": self.can2_enabled_var,
            "CAN3": self.can3_enabled_var,
            "CAN4": self.can4_enabled_var,
        }
        dbc_vars = {
            "CAN1": self.can1_dbc_var,
            "CAN2": self.can2_dbc_var,
            "CAN3": self.can3_dbc_var,
            "CAN4": self.can4_dbc_var,
        }
        for can_name in CAN_NAMES:
            dbc_name = proposed_dbc.get(can_name)
            enabled_vars[can_name].set(bool(dbc_name))
            dbc_vars[can_name].set(dbc_name or "N/A")

        if category_consensus:
            self.category_var.set(category_consensus)

        self._refresh_can_row_states()
        self._schedule_settings_save()
        self._refresh_match_status()

        result_lines = ["자동감지 완료", "", "[적용 결과]"]
        if category_consensus:
            prefix = getattr(pipeline, "CATEGORIES", {}).get(category_consensus, {}).get("prefix", category_consensus)
            result_lines.append(f"- 카테고리: {category_consensus} ({prefix})")
        for can_name in CAN_NAMES:
            if can_name in proposed_dbc:
                result_lines.append(f"- {can_name}: LOG={consensus[can_name]} → {proposed_dbc[can_name]} (활성)")
            else:
                result_lines.append(f"- {can_name}: 로그 파일명에 매핑 없음 → 비활성")

        self._show_auto_detect_popup("자동감지", result_lines, level="info")
        self._set_warning_status("자동감지 완료 - 실행 대기중", "info")

    # =========================================================
    # CAN 활성/비활성 및 DBC 선택 상태
    # =========================================================
    def _on_can_enabled_changed(self) -> None:
        self._refresh_can_row_states()
        self._refresh_match_status()
        self._schedule_settings_save()

    def _on_dbc_selection_changed(self, event=None) -> None:
        self._refresh_match_status()
        self._schedule_settings_save()

    def _refresh_can_row_states(self) -> None:
        specs = [
            (self.can1_enabled_var, self.can1_combo),
            (self.can2_enabled_var, self.can2_combo),
            (self.can3_enabled_var, self.can3_combo),
            (self.can4_enabled_var, self.can4_combo),
        ]
        for enabled_var, combo in specs:
            combo.configure(state="readonly" if enabled_var.get() else "disabled")

    # =========================================================
    # 설정 구성
    # =========================================================
    def _collect_can_config(self) -> dict:
        return {
            "CAN1": {
                "enabled": bool(self.can1_enabled_var.get()),
                "dbc": None if self.can1_dbc_var.get().strip() in ("", "N/A") else self.can1_dbc_var.get().strip(),
            },
            "CAN2": {
                "enabled": bool(self.can2_enabled_var.get()),
                "dbc": None if self.can2_dbc_var.get().strip() in ("", "N/A") else self.can2_dbc_var.get().strip(),
            },
            "CAN3": {
                "enabled": bool(self.can3_enabled_var.get()),
                "dbc": None if self.can3_dbc_var.get().strip() in ("", "N/A") else self.can3_dbc_var.get().strip(),
            },
            "CAN4": {
                "enabled": bool(self.can4_enabled_var.get()),
                "dbc": None if self.can4_dbc_var.get().strip() in ("", "N/A") else self.can4_dbc_var.get().strip(),
            },
        }

    def _build_dbc_name_by_ch_from_can_config(self, can_config: dict) -> dict:
        dbc_name_by_ch = {}
        for logical_channel, can_name in enumerate(CAN_NAMES, start=1):
            item = can_config.get(can_name, {})
            if not bool(item.get("enabled", False)):
                continue
            dbc = item.get("dbc")
            if isinstance(dbc, (list, tuple, set, dict)):
                raise ValueError(f"{can_name}: DBC는 1개만 선택할 수 있습니다.")
            if dbc:
                dbc_name_by_ch[logical_channel] = str(dbc)
        return dbc_name_by_ch

    def _build_config_preview_dict(self, report_only: bool = False) -> dict:
        base_dir = Path(self.project_dir_var.get()).expanduser().resolve()
        if not base_dir.exists() or not base_dir.is_dir():
            raise ValueError(f"프로젝트 폴더가 존재하지 않습니다: {base_dir}")

        category = self.category_var.get().strip()
        if category not in pipeline.CATEGORIES or category.upper() == "GLOBAL":
            raise ValueError(f"지원하지 않는 카테고리입니다: {category}")

        is_global = bool(self.global_mode_enabled_var.get())
        drop_first_seconds = 0.0 if is_global else float(self.drop_first_seconds_var.get().strip())
        change_threshold = int(self.change_threshold_var.get().strip())
        max_retry = int(self.max_retry_var.get().strip())

        can_config = self._collect_can_config()

        # 유효성 검사
        # - 일반 파이프라인 실행: 활성 CAN에는 DBC 1개가 반드시 있어야 함
        # - Report 단독 생성: 기존 AI답변 또는 샘플만 읽을 수 있으므로 CAN/DBC 미선택 허용
        if report_only:
            can_config = {name: {"enabled": False, "dbc": None} for name in CAN_NAMES}
        else:
            for can_name, item in can_config.items():
                enabled = bool(item.get("enabled", False))
                dbc = item.get("dbc")
                if isinstance(dbc, (list, tuple, set, dict)):
                    raise ValueError(f"{can_name}: DBC는 1개만 선택할 수 있습니다.")
                if enabled and not dbc:
                    raise ValueError(f"{can_name}: 활성 상태인데 DBC가 N/A입니다.")

        dbc_name_by_ch = self._build_dbc_name_by_ch_from_can_config(can_config)

        if not dbc_name_by_ch and not report_only:
            raise ValueError("DBC 파일을 최소 1개 이상 선택해야 합니다.")

        config_data = {
            "base_dir": str(base_dir),
            "active_category": category,
            "global_mode": is_global,

            "run_step_1": False if is_global else self.run_step_1_var.get(),
            "run_step_2": False if is_global else self.run_step_2_var.get(),
            "step_2_ai_enhancement": False if is_global else self.step_2_ai_enhancement_var.get(),
            "run_step_3": False if is_global else self.run_step_3_var.get(),
            "run_step_4": False if is_global else self.run_step_4_var.get(),
            "run_step_5": False if is_global else self.run_step_5_var.get(),
            "run_step_6": False if is_global else self.run_step_6_var.get(),
            "run_step_7": False if is_global else self.run_step_7_var.get(),
            "run_step_report": False if is_global else self.run_step_report_var.get(),
            "retry_failed_only": False if is_global else self.retry_failed_only_var.get(),

            "can_config": can_config,
            "dbc_name_by_ch": dbc_name_by_ch,

            "drop_first_seconds": drop_first_seconds,
            "asc_frame_direction": "both" if is_global else asc_frame_direction_label_to_value(self.asc_frame_direction_var.get()),
            "change_threshold": change_threshold,
            "skip_high_frequency": False if is_global else self.skip_high_frequency_var.get(),
            "global_exclude_crc_alv": self.global_exclude_crc_alv_var.get(),
            "step_5_enable_time_folder": False,
            "step_6_enable_time_detail": self.step_5_enable_time_folder_var.get(),

            "ai_provider": self.ai_provider_var.get().strip().lower(),
            "gpt_model": self.gpt_model_var.get().strip(),
            "gemini_model": self.gemini_model_var.get().strip(),
            "gemini_stream_option": self.gemini_stream_option_var.get().strip(),
            "api_key": "",
            "api_key_display": self.api_key_display_var.get().strip(),
            "base_url": self.base_url_var.get().strip(),
            "project_id": "" if self.project_id_var.get().strip().upper() == "N/A" else self.project_id_var.get().strip(),
            "api_version": self.api_version_var.get().strip(),

            "max_retry": max_retry,
            "skip_if_output_exists": self.skip_if_output_exists_var.get(),
            "completed_answer_file_pass": self.completed_answer_file_pass_var.get(),

            "merge_split_answer_files": False,
            "keep_split_answer_files_after_merge": False,

            "global_output_dir_name": "분석된 txt 파일",
            "report_output_dir_name": "Report_결과",
            "report_title": "AI 로그 분석 결과 레포트",
            "report_sample_if_empty": True,
            "step_6_output_dir_name": "AI답변_결과",
            "step_6_enable_ai_judgement": True,
            "step_6_ai_max_retry": 2,
        }
        return config_data

    def _precheck_warnings(self, config_data: dict) -> list[str]:
        warnings = []
        base_dir = Path(config_data["base_dir"])

        for ch, dbc_name in config_data.get("dbc_name_by_ch", {}).items():
            if not (base_dir / dbc_name).exists():
                warnings.append(f"CAN{ch} DBC 파일 없음")

        step2_ai_enabled = bool(config_data.get("run_step_2", False) and config_data.get("step_2_ai_enhancement", False))
        if config_data.get("run_step_4", False) or step2_ai_enabled:
            excel_glob = getattr(pipeline, "EXCEL_GLOB", "TestCase_모음*.xls*")
            excel_candidates = list(base_dir.glob(excel_glob))
            if not excel_candidates:
                warnings.append("TestCase 모음 엑셀파일 없음")

        if (config_data.get("run_step_5", False) or step2_ai_enabled) and (not self._has_detected_api_key_file(base_dir)):
            warnings.append("API KEY 미감지")

        level, text, details = self._evaluate_asc_dbc_mapping()
        self._last_match_detail_lines = details
        self._set_match_status(text, level)
        if level == "warn":
            warnings.append("로그 CAN-DBC 매핑 경고")
        elif level == "error":
            warnings.append("로그 CAN-DBC 매핑 오류")

        return warnings

    def _preview_config(self) -> None:
        try:
            config_data = self._build_config_preview_dict()
            preview_data = dict(config_data)
            if preview_data.get("api_key"):
                preview_data["api_key"] = "***MASKED***"
            self._log("\n[GUI] 설정 미리보기\n")
            self._log(json.dumps(preview_data, ensure_ascii=False, indent=2) + "\n")
            self._log("[GUI] 설정 미리보기 완료\n")
        except Exception as e:
            messagebox.showerror("설정 오류", str(e))


    # =========================================================
    # 실행/중지
    # =========================================================
    def _on_run_clicked(self) -> None:
        if self.is_running:
            messagebox.showinfo("실행 중", "이미 파이프라인이 실행 중입니다.")
            return

        try:
            config_data = self._build_config_preview_dict()
        except Exception as e:
            messagebox.showerror("설정 오류", str(e))
            self._set_warning_status(str(e), "error")
            return

        step2_ai_enabled = bool(config_data.get("run_step_2", False) and config_data.get("step_2_ai_enhancement", False))
        if (config_data.get("run_step_5", False) or step2_ai_enabled) and not self._has_detected_api_key_file(Path(config_data["base_dir"])):
            msg = "API KEY가 감지되지 않았습니다."
            if step2_ai_enabled and not config_data.get("run_step_5", False):
                msg = "Step 2 AI 후보 보강을 사용하려면 API KEY가 필요합니다."
            messagebox.showwarning("API KEY", msg)
            self._set_warning_status(msg, "error")
            return

        warnings = self._precheck_warnings(config_data)
        if warnings:
            self._set_warning_status(f"진행중.. ({' / '.join(warnings)})", "warn")
        else:
            self._set_warning_status("진행중.. (이상없음)", "info")

        self.stop_requested_by_user = False
        self._pending_report_open_once = False
        self._last_run_config_data = dict(config_data)
        self.last_completed_output_dir = None
        self._set_completed_folder_button(False)
        self._reset_step_statuses()
        self._set_progress_percent(0)
        self.status_var.set("실행 중")
        self.run_button.configure(state=tk.DISABLED)
        if hasattr(self, "report_button"):
            self.report_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.is_running = True

        self._log("\n" + "=" * 80 + "\n")
        self._log("[GUI] 파이프라인 실행 시작\n")
        self._log(f"[GUI] selected main = {self.selected_main_file.name}\n")
        self._log("=" * 80 + "\n")

        try:
            self._start_subprocess(config_data)
        except Exception as e:
            self.is_running = False
            self.status_var.set("대기 중")
            self.run_button.configure(state=tk.NORMAL)
            if hasattr(self, "report_button"):
                self.report_button.configure(state=tk.NORMAL)
            self.stop_button.configure(state=tk.DISABLED)
            self._set_warning_status(f"실행 프로세스 시작 실패: {e}", "error")
            messagebox.showerror("실행 실패", str(e))

    def _on_report_clicked(self) -> None:
        if self.is_running:
            messagebox.showinfo("실행 중", "이미 파이프라인이 실행 중입니다.")
            return

        try:
            config_data = self._build_config_preview_dict(report_only=True)
        except Exception as e:
            messagebox.showerror("설정 오류", str(e))
            self._set_warning_status(str(e), "error")
            return

        # 기존 Step 1~7은 다시 수행하지 않고, Report 생성 모듈만 단독 수행
        config_data["run_step_1"] = False
        config_data["run_step_2"] = False
        config_data["run_step_3"] = False
        config_data["run_step_4"] = False
        config_data["run_step_5"] = False
        config_data["run_step_6"] = False
        config_data["run_step_7"] = False
        config_data["run_step_report"] = True
        config_data["report_sample_if_empty"] = True

        self.stop_requested_by_user = False
        self._pending_report_open_once = True
        self._last_run_config_data = dict(config_data)
        self.last_completed_output_dir = None
        self._set_completed_folder_button(False)
        self._reset_step_statuses()
        self._set_progress_percent(0)
        self.status_var.set("레포트 생성 중")
        self.run_button.configure(state=tk.DISABLED)
        if hasattr(self, "report_button"):
            self.report_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.is_running = True

        self._set_warning_status("레포트 생성 중..", "info")
        self._log("\n" + "=" * 80 + "\n")
        self._log("[GUI] 결과 레포트 생성 시작\n")
        self._log(f"[GUI] selected main = {self.selected_main_file.name}\n")
        self._log("=" * 80 + "\n")

        try:
            self._start_subprocess(config_data)
        except Exception as e:
            self.is_running = False
            self.status_var.set("대기 중")
            self.run_button.configure(state=tk.NORMAL)
            if hasattr(self, "report_button"):
                self.report_button.configure(state=tk.NORMAL)
            self.stop_button.configure(state=tk.DISABLED)
            self._set_warning_status(f"레포트 생성 프로세스 시작 실패: {e}", "error")
            messagebox.showerror("레포트 생성 실패", str(e))

    def _find_latest_report_html(self) -> Path | None:
        try:
            base_dir = Path(self.project_dir_var.get()).expanduser().resolve()
            report_dir = base_dir / "Report_결과"
            if not report_dir.exists():
                return None
            reports = [p for p in report_dir.glob("*.html") if p.is_file()]
            if not reports:
                return None
            timestamp_reports = [p for p in reports if p.name != "Pipeline_Report_latest.html"]
            pool = timestamp_reports if timestamp_reports else reports
            return max(pool, key=lambda x: x.stat().st_mtime)
        except Exception:
            return None

    def _open_latest_report_once(self) -> None:
        report_path = self._find_latest_report_html()
        if report_path is None:
            self._log("[GUI] 자동 오픈할 Report HTML을 찾지 못했습니다.\n")
            return
        try:
            if os.name == "nt":
                os.startfile(str(report_path))  # type: ignore[attr-defined]
            else:
                webbrowser.open(report_path.resolve().as_uri())
            self._log(f"[GUI] Report 자동 오픈: {report_path}\n")
            self.report_status_var.set("생성 완료됨")
        except Exception as e:
            self._log(f"[GUI] Report 자동 오픈 실패: {e}\n")

    def _resolve_completed_output_dir(self, config_data: dict) -> Path:
        """마지막으로 수행한 가장 높은 단계의 대표 결과 폴더를 반환한다."""
        base_dir = Path(config_data.get("base_dir") or self.project_dir_var.get()).expanduser().resolve()
        if bool(config_data.get("global_mode", False)):
            return base_dir / str(config_data.get("global_output_dir_name", "분석된 txt 파일"))
        if bool(config_data.get("run_step_report", False)):
            return base_dir / str(config_data.get("report_output_dir_name", "Report_결과"))
        if any(bool(config_data.get(f"run_step_{step}", False)) for step in (5, 6, 7)):
            output_root = base_dir / str(config_data.get("output_dir", "AI_문의용_출력"))
            answer_root = output_root / str(config_data.get("step_7_output_dir_name") or config_data.get("step_6_output_dir_name") or "AI답변_결과")
            message_dir = answer_root / "메세지별"
            time_dir = answer_root / "시간별"
            if message_dir.exists():
                return message_dir
            if time_dir.exists():
                return time_dir
            return answer_root
        if bool(config_data.get("run_step_4", False)):
            return base_dir / str(config_data.get("output_dir", "AI_문의용_출력"))
        if bool(config_data.get("run_step_3", False)):
            return base_dir / "분석된 txt 파일"
        return base_dir

    def _set_completed_folder_button(self, enabled: bool, folder: Optional[Path] = None) -> None:
        if folder is not None:
            self.last_completed_output_dir = folder
        if hasattr(self, "open_completed_folder_button"):
            self.open_completed_folder_button.configure(state=(tk.NORMAL if enabled else tk.DISABLED))

    def _on_open_completed_results_clicked(self) -> None:
        folder = self.last_completed_output_dir
        if folder is None:
            messagebox.showinfo("완료 결과 폴더", "아직 정상 완료된 작업 결과 폴더가 없습니다.")
            return
        try:
            folder = folder.expanduser().resolve()
            if not folder.exists():
                messagebox.showwarning("완료 결과 폴더", f"결과 폴더를 찾을 수 없습니다.\n{folder}")
                return
            if os.name == "nt":
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
            self._log(f"[GUI] 완료 결과 폴더 열기: {folder}\n")
        except Exception as exc:
            self._log(f"[GUI] 완료 결과 폴더 열기 실패: {exc}\n")
            messagebox.showerror("완료 결과 폴더", f"결과 폴더를 열지 못했습니다.\n{exc}")

    def _start_subprocess(self, config_data: dict) -> None:
        self._excel_security_warning_shown = False
        self._stderr_warning_continuation_lines = 0
        self._python_warning_notice_shown = False
        env = os.environ.copy()
        env["PIPELINE_GUI_CONFIG_JSON"] = json.dumps(config_data, ensure_ascii=False)
        env["PYTHONIOENCODING"] = "utf-8"

        cmd = [sys.executable, "-u", str(self.selected_main_file)]

        self._log(f"[GUI] subprocess cmd = {cmd}\n")
        self._log(f"[GUI] cwd = {config_data['base_dir']}\n")

        popen_kwargs = dict(
            cwd=str(Path(config_data["base_dir"])),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            bufsize=1,
        )

        if sys.platform.startswith("win"):
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        self.process = subprocess.Popen(cmd, **popen_kwargs)

        assert self.process.stdout is not None
        assert self.process.stderr is not None

        self.stdout_reader = StreamReaderThread(self.process.stdout, self.log_queue, "STDOUT")
        self.stderr_reader = StreamReaderThread(self.process.stderr, self.log_queue, "STDERR")
        self.stdout_reader.start()
        self.stderr_reader.start()

        watcher = threading.Thread(target=self._wait_process_worker, daemon=True)
        watcher.start()

    def _wait_process_worker(self) -> None:
        if self.process is None:
            return


        return_code = self.process.wait()
        self.log_queue.put(("PROCESS_DONE", return_code))

    def _on_stop_clicked(self) -> None:
        if not self.is_running or self.process is None:
            return

        try:
            self.stop_requested_by_user = True
            self._set_warning_status("중지버튼 눌림", "warn")
            self._log("\n[GUI] 중지 버튼 눌림 - 강제 종료 요청\n")

            if sys.platform.startswith("win"):
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                    capture_output=True,
                    text=True,
                )
            else:
                self.process.terminate()
        except Exception as e:
            self._set_warning_status(f"강제 종료 실패: {e}", "error")
            self._log(f"[GUI][ERROR] 강제 종료 실패: {e}\n")

    def _on_process_done(self, return_code: int) -> None:
        self.is_running = False
        self.process = None
        self._set_completed_folder_button(False)
        self.status_var.set("대기 중")
        self.run_button.configure(state=tk.NORMAL)
        if hasattr(self, "report_button"):
            self.report_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)
        self._refresh_project_status(evaluate_mapping=True)

        if self.stop_requested_by_user:
            self._set_warning_status("중지버튼 눌림", "warn")
            self._log("\n[GUI] 사용자 요청으로 프로세스 종료\n")
            self.stop_requested_by_user = False
            return

        if return_code == 0:
            checked_steps = self._get_checked_step_numbers()
            if checked_steps:
                total_steps = len(checked_steps)
                last_step = checked_steps[-1]
                self._set_progress_percent(100, label=f"전체 Step {total_steps}/{total_steps} 완료 (100%)")
                self._set_current_progress_percent(100, label=f"현재 Step {last_step} 완료 (100%)")
            else:
                self._set_progress_percent(100, label="전체 완료 (100%)")
                self._set_current_progress_percent(100, label="현재 완료 (100%)")
            self._set_warning_status("정상 종료", "ok")
            completed_dir = self._resolve_completed_output_dir(self._last_run_config_data)
            self._set_completed_folder_button(True, completed_dir)
            self._log(f"\n[GUI] 프로세스 정상 종료\n[GUI] 완료 결과 폴더: {completed_dir}\n")
            if getattr(self, "_pending_report_open_once", False):
                self._pending_report_open_once = False
                self._open_latest_report_once()
        else:
            self._pending_report_open_once = False
            if hasattr(self, "report_status_var") and self.report_status_var.get() == "생성 중":
                self.report_status_var.set("생성 실패")
            self._set_warning_status(f"비정상 종료 (return code={return_code})", "error")
            self._log(f"\n[GUI] 프로세스 비정상 종료 (return code={return_code})\n")

    # =========================================================
    # Step 상태 / 진행률
    # =========================================================
    def _reset_step_statuses(self) -> None:
        for step_no in (1, 2, 3, 4, 5, 6, 7):
            self._set_step_status(step_no, "대기중")
        if hasattr(self, "report_status_var"):
            self.report_status_var.set("대기중")
        self._set_progress_percent(0, label="전체 0%")
        self._set_current_progress_percent(0, label="현재 0%")

    def _draw_progress_bar(self, canvas, rect, text_item, percent: int | float, label: str | None = None) -> int:
        percent = max(0, min(100, int(round(percent))))

        width = int(canvas.winfo_width())
        if width <= 1:
            width = 300

        height = int(canvas.winfo_height())
        if height <= 1:
            height = 14

        fill_width = int(width * percent / 100)
        canvas.coords(rect, 0, 0, fill_width, height)
        canvas.coords(text_item, width // 2, height // 2)
        canvas.itemconfigure(text_item, text=label if label is not None else f"{percent}%")
        return percent

    def _set_progress_percent(self, percent: int | float, label: str | None = None) -> None:
        if not hasattr(self, "progress_canvas"):
            return
        pct = self._draw_progress_bar(self.progress_canvas, self.progress_bar_rect, self.progress_text, percent, label)
        self.progress_percent_var.set(pct)

    def _set_current_progress_percent(self, percent: int | float, label: str | None = None) -> None:
        if not hasattr(self, "current_progress_canvas"):
            return
        pct = self._draw_progress_bar(
            self.current_progress_canvas,
            self.current_progress_bar_rect,
            self.current_progress_text,
            percent,
            label,
        )
        self.current_progress_percent_var.set(pct)

    def _get_checked_step_numbers(self) -> list[int]:
        checked = []
        step_vars = [
            (1, self.run_step_1_var),
            (2, self.run_step_2_var),
            (3, self.run_step_3_var),
            (4, self.run_step_4_var),
            (5, self.run_step_5_var),
            (6, self.run_step_6_var),
            (7, self.run_step_7_var),
        ]
        for step_no, var in step_vars:
            try:
                if bool(var.get()):
                    checked.append(step_no)
            except Exception:
                pass
        return checked

    def _set_overall_progress_by_step(self, step_no: int, status: str) -> None:
        checked = self._get_checked_step_numbers()
        if not checked:
            self._set_progress_percent(0, label="전체 0%")
            return

        total = len(checked)

        if step_no not in checked:
            completed_count = sum(
                1 for s in checked
                if self.step_status_vars.get(s) and self.step_status_vars[s].get() == "완료됨"
            )
            percent = int(completed_count * 100 / total)
            self._set_progress_percent(percent, label=f"전체 {completed_count}/{total} ({percent}%)")
            return

        pos = checked.index(step_no) + 1
        if status == "DONE":
            completed_count = pos
            label_status = "완료"
        else:
            # 진행 중인 Step 자체는 아직 완료된 것으로 계산하지 않는다.
            completed_count = pos - 1
            label_status = "진행중"

        percent = int(completed_count * 100 / total)
        self._set_progress_percent(
            percent,
            label=f"전체 Step {pos}/{total} {label_status} ({percent}%)",
        )

    def _set_step_status(self, step_no: int, status: str) -> None:
        if step_no not in self.step_status_vars:
            return

        self.step_status_vars[step_no].set(status)

        label = self.step_status_labels.get(step_no)
        if label is None:
            return

        palette = {
            "대기중": ("#E5E7EB", "#111827"),
            "진행중": ("#DBEAFE", "#1D4ED8"),
            "완료됨": ("#DCFCE7", "#166534"),
            "에러 발생": ("#FEE2E2", "#B91C1C"),
        }
        bg, fg = palette.get(status, ("#E5E7EB", "#111827"))
        label.configure(bg=bg, fg=fg)

    def _update_step_status_from_log_line(self, line: str) -> None:
        s = line.strip()

        if "[START] REPORT GENERATE" in s:
            self.report_status_var.set("생성 중")
            self._set_current_progress_percent(0, label="Report 생성 중 (0%)")
            self._log("[GUI] Report 생성 중...\n")
            return

        if "[DONE] REPORT GENERATE" in s:
            self.report_status_var.set("생성 완료됨")
            self._set_current_progress_percent(100, label="Report 생성 완료 (100%)")
            self._log("[GUI] Report 생성 완료\n")
            return

        step_map = {
            1: "STEP 1",
            2: "STEP 2",
            3: "STEP 3",
            4: "STEP 4",
            5: "STEP 5",
            6: "STEP 6",
            7: "STEP 7",
        }

        for step_no, step_text in step_map.items():
            if f"[START] {step_text}" in s:
                self._set_step_status(step_no, "진행중")
                self._set_overall_progress_by_step(step_no, status="START")
                self._set_current_progress_percent(0, label=f"현재 Step {step_no} 0%")
                self._log(f"[GUI] Step {step_no} 진행중...\n")
                return

            if f"[DONE] {step_text}" in s:
                self._set_step_status(step_no, "완료됨")
                self._set_overall_progress_by_step(step_no, status="DONE")
                self._set_current_progress_percent(100, label=f"현재 Step {step_no} 완료 (100%)")
                self._log(f"[GUI] Step {step_no} 완료\n")
                return

        if "[ERROR]" in s:
            for step_no in (1, 2, 3, 4, 5, 6, 7):
                if self.step_status_vars[step_no].get() == "진행중":
                    self._set_step_status(step_no, "에러 발생")
                    self._log(f"[GUI] Step {step_no} 에러 발생\n")
                    break

    def _update_subprogress_from_log_line(self, line: str) -> None:
        s = line.strip()

        active_step = None
        for step_no in (1, 2, 3, 4, 5, 6, 7):
            if self.step_status_vars[step_no].get() == "진행중":
                active_step = step_no
                break

        if active_step is None:
            return

        # Step 5는 CASE 단위 진행률만 하단 막대바에 반영한다.
        # split 내부 [1/19] 진행률은 사용자가 요청한 대로 막대바에 반영하지 않는다.
        m_case = re.search(r"\[CASE\s+(\d+)\s*/\s*(\d+)\s*\|\s*([0-9]+(?:\.[0-9]+)?)%\]", s)
        if m_case:
            cur = int(m_case.group(1))
            total = int(m_case.group(2))
            percent = int(max(0, cur - 1) * 100 / total) if total else 0
            self._set_current_progress_percent(
                percent,
                label=f"현재 Step {active_step} CASE {cur}/{total} 진행중 ({percent}%)",
            )
            self._set_warning_status(
                f"진행중.. (Step {active_step} CASE {cur}/{total}, {percent}%)",
                "info",
            )
            return

        if active_step == 5:
            # Step 5 내부 split [1/19] 진행률은 막대바에 반영하지 않는다.
            return

        m = re.search(r"\[(\d+)/(\d+)\]", s)
        if m:
            cur = int(m.group(1))
            total = int(m.group(2))
            percent = int(max(0, cur - 1) * 100 / total) if total else 0
            self._set_current_progress_percent(
                percent,
                label=f"현재 Step {active_step}: {cur}/{total} 진행중 ({percent}%)",
            )
            self._set_warning_status(f"진행중.. (Step {active_step}: {cur}/{total}, {percent}%)", "info")
            return

        m = re.search(r"\((\d+)/(\d+)\)", s)
        if m:
            cur = int(m.group(1))
            total = int(m.group(2))
            percent = int(max(0, cur - 1) * 100 / total) if total else 0
            self._set_current_progress_percent(
                percent,
                label=f"현재 Step {active_step}: {cur}/{total} 진행중 ({percent}%)",
            )
            self._set_warning_status(f"진행중.. (Step {active_step}: {cur}/{total}, {percent}%)", "info")
            return

    # =========================================================
    # 로그
    # =========================================================
    def _show_excel_security_warning(self) -> None:
        if self._excel_security_warning_shown:
            return
        self._excel_security_warning_shown = True
        messagebox.showwarning(
            "TestCase Excel 보안/권한 확인",
            "엑셀 보안 때문에 발생한 문제인지 확인해주세요.\n\n"
            "Excel에서 파일 → 정보 → 통합 문서 보호를 확인하고, "
            "'사내한(Restricted)'으로 되어 있다면 해당 문서가 보호 대상이 아닌 경우에만 "
            "'Any user' 등 허용된 권한으로 변경한 뒤 저장해 주세요.\n\n"
            "권한 변경 후 일반 XLSX로 저장되면 다시 실행할 수 있습니다.",
        )

    def _log(self, text: str) -> None:
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)

    def _clear_log(self) -> None:
        self.log_text.delete("1.0", tk.END)

    def _poll_log_queue(self) -> None:
        try:
            while True:
                item = self.log_queue.get_nowait()

                if not isinstance(item, tuple):
                    self._log(str(item))
                    continue

                kind = item[0]

                if kind in ("STDOUT", "STDERR"):
                    line = item[1]
                    self._log(line)
                    self._update_step_status_from_log_line(line)
                    self._update_subprogress_from_log_line(line)

                    if "[TESTCASE_EXCEL_SECURITY_WARNING]" in line or "Can't find workbook in OLE2 compound document" in line:
                        self._set_warning_status("TestCase Excel 보안/권한 설정 확인 필요", "warn")
                        self._show_excel_security_warning()

                    if kind == "STDERR" and not self.stop_requested_by_user:
                        stderr_class, self._stderr_warning_continuation_lines = classify_stderr_line(
                            line, self._stderr_warning_continuation_lines
                        )
                        if stderr_class in ("python_warning", "python_warning_continuation"):
                            if stderr_class == "python_warning" and not self._python_warning_notice_shown:
                                self._python_warning_notice_shown = True
                                self._log("[GUI][INFO] Python Warning은 실행 오류로 처리하지 않습니다. 실행을 계속합니다.\n")
                        elif stderr_class == "error":
                            self._set_warning_status("stderr 오류 발생 - 로그 확인 필요", "error")
                        elif stderr_class == "stderr":
                            self._set_warning_status("stderr 출력 발생 - 로그 확인 필요", "warn")

                    if "엑셀 파일을 찾지 못함" in line or "엑셀 파일 선택 실패" in line:
                        self._set_warning_status("TestCase 모음 엑셀파일 없음", "error")
                    elif "DBC 파일이 없음" in line or "DBC를 폴더에서 못 찾음" in line:
                        self._set_warning_status("DBC 파일 없음", "error")
                    elif "API KEY가 감지되지 않았습니다" in line or "API_KEY가 비어 있음" in line:
                        self._set_warning_status("API KEY가 감지되지 않았습니다.", "error")
                    elif "[ERROR]" in line and not self.stop_requested_by_user:
                        self._set_warning_status("파이프라인 실행 중 오류 발생", "error")

                elif kind == "PROCESS_DONE":
                    return_code = item[1]
                    self._on_process_done(return_code)

        except queue.Empty:
            pass

        self.after(100, self._poll_log_queue)


def main() -> None:
    app = PipelineGui()
    app.mainloop()


if __name__ == "__main__":
    main()
