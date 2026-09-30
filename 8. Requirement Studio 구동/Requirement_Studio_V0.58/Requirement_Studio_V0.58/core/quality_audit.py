from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

from core.cross_document_semantics import (
    attach_semantic_traceability, apply_coverage_mode, dedupe_and_scope_gaps, filter_gap_links_by_scope,
    normalize_external_dependencies, preserve_numeric_relation_semantics,
)

# Generic identifier detector. No MLM-specific IDs are hard-coded.
_EXPLICIT_ID_PATTERNS = [
    # End with an ASCII identifier lookahead rather than Unicode \b so IDs followed by Korean text are still detected.
    re.compile(r"(?<![A-Za-z0-9_])REQ[A-Z0-9]*[-_.][A-Z0-9][A-Z0-9_.-]*(?![A-Za-z0-9_.-])", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_])REQ\d+[A-Z0-9_.-]*(?![A-Za-z0-9_.-])", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_])SW[_-]?REQ[-_.A-Z0-9]*\d[A-Z0-9_.-]*(?![A-Za-z0-9_.-])", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_])SWR[-_.A-Z0-9]*\d[A-Z0-9_.-]*(?![A-Za-z0-9_.-])", re.IGNORECASE),
]

_FACT_TOKEN_PATTERNS = [
    re.compile(r"\b0x[0-9A-Fa-f]+\b"),
    re.compile(r"\b(?:Input|Output|Par|Param|Signal)_[A-Za-z0-9_]+\b"),
    re.compile(r"(?<![A-Za-z0-9_])[-+]?\d+(?:\.\d+)?\s*(?:ms|msec|s|sec|초|V|mV|A|mA|%|℃|°C|bps|kbps|Step|step)\b", re.IGNORECASE),
]

_SIGNAL_PATTERN = re.compile(r"\b(?:Input|Output|Par|Param|Signal)_[A-Za-z0-9_]+\b")
_LABEL_VALUE_PATTERNS = [
    re.compile(r"\b(?P<label>On|Off)\s*\(\s*(?P<value>0x[0-9A-Fa-f]+|\d+)\s*\)", re.IGNORECASE),
    re.compile(r"\b(?P<value>0x[0-9A-Fa-f]+|\d+)\s*=\s*(?P<label>On|Off)\b", re.IGNORECASE),
    # Normalized signal tables frequently use `0x1: Off`, `0x1 | Off`, or `Off: 0x1`.
    re.compile(r"\b(?P<value>0x[0-9A-Fa-f]+|\d+)\s*(?:[:：]|\|)\s*(?P<label>On|Off)\b", re.IGNORECASE),
    re.compile(r"\b(?P<label>On|Off)\s*(?:[:：]|=|\|)\s*(?P<value>0x[0-9A-Fa-f]+|\d+)\b", re.IGNORECASE),
]


def _list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value in (None, "", {}):
        return []
    return [value]


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _hash_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _location_interval(value: str) -> tuple[str, int, int, int | None] | None:
    """Parse stable normalizer locations such as Paragraph 12, Paragraph 12-15, Table 4 / Row 3.

    Returns (kind, start, end, table_no). This is intentionally limited to locations emitted by
    DocumentNormalizer and does not infer semantic section identity from prose.
    """
    text = _normalize_space(value)
    m = re.search(r"\bParagraph\s+(\d+)(?:\s*[-~]\s*(\d+))?\b", text, flags=re.IGNORECASE)
    if m:
        start = int(m.group(1)); end = int(m.group(2) or m.group(1))
        if start > end:
            start, end = end, start
        return ("paragraph", start, end, None)
    m = re.search(r"\bTable\s+(\d+)\s*/\s*Row\s+(\d+)(?:\s*[-~]\s*(\d+))?\b", text, flags=re.IGNORECASE)
    if m:
        table_no = int(m.group(1)); start = int(m.group(2)); end = int(m.group(3) or m.group(2))
        if start > end:
            start, end = end, start
        return ("table", start, end, table_no)
    return None


def _source_location_overlap(a: str, b: str) -> bool:
    """Deterministic location overlap for paragraph/table ranges plus conservative text fallback."""
    ia = _location_interval(a); ib = _location_interval(b)
    if ia and ib and ia[0] == ib[0]:
        if ia[0] == "table" and ia[3] != ib[3]:
            return False
        return max(ia[1], ib[1]) <= min(ia[2], ib[2])
    na = _normalize_space(a).lower(); nb = _normalize_space(b).lower()
    return bool(na and nb and (na == nb or na in nb or nb in na))


def _short_variant_values(text: str) -> list[str]:
    """Extract only compact variant/configuration labels, never free-form review/TBD sentences."""
    hay = _normalize_space(text)
    values: list[str] = []
    patterns = [
        r"\b[A-Za-z0-9_]+\s+Type\b",
        r"\bRGB\s*Type\b",
        r"\bWhite\s*LED\s*Type\b",
        r"\bDrive\s*Mode\s*(?:연동|Link(?:ed)?)?\b",
        r"\bPersonalization\b",
        r"개인화\s*연동",
        r"드라이브\s*모드\s*연동",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, hay, flags=re.IGNORECASE):
            value = _normalize_space(m.group(0))
            if value and len(value) <= 60 and value.lower() not in {x.lower() for x in values}:
                values.append(value)
    return values


def _dependency_objects(req: dict[str, Any], related_artifacts: list[str]) -> list[dict[str, Any]]:
    """Normalize source-backed external dependencies as structured objects.

    Internal Source tables/figures remain related_artifacts. External DB/spec/drawing/design
    references are captured only when the compact Source evidence explicitly mentions them.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(obj: dict[str, Any]) -> None:
        raw_name = obj.get("name")
        raw_purpose = obj.get("purpose")
        if isinstance(raw_name, (dict, list)):
            raw_name = ""
        if isinstance(raw_purpose, dict):
            raw_purpose = raw_purpose.get("text") or raw_purpose.get("reason") or ""
        elif isinstance(raw_purpose, list):
            raw_purpose = " ".join(str(x) for x in raw_purpose if not isinstance(x, (dict, list)))
        normalized = {
            "type": str(obj.get("type") or "external_document"),
            "name": _normalize_space(raw_name),
            "purpose": _normalize_space(raw_purpose),
            "knowledge_state": str(obj.get("knowledge_state") or "KNOWN"),
            "source_evidence": _list(obj.get("source_evidence")),
            "required_for": _list(obj.get("required_for")),
        }
        if not normalized["name"] and not normalized["purpose"]:
            return
        key = f"{normalized['type'].strip().lower()}|{normalized['name'].strip().lower()}"
        if key in seen:
            return
        seen.add(key)
        # Keep the dependency purpose compact; full source wording remains under source_evidence.
        if len(normalized["purpose"]) > 220:
            normalized["purpose"] = normalized["purpose"][:217].rstrip() + "..."
        out.append(normalized)

    for item in _list(req.get("external_dependencies")):
        if isinstance(item, dict):
            add({
                "type": item.get("type") or "external_document",
                "name": item.get("name") or item.get("document") or item.get("artifact") or "",
                "purpose": item.get("purpose") or item.get("reason") or "",
                "knowledge_state": item.get("knowledge_state") or "KNOWN",
                "source_evidence": item.get("source_evidence") or _list(req.get("source_evidence")),
            })
        else:
            text = _normalize_space(item)
            if text:
                add({"type": "external_document", "name": text, "purpose": "", "source_evidence": _list(req.get("source_evidence"))})

    # Search only source-backed compact fields; do not infer a dependency from domain expectations.
    evidence_rows = []
    for ev in _list(req.get("source_evidence")):
        if isinstance(ev, dict):
            evidence_rows.append(ev)
    source_strings: list[tuple[str, list]] = []
    for ev in evidence_rows:
        source_strings.append((f"{ev.get('location','')} {ev.get('text','')}", [ev]))
    for text in related_artifacts:
        source_strings.append((str(text), evidence_rows))
    clar = req.get("clarification_needed")
    if clar not in (None, "", [], {}):
        source_strings.append((_text(clar), evidence_rows))

    patterns = [
        (r"(?<![A-Za-z0-9_])CAN\s*DB(?![A-Za-z0-9_])", "database", "CAN DB"),
        (r"(?<![A-Za-z0-9_])LIN\s*DB(?![A-Za-z0-9_])", "database", "LIN DB"),
        (r"(?<![A-Za-z0-9_])System\s*Spec(?:ification)?(?![A-Za-z0-9_])|시스템\s*사양서?", "external_specification", "System Specification"),
        (r"차종별\s*(?:도면|drawing)", "vehicle_document", "차종별 도면"),
        (r"(?:별도|차종별)\s*(?:Table|표)", "external_table", "별도/차종별 Table"),
        (r"(?:디자인|설계)\s*(?:담당자)?\s*(?:협의|결정|튜닝)", "external_decision", "설계/디자인 결정"),
    ]
    for text, evs in source_strings:
        norm = _normalize_space(text)
        for pattern, dep_type, name in patterns:
            if re.search(pattern, norm, flags=re.IGNORECASE):
                add({
                    "type": dep_type,
                    "name": name,
                    "purpose": norm[:360],
                    "knowledge_state": "KNOWN",
                    "source_evidence": evs,
                })
    # Generic external-standard identifiers are source references, not imported requirement content.
    for text, evs in source_strings:
        for code in re.findall(r"(?<![A-Za-z0-9])(?:ES|MS)\s*\d{4,}(?:[-_]\d+)?(?![A-Za-z0-9])", _normalize_space(text), flags=re.IGNORECASE):
            add({"type": "external_specification", "name": re.sub(r"\s+", "", code.upper()), "purpose": "Detailed criteria are delegated to the referenced external specification.", "knowledge_state": "KNOWN", "source_evidence": evs, "required_for": ["Detailed behavior or verification criteria"]})
    return out


def default_applicability() -> dict[str, Any]:
    return {
        "vehicle_lines": [],
        "baseline_versions": [],
        "feature_variants": [],
        "enable_conditions": [],
        "exclusion_conditions": [],
        "knowledge_state": "UNKNOWN",
        "knowledge_state_reason": "",
        "source_evidence": [],
    }


def _explicit_ids(text: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for pattern in _EXPLICIT_ID_PATTERNS:
        for m in pattern.finditer(text or ""):
            value = m.group(0).strip()
            key = value.upper()
            if key not in seen:
                seen.add(key)
                values.append(value)
    return values


def _source_backed_extension_text(req: dict[str, Any]) -> str:
    parts = []
    for ev in _list(req.get("source_evidence")):
        if isinstance(ev, dict):
            parts.extend([str(ev.get("location") or ""), str(ev.get("text") or "")])
        else:
            parts.append(str(ev))
    for k in ("preconditions", "exception_conditions", "related_artifacts"):
        parts.extend(str(x) for x in _list(req.get(k)) if str(x).strip())
    clar = req.get("clarification_needed")
    if clar not in (None, "", [], {}):
        parts.append(_text(clar))
    return "\n".join(x for x in parts if x)


def _derive_review_extensions_from_compact_req(req: dict[str, Any], app: dict[str, Any]) -> None:
    """Derive review-side metadata only from fields already produced by the compact extractor.

    V0.53 keeps applicability values to compact variant labels and normalizes external dependencies
    to structured objects. Review/TBD prose is not stored as a feature variant.
    """
    hay = _source_backed_extension_text(req)
    versions = re.findall(r"(?:Ver(?:sion)?\s*\d+(?:\.\d+)*|Baseline\s*[A-Za-z0-9_.-]+)", hay, flags=re.IGNORECASE)
    if versions and not app.get("baseline_versions"):
        app["baseline_versions"] = list(dict.fromkeys(_normalize_space(x) for x in versions))

    pre = [_normalize_space(str(x)) for x in _list(req.get("preconditions")) if str(x).strip()]
    exc = [_normalize_space(str(x)) for x in _list(req.get("exception_conditions")) if str(x).strip()]
    if pre and not app.get("enable_conditions"):
        app["enable_conditions"] = pre
    if exc and not app.get("exclusion_conditions"):
        app["exclusion_conditions"] = exc

    # Only compact explicit variant/configuration labels are admitted here.
    if not app.get("feature_variants"):
        app["feature_variants"] = _short_variant_values(hay)[:20]
    else:
        cleaned: list[str] = []
        for value in _list(app.get("feature_variants")):
            for variant in _short_variant_values(str(value)):
                if variant.lower() not in {x.lower() for x in cleaned}:
                    cleaned.append(variant)
        app["feature_variants"] = cleaned[:20]

    related = [_normalize_space(str(x)) for x in _list(req.get("related_artifacts")) if str(x).strip()]
    req["external_dependencies"] = _dependency_objects(req, related)

    clar = _normalize_space(_text(req.get("clarification_needed")))
    if clar:
        if not req.get("tbd_items") and re.search(r"\bTBD\b|미정|확인\s*필요|정의\s*필요", clar, flags=re.IGNORECASE):
            req["tbd_items"] = [clar]
        if not req.get("conflicts") and re.search(r"상충|충돌|불일치|모순|서로\s*다름|표기\s*상이", clar, flags=re.IGNORECASE):
            req["conflicts"] = [{"classification": "Possible Conflict", "description": clar}]


def normalize_requirement_extensions(req: dict[str, Any]) -> dict[str, Any]:
    """Fill review extension fields locally without increasing AI output burden.

    V0.53 keeps the AI on the frozen compact V0.46-style extraction payload and then
    derives safe metadata from source_evidence. This prevents review metadata from competing
    with requirement recall inside the same model output budget.
    """
    raw_ids = _list(req.get("source_requirement_ids"))
    inferred_ids: list[str] = []
    seen: set[str] = set()
    for value in raw_ids:
        key = str(value).strip()
        if key and key.upper() not in seen:
            seen.add(key.upper())
            inferred_ids.append(key)
    for ev in _list(req.get("source_evidence")):
        if isinstance(ev, dict):
            hay = " ".join(str(ev.get(k) or "") for k in ("location", "text", "document"))
        else:
            hay = str(ev)
        for sid in _explicit_ids(hay):
            if sid.upper() not in seen:
                seen.add(sid.upper())
                inferred_ids.append(sid)
    req["source_requirement_ids"] = inferred_ids
    req.setdefault("source_requirement_occurrence_ids", [])
    if not isinstance(req.get("source_requirement_occurrence_ids"), list):
        req["source_requirement_occurrence_ids"] = _list(req.get("source_requirement_occurrence_ids"))
    req.setdefault("source_chunk_ids", [])
    if not isinstance(req.get("source_chunk_ids"), list):
        req["source_chunk_ids"] = _list(req.get("source_chunk_ids"))
    req.setdefault("source_backed_atomic_behaviors", [])
    if not isinstance(req.get("source_backed_atomic_behaviors"), list):
        req["source_backed_atomic_behaviors"] = _list(req.get("source_backed_atomic_behaviors"))
    req.setdefault("source_backed_facts", [])
    if not isinstance(req.get("source_backed_facts"), list):
        req["source_backed_facts"] = _list(req.get("source_backed_facts"))
    req.setdefault("source_semantic_unit_ids", [])
    if not isinstance(req.get("source_semantic_unit_ids"), list):
        req["source_semantic_unit_ids"] = _list(req.get("source_semantic_unit_ids"))
    req.setdefault("value_relation_status", [])
    if not isinstance(req.get("value_relation_status"), list):
        req["value_relation_status"] = _list(req.get("value_relation_status"))
    req.setdefault("normative_strength_findings", [])
    if not isinstance(req.get("normative_strength_findings"), list):
        req["normative_strength_findings"] = _list(req.get("normative_strength_findings"))
    req.setdefault("normative_strength_status", "NOT_EVALUATED")
    req.setdefault("semantic_provenance_status", "NOT_EVALUATED")

    app = req.get("applicability")
    if not isinstance(app, dict):
        app = {}
    base = default_applicability()
    for key in ("vehicle_lines", "baseline_versions", "feature_variants", "enable_conditions", "exclusion_conditions", "source_evidence"):
        base[key] = _list(app.get(key))
    state = str(app.get("knowledge_state") or "").strip().upper()
    if state not in {"KNOWN", "DERIVED", "UNKNOWN"}:
        state = "KNOWN" if any(base[k] for k in ("vehicle_lines", "baseline_versions", "feature_variants", "enable_conditions", "exclusion_conditions")) else "UNKNOWN"
    base["knowledge_state"] = state
    reason = str(app.get("knowledge_state_reason") or "").strip()
    if not reason and state == "UNKNOWN":
        reason = "No explicit applicability/variant evidence was confirmed from the current Source-backed compact fields."
    base["knowledge_state_reason"] = reason
    req["applicability"] = base

    for key in ("external_dependencies", "tbd_items", "conflicts", "open_issue_ids", "verification_constraints"):
        req[key] = _list(req.get(key))

    _derive_review_extensions_from_compact_req(req, base)
    if any(base.get(k) for k in ("vehicle_lines", "baseline_versions", "feature_variants", "enable_conditions", "exclusion_conditions")):
        base["knowledge_state"] = "DERIVED" if not app else state
        if base["knowledge_state"] != "UNKNOWN" and base.get("knowledge_state_reason", "").startswith("No explicit applicability"):
            base["knowledge_state_reason"] = "Applicability metadata was conservatively derived from Source-backed compact Requirement fields."
        # Preserve source evidence used by the compact extractor as the provenance for the sidecar view.
        if not base.get("source_evidence"):
            base["source_evidence"] = _list(req.get("source_evidence"))

    status = str(req.get("requirement_status") or "Draft").strip()
    req["requirement_status"] = status or "Draft"
    state = str(req.get("knowledge_state") or "").strip().upper()
    if state not in {"KNOWN", "DERIVED", "UNKNOWN"}:
        state = "KNOWN" if req.get("derivation_type") == "explicit" else "DERIVED"
    req["knowledge_state"] = state
    return req


def _iter_source_blocks(compact_text: str):
    pattern = re.compile(r"^\[SRC\s+([^|\]]+)\s*\|\s*([^|\]]+)\s*\|\s*([^\]]+)\]\s*$", re.MULTILINE)
    matches = list(pattern.finditer(compact_text or ""))
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(compact_text or "")
        text = (compact_text or "")[start:end].strip()
        yield {
            "chunk_id": match.group(1).strip(),
            "location": match.group(2).strip(),
            "kind": match.group(3).strip(),
            "text": text,
        }


def _find_explicit_matches(text: str) -> list[tuple[str, int, int]]:
    found: list[tuple[str, int, int]] = []
    occupied: set[tuple[int, int]] = set()
    for pattern in _EXPLICIT_ID_PATTERNS:
        for m in pattern.finditer(text or ""):
            span = (m.start(), m.end())
            if span in occupied:
                continue
            occupied.add(span)
            found.append((m.group(0).strip(), m.start(), m.end()))
    return sorted(found, key=lambda x: x[1])


def _is_declaration(line: str, source_id: str, start: int) -> bool:
    """Conservative declaration detector.

    IDs at a row/paragraph head are declarations; IDs embedded later are cross references.
    This keeps cross references out of the coverage denominator.
    """
    prefix = line[:start]
    cleaned = re.sub(r"^\s*(?:[-*•]\s*)?(?:\d+[.)]\s*)?(?:\|\s*)?(?:\[\s*)?", "", line)
    if cleaned.upper().startswith(source_id.upper()):
        return True
    # Common heading/table-cell forms such as "[REQ_A_001] ..." or "REQ_A_001 | ..."
    head = re.sub(r"^\s*[|\[({<\-–—*•\d.)\s]*", "", line)
    if head.upper().startswith(source_id.upper()):
        return True
    # If the identifier is very near the start and the preceding content is punctuation only.
    return start <= 12 and not re.search(r"[A-Za-z가-힣]", prefix)


def _infer_function_or_baseline(location: str, line: str) -> str:
    """Best-effort source context label without inventing domain facts.

    The label is copied only from visible source location/version-like text.  It is review context,
    not an inferred vehicle applicability fact.
    """
    loc = _normalize_space(location)
    text = _normalize_space(line)
    versions = re.findall(r"(?:Ver(?:sion)?\s*\d+(?:\.\d+)*|Baseline\s*[A-Za-z0-9_.-]+)", f"{loc} {text}", flags=re.IGNORECASE)
    if versions:
        return " | ".join(dict.fromkeys(versions))
    # Keep the source section/location itself as contextual identity when no version token exists.
    return loc[:240]


def extract_source_requirement_occurrences(compact_text: str) -> list[dict[str, Any]]:
    """Build declaration and reference occurrences without hard-coding source-specific IDs."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int, str]] = set()
    for block in _iter_source_blocks(compact_text):
        lines = block["text"].splitlines() or [block["text"]]
        for line_no, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line:
                continue
            matches = _find_explicit_matches(line)
            if not matches:
                continue
            for source_id, start, _end in matches:
                occurrence_type = "declaration" if _is_declaration(line, source_id, start) else ("table_reference" if "|" in line else "cross_reference")
                key = (source_id.upper(), block["chunk_id"], line_no, occurrence_type)
                if key in seen:
                    continue
                seen.add(key)
                excerpt = line[:700]
                context_hash = _hash_text(f"{block['location']}|{line}")
                out.append({
                    "occurrence_id": f"SRC-OCC-{len(out)+1:04d}",
                    "occurrence_type": occurrence_type,
                    "source_req_id": source_id,
                    "function_or_baseline": _infer_function_or_baseline(block["location"], line),
                    "section_path": block["location"],
                    "chunk_id": block["chunk_id"],
                    "line_in_chunk": line_no,
                    "source_location": block["location"],
                    "source_kind": block["kind"],
                    "source_excerpt": excerpt,
                    "content_hash": context_hash,
                    "stable_match_key": f"{source_id.upper()}|{block['location']}|{context_hash}",
                    "coverage_status": "Reference Only" if occurrence_type != "declaration" else "Pending",
                    "linked_candidate_ids": [],
                    "linked_srs_ids": [],
                    "linked_gap_issue_ids": [],
                    "disposition_reason": "Cross/table reference; excluded from declaration coverage denominator." if occurrence_type != "declaration" else "",
                    "uncertainty_reason": "",
                })
    return out


