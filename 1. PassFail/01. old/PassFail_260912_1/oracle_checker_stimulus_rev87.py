# -*- coding: utf-8 -*-
"""
oracle_checker_stimulus_rev87.py

Oracle Checker experimental stimulus engine (isolated module).

rev87 backend policy
- CANoe: two explicit backends are supported.
  * CAPL Frame output() (recommended for actual bus injection; does not require a CANoe Interaction Layer signal driver).
  * Signal.Value legacy mode (requires an available CANoe signal driver/Interaction Layer; otherwise CANoe may log 01-0083 and no frame is transmitted).
- CANalyzer: CAPL Frame output() only.
- rev87 compact auto-P/F uses a fixed ACTIVE bridge path. The user performs a one-time CANoe Network Node association
  to PF_Stimulus_Bridge_CANx_ACTIVE.can; afterward PassFail overwrites the ACTIVE source, calls COM CAPL Compile for
  existing nodes, restarts Measurement, and binds generated CAPL functions automatically.
- PassFail still does not create/insert a CANoe Network Node or save/modify the Vector configuration automatically.
- CAPL bridge supports database-defined CAN/CAN FD messages up to 64 bytes. Payload bytes are transferred through
  chunk setter CAPL functions (8 bytes/call) followed by an output() send function.
- CRC/Alive/Counter/E2E are not calculated. Existing GUI preflight remains authoritative.
- All actual vehicle stimulus remains in this module. Existing Pass/Fail observer/judge modules stay read-only.
- rev87 records the intended baseline/active raw payload and cycle time in Stimulus results so post-log diagnostics can compare the requested frame with what the logger actually captured.
- rev87 optional in-worker observer callback lets TX/RX auto-P/F sample output signals while the active frame is held without creating a second COM thread.
- rev87 generic dominance boost: every CAPL stimulus frame is re-sent at one tenth of the DBC nominal cycle during Hold (minimum 10 ms). Example: 200 ms nominal -> 20 ms injection. This improves temporal dominance over an original sender that may remain active, but it does not suppress that sender and does not calculate CRC/Alive/E2E.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import datetime as _dt
import json
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import zlib


class StimulusError(RuntimeError):
    pass


class StimulusValidationError(StimulusError):
    pass


@dataclass(frozen=True)
class StimulusProfile:
    tc_no: str
    channel: int
    message: str
    signal: str
    active_value: Any
    hold_sec: float = 0.5
    bus_name: str = "CAN"
    source: str = "Oracle input condition"
    logical_can: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StimulusCandidate:
    logical_can: str
    channel: int
    message: str
    signal: str
    active_value: Any
    bus_name: str = "CAN"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StimulusGroupProfile:
    name: str
    candidates: List[StimulusCandidate]
    hold_sec: float = 0.5
    source: str = "Manual candidate set"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "candidates": [x.to_dict() for x in self.candidates],
            "hold_sec": self.hold_sec,
            "source": self.source,
        }


@dataclass
class StimulusExecutionResult:
    ok: bool
    started_at: str
    finished_at: str
    tc_no: str
    channel: int
    message: str
    signal: str
    original_value: Any = None
    active_value: Any = None
    active_readback: Any = None
    restored_value: Any = None
    restore_ok: bool = False
    stopped_early: bool = False
    error: str = ""
    trace_path: str = ""
    backend: str = ""
    frame_count: int = 0
    hold_sec: float = 0.0
    baseline_payload_hex: str = ""
    active_payload_hex: str = ""
    cycle_ms: float = 0.0
    tx_interval_ms: float = 0.0
    hold_mode: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StimulusCandidateResult:
    logical_can: str
    channel: int
    message: str
    signal: str
    original_value: Any = None
    active_value: Any = None
    active_readback: Any = None
    restored_value: Any = None
    write_ok: bool = False
    restore_ok: bool = False
    error: str = ""
    baseline_payload_hex: str = ""
    active_payload_hex: str = ""
    cycle_ms: float = 0.0
    tx_interval_ms: float = 0.0
    hold_mode: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StimulusGroupExecutionResult:
    ok: bool
    started_at: str
    finished_at: str
    name: str
    stopped_early: bool = False
    restore_ok: bool = False
    error: str = ""
    items: Optional[List[StimulusCandidateResult]] = None
    trace_path: str = ""
    backend: str = ""
    frame_count: int = 0
    hold_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["items"] = [x.to_dict() for x in (self.items or [])]
        return data


def coerce_numeric_value(value: Any) -> Any:
    """rev87 PoC accepts numeric signal values only."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    text = str(value if value is not None else "").strip()
    if not text:
        raise StimulusValidationError("입력 Active Value가 비어 있습니다.")
    compact = text.replace(" ", "")
    try:
        if compact.lower().startswith(("0x", "+0x", "-0x")):
            sign = -1 if compact.startswith("-") else 1
            raw = compact[3:] if compact[0] in "+-" else compact[2:]
            return sign * int(raw, 16)
        if re_full_int(compact):
            return int(compact, 10)
        f = float(compact)
        return int(f) if f.is_integer() else f
    except Exception as e:
        raise StimulusValidationError(
            f"rev87 입력 테스트는 숫자형 Active Value만 지원합니다: {text}"
        ) from e


