# -*- coding: utf-8 -*-
# [Excel Compat 연동 변경] rev06: Excel Compat rev03 공통 reader/forward-fill helper 사용
"""
[V2 STEP 7 REV 06 변경점]
- TestCase Excel fallback TC 번호/분류 forward-fill을 Excel Compat rev03 공통 helper로 변경
- pandas FutureWarning을 제거하되 기존 분류/TC fallback 정책은 유지

Signal_Export_V2_Step_7_Signal_Classification_rev_04.py

목적
- 신규 Step 6의 관련 시그널 상세 변화 TXT를 입력으로 사용
- GUI/main에서 선택된 DBC만 검색하여 해당 Message/Signal의 핵심 DBC 근거 정보를 수집
- 사람이 Step 5 결과가 타당한지 검토할 수 있도록 AI답변_결과 하위 판단 해설 폴더에 근거/분류 txt 생성
- Sender MCU / Signal Receiver MCU / Message Receiver / 신호 의미 / 값 의미 / AI 판단 근거만 간결히 표시

입력
- {base_dir}/AI답변_결과/{메세지별,시간별}/AI답변_*.txt
  또는 호환 경로: {base_dir}/AI_문의용_출력/AI답변_결과/...
- GUI/main에서 선택된 DBC(config.dbc_name_by_ch) 우선

출력
- {base_dir}/AI답변_결과/판단 해설_메세지별/AI결과판단_*.txt
- {base_dir}/AI답변_결과/판단 해설_시간별/AI결과판단_*.txt
- 동일 폴더에 AI결과판단_분류_*.txt 추가 생성

주의
- DBC 근거는 API 없이 생성함
- 로컬 고신뢰/강제 규칙 신호는 API를 사용하지 않고, 애매한 신호만 파일 단위 batch API로 분류함
- "연관 없는 메세지" 섹션은 근거 생성 대상에서 제외
- 동일 Message:Signal은 1회만 DBC 근거 블록 생성하되, Step 5 원문 관측 라인은 모두 보존


[V2 REV 04 변경점]
- Excel fallback reader를 공통 호환 모듈로 전환하여 .xls/.xlsx/.xlsm 및 확장자-실제형식 불일치 지원
- XLS=xlrd>=2.0.1, XLSX/XLSM=openpyxl 자동 선택
- 기존 분류/TC fallback 알고리즘은 변경하지 않음

[V2 REV 03 변경점]
- GPT 호출 시 config.gpt_model이 없는 예외 경로의 fallback 기본값을 gpt-5.6-terra로 변경
- 정상 Main 연동 시에는 기존과 동일하게 config.gpt_model 선택값을 그대로 사용

[V2 REV 02 변경점]
- Step 6의 *_상세분석.txt와 *_요약.txt를 각각 독립 입력으로 분류
- 기존 AI결과판단_*.txt DBC 근거 전용 파일은 더 이상 생성하지 않음
- AI결과판단_상세분석 분류_*.txt 및 AI결과판단_요약 분류_*.txt 두 결과만 생성
- 요약 분류는 값 단일 행을 먼저, 중복 제거된 변화 행을 다음에 배치하고 신호 요약/사유를 신호당 1회만 표시
- 요약 분류 사유에서는 휴리스틱/AI 채택 메타, 신뢰도, 점수 문구를 제거

[REV 14 기존 변경점]
- retry_failed_only=True일 때 Step 6 정상 갱신 케이스와 Step 7 자체 .error 케이스의 합집합만 처리
- .warning.txt는 실패 재실행 대상에서 제외
- Step 7 사용자 로그/실패 문구의 과거 Step 6 명칭을 정리
- 단독 실행 시 최신 main_rev_27 설정 사용

[REV 13 변경점]
- 기존 Step 6 DBC 근거/분류 기능을 Step 7로 이동
- 신규 Step 6의 관련 시그널 상세 변화 파일을 입력으로 사용
- 고신뢰/강제 규칙 신호는 로컬 분류만 사용하고, 애매한 신호만 API 분류
- 별도의 전체 신호 AI 판단 근거 호출을 제거하여 API 사용량 축소

[REV 12 변경점]
- REV 10의 TC 정보 fallback, 3줄 분류 블록, 신호명/메시지 주기 기반 분류를 유지
- 00ms=입력, 50/100/200ms=출력을 절대 규칙으로 쓰지 않고 약한 사전 가중치로 축소
- 실제 DBC cycle_time/send type/comment를 파일명 주기보다 우선 사용
- CamelCase/underscore 신호명을 토큰화하여 Btn/Sw/Lvr/Pedal과 Req/Cmd/Tar/Act/Sta/Fdbk 등을 안정적으로 판별
- CRC/Alive/Counter/Diag/Timeout/Validity/SNA 등 비기능성 신호는 강한 제외 기준으로 처리
- TC 문구 연관도, 관측값 변화, Sender/Receiver/DBC 설명을 함께 점수화
- AI 분류를 원문 라인 복사 방식이 아닌 Message:Signal 단위 JSON으로 받아 공백 차이/누락 문제를 방지
- 휴리스틱과 AI가 충돌할 때 hard rule, 점수 차이, AI confidence를 이용해 하이브리드 결정
- 분류 사유에 실제 적용된 근거와 신뢰도를 표시
- 엑셀 fallback의 하위 TC 번호 해석 및 시트명 탐색을 보강
- retry_failed_only=True일 때 Step 6에서 정상 갱신된 케이스와 Step 7 자체 .error 케이스의 합집합만 처리
- Step 7 재실행 성공 시 기존 Step 7 .error 파일 자동 삭제
- .warning.txt는 확인용 상태이므로 실패 재실행 대상에서 제외
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from Signal_Export_V2_Excel_Compat_rev_03 import excel_file_compat, find_excel_file_compat, read_excel_compat, ffill_dataframe_columns_compat
from typing import Dict, List, Tuple, Optional, Iterable
import re
import traceback
import time
import json

try:
    import cantools
except Exception:  # pragma: no cover
    cantools = None

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

try:
    from openai import AzureOpenAI
except Exception:  # pragma: no cover
    AzureOpenAI = None

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None


# =========================================================
# Dataclass
# =========================================================
@dataclass
class RelatedSignalItem:
    msg_name: str
    sig_name: str
    original_lines: List[str] = field(default_factory=list)
    observed_values: List[str] = field(default_factory=list)


@dataclass
class DbcSignalEvidence:
    dbc_file: str
    message_name: str
    message_id: str
    message_id_decimal: str
    is_extended_frame: str
    dlc: str
    send_type: str
    cycle_time: str
    senders: str
    message_receivers: str
    message_comment: str
    signal_name: str
    start_bit: str
    length_bit: str
    byte_order: str
    signed: str
    initial_value: str
    factor: str
    offset: str
    minimum: str
    maximum: str
    unit: str
    signal_receivers: str
    value_type: str
    choices: str
    definition: str
    description: str
    signal_comment: str


@dataclass
class Step6Keyword:
    term: str
    meaning: str


@dataclass
class Step6SignalJudgement:
    reason: str
    keywords: List[Step6Keyword] = field(default_factory=list)


@dataclass
class ClassificationDecision:
    bucket: str
    scores: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)
    source: str = "heuristic"
    hard_rule: bool = False


# =========================================================
# 공통 유틸
# =========================================================
def _read_text_any(path: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return path.read_text(encoding=enc, errors="replace")
        except Exception:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


def _squash_spaces(s: object) -> str:
    txt = "" if s is None else str(s)
    txt = txt.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    txt = re.sub(r"\s{2,}", " ", txt)
    return txt.strip()


def _fmt(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        # 1.0처럼 정수 형태면 보기 좋게 정리
        if value.is_integer():
            return str(int(value))
    return str(value)


def _join_list(values: Iterable[object]) -> str:
    return ", ".join(str(v) for v in values if str(v).strip())


def _nonempty(*values: object) -> str:
    for value in values:
        txt = _squash_spaces(value)
        if txt and txt != "-":
            return txt
    return ""


def _truncate_text(text: str, limit: int = 12000) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + f"\n... (중략: {len(text) - limit}자)"



def _extract_case_main_no_from_name(name: str) -> Optional[int]:
    s = Path(name).stem
    m = re.search(r"_(\d+)(?:-[\d-]+)?번(?:_[a-z]+)?$", s, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"(\d+)(?:-[\d-]+)?번", s, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _extract_case_label_from_name(name: str) -> str:
    s = Path(name).stem
    m = re.search(r"_(\d+(?:-[\d-]+)?)번(?:_[a-z]+)?$", s, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"(\d+(?:-[\d-]+)?)번", s, flags=re.IGNORECASE)
    return m.group(1) if m else ""


def _extract_tc_prefix_from_name(name: str) -> str:
    s = Path(name).stem
    s = re.sub(r"^(AI답변_|AI문의용_|AI결과판단_분류_|AI결과판단_)", "", s)
    m = re.match(r"(?P<prefix>.+)_(\d+(?:-[\d-]+)?)번(?:_[a-z]+)?$", s, flags=re.IGNORECASE)
    return m.group("prefix").strip() if m else ""


def _is_nan_like(value) -> bool:
    try:
        import math
        if value is None:
            return True
        if isinstance(value, float) and math.isnan(value):
            return True
    except Exception:
        pass
    try:
        return str(value).strip().lower() in ("", "nan", "none", "null")
    except Exception:
        return False


def _shorten_reason_text(text: str, limit: int = 110) -> str:
    s = _squash_spaces(text)
    if not s or len(s) <= limit:
        return s
    return s[:limit].rstrip() + "..."


def _format_endpoint_role(ev: "DbcSignalEvidence") -> Tuple[str, str]:
    sender = ev.senders or "-"
    receiver = ev.signal_receivers or ev.message_receivers or "-"
    return sender, receiver


def _build_plain_meaning_from_evidence(ev: "DbcSignalEvidence", observed_values: List[str]) -> str:
    base = _nonempty(ev.definition, ev.description, ev.signal_comment, ev.message_comment)
    parts = []
    if base:
        parts.append(base)
    if ev.choices:
        parts.append(f"값 의미: {ev.choices}")
    if observed_values:
        parts.append("관측값: " + ", ".join(observed_values[:8]))
    return " / ".join(parts) if parts else "DBC에 명시 의미가 부족합니다. Message/Signal 명칭과 관측값을 함께 확인하세요."


# =========================================================
# AI답변 결과 수집
# =========================================================
def _collect_answer_roots(base_dir: Path, config) -> List[Path]:
    root_name = getattr(config, "output_root_dir_name", "AI답변_결과")
    req_root_name = getattr(config, "output_dir", "AI_문의용_출력")

    candidates = [
        base_dir / root_name,
        base_dir / req_root_name / root_name,  # 구버전/사용자 착각 경로 호환
    ]

    out: List[Path] = []
    seen = set()
    for p in candidates:
        try:
            rp = p.resolve()
        except Exception:
            rp = p
        if p.exists() and p.is_dir() and str(rp) not in seen:
            seen.add(str(rp))
            out.append(p)
    return out


def _normalize_retry_case_stem(name: str) -> str:
    """Step 5/Step 6/AI답변 파일명을 동일한 케이스 stem으로 정규화한다."""
    raw = str(name or "").strip()
    if raw.lower().endswith(".error.txt"):
        raw = raw[:-len(".error.txt")]
    elif raw.lower().endswith(".txt"):
        raw = raw[:-len(".txt")]
    else:
        raw = Path(raw).stem
        if raw.lower().endswith(".error"):
            raw = raw[:-len(".error")]

    for prefix in ("AI문의용_", "AI답변_", "AI결과판단_분류_", "AI결과판단_"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    return raw.strip()


def _strip_step5_split_suffix(case_stem: str) -> str:
    """Step 5 split suffix(_a, _b, ...)를 병합 케이스 stem으로 환원한다."""
    m = re.match(r"^(?P<base>.+)_(?P<suffix>[a-z]+)$", case_stem, flags=re.IGNORECASE)
    return m.group("base") if m else case_stem


def _make_retry_case_key(output_type: str, case_stem: str) -> str:
    return f"{str(output_type or '').strip().casefold()}::{str(case_stem or '').strip().casefold()}"


def _answer_retry_case_key(answer_path: Path, output_type: str) -> str:
    return _make_retry_case_key(output_type, _normalize_retry_case_stem(answer_path.name))


def _collect_current_step5_error_keys(base_dir: Path, config) -> set[str]:
    """현재 남아 있는 Step 5 입력 .error 파일의 병합 케이스 키를 수집한다."""
    input_root = base_dir / str(getattr(config, "input_root_dir_name", "AI_문의용_출력"))
    subfolders = list(getattr(config, "subfolders", ["메세지별", "시간별"]) or ["메세지별", "시간별"])
    out: set[str] = set()
    for sub_name in subfolders:
        sub_dir = input_root / sub_name
        if not sub_dir.exists():
            continue
        for err_path in sub_dir.glob("AI문의용_*.error.txt"):
            stem = _strip_step5_split_suffix(_normalize_retry_case_stem(err_path.name))
            if stem:
                out.add(_make_retry_case_key(sub_name, stem))
    return out


def _collect_step6_error_keys(base_dir: Path, config) -> set[str]:
    """판단 해설 폴더에 남아 있는 Step 6 .error 파일의 케이스 키를 수집한다."""
    out: set[str] = set()
    for root in _collect_answer_roots(base_dir, config):
        for output_type in ("메세지별", "시간별"):
            out_dir = root / _judgement_subfolder_name(output_type)
            if not out_dir.exists():
                continue
            for err_path in out_dir.glob("AI결과판단_*.error.txt"):
                if err_path.name.startswith("AI결과판단_분류_"):
                    continue
                stem = _normalize_retry_case_stem(err_path.name)
                if stem:
                    out.add(_make_retry_case_key(output_type, stem))
    return out


def _normalize_runtime_retry_keys(values) -> set[str]:
    out: set[str] = set()
    for value in list(values or []):
        text = str(value or "").strip().casefold()
        if "::" in text:
            out.add(text)
    return out


def _step6_error_path_for_answer(answer_path: Path, output_type: str) -> Path:
    answer_root = _answer_root_from_answer_path(answer_path)
    out_dir = answer_root / _judgement_subfolder_name(output_type)
    return out_dir / make_output_name(answer_path).replace(".txt", ".error.txt")


def _remove_step6_error_if_exists(answer_path: Path, output_type: str) -> None:
    err_path = _step6_error_path_for_answer(answer_path, output_type)
    try:
        if err_path.exists():
            err_path.unlink()
            print(f"[OK] 이전 Step 7 에러로그 삭제: {err_path.name}")
    except Exception as e:
        print(f"[WARN] Step 7 에러로그 삭제 실패: {err_path} ({e})")


def _is_probable_split_file(path: Path) -> bool:
    m = re.match(r"^(?P<base>.+)_(?P<suffix>[a-z]+)$", path.stem, flags=re.IGNORECASE)
    if not m:
        return False
    return path.with_name(m.group("base") + path.suffix).exists()


def collect_answer_files(base_dir: Path, config) -> List[Tuple[Path, str]]:
    roots = _collect_answer_roots(base_dir, config)
    subfolders = list(getattr(config, "subfolders", ["메세지별", "시간별"]) or ["메세지별", "시간별"])

    all_answers: List[Tuple[Path, str]] = []
    seen = set()
    for root in roots:
        for sub_name in subfolders:
            sub_dir = root / sub_name
            if not sub_dir.exists():
                continue
            for p in sorted(sub_dir.glob("AI답변_*.txt"), key=lambda x: x.name):
                if p.name.endswith(".error.txt"):
                    continue
                if _is_probable_split_file(p):
                    continue
                key = str(p.resolve())
                if key in seen:
                    continue
                seen.add(key)
                output_type = "시간별" if ("시간별" in p.stem or sub_name == "시간별") else "메세지별"
                all_answers.append((p, output_type))

    if not getattr(config, "retry_failed_only", False):
        return all_answers

    step5_runtime_keys = _normalize_runtime_retry_keys(getattr(config, "step_5_retry_case_keys", []))
    current_step5_error_keys = _collect_current_step5_error_keys(base_dir, config)
    step6_error_keys = _collect_step6_error_keys(base_dir, config)
    target_keys = step5_runtime_keys | current_step5_error_keys | step6_error_keys

    print(
        "[RETRY][STEP7-LEGACY] 대상 합집합: "
        f"Step5 선정={len(step5_runtime_keys)} / "
        f"현재 Step5 .error={len(current_step5_error_keys)} / "
        f"Step6 .error={len(step6_error_keys)} / "
        f"합계(중복제거)={len(target_keys)}"
    )

    if not target_keys:
        print("[RETRY][STEP7-LEGACY] 실패파일 재실행 대상이 없습니다.")
        return []

    result: List[Tuple[Path, str]] = []
    unresolved: List[str] = []
    available_keys = set()
    for answer_path, output_type in all_answers:
        key = _answer_retry_case_key(answer_path, output_type)
        available_keys.add(key)
        if key not in target_keys:
            continue
        if key in current_step5_error_keys:
            unresolved.append(f"{output_type}/{answer_path.name}")
            continue
        result.append((answer_path, output_type))

    missing_answers = sorted(target_keys - available_keys)
    if unresolved:
        print(f"[RETRY][STEP7-LEGACY][HOLD] Step 5 .error가 남아 처리 보류: {len(unresolved)}개")
        for item in unresolved[:20]:
            print(f"  - {item}")
    if missing_answers:
        print(f"[RETRY][STEP7-LEGACY][WAIT] 대응 AI답변 파일이 아직 없는 대상: {len(missing_answers)}개")
        for key in missing_answers[:20]:
            print(f"  - {key}")

    print(f"[RETRY][STEP7-LEGACY] 실제 재처리 AI답변: {len(result)}개")
    return result


# =========================================================
# Step 5 답변 파싱
# =========================================================
_RELATED_LINE_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)?sec\s+)?(?:CH\d+\s+)?(?P<msg>[A-Za-z_][\w\-]*)\s*:\s*(?P<sig>[A-Za-z_][\w\-]*)\b(?P<tail>.*)$",
    flags=re.IGNORECASE,
)


def _split_related_section(text: str) -> List[str]:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")

    # 첫 줄은 보통 파일명 제목이므로 제외. 명시적인 "연관 없는 메세지" 전까지만 관련 후보로 본다.
    body = lines[1:] if lines else []
    related_lines: List[str] = []

    for line in body:
        s = line.strip()
        if re.match(r"^연관\s*없는\s*메세지\s*(?:[:：]\s*)?$", s):
            break
        if not s:
            continue
        if s in ("연관 있는 메세지", "연관 있는 메세지 없음"):
            continue
        if s.startswith("#"):
            continue
        if _RELATED_LINE_RE.match(s):
            related_lines.append(s)

    return related_lines


def _extract_observed_value_from_tail(tail: str) -> str:
    s = (tail or "").strip()
    if not s:
        return ""

    # definition/description 뒤쪽은 값 관측 요약에서 제외
    s = re.sub(r"\s*\(\s*(?:definition|description)\s*:.*$", "", s, flags=re.IGNORECASE)
    s = s.strip()
    return s


def parse_related_signals(answer_path: Path) -> List[RelatedSignalItem]:
    text = _read_text_any(answer_path)
    related_lines = _split_related_section(text)

    by_key: Dict[Tuple[str, str], RelatedSignalItem] = {}
    order: List[Tuple[str, str]] = []

    for line in related_lines:
        m = _RELATED_LINE_RE.match(line)
        if not m:
            continue
        msg = m.group("msg").strip()
        sig = m.group("sig").strip()
        tail = m.group("tail") or ""
        key = (msg, sig)
        if key not in by_key:
            by_key[key] = RelatedSignalItem(msg_name=msg, sig_name=sig)
            order.append(key)
        item = by_key[key]
        if line not in item.original_lines:
            item.original_lines.append(line)
        value_text = _extract_observed_value_from_tail(tail)
        if value_text and value_text not in item.observed_values:
            item.observed_values.append(value_text)

    return [by_key[k] for k in order]


# =========================================================
# DBC description 보완 파싱
# =========================================================
def parse_ba_description_map_from_dbc_text(dbc_path: Path) -> Dict[Tuple[int, str], str]:
    try:
        text = _read_text_any(dbc_path)
    except Exception:
        return {}

    out: Dict[Tuple[int, str], str] = {}
    prefix = 'BA_ "Description" SG_'
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith(prefix):
            continue
        rest = s[len(prefix):].strip()
        parts = rest.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            fid = int(parts[0])
        except Exception:
            continue
        sig = parts[1]
        remainder = parts[2].strip()
        if not remainder.startswith('"'):
            continue
        end = remainder.rfind('";')
        if end == -1:
            continue
        raw_txt = remainder[1:end]
        raw_txt = raw_txt.replace(r"\\", "\\").replace(r"\"", '"')
        out[(fid, sig)] = _squash_spaces(raw_txt)
    return out


def _pick_comment(raw_comments) -> str:
    if not raw_comments:
        return ""
    if isinstance(raw_comments, dict):
        candidate = raw_comments.get("EN") or raw_comments.get(None)
        if not candidate:
            for v in raw_comments.values():
                if v:
                    candidate = v
                    break
        return _squash_spaces(candidate)
    return _squash_spaces(raw_comments)


# =========================================================
# DBC 검색
# =========================================================
def _is_valid_dbc_name(name: object) -> bool:
    s = str(name or "").strip()
    if not s:
        return False
    if s.lower() in ("n/a", "na", "none", "null"):
        return False
    return True


def _resolve_dbc_path(base_dir: Path, dbc_name: object) -> Optional[Path]:
    if not _is_valid_dbc_name(dbc_name):
        return None
    p = Path(str(dbc_name).strip())
    if not p.is_absolute():
        p = base_dir / p
    return p if p.exists() and p.is_file() else None


def collect_dbc_files(base_dir: Path, config=None) -> List[Path]:
    """
    Step 6 검색 대상 DBC를 제한한다.
    - 1순위: GUI/main에서 선택된 config.dbc_name_by_ch 값
      예: CAN1=P1, CAN2=M, CAN3=C이면 해당 P1/M/C DBC만 검색
    - 2순위: dbc_files_step2
    - 3순위: 선택 정보가 전혀 없을 때만 base_dir/*.dbc 전체 검색(호환용)
    """
    selected: List[Path] = []
    seen = set()

    if config is not None:
        dbc_map = getattr(config, "dbc_name_by_ch", {}) or {}
        if isinstance(dbc_map, dict):
            for ch in sorted(dbc_map.keys(), key=lambda x: str(x)):
                p = _resolve_dbc_path(base_dir, dbc_map.get(ch))
                if p is None:
                    continue
                key = str(p.resolve())
                if key not in seen:
                    seen.add(key)
                    selected.append(p)

        if not selected:
            for name in list(getattr(config, "dbc_files_step2", []) or []):
                p = _resolve_dbc_path(base_dir, name)
                if p is None:
                    continue
                key = str(p.resolve())
                if key not in seen:
                    seen.add(key)
                    selected.append(p)

    if selected:
        return selected

    # 선택 DBC 정보가 없는 경우만 전체 검색으로 fallback
    return sorted([p for p in base_dir.glob("*.dbc") if p.is_file()], key=lambda x: x.name.lower())


def _choices_to_text(choices) -> str:
    if not choices:
        return ""
    try:
        items = []
        for k, v in dict(choices).items():
            kk = f"0x{int(k):X}" if isinstance(k, int) else str(k)
            items.append(f"{kk}:{v}")
        return " / ".join(items)
    except Exception:
        return _squash_spaces(choices)


def _build_evidence_from_match(dbc_path: Path, msg, sig, ba_desc_map: Dict[Tuple[int, str], str]) -> DbcSignalEvidence:
    frame_id = getattr(msg, "frame_id", None)
    frame_id_int = int(frame_id) if frame_id is not None else None

    signal_comment = _squash_spaces(getattr(sig, "comment", ""))
    description = _squash_spaces(getattr(sig, "description", ""))
    if not description and frame_id_int is not None:
        description = ba_desc_map.get((frame_id_int, getattr(sig, "name", "")), "")
    if not description:
        description = _pick_comment(getattr(sig, "comments", None))

    definition = signal_comment
    if definition and description and definition == description:
        description = ""

    cycle_time = getattr(msg, "cycle_time", None)
    if cycle_time in (None, ""):
        cycle_time = getattr(msg, "cycle", None)

    send_type = getattr(msg, "send_type", None)
    if send_type in (None, ""):
        send_type = getattr(msg, "cycle_time", None)
        send_type = "" if send_type in (None, "") else "Cyclic"

    sig_initial = getattr(sig, "initial", None)
    if sig_initial is None:
        sig_initial = getattr(sig, "raw_initial", None)

    msg_receivers = getattr(msg, "receivers", None) or []
    if not msg_receivers:
        try:
            agg = []
            for s in getattr(msg, "signals", []) or []:
                for r in getattr(s, "receivers", []) or []:
                    if r not in agg:
                        agg.append(r)
            msg_receivers = agg
        except Exception:
            msg_receivers = []

    value_type = "Signed" if bool(getattr(sig, "is_signed", False)) else "Unsigned"

    return DbcSignalEvidence(
        dbc_file=dbc_path.name,
        message_name=_fmt(getattr(msg, "name", "")),
        message_id=(f"0x{frame_id_int:X}" if frame_id_int is not None else ""),
        message_id_decimal=(str(frame_id_int) if frame_id_int is not None else ""),
        is_extended_frame=_fmt(getattr(msg, "is_extended_frame", "")),
        dlc=_fmt(getattr(msg, "length", "")),
        send_type=_fmt(send_type),
        cycle_time=_fmt(cycle_time),
        senders=_join_list(getattr(msg, "senders", []) or []),
        message_receivers=_join_list(msg_receivers),
        message_comment=_squash_spaces(getattr(msg, "comment", "")),
        signal_name=_fmt(getattr(sig, "name", "")),
        start_bit=_fmt(getattr(sig, "start", "")),
        length_bit=_fmt(getattr(sig, "length", "")),
        byte_order=_fmt(getattr(sig, "byte_order", "")),
        signed=_fmt(bool(getattr(sig, "is_signed", False))),
        initial_value=_fmt(sig_initial),
        factor=_fmt(getattr(sig, "scale", "")),
        offset=_fmt(getattr(sig, "offset", "")),
        minimum=_fmt(getattr(sig, "minimum", "")),
        maximum=_fmt(getattr(sig, "maximum", "")),
        unit=_fmt(getattr(sig, "unit", "")),
        signal_receivers=_join_list(getattr(sig, "receivers", []) or []),
        value_type=value_type,
        choices=_choices_to_text(getattr(sig, "choices", {}) or {}),
        definition=definition,
        description=description,
        signal_comment=signal_comment,
    )


def build_dbc_index(base_dir: Path, config=None) -> Dict[Tuple[str, str], List[DbcSignalEvidence]]:
    if cantools is None:
        raise ImportError("cantools 패키지가 설치되어 있지 않습니다. py -m pip install cantools 필요")

    index: Dict[Tuple[str, str], List[DbcSignalEvidence]] = {}
    dbc_files = collect_dbc_files(base_dir, config=config)
    if not dbc_files:
        print(f"[WARN] Step 6 검색 대상 DBC 파일이 없습니다: {base_dir}")
        return index

    if config is not None and getattr(config, "dbc_name_by_ch", None):
        print(f"[INFO] Step 6 DBC 검색 대상: 선택된 DBC {len(dbc_files)}개")
    else:
        print(f"[INFO] Step 6 DBC 검색 대상: {len(dbc_files)}개")

    for dbc_path in dbc_files:
        try:
            db = cantools.database.load_file(str(dbc_path))
        except Exception as e:
            print(f"[WARN] DBC 로드 실패: {dbc_path.name} ({e})")
            continue

        ba_desc_map = parse_ba_description_map_from_dbc_text(dbc_path)
        msg_count = 0
        sig_count = 0
        for msg in getattr(db, "messages", []) or []:
            msg_count += 1
            for sig in getattr(msg, "signals", []) or []:
                sig_count += 1
                key = (str(getattr(msg, "name", "")), str(getattr(sig, "name", "")))
                if not key[0] or not key[1]:
                    continue
                try:
                    evidence = _build_evidence_from_match(dbc_path, msg, sig, ba_desc_map)
                    index.setdefault(key, []).append(evidence)
                except Exception as e:
                    print(f"[WARN] DBC signal evidence 생성 실패: {dbc_path.name} {key} ({e})")
                    continue
        print(f"[OK] DBC indexed: {dbc_path.name} / messages={msg_count}, signals={sig_count}")

    print(f"[OK] Step 6 DBC index entries: {len(index)}")
    return index


# Step 7 AI 판단 근거 생성
# =========================================================
def _step6_ai_enabled(config) -> bool:
    return bool(getattr(config, "step_7_enable_ai_judgement", getattr(config, "step_6_enable_ai_judgement", True)))


def _ask_gpt_for_step6(prompt: str, config) -> str:
    if AzureOpenAI is None:
        raise ImportError("openai 패키지가 설치되지 않았습니다. py -m pip install openai 필요")
    headers = {}
    project_id = getattr(config, "project_id", "") or ""
    if project_id:
        headers["X-Project-Id"] = project_id
    client = AzureOpenAI(
        azure_endpoint=getattr(config, "base_url", ""),
        api_key=getattr(config, "api_key", ""),
        api_version=getattr(config, "api_version", "2025-04-01-preview"),
        default_headers=headers if headers else None,
    )
    messages = [
        {"role": "system", "content": "차량 CAN/DBC 신호 검토를 돕는 전문가입니다. 근거 기반으로 짧고 명확하게 한국어로 설명하세요."},
        {"role": "user", "content": prompt},
    ]
    completion = client.chat.completions.create(
        model=getattr(config, "gpt_model", "gpt-5.6-terra"),
        messages=messages,
    )
    content = completion.choices[0].message.content
    return content if content is not None else ""


def _extract_gemini_text(resp_json: dict) -> str:
    candidates = resp_json.get("candidates") or []
    if candidates:
        content = (candidates[0] or {}).get("content") or {}
        parts = content.get("parts") or []
        texts = [p.get("text", "") for p in parts if p.get("text")]
        if texts:
            return "".join(texts)
    for key in ("outputText", "text", "result"):
        if isinstance(resp_json.get(key), str):
            return resp_json[key]
    return str(resp_json)


def _ask_gemini_for_step6(prompt: str, config) -> str:
    if requests is None:
        raise ImportError("requests 패키지가 설치되지 않았습니다. py -m pip install requests 필요")
    base_url = getattr(config, "base_url", "")
    model = getattr(config, "gemini_model", "gemini-3.1-pro-preview")
    stream_option = getattr(config, "gemini_stream_option", "generateContent")
    url = f"{base_url}/models/{model}:{stream_option}"
    params = {"key": getattr(config, "api_key", "")}
    headers = {"Content-Type": "application/json"}
    project_id = getattr(config, "project_id", "") or ""
    if project_id:
        headers["X-Project-Id"] = project_id
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    r = requests.post(url, params=params, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    return _extract_gemini_text(r.json())


def _ask_ai_for_step6(prompt: str, config) -> str:
    provider = str(getattr(config, "ai_provider", "gpt") or "gpt").lower()
    if provider == "gpt":
        return _ask_gpt_for_step6(prompt, config)
    if provider == "gemini":
        return _ask_gemini_for_step6(prompt, config)
    raise ValueError(f"지원하지 않는 ai_provider: {provider}")


def _find_excel_file(base_dir: Path, excel_glob: str) -> Optional[Path]:
    return find_excel_file_compat(base_dir, excel_glob, required=False)


def _normalize_sheet_name(value: object) -> str:
    return re.sub(r"[\s_.\-]+", "", str(value or "").strip().lower())


def _resolve_excel_sheet_name(excel_path: Path, desired: str) -> Optional[str]:
    if pd is None or not desired:
        return desired or None
    try:
        sheet_names = list(excel_file_compat(excel_path).sheet_names)
    except Exception:
        return desired
    if desired in sheet_names:
        return desired
    target = _normalize_sheet_name(desired)
    exact_normalized = [s for s in sheet_names if _normalize_sheet_name(s) == target]
    if exact_normalized:
        return exact_normalized[0]
    # "5. 시동 및 주행" ↔ "시동 및 주행"처럼 번호 접두부 차이를 허용한다.
    target_no_num = re.sub(r"^\d+", "", target)
    candidates = [s for s in sheet_names if re.sub(r"^\d+", "", _normalize_sheet_name(s)) == target_no_num]
    return candidates[0] if len(candidates) == 1 else desired


def _load_tc_map_from_excel_for_step6(config) -> Dict[Tuple[int, int], Tuple[str, str, str]]:
    if pd is None:
        return {}

    base_dir = Path(config.base_dir)
    excel_path = _find_excel_file(base_dir, getattr(config, "excel_glob", "TestCase_모음*.xls*"))
    if excel_path is None:
        return {}

    desired_sheet = getattr(config, "category_prefix", "") or getattr(config, "active_category", "")
    sheet_name = _resolve_excel_sheet_name(excel_path, desired_sheet)
    if not sheet_name:
        return {}

    tc_no_col_idx = int(getattr(config, "tc_no_column_index", 0))
    tc_class_col_idx = int(getattr(config, "tc_class_col_idx", getattr(config, "tc_class_column_index", 1)))
    tc_col_idx = int(getattr(config, "tc_col_idx", getattr(config, "tc_column_index", 2)))
    tc_expected_col_idx = int(getattr(config, "tc_expected_col_idx", 3))
    start_row_excel = int(getattr(config, "start_row_excel", 2))
    intentional_blank_token = str(getattr(config, "intentional_blank_token", "__BLANK__"))

    try:
        df = read_excel_compat(excel_path, sheet_name=sheet_name, header=None)
    except Exception as e:
        print(f"[WARN] Step 6 엑셀 sheet 읽기 실패: {excel_path.name} / {sheet_name} ({e})")
        return {}

    start_idx = max(0, start_row_excel - 1)
    try:
        ffill_dataframe_columns_compat(df, start_idx, [tc_no_col_idx, tc_class_col_idx])
    except Exception:
        pass

    tc_map: Dict[Tuple[int, int], Tuple[str, str, str]] = {}
    counters: Dict[int, int] = {}
    last_text: Dict[int, str] = {}

    for i in range(start_idx, len(df)):
        no_val = df.iat[i, tc_no_col_idx] if tc_no_col_idx < len(df.columns) else None
        if _is_nan_like(no_val):
            continue
        try:
            tc_no = int(float(str(no_val).strip()))
        except Exception:
            continue

        sub_no = counters.get(tc_no, 0) + 1
        counters[tc_no] = sub_no

        class_val = df.iat[i, tc_class_col_idx] if tc_class_col_idx < len(df.columns) else None
        tc_class = "" if _is_nan_like(class_val) else str(class_val).strip()

        raw = df.iat[i, tc_col_idx] if tc_col_idx < len(df.columns) else None
        if _is_nan_like(raw):
            tc_text = last_text.get(tc_no, "")
        else:
            s = str(raw).strip()
            if s == intentional_blank_token:
                tc_text = ""
                last_text[tc_no] = ""
            else:
                tc_text = s
                last_text[tc_no] = tc_text

        raw_expected = df.iat[i, tc_expected_col_idx] if tc_expected_col_idx < len(df.columns) else None
        if _is_nan_like(raw_expected):
            tc_expected = "예상결과 없음"
        else:
            s_expected = str(raw_expected).strip()
            tc_expected = "예상결과 없음" if not s_expected or s_expected == intentional_blank_token else s_expected

        tc_map[(tc_no, sub_no)] = (tc_class, tc_text, tc_expected)

    return tc_map


def _find_source_prompt_for_answer(base_dir: Path, answer_path: Path, output_type: str, config) -> str:
    """AI답변 파일명에 대응되는 AI문의용 원문을 찾는다. 분할본이면 첫 분할본의 상단 TC 정보를 사용한다."""
    stem = answer_path.stem
    req_stem = stem.replace("AI답변_", "AI문의용_", 1) if stem.startswith("AI답변_") else "AI문의용_" + stem
    output_dir_name = getattr(config, "output_dir", "AI_문의용_출력")
    search_dirs = [
        base_dir / output_dir_name / output_type,
        base_dir / output_dir_name / "메세지별",
        base_dir / output_dir_name / "시간별",
        base_dir / output_dir_name,
    ]
    uniq_dirs: List[Path] = []
    seen = set()
    for d in search_dirs:
        key = str(d)
        if key not in seen:
            seen.add(key)
            uniq_dirs.append(d)

    for d in uniq_dirs:
        p = d / f"{req_stem}{answer_path.suffix}"
        if p.exists() and p.is_file():
            return _truncate_text(_read_text_any(p), limit=6000)

    for d in uniq_dirs:
        if not d.exists():
            continue
        split_candidates = sorted(
            [p for p in d.glob(f"{req_stem}_*.txt") if p.is_file()],
            key=lambda x: x.name,
        )
        if split_candidates:
            return _truncate_text(_read_text_any(split_candidates[0]), limit=6000)
    return ""

def _select_primary_evidence(evidences: List[DbcSignalEvidence]) -> Optional[DbcSignalEvidence]:
    if not evidences:
        return None
    # 선택된 DBC 순서대로 들어온 첫 번째 후보를 기본 채택하되, 설명 정보가 있는 후보를 약간 우선한다.
    scored = []
    for i, ev in enumerate(evidences):
        score = 0
        if ev.senders:
            score += 2
        if ev.signal_receivers or ev.message_receivers:
            score += 2
        if ev.definition or ev.description or ev.message_comment:
            score += 2
        if ev.choices:
            score += 1
        scored.append((-score, i, ev))
    scored.sort(key=lambda x: (x[0], x[1]))
    return scored[0][2]


def _signal_meaning_for_output(ev: Optional[DbcSignalEvidence]) -> str:
    if ev is None:
        return "DBC 매칭 실패로 확인 불가"
    return _nonempty(ev.definition, ev.description, ev.signal_comment, ev.message_comment) or "DBC에 명시 의미가 부족합니다. Message/Signal 명칭과 값 의미를 함께 확인하세요."


def _build_ai_reason_prompt(base_dir: Path, answer_path: Path, output_type: str, items: List[RelatedSignalItem], chosen: Dict[Tuple[str, str], Optional[DbcSignalEvidence]], config) -> str:
    source_prompt = _find_source_prompt_for_answer(base_dir, answer_path, output_type, config)
    if not source_prompt:
        source_prompt = _extract_tc_info_from_excel_fallback(base_dir, answer_path, output_type, config)
    rows: List[str] = []
    for idx, item in enumerate(items, 1):
        ev = chosen.get((item.msg_name, item.sig_name))
        rows.append(f"[{idx}] {item.msg_name} : {item.sig_name}")
        rows.append("Step5 원문: " + " | ".join(item.original_lines[:8]))
        rows.append("Sender MCU: " + ((ev.senders if ev else "") or "-"))
        rows.append("Signal Receiver MCU: " + ((ev.signal_receivers if ev else "") or "-"))
        rows.append("Message Receiver: " + ((ev.message_receivers if ev else "") or "-"))
        rows.append("신호 의미: " + _signal_meaning_for_output(ev))
        rows.append("값 의미: " + ((ev.choices if ev else "") or "-"))
        rows.append("Description: " + ((ev.description if ev else "") or "-"))
        rows.append("Definition: " + ((ev.definition if ev else "") or "-"))
        rows.append("Message Comment: " + ((ev.message_comment if ev else "") or "-"))
        rows.append("")

    return _truncate_text(f"""
[목표]
아래는 Step 5에서 TC와 연관 있다고 추려진 Message:Signal과 선택 DBC 근거입니다.
각 신호별로 '왜 이 시그널이 해당 TC와 연관 있다고 볼 수 있는지'를 한국어 한두 문장으로 설명하고,
사람이 볼 때 가장 중요한 키워드 1~2개만 뽑아 짧게 풀이하세요.
최종 PASS/FAIL을 단정하지 말고, 연관 판단 근거만 작성하세요.

[원본 AI답변 파일]
{answer_path.name}

[출력 규칙 - 매우 중요]
- 반드시 JSON 배열만 출력하세요. Markdown 코드블록 금지.
- 각 원소는 message, signal, reason, keywords 키를 포함하세요.
- reason은 1~2문장으로 짧게 작성하세요.
- keywords는 최대 2개만 작성하세요.
- keywords의 각 원소는 term, meaning 키를 포함하세요.
- term은 예: EPB, SCU, N Mode, Brake, Gear 같은 핵심어만 작성하세요.
- DBC 근거가 부족하면 부족하다고 적되, Step5 원문/신호명 기준의 추정 근거를 함께 적으세요.

[대응 AI문의용/TC 정보]
{source_prompt if source_prompt else '(대응 AI문의용 원문을 찾지 못했습니다.)'}

[신호별 DBC 근거]
{chr(10).join(rows)}
""".strip(), limit=22000)


def _parse_ai_reason_json(answer: str) -> Dict[Tuple[str, str], Step6SignalJudgement]:
    text = (answer or "").strip()
    if not text:
        return {}
    m = re.search(r"\[\s*\{.*\}\s*\]", text, flags=re.DOTALL)
    if m:
        text = m.group(0)
    data = json.loads(text)
    out: Dict[Tuple[str, str], Step6SignalJudgement] = {}
    if isinstance(data, list):
        for row in data:
            if not isinstance(row, dict):
                continue
            msg = str(row.get("message", "")).strip()
            sig = str(row.get("signal", "")).strip()
            reason = _squash_spaces(row.get("reason", ""))
            keywords: List[Step6Keyword] = []
            raw_keywords = row.get("keywords", [])
            if isinstance(raw_keywords, list):
                for kw in raw_keywords[:2]:
                    if isinstance(kw, dict):
                        term = _squash_spaces(kw.get("term", ""))
                        meaning = _squash_spaces(kw.get("meaning", ""))
                    else:
                        term = _squash_spaces(kw)
                        meaning = ""
                    if term:
                        keywords.append(Step6Keyword(term=term, meaning=meaning))
            if msg and sig and reason:
                out[(msg, sig)] = Step6SignalJudgement(reason=reason, keywords=keywords)
    return out


def _fallback_keywords_from_text(item: RelatedSignalItem, ev: Optional[DbcSignalEvidence], reason: str) -> List[Step6Keyword]:
    """AI keywords가 비어 있을 때만 쓰는 보조 키워드 추출. 과다 추출 방지를 위해 최대 2개."""
    source = " ".join([
        item.msg_name, item.sig_name,
        ev.definition if ev else "", ev.description if ev else "", ev.message_comment if ev else "", reason or "",
    ])
    candidates: List[str] = []
    # 차량 도메인에서 사람이 판단에 자주 쓰는 대문자/혼합 약어 우선
    for token in re.findall(r"\b[A-Z][A-Z0-9_]{1,12}\b", source):
        if token in {"CAN", "FD", "DBC", "MSG", "SIG", "EC", "P"}:
            continue
        if token not in candidates:
            candidates.append(token)
    # N Mode 같은 표현 보완
    if re.search(r"N\s*Mode", source, flags=re.IGNORECASE) and "N Mode" not in candidates:
        candidates.insert(0, "N Mode")
    out: List[Step6Keyword] = []
    for term in candidates[:2]:
        meaning = "DBC/Step5 원문에서 반복적으로 확인되는 핵심 판단 키워드"
        if term.upper() == "EPB":
            meaning = "전자식 주차 브레이크 관련 요청/상태 키워드"
        elif term.upper() in {"SCU", "SBW", "TCU", "ESC", "BDC", "CGW"}:
            meaning = "해당 신호의 송신/수신 또는 기능 흐름과 관련된 제어기/시스템 키워드"
        elif term == "N Mode":
            meaning = "N 모드 요청 또는 상태 판단과 관련된 기능 키워드"
        out.append(Step6Keyword(term=term, meaning=meaning))
    return out


def generate_ai_judgement_map(base_dir: Path, answer_path: Path, output_type: str, items: List[RelatedSignalItem], chosen: Dict[Tuple[str, str], Optional[DbcSignalEvidence]], config) -> Dict[Tuple[str, str], Step6SignalJudgement]:
    default_no_key = "API KEY가 감지되지 않아 AI 판단 근거를 생성하지 않았습니다."
    default_disabled = "Step 7 AI 판단 옵션이 비활성화되어 AI 판단 근거를 생성하지 않았습니다."
    default_failed = "AI 판단 근거 생성에 실패했습니다. Step 5 원문 라인과 DBC 근거를 기준으로 수동 검토하세요."

    if not items:
        return {}
    if not _step6_ai_enabled(config):
        return {(item.msg_name, item.sig_name): Step6SignalJudgement(reason=default_disabled) for item in items}
    if not str(getattr(config, "api_key", "") or "").strip():
        return {(item.msg_name, item.sig_name): Step6SignalJudgement(reason=default_no_key) for item in items}

    prompt = _build_ai_reason_prompt(base_dir, answer_path, output_type, items, chosen, config)
    max_retry = int(getattr(config, "step_6_ai_max_retry", 2) or 2)
    wait_sec = float(getattr(config, "retry_wait_seconds", 2.0) or 2.0)
    last_exc: Exception | None = None
    for attempt in range(1, max_retry + 1):
        try:
            print(f"[INFO] Step 7 AI 판단 근거/키워드 생성: {answer_path.name} ({attempt}/{max_retry})")
            answer = (_ask_ai_for_step6(prompt, config) or "").strip()
            judgement_map = _parse_ai_reason_json(answer)
            if judgement_map:
                for item in items:
                    key = (item.msg_name, item.sig_name)
                    judgement_map.setdefault(key, Step6SignalJudgement(reason=default_failed))
                    if not judgement_map[key].keywords:
                        judgement_map[key].keywords = _fallback_keywords_from_text(item, chosen.get(key), judgement_map[key].reason)
                return judgement_map
            last_exc = ValueError("AI 응답 JSON 파싱 결과가 비어 있음")
        except Exception as e:
            last_exc = e
            print(f"[WARN] Step 7 AI 판단 근거/키워드 생성 실패: {answer_path.name} ({attempt}/{max_retry}) {e}")
            if attempt < max_retry:
                time.sleep(wait_sec)
    print(f"[WARN] Step 7 AI 판단 근거/키워드 최종 실패: {answer_path.name} ({last_exc})")
    return {(item.msg_name, item.sig_name): Step6SignalJudgement(reason=default_failed) for item in items}


# =========================================================
# TC 단위 입력/출력/제외 분류 - REV 11 하이브리드 분류
# =========================================================
def _extract_section(text: str, start_title: str, end_titles: List[str]) -> str:
    pattern = re.compile(rf"\[{re.escape(start_title)}\]\s*(.*)", flags=re.DOTALL)
    m = pattern.search(text or "")
    if not m:
        return ""
    tail = m.group(1)
    end_positions = []
    for title in end_titles:
        mm = re.search(rf"\n\[{re.escape(title)}\]", tail)
        if mm:
            end_positions.append(mm.start())
    return tail[:min(end_positions)].strip() if end_positions else tail.strip()


def _extract_tc_info_from_excel_fallback(base_dir: Path, answer_path: Path, output_type: str, config) -> str:
    main_no = _extract_case_main_no_from_name(answer_path.name)
    label = _extract_case_label_from_name(answer_path.name)
    tc_prefix = _extract_tc_prefix_from_name(answer_path.name)
    if main_no is None:
        return f"[파일명]\n{answer_path.name}\n\n[TC 정보]\n- 대응 AI문의용 원문과 엑셀 fallback 모두 찾지 못했습니다."

    tc_map = _load_tc_map_from_excel_for_step6(config)
    if not tc_map:
        return f"[파일명]\n{answer_path.name}\n\n[TC 정보]\n- 대응 AI문의용 원문을 찾지 못했고, 엑셀 fallback도 읽지 못했습니다."

    selected = None
    label_m = re.match(r"^(?P<main>\d+)(?:-(?P<subs>[\d-]+))?$", label or "")
    if label_m:
        try:
            main2 = int(label_m.group("main"))
            subs = label_m.group("subs")
            # 013-2번은 두 번째 하위 TC로 해석한다. 기존 '하이픈 개수' 방식의 오선택을 방지한다.
            sub_idx = int(subs.split("-")[-1]) if subs else 1
            if (main2, sub_idx) in tc_map:
                selected = ((main2, sub_idx), tc_map[(main2, sub_idx)])
        except Exception:
            pass

    if selected is None:
        exact_candidates = sorted(
            [(k, v) for k, v in tc_map.items() if k[0] == main_no],
            key=lambda x: x[0][1],
        )
        if exact_candidates:
            selected = exact_candidates[0]

    if selected is None:
        return f"[파일명]\n{answer_path.name}\n\n[TC 정보]\n- 대응 AI문의용 원문을 찾지 못했고, 엑셀에서 해당 TC 번호를 찾지 못했습니다."

    (tc_no, sub_no), (tc_class, tc_text, tc_expected) = selected
    tc_label = f"{tc_no:03d}" if sub_no == 1 else f"{tc_no:03d}-{sub_no}"
    file_title = f"{tc_prefix} {tc_label}번.txt".strip() if tc_prefix else answer_path.name
    return (
        f"[파일명]\n{file_title}\n\n"
        f"[TC 정보]\n"
        f"TC 순번: {tc_label}번\n"
        f"TC 분류: {tc_class or '-'}\n"
        f"TC 내용: {tc_text or '-'}\n"
        f"TC 예상 결과: {tc_expected or '예상결과 없음'}"
    ).strip()


def _extract_tc_info_text(base_dir: Path, answer_path: Path, output_type: str, config) -> str:
    source_prompt = _find_source_prompt_for_answer(base_dir, answer_path, output_type, config)
    if source_prompt:
        file_name = _extract_section(source_prompt, "파일명", ["TC 정보", "요청"])
        tc_info = _extract_section(source_prompt, "TC 정보", ["요청", "출력 방법", "관측된 시그널 목록"])
        return f"[파일명]\n{file_name or answer_path.name}\n\n[TC 정보]\n{tc_info or '- TC 정보 추출 실패'}".strip()
    return _extract_tc_info_from_excel_fallback(base_dir, answer_path, output_type, config)


# 신호명은 underscore와 CamelCase를 모두 토큰화한 뒤 점수화한다.
_INPUT_TOKENS = {
    "BTN": 3.5, "BUTTON": 3.5, "SW": 3.0, "SWITCH": 3.0, "LVR": 3.0, "LEVER": 3.0,
    "PEDAL": 3.5, "KEY": 2.5, "KNOB": 3.0, "HMI": 2.0, "TOUCH": 3.0, "PUSH": 2.0,
    "SELECTOR": 2.5, "ROTARY": 2.5, "USER": 1.5,
}
_OUTPUT_TOKENS = {
    "REQ": 2.5, "REQUEST": 2.5, "CMD": 3.0, "COMMAND": 3.0, "TAR": 2.5, "TARGET": 2.5,
    "ACT": 2.0, "ACTUAL": 2.0, "STA": 1.5, "STATE": 1.5, "STATUS": 1.5, "FDBK": 2.5,
    "FEEDBACK": 2.5, "RESP": 2.0, "RESPONSE": 2.0, "ACK": 2.0, "IND": 1.5,
    "INDICATOR": 2.0, "LMP": 2.0, "LAMP": 2.0, "DIS": 1.5, "DISPLAY": 2.0,
    "OUT": 1.5, "OUTPUT": 2.0, "MODE": 1.0, "RESULT": 2.0, "DECISION": 2.0,
    "EVENT": 1.2, "TRIGGER": 1.5, "NOTIFY": 1.5, "NOTIFICATION": 1.5,
}
_EXCLUDED_TOKENS = {
    "CRC": 5.0, "ALV": 5.0, "ALIVE": 5.0, "CNT": 3.5, "COUNTER": 3.5, "CHECKSUM": 5.0,
    "TIMEOUT": 4.0, "DIAG": 4.0, "DTC": 4.0, "ERR": 4.0, "ERROR": 4.0, "RESERVED": 4.0,
    "DUMMY": 4.0, "RAW": 2.5, "SNA": 4.0, "VALIDITY": 3.0, "VALID": 1.5, "QUAL": 2.5,
    "QUALITY": 2.5, "ROLLING": 3.0, "E2E": 3.0,
}
_TC_STOPWORDS = {
    "정상", "확인", "동작", "상태", "여부", "경우", "시", "및", "또는", "후", "전", "관련", "신호",
    "값", "결과", "차량", "기능", "tc", "내용", "예상결과", "순번", "분류", "파일명",
    "the", "and", "or", "is", "are", "to", "of", "for", "with",
}
_CONCEPT_ALIASES = {
    "brake": ["brake", "brk", "pedal", "브레이크", "제동"],
    "gear": ["gear", "shift", "shftr", "sbw", "tcu", "scu", "변속", "기어", "p단", "r단", "n단", "d단"],
    "epb": ["epb", "parkingbrake", "parkbrake", "주차브레이크", "주차 브레이크", "체결"],
    "voice": ["voice", "vcrec", "recognition", "tts", "음성", "보이스"],
    "audio": ["audio", "amp", "sound", "volume", "오디오", "사운드"],
    "door": ["door", "tailgate", "trunk", "도어", "테일게이트", "트렁크"],
    "lock": ["lock", "unlock", "latch", "잠금", "해제"],
    "seat": ["seat", "시트"],
    "light": ["lamp", "light", "lmp", "indicator", "램프", "조명", "등"],
    "cluster": ["cluster", "clu", "display", "indicator", "클러스터", "표시"],
    "climate": ["datc", "blower", "temp", "climate", "aircon", "공조", "온도", "풍량"],
    "speed": ["speed", "spd", "kph", "velocity", "차속", "속도"],
    "start": ["start", "ign", "ignition", "engine", "시동"],
    "window": ["window", "glass", "윈도우", "창문"],
    "wiper": ["wiper", "washer", "와이퍼", "워셔"],
    "steering": ["steer", "steering", "swrc", "핸들", "조향"],
    "battery": ["battery", "bms", "soc", "배터리"],
    "charge": ["charge", "charging", "obc", "충전"],
    "ota": ["ota", "update", "업데이트"],
    "auth": ["auth", "authentication", "smk", "smartkey", "인증", "스마트키"],
}
_SPECIAL_SIGNAL_BUCKET: Dict[str, str] = {
    "SCUFFPOSACTSTA": "output",
    "SCUFFPOSTARSTA": "output",
    "SCUFFEPBREQ": "output",
    "EPBFRCSTA": "output",
    "EPBLMPSTADIS": "output",
    "EPBOUTDATADIS": "output",
    "SBWSHFTRFFLVRINDICATORSTA": "output",
    "BRAKESWSTAICU": "output",
    "OTACONDGEARP": "excluded",
}


def _split_identifier_tokens(value: str) -> List[str]:
    if not value:
        return []
    raw_parts = [p for p in re.split(r"[_\-\s]+", value) if p]
    out: List[str] = []
    pattern = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+")
    for part in raw_parts:
        found = pattern.findall(part)
        out.extend(found if found else [part])
    return [x.upper() for x in out if x]


def _context_tokens(item: RelatedSignalItem, ev: Optional[DbcSignalEvidence]) -> List[str]:
    fields = [item.msg_name, item.sig_name]
    if ev is not None:
        fields.extend([ev.definition, ev.description, ev.signal_comment, ev.message_comment, ev.choices, ev.senders])
    tokens: List[str] = []
    for field in fields:
        tokens.extend(_split_identifier_tokens(_squash_spaces(field)))
    return tokens


def _extract_tc_keywords(tc_text: str) -> List[str]:
    tokens = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_]+|[가-힣]{2,}", tc_text or ""):
        t = token.strip().lower()
        if len(t) < 2 or t in _TC_STOPWORDS or t.isdigit():
            continue
        tokens.append(t)
    return list(dict.fromkeys(tokens))[:50]



def _detect_concepts(text: str) -> set[str]:
    normalized = re.sub(r"[\s_\-]+", "", (text or "").lower())
    found: set[str] = set()
    for concept, aliases in _CONCEPT_ALIASES.items():
        for alias in aliases:
            alias_n = re.sub(r"[\s_\-]+", "", alias.lower())
            if alias_n and alias_n in normalized:
                found.add(concept)
                break
    return found


def _has_meaningful_tc_info(tc_text: str) -> bool:
    s = _squash_spaces(tc_text)
    if len(s) < 20:
        return False
    return not any(marker in s for marker in ("찾지 못했습니다", "TC 정보 추출 실패", "[TC 정보] -"))


def _resolve_cycle_ms(item: RelatedSignalItem, ev: Optional[DbcSignalEvidence]) -> Optional[int]:
    if ev is not None:
        raw = _squash_spaces(ev.cycle_time)
        m = re.search(r"\d+(?:\.\d+)?", raw)
        if m:
            try:
                return int(round(float(m.group(0))))
            except Exception:
                pass
    m = re.search(r"_(\d+)ms\b", item.msg_name or "", flags=re.IGNORECASE)
    return int(m.group(1)) if m else None


def _is_event_message(item: RelatedSignalItem, ev: Optional[DbcSignalEvidence]) -> bool:
    source = " ".join([
        ev.send_type if ev else "", ev.message_comment if ev else "", item.msg_name or "",
    ]).lower()
    return bool(re.search(r"on\s*event|on\s*change|event|change|interrupt|\bec\b", source))


def _distinct_observation_count(item: RelatedSignalItem) -> int:
    values = set()
    for value in item.observed_values:
        normalized = re.sub(r"\s+", " ", value.strip().lower())
        if normalized:
            values.add(normalized)
    return len(values)


def _classification_override(config, item: RelatedSignalItem) -> Optional[str]:
    key = re.sub(r"[^A-Za-z0-9]", "", (item.sig_name or "").upper())
    user_map = getattr(config, "step_6_classification_overrides", {}) if config is not None else {}
    if isinstance(user_map, dict):
        for raw_key, raw_bucket in user_map.items():
            normalized = re.sub(r"[^A-Za-z0-9]", "", str(raw_key).upper())
            bucket = str(raw_bucket).strip().lower()
            if normalized == key and bucket in ("input", "output", "excluded"):
                return bucket
    return _SPECIAL_SIGNAL_BUCKET.get(key)


def _score_heuristic_decision(item: RelatedSignalItem, ev: Optional[DbcSignalEvidence], tc_text: str, config=None) -> ClassificationDecision:
    scores = {"input": 0.0, "output": 0.0, "excluded": 0.0}
    reasons: Dict[str, List[str]] = {"input": [], "output": [], "excluded": []}

    override = _classification_override(config, item)
    if override:
        return ClassificationDecision(
            bucket=override,
            scores={"input": 0.0, "output": 0.0, "excluded": 0.0, override: 99.0},
            confidence=1.0,
            reasons=["명시적 분류 override"],
            source="override",
            hard_rule=True,
        )

    tokens = _context_tokens(item, ev)
    token_set = set(tokens)
    for token in token_set:
        if token in _INPUT_TOKENS:
            scores["input"] += _INPUT_TOKENS[token]
            reasons["input"].append(f"{token} 입력 단서")
        if token in _OUTPUT_TOKENS:
            scores["output"] += _OUTPUT_TOKENS[token]
            reasons["output"].append(f"{token} 출력/상태 단서")
        if token in _EXCLUDED_TOKENS:
            scores["excluded"] += _EXCLUDED_TOKENS[token]
            reasons["excluded"].append(f"{token} 비기능/진단 단서")

    sig_compact = re.sub(r"[^A-Za-z0-9]", "", item.sig_name or "").upper()
    if re.search(r"POSACTSTA|POSTARSTA|ACTSTA|TARSTA|FRCSTA|LMPSTA|INDICATORSTA|OUTDATA", sig_compact):
        scores["output"] += 3.0
        reasons["output"].append("Actual/Target/표시 결과 조합")
    if re.search(r"BTN|BUTTON|SWSTA|SWITCH|LVR|LEVER|PEDAL", sig_compact):
        scores["input"] += 2.5
        reasons["input"].append("사람 조작 인터페이스 조합")

    # Driver brake active / 원시 brake switch는 사람이 직접 조작한 입력에 가깝다.
    # 단, ICU/Display/Out 계열로 재전송된 상태는 내부 출력으로 유지한다.
    if re.search(r"DRVBRK(?:ACTV|ACTIVE)?STA|BRKSWSTA", sig_compact):
        if re.search(r"ICU|DISPLAY|DIS|OUT", sig_compact):
            scores["output"] += 2.0
            reasons["output"].append("표시/재전송된 브레이크 상태")
        else:
            scores["input"] += 4.0
            reasons["input"].append("운전자 브레이크/브레이크 스위치 직접 입력")
    if re.search(r"COND", sig_compact):
        scores["excluded"] += 1.5
        reasons["excluded"].append("조건 판단 신호")

    # 메시지 주기는 절대 규칙이 아니라 약한 prior로만 사용한다.
    cycle_ms = _resolve_cycle_ms(item, ev)
    event_based = _is_event_message(item, ev)
    has_input_cue = scores["input"] > 0
    has_output_cue = scores["output"] > 0
    if cycle_ms == 0 or event_based:
        if has_input_cue:
            scores["input"] += 0.75
            reasons["input"].append("이벤트/00ms 약한 입력 가중치")
        elif has_output_cue:
            scores["output"] += 0.25
            reasons["output"].append("이벤트성 출력 가능성")
    elif cycle_ms in (50, 100, 200):
        if has_output_cue:
            scores["output"] += {50: 0.4, 100: 0.5, 200: 0.6}[cycle_ms]
            reasons["output"].append(f"{cycle_ms}ms 약한 상태/피드백 가중치")
    elif cycle_ms is not None and cycle_ms >= 300 and has_output_cue:
        scores["output"] += 0.35
        reasons["output"].append("장주기 상태 신호 약한 가중치")
    # 10/20ms는 안전/제어 입출력이 모두 존재하므로 중립으로 둔다.

    context = " ".join([
        item.msg_name, item.sig_name, " ".join(item.original_lines[:8]),
        ev.definition if ev else "", ev.description if ev else "", ev.choices if ev else "",
    ]).lower()
    tc_keywords = _extract_tc_keywords(tc_text)
    context_keyword_tokens = {
        token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9_]+|[가-힣]{2,}", context)
    }
    overlap = [kw for kw in tc_keywords if kw in context_keyword_tokens]
    tc_concepts = _detect_concepts(tc_text)
    signal_concepts = _detect_concepts(context)
    concept_overlap = sorted(tc_concepts & signal_concepts)
    meaningful_tc = _has_meaningful_tc_info(tc_text)
    relevance_found = bool(overlap or concept_overlap)
    if relevance_found:
        bonus = min(2.0, 0.30 * len(overlap) + 0.75 * len(concept_overlap))
        direction = "input" if scores["input"] > scores["output"] else "output"
        scores[direction] += bonus
        scores["excluded"] = max(0.0, scores["excluded"] - min(1.0, bonus))
        evidence_parts = []
        if concept_overlap:
            evidence_parts.append("기능 개념=" + ",".join(concept_overlap[:3]))
        if overlap:
            evidence_parts.append("키워드=" + ",".join(overlap[:3]))
        reasons[direction].append("TC 연관 " + " / ".join(evidence_parts))
    elif meaningful_tc:
        # Step 5의 관련 후보라도 TC 개념과 전혀 겹치지 않으면 제외 쪽을 우선한다.
        role_max = max(scores["input"], scores["output"])
        scores["excluded"] += max(2.5, role_max + 1.0)
        reasons["excluded"].append("TC 기능/키워드 연관 근거 부족")

    if _distinct_observation_count(item) >= 2:
        if relevance_found or not meaningful_tc:
            direction = "input" if scores["input"] > scores["output"] else "output"
            scores[direction] += 0.35
            scores["excluded"] = max(0.0, scores["excluded"] - 0.25)
            reasons[direction].append("실제 값 변화 관측")
        else:
            reasons["excluded"].append("값 변화는 있으나 TC 연관 근거 없음")

    # input/output가 거의 동점이면 단순 dict 순서로 input을 선택하지 않는다.
    if abs(scores["input"] - scores["output"]) < 0.35 and max(scores["input"], scores["output"]) > scores["excluded"]:
        strong_input = any(token in token_set for token in {"BTN", "BUTTON", "SW", "SWITCH", "LVR", "LEVER", "PEDAL", "KEY", "KNOB", "TOUCH"})
        strong_output = any(token in token_set for token in {"REQ", "REQUEST", "CMD", "COMMAND", "TAR", "TARGET", "ACT", "ACTUAL", "FDBK", "FEEDBACK", "INDICATOR", "LMP", "DISPLAY"})
        if strong_input and not strong_output:
            scores["input"] += 0.1
        elif strong_output:
            scores["output"] += 0.1
        else:
            scores["excluded"] += 0.1

    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_bucket, best_score = ordered[0]
    second_score = ordered[1][1]
    margin = best_score - second_score

    # 강한 제외 토큰은 주기/상태 단서보다 우선한다.
    hard_excluded = any(t in token_set for t in {"CRC", "ALV", "ALIVE", "CHECKSUM", "DTC", "TIMEOUT", "E2E"})
    if hard_excluded and scores["excluded"] >= 4.0:
        best_bucket = "excluded"
        best_score = scores["excluded"]
        margin = scores["excluded"] - max(scores["input"], scores["output"])

    if best_score < 1.0:
        best_bucket = "excluded"
        reasons["excluded"].append("입력/출력 역할 단서가 충분하지 않음")
        confidence = 0.35
    else:
        confidence = max(0.35, min(0.95, 0.5 + 0.10 * margin + 0.04 * best_score))

    selected_reasons = list(dict.fromkeys(reasons[best_bucket]))[:4]
    if not selected_reasons:
        selected_reasons = ["상대 점수 기준 분류"]
    return ClassificationDecision(
        bucket=best_bucket,
        scores=scores,
        confidence=confidence,
        reasons=selected_reasons,
        source="heuristic",
        hard_rule=hard_excluded,
    )


def _build_classification_prompt(base_dir: Path, answer_path: Path, output_type: str, items: List[RelatedSignalItem], chosen: Dict[Tuple[str, str], Optional[DbcSignalEvidence]], heuristic: Dict[Tuple[str, str], ClassificationDecision], config) -> str:
    tc_text = _extract_tc_info_text(base_dir, answer_path, output_type, config)
    rows: List[str] = []
    for idx, item in enumerate(items, 1):
        key = (item.msg_name, item.sig_name)
        ev = chosen.get(key)
        dec = heuristic[key]
        cycle = _resolve_cycle_ms(item, ev)
        rows.extend([
            f"[{idx}] message={item.msg_name}",
            f"signal={item.sig_name}",
            "Step6 상세 변화=" + " | ".join(item.original_lines[:8]),
            f"DBC Sender={((ev.senders if ev else '') or '-')}",
            f"Signal Receiver={((ev.signal_receivers if ev else '') or '-')}",
            f"Meaning={_signal_meaning_for_output(ev)}",
            f"Values={((ev.choices if ev else '') or '-')}",
            f"Cycle(ms)={cycle if cycle is not None else '-'} / SendType={((ev.send_type if ev else '') or '-')} / Comment={((ev.message_comment if ev else '') or '-')}",
            f"Heuristic={dec.bucket}, scores={dec.scores}, reasons={' / '.join(dec.reasons)}",
            "",
        ])

    return _truncate_text(f"""
[목표]
각 Message:Signal을 TC 관점에서 input / output / excluded 중 하나로 분류하세요.
input은 사람이 직접 조작한 버튼·스위치·레버·페달 등 원시 인터페이스 입력입니다.
output은 그 조작 이후 ECU 내부에서 만들어지는 요청·명령·목표·실제상태·피드백·표시 결과입니다.
excluded는 TC 핵심 인과 흐름과 직접 관련이 낮거나 CRC/Alive/Counter/Diag/Timeout/Validity 계열입니다.

[중요 판단 원칙]
- 메시지 주기는 보조 단서일 뿐 절대 규칙이 아닙니다.
- 00ms/Event는 사람 조작 단서가 함께 있을 때만 input 쪽 약한 근거로 사용하세요.
- 50/100/200ms는 상태/피드백 단서가 함께 있을 때만 output 쪽 약한 근거로 사용하세요.
- 10/20ms는 방향 판단 근거로 거의 사용하지 마세요.
- Req/Cmd/Target/Actual/Status/Feedback는 사용자가 직접 누른 입력이 아니라 내부 output으로 봅니다.
- CRC/Alive/Counter/Diag/Timeout/E2E는 강한 excluded 후보입니다.

[출력 규칙]
- JSON 배열만 출력하세요. Markdown 코드블록 금지.
- 각 원소는 message, signal, bucket, confidence, reason 키를 포함하세요.
- bucket은 input/output/excluded 중 하나입니다.
- confidence는 0.0~1.0 숫자입니다.
- reason은 한 문장으로 작성하세요.
- 모든 Message:Signal을 정확히 한 번씩 포함하세요.

{tc_text}

[분류 대상]
{chr(10).join(rows)}
""".strip(), limit=24000)


def _parse_ai_classification_json(answer: str) -> Dict[Tuple[str, str], ClassificationDecision]:
    text = (answer or "").strip()
    if not text:
        return {}
    m = re.search(r"\[\s*\{.*\}\s*\]", text, flags=re.DOTALL)
    if m:
        text = m.group(0)
    data = json.loads(text)
    out: Dict[Tuple[str, str], ClassificationDecision] = {}
    if not isinstance(data, list):
        return out
    for row in data:
        if not isinstance(row, dict):
            continue
        msg = _squash_spaces(row.get("message", ""))
        sig = _squash_spaces(row.get("signal", ""))
        bucket = _squash_spaces(row.get("bucket", "")).lower()
        if not msg or not sig or bucket not in ("input", "output", "excluded"):
            continue
        try:
            confidence = float(row.get("confidence", 0.5))
        except Exception:
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        reason = _squash_spaces(row.get("reason", "")) or "AI 분류"
        out[(msg, sig)] = ClassificationDecision(
            bucket=bucket,
            confidence=confidence,
            reasons=[reason],
            source="ai",
        )
    return out


def _merge_classification_decision(heuristic: ClassificationDecision, ai: Optional[ClassificationDecision]) -> ClassificationDecision:
    if ai is None:
        return heuristic
    if heuristic.hard_rule:
        return heuristic
    if heuristic.bucket == ai.bucket:
        return ClassificationDecision(
            bucket=heuristic.bucket,
            scores=heuristic.scores,
            confidence=max(heuristic.confidence, ai.confidence),
            reasons=list(dict.fromkeys(ai.reasons + heuristic.reasons))[:4],
            source="hybrid-agree",
        )

    sorted_scores = sorted(heuristic.scores.values(), reverse=True)
    margin = sorted_scores[0] - sorted_scores[1] if len(sorted_scores) >= 2 else 0.0
    # AI가 충분히 확신하고 휴리스틱이 애매할 때만 AI가 뒤집는다.
    if ai.confidence >= 0.80 and (heuristic.confidence < 0.72 or margin < 1.25):
        return ClassificationDecision(
            bucket=ai.bucket,
            scores=heuristic.scores,
            confidence=ai.confidence,
            reasons=ai.reasons + [f"휴리스틱 {heuristic.bucket}와 충돌했으나 AI 고신뢰 판단 채택"],
            source="hybrid-ai",
        )
    return ClassificationDecision(
        bucket=heuristic.bucket,
        scores=heuristic.scores,
        confidence=heuristic.confidence,
        reasons=heuristic.reasons + [f"AI는 {ai.bucket}({ai.confidence:.2f})였으나 휴리스틱 근거 유지"],
        source="hybrid-heuristic",
    )


def _classification_decisions(base_dir: Path, answer_path: Path, output_type: str, items: List[RelatedSignalItem], chosen: Dict[Tuple[str, str], Optional[DbcSignalEvidence]], config) -> Dict[Tuple[str, str], ClassificationDecision]:
    tc_text = _extract_tc_info_text(base_dir, answer_path, output_type, config)
    heuristic = {
        (item.msg_name, item.sig_name): _score_heuristic_decision(item, chosen.get((item.msg_name, item.sig_name)), tc_text, config)
        for item in items
    }

    if not _step6_ai_enabled(config) or not str(getattr(config, "api_key", "") or "").strip():
        return heuristic

    prompt = _build_classification_prompt(base_dir, answer_path, output_type, items, chosen, heuristic, config)
    max_retry = int(getattr(config, "step_6_ai_max_retry", 2) or 2)
    wait_sec = float(getattr(config, "retry_wait_seconds", 2.0) or 2.0)
    ai_map: Dict[Tuple[str, str], ClassificationDecision] = {}
    for attempt in range(1, max_retry + 1):
        try:
            print(f"[INFO] Step 6 하이브리드 입출력 분류: {answer_path.name} ({attempt}/{max_retry})")
            ai_map = _parse_ai_classification_json((_ask_ai_for_step6(prompt, config) or "").strip())
            if ai_map:
                break
        except Exception as e:
            print(f"[WARN] Step 6 AI 분류 실패: {answer_path.name} ({attempt}/{max_retry}) {e}")
            if attempt < max_retry:
                time.sleep(wait_sec)

    ai_map_ci = {(msg.upper(), sig.upper()): dec for (msg, sig), dec in ai_map.items()}
    return {
        key: _merge_classification_decision(dec, ai_map.get(key) or ai_map_ci.get((key[0].upper(), key[1].upper())))
        for key, dec in heuristic.items()
    }


def generate_classification_map(base_dir: Path, answer_path: Path, output_type: str, items: List[RelatedSignalItem], chosen: Dict[Tuple[str, str], Optional[DbcSignalEvidence]], config) -> Tuple[Dict[str, List[str]], Dict[str, ClassificationDecision]]:
    decisions = _classification_decisions(base_dir, answer_path, output_type, items, chosen, config)
    classified = {"input": [], "output": [], "excluded": []}
    line_decisions: Dict[str, ClassificationDecision] = {}
    assigned = set()
    for item in items:
        key = (item.msg_name, item.sig_name)
        decision = decisions.get(key) or ClassificationDecision("excluded", confidence=0.2, reasons=["분류 결과 없음"])
        for raw_line in item.original_lines:
            normalized = _squash_spaces(raw_line)
            if not normalized or normalized in assigned:
                continue
            classified[decision.bucket].append(normalized)
            line_decisions[normalized] = decision
            assigned.add(normalized)
    return classified, line_decisions


# =========================================================
# 신호 요약 / 실제 분류 근거 렌더링
# =========================================================
_TOKEN_KO_MAP = {
    "EPB": "전자식 주차브레이크", "LMP": "램프", "STA": "상태", "DIS": "표시", "OUT": "출력",
    "OUTDATA": "출력 데이터", "DATA": "데이터", "REQ": "요청", "CMD": "명령", "POS": "위치",
    "ACT": "실제", "TAR": "목표", "FRC": "체결력", "SW": "스위치", "BTN": "버튼",
    "LVR": "레버", "INDICATOR": "표시등", "GEAR": "기어", "P": "P단", "R": "R단",
    "N": "N단", "D": "D단", "SMK": "스마트키", "SCU": "변속 제어기", "SBW": "전자식 변속",
    "SHFTR": "시프터", "OTA": "OTA", "COND": "조건 판단", "STATUS": "상태", "STATE": "상태",
    "FDBK": "피드백", "FEEDBACK": "피드백", "PARK": "주차", "APPLY": "적용", "CLAMP": "체결",
    "CLU": "클러스터", "FF": "",
}


def _signal_summary_from_name(item: RelatedSignalItem, ev: Optional[DbcSignalEvidence]) -> str:
    words = [_TOKEN_KO_MAP.get(token, token.title()) for token in _split_identifier_tokens(item.sig_name)]
    words = [w for w in dict.fromkeys(words) if w]
    summary = " ".join(words).strip()
    if not summary and ev is not None:
        summary = _shorten_reason_text(_nonempty(ev.definition, ev.description, ev.signal_comment), 45)
    if not summary:
        summary = "관련 상태"
    if not summary.endswith("신호"):
        summary += " 신호"
    return _shorten_reason_text(summary, 55)


def _decision_reason_text(decision: ClassificationDecision) -> str:
    score_text = ", ".join(f"{k}={v:.1f}" for k, v in decision.scores.items()) if decision.scores else ""
    reason = " / ".join(decision.reasons[:3])
    meta = f"분류={decision.bucket}, 신뢰도={decision.confidence:.2f}"
    if score_text:
        meta += f", 점수({score_text})"
    return _shorten_reason_text(f"{reason} [{meta}]", 180)
# =========================================================
# 출력 생성
# =========================================================
def _value_or_dash(value: object) -> str:
    text = _squash_spaces(value)
    return text if text else "-"


def _format_keywords(keywords: List[Step6Keyword]) -> str:
    if not keywords:
        return "-"
    parts = []
    for kw in keywords[:2]:
        if kw.meaning:
            parts.append(f"{kw.term} = {kw.meaning}")
        else:
            parts.append(kw.term)
    return " / ".join(parts) if parts else "-"


def _render_compact_signal_block(item: RelatedSignalItem, ev: Optional[DbcSignalEvidence], judgement: Step6SignalJudgement) -> List[str]:
    lines: List[str] = []
    lines.append("[Step 5 원문 라인]")
    if item.original_lines:
        for ln in item.original_lines:
            lines.append(f"- {ln}")
    else:
        lines.append("- 원문 라인 없음")
    lines.append("")

    if ev is None:
        lines.append("Sender MCU   : DBC 매칭 실패")
        lines.append("Signal Receiver MCU : DBC 매칭 실패")
        lines.append("Message Receiver : DBC 매칭 실패")
        lines.append("신호 의미 : DBC에서 동일한 Message/Signal 조합을 찾지 못했습니다.")
        lines.append("값 의미: -")
        lines.append("Description : -")
        lines.append("Definition : -")
        lines.append("Message Comment : -")
    else:
        lines.append(f"Sender MCU   : {_value_or_dash(ev.senders)}")
        lines.append(f"Signal Receiver MCU : {_value_or_dash(ev.signal_receivers)}")
        lines.append(f"Message Receiver : {_value_or_dash(ev.message_receivers)}")
        lines.append(f"신호 의미 : {_value_or_dash(_signal_meaning_for_output(ev))}")
        lines.append(f"값 의미: {_value_or_dash(ev.choices)}")
        lines.append(f"Description : {_value_or_dash(ev.description)}")
        lines.append(f"Definition : {_value_or_dash(ev.definition)}")
        lines.append(f"Message Comment : {_value_or_dash(ev.message_comment)}")

    lines.append(f"AI 판단 근거 : {_value_or_dash(judgement.reason)}")
    lines.append(f"주요 키워드 : {_format_keywords(judgement.keywords)}")
    return lines


def make_output_name(answer_path: Path) -> str:
    stem = answer_path.stem
    if stem.startswith("AI답변_"):
        stem = stem.replace("AI답변_", "AI결과판단_", 1)
    else:
        stem = "AI결과판단_" + stem
    return stem + ".txt"


def render_case_evidence(base_dir: Path, answer_path: Path, output_type: str, items: List[RelatedSignalItem], index: Dict[Tuple[str, str], List[DbcSignalEvidence]], config=None) -> str:
    if not items:
        return "[결과]\n- Step 5 답변에서 연관 있는 메세지를 찾지 못했습니다.\n"

    chosen: Dict[Tuple[str, str], Optional[DbcSignalEvidence]] = {}
    for item in items:
        key = (item.msg_name, item.sig_name)
        chosen[key] = _select_primary_evidence(index.get(key, []))

    judgement_map: Dict[Tuple[str, str], Step6SignalJudgement] = {}
    if config is not None:
        judgement_map = generate_ai_judgement_map(base_dir, answer_path, output_type, items, chosen, config)

    lines: List[str] = []
    for idx, item in enumerate(items, 1):
        key = (item.msg_name, item.sig_name)
        if idx > 1:
            lines.append("")
            lines.append("=" * 80)
            lines.append("")
        judgement = judgement_map.get(key) or Step6SignalJudgement(reason="-")
        lines.extend(_render_compact_signal_block(item, chosen.get(key), judgement))

    return "\n".join(lines).rstrip() + "\n"


def _judgement_subfolder_name(output_type: str) -> str:
    return "판단 해설_시간별" if output_type == "시간별" else "판단 해설_메세지별"


def _answer_root_from_answer_path(answer_path: Path) -> Path:
    # .../AI답변_결과/메세지별/AI답변_x.txt -> .../AI답변_결과
    return answer_path.parent.parent


def make_classification_output_name(answer_path: Path) -> str:
    stem = make_output_name(answer_path).replace(".txt", "")
    if stem.startswith("AI결과판단_"):
        stem = stem.replace("AI결과판단_", "AI결과판단_분류_", 1)
    else:
        stem = "AI결과판단_분류_" + stem
    return stem + ".txt"


def render_classification_file(base_dir: Path, answer_path: Path, output_type: str, items: List[RelatedSignalItem], chosen: Dict[Tuple[str, str], Optional[DbcSignalEvidence]], config=None) -> str:
    tc_text = _extract_tc_info_text(base_dir, answer_path, output_type, config) if config is not None else f"[파일명]\n{answer_path.name}\n\n[TC 정보]\n-"
    if config is not None:
        classified, line_decisions = generate_classification_map(base_dir, answer_path, output_type, items, chosen, config)
    else:
        classified = {"input": [], "output": [], "excluded": []}
        line_decisions = {}

    line_to_item: Dict[str, Tuple[RelatedSignalItem, Optional[DbcSignalEvidence]]] = {}
    for item in items:
        ev = chosen.get((item.msg_name, item.sig_name))
        for raw_line in item.original_lines:
            line_to_item[_squash_spaces(raw_line)] = (item, ev)

    def render_lines(title: str, rows: List[str]) -> List[str]:
        out = [f"{title}:"]
        if not rows:
            out.append("-")
            return out
        for row in rows:
            key = _squash_spaces(row)
            item, ev = line_to_item.get(key, (RelatedSignalItem("", ""), None))
            decision = line_decisions.get(key) or ClassificationDecision("excluded", confidence=0.0, reasons=["분류 근거 없음"])
            out.append(row)
            out.append(f"    // 신호 요약 : {_signal_summary_from_name(item, ev)}")
            out.append(f"    // 사유 : {_decision_reason_text(decision)}")
        return out

    lines: List[str] = [tc_text, "", "[AI 판단 결과]"]
    lines.extend(render_lines("입력 시그널", classified.get("input", [])))
    lines.append("")
    lines.extend(render_lines("출력 시그널", classified.get("output", [])))
    lines.append("")
    lines.extend(render_lines("제외 시그널", classified.get("excluded", [])))
    if config is None or not str(getattr(config, "api_key", "") or "").strip():
        lines.extend(["", "[분류 참고]", "- API KEY가 없어도 개선된 휴리스틱 분류를 적용했습니다. 메시지 주기는 약한 보조 가중치로만 사용됩니다."])
    return "\n".join(lines).rstrip() + "\n"

def process_answer_file(answer_path: Path, output_type: str, index: Dict[Tuple[str, str], List[DbcSignalEvidence]], current_idx: int, total_count: int, config=None) -> Tuple[bool, str]:
    print(f"[CASE {current_idx}/{total_count} | {(current_idx / total_count * 100.0) if total_count else 100.0:.1f}%] Step 6 처리: {answer_path.name}")
    answer_root = _answer_root_from_answer_path(answer_path)
    out_dir = answer_root / _judgement_subfolder_name(output_type)
    try:
        base_dir_for_prompt = Path(config.base_dir) if config is not None else answer_root.parent
        items = parse_related_signals(answer_path)
        chosen: Dict[Tuple[str, str], Optional[DbcSignalEvidence]] = {}
        for item in items:
            key = (item.msg_name, item.sig_name)
            chosen[key] = _select_primary_evidence(index.get(key, []))

        out_text = render_case_evidence(base_dir_for_prompt, answer_path, output_type, items, index, config=config)
        out_path = out_dir / make_output_name(answer_path)
        _write_text(out_path, out_text)

        classification_text = render_classification_file(base_dir_for_prompt, answer_path, output_type, items, chosen, config=config)
        classification_path = out_dir / make_classification_output_name(answer_path)
        _write_text(classification_path, classification_text)

        _remove_step6_error_if_exists(answer_path, output_type)
        print(f"[OK] Step 6 판단 해설 저장 완료: {out_path}")
        print(f"[OK] Step 6 분류 저장 완료: {classification_path}")
        return True, "성공"
    except Exception as e:
        out_dir.mkdir(parents=True, exist_ok=True)
        err_path = out_dir / (make_output_name(answer_path).replace(".txt", ".error.txt"))
        err_text = (
            f"[실패 파일]\n{answer_path.name}\n\n"
            f"[원본 경로]\n{answer_path}\n\n"
            f"[실패 단계]\nSTEP 6 - DBC EVIDENCE EXPORT\n\n"
            f"[실패 사유]\n{e}\n\n"
            f"[상세 Traceback]\n{traceback.format_exc()}"
        )
        _write_text(err_path, err_text)
        print(f"[ERROR] Step 6 실패: {answer_path.name} ({e})")
        print(f"[ERROR] 실패 기록 저장: {err_path}")
        return False, str(e)


# =========================================================
# Entry
# =========================================================
def _legacy_run_step6(config) -> None:
    base_dir = Path(config.base_dir)
    output_root_name = getattr(config, "output_root_dir_name", "AI답변_결과")
    output_dir = base_dir / output_root_name

    print(f"[INFO] STEP 7 output root = {output_dir}")
    print("[INFO] STEP 7 subfolders = 판단 해설_메세지별 / 판단 해설_시간별")
    print(f"[INFO] STEP 7 AI 판단 근거 = {bool(getattr(config, 'step_7_enable_ai_judgement', getattr(config, 'step_6_enable_ai_judgement', True)))}")
    print(f"[INFO] STEP 7 실패파일만 재실행 = {bool(getattr(config, 'retry_failed_only', False))}")

    answer_files = collect_answer_files(base_dir, config)
    if not answer_files:
        if getattr(config, "retry_failed_only", False):
            print("[INFO] Step 6 실패파일 재실행 대상 중 현재 처리 가능한 AI답변이 없습니다.")
            print("[INFO] Step 5 .error가 남아 있다면 Step 5도 함께 체크하여 먼저 정상 답변을 생성하세요.")
        else:
            print("[WARN] Step 6 대상 AI답변 파일을 찾지 못했습니다.")
            print("[WARN] 먼저 Step 5를 정상 완료했는지 확인하세요.")
        output_dir.mkdir(parents=True, exist_ok=True)
        return

    index = build_dbc_index(base_dir, config=config)

    ok_count = 0
    fail_count = 0
    total = len(answer_files)
    for i, (answer_path, output_type) in enumerate(answer_files, 1):
        ok, _reason = process_answer_file(answer_path, output_type, index, i, total, config=config)
        if ok:
            ok_count += 1
        else:
            fail_count += 1

    print("\n" + "=" * 80)
    print("[STEP 7 LEGACY SUMMARY]")
    print(f"대상 AI답변 파일: {total}")
    print(f"성공: {ok_count}")
    print(f"실패: {fail_count}")
    print(f"출력 루트: {output_dir}")
    print("출력 폴더: 판단 해설_메세지별 / 판단 해설_시간별")
    print("=" * 80)

    if fail_count > 0:
        raise RuntimeError(f"Step 6 실패 파일이 있습니다: {fail_count}개")



# =========================================================
# V2 REV 02: Step 6 상세분석/요약 입력 + 애매한 신호만 AI
# =========================================================
_DETAIL_LINE_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)?sec\s+)?(?:CH\d+\s+)?"
    r"(?P<msg>[A-Za-z_][\w\-]*)\s*:\s*(?P<sig>[A-Za-z_][\w\-]*)\b(?P<tail>.*)$",
    re.IGNORECASE,
)


def _detail_case_stem(name: str) -> str:
    raw = str(name or "").strip()
    lower = raw.lower()
    for suffix_name in (".error.txt", ".warning.txt", ".txt"):
        if lower.endswith(suffix_name):
            raw = raw[:-len(suffix_name)]
            break
    else:
        raw = Path(raw).stem

    prefixes = (
        "AI결과판단_상세분석 분류_",
        "AI결과판단_요약 분류_",
        "AI결과판단_분류_",
        "AI결과판단_",
        "AI상세추출_",
    )
    for prefix_name in prefixes:
        if raw.startswith(prefix_name):
            raw = raw[len(prefix_name):]
            break

    changed = True
    while changed:
        changed = False
        for suffix_name in ("_상세분석", "_요약", "_시간별"):
            if raw.endswith(suffix_name):
                raw = raw[:-len(suffix_name)]
                changed = True
    return raw.strip()


def _step6_runtime_case_stems(values) -> set[str]:
    out: set[str] = set()
    for value in list(values or []):
        text = str(value or "").strip().casefold()
        if "::" not in text:
            continue
        _, stem = text.split("::", 1)
        normalized = _detail_case_stem(stem).casefold()
        if normalized:
            out.add(normalized)
    return out


def _step7_error_case_stems(base_dir: Path, config) -> set[str]:
    out: set[str] = set()
    root_name = str(getattr(config, "output_root_dir_name", "AI답변_결과"))
    request_root = str(getattr(config, "input_root_dir_name", "AI_문의용_출력"))
    for root in (base_dir / request_root / root_name, base_dir / root_name):
        for folder_name in ("판단 해설_메세지별", "판단 해설_시간별"):
            folder = root / folder_name
            if not folder.is_dir():
                continue
            for error_path in folder.glob("AI결과판단_*.error.txt"):
                stem = _detail_case_stem(error_path.name).casefold()
                if stem:
                    out.add(stem)
    return out


def collect_detail_files(base_dir: Path, config) -> List[Tuple[Path, str]]:
    root_name = str(getattr(config, "output_root_dir_name", "AI답변_결과"))
    request_root = str(getattr(config, "input_root_dir_name", "AI_문의용_출력"))
    roots = [base_dir / request_root / root_name, base_dir / root_name]
    result: List[Tuple[Path, str]] = []
    seen = set()
    for root in roots:
        for folder_name, output_type in [("상세 변화_메세지별", "메세지별"), ("상세 변화_시간별", "시간별")]:
            folder = root / folder_name
            if not folder.is_dir():
                continue
            candidates = list(folder.glob("AI상세추출_*_상세분석.txt"))
            candidates += list(folder.glob("AI상세추출_*_요약.txt"))
            for path in sorted(candidates, key=lambda p: p.name):
                if path.name.endswith(".error.txt") or path.name.endswith(".warning.txt"):
                    continue
                key = str(path.resolve())
                if key not in seen:
                    seen.add(key)
                    result.append((path, output_type))

    if not bool(getattr(config, "retry_failed_only", False)):
        return result

    step6_stems = _step6_runtime_case_stems(getattr(config, "step_6_retry_case_keys", []))
    step7_error_stems = _step7_error_case_stems(base_dir, config)
    target_stems = step6_stems | step7_error_stems
    print(
        "[RETRY][STEP7] 대상 합집합: "
        f"Step6 갱신={len(step6_stems)} / "
        f"Step7 .error={len(step7_error_stems)} / "
        f"합계(중복제거)={len(target_stems)}"
    )
    if not target_stems:
        print("[RETRY][STEP7] 실패파일 재실행 대상이 없습니다.")
        return []

    available_stems = {_detail_case_stem(path.name).casefold() for path, _ in result}
    selected = [
        (path, output_type)
        for path, output_type in result
        if _detail_case_stem(path.name).casefold() in target_stems
    ]
    missing = sorted(target_stems - available_stems)
    if missing:
        print(f"[RETRY][STEP7][WAIT] 대응 Step 6 상세 변화 파일이 없는 대상: {len(missing)}개")
        for item in missing[:20]:
            print(f"  - {item}")
    print(f"[RETRY][STEP7] 실제 재처리 상세 변화 파일: {len(selected)}개")
    return selected


def parse_related_signals(answer_path: Path) -> List[RelatedSignalItem]:
    by_key: Dict[Tuple[str, str], RelatedSignalItem] = {}
    order: List[Tuple[str, str]] = []
    for raw in _read_text_any(answer_path).splitlines():
        line = raw.strip()
        if not line or line.startswith("- 상세 변화 없음"):
            continue
        match = _DETAIL_LINE_RE.match(line)
        if not match:
            continue
        msg, sig = match.group("msg"), match.group("sig")
        if msg.lower() in {"message", "signal", "definition", "description"}:
            continue
        key = (msg, sig)
        if key not in by_key:
            by_key[key] = RelatedSignalItem(msg_name=msg, sig_name=sig)
            order.append(key)
        item = by_key[key]
        if line not in item.original_lines:
            item.original_lines.append(line)
        tail = (match.group("tail") or "").strip()
        if tail and tail not in item.observed_values:
            item.observed_values.append(tail)
    return [by_key[key] for key in order]


def _extract_tc_info_text(base_dir: Path, answer_path: Path, output_type: str, config) -> str:
    text = _read_text_any(answer_path)
    next_titles = ["TC 정보", "소스 정보", "선정 시그널 상세 변화", "선정 시그널 요약"]
    file_name = _extract_section(text, "파일명", next_titles)
    tc_info = _extract_section(text, "TC 정보", ["소스 정보", "선정 시그널 상세 변화", "선정 시그널 요약"])
    return f"[파일명]\n{file_name or answer_path.name}\n\n[TC 정보]\n{tc_info or '-'}".strip()


def _detail_input_kind(detail_path: Path) -> str:
    return "요약" if detail_path.stem.endswith("_요약") else "상세분석"


def make_classification_output_name(detail_path: Path) -> str:
    stem = detail_path.stem
    if stem.startswith("AI상세추출_"):
        stem = stem[len("AI상세추출_"):]
    kind = _detail_input_kind(detail_path)
    suffix_name = f"_{kind}"
    if stem.endswith(suffix_name):
        stem = stem[:-len(suffix_name)]
    return f"AI결과판단_{kind} 분류_{stem}.txt"


def _classification_decisions(
    base_dir: Path,
    answer_path: Path,
    output_type: str,
    items: List[RelatedSignalItem],
    chosen: Dict[Tuple[str, str], Optional[DbcSignalEvidence]],
    config,
) -> Dict[Tuple[str, str], ClassificationDecision]:
    tc_text = _extract_tc_info_text(base_dir, answer_path, output_type, config)
    heuristic = {
        (item.msg_name, item.sig_name): _score_heuristic_decision(
            item, chosen.get((item.msg_name, item.sig_name)), tc_text, config
        )
        for item in items
    }

    threshold = float(getattr(config, "step_7_local_confidence_threshold", 0.78) or 0.78)
    margin_threshold = float(getattr(config, "step_7_local_score_margin", 1.25) or 1.25)
    ambiguous_keys: List[Tuple[str, str]] = []
    for key, decision in heuristic.items():
        ordered = sorted(decision.scores.values(), reverse=True)
        margin = ordered[0] - ordered[1] if len(ordered) >= 2 else 0.0
        if decision.hard_rule or (decision.confidence >= threshold and margin >= margin_threshold):
            decision.source = "local-high-confidence"
        else:
            ambiguous_keys.append(key)

    if not ambiguous_keys:
        print(f"[INFO] Step 7 모든 신호 로컬 고신뢰 분류 완료: {answer_path.name}")
        return heuristic
    if not _step6_ai_enabled(config) or not str(getattr(config, "api_key", "") or "").strip():
        print(f"[INFO] Step 7 애매 신호 {len(ambiguous_keys)}개가 있으나 API 비활성/Key 없음 -> 로컬 결과 유지")
        return heuristic

    ambiguous_set = set(ambiguous_keys)
    ambiguous_items = [item for item in items if (item.msg_name, item.sig_name) in ambiguous_set]
    ambiguous_heuristic = {key: heuristic[key] for key in ambiguous_keys}
    prompt = _build_classification_prompt(
        base_dir, answer_path, output_type, ambiguous_items, chosen, ambiguous_heuristic, config
    )
    max_retry = int(getattr(config, "step_7_ai_max_retry", getattr(config, "step_6_ai_max_retry", 2)) or 2)
    wait_sec = float(getattr(config, "retry_wait_seconds", 2.0) or 2.0)
    ai_map: Dict[Tuple[str, str], ClassificationDecision] = {}
    for attempt in range(1, max_retry + 1):
        try:
            print(f"[INFO] Step 7 애매 신호만 AI 분류: {answer_path.name} | {len(ambiguous_items)}개 ({attempt}/{max_retry})")
            ai_map = _parse_ai_classification_json((_ask_ai_for_step6(prompt, config) or "").strip())
            if ai_map:
                break
        except Exception as exc:
            print(f"[WARN] Step 7 AI 분류 실패: {answer_path.name} ({attempt}/{max_retry}) {exc}")
            if attempt < max_retry:
                time.sleep(wait_sec)

    ai_map_ci = {(msg.upper(), sig.upper()): dec for (msg, sig), dec in ai_map.items()}
    result = dict(heuristic)
    for key in ambiguous_keys:
        result[key] = _merge_classification_decision(
            heuristic[key], ai_map.get(key) or ai_map_ci.get((key[0].upper(), key[1].upper()))
        )
    return result


def _summary_reason_text(decision: ClassificationDecision) -> str:
    """요약 결과에서는 휴리스틱/AI 채택 메타, 분류/신뢰도/점수 문구를 제거한다."""
    cleaned: List[str] = []
    for reason in decision.reasons:
        text = _squash_spaces(reason)
        if not text:
            continue
        text = re.split(r"\s*/\s*(?=휴리스틱|AI는|AI 고신뢰)", text, maxsplit=1)[0].strip()
        text = re.sub(r"\s*\[(?:분류|신뢰도|점수).*?\]\s*$", "", text).strip()
        if not text:
            continue
        if text.startswith(("휴리스틱 ", "AI는 ", "AI 고신뢰", "분류=", "신뢰도=", "점수(")):
            continue
        if text not in cleaned:
            cleaned.append(text)
    if cleaned:
        return _shorten_reason_text(" / ".join(cleaned[:2]), 150)
    return "신호명, DBC 근거, TC 연관성을 종합하여 분류했습니다."


