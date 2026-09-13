# -*- coding: utf-8 -*-
"""
step_3_converting_asc_to_txt_rev_15.py

[V2 REV 04]
- ASC 프레임 방향 자동 모드 추가: auto / rx / tx / both
- auto는 기본 Rx 분석을 수행하되, drop 이후 Rx가 매우 적고 Tx가 충분히 많으면 Rx+Tx로 자동 전환
- rx/tx/both를 사용자가 직접 선택한 경우에는 자동 전환 없이 해당 방향으로만 분석

[V2 REV 03]
- ASC 프레임 방향 옵션 추가: rx / tx / both
- 기존 기본값은 Rx만 분석으로 유지
- CANoe simulated bus 재로깅 ASC처럼 Tx 프레임만 존재하는 로그도 Tx 또는 Rx+Tx 옵션으로 분석 가능
- 선택 방향에 프레임이 없고 반대 방향 프레임만 있으면 원인 진단 경고를 출력

[V2 REV 02]
- 그룹형 상세 TXT / 시간순 상세 TXT / 변경된 시그널 모음 TXT 간 Message:Signal 일치성을 후검증
- 검증은 세 출력 파일 작성 완료 후 읽기 전용으로 수행하며 기존 산출물과 Step 3 성공/실패 판정에 영향을 주지 않음
- 불일치 또는 검증 자체 오류가 있을 때만 별도 *_Step3_결과검증_오류.txt 생성

[V2 REV 01]
- 그룹형 상세 TXT, 시간순 상세 TXT, 변경된 시그널 모음 TXT를 항상 생성
- 생성 여부 옵션은 사용하지 않음

[기존 기능 요약]
1) test_key를 출력 파일명에 쓰기 전에 항상 2자리 패딩(_format_test_key) 적용
   - 인포04 / 인포_4 / 인포_04 / 인포4 => 모두 "04"
   - 시트3 / 시트_03 => 모두 "03"
   - 66-3 => "66-3" (첫 토큰만 2자리 패딩: 6-3 => 06-3)

2) 중복 제거(select_latest_asc_per_test)도 동일하게 패딩된 key 기준으로 묶음
   - "4"와 "04"가 서로 다른 번호로 분리되지 않음

3) 키워드 뒤 숫자 추출 정규식이 "키워드 바로 뒤 숫자"도 안정적으로 허용
   - 인포04 같은 케이스도 1)우선순위 룰로 추출됨

4) 괄호/대괄호 trailing 허용 유지

5) "시트_4-2다리..." 처럼 번호 뒤에 바로 글자(한글/영문/기타)가 붙는 경우에도
   키워드 뒤 번호 추출(1순위)에서 "4-2" 전체가 안정적으로 캡처되도록
   번호 뒤 경계를 "(끝/허용문자/숫자-하이픈이 아닌 문자)"로 완화

[REV 15 변경점]
- DBC 파일 로드 및 message_group -> DBC 매칭 결과를 step_3 실행 시작 시 1회만 준비하고,
  모든 ASC 분석에서 재사용하도록 캐시화
- ASC 파일이 여러 개인 경우 매 파일마다 DBC를 반복 로드하지 않아 처리 속도 개선

[REV 14 변경점]
- 실패파일만 재실행 시 "ASC 파일 단위"가 아니라 "케이스 단위"로 재실행 대상 판정
- 같은 케이스(test_key)의 대표 ASC에 대해 아래 조건 중 하나라도 있으면 케이스 전체 재분석:
  1) 대표 ASC 옆에 .error.txt 존재
  2) 기대되는 step_3 출력(txt / 시간순 txt / 변경된 시그널 모음 txt) 중 필요한 파일이 누락
- 케이스 재실행 시 기존 step_3 출력 파일을 먼저 정리한 뒤 처음부터 다시 생성
- 따라서 일부만 남아 있는 불완전 케이스도 실패 케이스로 간주하고 전체 재생성 가능

[실패파일만 재실행 지원]
- config.retry_failed_only == True 일 때 위 케이스 단위 규칙 적용
- 성공 시 대응되는 .error.txt 삭제
- 실패 시 대응되는 .error.txt 생성
"""

from __future__ import annotations

import re
import traceback
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Set, Optional

import cantools


# =========================================================
# ASC 입력 폴더 유연 탐색 + 출력 폴더
# =========================================================
def _normalize_folder_name(s: str) -> str:
    return re.sub(r"[\s_\-]+", "", (s or "").strip().lower())


def find_log_dir_optional(base_dir: Path) -> Optional[Path]:
    """
    base_dir 바로 아래에서 'log파일' 류 폴더를 찾아 반환.
    없으면 None.
    """
    targets = {
        _normalize_folder_name("log파일"),
        _normalize_folder_name("log file"),
        _normalize_folder_name("로그파일"),
        _normalize_folder_name("로그폴더"),
    }

    for p in base_dir.iterdir():
        if p.is_dir() and _normalize_folder_name(p.name) in targets:
            return p
    return None


def ensure_output_dir(base_dir: Path) -> Path:
    out_dir = base_dir / "분석된 txt 파일"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def collect_asc_files(base_dir: Path) -> List[Path]:
    """
    base_dir의 asc + (있으면) log_dir의 asc를 합쳐서 반환.
    파일명이 동일하면 mtime이 최신인 1개만 선택.
    """
    asc_candidates: List[Path] = []

    asc_candidates += list(base_dir.glob("*.asc"))

    log_dir = find_log_dir_optional(base_dir)
    if log_dir is not None:
        asc_candidates += list(log_dir.glob("*.asc"))
        print(f"[OK] Log directory detected: {log_dir}")
    else:
        print("[WARN] Log directory not found. Using base_dir ASC files only.")

    best_by_name: Dict[str, Path] = {}
    for p in asc_candidates:
        name = p.name
        prev = best_by_name.get(name)
        if prev is None:
            best_by_name[name] = p
        else:
            if p.stat().st_mtime > prev.stat().st_mtime:
                best_by_name[name] = p

    selected = sorted(best_by_name.values(), key=lambda x: x.name)
    dup_count = len(asc_candidates) - len(selected)
    if dup_count > 0:
        print(f"[CHECK] Duplicate ASC filenames removed: {dup_count}")

    return selected


# =========================================================
# .error.txt 유틸
# =========================================================
def get_error_log_path_for_asc(asc_path: Path) -> Path:
    return asc_path.with_name(f"{asc_path.stem}.error.txt")


def has_error_log_for_asc(asc_path: Path) -> bool:
    return get_error_log_path_for_asc(asc_path).exists()


def write_error_log_for_asc(asc_path: Path, reason: str, exc: Exception | None = None) -> None:
    error_path = get_error_log_path_for_asc(asc_path)

    tb_text = ""
    exc_repr = ""
    if exc is not None:
        exc_repr = repr(exc)
        tb_text = traceback.format_exc()

    text = (
        f"[실패 파일]\n{asc_path.name}\n\n"
        f"[원본 경로]\n{asc_path}\n\n"
        f"[실패 단계]\nSTEP 3 - ASC -> TXT\n\n"
        f"[실패 사유]\n{reason}\n\n"
        f"[예외 메시지]\n{exc_repr}\n\n"
        f"[상세 Traceback]\n{tb_text}"
    )
    error_path.write_text(text, encoding="utf-8")


def remove_error_log_for_asc_if_exists(asc_path: Path) -> None:
    error_path = get_error_log_path_for_asc(asc_path)
    try:
        if error_path.exists():
            error_path.unlink()
            print(f"[OK] 이전 에러로그 삭제: {error_path.name}")
    except Exception as e:
        print(f"[WARN] 에러로그 삭제 실패: {error_path} ({e})")


# =========================================================
# ASC 파서(유연 버전: Vector ASC 중심)
# =========================================================
HEAD_RE = re.compile(
    r"^\s*(?P<time>\d+\.\d+)\s+(?P<bus>CANFD|CAN)\s+(?P<ch>\d+)\s+(?P<dir>Rx|Tx)\s+(?P<id>[0-9A-Fa-f]+x?)\s+",
    re.IGNORECASE
)

