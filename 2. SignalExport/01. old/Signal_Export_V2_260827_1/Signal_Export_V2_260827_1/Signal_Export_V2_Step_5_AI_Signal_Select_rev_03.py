# -*- coding: utf-8 -*-
"""
Signal_Export_V2_Step_5_AI_Signal_Select_rev_03.py

목적
- AI 문의용 txt를 읽어 GPT 또는 Gemini 호출

[V2 REV 03 변경점]
- Step 4 프롬프트의 ``후보_시그널수: 0``을 정상 무결과 케이스로 인식
- 후보 0개이면 API를 호출하지 않고 표준 AI답변 파일을 로컬 생성
- 후보 0개 결과는 ``연관 없는 메세지`` 항목이 비어 있어도 정상으로 검증
- split/최종 병합/완료파일 Pass/실패파일 재실행에서 동일한 후보 0개 판정 적용
- 구형 ``변경점_라인수`` 표기도 호환 유지
- 결과를 AI답변_결과/메세지별, AI답변_결과/시간별에 저장
- 모든 설정은 main.py에서 관리
- 이 파일은 순수 실행 모듈 역할만 수행

[REV 27 현재 실행 구조]
- 기본적으로 Step 4 후보 프롬프트 1개당 API 1회 호출
- 후보 프롬프트가 안전 상한을 넘은 케이스만 _a/_b/... 조각별 API 호출 후 최종 답변 1개로 병합
- Message:Signal 기준으로 중복 제거하며, 어느 조각에서든 관련으로 선정된 신호는 최종 연관 목록을 우선
- 후보 프롬프트 조각 구성/내용이 변경되면 source manifest로 감지해 기존 답변을 자동 재사용하지 않음
- 최종 실패 시 기존 실패 경고 수명주기를 유지

[추가/수정 사항]
- 응답이 아래 형식 오류를 내는 케이스 자동 보정:
  * "연관 있는 메세지 없음"을 출력했는데,
    "연관 없는 메세지" 섹션이 누락/공란인 경우
- 보정 재요청은 최대 2회까지 수행
- 단, "연관 있는 메세지 없음"이 아닌 경우(= 연관 있는 메세지가 1개 이상 있다고 답한 케이스)는
  "연관 없는 메세지" 섹션이 없어도 정상으로 간주(검증/보정 대상 아님)
- "연관 없는 메세지" 최소 기준: 의미 있는 줄 1줄 이상

[변경 사항 - 실패파일_요약 생성 정책]
- API 사용 중 최종 실패가 발생한 경우(해당 폴더 fail_count > 0)에만 요약 파일 생성
- 요약 파일 생성 위치:
  step_5_use_api_to_receive_response.py 파일이 위치한 폴더
- 파일명: 실패파일_요약_{메세지별/시간별}.txt

[REV - 결과 저장 전 definition/description 제거]
- step_4 프롬프트에는 (definition: ...), (description: ...) 또는 조합이 포함될 수 있음
- step_5 결과 파일에는 위 definition/description 괄호 블록만 제거하고 저장
- (meaning) 괄호(예: (Sec), (ON), (Invalid)) 등은 유지

[REV - 결과 저장 전 연관 있는 메세지 중복 제거 (메세지별만 적용)]
- AI 응답에서 "연관 있는 메세지" 영역만 후처리하여 중복 제거
- 적용 대상은 "메세지별" 출력 파일만
- "시간별" 출력 파일은 중복 제거를 적용하지 않음
- 중복 기준:
  * 왼쪽 시간 prefix(예: 0.123sec CH3)는 무시
  * 시간 prefix 제거 후의 나머지 라인이 완전히 동일하면 중복으로 간주
  * 값이 다르면 다른 라인으로 간주하여 유지
- "연관 없는 메세지" 영역은 절대 수정하지 않음

[REV - 결과 저장 전 연관 있는 메세지 시간 prefix 제거 (메세지별만 적용)]
- AI 응답에서 "연관 있는 메세지" 영역의 실제 메세지 라인에 한해
  앞의 시간 prefix(예: 11.5441sec CH1)를 제거하고 저장
- 적용 대상은 "메세지별" 출력 파일만
- "시간별" 출력 파일은 기존 그대로 유지
- 파일명/제목/설명 줄은 유지하고, 실제 메세지 라인만 변환
- "연관 없는 메세지" 영역은 절대 수정하지 않음

[추가 - step_4 분할 결과 병합]
- step_4에서 생성된 AI문의용_..._a.txt / _b.txt / _c.txt ... 에 대해
  step_5는 기존처럼 분할 파일 단위로 API 호출/저장
- 모든 처리 완료 후, step_5에서 최종 AI답변_....txt 로 병합 생성
- 메세지별:
  * 연관 있는 메세지: 같은 라인 중복 제거(입력 순서 유지)
  * 연관 없는 메세지: 같은 MSG:SIG 키는 1개로 병합(더 정보량이 큰 라인 채택)
  * 정렬은 하지 않음
- 시간별:
  * _a -> _b -> _c 순서대로 이어붙임
  * 제목은 첫 파일 기준 사용

[REV 13 유지 사항]
- 실패파일만 재실행 시 케이스 단위 판정 유지
- 최종 병합본(AI답변_...txt)이 존재하고, 관련 입력 .error.txt가 없으면
  split 출력(_a, _b, _c ...)이 없어도 정상 완료 케이스로 간주

[REV 14 유지 사항]
- retry_failed_only=True 경로에서도 케이스 병합 성공 후
  keep_split_answer_files_after_merge=False 이면 split 출력 삭제

[REV 15 유지 사항]
- split 찌꺼기 정리 로직을 일반 실행 / 실패파일만 재실행 모두에 공통 적용
- step_5 시작 시, 병합본이 이미 존재하고 입력 .error.txt가 없는 완료 케이스의 split 출력 파일을 사전 정리
- step_5 실행 중 병합 성공한 케이스도 옵션에 따라 split 출력 삭제
- step_5 종료 후에도 한 번 더 안전하게 split 찌꺼기 정리 수행

[REV 18 변경점]
- 결과 txt 저장을 atomic write 방식으로 변경
  * AI답변_xx.txt.tmp에 먼저 저장한 뒤 저장 완료 시 정식 txt로 교체
  * 비정상 종료로 남은 .tmp 파일은 실패/불완전 출력으로 간주
- retry_failed_only=True에서 split 완료 판단 시 파일 존재 여부뿐 아니라 최소 형식 검증 수행
  * 빈 파일, 형식 오류 문구, Traceback/API 오류 문구, 연관 없는 메세지 누락 등을 불완전으로 판단
- 모든 split 출력이 이미 있어도 최종 병합본만 없을 때, split 형식 검증을 통과한 경우에만 API 재호출 없이 병합
- 케이스 병합 결과도 atomic write + 최소 형식 검증 후 저장

[REV 19 변경점]
- 완료된 답변파일 Pass 옵션 지원
- 기존 split/병합 출력이 최소 형식 검증을 통과하면 API 재호출 없이 재사용 가능
- 정상 저장 완료된 split/병합본에 .ok.json 완료 마커를 생성
- 누락/불완전 split만 선택적으로 추가 처리하고 전체 split을 병합

[REV 17 유지 사항]
- 실패파일만 재실행(retry_failed_only=True) 시 분할 파일을 전부 삭제/처리하지 않음
- 이미 완료된 앞쪽 split 출력은 유지하고, 첫 누락/에러/형식불량 split의 직전 split부터 tail만 재실행
  예: a~e 완료, f~h 누락이면 e~h만 재실행하고 a~d는 그대로 사용
- 모든 split 출력은 있으나 최종 병합본만 없으면 API 재호출 없이 병합만 수행

[REV 16 변경점]
- step_5 전용 시간별 처리 옵션 지원
- config.step_5_enable_time_folder == False 이면
  "시간별" 폴더는 step_5 대상에서 제외
- 즉 step_1 ~ step_4에서 시간별 txt를 생성해도,
  step_5만 선택적으로 시간별 AI 처리를 건너뛸 수 있음

[REV 20 변경점]
- GUI 진행률 표시 보강을 위해 Step 5 CASE 진행률을 전체 대상 하위폴더 기준으로 출력
- 메세지별 + 시간별 Step 5 대상 CASE 수를 합산하여 [CASE 현재/전체 | %] 로그를 생성

[REV 24 변경점]
- retry_failed_only=True에서 Step 5가 실제 재실행 대상으로 선정한 케이스를 output type+case stem 키로 기록
- 동일 파이프라인에서 뒤이어 실행되는 Step 6이 Step 5 갱신 케이스를 함께 재분류할 수 있도록 config.step_5_retry_case_keys에 전달
- 기존 tail 재실행, atomic 저장, 완료된 답변파일 Pass 정책은 변경하지 않음


[REV 27 변경점]
- Step 4 후보 프롬프트가 기본 단일 파일이고 안전 상한 초과 시에만 _a/_b/...로 나뉘는 예외 안전 분할을 지원
- 단일/안전 분할을 같은 케이스 처리기로 다루고, split 답변을 Message:Signal 기준으로 병합 후 최종 AI답변 1개 생성
- 최종 병합본에 현재 모든 Step 4 입력 조각의 파일명/크기/SHA-256 manifest를 저장하여 후보 프롬프트 변경 시 재처리
- 정상 완료 시 split 답변은 삭제하고 최종 병합본만 유지, 일부 split 실패 시 기존 경고/.error 수명주기 유지

[REV 26 변경점]
- Step 4의 후보 시그널 단일 프롬프트를 TC당 1회 API 호출
- 일반 _a/_b/_c split 처리와 병합을 실행 경로에서 제거
- 실패파일만 재실행, 완료 파일 인정, .error 및 00_실패결과_경고 수명주기는 유지

[REV 25 변경점]
- 메세지별/시간별 AI답변 출력 폴더에 미해결 실패가 있으면 00_실패결과_경고.txt 생성
- 경고 파일은 최종 실패 split/케이스, 영향 케이스, 실패 사유와 부분 결과 주의사항을 표시
- 2차/3차 재시도 또는 실패파일만 재실행으로 모든 오류가 해결되면 경고 파일 자동 삭제
- 기존 AI답변_*.txt가 있어도 .error가 남아 있으면 완전한 정상 결과로 판단하지 않도록 명시

[REV 21]
- 완료 마커(.ok.json)를 AI답변_결과/메세지별 또는 시간별 폴더 내부에 직접 저장하지 않음
- 메세지별 출력의 마커는 AI답변_결과/메세지별_마커폴더에 저장
- 시간별 출력의 마커는 AI답변_결과/시간별_마커폴더에 저장
- 마커 읽기/쓰기/삭제 시 별도 마커폴더를 기준으로 처리하며, 구버전 위치의 마커는 발견 시 정리
- split 내부 진행률은 기존 로그로 남기되 GUI 막대바 계산 대상에서는 제외

[REV 23]
- Step 5 시작 시 config.api_key가 비어 있으면 "API KEY가 감지되지 않았습니다." 메시지로 즉시 중단
- API Key는 main의 API_Key류 txt 파일 자동 로드 결과를 사용하며, Step 5는 키 값을 로그에 출력하지 않음

[REV 22 유지]
- AI 답변 파일이 1개일 경우, split 파일 제거 기능에 영향받지 않도록 수정
"""

from __future__ import annotations

from pathlib import Path
import time
import traceback
from datetime import datetime
import json
import re
import hashlib
from typing import Dict, List, Tuple

try:
    import requests
except Exception:
    requests = None

try:
    from openai import AzureOpenAI
except Exception:
    AzureOpenAI = None


# =========================================================
# 파일명 변환
# =========================================================
def make_output_filename(input_filename: str) -> str:
    if input_filename.startswith("AI문의용_"):
        return input_filename.replace("AI문의용_", "AI답변_", 1)
    return "AI답변_" + input_filename


# =========================================================
# 입력 파일 기준 .error.txt 유틸
# =========================================================
def make_input_error_log_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}.error.txt")


def has_input_error_log(input_path: Path) -> bool:
    return make_input_error_log_path(input_path).exists()


def write_input_error_log(
    input_path: Path,
    stage: str,
    reason: str,
    exc: Exception | None = None,
    retry_count: int | None = None,
) -> Path:
    error_log_path = make_input_error_log_path(input_path)

    tb_text = ""
    exc_repr = ""
    if exc is not None:
        exc_repr = repr(exc)
        tb_text = traceback.format_exc()

    retry_text = ""
    if retry_count is not None:
        retry_text = f"[재시도 횟수]\n{retry_count}회 모두 실패\n\n"

    error_text = (
        f"[실패 파일]\n{input_path.name}\n\n"
        f"[원본 경로]\n{input_path}\n\n"
        f"[실패 단계]\n{stage}\n\n"
        f"{retry_text}"
        f"[추정 사유]\n{reason}\n\n"
        f"[예외 메시지]\n{exc_repr}\n\n"
        f"[상세 Traceback]\n{tb_text}"
    )
    error_log_path.write_text(error_text, encoding="utf-8")
    return error_log_path


def remove_input_error_log_if_exists(input_path: Path) -> None:
    error_log_path = make_input_error_log_path(input_path)
    try:
        if error_log_path.exists():
            error_log_path.unlink()
            print(f"[OK] 이전 에러로그 삭제: {error_log_path.name}")
    except Exception as e:
        print(f"[WARN] 에러로그 삭제 실패: {error_log_path} ({e})")


