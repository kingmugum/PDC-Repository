from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def _list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value in (None, "", {}):
        return []
    return [value]


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return ""
    if isinstance(value, list):
        return " ".join(str(x) for x in value if not isinstance(x, (dict, list)))
    return re.sub(r"\s+", " ", str(value)).strip()


def _blocks(compact_text: str) -> list[dict[str, str]]:
    pattern = re.compile(r"^\[SRC\s+([^|\]]+)\s*\|\s*([^|\]]+)\s*\|\s*([^\]]+)\]\s*$", re.MULTILINE)
    ms = list(pattern.finditer(compact_text or ""))
    out = []
    for i, m in enumerate(ms):
        text = (compact_text or "")[m.end():(ms[i + 1].start() if i + 1 < len(ms) else len(compact_text or ""))].strip()
        out.append({"chunk_id": m.group(1).strip(), "location": m.group(2).strip(), "kind": m.group(3).strip(), "text": text})
    return out


def _loc_key(v: str) -> tuple | None:
    t = _norm(v)
    m = re.search(r"Paragraph\s+(\d+)(?:\s*[-~]\s*(\d+))?", t, re.I)
    if m:
        return ("p", int(m.group(1)), int(m.group(2) or m.group(1)), None)
    m = re.search(r"Table\s+(\d+)\s*/\s*Row\s+(\d+)(?:\s*[-~]\s*(\d+))?", t, re.I)
    if m:
        return ("t", int(m.group(2)), int(m.group(3) or m.group(2)), int(m.group(1)))
    return None


def _loc_match(a: str, b: str) -> bool:
    ia, ib = _loc_key(a), _loc_key(b)
    if ia and ib and ia[0] == ib[0] and (ia[0] != "t" or ia[3] == ib[3]):
        return max(ia[1], ib[1]) <= min(ia[2], ib[2])
    na, nb = _norm(a).lower(), _norm(b).lower()
    return bool(na and nb and (na == nb or na in nb or nb in na))


def _tokens(text: str) -> set[str]:
    stop = {
        "한다", "하여야", "해야", "있다", "없다", "대한", "관련", "적용", "경우", "통해", "위한",
        "the", "and", "for", "with", "shall", "must", "from", "this", "that", "requirement",
    }
    return {
        x.lower() for x in re.findall(r"[A-Za-z0-9가-힣_.+-]+", _norm(text))
        if len(x) > 1 and x.lower() not in stop
    }


def _token_similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, min(len(ta), len(tb)))


def _numeric_tokens(text: str) -> set[str]:
    return {
        re.sub(r"\s+", "", x.lower())
        for x in re.findall(r"[-+]?\d+(?:\.\d+)?\s*(?:ms|msec|s|sec|초|v|mv|a|ma|%|℃|°c|bps|kbps|kbit/s|mbit/s|mm|cm)?", text or "", flags=re.I)
        if x.strip()
    }


def _numeric_compatible(a: str, b: str) -> bool:
    na, nb = _numeric_tokens(a), _numeric_tokens(b)
    if not na or not nb:
        return True
    return bool(na & nb)


def _looks_like_reference_only(text: str, location: str, kind: str) -> bool:
    t = f"{location} {kind} {text}".lower()
    if any(x in t for x in ["목차", "table of contents", "참조문서", "reference document", "그림 제목", "figure caption"]):
        return True
    # A row/list consisting mainly of external spec names/codes is review context rather than a requirement denominator.
    codes = re.findall(r"\b(?:ES|MS)\s*\d{4,}(?:[-_]\d+)?\b", text or "", flags=re.I)
    if codes and len(_tokens(text)) <= max(8, len(codes) * 4):
        return True
    return False


def _looks_like_heading_or_context(text: str, kind: str) -> bool:
    raw = _norm(text)
    if not raw:
        return True
    if len(raw) <= 60 and re.search(r"(?:목적|적용\s*범위|개요|관련\s*법규|관련\s*규격|시험\s*규격|참조\s*규격|시스템\s*구성|문서\s*정보)\s*$", raw, re.I):
        return True
    if str(kind).lower() in {"title", "heading", "caption"} and len(raw) <= 120:
        return True
    return False