HEXBYTE_RE = re.compile(r"^[0-9A-Fa-f]{2}$")
DATA_MARKERS = {"a", "b", "c", "d"}
DT_RE = re.compile(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})")
BASE_RE = re.compile(r"\bbase\s+(hex|dec)\b", re.IGNORECASE)
MSG_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*$")


# =========================================================
# Dataclass
# =========================================================
@dataclass
class AscParseStats:
    total_lines: int = 0
    head_matched: int = 0
    frames_yielded: int = 0
    bad_head_lines: int = 0
    marker_not_found: int = 0
    bad_length: int = 0
    not_enough_data: int = 0
    mode_counts: Dict[str, int] = field(default_factory=dict)

    def inc_mode(self, mode: str):
        self.mode_counts[mode] = self.mode_counts.get(mode, 0) + 1

    def _rate(self, num: int, den: int) -> float:
        return (num / den * 100.0) if den else 0.0

    def _judge(self):
        head_rate = self._rate(self.head_matched, self.total_lines)
        yield_rate = self._rate(self.frames_yielded, self.head_matched)
        marker_rate = self._rate(self.marker_not_found, self.head_matched)

        if self.bad_length > 0 or self.not_enough_data > 0:
            return "나쁨", head_rate, yield_rate, marker_rate

        if head_rate < 70.0:
            return "나쁨", head_rate, yield_rate, marker_rate
        if head_rate < 90.0:
            return "주의", head_rate, yield_rate, marker_rate

        if yield_rate < 70.0:
            return "나쁨", head_rate, yield_rate, marker_rate
        if yield_rate < 90.0:
            return "주의", head_rate, yield_rate, marker_rate

        if marker_rate > 15.0:
            return "나쁨", head_rate, yield_rate, marker_rate
        if marker_rate > 5.0:
            return "주의", head_rate, yield_rate, marker_rate

        return "좋음", head_rate, yield_rate, marker_rate

    def dump(self, title: str):
        verdict, head_rate, yield_rate, marker_rate = self._judge()
        print(f"[DEBUG] ASC parse stats: {title}")
        print(f"  verdict          : {verdict}")
        print(f"  total lines      : {self.total_lines}")
        print(f"  head matched     : {self.head_matched}  ({head_rate:.1f}%)")
        print(f"  frames yielded   : {self.frames_yielded}  ({yield_rate:.1f}% of head)")
        print(f"  bad head lines   : {self.bad_head_lines}  ({self._rate(self.bad_head_lines, self.total_lines):.1f}%)")
        print(f"  marker not found : {self.marker_not_found}  ({marker_rate:.1f}% of head)")
        print(f"  bad length       : {self.bad_length}")
        print(f"  not enough data  : {self.not_enough_data}")

        if self.mode_counts:
            print("  parser modes     :")
            for k in sorted(self.mode_counts.keys()):
                print(f"    {k:<16} : {self.mode_counts[k]}")


@dataclass
class AnalyzeStats:
    frames_after_drop: int = 0
    target_id_frames: int = 0
    decode_success: int = 0
    decode_fail: int = 0
    signal_rows_seen: int = 0
    signal_changes_found: int = 0

    def dump(self, title: str):
        print(f"[DEBUG] Analyze stats: {title}")
        print(f"  frames after drop      : {self.frames_after_drop}")
        print(f"  target_id_frames       : {self.target_id_frames}")
        print(f"  decode_success         : {self.decode_success}")
        print(f"  decode_fail            : {self.decode_fail}")
        print(f"  signal_rows_seen       : {self.signal_rows_seen}")
        print(f"  signal changes found   : {self.signal_changes_found}")


@dataclass
class GroupSpec:
    group_file: Path
    target_messages: List[str]
    target_signal_pairs: Set[Tuple[str, str]]


@dataclass
class Step3DbcCache:
    """
    step_3 실행 중 모든 ASC 분석에서 재사용하는 DBC 해석 캐시.
    - db_by_ch: CH별 cantools DB
    - msgs_by_ch_id: CH/Frame ID 기준 target message map
    - msgs_all_by_id: CH가 불일치할 때 fallback으로 쓰는 전체 Frame ID map
    """
    db_by_ch: Dict[int, cantools.database.Database]
    msgs_by_ch_id: Dict[int, Dict[int, List]]
    msgs_all_by_id: Dict[int, List[Tuple[int, object]]]


# =========================================================
# threshold 관련
# =========================================================
def should_skip_by_threshold(
    sig_name: str,
    change_count: int,
    threshold: int,
    skip_high_frequency: bool,
    threshold_except_substrings: List[str],
) -> bool:
    if not skip_high_frequency:
        return False
    if change_count < threshold:
        return False

    s = (sig_name or "").lower()

    if "pos" in s:
        return False

    for sub in threshold_except_substrings:
        if sub in s:
            return False

    return True


# =========================================================
# payload parser helpers
# =========================================================
def _is_uint_token(tok: str) -> bool:
    return bool(re.fullmatch(r"\d+", tok))


def _is_hexbyte_token(tok: str) -> bool:
    return bool(HEXBYTE_RE.fullmatch(tok))


def _collect_hexbytes(tokens: List[str], start_idx: int) -> List[str]:
    out = []
    for tok in tokens[start_idx:]:
        if _is_hexbyte_token(tok):
            out.append(tok)
        else:
            if out:
                break
    return out


def _try_marker_mode(tokens: List[str]) -> Tuple[bool, Optional[int], List[str], str]:
    for i, tok in enumerate(tokens):
        if tok.lower() in DATA_MARKERS and i + 1 < len(tokens):
            if not _is_uint_token(tokens[i + 1]):
                continue

            length = int(tokens[i + 1])
            if not (0 <= length <= 64):
                return False, None, [], "bad_length"

            data_tokens = _collect_hexbytes(tokens, i + 2)
            if len(data_tokens) < length:
                return False, length, data_tokens, "not_enough_data"

            return True, length, data_tokens[:length], "marker"

    return False, None, [], "fail"


def _try_numeric_head_mode(tokens: List[str]) -> Tuple[bool, Optional[int], List[str], str]:
    if len(tokens) >= 5 and all(_is_uint_token(tok) for tok in tokens[:4]):
        length = int(tokens[3])
        if not (0 <= length <= 64):
            return False, None, [], "bad_length"

        data_tokens = _collect_hexbytes(tokens, 4)
        if len(data_tokens) < length:
            return False, length, data_tokens, "not_enough_data"

        return True, length, data_tokens[:length], "numeric_head"

    return False, None, [], "fail"


def _try_name_plus_numeric_mode(tokens: List[str]) -> Tuple[bool, Optional[int], List[str], str]:
    if len(tokens) >= 6 and MSG_NAME_RE.fullmatch(tokens[0]) and all(_is_uint_token(tok) for tok in tokens[1:5]):
        length = int(tokens[4])
        if not (0 <= length <= 64):
            return False, None, [], "bad_length"

        data_tokens = _collect_hexbytes(tokens, 5)
        if len(data_tokens) < length:
            return False, length, data_tokens, "not_enough_data"

        return True, length, data_tokens[:length], "name_plus_numeric"

    return False, None, [], "fail"


def _try_scan_any_plausible_window(tokens: List[str]) -> Tuple[bool, Optional[int], List[str], str]:
    best = None

    for i, tok in enumerate(tokens):
        if not _is_uint_token(tok):
            continue

        length = int(tok)
        if not (0 <= length <= 64):
            continue

        data_tokens = _collect_hexbytes(tokens, i + 1)
        if len(data_tokens) < length:
            continue

        score = (len(data_tokens), -i)
        candidate = (score, i, length, data_tokens[:length])

        if best is None or candidate[0] > best[0]:
            best = candidate

    if best is not None:
        _score, _idx, length, data_tokens = best
        return True, length, data_tokens, "scan_fallback"

    return False, None, [], "fail"


def _parse_vector_payload_tokens(tokens: List[str]) -> Tuple[bool, Optional[int], List[str], str]:
    for parser in (
        _try_marker_mode,
        _try_numeric_head_mode,
        _try_name_plus_numeric_mode,
        _try_scan_any_plausible_window,
    ):
        ok, length, data_tokens, mode = parser(tokens)
        if ok:
            return ok, length, data_tokens, mode
        if mode in ("bad_length", "not_enough_data"):
            return ok, length, data_tokens, mode

    return False, None, [], "fail"