# =========================================================
# [FINAL] 결과 후처리: 라인 끝의 (definition/description ...) 제거 (meaning은 유지)
# =========================================================
_DEF_DESC_TAIL_BLOCKS_RE = re.compile(
    r"""
    (?:[ \t]*
        \(
            \s*(?:definition|description)\s*:\s*[^)]*
        \)
    )+
    [ \t]*$
    """,
    flags=re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

_DEF_DESC_TAIL_FALLBACK_RE = re.compile(
    r"""
    [ \t]*
    \(
        \s*(?:definition|description)\s*:\s*.*
    $
    """,
    flags=re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

_DEF_DESC_TAIL_SUPER_FALLBACK_RE = re.compile(
    r"""
    \s+
    \(
        \s*(?:definition|description)\s*:\s*.*
    $
    """,
    flags=re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)


def strip_definition_description_blocks(text: str) -> str:
    if not text:
        return ""

    original_endswith_newline = text.endswith("\n")

    out = text.replace("\r\n", "\n").replace("\r", "\n")
    out = _DEF_DESC_TAIL_BLOCKS_RE.sub("", out)
    out = _DEF_DESC_TAIL_FALLBACK_RE.sub("", out)
    out = _DEF_DESC_TAIL_SUPER_FALLBACK_RE.sub("", out)

    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r" +\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)

    if original_endswith_newline:
        return out.rstrip() + "\n"
    return out.strip()


# =========================================================
# REV 18: atomic 저장 / 최소 형식 검증 유틸
# =========================================================
_OUTPUT_ERROR_MARKERS = [
    "Traceback (most recent call last)",
    "BadRequestError",
    "AuthenticationError",
    "PermissionDeniedError",
    "RateLimitError",
    "InternalServerError",
    "APIConnectionError",
    "APITimeoutError",
    "HTTPError",
    "ConnectionError",
    "ReadTimeout",
    "ServiceUnavailable",
]


def make_tmp_output_path(output_path: Path) -> Path:
    """정식 결과 파일과 같은 폴더에 임시 저장 파일명을 만든다."""
    return output_path.with_name(output_path.name + ".tmp")


def remove_tmp_output_if_exists(output_path: Path) -> None:
    tmp_path = make_tmp_output_path(output_path)
    try:
        if tmp_path.exists():
            tmp_path.unlink()
            print(f"[CLEANUP] 임시 출력 삭제: {tmp_path.name}")
    except Exception as e:
        print(f"[WARN] 임시 출력 삭제 실패: {tmp_path.name} ({e})")


def has_tmp_output(output_path: Path) -> bool:
    return make_tmp_output_path(output_path).exists()


def atomic_write_text(output_path: Path, text: str, encoding: str = "utf-8") -> None:
    """
    결과 파일을 직접 덮어쓰지 않고 .tmp에 먼저 저장한 뒤 replace 한다.
    - 정상 저장 완료 전 프로그램이 종료되면 정식 .txt 대신 .tmp가 남는다.
    - 다음 retry_failed_only 실행 시 .tmp 존재를 불완전 출력으로 간주한다.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = make_tmp_output_path(output_path)
    tmp_path.write_text(text, encoding=encoding)
    tmp_path.replace(output_path)


def get_completion_marker_dir(output_path: Path) -> Path:
    """
    정상 완료 마커 저장 폴더를 반환한다.
    예) .../AI답변_결과/메세지별/AI답변_x.txt
        -> .../AI답변_결과/메세지별_마커폴더/AI답변_x.txt.ok.json
    """
    output_dir = output_path.parent
    folder_name = output_dir.name or "AI답변"
    return output_dir.parent / f"{folder_name}_마커폴더"


def make_completion_marker_path(output_path: Path) -> Path:
    """정상 완료 마커 파일 경로를 반환한다. 마커는 별도 *_마커폴더에 저장한다."""
    return get_completion_marker_dir(output_path) / f"{output_path.name}.ok.json"


def make_legacy_completion_marker_path(output_path: Path) -> Path:
    """REV20 이하에서 사용하던 구버전 완료 마커 경로를 반환한다."""
    return output_path.with_name(output_path.name + ".ok.json")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def remove_completion_marker_if_exists(output_path: Path) -> None:
    marker_paths = [
        make_completion_marker_path(output_path),
        make_legacy_completion_marker_path(output_path),
    ]
    for marker_path in marker_paths:
        try:
            if marker_path.exists():
                marker_path.unlink()
                print(f"[CLEANUP] 완료 마커 삭제: {marker_path.name}")
            tmp_marker_path = marker_path.with_name(marker_path.name + ".tmp")
            if tmp_marker_path.exists():
                tmp_marker_path.unlink()
                print(f"[CLEANUP] 완료 마커 임시파일 삭제: {tmp_marker_path.name}")
        except Exception as e:
            print(f"[WARN] 완료 마커 삭제 실패: {marker_path.name} ({e})")


def write_completion_marker(output_path: Path, source_path: Path | None = None, kind: str = "split") -> None:
    """
    정상 검증이 끝난 결과 파일에 완료 마커를 남긴다.
    - 마커에는 결과 파일명/크기/sha256을 저장하여 부분 저장이나 외부 변경을 추적한다.
    - 의미 판단 품질은 마커 대상이 아니며, 파일 저장 완료와 최소 형식 통과만 표시한다.
    """
    try:
        if not output_path.exists():
            return
        marker = {
            "status": "OK",
            "kind": kind,
            "output_file": output_path.name,
            "source_file": source_path.name if source_path is not None else "",
            "source_size": source_path.stat().st_size if source_path is not None and source_path.exists() else None,
            "source_sha256": _sha256_file(source_path) if source_path is not None and source_path.exists() else "",
            "size": output_path.stat().st_size,
            "sha256": _sha256_file(output_path),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        marker_path = make_completion_marker_path(output_path)
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_marker_path = marker_path.with_name(marker_path.name + ".tmp")
        tmp_marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_marker_path.replace(marker_path)

        legacy_marker_path = make_legacy_completion_marker_path(output_path)
        if legacy_marker_path.exists():
            try:
                legacy_marker_path.unlink()
                print(f"[CLEANUP] 구버전 위치 완료 마커 정리: {legacy_marker_path.name}")
            except Exception as legacy_e:
                print(f"[WARN] 구버전 위치 완료 마커 정리 실패: {legacy_marker_path.name} ({legacy_e})")
    except Exception as e:
        print(f"[WARN] 완료 마커 생성 실패: {output_path.name} ({e})")


def _validate_completion_marker_file(marker_path: Path, output_path: Path) -> Tuple[bool, str]:
    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return False, f"완료 마커 형식 오류: {marker_path.name}"
        if data.get("status") != "OK":
            return False, f"완료 마커 상태 비정상: {marker_path.name}"
        if data.get("output_file") != output_path.name:
            return False, f"완료 마커 파일명 불일치: {marker_path.name}"
        if not output_path.exists():
            return False, f"완료 마커 대상 파일 없음: {output_path.name}"
        size = output_path.stat().st_size
        if int(data.get("size", -1)) != int(size):
            return False, f"완료 마커 size 불일치: {output_path.name}"
        sha = _sha256_file(output_path)
        if str(data.get("sha256", "")) != sha:
            return False, f"완료 마커 sha256 불일치: {output_path.name}"
        return True, "정상"
    except Exception as e:
        return False, f"완료 마커 읽기 실패: {marker_path.name} ({e})"


def is_completion_marker_valid(output_path: Path) -> Tuple[bool, str]:
    marker_path = make_completion_marker_path(output_path)
    if marker_path.exists():
        return _validate_completion_marker_file(marker_path, output_path)

    legacy_marker_path = make_legacy_completion_marker_path(output_path)
    if legacy_marker_path.exists():
        legacy_ok, legacy_reason = _validate_completion_marker_file(legacy_marker_path, output_path)
        if legacy_ok:
            write_completion_marker(output_path, source_path=None, kind="migrated")
            migrated_marker_path = make_completion_marker_path(output_path)
            if migrated_marker_path.exists():
                return True, "정상(구버전 마커 이관 완료)"
            return True, "정상(구버전 마커 유효)"
        return False, legacy_reason

    return False, f"완료 마커 없음: {marker_path.name}"


def is_completion_marker_valid_for_input(input_path: Path, output_path: Path) -> Tuple[bool, str]:
    """완료 마커와 현재 Step 4 후보 프롬프트의 동일성을 함께 검증한다."""
    ok, reason = is_completion_marker_valid(output_path)
    if not ok:
        return ok, reason

    marker_path = make_completion_marker_path(output_path)
    if not marker_path.exists():
        marker_path = make_legacy_completion_marker_path(output_path)
    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"완료 마커 source 검증 실패: {marker_path.name} ({exc})"

    if not input_path.exists():
        return False, f"현재 후보 프롬프트 없음: {input_path.name}"
    if str(data.get("source_file", "")) != input_path.name:
        return False, f"완료 마커 source 파일명 불일치: {input_path.name}"

    marker_source_sha = str(data.get("source_sha256", "") or "")
    if not marker_source_sha:
        return False, f"완료 마커에 source 해시 없음: {marker_path.name}"
    current_source_sha = _sha256_file(input_path)
    if marker_source_sha != current_source_sha:
        return False, f"Step 4 후보 프롬프트 변경 감지: {input_path.name}"

    marker_source_size = data.get("source_size")
    if marker_source_size is not None and int(marker_source_size) != int(input_path.stat().st_size):
        return False, f"Step 4 후보 프롬프트 크기 변경 감지: {input_path.name}"
    return True, "정상(출력+현재 후보 프롬프트 일치)"


def ensure_completion_marker_for_valid_output(
    input_path: Path | None,
    output_path: Path,
    kind: str = "split",
) -> None:
    """기존 정상 출력에 완료 마커가 없거나 불일치하면 새로 생성한다."""
    marker_ok, _marker_reason = is_completion_marker_valid(output_path)
    if not marker_ok:
        write_completion_marker(output_path, source_path=input_path, kind=kind)


def validate_answer_text(
    answer: str,
    source_prompt: str | None = None,
    context: str = "",
    candidate_count: int | None = None,
) -> Tuple[bool, str]:
    """
    AI 답변/병합본의 최소 형식을 검증한다.
    의미 판단 품질은 검증하지 않고, 비정상 종료/빈 파일/명백한 형식 오류만 잡는다.
    """
    text = (answer or "").replace("\r\n", "\n").replace("\r", "\n")
    stripped = text.strip()

    if not stripped:
        return False, f"{context} 출력이 비어 있음".strip()

    if len(stripped) < 12:
        return False, f"{context} 출력이 비정상적으로 짧음".strip()

    if "형식 오류(재출력 필요)" in stripped:
        return False, f"{context} 형식 오류 문구 포함".strip()

    for marker in _OUTPUT_ERROR_MARKERS:
        if marker in stripped:
            return False, f"{context} 오류 문구 포함: {marker}".strip()

    if is_missing_unrelated_section(
        stripped,
        source_prompt or "",
        candidate_count=candidate_count,
    ):
        return False, f"{context} 연관 없는 메세지 섹션 누락/공란".strip()

    return True, "정상"


def validate_output_file_for_input(
    input_path: Path,
    output_path: Path,
    allow_existing_input_error: bool = False,
) -> Tuple[bool, str]:
    """
    개별 split 출력 파일이 재사용 가능한 상태인지 확인한다.

    allow_existing_input_error=True는 현재 API 호출이 새 출력 저장까지 성공한 직후에만 사용한다.
    이 경우 이전 실행에서 남은 .error를 출력 검증 전에 장애로 보지 않고,
    저장 검증 완료 후 remove_input_error_log_if_exists()로 정리한다.
    """
    if has_tmp_output(output_path):
        return False, f"임시 출력(.tmp) 존재: {make_tmp_output_path(output_path).name}"

    if has_input_error_log(input_path) and not allow_existing_input_error:
        return False, f"입력 .error 존재: {input_path.name}"

    if not output_path.exists():
        return False, f"split 출력 없음: {output_path.name}"

    if output_path.stat().st_size <= 0:
        return False, f"split 출력 빈 파일: {output_path.name}"

    try:
        answer = _read_text_any(output_path)
    except Exception as e:
        return False, f"split 출력 읽기 실패: {output_path.name} ({e})"

    try:
        source_prompt = input_path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        source_prompt = ""

    ok, reason = validate_answer_text(answer, source_prompt=source_prompt, context=output_path.name)
    return ok, reason


def validate_output_file_standalone(
    output_path: Path,
    context: str = "출력",
    candidate_count: int | None = None,
) -> Tuple[bool, str]:
    """병합본처럼 단일 입력 프롬프트가 없는 결과 파일을 최소 검증한다."""
    if has_tmp_output(output_path):
        return False, f"임시 출력(.tmp) 존재: {make_tmp_output_path(output_path).name}"

    if not output_path.exists():
        return False, f"{context} 없음: {output_path.name}"

    if output_path.stat().st_size <= 0:
        return False, f"{context} 빈 파일: {output_path.name}"

    try:
        text = _read_text_any(output_path)
    except Exception as e:
        return False, f"{context} 읽기 실패: {output_path.name} ({e})"

    return validate_answer_text(
        text,
        source_prompt=None,
        context=f"{context} {output_path.name}",
        candidate_count=candidate_count,
    )


# =========================================================
# 실패 사유 정리
# =========================================================
def classify_error_message(exc: Exception) -> str:
    msg = str(exc).lower()

    if "401" in msg or "unauthorized" in msg or "authentication" in msg or "api key" in msg:
        return "API 인증 실패 가능성"
    if "403" in msg or "forbidden" in msg:
        return "권한 부족 또는 접근 제한 가능성"
    if "404" in msg:
        return "엔드포인트 또는 요청 경로 오류 가능성"
    if "429" in msg or "rate limit" in msg or "too many requests" in msg:
        return "호출 횟수 제한 또는 속도 제한 가능성"
    if "500" in msg or "502" in msg or "503" in msg or "504" in msg:
        return "서버 일시 오류 가능성"
    if "timeout" in msg or "timed out" in msg:
        return "응답 시간 초과 가능성"
    if "connection" in msg or "network" in msg or "dns" in msg:
        return "네트워크 연결 문제 가능성"
    if "context length" in msg or "maximum context length" in msg or "token" in msg:
        return "입력 텍스트 길이 초과 가능성"
    if "encoding" in msg or "codec" in msg or "unicode" in msg:
        return "파일 인코딩 문제 가능성"

    return "원인 분류 불가, 상세 예외 확인 필요"


# =========================================================
# 응답 형식 검증/재요청용
# =========================================================
_MIN_UNRELATED_MEANINGFUL_LINES = 1
_MAX_REPAIR_REASK = 2


def _extract_candidate_count(txt_content: str) -> int:
    """Step 4 프롬프트에서 선언된 후보 수를 읽는다.

    현행 형식인 ``후보_시그널수``를 우선하고, 과거 형식인
    ``변경점_라인수``를 호환용으로 지원한다. 선언값이 없으면 -1을 반환한다.
    """
    for pattern in (
        r"후보_시그널수\s*:\s*(\d+)",
        r"변경점_라인수\s*:\s*(\d+)",
    ):
        m = re.search(pattern, txt_content or "")
        if not m:
            continue
        try:
            return int(m.group(1))
        except Exception:
            continue
    return -1


def _candidate_count_for_inputs(case_inputs: List[Path]) -> int:
    """안전 분할 입력 전체의 후보 수 합계를 반환한다.

    하나라도 선언 후보 수를 읽지 못하면 -1을 반환하여 기존의 엄격 검증을 유지한다.
    """
    total = 0
    for input_path in case_inputs:
        try:
            content = input_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return -1
        count = _extract_candidate_count(content)
        if count < 0:
            return -1
        total += count
    return total


def _build_zero_candidate_answer(output_path: Path) -> str:
    """후보 0개 케이스의 표준 정상 무결과 답변을 생성한다."""
    return (
        f"{output_path.name}\n\n"
        "연관 있는 메세지\n"
        "연관 있는 메세지 없음\n\n"
        "연관 없는 메세지\n"
    )

def _get_unrelated_section_tail(answer: str) -> str:
    if not answer:
        return ""

    m = re.search(r"연관\s*없는\s*메세지\s*\n", answer)
    if not m:
        m = re.search(r"연관\s*없는\s*메세지\s*[:：]\s*\n?", answer)

    if not m:
        return ""

    return answer[m.end():]


def is_missing_unrelated_section(
    answer: str,
    source_prompt: str,
    candidate_count: int | None = None,
) -> bool:
    if not answer:
        return True

    if candidate_count is None:
        candidate_count = _extract_candidate_count(source_prompt)
    if candidate_count == 0:
        return False

    if "연관 있는 메세지 없음" not in answer:
        return False

    tail = _get_unrelated_section_tail(answer)
    if not tail.strip():
        return True

    meaningful_lines = [ln.strip() for ln in tail.splitlines() if ln.strip()]
    if len(meaningful_lines) < _MIN_UNRELATED_MEANINGFUL_LINES:
        return True

    return False


def build_repair_instruction() -> str:
    return f"""
[재요청 - 형식 누락 수정]
이전 답변은 "연관 있는 메세지 없음"을 출력했지만, "연관 없는 메세지" 섹션이 누락되었거나 비어 있습니다.

반드시 아래 규칙을 지켜 전체를 다시 출력하세요.

- txt 명칭을 맨 위에 출력
- 다른 별도의 설명은 적지 말 것
- "연관 있는 메세지 없음"을 출력하는 경우에도 반드시 아래를 포함:
  1) "연관 없는 메세지" 제목
  2) 그 아래에 최소 {_MIN_UNRELATED_MEANINGFUL_LINES}줄 이상의 항목을 작성