def _has_requirement_force(text: str) -> bool:
    # Deliberately excludes nouns such as "제어기" and phrases such as "동작 전압".
    return bool(re.search(
        r"해야\s*한다|하여야\s*한다|할\s*것|하지\s*않아야|금지(?:한다|된다|되어야)?|"
        r"\d+(?:\.\d+)?\s*(?:ms|s|초|V|mV|A|mA|%|℃|mm)?\s*(?:이상|이하|초과|미만|이내)|"
        r"전환(?:한다|해야)|저장(?:한다|해야)|제어(?:한다|해야)|대기(?:한다|해야)|시도(?:한다|해야)|"
        r"복귀(?:한다|해야)|송신(?:한다|해야|금지)|수신(?:한다|해야)|시작(?:한다|해야)|중지(?:한다|해야)|"
        r"진입(?:한다|해야)|disable(?:d)?|enable(?:d)?|shall\b|must\b|within\b|not\s+exceed",
        text or "", re.I,
    ))


def _unit_type(text: str, location: str, kind: str) -> tuple[str, str]:
    if _looks_like_reference_only(text, location, kind) or _looks_like_heading_or_context(text, kind):
        return "reference_or_document_context", "review_context"
    strong = _has_requirement_force(text)
    # Tables often contain terse constraints (MAX 100mA, -40~85℃) without a normative verb.
    terse_constraint = bool(re.search(
        r"\bMAX\b|최대\s*(?:소비\s*)?전류|암전류|정격\s*전압|사용\s*온도|보존\s*온도|"
        r"커넥터|connector|lead[- ]?wire|\bdip\b|자동\s*납땜|납땜|solder|coating|코팅|핀\s*(?:간격|이격)|"
        r"\d+(?:\.\d+)?\s*(?:mm|mA|A|V|℃)\b|[-+]?\d+(?:\.\d+)?\s*[~～-]\s*[-+]?\d+(?:\.\d+)?\s*(?:V|℃)",
        text or "", re.I,
    ))
    return ("explicit_behavior_or_constraint" if (strong or terse_constraint) else "source_fact_or_description", "semantic_unit" if (strong or terse_constraint) else "review_context")


def build_semantic_source_units(compact_text: str) -> list[dict[str, Any]]:
    out = []
    for b in _blocks(compact_text):
        txt = _norm(b["text"])
        if not txt:
            continue
        fp = hashlib.sha256(f"{b['chunk_id']}|{b['location']}|{txt}".encode("utf-8", errors="ignore")).hexdigest()
        typ, elig = _unit_type(txt, b["location"], b["kind"])
        out.append({
            "source_semantic_unit_id": f"SRC-SEM-{fp[:12].upper()}",
            "source_chunk_id": b["chunk_id"],
            "source_location": b["location"],
            "source_kind": b["kind"],
            "source_excerpt_fingerprint": f"sha256:{fp}",
            "source_unit_type": typ,
            "source_excerpt": txt[:1200],
            "coverage_eligibility": elig,
            "linked_candidate_ids": [],
            "linked_srs_ids": [],
        })
    return out


def _req_text(req: dict[str, Any]) -> str:
    vals = [req.get(k) for k in ("function_name", "requirement", "activation_trigger", "preconditions", "processing_action", "output", "acceptance_criteria")]
    for ev in _list(req.get("source_evidence")):
        if isinstance(ev, dict):
            vals += [ev.get("location"), ev.get("text")]
    return _norm(vals).lower()


def _source_text(req: dict[str, Any]) -> str:
    vals = []
    for ev in _list(req.get("source_evidence")):
        if isinstance(ev, dict):
            vals.extend([ev.get("location"), ev.get("text")])
    return _norm(vals).lower() or _req_text(req)