def _req_evidence(req: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for ev in _list(req.get("source_evidence")):
        if isinstance(ev, dict):
            rows.append({
                "location": str(ev.get("location") or ""),
                "text": str(ev.get("text") or ""),
                "document": str(ev.get("document") or ""),
            })
        else:
            rows.append({"location": "", "text": str(ev), "document": ""})
    return rows


def _req_mentions_source_id(req: dict[str, Any], source_id: str) -> bool:
    target = source_id.upper()
    if any(str(x).strip().upper() == target for x in _list(req.get("source_requirement_ids"))):
        return True
    for ev in _req_evidence(req):
        if target in (ev["location"] + " " + ev["text"] + " " + ev["document"]).upper():
            return True
    hay = " ".join(_text(req.get(k)) for k in ("requirement", "derivation_reason", "clarification_needed"))
    return target in hay.upper()


def _location_similarity(req: dict[str, Any], occ: dict[str, Any]) -> int:
    score = 0
    loc = str(occ.get("source_location") or "")
    excerpt = _normalize_space(str(occ.get("source_excerpt") or "")).lower()
    occ_hash = str(occ.get("content_hash") or "")
    for ev in _req_evidence(req):
        ev_loc = ev["location"]
        ev_text = _normalize_space(ev["text"]).lower()
        if loc and ev_loc and _source_location_overlap(loc, ev_loc):
            score = max(score, 12)
        # Exact source fragment/hash evidence is stronger than ID-only linkage.
        fragment = excerpt[:120]
        if fragment and len(fragment) >= 24 and fragment in ev_text:
            score = max(score, 14)
        elif ev_text and len(ev_text) >= 24 and ev_text[:120] in excerpt:
            score = max(score, 13)
        if occ_hash and ev_text and _hash_text(f"{loc}|{ev_text}") == occ_hash:
            score = max(score, 15)
    return score


def _requirements_overlapping_occurrence(requirements: list[dict[str, Any]], occ: dict[str, Any]) -> list[dict[str, Any]]:
    """Conservative Source-location resolver for grouped Requirements.

    A grouped Candidate may cite Paragraph 125-131 while individual declarations sit inside that
    range. Stable range overlap is sufficient to create traceability when the Candidate already has
    Source evidence for that range; semantic Requirement generation is never performed here.
    """
    out = []
    occ_loc = str(occ.get("source_location") or "")
    occ_excerpt = _normalize_space(str(occ.get("source_excerpt") or "")).lower()
    sid = str(occ.get("source_req_id") or "").upper()
    for req in requirements:
        score = _location_similarity(req, occ)
        if score < 12:
            continue
        req_ids = {str(x).strip().upper() for x in _list(req.get("source_requirement_ids")) if str(x).strip()}
        evidence_text = " ".join(_normalize_space(ev.get("text", "")).lower() for ev in _req_evidence(req))
        direct = sid in req_ids or sid in evidence_text.upper() or (occ_excerpt and len(occ_excerpt) >= 24 and occ_excerpt[:80] in evidence_text)
        # Stable normalizer range overlap supports grouped-SRS traceability even if the compact AI
        # omitted one intermediate REQ ID. This only attaches provenance; it does not create behavior.
        range_backed = False
        for ev in _req_evidence(req):
            ev_loc = str(ev.get("location") or "")
            i = _location_interval(ev_loc)
            if i and i[1] != i[2] and _source_location_overlap(occ_loc, ev_loc):
                range_backed = True
                break
        if direct or range_backed:
            out.append(req)
    return out


def _evidence_location_envelopes(req: dict[str, Any], *, max_paragraph_span: int = 12, max_table_span: int = 12) -> list[str]:
    """Build conservative envelopes from multiple evidence locations for grouped Requirements.

    Example: evidence at Paragraph 125 and Paragraph 131 may represent one grouped Requirement
    covering the declarations in between. The envelope only affects provenance binding; it never
    creates Requirement behavior.
    """
    intervals = []
    for ev in _req_evidence(req):
        parsed = _location_interval(str(ev.get("location") or ""))
        if parsed:
            intervals.append(parsed)
    out: list[str] = []
    paragraph_points = [x for x in intervals if x[0] == "paragraph"]
    if len(paragraph_points) >= 2:
        start = min(x[1] for x in paragraph_points); end = max(x[2] for x in paragraph_points)
        if end - start <= max_paragraph_span:
            out.append(f"Paragraph {start}-{end}")
    table_groups: dict[int, list[tuple[str, int, int, int | None]]] = defaultdict(list)
    for item in intervals:
        if item[0] == "table" and item[3] is not None:
            table_groups[int(item[3])].append(item)
    for table_no, rows in table_groups.items():
        if len(rows) < 2:
            continue
        start = min(x[1] for x in rows); end = max(x[2] for x in rows)
        if end - start <= max_table_span:
            out.append(f"Table {table_no} / Row {start}-{end}")
    return out


def _normalize_repeat_excerpt(value: str) -> str:
    """Normalize repeated declaration text without erasing behavior-bearing facts.

    V0.55 intentionally removes only representation noise (REQ label, whitespace, punctuation,
    Unicode separators/case). Signal names, parameter names, values, conditions and actions remain.
    """
    text = _normalize_space(value).lower()
    for sid in _explicit_ids(text):
        text = re.sub(re.escape(sid), " ", text, flags=re.IGNORECASE)
    text = text.replace("→", " to ").replace("->", " to ")
    text = re.sub(r"[\[\]{}()<>|:：;,./\\]+", " ", text)
    text = re.sub(r"[-–—]+", " ", text)
    return _normalize_space(text)


def _repeat_fact_tokens(value: str) -> set[str]:
    text = _normalize_repeat_excerpt(value)
    tokens = {x.lower() for x in _SIGNAL_PATTERN.findall(value or "")}
    tokens.update(x.lower() for x in re.findall(r"\b0x[0-9a-f]+\b|\b\d+(?:\.\d+)?(?:ms|s|sec|초|%|v|a)?\b", text, flags=re.IGNORECASE))
    return tokens


def _repeat_equivalence(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Three-level repeated-occurrence equivalence used only for provenance repair.

    Exact/high-confidence matches may share traceability. Same-ID text with material behavior
    divergence remains Uncertain. This never creates Requirement content.
    """
    raw_a = str(a.get("source_excerpt") or "")
    raw_b = str(b.get("source_excerpt") or "")
    ta = _normalize_repeat_excerpt(raw_a)
    tb = _normalize_repeat_excerpt(raw_b)
    if not ta or not tb:
        return {"equivalence_class": "insufficient_evidence", "match_score": 0.0, "auto_link": False, "reason": "Empty normalized excerpt", "normalization_profile": "v0.55-repeat-1"}
    seq = 1.0 if ta == tb else SequenceMatcher(None, ta[:1200], tb[:1200]).ratio()
    tok_a = set(re.findall(r"[a-z0-9_]+|[가-힣]+", ta))
    tok_b = set(re.findall(r"[a-z0-9_]+|[가-힣]+", tb))
    union = tok_a | tok_b
    jaccard = (len(tok_a & tok_b) / len(union)) if union else 0.0
    facts_a = _repeat_fact_tokens(raw_a)
    facts_b = _repeat_fact_tokens(raw_b)
    facts_compatible = facts_a == facts_b or (not facts_a and not facts_b)
    if ta == tb:
        return {"equivalence_class": "exact_normalized_equivalence", "match_score": 1.0, "auto_link": True, "reason": "Same normalized declaration text", "normalization_profile": "v0.55-repeat-1"}
    # High-confidence equivalence remains conservative: fact-bearing tokens must agree.
    if facts_compatible and ((seq >= 0.84 and jaccard >= 0.72) or (min(len(ta), len(tb)) >= 24 and (ta in tb or tb in ta) and jaccard >= 0.70)):
        score = round((seq * 0.6 + jaccard * 0.4), 4)
        return {"equivalence_class": "high_confidence_semantic_equivalence", "match_score": score, "auto_link": True, "reason": "Same Source ID with highly similar normalized behavior and compatible fact tokens", "normalization_profile": "v0.55-repeat-1"}
    return {"equivalence_class": "same_id_behavior_divergence", "match_score": round((seq * 0.6 + jaccard * 0.4), 4), "auto_link": False, "reason": "Same Source ID but behavior evidence is not sufficiently equivalent for automatic linkage", "normalization_profile": "v0.55-repeat-1"}


def _repeat_excerpt_similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
    return float(_repeat_equivalence(a, b).get("match_score") or 0.0)


def _requirement_behavior_text(req: dict[str, Any]) -> str:
    """Text that must carry the actual Source-backed behavior; Source evidence itself is excluded."""
    parts = []
    for key in (
        "function_name", "requirement", "activation_trigger", "preconditions", "system_input_preconditions",
        "processing_action", "output", "acceptance_criteria", "failure_situations", "exception_conditions",
        "clarification_needed", "external_dependencies", "related_artifacts", "behavior_flows", "source_backed_atomic_behaviors"
    ):
        parts.append(_text(req.get(key)))
    return _normalize_space(" ".join(parts))


def _behavior_identifier_tokens(text: str) -> set[str]:
    """High-value named facts whose loss is a strong signal of Source-ID-only over-linkage."""
    tokens = set()
    # Signals/parameters/interfaces are intentionally generic and domain-safe.
    for m in re.finditer(r"\b(?:Input|Output|Par)_[A-Za-z0-9_]+\b", text or "", flags=re.IGNORECASE):
        tokens.add(m.group(0).lower())
    for m in re.finditer(r"\b0x[0-9A-Fa-f]+\b", text or ""):
        tokens.add(m.group(0).lower())
    # Common explicit interface/configuration tokens that are meaningful even without underscore.
    for m in re.finditer(r"\b(?:FactoryMode|CAN\s*DB|LIN\s*DB|RGB|White\s*LED)\b", text or "", flags=re.IGNORECASE):
        tokens.add(re.sub(r"\s+", " ", m.group(0)).lower())
    return tokens


def _semantic_preservation_result(occ: dict[str, Any], req: dict[str, Any]) -> dict[str, Any]:
    """Conservative audit: an ID/link alone is not proof that the Source behavior survived.

    This does not invent behavior and does not create a Requirement. It only checks whether
    high-value facts and action/transition cues from the declaration are visible in the
    Canonical behavior fields that reach SWE.1.
    """
    source = _normalize_space(str(occ.get("source_excerpt") or ""))
    body = _requirement_behavior_text(req)
    if not source or not body:
        return {"preserved": False, "score": 0.0, "reason": "Source declaration or Canonical behavior text is empty."}
    source_no_id = re.sub(r"\[?REQ[A-Z0-9_.-]+\]?", " ", source, flags=re.IGNORECASE)
    src_ids = _behavior_identifier_tokens(source_no_id)
    body_low = body.lower()
    matched_ids = {t for t in src_ids if t in body_low}
    id_recall = (len(matched_ids) / len(src_ids)) if src_ids else 1.0

    action_terms = [
        "주기", "송신", "저장", "유지", "초기화", "판단", "적용", "변경", "제어",
        "미작동", "무시", "검출", "설정", "전이", "이동", "mapping", "table", "도면",
    ]
    src_actions = {t for t in action_terms if t.lower() in source_no_id.lower()}
    matched_actions = {t for t in src_actions if t.lower() in body_low}
    action_recall = (len(matched_actions) / len(src_actions)) if src_actions else 1.0
    seq = SequenceMatcher(None, _normalize_repeat_excerpt(source_no_id), _normalize_repeat_excerpt(body)).ratio()

    # Named parameters/signals are stronger than generic wording. A declaration that names a
    # timing parameter but the Canonical body omits it is not considered semantically preserved.
    has_parameter = any(t.startswith("par_") for t in src_ids)
    parameter_ok = not has_parameter or all(t in body_low for t in src_ids if t.startswith("par_"))
    transition_source = bool(re.search(r"(?:->|→|\bto\b|에서\s*[^ ]+\s*로|이동\s*시|변경\s*시)", source_no_id, flags=re.IGNORECASE))
    transition_ok = (not transition_source) or bool(re.search(r"(?:->|→|전이|이동|변경)", body, flags=re.IGNORECASE))

    preserved = bool(
        parameter_ok and transition_ok and
        id_recall >= (0.60 if src_ids else 0.0) and
        (action_recall >= 0.50 or seq >= 0.34)
    )
    score = round((id_recall * 0.50 + action_recall * 0.25 + seq * 0.25), 4)
    reason = (
        "Source behavior facts are represented in Canonical behavior fields." if preserved else
        f"Source link exists, but behavior preservation is incomplete (identifier_recall={id_recall:.2f}, action_recall={action_recall:.2f}, text_similarity={seq:.2f}, parameter_ok={parameter_ok}, transition_ok={transition_ok})."
    )
    return {
        "preserved": preserved, "score": score, "reason": reason,
        "source_identifier_tokens": sorted(src_ids), "matched_identifier_tokens": sorted(matched_ids),
        "source_action_terms": sorted(src_actions), "matched_action_terms": sorted(matched_actions),
    }


def _dependency_link_candidates(requirements: list[dict[str, Any]], occ: dict[str, Any]) -> list[dict[str, Any]]:
    """Conservatively recognize Source statements whose behavior is an external-reference rule."""
    source = _normalize_space(str(occ.get("source_excerpt") or ""))
    if not source or not re.search(r"(?:참조|따른다|별도|도면|\b(?:CAN|LIN)\s*DB\b|\btable\b)", source, flags=re.IGNORECASE):
        return []
    source_low = source.lower()
    source_tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_.-]+|[가-힣]{2,}", source_low))
    domain_terms = {t for t in source_tokens if t in {"table", "도면", "차종별", "색좌표", "변환", "can", "lin", "db", "참조", "따른다"} or "table" in t or "도면" in t}
    scored = []
    for req in requirements:
        hay = _normalize_space(" ".join([
            _text(req.get("requirement")), _text(req.get("clarification_needed")),
            _text(req.get("external_dependencies")), _text(req.get("related_artifacts")),
            _text(req.get("verification_constraints")),
        ]))
        if not hay:
            continue
        hlow = hay.lower()
        id_tokens = _behavior_identifier_tokens(source)
        id_overlap = sum(1 for t in id_tokens if t in hlow)
        term_overlap = sum(1 for t in domain_terms if t in hlow)
        sim = SequenceMatcher(None, _normalize_repeat_excerpt(source), _normalize_repeat_excerpt(hay)).ratio()
        score = id_overlap * 3 + term_overlap * 2 + (2 if sim >= 0.32 else 0)
        if score >= 4:
            scored.append((score, req))
    if not scored:
        return []
    best = max(x[0] for x in scored)
    return [req for score, req in scored if score == best]


def _evidence_occurrence_score(req: dict[str, Any], occ: dict[str, Any], id_decl_count: dict[str, int]) -> int:
    """Score a Source Evidence -> Source Occurrence binding without creating new behavior."""
    sid = str(occ.get("source_req_id") or "").strip().upper()
    occ_loc = str(occ.get("source_location") or occ.get("section_path") or "")
    occ_excerpt = _normalize_space(str(occ.get("source_excerpt") or "")).lower()
    req_ids = {str(x).strip().upper() for x in _list(req.get("source_requirement_ids")) if str(x).strip()}
    score = 0
    for ev in _req_evidence(req):
        ev_loc = str(ev.get("location") or "")
        ev_text = _normalize_space(str(ev.get("text") or "")).lower()
        ev_ids = {x.upper() for x in _explicit_ids(f"{ev_loc} {ev_text}")}
        id_match = bool(sid and (sid in req_ids or sid in ev_ids))
        loc_match = bool(ev_loc and occ_loc and _source_location_overlap(ev_loc, occ_loc))
        sim = 0.0
        if ev_text and occ_excerpt:
            a = ev_text[:700]; b = occ_excerpt[:700]
            if a in b or b in a:
                sim = 1.0
            else:
                sim = SequenceMatcher(None, a, b).ratio()
        if id_match and loc_match:
            score = max(score, 100)
        elif id_match and sim >= 0.35:
            if id_decl_count.get(sid, 0) > 1:
                # Reused IDs require explicit repeated-behavior equivalence, not a loose text score.
                eq = _repeat_equivalence({"source_excerpt": ev_text}, {"source_excerpt": occ_excerpt})
                if eq.get("auto_link"):
                    score = max(score, 92)
            else:
                score = max(score, 92)
        elif id_match and id_decl_count.get(sid, 0) == 1:
            score = max(score, 82)
        elif loc_match and sim >= 0.55:
            score = max(score, 88)
        elif loc_match and sim >= 0.25:
            score = max(score, 78)
        elif loc_match:
            # Stable exact/range location is acceptable only if this block has one declaration.
            same_loc_count = 0
            # The caller supplies ID counts only; use unique source ID as a conservative proxy.
            if sid and id_decl_count.get(sid, 0) == 1:
                same_loc_count = 1
            if same_loc_count == 1:
                score = max(score, 70)
        elif sim >= 0.78:
            score = max(score, 72)
    return score


def _repair_requirement_traceability(requirements: list[dict[str, Any]], declarations: list[dict[str, Any]], id_decl_count: dict[str, int]) -> dict[str, int]:
    """Deterministically repair provenance without generating new Requirement behavior.

    V0.55 preserves the V0.54 repairs and adds auditable equivalence/disposition semantics:
    1) grouped-evidence envelopes (e.g. Paragraph 125 + 131 -> 125-131), and
    2) repeated-occurrence propagation only when the same Source ID has near-identical excerpts.
    """
    repaired_requirements = 0
    repaired_occurrences = 0
    grouped_range_links = 0
    repeated_equivalent_links = 0
    linkage_audit_records: list[dict[str, Any]] = []
    declarations_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_oid = {}
    for occ in declarations:
        sid = str(occ.get("source_req_id") or "").strip().upper()
        if sid:
            declarations_by_id[sid].append(occ)
        if occ.get("occurrence_id"):
            by_oid[str(occ.get("occurrence_id"))] = occ

    for req in requirements:
        req.setdefault("source_requirement_ids", [])
        req.setdefault("source_requirement_occurrence_ids", [])
        req.setdefault("source_chunk_ids", [])
        existing_occ = {str(x) for x in _list(req.get("source_requirement_occurrence_ids")) if str(x)}
        scored = [(occ, _evidence_occurrence_score(req, occ, id_decl_count)) for occ in declarations]
        strong = [(occ, score) for occ, score in scored if score >= 78]
        if not strong:
            best = max((score for _occ, score in scored), default=0)
            if best >= 70:
                best_rows = [(occ, score) for occ, score in scored if score == best]
                if len(best_rows) == 1:
                    strong = best_rows

        # Grouped Requirement repair: multiple explicit evidence points can define one small stable range.
        envelopes = _evidence_location_envelopes(req)
        envelope_rows: list[tuple[dict[str, Any], int]] = []
        for occ in declarations:
            occ_loc = str(occ.get("source_location") or "")
            if any(_source_location_overlap(env, occ_loc) for env in envelopes):
                envelope_rows.append((occ, 79))
        known = {str(x.get("occurrence_id") or "") for x, _ in strong}
        for row in envelope_rows:
            if str(row[0].get("occurrence_id") or "") not in known:
                strong.append(row); known.add(str(row[0].get("occurrence_id") or "")); grouped_range_links += 1
                linkage_audit_records.append({
                    "link_type": "grouped_evidence_envelope",
                    "candidate_id": str(req.get("candidate_id") or ""),
                    "srs_id": str(req.get("srs_id") or ""),
                    "occurrence_id": str(row[0].get("occurrence_id") or ""),
                    "source_requirement_id": str(row[0].get("source_req_id") or ""),
                    "source_location": str(row[0].get("source_location") or ""),
                    "envelopes": list(envelopes),
                    "match_score": row[1],
                    "linkage_reason": "Occurrence lies inside a conservative envelope formed by multiple explicit evidence locations.",
                    "policy_version": "v0.55-group-envelope-1",
                })

        changed = False
        for occ, _score in strong:
            oid = str(occ.get("occurrence_id") or "")
            sid = str(occ.get("source_req_id") or "")
            chunk = str(occ.get("chunk_id") or "")
            was_new = bool(oid and oid not in existing_occ)
            if was_new:
                # If a reused Source ID is linked outside the Requirement's explicit locations,
                # record why it was safe: exact/high-confidence repeated evidence.
                sid_upper = sid.strip().upper()
                loc_overlaps = any(_source_location_overlap(str(ev.get("location") or ""), str(occ.get("source_location") or "")) for ev in _req_evidence(req))
                if sid_upper and id_decl_count.get(sid_upper, 0) > 1 and not loc_overlaps:
                    eq_candidates = []
                    for ev in _req_evidence(req):
                        ev_ids = {x.upper() for x in _explicit_ids(f"{ev.get('location','')} {ev.get('text','')}")}
                        if sid_upper in ev_ids or sid_upper in {str(x).strip().upper() for x in _list(req.get("source_requirement_ids"))}:
                            eq = _repeat_equivalence({"source_excerpt": ev.get("text", "")}, occ)
                            if eq.get("auto_link"):
                                eq_candidates.append(eq)
                    if eq_candidates:
                        eq = max(eq_candidates, key=lambda x: float(x.get("match_score") or 0.0))
                        repeated_equivalent_links += 1
                        linkage_audit_records.append({
                            "link_type": "repeated_equivalent",
                            "candidate_id": str(req.get("candidate_id") or ""),
                            "srs_id": str(req.get("srs_id") or ""),
                            "source_requirement_id": sid,
                            "occurrence_id": oid,
                            "matched_anchor_occurrence_id": "source_evidence",
                            "equivalence_class": eq.get("equivalence_class"),
                            "match_score": eq.get("match_score"),
                            "normalization_profile": eq.get("normalization_profile"),
                            "match_reason": eq.get("reason"),
                            "policy_version": "v0.55-repeat-equivalence-1",
                        })
                req["source_requirement_occurrence_ids"].append(oid)
                existing_occ.add(oid); repaired_occurrences += 1; changed = True
            if sid and sid.upper() not in {str(x).upper() for x in req["source_requirement_ids"]}:
                req["source_requirement_ids"].append(sid); changed = True
            if chunk and chunk not in req["source_chunk_ids"]:
                req["source_chunk_ids"].append(chunk); changed = True

        # Repeated declarations: propagate only to the same Source ID with near-identical source text.
        seed_occs = [by_oid[x] for x in list(existing_occ) if x in by_oid]
        for seed in seed_occs:
            sid = str(seed.get("source_req_id") or "").strip().upper()
            if not sid:
                continue
            for sibling in declarations_by_id.get(sid, []):
                oid = str(sibling.get("occurrence_id") or "")
                if not oid or oid in existing_occ:
                    continue
                eq = _repeat_equivalence(seed, sibling)
                if not eq.get("auto_link"):
                    continue
                req["source_requirement_occurrence_ids"].append(oid)
                existing_occ.add(oid); repaired_occurrences += 1; repeated_equivalent_links += 1; changed = True
                linkage_audit_records.append({
                    "link_type": "repeated_equivalent",
                    "candidate_id": str(req.get("candidate_id") or ""),
                    "srs_id": str(req.get("srs_id") or ""),
                    "source_requirement_id": str(sibling.get("source_req_id") or ""),
                    "occurrence_id": oid,
                    "matched_anchor_occurrence_id": str(seed.get("occurrence_id") or ""),
                    "equivalence_class": eq.get("equivalence_class"),
                    "match_score": eq.get("match_score"),
                    "normalization_profile": eq.get("normalization_profile"),
                    "match_reason": eq.get("reason"),
                    "policy_version": "v0.55-repeat-equivalence-1",
                })
                chunk = str(sibling.get("chunk_id") or "")
                if chunk and chunk not in req["source_chunk_ids"]:
                    req["source_chunk_ids"].append(chunk)
                raw_sid = str(sibling.get("source_req_id") or "")
                if raw_sid and raw_sid.upper() not in {str(x).upper() for x in req["source_requirement_ids"]}:
                    req["source_requirement_ids"].append(raw_sid)

        # Materialize the accepted Source-backed declaration units on the Canonical Requirement.
        # These are not invented fields: they are bounded copies of linked declaration evidence and
        # are exported in SWE.1 as atomic behavior refs when a grouped SRS carries multiple Source IDs.
        atomic_units = []
        for oid in sorted(existing_occ):
            source_occ = by_oid.get(oid)
            if not source_occ:
                continue
            atomic_units.append({
                "source_requirement_id": str(source_occ.get("source_req_id") or ""),
                "source_occurrence_id": oid,
                "source_chunk_id": str(source_occ.get("chunk_id") or ""),
                "source_location": str(source_occ.get("source_location") or source_occ.get("section_path") or ""),
                "behavior_text": _normalize_space(str(source_occ.get("source_excerpt") or ""))[:900],
                "knowledge_state": "KNOWN",
            })
        if atomic_units != req.get("source_backed_atomic_behaviors"):
            req["source_backed_atomic_behaviors"] = atomic_units
            changed = True
        if changed:
            repaired_requirements += 1
    return {
        "repaired_requirement_count": repaired_requirements,
        "repaired_occurrence_link_count": repaired_occurrences,
        "grouped_range_link_count": grouped_range_links,
        "repeated_equivalent_link_count": repeated_equivalent_links,
        "linkage_audit_records": linkage_audit_records,
    }


def _build_behavior_coverage_summary(declarations: list[dict[str, Any]]) -> dict[str, Any]:
    """Informational behavior-level view; occurrence coverage remains the release/audit denominator.

    Repeated declarations with the same Source ID are clustered only when their excerpts are highly
    similar. This prevents duplicated source text from making functional coverage look artificially low
    while preserving uncertainty when one ID is reused for different behavior.
    """
    clusters: list[list[dict[str, Any]]] = []
    for occ in declarations:
        sid = str(occ.get("source_req_id") or "").strip().upper()
        placed = False
        for cluster in clusters:
            first = cluster[0]
            eq = _repeat_equivalence(first, occ)
            if sid and sid == str(first.get("source_req_id") or "").strip().upper() and eq.get("auto_link"):
                cluster.append(occ); placed = True; break
        if not placed:
            clusters.append([occ])
    covered = dispositioned = uncertain = missing = 0
    records = []
    for idx, cluster in enumerate(clusters, start=1):
        statuses = {str(x.get("coverage_status") or "") for x in cluster}
        if "Covered" in statuses or "Partially Covered" in statuses:
            status = "Covered"; covered += 1
        elif statuses & {"Gap / Insufficient Source", "Intentionally Excluded", "Not a SW Requirement"}:
            status = "Dispositioned"; dispositioned += 1
        elif "Uncertain" in statuses:
            status = "Uncertain"; uncertain += 1
        else:
            status = "Missing"; missing += 1
        records.append({
            "behavior_cluster_id": f"SRC-BHV-{idx:04d}",
            "source_requirement_id": str(cluster[0].get("source_req_id") or ""),
            "occurrence_ids": [str(x.get("occurrence_id") or "") for x in cluster],
            "status": status,
        })
    total = len(clusters)
    return {
        "behavior_cluster_count": total,
        "covered_behavior_count": covered,
        "dispositioned_behavior_count": dispositioned,
        "uncertain_behavior_count": uncertain,
        "missing_behavior_count": missing,
        "behavior_coverage_percent": round((covered / total * 100.0) if total else 0.0, 2),
        "records": records,
        "scope_note": "Informational unique-behavior estimate. Release coverage continues to use declaration occurrences; repeated IDs are clustered only when source excerpts are highly similar.",
    }


def build_source_coverage(data: dict[str, Any], compact_text: str) -> dict[str, Any]:
    occurrences = extract_source_requirement_occurrences(compact_text)
    declarations = [x for x in occurrences if x.get("occurrence_type") == "declaration"]
    references = [x for x in occurrences if x.get("occurrence_type") != "declaration"]

    unindexed_blocks = []
    for block in _iter_source_blocks(compact_text):
        if _explicit_ids(block.get("text") or ""):
            continue
        unindexed_blocks.append({
            "chunk_id": block.get("chunk_id"),
            "source_location": block.get("location"),
            "source_kind": block.get("kind"),
            "content_hash": _hash_text(block.get("text") or ""),
            "reason": "No supported explicit requirement identifier detected; semantic classification is deferred.",
        })

    requirements = [x for x in (data.get("requirements") or []) if isinstance(x, dict)]
    gaps = [x for x in (data.get("gaps") or []) if isinstance(x, dict)]
    for req in requirements:
        normalize_requirement_extensions(req)

    id_decl_count = defaultdict(int)
    for occ in declarations:
        id_decl_count[str(occ.get("source_req_id") or "").upper()] += 1

    traceability_repair = _repair_requirement_traceability(requirements, declarations, id_decl_count)

    gap_by_source: dict[str, list[str]] = defaultdict(list)
    gap_by_occ: dict[str, list[str]] = defaultdict(list)
    for gap in gaps:
        gid = str(gap.get("gap_id") or "").strip()
        for sid in _list(gap.get("related_source_requirement_ids")):
            if gid and str(sid).strip():
                gap_by_source[str(sid).strip().upper()].append(gid)
        for oid in _list(gap.get("related_source_occurrence_ids")):
            if gid and str(oid).strip():
                gap_by_occ[str(oid).strip()].append(gid)

    for occ in declarations:
        sid = str(occ.get("source_req_id") or "")
        oid = str(occ.get("occurrence_id") or "")
        # V0.56 single-truth rule: deterministic repair commits occurrence IDs onto the
        # Canonical Requirement first. Coverage must consume that committed linkage rather than
        # independently re-deciding and accidentally overwriting it as Uncertain.
        committed_candidates = [
            req for req in requirements
            if oid and oid in {str(x) for x in _list(req.get("source_requirement_occurrence_ids"))}
        ]
        candidates = [req for req in requirements if _req_mentions_source_id(req, sid)]
        overlap_candidates = _requirements_overlapping_occurrence(requirements, occ)
        linked: list[dict[str, Any]] = []

        if committed_candidates:
            linked = committed_candidates
            occ["linkage_source"] = "canonical_committed_occurrence"
        elif id_decl_count[sid.upper()] <= 1:
            # Unique explicit IDs may link to every SRS that intentionally groups that declaration.
            linked = []
            _seen_ids = set()
            for _req in candidates + overlap_candidates:
                _key = str(_req.get("candidate_id") or id(_req))
                if _key not in _seen_ids:
                    _seen_ids.add(_key); linked.append(_req)
        elif not linked:
            # Reused IDs require source-location/content evidence. Do not leave them Uncertain merely
            # because the identifier string is reused when stable evidence clearly overlaps.
            pool = []
            _seen_ids = set()
            for _req in candidates + overlap_candidates:
                _key = str(_req.get("candidate_id") or id(_req))
                if _key not in _seen_ids:
                    _seen_ids.add(_key); pool.append(_req)
            scored = [(req, _location_similarity(req, occ)) for req in pool]
            best = max((score for _req, score in scored), default=0)
            linked = [req for req, score in scored if score >= 12 and score == best]
            if pool and not linked:
                occ["coverage_status"] = "Uncertain"
                occ["uncertainty_reason"] = "Source ID is reused and Canonical evidence cannot disambiguate this declaration by stable location/content context."
                occ["disposition_reason"] = occ["uncertainty_reason"]

        # Stable location overlap can legitimately connect one grouped SRS to multiple declaration occurrences.
        if linked:
            # Preserve order while removing duplicate object identities.
            dedup = []
            seen_req = set()
            for req in linked:
                key = str(req.get("candidate_id") or id(req))
                if key not in seen_req:
                    seen_req.add(key); dedup.append(req)
            linked = dedup
            semantic_rows = []
            for req in linked:
                sem = _semantic_preservation_result(occ, req)
                semantic_rows.append({
                    "candidate_id": str(req.get("candidate_id") or ""),
                    "srs_id": str(req.get("srs_id") or ""),
                    **sem,
                })
            semantically_preserved = any(x.get("preserved") for x in semantic_rows)
            occ["semantic_behavior_preservation"] = semantic_rows
            occ["coverage_status"] = "Covered" if semantically_preserved else "Partially Covered"
            occ["linked_candidate_ids"] = [str(x.get("candidate_id") or "") for x in linked if x.get("candidate_id")]
            occ["linked_srs_ids"] = [str(x.get("srs_id") or "") for x in linked if x.get("srs_id")]
            if semantically_preserved:
                occ["disposition_reason"] = (
                    "Canonical Requirement is linked to this declaration occurrence by a committed deterministic occurrence link and the Source behavior is represented in Canonical behavior fields."
                    if occ.get("linkage_source") == "canonical_committed_occurrence"
                    else "Canonical Requirement is linked to this declaration occurrence by explicit ID/location evidence and the Source behavior is represented in Canonical behavior fields."
                )
            else:
                occ["disposition_reason"] = "Traceability exists, but Source-ID-only linkage is insufficient: the linked Canonical Requirement does not preserve enough of the declaration behavior in its actual behavior fields."
                occ["semantic_behavior_loss"] = True
            for req in linked:
                if sid and sid not in req.get("source_requirement_ids", []):
                    req.setdefault("source_requirement_ids", []).append(sid)
                if occ["occurrence_id"] not in req["source_requirement_occurrence_ids"]:
                    req["source_requirement_occurrence_ids"].append(occ["occurrence_id"])
                chunk_id = str(occ.get("chunk_id") or "")
                if chunk_id and chunk_id not in req["source_chunk_ids"]:
                    req["source_chunk_ids"].append(chunk_id)
        else:
            dependency_candidates = _dependency_link_candidates(requirements, occ)
            if dependency_candidates:
                occ["coverage_status"] = "Partially Covered"
                occ["linked_candidate_ids"] = [str(x.get("candidate_id") or "") for x in dependency_candidates if x.get("candidate_id")]
                occ["linked_srs_ids"] = [str(x.get("srs_id") or "") for x in dependency_candidates if x.get("srs_id")]
                occ["dependency_linkage"] = True
                occ["disposition_reason"] = "Source behavior is an external-reference/dependency rule and is linked to Canonical dependency/clarification evidence; no external value is invented."
                for req in dependency_candidates:
                    if sid and sid not in req.get("source_requirement_ids", []):
                        req.setdefault("source_requirement_ids", []).append(sid)
                    if occ["occurrence_id"] not in req.setdefault("source_requirement_occurrence_ids", []):
                        req["source_requirement_occurrence_ids"].append(occ["occurrence_id"])
                    chunk_id = str(occ.get("chunk_id") or "")
                    if chunk_id and chunk_id not in req.setdefault("source_chunk_ids", []):
                        req["source_chunk_ids"].append(chunk_id)
            elif gap_by_occ.get(occ["occurrence_id"]) or gap_by_source.get(sid.upper()):
                occ["coverage_status"] = "Gap / Insufficient Source"
                occ["linked_gap_issue_ids"] = list(dict.fromkeys(gap_by_occ.get(occ["occurrence_id"], []) + gap_by_source.get(sid.upper(), [])))
                occ["disposition_reason"] = "Declaration is explicitly dispositioned through a Gap/Insufficient Source record."
            elif occ["coverage_status"] != "Uncertain":
                occ["coverage_status"] = "Missing"
                occ["disposition_reason"] = "No Canonical Requirement or explicit Gap linkage was found for this declaration occurrence."


    counts = defaultdict(int)
    for occ in declarations:
        counts[occ["coverage_status"]] += 1
    total = len(declarations)
    covered = counts["Covered"]
    partial = counts["Partially Covered"]
    weighted = ((covered + 0.5 * partial) / total * 100.0) if total else 0.0

    fully_dispositioned = []
    uncertain_with_evidence = []
    undispositioned = []
    for occ in declarations:
        status = str(occ.get("coverage_status") or "")
        if status in {"Covered", "Partially Covered", "Gap / Insufficient Source", "Intentionally Excluded", "Not a SW Requirement"}:
            if str(occ.get("disposition_reason") or "").strip():
                fully_dispositioned.append(occ)
            else:
                undispositioned.append(occ)
        elif status == "Uncertain":
            has_reason = bool(str(occ.get("uncertainty_reason") or occ.get("disposition_reason") or "").strip())
            has_link = bool(_list(occ.get("linked_gap_issue_ids")))
            if has_reason or has_link:
                uncertain_with_evidence.append(occ)
            else:
                undispositioned.append(occ)
        else:
            undispositioned.append(occ)
    disposition = ((len(fully_dispositioned) + len(uncertain_with_evidence)) / total * 100.0) if total else 0.0

    explicit_with_evidence = [
        req for req in requirements
        if str(req.get("derivation_type") or "").lower() == "explicit" and _req_evidence(req)
    ]
    total_requirement_occurrence_links = sum(
        len({str(x) for x in _list(req.get("source_requirement_occurrence_ids")) if str(x)})
        for req in requirements
    )
    coverage_validity = "VALID"
    coverage_validity_reason = ""
    if declarations and explicit_with_evidence and total_requirement_occurrence_links == 0:
        coverage_validity = "INVALID"
        coverage_validity_reason = (
            "TRACEABILITY_BINDING_EMPTY: Canonical explicit Requirements and Source Evidence exist, "
            "but no Source Requirement Occurrence is linked. Coverage/Regression results are not release-valid."
        )

    # V0.56: linkage audit and final occurrence matrix share one truth. Proposal counts are not
    # reported as accepted links unless the final matrix commits the same Candidate/SRS and the
    # Source behavior is actually preserved.
    occ_by_id = {str(x.get("occurrence_id") or ""): x for x in declarations if str(x.get("occurrence_id") or "")}
    accepted_repeat = accepted_group = 0
    for rec in traceability_repair.get("linkage_audit_records") or []:
        if not isinstance(rec, dict):
            continue
        occ = occ_by_id.get(str(rec.get("occurrence_id") or "")) or {}
        cid = str(rec.get("candidate_id") or "")
        sid_value = str(rec.get("srs_id") or "")
        candidate_ok = (not cid) or cid in {str(x) for x in _list(occ.get("linked_candidate_ids"))}
        srs_ok = (not sid_value) or sid_value in {str(x) for x in _list(occ.get("linked_srs_ids"))}
        accepted = bool(occ and occ.get("coverage_status") == "Covered" and candidate_ok and srs_ok)
        rec["accepted_final"] = accepted
        rec["final_coverage_status"] = str(occ.get("coverage_status") or "Unmatched")
        rec["final_linked_candidate_ids"] = list(occ.get("linked_candidate_ids") or [])
        rec["final_linked_srs_ids"] = list(occ.get("linked_srs_ids") or [])
        if not accepted:
            rec["final_rejection_reason"] = str(occ.get("disposition_reason") or occ.get("uncertainty_reason") or "Proposal was not committed by final coverage semantics.")
        if accepted and rec.get("link_type") == "repeated_equivalent":
            accepted_repeat += 1
        if accepted and rec.get("link_type") == "grouped_evidence_envelope":
            accepted_group += 1
    traceability_repair["repeated_equivalent_proposal_count"] = int(traceability_repair.get("repeated_equivalent_link_count") or 0)
    traceability_repair["grouped_range_proposal_count"] = int(traceability_repair.get("grouped_range_link_count") or 0)
    traceability_repair["repeated_equivalent_link_count"] = accepted_repeat
    traceability_repair["grouped_range_link_count"] = accepted_group
    traceability_repair["linkage_audit_truth_policy"] = "v0.56-final-matrix-single-truth"

    return {
        "coverage_validity": coverage_validity,
        "coverage_validity_reason": coverage_validity_reason,
        "traceability_repair": traceability_repair,
        "total_requirement_occurrence_link_count": total_requirement_occurrence_links,
        "source_requirement_occurrences": occurrences,
        "declaration_occurrence_ids": [x["occurrence_id"] for x in declarations],
        "reference_occurrence_ids": [x["occurrence_id"] for x in references],
        "covered": [x["occurrence_id"] for x in declarations if x["coverage_status"] == "Covered"],
        "partially_covered": [x["occurrence_id"] for x in declarations if x["coverage_status"] == "Partially Covered"],
        "missing": [x["occurrence_id"] for x in declarations if x["coverage_status"] == "Missing"],
        "gap_or_insufficient_source": [x["occurrence_id"] for x in declarations if x["coverage_status"] == "Gap / Insufficient Source"],
        "intentionally_excluded": [x["occurrence_id"] for x in declarations if x["coverage_status"] == "Intentionally Excluded"],
        "not_sw_requirement": [x["occurrence_id"] for x in declarations if x["coverage_status"] == "Not a SW Requirement"],
        "uncertain": [x["occurrence_id"] for x in declarations if x["coverage_status"] == "Uncertain"],
        "explicit_source_requirement_occurrence_count": total,
        "reference_occurrence_count": len(references),
        "covered_count": covered,
        "partially_covered_count": partial,
        "missing_count": counts["Missing"],
        "semantic_behavior_loss_count": sum(1 for x in declarations if x.get("semantic_behavior_loss")),
        "semantic_behavior_loss_occurrence_ids": [x.get("occurrence_id") for x in declarations if x.get("semantic_behavior_loss")],
        "semantic_behavior_loss_release_blocking": any(x.get("semantic_behavior_loss") for x in declarations),
        "gap_or_insufficient_source_count": counts["Gap / Insufficient Source"],
        "intentionally_excluded_count": counts["Intentionally Excluded"],
        "not_sw_requirement_count": counts["Not a SW Requirement"],
        "uncertain_count": counts["Uncertain"],
        "unindexed_source_blocks_count": len(unindexed_blocks),
        "unindexed_source_blocks": unindexed_blocks,
        "weighted_source_coverage_percent": round(weighted, 2),
        "behavior_coverage_summary": _build_behavior_coverage_summary(declarations),
        "disposition_coverage_percent": round(disposition, 2),
        "fully_dispositioned_count": len(fully_dispositioned),
        "uncertain_with_evidence_count": len(uncertain_with_evidence),
        "undispositioned_count": len(undispositioned),
        "undispositioned_occurrence_ids": [x.get("occurrence_id") for x in undispositioned],
        "missing_program_extraction_count": counts["Missing"],
        "coverage_scope": "Declaration-only explicit source identifier coverage",
        "scope_note": (
            "Only declaration occurrences are used in the coverage denominator. Cross/table references are retained as reference evidence. "
            "Missing means no direct Canonical/Gap linkage was found and is treated as a program-extraction/review candidate; it does not by itself prove that the source item is a SW requirement. Uncertain contributes to disposition only when a concrete reason or review linkage exists."
        ),
    }


def _normalize_candidate_ref(value: str) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"CAND[_-]?\d+", text, flags=re.IGNORECASE):
        digits = re.search(r"\d+", text).group(0)
        return f"REQ-CAND-{int(digits):03d}"
    if re.fullmatch(r"REQ[-_]?CAND[-_]?\d+", text, flags=re.IGNORECASE):
        digits = re.search(r"\d+", text).group(0)
        return f"REQ-CAND-{int(digits):03d}"
    return text


def normalize_gap_references(gap: dict[str, Any], candidate_map: dict[str, str] | None = None) -> dict[str, Any]:
    copied = json.loads(json.dumps(gap, ensure_ascii=False))
    candidate_map = candidate_map or {}
    raw_candidates = []
    for key in ("related_candidate_ids", "related_candidates", "related_requirements"):
        raw_candidates.extend(_list(copied.get(key)))
    normalized = []
    for value in raw_candidates:
        raw = str(value or "").strip()
        mapped = candidate_map.get(raw) or candidate_map.get(raw.upper()) or _normalize_candidate_ref(raw)
        if mapped and mapped not in normalized:
            normalized.append(mapped)
    copied["related_candidate_ids"] = normalized
    copied.pop("related_candidates", None)
    copied.pop("related_requirements", None)
    copied.setdefault("related_srs_ids", [])
    copied.setdefault("related_source_occurrence_ids", [])
    copied.setdefault("related_source_requirement_ids", [])
    copied.setdefault("severity", "medium")
    copied.setdefault("blocking_for_verification", False)
    return copied


def _build_review_findings_for_missing(data: dict[str, Any]) -> None:
    findings = [x for x in (data.get("review_findings") or []) if isinstance(x, dict)]
    existing = {str(x.get("finding_id") or "") for x in findings}
    coverage = data.get("source_coverage") or {}
    if str(coverage.get("coverage_validity") or "VALID") == "INVALID":
        fid = "RF-TRACEABILITY-BINDING-EMPTY"
        if fid not in existing:
            findings.append({
                "finding_id": fid,
                "finding_type": "Global Traceability Binding Failure",
                "classification": "Traceability linkage regression",
                "status": "Open",
                "severity": "critical",
                "source_requirement_id": "",
                "source_occurrence_id": "",
                "source_location": "",
                "source_excerpt": "",
                "target_source_occurrence_ids": [],
                "target_srs_ids": [],
                "related_candidate_ids": [],
                "related_srs_ids": [],
                "reason": str(coverage.get("coverage_validity_reason") or "TRACEABILITY_BINDING_EMPTY"),
                "recommended_action": "Repair Source Requirement/Occurrence/Chunk binding before interpreting per-occurrence Missing findings.",
                "source_fact_confirmed": True,
                "canonical_link_confirmed": False,
                "extraction_coverage_confirmed": False,
            })
        # Avoid flooding the Review Package with false semantic Missing findings when the entire binding layer failed.
        data["review_findings"] = findings
        return

    for occ in (coverage.get("source_requirement_occurrences") or []):
        if not isinstance(occ, dict) or occ.get("occurrence_type") != "declaration":
            continue
        status = str(occ.get("coverage_status") or "")
        if status not in {"Missing", "Uncertain", "Partially Covered"}:
            continue
        prefix = "MISS" if status == "Missing" else ("SEM" if status == "Partially Covered" and occ.get("semantic_behavior_loss") else "UNC")
        fid = f"RF-COV-{prefix}-{str(occ.get('occurrence_id') or '').replace('SRC-OCC-', '')}"
        if fid in existing:
            continue
        if status == "Missing":
            description = "Explicit declaration occurrence has no Canonical Requirement/Gap linkage; program extraction or traceability review is required."
            finding_type = "Missing Source-backed behavior"
            classification = "Missing Source-backed behavior"
            severity = "high"
        elif status == "Partially Covered" and occ.get("semantic_behavior_loss"):
            description = "Source ID/Occurrence is linked, but the linked Canonical Requirement does not preserve the declaration's actual behavior in requirement/trigger/action/output/acceptance fields."
            finding_type = "Semantic Behavior Preservation Gap"
            classification = "Source-ID-only linkage / Semantic behavior loss"
            severity = "high"
        else:
            description = "Declaration occurrence cannot be safely aligned to a Canonical Requirement under the available location/content evidence."
            finding_type = "Coverage Uncertain"
            classification = "Traceability / classification uncertainty"
            severity = "review"
        findings.append({
            "finding_id": fid,
            "finding_type": finding_type,
            "classification": classification,
            "status": "Open",
            "severity": severity,
            "source_requirement_id": occ.get("source_req_id"),
            "source_occurrence_id": occ.get("occurrence_id"),
            "source_location": occ.get("source_location") or occ.get("section_path"),
            "source_excerpt": occ.get("source_excerpt"),
            "target_source_occurrence_ids": [occ.get("occurrence_id")],
            "target_srs_ids": list(occ.get("linked_srs_ids") or []),
            "related_candidate_ids": list(occ.get("linked_candidate_ids") or []),
            "related_srs_ids": list(occ.get("linked_srs_ids") or []),
            "reason": description,
            "recommended_action": (
                "Restore the Source-backed behavior in Canonical/SWE.1 text or correct the over-link; do not treat Source ID presence alone as preservation."
                if status == "Partially Covered" and occ.get("semantic_behavior_loss")
                else "Human review; do not auto-generate unsupported Requirement content."
            ),
            "source_fact_confirmed": True,
            "canonical_link_confirmed": bool(occ.get("linked_candidate_ids") or occ.get("linked_srs_ids")),
            "extraction_coverage_confirmed": status == "Covered",
        })
        if fid not in occ.setdefault("linked_gap_issue_ids", []):
            occ["linked_gap_issue_ids"].append(fid)
        if status == "Uncertain" and not str(occ.get("uncertainty_reason") or "").strip():
            occ["uncertainty_reason"] = description
        if not str(occ.get("disposition_reason") or "").strip():
            occ["disposition_reason"] = description
        existing.add(fid)
    data["review_findings"] = findings


def _refresh_coverage_disposition_summary(data: dict[str, Any]) -> None:
    """Refresh disposition-only metrics after Review/Disposition sidecars are attached.

    Coverage status remains Missing for a genuinely unextracted source behavior. Explicit
    disposition means the missing fact is managed/auditable, not that it has become Covered.
    """
    coverage = data.get("source_coverage") if isinstance(data.get("source_coverage"), dict) else {}
    declarations = [x for x in (coverage.get("source_requirement_occurrences") or []) if isinstance(x, dict) and x.get("occurrence_type") == "declaration"]
    fully, uncertain, undispositioned = [], [], []
    for occ in declarations:
        status = str(occ.get("coverage_status") or "")
        reason = str(occ.get("disposition_reason") or occ.get("uncertainty_reason") or "").strip()
        has_sidecar = bool(_list(occ.get("linked_gap_issue_ids")) or _list(occ.get("linked_missing_disposition_ids")))
        if status in {"Covered", "Partially Covered", "Gap / Insufficient Source", "Intentionally Excluded", "Not a SW Requirement"}:
            (fully if reason else undispositioned).append(occ)
        elif status == "Uncertain":
            (uncertain if reason or has_sidecar else undispositioned).append(occ)
        elif status == "Missing":
            # Missing remains a release-quality defect, but may be explicitly dispositioned for reference completeness.
            (fully if reason and has_sidecar else undispositioned).append(occ)
        else:
            undispositioned.append(occ)
    total = len(declarations)
    coverage["disposition_coverage_percent"] = round(((len(fully) + len(uncertain)) / total * 100.0) if total else 0.0, 2)
    coverage["fully_dispositioned_count"] = len(fully)
    coverage["uncertain_with_evidence_count"] = len(uncertain)
    coverage["undispositioned_count"] = len(undispositioned)
    coverage["undispositioned_occurrence_ids"] = [x.get("occurrence_id") for x in undispositioned]


def _build_missing_behavior_dispositions(data: dict[str, Any]) -> None:
    """Create explicit source-backed disposition objects for genuinely Missing behaviors.

    This is a review/audit sidecar only. It never creates a Canonical Requirement and never
    changes Missing to Covered. Repeated equivalent declarations are grouped conservatively.
    """
    coverage = data.get("source_coverage") if isinstance(data.get("source_coverage"), dict) else {}
    missing = [x for x in (coverage.get("source_requirement_occurrences") or []) if isinstance(x, dict) and x.get("occurrence_type") == "declaration" and x.get("coverage_status") == "Missing"]
    clusters: list[list[dict[str, Any]]] = []
    for occ in missing:
        sid = str(occ.get("source_req_id") or "").strip().upper()
        placed = False
        for cluster in clusters:
            first = cluster[0]
            if sid and sid == str(first.get("source_req_id") or "").strip().upper() and _repeat_equivalence(first, occ).get("auto_link"):
                cluster.append(occ); placed = True; break
        if not placed:
            clusters.append([occ])
    dispositions = []
    for idx, cluster in enumerate(clusters, start=1):
        first = cluster[0]
        did = f"MISSING-DISP-{idx:03d}"
        source_ids = list(dict.fromkeys(str(x.get("source_req_id") or "") for x in cluster if str(x.get("source_req_id") or "")))
        occ_ids = [str(x.get("occurrence_id") or "") for x in cluster if str(x.get("occurrence_id") or "")]
        chunks = list(dict.fromkeys(str(x.get("chunk_id") or "") for x in cluster if str(x.get("chunk_id") or "")))
        locations = list(dict.fromkeys(str(x.get("source_location") or x.get("section_path") or "") for x in cluster if str(x.get("source_location") or x.get("section_path") or "")))
        excerpt = _normalize_space(str(first.get("source_excerpt") or ""))[:320]
        dispositions.append({
            "disposition_id": did,
            "classification": "Source-backed Behavior Not Yet Canonicalized",
            "status": "Open",
            "release_blocking": True,
            "knowledge_state": "KNOWN",
            "source_requirement_ids": source_ids,
            "source_occurrence_ids": occ_ids,
            "source_chunk_ids": chunks,
            "source_locations": locations,
            "compact_source_excerpt": excerpt,
            "excerpt_fingerprint": f"sha256:{hashlib.sha256(excerpt.encode('utf-8', errors='ignore')).hexdigest()[:20]}" if excerpt else "",
            "candidate_state": "No Canonical Candidate",
            "required_action": "Extraction Candidate Needed / Human Disposition Required",
            "must_not_assume": "Do not generate source-missing values, variants, mappings, priorities or test data while resolving this missing behavior.",
            "policy_version": "v0.55-missing-disposition-1",
        })
        for occ in cluster:
            if did not in occ.setdefault("linked_missing_disposition_ids", []):
                occ["linked_missing_disposition_ids"].append(did)
            occ["disposition_reason"] = "Source-backed behavior is confirmed but not yet Canonicalized; explicit Missing Behavior Disposition is open."
    data["missing_behavior_dispositions"] = dispositions
    coverage["actual_missing_behavior_count"] = len(dispositions)
    coverage["actual_missing_behavior_disposition_count"] = len(dispositions)
    coverage["actual_missing_behavior_release_blocking"] = bool(dispositions)
    _refresh_coverage_disposition_summary(data)


def build_reference_integrity(data: dict[str, Any]) -> dict[str, Any]:
    reqs = [x for x in (data.get("requirements") or []) if isinstance(x, dict)]
    gaps = [x for x in (data.get("gaps") or []) if isinstance(x, dict)]
    candidate_ids = {str(x.get("candidate_id") or "") for x in reqs if x.get("candidate_id")}
    srs_ids = {str(x.get("srs_id") or "") for x in reqs if x.get("srs_id")}
    source_occ_ids = {
        str(x.get("occurrence_id") or "")
        for x in ((data.get("source_coverage") or {}).get("source_requirement_occurrences") or [])
        if isinstance(x, dict) and x.get("occurrence_id")
    }
    errors = []
    checked = defaultdict(int)
    for gap in gaps:
        gid = str(gap.get("gap_id") or "(gap)")
        for cid in _list(gap.get("related_candidate_ids")):
            checked["gap_to_candidate"] += 1
            if str(cid) not in candidate_ids:
                errors.append({"type": "gap_to_candidate", "source_id": gid, "target_id": str(cid), "message": "Referenced Candidate ID does not exist."})
        for sid in _list(gap.get("related_srs_ids")):
            checked["gap_to_srs"] += 1
            if str(sid) not in srs_ids:
                errors.append({"type": "gap_to_srs", "source_id": gid, "target_id": str(sid), "message": "Referenced SRS ID does not exist."})
        for oid in _list(gap.get("related_source_occurrence_ids")):
            checked["gap_to_source_occurrence"] += 1
            if source_occ_ids and str(oid) not in source_occ_ids:
                errors.append({"type": "gap_to_source_occurrence", "source_id": gid, "target_id": str(oid), "message": "Referenced Source Occurrence ID does not exist."})
    for disp in [x for x in (data.get("missing_behavior_dispositions") or []) if isinstance(x, dict)]:
        did = str(disp.get("disposition_id") or "(missing-disposition)")
        for oid in _list(disp.get("source_occurrence_ids")):
            checked["missing_disposition_to_source_occurrence"] += 1
            if source_occ_ids and str(oid) not in source_occ_ids:
                errors.append({"type": "missing_disposition_to_source_occurrence", "source_id": did, "target_id": str(oid), "message": "Referenced Source Occurrence ID does not exist."})
    return {
        "passed": not errors,
        "error_count": len(errors),
        "errors": errors,
        "checked_reference_counts": {
            "gap_to_candidate": checked["gap_to_candidate"],
            "gap_to_srs": checked["gap_to_srs"],
            "gap_to_source_occurrence": checked["gap_to_source_occurrence"],
            "missing_disposition_to_source_occurrence": checked["missing_disposition_to_source_occurrence"],
            "issue_to_srs": 0,
            "srs_to_tc": 0,
            "source_occurrence_to_srs": sum(len(_list(x.get("linked_srs_ids"))) for x in ((data.get("source_coverage") or {}).get("source_requirement_occurrences") or []) if isinstance(x, dict)),
        },
        "scope_note": "Reference validity only. Completeness is reported separately.",
    }


def build_reference_completeness(data: dict[str, Any]) -> dict[str, Any]:
    gaps = [x for x in (data.get("gaps") or []) if isinstance(x, dict)]
    conflicts = [x for x in (data.get("conflict_register") or []) if isinstance(x, dict)]
    findings = [x for x in (data.get("review_findings") or []) if isinstance(x, dict)]
    missing_dispositions = [x for x in (data.get("missing_behavior_dispositions") or []) if isinstance(x, dict)]
    unlinked_gaps = []
    for gap in gaps:
        linked = any(_list(gap.get(k)) for k in ("related_candidate_ids", "related_srs_ids", "related_source_occurrence_ids", "related_source_requirement_ids"))
        document_link = isinstance(gap.get("document_context_link"), dict) and bool(gap.get("document_context_link"))
        if not linked and not document_link:
            unlinked_gaps.append(str(gap.get("gap_id") or "(gap)"))
    unlinked_conflicts = []
    for c in conflicts:
        if not any(_list(c.get(k)) for k in ("affected_candidate_ids", "affected_srs_ids", "affected_source_occurrence_ids")):
            unlinked_conflicts.append(str(c.get("conflict_id") or "(conflict)"))
    unlinked_findings = []
    for f in findings:
        if not any(_list(f.get(k)) for k in ("target_srs_ids", "target_source_occurrence_ids")):
            unlinked_findings.append(str(f.get("finding_id") or "(finding)"))
    unlinked_missing_dispositions = []
    for d in missing_dispositions:
        if not _list(d.get("source_occurrence_ids")):
            unlinked_missing_dispositions.append(str(d.get("disposition_id") or "(missing-disposition)"))
    missing_without = []
    for occ in ((data.get("source_coverage") or {}).get("source_requirement_occurrences") or []):
        if isinstance(occ, dict) and occ.get("occurrence_type") == "declaration" and occ.get("coverage_status") == "Missing" and not (_list(occ.get("linked_gap_issue_ids")) or _list(occ.get("linked_missing_disposition_ids"))):
            missing_without.append(str(occ.get("occurrence_id") or ""))
    coverage = data.get("source_coverage") if isinstance(data.get("source_coverage"), dict) else {}
    undispositioned = [str(x) for x in (coverage.get("undispositioned_occurrence_ids") or []) if str(x)]
    passed = not (unlinked_gaps or unlinked_conflicts or unlinked_findings or unlinked_missing_dispositions or missing_without or undispositioned)
    explicit_count = int(coverage.get("explicit_source_requirement_occurrence_count") or 0)
    actual_missing_count = len(missing_dispositions) if explicit_count else None
    actual_missing_status = "EVALUATED" if explicit_count else "NOT_EVALUATED"
    return {
        "passed": passed,
        "unlinked_gap_count": len(unlinked_gaps),
        "unlinked_gap_ids": unlinked_gaps,
        "unlinked_conflict_count": len(unlinked_conflicts),
        "unlinked_conflict_ids": unlinked_conflicts,
        "unlinked_open_issue_count": len(unlinked_findings),
        "unlinked_open_issue_ids": unlinked_findings,
        "unlinked_missing_disposition_count": len(unlinked_missing_dispositions),
        "unlinked_missing_disposition_ids": unlinked_missing_dispositions,
        "actual_missing_behavior_count": actual_missing_count,
        "actual_missing_behavior_evaluation_status": actual_missing_status,
        "actual_missing_behavior_release_blocking": bool(missing_dispositions) if explicit_count else False,
        "coverage_missing_without_disposition_count": len(missing_without),
        "coverage_missing_without_disposition_ids": missing_without,
        "coverage_undispositioned_count": len(undispositioned),
        "coverage_undispositioned_ids": undispositioned,
        "scope_note": "Reference completeness means each review object/source occurrence has an auditable disposition link. It may PASS while actual Missing behaviors remain release-blocking; coverage and missing-behavior counts are separate quality gates.",
    }


def _evidence_to_source(ev: Any) -> dict[str, str]:
    if isinstance(ev, dict):
        text = str(ev.get("text") or "")[:700]
        return {"location": str(ev.get("location") or ""), "text": text, "hash": _hash_text(text)}
    text = str(ev or "")[:700]
    return {"location": "", "text": text, "hash": _hash_text(text)}


def _detect_signal_value_conflicts(compact_text: str) -> list[dict[str, Any]]:
    """Detect source-confirmed value/meaning contradictions for the same signal.

    V0.55 supports both single-line declarations (``Signal On(0x1)``) and normalized
    table rows where the signal name and value labels may be split across multiple lines
    inside one source block. Block-level association is used only when exactly one signal
    is present, preventing cross-signal table contamination.
    """
    observations: dict[str, list[dict[str, str]]] = defaultdict(list)
    signal_display: dict[str, str] = {}
    seen_obs: set[tuple[str, str, str, str, str]] = set()

    def pairs_from(text: str) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for pattern in _LABEL_VALUE_PATTERNS:
            for m in pattern.finditer(text or ""):
                pair = (m.group("label").lower(), m.group("value").lower())
                if pair not in seen:
                    seen.add(pair); pairs.append(pair)
        return pairs

    def add(signal: str, label: str, value: str, location: str, text: str) -> None:
        key_sig = signal.lower()
        signal_display.setdefault(key_sig, signal)
        key = (key_sig, label, value, location, _normalize_space(text))
        if key in seen_obs:
            return
        seen_obs.add(key)
        observations[key_sig].append({"label": label, "value": value, "location": location, "text": _normalize_space(text)[:700]})

    for block in _iter_source_blocks(compact_text):
        block_lines = [raw.strip() for raw in block["text"].splitlines() if raw.strip()]
        block_signals: list[str] = []
        block_pair_rows: list[tuple[str, list[tuple[str, str]]]] = []
        for line in block_lines:
            signals = _SIGNAL_PATTERN.findall(line)
            for sig in signals:
                if sig.lower() not in {x.lower() for x in block_signals}:
                    block_signals.append(sig)
            pairs = pairs_from(line)
            if pairs:
                block_pair_rows.append((line, pairs))
            if signals and pairs:
                for sig in signals:
                    for label, value in pairs:
                        add(sig, label, value, block["location"], line)

        # Normalized table fallback: a row/chunk can split signal name and mapping over lines.
        if len(block_signals) == 1 and block_pair_rows:
            sig = block_signals[0]
            for line, pairs in block_pair_rows:
                for label, value in pairs:
                    add(sig, label, value, block["location"], line if _SIGNAL_PATTERN.search(line) else f"{sig} | {line}")

    conflicts: list[dict[str, Any]] = []
    conflict_seen: set[tuple[Any, ...]] = set()
    for key_sig, rows in observations.items():
        found_for_signal = False
        for i in range(len(rows)):
            if found_for_signal:
                break
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                contradictory = (a["label"] == b["label"] and a["value"] != b["value"]) or (a["value"] == b["value"] and a["label"] != b["label"])
                if not contradictory:
                    continue
                key = (key_sig, a["label"], a["value"], b["label"], b["value"], a["location"], b["location"])
                reverse_key = (key_sig, b["label"], b["value"], a["label"], a["value"], b["location"], a["location"])
                if key in conflict_seen or reverse_key in conflict_seen:
                    continue
                conflict_seen.add(key)
                conflicts.append({
                    "signal": signal_display.get(key_sig, key_sig),
                    "source_a": {"location": a["location"], "text": a["text"], "hash": _hash_text(a["text"])},
                    "source_b": {"location": b["location"], "text": b["text"], "hash": _hash_text(b["text"])},
                    "must_not_assume": f"Authoritative value/meaning for {signal_display.get(key_sig, key_sig)}",
                    "key": key,
                })
                found_for_signal = True
                break
    return conflicts


def _detect_parameter_direction_conflicts(compact_text: str) -> list[dict[str, Any]]:
    """Detect opposite direction definitions for the same parameter (e.g. On->Off vs Off->On)."""
    by_param: dict[str, list[dict[str, str]]] = defaultdict(list)
    for block in _iter_source_blocks(compact_text):
        for raw in (block.get("text") or "").splitlines():
            line = _normalize_space(raw)
            if not line:
                continue
            params = [x for x in _SIGNAL_PATTERN.findall(line) if x.lower().startswith(("par_", "param_"))]
            dm = re.search(r"\b(On|Off)\s*(?:->|→|[-=]+>)\s*(On|Off)\b", line, flags=re.IGNORECASE)
            if not params or not dm:
                continue
            direction = f"{dm.group(1).lower()}->{dm.group(2).lower()}"
            for param in params:
                by_param[param.lower()].append({
                    "parameter": param, "direction": direction,
                    "location": str(block.get("location") or ""), "text": line[:700], "hash": _hash_text(line),
                })
    out = []
    for key, rows in by_param.items():
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                if a["direction"] == b["direction"]:
                    continue
                if {a["direction"], b["direction"]} != {"on->off", "off->on"}:
                    continue
                out.append({
                    "parameter": a["parameter"],
                    "source_a": {k: a[k] for k in ("location", "text", "hash")},
                    "source_b": {k: b[k] for k in ("location", "text", "hash")},
                    "must_not_assume": f"Authoritative transition direction for {a['parameter']}",
                })
                break
            else:
                continue
            break
    return out


def _conflict_identity(item: dict[str, Any]) -> tuple[str, str, str]:
    classification = str(item.get("classification") or "").strip().lower()
    a = item.get("source_a") if isinstance(item.get("source_a"), dict) else {}
    b = item.get("source_b") if isinstance(item.get("source_b"), dict) else {}
    ha = str(a.get("hash") or _hash_text(str(a.get("location") or "") + "|" + str(a.get("text") or "")))
    hb = str(b.get("hash") or _hash_text(str(b.get("location") or "") + "|" + str(b.get("text") or "")))
    pair = sorted([ha, hb])
    return classification, pair[0], pair[1]


def _dedupe_conflict_register(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        key = _conflict_identity(item)
        # Empty/incomplete evidence should not collapse unrelated issues solely by blank hashes.
        if key[1] and key[2] and key in seen:
            continue
        seen.add(key)
        copied = item
        copied["conflict_id"] = f"CONFLICT_{len(out)+1:03d}"
        out.append(copied)
    return out


def _split_naming_issues(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    conflicts, naming = [], []
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("classification") or "").lower() == "naming inconsistency":
            cp = dict(item)
            cp["issue_id"] = f"NAME-ISSUE-{len(naming)+1:03d}"
            cp.pop("conflict_id", None)
            cp["classification"] = "Naming Inconsistency / Possible Typographical Error"
            naming.append(cp)
        else:
            conflicts.append(item)
    for idx, item in enumerate(conflicts, start=1):
        item["conflict_id"] = f"CONFLICT_{idx:03d}"
    return conflicts, naming


def _source_lines_matching_terms(compact_text: str, terms: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    lowered_terms = [str(x).lower() for x in terms if str(x).strip()]
    if not lowered_terms:
        return rows
    for block in _iter_source_blocks(compact_text):
        for raw_line in (block.get("text") or "").splitlines():
            line = _normalize_space(raw_line)
            low = line.lower()
            if line and any(term in low for term in lowered_terms):
                rows.append({"location": str(block.get("location") or ""), "text": line[:700], "hash": _hash_text(line)})
    return rows


def _conflict_pair_is_direct(source_a: dict[str, Any], source_b: dict[str, Any], description: str = "") -> bool:
    """Return True only when the two evidence rows directly support the same stated conflict topic."""
    if not source_a or not source_b:
        return False
    ta = _normalize_space(source_a.get("text")); tb = _normalize_space(source_b.get("text"))
    if not ta or not tb or ta == tb:
        return False
    sig_a = {x.lower() for x in _SIGNAL_PATTERN.findall(ta)}
    sig_b = {x.lower() for x in _SIGNAL_PATTERN.findall(tb)}
    desc_sigs = {x.lower() for x in _SIGNAL_PATTERN.findall(description or "")}
    shared = sig_a & sig_b
    if desc_sigs and not ((sig_a | sig_b) & desc_sigs):
        return False
    # Signal value/meaning conflicts must share a signal and expose contradictory value/label pairs.
    if shared:
        pairs_a = {(m.group("label").lower(), m.group("value").lower()) for pat in _LABEL_VALUE_PATTERNS for m in pat.finditer(ta)}
        pairs_b = {(m.group("label").lower(), m.group("value").lower()) for pat in _LABEL_VALUE_PATTERNS for m in pat.finditer(tb)}
        for la, va in pairs_a:
            for lb, vb in pairs_b:
                if (la == lb and va != vb) or (va == vb and la != lb):
                    return True
    # Naming inconsistencies can use two different but closely related signal names when the description names both.
    if len(desc_sigs) >= 2 and sig_a and sig_b and sig_a != sig_b:
        return True
    return False


def _gap_conflict_candidate(gap: dict[str, Any], compact_text: str) -> dict[str, Any] | None:
    """Convert conflict-like Gap into evidence only when the Source evidence actually supports it."""
    hay = " ".join(_text(gap.get(k)) for k in ("description", "gap", "reason", "detail", "affected_requirements", "clarification_needed"))
    if not re.search(r"상충|충돌|불일치|표기\s*상이|모순|conflict|mismatch", hay, flags=re.IGNORECASE):
        return None
    signals = list(dict.fromkeys(_SIGNAL_PATTERN.findall(hay)))
    values = list(dict.fromkeys(re.findall(r"\b0x[0-9A-Fa-f]+\b", hay)))

    # Prefer deterministic direct signal/value contradictions found in the Source.
    for detected in _detect_signal_value_conflicts(compact_text):
        if signals and detected.get("signal", "").lower() not in {x.lower() for x in signals}:
            continue
        source_a = detected.get("source_a") or {}; source_b = detected.get("source_b") or {}
        if _conflict_pair_is_direct(source_a, source_b, hay):
            return {
                "classification": "Possible Conflict",
                "title": str(gap.get("title") or gap.get("description") or gap.get("gap") or "Source conflict").strip()[:180],
                "description": _normalize_space(hay)[:900],
                "source_a": source_a,
                "source_b": source_b,
                "must_not_assume": detected.get("must_not_assume") or "Authoritative value/meaning until reviewed.",
                "review_state": "Uncertain",
                "evidence_status": "Complete",
            }

    # Naming conflict: collect explicit evidence for each named signal, but mark Complete only if the pair supports the claim.
    source_a: dict[str, str] = {}; source_b: dict[str, str] = {}
    if len(signals) >= 2:
        a_rows = _source_lines_matching_terms(compact_text, [signals[0]])
        b_rows = _source_lines_matching_terms(compact_text, [signals[1]])
        source_a = a_rows[0] if a_rows else {}
        source_b = b_rows[0] if b_rows else {}
    else:
        rows = _source_lines_matching_terms(compact_text, signals + values)
        source_a = rows[0] if rows else {}
        source_b = rows[1] if len(rows) > 1 else {}
    complete = _conflict_pair_is_direct(source_a, source_b, hay)
    classification = "Naming Inconsistency" if len(signals) >= 2 else "Possible Conflict"
    return {
        "classification": classification,
        "title": str(gap.get("title") or gap.get("description") or gap.get("gap") or "Conflict-like Gap").strip()[:180],
        "description": _normalize_space(hay)[:900],
        "source_a": source_a if complete else (source_a or {}),
        "source_b": source_b if complete else (source_b or {}),
        "must_not_assume": "Authoritative resolution/value until directly supporting Source evidence is reviewed.",
        "review_state": "Uncertain",
        "evidence_status": "Complete" if complete else "Incomplete Conflict Evidence",
    }


def build_conflict_register(data: dict[str, Any], compact_text: str = "") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    coverage = (data.get("source_coverage") or {}).get("source_requirement_occurrences") or []

    for req in [x for x in (data.get("requirements") or []) if isinstance(x, dict)]:
        evidence = _list(req.get("source_evidence"))
        for raw in _list(req.get("conflicts")):
            if isinstance(raw, dict):
                title = str(raw.get("title") or raw.get("topic") or raw.get("description") or "Source conflict").strip()
                description = str(raw.get("description") or raw.get("detail") or "").strip()
                ctype = str(raw.get("classification") or raw.get("type") or "Possible Conflict").strip()
                source_a = raw.get("source_a") if isinstance(raw.get("source_a"), dict) else {}
                source_b = raw.get("source_b") if isinstance(raw.get("source_b"), dict) else {}
                if not _conflict_pair_is_direct(source_a, source_b, title + " " + description):
                    # Do not label unrelated Requirement evidence as a complete conflict pair.
                    source_a = source_a or {}
                    source_b = source_b or {}
                must_not_assume = str(raw.get("must_not_assume") or "").strip()
                resolution = str(raw.get("resolution_required_from") or "").strip()
            else:
                title = str(raw).strip() or "Source conflict"
                description = str(raw).strip()
                ctype = "Possible Conflict"
                source_a = {}
                source_b = {}
                must_not_assume = ""
                resolution = ""
            key = (title + "|" + description + "|" + str(req.get("srs_id") or "")).lower()
            if key in seen:
                continue
            seen.add(key)
            source_ids = {str(x).upper() for x in _list(req.get("source_requirement_ids"))}
            affected_occ = [str(o.get("occurrence_id")) for o in coverage if isinstance(o, dict) and str(o.get("source_req_id") or "").upper() in source_ids]
            out.append({
                "conflict_id": f"CONFLICT_{len(out)+1:03d}",
                "classification": ctype if ctype in {"Confirmed Conflict", "Possible Conflict", "Naming Inconsistency", "Missing Priority", "Clarification Needed"} else "Possible Conflict",
                "title": title,
                "description": description,
                "source_a": source_a,
                "source_b": source_b,
                "affected_candidate_ids": [str(req.get("candidate_id") or "")] if req.get("candidate_id") else [],
                "affected_srs_ids": [str(req.get("srs_id") or "")] if req.get("srs_id") else [],
                "affected_source_occurrence_ids": affected_occ,
                "status": "Open",
                "resolution_required_from": resolution,
                "must_not_assume": must_not_assume,
                "review_state": "Confirmed" if ctype == "Confirmed Conflict" and _conflict_pair_is_direct(source_a, source_b, title + " " + description) else "Uncertain",
                "evidence_status": "Complete" if _conflict_pair_is_direct(source_a, source_b, title + " " + description) else "Incomplete Conflict Evidence",
            })

    # Deterministic source-level signal mapping conflicts. Generic, not MLM-specific.
    for detected in _detect_signal_value_conflicts(compact_text):
        key = json.dumps(detected["key"], ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        signal = detected["signal"]
        affected = []
        affected_candidates = []
        for req in [x for x in (data.get("requirements") or []) if isinstance(x, dict)]:
            hay = " ".join(_text(req.get(k)) for k in ("requirement", "processing_action", "preconditions", "system_input_preconditions", "source_evidence"))
            if signal.lower() in hay.lower():
                if req.get("srs_id"):
                    affected.append(str(req.get("srs_id")))
                if req.get("candidate_id"):
                    affected_candidates.append(str(req.get("candidate_id")))
        affected_occ = [
            str(o.get("occurrence_id") or "") for o in coverage if isinstance(o, dict)
            and (
                _source_location_overlap(str(o.get("source_location") or ""), str(detected["source_a"].get("location") or ""))
                or _source_location_overlap(str(o.get("source_location") or ""), str(detected["source_b"].get("location") or ""))
            )
        ]
        out.append({
            "conflict_id": f"CONFLICT_{len(out)+1:03d}",
            "classification": "Value-Encoding Contradiction",
            "title": f"Signal value/meaning contradiction: {signal}",
            "description": "The same source signal is associated with contradictory On/Off value mappings in different source locations. No authoritative value is inferred.",
            "source_a": detected["source_a"],
            "source_b": detected["source_b"],
            "affected_candidate_ids": list(dict.fromkeys(affected_candidates)),
            "affected_srs_ids": list(dict.fromkeys(affected)),
            "affected_source_occurrence_ids": [x for x in affected_occ if x],
            "linked_gap_ids": [],
            "status": "Open",
            "resolution_required_from": "",
            "resolution_note": "Authoritative definition/owner must be identified from project evidence; owner is not inferred.",
            "must_not_assume": detected["must_not_assume"],
            "review_state": "Clarification Needed",
            "evidence_status": "Complete" if detected.get("source_a") and detected.get("source_b") else "Incomplete Conflict Evidence",
        })

    # Deterministic parameter-direction contradictions (e.g. On->Off vs Off->On).
    for detected in _detect_parameter_direction_conflicts(compact_text):
        param = str(detected.get("parameter") or "")
        affected_candidates = []
        affected_srs = []
        for req in [x for x in (data.get("requirements") or []) if isinstance(x, dict)]:
            hay = _requirement_behavior_text(req) + " " + _text(req.get("source_evidence"))
            if param and param.lower() in hay.lower():
                if req.get("candidate_id"):
                    affected_candidates.append(str(req.get("candidate_id")))
                if req.get("srs_id"):
                    affected_srs.append(str(req.get("srs_id")))
        affected_occ = [
            str(o.get("occurrence_id") or "") for o in coverage if isinstance(o, dict)
            and param and param.lower() in _text(o.get("source_excerpt")).lower()
        ]
        out.append({
            "conflict_id": f"CONFLICT_{len(out)+1:03d}",
            "classification": "Direction / Definition Contradiction",
            "title": f"Parameter direction contradiction: {param}",
            "description": "The same parameter is defined with opposite state-transition directions in different Source locations. No authoritative direction is inferred.",
            "source_a": detected.get("source_a") or {},
            "source_b": detected.get("source_b") or {},
            "affected_candidate_ids": list(dict.fromkeys(affected_candidates)),
            "affected_srs_ids": list(dict.fromkeys(affected_srs)),
            "affected_source_occurrence_ids": list(dict.fromkeys(x for x in affected_occ if x)),
            "linked_gap_ids": [],
            "status": "Open",
            "resolution_required_from": "",
            "resolution_note": "Authoritative transition direction must be confirmed from project evidence; the tool does not choose one.",
            "must_not_assume": detected.get("must_not_assume") or f"Authoritative transition direction for {param}",
            "review_state": "Clarification Needed",
            "evidence_status": "Complete",
        })

    # Synchronize conflict-like Gap records with the Conflict Register. The Gap remains the
    # resolution/dependency record; the Conflict Register holds the contradictory Source evidence.
    for gap in [x for x in (data.get("gaps") or []) if isinstance(x, dict)]:
        candidate = _gap_conflict_candidate(gap, compact_text)
        if not candidate:
            continue
        gid = str(gap.get("gap_id") or "").strip()
        gap.setdefault("linked_conflict_ids", [])
        # Avoid a duplicate if an existing deterministic/source conflict already covers the same SRS/terms.
        sig_terms = {x.lower() for x in _SIGNAL_PATTERN.findall(candidate.get("description") or "")}
        duplicate = None
        for existing in out:
            existing_terms = {x.lower() for x in _SIGNAL_PATTERN.findall(_text(existing.get("description")) + " " + _text(existing.get("title")))}
            if sig_terms and sig_terms & existing_terms:
                duplicate = existing
                break
        if duplicate is not None:
            if gid and gid not in duplicate.setdefault("linked_gap_ids", []):
                duplicate["linked_gap_ids"].append(gid)
            cid = str(duplicate.get("conflict_id") or "")
            if cid and cid not in gap["linked_conflict_ids"]:
                gap["linked_conflict_ids"].append(cid)
            continue
        conflict = {
            "conflict_id": f"CONFLICT_{len(out)+1:03d}",
            **candidate,
            "affected_candidate_ids": list(dict.fromkeys(str(x) for x in _list(gap.get("related_candidate_ids")) if str(x))),
            "affected_srs_ids": list(dict.fromkeys(str(x) for x in _list(gap.get("related_srs_ids")) if str(x))),
            "affected_source_occurrence_ids": list(dict.fromkeys(str(x) for x in _list(gap.get("related_source_occurrence_ids")) if str(x))),
            "linked_gap_ids": [gid] if gid else [],
            "status": "Open",
            "resolution_required_from": "",
        }
        out.append(conflict)
        if conflict["conflict_id"] not in gap["linked_conflict_ids"]:
            gap["linked_conflict_ids"].append(conflict["conflict_id"])
    return out


def build_export_preservation_audit(data: dict[str, Any]) -> dict[str, Any]:
    requirements = [x for x in (data.get("requirements") or []) if isinstance(x, dict)]
    mappings = {
        "applicability": "03_Applicability",
        "exception_conditions": "04_Open_Issues_Gaps",
        "clarification_needed": "04_Open_Issues_Gaps",
        "external_dependencies": "04_Open_Issues_Gaps",
        "tbd_items": "04_Open_Issues_Gaps",
        "conflicts": "04_Open_Issues_Gaps",
        "source_evidence": "06_Requirement_Review_Details",
        "source_requirement_ids": "06_Requirement_Review_Details",
        "source_requirement_occurrence_ids": "06_Requirement_Review_Details",
        "source_backed_atomic_behaviors": "SWE.1 Word main behavior / Review Annex",
        "requirement_status": "06_Requirement_Review_Details",
        "verification_constraints": "06_Requirement_Review_Details",
    }
    rows = []
    losses = []
    for field, destination in mappings.items():
        nonempty = sum(1 for req in requirements if req.get(field) not in (None, "", [], {}))
        rows.append({"field": field, "nonempty_requirement_count": nonempty, "destination": destination, "status": "Mapped to Review View"})
    return {
        "passed": not losses,
        "information_loss_count": len(losses),
        "losses": losses,
        "field_disposition": rows,
        "scope_note": "Canonical-to-export preservation only; this metric does not measure Source-to-Canonical coverage.",
        "rule": "Every review-relevant Canonical field must be visible in Final View, Review View, or explicitly Internal-only.",
    }


def _extract_fact_tokens(text: str) -> list[str]:
    out = []
    seen = set()
    for pattern in _FACT_TOKEN_PATTERNS:
        for match in pattern.finditer(text or ""):
            token = re.sub(r"\s+", " ", match.group(0)).strip()
            key = token.lower()
            if key not in seen:
                seen.add(key)
                out.append(token)
    return out


def _normalize_fact_token(value: str) -> str:
    text = _normalize_space(value).lower()
    # Normalize common number+unit spacing so "3 s" == "3s" and "600 ms" == "600ms".
    text = re.sub(r"(?<=\d)\s+(?=(?:ms|msec|s|sec|초|v|mv|a|ma|%|℃|°c|bps|kbps|step)\b)", "", text, flags=re.IGNORECASE)
    return text


def build_unsupported_generation_report(data: dict[str, Any], compact_text: str) -> dict[str, Any]:
    source_norm = _normalize_fact_token(compact_text or "")
    findings = []
    supported = 0
    uncertain = 0
    reviewed = 0
    for req in [x for x in (data.get("requirements") or []) if isinstance(x, dict)]:
        fields = (
            "requirement", "activation_trigger", "preconditions", "processing_action", "output",
            "acceptance_criteria", "exception_conditions", "external_dependencies", "tbd_items",
            "verification_constraints", "applicability"
        )
        combined = "\n".join(_text(req.get(k)) for k in fields)
        for token in _extract_fact_tokens(combined):
            reviewed += 1
            normalized_token = _normalize_fact_token(token)
            if normalized_token and normalized_token in source_norm:
                supported += 1
            else:
                uncertain += 1
                findings.append({
                    "finding_id": f"UGC_{len(findings)+1:03d}",
                    "severity": "Review",
                    "generated_assertion": token,
                    "source_comparison": "Exact factual token not found by deterministic source-token check.",
                    "classification": "Uncertain",
                    "affected_srs_ids": [str(req.get("srs_id") or "")] if req.get("srs_id") else [],
                })
    return {
        "reviewed_assertion_count": reviewed,
        "supported_assertion_count": supported,
        "safe_derived_assertion_count": 0,
        "unsupported_assertion_count": 0,
        "uncertain_assertion_count": uncertain,
        "unsupported_generation_rate_percent": 0.0,
        "findings": findings,
        "review_scope_note": "Automatic factual-token precheck across Requirement, applicability, dependency and verification fields, including normalized number/unit matching against text and table artifacts. Zero detected unsupported assertions is not a guarantee of zero hallucination. Uncertain items require semantic review.",
    }


def _intent_list(req: dict[str, Any]) -> list[str]:
    text = " ".join(_text(req.get(k)) for k in (
        "requirement", "activation_trigger", "preconditions", "processing_action", "output", "acceptance_criteria", "failure_situations", "exception_conditions"
    )).lower()
    intents = ["Normal / Positive"]
    if re.search(r"\b(?:invalid|reserved)\b|무효|예약|유효하지", text):
        intents.append("Invalid / Reserved")
    if re.search(r"\d+(?:\.\d+)?\s*(?:ms|msec|s|sec|초)\b|timer|timing|시간", text):
        intents.append("Timing")
    if any(x in text for x in ("state", "상태 전이", "상태전이", "변경될 때", "진입", "복귀", "wake", "sleep")):
        intents.append("State Transition")
    if _list(req.get("exception_conditions")) or any(x in text for x in ("fail", "고장", "예외")):
        intents.append("Exception / Fail-safe")
    app = req.get("applicability") if isinstance(req.get("applicability"), dict) else {}
    if any(_list(app.get(k)) for k in ("vehicle_lines", "baseline_versions", "feature_variants", "enable_conditions", "exclusion_conditions")):
        intents.append("Variant Applicability")
    return list(dict.fromkeys(intents))


def build_testability_result(data: dict[str, Any]) -> dict[str, Any]:
    rows = []
    counts = defaultdict(int)
    conflict_srs = {sid for c in (data.get("conflict_register") or []) if isinstance(c, dict) for sid in _list(c.get("affected_srs_ids"))}
    for req in [x for x in (data.get("requirements") or []) if isinstance(x, dict)]:
        srs = str(req.get("srs_id") or "")
        clar = _list(req.get("clarification_needed"))
        deps = _list(req.get("external_dependencies"))
        tbd = _list(req.get("tbd_items"))
        constraints = _list(req.get("verification_constraints"))
        category = str(req.get("category") or "")
        swe6_eligibility = str(req.get("swe6_eligibility") or "Eligible")
        verification_domain = str(req.get("verification_domain") or "SWE.6 Software Qualification")
        normal_test_available = bool(
            str(req.get("requirement") or "").strip()
            and any(str(req.get(k) or "").strip() for k in ("activation_trigger", "preconditions", "system_input_preconditions", "processing_action", "output", "acceptance_criteria"))
            and category != "비대상"
            and swe6_eligibility == "Eligible"
        )
        if swe6_eligibility == "Not Applicable" or category == "비대상":
            status = "Not Applicable"
            reason = f"Verification is allocated outside SWE.6 ({verification_domain})."
        elif swe6_eligibility.startswith("Deferred"):
            status = "Review Needed"
            reason = f"SWE.6 generation is deferred until software allocation is confirmed ({verification_domain})."
        elif srs in conflict_srs:
            status = "Partially Testable" if normal_test_available else "Review Needed"
            reason = "A normal/source-backed check may be possible, but an open source conflict blocks complete verification intent."
        elif tbd or deps or clar:
            status = "Partially Testable" if normal_test_available else "Review Needed"
            reason = "A normal/source-backed check may be possible, but TBD/Dependency/Clarification blocks one or more concrete intents; missing values are not invented."
        else:
            status = "Testable" if normal_test_available else "Review Needed"
            reason = "Source-backed normal verification is available." if normal_test_available else "No sufficiently concrete trigger/action/output/acceptance information was found for a normal test."
        counts[status] += 1
        intents = _intent_list(req) if swe6_eligibility == "Eligible" else []
        test_design_feasible = bool(normal_test_available and not (srs in conflict_srs or tbd or deps or clar))
        rows.append({
            "srs_id": srs,
            "testability_status": status,
            "testability_reason": reason,
            "normal_test_available": normal_test_available,
            "test_design_feasible": test_design_feasible,
            "concrete_tc_complete": False,
            # Deprecated compatibility alias. V0.55 defines this as concrete-TC completeness,
            # not merely source-level design feasibility. It is finalized after TC generation.
            "full_testability_available": False,
            "intent_complete_status": "Not Evaluated",
            "required_test_intents": intents,
            "covered_test_intents": [],
            "verification_constraints": constraints,
            "swe6_eligibility": swe6_eligibility,
            "verification_domain": verification_domain,
            "generated_tc_ids": [],
            "not_generated_test_intents": [],
            "required_intent_count": len(intents),
            "covered_intent_count": 0,
            "deferred_intent_count": len(intents),
            "intent_coverage_percent": 0.0,
        })
    return {
        "summary": {
            "testable_srs_count": counts["Testable"],
            "partially_testable_srs_count": counts["Partially Testable"],
            "normal_test_available_srs_count": sum(1 for x in rows if x.get("normal_test_available")),
            "test_design_feasible_srs_count": sum(1 for x in rows if x.get("test_design_feasible")),
            "concrete_tc_complete_srs_count": 0,
            "review_needed_srs_count": counts["Review Needed"],
            "blocked_srs_count": counts["Blocked"],
            "not_applicable_srs_count": counts["Not Applicable"],
            "total_generated_tc_count": 0,
            "required_intent_count": sum(x["required_intent_count"] for x in rows),
            "covered_intent_count": 0,
            "deferred_intent_count": sum(x["required_intent_count"] for x in rows),
            "intent_coverage_percent": 0.0,
        },
        "by_srs": rows,
        "scope_note": "Test Intent is a review plan. Concrete test values are not generated when source facts are missing or conflicted.",
    }


def finalize_test_intent_coverage(data: dict[str, Any], tc_cases: list[dict[str, Any]]) -> dict[str, Any]:
    result = data.get("testability_and_decomposition_result")
    if not isinstance(result, dict):
        return {}
    tc_by_srs: dict[str, list[str]] = defaultdict(list)
    for case in tc_cases or []:
        sid = str(case.get("srs_id") or "")
        tid = str(case.get("tc_id") or "")
        if sid and tid:
            tc_by_srs[sid].append(tid)
    total_required = total_covered = total_deferred = 0
    for row in result.get("by_srs") or []:
        if not isinstance(row, dict):
            continue
        srs = str(row.get("srs_id") or "")
        tc_ids = tc_by_srs.get(srs, [])
        row["generated_tc_ids"] = tc_ids
        if str(row.get("swe6_eligibility") or "Eligible") != "Eligible":
            row["normal_test_generated"] = False
            row["covered_test_intents"] = []
            row["not_generated_test_intents"] = []
            row["required_intent_count"] = 0
            row["covered_intent_count"] = 0
            row["deferred_intent_count"] = 0
            row["intent_coverage_percent"] = None
            row["intent_complete_status"] = "Not Applicable" if str(row.get("swe6_eligibility")) == "Not Applicable" else "Deferred pending SW allocation"
            row["concrete_tc_complete"] = False
            row["full_testability_available"] = False
            continue
        required = _list(row.get("required_test_intents"))
        covered = []
        if tc_ids and "Normal / Positive" in required:
            covered.append("Normal / Positive")
        deferred = []
        for intent in required:
            if intent not in covered:
                reason = "No dedicated concrete TC generated by the current exporter."
                if row.get("testability_status") in {"Review Needed", "Blocked"}:
                    reason = "Concrete TC deferred because source values/conflicts/dependencies require review."
                deferred.append({"intent": intent, "reason": reason})
        row["covered_test_intents"] = covered
        row["not_generated_test_intents"] = deferred
        row["required_intent_count"] = len(required)
        row["covered_intent_count"] = len(covered)
        row["deferred_intent_count"] = len(deferred)
        row["intent_coverage_percent"] = round((len(covered) / len(required) * 100.0), 2) if required else 100.0
        # Preserve source-level basic testability. Whether the current exporter actually emitted
        # a Normal TC is a separate implementation/output fact.
        row["normal_test_generated"] = bool(tc_ids and ("Normal / Positive" in covered or not required))
        row["intent_complete_status"] = (
            "Complete" if not deferred else ("Partial" if covered else "Deferred")
        )
        row["concrete_tc_complete"] = bool(not deferred)
        # V0.56 invariant: if all required intents already have concrete TC coverage, test design
        # is necessarily feasible. Keep the compatibility alias logically monotonic.
        if row["concrete_tc_complete"]:
            row["test_design_feasible"] = True
            row["intent_complete_status"] = "Complete"
        row["full_testability_available"] = bool(row["concrete_tc_complete"] and row.get("test_design_feasible"))
        total_required += len(required)
        total_covered += len(covered)
        total_deferred += len(deferred)
    summary = result.setdefault("summary", {})
    summary["total_generated_tc_count"] = len(tc_cases or [])
    summary["required_intent_count"] = total_required
    summary["covered_intent_count"] = total_covered
    summary["deferred_intent_count"] = total_deferred
    summary["intent_coverage_percent"] = round((total_covered / total_required * 100.0), 2) if total_required else 100.0
    complete_srs = sum(1 for row in result.get("by_srs") or [] if isinstance(row, dict) and row.get("intent_complete_status") == "Complete")
    partial_srs = sum(1 for row in result.get("by_srs") or [] if isinstance(row, dict) and row.get("intent_complete_status") == "Partial")
    deferred_srs = sum(1 for row in result.get("by_srs") or [] if isinstance(row, dict) and row.get("intent_complete_status") == "Deferred")
    normal_available = sum(1 for row in result.get("by_srs") or [] if isinstance(row, dict) and row.get("normal_test_available"))
    normal_generated = sum(1 for row in result.get("by_srs") or [] if isinstance(row, dict) and row.get("normal_test_generated"))
    summary["normal_test_available_srs_count"] = normal_available
    summary["normal_test_generated_srs_count"] = normal_generated
    summary["test_design_feasible_srs_count"] = sum(1 for row in result.get("by_srs") or [] if isinstance(row, dict) and row.get("test_design_feasible"))
    summary["concrete_tc_complete_srs_count"] = sum(1 for row in result.get("by_srs") or [] if isinstance(row, dict) and row.get("concrete_tc_complete"))
    data["test_intent_coverage"] = {
        "required_intent_count": total_required,
        "covered_intent_count": total_covered,
        "deferred_intent_count": total_deferred,
        "intent_coverage_percent": summary["intent_coverage_percent"],
        "normal_test_available_srs_count": normal_available,
        "normal_test_generated_srs_count": normal_generated,
        "intent_complete_srs_count": complete_srs,
        "intent_partial_srs_count": partial_srs,
        "intent_deferred_srs_count": deferred_srs,
        "scope_note": "V0.58 enforces allocation-aware monotonic semantics across normal_test_available, test_design_feasible, concrete_tc_complete, and intent_complete_status. full_testability_available is retained only as a compatibility alias for concrete_tc_complete. A generic TC counts only against Normal / Positive intent.",
    }
    return data["test_intent_coverage"]


def _enrich_gap_links_from_exact_evidence(data: dict[str, Any]) -> None:
    """Conservatively link Gap records using exact Source IDs, stable locations, signals/parameters, and dependency names."""
    reqs = [x for x in (data.get("requirements") or []) if isinstance(x, dict)]
    occs = [x for x in ((data.get("source_coverage") or {}).get("source_requirement_occurrences") or []) if isinstance(x, dict)]
    srs_by_candidate = {str(r.get("candidate_id") or ""): str(r.get("srs_id") or "") for r in reqs if r.get("candidate_id")}
    req_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    occ_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for req in reqs:
        for sid in _list(req.get("source_requirement_ids")):
            req_by_source[str(sid).strip().upper()].append(req)
    for occ in occs:
        sid = str(occ.get("source_req_id") or "").strip().upper()
        if sid:
            occ_by_source[sid].append(occ)

    def req_exact_tokens(req: dict[str, Any]) -> set[str]:
        hay = " ".join(_text(req.get(k)) for k in (
            "requirement", "processing_action", "output", "clarification_needed",
            "source_evidence", "related_artifacts", "external_dependencies"
        ))
        tokens = {x.lower() for x in _SIGNAL_PATTERN.findall(hay)}
        tokens.update(x.lower() for x in re.findall(r"\b(?:CAN|LIN)\s*DB\b|\bSystem\s*Spec\b|시스템\s*사양", hay, flags=re.IGNORECASE))
        return tokens

    req_tokens = {str(r.get("candidate_id") or id(r)): req_exact_tokens(r) for r in reqs}

    for gap in [x for x in (data.get("gaps") or []) if isinstance(x, dict)]:
        gap.setdefault("related_candidate_ids", [])
        gap.setdefault("related_srs_ids", [])
        gap.setdefault("related_source_occurrence_ids", [])
        gap.setdefault("related_source_requirement_ids", [])
        gap.setdefault("linked_conflict_ids", [])
        hay = " ".join(_text(gap.get(k)) for k in ("description", "gap", "reason", "detail", "affected_requirements", "related_source_requirement_ids", "source_evidence"))
        source_ids = list(dict.fromkeys([str(x).strip() for x in _list(gap.get("related_source_requirement_ids")) if str(x).strip()] + _explicit_ids(hay)))
        for sid in source_ids:
            if sid not in gap["related_source_requirement_ids"]:
                gap["related_source_requirement_ids"].append(sid)
            for req in req_by_source.get(sid.upper(), []):
                cid = str(req.get("candidate_id") or "")
                srs = str(req.get("srs_id") or "")
                if cid and cid not in gap["related_candidate_ids"]:
                    gap["related_candidate_ids"].append(cid)
                if srs and srs not in gap["related_srs_ids"]:
                    gap["related_srs_ids"].append(srs)
            for occ in occ_by_source.get(sid.upper(), []):
                oid = str(occ.get("occurrence_id") or "")
                if oid and oid not in gap["related_source_occurrence_ids"]:
                    gap["related_source_occurrence_ids"].append(oid)

        # Exact signal/parameter/dependency tokens may safely connect a document-level Gap to affected requirements.
        gap_tokens = {x.lower() for x in _SIGNAL_PATTERN.findall(hay)}
        gap_tokens.update(x.lower() for x in re.findall(r"\b(?:CAN|LIN)\s*DB\b|\bSystem\s*Spec\b|시스템\s*사양", hay, flags=re.IGNORECASE))
        if gap_tokens:
            for req in reqs:
                cid = str(req.get("candidate_id") or "")
                if not cid or not (gap_tokens & req_tokens.get(cid, set())):
                    continue
                srs = str(req.get("srs_id") or "")
                if cid not in gap["related_candidate_ids"]:
                    gap["related_candidate_ids"].append(cid)
                if srs and srs not in gap["related_srs_ids"]:
                    gap["related_srs_ids"].append(srs)
                for oid in _list(req.get("source_requirement_occurrence_ids")):
                    if str(oid) and str(oid) not in gap["related_source_occurrence_ids"]:
                        gap["related_source_occurrence_ids"].append(str(oid))

        # Gap Source evidence locations can connect to Requirements by stable paragraph/table overlap.
        gap_locations = []
        for ev in _list(gap.get("source_evidence")):
            if isinstance(ev, dict) and str(ev.get("location") or "").strip():
                gap_locations.append(str(ev.get("location")))
        if gap_locations:
            for req in reqs:
                if any(_source_location_overlap(gloc, rev.get("location") or "") for gloc in gap_locations for rev in _req_evidence(req)):
                    cid = str(req.get("candidate_id") or ""); srs = str(req.get("srs_id") or "")
                    if cid and cid not in gap["related_candidate_ids"]:
                        gap["related_candidate_ids"].append(cid)
                    if srs and srs not in gap["related_srs_ids"]:
                        gap["related_srs_ids"].append(srs)
                    for oid in _list(req.get("source_requirement_occurrence_ids")):
                        if str(oid) and str(oid) not in gap["related_source_occurrence_ids"]:
                            gap["related_source_occurrence_ids"].append(str(oid))

        # Existing candidate references deterministically imply their mapped SRS.
        for cid in list(gap.get("related_candidate_ids") or []):
            srs = srs_by_candidate.get(str(cid))
            if srs and srs not in gap["related_srs_ids"]:
                gap["related_srs_ids"].append(srs)
        if not any(_list(gap.get(k)) for k in ("related_candidate_ids", "related_srs_ids", "related_source_occurrence_ids", "related_source_requirement_ids")):
            gap.setdefault("document_context_link", {"scope": "document", "reason": "No exact Requirement/Occurrence anchor could be established deterministically; human review required."})


def apply_quality_audits(data: dict[str, Any], compact_text: str) -> dict[str, Any]:
    for req in [x for x in (data.get("requirements") or []) if isinstance(x, dict)]:
        normalize_requirement_extensions(req)
    normalize_external_dependencies(data)
    dedupe_and_scope_gaps(data)
    data["source_coverage"] = build_source_coverage(data, compact_text)
    attach_semantic_traceability(data, compact_text)
    preserve_numeric_relation_semantics(data)
    apply_coverage_mode(data)
    _enrich_gap_links_from_exact_evidence(data)
    filter_gap_links_by_scope(data)
    _build_review_findings_for_missing(data)
    _build_missing_behavior_dispositions(data)
    # Missing-disposition refresh writes explicit-ID metrics; restore N/A semantics for non-ID sources.
    apply_coverage_mode(data)
    _raw_conflicts = _dedupe_conflict_register(build_conflict_register(data, compact_text))
    data["conflict_register"], data["naming_issue_register"] = _split_naming_issues(_raw_conflicts)
    data["reference_integrity_result"] = build_reference_integrity(data)
    data["reference_completeness_result"] = build_reference_completeness(data)
    data["export_preservation_audit"] = build_export_preservation_audit(data)
    data["unsupported_generation_report"] = build_unsupported_generation_report(data, compact_text)
    data["testability_and_decomposition_result"] = build_testability_result(data)
    data.setdefault("test_intent_coverage", {})
    data.setdefault("regression_report", {})
    return data
