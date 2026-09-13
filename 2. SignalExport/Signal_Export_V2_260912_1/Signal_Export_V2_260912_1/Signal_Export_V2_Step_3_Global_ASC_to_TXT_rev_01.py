# -*- coding: utf-8 -*-
"""
Signal_Export_V2_Step_3_Global_ASC_to_TXT_rev_01.py

목적
- GLOBAL 특수 카테고리 전용 ASC 전체 디코딩 모듈
- message_group/TC/AI를 사용하지 않고, 선택된 DBC 전체를 대상으로 ASC의 모든 Message/Signal 변화를 추출
- drop_first_seconds는 GLOBAL 정책상 0초로 강제
- 출력 3종:
  1) Global_{ASC stem}_메세지별.txt
  2) Global_{ASC stem}_시간별.txt
  3) Global_{ASC stem}_변경된 시그널 모음.txt
- 대용량 결과는 _a, _b, _c ... suffix로 분할
- DBC 매칭 없음/디코딩 실패 Frame ID는 별도 진단 파일로 출력
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
import importlib.util
import re
import sys
import traceback

try:
    import cantools
except Exception:  # pragma: no cover
    cantools = None


@dataclass
class DecodeFailure:
    count: int = 0
    reason: str = ""
    channels: Set[int] = field(default_factory=set)


@dataclass
class SignalState:
    first_time: float
    first_value: object
    last_value: object
    changes: List[Tuple[float, object, object]] = field(default_factory=list)


# =========================================================
# Step 3 ASC 파서 재사용
# =========================================================
def _find_latest_rev_module_file(code_dir: Path, base_module: str) -> Path:
    rx = re.compile(rf"^{re.escape(base_module)}(?:[_\-.])rev(?:[_\-.])?(\d+)\.py$", re.IGNORECASE)
    best: Optional[Tuple[int, Path]] = None
    for path in code_dir.glob(f"{base_module}*.py"):
        m = rx.match(path.name)
        if not m:
            continue
        rev = int(m.group(1))
        if best is None or rev > best[0]:
            best = (rev, path)
    if best is None:
        raise FileNotFoundError(f"{base_module}_rev_xx.py 파일을 찾지 못했습니다: {code_dir}")
    return best[1]


def _load_step3_module():
    code_dir = Path(__file__).resolve().parent
    module_file = _find_latest_rev_module_file(code_dir, "Signal_Export_V2_Step_3_ASC_to_TXT")
    module_name = f"_global_reuse_{module_file.stem}".replace(".", "_").replace("-", "_")
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, str(module_file))
    if spec is None or spec.loader is None:
        raise ImportError(f"Step 3 모듈 spec 생성 실패: {module_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    print(f"[INFO] GLOBAL parser reuse: {module_file.name}")
    return module


# =========================================================
# 파일/폴더 유틸
# =========================================================
def _normalize_folder_name(s: str) -> str:
    return re.sub(r"[\s_\-]+", "", (s or "").strip().lower())


def find_log_dir_optional(base_dir: Path) -> Optional[Path]:
    targets = {
        _normalize_folder_name("log파일"),
        _normalize_folder_name("log file"),
        _normalize_folder_name("로그파일"),
        _normalize_folder_name("로그폴더"),
    }
    try:
        for p in base_dir.iterdir():
            if p.is_dir() and _normalize_folder_name(p.name) in targets:
                return p
    except Exception:
        pass
    return None


def collect_asc_files(base_dir: Path) -> List[Path]:
    candidates: List[Path] = []
    candidates += list(base_dir.glob("*.asc"))
    log_dir = find_log_dir_optional(base_dir)
    if log_dir:
        candidates += list(log_dir.glob("*.asc"))
        print(f"[OK] Log directory detected: {log_dir}")
    else:
        print("[WARN] Log directory not found. Using base_dir ASC files only.")

    # 같은 파일명이 base/log에 같이 있으면 최신 수정본만 사용
    best_by_name: Dict[str, Path] = {}
    for p in candidates:
        prev = best_by_name.get(p.name)
        if prev is None or p.stat().st_mtime > prev.stat().st_mtime:
            best_by_name[p.name] = p
    return sorted(best_by_name.values(), key=lambda p: p.name.lower())


def ensure_output_dir(base_dir: Path, config) -> Path:
    out_name = str(getattr(config, "global_output_dir_name", "분석된 txt 파일") or "분석된 txt 파일")
    out_dir = base_dir / out_name
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _safe_stem(stem: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]+', "_", str(stem or "global"))
    s = re.sub(r"\s+", "_", s).strip("_")
    return s or "global"


def _suffix(idx0: int) -> str:
    n = idx0
    s = ""
    while True:
        n, r = divmod(n, 26)
        s = chr(ord("a") + r) + s
        if n == 0:
            break
        n -= 1
    return s


def _cleanup_prior_split_outputs(base_path: Path) -> None:
    pattern = re.compile(rf"^{re.escape(base_path.stem)}(?:_[a-z]+)?{re.escape(base_path.suffix)}$", re.IGNORECASE)
    for p in base_path.parent.glob(base_path.stem + "*" + base_path.suffix):
        if pattern.match(p.name):
            try:
                p.unlink()
            except Exception:
                pass


def write_split_text(base_path: Path, lines: List[str], max_lines: int, max_chars: int) -> List[Path]:
    base_path.parent.mkdir(parents=True, exist_ok=True)
    _cleanup_prior_split_outputs(base_path)

    max_lines = max(1, int(max_lines or 100000))
    max_chars = max(1000, int(max_chars or 10_000_000))

    chunks: List[List[str]] = []
    cur: List[str] = []
    cur_chars = 0

    for line in lines:
        line_chars = len(line) + 1
        if cur and (len(cur) >= max_lines or cur_chars + line_chars > max_chars):
            chunks.append(cur)
            cur = []
            cur_chars = 0
        cur.append(line)
        cur_chars += line_chars
    if cur or not chunks:
        chunks.append(cur)

    written: List[Path] = []
    if len(chunks) == 1:
        base_path.write_text("\n".join(chunks[0]).rstrip() + "\n", encoding="utf-8-sig")
        written.append(base_path)
    else:
        for i, chunk in enumerate(chunks):
            out_path = base_path.with_name(f"{base_path.stem}_{_suffix(i)}{base_path.suffix}")
            out_path.write_text("\n".join(chunk).rstrip() + "\n", encoding="utf-8-sig")
            written.append(out_path)
    for p in written:
        print(f"[OK] saved: {p}")
    return written


# =========================================================
# DBC 준비
# =========================================================
def _resolve_dbc_path(base_dir: Path, name: object) -> Optional[Path]:
    text = str(name or "").strip()
    if not text or text.upper() == "N/A" or text.lower() in {"none", "null", "na"}:
        return None
    p = Path(text)
    if not p.is_absolute():
        p = base_dir / text
    return p if p.is_file() else None


def load_dbc_by_channel(base_dir: Path, dbc_name_by_ch: Dict[int, str]) -> Dict[int, object]:
    if cantools is None:
        raise ImportError("cantools 패키지가 설치되어 있지 않습니다. py -m pip install cantools 필요")

    out: Dict[int, object] = {}
    for raw_ch, dbc_name in sorted((dbc_name_by_ch or {}).items(), key=lambda x: int(x[0])):
        try:
            ch = int(raw_ch)
        except Exception:
            continue
        dbc_path = _resolve_dbc_path(base_dir, dbc_name)
        if dbc_path is None:
            print(f"[WARN] GLOBAL DBC 파일 없음: CH{ch} {dbc_name}")
            continue
        db = cantools.database.load_file(str(dbc_path))
        out[ch] = db
        print(f"[OK] GLOBAL DBC loaded: CH{ch} / {dbc_path.name} / messages={len(getattr(db, 'messages', []) or [])}")
    if not out:
        raise FileNotFoundError("GLOBAL 분석에 사용할 DBC가 없습니다. CAN별 채널/DBC를 최소 1개 이상 선택하세요.")
    return out


def build_message_index(db_by_ch: Dict[int, object]):
    by_ch_id: Dict[int, Dict[int, List[object]]] = {}
    all_by_id: Dict[int, List[Tuple[int, object]]] = {}
    for ch, db in db_by_ch.items():
        current: Dict[int, List[object]] = {}
        for msg in getattr(db, "messages", []) or []:
            fid = int(getattr(msg, "frame_id"))
            current.setdefault(fid, []).append(msg)
            all_by_id.setdefault(fid, []).append((ch, msg))
        by_ch_id[ch] = current
    return by_ch_id, all_by_id


# =========================================================
# 값/라인 유틸
# =========================================================
def _is_number_like(value) -> bool:
    return isinstance(value, (bool, int, float))


def _to_number(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    return value


def _format_value(value) -> str:
    if isinstance(value, bool):
        return f"0x{int(value):02X}"
    if isinstance(value, int):
        return f"0x{int(value):02X}"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _signal_ignored(sig_name: str, patterns: List[str]) -> bool:
    s = (sig_name or "").lower()
    for pat in patterns or []:
        try:
            if re.search(pat, s, flags=re.IGNORECASE):
                return True
        except re.error:
            if str(pat).lower() in s:
                return True
    return False


def _decode_frame(ch: int, can_id: int, data: bytes, by_ch_id, all_by_id):
    candidates: List[Tuple[int, object]] = []
    for msg in by_ch_id.get(ch, {}).get(can_id, []) or []:
        candidates.append((ch, msg))
    if not candidates:
        candidates.extend(all_by_id.get(can_id, []) or [])
    if not candidates:
        return None, None, "DBC 매칭 없음"

    candidates.sort(key=lambda x: (0 if x[0] == ch else 1, x[0]))
    last_error = ""
    for dbc_ch, msg in candidates:
        try:
            decoded = msg.decode(data, decode_choices=False)
            return msg, decoded, ""
        except Exception as exc:
            last_error = str(exc)[:160]
            continue
    return None, None, f"디코딩 실패: {last_error or 'candidate decode failed'}"


def _register_failure(failures: Dict[Tuple[int, int, str], DecodeFailure], ch: int, can_id: int, reason: str):
    key = (ch, can_id, reason)
    item = failures.setdefault(key, DecodeFailure(reason=reason))
    item.count += 1
    item.channels.add(ch)


# =========================================================
# ASC 분석
# =========================================================
def analyze_asc_file(asc_path: Path, config, step3, by_ch_id, all_by_id):
    ignore_patterns = list(getattr(config, "global_ignore_name_patterns", []) or [])
    max_lines = int(getattr(config, "global_split_max_lines", 100000) or 100000)
    max_chars = int(getattr(config, "global_split_max_chars", 10_000_000) or 10_000_000)
    output_dir = ensure_output_dir(Path(config.base_dir), config)

    drop_first_seconds = 0.0
    asc_frame_direction = getattr(config, "asc_frame_direction", "both") or "both"

    dir_counts, dir_ch_counts = step3.count_frame_directions_after_drop(str(asc_path), drop_first_seconds)
    selected_directions, auto_reason = step3.resolve_effective_asc_frame_directions(asc_frame_direction, dir_counts)
    step3.print_direction_diagnosis(
        asc_path.name,
        drop_first_seconds,
        selected_directions,
        dir_counts,
        dir_ch_counts,
        raw_option=asc_frame_direction,
        auto_reason=auto_reason,
    )

    states: Dict[Tuple[int, str, str], SignalState] = {}
    failures: Dict[Tuple[int, int, str], DecodeFailure] = {}
    frame_count = 0
    decoded_frame_count = 0
    decoded_signal_count = 0
    ignored_signal_count = 0

    for t, ch, _direction, can_id, data in step3.read_frames_from_asc(str(asc_path), frame_directions=selected_directions):
        frame_count += 1
        msg, decoded, reason = _decode_frame(ch, can_id, data, by_ch_id, all_by_id)
        if msg is None or decoded is None:
            _register_failure(failures, ch, can_id, reason or "디코딩 실패")
            continue
        decoded_frame_count += 1
        msg_name = str(getattr(msg, "name", ""))
        for sig_name, raw_val in decoded.items():
            if _signal_ignored(str(sig_name), ignore_patterns):
                ignored_signal_count += 1
                continue
            if not _is_number_like(raw_val):
                continue
            val = _to_number(raw_val)
            key = (ch, msg_name, str(sig_name))
            if key not in states:
                states[key] = SignalState(first_time=t, first_value=val, last_value=val)
                decoded_signal_count += 1
                continue
            st = states[key]
            if val != st.last_value:
                old = st.last_value
                st.last_value = val
                st.changes.append((t, old, val))
            decoded_signal_count += 1

    print(f"[GLOBAL] {asc_path.name}: frames={frame_count}, decoded_frames={decoded_frame_count}, signals={len(states)}, ignored_signals={ignored_signal_count}, failures={len(failures)}")

    case_id = _safe_stem(asc_path.stem)
    base = f"Global_{case_id}"
    grouped_path = output_dir / f"{base}_메세지별.txt"
    time_path = output_dir / f"{base}_시간별.txt"
    changed_path = output_dir / f"{base}_변경된 시그널 모음.txt"
    failure_path = output_dir / f"{base}_디코딩실패_FrameID.txt"

    grouped_lines: List[str] = []
    time_events: List[Tuple[float, int, str, str, str, object, object]] = []
    changed_by_msg_sig: Dict[Tuple[str, str], bool] = {}

    header = [
        f"# GLOBAL ASC 전체 분석 결과",
        f"# 원본 ASC: {asc_path.name}",
        f"# drop_first_seconds: 0.0",
        f"# frame_direction: {step3.format_asc_frame_directions(selected_directions)}",
        f"# CRC/ALV 제외: {bool(getattr(config, 'global_exclude_crc_alv', True))}",
        "",
    ]

    grouped_lines.extend(header)
    for (ch, msg_name, sig_name), st in sorted(states.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
        grouped_lines.append(f"{st.first_time:.4f}sec CH{ch} {msg_name} : {sig_name} {_format_value(st.first_value)}")
        time_events.append((st.first_time, ch, msg_name, sig_name, "INIT", None, st.first_value))
        changed_by_msg_sig[(msg_name, sig_name)] = changed_by_msg_sig.get((msg_name, sig_name), False) or bool(st.changes)
        for tt, old, new in st.changes:
            grouped_lines.append(f"{tt:.4f}sec CH{ch} {msg_name} : {sig_name} {_format_value(old)} → {_format_value(new)}")
            time_events.append((tt, ch, msg_name, sig_name, "CHANGE", old, new))

    time_lines = list(header)
    kind_order = {"INIT": 0, "CHANGE": 1}
    for tt, ch, msg_name, sig_name, kind, old, new in sorted(time_events, key=lambda x: (x[0], x[1], x[2], x[3], kind_order.get(x[4], 9))):
        if kind == "INIT":
            time_lines.append(f"{tt:.4f}sec CH{ch} {msg_name} : {sig_name} {_format_value(new)}")
        else:
            time_lines.append(f"{tt:.4f}sec CH{ch} {msg_name} : {sig_name} {_format_value(old)} → {_format_value(new)}")

    changed_lines = [
        "# GLOBAL 변경된 시그널 모음",
        f"# 원본 ASC: {asc_path.name}",
        "# 최초 등장 후 값이 변경된 시그널은 (최초 등장 후 값 변경 o)로 표기",
        "# 최초 등장 후 값이 변경되지 않은 시그널은 (최초 등장 후 값 변경 x)로 표기",
        "# ASC에 등장하지 않은 시그널은 출력하지 않음",
        "",
    ]
    for (msg_name, sig_name), changed in sorted(changed_by_msg_sig.items(), key=lambda x: (x[0][0], x[0][1])):
        label = "최초 등장 후 값 변경 o" if changed else "최초 등장 후 값 변경 x"
        changed_lines.append(f"{msg_name} : {sig_name} ({label})")

    failure_lines: List[str] = []
    if failures:
        failure_lines = [
            "# GLOBAL 디코딩 실패 Frame ID 요약",
            f"# 원본 ASC: {asc_path.name}",
            "# DBC 매칭 없음 또는 payload decode 실패 프레임을 Frame ID별로 집계",
            "",
        ]
        for (ch, can_id, reason), item in sorted(failures.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
            failure_lines.append(f"CH{ch} 0x{can_id:X} : {reason} / {item.count} frames")

    written = []
    written += write_split_text(grouped_path, grouped_lines, max_lines, max_chars)
    written += write_split_text(time_path, time_lines, max_lines, max_chars)
    written += write_split_text(changed_path, changed_lines, max_lines, max_chars)
    if failure_lines:
        written += write_split_text(failure_path, failure_lines, max_lines, max_chars)
    else:
        # 이전 실행에서 남아 있는 실패 파일 제거
        _cleanup_prior_split_outputs(failure_path)

    return written


# =========================================================
# 실행부
# =========================================================
def run(config) -> None:
    base_dir = Path(config.base_dir)
    step3 = _load_step3_module()

    print("[GLOBAL] 전용 ASC 전체 디코딩 시작")
    print("[GLOBAL] message_group/TC/AI 단계는 사용하지 않습니다.")
    print("[GLOBAL] drop_first_seconds = 0.0 강제")

    if getattr(config, "global_exclude_crc_alv", True):
        patterns = list(getattr(config, "global_ignore_name_patterns", []) or [r"crc", r"alv"])
        setattr(config, "global_ignore_name_patterns", patterns)
        print(f"[GLOBAL] CRC/ALV 제외 패턴: {patterns}")
    else:
        setattr(config, "global_ignore_name_patterns", [])
        print("[GLOBAL] CRC/ALV 제외 안 함")

    asc_files = collect_asc_files(base_dir)
    if not asc_files:
        print(f"[ERROR] GLOBAL 분석 대상 ASC 파일을 찾지 못했습니다: {base_dir}")
        return
    print(f"[OK] GLOBAL ASC files: {len(asc_files)}개")

    dbc_name_by_ch = dict(getattr(config, "dbc_name_by_ch", {}) or {})
    db_by_ch = load_dbc_by_channel(base_dir, dbc_name_by_ch)
    by_ch_id, all_by_id = build_message_index(db_by_ch)
    print(f"[OK] GLOBAL DBC index ready: channels={sorted(by_ch_id.keys())}, unique_frame_ids={len(all_by_id)}")

    all_written = []
    for idx, asc_path in enumerate(asc_files, 1):
        print("\n" + "-" * 80)
        print(f"[GLOBAL CASE {idx}/{len(asc_files)}] {asc_path.name}")
        print("-" * 80)
        try:
            all_written += analyze_asc_file(asc_path, config, step3, by_ch_id, all_by_id)
        except Exception as exc:
            print(f"[ERROR] GLOBAL ASC 분석 실패: {asc_path.name} / {exc}")
            traceback.print_exc()

    print("\n[GLOBAL] 출력 파일 수:", len(all_written))
    for p in all_written[:30]:
        print(f"  - {p.name}")
    if len(all_written) > 30:
        print(f"  ... (+{len(all_written)-30})")