def _allocation_for_text(source_text: str, generated_text: str = "") -> dict[str, str]:
    s = (source_text or "").lower()
    g = (generated_text or "").lower()
    combined = f"{s} {g}"

    sw = bool(re.search(r"\bsw\b|software|소프트웨어|\bmcu\b|eeprom|flash|watchdog|\btask\b|\bisr\b|algorithm", combined, re.I))
    connector = bool(re.search(r"커넥터|connector|lead[- ]?wire|\bdip\b|핀\s*(?:간격|이격)|pin\s*spacing|전원단\s*[+＋-]|단자", s, re.I))
    solder = bool(re.search(r"자동\s*납땜|납땜|solder", s, re.I))
    coating = bool(re.search(r"coating|코팅", s, re.I))
    env = bool(re.search(r"사용\s*온도|보존\s*온도|환경\s*시험|environmental|storage\s*temperature|operating\s*temperature|진동|습도", s, re.I))
    electrical_metric = bool(re.search(r"정격\s*전압|최대\s*소비\s*전류|암전류|rated\s*voltage|current\s*consumption|max(?:imum)?\s*current", s, re.I))
    external_ref = bool(re.search(r"따른다|참조한다|reference", s, re.I) and re.search(r"\b(?:ES|MS)\s*\d{4,}(?:[-_]\d+)?\b|규격|specification", s, re.I))
    multi_element = bool(re.search(r"\bmaster\b|\bslave\b|시스템|제어기|network|네트워크|\bcan\b|\blin\b|transceiver|obd", combined, re.I))
    active_behavior = _has_requirement_force(s) or bool(re.search(r"reset|check.?sum|복구", s, re.I))

    # High-confidence non-SW source domains take precedence unless the source explicitly assigns SW behavior.
    if (solder or coating) and not sw:
        return {
            "requirement_level": "Manufacturing Process",
            "allocation_status": "MANUFACTURING_PROCESS_REQUIREMENT",
            "swe1_eligibility": "Not Applicable",
            "swe6_eligibility": "Not Applicable",
            "verification_domain": "Manufacturing Process Verification",
            "allocation_rationale": "Source evidence is a soldering/coating/manufacturing-process constraint; software implementation responsibility is not indicated.",
        }
    if connector and not sw:
        return {
            "requirement_level": "Hardware/Mechanical",
            "allocation_status": "MECHANICAL_CONNECTOR_REQUIREMENT",
            "swe1_eligibility": "Not Applicable",
            "swe6_eligibility": "Not Applicable",
            "verification_domain": "Mechanical / Connector Verification",
            "allocation_rationale": "Source evidence is a physical connector/pin/spacing constraint; software implementation responsibility is not indicated.",
        }
    if env and not sw:
        return {
            "requirement_level": "Environmental Qualification",
            "allocation_status": "ENVIRONMENTAL_QUALIFICATION_REQUIREMENT",
            "swe1_eligibility": "Not Applicable",
            "swe6_eligibility": "Not Applicable",
            "verification_domain": "Environmental Qualification",
            "allocation_rationale": "Source evidence is an environmental/storage/qualification constraint; software implementation responsibility is not indicated.",
        }
    if electrical_metric and not sw:
        return {
            "requirement_level": "Electrical",
            "allocation_status": "ELECTRICAL_REQUIREMENT",
            "swe1_eligibility": "Not Applicable",
            "swe6_eligibility": "Not Applicable",
            "verification_domain": "Electrical Verification",
            "allocation_rationale": "Source evidence is an electrical performance/limit fact; software implementation responsibility is not indicated.",
        }
    if external_ref and not active_behavior:
        return {
            "requirement_level": "External Reference",
            "allocation_status": "EXTERNAL_STANDARD_REFERENCE",
            "swe1_eligibility": "Not Applicable",
            "swe6_eligibility": "Not Applicable",
            "verification_domain": "External Standard Evidence Required",
            "allocation_rationale": "Source delegates detailed criteria to an external specification; missing external contents are not invented.",
        }
    if multi_element and active_behavior and not sw:
        return {
            "requirement_level": "System",
            "allocation_status": "SYSTEM_REQUIREMENT_PENDING_SW_ALLOCATION",
            "swe1_eligibility": "Review Needed",
            "swe6_eligibility": "Deferred pending SW allocation",
            "verification_domain": "System Integration / SYS.5",
            "allocation_rationale": "Source states controller/system or multi-element behavior but does not explicitly allocate implementation responsibility to software.",
        }
    return {
        "requirement_level": "Software",
        "allocation_status": "SW_IMPLEMENTATION_REQUIREMENT",
        "swe1_eligibility": "Eligible",
        "swe6_eligibility": "Eligible",
        "verification_domain": "SWE.6 Software Qualification",
        "allocation_rationale": "No high-confidence non-software allocation evidence was found.",
    }


def apply_allocation_gate(req: dict[str, Any]) -> None:
    req.update(_allocation_for_text(_source_text(req), _req_text(req)))