""".strip()


# =========================================================
# 메세지별 판별 / 패턴
# =========================================================
_TIME_PREFIX_RE = re.compile(
    r"^\s*\d+(?:\.\d+)?sec(?:\s+CH\d+)?\s+",
    flags=re.IGNORECASE,
)


def is_messagewise_output_file(output_path: Path) -> bool:
    return "시간별" not in output_path.stem


def _normalize_related_line_for_messagewise_dedup(line: str) -> str | None:
    s = (line or "").strip()
    if not s:
        return None

    s = _TIME_PREFIX_RE.sub("", s).strip()
    if not s:
        return None

    if ":" not in s:
        return None

    if not re.match(r"^\w+\s*:\s*\w+\b", s):
        return None

    return s


def _convert_related_message_line_remove_time_prefix(line: str) -> str:
    original = line

    s = (line or "").strip()
    if not s:
        return original

    converted = _TIME_PREFIX_RE.sub("", s).strip()
    if not converted:
        return original

    if ":" not in converted:
        return original

    if not re.match(r"^\w+\s*:\s*\w+\b", converted):
        return original

    return converted


def _split_answer_into_related_and_unrelated(answer: str):
    normalized = answer.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")

    unrelated_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*연관\s*없는\s*메세지\s*(?:[:：]\s*)?$", line):
            unrelated_idx = i
            break

    if unrelated_idx is None:
        return lines, []

    return lines[:unrelated_idx], lines[unrelated_idx:]


def remove_time_prefix_related_messages_only_for_messagewise(answer: str) -> str:
    if not answer:
        return ""

    normalized = answer.replace("\r\n", "\n").replace("\r", "\n")
    original_endswith_newline = normalized.endswith("\n")

    if "연관 있는 메세지 없음" in normalized:
        return answer

    related_part, unrelated_part = _split_answer_into_related_and_unrelated(normalized)

    converted_related = []
    for line in related_part:
        if not line.strip():
            converted_related.append(line)
            continue

        converted_related.append(_convert_related_message_line_remove_time_prefix(line))

    out = "\n".join(converted_related + unrelated_part)

    if original_endswith_newline:
        return out.rstrip() + "\n"
    return out.rstrip()


def deduplicate_related_messages_only_for_messagewise(answer: str) -> str:
    if not answer:
        return ""

    normalized = answer.replace("\r\n", "\n").replace("\r", "\n")
    original_endswith_newline = normalized.endswith("\n")

    if "연관 있는 메세지 없음" in normalized:
        return answer

    related_part, unrelated_part = _split_answer_into_related_and_unrelated(normalized)

    deduped_related = []
    seen_norm_lines = set()

    for line in related_part:
        stripped = line.strip()

        if not stripped:
            deduped_related.append(line)
            continue

        norm = _normalize_related_line_for_messagewise_dedup(line)

        if norm is None:
            deduped_related.append(line)
            continue

        if norm in seen_norm_lines:
            continue

        seen_norm_lines.add(norm)
        deduped_related.append(line)

    out = "\n".join(deduped_related + unrelated_part)

    if original_endswith_newline:
        return out.rstrip() + "\n"
    return out.rstrip()


# =========================================================
# GPT 클라이언트 생성
# =========================================================
def create_gpt_client(base_url: str, api_key: str, api_version: str, project_id: str):
    if AzureOpenAI is None:
        raise ImportError("openai 패키지가 설치되지 않았습니다. py -m pip install openai 필요")

    headers = {}
    if project_id:
        headers["X-Project-Id"] = project_id

    client = AzureOpenAI(
        azure_endpoint=base_url,
        api_key=api_key,
        api_version=api_version,
        default_headers=headers if headers else None,
    )
    return client


# =========================================================
# Gemini 응답 텍스트 추출
# =========================================================
def _extract_gemini_text(resp_json: dict) -> str:
    candidates = resp_json.get("candidates") or []
    if candidates:
        content = (candidates[0] or {}).get("content") or {}
        parts = content.get("parts") or []
        texts = []
        for p in parts:
            t = p.get("text")
            if t:
                texts.append(t)
        if texts:
            return "".join(texts)

    for key in ("outputText", "text", "result"):
        if isinstance(resp_json.get(key), str):
            return resp_json[key]

    return json.dumps(resp_json, ensure_ascii=False)


# =========================================================
# API 호출
# =========================================================
def ask_gpt_with_txt_content(
    txt_content: str,
    gpt_model: str,
    base_url: str,
    api_key: str,
    project_id: str,
    api_version: str,
    use_system_message: bool,
    system_message: str,
) -> str:
    client = create_gpt_client(
        base_url=base_url,
        api_key=api_key,
        api_version=api_version,
        project_id=project_id,
    )

    messages = []
    if use_system_message and system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": txt_content})

    completion = client.chat.completions.create(
        model=gpt_model,
        messages=messages,
    )

    content = completion.choices[0].message.content
    return content if content is not None else ""


def ask_gemini_with_txt_content(
    txt_content: str,
    gemini_model: str,
    gemini_stream_option: str,
    base_url: str,
    api_key: str,
    project_id: str,
    use_system_message: bool,
    system_message: str,
) -> str:
    if requests is None:
        raise ImportError("requests 패키지가 설치되지 않았습니다. py -m pip install requests 필요")

    url = f"{base_url}/models/{gemini_model}:{gemini_stream_option}"
    params = {"key": api_key}

    headers = {"Content-Type": "application/json"}
    if project_id:
        headers["X-Project-Id"] = project_id

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": txt_content}]
            }
        ]
    }

    if use_system_message and system_message:
        payload["systemInstruction"] = {
            "parts": [{"text": system_message}]
        }

    r = requests.post(url, params=params, headers=headers, json=payload, timeout=120)
    r.raise_for_status()

    resp_json = r.json()
    return _extract_gemini_text(resp_json)


def ask_ai_with_txt_content(txt_content: str, config) -> str:
    provider = config.ai_provider.lower()

    if provider == "gpt":
        return ask_gpt_with_txt_content(
            txt_content=txt_content,
            gpt_model=config.gpt_model,
            base_url=config.base_url,
            api_key=config.api_key,
            project_id=config.project_id,
            api_version=config.api_version,
            use_system_message=config.use_system_message,
            system_message=config.system_message,
        )

    if provider == "gemini":
        return ask_gemini_with_txt_content(
            txt_content=txt_content,
            gemini_model=config.gemini_model,
            gemini_stream_option=config.gemini_stream_option,
            base_url=config.base_url,
            api_key=config.api_key,
            project_id=config.project_id,
            use_system_message=config.use_system_message,
            system_message=config.system_message,
        )

    raise ValueError(f"지원하지 않는 ai_provider: {provider}")


# =========================================================
# 단일 파일 처리
# =========================================================
def process_one_file(
    input_path: Path,
    output_path: Path,
    current_idx: int,
    total_count: int,
    config,
):
    percent = (current_idx / total_count) * 100
    print(f"\n[{current_idx}/{total_count} | {percent:.1f}%] 처리 시작: {input_path.name}")

    try:
        txt_content = input_path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception as e:
        reason = classify_error_message(e)
        error_log_path = write_input_error_log(
            input_path=input_path,
            stage="파일 읽기",
            reason=reason,
            exc=e,
            retry_count=None,
        )
        print(f"[{current_idx}/{total_count}] 파일 읽기 실패: {input_path.name}")
        print(f"[{current_idx}/{total_count}] 실패 기록 저장: {error_log_path.name}")
        return False, reason

    candidate_count = _extract_candidate_count(txt_content)
    if candidate_count == 0:
        try:
            answer = _build_zero_candidate_answer(output_path)
            valid_ok, valid_reason = validate_answer_text(
                answer,
                source_prompt=txt_content,
                context=output_path.name,
                candidate_count=0,
            )
            if not valid_ok:
                raise ValueError(f"후보 0개 결과 형식 검증 실패: {valid_reason}")
            atomic_write_text(output_path, answer, encoding="utf-8")
            saved_ok, saved_reason = validate_output_file_for_input(
                input_path,
                output_path,
                allow_existing_input_error=True,
            )
            if not saved_ok:
                raise ValueError(f"후보 0개 저장 결과 검증 실패: {saved_reason}")
            write_completion_marker(output_path, source_path=input_path, kind="zero-candidate")
            remove_input_error_log_if_exists(input_path)
            print(
                f"[{current_idx}/{total_count}] [NO-CANDIDATE] "
                f"후보 시그널 0개 -> API 호출 생략, 정상 무결과 저장: {output_path.name}"
            )
            return True, "성공(후보 0개/API 생략)"
        except Exception as e:
            reason = f"후보 0개 로컬 결과 생성 실패: {e}"
            error_log_path = write_input_error_log(
                input_path=input_path,
                stage="후보 0개 정상 무결과 생성",
                reason=reason,
                exc=e,
                retry_count=None,
            )
            print(f"[{current_idx}/{total_count}] {reason}")
            print(f"[{current_idx}/{total_count}] 실패 기록 저장: {error_log_path.name}")
            return False, reason

    last_exception = None
    last_reason = ""

    for attempt in range(1, config.max_retry + 1):
        try:
            answer = ask_ai_with_txt_content(txt_content, config) or ""

            if is_missing_unrelated_section(answer, txt_content):
                for k in range(1, _MAX_REPAIR_REASK + 1):
                    print(
                        f"[{current_idx}/{total_count}] [WARN] "
                        f"응답 형식 누락 감지 -> 보정 재요청 {k}/{_MAX_REPAIR_REASK}: {input_path.name}"
                    )

                    repair_prompt = txt_content + "\n\n" + build_repair_instruction()
                    answer2 = ask_ai_with_txt_content(repair_prompt, config) or ""
                    answer = answer2

                    if not is_missing_unrelated_section(answer, txt_content):
                        break

            if is_messagewise_output_file(output_path):
                answer = remove_time_prefix_related_messages_only_for_messagewise(answer)
                answer = deduplicate_related_messages_only_for_messagewise(answer)

            answer = strip_definition_description_blocks(answer)

            valid_ok, valid_reason = validate_answer_text(
                answer,
                source_prompt=txt_content,
                context=output_path.name,
            )
            if not valid_ok:
                raise ValueError(f"결과 형식 검증 실패: {valid_reason}")

            atomic_write_text(output_path, answer, encoding="utf-8")

            saved_ok, saved_reason = validate_output_file_for_input(
                input_path,
                output_path,
                allow_existing_input_error=True,
            )
            if not saved_ok:
                raise ValueError(f"저장 결과 검증 실패: {saved_reason}")

            write_completion_marker(output_path, source_path=input_path, kind="split")
            remove_input_error_log_if_exists(input_path)
            print(f"[{current_idx}/{total_count}] 저장 완료: {output_path.name}")
            return True, "성공"

        except Exception as e:
            last_exception = e
            last_reason = classify_error_message(e)

            print(
                f"[{current_idx}/{total_count}] "
                f"재시도 {attempt}/{config.max_retry} 실패: {input_path.name} | {last_reason}"
            )

            if attempt < config.max_retry:
                time.sleep(config.retry_wait_seconds)

    error_log_path = write_input_error_log(
        input_path=input_path,
        stage="API 호출 또는 결과 저장",
        reason=last_reason,
        exc=last_exception,
        retry_count=config.max_retry,
    )

    print(f"[{current_idx}/{total_count}] 최종 실패: {input_path.name}")
    print(f"[{current_idx}/{total_count}] 실패 기록 저장: {error_log_path.name}")

    return False, last_reason


# =========================================================
# 분할 결과 병합용
# =========================================================
_SPLIT_SUFFIX_RE = re.compile(r"^(?P<base>.+)_(?P<suffix>[a-z]+)\.txt$", re.IGNORECASE)


def _suffix_to_index(s: str) -> int:
    s = (s or "").lower().strip()
    n = 0
    for ch in s:
        if not ("a" <= ch <= "z"):
            return -1
        n = n * 26 + (ord(ch) - ord("a") + 1)
    return n - 1


def _read_text_any(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _split_answer_sections_for_merge(answer: str):
    """AI 표현 차이와 무관하게 제목 줄을 데이터에서 분리한다."""
    normalized = (answer or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if not lines:
        return "", [], []
    title_line = lines[0].strip()
    body_lines = lines[1:]
    unrelated_idx = None
    for i, line in enumerate(body_lines):
        if re.match(r"^\s*연관\s*없는\s*메세지\s*(?:[:：]\s*)?$", line.strip()):
            unrelated_idx = i
            break
    if unrelated_idx is None:
        related_part, unrelated_part = body_lines, []
    else:
        related_part, unrelated_part = body_lines[:unrelated_idx], body_lines[unrelated_idx + 1:]

    related_lines: List[str] = []
    for line in related_part:
        text = line.strip()
        if not text:
            continue
        if re.fullmatch(r"연관\s*있는\s*메세지", text):
            continue
        if re.fullmatch(r"연관\s*있는\s*메세지\s*없음", text):
            continue
        if _normalize_unrelated_msgsig_key(text) is not None:
            related_lines.append(text)

    unrelated_lines: List[str] = []
    for line in unrelated_part:
        text = line.strip()
        if text and _normalize_unrelated_msgsig_key(text) is not None:
            unrelated_lines.append(text)
    return title_line, related_lines, unrelated_lines


def _is_actual_related_message_line(line: str) -> bool:
    s = (line or "").strip()
    return bool(s and _normalize_unrelated_msgsig_key(s) is not None)


def _normalize_unrelated_msgsig_key(line: str) -> str | None:
    s = (line or "").strip()
    if not s:
        return None
    m = re.match(r"^(?P<msg>[A-Za-z_][\w\-]*)\s*:\s*(?P<sig>[A-Za-z_][\w\-]*)\b", s, re.IGNORECASE)
    if not m:
        return None
    return f"{m.group('msg')}:{m.group('sig')}"


def _pick_more_informative_line(old_line: str, new_line: str) -> str:
    old_s = (old_line or "").strip()
    new_s = (new_line or "").strip()
    return new_s if len(new_s) > len(old_s) else old_s


def merge_messagewise_answers(files: List[Path]) -> str:
    title = ""
    related_map: Dict[str, str] = {}
    related_order: List[str] = []
    unrelated_map: Dict[str, str] = {}
    unrelated_order: List[str] = []

    for f in files:
        title_line, related_lines, unrelated_lines = _split_answer_sections_for_merge(_read_text_any(f))
        if not title and title_line:
            title = title_line
        for s in related_lines:
            key = _normalize_unrelated_msgsig_key(s)
            if key is None:
                continue
            if key not in related_map:
                related_order.append(key)
                related_map[key] = s
            else:
                related_map[key] = _pick_more_informative_line(related_map[key], s)
        for s in unrelated_lines:
            key = _normalize_unrelated_msgsig_key(s)
            if key is None:
                continue
            if key not in unrelated_map:
                unrelated_order.append(key)
                unrelated_map[key] = s
            else:
                unrelated_map[key] = _pick_more_informative_line(unrelated_map[key], s)

    # 어느 조각에서든 관련으로 판단되면 관련을 우선한다.
    for key in list(unrelated_map):
        if key in related_map:
            unrelated_map.pop(key, None)
            if key in unrelated_order:
                unrelated_order.remove(key)

    out_lines: List[str] = []
    if title:
        out_lines.extend([title, ""])
    out_lines.append("연관 있는 메세지")
    if related_order:
        out_lines.extend(related_map[key] for key in related_order)
    else:
        out_lines.append("연관 있는 메세지 없음")
    out_lines.extend(["", "연관 없는 메세지"])
    out_lines.extend(unrelated_map[key] for key in unrelated_order if key in unrelated_map)
    return "\n".join(out_lines).rstrip() + "\n"


def merge_timewise_answers(files: List[Path]) -> str:
    title = ""
    related_result = []
    unrelated_result = []

    for f in files:
        text = _read_text_any(f)
        title_line, related_lines, unrelated_lines = _split_answer_sections_for_merge(text)

        if not title and title_line:
            title = title_line

        for line in related_lines:
            s = line.rstrip()
            if not s:
                continue
            related_result.append(s)

        for line in unrelated_lines:
            s = line.rstrip()
            if not s:
                continue
            unrelated_result.append(s)

    out_lines = []
    if title:
        out_lines.append(title)
        out_lines.append("")

    if related_result:
        out_lines.extend(related_result)
    else:
        out_lines.append("연관 있는 메세지 없음")

    if unrelated_result:
        out_lines.append("")
        out_lines.append("연관 없는 메세지")
        out_lines.extend(unrelated_result)

    return "\n".join(out_lines).rstrip() + "\n"


# =========================================================
# 케이스 단위 처리 유틸
# =========================================================
def _get_split_base_and_suffix_from_input_name(filename: str) -> Tuple[str, str | None]:
    m = _SPLIT_SUFFIX_RE.match(filename)
    if not m:
        stem = Path(filename).stem
        return stem, None
    return m.group("base"), m.group("suffix").lower()


def _normalize_retry_case_stem(case_base: str) -> str:
    """Step 5/6 사이에서 공유할 케이스 식별자 stem을 만든다."""
    stem = Path(str(case_base or "")).stem.strip()
    for prefix in ("AI문의용_", "AI답변_", "AI결과판단_분류_", "AI결과판단_"):
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
            break
    return stem.strip()


def make_step5_retry_case_key(output_type: str, case_base: str) -> str:
    return f"{str(output_type or '').strip().casefold()}::{_normalize_retry_case_stem(case_base).casefold()}"


def register_step5_retry_case_targets(config, output_type: str, case_bases: List[str]) -> None:
    """
    retry_failed_only에서 Step 5가 실제로 선정한 케이스를 config에 누적한다.
    같은 config 객체로 뒤이어 실행되는 Step 6이 이 목록을 재처리 대상으로 사용한다.
    """
    if not getattr(config, "retry_failed_only", False):
        return
    current = list(getattr(config, "step_5_retry_case_keys", []) or [])
    seen = {str(x).casefold() for x in current}
    for case_base in case_bases:
        key = make_step5_retry_case_key(output_type, case_base)
        if key and key not in seen:
            current.append(key)
            seen.add(key)
    setattr(config, "step_5_retry_case_keys", current)


def build_case_groups(input_files: List[Path]) -> Dict[str, List[Path]]:
    grouped: Dict[str, List[Path]] = {}
    for p in input_files:
        base, suffix = _get_split_base_and_suffix_from_input_name(p.name)
        grouped.setdefault(base, []).append(p)

    for base in grouped.keys():
        grouped[base].sort(
            key=lambda x: (_suffix_to_index(_get_split_base_and_suffix_from_input_name(x.name)[1] or ""), x.name)
        )

    return grouped


def get_expected_output_path_for_input(output_dir: Path, input_path: Path) -> Path:
    return output_dir / make_output_filename(input_path.name)


def get_merged_output_path_for_case(output_dir: Path, case_base: str) -> Path:
    return output_dir / f"{case_base.replace('AI문의용_', 'AI답변_', 1)}.txt"


def make_case_source_manifest_path(output_dir: Path, case_base: str) -> Path:
    merged_output = get_merged_output_path_for_case(output_dir, case_base)
    marker_dir = get_completion_marker_dir(merged_output)
    return marker_dir / f"{merged_output.name}.sources.json"


def remove_case_source_manifest_if_exists(output_dir: Path, case_base: str) -> None:
    path = make_case_source_manifest_path(output_dir, case_base)
    try:
        if path.exists():
            path.unlink()
            print(f"[CLEANUP] 케이스 입력 manifest 삭제: {path.name}")
        tmp_path = path.with_name(path.name + '.tmp')
        if tmp_path.exists():
            tmp_path.unlink()
    except Exception as exc:
        print(f"[WARN] 케이스 입력 manifest 삭제 실패: {path} ({exc})")


def write_case_source_manifest(
    case_base: str,
    case_inputs: List[Path],
    output_dir: Path,
) -> Path:
    merged_output = get_merged_output_path_for_case(output_dir, case_base)
    path = make_case_source_manifest_path(output_dir, case_base)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'status': 'OK',
        'case_base': case_base,
        'merged_output': merged_output.name,
        'merged_size': merged_output.stat().st_size if merged_output.exists() else None,
        'merged_sha256': _sha256_file(merged_output) if merged_output.exists() else '',
        'source_count': len(case_inputs),
        'candidate_count': _candidate_count_for_inputs(case_inputs),
        'sources': [
            {
                'name': src.name,
                'size': src.stat().st_size if src.exists() else None,
                'sha256': _sha256_file(src) if src.exists() else '',
            }
            for src in case_inputs
        ],
        'created_at': datetime.now().isoformat(timespec='seconds'),
    }
    tmp_path = path.with_name(path.name + '.tmp')
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp_path.replace(path)
    return path


def validate_case_source_manifest(
    case_base: str,
    case_inputs: List[Path],
    output_dir: Path,
) -> Tuple[bool, str]:
    path = make_case_source_manifest_path(output_dir, case_base)
    if not path.exists():
        return False, f"케이스 입력 manifest 없음: {path.name}"
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        return False, f"케이스 입력 manifest 읽기 실패: {path.name} ({exc})"

    if not isinstance(data, dict) or data.get('status') != 'OK':
        return False, f"케이스 입력 manifest 상태 오류: {path.name}"
    if data.get('case_base') != case_base:
        return False, f"케이스 입력 manifest case 불일치: {case_base}"

    merged_output = get_merged_output_path_for_case(output_dir, case_base)
    if not merged_output.exists():
        return False, f"최종 병합본 없음: {merged_output.name}"
    if data.get('merged_output') != merged_output.name:
        return False, f"manifest 최종 출력명 불일치: {merged_output.name}"
    if int(data.get('merged_size', -1)) != int(merged_output.stat().st_size):
        return False, f"manifest 최종 출력 크기 불일치: {merged_output.name}"
    if str(data.get('merged_sha256', '')) != _sha256_file(merged_output):
        return False, f"manifest 최종 출력 해시 불일치: {merged_output.name}"

    expected = list(data.get('sources') or [])
    if len(expected) != len(case_inputs):
        return False, f"Step 4 안전 분할 개수 변경 감지: {len(expected)} -> {len(case_inputs)}"

    by_name = {str(item.get('name', '')): item for item in expected if isinstance(item, dict)}
    for src in case_inputs:
        item = by_name.get(src.name)
        if item is None:
            return False, f"Step 4 후보 프롬프트 구성 변경 감지: {src.name}"
        if not src.exists():
            return False, f"현재 후보 프롬프트 없음: {src.name}"
        if int(item.get('size', -1)) != int(src.stat().st_size):
            return False, f"Step 4 후보 프롬프트 크기 변경 감지: {src.name}"
        if str(item.get('sha256', '')) != _sha256_file(src):
            return False, f"Step 4 후보 프롬프트 내용 변경 감지: {src.name}"

    return True, '정상(최종 결과+현재 안전 분할 입력 일치)'


def get_split_output_paths_for_case(case_inputs: List[Path], output_dir: Path) -> List[Path]:
    return [get_expected_output_path_for_input(output_dir, input_path) for input_path in case_inputs]


def is_case_completed(case_base: str, case_inputs: List[Path], output_dir: Path) -> bool:
    merged_output_path = get_merged_output_path_for_case(output_dir, case_base)
    case_candidate_count = _candidate_count_for_inputs(case_inputs)
    merged_ok, _merged_reason = validate_output_file_standalone(
        merged_output_path,
        context="최종 병합본",
        candidate_count=case_candidate_count,
    )
    if not merged_ok:
        return False

    manifest_ok, _manifest_reason = validate_case_source_manifest(case_base, case_inputs, output_dir)
    if not manifest_ok:
        return False

    for input_path in case_inputs:
        if has_input_error_log(input_path):
            return False

        split_output_path = get_expected_output_path_for_input(output_dir, input_path)
        if has_tmp_output(split_output_path):
            return False

    return True


def is_case_incomplete(case_base: str, case_inputs: List[Path], output_dir: Path) -> Tuple[bool, List[str]]:
    reasons = []

    merged_output_path = get_merged_output_path_for_case(output_dir, case_base)
    case_candidate_count = _candidate_count_for_inputs(case_inputs)
    merged_ok, merged_reason = validate_output_file_standalone(
        merged_output_path,
        context="최종 병합본",
        candidate_count=case_candidate_count,
    )
    manifest_ok, manifest_reason = validate_case_source_manifest(case_base, case_inputs, output_dir)

    input_error_exists = False
    split_problem_exists = False

    for input_path in case_inputs:
        if has_input_error_log(input_path):
            reasons.append(f".error 존재: {input_path.name}")
            input_error_exists = True

        split_output_path = get_expected_output_path_for_input(output_dir, input_path)

        if merged_ok and not split_output_path.exists() and not has_tmp_output(split_output_path):
            continue

        split_ok, split_reason = validate_output_file_for_input(input_path, split_output_path)
        if not split_ok:
            reasons.append(split_reason)
            split_problem_exists = True

    if merged_ok and manifest_ok and not input_error_exists and not split_problem_exists:
        return False, []

    if not merged_ok:
        reasons.append(merged_reason)
    if not manifest_ok:
        reasons.append(manifest_reason)

    deduped = []
    for reason in reasons:
        if reason not in deduped:
            deduped.append(reason)

    return (len(deduped) > 0), deduped


def cleanup_case_outputs(case_base: str, case_inputs: List[Path], output_dir: Path) -> None:
    merged_output_path = get_merged_output_path_for_case(output_dir, case_base)
    remove_case_source_manifest_if_exists(output_dir, case_base)

    for input_path in case_inputs:
        split_output_path = get_expected_output_path_for_input(output_dir, input_path)
        remove_tmp_output_if_exists(split_output_path)
        remove_completion_marker_if_exists(split_output_path)
        try:
            if split_output_path.exists():
                split_output_path.unlink()
                print(f"[RETRY] 기존 split 출력 삭제: {split_output_path.name}")
        except Exception as e:
            print(f"[WARN] split 출력 삭제 실패: {split_output_path} ({e})")

    remove_tmp_output_if_exists(merged_output_path)
    remove_completion_marker_if_exists(merged_output_path)
    try:
        if merged_output_path.exists():
            merged_output_path.unlink()
            print(f"[RETRY] 기존 최종 병합본 삭제: {merged_output_path.name}")
    except Exception as e:
        print(f"[WARN] 최종 병합본 삭제 실패: {merged_output_path} ({e})")


def get_retry_tail_start_index(case_inputs: List[Path], output_dir: Path) -> int | None:
    first_problem_idx = None

    for idx, input_path in enumerate(case_inputs):
        split_output_path = get_expected_output_path_for_input(output_dir, input_path)
        ok, reason = validate_output_file_for_input(input_path, split_output_path)
        if not ok:
            first_problem_idx = idx
            print(f"[RETRY][CHECK] 문제 split 감지: {split_output_path.name} | {reason}")
            break

    if first_problem_idx is None:
        return None

    return max(0, first_problem_idx - 1)


def cleanup_retry_tail_outputs(
    case_base: str,
    case_inputs: List[Path],
    output_dir: Path,
    start_index: int,
) -> List[Path]:
    merged_output_path = get_merged_output_path_for_case(output_dir, case_base)
    retry_inputs = case_inputs[start_index:]

    remove_case_source_manifest_if_exists(output_dir, case_base)
    remove_tmp_output_if_exists(merged_output_path)
    remove_completion_marker_if_exists(merged_output_path)
    try:
        if merged_output_path.exists():
            merged_output_path.unlink()
            print(f"[RETRY] 기존 최종 병합본 삭제: {merged_output_path.name}")
    except Exception as e:
        print(f"[WARN] 최종 병합본 삭제 실패: {merged_output_path} ({e})")

    for input_path in retry_inputs:
        split_output_path = get_expected_output_path_for_input(output_dir, input_path)
        remove_tmp_output_if_exists(split_output_path)
        remove_completion_marker_if_exists(split_output_path)
        try:
            if split_output_path.exists():
                split_output_path.unlink()
                print(f"[RETRY] tail split 출력 삭제: {split_output_path.name}")
        except Exception as e:
            print(f"[WARN] tail split 출력 삭제 실패: {split_output_path} ({e})")

    kept_count = max(0, start_index)
    print(
        f"[RETRY] split 재실행 범위: {start_index + 1}/{len(case_inputs)}부터 "
        f"{len(case_inputs)}/{len(case_inputs)}까지 | 앞쪽 유지 {kept_count}개"
    )
    return retry_inputs


def prepare_completed_answer_pass_inputs(
    case_base: str,
    case_inputs: List[Path],
    output_dir: Path,
) -> List[Path]:
    merged_output_path = get_merged_output_path_for_case(output_dir, case_base)
    remove_case_source_manifest_if_exists(output_dir, case_base)
    remove_tmp_output_if_exists(merged_output_path)
    remove_completion_marker_if_exists(merged_output_path)
    try:
        if merged_output_path.exists():
            merged_output_path.unlink()
            print(f"[PASS-EXISTING] 기존 최종 병합본 삭제 후 재병합 예정: {merged_output_path.name}")
    except Exception as e:
        print(f"[WARN] 최종 병합본 삭제 실패: {merged_output_path} ({e})")

    process_inputs: List[Path] = []
    kept_count = 0

    for input_path in case_inputs:
        split_output_path = get_expected_output_path_for_input(output_dir, input_path)
        ok, reason = validate_output_file_for_input(input_path, split_output_path)
        if ok:
            ensure_completion_marker_for_valid_output(input_path, split_output_path, kind="split")
            kept_count += 1
            print(f"[PASS-EXISTING] 완료 split 인정: {split_output_path.name}")
            continue

        print(f"[PASS-EXISTING] 추가 생성 대상 split: {split_output_path.name} | {reason}")
        remove_tmp_output_if_exists(split_output_path)
        remove_completion_marker_if_exists(split_output_path)
        try:
            if split_output_path.exists():
                split_output_path.unlink()
                print(f"[PASS-EXISTING] 불완전 split 삭제: {split_output_path.name}")
        except Exception as e:
            print(f"[WARN] 불완전 split 삭제 실패: {split_output_path} ({e})")
        process_inputs.append(input_path)

    print(
        f"[PASS-EXISTING] split 처리 계획: 전체 {len(case_inputs)}개 / "
        f"기존 인정 {kept_count}개 / 추가 생성 {len(process_inputs)}개"
    )
    return process_inputs


def delete_split_outputs_for_case(case_inputs: List[Path], output_dir: Path) -> None:
    """
    병합 후 split 출력 파일 삭제.
    단, split이 1개뿐인 케이스는 split 출력 경로와 최종 병합본 경로가 같아질 수 있으므로 삭제하지 않는다.
    """
    if len(case_inputs) < 2:
        print("[CLEANUP] split 1개 케이스는 최종본 보호를 위해 삭제하지 않음")
        return

    for p in get_split_output_paths_for_case(case_inputs, output_dir):
        remove_tmp_output_if_exists(p)
        remove_completion_marker_if_exists(p)
        try:
            if p.exists():
                p.unlink()
                print(f"[CLEANUP] 분할 파일 삭제: {p.name}")
        except Exception as e:
            print(f"[WARN] 분할 파일 삭제 실패: {p} ({e})")


def cleanup_completed_cases_splits(input_dir: Path, output_dir: Path, keep_split_files: bool) -> None:
    if keep_split_files:
        return

    input_files = sorted(
        [
            p for p in input_dir.glob("AI문의용_*.txt")
            if p.is_file()
            and not p.name.endswith(".error.txt")
            and not p.name.endswith(".warning.txt")
        ]
    )
    if not input_files:
        return

    case_groups = build_case_groups(input_files)
    cleaned_case_count = 0

    for case_base, case_inputs in sorted(case_groups.items()):
        if not is_case_completed(case_base, case_inputs, output_dir):
            continue

        split_paths = [p for p in get_split_output_paths_for_case(case_inputs, output_dir) if p.exists()]
        if not split_paths:
            continue

        # split이 1개뿐인 케이스는 최종본과 경로가 같을 수 있으므로 정리 대상에서 제외
        if len(case_inputs) < 2:
            continue

        delete_split_outputs_for_case(case_inputs, output_dir)
        cleaned_case_count += 1

    if cleaned_case_count > 0:
        print(f"[CLEANUP] 완료 케이스 split 정리 수: {cleaned_case_count}")


def _extract_candidate_pairs_from_prompt_text(text: str) -> List[Tuple[str, str]]:
    section_match = re.search(r"(?ms)^\[후보 시그널\]\s*\n(?P<body>.*?)(?:\n후보_시그널수\s*:|\Z)", text or "")
    body = section_match.group('body') if section_match else ''
    pairs: List[Tuple[str, str]] = []
    seen: set[Tuple[str, str]] = set()
    for m in re.finditer(
        r"(?m)^(?P<msg>[A-Za-z_][\w\-]*)\s*:\s*(?P<sig>[A-Za-z_][\w\-]*)\s*\([^\r\n]*\)\s*$",
        body,
        re.IGNORECASE,
    ):
        key = (m.group('msg'), m.group('sig'))
        normalized = (key[0].upper(), key[1].upper())
        if normalized not in {(a.upper(), b.upper()) for a, b in seen}:
            seen.add(key)
            pairs.append(key)
    return pairs


def _line_to_item(line: str) -> dict | None:
    m = re.match(
        r"^(?P<msg>[A-Za-z_][\w\-]*)\s*:\s*(?P<sig>[A-Za-z_][\w\-]*)\b(?P<tail>.*)$",
        (line or '').strip(),
        re.IGNORECASE,
    )
    if not m:
        return None
    tail = (m.group('tail') or '').strip()
    reason_match = re.search(r"//\s*사유\s*:\s*(.*)$", tail)
    return {
        'message': m.group('msg'),
        'signal': m.group('sig'),
        'reason': reason_match.group(1).strip() if reason_match else '',
        'raw_line': (line or '').strip(),
    }




def _normalize_msgsig_pair(message: str, signal: str) -> Tuple[str, str]:
    """Message:Signal 비교용 정규화. 대소문자/주변 공백 차이로 인한 오탐 삭제를 방지한다."""
    return ((message or '').strip().upper(), (signal or '').strip().upper())


def _collect_candidate_pairs_from_prompts(case_inputs: List[Path]) -> List[Tuple[str, str]]:
    """Step 4 후보 프롬프트에서 후보 Message:Signal을 중복 없이 수집한다."""
    candidate_pairs: List[Tuple[str, str]] = []
    seen_candidates: set[Tuple[str, str]] = set()
    for prompt_path in case_inputs:
        prompt_text = prompt_path.read_text(encoding='utf-8-sig', errors='replace')
        for pair in _extract_candidate_pairs_from_prompt_text(prompt_text):
            norm = _normalize_msgsig_pair(pair[0], pair[1])
            if norm not in seen_candidates:
                seen_candidates.add(norm)
                candidate_pairs.append(pair)
    return candidate_pairs


def _rebuild_answer_text_from_sections(
    title: str,
    related_lines: List[str],
    unrelated_lines: List[str],
    is_messagewise: bool,
) -> str:
    """후보 외 항목 제거 후 표준 답변 형식으로 재구성한다."""
    out_lines: List[str] = []
    if title:
        out_lines.extend([title, ""])

    if is_messagewise:
        out_lines.append("연관 있는 메세지")
        if related_lines:
            out_lines.extend(related_lines)
        else:
            out_lines.append("연관 있는 메세지 없음")
        out_lines.extend(["", "연관 없는 메세지"])
        out_lines.extend(unrelated_lines)
    else:
        if related_lines:
            out_lines.extend(related_lines)
        else:
            out_lines.append("연관 있는 메세지 없음")
        out_lines.extend(["", "연관 없는 메세지"])
        out_lines.extend(unrelated_lines)

    return "\n".join(out_lines).rstrip() + "\n"


def _answer_result_root_for_output_dir(output_dir: Path) -> Path:
    """메세지별/시간별 하위 폴더가 들어오면 AI답변_결과 루트로 올린다."""
    if output_dir.name in {"메세지별", "시간별"}:
        return output_dir.parent
    return output_dir


def _unknown_candidate_case_warning_path(merged_output_path: Path) -> Path:
    return merged_output_path.with_name(merged_output_path.stem + ".후보외삭제.txt")


def _sync_unknown_candidate_warning_summary(answer_root: Path) -> None:
    """AI답변_결과 루트에 후보 외 삭제 요약 파일을 동기화한다."""
    summary_path = answer_root / "00_AI후보외_삭제_경고.txt"
    warning_files = sorted(
        p for p in answer_root.glob("**/AI답변_*.후보외삭제.txt")
        if p.is_file()
    )
    if not warning_files:
        try:
            if summary_path.exists():
                summary_path.unlink()
        except Exception:
            pass
        return

    lines = [
        "=" * 84,
        "[중요: STEP 5 AI 후보 외 Message:Signal 제거 경고]",
        "=" * 84,
        "",
        "AI가 Step 4 후보 목록에 없는 Message:Signal을 답변에 포함하여,",
        "해당 항목을 최종 AI답변에서 제거했습니다.",
        "",
        "이 파일이 존재한다면 아래 케이스의 원본 AI 응답에 후보 외 항목이 있었음을 의미합니다.",
        "최종 AI답변_*.txt에는 제거 후 정제된 결과가 저장됩니다.",
        "상세 원본/제거 목록은 각 케이스의 *.후보외삭제.txt 파일을 확인하세요.",
        "",
        "[대상 케이스 요약]",
    ]
    for idx, p in enumerate(warning_files, start=1):
        try:
            first_lines = p.read_text(encoding='utf-8-sig', errors='replace').splitlines()
        except Exception:
            first_lines = []
        removed_count = "?"
        answer_file = p.name.replace('.후보외삭제.txt', '.txt')
        for ln in first_lines:
            if ln.startswith("제거 항목 수:"):
                removed_count = ln.split(":", 1)[1].strip()
                break
            if ln.startswith("답변 파일:"):
                answer_file = ln.split(":", 1)[1].strip()
        lines.append(f"{idx}. {answer_file} / 제거 항목 수: {removed_count} / 상세: {p.relative_to(answer_root)}")
    lines.append("")
    summary_path.write_text("\n".join(lines) + "\n", encoding='utf-8-sig')


def _write_unknown_candidate_warning_files(
    merged_output_path: Path,
    case_inputs: List[Path],
    removed_items: List[dict],
    candidate_count: int,
) -> None:
    """후보 외 제거 상세 파일과 AI답변_결과 루트 요약 파일을 생성한다."""
    output_dir = merged_output_path.parent
    answer_root = _answer_result_root_for_output_dir(output_dir)
    warning_path = _unknown_candidate_case_warning_path(merged_output_path)

    if not removed_items:
        try:
            if warning_path.exists():
                warning_path.unlink()
        except Exception:
            pass
        _sync_unknown_candidate_warning_summary(answer_root)
        return

    lines = [
        "=" * 84,
        "[STEP 5 AI 후보 외 Message:Signal 제거 상세]",
        "=" * 84,
        "",
        f"답변 파일: {merged_output_path.name}",
        f"후보 기준: Step 4 후보 프롬프트 {len(case_inputs)}개",
        f"Step 4 후보 수: {candidate_count}",
        f"제거 항목 수: {len(removed_items)}",
        "",
        "[처리 내용]",
        "AI 답변에 Step 4 후보 목록에 없는 Message:Signal이 포함되어 최종 AI답변에서 제거했습니다.",
        "대소문자와 공백 차이는 정규화하여 비교하므로, 표기 차이만 있는 정상 후보는 제거하지 않습니다.",
        "",
        "[제거 항목]",
    ]
    for idx, item in enumerate(removed_items, start=1):
        lines.append(f"{idx}. [{item.get('section', '')}] {item.get('message', '')} : {item.get('signal', '')}")
        raw_line = (item.get('raw_line') or '').strip()
        if raw_line:
            lines.append(f"   원문: {raw_line}")
    lines.extend([
        "",
        "[원본 후보 프롬프트]",
        *[f"- {p.name}" for p in case_inputs],
        "",
        "[주의]",
        "이 파일은 AI가 후보 외 항목을 생성했음을 알리기 위한 진단 파일입니다.",
        "최종 AI답변_*.txt는 후보 외 항목이 제거된 정제본입니다.",
    ])
    warning_path.write_text("\n".join(lines) + "\n", encoding='utf-8-sig')
    _sync_unknown_candidate_warning_summary(answer_root)


def _sanitize_answer_unknown_candidates(
    merged_output_path: Path,
    merged_text: str,
    case_inputs: List[Path],
    is_messagewise: bool,
) -> Tuple[str, List[dict], List[Tuple[str, str]]]:
    """
    AI가 Step 4 후보 목록에 없는 Message:Signal을 생성하면 최종 답변에서 제거한다.
    원문 split/AI응답은 그대로 두고, 최종 병합본만 정제한다.
    """
    candidate_pairs = _collect_candidate_pairs_from_prompts(case_inputs)
    candidate_keys = {_normalize_msgsig_pair(m, s) for m, s in candidate_pairs}

    title, related_lines, unrelated_lines = _split_answer_sections_for_merge(merged_text)
    kept_related: List[str] = []
    kept_unrelated: List[str] = []
    removed_items: List[dict] = []

    for section, source_lines, target_lines in [
        ("연관 있는 메세지", related_lines, kept_related),
        ("연관 없는 메세지", unrelated_lines, kept_unrelated),
    ]:
        for line in source_lines:
            item = _line_to_item(line)
            if not item:
                target_lines.append(line)
                continue
            norm = _normalize_msgsig_pair(item['message'], item['signal'])
            if norm in candidate_keys:
                target_lines.append(line)
            else:
                removed_items.append({
                    'section': section,
                    'message': item['message'],
                    'signal': item['signal'],
                    'raw_line': item.get('raw_line') or line,
                })

    if not removed_items:
        _write_unknown_candidate_warning_files(merged_output_path, case_inputs, [], len(candidate_pairs))
        return merged_text, [], candidate_pairs

    sanitized_text = _rebuild_answer_text_from_sections(title, kept_related, kept_unrelated, is_messagewise)
    _write_unknown_candidate_warning_files(merged_output_path, case_inputs, removed_items, len(candidate_pairs))
    return sanitized_text, removed_items, candidate_pairs

def write_structured_answer_json(
    merged_output_path: Path,
    merged_text: str,
    case_inputs: List[Path],
) -> Tuple[Path, List[str]]:
    candidate_pairs = _collect_candidate_pairs_from_prompts(case_inputs)

    _title, related_lines, unrelated_lines = _split_answer_sections_for_merge(merged_text)
    related = [item for item in (_line_to_item(x) for x in related_lines) if item]
    unrelated = [item for item in (_line_to_item(x) for x in unrelated_lines) if item]
    candidate_map = {_normalize_msgsig_pair(m, s): (m, s) for m, s in candidate_pairs}
    response_keys = {
        _normalize_msgsig_pair(item['message'], item['signal'])
        for item in related + unrelated
    }
    unknown = sorted(response_keys - set(candidate_map))
    # 후보 외 항목은 merge 단계에서 정제된다. 만약 여기까지 남아도 실패시키지 않고 JSON에 기록한다.
    unclassified_keys = [key for key in candidate_map if key not in response_keys]
    unclassified = [
        {'message': candidate_map[key][0], 'signal': candidate_map[key][1]}
        for key in unclassified_keys
    ]
    payload = {
        'status': 'OK' if not unclassified else 'WARNING_UNCLASSIFIED',
        'answer_file': merged_output_path.name,
        'source_prompts': [p.name for p in case_inputs],
        'candidate_count': len(candidate_pairs),
        'related_count': len(related),
        'unrelated_count': len(unrelated),
        'unclassified_count': len(unclassified),
        'unknown_candidate_count': len(unknown),
        'unknown_candidates': [{'message': m, 'signal': s} for m, s in unknown],
        'related': related,
        'unrelated': unrelated,
        'unclassified': unclassified,
    }
    json_path = merged_output_path.with_suffix('.json')
    tmp = json_path.with_name(json_path.name + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(json_path)

    warnings: List[str] = []
    warning_path = merged_output_path.with_name(merged_output_path.stem + '.warning.txt')
    if unclassified:
        warnings.append(f'AI가 분류하지 않은 후보 {len(unclassified)}개')
        warning_text = [
            '[STEP 5 후보 완전성 경고]',
            f'답변 파일: {merged_output_path.name}',
            f'전체 후보: {len(candidate_pairs)}',
            f'관련: {len(related)}',
            f'비관련: {len(unrelated)}',
            f'미분류: {len(unclassified)}',
            '',
            '[미분류 후보]',
            *[f"- {x['message']} : {x['signal']}" for x in unclassified],
        ]
        warning_path.write_text('\n'.join(warning_text) + '\n', encoding='utf-8-sig')
    elif warning_path.exists():
        warning_path.unlink()
    return json_path, warnings


def merge_one_case_outputs(case_base: str, case_inputs: List[Path], output_dir: Path) -> Tuple[bool, str]:
    split_output_paths = []
    for input_path in case_inputs:
        out_path = get_expected_output_path_for_input(output_dir, input_path)
        ok, reason = validate_output_file_for_input(input_path, out_path)
        if not ok:
            return False, f"병합 실패: split 출력 불완전 ({reason})"
        split_output_paths.append(out_path)

    merged_output_path = get_merged_output_path_for_case(output_dir, case_base)
    is_messagewise = "시간별" not in case_base
    case_candidate_count = _candidate_count_for_inputs(case_inputs)

    try:
        if is_messagewise:
            merged_text = merge_messagewise_answers(split_output_paths)
        else:
            merged_text = merge_timewise_answers(split_output_paths)

        valid_ok, valid_reason = validate_answer_text(
            merged_text,
            source_prompt=None,
            context=merged_output_path.name,
            candidate_count=case_candidate_count,
        )
        if not valid_ok:
            return False, f"병합 결과 형식 검증 실패: {valid_reason}"

        merged_text, removed_unknown_items, _candidate_pairs = _sanitize_answer_unknown_candidates(
            merged_output_path, merged_text, case_inputs, is_messagewise=is_messagewise
        )
        if removed_unknown_items:
            print(
                f"[WARN] AI 후보 외 Message:Signal {len(removed_unknown_items)}개 제거: {merged_output_path.name}"
            )
            for item in removed_unknown_items[:20]:
                print(f"  - [{item.get('section', '')}] {item.get('message', '')}:{item.get('signal', '')}")
            if len(removed_unknown_items) > 20:
                print(f"  ... (+{len(removed_unknown_items) - 20})")

        valid_ok, valid_reason = validate_answer_text(
            merged_text,
            source_prompt=None,
            context=merged_output_path.name,
            candidate_count=case_candidate_count,
        )
        if not valid_ok:
            return False, f"후보 외 항목 제거 후 형식 검증 실패: {valid_reason}"

        atomic_write_text(merged_output_path, merged_text, encoding="utf-8")

        saved_ok, saved_reason = validate_output_file_standalone(
            merged_output_path,
            context="최종 병합본",
            candidate_count=case_candidate_count,
        )
        if not saved_ok:
            return False, f"병합 저장 결과 검증 실패: {saved_reason}"

        json_path, structure_warnings = write_structured_answer_json(merged_output_path, merged_text, case_inputs)
        write_completion_marker(merged_output_path, source_path=None, kind="merged")
        manifest_path = write_case_source_manifest(case_base, case_inputs, output_dir)
        print(
            f"[MERGE] 케이스 병합 완료: {merged_output_path.name} <= "
            f"{len(split_output_paths)}개 입력 | manifest={manifest_path.name} | json={json_path.name}"
        )
        return True, "성공"
    except Exception as e:
        return False, f"병합 실패: {e}"


# =========================================================
# REV 25: AI답변 폴더 실패 결과 경고 파일
# =========================================================
_FAILURE_WARNING_FILENAME = "00_실패결과_경고.txt"


def _extract_error_section(error_text: str, titles: List[str]) -> str:
    """error.txt의 지정 섹션에서 첫 번째 의미 있는 내용을 추출한다."""
    text = (error_text or "").replace("\r\n", "\n").replace("\r", "\n")
    for title in titles:
        m = re.search(
            rf"\[{re.escape(title)}\]\s*(.*?)(?=\n\s*\[[^\]]+\]|\Z)",
            text,
            flags=re.DOTALL,
        )
        if not m:
            continue
        value = " ".join(line.strip() for line in m.group(1).splitlines() if line.strip())
        if value:
            return value
    return ""


def _error_path_to_original_input_name(error_path: Path) -> str:
    name = error_path.name
    if name.lower().endswith(".error.txt"):
        return name[:-len(".error.txt")] + ".txt"
    return name


def _case_base_from_failure_input_name(input_name: str) -> str:
    """split 입력명 또는 케이스명을 AI문의용 case base로 정규화한다."""
    name = str(input_name or "").strip()
    if not name:
        return "알 수 없는 케이스"

    # 병합 실패처럼 확장자가 없는 case_base가 전달되는 경우.
    if not name.lower().endswith(".txt"):
        return Path(name).stem

    base, _suffix = _get_split_base_and_suffix_from_input_name(name)
    return base


def _read_failure_reason_from_error(error_path: Path) -> str:
    try:
        text = error_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"error.txt 읽기 실패: {e}"

    reason = _extract_error_section(text, ["추정 사유", "실패 사유"])
    exc_message = _extract_error_section(text, ["예외 메시지"])
    if reason and exc_message and exc_message not in reason:
        return f"{reason} / 예외: {exc_message[:500]}"
    if reason:
        return reason
    if exc_message:
        return exc_message
    return "상세 사유는 원본 .error.txt를 확인하세요."


def _collect_unresolved_step5_error_records(input_dir: Path, output_dir: Path) -> List[dict]:
    records: List[dict] = []
    if not input_dir.exists():
        return records

    for error_path in sorted(input_dir.glob("AI문의용_*.error.txt"), key=lambda x: x.name.lower()):
        input_name = _error_path_to_original_input_name(error_path)
        case_base = _case_base_from_failure_input_name(input_name)
        records.append({
            "case_base": case_base,
            "input_file": input_name,
            "output_file": make_output_filename(input_name),
            "reason": _read_failure_reason_from_error(error_path),
            "source": "현재 .error.txt",
            "error_file": error_path.name,
        })
    return records


def _merge_failure_warning_records(
    unresolved_records: List[dict],
    current_failed_files: List[dict] | None,
) -> List[dict]:
    """현재 .error 기록과 이번 실행 실패 목록을 중복 없이 합친다."""
    merged: List[dict] = []
    seen = set()

    for item in list(unresolved_records or []):
        key = (
            str(item.get("input_file", "")).casefold(),
            str(item.get("output_file", "")).casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(item))

    for item in list(current_failed_files or []):
        input_file = str(item.get("input_file", "") or "").strip()
        output_file = str(item.get("output_file", "") or "").strip()
        reason = str(item.get("reason", "") or "원인 미상").strip()
        key = (input_file.casefold(), output_file.casefold())
        if key in seen:
            continue
        seen.add(key)
        merged.append({
            "case_base": _case_base_from_failure_input_name(input_file),
            "input_file": input_file or "-",
            "output_file": output_file or "-",
            "reason": reason,
            "source": "이번 실행 최종 실패",
            "error_file": "-",
        })

    return merged


def sync_step5_failure_warning_file(
    input_dir: Path,
    output_dir: Path,
    current_failed_files: List[dict] | None = None,
) -> dict:
    """
    AI답변 출력 폴더의 00_실패결과_경고.txt를 현재 실패 상태와 동기화한다.

    - 미해결 .error 또는 이번 실행 최종 실패가 있으면 생성/갱신
    - 모든 실패가 해결되면 기존 경고 파일 삭제
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    warning_path = output_dir / _FAILURE_WARNING_FILENAME

    unresolved_records = _collect_unresolved_step5_error_records(input_dir, output_dir)
    records = _merge_failure_warning_records(unresolved_records, current_failed_files)

    if not records:
        try:
            if warning_path.exists():
                warning_path.unlink()
                print(f"[OK] Step 5 실패가 모두 해결되어 결과 경고 파일 삭제: {warning_path}")
        except Exception as e:
            print(f"[WARN] 결과 경고 파일 삭제 실패: {warning_path} ({e})")
        return {
            "warning_file": "",
            "unresolved_error_count": 0,
            "affected_case_count": 0,
        }

    grouped: Dict[str, List[dict]] = {}
    for item in records:
        case_base = str(item.get("case_base", "") or "알 수 없는 케이스")
        grouped.setdefault(case_base, []).append(item)

    now = datetime.now()
    lines = [
        "=" * 84,
        "[중요: STEP 5 실패 결과 경고]",
        "=" * 84,
        "",
        "이 폴더에는 아직 해결되지 않은 Step 5 실패가 있습니다.",
        "폴더 안에 AI답변_*.txt 또는 최종 병합본이 존재하더라도,",
        "일부 split만 반영된 부분 결과이거나 이전 실행 결과일 수 있으므로",
        "이 경고 파일이 존재하는 동안에는 정상 완료 결과로 판단하지 마세요.",
        "",
        f"경고 생성/갱신 시각: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"출력 구분: {output_dir.name}",
        f"미해결 실패 항목 수: {len(records)}",
        f"영향 케이스 수: {len(grouped)}",
        "",
        "[자동 삭제 조건]",
        "- 2차/3차 재시도 또는 '실패파일만 재실행'으로 모든 실패가 해결되면",
        "  대응 .error.txt가 삭제되고 이 경고 파일도 다음 상태 동기화 시 자동 삭제됩니다.",
        "",
        "[영향 케이스 및 실패 항목]",
    ]

    for case_index, (case_base, case_records) in enumerate(grouped.items(), start=1):
        merged_output_path = get_merged_output_path_for_case(output_dir, case_base)
        merged_state = "존재함 - 완전성 보장 안 됨" if merged_output_path.exists() else "없음"
        case_display = case_base.replace("AI문의용_", "", 1)
        lines.extend([
            "",
            f"{case_index}. {case_display}",
            f"   최종 병합 답변: {merged_state}",
        ])
        for rec_index, item in enumerate(case_records, start=1):
            lines.extend([
                f"   {case_index}-{rec_index}) 입력: {item.get('input_file', '-')}",
                f"       예상 출력: {item.get('output_file', '-')}",
                f"       기록 출처: {item.get('source', '-')}",
                f"       실패 사유: {item.get('reason', '-')}",
            ])
            error_file = str(item.get("error_file", "") or "-")
            if error_file != "-":
                lines.append(f"       상세 error: {input_dir / error_file}")

    lines.extend([
        "",
        "[권장 조치]",
        "1. GUI에서 Step 5와 '실패파일만 재실행'을 체크하여 다시 실행하세요.",
        "2. 입력 텍스트 길이 초과가 반복되면 Step 4 분할 크기를 더 작게 조정하세요.",
        "3. 서버 오류가 같은 split에서 반복되면 debug_00 버전의 상세 로그를 확인하세요.",
        "4. 이 경고 파일이 자동 삭제되고 AI문의용 폴더의 대응 .error.txt가 없는지 확인한 뒤",
        "   최종 AI답변과 Step 6 결과를 정상 완료본으로 사용하세요.",
        "",
    ])

    atomic_write_text(warning_path, "\n".join(lines), encoding="utf-8-sig")
    print(f"[WARN] Step 5 미해결 실패 경고 파일 생성/갱신: {warning_path}")
    return {
        "warning_file": str(warning_path),
        "unresolved_error_count": len(records),
        "affected_case_count": len(grouped),
    }