# =========================================================
# ASC 관련
# =========================================================
def detect_asc_base(path: str, max_lines: int = 200) -> int:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if i >= max_lines:
                break
            m = BASE_RE.search(line)
            if m:
                return 16 if m.group(1).lower() == "hex" else 10
    return 16


def parse_can_id(id_str: str, default_base: int) -> int:
    s = id_str.strip().lower()
    if s.endswith("x"):
        return int(s[:-1], 16)
    if s.startswith("0x"):
        return int(s, 16)
    if re.search(r"[a-f]", s):
        return int(s, 16)
    return int(s, default_base)


def get_asc_parse_stats(path: str) -> AscParseStats:
    stats = AscParseStats()

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            stats.total_lines += 1

            m = HEAD_RE.match(line)
            if not m:
                stats.bad_head_lines += 1
                continue

            stats.head_matched += 1
            rest = line[m.end():].strip()
            tokens = rest.split()

            ok, length, data_tokens, mode = _parse_vector_payload_tokens(tokens)

            if not ok:
                if mode == "bad_length":
                    stats.bad_length += 1
                elif mode == "not_enough_data":
                    stats.not_enough_data += 1
                else:
                    stats.marker_not_found += 1
                stats.inc_mode(mode)
                continue

            if length is None:
                stats.bad_length += 1
                stats.inc_mode("bad_length")
                continue

            if len(data_tokens) < length:
                stats.not_enough_data += 1
                stats.inc_mode("not_enough_data")
                continue

            stats.frames_yielded += 1
            stats.inc_mode(mode)

    return stats


VALID_ASC_FRAME_DIRECTIONS = {"rx", "tx"}
ASC_FRAME_DIRECTION_AUTO_RX_MAX_FRAMES = 100
ASC_FRAME_DIRECTION_AUTO_TX_MIN_FRAMES = 1000
ASC_FRAME_DIRECTION_AUTO_TX_RX_RATIO = 10


def _normalize_asc_frame_direction_text(value) -> str:
    text = str(value or "auto").strip().lower()
    text = text.replace(" ", "")
    text = text.replace("_", "")
    text = text.replace("-", "")
    return text


def is_auto_asc_frame_direction(value) -> bool:
    text = _normalize_asc_frame_direction_text(value)
    return text in ("auto", "자동", "rxauto", "autofallback", "rxpriority", "rx우선", "rx우선자동")


def normalize_asc_frame_directions(value) -> Set[str]:
    """ASC 분석 대상 방향을 {rx, tx} 집합으로 정규화한다.

    허용값:
    - auto / 자동: 기본 Rx, 특정 조건에서 Rx+Tx 자동 전환을 위한 설정값
    - rx / Rx / 일반 / real
    - tx / Tx / simulated / sim
    - both / all / rx+tx / tx+rx
    - ["rx", "tx"] 같은 리스트/튜플/세트

    주의: auto 자체는 이 함수에서는 일단 Rx로 정규화한다.
    실제 자동 전환은 resolve_effective_asc_frame_directions()에서 프레임 수를 보고 결정한다.
    """
    if isinstance(value, (list, tuple, set)):
        out: Set[str] = set()
        for item in value:
            out |= normalize_asc_frame_directions(item)
        return out or {"rx"}

    text = _normalize_asc_frame_direction_text(value)

    if text in ("both", "all", "rxtx", "txrx", "rx+tx", "tx+rx", "전체"):
        return {"rx", "tx"}
    if text in ("tx", "sim", "simulated", "simulatedbus", "송신"):
        return {"tx"}
    if text in ("rx", "real", "realbus", "수신") or is_auto_asc_frame_direction(value):
        return {"rx"}

    print(f"[WARN] 지원하지 않는 ASC_FRAME_DIRECTION 값입니다: {value!r} -> auto로 처리")
    return {"rx"}


def should_auto_switch_to_rx_tx(dir_counts: Dict[str, int]) -> bool:
    """Rx가 매우 적고 Tx가 충분히 많을 때만 auto 모드에서 Rx+Tx로 전환한다."""
    rx_count = int(dir_counts.get("rx", 0) or 0)
    tx_count = int(dir_counts.get("tx", 0) or 0)

    if tx_count < ASC_FRAME_DIRECTION_AUTO_TX_MIN_FRAMES:
        return False
    if rx_count > ASC_FRAME_DIRECTION_AUTO_RX_MAX_FRAMES:
        return False

    ratio_base = max(rx_count, 1)
    return tx_count >= ratio_base * ASC_FRAME_DIRECTION_AUTO_TX_RX_RATIO


def resolve_effective_asc_frame_directions(value, dir_counts: Dict[str, int]) -> Tuple[Set[str], str]:
    """사용자 설정과 ASC Rx/Tx 분포를 바탕으로 실제 분석 방향을 결정한다."""
    if is_auto_asc_frame_direction(value):
        if should_auto_switch_to_rx_tx(dir_counts):
            return {"rx", "tx"}, "auto_switch_to_both"
        return {"rx"}, "auto_rx"
    return normalize_asc_frame_directions(value), "manual"


def format_asc_frame_directions(directions: Set[str]) -> str:
    dirs = normalize_asc_frame_directions(directions)
    if dirs == {"rx"}:
        return "Rx only"
    if dirs == {"tx"}:
        return "Tx only"
    return "Rx + Tx"


def format_asc_frame_direction_setting(value) -> str:
    if is_auto_asc_frame_direction(value):
        return "Auto (Rx priority, Tx fallback to Rx+Tx)"
    return format_asc_frame_directions(normalize_asc_frame_directions(value))