def _best_semantic_matches(req: dict[str, Any], units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    pre_chunks = {str(x).strip() for x in _list(req.get("source_chunk_ids")) if str(x).strip()}
    if pre_chunks:
        for u in units:
            if str(u.get("source_chunk_id") or "") in pre_chunks:
                matched.append(u)

    evidence_items = [x for x in _list(req.get("source_evidence")) if isinstance(x, dict)]
    for ev in evidence_items:
        loc = _norm(ev.get("location"))
        txt = _norm(ev.get("text"))
        for u in units:
            score = 0.0
            excerpt = str(u.get("source_excerpt") or "")
            if loc and _loc_match(loc, str(u.get("source_location") or "")):
                score += 0.55
            if txt:
                low_txt, low_excerpt = txt.lower(), excerpt.lower()
                if low_txt in low_excerpt or (len(low_excerpt) > 25 and low_excerpt[:260] in low_txt):
                    score += 0.55
                else:
                    score += 0.45 * _token_similarity(txt, excerpt)
            if score >= 0.72 and _numeric_compatible(txt, excerpt) and u not in matched:
                matched.append(u)

    if matched:
        return matched

    # Last-resort deterministic fallback: choose only a unique high-similarity semantic unit.
    # This is intentionally conservative because generated Requirement wording is not Source evidence.
    req_source = " ".join(_norm(x.get("text")) for x in evidence_items if _norm(x.get("text")))
    req_anchor = req_source or _norm(req.get("requirement"))
    if not req_anchor:
        return []
    scored = []
    for u in units:
        excerpt = str(u.get("source_excerpt") or "")
        sim = _token_similarity(req_anchor, excerpt)
        if sim >= 0.72 and _numeric_compatible(req_anchor, excerpt):
            scored.append((sim, u))
    scored.sort(key=lambda x: x[0], reverse=True)
    if scored and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.12):
        return [scored[0][1]]
    return []


def _source_fact_object(unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_semantic_unit_id": unit.get("source_semantic_unit_id"),
        "source_chunk_id": unit.get("source_chunk_id"),
        "source_location": unit.get("source_location"),
        "source_fact": unit.get("source_excerpt"),
        "knowledge_state": "KNOWN",
    }