# =========================================================
# 폴더 단위 처리
# =========================================================
def process_one_subfolder(input_dir: Path, output_dir: Path, config, step5_global_state: dict | None = None):
    if not input_dir.exists():
        print(f"[WARN] 입력 하위 폴더가 존재하지 않아 건너뜀: {input_dir}")
        return {
            "input_dir": str(input_dir),
            "output_dir": str(output_dir),
            "total": 0,
            "success": 0,
            "skip": 0,
            "fail": 0,
            "failed_files": [],
            "warning_file": "",
            "unresolved_error_count": 0,
            "affected_case_count": 0,
        }

    output_dir.mkdir(parents=True, exist_ok=True)

    keep_split_files = getattr(config, "keep_split_answer_files_after_merge", True)

    cleanup_completed_cases_splits(
        input_dir=input_dir,
        output_dir=output_dir,
        keep_split_files=keep_split_files,
    )

    input_files = sorted(
        [
            p for p in input_dir.glob(config.file_pattern)
            if p.is_file()
            and not p.name.endswith(".error.txt")
            and not p.name.endswith(".warning.txt")
        ]
    )

    if not input_files:
        print(f"[WARN] 처리할 파일이 없어. 폴더: {input_dir} | 패턴: {config.file_pattern}")
        warning_state = sync_step5_failure_warning_file(input_dir, output_dir, current_failed_files=[])
        return {
            "input_dir": str(input_dir),
            "output_dir": str(output_dir),
            "total": 0,
            "success": 0,
            "skip": 0,
            "fail": 0,
            "failed_files": [],
            **warning_state,
        }

    provider = config.ai_provider.lower()
    if provider == "gpt":
        model_desc = config.gpt_model
    else:
        model_desc = f"{config.gemini_model} ({config.gemini_stream_option})"

    print("\n==============================")
    print(f"[START] 폴더 처리 시작: {input_dir.name}")
    print(f"입력 폴더: {input_dir}")
    print(f"출력 폴더: {output_dir}")
    print(f"사용 모델: {provider} / {model_desc}")
    print(f"실패파일만 재실행: {getattr(config, 'retry_failed_only', False)}")
    print(f"완료된 답변파일 Pass: {getattr(config, 'completed_answer_file_pass', False)}")
    print("==============================")

    success_count = 0
    skip_count = 0
    fail_count = 0
    failed_files = []

    case_groups = build_case_groups(input_files)
    all_case_bases = sorted(case_groups.keys())

    selected_case_bases: List[str] = []
    skipped_case_bases: List[str] = []

    if getattr(config, "retry_failed_only", False) or getattr(config, "completed_answer_file_pass", False):
        mode_label = "RETRY" if getattr(config, "retry_failed_only", False) else "PASS-EXISTING"
        for case_base in all_case_bases:
            case_inputs = case_groups[case_base]
            incomplete, reasons = is_case_incomplete(case_base, case_inputs, output_dir)
            if incomplete:
                selected_case_bases.append(case_base)
                print(f"[{mode_label}][CASE] 대상 선정: {case_base}")
                for reason in reasons:
                    print(f"  - {reason}")
            else:
                skipped_case_bases.append(case_base)

        print(
            f"[INFO] {mode_label} 케이스 수: 전체 {len(all_case_bases)} -> "
            f"대상 {len(selected_case_bases)}, 기존 완료 인정 {len(skipped_case_bases)}"
        )
        if getattr(config, "retry_failed_only", False):
            register_step5_retry_case_targets(config, input_dir.name, selected_case_bases)
            print(
                f"[RETRY][STEP5->STEP6] Step 6 연계 대상 누적: "
                f"{len(getattr(config, 'step_5_retry_case_keys', []) or [])}개"
            )
    else:
        selected_case_bases = all_case_bases

    if not selected_case_bases:
        print(f"[WARN] 재실행 대상 케이스가 없어. 폴더: {input_dir}")
        cleanup_completed_cases_splits(
            input_dir=input_dir,
            output_dir=output_dir,
            keep_split_files=keep_split_files,
        )
        warning_state = sync_step5_failure_warning_file(input_dir, output_dir, current_failed_files=[])
        return {
            "input_dir": str(input_dir),
            "output_dir": str(output_dir),
            "total": 0,
            "success": 0,
            "skip": len(skipped_case_bases),
            "fail": 0,
            "failed_files": [],
            **warning_state,
        }

    total_case_count = len(selected_case_bases)

    for case_idx, case_base in enumerate(selected_case_bases, start=1):
        case_inputs = case_groups[case_base]

        if step5_global_state is not None and int(step5_global_state.get("total", 0) or 0) > 0:
            step5_global_state["current"] = int(step5_global_state.get("current", 0) or 0) + 1
            display_idx = int(step5_global_state["current"])
            display_total = int(step5_global_state["total"])
        else:
            display_idx = case_idx
            display_total = total_case_count

        case_percent = (display_idx / display_total) * 100 if display_total else 0.0

        print("\n" + "-" * 80)
        print(f"[CASE {display_idx}/{display_total} | {case_percent:.1f}%] 처리 시작: {case_base}")
        print(f"[CASE] 현재 폴더: {input_dir.name} | 폴더 내 순번: {case_idx}/{total_case_count}")
        print(f"[CASE] split 수: {len(case_inputs)}")
        print("-" * 80)

        case_process_inputs = case_inputs

        if getattr(config, "completed_answer_file_pass", False):
            case_process_inputs = prepare_completed_answer_pass_inputs(
                case_base=case_base,
                case_inputs=case_inputs,
                output_dir=output_dir,
            )
            if not case_process_inputs:
                print("[PASS-EXISTING] 모든 split 출력이 이미 검증되어 API 재호출 없이 병합만 수행합니다.")

        elif getattr(config, "retry_failed_only", False):
            retry_start_index = get_retry_tail_start_index(case_inputs, output_dir)
            if retry_start_index is None:
                case_process_inputs = []
                merged_output_path = get_merged_output_path_for_case(output_dir, case_base)
                remove_tmp_output_if_exists(merged_output_path)
                remove_completion_marker_if_exists(merged_output_path)
                try:
                    if merged_output_path.exists():
                        merged_output_path.unlink()
                        print(f"[RETRY] 기존 최종 병합본 삭제: {merged_output_path.name}")
                except Exception as e:
                    print(f"[WARN] 최종 병합본 삭제 실패: {merged_output_path} ({e})")
                print("[RETRY] 모든 split 출력이 이미 존재하여 API 재호출 없이 병합만 수행합니다.")
            else:
                case_process_inputs = cleanup_retry_tail_outputs(
                    case_base=case_base,
                    case_inputs=case_inputs,
                    output_dir=output_dir,
                    start_index=retry_start_index,
                )

        case_all_success = True

        for split_idx, input_path in enumerate(case_process_inputs, start=1):
            output_name = make_output_filename(input_path.name)
            output_path = output_dir / output_name

            effective_skip_if_output_exists = bool(config.skip_if_output_exists) and (
                not getattr(config, "retry_failed_only", False)
                and not getattr(config, "completed_answer_file_pass", False)
            )

            if effective_skip_if_output_exists and output_path.exists():
                print(
                    f"\n[CASE {case_idx}/{total_case_count}] "
                    f"[{split_idx}/{len(case_process_inputs)}] 건너뜀: {output_name} (이미 존재)"
                )
                skip_count += 1
                continue

            ok, reason = process_one_file(
                input_path=input_path,
                output_path=output_path,
                current_idx=split_idx,
                total_count=len(case_process_inputs),
                config=config,
            )

            if ok:
                success_count += 1
            else:
                case_all_success = False
                fail_count += 1
                failed_files.append({
                    "input_file": input_path.name,
                    "output_file": output_name,
                    "reason": reason
                })

            print(f"[CASE {case_idx}/{total_case_count}] 현재 현황 -> 성공: {success_count}, 건너뜀: {skip_count}, 실패: {fail_count}")
            time.sleep(config.sleep_between_calls)

        if case_all_success:
            merged_ok, merged_reason = merge_one_case_outputs(case_base, case_inputs, output_dir)
            if not merged_ok:
                fail_count += 1
                failed_files.append({
                    "input_file": case_base,
                    "output_file": get_merged_output_path_for_case(output_dir, case_base).name,
                    "reason": merged_reason,
                })
                print(f"[CASE FAIL] {case_base} | {merged_reason}")
            else:
                print(f"[CASE OK] 케이스 완료: {case_base}")
                # split 2개 이상인 실제 분할 케이스만 삭제
                if not keep_split_files and len(case_inputs) >= 2:
                    delete_split_outputs_for_case(case_inputs, output_dir)
        else:
            print(f"[CASE FAIL] 케이스 불완전(부분 성공 포함)으로 최종 실패 처리: {case_base}")

    cleanup_completed_cases_splits(
        input_dir=input_dir,
        output_dir=output_dir,
        keep_split_files=keep_split_files,
    )

    warning_state = sync_step5_failure_warning_file(
        input_dir=input_dir,
        output_dir=output_dir,
        current_failed_files=failed_files,
    )

    summary_path = None
    if fail_count > 0:
        report_dir = Path(__file__).resolve().parent
        summary_path = report_dir / f"실패파일_요약_{input_dir.name}.txt"

        summary_lines = [
            "[작업 요약]",
            f"입력 폴더: {input_dir}",
            f"출력 폴더: {output_dir}",
            f"선정 케이스 수: {len(selected_case_bases)}",
            f"성공(split 기준): {success_count}",
            f"건너뜀(split 기준): {skip_count}",
            f"실패(split/케이스 기준 합산): {fail_count}",
            "",
            "[실패 파일 목록]",
        ]

        for i, item in enumerate(failed_files, start=1):
            summary_lines.append(
                f"{i}. 입력파일: {item['input_file']} | 출력파일: {item['output_file']} | 사유: {item['reason']}"
            )

        summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    print("\n[END] 폴더 처리 완료:", input_dir.name)
    print(f"  성공(API 요청 조각 기준): {success_count}, 건너뜀(케이스 기준): {skip_count}, 실패(API 요청/케이스 합산): {fail_count}")
    if summary_path:
        print(f"  실패 요약 파일: {summary_path}")
    else:
        print("  실패 없음: 실패 요약 파일 생성 안 함")
    if warning_state.get("warning_file"):
        print(f"  결과 폴더 경고 파일: {warning_state['warning_file']}")
    else:
        print("  결과 폴더 경고 파일: 없음")

    return {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "total": len(selected_case_bases),
        "success": success_count,
        "skip": skip_count,
        "fail": fail_count,
        "failed_files": failed_files,
        **warning_state,
    }