def count_frame_directions_after_drop(path: str, drop_first_seconds: float) -> Tuple[Dict[str, int], Dict[Tuple[str, int], int]]:
    """payload decode 전, ASC head 기준으로 drop 이후 Rx/Tx와 채널별 개수를 센다."""
    dir_counts: Dict[str, int] = {}
    dir_ch_counts: Dict[Tuple[str, int], int] = {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = HEAD_RE.match(line)
            if not m:
                continue
            try:
                t = float(m.group("time"))
            except Exception:
                continue
            if t < drop_first_seconds:
                continue
            direction = str(m.group("dir") or "").strip().lower()
            try:
                ch = int(m.group("ch"))
            except Exception:
                continue
            if direction not in VALID_ASC_FRAME_DIRECTIONS:
                continue
            dir_counts[direction] = dir_counts.get(direction, 0) + 1
            key = (direction, ch)
            dir_ch_counts[key] = dir_ch_counts.get(key, 0) + 1
    return dir_counts, dir_ch_counts


def print_direction_diagnosis(asc_name: str, drop_first_seconds: float, selected_directions: Set[str], dir_counts: Dict[str, int], dir_ch_counts: Dict[Tuple[str, int], int], *, raw_option=None, auto_reason: str = "manual") -> None:
    selected_directions = normalize_asc_frame_directions(selected_directions)
    selected_count = sum(dir_counts.get(d, 0) for d in selected_directions)
    other_dirs = VALID_ASC_FRAME_DIRECTIONS - selected_directions
    other_count = sum(dir_counts.get(d, 0) for d in other_dirs)

    def _fmt_counts() -> str:
        parts = []
        for d in ("rx", "tx"):
            if dir_counts.get(d, 0):
                parts.append(f"{d.upper()}={dir_counts.get(d, 0)}")
        return ", ".join(parts) if parts else "없음"

    if is_auto_asc_frame_direction(raw_option):
        print(f"[INFO] ASC frame direction option: Auto (Rx priority)")
        if auto_reason == "auto_switch_to_both":
            print(
                "[INFO] ASC frame direction auto decision: Rx 프레임이 매우 적고 Tx 프레임이 충분히 많아 "
                "Rx + Tx로 자동 전환"
            )
        else:
            print("[INFO] ASC frame direction auto decision: Rx only 유지")
    else:
        print(f"[INFO] ASC frame direction option: {format_asc_frame_directions(selected_directions)}")
    print(f"[INFO] ASC frame direction effective: {format_asc_frame_directions(selected_directions)}")
    print(f"[INFO] ASC frame direction counts after drop({drop_first_seconds}s): {_fmt_counts()}")
    if dir_ch_counts:
        for d in ("rx", "tx"):
            ch_parts = [f"CH{ch}={cnt}" for (dd, ch), cnt in sorted(dir_ch_counts.items(), key=lambda x: (x[0][0], x[0][1])) if dd == d]
            if ch_parts:
                print(f"  {d.upper()} by channel: " + ", ".join(ch_parts))

    if selected_count == 0 and other_count > 0:
        other_text = format_asc_frame_directions(other_dirs)
        selected_text = format_asc_frame_directions(selected_directions)
        print(
            f"[WARN] 선택한 방향({selected_text})의 프레임이 drop 이후 0개입니다. "
            f"반대 방향({other_text}) 프레임은 {other_count}개 존재합니다."
        )
        if selected_directions == {"rx"} and dir_counts.get("tx", 0) > 0:
            print(
                "[WARN] 이 ASC는 CANoe simulated bus 재로깅처럼 Tx 프레임만 기록된 파일일 가능성이 큽니다. "
                "GUI에서 'Tx만(Simulated bus)' 또는 'Rx+Tx(전체)'로 변경해 다시 실행하세요."
            )


def read_frames_from_asc(path: str, frame_directions=None):
    default_base = detect_asc_base(path)
    allowed_directions = normalize_asc_frame_directions(frame_directions)

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = HEAD_RE.match(line)
            if not m:
                continue

            t = float(m.group("time"))
            ch = int(m.group("ch"))
            direction = m.group("dir")

            if direction.lower() not in allowed_directions:
                continue

            raw_id = m.group("id")
            can_id = parse_can_id(raw_id, default_base)

            rest = line[m.end():].strip()
            tokens = rest.split()

            ok, length, data_tokens, _mode = _parse_vector_payload_tokens(tokens)
            if not ok or length is None:
                continue
            if len(data_tokens) < length:
                continue

            data = bytes(int(b, 16) for b in data_tokens[:length])
            yield t, ch, direction, can_id, data


# =========================================================
# 파일명에서 datetime / test_key 추출
# =========================================================
def extract_datetime_from_asc_stem(asc_stem: str) -> Optional[datetime]:
    m = DT_RE.search(asc_stem)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d_%H-%M-%S")
    except ValueError:
        return None


_SUFFIX_TC_RE = r"(?:[_\-\s]*TC)?"
_ALLOWED_TRAIL_CHARS_CLASS = r"[_\-\s\(\)\[\]\{\}]"


def _build_keyword_number_regex(keywords: List[str]) -> re.Pattern:
    escaped = [re.escape(k) for k in (keywords or []) if k]
    if not escaped:
        return re.compile(r"$^")

    kw_pat = "|".join(escaped)
    end_guard = rf"(?=$|{_ALLOWED_TRAIL_CHARS_CLASS}|[^0-9-])"

    pattern = (
        rf"(?:^|{_ALLOWED_TRAIL_CHARS_CLASS})"
        rf"(?:{kw_pat})"
        rf"{_SUFFIX_TC_RE}"
        rf"{_ALLOWED_TRAIL_CHARS_CLASS}*"
        rf"([0-9]+(?:-[0-9]+)*)"
        rf"{end_guard}"
    )
    return re.compile(pattern, flags=re.IGNORECASE)


def _format_test_key(key: str) -> str:
    s = (key or "").strip()

    if re.fullmatch(r"\d+(?:-\d+)*", s):
        parts = s.split("-")
        parts[0] = parts[0].zfill(2)
        return "-".join(parts)

    m = re.fullmatch(r"(\d+)", s)
    if m:
        return m.group(1).zfill(2)

    return s


def extract_test_key_from_asc_stem(asc_stem: str, keywords=None) -> str:
    if keywords is None:
        keywords = []

    stem_wo_dt = re.sub(r"_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$", "", asc_stem, flags=re.IGNORECASE)

    kw_re = _build_keyword_number_regex(keywords)
    m = kw_re.search(stem_wo_dt)
    if m:
        return m.group(1)

    m = re.search(
        rf"(?:^|[_\-\s])([0-9]+(?:-[0-9]+)+)(?=$|{_ALLOWED_TRAIL_CHARS_CLASS})",
        stem_wo_dt,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1)

    m = re.search(
        rf"(?:^|[_\-\s])([0-9]+)(?=$|{_ALLOWED_TRAIL_CHARS_CLASS})",
        stem_wo_dt,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1)

    return stem_wo_dt


def make_output_txt_name_from_key(test_key: str, prefix: str) -> str:
    safe_key = re.sub(r'[\\/:*?"<>|]', "_", str(test_key))
    return f"{prefix} {safe_key}번.txt"


def make_output_txt_name_timeorder_from_key(test_key: str, prefix: str) -> str:
    safe_key = re.sub(r'[\\/:*?"<>|]', "_", str(test_key))
    return f"{prefix} {safe_key}번_시간순.txt"


def make_output_txt_name_changed_signals_from_key(test_key: str, prefix: str) -> str:
    safe_key = re.sub(r'[\\/:*?"<>|]', "_", str(test_key))
    return f"{prefix} {safe_key}번_변경된 시그널 모음.txt"


# =========================================================
# message_group 로딩
# =========================================================
def load_latest_message_group(base_dir: Path) -> Optional[GroupSpec]:
    group_files = list(base_dir.glob("*message_group*.txt"))
    if not group_files:
        print("[ERROR] message_group 텍스트 파일을 못 찾음. 예: 1_cluster_message_group.txt")
        return None

    latest = max(group_files, key=lambda p: p.stat().st_mtime)

    target_messages: List[str] = []
    target_signal_pairs: Set[Tuple[str, str]] = set()

    with open(latest, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue

            if ":" in s:
                msg_name, sig_name = map(str.strip, s.split(":", 1))
                if msg_name:
                    target_messages.append(msg_name)
                if msg_name and sig_name:
                    target_signal_pairs.add((msg_name, sig_name))
            else:
                target_messages.append(s)

    seen = set()
    messages_unique = []
    for m in target_messages:
        mm = m.strip()
        if mm and mm not in seen:
            seen.add(mm)
            messages_unique.append(mm)

    return GroupSpec(
        group_file=latest,
        target_messages=messages_unique,
        target_signal_pairs=target_signal_pairs,
    )


# =========================================================
# DBC 준비
# =========================================================
def _load_dbc_by_channel(base_dir: Path, dbc_name_by_ch) -> Dict[int, cantools.database.Database]:
    dbc_files = sorted(base_dir.glob("*.dbc"))
    dbc_path_by_name = {p.name: p for p in dbc_files}

    db_by_ch = {}
    for ch, dbc_name in dbc_name_by_ch.items():
        p = dbc_path_by_name.get(dbc_name)
        if p is None:
            raise FileNotFoundError(f"CH{ch}에 지정한 DBC를 폴더에서 못 찾음: {dbc_name}")
        db_by_ch[ch] = cantools.database.load_file(str(p))

    return db_by_ch


def _build_msgs_by_ch_id(
    db_by_ch: Dict[int, cantools.database.Database],
    target_messages: List[str]
) -> Dict[int, Dict[int, List]]:
    msgs_by_ch_id: Dict[int, Dict[int, List]] = {}
    missing_by_ch: Dict[int, List[str]] = {}

    print("[CHECK] message_group -> DBC 매칭 시작")

    for ch, db in db_by_ch.items():
        msgs_by_id: Dict[int, List] = {}
        missing: List[str] = []

        print(f"\n[CHECK] CH{ch} DBC loading result")

        for name in target_messages:
            clean_name = name.strip()
            if not clean_name:
                continue

            try:
                msg = db.get_message_by_name(clean_name)
                msgs_by_id.setdefault(msg.frame_id, []).append(msg)
            except KeyError:
                missing.append(clean_name)

        msgs_by_ch_id[ch] = msgs_by_id
        missing_by_ch[ch] = missing

        found_count = len(target_messages) - len(missing)
        print(f"  found   : {found_count}")
        print(f"  missing : {len(missing)}")

        if missing:
            sample = ", ".join(missing[:10])
            more = "" if len(missing) <= 10 else f" ... (+{len(missing) - 10})"
            print(f"  missing sample: {sample}{more}")

        duplicate_ids = {fid: msgs for fid, msgs in msgs_by_id.items() if len(msgs) > 1}
        if duplicate_ids:
            print(f"  duplicate frame_id count: {len(duplicate_ids)}")
            shown = 0
            for fid, msgs in sorted(duplicate_ids.items(), key=lambda x: x[0]):
                names = [m.name for m in msgs]
                print(f"    0x{fid:X} -> {names}")
                shown += 1
                if shown >= 10:
                    remaining = len(duplicate_ids) - shown
                    if remaining > 0:
                        print(f"    ... (+{remaining})")
                    break
        else:
            print("  duplicate frame_id count: 0")

    print("\n[CHECK] message_group -> DBC 매칭 요약")
    for ch in sorted(db_by_ch.keys()):
        total = len(target_messages)
        miss = missing_by_ch.get(ch, [])
        found = total - len(miss)
        print(f"  CH{ch}: found={found}, missing={len(miss)}")

    return msgs_by_ch_id


def _build_msgs_all_by_id(msgs_by_ch_id: Dict[int, Dict[int, List]]) -> Dict[int, List[Tuple[int, object]]]:
    all_by_id: Dict[int, List[Tuple[int, object]]] = {}
    for dbc_ch, d in msgs_by_ch_id.items():
        for fid, msgs in d.items():
            for m in msgs:
                all_by_id.setdefault(fid, []).append((dbc_ch, m))
    return all_by_id


def build_step3_dbc_cache(
    base_dir: Path,
    dbc_name_by_ch,
    group_spec: GroupSpec,
) -> Step3DbcCache:
    """
    DBC 로드와 message_group 매칭을 step_3 실행당 1회만 수행한다.
    기존에는 analyze_single_asc()가 ASC 파일마다 동일 작업을 반복했기 때문에,
    ASC 수가 많거나 DBC가 큰 경우 불필요한 시간이 누적될 수 있었다.
    """
    print("\n[CHECK] step_3 DBC 캐시 준비 시작")
    db_by_ch = _load_dbc_by_channel(base_dir, dbc_name_by_ch)
    msgs_by_ch_id = _build_msgs_by_ch_id(db_by_ch, group_spec.target_messages)
    msgs_all_by_id = _build_msgs_all_by_id(msgs_by_ch_id)
    print("[OK] step_3 DBC 캐시 준비 완료")
    return Step3DbcCache(
        db_by_ch=db_by_ch,
        msgs_by_ch_id=msgs_by_ch_id,
        msgs_all_by_id=msgs_all_by_id,
    )


def _precheck_missing_ids_in_log(
    asc_path: str,
    msgs_by_ch_id: Dict[int, Dict[int, List]],
    drop_first_seconds: float,
    frame_directions=None,
):
    expected_ids_by_ch = {ch: set(d.keys()) for ch, d in msgs_by_ch_id.items()}
    seen_ids_by_ch = {ch: set() for ch in expected_ids_by_ch.keys()}

    for t, ch, _direction, can_id, _data in read_frames_from_asc(asc_path, frame_directions=frame_directions):
        if t < drop_first_seconds:
            continue
        if ch in expected_ids_by_ch and can_id in expected_ids_by_ch[ch]:
            seen_ids_by_ch[ch].add(can_id)

    missing = []
    for ch, expected in expected_ids_by_ch.items():
        miss = expected - seen_ids_by_ch.get(ch, set())
        if miss:
            missing.append((ch, sorted(miss)))

    if missing:
        print("[CHECK] DBC(target)에 있지만 로그(drop 이후)에 등장하지 않은 CAN ID가 있습니다.")
        for ch, ids in missing:
            sample = ", ".join(f"0x{x:X}" for x in ids[:20])
            more = "" if len(ids) <= 20 else f" ... (+{len(ids)-20})"
            print(f"  CH{ch} missing IDs: {sample}{more}")
    else:
        print("[CHECK] DBC(target) CAN ID들이 로그(drop 이후)에 모두 1회 이상 등장했습니다.")


# =========================================================
# 분석 본체
# =========================================================

# =========================================================
# V2 REV 02: Step 3 산출물 비간섭 일치성 검증
# =========================================================
_STEP3_DETAIL_PAIR_RE = re.compile(
    r"^\s*\d+(?:\.\d+)?sec\s+CH\d+\s+"
    r"(?P<msg>[A-Za-z_][\w\-]*)\s*:\s*(?P<sig>[A-Za-z_][\w\-]*)\b",
    re.IGNORECASE,
)
_STEP3_CHANGED_PAIR_RE = re.compile(
    r"^\s*(?P<msg>[A-Za-z_][\w\-]*)\s*:\s*(?P<sig>[A-Za-z_][\w\-]*)\b",
    re.IGNORECASE,
)


def _step3_validation_error_path(changed_signals_path: Path) -> Path:
    stem = changed_signals_path.stem
    suffix = "_변경된 시그널 모음"
    if stem.endswith(suffix):
        stem = stem[:-len(suffix)]
    return changed_signals_path.with_name(stem + "_Step3_결과검증_오류.txt")


def _read_pairs_from_detail_txt(path: Path) -> Set[Tuple[str, str]]:
    pairs: Set[Tuple[str, str]] = set()
    if not path.is_file():
        return pairs
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        m = _STEP3_DETAIL_PAIR_RE.match(raw.strip())
        if m:
            pairs.add((m.group("msg"), m.group("sig")))
    return pairs


def _read_pairs_from_changed_txt(path: Path) -> Set[Tuple[str, str]]:
    pairs: Set[Tuple[str, str]] = set()
    if not path.is_file():
        return pairs
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _STEP3_CHANGED_PAIR_RE.match(line)
        if m:
            pairs.add((m.group("msg"), m.group("sig")))
    return pairs


def validate_step3_outputs_non_blocking(
    grouped_path: Path,
    timeorder_path: Path,
    changed_signals_path: Path,
) -> None:
    """
    세 Step 3 결과를 작성한 뒤 읽기 전용으로 검증한다.

    중요:
    - 기존 세 TXT를 수정하지 않는다.
    - 불일치가 있어도 Step 3 성공/실패 반환값을 바꾸지 않는다.
    - 오류가 있을 때만 별도 검증 오류 TXT를 생성한다.
    """
    error_path = _step3_validation_error_path(changed_signals_path)
    problems: List[str] = []
    try:
        for label, path in (
            ("그룹형 상세 TXT", grouped_path),
            ("시간순 상세 TXT", timeorder_path),
            ("변경된 시그널 모음 TXT", changed_signals_path),
        ):
            if not path.is_file():
                problems.append(f"{label} 누락: {path.name}")

        grouped_pairs = _read_pairs_from_detail_txt(grouped_path)
        timeorder_pairs = _read_pairs_from_detail_txt(timeorder_path)
        changed_pairs = _read_pairs_from_changed_txt(changed_signals_path)

        missing_in_changed = sorted(grouped_pairs - changed_pairs)
        if missing_in_changed:
            problems.append(
                "그룹형 상세에는 있으나 변경된 시그널 모음에 없는 Message:Signal: "
                + ", ".join(f"{msg}:{sig}" for msg, sig in missing_in_changed)
            )

        missing_in_details = sorted(changed_pairs - (grouped_pairs | timeorder_pairs))
        if missing_in_details:
            problems.append(
                "변경된 시그널 모음에는 있으나 그룹형/시간순 상세 모두에 없는 Message:Signal: "
                + ", ".join(f"{msg}:{sig}" for msg, sig in missing_in_details)
            )
    except Exception as exc:
        problems.append(f"Step 3 결과 일치성 검증 자체에서 예외 발생: {exc}")

    try:
        if problems:
            error_path.write_text(
                "[Step 3 결과 검증 오류]\n"
                "Step 3의 기존 3개 결과 파일은 수정하지 않았으며, 파이프라인 실행에도 영향을 주지 않습니다.\n\n"
                + "\n".join(f"- {item}" for item in problems)
                + "\n",
                encoding="utf-8-sig",
            )
            print(f"[WARN] Step 3 결과 검증 오류 파일 생성(비간섭): {error_path.name}")
        elif error_path.exists():
            error_path.unlink()
            print(f"[OK] 이전 Step 3 결과 검증 오류 파일 삭제: {error_path.name}")
    except Exception as exc:
        # 검증 로그 파일 쓰기 실패도 본 Step 3 결과에는 영향을 주지 않는다.
        print(f"[WARN] Step 3 결과 검증 로그 처리 실패(비간섭): {exc}")


def analyze_single_asc(
    asc_path: str,
    base_dir: Path,
    output_dir: Path,
    group_spec: GroupSpec,
    dbc_name_by_ch,
    drop_first_seconds: float,
    ignore_name_patterns: List[str],
    change_threshold: int,
    output_prefix: str,
    domain_keywords: List[str],
    skip_high_frequency: bool,
    threshold_except_substrings: List[str],
    output_grouped_txt: bool,
    output_timeorder_txt: bool,
    asc_frame_direction="auto",
    dbc_cache: Optional[Step3DbcCache] = None,
):
    asc_file = Path(asc_path)

    raw_key = extract_test_key_from_asc_stem(asc_file.stem, keywords=domain_keywords)
    test_key = _format_test_key(raw_key)

    output_filename = make_output_txt_name_from_key(test_key, prefix=output_prefix)
    output_path = str(output_dir / output_filename)

    timeorder_filename = make_output_txt_name_timeorder_from_key(test_key, prefix=output_prefix)
    timeorder_path = str(output_dir / timeorder_filename)

    changed_signals_filename = make_output_txt_name_changed_signals_from_key(test_key, prefix=output_prefix)
    changed_signals_path = str(output_dir / changed_signals_filename)

    try:
        if dbc_cache is None:
            # 단독/외부 호출 호환: 캐시가 전달되지 않으면 기존처럼 내부에서 준비한다.
            dbc_cache = build_step3_dbc_cache(base_dir, dbc_name_by_ch, group_spec)

        msgs_by_ch_id = dbc_cache.msgs_by_ch_id
        msgs_all_by_id = dbc_cache.msgs_all_by_id
    except Exception as e:
        reason = f"DBC 준비 실패: {e}"
        print(f"[ERROR] {reason}")
        return False, reason

    try:
        dir_counts, dir_ch_counts = count_frame_directions_after_drop(asc_path, drop_first_seconds)
        selected_directions, auto_reason = resolve_effective_asc_frame_directions(asc_frame_direction, dir_counts)
        print_direction_diagnosis(
            asc_file.name,
            drop_first_seconds,
            selected_directions,
            dir_counts,
            dir_ch_counts,
            raw_option=asc_frame_direction,
            auto_reason=auto_reason,
        )

        _precheck_missing_ids_in_log(asc_path, msgs_by_ch_id, drop_first_seconds, frame_directions=selected_directions)
        ps = get_asc_parse_stats(asc_path)
        ps.dump(asc_file.name)

        first_seen: Dict[Tuple[int, str, str], Tuple[float, float]] = {}
        last: Dict[Tuple[int, str, str], float] = {}
        changes_after_drop: Dict[Tuple[int, str, str], List[Tuple[float, float, float]]] = {}
        had_any_change_after_drop: Set[Tuple[int, str, str]] = set()

        seen_before_drop: Set[Tuple[int, str, str]] = set()

        time_events: List[Tuple[float, int, str, str, str, Optional[float], float]] = []
        stats = AnalyzeStats()

        for t, ch, _direction, can_id, data in read_frames_from_asc(asc_path, frame_directions=selected_directions):
            cand_msgs = msgs_by_ch_id.get(ch, {}).get(can_id)
            cand_msg_pairs: List[Tuple[int, object]] = []

            if cand_msgs:
                cand_msg_pairs.extend((ch, m) for m in cand_msgs)

            if not cand_msg_pairs:
                cand_msg_pairs.extend(msgs_all_by_id.get(can_id, []))

            if not cand_msg_pairs:
                continue

            cand_msg_pairs.sort(key=lambda x: (0 if x[0] == ch else 1))

            decoded = None
            used_msg = None

            for _dbc_ch, m in cand_msg_pairs:
                try:
                    decoded = m.decode(data, decode_choices=False)
                    used_msg = m
                    break
                except Exception:
                    continue

            if decoded is None or used_msg is None:
                continue

            msg_name = used_msg.name

            for sig, val in decoded.items():
                if group_spec.target_signal_pairs:
                    if (msg_name, sig) not in group_spec.target_signal_pairs:
                        continue

                sig_lower = sig.lower()
                if any(re.search(pat, sig_lower) for pat in ignore_name_patterns):
                    continue

                if isinstance(val, bool):
                    num_val = int(val)
                elif isinstance(val, int):
                    num_val = int(val)
                elif isinstance(val, float):
                    num_val = float(val)
                else:
                    continue

                key = (ch, msg_name, sig)

                if t < drop_first_seconds:
                    seen_before_drop.add(key)
                    continue

                stats.frames_after_drop += 1
                stats.target_id_frames += 1
                stats.decode_success += 1
                stats.signal_rows_seen += 1

                if key not in first_seen:
                    first_seen[key] = (t, num_val)

                if key not in last:
                    last[key] = num_val
                    continue

                prev = last[key]
                if num_val != prev:
                    last[key] = num_val
                    changes_after_drop.setdefault(key, []).append((t, prev, num_val))
                    had_any_change_after_drop.add(key)
                    stats.signal_changes_found += 1

        init_only_new_after_drop_keys: Set[Tuple[int, str, str]] = set()
        for key in first_seen.keys():
            if key in had_any_change_after_drop:
                continue
            if key in seen_before_drop:
                continue
            init_only_new_after_drop_keys.add(key)

        skipped_set: Set[Tuple[int, str, str]] = set()

        changed_label = "(1회이상 값 변경)"
        init_label = f"({drop_first_seconds}초 이후 값 변경 없음)"

        changed_status_by_msg_sig: Dict[Tuple[str, str], bool] = {}
        init_only_new_after_drop_pairs: Set[Tuple[str, str]] = set()

        for (ch, msg_name, sig), (_t0, _v0) in first_seen.items():
            is_changed = (ch, msg_name, sig) in had_any_change_after_drop

            if is_changed:
                seq = changes_after_drop.get((ch, msg_name, sig), [])
                if should_skip_by_threshold(
                    sig_name=sig,
                    change_count=len(seq),
                    threshold=change_threshold,
                    skip_high_frequency=skip_high_frequency,
                    threshold_except_substrings=threshold_except_substrings,
                ):
                    continue

                changed_status_by_msg_sig[(msg_name, sig)] = True
                continue

            if (ch, msg_name, sig) in seen_before_drop:
                continue

            init_only_new_after_drop_pairs.add((msg_name, sig))

        out_items: List[Tuple[str, str, str]] = []

        for (msg_name, sig) in changed_status_by_msg_sig.keys():
            out_items.append((msg_name, sig, "changed"))

        for (msg_name, sig) in init_only_new_after_drop_pairs:
            if (msg_name, sig) in changed_status_by_msg_sig:
                continue
            out_items.append((msg_name, sig, "init_not_changed"))

        out_items.sort(key=lambda x: (x[0], x[1], x[2]))

        with open(changed_signals_path, "w", encoding="utf-8") as out:
            print(f"#*{drop_first_seconds}초 이후에 변경이 있는 시그널은 {changed_label}으로 표기", file=out)
            print(
                f"#*{drop_first_seconds}초 이후에 신규로 발생했으나 값이 바뀌지 않는 시그널은 {init_label}으로 표기",
                file=out
            )

            for msg_name, sig, kind in out_items:
                if kind == "changed":
                    print(f"{msg_name} : {sig} {changed_label}", file=out)
                else:
                    print(f"{msg_name} : {sig} {init_label}", file=out)

        print(f"[OK] saved: {changed_signals_path}")

        if output_timeorder_txt:
            for key in had_any_change_after_drop:
                if key in first_seen:
                    ch, msg_name, sig = key
                    t0, v0 = first_seen[key]
                    time_events.append((t0, ch, msg_name, sig, "INIT", None, v0))

            for key in init_only_new_after_drop_keys:
                ch, msg_name, sig = key
                t0, v0 = first_seen[key]
                time_events.append((t0, ch, msg_name, sig, "INIT_ONLY_NEW", None, v0))

            for key, seq in changes_after_drop.items():
                ch, msg_name, sig = key

                if should_skip_by_threshold(
                    sig_name=sig,
                    change_count=len(seq),
                    threshold=change_threshold,
                    skip_high_frequency=skip_high_frequency,
                    threshold_except_substrings=threshold_except_substrings,
                ):
                    skipped_set.add((ch, msg_name, sig))
                    continue

                for tt, prev, new in seq:
                    time_events.append((tt, ch, msg_name, sig, "CHANGE", prev, new))

            if skipped_set:
                time_events = [e for e in time_events if (e[1], e[2], e[3]) not in skipped_set]

        if output_grouped_txt:
            with open(output_path, "w", encoding="utf-8") as out:
                for key in sorted(changes_after_drop.keys(), key=lambda x: (x[0], x[1], x[2])):
                    ch, msg_name, sig = key
                    seq = changes_after_drop[key]

                    if should_skip_by_threshold(
                        sig_name=sig,
                        change_count=len(seq),
                        threshold=change_threshold,
                        skip_high_frequency=skip_high_frequency,
                        threshold_except_substrings=threshold_except_substrings,
                    ):
                        skipped_set.add((ch, msg_name, sig))
                        continue

                    if key in first_seen:
                        t0, v0 = first_seen[key]
                        if isinstance(v0, float):
                            print(f"{t0:.4f}sec CH{ch} {msg_name} : {sig} {v0}", file=out)
                        else:
                            print(f"{t0:.4f}sec CH{ch} {msg_name} : {sig} 0x{int(v0):02X}", file=out)

                    for tt, prev, new in seq:
                        if isinstance(prev, float) or isinstance(new, float):
                            print(f"{tt:.4f}sec CH{ch} {msg_name} : {sig} {prev} → {new}", file=out)
                        else:
                            print(
                                f"{tt:.4f}sec CH{ch} {msg_name} : {sig} 0x{int(prev):02X} → 0x{int(new):02X}",
                                file=out
                            )

                for key in sorted(init_only_new_after_drop_keys, key=lambda x: (x[0], x[1], x[2])):
                    ch, msg_name, sig = key

                    if (ch, msg_name, sig) in skipped_set:
                        continue

                    t0, v0 = first_seen[key]
                    if isinstance(v0, float):
                        print(f"{t0:.4f}sec CH{ch} {msg_name} : {sig} {v0}", file=out)
                    else:
                        print(f"{t0:.4f}sec CH{ch} {msg_name} : {sig} 0x{int(v0):02X}", file=out)

            print(f"[OK] saved: {output_path}")

        if output_timeorder_txt:
            kind_order = {"INIT": 0, "INIT_ONLY_NEW": 0, "CHANGE": 1}
            time_events.sort(key=lambda e: (e[0], e[1], e[2], e[3], kind_order.get(e[4], 9)))

            with open(timeorder_path, "w", encoding="utf-8") as out:
                for tt, ch, msg_name, sig, kind, prev, new in time_events:
                    if kind in ("INIT", "INIT_ONLY_NEW"):
                        v0 = new
                        if isinstance(v0, float):
                            print(f"{tt:.4f}sec CH{ch} {msg_name} : {sig} {v0}", file=out)
                        else:
                            print(f"{tt:.4f}sec CH{ch} {msg_name} : {sig} 0x{int(v0):02X}", file=out)
                    else:
                        if isinstance(prev, float) or isinstance(new, float):
                            print(f"{tt:.4f}sec CH{ch} {msg_name} : {sig} {prev} → {new}", file=out)
                        else:
                            print(
                                f"{tt:.4f}sec CH{ch} {msg_name} : {sig} 0x{int(prev):02X} → 0x{int(new):02X}",
                                file=out
                            )

            print(f"[OK] saved: {timeorder_path}")

        # V2 REV 02: 기존 산출물 생성 완료 후 비간섭 검증만 수행한다.
        validate_step3_outputs_non_blocking(
            grouped_path=Path(output_path),
            timeorder_path=Path(timeorder_path),
            changed_signals_path=Path(changed_signals_path),
        )

        stats.dump(asc_file.name)
        return True, "성공"

    except Exception as e:
        reason = f"ASC 분석 중 예외 발생: {e}"
        print(f"[ERROR] {reason}")
        return False, reason


# =========================================================
# ASC 중복 제거
# =========================================================
def select_latest_asc_per_test(asc_files, domain_keywords):
    latest_by_key = {}
    all_by_key: Dict[str, List[Path]] = {}

    for asc_file in asc_files:
        raw_key = extract_test_key_from_asc_stem(asc_file.stem, keywords=domain_keywords)
        test_key = _format_test_key(raw_key)

        all_by_key.setdefault(test_key, []).append(asc_file)

        dt = extract_datetime_from_asc_stem(asc_file.stem)
        has_dt = dt is not None
        dt_for_sort = dt if dt is not None else datetime.min
        mtime = asc_file.stat().st_mtime

        candidate = (has_dt, dt_for_sort, mtime, asc_file)
        prev = latest_by_key.get(test_key)

        if prev is None:
            latest_by_key[test_key] = candidate
            continue

        if candidate[0] != prev[0]:
            if candidate[0] and not prev[0]:
                latest_by_key[test_key] = candidate
            continue

        if candidate[0] and prev[0]:
            if candidate[1] > prev[1]:
                latest_by_key[test_key] = candidate
            elif candidate[1] == prev[1] and candidate[2] > prev[2]:
                latest_by_key[test_key] = candidate
            continue

        if candidate[2] > prev[2]:
            latest_by_key[test_key] = candidate

    selected = [v[3] for v in latest_by_key.values()]
    selected.sort(key=lambda p: (_format_test_key(extract_test_key_from_asc_stem(p.stem, keywords=domain_keywords)), p.name))
    return selected, latest_by_key, all_by_key


def _write_duplicate_asc_report(
    output_dir: Path,
    output_prefix: str,
    latest_by_key: Dict[str, Tuple[bool, datetime, float, Path]],
    all_by_key: Dict[str, List[Path]],
):
    dup_keys = sorted([k for k, v in all_by_key.items() if len(v) >= 2])
    report_path = output_dir / "0. 중복된 asc 번호.txt"

    with open(report_path, "w", encoding="utf-8") as out:
        for key in dup_keys:
            chosen = latest_by_key[key][3]
            candidates = all_by_key[key]

            skipped = [p for p in candidates if p.resolve() != chosen.resolve()]
            skipped_sorted = sorted(skipped, key=lambda p: (p.name, p.stat().st_mtime))

            txt_name = make_output_txt_name_from_key(key, prefix=output_prefix)
            print(txt_name, file=out)
            print(f"(chosen: {chosen.name})", file=out)
            if skipped_sorted:
                skipped_names = ", ".join(p.name for p in skipped_sorted)
                print(f"(skipped: {skipped_names})", file=out)
            else:
                print("(skipped: -)", file=out)
            print("", file=out)

    print(f"[OK] saved: {report_path}")


# =========================================================
# step_3 케이스 출력 유틸
# =========================================================
def get_expected_output_paths_for_test_key(
    output_dir: Path,
    output_prefix: str,
    test_key: str,
) -> Dict[str, Path]:
    return {
        "grouped": output_dir / make_output_txt_name_from_key(test_key, prefix=output_prefix),
        "timeorder": output_dir / make_output_txt_name_timeorder_from_key(test_key, prefix=output_prefix),
        "changed_signals": output_dir / make_output_txt_name_changed_signals_from_key(test_key, prefix=output_prefix),
    }


def is_step3_case_incomplete(
    asc_path: Path,
    output_dir: Path,
    output_prefix: str,
    domain_keywords: List[str],
    output_grouped_txt: bool,
    output_timeorder_txt: bool,
) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    raw_key = extract_test_key_from_asc_stem(asc_path.stem, keywords=domain_keywords)
    test_key = _format_test_key(raw_key)
    expected = get_expected_output_paths_for_test_key(output_dir, output_prefix, test_key)

    if has_error_log_for_asc(asc_path):
        reasons.append(f".error 존재: {asc_path.name}")

    if not expected["changed_signals"].exists():
        reasons.append(f"변경된 시그널 모음 누락: {expected['changed_signals'].name}")

    if output_grouped_txt and not expected["grouped"].exists():
        reasons.append(f"grouped txt 누락: {expected['grouped'].name}")

    if output_timeorder_txt and not expected["timeorder"].exists():
        reasons.append(f"timeorder txt 누락: {expected['timeorder'].name}")

    return (len(reasons) > 0), reasons


def cleanup_step3_case_outputs(
    asc_path: Path,
    output_dir: Path,
    output_prefix: str,
    domain_keywords: List[str],
) -> None:
    raw_key = extract_test_key_from_asc_stem(asc_path.stem, keywords=domain_keywords)
    test_key = _format_test_key(raw_key)
    expected = get_expected_output_paths_for_test_key(output_dir, output_prefix, test_key)

    for _kind, p in expected.items():
        try:
            if p.exists():
                p.unlink()
                print(f"[RETRY] 기존 step_3 출력 삭제: {p.name}")

        except Exception as e:
            print(f"[WARN] 기존 step_3 출력 삭제 실패: {p} ({e})")


# =========================================================
# 실행부
# =========================================================
def run(config) -> None:
    base_dir = Path(config.base_dir)
    active_category = config.active_category
    domain_prefix = config.category_prefix
    domain_keywords = list(config.category_keywords)

    dbc_name_by_ch = dict(config.dbc_name_by_ch)
    drop_first_seconds = float(config.drop_first_seconds)
    asc_frame_direction = getattr(config, "asc_frame_direction", "auto")
    ignore_name_patterns = list(config.ignore_name_patterns)
    change_threshold = int(config.change_threshold)

    threshold_except_substrings = list(config.threshold_except_substrings)
    skip_high_frequency = bool(config.skip_high_frequency)
    enable_info_only_ignore = bool(config.enable_info_only_ignore)
    info_only_ignore_patterns = list(config.info_only_ignore_patterns)
    category_extra_ignore_patterns = dict(config.category_extra_ignore_patterns)
    # V2 고정 정책: 세 가지 Step 3 산출물은 항상 생성한다.
    output_grouped_txt = True
    output_timeorder_txt = True

    output_dir = ensure_output_dir(base_dir)
    print(f"[OK] Output directory: {output_dir}")

    asc_files = collect_asc_files(base_dir)
    if not asc_files:
        print(f"[ERROR] .asc 파일을 못 찾음: {base_dir} (및 log파일 폴더)")
        return
    print(f"[OK] Found {len(asc_files)} ASC files (merged)")

    dbc_files = sorted(base_dir.glob("*.dbc"))
    if not dbc_files:
        print("[ERROR] 같은 폴더에서 .dbc 파일을 못 찾음")
        return
    print(f"[OK] Found {len(dbc_files)} DBC files")

    group_spec = load_latest_message_group(base_dir)
    if group_spec is None:
        return

    if not group_spec.target_messages:
        print("[ERROR] message_group 파일이 비어있거나 읽기 실패")
        return

    print(f"[INFO] ACTIVE_CATEGORY = {active_category}")
    print(f"[INFO] CATEGORY_PREFIX = {domain_prefix}")
    print(f"[INFO] CATEGORY_KEYWORDS = {domain_keywords}")
    print(f"[INFO] ASC_FRAME_DIRECTION = {format_asc_frame_direction_setting(asc_frame_direction)}")
    print(f"[OK] message_group selected: {group_spec.group_file.name}")
    print(f"[OK] target message count: {len(group_spec.target_messages)}")
    print(f"[OK] target signal pair count: {len(group_spec.target_signal_pairs)}")

    try:
        dbc_cache = build_step3_dbc_cache(
            base_dir=base_dir,
            dbc_name_by_ch=dbc_name_by_ch,
            group_spec=group_spec,
        )
    except Exception as e:
        print(f"[ERROR] step_3 DBC 캐시 준비 실패: {e}")
        return

    print("\n[DEBUG] test_key extraction result")
    for asc_file in asc_files:
        raw = extract_test_key_from_asc_stem(asc_file.stem, keywords=domain_keywords)
        key = _format_test_key(raw)
        dt = extract_datetime_from_asc_stem(asc_file.stem)
        print(f"  {asc_file.name}")
        print(f"    -> test_key(raw)=[{raw}]  normalized=[{key}]  datetime=[{dt}]")

    selected_asc_files, latest_by_key, all_by_key = select_latest_asc_per_test(
        asc_files,
        domain_keywords=domain_keywords
    )

    original_count = len(asc_files)
    selected_count = len(selected_asc_files)
    reduced_count = original_count - selected_count

    print(f"\n[CHECK] 전체 ASC 파일 수            : {original_count}개")
    print(f"[CHECK] 중복 제거 후 선택된 파일 수 : {selected_count}개")
    print(f"[CHECK] 중복 번호로 인해 줄어든 수  : {reduced_count}개")

    for key in sorted(latest_by_key.keys()):
        chosen = latest_by_key[key][3]
        print(f"  [SELECTED] {key} -> {chosen.name}")

    _write_duplicate_asc_report(
        output_dir=output_dir,
        output_prefix=domain_prefix,
        latest_by_key=latest_by_key,
        all_by_key=all_by_key,
    )

    if getattr(config, "retry_failed_only", False):
        retry_targets: List[Path] = []

        print(f"\n[INFO] 실패파일만 재실행 모드(step_3)")
        print(f"[INFO] 중복 제거 후 ASC 수: {len(selected_asc_files)}")

        for asc_file in selected_asc_files:
            incomplete, reasons = is_step3_case_incomplete(
                asc_path=asc_file,
                output_dir=output_dir,
                output_prefix=domain_prefix,
                domain_keywords=domain_keywords,
                output_grouped_txt=output_grouped_txt,
                output_timeorder_txt=output_timeorder_txt,
            )

            if not incomplete:
                continue

            print(f"[RETRY][CASE] 대상 선정: {asc_file.name}")
            for reason in reasons:
                print(f"  - {reason}")

            cleanup_step3_case_outputs(
                asc_path=asc_file,
                output_dir=output_dir,
                output_prefix=domain_prefix,
                domain_keywords=domain_keywords,
            )
            retry_targets.append(asc_file)

        selected_asc_files = retry_targets
        print(f"[INFO] 케이스 기준 재실행 대상 ASC 수: {len(selected_asc_files)}")

    effective_ignore_patterns = list(ignore_name_patterns)

    if enable_info_only_ignore:
        effective_ignore_patterns += info_only_ignore_patterns

    effective_ignore_patterns += category_extra_ignore_patterns.get(active_category, [])

    if not selected_asc_files:
        print("[INFO] step_3에서 재실행할 ASC 파일이 없습니다.")
        return

    for i, asc_file in enumerate(selected_asc_files, 1):
        print(f"\n[{i}/{len(selected_asc_files)}] Processing: {asc_file.name}")

        success, reason = analyze_single_asc(
            asc_path=str(asc_file),
            base_dir=base_dir,
            output_dir=output_dir,
            group_spec=group_spec,
            dbc_name_by_ch=dbc_name_by_ch,
            drop_first_seconds=drop_first_seconds,
            ignore_name_patterns=effective_ignore_patterns,
            change_threshold=change_threshold,
            output_prefix=domain_prefix,
            domain_keywords=domain_keywords,
            skip_high_frequency=skip_high_frequency,
            threshold_except_substrings=threshold_except_substrings,
            output_grouped_txt=output_grouped_txt,
            output_timeorder_txt=output_timeorder_txt,
            asc_frame_direction=asc_frame_direction,
            dbc_cache=dbc_cache,
        )

        if not success:
            write_error_log_for_asc(asc_file, reason=reason)
            print(f"[FAIL] {asc_file.name} processing failed. Skipping...")
            print(f"[FAIL] 에러로그 저장: {get_error_log_path_for_asc(asc_file)}")
            continue

        remove_error_log_for_asc_if_exists(asc_file)

    print("\n[OK] All ASC files processed!")



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