def attach_semantic_traceability(data: dict[str, Any], compact_text: str) -> None:
    units = build_semantic_source_units(compact_text)
    data["semantic_source_units"] = units
    reqs = [x for x in data.get("requirements", []) if isinstance(x, dict)]

    for req in reqs:
        req.setdefault("source_semantic_unit_ids", [])
        req.setdefault("source_chunk_ids", [])
        req.setdefault("source_backed_atomic_behaviors", [])
        req.setdefault("source_backed_facts", [])
        matched = _best_semantic_matches(req, units)

        for u in matched:
            uid = str(u["source_semantic_unit_id"])
            if uid not in req["source_semantic_unit_ids"]:
                req["source_semantic_unit_ids"].append(uid)
            if u["source_chunk_id"] not in req["source_chunk_ids"]:
                req["source_chunk_ids"].append(u["source_chunk_id"])
            cid, sid = str(req.get("candidate_id") or ""), str(req.get("srs_id") or "")
            if cid and cid not in u["linked_candidate_ids"]:
                u["linked_candidate_ids"].append(cid)
            if sid and sid not in u["linked_srs_ids"]:
                u["linked_srs_ids"].append(sid)

        apply_allocation_gate(req)
        eligibility = str(req.get("swe1_eligibility") or "Eligible")
        if eligibility != "Not Applicable" and not req.get("source_backed_atomic_behaviors"):
            for u in matched:
                if u.get("coverage_eligibility") != "semantic_unit":
                    continue
                req["source_backed_atomic_behaviors"].append({
                    "source_semantic_unit_id": u["source_semantic_unit_id"],
                    "source_chunk_id": u["source_chunk_id"],
                    "source_location": u["source_location"],
                    "behavior_text": u["source_excerpt"][:900],
                    "knowledge_state": "KNOWN",
                })
        if eligibility == "Not Applicable" and not req.get("source_backed_facts"):
            req["source_backed_facts"] = [_source_fact_object(u) for u in matched]

        if eligibility == "Eligible":
            complete = bool(req.get("source_semantic_unit_ids") and req.get("source_backed_atomic_behaviors"))
            req["semantic_provenance_status"] = "COMPLETE" if complete else "INCOMPLETE_REVIEW_REQUIRED"
        elif eligibility == "Review Needed":
            complete = bool(req.get("source_semantic_unit_ids") and (req.get("source_backed_atomic_behaviors") or req.get("source_backed_facts")))
            req["semantic_provenance_status"] = "COMPLETE" if complete else "INCOMPLETE_REVIEW_REQUIRED"
        else:
            complete = bool(req.get("source_semantic_unit_ids") and req.get("verification_domain"))
            req["semantic_provenance_status"] = "COMPLETE" if complete else "INCOMPLETE_REVIEW_REQUIRED"

    eligible = [u for u in units if u.get("coverage_eligibility") == "semantic_unit"]
    covered = [u for u in eligible if u.get("linked_candidate_ids") or u.get("linked_srs_ids")]
    dispositions = []
    counts: dict[str, int] = {}
    for u in eligible:
        linked = bool(u.get("linked_candidate_ids") or u.get("linked_srs_ids"))
        if linked:
            status = "COVERED_BY_CANONICAL"
            reason = "Semantic Source Unit is linked to at least one Canonical Requirement/SRS."
            linked_reqs = [r for r in reqs if str(r.get("candidate_id") or "") in u.get("linked_candidate_ids", []) or str(r.get("srs_id") or "") in u.get("linked_srs_ids", [])]
            exemplar = linked_reqs[0] if linked_reqs else {}
            level = str(exemplar.get("requirement_level") or "")
            allocation = str(exemplar.get("allocation_status") or "")
            domain = str(exemplar.get("verification_domain") or "")
        else:
            alloc = _allocation_for_text(str(u.get("source_excerpt") or ""), "")
            allocation = alloc["allocation_status"]
            level = alloc["requirement_level"]
            domain = alloc["verification_domain"]
            if allocation in {"HW_REQUIREMENT", "ELECTRICAL_REQUIREMENT", "MECHANICAL_CONNECTOR_REQUIREMENT", "MANUFACTURING_PROCESS_REQUIREMENT", "ENVIRONMENTAL_QUALIFICATION_REQUIREMENT"}:
                status = "NOT_SW_WITH_ALLOCATION_DECISION"
                reason = "Source unit is a high-confidence non-software constraint and is preserved outside SWE.1."
            elif allocation == "EXTERNAL_STANDARD_REFERENCE":
                status = "EXTERNAL_DEPENDENCY_ONLY"
                reason = "Source unit delegates detail to an external specification; missing external contents are not invented."
            elif allocation == "SYSTEM_REQUIREMENT_PENDING_SW_ALLOCATION":
                status = "REVIEW_NEEDED"
                reason = "System/multi-element behavior exists but no Canonical linkage or explicit software allocation was established."
            else:
                status = "SEMANTIC_MISSING_POTENTIAL_EXTRACTION_LOSS"
                reason = "Eligible source behavior/constraint has no Canonical linkage and requires extraction review."
        counts[status] = counts.get(status, 0) + 1
        dispositions.append({
            "source_semantic_unit_id": u.get("source_semantic_unit_id"),
            "source_chunk_id": u.get("source_chunk_id"),
            "source_location": u.get("source_location"),
            "source_excerpt": u.get("source_excerpt"),
            "source_unit_type": u.get("source_unit_type"),
            "coverage_eligibility": u.get("coverage_eligibility"),
            "linked_candidate_ids": list(u.get("linked_candidate_ids") or []),
            "linked_srs_ids": list(u.get("linked_srs_ids") or []),
            "disposition_status": status,
            "disposition_reason": reason,
            "requirement_level": level,
            "allocation_status": allocation,
            "verification_domain": domain,
        })

    uncovered = [x for x in dispositions if x.get("disposition_status") != "COVERED_BY_CANONICAL"]
    data["semantic_source_unit_coverage"] = {
        "eligible_unit_count": len(eligible),
        "covered_unit_count": len(covered),
        "coverage_percent": round(len(covered) / len(eligible) * 100, 2) if eligible else None,
        "dispositioned_unit_count": len(dispositions),
        "disposition_coverage_percent": 100.0 if eligible and len(dispositions) == len(eligible) else (None if not eligible else round(len(dispositions) / len(eligible) * 100, 2)),
        "uncovered_unit_count": len(uncovered),
        "uncovered_unit_records": uncovered,
        "disposition_records": dispositions,
        "disposition_counts": counts,
        "scope_note": "Only source units classified as behavior/constraint candidates are in the denominator. Every eligible unit receives an auditable disposition even when not linked to a Canonical Requirement.",
    }

    provenance_rows = []
    for req in reqs:
        eligibility = str(req.get("swe1_eligibility") or "Eligible")
        missing = []
        if not req.get("source_requirement_ids"):
            if not req.get("source_semantic_unit_ids"):
                missing.append("source_semantic_unit_ids")
            if eligibility == "Eligible" and not req.get("source_backed_atomic_behaviors"):
                missing.append("source_backed_atomic_behaviors")
            elif eligibility == "Review Needed" and not (req.get("source_backed_atomic_behaviors") or req.get("source_backed_facts")):
                missing.append("source_backed_behavior_or_fact")
            elif eligibility == "Not Applicable" and not req.get("verification_domain"):
                missing.append("verification_domain")
        provenance_rows.append({
            "candidate_id": req.get("candidate_id"),
            "srs_id": req.get("srs_id"),
            "swe1_eligibility": eligibility,
            "semantic_provenance_status": req.get("semantic_provenance_status"),
            "missing_fields": missing,
        })
    blocking = [x for x in provenance_rows if x["missing_fields"] and x["swe1_eligibility"] == "Eligible"]
    review = [x for x in provenance_rows if x["missing_fields"] and x["swe1_eligibility"] != "Eligible"]
    data["semantic_provenance_audit"] = {
        "passed": not blocking,
        "blocking_incomplete_count": len(blocking),
        "review_incomplete_count": len(review),
        "blocking_records": blocking,
        "review_records": review,
        "scope_note": "No-ID SWE.1 Eligible items require semantic source units plus source-backed atomic behavior. Pending/Not-SW items preserve source provenance without forcing software behavior.",
    }
    data["semantic_source_unit_classifier_audit"] = {
        "total_unit_count": len(units),
        "semantic_eligible_count": len(eligible),
        "review_context_count": len(units) - len(eligible),
        "by_unit_type": {k: sum(1 for u in units if u.get("source_unit_type") == k) for k in sorted({str(u.get("source_unit_type") or "") for u in units})},
        "ground_truth_precision_recall": None,
        "scope_note": "Classifier counts are observable QA statistics only. False-positive/false-negative rates are not claimed without a human-labelled source-unit Gold set.",
    }


