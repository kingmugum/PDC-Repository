from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

BASIC_FUNCTIONAL_MODE = "BASIC_FUNCTIONAL_SOURCE_BACKED"
NOT_CONFIRMED = "입력문서에서 확인되지 않음"


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_text(v) for v in value.values() if v not in (None, "", [], {}))
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text(v) for v in value if v not in (None, "", [], {}))
    return str(value).strip()


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", _text(value)).strip()


def _source_text(req: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("requirement", "activation_trigger", "preconditions", "processing_action", "output", "acceptance_criteria"):
        value = _text(req.get(key))
        if value:
            parts.append(value)
    for atom in _list(req.get("source_backed_atomic_behaviors")):
        if isinstance(atom, dict):
            value = _text(atom.get("behavior_text") or atom.get("source_fact"))
        else:
            value = _text(atom)
        if value:
            parts.append(value)
    for ev in _list(req.get("source_evidence")):
        if isinstance(ev, dict):
            value = _text(ev.get("text"))
        else:
            value = _text(ev)
        if value:
            parts.append(value)
    for fact in _list(req.get("source_table_fact_matches")):
        if isinstance(fact, dict):
            value = _text(fact.get("source_literal"))
            if value:
                parts.append(value)
    # Preserve newlines where Source evidence used them; they help enum parsing.
    return "\n".join(dict.fromkeys(x for x in parts if x))


def _fact_records(req: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for atom in _list(req.get("source_backed_atomic_behaviors")):
        if isinstance(atom, dict):
            text = _norm(atom.get("behavior_text") or atom.get("source_fact"))
            fid = str(atom.get("source_fact_fragment_id") or "")
            sem = str(atom.get("source_semantic_unit_id") or "")
            loc = _norm(atom.get("source_location"))
        else:
            text = _norm(atom); fid = sem = loc = ""
        if not text:
            continue
        key=(fid,text.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({"text":text,"fid":fid,"sem":sem,"location":loc})
    for alloc in _list(req.get("fact_level_allocations")):
        if not isinstance(alloc, dict):
            continue
        text=_norm(alloc.get("source_fact")); fid=str(alloc.get("source_fact_fragment_id") or "")
        if not text:
            continue
        key=(fid,text.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({"text":text,"fid":fid,"sem":str(alloc.get("source_semantic_unit_id") or ""),"location":_norm(alloc.get("source_location"))})
    return out


def _core_requirement_text(req: dict[str, Any]) -> str:
    parts=[]
    for key in ("requirement", "activation_trigger", "preconditions", "processing_action", "output", "acceptance_criteria"):
        v=_text(req.get(key))
        if v: parts.append(v)
    for rec in _fact_records(req):
        if rec.get("text"): parts.append(rec["text"])
    return "\n".join(dict.fromkeys(parts))


def _clean_variable(text: str) -> str:
    text = re.sub(r"^[\s,.;:()]+|[\s,.;:()]+$", "", text or "")
    text = re.sub(r"\b(?:HU|ECU|제어기|시스템)\s*(?:는|은)?\s*", "", text, flags=re.I)
    text = re.sub(r"(?:이|가|은|는)$", "", text).strip()
    return text[-42:].strip()


_VALUE = r"(?:0x[0-9A-Fa-f]+|[-+]?\d+(?:\.\d+)?\s*(?:mV|V|mA|A|ms|s|초|%|MB|KB|℃|°C)?|ON|OFF|HIGH|LOW|High|Low|True|False)"


def _parse_conditional_io(text: str) -> dict[str, str] | None:
    raw=_norm(text)
    if not raw:
        return None
    # Korean functional relation: "입력 전원이 12V가 되면 출력 전원이 5V가 되어야 한다"
    pat = re.compile(
        rf"(?P<ivar>[^,.;]{{2,48}}?)\s*(?P<ival>{_VALUE})\s*(?:가|이)?\s*(?:되면|이면|일\s*경우|일\s*때|때|시)\s*"
        rf"(?P<ovar>[^,.;]{{2,52}}?)\s*(?P<oval>{_VALUE})\s*(?:가|이)?\s*(?:되어야|돼야|되야|이어야|여야|된다|되어야\s*한다)",
        re.I,
    )
    m=pat.search(raw)
    if not m:
        return None
    ivar=_clean_variable(m.group("ivar")); ovar=_clean_variable(m.group("ovar"))
    if not ivar or not ovar:
        return None
    return {"input_variable":ivar,"input_compare":"=","input_value":m.group("ival").strip(),"output_variable":ovar,"output_compare":"=","output_value":m.group("oval").strip()}


def _signal_role(name: str) -> tuple[str, str]:
    raw=name or ""
    lower=raw.lower()
    suffixes = [
        ("request","request"),("req","request"),("command","request"),("cmd","request"),
        ("response","response"),("resp","response"),("status","response"),("state","response"),("stat","response"),
    ]
    for suffix, role in suffixes:
        if lower.endswith(suffix):
            return raw[:len(raw)-len(suffix)].rstrip("_"), role
    return raw, "unknown"


def _extract_signal_enum_blocks(source: str) -> dict[str, list[dict[str, str]]]:
    # Identify only explicit SignalName + "값" blocks to avoid treating arbitrary hex prose as an enum table.
    names = list(dict.fromkeys(re.findall(r"\b([A-Za-z][A-Za-z0-9_]{3,})\s*값\b", source)))
    out: dict[str, list[dict[str,str]]] = {}
    for name in names:
        best_pairs=[]
        for start in re.finditer(re.escape(name) + r"\s*값", source, re.I):
            tail=source[start.end():]
            next_m=re.search(r"\b[A-Za-z][A-Za-z0-9_]{3,}\s*값\b", tail)
            body=tail[:next_m.start()] if next_m else tail[:2200]
            pairs=[]
            for m in re.finditer(r"(0x[0-9A-Fa-f]+|\d+)\s*:\s*(.*?)(?=(?:0x[0-9A-Fa-f]+|\d+)\s*:|$)", body, re.S):
                meaning=re.sub(r"\s+", " ", m.group(2)).strip(" -|•\n\t")
                if len(meaning)>160:
                    meaning=meaning[:160].rstrip()+"…"
                pairs.append({"value":m.group(1),"meaning":meaning})
            if len(pairs)>len(best_pairs):
                best_pairs=pairs
        if best_pairs:
            out[name]=best_pairs
    return out


def _semantic_label(meaning: str) -> str:
    low=(meaning or "").lower()
    for label in ("front","rear","left","right","top"):
        if re.search(rf"\b{label}\b", low):
            return label
    ko={"전방":"front","후방":"rear","좌측":"left","우측":"right","탑":"top"}
    for token,label in ko.items():
        if token in meaning:
            return label
    if "invalid" in low or "무효" in low:
        return "invalid"
    if "error" in low or "고장" in meaning:
        return "error"
    if "default" in low:
        return "default"
    return ""


def _sequence_labels(source: str) -> list[str]:
    best: list[str] = []
    for m in re.finditer(r"([A-Za-z가-힣]+(?:\s*(?:->|→)\s*[A-Za-z가-힣]+){1,8})", source):
        terms=re.split(r"\s*(?:->|→)\s*", m.group(1))
        labels=[]
        for t in terms:
            lbl=_semantic_label(t)
            if lbl:
                labels.append(lbl)
        if len(labels)>len(best):
            best=labels
    return best


def _fact_ids_matching(req: dict[str, Any], needles: list[str]) -> list[str]:
    low_needles=[n.lower() for n in needles if n]
    ids=[]
    for rec in _fact_records(req):
        low=rec["text"].lower()
        if any(n in low for n in low_needles):
            if rec["fid"] and rec["fid"] not in ids:
                ids.append(rec["fid"])
    return ids


def _source_trace_for_fids(req: dict[str, Any], fids: list[str]) -> tuple[list[str],list[str]]:
    sems=[]; locs=[]; wanted=set(fids)
    for rec in _fact_records(req):
        if wanted and rec["fid"] not in wanted:
            continue
        if rec["sem"] and rec["sem"] not in sems: sems.append(rec["sem"])
        if rec["location"] and rec["location"] not in locs: locs.append(rec["location"])
    if not sems:
        sems=[str(x) for x in _list(req.get("source_semantic_unit_ids")) if str(x)]
    if not locs:
        for ev in _list(req.get("source_evidence")):
            if isinstance(ev,dict):
                loc=_norm(ev.get("location"))
                if loc and loc not in locs: locs.append(loc)
    return sems,locs




FACT_ROLE_ORDER = (
    "PRECONDITION", "TRIGGER", "INPUT", "ACTION", "SEQUENCE",
    "OBSERVABLE", "EXPECTED", "CONSTRAINT", "EXCEPTION", "NEGATIVE_REQUIREMENT",
    "STATE_TRANSITION", "VARIANT_CONDITION", "TBD_CONFLICT",
)


def classify_source_backed_facts(req: dict[str, Any]) -> list[dict[str, Any]]:
    """Classify finalized Source-backed facts by verification role.

    This is deliberately multi-label.  V0.92 uses the roles to decide where a fact is
    projected in the human test case; it does not rewrite or split the Canonical SRS.
    """
    out: list[dict[str, Any]] = []
    for rec in _fact_records(req):
        text = rec["text"]
        low = text.lower()
        roles: list[str] = []
        if re.search(r"(?:완료\s*후|이후|사전\s*조건|상태에서|인\s*경우|일\s*경우|때|시\b)", text):
            roles.append("PRECONDITION")
        if re.search(r"(?:요청|command|cmd|수신|trigger|입력)", low):
            roles.append("TRIGGER")
        if re.search(r"(?:적용|주입|설정|입력|request|command|cmd)", low):
            roles.append("INPUT")
        if re.search(r"(?:송출|송신|전송|제어|수행|처리|저장|resiz|crop)", low):
            roles.append("ACTION")
        if re.search(r"(?:->|→|순서|순차|step)", low):
            roles.append("SEQUENCE")
        if re.search(r"(?:확인|관찰|피드백|상태\s*신호|state|status|출력)", low):
            roles.append("OBSERVABLE")
        if re.search(r"(?:되어야|해야\s*한다|이어야|여야|일치|0x[0-9a-f]+|\bon\b|\boff\b)", low):
            roles.append("EXPECTED")
        if re.search(r"(?:이하|미만|이상|초과|최대|최소|허용|금지|\d+(?:\.\d+)?\s*(?:ms|s|초|mb|kb|v|a|%))", low):
            roles.append("CONSTRAINT")
        if re.search(r"(?:미수신|timeout|error|invalid|고장|오류|예외|실패)", low):
            roles.append("EXCEPTION")
        if re.search(r"(?:하지\s*않|없음|금지|no\s*retry|retry\s*없)", low):
            roles.append("NEGATIVE_REQUIREMENT")
        if re.search(r"(?:전이|transition|target\s*state|상태로)", low):
            roles.append("STATE_TRANSITION")
        if re.search(r"(?:hev|phev|ev|ice|차종|variant)", low):
            roles.append("VARIANT_CONDITION")
        if re.search(r"(?:tbd|충돌|conflict|미확정|확정되지)", low):
            roles.append("TBD_CONFLICT")
        if not roles:
            roles.append("ACTION")
        # stable order for deterministic regression
        roles = [r for r in FACT_ROLE_ORDER if r in roles]
        out.append({**rec, "roles": roles})
    return out


def _field_trace(case: dict[str, Any], field: str, fids: list[str] | set[str] | tuple[str, ...]) -> None:
    trace = case.setdefault("field_fact_trace", {})
    trace[field] = list(dict.fromkeys(str(x) for x in fids if str(x)))


def _set_structured_case_fields(
    case: dict[str, Any], *, objective: str = "", precondition: str = "", environment: str = "",
    input_variable: str = "", input_compare: str = "", input_value: str = "", execution: str = "",
    output_variable: str = "", output_compare: str = "", output_value: str = "", expected_state: str = "",
    pass_criterion: str = "", field_fids: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    case["test_objective"] = _norm(objective or case.get("verification_objective") or case.get("test_intent") or case.get("evaluation_name"))
    case["precondition"] = _norm(precondition)
    case["test_environment"] = _norm(environment)
    case["input_variable"] = _norm(input_variable)
    case["input_compare"] = _norm(input_compare)
    case["input_value"] = _norm(input_value)
    case["test_execution"] = _text(execution).strip()
    case["output_variable"] = _norm(output_variable)
    case["output_compare"] = _norm(output_compare)
    case["output_value"] = _text(output_value).strip()
    case["expected_state"] = _text(expected_state).strip()
    case["pass_criterion"] = _text(pass_criterion).strip()
    for k, vals in (field_fids or {}).items():
        _field_trace(case, k, vals)
    return case


def _fact_ids_for_value(req: dict[str, Any], *needles: str) -> list[str]:
    clean=[_norm(x) for x in needles if _norm(x)]
    if not clean:
        return []
    return _fact_ids_matching(req, clean)



def _related_context_fids(req: dict[str, Any], context: str) -> list[str]:
    """Find exact facts that establish a Source-backed precondition/trigger named in context."""
    ctx=_norm(context)
    if not ctx:
        return []
    anchors=[]
    # Signal/identifier anchors.
    anchors.extend(re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{2,}\b",ctx))
    # Korean/compound phrase directly preceding completion/after/condition words.
    for m in re.finditer(r"([A-Za-z가-힣0-9_ /-]{2,48}?)(?:완료\s*후|이후|인\s*경우|일\s*경우)",ctx):
        anchors.append(_norm(m.group(1)))
    generic={"HU","ECU","System","Source","Command","CMD","On","Off"}
    anchors=[a for a in anchors if a not in generic and len(a)>=2]
    ids=[]
    for rec in _fact_records(req):
        low=rec["text"].lower()
        if any(a.lower() in low for a in anchors):
            if rec["fid"] and rec["fid"] not in ids:
                ids.append(rec["fid"])
    return ids


def _trace_integrity_review(req: dict[str, Any], case: dict[str, Any]) -> dict[str, Any] | None:
    """Review-route populated verification values that lack exact Fact Fragment provenance."""
    trace = case.get("field_fact_trace") if isinstance(case.get("field_fact_trace"), dict) else {}
    required = []
    for field in ("input_value", "output_value", "pass_criterion"):
        value = _text(case.get(field))
        if value and not _list(trace.get(field)):
            required.append(field)
    if not required:
        case["exact_field_trace_status"] = "PASS"
        return None
    case["exact_field_trace_status"] = "REVIEW_REQUIRED"
    case["human_review_required"] = True
    case["execution_readiness"] = "REVIEW_REQUIRED"
    case["deferred_reason_code"] = "EXACT_FIELD_FACT_TRACE_REQUIRED"
    case["deferred_reason_detail"] = "Input/Expected/PASS 값의 정확한 Source Fact Fragment 연결이 필요합니다."
    case["required_resolution"] = "해당 값의 정확한 Source Fact Fragment를 연결하거나, 연결 전까지 Review 상태로 유지합니다."
    return {
        "parent_srs_id": str(req.get("srs_id") or case.get("parent_srs_id") or ""),
        "review_type": "EXACT_FIELD_FACT_TRACE_REQUIRED",
        "signal": _norm(case.get("output_variable") or case.get("input_variable")),
        "value": " / ".join(required),
        "meaning": _norm(case.get("evaluation_name")),
        "role": "Traceability",
        "reason": "사람용 TC에 채워진 Input/Expected/PASS 값 중 일부가 정확한 Source Fact Fragment와 연결되지 않았습니다.",
        "required_resolution": "해당 값의 정확한 Source Fact Fragment를 연결하거나, 연결 전까지 실행 가능 TC가 아닌 Review 상태로 유지합니다.",
    }


def _condition_from_prefix(prefix: str) -> str:
    p=_norm(prefix)
    if not p:
        return ""
    p=re.sub(r"^(?:HU|ECU|시스템)(?:은|는|이|가)?\s*", "", p, flags=re.I)
    p=re.sub(r"^(?:하고|그리고|또는)\s*", "", p, flags=re.I)
    # Keep the Source wording but trim obvious actor/action scaffolding.
    m=re.search(r"(.{2,100}?)(?:완료\s*후|이후|인\s*경우|일\s*경우|수신(?:하면|\s*시)|때|시)\s*$", p)
    return _norm(m.group(0) if m else p[-100:])


def _extract_signal_assignments(text: str) -> list[dict[str, str]]:
    """Extract literal signal/value output assignments with nearby Source conditions."""
    raw=_norm(text)
    if not raw:
        return []
    pat=re.compile(
        r"(?P<prefix>[^.;]{0,150}?)"
        r"(?:신호\s*\()?\s*(?P<signal>[A-Za-z][A-Za-z0-9_]{2,})\)?\s*(?:를|을)?\s*"
        r"(?P<value>0x[0-9A-Fa-f]+|ON|OFF|On|Off|HIGH|LOW)"
        r"(?:\s*\((?P<meaning>[^)]{1,80})\))?\s*(?:로|으로)?\s*"
        r"(?P<verb>송출|송신|전송|출력|제어|설정)", re.I,
    )
    out=[]
    for m in pat.finditer(raw):
        out.append({
            "prefix": _norm(m.group("prefix")), "signal": m.group("signal"),
            "value": m.group("value"), "meaning": _norm(m.group("meaning")), "verb": m.group("verb"),
        })
    return out


def _input_label_from_condition(prefix: str) -> str:
    p=_norm(prefix)
    # Prefer explicit Command/request phrase when available.
    for pat in (
        r"([^,.;]{2,48}?(?:Command|CMD|요청))\s*(?:을|를)?\s*수신",
        r"([^,.;]{2,48}?차종)인\s*경우",
    ):
        m=re.search(pat,p,re.I)
        if m:
            label=_norm(m.group(1))
            label=re.sub(r"^(?:HU|ECU|시스템)(?:은|는|이|가)?\s*", "", label, flags=re.I)
            label=re.sub(r"^(?:하고|그리고|또는)\s*", "", label, flags=re.I)
            label=re.sub(r"^(?:실시간\s*감시모드\s*)", "실시간 감시모드 ", label)
            return label.strip()
    return ""


def _direct_signal_output_cases(req: dict[str,Any], base: dict[str,Any], start_index: int, occupied_fids: set[str]) -> tuple[list[dict[str,Any]], int]:
    cases=[]; idx=start_index
    for rec in _fact_records(req):
        if rec["fid"] and rec["fid"] in occupied_fids:
            continue
        assigns=_extract_signal_assignments(rec["text"])
        if not assigns:
            continue
        by_signal: dict[str,list[dict[str,str]]] = defaultdict(list)
        for a in assigns:
            by_signal[a["signal"]].append(a)
        for signal,items in by_signal.items():
            value_fids=[rec["fid"]] if rec["fid"] else _fact_ids_for_value(req,signal,*[x["value"] for x in items])
            context_fids=[]
            for x in items:
                context_fids.extend(_related_context_fids(req,x["prefix"]))
            fid=list(dict.fromkeys(context_fids+value_fids))
            vectors=[]
            for n,a in enumerate(items,1):
                vectors.append({
                    "step": n,
                    "input_variable": _input_label_from_condition(a["prefix"]),
                    "input_value": _input_label_from_condition(a["prefix"]),
                    "output_variable": signal,
                    "expected_output": a["value"],
                    "output_meaning": a["meaning"],
                    "source_fact_fragment_ids": fid,
                })
            title=f"{signal} 출력 확인"
            obj=f"Source 조건에 따라 {signal}의 출력 값이 정의와 일치하는지 확인한다."
            case=_base_case(base,req,idx,kind="DIRECT_SIGNAL_OUTPUT",title=title,objective=obj,fids=fid)
            conditions=[_condition_from_prefix(a["prefix"]) for a in items if _condition_from_prefix(a["prefix"])]
            in_labels=[_input_label_from_condition(a["prefix"]) for a in items if _input_label_from_condition(a["prefix"])]
            input_var="조건 / Command" if in_labels else ""
            input_val="\n".join(dict.fromkeys(in_labels))
            output_val="\n".join(f"{n}) {a['value']}"+(f" · {a['meaning']}" if a['meaning'] else "") for n,a in enumerate(items,1))
            if len(items)==1:
                output_val=items[0]["value"]+(f" · {items[0]['meaning']}" if items[0]["meaning"] else "")
            passc=(f"Source 조건에서 {signal}={items[0]['value']}이면 PASS" if len(items)==1 else f"각 조건에서 {signal}의 출력 값이 Source 정의와 모두 일치하면 PASS")
            _set_structured_case_fields(
                case, objective=obj, precondition="\n".join(dict.fromkeys(conditions)),
                input_variable=input_var, input_compare="조건별" if input_val else "", input_value=input_val,
                execution=f"Source에 정의된 조건을 적용하고 {signal}을 관찰한다.",
                output_variable=signal, output_compare="조건별" if len(items)>1 else "=", output_value=output_val,
                expected_state="\n".join(x["meaning"] for x in items if x["meaning"]), pass_criterion=passc,
                field_fids={"precondition":context_fids,"input_value":fid if input_val else [],"output_value":value_fids or fid,"pass_criterion":fid},
            )
            case["test_vectors"]=vectors
            case["split_decision"]="KEEP_AS_VECTOR" if len(items)>1 else "KEEP_SINGLE_OBJECTIVE"
            cases.append(case); idx+=1
    return cases,idx


def _variant_state_cases(req: dict[str,Any], base: dict[str,Any], start_index: int, occupied_fids: set[str]) -> tuple[list[dict[str,Any]], int]:
    cases=[]; idx=start_index
    pat=re.compile(r"(?P<variants>(?:HEV|PHEV|EV|ICE)(?:\s*/\s*(?:HEV|PHEV|EV|ICE)){1,4})\s*차종인\s*경우.*?\b(?P<state>[A-Za-z][A-Za-z0-9_]{1,})\s*(?P<value>On|Off|ON|OFF)\b",re.I)
    for rec in _fact_records(req):
        if rec["fid"] and rec["fid"] in occupied_fids:
            continue
        m=pat.search(rec["text"])
        if not m:
            continue
        fid=[rec["fid"]] if rec["fid"] else _fact_ids_for_value(req,m.group("variants"),m.group("state"),m.group("value"))
        obj=f"{m.group('variants')} 차종에서 {m.group('state')} 상태가 Source 정의와 일치하는지 확인한다."
        case=_base_case(base,req,idx,kind="VARIANT_EXPECTED_STATE",title=f"{m.group('state')} Variant 상태 확인",objective=obj,fids=fid)
        _set_structured_case_fields(
            case, objective=obj, precondition=f"차종 = {m.group('variants')}",
            input_variable="차종", input_compare="∈", input_value=m.group("variants"),
            execution="Source에 정의된 기능 흐름을 수행하고 Variant 전용 상태를 확인한다.",
            output_variable=m.group("state"), output_compare="=", output_value=m.group("value"),
            expected_state=f"{m.group('state')} {m.group('value')}",
            pass_criterion=f"대상 차종에서 {m.group('state')}={m.group('value')}이면 PASS",
            field_fids={"input_value":fid,"output_value":fid,"pass_criterion":fid},
        )
        case["split_decision"]="SPLIT_BY_VARIANT_OBJECTIVE"
        cases.append(case); idx+=1
    return cases,idx


def _timeout_exception_cases(req: dict[str,Any], base: dict[str,Any], start_index: int, occupied_fids: set[str]) -> tuple[list[dict[str,Any]], int]:
    cases=[]; idx=start_index
    for rec in _fact_records(req):
        if rec["fid"] and rec["fid"] in occupied_fids:
            continue
        text=rec["text"]
        if not re.search(r"(?:미수신|수신하지\s*못|timeout)",text,re.I):
            continue
        tm=re.search(r"(\d+(?:\.\d+)?)\s*(초|ms|s)\s*(?:동안)?",text,re.I)
        if not tm:
            continue
        time_value=f"{tm.group(1)}{tm.group(2)}"
        source_name="피드백 신호" if "피드백" in text else "응답 / 상태 신호"
        outcomes=[]; seen_out=set()
        for token in ("미응답", "촬영 중단", "촬영을 중단", "Retry 없음", "재시도 없음"):
            if token.lower() in text.lower():
                normalized=token.replace("촬영을 중단","촬영 중단")
                key=normalized.lower()
                if key not in seen_out:
                    seen_out.add(key); outcomes.append(normalized)
        if not outcomes:
            continue
        fid=[rec["fid"]] if rec["fid"] else _fact_ids_for_value(req,time_value,*outcomes)
        expected=" / ".join(dict.fromkeys(outcomes))
        obj=f"{source_name}가 {time_value} 동안 미수신될 때 Source-defined 예외 처리를 확인한다."
        case=_base_case(base,req,idx,kind="TIMEOUT_EXCEPTION",title="Timeout / 미응답 처리 확인",objective=obj,fids=fid)
        _set_structured_case_fields(
            case, objective=obj, input_variable=source_name, input_compare="미수신", input_value=time_value,
            execution=f"관련 요청 후 {source_name}를 {time_value} 동안 미수신 상태로 유지한다.",
            expected_state=expected, pass_criterion=f"{time_value} 미수신 시 {expected}이 확인되면 PASS",
            field_fids={"input_value":fid,"pass_criterion":fid},
        )
        case["split_decision"]="SPLIT_EXCEPTION_PATH"
        case["test_vectors"]=[{"step":1,"input_variable":source_name,"input_compare":"미수신","input_value":time_value,"expected_state":expected,"source_fact_fragment_ids":fid}]
        cases.append(case); idx+=1
    return cases,idx


def _pipe_decision_table_cases(req: dict[str,Any], base: dict[str,Any], start_index: int) -> tuple[list[dict[str,Any]], int]:
    """Parse simple Source-backed pipe tables as one TC with N vectors.

    It is intentionally conservative: only tables with >=2 input columns and one obvious
    result column are projected.  The table stays one TC because the decision function is common.
    """
    source=_source_text(req)
    lines=[ln.strip() for ln in source.splitlines() if "|" in ln and not re.match(r"^\s*[-:| ]+$",ln)]
    if len(lines)<2:
        return [],start_index
    cases=[]; idx=start_index; i=0
    while i < len(lines)-1:
        header=[x.strip() for x in lines[i].split("|")]
        if len(header)<3:
            i+=1; continue
        result_idx=None
        for j,h in enumerate(header):
            if re.search(r"(?:동작\s*여부|상태|결과|sidemirroropen|expected|output)",h,re.I):
                result_idx=j
        if result_idx is None or result_idx==0:
            i+=1; continue
        rows=[]; j=i+1
        while j<len(lines):
            vals=[x.strip() for x in lines[j].split("|")]
            if len(vals)!=len(header): break
            rows.append(vals); j+=1
        if not rows:
            i+=1; continue
        table_text=" ".join(header + [v for row in rows for v in row])
        fids=_fact_ids_for_value(req,*header,*[v for row in rows for v in row])
        # Avoid executable projection if the table has no exact finalized fact provenance.
        obj=f"Source Decision Table의 조건 조합에 따른 {header[result_idx]} 결과를 확인한다."
        case=_base_case(base,req,idx,kind="DECISION_TABLE",title=f"{header[result_idx]} Decision Table 확인",objective=obj,fids=fids or None)
        input_cols=[h for n,h in enumerate(header) if n!=result_idx]
        vectors=[]
        for n,row in enumerate(rows,1):
            vectors.append({
                "step":n,
                "input_variable":" / ".join(input_cols),
                "input_value":" / ".join(v for k,v in enumerate(row) if k!=result_idx),
                "output_variable":header[result_idx],
                "expected_output":row[result_idx],
                "source_fact_fragment_ids":fids,
            })
        _set_structured_case_fields(
            case, objective=obj,
            input_variable=" / ".join(input_cols), input_compare="조합", input_value="\n".join(f"{n}) "+v["input_value"] for n,v in enumerate(vectors,1)),
            execution="Source Decision Table의 각 조건 조합을 적용하고 결과를 관찰한다.",
            output_variable=header[result_idx], output_compare="조합 일치", output_value="\n".join(f"{n}) "+v["expected_output"] for n,v in enumerate(vectors,1)),
            expected_state="각 조합의 결과가 Source 표와 일치",
            pass_criterion="모든 Source-defined 조합의 결과가 Decision Table과 일치하면 PASS",
            field_fids={"input_value":fids,"output_value":fids,"pass_criterion":fids},
        )
        case["test_vectors"]=vectors
        case["split_decision"]="KEEP_AS_VECTOR"
        cases.append(case); idx+=1
        i=j
    return cases,idx


def _state_transition_cases(req: dict[str,Any], base: dict[str,Any], start_index: int, occupied_fids: set[str]) -> tuple[list[dict[str,Any]], int]:
    cases=[]; idx=start_index
    for rec in _fact_records(req):
        if rec["fid"] and rec["fid"] in occupied_fids:
            continue
        text=rec["text"]
        if "전이" not in text and "transition" not in text.lower():
            continue
        fid=[rec["fid"]] if rec["fid"] else []
        # Negative/inhibit transition first.
        mneg=re.search(r"(?P<cond>[^.;]{2,80}?)(?:상태에서는|인\s*경우).*?(?P<target>[A-Za-z가-힣][A-Za-z가-힣0-9 _-]{1,40})\s*(?:상태로\s*)?전이.*?(?:하지\s*않|금지)",text,re.I)
        if mneg:
            cond=_norm(mneg.group("cond")); target=_norm(mneg.group("target"))
            target=re.sub(r"^(?:시스템|System|HU|ECU)(?:은|는|이|가)?\s*", "", target, flags=re.I).strip()
            obj=f"{cond} 조건에서 {target} 전이가 금지되는지 확인한다."
            case=_base_case(base,req,idx,kind="STATE_TRANSITION_INHIBIT",title=f"{target} 전이 금지 확인",objective=obj,fids=fid or None)
            case["condition_logic"]="INHIBIT"
            case["expected_target_state"]=f"NOT {target}"
            _set_structured_case_fields(case,objective=obj,precondition=cond,input_variable="System State",input_compare="=",input_value=cond,
                execution=f"{cond} 상태에서 {target} 전이 발생 여부를 관찰한다.",output_variable=f"{target} Transition",output_compare="금지",output_value="발생하지 않음",
                expected_state=f"{target} 전이 금지",pass_criterion=f"{cond} 상태에서 {target} 전이가 발생하지 않으면 PASS",
                field_fids={"input_value":fid,"output_value":fid,"pass_criterion":fid})
            case["split_decision"]="SPLIT_NEGATIVE_PATH"; cases.append(case); idx+=1; continue
        m=re.search(r"(?P<cond>[^.;]{2,120}?)(?:인\s*경우|일\s*경우|이면).*?(?P<target>[A-Za-z가-힣][A-Za-z가-힣0-9 _-]{1,40})\s*상태로\s*전이",text,re.I)
        if not m:
            continue
        cond=_norm(m.group("cond")); target=_norm(m.group("target"))
        target=re.sub(r"^(?:시스템|System|HU|ECU)(?:은|는|이|가)?\s*", "", target, flags=re.I).strip()
        logic="ANY_OF" if re.search(r"(?:또는|\bor\b)",cond,re.I) else ("ALL_OF" if re.search(r"(?:이고|그리고|\band\b)",cond,re.I) else "SINGLE")
        obj=f"{cond} 조건에서 {target} 상태 전이를 확인한다."
        case=_base_case(base,req,idx,kind="STATE_TRANSITION",title=f"{target} 상태 전이 확인",objective=obj,fids=fid or None)
        case["condition_logic"]=logic; case["expected_target_state"]=target
        _set_structured_case_fields(case,objective=obj,precondition=cond,input_variable="전이 조건",input_compare=logic,input_value=cond,
            execution="Source-defined 전이 조건을 적용하고 시스템 상태를 관찰한다.",output_variable="System State",output_compare="=",output_value=target,
            expected_state=target,pass_criterion=f"{cond}일 때 System State={target}이면 PASS",
            field_fids={"input_value":fid,"output_value":fid,"pass_criterion":fid})
        case["split_decision"]="SPLIT_BY_TARGET_STATE"; cases.append(case); idx+=1
    return cases,idx


def _blocking_source_reviews(req: dict[str, Any]) -> tuple[list[dict[str, Any]], set[str]]:
    reviews=[]; blocking_fids:set[str]=set()
    for rec in classify_source_backed_facts(req):
        if "TBD_CONFLICT" not in rec.get("roles",[]):
            continue
        fid=str(rec.get("fid") or "")
        if fid: blocking_fids.add(fid)
        text=rec.get("text") or ""
        review_type="SOURCE_TBD_REVIEW" if re.search(r"(?:tbd|미확정|확정되지)",text,re.I) else "SOURCE_CONFLICT_REVIEW"
        reviews.append({
            "parent_srs_id":str(req.get("srs_id") or ""),
            "review_type":review_type,
            "signal":"",
            "value":fid,
            "meaning":text,
            "role":"Source Governance",
            "reason":"Source에 TBD/Conflict/미확정 정보가 있어 deterministic executable TC로 확정할 수 없습니다.",
            "required_resolution":"승인된 Source/변경 결정 또는 외부 의존 근거를 연결한 뒤 해당 Fact의 TC를 재생성합니다.",
            "source_fact_fragment_ids":[fid] if fid else [],
        })
    for item in _list(req.get("tbd_items")):
        txt=_norm(item)
        if txt:
            reviews.append({"parent_srs_id":str(req.get("srs_id") or ""),"review_type":"SOURCE_TBD_REVIEW","signal":"","value":"","meaning":txt,"role":"Source Governance","reason":"Requirement에 연결된 TBD 항목이 미종결 상태입니다.","required_resolution":"TBD 항목의 최종 정의를 연결하거나 명시적 disposition을 기록합니다.","source_fact_fragment_ids":[]})
    for key in ("canonical_conflict_ids","conflict_ids","canonical_gap_ids"):
        for value in _list(req.get(key)):
            if str(value):
                reviews.append({"parent_srs_id":str(req.get("srs_id") or ""),"review_type":"SOURCE_CONFLICT_REVIEW","signal":"","value":str(value),"meaning":str(value),"role":"Source Governance","reason":"Requirement에 Open Conflict/Gap 참조가 존재합니다.","required_resolution":"Open Conflict/Gap의 authoritative decision을 연결한 뒤 affected TC를 재생성합니다.","source_fact_fragment_ids":[]})
    return reviews,blocking_fids


def _review_only_case(base: dict[str,Any], req: dict[str,Any], idx: int, reason: str) -> dict[str,Any]:
    case=dict(base)
    sid=str(base.get("parent_srs_id") or req.get("srs_id") or "SRS")
    case["evaluation_objective_id"]=f"EVAL_{re.sub(r'[^A-Za-z0-9_]+','_',sid).strip('_')}_REVIEW{idx:02d}"
    case["basic_functional_tc_id"]=""
    case["test_design_mode"]="BASIC_FUNCTIONAL_REVIEW"
    case["basic_case_kind"]="SOURCE_CONFLICT_TBD_REVIEW"
    case["evaluation_name"]="Source 미확정 / Conflict 검토"
    case["test_objective"]="Source 미확정 또는 Conflict 해소 후 실행 가능한 TC를 재생성한다."
    case["precondition"]=""
    case["test_environment"]=""
    case["input_variable"]=""; case["input_compare"]=""; case["input_value"]=""
    case["test_execution"]=""
    case["output_variable"]=""; case["output_compare"]=""; case["output_value"]=""
    case["expected_state"]=""
    case["pass_criterion"]=""
    case["human_review_required"]=True
    case["execution_readiness"]="REVIEW_REQUIRED"
    case["deferred_reason_code"]="SOURCE_CONFLICT_TBD_REVIEW"
    case["deferred_reason_detail"]=reason
    case["required_resolution"]="Authoritative Source decision을 연결한 뒤 재생성합니다."
    case["split_decision"]="REVIEW"
    case["field_fact_trace"]={}
    case["exact_field_trace_status"]="NOT_APPLICABLE"
    case["test_vectors"]=[]
    return case


def _base_case(base: dict[str,Any], req: dict[str,Any], idx: int, *, kind: str, title: str, objective: str, fids: list[str] | None = None) -> dict[str,Any]:
    case=dict(base)
    sid=str(base.get("parent_srs_id") or req.get("srs_id") or "SRS")
    case["evaluation_objective_id"] = f"EVAL_{re.sub(r'[^A-Za-z0-9_]+','_',sid).strip('_')}_BF{idx:02d}"
    case["basic_functional_tc_id"] = f"E2E_TC_{sid}_{idx:02d}"
    case["test_design_mode"] = BASIC_FUNCTIONAL_MODE
    case["basic_case_kind"] = kind
    case["evaluation_name"] = title
    case["verification_objective"] = objective
    case["test_intent"] = objective
    if fids is not None:
        case["source_fact_fragment_ids"] = list(dict.fromkeys(x for x in fids if x))
        sems,locs=_source_trace_for_fids(req, case["source_fact_fragment_ids"])
        if sems: case["source_semantic_unit_ids"] = sems
        if locs: case["source_locations"] = locs
    case.setdefault("test_vectors", [])
    case.setdefault("field_fact_trace", {})
    case.setdefault("test_objective", _norm(objective or title))
    case.setdefault("precondition", "")
    case.setdefault("test_environment", "")
    case.setdefault("expected_state", "")
    case.setdefault("pass_criterion", "")
    case.setdefault("split_decision", "KEEP_SINGLE_OBJECTIVE")
    case.setdefault("exact_field_trace_status", "NOT_EVALUATED")
    return case


def _enum_cases(req: dict[str,Any], base: dict[str,Any], start_index: int) -> tuple[list[dict[str,Any]], list[dict[str,Any]], int]:
    source=_source_text(req)
    blocks=_extract_signal_enum_blocks(source)
    if len(blocks)<2:
        return [],[],start_index
    grouped: dict[str,dict[str,tuple[str,list[dict[str,str]]]]] = defaultdict(dict)
    for name,pairs in blocks.items():
        stem,role=_signal_role(name)
        if role in {"request","response"}:
            grouped[stem.lower()][role]=(name,pairs)
    cases=[]; reviews=[]; idx=start_index
    seq=_sequence_labels(source)
    for stem,roles in grouped.items():
        if "request" not in roles or "response" not in roles:
            continue
        in_name,in_pairs=roles["request"]; out_name,out_pairs=roles["response"]
        core_text=_core_requirement_text(req).lower()
        if in_name.lower() not in core_text and out_name.lower() not in core_text:
            continue
        in_by_label={_semantic_label(p["meaning"]):p for p in in_pairs if _semantic_label(p["meaning"])}
        out_by_label={_semantic_label(p["meaning"]):p for p in out_pairs if _semantic_label(p["meaning"])}
        used:set[str]=set()
        if len(seq)>=2 and all(lbl in in_by_label and lbl in out_by_label for lbl in seq):
            vectors=[]
            for order,lbl in enumerate(seq,1):
                ip=in_by_label[lbl]; op=out_by_label[lbl]
                vectors.append({"step":order,"input_variable":in_name,"input_value":ip["value"],"input_meaning":ip["meaning"],"output_variable":out_name,"expected_output":op["value"],"output_meaning":op["meaning"]})
                used.add(lbl)
            fids=_fact_ids_matching(req,[in_name,out_name]+seq)
            case=_base_case(base,req,idx,kind="SEQUENCE_REQUEST_RESPONSE",title="순차 요청 / 응답 확인",objective=f"{in_name} 요청 순서와 {out_name} 응답의 단계별 대응을 확인한다.",fids=fids)
            case.update({
                "test_preparation":"요청/응답 Signal을 관찰할 수 있는 평가 환경을 준비한다.",
                "prep_variable":"","prep_compare":"","prep_value":"",
                "test_execution":"Source에 정의된 순서로 요청 값을 적용하고 각 단계의 응답 값을 관찰한다.",
                "input_variable":in_name,"input_compare":"순차 입력",
                "input_value":"\n".join(f"{v['step']}) {v['input_value']}" for v in vectors),
                "expected_result":"각 요청 단계에서 Source에 정의된 대응 응답이 동일 순서로 확인되어야 한다.",
                "output_variable":out_name,"output_compare":"순차 일치",
                "output_value":"\n".join(f"{v['step']}) {v['expected_output']} · {v['output_meaning']}" for v in vectors),
                "test_vectors":vectors,
            })
            in_fids=_fact_ids_for_value(req,in_name,*[v["input_value"] for v in vectors])
            out_fids=_fact_ids_for_value(req,out_name,*[v["expected_output"] for v in vectors])
            _set_structured_case_fields(
                case, objective=f"{in_name} 요청 순서와 {out_name} 응답의 단계별 대응을 확인한다.",
                environment="요청/응답 Signal을 관찰할 수 있는 평가 환경",
                input_variable=in_name,input_compare="순차 입력",input_value=case["input_value"],
                execution=case["test_execution"], output_variable=out_name,output_compare="순차 일치",output_value=case["output_value"],
                expected_state="Source-defined 요청/응답 순서 일치",
                pass_criterion="모든 단계의 요청 값과 응답 값 및 순서가 Source 정의와 일치하면 PASS",
                field_fids={"input_value":in_fids or fids,"output_value":out_fids or fids,"pass_criterion":list(dict.fromkeys((in_fids or [])+(out_fids or [])+fids))},
            )
            case["split_decision"]="KEEP_AS_SEQUENCE"
            cases.append(case); idx+=1
        # Common functional mappings outside the explicit sequence (e.g. Top View) remain separate.
        for lbl in ("front","rear","left","right","top"):
            if lbl in used or lbl not in in_by_label or lbl not in out_by_label:
                continue
            ip=in_by_label[lbl]; op=out_by_label[lbl]
            fids=_fact_ids_matching(req,[in_name,out_name,lbl])
            case=_base_case(base,req,idx,kind="ENUM_REQUEST_RESPONSE",title=f"{lbl.title()} 요청 / 응답 확인",objective=f"{in_name}의 {ip['value']} 요청에 대해 {out_name}의 Source-defined 응답을 확인한다.",fids=fids)
            case.update({
                "test_preparation":"요청/응답 Signal을 관찰할 수 있는 평가 환경을 준비한다.",
                "test_execution":f"{in_name}에 Source-defined 요청 값을 적용한다.",
                "input_variable":in_name,"input_compare":"=","input_value":ip["value"],
                "expected_result":f"{out_name}에서 Source-defined 대응 값이 확인되어야 한다.",
                "output_variable":out_name,"output_compare":"=","output_value":op["value"],
                "test_vectors":[{"step":1,"input_variable":in_name,"input_value":ip["value"],"input_meaning":ip["meaning"],"output_variable":out_name,"expected_output":op["value"],"output_meaning":op["meaning"]}],
            })
            in_fids=_fact_ids_for_value(req,in_name,ip["value"],lbl)
            out_fids=_fact_ids_for_value(req,out_name,op["value"],lbl)
            _set_structured_case_fields(
                case, objective=f"{in_name}={ip['value']} 요청에 대해 {out_name}={op['value']} 응답을 확인한다.",
                environment="요청/응답 Signal을 관찰할 수 있는 평가 환경",
                input_variable=in_name,input_compare="=",input_value=ip["value"],execution=case["test_execution"],
                output_variable=out_name,output_compare="=",output_value=op["value"],expected_state=op["meaning"],
                pass_criterion=f"{in_name}={ip['value']} 요청에 {out_name}={op['value']}가 확인되면 PASS",
                field_fids={"input_value":in_fids or fids,"output_value":out_fids or fids,"pass_criterion":list(dict.fromkeys((in_fids or [])+(out_fids or [])+fids))},
            )
            case["split_decision"]="SPLIT_INDEPENDENT_MAPPING"
            cases.append(case); idx+=1
        # Invalid/error values without Source-defined reaction are review items, not executable PASS/FAIL cases.
        for name,pairs,role in ((in_name,in_pairs,"입력"),(out_name,out_pairs,"출력")):
            for p in pairs:
                lbl=_semantic_label(p["meaning"])
                if lbl not in {"invalid","error"}:
                    continue
                reviews.append({
                    "parent_srs_id":str(req.get("srs_id") or base.get("parent_srs_id") or ""),
                    "review_type":"SOURCE_DEFINED_VALUE_WITHOUT_EXPECTED_BEHAVIOR",
                    "signal":name,"value":p["value"],"meaning":p["meaning"],"role":role,
                    "reason":f"{name}={p['value']} ({p['meaning']}) 값은 Source에 정의되어 있으나 이 값에 대한 HU/ECU의 기대 처리 결과가 현재 Source에서 확인되지 않습니다.",
                    "required_resolution":"기대 동작이 정의된 Source 절/외부 사양을 연결하거나 사람 검토 후 Deferred/시험 케이스 여부를 결정합니다.",
                })
    return cases,reviews,idx


def _conditional_cases(req: dict[str,Any], base: dict[str,Any], start_index: int, occupied_fids: set[str]) -> tuple[list[dict[str,Any]],int]:
    cases=[]; idx=start_index
    for rec in _fact_records(req):
        if rec["fid"] and rec["fid"] in occupied_fids:
            continue
        parsed=_parse_conditional_io(rec["text"])
        if not parsed:
            continue
        case=_base_case(base,req,idx,kind="CONDITIONAL_INPUT_OUTPUT",title="조건별 입력 / 출력 확인",objective=rec["text"],fids=[rec["fid"]] if rec["fid"] else None)
        case.update({
            "test_preparation":"해당 입력 조건을 설정하고 출력 값을 관찰할 수 있는 환경을 준비한다.",
            "test_execution":f"{parsed['input_variable']} 조건을 Source-defined 값으로 적용한다.",
            "input_variable":parsed["input_variable"],"input_compare":parsed["input_compare"],"input_value":parsed["input_value"],
            "expected_result":rec["text"],
            "output_variable":parsed["output_variable"],"output_compare":parsed["output_compare"],"output_value":parsed["output_value"],
            "test_vectors":[{"step":1,**parsed}],
        })
        fids=[rec["fid"]] if rec["fid"] else _fact_ids_for_value(req,parsed["input_variable"],parsed["input_value"],parsed["output_variable"],parsed["output_value"])
        _set_structured_case_fields(
            case, objective=f"{parsed['input_variable']}={parsed['input_value']} 조건에서 {parsed['output_variable']}={parsed['output_value']} 출력 관계를 확인한다.",
            environment="입력 조건 설정 및 출력 관찰 가능 환경",
            input_variable=parsed["input_variable"],input_compare=parsed["input_compare"],input_value=parsed["input_value"],
            execution=case["test_execution"], output_variable=parsed["output_variable"],output_compare=parsed["output_compare"],output_value=parsed["output_value"],
            expected_state=rec["text"], pass_criterion=f"{parsed['input_variable']}={parsed['input_value']}일 때 {parsed['output_variable']}={parsed['output_value']}이면 PASS",
            field_fids={"input_value":fids,"output_value":fids,"pass_criterion":fids},
        )
        case["split_decision"]="SPLIT_INDEPENDENT_CONDITION"
        cases.append(case); idx+=1
    return cases,idx


def _dimension_case(req: dict[str,Any], base: dict[str,Any], start_index: int) -> tuple[list[dict[str,Any]],int]:
    core=_core_requirement_text(req)
    if not re.search(r"resiz|리사이즈|해상도|crop|변환",core,re.I):
        return [],start_index
    source=core + "\n" + _source_text(req)
    iv=ov=""; in_fids=[]; out_fids=[]
    # First preference: literal relation in one Source-backed sentence.
    m=re.search(r"(\d+\s*[x×*]\s*\d+)\s*(?:을|를)?\s*(\d+\s*[x×*]\s*\d+)\s*(?:으로|로)?\s*(?:resiz(?:e|ing)|리사이즈|변환)",source,re.I)
    if m:
        iv=re.sub(r"\s+","",m.group(1)).replace("*","×").replace("x","×")
        ov=re.sub(r"\s+","",m.group(2)).replace("*","×").replace("x","×")
        in_fids=_fact_ids_for_value(req,m.group(1),iv)
        out_fids=_fact_ids_for_value(req,m.group(2),ov,"resiz")
    else:
        # V0.92 also supports a relation spread over two exact fragments within one Canonical SRS:
        # an explicit input dimension fact + an explicit resize/output dimension fact.
        in_rec=None; out_rec=None; in_dim=out_dim=""
        for rec in _fact_records(req):
            mi=re.search(r"(?:입력|원본|input)[^\d]{0,40}(\d+\s*[x×*]\s*\d+)",rec["text"],re.I)
            if mi and in_rec is None:
                in_rec=rec; in_dim=mi.group(1)
            mo=re.search(r"(\d+\s*[x×*]\s*\d+)[^.;]{0,40}(?:resiz(?:e|ing)|리사이즈|변환|조정)",rec["text"],re.I)
            if not mo:
                mo=re.search(r"(?:resiz(?:e|ing)|리사이즈|변환|조정)[^\d]{0,40}(\d+\s*[x×*]\s*\d+)",rec["text"],re.I)
            if mo and out_rec is None:
                out_rec=rec; out_dim=mo.group(1)
        if in_rec and out_rec:
            iv=re.sub(r"\s+","",in_dim).replace("*","×").replace("x","×")
            ov=re.sub(r"\s+","",out_dim).replace("*","×").replace("x","×")
            in_fids=[in_rec["fid"]] if in_rec.get("fid") else []
            out_fids=[out_rec["fid"]] if out_rec.get("fid") else []
    if not iv or not ov:
        return [],start_index
    fids=list(dict.fromkeys(in_fids+out_fids)) or _fact_ids_matching(req,[iv,ov,"resiz"])
    case=_base_case(base,req,start_index,kind="DIMENSION_TRANSFORM",title="영상 크기 변환 확인",objective=f"Source-defined 영상 크기 변환 {iv} → {ov}를 확인한다.",fids=fids or None)
    case.update({
        "test_preparation":"Source-defined 입력 해상도의 영상을 준비한다.",
        "test_execution":"Source에 정의된 Resize 처리를 수행한다.",
        "input_variable":"입력 영상 해상도","input_compare":"=","input_value":iv,
        "expected_result":"Resize 결과가 Source-defined 출력 해상도와 일치해야 한다.",
        "output_variable":"출력 영상 해상도","output_compare":"=","output_value":ov,
        "test_vectors":[{"step":1,"input_variable":"입력 영상 해상도","input_value":iv,"output_variable":"출력 영상 해상도","expected_output":ov,"source_fact_fragment_ids":fids}],
    })
    _set_structured_case_fields(
        case, objective=f"입력 영상 {iv}가 Source-defined 처리 후 {ov}로 변환되는지 확인한다.",
        environment="입력/출력 영상 해상도 확인 가능 환경",
        input_variable="입력 영상 해상도",input_compare="=",input_value=iv,execution=case["test_execution"],
        output_variable="출력 영상 해상도",output_compare="=",output_value=ov,expected_state=f"Resize 결과 {ov}",
        pass_criterion=f"{iv} 입력이 {ov}로 변환되면 PASS",
        field_fids={"input_value":in_fids or fids,"output_value":out_fids or fids,"pass_criterion":fids},
    )
    case["split_decision"]="SPLIT_TRANSFORM_OBJECTIVE"
    return [case],start_index+1


def _artifact_property_case(req: dict[str,Any], base: dict[str,Any], start_index: int) -> tuple[list[dict[str,Any]],int]:
    """Build Source-backed artifact-property cases with exact per-property provenance.

    V0.92 keeps closely related Format+Resolution in one objective when both are explicit, while
    numeric Size constraints become a separate criterion so a missing fragment cannot hide behind
    another property fragment.
    """
    core=_core_requirement_text(req)
    if not re.search(r"format|resolution|size|jpeg|저장|해상도|크기",core,re.I):
        return [],start_index
    source=core + "\n" + _source_text(req)
    props=[]
    # Accept both key:value and natural Korean/English forms.
    m=re.search(r"\bFormat\s*[:：]\s*([A-Za-z0-9_-]+)",source,re.I) or re.search(r"\b(JPEG|PNG|BMP)\s*(?:형식|format)",source,re.I)
    if m: props.append(("Format","=",m.group(1),_fact_ids_for_value(req,m.group(1))))
    m=re.search(r"\bResolution\s*[:：]\s*(\d+\s*[x×*]\s*\d+)",source,re.I) or re.search(r"(?:해상도(?:는|가)?\s*)(\d+\s*[x×*]\s*\d+)",source,re.I)
    if m:
        val=re.sub(r"\s+","",m.group(1)).replace("*","×").replace("x","×")
        props.append(("Resolution","=",val,_fact_ids_for_value(req,m.group(1),val)))
    m=re.search(r"\bSize\s*[:：]\s*([-+]?\d+(?:\.\d+)?)\s*(MB|KB)?\s*(이하|미만|이상|초과)?",source,re.I)
    if not m:
        m=re.search(r"(?:크기(?:는|가)?\s*)([-+]?\d+(?:\.\d+)?)\s*(MB|KB)\s*(이하|미만|이상|초과)",source,re.I)
    size_prop=None
    if m:
        op={"이하":"<=","미만":"<","이상":">=","초과":">"}.get(m.group(3) or "","=")
        val=m.group(1)+(f" {m.group(2)}" if m.group(2) else "")
        size_prop=("Size",op,val,_fact_ids_for_value(req,m.group(1),val,"크기","Size"))

    cases=[]; idx=start_index
    grouped=[p for p in props if p[0] in {"Format","Resolution"}]
    if grouped:
        all_fids=list(dict.fromkeys(fid for p in grouped for fid in p[3]))
        case=_base_case(base,req,idx,kind="OUTPUT_ARTIFACT_PROPERTIES",title="저장 Format / Resolution 확인",objective="저장 산출물의 Format / Resolution이 Source 정의와 일치하는지 확인한다.",fids=all_fids or None)
        oval="\n".join(p[2] for p in grouped); ovar="\n".join(p[0] for p in grouped); ocmp="\n".join(p[1] for p in grouped)
        _set_structured_case_fields(
            case, objective="저장 산출물의 Format / Resolution이 Source 정의와 일치하는지 확인한다.",
            environment="처리/저장된 산출물 속성 확인 가능 환경", input_variable="처리 완료 산출물",input_compare="",input_value="",
            execution="Source-defined 처리/저장 동작 후 최종 산출물 속성을 확인한다.",output_variable=ovar,output_compare=ocmp,output_value=oval,
            expected_state=" / ".join(p[2] for p in grouped),pass_criterion="Format과 Resolution이 모두 Source 정의와 일치하면 PASS",
            field_fids={"input_value":[],"output_value":all_fids,"pass_criterion":all_fids},
        )
        case["test_vectors"]=[{"step":n+1,"output_variable":p[0],"output_compare":p[1],"expected_output":p[2],"source_fact_fragment_ids":p[3]} for n,p in enumerate(grouped)]
        case["split_decision"]="KEEP_AS_SHARED_ARTIFACT_OBJECTIVE"
        cases.append(case); idx+=1
    if size_prop:
        p=size_prop; fids=p[3]
        case=_base_case(base,req,idx,kind="OUTPUT_ARTIFACT_SIZE_CONSTRAINT",title="저장 이미지 크기 제한 확인",objective=f"저장 산출물의 크기가 Source 제한 {p[1]} {p[2]}를 만족하는지 확인한다.",fids=fids or None)
        _set_structured_case_fields(
            case, objective=f"저장 산출물의 크기가 Source 제한 {p[1]} {p[2]}를 만족하는지 확인한다.",
            environment="저장 산출물 파일 크기 측정 가능 환경",input_variable="저장 산출물",input_compare="측정",input_value="",
            execution="Source-defined 처리/저장 후 파일 크기를 측정한다.",output_variable="파일 크기",output_compare=p[1],output_value=p[2],
            expected_state=f"파일 크기 {p[1]} {p[2]}",pass_criterion=f"저장 산출물 파일 크기가 {p[1]} {p[2]}이면 PASS",
            field_fids={"input_value":[],"output_value":fids,"pass_criterion":fids},
        )
        case["test_vectors"]=[{"step":1,"output_variable":"파일 크기","output_compare":p[1],"expected_output":p[2],"source_fact_fragment_ids":fids}]
        case["split_decision"]="SPLIT_NUMERIC_CONSTRAINT"
        cases.append(case); idx+=1
    return cases,idx


def _fallback_case(req: dict[str,Any], base: dict[str,Any], idx: int) -> dict[str,Any]:
    title=_norm(req.get("function_name")) or "기본 기능 확인"
    case=_base_case(base,req,idx,kind="SOURCE_BACKED_FALLBACK",title=title,objective=f"{title}의 Source-backed 기본 동작을 확인한다.")
    pre_parts=[]
    for value in _list(req.get("preconditions")):
        if _norm(value): pre_parts.append(_norm(value))
    if _norm(req.get("activation_trigger")): pre_parts.append(_norm(req.get("activation_trigger")))
    expected=_norm(req.get("output") or req.get("acceptance_criteria"))
    base_fids=[str(x) for x in _list(base.get("source_fact_fragment_ids")) if str(x)]
    passc=_norm(req.get("acceptance_criteria")) if base_fids else ""
    _set_structured_case_fields(
        case, objective=f"{title}의 Source-backed 기본 동작을 확인한다.", precondition="\n".join(dict.fromkeys(pre_parts)),
        environment="", input_variable=_norm(base.get("variable")), input_compare=_norm(base.get("compare")), input_value=_norm(base.get("value")),
        execution=_norm(base.get("test_execution")) or _norm(req.get("processing_action")),
        expected_state=expected, pass_criterion=passc,
        field_fids={"input_value":base_fids if _norm(base.get("value")) else [], "pass_criterion":base_fids if passc else []},
    )
    case["test_preparation"]="\n".join(dict.fromkeys(pre_parts))
    case["expected_result"]=expected
    case["test_vectors"]=[]
    case["split_decision"]="REVIEW_FALLBACK" if case.get("human_review_required") else "KEEP_SINGLE_OBJECTIVE"
    return case


def build_basic_functional_cases(data: dict[str,Any], e2e_objective_cases: list[dict[str,Any]]) -> tuple[list[dict[str,Any]], list[dict[str,Any]], dict[str,Any]]:
    """Build Source-backed Basic Functional cases without EP/BVA/fault injection expansion.

    The function is intentionally conservative. It expands only relations that are literally recoverable
    from the Source-backed requirement/fact/evidence text. Undefined Invalid/Error reactions are routed to
    review, not converted into synthetic PASS/FAIL expectations.
    """
    reqs={str(r.get("srs_id") or ""):r for r in _list(data.get("requirements")) if isinstance(r,dict)}
    by_srs: dict[str,list[dict[str,Any]]] = defaultdict(list)
    for case in e2e_objective_cases:
        if isinstance(case,dict): by_srs[str(case.get("parent_srs_id") or "")].append(case)
    out=[]; reviews=[]; srs_expansion={}
    primary_types={"SWE6_TC","SYS5_CANDIDATE","ELECTRICAL_VERIFICATION_INTENT","ENVIRONMENTAL_VERIFICATION_INTENT","MECHANICAL_VERIFICATION_INTENT","MANUFACTURING_VERIFICATION_INTENT"}
    for sid, bases in by_srs.items():
        req=reqs.get(sid,{})
        primary=[b for b in bases if str(b.get("test_object_type") or "") in primary_types]
        review_only=[b for b in bases if b not in primary]
        produced=[]
        next_idx=1
        # Expand each primary scope independently so SYS.5/SWE.6 fact boundaries remain intact.
        for base in primary:
            base_fids={str(x) for x in _list(base.get("source_fact_fragment_ids")) if str(x)}
            local=[]
            source_reviews,blocking_fids=_blocking_source_reviews(req)
            reviews.extend(source_reviews)
            if base_fids and blocking_fids and base_fids.issubset(blocking_fids):
                produced.append(_review_only_case(base,req,next_idx,"해당 검증 범위의 Source Fact가 TBD/Conflict 상태입니다.")); next_idx+=1
                continue
            enum_cases, enum_reviews, next_idx=_enum_cases(req,base,next_idx)
            # If a parent has multiple primary verification scopes, never project a derived case
            # across a fact boundary without an exact fragment intersection.
            def _scope(items):
                if len(primary)>1 and base_fids:
                    return [c for c in items if set(str(x) for x in _list(c.get("source_fact_fragment_ids")) if str(x)) & base_fids]
                return items
            enum_cases=_scope(enum_cases)
            local.extend(enum_cases); reviews.extend(enum_reviews)
            occupied={fid for c in enum_cases for fid in _list(c.get("source_fact_fragment_ids")) if fid}

            conditional,next_idx=_conditional_cases(req,base,next_idx,occupied)
            conditional=_scope(conditional); local.extend(conditional)
            occupied.update(fid for c in conditional for fid in _list(c.get("source_fact_fragment_ids")) if fid)

            direct,next_idx=_direct_signal_output_cases(req,base,next_idx,occupied)
            direct=_scope(direct); local.extend(direct)
            occupied.update(fid for c in direct for fid in _list(c.get("source_fact_fragment_ids")) if fid)

            variant,next_idx=_variant_state_cases(req,base,next_idx,occupied)
            variant=_scope(variant); local.extend(variant)
            occupied.update(fid for c in variant for fid in _list(c.get("source_fact_fragment_ids")) if fid)

            # Exception/timeout is intentionally allowed to reuse the same fact as a normal path;
            # independent failure behavior is a separate Primary Objective in V0.92.
            timeout,next_idx=_timeout_exception_cases(req,base,next_idx,set())
            timeout=_scope(timeout); local.extend(timeout)

            transitions,next_idx=_state_transition_cases(req,base,next_idx,occupied)
            transitions=_scope(transitions); local.extend(transitions)
            occupied.update(fid for c in transitions for fid in _list(c.get("source_fact_fragment_ids")) if fid)

            decision_tables,next_idx=_pipe_decision_table_cases(req,base,next_idx)
            decision_tables=_scope(decision_tables); local.extend(decision_tables)

            dim,next_idx=_dimension_case(req,base,next_idx)
            dim=_scope(dim); local.extend(dim)
            props,next_idx=_artifact_property_case(req,base,next_idx)
            props=_scope(props); local.extend(props)

            if not local:
                local.append(_fallback_case(req,base,next_idx)); next_idx+=1
            # V0.92 exact per-field Source Fact trace gate: review-route, never synthesize provenance.
            for c in local:
                review_item=_trace_integrity_review(req,c)
                if review_item:
                    reviews.append(review_item)
            produced.extend(local)
        # Preserve review-only scopes when no executable primary represents them.
        if not primary:
            for n,base in enumerate(review_only,1):
                case=dict(base)
                case["test_design_mode"]="BASIC_FUNCTIONAL_REVIEW"
                case["basic_functional_tc_id"]=""
                out.append(case)
        else:
            # Parent/review objects remain related context on the generated functional cases.
            review_ids=[str(x.get("test_object_id") or "") for x in review_only if str(x.get("test_object_id") or "")]
            for case in produced:
                related=list(dict.fromkeys([str(x) for x in _list(case.get("related_test_object_ids")) if str(x)] + review_ids))
                case["related_test_object_ids"]=related
                out.append(case)
        srs_expansion[sid]={"objective_case_count":len(bases),"basic_functional_case_count":sum(1 for x in produced if str(x.get("test_design_mode") or "")==BASIC_FUNCTIONAL_MODE) if primary else 0,"review_only_case_count":sum(1 for x in produced if str(x.get("test_design_mode") or "")=="BASIC_FUNCTIONAL_REVIEW")}
    # Stable sequential human-facing TC ids, while evaluation IDs stay SRS-scoped.
    n=1
    for case in out:
        if str(case.get("test_design_mode") or "") == BASIC_FUNCTIONAL_MODE:
            case["basic_functional_tc_id"] = f"E2E_TC_{n:03d}"
            n+=1
    dedup_reviews=[]; seen_reviews=set()
    for item in reviews:
        key=(item.get("parent_srs_id"),item.get("review_type"),item.get("signal"),item.get("value"),item.get("meaning"))
        if key in seen_reviews: continue
        seen_reviews.add(key); dedup_reviews.append(item)
    reviews=dedup_reviews
    role_map={sid: classify_source_backed_facts(reqs.get(sid,{})) for sid in reqs}
    decision_examples=[]
    for case in out:
        if str(case.get("test_design_mode") or "") != BASIC_FUNCTIONAL_MODE:
            continue
        decision_examples.append({
            "decision_example_id":f"DEX-{len(decision_examples)+1:04d}",
            "parent_srs_id":str(case.get("parent_srs_id") or ""),
            "context":_norm(case.get("test_objective") or case.get("evaluation_name")),
            "ai_initial_decision":str(case.get("split_decision") or "KEEP_SINGLE_OBJECTIVE"),
            "user_final_decision":"",
            "user_comment":"",
            "test_case_id":str(case.get("basic_functional_tc_id") or ""),
            "source_fact_fragment_ids":[str(x) for x in _list(case.get("source_fact_fragment_ids")) if str(x)],
        })
    audit={
        "schema_version":"REQ-STUDIO-BASIC-FUNCTIONAL-DESIGN-0.92",
        "mode":BASIC_FUNCTIONAL_MODE,
        "basic_functional_case_count":sum(1 for x in out if str(x.get("test_design_mode") or "")==BASIC_FUNCTIONAL_MODE),
        "review_only_case_count":sum(1 for x in out if str(x.get("test_design_mode") or "")=="BASIC_FUNCTIONAL_REVIEW"),
        "review_item_count":len(reviews),
        "undefined_value_review_count":sum(1 for x in reviews if x.get("review_type")=="SOURCE_DEFINED_VALUE_WITHOUT_EXPECTED_BEHAVIOR"),
        "exact_field_trace_review_count":sum(1 for x in reviews if x.get("review_type")=="EXACT_FIELD_FACT_TRACE_REQUIRED"),
        "srs_expansion":srs_expansion,
        "fact_role_map":role_map,
        "decision_example_candidates":decision_examples,
        "guardrails":[
            "No EP/BVA/fault-injection expansion in V0.92 Basic Functional mode.",
            "Only Source-backed literal values/relations may populate Input/Output/Expected/PASS criteria.",
            "Invalid/Error/TBD/Conflict facts without Source-defined reaction remain review items, not synthetic PASS/FAIL cases.",
            "One Canonical SRS may produce multiple Primary Test Objectives without automatically splitting the Canonical SRS.",
            "Same objective + same execution flow may remain one TC with N vectors/steps; independent failure objectives are split.",
            "Every populated Input/Expected/PASS value must carry exact Source Fact Fragment trace or be review-routed.",
            "Decision Example Registry is captured for future V0.93 Guideline Mining; V0.92 does not auto-promote user examples into global rules.",
        ],
    }
    return out,reviews,audit