def _dedupe_preserve(lines: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for line in lines:
        normalized = _squash_spaces(line)
        if normalized and normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out


def _render_classification_output(
    tc_text: str,
    items: List[RelatedSignalItem],
    chosen: Dict[Tuple[str, str], Optional[DbcSignalEvidence]],
    decisions: Dict[Tuple[str, str], ClassificationDecision],
    summary_mode: bool,
) -> str:
    bucket_items: Dict[str, List[RelatedSignalItem]] = {"input": [], "output": [], "excluded": []}
    for item in items:
        decision = decisions.get((item.msg_name, item.sig_name)) or ClassificationDecision("excluded")
        bucket_items.setdefault(decision.bucket, []).append(item)

    def render_bucket(title: str, bucket: str) -> List[str]:
        out = [f"{title}:"]
        selected_items = bucket_items.get(bucket, [])
        if not selected_items:
            out.append("-")
            return out
        for item in selected_items:
            ev = chosen.get((item.msg_name, item.sig_name))
            decision = decisions.get((item.msg_name, item.sig_name)) or ClassificationDecision("excluded")
            original = _dedupe_preserve(item.original_lines)
            if summary_mode:
                value_rows = [line for line in original if "→" not in line]
                change_rows = [line for line in original if "→" in line]
                out.extend(value_rows)
                out.extend(change_rows)
                out.extend([
                    f"    // 신호 요약 : {_signal_summary_from_name(item, ev)}",
                    f"    // 사유 : {_summary_reason_text(decision)}",
                ])
            else:
                for line in original:
                    out.extend([
                        line,
                        f"    // 신호 요약 : {_signal_summary_from_name(item, ev)}",
                        f"    // 사유 : {_decision_reason_text(decision)}",
                    ])
        return out

    lines = [tc_text, "", "[AI 판단 결과]"]
    lines.extend(render_bucket("입력 시그널", "input"))
    lines.append("")
    lines.extend(render_bucket("출력 시그널", "output"))
    lines.append("")
    lines.extend(render_bucket("제외 시그널", "excluded"))
    return "\n".join(lines).rstrip() + "\n"


def process_detail_file(
    detail_path: Path,
    output_type: str,
    index: Dict[Tuple[str, str], List[DbcSignalEvidence]],
    current_idx: int,
    total_count: int,
    config,
) -> Tuple[bool, str]:
    print(f"[CASE {current_idx}/{total_count} | {(current_idx/total_count*100) if total_count else 100:.1f}%] Step 7 처리: {detail_path.name}")
    root = detail_path.parent.parent
    out_dir = root / _judgement_subfolder_name(output_type)
    output_path = out_dir / make_classification_output_name(detail_path)
    try:
        items = parse_related_signals(detail_path)
        chosen: Dict[Tuple[str, str], Optional[DbcSignalEvidence]] = {
            (item.msg_name, item.sig_name): _select_primary_evidence(index.get((item.msg_name, item.sig_name), []))
            for item in items
        }
        base_dir = Path(config.base_dir)
        decisions = _classification_decisions(base_dir, detail_path, output_type, items, chosen, config)
        tc_text = _extract_tc_info_text(base_dir, detail_path, output_type, config)
        summary_mode = _detail_input_kind(detail_path) == "요약"
        _write_text(
            output_path,
            _render_classification_output(tc_text, items, chosen, decisions, summary_mode=summary_mode),
        )

        err_path = output_path.with_name(output_path.stem + ".error.txt")
        if err_path.exists():
            err_path.unlink()
        print(f"[OK] Step 7 분류 저장: {output_path}")
        return True, "성공"
    except Exception as exc:
        out_dir.mkdir(parents=True, exist_ok=True)
        err_path = output_path.with_name(output_path.stem + ".error.txt")
        _write_text(err_path, (
            f"[실패 파일]\n{detail_path.name}\n\n[실패 단계]\nSTEP 7 - 입력/출력/제외 시그널 분류\n\n"
            f"[실패 사유]\n{exc}\n\n[Traceback]\n{traceback.format_exc()}"
        ))
        print(f"[ERROR] Step 7 실패: {detail_path.name} ({exc})")
        return False, str(exc)


def _cleanup_legacy_step7_outputs(base_dir: Path, config) -> None:
    root_name = str(getattr(config, "output_root_dir_name", "AI답변_결과"))
    request_root = str(getattr(config, "input_root_dir_name", "AI_문의용_출력"))
    for root in (base_dir / request_root / root_name, base_dir / root_name):
        for folder_name in ("판단 해설_메세지별", "판단 해설_시간별"):
            folder = root / folder_name
            if not folder.is_dir():
                continue
            for legacy in folder.glob("AI결과판단_*.txt"):
                if legacy.name.startswith("AI결과판단_상세분석 분류_"):
                    continue
                if legacy.name.startswith("AI결과판단_요약 분류_"):
                    continue
                if legacy.name.endswith(".error.txt"):
                    continue
                try:
                    legacy.unlink()
                    print(f"[CLEANUP] 구형 Step 7 출력 삭제: {legacy.name}")
                except Exception as exc:
                    print(f"[WARN] 구형 Step 7 출력 삭제 실패: {legacy.name} ({exc})")


def run(config) -> None:
    base_dir = Path(config.base_dir)
    detail_files = collect_detail_files(base_dir, config)
    _cleanup_legacy_step7_outputs(base_dir, config)
    if not detail_files:
        print("[WARN] Step 7 대상 Step 6 상세분석/요약 파일을 찾지 못했습니다.")
        return
    dbc_index = build_dbc_index(base_dir, config=config)
    success = 0
    fail = 0
    for idx, (path, output_type) in enumerate(detail_files, 1):
        ok, _ = process_detail_file(path, output_type, dbc_index, idx, len(detail_files), config)
        success += int(ok)
        fail += int(not ok)
    print("\n[STEP 7 SUMMARY]")
    print(f"대상 파일: {len(detail_files)}, 성공: {success}, 실패: {fail}")
    if fail:
        raise RuntimeError(f"Step 7 실패 파일이 있습니다: {fail}개")


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