def apply_coverage_mode(data: dict[str, Any]) -> None:
    cov = data.get("source_coverage") if isinstance(data.get("source_coverage"), dict) else {}
    sem = data.get("semantic_source_unit_coverage") or {}
    if int(cov.get("explicit_source_requirement_occurrence_count") or 0) == 0:
        cov.update({
            "coverage_validity": "NOT_APPLICABLE",
            "coverage_validity_reason": "No supported explicit requirement identifiers were found.",
            "coverage_mode": "EXPLICIT_ID_COVERAGE_NOT_APPLICABLE",
            "weighted_source_coverage_percent": None,
            "disposition_coverage_percent": None,
            "missing_count": None,
            "actual_missing_behavior_count": None,
            "actual_missing_behavior_disposition_count": None,
            "actual_missing_behavior_evaluation_status": "NOT_EVALUATED",
            "actual_missing_behavior_release_blocking": False,
            "coverage_scope": "Explicit-ID-only coverage unavailable for this source.",
            "recommended_next_mode": "SEMANTIC_SOURCE_UNIT_COVERAGE_AVAILABLE" if sem.get("eligible_unit_count") else "SEMANTIC_SOURCE_UNIT_COVERAGE_PENDING",
            "semantic_source_unit_coverage": sem,
        })
    else:
        cov["coverage_mode"] = "EXPLICIT_ID_COVERAGE_AVAILABLE"
        cov["semantic_source_unit_coverage"] = sem
    data["source_coverage"] = cov


def normalize_external_dependencies(data: dict[str, Any]) -> None:
    for req in [x for x in data.get("requirements", []) if isinstance(x, dict)]:
        out = []
        seen = set()
        for item in _list(req.get("external_dependencies")):
            if isinstance(item, dict):
                name = _norm(item.get("name") or item.get("document") or item.get("artifact"))
                purpose = _norm(item.get("purpose") or item.get("reason"))
                typ = _norm(item.get("type")) or "external_document"
                ev = _list(item.get("source_evidence")) or _list(req.get("source_evidence"))
                ks = _norm(item.get("knowledge_state")) or "KNOWN"
                required = _list(item.get("required_for"))
            else:
                name = _norm(item)
                purpose = ""
                typ = "external_document"
                ev = _list(req.get("source_evidence"))
                ks = "KNOWN"
                required = []
            if not name and not purpose:
                continue
            key = (typ.lower(), name.lower(), purpose.lower())
            if key in seen:
                continue
            seen.add(key)
            out.append({"type": typ, "name": name, "purpose": purpose, "knowledge_state": ks, "source_evidence": ev, "required_for": required})
        req["external_dependencies"] = out


