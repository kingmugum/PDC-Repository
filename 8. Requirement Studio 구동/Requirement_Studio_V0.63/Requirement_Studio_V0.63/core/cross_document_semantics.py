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


def _external_reference_codes(text: str) -> list[str]:
    # Includes forms such as ES95400-30 and MS201-02.
    return re.findall(r"\b(?:ES|MS)\s*\d{3,}(?:[-_]\d+)?\b", text or "", flags=re.I)


def _looks_like_revision_metadata(text: str, location: str = "", kind: str = "") -> bool:
    raw = _norm(text)
    hay = f"{_norm(location)} {_norm(kind)} {raw}".lower()
    if any(x in hay for x in ("change history", "revision history", "변경 이력", "변경이력", "개정 이력", "개정이력", "발행 이력", "문서 이력")):
        return True
    # A dated/versioned publication row is metadata, not a behavior/constraint.
    date_like = bool(re.search(r"\b20\d{2}[./-]\d{1,2}(?:[./-]\d{1,2})?\b|\bV?\d+(?:\.\d+){1,3}\b", raw, re.I))
    release_like = bool(re.search(r"차종\s*사양서\s*발행|발행|개정|revision|rev\.?\s*\d", raw, re.I))
    return bool(len(raw) <= 220 and date_like and release_like)


def _strip_structural_prefix(text: str) -> str:
    """Remove table-row ordinals / section-number prefixes without changing requirement content.

    This is used only for structural classification (heading/reference-row detection), never to
    rewrite Source evidence.  It lets normalized rows such as ``31 | MS201-02 | ...`` and
    headings such as ``5.4.2.1 커넥터 타입`` be classified generically.
    """
    raw = _norm(text)
    raw = re.sub(r"^\s*\d{1,4}\s*[|｜]\s*", "", raw)
    raw = re.sub(r"^\s*\d+(?:\.\d+){1,6}\.?\s+", "", raw)
    return raw.strip()


def _looks_like_external_reference_only(text: str, location: str = "", kind: str = "") -> bool:
    raw_original = _norm(text)
    raw = _strip_structural_prefix(raw_original)
    codes = _external_reference_codes(raw)
    if not codes:
        return False
    # Typical reference-list rows are "CODE | standard title". Words such as
    # "금지" may be part of the title itself and must not turn the external
    # document name into an in-document software requirement.
    if re.match(r"^\s*(?:ES|MS)\s*\d{3,}(?:[-_]\d+)?\s*[|｜]", raw, re.I):
        tail = re.split(r"[|｜]", raw, maxsplit=1)[1] if re.search(r"[|｜]", raw) else ""
        if not re.search(r"[-+]?\d+(?:\.\d+)?\s*(?:ms|s|V|mV|A|mA|%|℃|mm)\b|해야\s*한다|하여야\s*한다|shall\b|must\b", tail, re.I):
            return True
    # A terse row that starts with a standard identifier and then only names the
    # external document is reference context even when the title contains nouns such
    # as "금지".  Do not import normative force from the external standard title.
    start = re.match(r"^\s*((?:ES|MS)\s*\d{3,}(?:[-_]\d+)?)\s*(?:[|｜:\-]\s*)?(.*)$", raw, re.I)
    if start:
        tail = _norm(start.group(2))
        explicit_body = bool(re.search(
            r"해야\s*한다|하여야\s*한다|할\s*것|한다(?:\.|$)|되어야|"
            r"[-+]?\d+(?:\.\d+)?\s*(?:ms|s|초|V|mV|A|mA|%|℃|mm)\b|"
            r"(?:이상|이하|초과|미만|이내)|shall\b|must\b|within\b|not\s+exceed",
            tail, re.I,
        ))
        if tail and len(tail) <= 180 and not explicit_body:
            return True

    # A standard-code/name row remains reference context unless the row itself contains
    # an enforceable condition/value/behavior. Do not infer the external document body.
    normative = bool(re.search(
        r"해야\s*한다|하여야\s*한다|할\s*것|금지(?:한다|된다|되어야)?|"
        r"\d+(?:\.\d+)?\s*(?:ms|s|초|V|mV|A|mA|%|℃|mm)?\s*(?:이상|이하|초과|미만|이내)|"
        r"전환(?:한다|해야)|저장(?:한다|해야)|제어(?:한다|해야)|송신(?:한다|해야|금지)|"
        r"shall\b|must\b|within\b|not\s+exceed",
        raw, re.I,
    ))
    terse_numeric = bool(re.search(r"\bMAX\b|[-+]?\d+(?:\.\d+)?\s*(?:mA|A|V|℃|mm)\b", raw, re.I))
    return not (normative or terse_numeric)


def _looks_like_reference_only(text: str, location: str, kind: str) -> bool:
    t = f"{location} {kind} {text}".lower()
    if any(x in t for x in ["목차", "table of contents", "참조문서", "reference document", "그림 제목", "figure caption"]):
        return True
    if _looks_like_revision_metadata(text, location, kind):
        return True
    if _looks_like_external_reference_only(text, location, kind):
        return True
    return False


