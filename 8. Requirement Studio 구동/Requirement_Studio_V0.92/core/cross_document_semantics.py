from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_ENGINEERING_IDENTIFIER_RE = re.compile(
    r"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+(?![A-Za-z0-9_])"
)

def _engineering_identifiers(text: str) -> list[str]:
    """Extract ASCII engineering identifiers even when followed by Korean particles.

    Unicode ``\b`` treats Korean letters as word characters, so literals such as
    ``SVM_Typ2의`` or ``ICMU_RealTimeMonStat를`` were previously missed.  ASCII
    lookarounds preserve the identifier boundary without consuming the Korean suffix.
    """
    return list(dict.fromkeys(m.group(0) for m in _ENGINEERING_IDENTIFIER_RE.finditer(text or "")))


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
    # V0.69: separate Korean/ASCII boundaries so engineering literals such as
    # ``최초B+`` and generated prose ``최초 B+`` compare as the same material fact.
    # This is intentionally used only for semantic matching; raw Source text is never rewritten.
    normalized = _norm(text)
    parts = re.findall(r"[가-힣]+|[A-Za-z0-9_.+-]+", normalized)
    return {x.lower() for x in parts if len(x) > 1 and x.lower() not in stop}


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

    V0.65 keeps parameter/interface/variant guidance auditable as review context instead of
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


def _ordered_list_parts(text: str, *, source_kind: str = "") -> list[tuple[str, str, str]]:
    """Return ordered-list members only when the structure is unambiguous.

    V0.65 deliberately does not apply digit-marker splitting to table cells. Numeric engineering
    literals such as ``6.5V``/``18.5V``, revisions such as ``1.3`` and heading numbers such as
    ``5.4.1.1`` are Source facts, not list markers. For paragraph-like text a numeric/letter marker
    must be followed by whitespace and at least two markers must form a plausible ordered list.
    """
    raw = str(text or "").strip()
    if not raw:
        return []
    if "table" in str(source_kind or "").lower():
        return []

    marker_re = re.compile(
        r"(?:(?<=^)|(?<=\s))(?P<marker>(?:\d{1,2}[.)]|[가-하][.)]|[①-⑳]))(?=\s)"
    )
    matches = list(marker_re.finditer(raw))
    if len(matches) < 2:
        return []

    # Numeric ordered lists must be monotonic consecutive members. This rejects accidental
    # structural/version tokens even if normalization inserted spaces around them.
    numeric = []
    for m in matches:
        token = m.group("marker")
        mm = re.fullmatch(r"(\d{1,2})[.)]", token)
        if mm:
            numeric.append(int(mm.group(1)))
    if numeric and len(numeric) == len(matches):
        if any(b != a + 1 for a, b in zip(numeric, numeric[1:])):
            return []

    parts: list[tuple[str, str, str]] = []
    prefix = raw[:matches[0].start()].strip()
    if prefix and not prefix.endswith((":", "：")):
        parts.append((prefix, prefix, ""))
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[start:end].strip(" ;,\t")
        raw_fragment = raw[match.start():end].strip(" ;,\t")
        if body:
            parts.append((body, raw_fragment, match.group("marker")))
    return parts


def _split_behavior_clauses(text: str) -> list[str]:
    """Conservatively split a compound behavior sentence at explicit action connectors.

    This is not a general Korean parser. It only recognizes strong action-connective endings that
    commonly join independent controller behaviors (receive/store/check/control/etc.). Keeping the
    connector in the preceding fragment preserves Source wording while giving different behaviors
    stable fragment ownership IDs.
    """
    raw = str(text or "").strip()
    if not raw:
        return []
    # Semicolons are already explicit clause boundaries.
    seeds = [x.strip() for x in re.split(r"\s*[;；]\s*", raw) if x.strip()]
    out: list[str] = []
    connector_re = re.compile(
        r"(?:전달\s*받아|정보를\s*받아|명령을\s*받아|신호를\s*받아|데이터를\s*받아|"
        r"수신(?:하여|하고)|저장하고|검사하고|확인하고|판단하고|송신하고|출력하고|"
        r"제어하고|변경하고|전환하고|복구하고|기록하고|설정하고|인가하고|전달하고)\s+",
        re.I,
    )
    for seed in seeds:
        cursor = 0
        local: list[str] = []
        for m in connector_re.finditer(seed):
            candidate = seed[cursor:m.end()].strip()
            tail = seed[m.end():].strip()
            # Avoid tiny grammatical shards. Both sides must still carry useful content.
            if len(re.sub(r"\W+", "", candidate, flags=re.UNICODE)) >= 5 and len(re.sub(r"\W+", "", tail, flags=re.UNICODE)) >= 5:
                local.append(candidate)
                cursor = m.end()
        remainder = seed[cursor:].strip()
        if remainder:
            local.append(remainder)
        out.extend(local or [seed])
    return out


def _critical_ownership_token_groups(text: str) -> dict[str, set[str]]:
    """Return source-backed engineering tokens used only to complete exact fragment ownership.

    V0.73 does not use these tokens to invent requirements or allocation. They only help recover
    a Source Fact Fragment from an already-matched Source location when the Canonical text retained
    a signal/timing/enum fact that the similarity-only fragment selector would otherwise drop.
    """
    groups = {"identifiers": set(), "timing": set(), "hex": set(), "retry": set()}
    for fact in _structured_source_facts(text):
        for value in fact.get("identifiers") or []:
            token = re.sub(r"\s+", "", str(value)).lower()
            if token:
                groups["identifiers"].add(token)
        for value in fact.get("timing_values") or []:
            token = re.sub(r"\s+", "", str(value)).lower()
            if token:
                groups["timing"].add(token)
        for value in fact.get("numeric_values") or []:
            token = re.sub(r"\s+", "", str(value)).lower()
            if token.startswith("0x"):
                groups["hex"].add(token)
            if token.endswith("회"):
                groups["retry"].add(token)
        for enum in fact.get("enum_mappings") or []:
            if isinstance(enum, dict):
                token = re.sub(r"\s+", "", str(enum.get("value") or "")).lower()
                if token.startswith("0x"):
                    groups["hex"].add(token)
                if token.endswith("회"):
                    groups["retry"].add(token)
    # Power-rail literals such as B+ are load-bearing operating conditions but are not normal
    # identifier tokens. Preserve them for exact fragment ownership completion.
    for value in re.findall(r"(?<![A-Za-z0-9_])B\s*[+-](?![A-Za-z0-9_])", text or "", re.I):
        groups["identifiers"].add(re.sub(r"\s+", "", value).lower())
    # Retry counts are often written as prose without an assignment expression.
    for value in re.findall(r"(?<![0-9])\d+\s*회(?![0-9])", text or ""):
        groups["retry"].add(re.sub(r"\s+", "", value).lower())
    return groups


def _critical_ownership_tokens(text: str) -> set[str]:
    groups = _critical_ownership_token_groups(text)
    return set().union(*groups.values())