# =========================================================
# 기존 전체 병합 함수는 유지하되, retry_failed_only=False일 때만 보조적으로 사용
# =========================================================
def merge_split_answer_files_in_dir(output_dir: Path, keep_split_files: bool = True) -> None:
    if not output_dir.exists() or not output_dir.is_dir():
        return

    txt_files = [p for p in output_dir.glob("AI답변_*.txt") if p.is_file()]
    if not txt_files:
        return

    grouped = {}

    for p in txt_files:
        m = _SPLIT_SUFFIX_RE.match(p.name)
        if not m:
            continue

        base = m.group("base")
        suffix = m.group("suffix")
        idx = _suffix_to_index(suffix)

        if idx < 0:
            continue

        grouped.setdefault(base, []).append((idx, p))

    if not grouped:
        return

    for base, items in grouped.items():
        items.sort(key=lambda x: x[0])
        split_paths = [p for _idx, p in items]

        merged_path = output_dir / f"{base}.txt"
        is_messagewise = "시간별" not in base

        try:
            if is_messagewise:
                merged_text = merge_messagewise_answers(split_paths)
            else:
                merged_text = merge_timewise_answers(split_paths)

            valid_ok, valid_reason = validate_answer_text(merged_text, source_prompt=None, context=merged_path.name)
            if not valid_ok:
                raise ValueError(f"병합 결과 형식 검증 실패: {valid_reason}")

            atomic_write_text(merged_path, merged_text, encoding="utf-8")
            saved_ok, saved_reason = validate_output_file_standalone(merged_path, context="최종 병합본")
            if not saved_ok:
                raise ValueError(f"병합 저장 결과 검증 실패: {saved_reason}")
            write_completion_marker(merged_path, source_path=None, kind="merged")
            print(f"[MERGE] 병합 완료: {merged_path.name} <= {len(split_paths)}개 파일")

            if not keep_split_files:
                for p in split_paths:
                    remove_completion_marker_if_exists(p)
                    try:
                        p.unlink()
                        print(f"[MERGE] 분할 파일 삭제: {p.name}")
                    except Exception as e:
                        print(f"[WARN] 병합 후 분할 파일 삭제 실패: {p.name} ({e})")

        except Exception as e:
            print(f"[WARN] 병합 실패: {base}.txt ({e})")
            print(traceback.format_exc())