def _looks_like_heading_or_context(text: str, kind: str) -> bool:
    raw = _strip_structural_prefix(text)
    # PDF/DOCX normalization can append a page number to a short heading.
    # Strip that pagination suffix only for structural classification.
    raw = re.sub(r"\s+\d{1,4}\s*$", "", raw).strip()
    if not raw:
        return True
    if len(raw) <= 60 and re.search(r"(?:목적|적용\s*범위|개요|관련\s*법규|관련\s*규격|시험\s*규격|참조\s*규격|시스템\s*구성|문서\s*정보)\s*$", raw, re.I):
        return True
    if str(kind).lower() in {"title", "heading", "caption"} and len(raw) <= 120:
        return True
    # Normalized DOCX/PDF streams frequently lose the original Heading style.  Short
    # section/figure labels must remain context even when they contain engineering nouns
    # such as connector/soldering that are also valid requirement-domain keywords.
    if len(raw) <= 100 and not re.search(r"[-+]?\d+(?:\.\d+)?\s*(?:ms|s|초|V|mV|A|mA|%|℃|mm)\b", raw, re.I):
        if re.match(r"^(?:그림|figure)\s*\d+", raw, re.I):
            return True
        if re.search(
            r"(?:사양(?:\s*및\s*[^.]{1,35})?|타입|type|방식|구성|배치|거리|간격|이격|"
            r"납땜\s*방식|connector\s*(?:specification|type)?|커넥터\s*(?:사양|타입|납땜방식|단자간\s*거리))$",
            raw, re.I,
        ) and not re.search(r"해야|하여야|한다|금지(?:한다|된다|되어야)|shall\b|must\b|이상|이하|초과|미만|MAX", raw, re.I):
            return True
    # Document normalizers do not always preserve heading kind. Short title-like
    # blocks without a value or normative predicate are context, not coverage units.
    if len(raw) <= 70 and not re.search(r"\d", raw) and not re.search(
        r"해야|하여야|할\s*것|금지|적용한다|전환한다|저장한다|제어한다|송신한다|수신한다|"
        r"이상|이하|초과|미만|MAX|shall\b|must\b", raw, re.I
    ) and re.search(
        r"(?:사양|구성|요구사항|시험|규격|인터페이스|커넥터|connector(?:\s*type)?|핀\s*배치|도면|figure|그림)\s*$",
        raw, re.I,
    ):
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