def _source_fact_fragments_for_unit(unit: dict[str, Any]) -> list[dict[str, Any]]:
    """Split a compound Semantic Source Unit into stable behavior/fact fragments.

    V0.65 is table/decimal aware and adds conservative behavior-clause fragmentation. Ordered-list
    markers remain structural metadata, never numeric facts. Source text is always retained in
    ``source_excerpt_raw`` and no normalized fragment may be created by cutting an engineering
    literal such as a decimal voltage, revision, date, heading number or specification identifier.
    """
    raw = str(unit.get("source_excerpt") or "").strip()
    if not raw:
        return []

    source_kind = str(unit.get("source_kind") or "")
    coarse_parts = [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+|\s*[•·▪◦]\s*", raw) if x and x.strip()]
    # Preserve detached closing punctuation as part of the preceding raw clause. Source documents
    # occasionally contain forms such as "...없다. )". Display normalization may ignore the stray
    # bracket, but source_excerpt_raw must retain it for exact provenance/drill-down.
    while len(coarse_parts) >= 2 and re.fullmatch(r"[)\]\}）】》〉]+", coarse_parts[-1]):
        tail = coarse_parts.pop()
        coarse_parts[-1] = coarse_parts[-1] + " " + tail
    if not coarse_parts:
        coarse_parts = [raw]

    parts: list[tuple[str, str, str]] = []
    for coarse in coarse_parts:
        ordered = _ordered_list_parts(coarse, source_kind=source_kind)
        if ordered:
            parts.extend(ordered)
            continue
        # Table cells are literal fact records; never apply prose action splitting to them.
        if "table" in source_kind.lower():
            parts.append((coarse, coarse, ""))
            continue
        behavior_parts = _split_behavior_clauses(coarse)
        if len(behavior_parts) > 1:
            for clause in behavior_parts:
                parts.append((clause, clause, ""))
        else:
            parts.append((coarse, coarse, ""))

    out = []
    for idx, (text, raw_fragment, list_marker) in enumerate(parts, 1):
        if len(re.sub(r"\W+", "", text, flags=re.UNICODE)) < 3:
            continue
        uid = str(unit.get("source_semantic_unit_id") or "")
        fid = hashlib.sha256(f"{uid}|{idx}|{raw_fragment}".encode("utf-8", errors="ignore")).hexdigest()[:12].upper()
        item = {
            "source_fact_fragment_id": f"SRC-FRAG-{fid}",
            "parent_source_semantic_unit_id": uid,
            "source_chunk_id": unit.get("source_chunk_id"),
            "source_location": unit.get("source_location"),
            "source_kind": unit.get("source_kind"),
            "source_excerpt": text,
            "source_excerpt_raw": raw_fragment,
            "fragment_index": idx,
            "knowledge_state": "KNOWN",
        }
        if list_marker:
            item["source_list_marker"] = list_marker
        out.append(item)
    return out or [{
        "source_fact_fragment_id": f"SRC-FRAG-{hashlib.sha256(raw.encode('utf-8', errors='ignore')).hexdigest()[:12].upper()}",
        "parent_source_semantic_unit_id": str(unit.get("source_semantic_unit_id") or ""),
        "source_chunk_id": unit.get("source_chunk_id"),
        "source_location": unit.get("source_location"),
        "source_kind": unit.get("source_kind"),
        "source_excerpt": raw,
        "source_excerpt_raw": raw,
        "fragment_index": 1,
        "knowledge_state": "KNOWN",
    }]



def _source_location_keys(value: Any) -> set[str]:
    """Return conservative comparable Source-location keys without widening Source scope."""
    text = str(value or "").strip().lower()
    if not text:
        return set()
    keys: set[str] = set()
    for page in re.findall(r"\bpage\s*(\d+)\b", text, re.I):
        keys.add(f"page:{int(page)}")
    for table in re.findall(r"\btable\s*(\d+)\b", text, re.I):
        keys.add(f"table:{int(table)}")
    for start, end in re.findall(r"\bparagraphs?\s*(\d+)(?:\s*[-~–]\s*(\d+))?", text, re.I):
        a = int(start); b = int(end or start)
        if b < a:
            a, b = b, a
        # Source location ranges are small in normal exports; cap expansion defensively.
        for para in range(a, min(b, a + 50) + 1):
            keys.add(f"paragraph:{para}")
    # Combined citations are often rendered as `Paragraphs 205, 208`. Preserve every
    # explicitly named paragraph rather than treating only the first number as the anchor.
    for group in re.findall(r"\bparagraphs?\s*((?:\d+\s*[,/&+]\s*)+\d+)", text, re.I):
        for para in re.findall(r"\d+", group):
            keys.add(f"paragraph:{int(para)}")
    # Table row identity is load-bearing for numeric/electrical facts such as rated voltage.
    # Keep the parent table key for compatibility and add row-specific keys when available.
    for table, row_start, row_end in re.findall(r"\btable\s*(\d+)[^\n]{0,40}?\brows?\s*(\d+)(?:\s*[-~–]\s*(\d+))?", text, re.I):
        a = int(row_start); b = int(row_end or row_start)
        if b < a:
            a, b = b, a
        for row in range(a, min(b, a + 50) + 1):
            keys.add(f"table:{int(table)}:row:{row}")
    for row in re.findall(r"\brow\s*(\d+)\b", text, re.I):
        keys.add(f"row:{int(row)}")
    # Korean Page/Table/Paragraph labels occasionally survive normalization.
    for page in re.findall(r"(?:페이지|쪽)\s*(\d+)", text):
        keys.add(f"page:{int(page)}")
    for para in re.findall(r"(?:문단|단락)\s*(\d+)", text):
        keys.add(f"paragraph:{int(para)}")
    if not keys:
        compact = re.sub(r"\s+", " ", text).strip(" ,;:/")
        if compact:
            keys.add(f"literal:{compact}")
    return keys


def _explicit_requirement_source_location_keys(req: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for ev in _list(req.get("source_evidence")):
        if isinstance(ev, dict):
            keys |= _source_location_keys(ev.get("location"))
    return keys

def _fragments_for_requirement(req: dict[str, Any], matched_units: list[dict[str, Any]], fragment_index: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Unit matching may legitimately use broad Source Evidence, but fragment ownership must not.
    # Otherwise two different SRS that cite the same composite paragraph inherit the whole paragraph
    # and recreate multi-SRS allocation conflicts. Use Canonical behavior fields as the ownership
    # discriminator; Source Evidence remains the anchor that selected the parent Semantic Unit.
    ownership_text = _norm([
        req.get("function_name"), req.get("requirement"), req.get("activation_trigger"),
        req.get("preconditions"), req.get("processing_action"), req.get("output"),
        req.get("acceptance_criteria"),
    ]).lower()
    req_text = ownership_text or _req_text(req)
    matched_unit_ids = {str(u.get("source_semantic_unit_id") or "") for u in matched_units}
    candidates = [f for f in fragment_index if str(f.get("parent_source_semantic_unit_id") or "") in matched_unit_ids]
    # V0.74 Source-bounded recovery: critical clauses can live in a neighboring Semantic Unit on
    # the exact Source page/location already cited by the requirement. Similarity-only unit matching
    # must not make such a literal timing/signal clause unreachable. This pool is used only for
    # critical-fact completion and still requires literal critical-token overlap below.
    explicit_location_keys = _explicit_requirement_source_location_keys(req)
    location_candidates = []
    adjacent_paragraph_keys: set[str] = set()
    for key in explicit_location_keys:
        if key.startswith("paragraph:"):
            try:
                n = int(key.split(":", 1)[1])
                if n > 1:
                    adjacent_paragraph_keys.add(f"paragraph:{n-1}")
                adjacent_paragraph_keys.add(f"paragraph:{n+1}")
            except Exception:
                pass
    if explicit_location_keys:
        for f in fragment_index:
            fkeys = _source_location_keys(f.get("source_location"))
            if fkeys & explicit_location_keys:
                item = dict(f)
                item["source_location_completion_scope"] = "EXACT_CITED_LOCATION"
                location_candidates.append(item)
            elif fkeys & adjacent_paragraph_keys:
                # V0.77 one-paragraph continuation recovery is deliberately narrow. The fragment
                # is only a candidate here; actual attachment still requires critical-token or
                # material behavior similarity below.
                item = dict(f)
                item["source_location_completion_scope"] = "ADJACENT_PARAGRAPH_CONTINUATION"
                location_candidates.append(item)
    completion_candidates = list({str(f.get("source_fact_fragment_id") or id(f)): f for f in (candidates + location_candidates)}.values())
    scored = []
    for f in candidates:
        txt = str(f.get("source_excerpt") or "")
        score = _token_similarity(txt, req_text)
        if _numeric_compatible(txt, req_text):
            scored.append((score, f))
    selected: list[dict[str, Any]] = []
    if scored:
        # V0.66 minimum-ownership rule: a fragment must be materially related to the Canonical
        # behavior, and weak clauses from the same composite paragraph are not inherited merely
        # because the parent Semantic Unit matched. Keep the best material matches only.
        best = max(score for score, _ in scored)
        threshold = max(0.35, best - 0.35)
        for score, f in scored:
            if score < threshold:
                continue
            item = dict(f)
            item["ownership_match_score"] = round(score, 3)
            item["ownership_policy"] = "V0.66_MINIMUM_MATERIAL_MATCH"
            selected.append(item)

    # V0.73 critical-fact completion. Similarity alone can drop a short table/exception clause
    # that carries a material signal, enum, retry count, or timing threshold already retained by
    # the Canonical requirement. Search only inside already-matched Semantic Units and add the
    # minimum exact fragments needed to own those critical facts.
    req_groups = _critical_ownership_token_groups(ownership_text)
    req_critical = set().union(*req_groups.values())
    covered: set[str] = set()
    for item in selected:
        covered |= _critical_ownership_tokens(str(item.get("source_excerpt") or ""))
    missing = req_critical - covered
    if missing:
        selected_ids = {str(x.get("source_fact_fragment_id") or "") for x in selected}
        ranked_completion = []
        for f in completion_candidates:
            fid = str(f.get("source_fact_fragment_id") or "")
            if fid and fid in selected_ids:
                continue
            txt = str(f.get("source_excerpt") or "")
            groups = _critical_ownership_token_groups(txt)
            overlap = missing & set().union(*groups.values())
            if not overlap:
                continue
            strong = bool(req_groups["identifiers"] & groups["identifiers"] & missing) or bool(req_groups["timing"] & groups["timing"] & missing) or bool(req_groups["retry"] & groups["retry"] & missing)
            # Hex-only overlap can be ambiguous in dense tables. Require additional material
            # similarity or two matching critical facts before accepting it automatically.
            if not strong and not (len(overlap) >= 2 or _token_similarity(txt, req_text) >= 0.20):
                continue
            ranked_completion.append((len(overlap), _token_similarity(txt, req_text), f, overlap))
        ranked_completion.sort(key=lambda x: (-x[0], -x[1], str(x[2].get("source_location") or ""), int(x[2].get("fragment_index") or 0)))
        for _, score, f, overlap in ranked_completion:
            useful = missing & overlap
            if not useful:
                continue
            item = dict(f)
            item["ownership_match_score"] = round(score, 3)
            item["ownership_policy"] = (
                "V0.73_CRITICAL_FACT_COMPLETION"
                if str(f.get("parent_source_semantic_unit_id") or "") in matched_unit_ids
                else "V0.74_SOURCE_BOUNDED_CRITICAL_FACT_COMPLETION"
            )
            item["ownership_completion_tokens"] = sorted(useful)
            selected.append(item)
            missing -= useful
            if not missing:
                break

    # V0.77 source-bounded behavior completion. Critical-token completion cannot recover a
    # materially important clause that contains no signal/timing/retry literal (for example
    # "IGN on이면 남은 과정을 생략하고 종료" or "mirror 실패가 캡처를 종료시키지 않음").
    # For each Canonical behavior clause, attach at most one high-similarity Source fragment from
    # the already matched or explicitly cited Source location. A one-paragraph continuation is
    # allowed only at a stricter threshold. No new behavior sentence is generated.
    canonical_clauses = [x.strip() for x in _split_behavior_clauses(ownership_text) if x and x.strip()]
    selected_ids = {str(x.get("source_fact_fragment_id") or "") for x in selected}
    for clause in canonical_clauses:
        if not (_has_requirement_force(clause) or _software_like_behavior_terms(clause) or _critical_ownership_tokens(clause)):
            continue
        if any(_token_similarity(str(x.get("source_excerpt") or ""), clause) >= 0.36 for x in selected):
            continue
        ranked: list[tuple[float, dict[str, Any]]] = []
        for f in completion_candidates:
            fid = str(f.get("source_fact_fragment_id") or "")
            if fid and fid in selected_ids:
                continue
            ftxt = str(f.get("source_excerpt") or "")
            if not ftxt or not _numeric_compatible(ftxt, clause):
                continue
            score = _token_similarity(ftxt, clause)
            scope = str(f.get("source_location_completion_scope") or "")
            threshold = 0.46 if scope == "ADJACENT_PARAGRAPH_CONTINUATION" else 0.34
            if score >= threshold:
                ranked.append((score, f))
        if not ranked:
            continue
        ranked.sort(key=lambda x: (-x[0], str(x[1].get("source_location") or ""), int(x[1].get("fragment_index") or 0)))
        score, f = ranked[0]
        item = dict(f)
        item["ownership_match_score"] = round(score, 3)
        item["ownership_policy"] = (
            "V0.77_ADJACENT_PARAGRAPH_BEHAVIOR_COMPLETION"
            if str(f.get("source_location_completion_scope") or "") == "ADJACENT_PARAGRAPH_CONTINUATION"
            else "V0.77_SOURCE_BOUNDED_BEHAVIOR_COMPLETION"
        )
        item["ownership_completion_clause"] = clause[:500]
        selected.append(item)
        if fid:
            selected_ids.add(fid)

    if selected:
        dedup = {}
        for item in selected:
            key = str(item.get("source_fact_fragment_id") or "") or json.dumps(item, ensure_ascii=False, sort_keys=True)
            dedup[key] = item
        result = list(dedup.values())
        result.sort(key=lambda x: (str(x.get("source_location") or ""), int(x.get("fragment_index") or 0)))
        return result

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


def _allocation_for_text(source_text: str, generated_text: str = "") -> dict[str, Any]:
    """Classify verification ownership from Source-backed domain and behavior evidence.

    V0.77 keeps high-confidence non-software domains conservative, but no longer requires the
    literal word ``SW`` for every controller behavior. A Source clause that names a controller/
    ECU-like actor and an executable software-like behavior may be promoted as an *inferred*
    software-behavior candidate. The inference is explicitly review-required and never creates
    missing signals, values, timing, thresholds, or acceptance criteria.
    """
    s = (source_text or "").lower()
    g = (generated_text or "").lower()
    combined = f"{s} {g}"

    positive_sw_evidence = _explicit_sw_allocation_evidence(source_text)
    inferred_sw_evidence = _inferred_controller_software_behavior_evidence(source_text)
    # Generated wording may help identify an already explicit Source concept, but generated text
    # alone must never create software ownership. Therefore only Source evidence is authoritative.
    sw_positive = bool(positive_sw_evidence)
    sw_inferred = bool(inferred_sw_evidence)

    connector = bool(re.search(r"커넥터|connector|lead[- ]?wire|\bdip\b|핀\s*(?:간격|이격)|pin\s*spacing|전원단\s*[+＋-]|단자", s, re.I))
    solder = bool(re.search(r"자동\s*납땜|납땜|solder", s, re.I))
    coating = bool(re.search(r"coating|코팅", s, re.I))
    env = bool(re.search(r"사용\s*온도|보존\s*온도|환경\s*시험|environmental|storage\s*temperature|operating\s*temperature|진동|습도", s, re.I))
    electrical_metric = bool(re.search(r"정격\s*전압|최대\s*소비\s*전류|암전류|rated\s*voltage|current\s*consumption|max(?:imum)?\s*current", s, re.I))
    external_ref = bool(re.search(r"따른다|참조한다|reference", s, re.I) and re.search(r"\b(?:ES|MS|ISO|IEC|SAE|ASTM|KS|UN|IEEE)\s*[A-Za-z0-9_.-]*\d[A-Za-z0-9_.-]*\b|규격|specification", s, re.I))
    multi_element = bool(re.search(r"\bmaster\b|\bslave\b|시스템|제어기|network|네트워크|\bcan\b|\blin\b|transceiver|obd", combined, re.I))
    active_behavior = _has_requirement_force(s) or bool(re.search(r"reset|check.?sum|복구|저장|검사|제어|전환|수신|송신", s, re.I))

    def result(level: str, status: str, swe1: str, swe6: str, domain: str, rationale: str, *, confidence: str, evidence_type: str = "", evidence: list[str] | None = None, inferred_evidence: list[str] | None = None, review_required: bool = False) -> dict[str, Any]:
        return {
            "requirement_level": level,
            "allocation_status": status,
            "swe1_eligibility": swe1,
            "swe6_eligibility": swe6,
            "verification_domain": domain,
            "allocation_rationale": rationale,
            "allocation_confidence": confidence,
            "software_allocation_evidence_type": evidence_type,
            "positive_sw_allocation_evidence": list(evidence or []),
            "software_behavior_inference_evidence": list(inferred_evidence or []),
            "software_allocation_review_required": bool(review_required),
        }

    # High-confidence non-SW source domains take precedence unless Source-positive SW evidence exists.
    if (solder or coating) and not sw_positive:
        return result("Manufacturing Process", "MANUFACTURING_PROCESS_REQUIREMENT", "Not Applicable", "Not Applicable", "Manufacturing Process Verification",
                      "Source evidence is a soldering/coating/manufacturing-process constraint; software implementation responsibility is not indicated.", confidence="HIGH")
    if connector and not sw_positive:
        return result("Hardware/Mechanical", "MECHANICAL_CONNECTOR_REQUIREMENT", "Not Applicable", "Not Applicable", "Mechanical / Connector Verification",
                      "Source evidence is a physical connector/pin/spacing constraint; software implementation responsibility is not indicated.", confidence="HIGH")
    if env and not sw_positive:
        return result("Environmental Qualification", "ENVIRONMENTAL_QUALIFICATION_REQUIREMENT", "Not Applicable", "Not Applicable", "Environmental Qualification",
                      "Source evidence is an environmental/storage/qualification constraint; software implementation responsibility is not indicated.", confidence="HIGH")
    if electrical_metric and not sw_positive:
        return result("Electrical", "ELECTRICAL_REQUIREMENT", "Not Applicable", "Not Applicable", "Electrical Verification",
                      "Source evidence is an electrical performance/limit fact; software implementation responsibility is not indicated.", confidence="HIGH")
    if external_ref and not active_behavior:
        return result("External Reference", "EXTERNAL_STANDARD_REFERENCE", "Not Applicable", "Not Applicable", "External Standard Evidence Required",
                      "Source delegates detailed criteria to an external specification; missing external contents are not invented.", confidence="HIGH")

    interface_fact = bool(re.search(
        r"(?:\bCAN\b|\bLIN\b|\bEthernet\b|\bFlexRay\b).*?(?:kbit/s|kbps|mbit/s|mbps|baud|bitrate|\bNM\b\s*(?:지원|support))|"
        r"(?:kbit/s|kbps|mbit/s|mbps|baud|bitrate).*?(?:\bCAN\b|\bLIN\b|\bEthernet\b|\bFlexRay\b)",
        s, re.I,
    ))
    if interface_fact and not active_behavior and not sw_positive:
        return result("System / Interface Fact", "INTERFACE_FACT_PENDING_SW_ALLOCATION", "Review Needed", "Deferred pending SW allocation", "System Integration / Interface Allocation Review",
                      "Source provides an interface/configuration fact, but positive software implementation responsibility is not confirmed.", confidence="MEDIUM")

    if sw_positive:
        evidence_type = "EXPLICIT_SOFTWARE_CONTEXT" if any(re.search(r"software|소프트웨어|s\s*/\s*w|\bsw\b", x, re.I) for x in positive_sw_evidence) else "SOFTWARE_STRUCTURAL_CONSTRAINT"
        return result("Software", "SW_IMPLEMENTATION_REQUIREMENT", "Eligible", "Eligible", "SWE.6 Software Qualification",
                      "Positive software allocation/structural evidence exists in the Source fact.", confidence="HIGH", evidence_type=evidence_type, evidence=positive_sw_evidence)

    # V0.77 practical promotion policy: controller/ECU behaviors that are explicitly present in
    # Source and look executable by software may enter Main SWE.1 and SWE.6 candidate generation
    # even when the Source does not literally say "software".  This is a review-required modeling
    # inference, not positive allocation evidence; Official Release remains blocked until reviewed.
    if sw_inferred:
        return result(
            "Software Candidate", "SW_BEHAVIOR_INFERRED_REVIEW_REQUIRED", "Eligible", "Eligible",
            "SWE.6 Software Qualification (Allocation Review Required)",
            "Source names a controller/ECU-like actor performing an executable software-like behavior. V0.77 permits review-required SWE.1/SWE.6 candidate promotion without treating the inference as explicit software allocation.",
            confidence="MEDIUM", evidence_type="INFERRED_CONTROLLER_SOFTWARE_BEHAVIOR",
            inferred_evidence=inferred_sw_evidence, review_required=True,
        )

    if active_behavior or multi_element:
        return result("System", "SYSTEM_REQUIREMENT_PENDING_SW_ALLOCATION", "Review Needed", "Deferred pending SW allocation", "System Integration / SYS.5",
                      "Source states controller/system behavior, but no positive Source-backed software allocation evidence is present.", confidence="MEDIUM")

    return result("System / Unallocated", "SYSTEM_REQUIREMENT_PENDING_SW_ALLOCATION", "Review Needed", "Deferred pending SW allocation", "System Integration / SYS.5",
                  "No positive Source-backed software allocation evidence is present; absence of non-software evidence is not treated as software allocation evidence.", confidence="LOW")


def _explicit_sw_allocation_evidence(text: str) -> list[str]:
    """Return only positive Source evidence that reasonably supports software ownership."""
    raw = _norm(text)
    findings: list[str] = []
    patterns = [
        # Explicit software wording, including common S/W notation.
        r"(?:software|소프트웨어|\bSW\b|S\s*/\s*W).{0,100}(?:담당|책임|구현|설정|구성|제어|오류|요구|requirement|configure|implement)?",
        r"(?:담당|책임|구현|설정|구성|configure|implement).{0,100}(?:software|소프트웨어|\bSW\b|S\s*/\s*W)",
        # Structural software concepts are positive evidence even when the word SW is omitted.
        r"\b(?:Task|ISR|Runnable|SWC|RTE|BSW|ASW|scheduler)\b.{0,100}(?:제약|순서|우선|실행|호출|배치|위치|금지|해야|shall|must)?",
        r"(?:Watchdog|WDT).{0,100}\b(?:Task|ISR|scheduler)\b|\b(?:Task|ISR|scheduler)\b.{0,100}(?:Watchdog|WDT)",
    ]
    for pat in patterns:
        for m in re.finditer(pat, raw, re.I):
            value = m.group(0).strip()
            if value:
                findings.append(value)
    return list(dict.fromkeys(findings))


def _software_like_behavior_terms(text: str) -> list[str]:
    """Return literal software-like action terms that already exist in Source text.

    The list is intentionally behavior-oriented. Generic "operate/동작" by itself is excluded so
    environmental/electrical/system-level operating statements are not promoted merely because a
    controller noun is nearby.
    """
    raw = _norm(text)
    terms = []
    patterns = [
        r"저장|기록|송신|송출|수신|판단|제어|전환|처리|계산|변환|병합|재시도|복구|확인|검사|비교|선택|설정|초기화|종료|시작|요청|응답|활성화|비활성화|인코딩|디코딩",
        r"check.?sum|checksum|reset|retry|recover|restore|store|save|transmit|receive|send|publish|subscribe|determine|decide|calculate|process|convert|merge|compare|select|configure|initialize|terminate|start|request|respond|enable|disable|encode|decode|validate|verify",
    ]
    for pat in patterns:
        for m in re.finditer(pat, raw, re.I):
            value = m.group(0).strip()
            if value and value not in terms:
                terms.append(value)
    return terms


def _inferred_controller_software_behavior_evidence(text: str) -> list[str]:
    """Return Source-backed evidence for V0.77 inferred controller software behavior.

    This is deliberately narrower than "not hardware". It requires (1) a controller/ECU-like
    actor in the Source and (2) an explicit executable software-like action. Protocol names alone,
    pure system statements, or physical/electrical/environmental facts do not qualify.
    """
    raw = _norm(text)
    if not raw:
        return []
    # V0.82 trigger/condition boundary: a condition fragment is not positive or inferred
    # software ownership evidence merely because it contains a software-like verb token such as
    # 수신/변환.  Examples include "ERR PIN ... 변환 시", "B+ 인가 시", or a wake event.
    # The enclosing controller requirement may still be inferred as software-like when it contains
    # an explicit consequent control action (판단/전환/제어/etc.).
    if re.search(r"(?:\s|^)(?:시|경우|때)\s*$", raw, re.I):
        return []
    actor_hits: list[str] = []
    actor_patterns = [
        r"(?:[가-힣A-Za-z0-9_ -]{0,36}(?:제어기|컨트롤러))\s*(?:은|는|이|가|에서)",
        r"(?<![A-Za-z0-9_])(?:ECU|electronic\s+control\s+unit|controller|control\s+unit)(?![A-Za-z0-9_])",
        # Common specification style: acronym actor + Korean topic/subject particle, e.g. HU는.
        r"(?<![A-Za-z0-9_])(?!CAN(?![A-Za-z0-9_])|LIN(?![A-Za-z0-9_])|ETHERNET(?![A-Za-z0-9_])|FLEXRAY(?![A-Za-z0-9_])|NM(?![A-Za-z0-9_]))[A-Z][A-Z0-9_]{1,15}(?![A-Za-z0-9_])\s*(?:은|는|이|가|에서)",
    ]
    for pat in actor_patterns:
        for m in re.finditer(pat, raw, re.I):
            value = m.group(0).strip()
            if value and value not in actor_hits:
                actor_hits.append(value)
    behavior_hits = _software_like_behavior_terms(raw)
    if not actor_hits or not behavior_hits:
        return []
    evidence = [f"actor={actor_hits[0]}", f"behavior={behavior_hits[0]}"]
    # Keep a short literal excerpt for reviewer drill-down without generating a new fact.
    excerpt = raw[:220].strip()
    if excerpt:
        evidence.append(f"source_excerpt={excerpt}")
    return evidence


def _structured_source_facts(text: str, *, unit_id: str = "", location: str = "") -> list[dict[str, Any]]:
    """Extract conservative Source fact objects for trace/audit and table joins.

    These records never create a requirement or test value.  They merely structure literal facts
    already present in a linked Source unit so values that *do* exist in tables are not lost.
    """
    raw = _norm(text)
    if not raw:
        return []
    identifiers = _engineering_identifiers(raw)
    external_spec_identifiers = list(dict.fromkeys(re.findall(
        r"\b(?:ES|MS|ISO|IEC|SAE|ASTM|KS|UN|IEEE|J)\s*[A-Za-z0-9_.-]*\d[A-Za-z0-9_.-]*\b",
        raw, re.I,
    )))
    # External specification IDs such as ES995480-00 are identifiers, not numeric ranges.
    numeric_scan_text = raw
    for spec_id in external_spec_identifiers:
        numeric_scan_text = numeric_scan_text.replace(spec_id, " ")
    numeric = list(dict.fromkeys(re.findall(
        r"(?<![A-Za-z0-9_])(?:0x[0-9A-Fa-f]+|[-+]?\d+(?:\.\d+)?)\s*(?:ms|msec|s|sec|초|V|mV|A|mA|%|℃|°C|mm|회|step|kbit/s|kbps)?",
        numeric_scan_text,
        re.I,
    )))
    enum_pairs = []
    for m in re.finditer(r"\b(0x[0-9A-Fa-f]+|\d+)\s*(?:=|:)\s*([^,;|/]{1,50})", raw):
        enum_pairs.append({"value": m.group(1), "meaning": m.group(2).strip()})
    range_tokens = list(dict.fromkeys(re.findall(
        r"(?:0x[0-9A-Fa-f]+|[-+]?\d+(?:\.\d+)?)\s*(?:~|～|-)\s*(?:0x[0-9A-Fa-f]+|[-+]?\d+(?:\.\d+)?)\s*(?:ms|s|V|mV|A|mA|%|℃|mm)?",
        numeric_scan_text, re.I,
    )))
    relations = []
    for m in re.finditer(r"(0x[0-9A-Fa-f]+|[-+]?\d+(?:\.\d+)?)\s*(?:ms|s|V|mV|A|mA|%|℃|mm)?\s*(이상|이하|초과|미만|이내)", raw, re.I):
        relations.append(m.group(0).strip())
    timing = [x for x in numeric if re.fullmatch(r"[-+]?\d+(?:\.\d+)?\s*(?:ms|msec|sec|초|s)", x.strip(), re.I)]
    communication_bitrate = bool(re.search(r"\b(?:CAN|LIN|Ethernet|FlexRay)\b.*?\d+(?:\.\d+)?\s*(?:kbit/s|kbps|mbit/s|mbps|baud)\b|\d+(?:\.\d+)?\s*(?:kbit/s|kbps|mbit/s|mbps|baud)\b.*?\b(?:CAN|LIN|Ethernet|FlexRay)\b", raw, re.I))
    # V0.66: PROHIBITION is reserved for explicit negative normative relations.
    # Words such as "의도하지 않은" or "불가능한 경우" describe a failure/recovery context,
    # not a prohibition by themselves. Invalid/reserved markers are handled separately below.
    prohibited = bool(re.search(
        r"금지(?:한다|된다|되어야)?|하지\s*않아야|해서는\s*안|할\s*수\s*없|"
        r"연동되지\s*않|사용\s*불가|shall\s+not|must\s+not",
        raw, re.I,
    ))
    failure_handling = bool(re.search(
        r"(?:오류|고장|fault|error|invalid|이상).{0,80}(?:복구|복귀|reset|초기화|안전\s*상태|fallback)|"
        r"(?:복구|복귀|reset|초기화|안전\s*상태|fallback).{0,80}(?:오류|고장|fault|error|invalid|이상)",
        raw, re.I,
    ))
    fact_type = "SOURCE_LITERAL_FACT"
    if external_spec_identifiers and not identifiers and not numeric:
        fact_type = "EXTERNAL_SPEC_IDENTIFIER"
    elif communication_bitrate:
        fact_type = "COMMUNICATION_BITRATE"
    elif enum_pairs:
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
    elif failure_handling:
        fact_type = "FAILURE_HANDLING_REQUIREMENT"

    # V0.65 separates the semantic role of a table value from the literal fact type.
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
        "external_spec_identifiers": external_spec_identifiers,
        "numeric_values": numeric,
        "timing_values": timing,
        "range_values": range_tokens,
        "explicit_relations": relations,
        "enum_mappings": enum_pairs,
        "prohibition": prohibited,
        "failure_handling": failure_handling,
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
    parent_inferred = str(parent_alloc.get("allocation_status") or "") == "SW_BEHAVIOR_INFERRED_REVIEW_REQUIRED"
    allocation_inheritance = "FACT_LEVEL_CLASSIFIED"
    allocation_override = False
    allocation_override_reason = ""
    # V0.65 invariant: a child Source fact cannot silently outrank a conservative parent
    # allocation.  Only explicit SW responsibility in the same Source fact may override it.
    if parent_pending and not override_evidence and (str(alloc.get("swe6_eligibility") or "") == "Eligible" or str(alloc.get("swe6_eligibility") or "").startswith("Deferred")):
        alloc = {
            **alloc,
            "requirement_level": parent_alloc.get("requirement_level") or alloc.get("requirement_level") or "System",
            "allocation_status": "INHERIT_PARENT_ALLOCATION_PENDING",
            "swe1_eligibility": "Review Needed",
            "swe6_eligibility": "Deferred pending SW allocation",
            "verification_domain": parent_alloc.get("verification_domain") or alloc.get("verification_domain") or "System Integration / SYS.5",
            "allocation_rationale": "Parent requirement is pending software allocation; child fact inherits that decision because no explicit fact-level SW allocation evidence exists.",
        }
        allocation_inheritance = "PARENT_ALLOCATION_INHERITED_PENDING"
    elif parent_pending and str(alloc.get("swe6_eligibility") or "") == "Eligible" and override_evidence:
        allocation_override = True
        allocation_inheritance = "EXPLICIT_FACT_LEVEL_OVERRIDE"
        allocation_override_reason = "Explicit SW allocation wording exists in the same Source fact."
    elif parent_inferred and str(alloc.get("allocation_status") or "") == "SYSTEM_REQUIREMENT_PENDING_SW_ALLOCATION" and _software_like_behavior_terms(source_text):
        # A short fragment such as "1회 재시도한다" may omit the controller subject even though
        # its parent Source-backed requirement clearly names one. Preserve the review-required
        # inferred software scope for software-like child behavior, but do not inherit it across
        # electrical/mechanical/environmental/manufacturing classifications.
        alloc = {
            **alloc,
            "requirement_level": "Software Candidate",
            "allocation_status": "SW_BEHAVIOR_INFERRED_REVIEW_REQUIRED",
            "swe1_eligibility": "Eligible",
            "swe6_eligibility": "Eligible",
            "verification_domain": "SWE.6 Software Qualification (Allocation Review Required)",
            "allocation_rationale": "Child fact inherits the V0.77 review-required controller software-behavior inference because the Source fragment contains an executable software-like action and no high-confidence non-software domain evidence.",
            "allocation_confidence": "MEDIUM",
            "software_allocation_evidence_type": "INFERRED_CONTROLLER_SOFTWARE_BEHAVIOR_INHERITED",
            "software_behavior_inference_evidence": list(parent_alloc.get("software_behavior_inference_evidence") or []),
            "software_allocation_review_required": True,
        }
        allocation_inheritance = "PARENT_INFERRED_SOFTWARE_BEHAVIOR_INHERITED"
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
        "allocation_confidence": alloc.get("allocation_confidence"),
        "software_allocation_evidence_type": alloc.get("software_allocation_evidence_type"),
        "positive_sw_allocation_evidence": list(alloc.get("positive_sw_allocation_evidence") or []),
        "software_behavior_inference_evidence": list(alloc.get("software_behavior_inference_evidence") or []),
        "software_allocation_review_required": bool(alloc.get("software_allocation_review_required")),
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



def _e2e_engineering_projection(req: dict[str, Any]) -> None:
    """V0.80 project one Canonical Engineering Requirement into SYS/SWE views.

    The Canonical requirement remains the single truth.  SYS.1/SWE.1 and SYS.5/SWE.6 are
    *views/allocation projections*, not independent regenerated requirements.  A fact that is not
    SWE.1/SWE.6 eligible is therefore never interpreted as "not a requirement" or "not verifiable".
    High-confidence HW/Electrical/Environmental/Manufacturing facts remain in the Engineering Main
    view and their native verification domain rather than being forced into SYS/SWE.
    """
    allocation = str(req.get("allocation_status") or "")
    level = str(req.get("requirement_level") or "")
    parent_domain = str(req.get("verification_domain") or "")
    fact_allocs = [x for x in (req.get("fact_level_allocations") or []) if isinstance(x, dict)]
    raw_domains = []
    for value in [parent_domain] + [str(x.get("verification_domain") or "") for x in fact_allocs]:
        value = _norm(value)
        if value and value not in raw_domains:
            raw_domains.append(value)

    def domain_family(text: str) -> str:
        low = text.lower()
        if "swe.6" in low or "software qualification" in low:
            return "Software"
        if "sys.5" in low or "system integration" in low or "system qualification" in low or "interface allocation" in low:
            return "System"
        if "electrical" in low:
            return "Electrical"
        if "environment" in low:
            return "Environmental"
        if "manufactur" in low or "solder" in low or "coating" in low:
            return "Manufacturing"
        if "mechanical" in low or "connector" in low or "hardware" in low:
            return "Hardware/Mechanical"
        if "external" in low or "standard" in low:
            return "External Dependency"
        return ""

    engineering_domains: list[str] = []
    for value in raw_domains:
        fam = domain_family(value)
        if fam and fam not in engineering_domains:
            engineering_domains.append(fam)
    if not engineering_domains:
        low_level = level.lower()
        if "software" in low_level:
            engineering_domains.append("Software")
        elif "system" in low_level:
            engineering_domains.append("System")
        elif "electrical" in low_level:
            engineering_domains.append("Electrical")
        elif "environment" in low_level:
            engineering_domains.append("Environmental")
        elif "manufactur" in low_level:
            engineering_domains.append("Manufacturing")
        elif "mechanical" in low_level or "hardware" in low_level:
            engineering_domains.append("Hardware/Mechanical")
        elif "external" in low_level:
            engineering_domains.append("External Dependency")
        else:
            engineering_domains.append("Unallocated Engineering")

    has_system_fact = (
        allocation.startswith("SYSTEM_REQUIREMENT")
        or allocation.startswith("INTERFACE_FACT")
        or any(domain_family(x) == "System" for x in raw_domains)
    )
    is_inferred_sw = allocation == "SW_BEHAVIOR_INFERRED_REVIEW_REQUIRED"
    is_explicit_sw = allocation == "SW_IMPLEMENTATION_REQUIREMENT"
    has_sw_fact = is_inferred_sw or is_explicit_sw or any(domain_family(x) == "Software" for x in raw_domains)

    # Until an inferred controller behavior receives allocation sign-off, it remains a valid
    # System Requirement candidate *and* a review-required Software Requirement candidate.
    if has_system_fact or is_inferred_sw:
        sys1 = "Eligible"
    elif is_explicit_sw:
        sys1 = "Not Applicable"
    elif allocation == "EXTERNAL_STANDARD_REFERENCE":
        sys1 = "Review Needed"
    else:
        sys1 = "Not Applicable"

    if has_system_fact:
        sys5 = "Eligible"
    elif is_inferred_sw:
        sys5 = "Review Needed"
    elif allocation == "EXTERNAL_STANDARD_REFERENCE":
        sys5 = "Deferred - External Dependency"
    else:
        sys5 = "Not Applicable"

    # Preserve existing software eligibility as authoritative; expose symmetric system fields.
    req["sys1_eligibility"] = sys1
    req["sys5_eligibility"] = sys5
    req["engineering_domains"] = engineering_domains
    req["verification_domains"] = raw_domains

    review_text = _norm([
        req.get("clarification_needed"), req.get("conflicts"), req.get("open_issue_ids"),
        req.get("tbd_items"), req.get("requirement_status"),
    ])
    change_pending = bool(re.search(
        r"(?:proposed|proposal|change[ -]?pending|제안|변경\s*(?:예정|제안|필요)|최종\s*(?:기준|인터페이스|적용)\s*확인|"
        r"적용\s*버전|이슈\s*(?:해결|대응)|불명확|상충)",
        review_text, re.I,
    ))
    human_required = bool(
        is_inferred_sw
        or str(req.get("swe1_eligibility") or "") == "Review Needed"
        or sys1 == "Review Needed"
        or str(req.get("requirement_status") or "") in {"Review Needed", "Blocked"}
        or review_text
        or req.get("cross_domain_bundle_review_required")
        or change_pending
    )
    req["canonical_state"] = (
        "PROPOSED_CHANGE_PENDING" if change_pending
        else "CANONICAL_REVIEW_REQUIRED" if human_required
        else "CANONICAL_SOURCE_BACKED"
    )
    req["review_status"] = "HUMAN_DECISION_REQUIRED" if human_required else "SOURCE_BACKED"
    req["human_decision_required"] = human_required
    req["main_spec_visibility"] = True
    req["review_view_visibility"] = True
    req["official_release_eligible"] = bool(
        not human_required and str(req.get("requirement_status") or "") == "Approved"
    )
    hold_reasons: list[str] = []
    if is_inferred_sw:
        hold_reasons.append("Software allocation pending human review")
    if change_pending:
        hold_reasons.append("Proposed/change-pending Source fact requires authoritative decision")
    if req.get("cross_domain_bundle_review_required"):
        hold_reasons.append("Cross-domain fact bundle requires domain review")
    if str(req.get("swe1_eligibility") or "") == "Review Needed":
        hold_reasons.append("Software allocation/eligibility review pending")
    if sys1 == "Review Needed":
        hold_reasons.append("System requirement allocation review pending")
    req["hold_reason"] = "; ".join(dict.fromkeys(hold_reasons))


def apply_allocation_gate(req: dict[str, Any], matched_units: list[dict[str, Any]] | None = None) -> None:
    """Apply parent allocation plus fact-level allocation without automatic SRS splitting.

    V0.65 retains parent->child inheritance and separates primary verification domains from external
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

    # V0.73: Source Evidence may contain an exact page/table anchor with a shortened paraphrase.
    # If the Canonical requirement retains a critical signal/timing/enum fact and that fact exists
    # in a unit at the explicitly cited location, preserve that unit as an additional Source anchor.
    # A lone generic hex literal is not enough; require identifier/timing/retry overlap, or at least
    # two critical-token overlaps. This remains conservative and never creates new domain facts.
    req_groups = _critical_ownership_token_groups(_req_text(req))
    req_critical = set().union(*req_groups.values())
    for ev in evidence_items:
        loc = _norm(ev.get("location"))
        if not loc:
            continue
        for u in units:
            if not _loc_match(loc, str(u.get("source_location") or "")):
                continue
            unit_groups = _critical_ownership_token_groups(str(u.get("source_excerpt") or ""))
            overlap = req_critical & set().union(*unit_groups.values())
            strong_overlap = bool(req_groups["identifiers"] & unit_groups["identifiers"]) or bool(req_groups["timing"] & unit_groups["timing"]) or bool(req_groups["retry"] & unit_groups["retry"]) or len(overlap) >= 2
            if strong_overlap and _numeric_compatible(_norm(ev.get("text")), str(u.get("source_excerpt") or "")) and u not in matched:
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


def _augment_atomic_behaviors_from_fragments(req: dict[str, Any]) -> None:
    """Backfill Source-owned fragments that are missing from pre-existing atomic behaviors.

    V0.65 does not replace AI-produced atomic behaviors and does not split an SRS mechanically.
    It only appends exact Source fragments already owned by the requirement when no existing atom
    materially represents that fragment.  This closes the case where a compound OR/list Source
    survives in the Canonical sentence but one list member disappears from child-intent trace.
    """
    if str(req.get("swe1_eligibility") or "Eligible") == "Not Applicable":
        return
    fragments = [x for x in (req.get("source_fact_fragments") or []) if isinstance(x, dict)]
    if not fragments:
        return
    atoms = [x for x in (req.get("source_backed_atomic_behaviors") or []) if isinstance(x, dict)]
    req_text = " ".join([_req_text(req), _source_text(req)])

    for frag in fragments:
        frag_text = str(frag.get("source_excerpt") or "").strip()
        if not frag_text:
            continue
        # Ownership itself is not enough: the fragment must also materially match the current
        # requirement. This prevents unrelated clauses from the same paragraph being appended.
        if _token_similarity(frag_text, req_text) < 0.34 or not _numeric_compatible(frag_text, req_text):
            continue
        fid = str(frag.get("source_fact_fragment_id") or "")
        represented = False
        for atom in atoms:
            if fid and str(atom.get("source_fact_fragment_id") or "") == fid:
                represented = True
                break
            atom_text = str(atom.get("behavior_text") or atom.get("source_fact") or "").strip()
            if atom_text and _numeric_compatible(frag_text, atom_text) and _token_similarity(frag_text, atom_text) >= 0.82:
                # V0.66: text-equivalent atoms recovered before fragment indexing must inherit
                # the exact Source Fact Fragment ID instead of merely suppressing a duplicate atom.
                if fid and not str(atom.get("source_fact_fragment_id") or ""):
                    atom["source_fact_fragment_id"] = fid
                    atom.setdefault("source_semantic_unit_id", frag.get("parent_source_semantic_unit_id"))
                    atom.setdefault("source_chunk_id", frag.get("source_chunk_id"))
                    atom.setdefault("source_location", frag.get("source_location"))
                    atom["fragment_link_backfilled"] = True
                represented = True
                break
        if represented:
            continue
        unit = {
            "source_semantic_unit_id": frag.get("parent_source_semantic_unit_id"),
            "source_chunk_id": frag.get("source_chunk_id"),
            "source_location": frag.get("source_location"),
            "source_excerpt": frag_text,
            "source_unit_type": "fact_fragment",
            "coverage_eligibility": "semantic_unit",
            "source_fact_fragment_id": fid,
        }
        atom = _source_backed_atom(unit, preservation_reason="fact_fragment_backfill")
        if fid:
            atom["source_fact_fragment_id"] = fid
        atoms.append(atom)

    req["source_backed_atomic_behaviors"] = atoms



def _requirement_ownership_text(req: dict[str, Any]) -> str:
    return _norm([
        req.get("function_name"), req.get("requirement"), req.get("activation_trigger"),
        req.get("preconditions"), req.get("processing_action"), req.get("output"),
        req.get("acceptance_criteria"),
    ]).lower()


def _disambiguate_shared_fragment_ownership(reqs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove clear parent-child leakage while preserving legitimate shared Source ownership.

    V0.75 adds a critical-fact retention guard.  A shared fragment must not be removed from a
    claimant when that fragment contains a signal/timing/hex/retry token that the claimant's own
    Canonical behavior asserts.  This prevents dominant-parent cleanup from orphaning shared
    governing clauses (for example, a one-retry rule that applies to two sibling capture SRS).
    Non-critical semantic leakage continues to use the V0.74 dominant-parent rule.
    """
    claims: dict[str, list[tuple[dict[str, Any], dict[str, Any], float]]] = {}
    for req in reqs:
        rtext = _requirement_ownership_text(req)
        for frag in [x for x in (req.get("source_fact_fragments") or []) if isinstance(x, dict)]:
            fid = str(frag.get("source_fact_fragment_id") or "")
            if not fid:
                continue
            score = _token_similarity(str(frag.get("source_excerpt") or ""), rtext)
            claims.setdefault(fid, []).append((req, frag, score))

    records: list[dict[str, Any]] = []
    for fid, members in claims.items():
        unique = {str(req.get("srs_id") or req.get("candidate_id") or id(req)): (req, frag, score) for req, frag, score in members}
        vals = list(unique.values())
        if len(vals) < 2:
            continue
        vals.sort(key=lambda x: x[2], reverse=True)
        best_req, best_frag, best_score = vals[0]
        second_score = vals[1][2]
        best_sid = str(best_req.get("srs_id") or best_req.get("candidate_id") or "")
        clear_dominance = best_score >= 0.42 and (best_score - second_score) >= 0.16
        if not clear_dominance:
            records.append({
                "source_fact_fragment_id": fid,
                "resolution": "SHARED_REVIEW_REQUIRED",
                "claimants": [{"srs_id": str(r.get("srs_id") or r.get("candidate_id") or ""), "similarity": round(sc, 3)} for r, _, sc in vals],
                "source_excerpt": best_frag.get("source_excerpt"),
            })
            continue

        fragment_critical = _critical_ownership_tokens(str(best_frag.get("source_excerpt") or ""))
        removed = []
        preserved_critical = []
        for req, frag, score in vals[1:]:
            sid = str(req.get("srs_id") or req.get("candidate_id") or "")
            if score >= best_score - 0.16:
                continue
            claimant_critical = _critical_ownership_tokens(_requirement_ownership_text(req))
            critical_overlap = sorted(fragment_critical & claimant_critical)
            if critical_overlap:
                preserved_critical.append({
                    "srs_id": sid,
                    "similarity": round(score, 3),
                    "critical_tokens": critical_overlap,
                })
                continue
            req["source_fact_fragments"] = [x for x in (req.get("source_fact_fragments") or []) if not (isinstance(x, dict) and str(x.get("source_fact_fragment_id") or "") == fid)]
            req["source_backed_atomic_behaviors"] = [x for x in (req.get("source_backed_atomic_behaviors") or []) if not (isinstance(x, dict) and str(x.get("source_fact_fragment_id") or "") == fid)]
            req["fact_level_allocations"] = [x for x in (req.get("fact_level_allocations") or []) if not (isinstance(x, dict) and str(x.get("source_fact_fragment_id") or "") == fid)]
            removed.append({"srs_id": sid, "similarity": round(score, 3)})
        if removed or preserved_critical:
            if removed and preserved_critical:
                resolution = "DOMINANT_PARENT_WITH_CRITICAL_SHARED_RETENTION"
            elif removed:
                resolution = "DOMINANT_PARENT_ONLY"
            else:
                resolution = "SHARED_CRITICAL_FACT_PRESERVED"
            records.append({
                "source_fact_fragment_id": fid,
                "resolution": resolution,
                "dominant_srs_id": best_sid,
                "dominant_similarity": round(best_score, 3),
                "removed_claimants": removed,
                "preserved_critical_claimants": preserved_critical,
                "source_excerpt": best_frag.get("source_excerpt"),
            })
    return records




def _source_evidence_matches_semantic_unit(ev: dict[str, Any], unit: dict[str, Any], req_text: str) -> bool:
    """Return True only when an evidence row is materially owned by the semantic unit, not the requirement.

    V0.81 uses this when a Semantic Unit is proven to belong to a different Canonical parent.
    Location equality alone is intentionally insufficient when the evidence text is non-empty; this avoids
    deleting a legitimate sibling fact that happens to share a paragraph/table location.
    """
    if not isinstance(ev, dict):
        return False
    ev_loc = str(ev.get("location") or "")
    unit_loc = str(unit.get("source_location") or "")
    if ev_loc and unit_loc and not _loc_match(ev_loc, unit_loc):
        return False
    ev_text = _norm(ev.get("text"))
    excerpt = _norm(unit.get("source_excerpt"))
    if not excerpt:
        return False
    if not ev_text:
        # A location-only evidence anchor can be removed only when it points exactly to this unit and
        # the unit itself has no material ownership relation to the Canonical requirement.
        return bool(ev_loc and unit_loc and _loc_match(ev_loc, unit_loc) and _token_similarity(excerpt, req_text) < 0.12)
    unit_score = _token_similarity(ev_text, excerpt)
    req_score = _token_similarity(ev_text, req_text)
    return bool(unit_score >= 0.34 and unit_score >= req_score + 0.12)


def _remove_semantic_unit_claim(req: dict[str, Any], unit: dict[str, Any]) -> None:
    """Remove one proven-unrelated Semantic Unit claim from a Canonical requirement.

    This is a trace repair, not requirement generation.  Every child structure derived from the removed
    unit is cleaned together so stale provenance cannot continue to affect allocation/domain projection.
    """
    uid = str(unit.get("source_semantic_unit_id") or "")
    if not uid:
        return
    req["source_semantic_unit_ids"] = [str(x) for x in (req.get("source_semantic_unit_ids") or []) if str(x) != uid]
    req["source_fact_fragments"] = [
        x for x in (req.get("source_fact_fragments") or [])
        if not (isinstance(x, dict) and str(x.get("parent_source_semantic_unit_id") or x.get("source_semantic_unit_id") or "") == uid)
    ]
    for key in ("source_backed_atomic_behaviors", "source_backed_facts", "fact_level_allocations", "source_table_fact_matches"):
        req[key] = [
            x for x in (req.get(key) or [])
            if not (isinstance(x, dict) and str(x.get("source_semantic_unit_id") or x.get("parent_source_semantic_unit_id") or "") == uid)
        ]
    req_text = _requirement_ownership_text(req) or _req_text(req)
    req["source_evidence"] = [
        ev for ev in (req.get("source_evidence") or [])
        if not (isinstance(ev, dict) and _source_evidence_matches_semantic_unit(ev, unit, req_text))
    ]


def _semantic_material_similarity(source_text: str, requirement_text: str) -> float:
    """Token similarity with conservative Korean particle/subtoken tolerance for ownership only."""
    base = _token_similarity(source_text, requirement_text)
    st, rt = _tokens(source_text), _tokens(requirement_text)
    if not st or not rt:
        return base
    matched = 0
    used: set[str] = set()
    for a in st:
        candidates = [b for b in rt if b not in used and len(a) >= 3 and len(b) >= 3 and (a in b or b in a)]
        if candidates:
            b = max(candidates, key=lambda x: min(len(a), len(x)))
            used.add(b)
            matched += 1
    fuzzy = matched / max(1, min(len(st), len(rt)))
    return max(base, fuzzy)


def _disambiguate_shared_semantic_unit_ownership(reqs: list[dict[str, Any]], units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """V0.81 reject clear cross-SRS Semantic Unit leakage before domain projection.

    Previous fragment-level containment could remove a leaked fragment but leave the parent Semantic Unit,
    Source evidence, and already-derived allocation on the wrong SRS.  This pass works one level higher:
    only a *shared* Semantic Unit with a clear materially dominant Canonical owner is auto-cleaned. Ambiguous
    or genuinely shared units remain reviewable. Critical Source tokens asserted by the weaker claimant are
    retained to protect legitimate shared timing/signal/retry rules.
    """
    unit_by_id = {
        str(u.get("source_semantic_unit_id") or ""): u
        for u in units if isinstance(u, dict) and str(u.get("source_semantic_unit_id") or "")
    }
    claims: dict[str, list[tuple[dict[str, Any], float]]] = {}
    for req in reqs:
        rtext = _requirement_ownership_text(req) or _req_text(req)
        for uid in {str(x) for x in (req.get("source_semantic_unit_ids") or []) if str(x)}:
            unit = unit_by_id.get(uid)
            if not unit:
                continue
            score = _semantic_material_similarity(str(unit.get("source_excerpt") or ""), rtext)
            claims.setdefault(uid, []).append((req, score))

    records: list[dict[str, Any]] = []
    for uid, members in claims.items():
        # A single claimant is not enough evidence to auto-delete a trace, even when similarity is low.
        unique = {str(r.get("srs_id") or r.get("candidate_id") or id(r)): (r, sc) for r, sc in members}
        vals = list(unique.values())
        if len(vals) < 2:
            continue
        unit = unit_by_id.get(uid) or {}
        vals.sort(key=lambda x: x[1], reverse=True)
        best_req, best_score = vals[0]
        second_score = vals[1][1]
        best_sid = str(best_req.get("srs_id") or best_req.get("candidate_id") or "")
        clear_dominance = best_score >= 0.30 and (best_score - second_score) >= 0.18
        if not clear_dominance:
            records.append({
                "source_semantic_unit_id": uid,
                "resolution": "SHARED_SEMANTIC_REVIEW_REQUIRED",
                "claimants": [
                    {"srs_id": str(r.get("srs_id") or r.get("candidate_id") or ""), "similarity": round(sc, 3)}
                    for r, sc in vals
                ],
                "source_excerpt": unit.get("source_excerpt"),
            })
            continue

        unit_critical = _critical_ownership_tokens(str(unit.get("source_excerpt") or ""))
        removed: list[dict[str, Any]] = []
        preserved: list[dict[str, Any]] = []
        for req, score in vals[1:]:
            sid = str(req.get("srs_id") or req.get("candidate_id") or "")
            req_text = _requirement_ownership_text(req) or _req_text(req)
            # A materially matching paraphrase may legitimately share a Source Unit with a recovered
            # native-domain Canonical requirement. Preserve such claims even when the exact-literal
            # recovered row scores higher; V0.81 targets *unrelated* leakage, not canonical aliases.
            if score >= best_score - 0.18 or (score >= 0.38 and _numeric_compatible(str(unit.get("source_excerpt") or ""), req_text)):
                continue
            req_critical = _critical_ownership_tokens(req_text)
            critical_overlap = sorted(unit_critical & req_critical)
            if critical_overlap:
                preserved.append({"srs_id": sid, "similarity": round(score, 3), "critical_tokens": critical_overlap})
                continue
            _remove_semantic_unit_claim(req, unit)
            cid = str(req.get("candidate_id") or "")
            if cid:
                unit["linked_candidate_ids"] = [x for x in (unit.get("linked_candidate_ids") or []) if str(x) != cid]
            if sid:
                unit["linked_srs_ids"] = [x for x in (unit.get("linked_srs_ids") or []) if str(x) != sid]
            removed.append({"srs_id": sid, "similarity": round(score, 3)})
        if removed or preserved:
            records.append({
                "source_semantic_unit_id": uid,
                "resolution": "DOMINANT_SEMANTIC_PARENT_ONLY" if removed and not preserved else "DOMINANT_SEMANTIC_PARENT_WITH_CRITICAL_SHARED_RETENTION",
                "dominant_srs_id": best_sid,
                "dominant_similarity": round(best_score, 3),
                "removed_claimants": removed,
                "preserved_critical_claimants": preserved,
                "source_excerpt": unit.get("source_excerpt"),
            })
    return records


def _reconcile_swe6_fact_scope(req: dict[str, Any]) -> None:
    """V0.81 keep parent SWE.6 eligibility consistent with authoritative fact-level scope.

    An Eligible parent with fact allocations but zero Eligible facts cannot silently remain Eligible.
    It is explicitly deferred for fact-allocation review; this preserves the requirement/SYS.5 trace and
    prevents the invalid state Eligible + zero qualifying TC scope.
    """
    if str(req.get("swe6_eligibility") or "") != "Eligible":
        req["swe6_scope_consistency_status"] = "CONSISTENT_OR_NOT_APPLICABLE"
        return
    fact_allocs = [x for x in (req.get("fact_level_allocations") or []) if isinstance(x, dict)]
    if not fact_allocs:
        req["swe6_scope_consistency_status"] = "NO_FACT_LEVEL_SCOPE_LEGACY_OR_EXPLICIT_ID"
        return
    if any(str(x.get("swe6_eligibility") or "") == "Eligible" for x in fact_allocs):
        req["swe6_scope_consistency_status"] = "ELIGIBLE_FACT_SCOPE_PRESENT"
        return
    req["swe6_eligibility"] = "Deferred - Fact Allocation Review"
    req["swe6_scope_consistency_status"] = "DEFERRED_NO_ELIGIBLE_FACT_SCOPE"
    req["swe6_scope_consistency_reason"] = (
        "Parent was SWE.6 Eligible but no fact-level allocation remains SWE.6 Eligible; parent qualification scope is deferred until fact allocation is resolved."
    )
    req["human_decision_required"] = True
    req["review_status"] = "HUMAN_DECISION_REQUIRED"
    req["official_release_eligible"] = False
    reasons = [x.strip() for x in str(req.get("hold_reason") or "").split(";") if x.strip()]
    reasons.append("SWE.6 parent eligibility has no eligible fact-level scope")
    req["hold_reason"] = "; ".join(dict.fromkeys(reasons))


def _complete_explicit_cited_non_sw_matches(
    req: dict[str, Any], units: list[dict[str, Any]], matched: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """V0.78 recover explicitly cited high-confidence non-SW clauses without widening Source scope.

    A combined Mechanical/Manufacturing/Electrical requirement can cite multiple exact Source
    locations while semantic matching selects only one of them.  If another eligible Semantic Unit
    sits at an already-cited location, is independently classified into a high-confidence non-SW
    domain, and materially overlaps the Canonical text, add that unit to the trace graph.  This is
    provenance completion only; it does not change allocation or create new requirement text.
    """
    cited = _explicit_requirement_source_location_keys(req)
    if not cited:
        return matched
    non_sw = {
        "HW_REQUIREMENT", "ELECTRICAL_REQUIREMENT", "MECHANICAL_CONNECTOR_REQUIREMENT",
        "MANUFACTURING_PROCESS_REQUIREMENT", "ENVIRONMENTAL_QUALIFICATION_REQUIREMENT",
    }
    req_text = _requirement_ownership_text(req) or _req_text(req)
    out = list(matched)
    seen = {str(x.get("source_semantic_unit_id") or "") for x in out}
    for unit in units:
        uid = str(unit.get("source_semantic_unit_id") or "")
        if not uid or uid in seen:
            continue
        if not (_source_location_keys(unit.get("source_location")) & cited):
            continue
        alloc = _allocation_for_text(str(unit.get("source_excerpt") or ""), "")
        if str(alloc.get("allocation_status") or "") not in non_sw:
            continue
        excerpt = str(unit.get("source_excerpt") or "")
        score = _token_similarity(excerpt, req_text)
        # Korean grammatical particles can turn `자동납땜` into `자동납땜을` and defeat exact
        # token equality. For this exact-cited non-SW trace completion only, accept a material
        # prefix/subtoken overlap of length >=3 in addition to the normal similarity score.
        et, rt = _tokens(excerpt), _tokens(req_text)
        fuzzy_material = any(
            len(a) >= 3 and len(b) >= 3 and (a in b or b in a)
            for a in et for b in rt
        )
        if score < 0.16 and not fuzzy_material:
            continue
        item = dict(unit)
        item["explicit_cited_non_sw_trace_completion"] = True
        item["trace_completion_similarity"] = round(score, 3)
        out.append(item)
        seen.add(uid)
    return out


def _complete_explicit_cited_requirement_matches(
    req: dict[str, Any], units: list[dict[str, Any]], matched: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """V0.79 complete exact-cited semantic provenance for Eligible/Review requirements.

    Extraction may preserve a concrete Source paragraph in ``source_evidence`` while semantic
    matching misses the corresponding Semantic Unit because the generated Canonical sentence is
    longer, combines a paragraph range, or uses a conservative paraphrase.  This completion never
    widens beyond explicitly cited Source locations and requires material lexical/critical overlap.
    It only repairs trace binding; it does not change requirement text or allocation.
    """
    cited = _explicit_requirement_source_location_keys(req)
    if not cited:
        return matched
    req_text = _requirement_ownership_text(req) or _req_text(req)
    req_tokens = _tokens(req_text)
    req_critical = _critical_ownership_tokens(req_text)
    out = list(matched)
    seen = {str(x.get("source_semantic_unit_id") or "") for x in out}
    for unit in units:
        uid = str(unit.get("source_semantic_unit_id") or "")
        if not uid or uid in seen:
            continue
        if not (_source_location_keys(unit.get("source_location")) & cited):
            continue
        excerpt = str(unit.get("source_excerpt") or "")
        if not excerpt or not _numeric_compatible(req_text, excerpt):
            continue
        score = _token_similarity(excerpt, req_text)
        unit_tokens = _tokens(excerpt)
        lexical_overlap = len(req_tokens & unit_tokens) / max(1, min(len(req_tokens), len(unit_tokens), 12)) if (req_tokens and unit_tokens) else 0.0
        critical_overlap = bool(req_critical & _critical_ownership_tokens(excerpt))
        fuzzy_material = any(
            len(a) >= 3 and len(b) >= 3 and (a in b or b in a)
            for a in unit_tokens for b in req_tokens
        )
        if score < 0.24 and lexical_overlap < 0.34 and not critical_overlap and not fuzzy_material:
            continue
        item = dict(unit)
        item["explicit_cited_requirement_trace_completion"] = True
        item["trace_completion_similarity"] = round(score, 3)
        out.append(item)
        seen.add(uid)
    return out


def _contextualize_conflicting_shared_fragments(
    reqs: list[dict[str, Any]], fragment_index: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """V0.78 make parent-context allocation explicit when one literal fragment has divergent claims.

    The same literal Source sentence may legitimately participate in more than one parent behavior,
    but a single fragment ID with incompatible inherited allocations is ambiguous to downstream
    audit consumers.  When divergent allocation/domain claims are detected, create deterministic
    contextual aliases per parent while preserving `contextual_alias_of` back to the physical Source
    fragment.  No Source text or allocation decision is changed.
    """
    claims: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for req in reqs:
        alloc_by_fragment = {
            str(a.get("source_fact_fragment_id") or ""): a
            for a in (req.get("fact_level_allocations") or [])
            if isinstance(a, dict) and str(a.get("source_fact_fragment_id") or "")
        }
        for frag in (req.get("source_fact_fragments") or []):
            if not isinstance(frag, dict):
                continue
            fid = str(frag.get("source_fact_fragment_id") or "")
            if fid and fid in alloc_by_fragment:
                claims.setdefault(fid, []).append((req, alloc_by_fragment[fid]))

    index_by_id = {
        str(x.get("source_fact_fragment_id") or ""): x
        for x in fragment_index if isinstance(x, dict) and str(x.get("source_fact_fragment_id") or "")
    }
    records: list[dict[str, Any]] = []
    for fid, members in claims.items():
        if len(members) < 2:
            continue
        signatures = {
            (str(a.get("allocation_status") or ""), str(a.get("verification_domain") or ""))
            for _, a in members
        }
        if len(signatures) <= 1:
            continue
        aliases = []
        for req, alloc in members:
            sid = str(req.get("srs_id") or req.get("candidate_id") or "UNSCOPED")
            raw = f"{fid}|{sid}|{alloc.get('allocation_status','')}|{alloc.get('verification_domain','')}"
            alias = "SRC-FRAGCTX-" + hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:12].upper()

            for key in ("source_fact_fragments", "source_backed_atomic_behaviors", "fact_level_allocations"):
                updated = []
                for item in (req.get(key) or []):
                    if isinstance(item, dict) and str(item.get("source_fact_fragment_id") or "") == fid:
                        item = dict(item)
                        item["source_fact_fragment_id"] = alias
                        item["contextual_alias_of"] = fid
                        item["contextual_parent_srs_id"] = sid
                        item["context_dependent_allocation"] = True
                    updated.append(item)
                req[key] = updated

            base = index_by_id.get(fid)
            if base and alias not in index_by_id:
                alias_record = dict(base)
                alias_record["source_fact_fragment_id"] = alias
                alias_record["contextual_alias_of"] = fid
                alias_record["contextual_parent_srs_id"] = sid
                alias_record["context_dependent_allocation"] = True
                fragment_index.append(alias_record)
                index_by_id[alias] = alias_record
            aliases.append({
                "srs_id": sid,
                "contextual_fragment_id": alias,
                "allocation_status": str(alloc.get("allocation_status") or ""),
                "verification_domain": str(alloc.get("verification_domain") or ""),
            })
        records.append({
            "source_fact_fragment_id": fid,
            "resolution": "CONTEXTUAL_FRAGMENT_ALIAS_PER_PARENT",
            "context_dependent_allocation": True,
            "aliases": aliases,
            "source_excerpt": (index_by_id.get(fid) or {}).get("source_excerpt"),
        })
    return records

def _semantic_review_tokens(text: Any) -> set[str]:
    raw = re.findall(r"[A-Za-z0-9가-힣_]+", _norm(text).lower())
    stop = {
        "해야", "한다", "하여", "위해", "관련", "제어", "시스템", "기능", "경우", "상태",
        "the", "and", "shall", "system", "control", "controller",
    }
    return {x for x in raw if len(x) > 1 and x not in stop}


def _semantic_review_shortcut(unit: dict[str, Any], reqs: list[dict[str, Any]]) -> dict[str, Any]:
    """Suggest a reviewer shortcut without auto-closing an OPEN Semantic Unit.

    This is deliberately advisory.  High overlap may mean an existing SRS already covers the
    text, but unique normative behavior must still be linked/expanded rather than excluded.
    """
    excerpt = _norm(unit.get("source_excerpt"))
    u_tokens = _semantic_review_tokens(excerpt)
    if len(u_tokens) < 3:
        return {}
    best: tuple[float, dict[str, Any] | None] = (0.0, None)
    for req in reqs:
        req_text = " ".join([
            _norm(req.get("requirement")),
            " ".join(_norm(x.get("behavior_text") or x.get("source_fact")) for x in _list(req.get("source_backed_atomic_behaviors")) if isinstance(x, dict)),
        ])
        r_tokens = _semantic_review_tokens(req_text)
        if not r_tokens:
            continue
        containment = len(u_tokens & r_tokens) / max(1, len(u_tokens))
        if containment > best[0]:
            best = (containment, req)
    score, req = best
    if req is None or score < 0.55:
        return {}
    return {
        "review_shortcut_suggestion": "POSSIBLE_EXISTING_SRS_COVERAGE",
        "suggested_srs_id": str(req.get("srs_id") or ""),
        "suggested_candidate_id": str(req.get("candidate_id") or ""),
        "similarity_score": round(score, 3),
        "suggested_action": (
            "Compare the OPEN unit against the suggested SRS. If fully duplicated/non-normative, a human may record "
            "Intentional Exclusion with rationale; if any unique normative behavior/timing/interface obligation remains, link or expand the SRS instead."
        ),
    }


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
        matched = _complete_explicit_cited_non_sw_matches(req, units, matched)
        matched = _complete_explicit_cited_requirement_matches(req, units, matched)
        req["source_fact_fragments"] = _fragments_for_requirement(req, matched, fragment_index)

        # V0.65 conservative Source Table Fact Join.  Exact identifier overlap or an already
        # linked Semantic Unit is required for HIGH-confidence automatic use in SWE.6.  Numeric
        # coincidence alone is never enough to join a table fact to a requirement.
        linked_unit_ids = {str(u.get("source_semantic_unit_id") or "") for u in matched}
        req_join_text = " ".join([
            _req_text(req), _source_text(req),
            " ".join(str(x.get("text") or "") for x in _list(req.get("source_evidence")) if isinstance(x, dict)),
        ])
        req_identifiers = set(_engineering_identifiers(req_join_text))
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

        # A V0.74 completion fragment may come from another Semantic Unit at the exact Source
        # location already cited by this requirement. Promote that unit into the trace graph only
        # because an exact selected fragment now depends on it; do not infer any new Source scope.
        fragment_parent_ids = {str(f.get("parent_source_semantic_unit_id") or "") for f in (req.get("source_fact_fragments") or []) if isinstance(f, dict)}
        for u in units:
            uid = str(u.get("source_semantic_unit_id") or "")
            if not uid or uid not in fragment_parent_ids or uid in req["source_semantic_unit_ids"]:
                continue
            req["source_semantic_unit_ids"].append(uid)
            chunk_id = u.get("source_chunk_id")
            if chunk_id and chunk_id not in req["source_chunk_ids"]:
                req["source_chunk_ids"].append(chunk_id)
            cid, sid = str(req.get("candidate_id") or ""), str(req.get("srs_id") or "")
            if cid and cid not in u["linked_candidate_ids"]:
                u["linked_candidate_ids"].append(cid)
            if sid and sid not in u["linked_srs_ids"]:
                u["linked_srs_ids"].append(sid)

        apply_allocation_gate(req, matched)
        _e2e_engineering_projection(req)
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

        # V0.65: pre-existing atomic behavior lists may be incomplete even when the Canonical
        # requirement text contains every Source list member. Backfill only owned Source fragments
        # that are not already materially represented.
        _augment_atomic_behaviors_from_fragments(req)

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

    # V0.81 containment works at Semantic Unit first, then Fact Fragment. This prevents a leaked
    # manufacturing/electrical/etc. Source unit from surviving in Canonical provenance after its
    # fragment was already removed. Ambiguous shared ownership remains review-required.
    data["semantic_parent_containment_review"] = _disambiguate_shared_semantic_unit_ownership(reqs, units)
    data["fragment_parent_containment_review"] = _disambiguate_shared_fragment_ownership(reqs)

    # Ownership cleanup may change the evidence that drove parent/fact allocation. Recompute the
    # allocation from the corrected Source claims before E2E projection; stale domain metadata is
    # never allowed to survive a provenance repair.
    units_by_id = {str(u.get("source_semantic_unit_id") or ""): u for u in units if isinstance(u, dict)}
    for req in reqs:
        remaining_units = [units_by_id[x] for x in (req.get("source_semantic_unit_ids") or []) if str(x) in units_by_id]
        apply_allocation_gate(req, remaining_units)
        _e2e_engineering_projection(req)
        _reconcile_swe6_fact_scope(req)
    data["shared_fragment_contextualization"] = _contextualize_conflicting_shared_fragments(reqs, fragment_index)

    # V0.65 fact-fragment ownership audit. The same exact fragment may support multiple SRS,
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
        terminal = status in {
            "COVERED_BY_CANONICAL", "NOT_SW_WITH_ALLOCATION_DECISION", "EXTERNAL_DEPENDENCY_ONLY",
            "INTENTIONALLY_EXCLUDED_WITH_RATIONALE",
        }
        review_state = "CLOSED" if terminal else "OPEN"
        required_resolution = ""
        if not terminal:
            required_resolution = (
                "Link this eligible Source Semantic Unit to a Canonical/SRS, an explicit Gap/Conflict/External Dependency, "
                "or record an intentional exclusion with rationale. Do not leave REVIEW_NEEDED as an implicit terminal state."
            )
        counts[status] = counts.get(status, 0) + 1
        review_shortcut = _semantic_review_shortcut(u, reqs) if not terminal else {}
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
            "terminal_disposition": terminal,
            "review_state": review_state,
            "review_owner": "UNASSIGNED" if not terminal else "",
            "required_resolution": required_resolution,
            "requirement_level": level,
            "allocation_status": allocation,
            "verification_domain": domain,
            **review_shortcut,
        })

    uncovered = [x for x in dispositions if x.get("disposition_status") != "COVERED_BY_CANONICAL"]
    open_records = [x for x in dispositions if not bool(x.get("terminal_disposition"))]
    terminal_count = len(dispositions) - len(open_records)
    data["semantic_source_unit_coverage"] = {
        "eligible_unit_count": len(eligible),
        "covered_unit_count": len(covered),
        "coverage_percent": round(len(covered) / len(eligible) * 100, 2) if eligible else None,
        "dispositioned_unit_count": len(dispositions),
        "disposition_coverage_percent": 100.0 if eligible and len(dispositions) == len(eligible) else (None if not eligible else round(len(dispositions) / len(eligible) * 100, 2)),
        "terminal_disposition_count": terminal_count,
        "terminal_disposition_percent": round(terminal_count / len(eligible) * 100, 2) if eligible else None,
        "open_review_needed_count": len(open_records),
        "open_review_needed_records": open_records,
        "terminal_disposition_complete": not open_records,
        "uncovered_unit_count": len(uncovered),
        "uncovered_unit_records": uncovered,
        "disposition_records": dispositions,
        "disposition_counts": counts,
        "scope_note": "Every eligible Source Semantic Unit receives an auditable disposition. V0.73 continues to report whether that disposition is terminal; REVIEW_NEEDED remains OPEN until linked to a Canonical/SRS, Gap/Conflict/External Dependency, or intentional exclusion with rationale.",
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