def dedupe_and_scope_gaps(data: dict[str, Any]) -> None:
    req_count = len([x for x in data.get("requirements", []) if isinstance(x, dict)])
    merged = {}
    for gap in [x for x in data.get("gaps", []) if isinstance(x, dict)]:
        g = json.loads(json.dumps(gap, ensure_ascii=False, default=str))
        text = _norm(g.get("message") or g.get("description") or g.get("reason") or g.get("title") or g.get("missing_information") or g.get("gap"))
        relc = list(dict.fromkeys(str(x) for x in _list(g.get("related_candidate_ids")) if str(x)))
        rels = list(dict.fromkeys(str(x) for x in _list(g.get("related_srs_ids")) if str(x)))
        exact = bool(_list(g.get("related_source_requirement_ids")) or _list(g.get("related_source_occurrence_ids")))
        broad = bool(req_count and len(relc) > max(8, int(req_count * 0.35)) and not exact)
        doc_hint = bool(re.search(r"목차|table of contents|참조문서\s*목록|reference document list|문서\s*전체|빈\s*표|그림\s*제목|figure", text, re.I))
        scope = "document" if doc_hint else ("requirement" if exact else ("section" if (relc or rels or not broad) else "document"))
        g["gap_scope"] = scope
        if scope == "document":
            g["related_candidate_ids"] = []
            g["related_srs_ids"] = []
            g["document_context_link"] = {"scope": "document", "reason": "Document-level information gap is not fanned out to every Requirement."}
        norm_issue = re.sub(r"\s+", " ", text.lower()).strip()[:260]
        key = (str(g.get("gap_type") or g.get("type") or "gap").lower(), scope, str(g.get("missing_information_type") or "").lower(), norm_issue)
        if key not in merged:
            merged[key] = g
        else:
            m = merged[key]
            for f in ("related_candidate_ids", "related_srs_ids", "related_source_requirement_ids", "related_source_occurrence_ids"):
                m[f] = list(dict.fromkeys(_list(m.get(f)) + _list(g.get(f))))
    out = list(merged.values())
    for i, g in enumerate(out, 1):
        g["gap_id"] = f"GAP_{i:03d}"
    data["gaps"] = out


def filter_gap_links_by_scope(data: dict[str, Any]) -> None:
    """Prevent broad post-enrichment fan-out from violating the declared gap scope."""
    reqs = [x for x in data.get("requirements", []) if isinstance(x, dict)]
    by_cid = {str(r.get("candidate_id") or ""): r for r in reqs}
    by_sid = {str(r.get("srs_id") or ""): r for r in reqs}
    n = len(reqs)

    def req_matches_gap(req: dict[str, Any], gap: dict[str, Any]) -> bool:
        gap_ev = [x for x in _list(gap.get("source_evidence")) if isinstance(x, dict)]
        req_ev = [x for x in _list(req.get("source_evidence")) if isinstance(x, dict)]
        for ge in gap_ev:
            gloc = _norm(ge.get("location"))
            if gloc and any(_loc_match(gloc, _norm(rev.get("location"))) for rev in req_ev):
                return True
        hay = " ".join(_norm(gap.get(k)) for k in ("description", "gap", "reason", "detail", "missing_information", "title"))
        req_hay = " ".join([_source_text(req), _req_text(req), _norm(req.get("external_dependencies"))])
        sim = _token_similarity(hay, req_hay)
        if sim >= 0.34:
            return True
        # Exact external specification / signal-like tokens are deterministic anchors.
        anchors = set(re.findall(r"\b(?:ES|MS)\s*\d{4,}(?:[-_]\d+)?\b|\b[A-Za-z][A-Za-z0-9_]{3,}\b", hay, flags=re.I))
        if anchors and any(a.lower() in req_hay.lower() for a in anchors):
            return True
        return False

    for gap in [x for x in data.get("gaps", []) if isinstance(x, dict)]:
        scope = str(gap.get("gap_scope") or "section")
        if scope == "document":
            gap["related_candidate_ids"] = []
            gap["related_srs_ids"] = []
            gap["document_context_link"] = {"scope": "document", "reason": "Document-level gap is retained as context only."}
            continue
        cids = [str(x) for x in _list(gap.get("related_candidate_ids")) if str(x)]
        sids = [str(x) for x in _list(gap.get("related_srs_ids")) if str(x)]
        broad = bool(n and max(len(set(cids)), len(set(sids))) > max(6, int(n * 0.35)))
        if scope != "section" or not broad:
            continue
        kept_cids = [cid for cid in dict.fromkeys(cids) if cid in by_cid and req_matches_gap(by_cid[cid], gap)]
        kept_sids = [sid for sid in dict.fromkeys(sids) if sid in by_sid and req_matches_gap(by_sid[sid], gap)]
        # Keep candidate/SRS pairs synchronized.
        for cid in kept_cids:
            sid = str(by_cid[cid].get("srs_id") or "")
            if sid and sid not in kept_sids:
                kept_sids.append(sid)
        for sid in kept_sids:
            cid = str(by_sid[sid].get("candidate_id") or "")
            if cid and cid not in kept_cids:
                kept_cids.append(cid)
        gap["related_candidate_ids"] = kept_cids
        gap["related_srs_ids"] = kept_sids
        if not kept_cids and not kept_sids:
            gap["section_context_link"] = {"scope": "section", "reason": "Broad section gap had no deterministic Requirement anchor after scope filtering."}