def _looks_like_governance_or_matrix_context(text: str, location: str = "", kind: str = "") -> str | None:
    """Classify non-behavior document governance/table-header rows without discarding them.

    V0.63 keeps parameter/interface/variant guidance auditable as review context instead of
    counting it as a behavior/constraint denominator.  The rule is structural and never keys on
    a document name, SRS ID, parameter name, or standard number.
    """
    raw = _strip_structural_prefix(text)
    low = raw.lower()
    if not raw:
        return "heading_or_document_context"
    # Matrix/header rows: column labels, not enforceable behavior.
    if "|" in raw or "｜" in raw:
        cells = [c.strip() for c in re.split(r"[|｜]", raw) if c.strip()]
        header_terms = {"element", "최신 버전", "차종", "variant", "세부 기능", "기능", "적용 차종", "version"}
        if cells and sum(1 for c in cells if c.lower() in header_terms or any(t in c.lower() for t in header_terms)) >= max(2, len(cells)//2):
            return "variant_matrix_header"
    # Appendix / implementation guidance that tells the integrator to configure items by vehicle
    # rather than defining the actual value/behavior in this source.
    if re.search(r"차종.{0,30}(?:parameter|파라미터).{0,30}(?:설정|선정)|(?:parameter|파라미터).{0,30}차종", raw, re.I):
        return "parameter_governance_context"
    if re.search(r"차종.{0,30}(?:signal|시그널|신호).{0,30}(?:설정|선정)|(?:signal|시그널|신호).{0,30}차종", raw, re.I):
        return "interface_governance_context"
    if re.search(r"(?:appendix|부록).{0,60}(?:참고|안내|설정)|(?:참고|안내).{0,60}(?:appendix|부록)", raw, re.I):
        return "appendix_guidance_context"
    return None


def _unit_type(text: str, location: str, kind: str) -> tuple[str, str]:
    governance_type = _looks_like_governance_or_matrix_context(text, location, kind)
    if governance_type:
        return governance_type, "review_context"
    if _looks_like_revision_metadata(text, location, kind):
        return "revision_history_context", "review_context"
    if _looks_like_external_reference_only(text, location, kind):
        return "external_reference_only", "review_context"
    if _looks_like_heading_or_context(text, kind):
        return "heading_or_document_context", "review_context"
    if _looks_like_reference_only(text, location, kind):
        return "reference_or_document_context", "review_context"
    # Terse interface configuration facts (bitrate/NM support) are allocation-review
    # context until software ownership is proven. They are not extraction-loss candidates.
    if re.search(
        r"(?:\bCAN\b|\bLIN\b|\bEthernet\b|\bFlexRay\b).*?(?:kbit/s|kbps|mbit/s|mbps|baud|bitrate|\bNM\b\s*(?:지원|support))|"
        r"(?:kbit/s|kbps|mbit/s|mbps|baud|bitrate).*?(?:\bCAN\b|\bLIN\b|\bEthernet\b|\bFlexRay\b)",
        text or "", re.I,
    ) and not _has_requirement_force(text):
        return "interface_fact", "allocation_review_context"
    strong = _has_requirement_force(text)
    # Tables often contain terse constraints (MAX 100mA, -40~85℃) without a normative verb.
    terse_constraint = bool(re.search(
        r"\bMAX\b|최대\s*(?:소비\s*)?전류|암전류|정격\s*전압|사용\s*온도|보존\s*온도|"
        r"커넥터|connector|lead[- ]?wire|\bdip\b|자동\s*납땜|납땜|solder|coating|코팅|핀\s*(?:간격|이격)|"
        r"\b(?:Input|Output|Par|Param|Parameter)_[A-Za-z0-9_]+\b|"
        r"\d+(?:\.\d+)?\s*(?:ms|s|초|mm|mA|A|V|%|℃|회|kbit/s|kbps)\b|[-+]?\d+(?:\.\d+)?\s*[~～-]\s*[-+]?\d+(?:\.\d+)?\s*(?:V|℃|%|ms|s)",
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


def _source_fact_fragments_for_unit(unit: dict[str, Any]) -> list[dict[str, Any]]:
    """Split a compound Semantic Source Unit into stable clause-level fact fragments.

    Fragmentation is conservative: sentence/newline/bullet boundaries only. It does not
    rewrite the Source or infer missing conjunction semantics. The parent Semantic Unit remains
    the stable document anchor; fragments provide ownership when different SRS use different
    clauses from the same paragraph/table cell.
    """
    raw = str(unit.get("source_excerpt") or "").strip()
    if not raw:
        return []
    parts = [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+|\s*[•·▪◦]\s*", raw) if x and x.strip()]
    if not parts:
        parts = [raw]
    out = []
    for idx, text in enumerate(parts, 1):
        # Ignore punctuation-only / tiny fragments created by normalization.
        if len(re.sub(r"\W+", "", text, flags=re.UNICODE)) < 3:
            continue
        uid = str(unit.get("source_semantic_unit_id") or "")
        fid = hashlib.sha256(f"{uid}|{idx}|{text}".encode("utf-8", errors="ignore")).hexdigest()[:12].upper()
        out.append({
            "source_fact_fragment_id": f"SRC-FRAG-{fid}",
            "parent_source_semantic_unit_id": uid,
            "source_chunk_id": unit.get("source_chunk_id"),
            "source_location": unit.get("source_location"),
            "source_kind": unit.get("source_kind"),
            "source_excerpt": text,
            "fragment_index": idx,
            "knowledge_state": "KNOWN",
        })
    return out or [{
        "source_fact_fragment_id": f"SRC-FRAG-{hashlib.sha256(raw.encode('utf-8', errors='ignore')).hexdigest()[:12].upper()}",
        "parent_source_semantic_unit_id": str(unit.get("source_semantic_unit_id") or ""),
        "source_chunk_id": unit.get("source_chunk_id"),
        "source_location": unit.get("source_location"),
        "source_kind": unit.get("source_kind"),
        "source_excerpt": raw,
        "fragment_index": 1,
        "knowledge_state": "KNOWN",
    }]


def _fragments_for_requirement(req: dict[str, Any], matched_units: list[dict[str, Any]], fragment_index: list[dict[str, Any]]) -> list[dict[str, Any]]:
    req_text = " ".join([_req_text(req), _source_text(req)])
    matched_unit_ids = {str(u.get("source_semantic_unit_id") or "") for u in matched_units}
    candidates = [f for f in fragment_index if str(f.get("parent_source_semantic_unit_id") or "") in matched_unit_ids]
    selected = []
    for f in candidates:
        txt = str(f.get("source_excerpt") or "")
        score = _token_similarity(txt, req_text)
        if score >= 0.34 and _numeric_compatible(txt, req_text):
            item = dict(f)
            item["ownership_match_score"] = round(score, 3)
            selected.append(item)
    if selected:
        # Keep all materially matching clauses, ordered as in Source.
        selected.sort(key=lambda x: (str(x.get("source_location") or ""), int(x.get("fragment_index") or 0)))
        return selected
    # A single-clause unit can safely remain owned as a whole; a compound unit without a
    # deterministic clause match is left unresolved instead of being copied wholesale.
    by_unit = {}
    for f in candidates:
        by_unit.setdefault(str(f.get("parent_source_semantic_unit_id") or ""), []).append(f)
    fallback = []
    for uid, group in by_unit.items():
        if len(group) == 1:
            item = dict(group[0]); item["ownership_match_score"] = 1.0
            fallback.append(item)
    return fallback


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

    # Interface facts such as bus bitrate or network-management support do not, by
    # themselves, prove that application software owns the configuration.  Preserve
    # the fact but hold SWE.1/SWE.6 allocation until explicit SW responsibility is
    # available.  This is intentionally generic and does not key on any SRS/document ID.
    interface_fact = bool(re.search(
        r"(?:\bCAN\b|\bLIN\b|\bEthernet\b|\bFlexRay\b).*?(?:kbit/s|kbps|mbit/s|mbps|baud|bitrate|\bNM\b\s*(?:지원|support))|"
        r"(?:kbit/s|kbps|mbit/s|mbps|baud|bitrate).*?(?:\bCAN\b|\bLIN\b|\bEthernet\b|\bFlexRay\b)",
        s, re.I,
    ))
    explicit_sw_allocation = bool(re.search(
        r"(?:software|소프트웨어|\bSW\b).{0,60}(?:설정|구성|담당|책임|지원|configure|configuration|implement)|"
        r"(?:설정|구성|담당|책임|configure|configuration|implement).{0,60}(?:software|소프트웨어|\bSW\b)",
        s, re.I,
    ))
    if interface_fact and not active_behavior and not explicit_sw_allocation:
        return {
            "requirement_level": "System / Interface Fact",
            "allocation_status": "INTERFACE_FACT_PENDING_SW_ALLOCATION",
            "swe1_eligibility": "Review Needed",
            "swe6_eligibility": "Deferred pending SW allocation",
            "verification_domain": "System Integration / Interface Allocation Review",
            "allocation_rationale": "Source provides an interface/configuration fact, but explicit software implementation responsibility is not confirmed.",
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


def _explicit_sw_allocation_evidence(text: str) -> list[str]:
    raw = _norm(text)
    findings = []
    patterns = [
        r"(?:software|소프트웨어|\bSW\b).{0,80}(?:담당|책임|구현|설정|구성|제어|configure|implement)",
        r"(?:담당|책임|구현|설정|구성|configure|implement).{0,80}(?:software|소프트웨어|\bSW\b)",
    ]
    for pat in patterns:
        m = re.search(pat, raw, re.I)
        if m:
            findings.append(m.group(0).strip())
    return list(dict.fromkeys(findings))


def _structured_source_facts(text: str, *, unit_id: str = "", location: str = "") -> list[dict[str, Any]]:
    """Extract conservative Source fact objects for trace/audit and table joins.

    These records never create a requirement or test value.  They merely structure literal facts
    already present in a linked Source unit so values that *do* exist in tables are not lost.
    """
    raw = _norm(text)
    if not raw:
        return []
    identifiers = list(dict.fromkeys(re.findall(
        r"\b(?:Input|Output|Par|Param|Parameter|P|I|O)_[A-Za-z][A-Za-z0-9_]*\b|\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+\b",
        raw,
    )))
    numeric = list(dict.fromkeys(re.findall(
        r"(?<![A-Za-z0-9_])(?:0x[0-9A-Fa-f]+|[-+]?\d+(?:\.\d+)?)\s*(?:ms|msec|s|sec|초|V|mV|A|mA|%|℃|°C|mm|회|step|kbit/s|kbps)?",
        raw,
        re.I,
    )))
    enum_pairs = []
    for m in re.finditer(r"\b(0x[0-9A-Fa-f]+|\d+)\s*(?:=|:)\s*([^,;|/]{1,50})", raw):
        enum_pairs.append({"value": m.group(1), "meaning": m.group(2).strip()})
    range_tokens = list(dict.fromkeys(re.findall(
        r"(?:0x[0-9A-Fa-f]+|[-+]?\d+(?:\.\d+)?)\s*(?:~|～|-)\s*(?:0x[0-9A-Fa-f]+|[-+]?\d+(?:\.\d+)?)\s*(?:ms|s|V|mV|A|mA|%|℃|mm)?",
        raw, re.I,
    )))
    relations = []
    for m in re.finditer(r"(0x[0-9A-Fa-f]+|[-+]?\d+(?:\.\d+)?)\s*(?:ms|s|V|mV|A|mA|%|℃|mm)?\s*(이상|이하|초과|미만|이내)", raw, re.I):
        relations.append(m.group(0).strip())
    timing = [x for x in numeric if re.search(r"(?:ms|msec|s|sec|초)\s*$", x, re.I)]
    prohibited = bool(re.search(r"금지|하지\s*않|invalid|reserved|사용\s*불가|불가", raw, re.I))
    fact_type = "SOURCE_LITERAL_FACT"
    if enum_pairs:
        fact_type = "ENUM_MAPPING"
    elif timing:
        fact_type = "TIMING_VALUE"
    elif identifiers and numeric:
        fact_type = "INTERFACE_OR_PARAMETER_VALUE"
    elif identifiers:
        fact_type = "SIGNAL_OR_PARAMETER_IDENTIFIER"
    elif range_tokens:
        fact_type = "RANGE"
    elif prohibited:
        fact_type = "PROHIBITION"

    # V0.63 separates the semantic role of a table value from the literal fact type.
    # A range/enum/encoding row must never be collapsed to an arbitrary member value.
    encoding_rule = bool(re.search(r"(?:value|raw|physical).{0,12}(?:x|×|\*)\s*[-+]?\d+(?:\.\d+)?\s*(?:ms|s|V|mV|%|step)?|\bencoding\b|\bscale\b|factor", raw, re.I))
    invalid_marker = bool(re.search(r"\b(?:invalid|reserved)\b|무효|예약", raw, re.I))
    explicit_assignment = bool(identifiers and re.search(r"(?:=|:|：)", raw))
    if encoding_rule:
        value_role = "ENCODING_RULE"
    elif enum_pairs and len(enum_pairs) >= 1:
        value_role = "ENUM_MAPPING"
    elif range_tokens:
        value_role = "RANGE_CONSTRAINT"
    elif invalid_marker and len(numeric) >= 1:
        value_role = "INVALID_MARKER"
    elif timing and len(numeric) == 1 and explicit_assignment:
        value_role = "TIMING_CRITERION"
    elif len(numeric) == 1 and identifiers and explicit_assignment:
        value_role = "SINGLE_REQUIRED_VALUE"
    else:
        value_role = "SOURCE_LITERAL_ONLY"
    return [{
        "fact_id": f"FACT-{hashlib.sha256((unit_id+'|'+location+'|'+raw).encode('utf-8', errors='ignore')).hexdigest()[:12].upper()}",
        "fact_type": fact_type,
        "source_literal": raw,
        "identifiers": identifiers,
        "numeric_values": numeric,
        "timing_values": timing,
        "range_values": range_tokens,
        "explicit_relations": relations,
        "enum_mappings": enum_pairs,
        "prohibition": prohibited,
        "knowledge_state": "KNOWN",
        "value_role": value_role,
        "auto_tc_value_allowed": value_role in {"SINGLE_REQUIRED_VALUE", "TIMING_CRITERION"},
        "source_semantic_unit_id": unit_id,
        "source_location": location,
    }]


def build_source_table_fact_index(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for unit in units:
        if not isinstance(unit, dict):
            continue
        location = str(unit.get("source_location") or "")
        kind = str(unit.get("source_kind") or "")
        if not (re.search(r"Table\s+\d+\s*/\s*Row\s+\d+", location, re.I) or "table" in kind.lower()):
            continue
        if unit.get("coverage_eligibility") == "review_context" and unit.get("source_unit_type") in {"variant_matrix_header", "heading_or_document_context", "revision_history_context"}:
            continue
        out.extend(_structured_source_facts(
            str(unit.get("source_excerpt") or ""),
            unit_id=str(unit.get("source_semantic_unit_id") or ""),
            location=location,
        ))
    return out


def _fact_level_allocation(unit: dict[str, Any], parent_alloc: dict[str, Any] | None = None) -> dict[str, Any]:
    source_text = str(unit.get("source_excerpt") or "")
    alloc = _allocation_for_text(source_text, "")
    parent_alloc = parent_alloc or {}
    override_evidence = _explicit_sw_allocation_evidence(source_text)
    parent_pending = str(parent_alloc.get("swe6_eligibility") or "").startswith("Deferred") or "PENDING_SW_ALLOCATION" in str(parent_alloc.get("allocation_status") or "")
    allocation_inheritance = "FACT_LEVEL_CLASSIFIED"
    allocation_override = False
    allocation_override_reason = ""
    # V0.63 invariant: a child Source fact cannot silently outrank a conservative parent
    # allocation.  Only explicit SW responsibility in the same Source fact may override it.
    if parent_pending and str(alloc.get("swe6_eligibility") or "") == "Eligible" and not override_evidence:
        alloc = {
            "requirement_level": parent_alloc.get("requirement_level") or "System",
            "allocation_status": "INHERIT_PARENT_ALLOCATION_PENDING",
            "swe1_eligibility": "Review Needed",
            "swe6_eligibility": "Deferred pending SW allocation",
            "verification_domain": parent_alloc.get("verification_domain") or "System Integration / SYS.5",
            "allocation_rationale": "Parent requirement is pending software allocation; child fact inherits that decision because no explicit fact-level SW allocation evidence exists.",
        }
        allocation_inheritance = "PARENT_ALLOCATION_INHERITED_PENDING"
    elif parent_pending and str(alloc.get("swe6_eligibility") or "") == "Eligible" and override_evidence:
        allocation_override = True
        allocation_inheritance = "EXPLICIT_FACT_LEVEL_OVERRIDE"
        allocation_override_reason = "Explicit SW allocation wording exists in the same Source fact."
    structured = _structured_source_facts(
        source_text,
        unit_id=str(unit.get("source_fact_fragment_id") or unit.get("source_semantic_unit_id") or unit.get("parent_source_semantic_unit_id") or ""),
        location=str(unit.get("source_location") or ""),
    )
    return {
        "source_semantic_unit_id": unit.get("source_semantic_unit_id") or unit.get("parent_source_semantic_unit_id"),
        "source_fact_fragment_id": unit.get("source_fact_fragment_id"),
        "source_chunk_id": unit.get("source_chunk_id"),
        "source_location": unit.get("source_location"),
        "source_fact": unit.get("source_excerpt"),
        "knowledge_state": "KNOWN",
        "requirement_level": alloc.get("requirement_level"),
        "allocation_status": alloc.get("allocation_status"),
        "swe1_eligibility": alloc.get("swe1_eligibility"),
        "swe6_eligibility": alloc.get("swe6_eligibility"),
        "verification_domain": alloc.get("verification_domain"),
        "allocation_rationale": alloc.get("allocation_rationale"),
        "allocation_inheritance": allocation_inheritance,
        "allocation_override": allocation_override,
        "allocation_override_evidence": override_evidence,
        "allocation_override_reason": allocation_override_reason,
        "structured_source_facts": structured,
    }


def _normalized_primary_domain(domain: str) -> str:
    d = _norm(domain)
    aliases = {
        "System Integration / Interface Allocation Review": "System Integration / SYS.5",
        "Cross-domain Verification Review": "Cross-domain Verification Review",
    }
    return aliases.get(d, d)


def apply_allocation_gate(req: dict[str, Any], matched_units: list[dict[str, Any]] | None = None) -> None:
    """Apply parent allocation plus fact-level allocation without automatic SRS splitting.

    V0.63 adds parent->child inheritance and separates primary verification domains from external
    dependency evidence.  This prevents child facts from becoming SWE.6 Eligible merely because a
    terse table row looks software-like while the parent is still pending allocation.
    """
    parent_alloc = _allocation_for_text(_source_text(req), _req_text(req))
    req.update(parent_alloc)
    units = [u for u in (matched_units or []) if isinstance(u, dict)]
    fragment_units = [
        {
            "source_semantic_unit_id": f.get("parent_source_semantic_unit_id"),
            "parent_source_semantic_unit_id": f.get("parent_source_semantic_unit_id"),
            "source_fact_fragment_id": f.get("source_fact_fragment_id"),
            "source_chunk_id": f.get("source_chunk_id"),
            "source_location": f.get("source_location"),
            "source_excerpt": f.get("source_excerpt"),
            "source_kind": f.get("source_kind"),
        }
        for f in (req.get("source_fact_fragments") or []) if isinstance(f, dict)
    ]
    allocation_units = fragment_units or units
    fact_allocs = [_fact_level_allocation(u, parent_alloc) for u in allocation_units]
    req["fact_level_allocations"] = fact_allocs

    external_domains = list(dict.fromkeys(
        str(x.get("verification_domain") or "") for x in fact_allocs
        if str(x.get("allocation_status") or "") == "EXTERNAL_STANDARD_REFERENCE" and str(x.get("verification_domain") or "")
    ))
    primary_domains = list(dict.fromkeys(
        _normalized_primary_domain(str(x.get("verification_domain") or "")) for x in fact_allocs
        if str(x.get("verification_domain") or "")
        and str(x.get("allocation_status") or "") != "EXTERNAL_STANDARD_REFERENCE"
    ))
    req["cross_domain_verification_domains"] = primary_domains
    req["external_dependency_domains"] = external_domains
    req["cross_domain_bundle_review_required"] = len(primary_domains) > 1
    req["mixed_external_dependency_review_required"] = bool(external_domains and primary_domains)

    # Keep the parent.  Only a bundle made entirely of high-confidence Not-SW primary facts is
    # excluded from SWE.1/SWE.6 as a cross-domain review object.  Mixed System/SW bundles remain
    # at the conservative parent allocation and are flagged for review.
    non_sw = [x for x in fact_allocs if str(x.get("swe1_eligibility") or "") == "Not Applicable"]
    if len(primary_domains) > 1 and non_sw and len(non_sw) == len(fact_allocs):
        req.update({
            "requirement_level": "Cross-domain Source Fact Bundle",
            "allocation_status": "CROSS_DOMAIN_FACT_BUNDLE_REVIEW_REQUIRED",
            "swe1_eligibility": "Not Applicable",
            "swe6_eligibility": "Not Applicable",
            "verification_domain": "Cross-domain Verification Review",
            "allocation_rationale": "Linked Source facts span multiple non-software verification domains. The parent is preserved without automatic SRS splitting; fact-level allocation is authoritative for review.",
        })


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

    # V0.59 location-first fallback: source_evidence is already a source-backed
    # anchor. If exactly one block (or one clearly strongest block) shares the
    # same Paragraph/Table location, preserve that Source Unit even when the
    # evidence text is a shortened paraphrase produced by the extraction layer.
    for ev in evidence_items:
        loc = _norm(ev.get("location"))
        txt = _norm(ev.get("text"))
        if not loc:
            continue
        loc_units = [u for u in units if _loc_match(loc, str(u.get("source_location") or "")) and _numeric_compatible(txt, str(u.get("source_excerpt") or ""))]
        if not loc_units:
            continue
        if len(loc_units) == 1:
            return [loc_units[0]]
        ranked = sorted(((_token_similarity(txt, str(u.get("source_excerpt") or "")), u) for u in loc_units), key=lambda x: x[0], reverse=True)
        if ranked and ranked[0][0] >= 0.25 and (len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= 0.10):
            return [ranked[0][1]]

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
    structured = _structured_source_facts(
        str(unit.get("source_excerpt") or ""),
        unit_id=str(unit.get("source_fact_fragment_id") or unit.get("source_semantic_unit_id") or unit.get("parent_source_semantic_unit_id") or ""),
        location=str(unit.get("source_location") or ""),
    )
    return {
        "source_semantic_unit_id": unit.get("source_semantic_unit_id") or unit.get("parent_source_semantic_unit_id"),
        "source_fact_fragment_id": unit.get("source_fact_fragment_id"),
        "source_chunk_id": unit.get("source_chunk_id"),
        "source_location": unit.get("source_location"),
        "source_fact": unit.get("source_excerpt"),
        "structured_source_facts": structured,
        "knowledge_state": "KNOWN",
    }


def _source_backed_atom(unit: dict[str, Any], *, preservation_reason: str = "semantic_unit") -> dict[str, Any]:
    # Preserve the source clause verbatim. This closes provenance without inventing
    # timing, ordering, values or implementation details that are not in the Source.
    return {
        "source_semantic_unit_id": unit.get("source_semantic_unit_id") or unit.get("parent_source_semantic_unit_id"),
        "source_fact_fragment_id": unit.get("source_fact_fragment_id"),
        "source_chunk_id": unit.get("source_chunk_id"),
        "source_location": unit.get("source_location"),
        "behavior_text": str(unit.get("source_excerpt") or "")[:900],
        "knowledge_state": "KNOWN",
        "preservation_reason": preservation_reason,
    }


def _unit_can_back_requirement(req: dict[str, Any], unit: dict[str, Any]) -> bool:
    if unit.get("coverage_eligibility") == "semantic_unit":
        return True
    if unit.get("source_unit_type") in {
        "revision_history_context", "external_reference_only",
        "heading_or_document_context", "reference_or_document_context",
    }:
        return False
    excerpt = str(unit.get("source_excerpt") or "")
    if not excerpt:
        return False
    # A source description may lack a normative suffix (e.g. terse function rows)
    # while the Canonical item is a confirmed SWE.1 requirement. Require strong
    # source-evidence overlap before allowing it to back Atomic Behavior.
    source = _source_text(req)
    return _token_similarity(source, excerpt) >= 0.42 and _numeric_compatible(source, excerpt)


def attach_semantic_traceability(data: dict[str, Any], compact_text: str) -> None:
    units = build_semantic_source_units(compact_text)
    data["semantic_source_units"] = units
    table_fact_index = build_source_table_fact_index(units)
    data["source_table_fact_index"] = table_fact_index
    fragment_index = [frag for unit in units for frag in _source_fact_fragments_for_unit(unit)]
    data["source_fact_fragment_index"] = fragment_index
    reqs = [x for x in data.get("requirements", []) if isinstance(x, dict)]

    for req in reqs:
        req.setdefault("source_semantic_unit_ids", [])
        req.setdefault("source_chunk_ids", [])
        req.setdefault("source_backed_atomic_behaviors", [])
        req.setdefault("source_backed_facts", [])
        matched = _best_semantic_matches(req, units)
        req["source_fact_fragments"] = _fragments_for_requirement(req, matched, fragment_index)

        # V0.63 conservative Source Table Fact Join.  Exact identifier overlap or an already
        # linked Semantic Unit is required for HIGH-confidence automatic use in SWE.6.  Numeric
        # coincidence alone is never enough to join a table fact to a requirement.
        linked_unit_ids = {str(u.get("source_semantic_unit_id") or "") for u in matched}
        req_join_text = " ".join([
            _req_text(req), _source_text(req),
            " ".join(str(x.get("text") or "") for x in _list(req.get("source_evidence")) if isinstance(x, dict)),
        ])
        req_identifiers = set(re.findall(r"\b(?:Input|Output|Par|Param|Parameter|P|I|O)_[A-Za-z][A-Za-z0-9_]*\b|\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+\b", req_join_text))
        fact_matches = []
        for fact in table_fact_index:
            ids = set(str(x) for x in fact.get("identifiers") or [])
            exact_id_overlap = sorted(ids & req_identifiers)
            same_unit = str(fact.get("source_semantic_unit_id") or "") in linked_unit_ids
            if same_unit or exact_id_overlap:
                item = dict(fact)
                item["join_confidence"] = "HIGH" if exact_id_overlap or same_unit else "REVIEW"
                item["join_basis"] = "linked_semantic_unit" if same_unit else "exact_identifier_overlap"
                item["matched_identifiers"] = exact_id_overlap
                fact_matches.append(item)
        req["source_table_fact_matches"] = fact_matches

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

        apply_allocation_gate(req, matched)
        eligibility = str(req.get("swe1_eligibility") or "Eligible")
        if eligibility != "Not Applicable" and not req.get("source_backed_atomic_behaviors"):
            fragment_units = [
                {
                    "source_semantic_unit_id": f.get("parent_source_semantic_unit_id"),
                    "source_chunk_id": f.get("source_chunk_id"),
                    "source_location": f.get("source_location"),
                    "source_excerpt": f.get("source_excerpt"),
                    "source_unit_type": "fact_fragment",
                    "coverage_eligibility": "semantic_unit",
                    "source_fact_fragment_id": f.get("source_fact_fragment_id"),
                }
                for f in (req.get("source_fact_fragments") or []) if isinstance(f, dict)
            ]
            for u in (fragment_units or matched):
                if not _unit_can_back_requirement(req, u):
                    continue
                reason = "fact_fragment" if u.get("source_fact_fragment_id") else ("semantic_unit" if u.get("coverage_eligibility") == "semantic_unit" else "source_description_promoted_by_confirmed_requirement")
                atom = _source_backed_atom(u, preservation_reason=reason)
                if u.get("source_fact_fragment_id"):
                    atom["source_fact_fragment_id"] = u.get("source_fact_fragment_id")
                req["source_backed_atomic_behaviors"].append(atom)

        # V0.59 provenance completion fallback: when a no-ID Eligible/Pending item
        # already has deterministic semantic IDs but a prior classifier labelled the
        # source block as descriptive, use the exact linked Source clause as the
        # atomic/fact object. Never synthesize a new behavior sentence.
        if eligibility in {"Eligible", "Review Needed"} and not req.get("source_backed_atomic_behaviors"):
            linked_ids = {str(x) for x in req.get("source_semantic_unit_ids") or [] if str(x)}
            linked_units = [u for u in units if str(u.get("source_semantic_unit_id") or "") in linked_ids]
            for u in linked_units:
                if _unit_can_back_requirement(req, u):
                    req["source_backed_atomic_behaviors"].append(
                        _source_backed_atom(u, preservation_reason="linked_source_clause_fallback")
                    )

        if eligibility == "Not Applicable" and not req.get("source_backed_facts"):
            req["source_backed_facts"] = [_source_fact_object(u) for u in matched]
        elif eligibility == "Review Needed" and not req.get("source_backed_atomic_behaviors") and not req.get("source_backed_facts"):
            # Pending System allocation still needs auditable source provenance even
            # when the source clause is descriptive rather than a SWE.1 behavior.
            req["source_backed_facts"] = [_source_fact_object(u) for u in matched if str(u.get("source_excerpt") or "").strip()]

        if eligibility == "Eligible":
            complete = bool(req.get("source_semantic_unit_ids") and req.get("source_backed_atomic_behaviors"))
            req["semantic_provenance_status"] = "COMPLETE" if complete else "INCOMPLETE_REVIEW_REQUIRED"
        elif eligibility == "Review Needed":
            complete = bool(req.get("source_semantic_unit_ids") and (req.get("source_backed_atomic_behaviors") or req.get("source_backed_facts")))
            req["semantic_provenance_status"] = "COMPLETE" if complete else "INCOMPLETE_REVIEW_REQUIRED"
        else:
            complete = bool(req.get("source_semantic_unit_ids") and req.get("verification_domain"))
            req["semantic_provenance_status"] = "COMPLETE" if complete else "INCOMPLETE_REVIEW_REQUIRED"

    # V0.63 fact-fragment ownership audit. The same exact fragment may support multiple SRS,
    # but conflicting primary allocations require review unless the clauses were split into
    # different fragment IDs.
    fragment_claims: dict[str, list[dict[str, Any]]] = {}
    for req in reqs:
        alloc_by_fragment = {str(a.get("source_fact_fragment_id") or ""): a for a in (req.get("fact_level_allocations") or []) if isinstance(a, dict) and a.get("source_fact_fragment_id")}
        for frag in req.get("source_fact_fragments") or []:
            if not isinstance(frag, dict):
                continue
            fid = str(frag.get("source_fact_fragment_id") or "")
            if not fid:
                continue
            alloc = alloc_by_fragment.get(fid) or {}
            fragment_claims.setdefault(fid, []).append({
                "srs_id": str(req.get("srs_id") or ""),
                "allocation_status": str(alloc.get("allocation_status") or req.get("allocation_status") or ""),
                "verification_domain": str(alloc.get("verification_domain") or req.get("verification_domain") or ""),
                "source_excerpt": frag.get("source_excerpt"),
            })
    conflicts = []
    for fid, claims in fragment_claims.items():
        domains = {c["verification_domain"] for c in claims if c["verification_domain"]}
        allocations = {c["allocation_status"] for c in claims if c["allocation_status"]}
        if len(claims) > 1 and (len(domains) > 1 or len(allocations) > 1):
            conflicts.append({"source_fact_fragment_id": fid, "claims": claims, "issue": "SOURCE_FACT_MULTI_SRS_ALLOCATION_CONFLICT", "severity": "RELEASE_REVIEW"})
    data["source_fact_multi_srs_allocation_conflicts"] = conflicts

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
        shared = _tokens(hay) & _tokens(req_hay)
        # Similarity alone used to over-anchor broad mode/TBD gaps to unrelated
        # voltage/current/temperature SRS. Require stronger lexical evidence and
        # at least two shared non-stopword tokens.
        if sim >= 0.55 and len(shared) >= 2:
            return True
        # Exact external specification / signal-like tokens are deterministic anchors.
        anchors = set(re.findall(r"\b(?:ES|MS)\s*\d{3,}(?:[-_]\d+)?\b|\b[A-Za-z][A-Za-z0-9_]{3,}\b", hay, flags=re.I))
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
        if scope != "section":
            continue
        # For no-ID section gaps, every direct Candidate/SRS link must survive a
        # deterministic anchor check. Sparse but weak links are not automatically
        # trustworthy; if none survive, keep the issue as section context instead.
        exact_source_anchor = bool(_list(gap.get("related_source_requirement_ids")) or _list(gap.get("related_source_occurrence_ids")))
        if exact_source_anchor:
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


def _explicit_value_relations(source_text: str) -> list[dict[str, Any]]:
    text = _norm(source_text)
    out: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []

    def add(m: re.Match, relation: str, normalized_value: str, literal: str | None = None) -> None:
        span = m.span()
        occupied.append(span)
        out.append({
            "source_value_text": (literal or m.group(0)).strip(),
            "normalized_value": normalized_value,
            "relation": relation,
            "relation_confirmed": True,
            "clarification": "",
            "source_span": [span[0], span[1]],
        })

    # Explicit range, e.g. DC 7V ~ 18V, -40℃ ~ +85℃.
    range_pat = re.compile(
        r"([-+]?\d+(?:\.\d+)?)\s*(mA|A|mV|V|ms|s|℃|mm|%)?\s*[~～]\s*"
        r"([-+]?\d+(?:\.\d+)?)\s*(mA|A|mV|V|ms|s|℃|mm|%)?",
        re.I,
    )
    for m in range_pat.finditer(text):
        u1, u2 = m.group(2) or "", m.group(4) or ""
        unit = u2 or u1
        add(m, "RANGE_EXPLICIT", f"{m.group(1)}{unit}~{m.group(3)}{unit}")

    op_map = {
        "이하": "LESS_THAN_OR_EQUAL_EXPLICIT",
        "이상": "GREATER_THAN_OR_EQUAL_EXPLICIT",
        "초과": "GREATER_THAN_EXPLICIT",
        "미만": "LESS_THAN_EXPLICIT",
        "이내": "WITHIN_EXPLICIT",
    }
    op_pat = re.compile(
        r"([-+]?\d+(?:\.\d+)?)\s*(mA|A|mV|V|ms|s|초|℃|mm|%)?\s*(이하|이상|초과|미만|이내)",
        re.I,
    )
    for m in op_pat.finditer(text):
        if any(max(m.start(), a) < min(m.end(), b) for a, b in occupied):
            continue
        unit = m.group(2) or ""
        add(m, op_map[m.group(3)], f"{m.group(1)}{unit}")

    sym_map = {"<=": "LESS_THAN_OR_EQUAL_EXPLICIT", ">=": "GREATER_THAN_OR_EQUAL_EXPLICIT", "<": "LESS_THAN_EXPLICIT", ">": "GREATER_THAN_EXPLICIT"}
    sym_pat = re.compile(r"(<=|>=|<|>)\s*([-+]?\d+(?:\.\d+)?)\s*(mA|A|mV|V|ms|s|℃|mm|%)?", re.I)
    for m in sym_pat.finditer(text):
        if any(max(m.start(), a) < min(m.end(), b) for a, b in occupied):
            continue
        unit = m.group(3) or ""
        add(m, sym_map[m.group(1)], f"{m.group(2)}{unit}")
    return out


def _ambiguous_value_relations(source_text: str, explicit: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    text = _norm(source_text)
    explicit = explicit or _explicit_value_relations(text)
    occupied = [tuple(x.get("source_span") or []) for x in explicit if len(x.get("source_span") or []) == 2]
    out: list[dict[str, Any]] = []

    def overlaps(span: tuple[int, int]) -> bool:
        return any(max(span[0], a) < min(span[1], b) for a, b in occupied)

    # Literal MAX is preserved as written rather than silently converted into <=.
    for m in re.finditer(r"\bMAX\s*([-+]?\d+(?:\.\d+)?)\s*(mA|A|mV|V|ms|s|℃|mm|%)?", text, re.I):
        if overlaps(m.span()):
            continue
        literal = m.group(0).strip()
        out.append({
            "source_value_text": literal,
            "normalized_value": f"{m.group(1)}{m.group(2) or ''}",
            "relation": "SOURCE_LITERAL_MAX",
            "relation_confirmed": False,
            "clarification": "Source uses the literal 'MAX'; the formal acceptance comparator and measurement conditions require confirmation.",
            "source_span": [m.start(), m.end()],
        })

    # Label : value without an explicit comparator is ambiguous target/limit semantics.
    for m in re.finditer(r"([^\n|:：]{2,44})\s*[:：]\s*([-+]?\d+(?:\.\d+)?)\s*(mA|A|mV|V|ms|s|℃|mm|%)\b", text, re.I):
        span = m.span()
        if overlaps(span):
            continue
        # A comparator or range immediately after the captured value makes the clause explicit.
        nearby = text[m.start():min(len(text), m.end()+24)]
        if re.search(r"이상|이하|초과|미만|이내|<=|>=|<|>|[~～]\s*[-+]?\d", nearby, re.I):
            continue
        literal = m.group(0).strip()
        if any(x.get("source_value_text") == literal for x in out):
            continue
        prefix = m.group(1).strip()
        out.append({
            "source_value_text": literal,
            "normalized_value": f"{m.group(2)}{m.group(3)}",
            "relation": "UNSPECIFIED_LIMIT_OR_TARGET",
            "relation_confirmed": False,
            "clarification": f"Source states '{prefix}' with a value but does not explicitly define equality/upper/lower-limit semantics.",
            "source_span": [m.start(), m.end()],
        })
    return out


def _value_relations(source_text: str) -> list[dict[str, Any]]:
    explicit = _explicit_value_relations(source_text)
    ambiguous = _ambiguous_value_relations(source_text, explicit)
    # Remove internal span from exported records.
    return [{k: v for k, v in x.items() if k != "source_span"} for x in (explicit + ambiguous)]


def _generated_strengthens_relation(text: str, value: str) -> bool:
    if not text or not value:
        return False
    m = re.match(r"[-+]?\d+(?:\.\d+)?", value)
    number = re.escape(m.group(0)) if m else re.escape(value)
    return bool(re.search(
        rf"{number}\s*(?:mA|A|mV|V|ms|s|℃|mm|%)?\s*(?:이하|이상|초과|미만|이어야\s*한다|여야\s*한다|를?\s*만족해야\s*한다|를?\s*만족한다)|"
        rf"(?:<=|>=|<|>)\s*{number}",
        text, re.I,
    ))


def preserve_numeric_relation_semantics(data: dict[str, Any]) -> None:
    for req in [x for x in data.get("requirements", []) if isinstance(x, dict)]:
        src = "\n".join(_norm(ev.get("text")) for ev in _list(req.get("source_evidence")) if isinstance(ev, dict) and _norm(ev.get("text")))
        relations = _value_relations(src)
        req["value_relation_status"] = relations
        ambiguous = [x for x in relations if not x.get("relation_confirmed")]
        explicit = [x for x in relations if x.get("relation_confirmed")]
        if not ambiguous:
            req["normative_strength_status"] = "SOURCE_RELATION_EXPLICIT_OR_NOT_NUMERIC"
            req["normative_strength_findings"] = []
            continue

        strengthened = []
        for rel in ambiguous:
            value = str(rel.get("normalized_value") or "")
            bad_fields = [k for k in ("requirement", "acceptance_criteria") if _generated_strengthens_relation(_norm(req.get(k)), value)]
            if bad_fields:
                strengthened.append({"value": value, "fields": bad_fields, "source_value_text": rel.get("source_value_text")})

        if strengthened:
            req["normative_strength_status"] = "SOURCE_RELATION_AMBIGUOUS_GENERATED_STRENGTHENING_REMOVED"
            clar = _list(req.get("clarification_needed"))
            for rel in ambiguous:
                c = str(rel.get("clarification") or "")
                if c and c not in clar:
                    clar.append(c)
            req["clarification_needed"] = clar
            # Only replace the generated requirement wholesale for a terse source that
            # contains no explicit relational facts. Mixed explicit/ambiguous clauses
            # keep their confirmed ranges/operators and surface clarification only for
            # the ambiguous value clause.
            if len(src) <= 260 and not explicit:
                literals = "; ".join(str(x.get("source_value_text") or "") for x in ambiguous if x.get("source_value_text"))
                req["requirement"] = f"Source 표기 보존: {literals or src}"
                req["acceptance_criteria"] = "Source에 공식 비교 관계/허용 기준이 명시되지 않아 확인이 필요하다."
            req["normative_strength_findings"] = strengthened
        else:
            req["normative_strength_status"] = "SOURCE_RELATION_AMBIGUOUS_PRESERVED"
            req["normative_strength_findings"] = []