# =========================================================
# 실행부
# =========================================================
def _collect_step5_selected_case_count_for_progress(input_dir: Path, output_dir: Path, config) -> int:
    """GUI 진행률 표시용으로 해당 하위폴더에서 실제 처리 대상 CASE 수를 미리 계산한다."""
    input_files = sorted(
        [
            p for p in input_dir.glob(config.file_pattern)
            if p.is_file()
            and not p.name.endswith(".error.txt")
            and not p.name.endswith(".warning.txt")
        ]
    )
    if not input_files:
        return 0

    case_groups = build_case_groups(input_files)
    all_case_bases = sorted(case_groups.keys())

    if getattr(config, "retry_failed_only", False) or getattr(config, "completed_answer_file_pass", False):
        count = 0
        for case_base in all_case_bases:
            case_inputs = case_groups[case_base]
            incomplete, _reasons = is_case_incomplete(case_base, case_inputs, output_dir)
            if incomplete:
                count += 1
        return count

    return len(all_case_bases)


def _run_adaptive_safe_split(config) -> None:
    if not str(getattr(config, "api_key", "") or "").strip():
        print("[ERROR] API KEY가 감지되지 않았습니다.")
        raise ValueError("API KEY가 감지되지 않았습니다.")

    base_dir = Path(config.base_dir)
    if getattr(config, "retry_failed_only", False):
        # 동일 실행에서 Step 5가 실제로 선택한 케이스만 새로 기록한다.
        setattr(config, "step_5_retry_case_keys", [])
    input_root_dir = base_dir / config.input_root_dir_name
    output_root_dir = input_root_dir / config.output_root_dir_name

    start_time = datetime.now()

    if not input_root_dir.exists():
        print(f"입력 루트 폴더가 존재하지 않아: {input_root_dir}")
        return

    output_root_dir.mkdir(parents=True, exist_ok=True)

    provider = config.ai_provider.lower()
    if provider == "gpt":
        model_desc = config.gpt_model
    elif provider == "gemini":
        model_desc = f"{config.gemini_model} ({config.gemini_stream_option})"
    else:
        raise ValueError(f"지원하지 않는 ai_provider: {provider}")

    target_subfolders = list(config.subfolders)

    if not getattr(config, "step_5_enable_time_folder", False):
        target_subfolders = [sub for sub in target_subfolders if sub != "시간별"]

    print("===== STEP 5 기본 단일 + 예외 안전 분할 처리 시작 =====")
    print(f"입력 루트: {input_root_dir}")
    print(f"출력 루트: {output_root_dir}")
    print(f"대상 하위폴더: {target_subfolders}")
    print(f"대상 파일 패턴: {config.file_pattern}")
    print(f"사용 모델: {provider} / {model_desc}")
    print(f"실패파일만 재실행: {getattr(config, 'retry_failed_only', False)}")
    print(f"완료된 답변파일 Pass: {getattr(config, 'completed_answer_file_pass', False)}")
    print(f"STEP_5 시간별 처리 사용: {getattr(config, 'step_5_enable_time_folder', False)}")

    step5_total_case_count = 0
    for sub in target_subfolders:
        input_dir = input_root_dir / sub
        output_dir = output_root_dir / sub
        step5_total_case_count += _collect_step5_selected_case_count_for_progress(input_dir, output_dir, config)

    print(f"[STEP5] 전체 CASE 진행률 기준 수: {step5_total_case_count}개")
    if getattr(config, "step_5_enable_time_folder", False):
        print("[STEP5] 시간별 폴더가 Step 5 진행률 기준 수에 포함됩니다.")

    step5_global_state = {"current": 0, "total": step5_total_case_count}

    all_results = []

    for sub in target_subfolders:
        input_dir = input_root_dir / sub
        output_dir = output_root_dir / sub
        result = process_one_subfolder(input_dir, output_dir, config, step5_global_state=step5_global_state)
        all_results.append((sub, result))

    merge_enabled = getattr(config, "merge_split_answer_files", True)
    keep_split_files = getattr(config, "keep_split_answer_files_after_merge", True)

    if merge_enabled and not getattr(config, "retry_failed_only", False):
        print("\n===== 분할 답변 파일 병합 시작 =====")
        for sub in target_subfolders:
            out_dir = output_root_dir / sub
            print(f"[MERGE] 대상 폴더: {out_dir}")
            merge_split_answer_files_in_dir(
                output_dir=out_dir,
                keep_split_files=keep_split_files,
            )
        print("===== 분할 답변 파일 병합 완료 =====")

    result_by_sub = {sub: result for sub, result in all_results}
    for sub in target_subfolders:
        input_dir = input_root_dir / sub
        out_dir = output_root_dir / sub
        cleanup_completed_cases_splits(
            input_dir=input_dir,
            output_dir=out_dir,
            keep_split_files=keep_split_files,
        )

        # 전역 병합 이후 최종 폴더 상태를 다시 반영한다.
        result = result_by_sub.get(sub, {})
        warning_state = sync_step5_failure_warning_file(
            input_dir=input_dir,
            output_dir=out_dir,
            current_failed_files=list(result.get("failed_files", []) or []),
        )
        result.update(warning_state)

    end_time = datetime.now()
    elapsed = end_time - start_time

    total_files = sum(r["total"] for _sub, r in all_results)
    total_success = sum(r["success"] for _sub, r in all_results)
    total_skip = sum(r["skip"] for _sub, r in all_results)
    total_fail = sum(r["fail"] for _sub, r in all_results)

    overall_summary_path = output_root_dir / "전체_요약.txt"
    lines = [
        "[전체 작업 요약]",
        f"시작 시각: {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"종료 시각: {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"총 소요 시간: {elapsed}",
        "",
        f"AI Provider: {provider}",
        f"모델 정보: {model_desc}",
        "",
        f"총 대상(케이스 기준): {total_files}",
        f"성공(split 기준): {total_success}",
        f"건너뜀(split 기준): {total_skip}",
        f"실패(split/케이스 기준 합산): {total_fail}",
        "",
        f"분할 병합 사용: {merge_enabled}",
        f"분할 파일 유지: {keep_split_files}",
        f"STEP_5 시간별 처리 사용: {getattr(config, 'step_5_enable_time_folder', False)}",
        "",
        "[폴더별 요약]",
    ]

    for sub, r in all_results:
        lines += [
            f"- {sub}",
            f"  total={r['total']}, success={r['success']}, skip={r['skip']}, fail={r['fail']}",
        ]
        if r.get("warning_file"):
            lines.append(f"  IMPORTANT: 결과 경고 파일={r['warning_file']}")
            lines.append(
                f"  unresolved={r.get('unresolved_error_count', 0)}, "
                f"affected_cases={r.get('affected_case_count', 0)}"
            )
        if r["failed_files"]:
            lines.append("  failed samples:")
            for item in r["failed_files"][:10]:
                lines.append(f"    - {item['input_file']} | {item['reason']}")
        lines.append("")

    overall_summary_path.write_text("\n".join(lines), encoding="utf-8")

    print("\n===== 전체 작업 완료 =====")
    print(f"총 대상(케이스 기준): {total_files}")
    print(f"성공(API 요청 조각 기준): {total_success}")
    print(f"건너뜀(케이스 기준): {total_skip}")
    print(f"실패(API 요청/케이스 합산): {total_fail}")
    warning_count = sum(1 for _sub, r in all_results if r.get("warning_file"))
    print(f"결과 경고 파일 생성 폴더 수: {warning_count}")
    print(f"전체 요약 파일: {overall_summary_path}")
    if total_fail > 0:
        raise RuntimeError(f"Step 5 실패 파일 또는 케이스가 있습니다: {total_fail}개")



# =========================================================
# REV 27: 후보 외 AI 생성 Message:Signal 제거 및 경고 파일 생성
# REV 26: TC당 단일 후보 프롬프트 처리
# =========================================================
def _is_legacy_split_input(path: Path) -> bool:
    match = re.match(r"^(?P<base>.+)_(?P<suffix>[a-z]+)\.txt$", path.name, flags=re.IGNORECASE)
    if not match:
        return False
    return path.with_name(match.group('base') + '.txt').exists()


def _single_input_files(input_dir: Path, pattern: str) -> List[Path]:
    files: List[Path] = []
    for path in sorted(input_dir.glob(pattern), key=lambda p: p.name):
        if not path.is_file() or path.name.endswith('.error.txt') or path.name.endswith('.warning.txt'):
            continue
        if _is_legacy_split_input(path):
            print(f"[CLEANUP] 구형 split 입력은 단일 원본이 있어 제외: {path.name}")
            continue
        files.append(path)
    return files


def _single_case_incomplete(input_path: Path, output_path: Path) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    if has_input_error_log(input_path):
        reasons.append(f"입력 .error 존재: {make_input_error_log_path(input_path).name}")
    valid, reason = validate_output_file_for_input(input_path, output_path)
    if not valid:
        reasons.append(reason)
    else:
        marker_ok, marker_reason = is_completion_marker_valid_for_input(input_path, output_path)
        if not marker_ok:
            reasons.append(marker_reason)
    return bool(reasons), reasons


def process_single_subfolder(input_dir: Path, output_dir: Path, config, global_state: dict | None = None) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not input_dir.exists():
        return {'total': 0, 'success': 0, 'skip': 0, 'fail': 0, 'failed_files': [], 'warning_file': ''}

    inputs = _single_input_files(input_dir, config.file_pattern)
    selected: List[Path] = []
    skipped = 0
    for path in inputs:
        output = get_expected_output_path_for_input(output_dir, path)
        incomplete, reasons = _single_case_incomplete(path, output)
        if getattr(config, 'retry_failed_only', False):
            if incomplete:
                selected.append(path)
                print(f"[RETRY][CASE] 대상 선정: {path.stem}")
                for reason in reasons:
                    print(f"  - {reason}")
            else:
                skipped += 1
        elif getattr(config, 'completed_answer_file_pass', False) or getattr(config, 'skip_if_output_exists', True):
            if not incomplete:
                skipped += 1
                print(f"[PASS-EXISTING] 완료 답변 인정: {output.name}")
            else:
                selected.append(path)
        else:
            selected.append(path)

    if getattr(config, 'retry_failed_only', False):
        register_step5_retry_case_targets(config, input_dir.name, [p.stem for p in selected])

    success = 0
    fail = 0
    failed_files: List[dict] = []
    total = len(selected)
    for local_idx, input_path in enumerate(selected, 1):
        if global_state and global_state.get('total', 0):
            global_state['current'] += 1
            display_idx, display_total = global_state['current'], global_state['total']
        else:
            display_idx, display_total = local_idx, total
        pct = display_idx * 100 / display_total if display_total else 100.0
        print(f"\n[CASE {display_idx}/{display_total} | {pct:.1f}%] 처리 시작: {input_path.stem}")
        output_path = get_expected_output_path_for_input(output_dir, input_path)
        ok, reason = process_one_file(input_path, output_path, 1, 1, config)
        if ok:
            write_completion_marker(output_path, source_path=input_path, kind='single')
            success += 1
        else:
            fail += 1
            failed_files.append({'input_file': input_path.name, 'output_file': output_path.name, 'reason': reason})
        time.sleep(config.sleep_between_calls)

    warning_state = sync_step5_failure_warning_file(input_dir, output_dir, current_failed_files=failed_files)
    return {
        'total': total,
        'success': success,
        'skip': skipped,
        'fail': fail,
        'failed_files': failed_files,
        **warning_state,
    }


def run(config) -> None:
    # REV 27: 평상시는 TC당 단일 파일, 안전 상한 초과 케이스만 _a/_b/... 처리한다.
    setattr(config, 'merge_split_answer_files', True)
    setattr(config, 'keep_split_answer_files_after_merge', False)
    print('[INFO] Step 5 분할 정책: 기본 단일 + 예외 안전 분할')
    _run_adaptive_safe_split(config)


def _load_latest_v2_main_module():
    """같은 폴더의 Signal_Export_V2_Main_rev_xx.py 중 가장 높은 rev를 로드한다."""
    import importlib.util
    import re as _re
    import sys as _sys
    code_dir = Path(__file__).resolve().parent
    base = "Signal_Export_V2_Main"
    rx = _re.compile(rf"^{_re.escape(base)}(?:[_\-.])rev(?:[_\-.])?(\d+)\.py$", _re.IGNORECASE)
    best = None
    for path in code_dir.glob(f"{base}*.py"):
        m = rx.match(path.name)
        if not m:
            continue
        rev = int(m.group(1))
        if best is None or rev > best[0]:
            best = (rev, path)
    selected = best[1] if best else code_dir / f"{base}.py"
    if not selected.is_file():
        raise FileNotFoundError(f"{base}_rev_xx.py를 찾지 못했습니다: {code_dir}")
    module_name = f"_dyn_{base}_{selected.stem}"
    spec = importlib.util.spec_from_file_location(module_name, str(selected))
    if spec is None or spec.loader is None:
        raise ImportError(f"Main 모듈 spec 생성 실패: {selected}")
    module = importlib.util.module_from_spec(spec)
    _sys.modules[module_name] = module
    spec.loader.exec_module(module)
    print(f"[INFO] Selected latest V2 Main: {selected.name}")
    return module


def main() -> None:
    main_module = _load_latest_v2_main_module()
    run(main_module.build_config())


if __name__ == "__main__":
    main()