def re_full_int(text: str) -> bool:
    if not text:
        return False
    if text[0] in "+-":
        return len(text) > 1 and text[1:].isdigit()
    return text.isdigit()


def _safe_capl_token(text: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]", "_", str(text or ""))
    if not token:
        token = "CAN"
    if token[0].isdigit():
        token = "_" + token
    return token[:24]


def vector_bridge_function_base(logical_can: str, channel: int, message: str) -> str:
    """Deterministic CAPL bridge base name shared by generator and runtime lookup."""
    raw = f"{str(logical_can or '').upper()}|{int(channel)}|{str(message)}".encode("utf-8", "replace")
    digest = zlib.crc32(raw) & 0xFFFFFFFF
    return f"PF_TX_{digest:08X}"


def canalyzer_bridge_function_name(logical_can: str, channel: int, message: str) -> str:
    """Backward-compatible rev64 function base name."""
    return vector_bridge_function_base(logical_can, channel, message)


def _infer_cycle_ms(message_obj: Any, message_name: str) -> int:
    try:
        value = int(getattr(message_obj, "cycle_time", 0) or 0)
        if value > 0:
            return max(20, min(value, 500))
    except Exception:
        pass
    m = re.search(r"(?:^|[_\-])(\d{1,5})\s*ms(?:$|[_\-])", str(message_name or ""), re.IGNORECASE)
    if m:
        try:
            return max(20, min(int(m.group(1)), 500))
        except Exception:
            pass
    return 100


def generate_vector_capl_bridges(
    profile: StimulusGroupProfile,
    dbc_resolver: Callable[[int, str], Any],
    output_dir: str | Path,
    revision: str = "rev87",
) -> List[str]:
    """Generate one CAPL frame-injection bridge source per logical CAN.

    The bridge uses a database-symbolic message object. Up to 64 payload bytes are filled using one or more
    setter functions (8 byte parameters per COM call), followed by a zero-argument SEND function which calls
    CAPL output(). rev87 can copy generated content into a fixed ACTIVE source and compile already-configured CAPL nodes,
    but it never creates/inserts Vector configuration nodes automatically.
    """
    items = list(profile.candidates or [])
    if not items:
        raise StimulusValidationError("CAPL Bridge를 생성할 후보 Signal이 없습니다.")
    grouped: Dict[str, Dict[Tuple[int, str], Any]] = {}
    logical_channels: Dict[str, set] = {}
    for item in items:
        logical = str(item.logical_can or f"CH{int(item.channel)}").strip().upper()
        logical_channels.setdefault(logical, set()).add(int(item.channel))
        msg = dbc_resolver(int(item.channel), str(item.message))
        if msg is None:
            raise StimulusValidationError(
                f"CAPL Bridge 생성용 DBC Message를 찾지 못했습니다: {logical}/CAN{item.channel} {item.message}"
            )
        length = int(getattr(msg, "length", 0) or 0)
        if length <= 0 or length > 64:
            raise StimulusValidationError(
                f"rev87 CAPL Bridge는 DBC payload 1~64 byte만 지원합니다: {item.message}, DLC/Length={length}"
            )
        signals = list(getattr(msg, "signals", []) or [])
        if any(bool(getattr(sig, "is_multiplexer", False)) or getattr(sig, "multiplexer_ids", None) for sig in signals):
            raise StimulusValidationError(
                f"rev87 CAPL Bridge는 multiplexed Message를 지원하지 않습니다: {item.message}"
            )
        grouped.setdefault(logical, {})[(int(item.channel), str(item.message))] = msg

    for logical, channels in logical_channels.items():
        if len(channels) != 1:
            raise StimulusValidationError(
                f"CAPL Bridge 생성 불가: 논리 CAN {logical}이 복수 CANoe 논리 채널 {sorted(channels)}에 매핑되어 있습니다. "
                "CAN/채널 매핑을 먼저 확정하세요."
            )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    for logical, messages in sorted(grouped.items()):
        logical_token = _safe_capl_token(logical)
        lines = [
            "/*@!Encoding:1252*/",
            f"/* Oracle Checker {revision} - Vector CAPL Stimulus Bridge */",
            f"/* Logical CAN: {logical} */",
            "/* Generated source. Compact auto-P/F may copy this content into PF_Stimulus_Bridge_CANx_ACTIVE.can. */",
            "/* ACTIVE workflow: associate the fixed ACTIVE file to a matching CANoe Network Node once. */",
            "/* PassFail compiles existing CAPL nodes but never creates/inserts/saves Vector configuration nodes. */",
            "",
            "variables",
            "{",
        ]
        definitions: List[Tuple[str, int, str, Any, str]] = []
        for idx, ((channel, message_name), msg) in enumerate(sorted(messages.items()), start=1):
            base = vector_bridge_function_base(logical, channel, message_name)
            var = f"pfMsg_{idx}_{base[-4:]}"
            lines.append(f"  message {message_name} {var};")
            definitions.append((base, channel, message_name, msg, var))
        lines += ["}", ""]

        for base, channel, message_name, msg, var in definitions:
            length = int(getattr(msg, "length", 0) or 0)
            chunks = (length + 7) // 8
            lines.append(f"/* CAN{channel} / {message_name} / DBC Length={length} */")
            for chunk in range(chunks):
                start_byte = chunk * 8
                params = ", ".join(f"long b{i}" for i in range(8))
                lines.append(f"void {base}_SET{chunk}({params})")
                lines.append("{")
                for offset in range(8):
                    byte_index = start_byte + offset
                    if byte_index < length:
                        lines.append(f"  {var}.byte({byte_index}) = (byte)b{offset};")
                lines.append("}")
                lines.append("")
            lines.append(f"void {base}_SEND()")
            lines.append("{")
            lines.append(f"  output({var});")
            lines.append("}")
            lines.append("")
            # Backward compatibility for rev64 Classic CAN bridge consumers.
            if length <= 8:
                params = ", ".join(f"long b{i}" for i in range(8))
                lines.append(f"void {base}({params})")
                lines.append("{")
                for i in range(length):
                    lines.append(f"  {var}.byte({i}) = (byte)b{i};")
                lines.append(f"  output({var});")
                lines.append("}")
                lines.append("")
        path = out_dir / f"PF_Stimulus_Bridge_{logical_token}_{revision}.can"
        path.write_text("\n".join(lines), encoding="cp1252", errors="replace")
        written.append(str(path))
    return written


