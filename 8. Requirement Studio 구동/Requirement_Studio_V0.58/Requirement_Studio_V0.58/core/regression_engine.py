from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from typing import Any

_EXPLICIT_ID_PATTERNS = [
    re.compile(r"(?<![A-Za-z0-9_])REQ[A-Z0-9]*[-_.][A-Z0-9][A-Z0-9_.-]*(?![A-Za-z0-9_.-])", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_])REQ\d+[A-Z0-9_.-]*(?![A-Za-z0-9_.-])", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_])SW[_-]?REQ[-_.A-Z0-9]*\d[A-Z0-9_.-]*(?![A-Za-z0-9_.-])", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_])SWR[-_.A-Z0-9]*\d[A-Z0-9_.-]*(?![A-Za-z0-9_.-])", re.IGNORECASE),
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
        return str(value)
    return str(value)


def _normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_text(value: Any) -> str:
    text = _normalize_space(value).lower()
    text = re.sub(r"[\[\]{}()<>|,:;]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_normalize_text(value).encode("utf-8", errors="ignore")).hexdigest()[:20]


def _explicit_ids(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for pattern in _EXPLICIT_ID_PATTERNS:
        for match in pattern.finditer(text or ""):
            value = match.group(0).strip().upper()
            if value not in seen:
                seen.add(value)
                out.append(value)
    return out


def _location_interval(value: str) -> tuple[str, int, int, int | None] | None:
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


def _location_overlap(a: str, b: str) -> bool:
    ia = _location_interval(a); ib = _location_interval(b)
    if ia and ib and ia[0] == ib[0]:
        if ia[0] == "table" and ia[3] != ib[3]:
            return False
        return max(ia[1], ib[1]) <= min(ia[2], ib[2])
    na = _normalize_text(a); nb = _normalize_text(b)
    return bool(na and nb and (na == nb or na in nb or nb in na))


def _similarity(a: str, b: str) -> float:
    na = _normalize_text(a); nb = _normalize_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        shorter = min(len(na), len(nb)); longer = max(len(na), len(nb))
        return max(0.75, shorter / longer)
    seq = SequenceMatcher(None, na, nb).ratio()
    ta = set(na.split()); tb = set(nb.split())
    jac = len(ta & tb) / max(1, len(ta | tb))
    return max(seq, jac)


def _evidence_rows(req: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for ev in _list(req.get("source_evidence")):
        if isinstance(ev, dict):
            rows.append({
                "location": _normalize_space(ev.get("location")),
                "text": _normalize_space(ev.get("text"))[:1200],
                "document": _normalize_space(ev.get("document")),
            })
        elif str(ev).strip():
            rows.append({"location": "", "text": _normalize_space(ev)[:1200], "document": ""})
    return rows


def _source_ids(req: dict[str, Any]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for item in _list(req.get("source_requirement_ids")):
        key = _normalize_space(item).upper()
        if key and key not in seen:
            seen.add(key); values.append(key)
    hay = " ".join(
        [_text(req.get("requirement")), _text(req.get("derivation_reason")), _text(req.get("function_name"))]
        + [f"{x['location']} {x['text']}" for x in _evidence_rows(req)]
    )
    for sid in _explicit_ids(hay):
        if sid not in seen:
            seen.add(sid); values.append(sid)
    return values


def reconstruct_baseline_behaviors(previous_payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    canonical = previous_payload.get("canonical_requirement") or {}
    requirements = [x for x in (canonical.get("requirements") or []) if isinstance(x, dict)]
    behaviors: list[dict[str, Any]] = []
    failed = 0
    partial = 0
    for idx, req in enumerate(requirements, start=1):
        ids = _source_ids(req)
        evidence = _evidence_rows(req)
        requirement_text = _normalize_space(req.get("requirement"))
        if evidence or ids:
            reconstruction_status = "Reconstructed"
        elif requirement_text:
            reconstruction_status = "Partial"
            partial += 1
        else:
            reconstruction_status = "Failed"
            failed += 1
        excerpts = [x.get("text", "") for x in evidence if x.get("text")]
        locations = [x.get("location", "") for x in evidence if x.get("location")]
        behaviors.append({
            "baseline_behavior_id": f"BHB-{idx:04d}",
            "reconstruction_status": reconstruction_status,
            "baseline_candidate_ids": [str(req.get("candidate_id"))] if req.get("candidate_id") else [],
            "baseline_srs_ids": [str(req.get("srs_id"))] if req.get("srs_id") else [],
            "source_requirement_ids": ids,
            "source_evidence": evidence,
            "source_locations": locations,
            "normalized_excerpt_fingerprints": [_fingerprint(x) for x in excerpts],
            "baseline_requirement_text": requirement_text[:1600],
            "baseline_requirement_fingerprint": _fingerprint(requirement_text) if requirement_text else "",
        })
    source_backed = sum(1 for x in behaviors if x["reconstruction_status"] == "Reconstructed")
    return behaviors, {
        "baseline_requirement_count": len(requirements),
        "source_backed_behavior_count": source_backed,
        "source_backed_behavior_reconstruction_failed_count": failed + partial,
        "baseline_behavior_reconstructed_count": len(behaviors) - failed,
        "baseline_behavior_partial_count": partial,
        "baseline_behavior_failed_count": failed,
    }


def _current_occurrences(current_data: dict[str, Any]) -> list[dict[str, Any]]:
    coverage = current_data.get("source_coverage") or {}
    return [x for x in (coverage.get("source_requirement_occurrences") or []) if isinstance(x, dict) and x.get("occurrence_type", "declaration") == "declaration"]


def _current_requirements(current_data: dict[str, Any]) -> list[dict[str, Any]]:
    return [x for x in (current_data.get("requirements") or []) if isinstance(x, dict)]


def _match_occurrences(behavior: dict[str, Any], occurrences: list[dict[str, Any]]) -> list[tuple[int, str, dict[str, Any]]]:
    ids = set(behavior.get("source_requirement_ids") or [])
    locations = behavior.get("source_locations") or []
    evidence_texts = [x.get("text", "") for x in behavior.get("source_evidence") or [] if isinstance(x, dict)]
    scored: list[tuple[int, str, dict[str, Any]]] = []
    id_counts: dict[str, int] = {}
    for occ in occurrences:
        sid = _normalize_space(occ.get("source_req_id")).upper()
        if sid:
            id_counts[sid] = id_counts.get(sid, 0) + 1
    for occ in occurrences:
        sid = _normalize_space(occ.get("source_req_id")).upper()
        loc = _normalize_space(occ.get("source_location") or occ.get("section_path"))
        excerpt = _normalize_space(occ.get("source_excerpt"))
        score = 0; method = ""
        if ids and sid in ids:
            if any(_location_overlap(bloc, loc) for bloc in locations if bloc and loc):
                score, method = 100, "source_requirement_id+source_location"
            else:
                sim = max((_similarity(text, excerpt) for text in evidence_texts if text and excerpt), default=0.0)
                if sim >= 0.70:
                    score, method = 92, "source_requirement_id+normalized_excerpt"
                elif sim >= 0.45:
                    score, method = 82, "source_requirement_id+excerpt_similarity"
                elif id_counts.get(sid, 0) == 1:
                    score, method = 60, "source_requirement_id_only_fallback"
                else:
                    score, method = 40, "reused_source_id_ambiguous"
        else:
            if locations and any(_location_overlap(bloc, loc) for bloc in locations if bloc and loc):
                sim = max((_similarity(text, excerpt) for text in evidence_texts if text and excerpt), default=0.0)
                score, method = (78 if sim >= 0.35 else 68), "source_location_overlap"
            else:
                sim = max((_similarity(text, excerpt) for text in evidence_texts if text and excerpt), default=0.0)
                if sim >= 0.72:
                    score, method = 72, "normalized_excerpt_similarity"
        if score:
            scored.append((score, method, occ))
    if not scored:
        return []
    best = max(x[0] for x in scored)
    # Keep all equally strong occurrence matches. This supports repeated declarations of the same behavior.
    return [x for x in scored if x[0] == best]


def _match_current_requirements(behavior: dict[str, Any], occurrences: list[dict[str, Any]], requirements: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    req_by_srs = {str(r.get("srs_id") or ""): r for r in requirements if r.get("srs_id")}
    req_by_cid = {str(r.get("candidate_id") or ""): r for r in requirements if r.get("candidate_id")}
    matched: list[dict[str, Any]] = []
    methods: list[str] = []
    seen: set[str] = set()
    for occ in occurrences:
        for sid in _list(occ.get("linked_srs_ids")):
            req = req_by_srs.get(str(sid))
            if req:
                key = str(req.get("candidate_id") or req.get("srs_id") or id(req))
                if key not in seen:
                    seen.add(key); matched.append(req); methods.append("occurrence_to_srs")
        for cid in _list(occ.get("linked_candidate_ids")):
            req = req_by_cid.get(str(cid))
            if req:
                key = str(req.get("candidate_id") or req.get("srs_id") or id(req))
                if key not in seen:
                    seen.add(key); matched.append(req); methods.append("occurrence_to_candidate")

    # Traceability fallback: current behavior exists but explicit occurrence linkage may be broken.
    ids = set(behavior.get("source_requirement_ids") or [])
    locations = behavior.get("source_locations") or []
    evidence_texts = [x.get("text", "") for x in behavior.get("source_evidence") or [] if isinstance(x, dict)]
    behavior_text = _normalize_space(behavior.get("baseline_requirement_text"))
    for req in requirements:
        req_ids = set(_source_ids(req))
        req_evidence = _evidence_rows(req)
        id_match = bool(ids and ids & req_ids)
        loc_match = any(_location_overlap(bloc, ev.get("location", "")) for bloc in locations for ev in req_evidence if bloc and ev.get("location"))
        sim = max((_similarity(bt, ev.get("text", "")) for bt in evidence_texts for ev in req_evidence if bt and ev.get("text")), default=0.0)
        current_behavior_text = " ".join(_normalize_space(req.get(k)) for k in ("function_name", "requirement", "processing_action", "output", "acceptance_criteria"))
        behavior_sim = _similarity(behavior_text, current_behavior_text) if behavior_text and current_behavior_text else 0.0
        # V0.55: a grouped/current Requirement may preserve the baseline behavior while one or more
        # source IDs/occurrences are incomplete. Require at least one source anchor (ID/location)
        # before semantic matching can rescue the behavior; semantic similarity alone never PASSes.
        anchored_semantic_match = (id_match and behavior_sim >= 0.34) or (loc_match and behavior_sim >= 0.34)
        if (id_match and (loc_match or sim >= 0.40)) or (not ids and loc_match and sim >= 0.30) or anchored_semantic_match:
            key = str(req.get("candidate_id") or req.get("srs_id") or id(req))
            if key not in seen:
                seen.add(key); matched.append(req)
                methods.append("candidate_behavior_semantic_fallback" if anchored_semantic_match and not (loc_match or sim >= 0.40) else "candidate_source_evidence_fallback")
    return matched, methods


def _explicit_disposition(occurrences: list[dict[str, Any]]) -> bool:
    for occ in occurrences:
        status = str(occ.get("coverage_status") or "")
        reason = _normalize_space(occ.get("disposition_reason"))
        links = _list(occ.get("linked_gap_issue_ids"))
        if status in {"Gap / Insufficient Source", "Intentionally Excluded", "Not a SW Requirement"} and reason and (links or status != "Gap / Insufficient Source"):
            return True
    return False


def build_regression_report(
    current_data: dict[str, Any],
    previous_payload: dict[str, Any] | None,
    previous_path: str,
    *,
    current_run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_run = current_run or {}
    if not previous_payload:
        return {
            "baseline_available": False,
            "baseline_path": "",
            "baseline_version": "",
            "baseline_is_v046_reference": False,
            "run_compatibility": {"source_match": False, "comparison_mode": "not_evaluated"},
            "baseline_behavior_summary": {},
            "comparison_coverage": {},
            "regression_count": 0,
            "critical_regression_count": 0,
            "findings": [],
            "regression_gate": {
                "status": "NOT_EVALUATED",
                "passed": False,
                "reason": previous_path or "No compatible baseline available.",
                "policy": "A regression gate may pass only after baseline behaviors were reconstructed and compared with sufficient evidence.",
            },
            "scope_note": "No same-source baseline available; absence of findings is not interpreted as PASS.",
        }

    previous_run = previous_payload.get("run") or {}
    previous_data = previous_payload.get("canonical_requirement") or {}
    gold_meta = previous_payload.get("gold_source_contract") if isinstance(previous_payload.get("gold_source_contract"), dict) else {}
    baseline_type = str(gold_meta.get("baseline_type") or ("full_review_package" if not gold_meta else ""))
    baseline_origin_version = str(gold_meta.get("baseline_origin_version") or previous_run.get("requirement_studio_version") or "")
    baseline_is_full_review_package = bool(gold_meta.get("is_full_review_package", not bool(gold_meta)))
    baseline_behavior_scope = str(gold_meta.get("behavior_scope") or ("full review package" if baseline_is_full_review_package else ""))
    baseline_version = str(previous_run.get("requirement_studio_version") or "")
    baseline_is_v046 = baseline_version.strip().lower() in {"v0.46", "0.46"}
    source_match = bool(str(previous_run.get("source_sha256") or "") and str(previous_run.get("source_sha256") or "") == str(current_run.get("source_sha256") or ""))
    provider_match = _normalize_space(previous_run.get("provider_id") or previous_run.get("provider")).lower() == _normalize_space(current_run.get("provider_id") or current_run.get("provider")).lower()
    model_match = _normalize_space(previous_run.get("model")).lower() == _normalize_space(current_run.get("model")).lower()
    extraction_profile_baseline = str(previous_run.get("extraction_core_profile") or ("v0.46-native" if baseline_is_v046 else "unknown"))
    extraction_profile_current = str(current_run.get("extraction_core_profile") or "v0.46-compatible-1.1")
    extraction_core_match = baseline_is_v046 or extraction_profile_baseline == extraction_profile_current
    comparison_mode = "same_model" if provider_match and model_match else "cross_model"
    run_compatibility = {
        "source_match": source_match,
        "baseline_version": baseline_version,
        "current_version": str(current_run.get("requirement_studio_version") or ""),
        "provider_match": provider_match,
        "model_match": model_match,
        "baseline_provider": str(previous_run.get("provider") or previous_run.get("provider_id") or ""),
        "current_provider": str(current_run.get("provider") or current_run.get("provider_id") or ""),
        "baseline_model": str(previous_run.get("model") or ""),
        "current_model": str(current_run.get("model") or ""),
        "extraction_core_match": extraction_core_match,
        "baseline_extraction_core_profile": extraction_profile_baseline,
        "current_extraction_core_profile": extraction_profile_current,
        "comparison_mode": comparison_mode,
    }
    if not source_match:
        return {
            "baseline_available": True,
            "baseline_path": previous_path,
            "baseline_version": baseline_version,
            "baseline_is_v046_reference": baseline_is_v046,
            "run_compatibility": run_compatibility,
            "baseline_behavior_summary": {},
            "comparison_coverage": {},
            "regression_count": 0,
            "critical_regression_count": 0,
            "findings": [],
            "regression_gate": {"status": "NOT_EVALUATED", "passed": False, "reason": "Baseline source SHA-256 differs from the current source.", "policy": "Regression requires the same source."},
            "scope_note": "Different source; no release regression conclusion is made.",
        }

    behaviors, summary = reconstruct_baseline_behaviors(previous_payload)
    coverage = current_data.get("source_coverage") if isinstance(current_data.get("source_coverage"), dict) else {}
    if str(coverage.get("coverage_validity") or "VALID") == "INVALID":
        finding = {
            "finding_id": "REG-GLOBAL-TRACEABILITY",
            "severity": "Critical",
            "classification": "Traceability linkage regression",
            "baseline_behavior_id": "GLOBAL",
            "baseline_requirement_ids": [],
            "baseline_candidate_ids": [],
            "baseline_srs_ids": [],
            "baseline_source_evidence": [],
            "current_source_occurrence_ids": [],
            "current_coverage_status": "INVALID",
            "current_candidate_ids": [],
            "current_srs_ids": [],
            "current_disposition": "",
            "decision": "FAIL",
            "reason": str(coverage.get("coverage_validity_reason") or "TRACEABILITY_BINDING_EMPTY"),
            "comparison_method": "global_traceability_precondition",
            "comparison_confidence": "High",
        }
        return {
            "baseline_available": True,
            "baseline_path": previous_path,
            "baseline_version": baseline_version,
            "baseline_is_v046_reference": baseline_is_v046,
            "run_compatibility": run_compatibility,
            "baseline_behavior_summary": summary,
            "comparison_coverage": {
                "comparison_coverage_percent": 0.0,
                "matched_baseline_behavior_count": 0,
                "unmatched_baseline_behavior_count": int(summary.get("source_backed_behavior_count") or 0),
                "match_method_counts": {"global_traceability_precondition": 1},
            },
            "regression_count": 1,
            "critical_regression_count": 1,
            "human_review_regression_count": 0,
            "findings": [finding],
            "regression_gate": {
                "status": "FAIL",
                "passed": False,
                "reason": "Global Source-to-Canonical traceability binding is invalid; per-behavior absence findings are suppressed until linkage is repaired.",
                "policy": "Regression cannot PASS when Source Coverage validity is INVALID.",
            },
            "scope_note": "Global traceability failure blocks reliable behavior-level regression interpretation.",
        }

    occurrences = _current_occurrences(current_data)
    requirements = _current_requirements(current_data)
    findings: list[dict[str, Any]] = []
    method_counts: dict[str, int] = {}
    matched_behavior_count = 0
    missing_behavior_count = 0
    uncertain_behavior_count = 0
    partial_behavior_count = 0
    explicitly_dispositioned_count = 0
    unmatchable_count = 0

    for behavior in behaviors:
        if behavior.get("reconstruction_status") == "Failed":
            unmatchable_count += 1
            findings.append({
                "finding_id": f"REG-{len(findings)+1:03d}",
                "severity": "Review",
                "classification": "Baseline behavior reconstruction failed",
                "baseline_behavior_id": behavior.get("baseline_behavior_id"),
                "baseline_requirement_ids": behavior.get("source_requirement_ids") or [],
                "baseline_candidate_ids": behavior.get("baseline_candidate_ids") or [],
                "baseline_srs_ids": behavior.get("baseline_srs_ids") or [],
                "baseline_source_evidence": behavior.get("source_evidence") or [],
                "current_source_occurrence_ids": [],
                "current_coverage_status": "Unmatchable",
                "current_candidate_ids": [],
                "current_srs_ids": [],
                "current_disposition": "",
                "decision": "HUMAN_REVIEW_NEEDED",
                "reason": "The baseline Requirement could not be reconstructed into a source-backed comparison behavior.",
                "comparison_method": "none",
            })
            continue

        occ_matches = _match_occurrences(behavior, occurrences)
        if occ_matches:
            for _score, method, _occ in occ_matches:
                method_counts[method] = method_counts.get(method, 0) + 1
        current_occs = [x[2] for x in occ_matches]
        current_reqs, req_methods = _match_current_requirements(behavior, current_occs, requirements)
        for method in req_methods:
            method_counts[method] = method_counts.get(method, 0) + 1

        # No occurrence match: try direct current Canonical evidence. This distinguishes behavior loss from locator/schema drift.
        if not current_occs:
            fallback_reqs, fallback_methods = _match_current_requirements(behavior, [], requirements)
            if fallback_reqs:
                current_reqs = fallback_reqs
                for method in fallback_methods:
                    method_counts[method] = method_counts.get(method, 0) + 1

        if current_occs or current_reqs:
            matched_behavior_count += 1
        statuses = sorted({str(x.get("coverage_status") or "") for x in current_occs if str(x.get("coverage_status") or "")})
        candidate_ids = sorted({str(x.get("candidate_id") or "") for x in current_reqs if x.get("candidate_id")})
        srs_ids = sorted({str(x.get("srs_id") or "") for x in current_reqs if x.get("srs_id")})
        occ_ids = [str(x.get("occurrence_id") or "") for x in current_occs if x.get("occurrence_id")]
        disposition = "; ".join(sorted({str(x.get("disposition_reason") or "") for x in current_occs if str(x.get("disposition_reason") or "").strip()}))
        explicit_disp = _explicit_disposition(current_occs)

        method = occ_matches[0][1] if occ_matches else (req_methods[0] if req_methods else "none")
        confidence = "High" if occ_matches and occ_matches[0][0] >= 90 else ("Medium" if current_occs or current_reqs else "Low")
        baseline_evidence = behavior.get("source_evidence") or []

        # Behavior truly absent: Source occurrence is identifiable but no current Candidate/SRS preserves it.
        if current_occs and not current_reqs and ("Missing" in statuses or not statuses):
            missing_behavior_count += 1
            findings.append({
                "finding_id": f"REG-{len(findings)+1:03d}",
                "severity": "High",
                "classification": "Baseline behavior absent",
                "baseline_behavior_id": behavior.get("baseline_behavior_id"),
                "baseline_requirement_ids": behavior.get("source_requirement_ids") or [],
                "baseline_candidate_ids": behavior.get("baseline_candidate_ids") or [],
                "baseline_srs_ids": behavior.get("baseline_srs_ids") or [],
                "baseline_source_evidence": baseline_evidence,
                "current_source_occurrence_ids": occ_ids,
                "current_coverage_status": ", ".join(statuses) or "Missing",
                "current_candidate_ids": [],
                "current_srs_ids": [],
                "current_disposition": disposition,
                "current_behavior_present": False,
                "traceability_linkage_complete": False,
                "decision": "FAIL",
                "reason": "V0.46 source-backed behavior is identifiable in the current source but no Current Canonical Requirement/SRS preserves it.",
                "comparison_method": method,
                "comparison_confidence": confidence,
            })
            continue

        # Explicit Gap/Exclusion is a real disposition but still needs human review when baseline had a concrete Requirement.
        if current_occs and not current_reqs and explicit_disp:
            explicitly_dispositioned_count += 1
            findings.append({
                "finding_id": f"REG-{len(findings)+1:03d}",
                "severity": "Review",
                "classification": "Baseline behavior explicitly re-dispositioned",
                "baseline_behavior_id": behavior.get("baseline_behavior_id"),
                "baseline_requirement_ids": behavior.get("source_requirement_ids") or [],
                "baseline_candidate_ids": behavior.get("baseline_candidate_ids") or [],
                "baseline_srs_ids": behavior.get("baseline_srs_ids") or [],
                "baseline_source_evidence": baseline_evidence,
                "current_source_occurrence_ids": occ_ids,
                "current_coverage_status": ", ".join(statuses),
                "current_candidate_ids": [],
                "current_srs_ids": [],
                "current_disposition": disposition,
                "current_behavior_present": False,
                "traceability_linkage_complete": bool(current_occs),
                "decision": "HUMAN_REVIEW_NEEDED",
                "reason": "The baseline Requirement is no longer a Current Requirement but has an explicit source-backed disposition; human approval is required.",
                "comparison_method": method,
                "comparison_confidence": confidence,
            })
            continue

        # Behavior exists but traceability is broken/missing. Do not call this behavior absent, but do not PASS.
        if current_reqs and not current_occs:
            uncertain_behavior_count += 1
            findings.append({
                "finding_id": f"REG-{len(findings)+1:03d}",
                "severity": "Review",
                "classification": "Traceability linkage regression",
                "baseline_behavior_id": behavior.get("baseline_behavior_id"),
                "baseline_requirement_ids": behavior.get("source_requirement_ids") or [],
                "baseline_candidate_ids": behavior.get("baseline_candidate_ids") or [],
                "baseline_srs_ids": behavior.get("baseline_srs_ids") or [],
                "baseline_source_evidence": baseline_evidence,
                "current_source_occurrence_ids": [],
                "current_coverage_status": "Canonical behavior found; Source Occurrence link missing/unmatched",
                "current_candidate_ids": candidate_ids,
                "current_srs_ids": srs_ids,
                "current_disposition": "",
                "current_behavior_present": True,
                "traceability_linkage_complete": False,
                "decision": "HUMAN_REVIEW_NEEDED",
                "reason": "Current Canonical evidence appears to preserve the behavior, but Source Occurrence traceability is insufficient for an automatic PASS.",
                "comparison_method": method,
                "comparison_confidence": confidence,
            })
            continue

        if current_occs:
            bad_statuses = {x for x in statuses if x in {"Missing", "Partially Covered", "Uncertain", "Pending"}}
            if bad_statuses:
                if "Partially Covered" in bad_statuses:
                    partial_behavior_count += 1
                else:
                    uncertain_behavior_count += 1
                findings.append({
                    "finding_id": f"REG-{len(findings)+1:03d}",
                    "severity": "Review" if current_reqs else "High",
                    "classification": (
                        "Traceability linkage regression"
                        if current_reqs and bad_statuses == {"Missing"}
                        else ("Coverage uncertainty" if current_reqs else "Baseline behavior absent")
                    ),
                    "baseline_behavior_id": behavior.get("baseline_behavior_id"),
                    "baseline_requirement_ids": behavior.get("source_requirement_ids") or [],
                    "baseline_candidate_ids": behavior.get("baseline_candidate_ids") or [],
                    "baseline_srs_ids": behavior.get("baseline_srs_ids") or [],
                    "baseline_source_evidence": baseline_evidence,
                    "current_source_occurrence_ids": occ_ids,
                    "current_coverage_status": ", ".join(statuses),
                    "current_candidate_ids": candidate_ids,
                    "current_srs_ids": srs_ids,
                    "current_disposition": disposition,
                    "current_behavior_present": bool(current_reqs),
                    "traceability_linkage_complete": False,
                    "decision": "HUMAN_REVIEW_NEEDED" if current_reqs or explicit_disp else "FAIL",
                    "reason": (
                        "Current Canonical behavior exists, but the matched source occurrence remains Missing; treat this as a traceability-linkage regression rather than functional absence."
                        if current_reqs and bad_statuses == {"Missing"}
                        else "A V0.46 source-backed behavior is not fully Covered in the current occurrence matrix."
                    ),
                    "comparison_method": method,
                    "comparison_confidence": confidence,
                })
                continue

        if not current_occs and not current_reqs:
            unmatchable_count += 1
            findings.append({
                "finding_id": f"REG-{len(findings)+1:03d}",
                "severity": "Review",
                "classification": "Baseline behavior unmatchable",
                "baseline_behavior_id": behavior.get("baseline_behavior_id"),
                "baseline_requirement_ids": behavior.get("source_requirement_ids") or [],
                "baseline_candidate_ids": behavior.get("baseline_candidate_ids") or [],
                "baseline_srs_ids": behavior.get("baseline_srs_ids") or [],
                "baseline_source_evidence": baseline_evidence,
                "current_source_occurrence_ids": [],
                "current_coverage_status": "Unmatched",
                "current_candidate_ids": [],
                "current_srs_ids": [],
                "current_disposition": "",
                "current_behavior_present": False,
                "traceability_linkage_complete": False,
                "decision": "HUMAN_REVIEW_NEEDED",
                "reason": "The baseline behavior could not be reliably aligned to Current Source Occurrence or Canonical evidence. It is unsafe to treat this as PASS or FAIL automatically.",
                "comparison_method": "none",
                "comparison_confidence": "Low",
            })

    fail_findings = [x for x in findings if x.get("decision") == "FAIL"]
    review_findings = [x for x in findings if x.get("decision") == "HUMAN_REVIEW_NEEDED"]
    source_backed_count = int(summary.get("source_backed_behavior_count") or 0)
    comparison_percent = round((matched_behavior_count / source_backed_count * 100.0), 2) if source_backed_count else 0.0
    summary.update({
        "current_matched_behavior_count": matched_behavior_count,
        "current_missing_behavior_count": missing_behavior_count,
        "current_uncertain_behavior_count": uncertain_behavior_count,
        "current_partial_behavior_count": partial_behavior_count,
        "current_explicitly_dispositioned_behavior_count": explicitly_dispositioned_count,
        "baseline_unmatchable_behavior_count": unmatchable_count,
    })
    comparison_coverage = {
        "comparison_coverage_percent": comparison_percent,
        "matched_baseline_behavior_count": matched_behavior_count,
        "unmatched_baseline_behavior_count": max(0, source_backed_count - matched_behavior_count),
        "match_method_counts": method_counts,
        "source_requirement_id_match_count": sum(v for k, v in method_counts.items() if "source_requirement_id" in k),
        "source_location_match_count": sum(v for k, v in method_counts.items() if "location" in k),
        "content_hash_match_count": 0,
        "normalized_excerpt_match_count": sum(v for k, v in method_counts.items() if "excerpt" in k),
        "source_id_only_fallback_match_count": method_counts.get("source_requirement_id_only_fallback", 0),
        "candidate_evidence_fallback_match_count": method_counts.get("candidate_source_evidence_fallback", 0),
    }

    # Strict anti-false-pass gate.
    if not baseline_is_v046:
        gate_status = "HUMAN_REVIEW_NEEDED"
        reason = "A baseline was compared, but it is not the protected V0.46 extraction reference."
    elif fail_findings:
        gate_status = "FAIL"
        reason = f"{len(fail_findings)} source-backed baseline behavior regression(s) require failure."
    elif review_findings or summary.get("source_backed_behavior_reconstruction_failed_count", 0) or comparison_percent < 100.0:
        gate_status = "HUMAN_REVIEW_NEEDED"
        reason = "No critical absence was proven, but comparison/reconstruction/traceability evidence is insufficient for an automatic PASS."
    elif comparison_mode != "same_model":
        gate_status = "HUMAN_REVIEW_NEEDED"
        reason = "Baseline and current runs use different provider/model settings; result is a cross-model robustness comparison, not a release-equivalent run."
    else:
        gate_status = "PASS"
        reason = "All reconstructed V0.46 source-backed behaviors were fully compared and preserved with no unresolved regression finding."

    previous_ug = previous_data.get("unsupported_generation_report") or ((previous_payload.get("calculated_review_evidence") or {}).get("unsupported_generation_report") or {})
    current_ug = current_data.get("unsupported_generation_report") or {}
    return {
        "baseline_available": True,
        "baseline_path": previous_path,
        "baseline_version": baseline_version,
        "baseline_is_v046_reference": baseline_is_v046,
        "baseline_type": baseline_type,
        "baseline_origin_version": baseline_origin_version,
        "baseline_is_full_review_package": baseline_is_full_review_package,
        "baseline_behavior_scope": baseline_behavior_scope,
        "run_compatibility": run_compatibility,
        "current_requirement_count": len(requirements),
        "previous_requirement_count": len(previous_data.get("requirements") or []),
        "requirement_count_delta": len(requirements) - len(previous_data.get("requirements") or []),
        "baseline_behavior_summary": summary,
        "comparison_coverage": comparison_coverage,
        "regression_count": len(findings),
        "critical_regression_count": len(fail_findings),
        "human_review_regression_count": len(review_findings),
        "findings": findings,
        "regression_gate": {
            "status": gate_status,
            "passed": gate_status == "PASS",
            "reason": reason,
            "policy": "PASS requires same-source V0.46 baseline, full baseline behavior reconstruction/comparison, no Missing/Partial/Uncertain regression, and release-comparable run settings.",
        },
        "unsupported_generation_change": {
            "previous_detected": previous_ug.get("unsupported_assertion_count", 0),
            "current_detected": current_ug.get("unsupported_assertion_count", 0),
            "previous_uncertain": previous_ug.get("uncertain_assertion_count", 0),
            "current_uncertain": current_ug.get("uncertain_assertion_count", 0),
        },
        "scope_note": "Regression is behavior/evidence based. Requirement count and SRS numbering are informational only. Cross-model runs are reported separately and cannot silently PASS the release gate.",
    }
