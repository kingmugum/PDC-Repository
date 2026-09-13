# -*- coding: utf-8 -*-
"""
Signal_Export_V2_Step_6_Signal_Detail_rev_04.py

[V2 REV 04 변경점]
- Step 5 후보 외 Message:Signal 제거 경고 파일(*.후보외삭제.txt)을 Step 6 처리 대상에서 제외
- AI답변_*.txt 최종 정제본만 상세 추출 대상으로 수집하여 경고/진단 TXT로 인한 거짓 실패 방지

[V2 REV 03 변경점]
- DBC Choices의 정수 키 0을 빈값으로 오인하던 정규화 오류 수정
- 0x00/0 값의 의미(Unbelted, Off 등)를 요약 파일과 Step 7 요약 분류에 정상 표시
- None만 빈값으로 취급하여 0, 0.0, Decimal(0) 등 유효한 zero choice를 보존

[V2 REV 02 변경점]
- 메세지별/시간별 각각 기존 원문 보존형 *_상세분석.txt와 채널·시간 제거형 *_요약.txt를 동시에 생성
- 요약은 동일 Message:Signal 값/변화 행을 CH 차이와 시간 차이를 무시해 중복 제거
- 변화에 등장한 각 단일 값을 DBC Choices 의미와 함께 추가하며 변화 행에는 의미 괄호를 붙이지 않음
- 기존 무접미사 AI상세추출_*.txt는 성공 시 정리하여 Step 7 입력 중복을 방지

[REV 02 기존 변경점]
- retry_failed_only=True일 때 Step 5 실제 재실행 대상과 Step 6 자체 .error 대상의 합집합만 처리
- Step 6 성공 케이스를 config.step_6_retry_case_keys에 기록하여 Step 7 재실행 대상으로 전달
- .warning.txt는 실패 재실행 대상에 포함하지 않음
- 단독 실행 시 최신 main_rev_27 설정 사용

목적
- Step 5가 선정한 관련 Message : Signal 목록을 읽는다.
- Step 3의 시그널별 그룹형 상세 TXT에서 선정 신호의 실제 변화 라인만 로컬로 추출한다.
- 선택 시 시간순 TXT에도 동일 선정 목록을 적용하여 시간순 상세 파일을 생성한다.
- API는 사용하지 않는다.
- TC/소스 파일 식별이 다르거나 일부 선정 신호가 상세 원본에서 발견되지 않으면 .warning.txt를 생성한다.

출력
- AI답변_결과/상세 변화_메세지별/AI상세추출_*.txt
- 시간순 상세 옵션 사용 시 AI답변_결과/상세 변화_시간별/AI상세추출_*_시간별.txt
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
import re
import traceback
import json

try:
    import cantools
except Exception:  # pragma: no cover
    cantools = None


@dataclass
class SelectedSignal:
    message: str
    signal: str
    reasons: List[str] = field(default_factory=list)


_RELATED_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\d+(?:\.\d+)?sec\s+)?(?:CH\d+\s+)?"
    r"(?P<msg>[A-Za-z_][\w\-]*)\s*:\s*(?P<sig>[A-Za-z_][\w\-]*)\b(?P<tail>.*)$",
    re.IGNORECASE,
)
_DETAIL_RE = re.compile(
    r"^\s*(?P<time>\d+(?:\.\d+)?)sec\s+(?P<ch>CH\d+)\s+"
    r"(?P<msg>[A-Za-z_][\w\-]*)\s*:\s*(?P<sig>[A-Za-z_][\w\-]*)\b.*$",
    re.IGNORECASE,
)
_CASE_RE = re.compile(r"^(?P<prefix>.+?)[_\s](?P<label>\d+(?:-[\d-]+)?)번(?:_시간별)?$", re.IGNORECASE)


def _read_text(path: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return path.read_text(encoding=enc, errors="replace")
        except Exception:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


def _extract_section(text: str, title: str, next_titles: Iterable[str]) -> str:
    match = re.search(rf"(?ms)^\[{re.escape(title)}\]\s*\n(?P<body>.*)$", text or "")
    if not match:
        return ""
    body = match.group("body")
    positions: List[int] = []
    for next_title in next_titles:
        m = re.search(rf"(?m)^\[{re.escape(next_title)}\]\s*$", body)
        if m:
            positions.append(m.start())
    if positions:
        body = body[:min(positions)]
    return body.strip()


def _answer_roots(base_dir: Path, config) -> List[Path]:
    root_name = str(getattr(config, "output_root_dir_name", "AI답변_결과"))
    request_root = str(getattr(config, "input_root_dir_name", "AI_문의용_출력"))
    candidates = [base_dir / request_root / root_name, base_dir / root_name]
    result: List[Path] = []
    seen: Set[str] = set()
    for path in candidates:
        if not path.is_dir():
            continue
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result



def _normalize_case_stem(name: str) -> str:
    """Step 5 답변/Step 6 결과 파일명을 공통 케이스 stem으로 정규화한다."""
    raw = str(name or "").strip()
    lower = raw.lower()
    for suffix in (".error.txt", ".warning.txt", ".txt"):
        if lower.endswith(suffix):
            raw = raw[:-len(suffix)]
            break
    else:
        raw = Path(raw).stem

    for prefix in ("AI문의용_", "AI답변_", "AI상세추출_"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    if raw.endswith("_시간별"):
        raw = raw[:-len("_시간별")]
    # Step 5 예외 안전 분할 suffix를 병합 케이스로 환원한다.
    match = re.match(r"^(?P<base>.+)_(?P<suffix>[a-z]+)$", raw, flags=re.IGNORECASE)
    if match:
        raw = match.group("base")
    return raw.strip()


def _make_retry_case_key(output_type: str, case_stem: str) -> str:
    return f"{str(output_type or '').strip().casefold()}::{str(case_stem or '').strip().casefold()}"


def _runtime_retry_case_stems(values) -> Set[str]:
    """Step 5 런타임 키에서 output type과 무관한 케이스 stem만 추출한다."""
    out: Set[str] = set()
    for value in list(values or []):
        text = str(value or "").strip().casefold()
        if "::" not in text:
            continue
        _, case_stem = text.split("::", 1)
        if case_stem:
            out.add(case_stem)
    return out


def _step6_error_case_stems(base_dir: Path, config) -> Set[str]:
    """상세 변화 폴더에 남아 있는 Step 6 .error 케이스를 수집한다."""
    out: Set[str] = set()
    for root in _answer_roots(base_dir, config):
        for folder_name in ("상세 변화_메세지별", "상세 변화_시간별"):
            folder = root / folder_name
            if not folder.is_dir():
                continue
            for error_path in folder.glob("AI상세추출_*.error.txt"):
                stem = _normalize_case_stem(error_path.name).casefold()
                if stem:
                    out.add(stem)
    return out


def _register_step6_success(config, answer_path: Path) -> None:
    """Step 6에서 정상 갱신된 케이스를 Step 7 런타임 대상으로 기록한다."""
    case_stem = _normalize_case_stem(answer_path.name)
    if not case_stem:
        return
    key = _make_retry_case_key("메세지별", case_stem)
    current = list(getattr(config, "step_6_retry_case_keys", []) or [])
    normalized = {str(item).strip().casefold() for item in current}
    if key.casefold() not in normalized:
        current.append(key)
    setattr(config, "step_6_retry_case_keys", current)


def _is_step6_answer_file(path: Path) -> bool:
    """Step 6 상세 추출 대상으로 사용할 최종 AI답변 TXT만 판별한다."""
    name = str(path.name or "")
    lower = name.lower()
    if not name.startswith("AI답변_") or not lower.endswith(".txt"):
        return False
    # Step 5 후보 외 항목 제거 상세 기록은 사용자 경고/추적용 파일이므로
    # 실제 AI답변 최종본처럼 Step 6에서 상세 추출하면 안 된다.
    if ".후보외삭제" in name:
        return False
    # 기타 진단/경고/요약 텍스트도 Step 6 입력에서 제외한다.
    excluded_suffixes = (
        ".error.txt",
        ".warning.txt",
        ".후보외삭제.txt",
        ".sources.txt",
    )
    if lower.endswith(excluded_suffixes):
        return False
    return True


def collect_answer_files(base_dir: Path, config) -> List[Path]:
    files: List[Path] = []
    seen: Set[str] = set()
    skipped_aux = 0
    for root in _answer_roots(base_dir, config):
        folder = root / "메세지별"
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("AI답변_*.txt"), key=lambda p: p.name):
            if not _is_step6_answer_file(path):
                skipped_aux += 1
                continue
            # 예외 안전 분할 조각 답변은 최종 병합본이 있으면 제외한다.
            match = re.match(r"^(?P<base>.+)_(?P<suffix>[a-z]+)\.txt$", path.name, flags=re.IGNORECASE)
            if match and path.with_name(match.group("base") + ".txt").exists():
                continue
            key = str(path.resolve())
            if key not in seen:
                seen.add(key)
                files.append(path)
    if skipped_aux:
        print(f"[INFO] Step 6 입력 제외 보조/경고 AI답변 TXT: {skipped_aux}개")

    if not bool(getattr(config, "retry_failed_only", False)):
        return files

    step5_stems = _runtime_retry_case_stems(getattr(config, "step_5_retry_case_keys", []))
    step6_error_stems = _step6_error_case_stems(base_dir, config)
    target_stems = step5_stems | step6_error_stems

    print(
        "[RETRY][STEP6] 대상 합집합: "
        f"Step5 갱신={len(step5_stems)} / "
        f"Step6 .error={len(step6_error_stems)} / "
        f"합계(중복제거)={len(target_stems)}"
    )
    if not target_stems:
        print("[RETRY][STEP6] 실패파일 재실행 대상이 없습니다.")
        return []

    available_stems = {_normalize_case_stem(path.name).casefold() for path in files}
    selected = [path for path in files if _normalize_case_stem(path.name).casefold() in target_stems]
    missing = sorted(target_stems - available_stems)
    if missing:
        print(f"[RETRY][STEP6][WAIT] 대응 AI답변 파일이 없는 대상: {len(missing)}개")
        for item in missing[:20]:
            print(f"  - {item}")
    print(f"[RETRY][STEP6] 실제 재처리 AI답변: {len(selected)}개")
    return selected


@dataclass
class ParsedDetailLine:
    time_text: str
    channel: int
    message: str
    signal: str
    old_value: str
    new_value: str = ""


_DETAIL_VALUE_RE = re.compile(
    r"^\s*(?P<time>\d+(?:\.\d+)?)sec\s+CH(?P<ch>\d+)\s+"
    r"(?P<msg>[A-Za-z_][\w\-]*)\s*:\s*(?P<sig>[A-Za-z_][\w\-]*)\s+"
    r"(?P<old>0x[0-9A-Fa-f]+|[-+]?\d+(?:\.\d+)?)"
    r"(?:\s*→\s*(?P<new>0x[0-9A-Fa-f]+|[-+]?\d+(?:\.\d+)?))?\s*$",
    re.IGNORECASE,
)


def _parse_detail_value_line(line: str) -> Optional[ParsedDetailLine]:
    m = _DETAIL_VALUE_RE.match((line or "").strip())
    if not m:
        return None
    return ParsedDetailLine(
        time_text=m.group("time"),
        channel=int(m.group("ch")),
        message=m.group("msg"),
        signal=m.group("sig"),
        old_value=m.group("old"),
        new_value=m.group("new") or "",
    )


def _canonical_numeric_token(value: object) -> str:
    # 0은 유효한 DBC Choice 값이다. ``value or ""``를 사용하면 정수 0이
    # 빈 문자열로 바뀌어 0x00의 의미가 인덱스에서 누락된다.
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        if text.lower().startswith("0x"):
            return f"i:{int(text, 16)}"
        number = float(text)
        if number.is_integer():
            return f"i:{int(number)}"
        return f"f:{number:.12g}"
    except Exception:
        return "s:" + text.casefold()


def _build_dbc_choice_maps(base_dir: Path, config) -> Tuple[dict, dict]:
    """(CH, Message, Signal) 우선 + Message/Signal fallback Choices index."""
    by_ch: Dict[int, Dict[Tuple[str, str], Dict[str, str]]] = {}
    fallback: Dict[Tuple[str, str], Dict[str, str]] = {}
    if cantools is None:
        print("[WARN] Step 6 DBC 값 의미 보강 생략: cantools 미설치")
        return by_ch, fallback

    dbc_map = getattr(config, "dbc_name_by_ch", {}) or {}
    if not isinstance(dbc_map, dict):
        return by_ch, fallback

    ordered_channels = [ch for ch in (4, 3, 2, 1) if ch in dbc_map] + [
        ch for ch in dbc_map.keys() if ch not in (4, 3, 2, 1)
    ]
    for raw_ch in ordered_channels:
        try:
            ch = int(raw_ch)
        except Exception:
            continue
        raw_name = str(dbc_map.get(raw_ch, "") or "").strip()
        if not raw_name or raw_name.lower() in {"n/a", "na", "none", "null"}:
            continue
        dbc_path = Path(raw_name)
        if not dbc_path.is_absolute():
            dbc_path = base_dir / dbc_path
        if not dbc_path.is_file():
            continue
        try:
            db = cantools.database.load_file(str(dbc_path))
        except Exception as exc:
            print(f"[WARN] Step 6 DBC Choices 로드 실패: CH{ch} {dbc_path.name} ({exc})")
            continue
        per_ch: Dict[Tuple[str, str], Dict[str, str]] = {}
        for msg in getattr(db, "messages", []) or []:
            for sig in getattr(msg, "signals", []) or []:
                choices = dict(getattr(sig, "choices", {}) or {})
                if not choices:
                    continue
                choice_map: Dict[str, str] = {}
                for raw_value, raw_meaning in choices.items():
                    key = _canonical_numeric_token(raw_value)
                    meaning = str(raw_meaning if raw_meaning is not None else "").strip()
                    if key and meaning:
                        choice_map[key] = meaning
                if not choice_map:
                    continue
                pair = (str(getattr(msg, "name", "")), str(getattr(sig, "name", "")))
                if not pair[0] or not pair[1]:
                    continue
                per_ch[pair] = choice_map
                fallback.setdefault(pair, choice_map)
        by_ch[ch] = per_ch
    return by_ch, fallback


def _choice_meaning(
    choice_maps: Tuple[dict, dict],
    channels: List[int],
    message: str,
    signal: str,
    value_token: str,
) -> str:
    by_ch, fallback = choice_maps
    key = _canonical_numeric_token(value_token)
    meanings: List[str] = []
    for ch in channels:
        meaning = (by_ch.get(ch, {}).get((message, signal), {}) or {}).get(key, "")
        if meaning and meaning not in meanings:
            meanings.append(meaning)
    if not meanings:
        meaning = (fallback.get((message, signal), {}) or {}).get(key, "")
        if meaning:
            meanings.append(meaning)
    return " / ".join(meanings)


def _summary_rows_for_signal(
    message: str,
    signal: str,
    rows: List[str],
    choice_maps: Tuple[dict, dict],
) -> List[str]:
    """
    시간/CH를 제거하고 동일 본문은 1개만 유지한다.
    원문에서 처음 나온 단일 값/변화 행 순서는 유지한 뒤,
    변화에만 등장한 단일 값은 마지막에 1회씩 추가한다.
    """
    parsed_rows: List[ParsedDetailLine] = []
    for raw in rows:
        parsed = _parse_detail_value_line(raw)
        if parsed and parsed.message == message and parsed.signal == signal:
            parsed_rows.append(parsed)

    event_rows: List[Tuple[str, str, str]] = []  # kind, old, new
    seen_event = set()
    value_order: List[str] = []
    value_channels: Dict[str, List[int]] = {}
    standalone_values = set()

    def register_value(token: str, ch: int) -> None:
        canonical = _canonical_numeric_token(token)
        if canonical not in value_order:
            value_order.append(canonical)
        value_channels.setdefault(canonical, [])
        if ch not in value_channels[canonical]:
            value_channels[canonical].append(ch)

    token_display: Dict[str, str] = {}
    for parsed in parsed_rows:
        old_key = _canonical_numeric_token(parsed.old_value)
        token_display.setdefault(old_key, parsed.old_value)
        register_value(parsed.old_value, parsed.channel)
        if parsed.new_value:
            new_key = _canonical_numeric_token(parsed.new_value)
            token_display.setdefault(new_key, parsed.new_value)
            register_value(parsed.new_value, parsed.channel)
            event_key = ("change", old_key, new_key)
        else:
            standalone_values.add(old_key)
            event_key = ("value", old_key, "")
        if event_key not in seen_event:
            seen_event.add(event_key)
            event_rows.append(event_key)

    out: List[str] = []
    for kind, old_key, new_key in event_rows:
        old_text = token_display.get(old_key, old_key)
        if kind == "change":
            new_text = token_display.get(new_key, new_key)
            out.append(f"{message} : {signal} {old_text} → {new_text}")
        else:
            meaning = _choice_meaning(choice_maps, value_channels.get(old_key, []), message, signal, old_text)
            suffix = f" ({meaning})" if meaning else ""
            out.append(f"{message} : {signal} {old_text}{suffix}")

    for value_key in value_order:
        if value_key in standalone_values:
            continue
        value_text = token_display.get(value_key, value_key)
        meaning = _choice_meaning(choice_maps, value_channels.get(value_key, []), message, signal, value_text)
        suffix = f" ({meaning})" if meaning else ""
        out.append(f"{message} : {signal} {value_text}{suffix}")
    return out


def parse_selected_signals(answer_path: Path) -> List[SelectedSignal]:
    """Step 5 JSON을 우선 사용하고, 없으면 표준/비표준 TXT를 안전하게 해석한다."""
    json_path = answer_path.with_suffix('.json')
    if json_path.is_file():
        try:
            data = json.loads(json_path.read_text(encoding='utf-8'))
            result: List[SelectedSignal] = []
            for item in list(data.get('related') or []):
                msg = str(item.get('message', '')).strip()
                sig = str(item.get('signal', '')).strip()
                reason = str(item.get('reason', '')).strip()
                if msg and sig:
                    result.append(SelectedSignal(message=msg, signal=sig, reasons=[reason] if reason else []))
            return result
        except Exception as exc:
            print(f"[WARN] Step 5 JSON 읽기 실패, TXT fallback 사용: {json_path.name} ({exc})")

    text = _read_text(answer_path).replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    selected: Dict[Tuple[str, str], SelectedSignal] = {}
    order: List[Tuple[str, str]] = []
    for idx, raw in enumerate(lines):
        line = raw.strip()
        if idx == 0 or not line:
            continue
        if re.fullmatch(r"연관\s*없는\s*메세지", line):
            break
        if re.fullmatch(r"연관\s*있는\s*메세지(?:\s*없음)?", line):
            continue
        match = _RELATED_RE.match(line)
        if not match:
            continue
        msg, sig = match.group("msg"), match.group("sig")
        if msg.lower() in {"definition", "description", "message", "signal"}:
            continue
        key = (msg, sig)
        if key not in selected:
            selected[key] = SelectedSignal(message=msg, signal=sig)
            order.append(key)
        tail = (match.group("tail") or "").strip()
        reason_match = re.search(r"//\s*사유\s*:\s*(.*)$", tail)
        if reason_match:
            reason = reason_match.group(1).strip()
            if reason and reason not in selected[key].reasons:
                selected[key].reasons.append(reason)
    return [selected[key] for key in order]


def _case_parts_from_answer(answer_path: Path) -> Tuple[str, str]:
    stem = answer_path.stem
    if stem.startswith("AI답변_"):
        stem = stem[len("AI답변_"):]
    match = _CASE_RE.match(stem)
    if not match:
        raise ValueError(f"AI답변 파일명에서 TC 식별자를 추출하지 못함: {answer_path.name}")
    return match.group("prefix").strip(), match.group("label").strip()


def _expected_source_paths(base_dir: Path, prefix: str, label: str) -> Tuple[Path, Path, Path]:
    analyzed = base_dir / "분석된 txt 파일"
    grouped = analyzed / f"{prefix} {label}번.txt"
    timewise = analyzed / f"{prefix} {label}번_시간순.txt"
    changed = analyzed / f"{prefix} {label}번_변경된 시그널 모음.txt"
    return grouped, timewise, changed


def _find_inquiry_file(base_dir: Path, answer_path: Path, config) -> Optional[Path]:
    input_root = base_dir / str(getattr(config, "input_root_dir_name", "AI_문의용_출력")) / "메세지별"
    name = answer_path.name.replace("AI답변_", "AI문의용_", 1)
    path = input_root / name
    if path.is_file():
        return path
    stem = Path(name).stem
    candidates = sorted(input_root.glob(stem + '_*.txt'), key=lambda p: p.name)
    return candidates[0] if candidates else None


def _extract_tc_info(inquiry_path: Optional[Path]) -> Tuple[str, str]:
    if inquiry_path is None:
        return "-", ""
    text = _read_text(inquiry_path)
    tc_info = _extract_section(text, "TC 정보", ["요청", "출력 방법", "후보 시그널"])
    source_name = _extract_section(text, "파일명", ["TC 정보"])
    return tc_info or "-", source_name.strip()


def _extract_selected_lines(source_path: Path, selected_keys: Set[Tuple[str, str]]) -> Tuple[List[str], Set[Tuple[str, str]]]:
    lines: List[str] = []
    found: Set[Tuple[str, str]] = set()
    normalized_lookup = {(msg.upper(), sig.upper()): (msg, sig) for msg, sig in selected_keys}
    for raw in _read_text(source_path).splitlines():
        match = _DETAIL_RE.match(raw.strip())
        if not match:
            continue
        normalized_key = (match.group("msg").upper(), match.group("sig").upper())
        original_selected_key = normalized_lookup.get(normalized_key)
        if original_selected_key is not None:
            lines.append(raw.strip())
            found.add(original_selected_key)
    return lines, found


def _detail_output_name(answer_path: Path, kind: str, timewise: bool = False) -> str:
    stem = answer_path.stem.replace("AI답변_", "AI상세추출_", 1)
    if timewise and not stem.endswith("_시간별"):
        stem += "_시간별"
    return f"{stem}_{kind}.txt"


def _legacy_detail_output_name(answer_path: Path, timewise: bool = False) -> str:
    stem = answer_path.stem.replace("AI답변_", "AI상세추출_", 1)
    if timewise and not stem.endswith("_시간별"):
        stem += "_시간별"
    return stem + ".txt"


def _warning_name(detail_path: Path) -> Path:
    return detail_path.with_name(detail_path.stem + ".warning.txt")


def _error_name(detail_path: Path) -> Path:
    return detail_path.with_name(detail_path.stem + ".error.txt")


def _render_detail(
    answer_path: Path,
    source_paths: List[Path],
    inquiry_path: Optional[Path],
    tc_info: str,
    source_candidate_name: str,
    selected: List[SelectedSignal],
    selected_lines: List[str],
) -> str:
    reasons = {(item.message, item.signal): " / ".join(item.reasons) for item in selected}
    grouped: Dict[Tuple[str, str], List[str]] = {}
    order: List[Tuple[str, str]] = []
    for line in selected_lines:
        match = _DETAIL_RE.match(line)
        if not match:
            continue
        key = (match.group("msg"), match.group("sig"))
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(line)

    out = [
        "[파일명]",
        answer_path.name,
        "",
        "[TC 정보]",
        tc_info,
        "",
        "[소스 정보]",
        f"Step 5 답변: {answer_path.name}",
        f"Step 4 문의: {inquiry_path.name if inquiry_path else '-'}",
        f"Step 4 후보 원본: {source_candidate_name or '-'}",
        f"Step 3 상세 원본: {' / '.join(p.name for p in source_paths)}",
        "",
        "[선정 시그널 상세 변화]",
    ]
    for idx, item in enumerate(selected, 1):
        key = (item.message, item.signal)
        out.extend([
            "",
            f"[선정 시그널 {idx}]",
            f"Message = {item.message}",
            f"Signal = {item.signal}",
            f"Step 5 선정 사유 = {reasons.get(key, '')}",
            "상세 변화:",
        ])
        rows = grouped.get(key, [])
        if rows:
            out.extend(rows)
        else:
            out.append("- 상세 변화 없음")
    return "\n".join(out).rstrip() + "\n"



def _render_summary(
    answer_path: Path,
    source_paths: List[Path],
    inquiry_path: Optional[Path],
    tc_info: str,
    source_candidate_name: str,
    selected: List[SelectedSignal],
    selected_lines: List[str],
    choice_maps: Tuple[dict, dict],
) -> str:
    reasons = {(item.message, item.signal): " / ".join(item.reasons) for item in selected}
    grouped: Dict[Tuple[str, str], List[str]] = {}
    for line in selected_lines:
        parsed = _parse_detail_value_line(line)
        if not parsed:
            continue
        grouped.setdefault((parsed.message, parsed.signal), []).append(line)

    out = [
        "[파일명]",
        answer_path.name,
        "",
        "[TC 정보]",
        tc_info,
        "",
        "[소스 정보]",
        f"Step 5 답변: {answer_path.name}",
        f"Step 4 문의: {inquiry_path.name if inquiry_path else '-'}",
        f"Step 4 후보 원본: {source_candidate_name or '-'}",
        f"Step 3 상세 원본: {' / '.join(p.name for p in source_paths)}",
        "",
        "[선정 시그널 요약]",
    ]
    for idx, item in enumerate(selected, 1):
        key = (item.message, item.signal)
        out.extend([
            "",
            f"[선정 시그널 {idx}]",
            f"Message = {item.message}",
            f"Signal = {item.signal}",
            f"Step 5 선정 사유 = {reasons.get(key, '')}",
            "상세 변화:",
        ])
        rows = _summary_rows_for_signal(
            item.message, item.signal, grouped.get(key, []), choice_maps
        )
        if rows:
            out.extend(rows)
        else:
            out.append("- 상세 변화 없음")
    return "\n".join(out).rstrip() + "\n"



def process_answer(answer_path: Path, base_dir: Path, config, index: int, total: int, choice_maps: Tuple[dict, dict]) -> Tuple[bool, str]:
    print(f"[CASE {index}/{total} | {(index/total*100) if total else 100:.1f}%] Step 6 처리: {answer_path.name}")
    root = answer_path.parent.parent
    msg_dir = root / "상세 변화_메세지별"
    time_dir = root / "상세 변화_시간별"
    try:
        prefix, label = _case_parts_from_answer(answer_path)
        grouped_path, time_path, changed_path = _expected_source_paths(base_dir, prefix, label)
        if not grouped_path.is_file() and not time_path.is_file():
            raise FileNotFoundError(f"그룹형/시간순 상세 TXT가 모두 없음: {grouped_path.name}, {time_path.name}")

        selected = parse_selected_signals(answer_path)
        selected_keys = {(item.message, item.signal) for item in selected}
        inquiry = _find_inquiry_file(base_dir, answer_path, config)
        tc_info, source_candidate_name = _extract_tc_info(inquiry)
        warning_lines: List[str] = []
        expected_candidate_name = changed_path.name
        if source_candidate_name and Path(source_candidate_name).name != expected_candidate_name:
            warning_lines.append(f"Step 4 후보 원본 불일치: 기록={source_candidate_name}, 기대={expected_candidate_name}")

        detail_lines: List[str] = []
        found: Set[Tuple[str, str]] = set()
        source_paths: List[Path] = []
        if grouped_path.is_file():
            grouped_lines, grouped_found = _extract_selected_lines(grouped_path, selected_keys)
            detail_lines.extend(grouped_lines)
            found |= grouped_found
            source_paths.append(grouped_path)

        # 원본 Step 3 rev15의 그룹형 TXT에는 "최초 등장 후 값 변경 없음" 신호가 없을 수 있다.
        # Step 3 알고리즘은 바꾸지 않고, 누락된 선정 신호만 시간순 TXT에서 보완한다.
        missing_after_group = selected_keys - found
        if missing_after_group and time_path.is_file():
            fallback_lines, fallback_found = _extract_selected_lines(time_path, missing_after_group)
            detail_lines.extend(fallback_lines)
            found |= fallback_found
            if fallback_found:
                source_paths.append(time_path)
                warning_lines.append(
                    "그룹형 상세에 없던 신호를 시간순 상세에서 보완: "
                    + ", ".join(f"{m}:{s}" for m, s in sorted(fallback_found))
                )

        missing = selected_keys - found
        if missing:
            warning_lines.append(
                "Step 3 상세 TXT에서 미매칭 선정 신호: "
                + ", ".join(f"{m}:{s}" for m, s in sorted(missing))
            )
        if not source_paths:
            source_paths = [grouped_path if grouped_path.is_file() else time_path]

        msg_detail_out = msg_dir / _detail_output_name(answer_path, kind="상세분석", timewise=False)
        msg_summary_out = msg_dir / _detail_output_name(answer_path, kind="요약", timewise=False)
        _write_text(msg_detail_out, _render_detail(
            answer_path, source_paths, inquiry, tc_info, source_candidate_name, selected, detail_lines
        ))
        _write_text(msg_summary_out, _render_summary(
            answer_path, source_paths, inquiry, tc_info, source_candidate_name, selected, detail_lines, choice_maps
        ))
        msg_warning = _warning_name(msg_detail_out)
        if warning_lines:
            _write_text(msg_warning, "[STEP 6 확인 경고]\n" + "\n".join(f"- {x}" for x in warning_lines) + "\n")
        elif msg_warning.exists():
            msg_warning.unlink()

        make_timewise = bool(getattr(config, "step_6_enable_time_detail", getattr(config, "step_5_enable_time_folder", False)))
        if make_timewise and time_path.is_file():
            time_lines, time_found = _extract_selected_lines(time_path, selected_keys)
            time_warnings: List[str] = []
            time_missing = selected_keys - time_found
            if time_missing:
                time_warnings.append("시간순 TXT에서 미매칭 선정 신호: " + ", ".join(f"{m}:{s}" for m, s in sorted(time_missing)))
            time_detail_out = time_dir / _detail_output_name(answer_path, kind="상세분석", timewise=True)
            time_summary_out = time_dir / _detail_output_name(answer_path, kind="요약", timewise=True)
            _write_text(time_detail_out, _render_detail(
                answer_path, [time_path], inquiry, tc_info, source_candidate_name, selected, time_lines
            ))
            _write_text(time_summary_out, _render_summary(
                answer_path, [time_path], inquiry, tc_info, source_candidate_name, selected, time_lines, choice_maps
            ))
            time_warning = _warning_name(time_detail_out)
            if time_warnings:
                _write_text(time_warning, "[STEP 6 확인 경고]\n" + "\n".join(f"- {x}" for x in time_warnings) + "\n")
            elif time_warning.exists():
                time_warning.unlink()

        err = _error_name(msg_detail_out)
        if err.exists():
            err.unlink()
        legacy_msg = msg_dir / _legacy_detail_output_name(answer_path, timewise=False)
        if legacy_msg.exists():
            legacy_msg.unlink()
        legacy_time = time_dir / _legacy_detail_output_name(answer_path, timewise=True)
        if legacy_time.exists():
            legacy_time.unlink()
        print(f"[OK] Step 6 상세분석 저장: {msg_detail_out}")
        print(f"[OK] Step 6 요약 저장: {msg_summary_out}")
        if warning_lines:
            print(f"[WARN] Step 6 warning 생성: {msg_warning}")
        return True, "성공"
    except Exception as exc:
        fallback = msg_dir / _detail_output_name(answer_path, kind="상세분석", timewise=False)
        err = _error_name(fallback)
        _write_text(err, (
            f"[실패 파일]\n{answer_path.name}\n\n"
            f"[실패 단계]\nSTEP 6 - 관련 시그널 상세 변화 추출\n\n"
            f"[실패 사유]\n{exc}\n\n[Traceback]\n{traceback.format_exc()}"
        ))
        print(f"[ERROR] Step 6 실패: {answer_path.name} ({exc})")
        return False, str(exc)


def run(config) -> None:
    base_dir = Path(config.base_dir)
    if bool(getattr(config, "retry_failed_only", False)):
        setattr(config, "step_6_retry_case_keys", [])
    answers = collect_answer_files(base_dir, config)
    choice_maps = _build_dbc_choice_maps(base_dir, config)
    if not answers:
        print("[WARN] Step 6 대상 AI답변 파일이 없습니다.")
        return
    success = 0
    fail = 0
    for idx, answer in enumerate(answers, 1):
        ok, _ = process_answer(answer, base_dir, config, idx, len(answers), choice_maps)
        success += int(ok)
        fail += int(not ok)
        if ok:
            _register_step6_success(config, answer)
    print("\n[STEP 6 SUMMARY]")
    print(f"대상: {len(answers)}, 성공: {success}, 실패: {fail}")
    if bool(getattr(config, "retry_failed_only", False)):
        print(f"Step 7 전달 성공 케이스: {len(getattr(config, 'step_6_retry_case_keys', []) or [])}개")
    if fail:
        raise RuntimeError(f"Step 6 실패 파일이 있습니다: {fail}개")



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