def _ambiguous_value_relations(source_text: str) -> list[dict[str, Any]]:
    text = _norm(source_text)
    out = []
    # Literal MAX is preserved as written rather than silently converted into <=.
    for m in re.finditer(r"\bMAX\s*([-+]?\d+(?:\.\d+)?)\s*(mA|A|mV|V|ms|s|℃|mm|%)?", text, re.I):
        literal = m.group(0).strip()
        out.append({
            "source_value_text": literal,
            "normalized_value": f"{m.group(1)}{m.group(2) or ''}",
            "relation": "SOURCE_LITERAL_MAX",
            "relation_confirmed": False,
            "clarification": "Source uses the literal 'MAX'; the formal acceptance comparator and measurement conditions require confirmation.",
        })
    # Label : value without an explicit comparator is ambiguous target/limit semantics.
    for m in re.finditer(r"([^\n|:：]{2,36})\s*[:：]\s*([-+]?\d+(?:\.\d+)?)\s*(mA|A|mV|V|ms|s|℃|mm|%)\b", text, re.I):
        prefix = m.group(1).strip()
        if re.search(r"이상|이하|초과|미만|<=|>=|<|>", m.group(0)):
            continue
        literal = m.group(0).strip()
        if any(x.get("source_value_text") == literal for x in out):
            continue
        out.append({
            "source_value_text": literal,
            "normalized_value": f"{m.group(2)}{m.group(3)}",
            "relation": "UNSPECIFIED_LIMIT_OR_TARGET",
            "relation_confirmed": False,
            "clarification": f"Source states '{prefix}' with a value but does not explicitly define equality/upper/lower-limit semantics.",
        })
    return out


def _generated_strengthens_relation(text: str, value: str) -> bool:
    if not text or not value:
        return False
    number = re.escape(re.match(r"[-+]?\d+(?:\.\d+)?", value).group(0)) if re.match(r"[-+]?\d+(?:\.\d+)?", value) else re.escape(value)
    return bool(re.search(rf"{number}\s*(?:mA|A|mV|V|ms|s|℃|mm|%)?\s*(?:이하|이상|초과|미만|이어야\s*한다|여야\s*한다)|(?:<=|>=|<|>)\s*{number}", text, re.I))


def preserve_numeric_relation_semantics(data: dict[str, Any]) -> None:
    for req in [x for x in data.get("requirements", []) if isinstance(x, dict)]:
        src = "\n".join(_norm(ev.get("text")) for ev in _list(req.get("source_evidence")) if isinstance(ev, dict) and _norm(ev.get("text")))
        relations = _ambiguous_value_relations(src)
        req["value_relation_status"] = relations
        if not relations:
            req["normative_strength_status"] = "SOURCE_RELATION_EXPLICIT_OR_NOT_NUMERIC"
            continue
        strengthened = []
        for rel in relations:
            value = str(rel.get("normalized_value") or "")
            bad_fields = [k for k in ("requirement", "acceptance_criteria") if _generated_strengthens_relation(_norm(req.get(k)), value)]
            if bad_fields:
                strengthened.append({"value": value, "fields": bad_fields, "source_value_text": rel.get("source_value_text")})
        if strengthened:
            req["normative_strength_status"] = "SOURCE_RELATION_AMBIGUOUS_GENERATED_STRENGTHENING_REMOVED"
            clar = _list(req.get("clarification_needed"))
            for rel in relations:
                c = str(rel.get("clarification") or "")
                if c and c not in clar:
                    clar.append(c)
            req["clarification_needed"] = clar
            # For terse numeric facts, keep the Source literal instead of asserting an invented comparator/equality.
            if len(src) <= 260:
                req["requirement"] = f"Source 표기 보존: {src}"
                req["acceptance_criteria"] = "Source에 공식 비교 관계/허용 기준이 명시되지 않아 확인이 필요하다."
            req["normative_strength_findings"] = strengthened
        else:
            req["normative_strength_status"] = "SOURCE_RELATION_AMBIGUOUS_PRESERVED"
            req["normative_strength_findings"] = []
