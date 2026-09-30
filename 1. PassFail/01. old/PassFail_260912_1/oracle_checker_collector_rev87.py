# -*- coding: utf-8 -*-
"""
Oracle Checker rev87 - Optional CAPL Event Collector helper.

Purpose
-------
- Generate a CANoe/CANalyzer CAPL observer node from the currently loaded Oracle TC + DBC mapping.
- The CAPL node is read-only: it never calls output()/setSignal() and never changes vehicle signals.
- CAPL on signal_update handlers latch expected-value edges into a small in-CAPL FIFO.
- Python reads only five generic CAPL functions (COUNT/POP_ID/LAST_MS/OVERFLOW/SIGNATURE).
- If this module/file/CAPL node is absent, the existing COM polling + ASC/BLF fallback remains usable.

Operational boundary
--------------------
This module does not import the Pass/Fail GUI/core and does not decide PASS/FAIL. It only provides
observation evidence to the existing Python judge.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import hashlib
import json
import math
import re
import zlib

COLLECTOR_REV = 68
COLLECTOR_QUEUE_SIZE = 4096
COLLECTOR_CAPL_FUNCTIONS = (
    "PF_OBS_COUNT",
    "PF_OBS_POP_ID",
    "PF_OBS_LAST_MS",
    "PF_OBS_OVERFLOW",
    "PF_OBS_SIGNATURE",
    "PF_OBS_SET_ACTIVE",
)

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_HEX_RE = re.compile(r"^[+-]?0[xX][0-9a-fA-F]+$")
_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?$")


@dataclass(frozen=True)
class CollectorTarget:
    target_id: int
    channel: int
    logical_can: str
    message: str
    signal: str
    expected_raw: str
    expected_numeric: float
    key: str

    @property
    def capl_signal_ref(self) -> str:
        return f"{self.logical_can}::{self.message}::{self.signal}"


@dataclass
class CollectorCatalog:
    targets: List[CollectorTarget]
    signature_u32: int
    signature_hex: str
    skipped: List[str]
    dbc_paths: Dict[int, str]

    def by_id(self) -> Dict[int, CollectorTarget]:
        return {int(t.target_id): t for t in self.targets}

    def by_key(self) -> Dict[str, CollectorTarget]:
        return {t.key: t for t in self.targets}


def _numeric_expected(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        try:
            f = float(value)
            return f if math.isfinite(f) else None
        except Exception:
            return None
    s = str(value).strip().replace(" ", "")
    if not s:
        return None
    try:
        if _HEX_RE.match(s):
            return float(int(s, 16))
        if _INT_RE.match(s):
            return float(int(s, 10))
        if _FLOAT_RE.match(s):
            f = float(s)
            return f if math.isfinite(f) else None
    except Exception:
        return None
    return None


def _canonical_numeric(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return format(float(value), ".17g")


def target_key(channel: int, message: str, signal: str, expected_raw: Any) -> Optional[str]:
    num = _numeric_expected(expected_raw)
    if num is None:
        return None
    return f"CAN{int(channel)}|{str(message).strip()}|{str(signal).strip()}|{_canonical_numeric(num)}"


def _iter_conditions(items: Iterable[Any]) -> Iterable[Any]:
    for item in items or []:
        if item is None:
            continue
        cond = getattr(item, "condition", None)
        is_valid = getattr(item, "is_valid", None)
        if cond is not None:
            if is_valid is False:
                continue
            yield cond
        else:
            yield item


def _read_dbc_message_signals(path: str | Path) -> Dict[str, set[str]]:
    """Minimal read-only DBC symbol scan used only for Collector source generation.

    The normal PassFail core may use cantools for full decoding.  The optional Collector generator only
    needs to know whether Message/Signal symbols exist on each logical CAN, so it deliberately keeps a
    tiny text parser and does not add a new hard dependency.
    """
    p = Path(path)
    raw = p.read_bytes()
    text = None
    for enc in ("utf-8-sig", "cp949", "latin1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    if text is None:
        text = raw.decode("latin1", errors="replace")
    out: Dict[str, set[str]] = {}
    current_msg: Optional[str] = None
    bo_re = re.compile(r"^\s*BO_\s+\d+\s+([A-Za-z_][A-Za-z0-9_]*)\s*:")
    sg_re = re.compile(r"^\s*SG_\s+([A-Za-z_][A-Za-z0-9_]*)\b")
    for line in text.splitlines():
        m = bo_re.match(line)
        if m:
            current_msg = m.group(1)
            out.setdefault(current_msg, set())
            continue
        m = sg_re.match(line)
        if m and current_msg:
            out.setdefault(current_msg, set()).add(m.group(1))
    return out


def _load_dbc_map(dbc_path_by_channel: Dict[int, str | Path]):
    out: Dict[int, Dict[str, set[str]]] = {}
    for ch, raw_path in sorted((dbc_path_by_channel or {}).items()):
        p = Path(raw_path)
        if not p.is_file():
            continue
        try:
            out[int(ch)] = _read_dbc_message_signals(p)
        except Exception:
            continue
    return out


def build_catalog(
    conditions: Iterable[Any],
    dbc_path_by_channel: Dict[int, str | Path],
) -> CollectorCatalog:
    """Build a deterministic target catalog from all loaded valid conditions + DBC locations."""
    db_by_ch = _load_dbc_map(dbc_path_by_channel)
    skipped: List[str] = []
    keys: Dict[str, Tuple[int, str, str, str, float]] = {}

    for cond in _iter_conditions(conditions):
        expectations = list(getattr(cond, "input_conditions", []) or []) + list(getattr(cond, "output_conditions", []) or [])
        for exp in expectations:
            msg_name = str(getattr(exp, "message", "") or "").strip()
            sig_name = str(getattr(exp, "signal", "") or "").strip()
            exp_raw = str(getattr(exp, "expected_value_raw", "") or "").strip()
            exp_num = _numeric_expected(exp_raw)
            if not msg_name or not sig_name:
                continue
            if exp_num is None:
                skipped.append(f"비숫자 Expected: {msg_name}.{sig_name}={exp_raw}")
                continue
            if not (_IDENT_RE.match(msg_name) and _IDENT_RE.match(sig_name)):
                skipped.append(f"CAPL 식별자 제약: {msg_name}.{sig_name}")
                continue
            for ch, symbols in db_by_ch.items():
                logical_can = f"CAN{int(ch)}"
                if not _IDENT_RE.match(logical_can):
                    continue
                if msg_name not in symbols or sig_name not in symbols.get(msg_name, set()):
                    continue
                key = target_key(ch, msg_name, sig_name, exp_raw)
                if key is None:
                    continue
                keys[key] = (int(ch), msg_name, sig_name, exp_raw, float(exp_num))

    sorted_items = sorted(keys.items(), key=lambda kv: kv[0])
    targets: List[CollectorTarget] = []
    for idx, (key, (ch, msg, sig, exp_raw, exp_num)) in enumerate(sorted_items, start=1):
        targets.append(
            CollectorTarget(
                target_id=idx,
                channel=int(ch),
                logical_can=f"CAN{int(ch)}",
                message=msg,
                signal=sig,
                expected_raw=exp_raw,
                expected_numeric=float(exp_num),
                key=key,
            )
        )

    signature_payload = "\n".join(t.key for t in targets).encode("utf-8")
    signature_u32 = zlib.crc32(signature_payload) & 0xFFFFFFFF
    return CollectorCatalog(
        targets=targets,
        signature_u32=signature_u32,
        signature_hex=f"{signature_u32:08X}",
        skipped=skipped,
        dbc_paths={int(ch): str(Path(p)) for ch, p in (dbc_path_by_channel or {}).items()},
    )


def select_targets_for_conditions(
    catalog: CollectorCatalog,
    conditions: Iterable[Any],
    channels: Optional[Sequence[int]] = None,
) -> List[CollectorTarget]:
    allowed = {int(x) for x in channels} if channels is not None else None
    desired_keys = set()
    for cond in _iter_conditions(conditions):
        expectations = list(getattr(cond, "input_conditions", []) or []) + list(getattr(cond, "output_conditions", []) or [])
        for exp in expectations:
            msg = str(getattr(exp, "message", "") or "").strip()
            sig = str(getattr(exp, "signal", "") or "").strip()
            exp_raw = getattr(exp, "expected_value_raw", "")
            for ch in catalog.dbc_paths.keys():
                if allowed is not None and int(ch) not in allowed:
                    continue
                key = target_key(int(ch), msg, sig, exp_raw)
                if key:
                    desired_keys.add(key)
    by_key = catalog.by_key()
    return [by_key[k] for k in sorted(desired_keys) if k in by_key]


def _capl_float(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value)}.0"
    return format(float(value), ".17g")


def generate_capl_text(catalog: CollectorCatalog) -> str:
    targets = list(catalog.targets)
    max_id = max([t.target_id for t in targets], default=0)
    match_size = max(2, max_id + 1)
    lines: List[str] = []
    lines.extend([
        "/*@!Encoding:65001*/",
        "/*",
        "  Oracle Checker rev87 - OPTIONAL CAPL Event Collector",
        "  READ-ONLY observer: no output(), no setSignal(), no signal write.",
        "  Generated from current Oracle TC + CAN1~CAN3 DBC mapping.",
        f"  Catalog signature: 0x{catalog.signature_hex}",
        "  If this node is absent/old/uncompiled, Python falls back to rev87 COM polling + ASC/BLF review.",
        "*/",
        "",
        "variables",
        "{",
        f"  long gPFObsIds[{COLLECTOR_QUEUE_SIZE}];",
        f"  long gPFObsMs[{COLLECTOR_QUEUE_SIZE}];",
        f"  int  gPFObsMatch[{match_size}];",
        f"  int  gPFObsActive[{match_size}];",
        "  long gPFObsHead = 0;",
        "  long gPFObsTail = 0;",
        "  long gPFObsCount = 0;",
        "  long gPFObsOverflow = 0;",
        "  long gPFObsLastMs = 0;",
        "}",
        "",
        "void PF_OBS_PUSH(long targetId)",
        "{",
        "  long nowMs;",
        "  nowMs = timeNow() / 100; /* timeNow() uses 10 us units */",
        "  if (nowMs <= 0) nowMs = 1;",
        f"  if (gPFObsCount >= {COLLECTOR_QUEUE_SIZE})",
        "  {",
        "    gPFObsOverflow = gPFObsOverflow + 1;",
        "    return;",
        "  }",
        "  gPFObsIds[gPFObsTail] = targetId;",
        "  gPFObsMs[gPFObsTail] = nowMs;",
        f"  gPFObsTail = (gPFObsTail + 1) % {COLLECTOR_QUEUE_SIZE};",
        "  gPFObsCount = gPFObsCount + 1;",
        "}",
        "",
        "long PF_OBS_COUNT()",
        "{",
        "  return gPFObsCount;",
        "}",
        "",
        "long PF_OBS_POP_ID()",
        "{",
        "  long outId;",
        "  if (gPFObsCount <= 0)",
        "  {",
        "    gPFObsLastMs = 0;",
        "    return 0;",
        "  }",
        "  outId = gPFObsIds[gPFObsHead];",
        "  gPFObsLastMs = gPFObsMs[gPFObsHead];",
        f"  gPFObsHead = (gPFObsHead + 1) % {COLLECTOR_QUEUE_SIZE};",
        "  gPFObsCount = gPFObsCount - 1;",
        "  return outId;",
        "}",
        "",
        "long PF_OBS_LAST_MS()",
        "{",
        "  return gPFObsLastMs;",
        "}",
        "",
        "long PF_OBS_OVERFLOW()",
        "{",
        "  return gPFObsOverflow;",
        "}",
        "",
        "long PF_OBS_SIGNATURE()",
        "{",
        f"  return {int(catalog.signature_u32) if int(catalog.signature_u32) <= 0x7FFFFFFF else int(catalog.signature_u32) - 0x100000000};",
        "}",
        "",
        "long PF_OBS_SET_ACTIVE(long targetId, long active)",
        "{",
        f"  if ((targetId <= 0) || (targetId >= {match_size})) return 0;",
        "  gPFObsActive[targetId] = (active != 0);",
        "  gPFObsMatch[targetId] = 0;",
        "  return 1;",
        "}",
        "",
        "on start",
        "{",
        "  int i;",
        "  gPFObsHead = 0;",
        "  gPFObsTail = 0;",
        "  gPFObsCount = 0;",
        "  gPFObsOverflow = 0;",
        "  gPFObsLastMs = 0;",
        f"  for (i = 0; i < {match_size}; i++)",
        "  {",
        "    gPFObsMatch[i] = 0;",
        "    gPFObsActive[i] = 0;",
        "  }",
        "}",
        "",
    ])

    grouped: Dict[Tuple[int, str, str], List[CollectorTarget]] = {}
    for t in targets:
        grouped.setdefault((t.channel, t.message, t.signal), []).append(t)

    for (ch, msg, sig), group in sorted(grouped.items(), key=lambda x: x[0]):
        lines.append(f"on signal_update CAN{int(ch)}::{msg}::{sig}")
        lines.append("{")
        lines.append("  double v;")
        lines.append("  v = this;")
        for t in sorted(group, key=lambda x: x.target_id):
            e = _capl_float(t.expected_numeric)
            tol = "0.000000001"
            lines.append(f"  if (gPFObsActive[{t.target_id}] != 0)")
            lines.append("  {")
            lines.append(f"    if ((v >= ({e} - {tol})) && (v <= ({e} + {tol})))")
            lines.append("    {")
            lines.append(f"      if (gPFObsMatch[{t.target_id}] == 0) PF_OBS_PUSH({t.target_id});")
            lines.append(f"      gPFObsMatch[{t.target_id}] = 1;")
            lines.append("    }")
            lines.append("    else")
            lines.append("    {")
            lines.append(f"      gPFObsMatch[{t.target_id}] = 0;")
            lines.append("    }")
            lines.append("  }")
            lines.append("  else")
            lines.append("  {")
            lines.append(f"    gPFObsMatch[{t.target_id}] = 0;")
            lines.append("  }")
        lines.append("}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def generate_collector_files(
    conditions: Iterable[Any],
    dbc_path_by_channel: Dict[int, str | Path],
    capl_path: str | Path,
    manifest_path: Optional[str | Path] = None,
) -> CollectorCatalog:
    catalog = build_catalog(conditions, dbc_path_by_channel)
    capl_path = Path(capl_path)
    capl_path.parent.mkdir(parents=True, exist_ok=True)
    capl_path.write_text(generate_capl_text(catalog), encoding="utf-8")
    if manifest_path is None:
        manifest_path = capl_path.with_suffix(".manifest.json")
    manifest_path = Path(manifest_path)
    manifest = {
        "rev": COLLECTOR_REV,
        "signature_u32": catalog.signature_u32,
        "signature_hex": catalog.signature_hex,
        "target_count": len(catalog.targets),
        "dbc_paths": catalog.dbc_paths,
        "targets": [asdict(t) for t in catalog.targets],
        "skipped": list(catalog.skipped),
        "capl_functions": list(COLLECTOR_CAPL_FUNCTIONS),
        "read_only": True,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return catalog


def short_catalog_summary(catalog: CollectorCatalog) -> str:
    return (
        f"targets={len(catalog.targets)}, signature=0x{catalog.signature_hex}, "
        f"dbc={len(catalog.dbc_paths)}, skipped={len(catalog.skipped)}"
    )
