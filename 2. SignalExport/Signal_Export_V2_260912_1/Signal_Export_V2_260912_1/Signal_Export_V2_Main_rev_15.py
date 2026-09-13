# -*- coding: utf-8 -*-
"""
[V2 MAIN REV 15 변경점]
- 12번째 일반 카테고리 CONNECT 추가
  * prefix: 12. Connect UX 사양서 기반 TC 검토 초안
  * keywords: 커넥트 / UX / Connect / connect
- Connect UX TC 60개 범위를 기준으로 기존 1~11 카테고리의 ECU sender/message-name Rule을 선별·통합
- CONNECT 선택 시 TestCase Excel의 동일 prefix 시트를 Step 2 AI/Step 4/Step 7에서 기존 공통 Excel reader로 사용
- 기존 1~11 카테고리의 prefix/include/exclude 설정은 변경하지 않음

[V2 MAIN REV 14 변경점]
- TestCase Excel 검색을 TestCase_모음*.xls*로 확장하여 .xls/.xlsx/.xlsm 입력을 허용
- 실제 Excel reader 선택은 공통 Excel Compat 모듈에서 파일 signature 기준으로 처리
- Step 2 AI/Step 4/Step 7의 Excel 형식 호환 정책과 Main 사전검사를 동기화

Signal_Export_V2_Main_rev_15.py

목적
- Signal Export V2 Milestone 01
- step_1 ~ step_7 + Report 파이프라인을 하나의 진입점에서 실행
- 사용자가 바꾸는 모든 옵션은 이 파일에서만 관리
- 각 step 모듈은 run(config) 형태로 호출

추가 기능(Rev 자동 선택)
- STEP/REPORT MODULE 값이 고정(base) 이름이면, 같은 폴더에서
  "{base}_rev_XX.py" / "{base}_revXX.py" / "{base}_rev.XX.py" 중
  가장 큰 XX(숫자) rev 파일이 있으면 그걸 자동으로 선택
- rev 파일이 없으면 base 모듈을 그대로 사용

주의
- Python import는 점(.)이 들어간 모듈명을 직접 import할 수 없어서,
  rev.01 같은 파일은 importlib로 "파일 경로 로딩" 방식으로 불러옵니다.

[GUI 연동 추가]
- subprocess로 실행되는 GUI가 환경변수 PIPELINE_GUI_CONFIG_JSON에 설정을 담아 전달하면
  build_config() 결과 위에 override 적용
- GUI가 없는 일반 단독 실행 시에는 기존 동작 그대로 유지

[로그 CAN 직접 매핑 구조]
- GUI에서 can_config:
    {
      "CAN1": {"enabled": True, "dbc": "xxx_B1.dbc"},
      "CAN2": {"enabled": True, "dbc": "xxx_C.dbc"},
      "CAN3": {"enabled": False, "dbc": None},
      "CAN4": {"enabled": True, "dbc": "xxx_P1.dbc"},
    }
  를 전달할 수 있음
- CAN1~CAN4는 ASC/BLF 로그에 기록된 채널 번호를 의미하며 VN1640A 물리 포트와 무관함
- main.py는 can_config를 우선 해석하여 CANx당 DBC 1개의 dbc_name_by_ch를 생성
- 비활성 CAN은 분석 대상에서 제외

[GPT 기본 모델 변경]
- 기본 GPT 모델은 gpt-5.6-terra
- GUI에서 사용자가 필요 시 gpt-5.4 또는 기존 gpt-5.2 선택 가능
- GPT_MODEL_OPTIONS를 단일 허용 목록으로 사용하여 GUI/Main 검증 정책 동기화
- Gemini 선택 기능은 그대로 유지

[실패 파일만 재실행 옵션]
- GUI에서 retry_failed_only=True 전달 가능
- 실제 .error 파일 기반 필터링은 각 step에서 수행

[REV 19 추가]
- Step 6 결과판단 출력에 Sender/Receiver/신호 의미 우선 요약과 AI 판단 설명 옵션 추가

[REV 17 유지]
- API_KEY를 main.py에 평문으로 보관하지 않고 base_dir의 API_Key류 txt 파일에서 자동 로드
- API Key 파일명 대소문자/앞뒤 문구 허용 및 표시명 생성 지원
- Step 5 실행 시 API KEY 미감지이면 즉시 중단

[REV 16 유지]
- 카테고리 별 Keyword 변경 

[REV 20 유지]
- Step 6 출력 위치를 AI답변_결과 하위 판단 해설_메세지별/시간별 구조로 변경

[REV 21 변경점]
- 기존 번호 체계의 Step 7 DBC 근거/AI 판단 기능을 Step 6으로 변경
- Report는 실행 단계 번호에서 분리하고 report_generate 모듈로 호출
- DBC 근거/AI 판단 및 Report의 처리 내용과 산출물 구조는 유지

[REV 15 추가]
- Step 5 완료된 답변파일 Pass 옵션 추가
  * completed_answer_file_pass=True이면 기존 완료 AI답변 split을 검증/마킹 후 재사용
  * 누락/불완전 split만 추가 처리하고 전체 split을 병합

[REV 14 추가]
- 시간별 관련 옵션을 2개로 분리
  1) OUTPUT_TIMEORDER_TXT
     - step_1 ~ step_4 구간에서 시간별 txt 생성 여부
  2) STEP_5_ENABLE_TIME_FOLDER
     - step_5에서 시간별 폴더(AI_문의용_출력/시간별)를 실제 AI 처리할지 여부
- 기본값:
  *   * STEP_5_ENABLE_TIME_FOLDER = False


[REV 27 변경점]
- 실패파일만 재실행의 런타임 연계를 Step 5 → Step 6 → Step 7 구조로 확장
- Step 6 성공 케이스 키를 Step 7에 전달하는 내부 상태(step_6_retry_case_keys) 추가
- 후보 프롬프트는 기본 단일 파일, 90,000자 초과 시에만 예외 안전 분할로 표시 정합화

[REV 26 변경점]
- Step 4 후보 프롬프트는 기본 TC당 1개, 90,000자 초과 시에만 후보 블록 단위 _a/_b/... 예외 안전 분할
- Step 5는 단일/안전 분할을 자동 인식해 처리하고 Message:Signal 기준 병합 후 최종 AI답변 1개만 유지
- 안전 분할 입력 manifest로 현재 Step 4 후보 프롬프트와 최종 답변의 일치 여부 검증

[REV 25 변경점]
- 파이프라인을 Step 1~7 구조로 확장
- Step 4는 변경된 시그널 모음 기반 후보 프롬프트, Step 5는 관련 후보 시그널 선정
- 신규 Step 6은 관련 시그널 상세 변화 로컬 추출
- 기존 DBC 근거/입력·출력·제외 분류는 Step 7로 이동
- 그룹형 상세 TXT는 항상 생성하고 일반 split/병합 GUI 옵션은 제거

[REV 24 변경점]
- Step 4 AI 문의용 기본 분할을 2,500줄 + 160,000자 이중 기준으로 변경(구 알고리즘 이력)
- 현행 rev27 실행 경로에서는 후보 블록 기준 예외 안전 분할이 적용됨


[V2 REV 06 변경점]
- GUI/요구사항의 CH1 선택 지원과 맞도록 validate_config()의 허용 채널을 1,2,3,4로 확장
- simulated bus 재로깅 등 CH1 ASC 로그 분석 시 Main 검증 단계에서 중단되지 않도록 수정

[V2 REV 07 변경점]
- GLOBAL 특수 카테고리/전용 모드 추가
- GLOBAL 선택 시 기존 Step 1~7/Report/API 실행 요청을 무시하고 BLF→ASC 후 Global 전용 ASC 전체 디코딩만 수행
- GLOBAL은 drop_first_seconds=0, Rx+Tx 전체 분석, message_group/TC/AI 미사용

[V2 REV 08 변경점]
- GLOBAL을 카테고리 목록에서 제거하고 GUI의 별도 글로벌 사용 체크박스(global_mode)로 제어
- 일반 카테고리 선택값은 유지하되 global_mode=True이면 전용 모드로 실행

[V2 REV 09 변경점]
- 7. 블루링크, CCS 카테고리 파일명 별칭에 한글 단축어 "블루", "링크" 추가
- 블루_... / 링크_... 형식의 ASC·BLF 로그를 BLUELINK_CCS 카테고리로 처리
- 기존 블루링크/BLUELINK/CCS 별칭과 카테고리 필터 동작은 유지

[V2 REV 05 변경점]
- Step 3 ASC 프레임 방향 기본값을 자동(Rx 우선)으로 변경
  * asc_frame_direction = auto / rx / tx / both
  * auto는 기본적으로 Rx만 분석하되, drop 이후 Rx가 매우 적고 Tx가 충분히 많으면 Rx+Tx로 자동 전환
  * 사용자가 rx/tx/both를 직접 선택하면 자동 전환 없이 해당 방향으로만 분석

[V2 REV 04 변경점]
- Step 3 ASC 프레임 방향 옵션 추가
  * asc_frame_direction = rx / tx / both
  * 기본값은 기존 호환을 위해 rx
  * CANoe simulated bus 재로깅 ASC처럼 Tx만 존재하는 로그를 Step 3에서 분석 가능

[V2 REV 03 변경점]
- ADAS 카테고리 키워드에 "보조" 별칭 추가
- 보조_042_... 형태 ASC 파일을 6. 운전자 보조 카테고리로 인식

[V2 REV 02 변경점]
- 정상 종료 후 사용자 비표시 후보목록/마커폴더/AI답변 JSON 정리

[V2 MAIN REV 12 변경점]
- GPT 기본 모델을 gpt-5.6-terra로 변경
- GPT_MODEL_OPTIONS=(gpt-5.6-terra, gpt-5.4, gpt-5.2) 허용 목록 추가
- GUI override 보정/validate_config가 동일 허용 목록을 사용하도록 통일

[V2 MAIN REV 13 변경점]
- Step 2 AI 후보 보강 옵션(step_2_ai_enhancement) 추가, 기본 False
- 옵션 ON일 때 Step 2가 TestCase Excel/API Key를 사용하므로 Main 사전 검증 조건 확장
- 옵션 OFF는 기존 Step 2 실행 경로에 영향을 주지 않음
- GLOBAL 모드에서는 Step 2 AI 보강을 강제로 False 처리

[V2 MAIN REV 11 변경점]
- 과거 CH→CAN 설정 키·PipelineConfig 필드·외부 override 경로를 완전히 제거
- 구 설정 JSON에 rename_asc_channel_to_can이 남아 있어도 읽거나 실행하지 않음
- 로그 분석은 ASC/BLF 본문의 CAN1~CAN4 번호만 직접 사용
- PIPELINE_GUI_CONFIG_JSON이 없거나 파싱되지 않으면 경고 후 Main 기본 설정으로 계속 실행하는 기존 정책 유지

[V2 MAIN REV 10 변경점]
- VN1640A 물리 채널 매핑을 제거하고 ASC/BLF 로그의 CAN1~CAN4 번호를 직접 DBC 키로 사용
- can_config 형식을 {CANx: {enabled, dbc}}로 변경하고 비활성 CAN은 분석 대상에서 제외
- CAN1~CAN4 지원 및 CANx당 단일 DBC만 허용
- 유효하게 파싱된 CAN 설정의 구조 오류는 즉시 중단하고 복수 DBC/잘못된 CAN 매핑으로 fallback하지 않음
- 구버전 can_config의 channel 값은 무시하고 CAN 행의 DBC/활성 상태만 호환 복원
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import traceback
import re
import importlib
import importlib.util
import sys
import os
import json

# =========================================================
# [추가] 실행 후 __pycache__ 자동 삭제용
# =========================================================
import shutil
import atexit


def remove_pycache(base_dir: Path) -> None:
    """
    base_dir(프로젝트 폴더) 하위에 생성된 모든 __pycache__ 폴더를 삭제.
    - 정상 종료/예외 종료 모두에서 실행되도록 atexit + finally로 호출 가능.
    """
    try:
        for d in base_dir.rglob("__pycache__"):
            shutil.rmtree(d, ignore_errors=True)
    except Exception:
        pass


# =========================================================
# [0] 실행 단계 선택
# =========================================================
RUN_STEP_1_BLF_TO_ASC_ADD_RENAME = True
RUN_STEP_2_EXPORT_MESSAGE_GROUP = True
# Step 2 AI 후보 보강: 사용자가 명시적으로 켠 실행에서만 사용 (기본 OFF)
STEP_2_AI_ENHANCEMENT = False
RUN_STEP_3_ASC_TO_TXT = True
RUN_STEP_4_TXT_TO_AI_REQUEST = True
RUN_STEP_5_CALL_AI = True
RUN_STEP_6_EXTRACT_DETAILS = True
RUN_STEP_7_CLASSIFY_SIGNALS = True
RUN_REPORT_GENERATE = False


# =========================================================
# [0-1] 실패 파일만 재실행 옵션
# =========================================================
RETRY_FAILED_ONLY = False


# =========================================================
# [1] 카테고리 선택
# =========================================================
ACTIVE_CATEGORY = "CONVENIENCE"


# =========================================================
# [1-1] 카테고리별 설정
# =========================================================
DEFAULT_EXCLUDE_KEYWORDS = ["TP", "DEV"]

CATEGORIES = {
    "SEAT": {
        "prefix": "1. 시트 및 안전 장치",
        "keywords": ["시트"],
        "include_keywords": [
            "ATS", "BDC", "CTS", "HU", "H_U_MM_FD", "PSS", "PSU", "SAU", "SHVU",
        ],
        "include_message_name_keywords": [],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "CLUSTER": {
        "prefix": "2. 클러스터",
        "keywords": ["클러스터", "클러"],
        "include_keywords": [
            "ADP", "AMP", "ATCU", "BLTN_CAM", "CLU", "CLU_MM_FD", "DATC", "EMS",
            "EXT_AMP", "GW_BDC_FD", "HU", "HUD", "H_U_MM_FD", "ILCU", "MFSW",
            "PDC", "PSS", "PSU", "SAU", "SBCM", "SHVU", "SWRC", "VPC", "WHL_01" 
        ],
        "include_message_name_keywords": [
            "CLU", "DATC", "EMS","ILCU", "MFSW", "PSS", "SBCM", "SWRC", "VPC", "WHL_01"
        ],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "CONVENIENCE": {
        "prefix": "3. 편의 장치",
        "keywords": ["편의", "편의장치"],
        "include_keywords": [
            "AMP", "AST", "ATCU", "BDC", "BLTN", "CGW", "CLU", "DATC",
            "DRV", "EMS", "ETCS", "FCS", "FPM", "HU", "ILCU", "IRCU", "LKAS",
            "MFSW", "MLM", "OHCL", "PDC", "PSS", "PSU", "SAL", "SBCM", "SBW",
            "SCM", "TCU", "USM", "UWB", "VPC",
        ],
        "include_message_name_keywords": [
            "SBW", "UWB", "TCU", "ETCS"
        ],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "INFOTAINMENT": {
        "prefix": "4. 인포테인먼트",
        "keywords": ["인포", "인포테인먼트"],
        "include_keywords": [
            "ADP", "AMP", "ATCU", "BLTN_CAM", "CLU", "CLU_MM_FD", "DATC",
            "EXT_AMP", "GW_BDC_FD", "HU", "HUD", "H_U_MM_FD", "ILCU", "MFSW",
            "PDC", "PSS", "PSU", "SAU", "SBCM", "SHVU", "SWRC", "VPC",
        ],
        "include_message_name_keywords": [
            "CLU", "DATC", "ILCU", "MFSW", "PSS", "SBCM", "SWRC", "VPC"
        ],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "DRIVE": {
        "prefix": "5. 시동 및 주행",
        "keywords": ['시동', '주행'],
        "include_keywords": [
            "ABS", "ABS_ESC", "ADP", "AMP", "ATS", "AWD", "BDC", "BLTN", "BMS", "CCU", "CGW",
            "CLU", "CMR", "CV", "DATC", "EMS", "ESC", "ETCS", "EPB", "FCS", "FCU",
            "IC", "ILCU", "IRCU", "MCU", "MFSW", "MM", "OHCL", "PDC", "PRK",
            "PSU", "PTGM", "ROA", "SAL", "SAU", "SBCM", "SBR", "SBW", "SCM", "SHVU", "SWRC",
            "TCU", "VCMS", "VCU", "VPC", "WHL"
        ],
        "include_message_name_keywords": [
            "ABS_ESC", "ACT", "AWD", "BTN", "CLU", "CMD", "DATC", "EPB", "FB", "FDBK", "ILCU",
            "MFSW", "MODE", "PSS", "REQ", "SBCM", "SBR", "SBW", "SET", "STA", "STAT",
            "STATE", "STATUS", "SW", "SWRC", "VAL", "VALUE", "VPC", "WHL"
        ],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "ADAS": {
        "prefix": "6. 운전자 보조",
        "keywords": ['운전자', '운전자보조', 'ADAS', '보조'],
        "include_keywords": [
            "ABS", "ADP", "ADAS_DRV", "ADAS_PRK", "AMP", "ATS", "BDC", "BMS", "CCU", "CGW", "CLU",
            "CMR", "CV", "DATC", "EMS", "ESC", "FCU", "FR_CMR", "IC", "MCU", "MM", "PRK",
            "ROA", "RR_C_RDR", "SAL", "TCU", "VCMS", "VPC"
        ],
        "include_message_name_keywords": [
            "ACT", "ADAS_DRV", "ADAS_PRK", "BTN", "CMD", "FB", "FDBK", "FR_CMR", "MODE", "REQ", "SET", "STA",
            "STAT", "STATE", "STATUS", "SW", "VAL", "VALUE",
            "CLU", "DATC", "ILCU", "MFSW", "PSS", "SBCM", "SWRC", "VPC", "RR_C_RDR"
        ],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "BLUELINK_CCS": {
        "prefix": "7. 블루링크, CCS",
        "keywords": ['블루링크', '블루', '링크', 'BLUELINK', 'CCS'],
        "include_keywords": [
            "ABS", "ADP", "AMP", "ATS", "BDC", "BLTN", "BMS", "CCU", "CGW",
            "CLU", "CMR", "CV", "DATC", "EMS", "ESC", "ETCS", "FCS", "FCU",
            "IC", "ILCU", "IRCU", "MCU", "MM", "OHCL", "PDC", "PRK", "PSU",
            "PTGM", "ROA", "SAL", "SAU", "SBCM", "SCM", "SHVU", "SWRC", "TCU",
            "VCMS", "VPC"
        ],
        "include_message_name_keywords": [
            "ACT", "BTN", "CMD", "FB", "FBK", "FDBK", "MODE", "REQ", "SET",
            "STA", "STAT", "STATE", "STATUS", "SW", "VAL", "VALUE",
            "CLU", "DATC", "ILCU", "MFSW", "PSS", "SBCM", "SWRC", "VPC"
        ],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "EV": {
        "prefix": "8. 환경차",
        "keywords": ['환경차', 'EV'],
        "include_keywords": [
            "ADP", "AMP", "ATS", "BDC", "BMS", "CCU", "CGW", "CLU", "CMR",
            "CV", "DATC", "EMS", "ESC", "ETCS", "FCU", "IC", "ILCU", "IRCU",
            "MCU", "MM", "PDC", "PRK", "PTGM", "SBCM", "SWRC", "TCU", "VCMS",
            "VCU", "VPC"
        ],
        "include_message_name_keywords": [
            "ACT", "BTN", "CMD", "FB", "FDBK", "MODE", "REQ", "SET", "STA",
            "STAT", "STATE", "STATUS", "SW", "VAL", "VALUE",
            "CLU", "DATC", "ILCU", "MFSW", "PSS", "SBCM", "SWRC", "VPC"
        ],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "SCENARIO": {
        "prefix": "9. 시나리오 TC",
        "keywords": ['시나리오', 'SCENARIO'],
        "include_keywords": [
            "ADP", "AMP", "ATS", "BMS", "CCU", "CGW", "CLU", "CV", "EMS",
            "ESC", "ETCS", "FCU", "IC", "MCU", "MM", "TCU", "VCMS", "VPC"
        ],
        "include_message_name_keywords": [
            "ACT", "BTN", "CMD", "FB", "FBK", "FDBK", "MODE", "REQ", "SET",
            "STA", "STAT", "STATE", "STATUS", "SW", "VAL", "VALUE",
            "CLU", "DATC", "ILCU", "MFSW", "PSS", "SBCM", "SWRC", "VPC"
        ],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "AVP": {
        "prefix": "10. AVP_과거차문제",
        "keywords": ['AVP', '과거차문제'],
        "include_keywords": [
            "ABS", "ADP", "AMP", "ATS", "BDC", "BLTN", "BMS", "CCU", "CGW",
            "CLU", "CMR", "CV", "DATC", "EMS", "ESC", "ETCS", "FCS", "FCU",
            "IC", "ILCU", "IRCU", "MCU", "MM", "OHCL", "PDC", "PRK", "PSU",
            "PTGM", "ROA", "SAL", "SAU", "SBCM", "SCM", "SHVU", "SWRC", "TCU",
            "VCMS", "VPC"
        ],
        "include_message_name_keywords": [
            "ACT", "BTN", "CMD", "FB", "FBK", "FDBK", "MODE", "REQ", "SET",
            "STA", "STAT", "STATE", "STATUS", "SW", "VAL", "VALUE",
            "CLU", "DATC", "ILCU", "MFSW", "PSS", "SBCM", "SWRC", "VPC"
        ],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "NEWSPEC": {
        "prefix": "11. 신사양 임시 적용 TC",
        "keywords": ['신사양', '임시'],
        "include_keywords": [
            "ADP", "AMP", "CCU", "CGW", "CLU", "CMR", "CV", "DATC", "ETCS",
            "IC", "MM", "PRK"
        ],
        "include_message_name_keywords": [
            "ACT", "BTN", "CMD", "FB", "FBK", "FDBK", "MODE", "REQ", "SET",
            "STA", "STAT", "STATE", "STATUS", "SW", "VAL", "VALUE",
            "CLU", "DATC", "ILCU", "MFSW", "PSS", "SBCM", "SWRC", "VPC"
        ],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "CONNECT": {
        "prefix": "12. Connect UX 사양서 기반 TC 검토 초안",
        "keywords": ['커넥트', 'UX', 'Connect', 'connect'],
        # Connect UX는 HU 중심 UX뿐 아니라 ADAS/공조/시트/도어/EV/주행/주차/클러스터를
        # 한 TC 묶음에서 폭넓게 다루므로 기존 1~11 카테고리에서 관련 sender 토큰을 선별 통합한다.
        "include_keywords": [
            "ABS", "ADP", "AMP", "AST", "ATCU", "ATS", "BDC", "BLTN",
            "BMS", "CCU", "CGW", "CLU", "CMR", "CV", "DATC", "DRV",
            "EMS", "EPB", "ESC", "ETCS", "FCS", "FCU", "FPM", "HU",
            "HUD", "H_U_MM_FD", "IC", "ILCU", "IRCU", "LKAS", "MCU",
            "MFSW", "MLM", "MM", "OHCL", "PDC", "PRK", "PSS", "PSU",
            "PTGM", "SAL", "SAU", "SBCM", "SBR", "SBW", "SCM", "SHVU",
            "SWRC", "TCU", "USM", "UWB", "VCMS", "VCU", "VPC", "WHL",
            "RR_C_RDR"
        ],
        "include_message_name_keywords": [
            "ABS_ESC", "ACT", "ADAS_DRV", "ADAS_PRK", "BTN", "CLU", "CMD",
            "DATC", "EPB", "ETCS", "FB", "FBK", "FDBK", "FR_CMR", "ILCU",
            "MFSW", "MODE", "PSS", "REQ", "RR_C_RDR", "SBCM", "SBR", "SBW",
            "SET", "STA", "STAT", "STATE", "STATUS", "SW", "SWRC", "TCU",
            "UWB", "VAL", "VALUE", "VPC", "WHL"
        ],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
}


# =========================================================
# [2] DBC 파일명 설정
# - 기본값(단독 실행 시)
# - GUI가 can_config / dbc_name_by_ch 를 넘기면 override 됨
# =========================================================
DBC_NAME_BY_CH = {}  # GUI 자동감지 또는 직접 선택으로 명시 설정

DBC_FILES_STEP2 = list(dict.fromkeys(DBC_NAME_BY_CH.values()))

# =========================================================
# [3] 기타 분석 옵션
# =========================================================
DROP_FIRST_SECONDS = 8.0

# Step 3 ASC 분석 프레임 방향
# - "auto" : 기본은 Rx로 분석하되, drop 이후 Rx가 매우 적고 Tx가 충분히 많으면 Rx+Tx로 자동 전환
# - "rx"   : Rx만 강제 분석
# - "tx"   : CANoe simulated bus 재로깅처럼 Tx로 찍힌 로그만 강제 분석
# - "both" : Rx+Tx 전체 강제 분석
ASC_FRAME_DIRECTION = "auto"

IGNORE_NAME_PATTERNS = [
    r"crc",
    r"alv",
]

CHANGE_THRESHOLD = 100

THRESHOLD_EXCEPT_SUBSTRINGS = [
    "spd",
    "speed",
    "veh",
    "vss",
    "kph",
    "mph",
    "whl",
    "wheel",
    "cluster",
]

SKIP_HIGH_FREQUENCY = True

ENABLE_INFO_ONLY_IGNORE = False

INFO_ONLY_IGNORE_PATTERNS = [
    r"\binfo\b",
    r"^info_",
    r"_info$",
]

CATEGORY_EXTRA_IGNORE_PATTERNS = {
    "SEAT": [],
    "CLUSTER": [],
    "CONVENIENCE": [],

    "INFOTAINMENT": [],
    "DRIVE": [],
    "ADAS": [],
    "BLUELINK_CCS": [],
    "EV": [],
    "SCENARIO": [],
    "AVP": [],
    "NEWSPEC": [],
    "CONNECT": [],
    "GLOBAL": [],
}

# =========================================================
# [3-0] GLOBAL 전용 옵션
# =========================================================
GLOBAL_CATEGORY_KEY = "GLOBAL"  # 저장 설정/구버전 호환용 토큰, 일반 CATEGORIES에는 포함하지 않음
GLOBAL_MODE_ENABLED = False
GLOBAL_EXCLUDE_CRC_ALV = True
GLOBAL_IGNORE_NAME_PATTERNS = [
    r"crc",
    r"alv",
]
GLOBAL_SPLIT_MAX_LINES = 100000
GLOBAL_SPLIT_MAX_CHARS = 10_000_000
GLOBAL_OUTPUT_DIR_NAME = "분석된 txt 파일"


# =========================================================
# [3-1] Step 3 산출물 3종은 항상 생성
# - 그룹형 상세 / 시간순 상세 / 변경된 시그널 모음은 선택 옵션이 아님
# - 아래 옵션은 Step 6의 시간별 상세 복원 여부만 제어
# =========================================================
STEP_5_ENABLE_TIME_FOLDER = False


# =========================================================
# [4] message_group 추출 옵션
# =========================================================
INCLUDE_IGNORE_CASE = False
INCLUDE_MESSAGE_NAME_IGNORE_CASE = False


# =========================================================
# [5] AI 문의용 TXT 생성 옵션
# =========================================================
EXCEL_GLOB = "TestCase_모음*.xls*"
OUTPUT_DIR = "AI_문의용_출력"
OUTPUT_DIR_MSG = "메세지별"
OUTPUT_DIR_TIME = "시간별"
DBC_DIR = "."
DEDUP_WINDOW_SEC = 0.2
SPLIT_LINES_THRESHOLD = 2500
SPLIT_LINES_PER_FILE = 2500
SPLIT_CHARS_THRESHOLD = 160000
SPLIT_CHARS_PER_FILE = 160000

# REV 26: 변경 시그널 후보 프롬프트의 예외 안전 분할 기준
CANDIDATE_PROMPT_SAFE_SPLIT_CHARS = 90000
CANDIDATE_PROMPT_MAX_SPLIT_PARTS_WARNING = 10

INTENTIONAL_BLANK_TOKEN = "__BLANK__"
TC_NO_COLUMN_INDEX = 0
TC_CLASS_COLUMN_INDEX = 1
TC_COLUMN_INDEX = 2
START_ROW_EXCEL = 2


# =========================================================
# [6] AI 호출 옵션
# =========================================================
AI_PROVIDER = "gpt"

GPT_MODEL = "gpt-5.6-terra"
GPT_MODEL_OPTIONS = ("gpt-5.6-terra", "gpt-5.4", "gpt-5.2")
API_VERSION = "2025-04-01-preview"

GEMINI_MODEL = "gemini-3.1-pro-preview"
GEMINI_STREAM_OPTION = "generateContent"

API_KEY = ""  # REV17: 실제 API Key는 base_dir의 API_Key류 txt 파일에서 자동 로드
BASE_URL = "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3"
PROJECT_ID = ""

INPUT_ROOT_DIR_NAME = "AI_문의용_출력"
SUBFOLDERS = ["메세지별", "시간별"]
OUTPUT_ROOT_DIR_NAME = "AI답변_결과"

FILE_PATTERN = "AI문의용_*.txt"
SKIP_IF_OUTPUT_EXISTS = True
COMPLETED_ANSWER_FILE_PASS = False
MAX_RETRY = 3
SLEEP_BETWEEN_CALLS = 1.0
RETRY_WAIT_SECONDS = 2.0

USE_SYSTEM_MESSAGE = True
SYSTEM_MESSAGE = (
    "사용자가 제공한 형식과 지시사항을 엄격히 따르고, "
    "불필요한 설명 없이 결과만 출력하세요."
)


# =========================================================
# [6-1] step_5 분할 결과 병합 옵션
# =========================================================
MERGE_SPLIT_ANSWER_FILES = True
KEEP_SPLIT_ANSWER_FILES_AFTER_MERGE = False


# =========================================================
# [6-2] Report 생성 옵션
# =========================================================
REPORT_OUTPUT_DIR_NAME = "Report_결과"
REPORT_TITLE = "AI 로그 분석 결과 레포트"
REPORT_SAMPLE_IF_EMPTY = True

# =========================================================
# [6-3] Step 6/7 옵션
# =========================================================
STEP_6_OUTPUT_DIR_NAME = "AI답변_결과"
STEP_6_ENABLE_TIME_DETAIL = False
STEP_7_OUTPUT_DIR_NAME = "AI답변_결과"
STEP_7_ENABLE_AI_JUDGEMENT = True
STEP_7_AI_MAX_RETRY = 2
STEP_7_LOCAL_CONFIDENCE_THRESHOLD = 0.78
STEP_7_LOCAL_SCORE_MARGIN = 1.25


# =========================================================
# [7] step 모듈 파일명 (base name만 적으면 rev 자동 선택)
# =========================================================
STEP_1_MODULE = "Signal_Export_V2_Step_1_BLF_to_ASC"
STEP_2_MODULE = "Signal_Export_V2_Step_2_Message_Group"
STEP_3_MODULE = "Signal_Export_V2_Step_3_ASC_to_TXT"
STEP_4_MODULE = "Signal_Export_V2_Step_4_AI_Request"
STEP_5_MODULE = "Signal_Export_V2_Step_5_AI_Signal_Select"
STEP_6_MODULE = "Signal_Export_V2_Step_6_Signal_Detail"
STEP_7_MODULE = "Signal_Export_V2_Step_7_Signal_Classification"
GLOBAL_STEP_3_MODULE = "Signal_Export_V2_Step_3_Global_ASC_to_TXT"
REPORT_MODULE = "Signal_Export_V2_Report"


# =========================================================
# [7-1] Rev 자동 선택 로더
# =========================================================
_REV_RE = re.compile(
    r"^(?P<base>.+?)"
    r"(?P<sep>[_\-.])rev(?P<sep2>[_\-.])?(?P<num>\d+)$",
    re.IGNORECASE
)


def _find_latest_rev_module_file(base_dir: Path, base_module: str) -> Optional[Tuple[Path, int]]:
    best: Optional[Tuple[Path, int]] = None

    for p in base_dir.glob(f"{base_module}*.py"):
        stem = p.stem
        m = _REV_RE.match(stem)
        if not m:
            continue
        if m.group("base") != base_module:
            continue

        rev_num = int(m.group("num"))
        if best is None or rev_num > best[1]:
            best = (p, rev_num)

    return best


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


def resolve_step_module(base_dir: Path, base_module_name: str):
    search_dirs = []
    for d in (Path(base_dir), Path(__file__).resolve().parent):
        if d not in search_dirs:
            search_dirs.append(d)

    for search_dir in search_dirs:
        best = _find_latest_rev_module_file(search_dir, base_module_name)
        if best is not None:
            module_file, rev_num = best
            print(
                f"[INFO] Using REV module for '{base_module_name}': "
                f"{module_file.name} (rev={rev_num}, dir={module_file.parent})"
            )
            return _load_module_by_file(module_file, unique_name_hint=base_module_name)

    print(f"[INFO] Using BASE module for '{base_module_name}': {base_module_name}.py")
    return importlib.import_module(base_module_name)


# =========================================================
# Dataclass
# =========================================================
@dataclass
class PipelineConfig:
    base_dir: Path
    active_category: str
    category_prefix: str
    category_keywords: List[str]

    run_step_1: bool = True
    run_step_2: bool = True
    # 기존 Rule 기반 Step 2에 AI 후보를 추가하는 선택 옵션. 기본 OFF.
    step_2_ai_enhancement: bool = False
    run_step_3: bool = True
    run_step_4: bool = True
    run_step_5: bool = True
    run_step_6: bool = False
    run_step_7: bool = False
    run_step_report: bool = False

    retry_failed_only: bool = False

    # 실패파일 재실행 시 Step 5가 실제로 선정한 케이스를 Step 6에 전달하는 런타임 목록.
    # GUI 설정값이 아니라 동일 파이프라인 실행 중 Step 5 -> Step 6 연계를 위한 내부 상태이다.
    step_5_retry_case_keys: List[str] = field(default_factory=list)

    # 실패파일 재실행 시 Step 6에서 실제 정상 갱신된 케이스를 Step 7에 전달하는 런타임 목록.
    # GUI 설정값이 아니라 동일 파이프라인 실행 중 Step 6 -> Step 7 연계를 위한 내부 상태이다.
    step_6_retry_case_keys: List[str] = field(default_factory=list)

    include_keywords: List[str] = field(default_factory=list)
    include_message_name_keywords: List[str] = field(default_factory=list)
    exclude_keywords: List[str] = field(default_factory=list)
    include_ignore_case: bool = False
    include_message_name_ignore_case: bool = False
    dbc_files_step2: List[str] = field(default_factory=list)
    output_txt_step2: str = "message_group.txt"

    # Step 2 AI 후보 보강 안전 분할/컨텍스트 기본값
    step_2_ai_message_chunk_chars: int = 50000
    step_2_ai_signal_chunk_chars: int = 60000
    step_2_ai_signals_per_part: int = 200
    step_2_ai_tc_context_max_chars: int = 60000

    # GUI 로그 CAN 설정 원본
    can_config: Dict[str, Dict[str, object]] = field(default_factory=dict)

    # 실제 step_3 해석용 로그 채널(CAN 번호) -> DBC 최종값
    dbc_name_by_ch: Dict[int, str] = field(default_factory=dict)

    drop_first_seconds: float = 8.0
    asc_frame_direction: str = "auto"
    ignore_name_patterns: List[str] = field(default_factory=list)
    change_threshold: int = 100
    threshold_except_substrings: List[str] = field(default_factory=list)
    skip_high_frequency: bool = True
    enable_info_only_ignore: bool = False
    info_only_ignore_patterns: List[str] = field(default_factory=list)
    category_extra_ignore_patterns: Dict[str, List[str]] = field(default_factory=dict)

    excel_glob: str = "TestCase_모음*.xls*"
    output_dir: str = "AI_문의용_출력"
    output_dir_msg: str = "메세지별"
    output_dir_time: str = "시간별"
    dbc_dir: str = "."
    dedup_window_sec: float = 0.2
    split_lines_threshold: int = 2500
    split_lines_per_file: int = 2500
    split_chars_threshold: int = 160000
    split_chars_per_file: int = 160000
    candidate_prompt_safe_split_chars: int = 90000
    candidate_prompt_max_split_parts_warning: int = 10
    intentional_blank_token: str = "__BLANK__"
    tc_no_column_index: int = 0
    tc_class_column_index: int = 1
    tc_column_index: int = 2
    start_row_excel: int = 2

    ai_provider: str = "gpt"
    gpt_model: str = GPT_MODEL
    gemini_model: str = "gemini-3.1-pro-preview"
    gemini_stream_option: str = "generateContent"
    api_key: str = ""
    api_key_source_file: str = ""
    api_key_display_name: str = ""
    base_url: str = ""
    project_id: str = ""
    api_version: str = "2025-04-01-preview"
    input_root_dir_name: str = "AI_문의용_출력"
    subfolders: List[str] = field(default_factory=lambda: ["메세지별", "시간별"])
    output_root_dir_name: str = "AI답변_결과"
    file_pattern: str = "AI문의용_*.txt"
    skip_if_output_exists: bool = True
    completed_answer_file_pass: bool = False
    max_retry: int = 3
    sleep_between_calls: float = 1.0
    retry_wait_seconds: float = 2.0
    use_system_message: bool = True
    system_message: str = ""

    merge_split_answer_files: bool = True
    keep_split_answer_files_after_merge: bool = True

    # step_5 전용 시간별 처리 옵션
    step_5_enable_time_folder: bool = False

    report_output_dir_name: str = "Report_결과"
    report_title: str = "AI 로그 분석 결과 레포트"
    report_sample_if_empty: bool = True

    step_6_output_dir_name: str = "AI답변_결과"
    step_6_enable_time_detail: bool = False
    step_7_output_dir_name: str = "AI답변_결과"
    step_7_enable_ai_judgement: bool = True
    step_7_ai_max_retry: int = 2
    step_7_local_confidence_threshold: float = 0.78
    step_7_local_score_margin: float = 1.25
    # 구 Step 6 분류 함수 호환용 alias
    step_6_enable_ai_judgement: bool = True
    step_6_ai_max_retry: int = 2

    # GLOBAL 특수 모드 옵션
    global_mode: bool = False
    global_exclude_crc_alv: bool = True
    global_ignore_name_patterns: List[str] = field(default_factory=lambda: [r"crc", r"alv"])
    global_split_max_lines: int = 100000
    global_split_max_chars: int = 10_000_000
    global_output_dir_name: str = "분석된 txt 파일"

def build_default_can_config_from_dbc_name_by_ch(dbc_name_by_ch: Dict[int, str]) -> Dict[str, Dict[str, object]]:
    """로그 CAN 번호 기반 기본 설정을 GUI 호환 can_config 형태로 변환한다."""
    result: Dict[str, Dict[str, object]] = {}
    for logical_channel in range(1, 5):
        dbc = dbc_name_by_ch.get(logical_channel)
        result[f"CAN{logical_channel}"] = {
            "enabled": bool(dbc),
            "dbc": str(dbc) if dbc else None,
        }
    return result


def normalize_can_config(raw_can_config) -> Dict[str, Dict[str, object]]:
    """
    GUI 입력 can_config를 로그 CAN 기준으로 정규화한다.

    최신 형식:
      {"CAN1": {"enabled": True, "dbc": "B1.dbc"}, ...}

    구버전 호환:
    - enabled가 없으면 해당 CAN 행에 DBC가 지정되어 있는지를 기준으로 활성 상태를 복원한다.
    - 과거의 physical channel 값은 더 이상 해석하지 않는다.
    """
    out: Dict[str, Dict[str, object]] = {}
    if not isinstance(raw_can_config, dict):
        return out

    for can_name in ("CAN1", "CAN2", "CAN3", "CAN4"):
        item = raw_can_config.get(can_name, {})
        if not isinstance(item, dict):
            raise ValueError(f"{can_name}: CAN 설정은 객체 1개여야 합니다.")

        raw_dbc = item.get("dbc")
        if isinstance(raw_dbc, (list, tuple, set, dict)):
            raise ValueError(f"{can_name}: DBC는 1개만 지정할 수 있습니다.")

        dbc = str(raw_dbc).strip() if raw_dbc is not None else None
        if dbc in ("", "N/A", "n/a", "None", "none"):
            dbc = None

        if "enabled" in item:
            enabled = bool(item.get("enabled"))
        else:
            # 구버전 설정 호환: 채널 번호는 무시하고 DBC 존재 여부로 활성 상태만 복원한다.
            enabled = bool(dbc)

        out[can_name] = {
            "enabled": enabled,
            "dbc": dbc,
        }

    return out


def build_dbc_name_by_ch_from_can_config(can_config: Dict[str, Dict[str, object]]) -> Dict[int, str]:
    """can_config -> 로그 채널 번호(CAN1=1 ... CAN4=4)별 단일 DBC 매핑을 생성한다."""
    result: Dict[int, str] = {}

    for logical_channel, can_name in enumerate(("CAN1", "CAN2", "CAN3", "CAN4"), start=1):
        item = can_config.get(can_name, {})
        enabled = bool(item.get("enabled", False))
        dbc = item.get("dbc")

        if not enabled or not dbc:
            continue

        if isinstance(dbc, (list, tuple, set, dict)):
            raise ValueError(f"{can_name}: DBC는 1개만 지정할 수 있습니다.")

        result[logical_channel] = str(dbc)

    return result


# =========================================================
# [6-0] API Key 외부 파일 자동 탐색/로드
# =========================================================
_API_KEY_FILE_MARKER_RE = re.compile(r"api[\s_\-]*key", re.IGNORECASE)
_API_KEY_ASSIGN_RE = re.compile(r"^(?:API[_\s\-]*KEY|api[_\s\-]*key)\s*=\s*(?P<value>.+)$", re.IGNORECASE)
_API_KEY_ALLOWED_SUFFIXES = {".txt", ""}


def _is_probable_api_key_file(path: Path) -> bool:
    """
    base_dir에 있는 API_Key류 파일인지 판단한다.
    - xx_API_Key_yy.txt / aa_API_KEY_bb.txt / api_key_yy.txt / apikey_xxx.txt / APIKEY 모두 허용
    - txt 또는 확장자 없는 파일만 대상으로 하여 일반 코드/엑셀 파일 오탐을 줄인다.
    """
    if not path.is_file():
        return False
    if path.suffix.lower() not in _API_KEY_ALLOWED_SUFFIXES:
        return False
    stem = path.stem or path.name
    compact = re.sub(r"[^a-z0-9]+", "", stem.lower())
    return "apikey" in compact


def make_api_key_display_name(api_key_file: Path | str | None) -> str:
    """
    API Key 파일명에서 GUI 표시용 별칭을 생성한다.
    예)
      260611_API_Key_1차 Key.txt -> 260611_1차 Key
      xx_API_Key_yy.txt          -> API 입력됨
      APIKEY                     -> API 입력됨
    """
    if api_key_file is None:
        return "API KEY 미감지"

    stem = Path(api_key_file).stem or Path(api_key_file).name
    m = _API_KEY_FILE_MARKER_RE.search(stem)
    if m:
        left = stem[:m.start()]
        right = stem[m.end():]
    else:
        compact = re.sub(r"[^a-z0-9]+", "", stem.lower())
        idx = compact.find("apikey")
        if idx < 0:
            return "API 입력됨"
        left = ""
        right = ""

    label = "_".join(x.strip(" _-\t") for x in (left, right) if x.strip(" _-\t"))
    # 앞/뒤 구분자는 _로 정리하되, 사용자가 뒤쪽에 적은 "1차 Key" 같은 설명 내부 공백은 보존한다.
    label = re.sub(r"[_\-]+", "_", label).strip("_").strip()

    # xx/yy/aa/bb 같은 의미 없는 자리표시자만 남으면 실제 키 내용은 숨기고 입력 여부만 표시
    compact_label = re.sub(r"[\s_\-]+", "", label.lower())
    if not compact_label or re.fullmatch(r"[xyab]+", compact_label):
        return "API 입력됨"

    return label


def _read_api_key_text_file(path: Path) -> str:
    text = ""
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            text = path.read_text(encoding=enc, errors="replace")
            break
        except Exception:
            continue

    for raw_line in text.splitlines():
        line = (raw_line or "").strip()
        if not line or line.startswith("#"):
            continue

        m = _API_KEY_ASSIGN_RE.match(line)
        if m:
            line = m.group("value").strip()

        line = line.strip().strip('"').strip("'").strip()
        if line:
            return line

    return ""


def resolve_external_api_key(base_dir: Path | str) -> Tuple[str, Optional[Path], str]:
    """
    base_dir에서 API_Key류 txt 파일을 찾아 (api_key, path, display_name)을 반환한다.
    여러 파일이 있으면 최신 수정 파일을 우선 사용한다.
    """
    base = Path(base_dir).expanduser().resolve()
    if not base.exists() or not base.is_dir():
        return "", None, "API KEY 미감지"

    candidates = [p for p in base.iterdir() if _is_probable_api_key_file(p)]
    candidates.sort(key=lambda p: (p.stat().st_mtime if p.exists() else 0, p.name.lower()), reverse=True)

    for p in candidates:
        key = _read_api_key_text_file(p)
        if key:
            return key, p, make_api_key_display_name(p)

    return "", None, "API KEY 미감지"


def apply_api_key_from_file(config: PipelineConfig) -> PipelineConfig:
    """config.api_key가 비어 있으면 base_dir의 API_Key류 파일에서 자동 로드한다."""
    if str(getattr(config, "api_key", "") or "").strip():
        config.api_key_source_file = "직접 설정"
        config.api_key_display_name = "API 입력됨"
        return config

    api_key, api_path, display = resolve_external_api_key(config.base_dir)
    config.api_key = api_key
    config.api_key_source_file = str(api_path) if api_path is not None else ""
    config.api_key_display_name = display

    if api_key:
        print(f"[OK] API Key 파일 감지: {api_path.name if api_path else ''} / 표시명: {display}")
    elif getattr(config, "run_step_5", False) or (getattr(config, "run_step_7", False) and getattr(config, "step_7_enable_ai_judgement", True)):
        print("[WARN] API KEY가 감지되지 않았습니다.")

    return config

def build_config() -> PipelineConfig:
    selected = CATEGORIES[ACTIVE_CATEGORY]
    suffix = ACTIVE_CATEGORY.strip().lower()
    output_txt_step2 = f"message_group_{suffix}.txt"

    default_can_config = build_default_can_config_from_dbc_name_by_ch(DBC_NAME_BY_CH)

    return PipelineConfig(
        base_dir=Path(__file__).resolve().parent,
        active_category=ACTIVE_CATEGORY,
        category_prefix=selected["prefix"],
        category_keywords=selected["keywords"],

        run_step_1=RUN_STEP_1_BLF_TO_ASC_ADD_RENAME,
        run_step_2=RUN_STEP_2_EXPORT_MESSAGE_GROUP,
        step_2_ai_enhancement=STEP_2_AI_ENHANCEMENT,
        run_step_3=RUN_STEP_3_ASC_TO_TXT,
        run_step_4=RUN_STEP_4_TXT_TO_AI_REQUEST,
        run_step_5=RUN_STEP_5_CALL_AI,
        run_step_6=RUN_STEP_6_EXTRACT_DETAILS,
        run_step_7=RUN_STEP_7_CLASSIFY_SIGNALS,
        run_step_report=RUN_REPORT_GENERATE,

        retry_failed_only=RETRY_FAILED_ONLY,

        include_keywords=selected.get("include_keywords", []),
        include_message_name_keywords=selected.get("include_message_name_keywords", []),
        exclude_keywords=selected.get("exclude_keywords", DEFAULT_EXCLUDE_KEYWORDS),
        include_ignore_case=INCLUDE_IGNORE_CASE,
        include_message_name_ignore_case=INCLUDE_MESSAGE_NAME_IGNORE_CASE,
        dbc_files_step2=DBC_FILES_STEP2,
        output_txt_step2=output_txt_step2,

        can_config=default_can_config,
        dbc_name_by_ch=DBC_NAME_BY_CH.copy(),

        drop_first_seconds=DROP_FIRST_SECONDS,
        asc_frame_direction=ASC_FRAME_DIRECTION,
        ignore_name_patterns=IGNORE_NAME_PATTERNS,
        change_threshold=CHANGE_THRESHOLD,
        threshold_except_substrings=THRESHOLD_EXCEPT_SUBSTRINGS,
        skip_high_frequency=SKIP_HIGH_FREQUENCY,
        enable_info_only_ignore=ENABLE_INFO_ONLY_IGNORE,
        info_only_ignore_patterns=INFO_ONLY_IGNORE_PATTERNS,
        category_extra_ignore_patterns=CATEGORY_EXTRA_IGNORE_PATTERNS,

        excel_glob=EXCEL_GLOB,
        output_dir=OUTPUT_DIR,
        output_dir_msg=OUTPUT_DIR_MSG,
        output_dir_time=OUTPUT_DIR_TIME,
        dbc_dir=DBC_DIR,
        dedup_window_sec=DEDUP_WINDOW_SEC,
        split_lines_threshold=SPLIT_LINES_THRESHOLD,
        split_lines_per_file=SPLIT_LINES_PER_FILE,
        split_chars_threshold=SPLIT_CHARS_THRESHOLD,
        split_chars_per_file=SPLIT_CHARS_PER_FILE,
        candidate_prompt_safe_split_chars=CANDIDATE_PROMPT_SAFE_SPLIT_CHARS,
        candidate_prompt_max_split_parts_warning=CANDIDATE_PROMPT_MAX_SPLIT_PARTS_WARNING,
        intentional_blank_token=INTENTIONAL_BLANK_TOKEN,
        tc_no_column_index=TC_NO_COLUMN_INDEX,
        tc_class_column_index=TC_CLASS_COLUMN_INDEX,
        tc_column_index=TC_COLUMN_INDEX,
        start_row_excel=START_ROW_EXCEL,

        ai_provider=AI_PROVIDER,
        gpt_model=GPT_MODEL,
        gemini_model=GEMINI_MODEL,
        gemini_stream_option=GEMINI_STREAM_OPTION,
        api_key=API_KEY,
        api_key_source_file="",
        api_key_display_name="",
        base_url=BASE_URL,
        project_id=PROJECT_ID,
        api_version=API_VERSION,
        input_root_dir_name=INPUT_ROOT_DIR_NAME,
        subfolders=SUBFOLDERS,
        output_root_dir_name=OUTPUT_ROOT_DIR_NAME,
        file_pattern=FILE_PATTERN,
        skip_if_output_exists=SKIP_IF_OUTPUT_EXISTS,
        completed_answer_file_pass=COMPLETED_ANSWER_FILE_PASS,
        max_retry=MAX_RETRY,
        sleep_between_calls=SLEEP_BETWEEN_CALLS,
        retry_wait_seconds=RETRY_WAIT_SECONDS,
        use_system_message=USE_SYSTEM_MESSAGE,
        system_message=SYSTEM_MESSAGE,

        merge_split_answer_files=True,
        keep_split_answer_files_after_merge=False,
        step_5_enable_time_folder=STEP_5_ENABLE_TIME_FOLDER,

        report_output_dir_name=REPORT_OUTPUT_DIR_NAME,
        report_title=REPORT_TITLE,
        report_sample_if_empty=REPORT_SAMPLE_IF_EMPTY,
        step_6_output_dir_name=STEP_6_OUTPUT_DIR_NAME,
        step_6_enable_time_detail=STEP_6_ENABLE_TIME_DETAIL,
        step_7_output_dir_name=STEP_7_OUTPUT_DIR_NAME,
        step_7_enable_ai_judgement=STEP_7_ENABLE_AI_JUDGEMENT,
        step_7_ai_max_retry=STEP_7_AI_MAX_RETRY,
        step_7_local_confidence_threshold=STEP_7_LOCAL_CONFIDENCE_THRESHOLD,
        step_7_local_score_margin=STEP_7_LOCAL_SCORE_MARGIN,
        step_6_enable_ai_judgement=STEP_7_ENABLE_AI_JUDGEMENT,
        step_6_ai_max_retry=STEP_7_AI_MAX_RETRY,
        global_mode=GLOBAL_MODE_ENABLED,
        global_exclude_crc_alv=GLOBAL_EXCLUDE_CRC_ALV,
        global_ignore_name_patterns=GLOBAL_IGNORE_NAME_PATTERNS,
        global_split_max_lines=GLOBAL_SPLIT_MAX_LINES,
        global_split_max_chars=GLOBAL_SPLIT_MAX_CHARS,
        global_output_dir_name=GLOBAL_OUTPUT_DIR_NAME,
    )


# =========================================================
# GUI override 적용
# =========================================================
def apply_gui_overrides(config: PipelineConfig) -> PipelineConfig:
    raw = os.environ.get("PIPELINE_GUI_CONFIG_JSON", "").strip()
    if not raw:
        return config

    try:
        data = json.loads(raw)
    except Exception as e:
        print(f"[WARN] PIPELINE_GUI_CONFIG_JSON 파싱 실패: {e}")
        return config

    try:
        # 구버전 GUI 호환: 과거 Step 6 하나만 전달되면 신규 Step 6/7을 함께 실행한다.
        if "run_step_7" not in data and "run_step_6" in data:
            data["run_step_7"] = data["run_step_6"]

        if "base_dir" in data and data["base_dir"]:
            config.base_dir = Path(data["base_dir"])

        if "active_category" in data and data["active_category"] in CATEGORIES:
            active_category = data["active_category"]
            selected = CATEGORIES[active_category]
            suffix = active_category.strip().lower()

            config.active_category = active_category
            config.category_prefix = selected["prefix"]
            config.category_keywords = selected["keywords"]
            config.include_keywords = selected.get("include_keywords", [])
            config.include_message_name_keywords = selected.get("include_message_name_keywords", [])
            config.exclude_keywords = selected.get("exclude_keywords", DEFAULT_EXCLUDE_KEYWORDS)
            config.output_txt_step2 = f"message_group_{suffix}.txt"

        # 구버전 설정에서 active_category=GLOBAL로 전달된 경우에는
        # 카테고리는 기본값을 유지하고 전용 global_mode만 활성화한다.
        if str(data.get("active_category", "")).strip().upper() == GLOBAL_CATEGORY_KEY:
            config.global_mode = True

        scalar_attrs = [
            "run_step_1",
            "run_step_2",
            "step_2_ai_enhancement",
            "run_step_3",
            "run_step_4",
            "run_step_5",
            "run_step_6",
            "run_step_7",
            "run_step_report",
            "retry_failed_only",
            "global_mode",
            "global_mode_enabled",
            "drop_first_seconds",
            "asc_frame_direction",
            "change_threshold",
            "skip_high_frequency",
            "ai_provider",
            "gpt_model",
            "gemini_model",
            "gemini_stream_option",
            "api_key",
            "base_url",
            "project_id",
            "api_version",
            "max_retry",
            "skip_if_output_exists",
            "completed_answer_file_pass",
            "merge_split_answer_files",
            "keep_split_answer_files_after_merge",
            "step_5_enable_time_folder",
            "split_lines_threshold",
            "split_lines_per_file",
            "split_chars_threshold",
            "split_chars_per_file",
            "candidate_prompt_safe_split_chars",
            "candidate_prompt_max_split_parts_warning",
            "report_output_dir_name",
            "report_title",
            "report_sample_if_empty",
            "step_6_output_dir_name",
            "step_6_enable_time_detail",
            "step_7_output_dir_name",
            "step_7_enable_ai_judgement",
            "step_7_ai_max_retry",
            "step_7_local_confidence_threshold",
            "step_7_local_score_margin",
            "global_exclude_crc_alv",
            "global_split_max_lines",
            "global_split_max_chars",
            "global_output_dir_name",
        ]

        for attr in scalar_attrs:
            if attr in data:
                if attr == "global_mode_enabled":
                    config.global_mode = bool(data[attr])
                else:
                    setattr(config, attr, data[attr])

        config.global_mode = bool(getattr(config, "global_mode", False))

        config.merge_split_answer_files = True
        config.keep_split_answer_files_after_merge = False
        config.step_6_enable_ai_judgement = bool(getattr(config, "step_7_enable_ai_judgement", True))
        config.step_6_ai_max_retry = int(getattr(config, "step_7_ai_max_retry", 2))

        # GPT 모델 허용값 보정
        if config.ai_provider == "gpt":
            allowed_gpt_models = set(GPT_MODEL_OPTIONS)
            if config.gpt_model not in allowed_gpt_models:
                print(f"[WARN] 허용되지 않은 GPT 모델이 전달되어 기본값으로 보정: {config.gpt_model} -> {GPT_MODEL}")
                config.gpt_model = GPT_MODEL

        # GUI가 로그 CAN 기준 can_config를 넘긴 경우: 이 값을 최우선 사용
        if "can_config" in data:
            normalized_can_config = normalize_can_config(data["can_config"])
            if normalized_can_config:
                config.can_config = normalized_can_config
                config.dbc_name_by_ch = build_dbc_name_by_ch_from_can_config(normalized_can_config)
                config.dbc_files_step2 = list(dict.fromkeys(config.dbc_name_by_ch.values()))

        # 호환성: can_config가 없고 로그 채널 기준 dbc_name_by_ch만 넘긴 경우
        elif "dbc_name_by_ch" in data and isinstance(data["dbc_name_by_ch"], dict):
            normalized = {}
            for k, v in data["dbc_name_by_ch"].items():
                try:
                    kk = int(k)
                except Exception:
                    continue

                vv = str(v).strip() if v is not None else ""
                if not vv or vv in ("N/A", "n/a", "None", "none"):
                    continue

                normalized[kk] = vv

            if normalized:
                config.dbc_name_by_ch = normalized
                config.dbc_files_step2 = list(dict.fromkeys(normalized.values()))
                config.can_config = build_default_can_config_from_dbc_name_by_ch(normalized)

    except Exception as e:
        raise ValueError(f"GUI 설정 적용 실패: {e}") from e

    return config


def is_global_mode(config: PipelineConfig) -> bool:
    return bool(getattr(config, "global_mode", False))


def apply_global_mode_guards(config: PipelineConfig) -> PipelineConfig:
    """GLOBAL은 기존 TC/AI 파이프라인이 아니라 전체 ASC 디코딩 전용 모드로 강제한다."""
    if not is_global_mode(config):
        config.global_mode = False
        return config

    config.global_mode = True

    # GUI에서 잘못 전달되거나 구 설정 파일이 복원되더라도 Main에서 최종 방어한다.
    config.run_step_1 = False
    config.run_step_2 = False
    config.step_2_ai_enhancement = False
    config.run_step_3 = False
    config.run_step_4 = False
    config.run_step_5 = False
    config.run_step_6 = False
    config.run_step_7 = False
    config.run_step_report = False
    config.retry_failed_only = False

    # GLOBAL은 TC 적용/AI 프롬프트용 필터가 아니므로 로그 전체를 대상으로 한다.
    config.drop_first_seconds = 0.0
    config.asc_frame_direction = "both"
    config.skip_high_frequency = False
    config.change_threshold = int(getattr(config, "change_threshold", 100) or 100)
    config.step_5_enable_time_folder = False
    config.step_6_enable_time_detail = False

    if bool(getattr(config, "global_exclude_crc_alv", True)):
        config.global_ignore_name_patterns = list(getattr(config, "global_ignore_name_patterns", []) or GLOBAL_IGNORE_NAME_PATTERNS)
    else:
        config.global_ignore_name_patterns = []

    return config


def validate_config(config: PipelineConfig) -> None:
    if not config.active_category:
        raise ValueError("ACTIVE_CATEGORY 값이 비어 있음")

    if config.active_category not in CATEGORIES:
        raise ValueError(
            f"지원하지 않는 ACTIVE_CATEGORY: {config.active_category}\n"
            f"사용 가능 값: {list(CATEGORIES.keys())}"
        )

    if config.ai_provider not in ("gpt", "gemini"):
        raise ValueError(
            f"지원하지 않는 AI_PROVIDER: {config.ai_provider}\n"
            f"사용 가능 값: ['gpt', 'gemini']"
        )

    if config.ai_provider == "gpt":
        allowed_gpt_models = set(GPT_MODEL_OPTIONS)
        if config.gpt_model not in allowed_gpt_models:
            raise ValueError(
                f"지원하지 않는 GPT_MODEL: {config.gpt_model}\n"
                f"사용 가능 값: {sorted(allowed_gpt_models)}"
            )

    # 로그 CAN 기준 can_config 검증
    if config.can_config:
        for can_name in ("CAN1", "CAN2", "CAN3", "CAN4"):
            item = config.can_config.get(can_name, {})
            if not isinstance(item, dict):
                raise ValueError(f"{can_name}: CAN 설정은 객체 1개여야 합니다.")

            enabled = bool(item.get("enabled", False))
            dbc = item.get("dbc")

            if isinstance(dbc, (list, tuple, set, dict)):
                raise ValueError(f"{can_name}: DBC는 1개만 지정할 수 있습니다.")

            if enabled and not dbc:
                raise ValueError(f"{can_name}: 활성 상태인데 DBC가 지정되지 않았습니다.")

    # can_config가 있으면 항상 dbc_name_by_ch 재생성 일치 보정
    if config.can_config:
        rebuilt = build_dbc_name_by_ch_from_can_config(config.can_config)
        config.dbc_name_by_ch = rebuilt
        config.dbc_files_step2 = list(dict.fromkeys(rebuilt.values()))

    report_only = (
        bool(getattr(config, "run_step_report", False))
        and not any([
            config.run_step_1,
            config.run_step_2,
            config.run_step_3,
            config.run_step_4,
            config.run_step_5,
            getattr(config, "run_step_6", False),
            getattr(config, "run_step_7", False),
        ])
    )

    if not config.dbc_name_by_ch and not report_only:
        raise ValueError("활성화된 로그 CAN-DBC 매핑이 비어 있음")

    for ch, dbc_name in sorted(config.dbc_name_by_ch.items()):
        dbc_path = config.base_dir / dbc_name
        if not dbc_path.exists():
            print(f"[WARN] CAN{ch} DBC 파일이 없음: {dbc_name}")

    for dbc_name in config.dbc_files_step2:
        dbc_path = config.base_dir / dbc_name
        if not dbc_path.exists():
            print(f"[WARN] step_2용 DBC 파일이 없음: {dbc_name}")

    excel_candidates = list(config.base_dir.glob(config.excel_glob))
    if config.run_step_4 and not excel_candidates:
        print(f"[WARN] 엑셀 파일이 없음: {config.excel_glob}")

    # Step 2 AI 후보 보강은 사용자가 명시적으로 ON한 경우에만 TestCase/API가 필수다.
    if config.run_step_2 and bool(getattr(config, "step_2_ai_enhancement", False)):
        if not excel_candidates:
            raise ValueError(f"Step 2 AI 후보 보강에 필요한 TestCase 엑셀 파일이 없습니다: {config.excel_glob}")
        if not str(getattr(config, "api_key", "") or "").strip():
            raise ValueError("Step 2 AI 후보 보강을 사용하려면 API KEY가 필요합니다.")

    if config.run_step_5 and not str(getattr(config, "api_key", "") or "").strip():
        raise ValueError("API KEY가 감지되지 않았습니다.")

    if (not config.run_step_5) and getattr(config, "run_step_7", False) and getattr(config, "step_7_enable_ai_judgement", True) and not str(getattr(config, "api_key", "") or "").strip():
        print("[WARN] Step 7의 애매한 신호 AI 분류는 API KEY가 없어 생략되고 로컬 분류만 사용됩니다.")


def print_config_summary(config: PipelineConfig) -> None:
    print("=" * 80)
    print("[CONFIG SUMMARY]")
    print(f"BASE_DIR                  = {config.base_dir}")
    print(f"ACTIVE_CATEGORY           = {config.active_category}")
    print(f"CATEGORY_PREFIX           = {config.category_prefix}")
    print(f"CATEGORY_KEYWORDS         = {config.category_keywords}")
    print(f"GLOBAL_MODE               = {getattr(config, 'global_mode', False)}")
    print(f"RUN_STEP_1                = {config.run_step_1}")
    print(f"RUN_STEP_2                = {config.run_step_2}")
    print(f"STEP_2_AI_ENHANCEMENT     = {getattr(config, 'step_2_ai_enhancement', False)}")
    print(f"RUN_STEP_3                = {config.run_step_3}")
    print(f"RUN_STEP_4                = {config.run_step_4}")
    print(f"RUN_STEP_5                = {config.run_step_5}")
    print(f"RUN_STEP_6                = {getattr(config, 'run_step_6', False)}")
    print(f"RUN_STEP_7                = {getattr(config, 'run_step_7', False)}")
    print(f"RUN_REPORT_GENERATE       = {config.run_step_report}")
    print(f"RETRY_FAILED_ONLY         = {config.retry_failed_ONLY if hasattr(config, 'retry_failed_ONLY') else config.retry_failed_only}")
    print(f"STEP5_RETRY_CASE_KEYS     = {len(getattr(config, 'step_5_retry_case_keys', []) or [])}개")
    print(f"STEP6_RETRY_CASE_KEYS     = {len(getattr(config, 'step_6_retry_case_keys', []) or [])}개")
    print(f"COMPLETED_ANSWER_FILE_PASS = {getattr(config, 'completed_answer_file_pass', False)}")
    print(f"INCLUDE_KEYWORDS          = {config.include_keywords}")
    print(f"INCLUDE_MSG_NAME_KEYWORDS = {config.include_message_name_keywords}")
    print(f"EXCLUDE_KEYWORDS          = {config.exclude_keywords}")

    print("CAN_CONFIG                =")
    for can_name in ("CAN1", "CAN2", "CAN3", "CAN4"):
        item = config.can_config.get(can_name, {}) if config.can_config else {}
        enabled = bool(item.get("enabled", False))
        dbc = item.get("dbc")
        dbc_text = dbc if dbc else "N/A"
        print(f"  {can_name} -> {'활성' if enabled else '비활성'} / {dbc_text}")

    print(f"DBC_NAME_BY_CH            = {config.dbc_name_by_ch}")
    print(f"DBC_FILES_STEP2           = {config.dbc_files_step2}")
    print(f"OUTPUT_TXT_STEP2          = {config.output_txt_step2}")
    print(f"DROP_FIRST_SECONDS        = {config.drop_first_seconds}")
    print(f"ASC_FRAME_DIRECTION       = {getattr(config, 'asc_frame_direction', 'auto')}")
    print(f"IGNORE_NAME_PATTERNS      = {config.ignore_name_patterns}")
    print(f"CHANGE_THRESHOLD          = {config.change_threshold}")
    print(f"THRESHOLD_EXCEPT_SUBSTR   = {config.threshold_except_substrings}")
    print(f"SKIP_HIGH_FREQUENCY       = {config.skip_high_frequency}")
    if getattr(config, "global_mode", False):
        print(f"GLOBAL_EXCLUDE_CRC_ALV    = {getattr(config, 'global_exclude_crc_alv', True)}")
        print(f"GLOBAL_IGNORE_PATTERNS    = {getattr(config, 'global_ignore_name_patterns', [])}")
        print(f"GLOBAL_SPLIT_MAX_LINES    = {getattr(config, 'global_split_max_lines', 100000)}")
        print(f"GLOBAL_SPLIT_MAX_CHARS    = {getattr(config, 'global_split_max_chars', 10000000)}")
    print(f"ENABLE_INFO_ONLY_IGNORE   = {config.enable_info_only_ignore}")
    print(f"STEP_5_ENABLE_TIME_FOLDER = {config.step_5_enable_time_folder}")
    print(f"EXCEL_GLOB                = {config.excel_glob}")
    print(f"OUTPUT_DIR                = {config.output_dir}")
    print(f"SPLIT_LINES_THRESHOLD     = {config.split_lines_threshold}")
    print(f"SPLIT_LINES_PER_FILE      = {config.split_lines_per_file}")
    print(f"SPLIT_CHARS_THRESHOLD     = {config.split_chars_threshold}")
    print(f"SPLIT_CHARS_PER_FILE      = {config.split_chars_per_file}")
    print(f"CANDIDATE_SAFE_SPLIT_CHARS = {getattr(config, 'candidate_prompt_safe_split_chars', 90000)}")
    print(f"CANDIDATE_MAX_SPLIT_PARTS_WARNING = {getattr(config, 'candidate_prompt_max_split_parts_warning', 10)}")
    print(f"AI_PROVIDER               = {config.ai_provider}")
    print(f"API_KEY_STATUS            = {getattr(config, 'api_key_display_name', 'API 입력됨') if getattr(config, 'api_key', '') else 'API KEY 미감지'}")
    if getattr(config, "api_key_source_file", ""):
        print(f"API_KEY_SOURCE            = {Path(config.api_key_source_file).name}")

    if config.ai_provider == "gpt":
        print(f"MODEL                     = {config.gpt_model}")
        print(f"API_VERSION               = {config.api_version}")
    elif config.ai_provider == "gemini":
        print(f"MODEL                     = {config.gemini_model}")
        print(f"GEMINI_STREAM_OPTION      = {config.gemini_stream_option}")

    print("CANDIDATE_SPLIT_MODE      = 기본 단일 / 90,000자 초과 시 예외 안전 분할")
    print(f"REPORT_OUTPUT_DIR         = {config.report_output_dir_name}")
    print(f"REPORT_SAMPLE_IF_EMPTY    = {config.report_sample_if_empty}")
    print(f"STEP_6_OUTPUT_DIR         = {getattr(config, 'step_6_output_dir_name', 'AI답변_결과')}")
    print(f"STEP_6_TIME_DETAIL        = {getattr(config, 'step_6_enable_time_detail', False)}")
    print(f"STEP_7_AI_JUDGEMENT       = {getattr(config, 'step_7_enable_ai_judgement', True)}")
    print(f"STEP_7_LOCAL_THRESHOLD    = {getattr(config, 'step_7_local_confidence_threshold', 0.78)}")
    print("=" * 80)


def run_step(module_name: str, config: PipelineConfig, step_label: str) -> None:
    try:
        module = resolve_step_module(config.base_dir, module_name)
    except Exception as e:
        raise ImportError(
            f"{step_label} 모듈 로딩 실패: {module_name}\n"
            f"base/rev 파일명 또는 위치 확인 필요\n"
            f"원인: {e}"
        ) from e

    if not hasattr(module, "run"):
        raise AttributeError(
            f"{step_label} 모듈에 run(config) 함수가 없음: {module_name}"
        )

    print("\n" + "=" * 80)
    print(f"[START] {step_label}")
    print("=" * 80)

    module.run(config)

    print(f"[DONE] {step_label}")



def cleanup_user_invisible_artifacts(config: PipelineConfig) -> None:
    """정상 종료 후 사용자에게 불필요한 내부 보조자료만 best-effort로 정리한다."""
    import shutil

    base_dir = Path(config.base_dir)
    output_root = base_dir / str(getattr(config, "output_dir", "AI_문의용_출력"))
    removed_dirs = 0
    removed_json = 0
    warnings = []

    # Step 4 이상을 수행한 경우 후보 manifest 폴더 정리.
    if bool(getattr(config, "run_step_4", False)):
        candidate_dir = output_root / "후보목록"
        if candidate_dir.exists():
            try:
                shutil.rmtree(candidate_dir)
                removed_dirs += 1
                print(f"[CLEANUP] removed internal folder: {candidate_dir}")
            except Exception as exc:
                warnings.append(f"{candidate_dir}: {exc}")

    # Step 5~7을 수행한 경우 마커와 구조화 JSON 정리.
    if any(bool(getattr(config, f"run_step_{step}", False)) for step in (5, 6, 7)):
        answer_root = output_root / str(getattr(config, "step_6_output_dir_name", "AI답변_결과"))
        marker_names = {"마커폴더", "메세지별_마커폴더", "시간별_마커폴더"}
        if answer_root.exists():
            for child in list(answer_root.iterdir()):
                if child.is_dir() and (child.name in marker_names or child.name.endswith("_마커폴더")):
                    try:
                        shutil.rmtree(child)
                        removed_dirs += 1
                        print(f"[CLEANUP] removed marker folder: {child}")
                    except Exception as exc:
                        warnings.append(f"{child}: {exc}")
            for folder_name in ("메세지별", "시간별"):
                answer_dir = answer_root / folder_name
                if not answer_dir.is_dir():
                    continue
                for json_path in answer_dir.glob("AI답변_*.json"):
                    try:
                        json_path.unlink()
                        removed_json += 1
                        print(f"[CLEANUP] removed internal JSON: {json_path}")
                    except Exception as exc:
                        warnings.append(f"{json_path}: {exc}")

    print(f"[CLEANUP] summary: folders={removed_dirs}, json={removed_json}, warnings={len(warnings)}")
    for warning in warnings:
        print(f"[CLEANUP][WARN] {warning}")

def _has_blf_inputs_for_global(base_dir: Path) -> bool:
    base = Path(base_dir)
    if list(base.glob("*.blf")):
        return True
    targets = {"log파일", "logfile", "로그파일", "로그폴더"}
    try:
        for child in base.iterdir():
            norm = re.sub(r"[\s_\-]+", "", child.name.strip().lower())
            if child.is_dir() and norm in targets and list(child.glob("*.blf")):
                return True
    except Exception:
        pass
    return False


def run_pipeline(config: PipelineConfig) -> None:
    if is_global_mode(config):
        print("\n[GLOBAL] 특수 모드 실행: BLF→ASC 후 전체 ASC 디코딩만 수행합니다.")
        if _has_blf_inputs_for_global(config.base_dir):
            run_step(STEP_1_MODULE, config, "GLOBAL PREP - BLF -> ASC")
        else:
            print("[GLOBAL] BLF 파일이 없어 Step 1 변환 준비를 생략하고 기존 ASC를 분석합니다.")
        run_step(GLOBAL_STEP_3_MODULE, config, "GLOBAL - ASC 전체 디코딩")
        cleanup_user_invisible_artifacts(config)
        print("\n[OK] GLOBAL 모드 실행 완료")
        return

    if config.run_step_1:
        run_step(STEP_1_MODULE, config, "STEP 1 - BLF -> ASC")

    if config.run_step_2:
        run_step(STEP_2_MODULE, config, "STEP 2 - MESSAGE GROUP EXPORT")

    if config.run_step_3:
        run_step(STEP_3_MODULE, config, "STEP 3 - ASC -> TXT")

    if config.run_step_4:
        run_step(STEP_4_MODULE, config, "STEP 4 - TXT -> AI REQUEST TXT")

    if config.run_step_5:
        run_step(STEP_5_MODULE, config, "STEP 5 - AI CALL")

    if getattr(config, "run_step_6", False):
        run_step(STEP_6_MODULE, config, "STEP 6 - RELATED SIGNAL DETAIL EXTRACTION")

    if getattr(config, "run_step_7", False):
        run_step(STEP_7_MODULE, config, "STEP 7 - INPUT OUTPUT EXCLUDED CLASSIFICATION")

    if getattr(config, "run_step_report", False):
        run_step(REPORT_MODULE, config, "REPORT GENERATE")

    cleanup_user_invisible_artifacts(config)
    print("\n[OK] 전체 파이프라인 실행 완료")


def main() -> None:
    config = build_config()
    config = apply_gui_overrides(config)
    config = apply_global_mode_guards(config)
    config = apply_api_key_from_file(config)
    validate_config(config)
    print_config_summary(config)

    atexit.register(lambda: remove_pycache(config.base_dir))

    try:
        run_pipeline(config)
    except Exception as e:
        print("\n[ERROR] 파이프라인 실행 중 예외 발생")
        print(f"예외 내용: {e}")
        print("\n[TRACEBACK]")
        traceback.print_exc()
        raise
    finally:
        remove_pycache(config.base_dir)


def _run_latest_main_entrypoint() -> None:
    """오래된 Main rev를 직접 실행해도 같은 폴더의 최신 Main rev로 인계한다."""
    code_dir = Path(__file__).resolve().parent
    best = _find_latest_rev_module_file(code_dir, "Signal_Export_V2_Main")
    if best is not None:
        latest_path, latest_rev = best
        if latest_path.resolve() != Path(__file__).resolve():
            print(f"[INFO] Newer V2 Main detected: {latest_path.name} (rev={latest_rev})")
            latest_module = _load_module_by_file(latest_path, "Signal_Export_V2_Main")
            latest_module.main()
            return
    main()


if __name__ == "__main__":
    _run_latest_main_entrypoint()