def generate_canalyzer_capl_bridges(
    profile: StimulusGroupProfile,
    dbc_resolver: Callable[[int, str], Any],
    output_dir: str | Path,
    revision: str = "rev87",
) -> List[str]:
    """Backward-compatible alias; rev87 bridge can be used by CANoe and CANalyzer."""
    return generate_vector_capl_bridges(profile, dbc_resolver, output_dir, revision=revision)


def capl_function_names_for_group(
    profile: StimulusGroupProfile,
    dbc_resolver: Callable[[int, str], Any],
) -> List[str]:
    """Return exact rev87 bridge function names needed for a group without touching Vector COM."""
    if dbc_resolver is None:
        raise StimulusValidationError("CAPL 함수 목록 계산에는 DBC resolver가 필요합니다.")
    names: List[str] = []
    seen = set()
    for item in list(profile.candidates or []):
        key = (str(item.logical_can or f"CAN{int(item.channel)}").upper(), int(item.channel), str(item.message))
        if key in seen:
            continue
        seen.add(key)
        logical, channel, message = key
        msg = dbc_resolver(channel, message)
        if msg is None:
            raise StimulusValidationError(f"CAPL Bridge DBC Message를 찾지 못했습니다: {logical}/CAN{channel} {message}")
        length = int(getattr(msg, "length", 0) or 0)
        if length <= 0 or length > 64:
            raise StimulusValidationError(f"rev87 CAPL Bridge는 DBC payload 1~64 byte만 지원합니다: {message}, Length={length}")
        signals = list(getattr(msg, "signals", []) or [])
        if any(bool(getattr(sig, "is_multiplexer", False)) or getattr(sig, "multiplexer_ids", None) for sig in signals):
            raise StimulusValidationError(f"rev87 CAPL Bridge는 multiplexed Message를 지원하지 않습니다: {message}")
        base = vector_bridge_function_base(logical, channel, message)
        chunks = max(1, (length + 7) // 8)
        for chunk in range(chunks):
            names.append(f"{base}_SET{chunk}")
        names.append(f"{base}_SEND")
    return names


def capl_function_names_for_single(
    profile: StimulusProfile,
    dbc_resolver: Callable[[int, str], Any],
) -> List[str]:
    group = StimulusGroupProfile(
        name=f"{profile.tc_no or 'Selected TC'} single",
        candidates=[StimulusCandidate(
            logical_can=str(profile.logical_can or f"CAN{int(profile.channel)}"),
            channel=int(profile.channel), message=str(profile.message), signal=str(profile.signal),
            active_value=profile.active_value, bus_name=profile.bus_name,
        )],
        hold_sec=profile.hold_sec, source=profile.source,
    )
    return capl_function_names_for_group(group, dbc_resolver)


class StimulusExecutor:
    MIN_HOLD_SEC = 0.05
    MAX_HOLD_SEC = 5.0
    MAX_GROUP_ITEMS = 8

    def __init__(
        self,
        trace_dir: Optional[str | Path] = None,
        dbc_resolver: Optional[Callable[[int, str], Any]] = None,
        canoe_backend_mode: str = "capl",
        capl_function_registry: Optional[Dict[str, Any]] = None,
    ):
        self.trace_dir = Path(trace_dir) if trace_dir else None
        self.dbc_resolver = dbc_resolver
        self.capl_function_registry = dict(capl_function_registry or {})
        mode = str(canoe_backend_mode or "capl").strip().lower()
        self.canoe_backend_mode = "signal" if mode.startswith("signal") else "capl"

    def _product(self, client: Any) -> str:
        try:
            info = client.get_application_info() if hasattr(client, "get_application_info") else {}
        except Exception:
            info = {}
        return str((info or {}).get("product") or "").strip()

    def _backend(self, client: Any) -> str:
        product = self._product(client).lower()
        if product == "canoe":
            return "CANoe Signal.Value" if self.canoe_backend_mode == "signal" else "CANoe CAPL output()"
        if product == "canalyzer":
            return "CANalyzer CAPL output()"
        raise StimulusValidationError("연결된 Vector 제품을 CANoe/CANalyzer로 확인하지 못했습니다.")

    def _bus_candidates(self, client: Any, bus_name: str = "CAN") -> List[str]:
        names: List[str] = []
        try:
            for x in client._bus_name_candidates():
                if x and x not in names:
                    names.append(x)
        except Exception:
            pass
        for x in (bus_name, "CAN"):
            x = str(x or "").strip()
            if x and x not in names:
                names.append(x)
        return names or ["CAN"]

    def _get_signal_object_raw(
        self, client: Any, channel: int, message: str, signal: str, bus_name: str = "CAN"
    ) -> Tuple[Any, str]:
        app = getattr(client, "app", None)
        if app is None:
            raise StimulusValidationError("주입된 Vector client에 활성 app 객체가 없습니다.")
        last_error = None
        for candidate_bus in self._bus_candidates(client, bus_name):
            try:
                bus = app.GetBus(candidate_bus)
                sig = bus.GetSignal(int(channel), str(message), str(signal))
                _ = sig.Value
                return sig, candidate_bus
            except Exception as e:
                last_error = e
        raise StimulusValidationError(
            f"Vector Signal 객체 접근 실패: channel={channel}, message={message}, signal={signal}, 원인={last_error}"
        )

    def _get_signal_object(self, client: Any, profile: StimulusProfile) -> Tuple[Any, str]:
        return self._get_signal_object_raw(
            client, profile.channel, profile.message, profile.signal, profile.bus_name
        )

    def _validate_client_and_hold(self, client: Any, hold_sec: float) -> Tuple[float, str]:
        if client is None:
            raise StimulusValidationError("Vector client가 없습니다.")
        try:
            if not bool(client.is_connected()):
                raise StimulusValidationError("Vector CANoe/CANalyzer 연결이 없습니다.")
        except StimulusValidationError:
            raise
        except Exception as e:
            raise StimulusValidationError(f"Vector 연결 상태 확인 실패: {e}") from e

        product = self._product(client)
        if product.lower() not in ("canoe", "canalyzer"):
            raise StimulusValidationError("연결된 Vector 제품을 CANoe/CANalyzer로 확인하지 못했습니다.")
        try:
            if not bool(client.is_measurement_running()):
                raise StimulusValidationError(f"{product} Measurement가 실행 중이 아닙니다.")
        except StimulusValidationError:
            raise
        except Exception as e:
            raise StimulusValidationError(f"Measurement 상태 확인 실패: {e}") from e

        hold = float(hold_sec)
        if hold < self.MIN_HOLD_SEC or hold > self.MAX_HOLD_SEC:
            raise StimulusValidationError(
                f"Hold time은 {self.MIN_HOLD_SEC:.2f}~{self.MAX_HOLD_SEC:.1f}s 범위만 허용합니다."
            )
        return hold, product

    def _resolve_dbc_message(self, channel: int, message: str) -> Any:
        if self.dbc_resolver is None:
            raise StimulusValidationError(
                "CAPL Frame Stimulus에는 DBC Message 정보가 필요합니다. 설정 탭에서 해당 CAN의 DBC를 지정하세요."
            )
        try:
            msg = self.dbc_resolver(int(channel), str(message))
        except Exception as e:
            raise StimulusValidationError(f"DBC Message 조회 실패: CAN{channel}/{message}: {e}") from e
        if msg is None:
            raise StimulusValidationError(f"DBC에서 Message를 찾지 못했습니다: CAN{channel}/{message}")
        length = int(getattr(msg, "length", 0) or 0)
        if length <= 0 or length > 64:
            raise StimulusValidationError(
                f"rev87 CAPL Frame backend는 DBC payload 1~64 byte만 지원합니다: {message}, DLC/Length={length}"
            )
        signals = list(getattr(msg, "signals", []) or [])
        if any(bool(getattr(sig, "is_multiplexer", False)) or getattr(sig, "multiplexer_ids", None) for sig in signals):
            raise StimulusValidationError(
                f"rev87 CAPL Frame backend는 multiplexed Message를 지원하지 않습니다: {message}"
            )
        return msg

    def _read_message_values(self, client: Any, channel: int, msg: Any, bus_name: str) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        message_name = str(getattr(msg, "name", "") or "")
        if not message_name:
            raise StimulusValidationError("DBC Message 이름이 비어 있습니다.")
        for sig_def in list(getattr(msg, "signals", []) or []):
            sig_name = str(getattr(sig_def, "name", "") or "")
            if not sig_name:
                continue
            sig, _ = self._get_signal_object_raw(client, channel, message_name, sig_name, bus_name)
            value = sig.Value
            if value is None:
                raise StimulusValidationError(
                    f"CAPL Frame 재구성을 위한 현재 Signal 값을 읽지 못했습니다: {message_name}.{sig_name}"
                )
            values[sig_name] = value
        return values

    def _encode_payload(self, msg: Any, values: Dict[str, Any]) -> bytes:
        try:
            payload = msg.encode(values, scaling=True, strict=False)
        except TypeError:
            payload = msg.encode(values)
        except Exception as e:
            raise StimulusValidationError(
                f"DBC payload encode 실패({getattr(msg, 'name', '-')}). multiplex/choice/범위/DBC 정의를 확인하세요: {e}"
            ) from e
        payload = bytes(payload)
        length = int(getattr(msg, "length", len(payload)) or len(payload))
        if len(payload) != length:
            payload = payload[:length].ljust(length, b"\x00")
        return payload

    def _get_capl_bridge_functions(
        self, client: Any, logical_can: str, channel: int, message: str, payload_length: int
    ) -> Dict[str, Any]:
        """Use CAPLFunction objects captured by the worker during Measurement.OnInit."""
        base = vector_bridge_function_base(logical_can, channel, message)
        chunks = max(1, (int(payload_length) + 7) // 8)
        registry = self.capl_function_registry or {}
        setters = []
        missing = []
        for chunk in range(chunks):
            name = f"{base}_SET{chunk}"
            fn = registry.get(name)
            if fn is None:
                missing.append(name)
            else:
                setters.append(fn)
        send_name = f"{base}_SEND"
        send_func = registry.get(send_name)
        if send_func is None:
            missing.append(send_name)
        if missing:
            raise StimulusValidationError(
                "Measurement.OnInit CAPL function binding이 없습니다: " + ", ".join(missing[:12]) +
                ". rev87에서는 실제 테스트 worker가 Measurement를 재시작하면서 OnInit에서 GetFunction을 획득해야 합니다."
            )
        return {"mode": "chunk", "base": base, "setters": setters, "send": send_func}

    @staticmethod
    def _call_capl_send(frame: Dict[str, Any], payload: bytes) -> None:
        raw = bytes(payload)
        bridge = frame.get("bridge") or {}
        if bridge.get("mode") == "legacy":
            args = [int(x) for x in raw[:8].ljust(8, b"\x00")]
            bridge["legacy"].Call(*args)
            return
        setters = list(bridge.get("setters") or [])
        for chunk, func in enumerate(setters):
            part = raw[chunk * 8:(chunk + 1) * 8].ljust(8, b"\x00")
            func.Call(*[int(x) for x in part])
        send_func = bridge.get("send")
        if send_func is None:
            raise StimulusValidationError("CAPL Bridge SEND 함수가 없습니다.")
        send_func.Call()

    def _prepare_capl_frame(
        self,
        client: Any,
        logical_can: str,
        channel: int,
        message: str,
        overrides: Dict[str, Any],
        bus_name: str = "CAN",
    ) -> Dict[str, Any]:
        msg = self._resolve_dbc_message(channel, message)
        baseline_values = self._read_message_values(client, channel, msg, bus_name)
        active_values = dict(baseline_values)
        for sig_name, value in overrides.items():
            if sig_name not in baseline_values:
                raise StimulusValidationError(f"DBC/COM 기준 Signal이 없습니다: {message}.{sig_name}")
            active_values[sig_name] = coerce_numeric_value(value)
        baseline_payload = self._encode_payload(msg, baseline_values)
        active_payload = self._encode_payload(msg, active_values)
        bridge = self._get_capl_bridge_functions(client, logical_can, channel, message, len(active_payload))
        cycle_ms = _infer_cycle_ms(msg, message)
        # rev87: Generic temporal-dominance boost for every input stimulus.
        # A 200 ms source is injected every 20 ms, 100 ms -> 10 ms.
        # 10 ms is the lower bound to avoid an uncontrolled bus-load increase on fast messages.
        tx_interval_ms = max(10.0, float(cycle_ms) / 10.0)
        return {
            "logical_can": str(logical_can or f"CH{channel}").upper(),
            "channel": int(channel),
            "message": str(message),
            "message_obj": msg,
            "bridge": bridge,
            "func_name": bridge.get("base", ""),
            "baseline_values": baseline_values,
            "active_values": active_values,
            "baseline_payload": baseline_payload,
            "active_payload": active_payload,
            "cycle_ms": cycle_ms,
            "tx_interval_ms": tx_interval_ms,
            "hold_mode": "dbc_cycle_div10_dominance",
        }

    def validate(self, client: Any, profile: StimulusProfile) -> Dict[str, Any]:
        hold, product = self._validate_client_and_hold(client, profile.hold_sec)
        if int(profile.channel) <= 0:
            raise StimulusValidationError("유효한 CAN 채널이 아닙니다.")
        if not str(profile.message).strip() or not str(profile.signal).strip():
            raise StimulusValidationError("Message/Signal 이름이 비어 있습니다.")
        active = coerce_numeric_value(profile.active_value)

        use_capl = product.lower() == "canalyzer" or (product.lower() == "canoe" and self.canoe_backend_mode == "capl")
        if not use_capl:
            sig, bus_name = self._get_signal_object(client, profile)
            original = sig.Value
            if original is None:
                raise StimulusValidationError("실행 전 Signal 원래 값을 읽지 못해 안전한 원복 기준을 확보할 수 없습니다.")
            return {
                "backend": "CANoe Signal.Value (Interaction Layer driver 필요)",
                "backend_kind": "signal",
                "product": product,
                "bus_name": bus_name,
                "original_value": original,
                "active_value": active,
                "hold_sec": hold,
            }

        logical_can = str(profile.logical_can or f"CH{int(profile.channel)}").upper()
        frame = self._prepare_capl_frame(
            client, logical_can, int(profile.channel), str(profile.message),
            {str(profile.signal): active}, profile.bus_name,
        )
        return {
            "backend": f"{product} CAPL output()",
            "backend_kind": "capl",
            "product": product,
            "original_value": frame["baseline_values"].get(str(profile.signal)),
            "active_value": active,
            "hold_sec": hold,
            "frame": frame,
        }

    def validate_group(self, client: Any, profile: StimulusGroupProfile) -> Dict[str, Any]:
        hold, product = self._validate_client_and_hold(client, profile.hold_sec)
        items = list(profile.candidates or [])
        if not items:
            raise StimulusValidationError("수동 후보 Signal이 없습니다.")
        if len(items) > self.MAX_GROUP_ITEMS:
            raise StimulusValidationError(
                f"rev87 수동 후보 묶음은 최대 {self.MAX_GROUP_ITEMS}개 Signal만 허용합니다. 현재={len(items)}개"
            )

        seen = set()
        normalized: List[Dict[str, Any]] = []
        for idx, item in enumerate(items, start=1):
            channel = int(item.channel)
            message = str(item.message or "").strip()
            signal = str(item.signal or "").strip()
            logical_can = str(item.logical_can or f"CH{channel}").strip().upper()
            if channel <= 0:
                raise StimulusValidationError(f"{idx}행: 유효한 CAN 채널이 아닙니다.")
            if not message or not signal:
                raise StimulusValidationError(f"{idx}행: Message/Signal이 비어 있습니다.")
            key = (channel, message.lower(), signal.lower())
            if key in seen:
                raise StimulusValidationError(f"{idx}행: 동일 Signal이 중복 입력되었습니다: CAN{channel}/{message}/{signal}")
            seen.add(key)
            normalized.append({
                "logical_can": logical_can,
                "channel": channel,
                "message": message,
                "signal": signal,
                "active_value": coerce_numeric_value(item.active_value),
                "bus_name": item.bus_name,
            })

        use_capl = product.lower() == "canalyzer" or (product.lower() == "canoe" and self.canoe_backend_mode == "capl")
        if not use_capl:
            checked_items: List[Dict[str, Any]] = []
            for idx, item in enumerate(normalized, start=1):
                sig, bus_name = self._get_signal_object_raw(
                    client, item["channel"], item["message"], item["signal"], item["bus_name"]
                )
                original = sig.Value
                if original is None:
                    raise StimulusValidationError(
                        f"{idx}행: 시작 전 값을 읽지 못해 원복 기준을 확보할 수 없습니다: "
                        f"CAN{item['channel']}/{item['message']}/{item['signal']}"
                    )
                checked_items.append({**item, "original_value": original, "bus_name": bus_name})
            return {
                "backend": "CANoe Signal.Value (Interaction Layer driver 필요)",
                "backend_kind": "signal",
                "product": product,
                "hold_sec": hold,
                "items": checked_items,
            }

        groups: Dict[Tuple[str, int, str, str], Dict[str, Any]] = {}
        for item in normalized:
            key = (item["logical_can"], item["channel"], item["message"], item["bus_name"])
            groups.setdefault(key, {})[item["signal"]] = item["active_value"]
        frames: List[Dict[str, Any]] = []
        for (logical, channel, message, bus_name), overrides in groups.items():
            frames.append(self._prepare_capl_frame(client, logical, channel, message, overrides, bus_name))
        for item in normalized:
            frame = next(
                f for f in frames
                if f["logical_can"] == item["logical_can"] and f["channel"] == item["channel"] and f["message"] == item["message"]
            )
            item["original_value"] = frame["baseline_values"].get(item["signal"])
        return {
            "backend": f"{product} CAPL output()",
            "backend_kind": "capl",
            "product": product,
            "hold_sec": hold,
            "items": normalized,
            "frames": frames,
        }

    def _hold_capl_frames(
        self,
        frames: List[Dict[str, Any]],
        hold_sec: float,
        stop_event: Optional[threading.Event],
        observer_callback: Optional[Callable[[], None]] = None,
        observer_interval_sec: float = 0.04,
    ) -> Tuple[bool, int]:
        if not frames:
            return False, 0
        count = 0
        now = time.monotonic()
        next_due: List[float] = []
        intervals: List[float] = []
        for frame in frames:
            self._call_capl_send(frame, frame["active_payload"])
            count += 1
            requested_interval_ms = float(frame.get("tx_interval_ms", 0) or 0)
            if requested_interval_ms > 0:
                interval = max(0.01, min(0.5, requested_interval_ms / 1000.0))
            else:
                interval = max(0.02, min(0.5, float(frame.get("cycle_ms", 100)) / 1000.0))
            intervals.append(interval)
            next_due.append(now + interval)

        deadline = now + float(hold_sec)
        stopped = False
        observe_interval = max(0.02, float(observer_interval_sec or 0.04))
        next_observe = now
        while True:
            if stop_event is not None and stop_event.is_set():
                stopped = True
                break
            now = time.monotonic()
            if observer_callback is not None and now >= next_observe:
                observer_callback()
                while next_observe <= now:
                    next_observe += observe_interval
            if now >= deadline:
                break
            for idx, frame in enumerate(frames):
                if now >= next_due[idx]:
                    self._call_capl_send(frame, frame["active_payload"])
                    count += 1
                    while next_due[idx] <= now:
                        next_due[idx] += intervals[idx]
            wake_points = list(next_due) + [deadline]
            if observer_callback is not None:
                wake_points.append(next_observe)
            sleep_for = min(0.02, max(0.001, min(wake_points) - time.monotonic()))
            time.sleep(sleep_for)
        return stopped, count

    # Backward compatibility for external test code.
    _hold_canalyzer_frames = _hold_capl_frames

    def execute_once(
        self,
        client: Any,
        profile: StimulusProfile,
        stop_event: Optional[threading.Event] = None,
        observer_callback: Optional[Callable[[], None]] = None,
        observer_interval_sec: float = 0.04,
    ) -> StimulusExecutionResult:
        started = _dt.datetime.now()
        result = StimulusExecutionResult(
            ok=False,
            started_at=started.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            finished_at="",
            tc_no=str(profile.tc_no or ""),
            channel=int(profile.channel),
            message=str(profile.message),
            signal=str(profile.signal),
            active_value=profile.active_value,
            hold_sec=float(profile.hold_sec),
        )
        signal_obj = None
        original = None
        capl_frame = None
        try:
            checked = self.validate(client, profile)
            result.backend = checked.get("backend", "")
            result.original_value = checked.get("original_value")
            result.active_value = checked.get("active_value")
            original = checked.get("original_value")

            if checked.get("backend_kind") == "signal":
                signal_obj, _ = self._get_signal_object(client, profile)
                signal_obj.Value = result.active_value
                result.frame_count = 1
                try:
                    result.active_readback = signal_obj.Value
                except Exception:
                    result.active_readback = None
                deadline = time.monotonic() + float(checked["hold_sec"])
                next_observe = time.monotonic()
                observe_interval = max(0.02, float(observer_interval_sec or 0.04))
                while time.monotonic() < deadline:
                    if stop_event is not None and stop_event.is_set():
                        result.stopped_early = True
                        break
                    now_obs = time.monotonic()
                    if observer_callback is not None and now_obs >= next_observe:
                        observer_callback()
                        next_observe = now_obs + observe_interval
                    time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
            else:
                capl_frame = checked["frame"]
                result.baseline_payload_hex = bytes(capl_frame.get("baseline_payload") or b"").hex(" ").upper()
                result.active_payload_hex = bytes(capl_frame.get("active_payload") or b"").hex(" ").upper()
                result.cycle_ms = float(capl_frame.get("cycle_ms", 0) or 0)
                result.tx_interval_ms = float(capl_frame.get("tx_interval_ms", 0) or 0)
                result.hold_mode = str(capl_frame.get("hold_mode", "") or "")
                stopped, count = self._hold_capl_frames(
                    [capl_frame], checked["hold_sec"], stop_event,
                    observer_callback=observer_callback, observer_interval_sec=observer_interval_sec,
                )
                result.stopped_early = stopped
                result.frame_count += count
            result.ok = True
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"
            result.ok = False
        finally:
            if signal_obj is not None and original is not None:
                try:
                    signal_obj.Value = original
                    try:
                        result.restored_value = signal_obj.Value
                    except Exception:
                        result.restored_value = original
                    result.restore_ok = True
                except Exception as restore_error:
                    result.restore_ok = False
                    result.error = f"{result.error} / 원래 값 복원 실패: {type(restore_error).__name__}: {restore_error}".strip(" /")
                    result.ok = False
            elif capl_frame is not None:
                try:
                    self._call_capl_send(capl_frame, capl_frame["baseline_payload"])
                    result.frame_count += 1
                    result.restored_value = original
                    result.restore_ok = True
                except Exception as restore_error:
                    result.restore_ok = False
                    result.error = f"{result.error} / CAPL release Frame 송신 실패: {type(restore_error).__name__}: {restore_error}".strip(" /")
                    result.ok = False
            result.finished_at = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            result.trace_path = self._append_trace(profile.to_dict(), result.to_dict(), "single")
        return result

    def execute_group_once(
        self,
        client: Any,
        profile: StimulusGroupProfile,
        stop_event: Optional[threading.Event] = None,
        observer_callback: Optional[Callable[[], None]] = None,
        observer_interval_sec: float = 0.04,
    ) -> StimulusGroupExecutionResult:
        started = _dt.datetime.now()
        result = StimulusGroupExecutionResult(
            ok=False,
            started_at=started.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            finished_at="",
            name=str(profile.name or "Manual Candidate Set"),
            items=[],
            hold_sec=float(profile.hold_sec),
        )
        written: List[Tuple[Any, StimulusCandidateResult]] = []
        capl_frames: List[Dict[str, Any]] = []
        try:
            checked = self.validate_group(client, profile)
            result.backend = checked.get("backend", "")
            if checked.get("backend_kind") == "signal":
                prepared: List[Tuple[Any, StimulusCandidateResult]] = []
                for item in checked["items"]:
                    sig, _ = self._get_signal_object_raw(
                        client, item["channel"], item["message"], item["signal"], item.get("bus_name", "CAN")
                    )
                    original = sig.Value
                    if original is None:
                        raise StimulusValidationError(
                            f"실행 직전 원래 값 읽기 실패: CAN{item['channel']}/{item['message']}/{item['signal']}"
                        )
                    item_result = StimulusCandidateResult(
                        logical_can=item["logical_can"], channel=item["channel"], message=item["message"],
                        signal=item["signal"], original_value=original, active_value=item["active_value"],
                    )
                    result.items.append(item_result)
                    prepared.append((sig, item_result))
                for sig, item_result in prepared:
                    sig.Value = item_result.active_value
                    item_result.write_ok = True
                    written.append((sig, item_result))
                    try:
                        item_result.active_readback = sig.Value
                    except Exception:
                        item_result.active_readback = None
                result.frame_count = len(written)
                deadline = time.monotonic() + float(checked["hold_sec"])
                next_observe = time.monotonic()
                observe_interval = max(0.02, float(observer_interval_sec or 0.04))
                while time.monotonic() < deadline:
                    if stop_event is not None and stop_event.is_set():
                        result.stopped_early = True
                        break
                    now_obs = time.monotonic()
                    if observer_callback is not None and now_obs >= next_observe:
                        observer_callback()
                        next_observe = now_obs + observe_interval
                    time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
            else:
                capl_frames = list(checked.get("frames") or [])
                for item in checked["items"]:
                    frame = next(
                        (
                            f for f in capl_frames
                            if f["logical_can"] == item["logical_can"]
                            and f["channel"] == item["channel"]
                            and f["message"] == item["message"]
                        ),
                        None,
                    )
                    result.items.append(StimulusCandidateResult(
                        logical_can=item["logical_can"], channel=item["channel"], message=item["message"],
                        signal=item["signal"], original_value=item.get("original_value"), active_value=item["active_value"],
                        baseline_payload_hex=(
                            bytes(frame.get("baseline_payload") or b"").hex(" ").upper() if frame else ""
                        ),
                        active_payload_hex=(
                            bytes(frame.get("active_payload") or b"").hex(" ").upper() if frame else ""
                        ),
                        cycle_ms=float(frame.get("cycle_ms", 0) or 0) if frame else 0.0,
                        tx_interval_ms=float(frame.get("tx_interval_ms", 0) or 0) if frame else 0.0,
                        hold_mode=str(frame.get("hold_mode", "") or "") if frame else "",
                    ))
                stopped, count = self._hold_capl_frames(
                    capl_frames, checked["hold_sec"], stop_event,
                    observer_callback=observer_callback, observer_interval_sec=observer_interval_sec,
                )
                result.stopped_early = stopped
                result.frame_count += count
                for item_result in result.items:
                    item_result.write_ok = True
            result.ok = True
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"
            result.ok = False
        finally:
            restore_errors: List[str] = []
            if written:
                for sig, item_result in reversed(written):
                    try:
                        sig.Value = item_result.original_value
                        try:
                            item_result.restored_value = sig.Value
                        except Exception:
                            item_result.restored_value = item_result.original_value
                        item_result.restore_ok = True
                    except Exception as restore_error:
                        item_result.restore_ok = False
                        item_result.error = f"{type(restore_error).__name__}: {restore_error}"
                        restore_errors.append(
                            f"CAN{item_result.channel}/{item_result.message}/{item_result.signal}: {item_result.error}"
                        )
            elif capl_frames:
                for frame in reversed(capl_frames):
                    try:
                        self._call_capl_send(frame, frame["baseline_payload"])
                        result.frame_count += 1
                    except Exception as restore_error:
                        restore_errors.append(
                            f"CAN{frame['channel']}/{frame['message']}: {type(restore_error).__name__}: {restore_error}"
                        )
                for item_result in result.items or []:
                    if not restore_errors:
                        item_result.restored_value = item_result.original_value
                        item_result.restore_ok = True
                    else:
                        item_result.restore_ok = False
            result.restore_ok = bool(result.items) and all(x.restore_ok for x in (result.items or []))
            if restore_errors:
                result.error = f"{result.error} / 원복 실패: {' | '.join(restore_errors)}".strip(" /")
                result.ok = False
            result.finished_at = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            result.trace_path = self._append_trace(profile.to_dict(), result.to_dict(), "group")
        return result

    def _append_trace(self, profile_data: Dict[str, Any], result_data: Dict[str, Any], mode: str) -> str:
        if self.trace_dir is None:
            return ""
        try:
            self.trace_dir.mkdir(parents=True, exist_ok=True)
            path = self.trace_dir / f"stimulus_execution_{_dt.datetime.now().strftime('%Y%m%d')}.jsonl"
            record = {"mode": mode, "profile": profile_data, "result": result_data}
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            return str(path)
        except Exception:
            return ""
