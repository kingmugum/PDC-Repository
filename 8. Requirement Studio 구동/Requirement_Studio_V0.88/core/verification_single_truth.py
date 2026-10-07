from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any

from core.quality_audit import finalize_test_intent_coverage
from core.swe6_exporter import build_swe6_cases, build_sys5_candidates
from core.review_decision_registry import CLOSED_MODE_DISPOSITIONS, load_mode_transition_decisions

BUNDLE_SCHEMA_VERSION = "REQ-STUDIO-VERIFICATION-BUNDLE-0.87"


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(x).strip() for x in value if str(x).strip())
    if isinstance(value, dict):
        return "; ".join(f"{k}={v}" for k, v in value.items() if v not in (None, "", [], {}))
    return str(value).strip()


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _normalize(text: Any) -> str:
    return re.sub(r"\s+", " ", _text(text)).strip()


def _req_lookup(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(req.get("srs_id") or ""): req
        for req in (data.get("requirements") or [])
        if isinstance(req, dict) and str(req.get("srs_id") or "")
    }


def _testability_lookup(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = data.get("testability_and_decomposition_result")
    if not isinstance(result, dict):
        return {}
    return {
        str(row.get("srs_id") or ""): row
        for row in (result.get("by_srs") or [])
        if isinstance(row, dict) and str(row.get("srs_id") or "")
    }


def _source_locations(req: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for ev in _list(req.get("source_evidence")):
        if isinstance(ev, dict):
            loc = _normalize(ev.get("location"))
            if loc and loc not in out:
                out.append(loc)
    for alloc in _list(req.get("fact_level_allocations")):
        if isinstance(alloc, dict):
            loc = _normalize(alloc.get("source_location"))
            if loc and loc not in out:
                out.append(loc)
    return out


def _source_trace_for_req(req: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    sem_ids = [str(x) for x in _list(req.get("source_semantic_unit_ids")) if str(x)]
    fragment_ids: list[str] = []
    for key in ("source_fact_fragments", "fact_level_allocations", "source_backed_atomic_behaviors"):
        for item in _list(req.get(key)):
            if not isinstance(item, dict):
                continue
            fid = str(item.get("source_fact_fragment_id") or "")
            if fid and fid not in fragment_ids:
                fragment_ids.append(fid)
            sem = str(item.get("source_semantic_unit_id") or item.get("parent_source_semantic_unit_id") or "")
            if sem and sem not in sem_ids:
                sem_ids.append(sem)
    return sem_ids, fragment_ids, _source_locations(req)


def _trace_for_fragment(req: dict[str, Any], fragment_ids: list[str]) -> tuple[list[str], list[str], list[str]]:
    wanted = {str(x) for x in fragment_ids if str(x)}
    sem_ids: list[str] = []
    locations: list[str] = []
    fids: list[str] = []
    for alloc in _list(req.get("fact_level_allocations")):
        if not isinstance(alloc, dict):
            continue
        fid = str(alloc.get("source_fact_fragment_id") or "")
        if wanted and fid not in wanted:
            continue
        if fid and fid not in fids:
            fids.append(fid)
        sem = str(alloc.get("source_semantic_unit_id") or "")
        if sem and sem not in sem_ids:
            sem_ids.append(sem)
        loc = _normalize(alloc.get("source_location"))
        if loc and loc not in locations:
            locations.append(loc)
    if not sem_ids and not fids:
        sem_ids, all_fids, locations = _source_trace_for_req(req)
        fids = [x for x in all_fids if not wanted or x in wanted]
    return sem_ids, fids, locations


def _source_backed_behaviors(req: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for atom in _list(req.get("source_backed_atomic_behaviors")):
        if isinstance(atom, dict):
            text = _normalize(atom.get("behavior_text") or atom.get("source_fact"))
        else:
            text = _normalize(atom)
        if text and text not in out:
            out.append(text)
    if not out:
        req_text = _normalize(req.get("requirement"))
        if req_text:
            out.append(req_text)
    return out


def _actor_key(req: dict[str, Any]) -> str:
    text = _normalize(req.get("requirement"))
    patterns = [
        r"^(.{1,48}?(?:제어기|컨트롤러))\s*(?:은|는|이|가)",
        r"^([A-Z][A-Z0-9_]{1,15})\s*(?:은|는|이|가)",
        r"^((?:ECU|controller|control unit))\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return _normalize(m.group(1)).lower()
    return ""


def _mode_family_key(req: dict[str, Any]) -> str:
    """Return a conservative family key for genuinely comparable mode/state transitions.

    V0.85 intentionally avoids the old catch-all ``mode_transition`` bucket because it
    paired unrelated HU behaviors (capture, mirror, ignition, upload, etc.) and produced
    dozens of low-value findings.  Only a recognizable engineering family is compared.
    """
    fn = _normalize(req.get("function_name"))
    blob = " ".join(_normalize(req.get(k)) for k in ("function_name", "requirement", "processing_action", "output"))
    if not re.search(r"(?:mode|모드|sleep|wake|상태\s*전환|상태전이|전환|fold|unfold|폴딩|펼침|접힘|IGN\d*\s*(?:On|Off))", blob, re.I):
        return ""
    if re.search(r"(?:low\s*power|high\s*power|sleep\s*mode|power\s*mode|저전력|고전력|슬립\s*모드|B-CAN\s*(?:SLEEP|WAKE))", blob, re.I):
        return "power_mode_transition"
    if re.search(r"(?:capture\s*mode|캡처\s*모드|CaptureMode|RealTimeMon)", blob, re.I):
        return "capture_mode_transition"
    if re.search(r"(?:fold|unfold|mirror|미러|폴딩|펼침|접힘)", blob, re.I):
        return "mirror_fold_transition"
    if re.search(r"(?:IGN\d*\s*(?:On|Off)|ignition|시동)", blob, re.I):
        return "ignition_transition"
    if re.search(r"(?:sleep|wake|wakeup|wake-up|슬립|웨이크|기상)", blob, re.I):
        return "sleep_wake_transition"
    if fn:
        normalized_fn = re.sub(r"(?:low|high|on|off|sleep|wake|저전력|고전력|슬립|웨이크)", "", fn, flags=re.I)
        normalized_fn = re.sub(r"\s+", " ", normalized_fn).strip(" -_/()")
        if normalized_fn and re.search(r"(?:mode|모드|상태|power|capture|mirror)", normalized_fn, re.I):
            return normalized_fn.lower()
    return ""

def _source_number(req: dict[str, Any]) -> tuple[str, int | None]:
    locs = _source_locations(req)
    if not locs:
        return "", None
    loc = locs[0]
    m = re.search(r"\b(Paragraph|Page)\s*(\d+)", loc, re.I)
    if m:
        return m.group(1).lower(), int(m.group(2))
    m = re.search(r"\b(\d+(?:\.\d+){1,4})\b", loc)
    if m:
        # Section numbering is used only as a broad family hint, not arithmetic distance.
        return "section", None
    return "", None


def _mode_finding_id(actor: str, family: str, srs_ids: list[str]) -> str:
    raw = "|".join([actor, family] + sorted(str(x) for x in srs_ids))
    return "MT-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12].upper()


def detect_mode_transition_allocation_findings(data: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for req in (data.get("requirements") or []):
        if not isinstance(req, dict):
            continue
        family = _mode_family_key(req)
        actor = _actor_key(req)
        if not family or not actor:
            continue
        kind, num = _source_number(req)
        candidates.append({"req": req, "family": family, "actor": actor, "source_kind": kind, "source_num": num})

    registry = load_mode_transition_decisions()
    findings: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for i, left in enumerate(candidates):
        for right in candidates[i + 1:]:
            if left["actor"] != right["actor"] or left["family"] != right["family"]:
                continue
            # Same-family transitions are compared only when the Source locations are local to one another.
            # This prevents one HU actor from creating a combinatorial cross-product across an entire PDF.
            same_source_neighborhood = (
                left["source_kind"] and left["source_kind"] == right["source_kind"]
                and left["source_num"] is not None and right["source_num"] is not None
                and abs(int(left["source_num"]) - int(right["source_num"])) <= 12
            )
            if left["source_kind"] in {"paragraph", "page"} and right["source_kind"] in {"paragraph", "page"} and not same_source_neighborhood:
                continue
            lreq, rreq = left["req"], right["req"]
            lid, rid = str(lreq.get("srs_id") or ""), str(rreq.get("srs_id") or "")
            pair = tuple(sorted((lid, rid)))
            if not lid or not rid or pair in seen_pairs:
                continue
            lsig = (str(lreq.get("allocation_status") or ""), str(lreq.get("sys5_eligibility") or ""), str(lreq.get("swe6_eligibility") or ""))
            rsig = (str(rreq.get("allocation_status") or ""), str(rreq.get("sys5_eligibility") or ""), str(rreq.get("swe6_eligibility") or ""))
            if lsig == rsig:
                continue
            meaningful = (
                (lsig[2] == "Eligible") != (rsig[2] == "Eligible")
                or (str(lsig[1]).startswith("Eligible")) != (str(rsig[1]).startswith("Eligible"))
                or ("PENDING_SW_ALLOCATION" in lsig[0]) != ("PENDING_SW_ALLOCATION" in rsig[0])
            )
            if not meaningful:
                continue
            seen_pairs.add(pair)
            finding_id = _mode_finding_id(left["actor"], left["family"], [lid, rid])
            decision = registry.get(finding_id, {})
            disposition = str(decision.get("disposition") or "PENDING").upper()
            findings.append({
                "finding_id": finding_id,
                "finding_type": "MODE_TRANSITION_ALLOCATION_INCONSISTENCY",
                "severity": "RELEASE_REVIEW",
                "gate_scope": "ARTIFACT_READINESS",
                "affected_srs_ids": [lid, rid],
                "actor": left["actor"],
                "mode_transition_family": left["family"],
                "left_allocation": {"allocation_status": lsig[0], "sys5_eligibility": lsig[1], "swe6_eligibility": lsig[2]},
                "right_allocation": {"allocation_status": rsig[0], "sys5_eligibility": rsig[1], "swe6_eligibility": rsig[2]},
                "reason": "Same controller/actor and same mode-transition family has divergent SYS.5/SWE.6 allocation. This is a human-review finding, not an automatic reallocation rule.",
                "required_resolution": "Confirm fact-level System/SW responsibility for both transitions and approve whether the allocation difference is intentional.",
                "source_locations": list(dict.fromkeys(_source_locations(lreq) + _source_locations(rreq))),
                "review_disposition": disposition,
                "review_owner": str(decision.get("owner") or ""),
                "review_rationale": str(decision.get("rationale") or ""),
                "reviewed_at": str(decision.get("reviewed_at") or ""),
                "review_closed": disposition in CLOSED_MODE_DISPOSITIONS,
            })
    data["mode_transition_allocation_findings"] = findings
    return findings

def _required_resolution(reason_code: str) -> str:
    code = str(reason_code or "").upper()
    if code == "ALLOCATION_PENDING":
        return "System/SW allocation owner must approve software responsibility and SWE.6 applicability; retain SYS.5 trace until then."
    if code == "EXTERNAL_SPEC_REQUIRED":
        return "Obtain and approve the referenced external specification/evidence before concrete test criteria are authored."
    if code == "SOURCE_INSUFFICIENT":
        return "Close the Source clarification/TBD with authoritative engineering evidence before concrete test data are authored."
    if code == "EXPORTER_CAPABILITY_PENDING":
        return "Retain the Source-backed intent and add exporter support or a reviewed human-authored procedure without inventing Source-missing data."
    return "Human engineering review is required to disposition this verification intent."


def _test_object_type_for_deferred(reason_code: str) -> str:
    code = str(reason_code or "").upper()
    if code == "ALLOCATION_PENDING":
        return "ALLOCATION_PENDING_INTENT"
    if code == "EXTERNAL_SPEC_REQUIRED":
        return "EXTERNAL_DEPENDENCY_INTENT"
    if code == "HUMAN_REVIEW_REQUIRED":
        return "REVIEW_REQUIRED"
    return "DEFERRED_INTENT"


def _native_object_type(allocation: dict[str, Any]) -> str:
    status = str(allocation.get("allocation_status") or "")
    domain = str(allocation.get("verification_domain") or "").lower()
    if status == "EXTERNAL_STANDARD_REFERENCE" or "external" in domain:
        return "EXTERNAL_DEPENDENCY_INTENT"
    if "electrical" in domain:
        return "ELECTRICAL_VERIFICATION_INTENT"
    if "environment" in domain:
        return "ENVIRONMENTAL_VERIFICATION_INTENT"
    if "mechanical" in domain or "connector" in domain or "hardware" in domain:
        return "MECHANICAL_VERIFICATION_INTENT"
    if "manufactur" in domain or "solder" in domain:
        return "MANUFACTURING_VERIFICATION_INTENT"
    return ""


def build_integrated_test_objects(
    data: dict[str, Any],
    swe6_cases: list[dict[str, Any]],
    sys5_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reqs = _req_lookup(data)
    test_rows = _testability_lookup(data)
    objects: list[dict[str, Any]] = []

    # 1) SYS.5 candidates — preserve system verification visibility even when SWE.6 is deferred.
    for case in sys5_candidates:
        sid = str(case.get("srs_id") or "")
        req = reqs.get(sid, {})
        scope_basis = str(case.get("source_scope_basis") or "FACT_LEVEL_SYS5")
        if scope_basis == "PARENT_FALLBACK":
            sem_ids = [str(x) for x in _list(req.get("source_semantic_unit_ids")) if str(x)]
            fids = []
            locations = _source_locations(req)
        else:
            sem_ids, fids, locations = _trace_for_fragment(req, list(case.get("source_fact_fragment_ids") or []))
        objects.append({
            "test_object_type": "SYS5_CANDIDATE",
            "test_object_id": str(case.get("sys5_id") or ""),
            "parent_srs_id": sid,
            "candidate_id": str(req.get("candidate_id") or ""),
            "source_semantic_unit_ids": sem_ids,
            "source_fact_fragment_ids": fids,
            "source_locations": locations,
            "source_backed_behavior": str(case.get("objective") or ""),
            "verification_objective": str(case.get("objective") or ""),
            "test_intent": str(case.get("objective") or ""),
            "engineering_domain": " | ".join(str(x) for x in _list(req.get("engineering_domains")) if str(x)),
            "verification_domain": str(case.get("verification_domain") or "SYS.5 System Qualification Candidate"),
            "sys5_eligibility": str(req.get("sys5_eligibility") or ""),
            "swe6_eligibility": str(req.get("swe6_eligibility") or ""),
            "allocation_status": str(req.get("allocation_status") or ""),
            "execution_readiness": str(case.get("execution_readiness") or "REVIEW_REQUIRED"),
            "human_review_required": bool(case.get("human_decision_required")) or True,
            "deferred_reason_code": "",
            "deferred_reason_detail": "",
            "required_resolution": "Approve System qualification scope, controllable conditions, observations, and acceptance criteria before execution.",
            "source_or_external_dependency": str(case.get("missing_data_or_dependency") or ""),
            "test_preparation": "",
            "test_execution": "",
            "expected_result": "",
            "variable": "",
            "compare": "",
            "value": "",
            "output_value": "",
            "pass_fail": "",
            "comment": "",
            "capture": "",
            "source_scope_basis": scope_basis,
        })

    # 2) SWE.6 candidate cases — reuse the exact finalized case objects.
    for case in swe6_cases:
        sid = str(case.get("srs_id") or "")
        req = reqs.get(sid, {})
        sem_ids = [str(x) for x in _list(case.get("source_semantic_unit_ids")) if str(x)]
        fids = [str(x) for x in _list(case.get("swe6_scope_fragment_ids")) if str(x)]
        if not sem_ids or not fids:
            s2, f2, loc2 = _trace_for_fragment(req, fids)
            sem_ids = sem_ids or s2
            fids = fids or f2
            locations = loc2
        else:
            locations = _source_locations(req)
        objects.append({
            "test_object_type": "SWE6_TC",
            "test_object_id": str(case.get("tc_id") or ""),
            "parent_srs_id": sid,
            "candidate_id": str(req.get("candidate_id") or ""),
            "source_semantic_unit_ids": sem_ids,
            "source_fact_fragment_ids": fids,
            "source_locations": locations,
            "source_backed_behavior": " | ".join(str(x) for x in _list(case.get("source_backed_atomic_behaviors")) if str(x)),
            "verification_objective": str(case.get("description") or ""),
            "test_intent": str(case.get("name") or ""),
            "engineering_domain": " | ".join(str(x) for x in _list(req.get("engineering_domains")) if str(x)),
            "verification_domain": str(case.get("verification_domain") or req.get("verification_domain") or ""),
            "sys5_eligibility": str(req.get("sys5_eligibility") or ""),
            "swe6_eligibility": str(req.get("swe6_eligibility") or ""),
            "allocation_status": str(req.get("allocation_status") or ""),
            "execution_readiness": str(case.get("execution_readiness") or "REVIEW_REQUIRED"),
            "human_review_required": bool(req.get("human_decision_required")) or str(case.get("execution_readiness") or "") != "READY",
            "deferred_reason_code": "",
            "deferred_reason_detail": "",
            "required_resolution": str(req.get("hold_reason") or ""),
            "source_or_external_dependency": _text(req.get("external_dependencies")),
            "test_preparation": str(case.get("prep_desc") or ""),
            "test_execution": str(case.get("exec_desc") or ""),
            "expected_result": str(case.get("expected_desc") or ""),
            "variable": str(case.get("expected_var") or case.get("exec_var") or case.get("prep_var") or ""),
            "compare": str(case.get("expected_compare") or case.get("exec_compare") or case.get("prep_compare") or ""),
            "value": str(case.get("expected_value") or case.get("exec_value") or case.get("prep_value") or ""),
            "output_value": "",
            "pass_fail": "",
            "comment": "",
            "capture": "",
        })

    # 3) Authoritative deferred/allocation/external intents from finalized testability single truth.
    deferred_counter = Counter()
    for sid, row in test_rows.items():
        req = reqs.get(sid, {})
        sem_ids, fids, locations = _source_trace_for_req(req)
        source_behavior = " | ".join(_source_backed_behaviors(req))
        for item in _list(row.get("not_generated_test_intents")):
            if not isinstance(item, dict):
                continue
            reason_code = str(item.get("reason_code") or "")
            obj_type = _test_object_type_for_deferred(reason_code)
            deferred_counter[obj_type] += 1
            prefix = {
                "ALLOCATION_PENDING_INTENT": "AP_INTENT",
                "EXTERNAL_DEPENDENCY_INTENT": "EXT_INTENT",
                "REVIEW_REQUIRED": "REV_INTENT",
            }.get(obj_type, "DEF_INTENT")
            obj_id = f"{prefix}_{deferred_counter[obj_type]:03d}"
            intent_name = str(item.get("intent") or "Deferred Verification Intent")
            requirement = _normalize(req.get("requirement"))
            objects.append({
                "test_object_type": obj_type,
                "test_object_id": obj_id,
                "parent_srs_id": sid,
                "candidate_id": str(req.get("candidate_id") or ""),
                "source_semantic_unit_ids": sem_ids,
                "source_fact_fragment_ids": fids,
                "source_locations": locations,
                "source_backed_behavior": source_behavior or requirement,
                "verification_objective": requirement or source_behavior,
                "test_intent": (f"{intent_name} | {requirement}" if requirement else intent_name),
                "engineering_domain": " | ".join(str(x) for x in _list(req.get("engineering_domains")) if str(x)),
                "verification_domain": str(req.get("verification_domain") or ""),
                "sys5_eligibility": str(req.get("sys5_eligibility") or ""),
                "swe6_eligibility": str(req.get("swe6_eligibility") or ""),
                "allocation_status": str(req.get("allocation_status") or ""),
                "execution_readiness": "REVIEW_REQUIRED",
                "human_review_required": bool(item.get("human_review_required", True)),
                "deferred_reason_code": reason_code,
                "deferred_reason_detail": str(item.get("reason") or ""),
                "required_resolution": _required_resolution(reason_code),
                "source_or_external_dependency": str(item.get("source_or_dependency") or ""),
                "test_preparation": "",
                "test_execution": "",
                "expected_result": "",
                "variable": "",
                "compare": "",
                "value": "",
                "output_value": "",
                "pass_fail": "",
                "comment": "",
                "capture": "",
            })

    # 4) Native/non-software verification facts that are outside SYS.5/SWE.6 qualification.
    native_counter = Counter()
    native_seen: set[tuple[str, str, str]] = set()
    for sid, req in reqs.items():
        for alloc in _list(req.get("fact_level_allocations")):
            if not isinstance(alloc, dict):
                continue
            obj_type = _native_object_type(alloc)
            if not obj_type:
                continue
            fid = str(alloc.get("source_fact_fragment_id") or "")
            fact = _normalize(alloc.get("source_fact"))
            dedup_key = (sid, fid, obj_type)
            if dedup_key in native_seen:
                continue
            native_seen.add(dedup_key)
            # External dependency may already be represented by a deferred intent. Fact-level row
            # is still useful when it has a distinct fragment, but the ID remains a verification object.
            native_counter[obj_type] += 1
            prefix = {
                "ELECTRICAL_VERIFICATION_INTENT": "ELEC_INTENT",
                "ENVIRONMENTAL_VERIFICATION_INTENT": "ENV_INTENT",
                "MECHANICAL_VERIFICATION_INTENT": "MECH_INTENT",
                "MANUFACTURING_VERIFICATION_INTENT": "MFG_INTENT",
                "EXTERNAL_DEPENDENCY_INTENT": "EXT_FACT",
            }.get(obj_type, "NSW_INTENT")
            sem_ids, fids, locations = _trace_for_fragment(req, [fid] if fid else [])
            objects.append({
                "test_object_type": obj_type,
                "test_object_id": f"{prefix}_{native_counter[obj_type]:03d}",
                "parent_srs_id": sid,
                "candidate_id": str(req.get("candidate_id") or ""),
                "source_semantic_unit_ids": sem_ids,
                "source_fact_fragment_ids": fids,
                "source_locations": locations,
                "source_backed_behavior": fact or _normalize(req.get("requirement")),
                "verification_objective": fact or _normalize(req.get("requirement")),
                "test_intent": fact or _normalize(req.get("requirement")),
                "engineering_domain": " | ".join(str(x) for x in _list(req.get("engineering_domains")) if str(x)),
                "verification_domain": str(alloc.get("verification_domain") or req.get("verification_domain") or ""),
                "sys5_eligibility": str(req.get("sys5_eligibility") or ""),
                "swe6_eligibility": str(alloc.get("swe6_eligibility") or req.get("swe6_eligibility") or ""),
                "allocation_status": str(alloc.get("allocation_status") or req.get("allocation_status") or ""),
                "execution_readiness": "REVIEW_REQUIRED",
                "human_review_required": True,
                "deferred_reason_code": "EXTERNAL_SPEC_REQUIRED" if obj_type == "EXTERNAL_DEPENDENCY_INTENT" else "NON_SWE6_VERIFICATION_DOMAIN",
                "deferred_reason_detail": "Source-backed fact is allocated to a non-SWE.6 verification domain and is preserved for domain-specific verification planning.",
                "required_resolution": "Approve the responsible verification owner/domain and author execution criteria only from approved Source/evidence.",
                "source_or_external_dependency": _text(req.get("external_dependencies")),
                "test_preparation": "",
                "test_execution": "",
                "expected_result": "",
                "variable": "",
                "compare": "",
                "value": "",
                "output_value": "",
                "pass_fail": "",
                "comment": "",
                "capture": "",
            })

    return objects



def _state_transition_model(req: dict[str, Any]) -> dict[str, Any]:
    """Extract only Source-backed state-transition structure.

    This never invents transition logic.  ALL_OF/ANY_OF and target state are populated only
    when literal Source-backed requirement/atomic text supports them; otherwise they remain
    blank and the Semantic Verification Quality Gate requests human review.
    """
    family = _mode_family_key(req)
    if not family:
        return {}
    blob = " ".join(_normalize(req.get(k)) for k in ("requirement", "processing_action", "acceptance_criteria"))
    logic = ""
    if re.search(r"(?:모든\s*조건|모두\s*(?:참|만족)|\(&\)|\bAND\b|all\s+conditions)", blob, re.I):
        logic = "ALL_OF"
    elif re.search(r"(?:하나라도|중\s*(?:하나|1개)|\(or\)|\bOR\b|any\s+of)", blob, re.I):
        logic = "ANY_OF"
    atoms = [x for x in _list(req.get("source_backed_atomic_behaviors")) if isinstance(x, dict)]
    transition_atoms = []
    condition_atoms = []
    for atom in atoms:
        txt = _normalize(atom.get("behavior_text") or atom.get("source_fact"))
        if not txt:
            continue
        if re.search(r"(?:전환|transition|진입|enter|변경해야|되어야)", txt, re.I):
            transition_atoms.append(atom)
        else:
            condition_atoms.append(atom)
    target = ""
    search_texts = [_normalize(x.get("behavior_text") or x.get("source_fact")) for x in transition_atoms] + [blob]
    for txt in search_texts:
        if not txt:
            continue
        m = re.search(r"([A-Za-z0-9_+./ -]{2,60}(?:Mode|MODE)(?:\s*\([^)]*(?:Mode|MODE)[^)]*\))?)\s*(?:로|으로)?\s*(?:전환|진입)", txt, re.I)
        if not m:
            m = re.search(r"([^,.;]{2,60}?(?:모드|상태))\s*(?:로|으로)\s*(?:전환|진입)", txt, re.I)
        if m:
            target = _normalize(m.group(1))
            target = re.sub(r"^(?:.*?)(?:이면|경우|시)\s*", "", target).strip()
            break
    condition_ids = [str(x.get("source_fact_fragment_id") or "") for x in condition_atoms if str(x.get("source_fact_fragment_id") or "")]
    condition_texts = [_normalize(x.get("behavior_text") or x.get("source_fact")) for x in condition_atoms if _normalize(x.get("behavior_text") or x.get("source_fact"))]
    return {
        "transition_family": family,
        "condition_logic": logic,
        "condition_fragment_ids": condition_ids,
        "condition_texts": condition_texts,
        "expected_target_state": target,
    }


def _norm_intent(value: Any) -> str:
    text = _normalize(value).lower()
    text = re.sub(r"[^0-9a-z가-힣_]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _evaluation_objective_id(srs_id: str, scope: str = "MAIN") -> str:
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", str(srs_id or "REQ")).strip("_") or "REQ"
    suffix = re.sub(r"[^A-Za-z0-9_]+", "_", scope).strip("_") or "MAIN"
    return f"EVAL_{safe}_{suffix}"


def build_e2e_evaluation_cases(data: dict[str, Any], objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project raw SYS.5/SWE.6/Deferred/native objects into reviewer-facing E2E cases.

    Raw objects remain in the finalized bundle for audit.  The human-facing E2E main sheet is
    objective-centric: review-only Deferred/AP objects already represented by a SYS.5/SWE.6/native
    scope are attached as related review objects instead of appearing as duplicate test rows.
    """
    reqs = _req_lookup(data)
    by_srs: dict[str, list[dict[str, Any]]] = {}
    for obj in objects:
        by_srs.setdefault(str(obj.get("parent_srs_id") or ""), []).append(obj)
    cases: list[dict[str, Any]] = []
    primary_types = {
        "SWE6_TC", "SYS5_CANDIDATE",
        "ELECTRICAL_VERIFICATION_INTENT", "ENVIRONMENTAL_VERIFICATION_INTENT",
        "MECHANICAL_VERIFICATION_INTENT", "MANUFACTURING_VERIFICATION_INTENT",
    }
    review_types = {"SYS5_PARENT_SCOPE_REVIEW", "DEFERRED_INTENT", "ALLOCATION_PENDING_INTENT", "EXTERNAL_DEPENDENCY_INTENT", "REVIEW_REQUIRED"}
    for sid, req in reqs.items():
        raw_per = by_srs.get(sid, [])
        per = []
        for raw in raw_per:
            item = dict(raw)
            if str(item.get("test_object_type") or "") == "SYS5_CANDIDATE" and str(item.get("source_scope_basis") or "") == "PARENT_FALLBACK":
                item["test_object_type"] = "SYS5_PARENT_SCOPE_REVIEW"
            per.append(item)
        state = _state_transition_model(req)
        primary = [x for x in per if str(x.get("test_object_type") or "") in primary_types]
        reviews = [x for x in per if str(x.get("test_object_type") or "") in review_types]
        emitted_review_keys: set[tuple] = set()

        def append_case(obj: dict[str, Any], scope: str, related: list[dict[str, Any]]):
            obj = dict(obj)
            fids = [str(x) for x in _list(obj.get("source_fact_fragment_ids")) if str(x)]
            if str(obj.get("test_object_type") or "") == "SYS5_CANDIDATE" and (str(obj.get("source_scope_basis") or "") == "PARENT_FALLBACK" or not fids):
                obj["test_object_type"] = "SYS5_PARENT_SCOPE_REVIEW"
            if state and str(obj.get("test_object_type") or "") in {"SYS5_CANDIDATE", "SYS5_PARENT_SCOPE_REVIEW"} and state.get("condition_fragment_ids"):
                # A state-transition objective is the governing relation; preserve the complete condition set.
                fids = list(dict.fromkeys(fids + list(state.get("condition_fragment_ids") or [])))
            case = dict(obj)
            case.update({
                "evaluation_objective_id": _evaluation_objective_id(sid, scope),
                "related_test_object_ids": [str(x.get("test_object_id") or "") for x in related if str(x.get("test_object_id") or "")],
                "source_fact_fragment_ids": fids,
                **state,
            })
            if not case.get("verification_objective"):
                case["verification_objective"] = _normalize(req.get("requirement"))
            cases.append(case)

        for obj in primary:
            typ = str(obj.get("test_object_type") or "")
            scope = "SWE6" if typ == "SWE6_TC" else ("SYS5" if typ.startswith("SYS5") else typ.replace("_VERIFICATION_INTENT", ""))
            pfids = set(str(x) for x in _list(obj.get("source_fact_fragment_ids")) if str(x))
            related = []
            for rev in reviews:
                rfids = set(str(x) for x in _list(rev.get("source_fact_fragment_ids")) if str(x))
                if str(rev.get("test_object_type") or "") == "SYS5_PARENT_SCOPE_REVIEW":
                    # Parent-only SYS.5 scope is governance context, never a second executable row
                    # when another fact-backed evaluation object already represents this SRS.
                    related.append(rev)
                    continue
                if state and typ.startswith("SYS5"):
                    # State-transition review objects belong to the same governing objective.
                    related.append(rev)
                    continue
                if pfids and rfids and pfids.intersection(rfids):
                    related.append(rev)
            append_case(obj, scope, related)
            for rev in related:
                key=(str(rev.get("test_object_type") or ""), tuple(sorted(str(x) for x in _list(rev.get("source_fact_fragment_ids")) if str(x))), str(rev.get("deferred_reason_code") or ""), _norm_intent(rev.get("verification_objective") or rev.get("test_intent")))
                emitted_review_keys.add(key)

        # Review-only scopes not represented by a primary candidate remain visible as E2E cases.
        grouped: dict[tuple, list[dict[str, Any]]] = {}
        for rev in reviews:
            key=(str(rev.get("test_object_type") or ""), tuple(sorted(str(x) for x in _list(rev.get("source_fact_fragment_ids")) if str(x))), str(rev.get("deferred_reason_code") or ""), _norm_intent(rev.get("verification_objective") or rev.get("test_intent")))
            if key in emitted_review_keys:
                continue
            grouped.setdefault(key, []).append(rev)
        for n,(key, group) in enumerate(grouped.items(),1):
            obj=dict(group[0])
            related=group[1:]
            scope=f"REVIEW{n:02d}"
            append_case(obj, scope, related)

    # Exact duplicate cases are never exported twice.
    unique=[]; seen=set()
    for case in cases:
        key=(case.get("parent_srs_id"), case.get("test_object_type"), tuple(sorted(str(x) for x in _list(case.get("source_fact_fragment_ids")) if str(x))), _norm_intent(case.get("verification_objective") or case.get("test_intent")), case.get("deferred_reason_code"))
        if key in seen:
            continue
        seen.add(key); unique.append(case)
    return unique


def build_semantic_verification_quality_audit(data: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    seen=set()
    for case in cases:
        key=(case.get("parent_srs_id"), case.get("test_object_type"), tuple(sorted(str(x) for x in _list(case.get("source_fact_fragment_ids")) if str(x))), _norm_intent(case.get("verification_objective") or case.get("test_intent")), case.get("deferred_reason_code"))
        if key in seen:
            issues.append({"issue":"DUPLICATE_E2E_EVALUATION_CASE","severity":"FAIL","evaluation_objective_id":case.get("evaluation_objective_id")})
        seen.add(key)
        if case.get("transition_family"):
            if not case.get("condition_logic"):
                issues.append({"issue":"STATE_TRANSITION_LOGIC_REVIEW_REQUIRED","severity":"REVIEW_REQUIRED","evaluation_objective_id":case.get("evaluation_objective_id"),"parent_srs_id":case.get("parent_srs_id")})
            if not case.get("expected_target_state"):
                issues.append({"issue":"STATE_TRANSITION_TARGET_REVIEW_REQUIRED","severity":"REVIEW_REQUIRED","evaluation_objective_id":case.get("evaluation_objective_id"),"parent_srs_id":case.get("parent_srs_id")})
        if str(case.get("test_object_type") or "") == "SYS5_PARENT_SCOPE_REVIEW":
            issues.append({"issue":"SYS5_PARENT_SCOPE_REVIEW_REQUIRED","severity":"REVIEW_REQUIRED","evaluation_objective_id":case.get("evaluation_objective_id"),"parent_srs_id":case.get("parent_srs_id")})
    if any(str(x.get("severity")) == "FAIL" for x in issues):
        status="FAIL"
    elif issues:
        status="REVIEW_REQUIRED"
    else:
        status="PASS"
    return {
        "schema_version":"REQ-STUDIO-SEMANTIC-VERIFICATION-QUALITY-0.87",
        "status":status,
        "passed":status=="PASS",
        "issue_count":len(issues),
        "issues":issues,
        "evaluation_case_count":len(cases),
        "rule":"Structural Single Truth PASS does not imply Semantic Verification Quality PASS.",
    }

def _build_single_truth_audit(data: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    reqs = _req_lookup(data)
    test_rows = _testability_lookup(data)
    cases = [x for x in bundle.get("swe6_cases") or [] if isinstance(x, dict)]
    sys5 = [x for x in bundle.get("sys5_candidates") or [] if isinstance(x, dict)]
    objects = [x for x in bundle.get("integrated_test_objects") or [] if isinstance(x, dict)]
    blockers: list[dict[str, Any]] = []

    tc_by_srs: dict[str, list[str]] = {}
    for case in cases:
        tc_by_srs.setdefault(str(case.get("srs_id") or ""), []).append(str(case.get("tc_id") or ""))
    obj_by_srs: dict[str, list[dict[str, Any]]] = {}
    for obj in objects:
        obj_by_srs.setdefault(str(obj.get("parent_srs_id") or ""), []).append(obj)

    for sid, req in reqs.items():
        eligibility = str(req.get("swe6_eligibility") or "")
        per_req = obj_by_srs.get(sid, [])
        deferred_objs = [x for x in per_req if x.get("test_object_type") in {"DEFERRED_INTENT", "ALLOCATION_PENDING_INTENT", "EXTERNAL_DEPENDENCY_INTENT", "REVIEW_REQUIRED"}]
        if eligibility == "Eligible" and not tc_by_srs.get(sid) and not deferred_objs:
            blockers.append({
                "issue": "SWE6_ELIGIBLE_WITHOUT_TC_OR_DEFERRED_INTENT",
                "srs_id": sid,
                "severity": "RELEASE_BLOCKING",
                "required_resolution": "Generate a Source-backed SWE.6 candidate TC or record an explicit deferred/review disposition.",
            })
        if eligibility.startswith("Deferred"):
            allocation_pending = [x for x in per_req if x.get("test_object_type") in {"ALLOCATION_PENDING_INTENT", "DEFERRED_INTENT", "REVIEW_REQUIRED"}]
            if not allocation_pending:
                blockers.append({
                    "issue": "SWE6_DEFERRED_WITHOUT_DEFERRED_INTENT",
                    "srs_id": sid,
                    "severity": "RELEASE_BLOCKING",
                    "required_resolution": "Create an auditable deferred/allocation-pending intent with reason and Source trace.",
                })

    expected_deferred = sum(
        len([x for x in _list(row.get("not_generated_test_intents")) if isinstance(x, dict)])
        for row in test_rows.values()
    )
    actual_deferred = sum(1 for x in objects if x.get("test_object_type") in {"DEFERRED_INTENT", "ALLOCATION_PENDING_INTENT", "EXTERNAL_DEPENDENCY_INTENT", "REVIEW_REQUIRED"})
    # External fact-level verification objects can share EXTERNAL_DEPENDENCY_INTENT type but are
    # marked NON_SWE6/EXTERNAL_SPEC in a separate native path. Count only objects whose ID denotes
    # a deferred-intent family for parity with not_generated_test_intents.
    actual_deferred_from_testability = sum(1 for x in objects if str(x.get("test_object_id") or "").startswith(("DEF_INTENT_", "AP_INTENT_", "EXT_INTENT_", "REV_INTENT_")))
    if expected_deferred != actual_deferred_from_testability:
        blockers.append({
            "issue": "DEFERRED_INTENT_COUNT_MISMATCH",
            "expected_from_testability": expected_deferred,
            "actual_integrated_rows": actual_deferred_from_testability,
            "severity": "RELEASE_BLOCKING",
        })

    expected_tc_ids = {str(x.get("tc_id") or "") for x in cases if x.get("tc_id")}
    integrated_tc_ids = {str(x.get("test_object_id") or "") for x in objects if x.get("test_object_type") == "SWE6_TC" and x.get("test_object_id")}
    if expected_tc_ids != integrated_tc_ids:
        blockers.append({
            "issue": "INTEGRATED_SWE6_TC_ID_MISMATCH",
            "missing_ids": sorted(expected_tc_ids - integrated_tc_ids),
            "extra_ids": sorted(integrated_tc_ids - expected_tc_ids),
            "severity": "RELEASE_BLOCKING",
        })

    expected_sys5_ids = {str(x.get("sys5_id") or "") for x in sys5 if x.get("sys5_id")}
    integrated_sys5_ids = {str(x.get("test_object_id") or "") for x in objects if x.get("test_object_type") == "SYS5_CANDIDATE" and x.get("test_object_id")}
    if expected_sys5_ids != integrated_sys5_ids:
        blockers.append({
            "issue": "INTEGRATED_SYS5_ID_MISMATCH",
            "missing_ids": sorted(expected_sys5_ids - integrated_sys5_ids),
            "extra_ids": sorted(integrated_sys5_ids - expected_sys5_ids),
            "severity": "RELEASE_BLOCKING",
        })

    missing_trace = [
        str(x.get("test_object_id") or "")
        for x in objects
        if x.get("test_object_id")
        and not _list(x.get("source_semantic_unit_ids"))
        and not _list(x.get("source_fact_fragment_ids"))
    ]
    if missing_trace:
        blockers.append({
            "issue": "INTEGRATED_TEST_OBJECT_SOURCE_TRACE_MISSING",
            "test_object_ids": missing_trace,
            "severity": "RELEASE_BLOCKING",
        })

    counts = Counter(str(x.get("test_object_type") or "") for x in objects)
    return {
        "schema_version": "REQ-STUDIO-STRUCTURAL-SINGLE-TRUTH-AUDIT-0.87",
        "passed": not blockers,
        "release_gate_status": "PASS" if not blockers else "FAIL",
        "blocking_issue_count": len(blockers),
        "blocking_records": blockers,
        "generated_tc_ids": sorted(expected_tc_ids),
        "sys5_candidate_ids": sorted(expected_sys5_ids),
        "test_object_type_counts": dict(counts),
        "expected_deferred_intent_count": expected_deferred,
        "integrated_deferred_intent_count": actual_deferred_from_testability,
        "total_integrated_test_object_count": len(objects),
        "scope_note": "All V0.88 E2E outputs are derived from one finalized in-memory verification bundle. Source-missing test values/results are never synthesized to satisfy counts.",
    }


def _merge_into_swe6_audit(data: dict[str, Any], integrated_audit: dict[str, Any], mode_findings: list[dict[str, Any]]) -> None:
    audit = data.get("swe6_export_preservation_audit")
    if not isinstance(audit, dict):
        return
    blockers = [x for x in _list(audit.get("blocking_records")) if isinstance(x, dict)]
    for rec in integrated_audit.get("blocking_records") or []:
        if isinstance(rec, dict) and not any(str(x.get("issue") or "") == str(rec.get("issue") or "") and str(x.get("srs_id") or "") == str(rec.get("srs_id") or "") for x in blockers):
            blockers.append(rec)
    audit["blocking_records"] = blockers
    audit["blocking_issue_count"] = len(blockers)
    if blockers:
        audit["passed"] = False
        audit["tool_quality_gate_passed"] = False
        audit["tool_quality_gate_status"] = "FAIL"
        audit["artifact_readiness_gate_passed"] = False
        audit["artifact_readiness_gate_status"] = "FAIL"
        audit["release_gate_passed"] = False
        audit["audit_status"] = "FAIL"

    if mode_findings:
        review = [x for x in _list(audit.get("review_issue_records")) if isinstance(x, dict)]
        release_review = [x for x in _list(audit.get("release_review_issue_records")) if isinstance(x, dict)]
        artifact = [x for x in _list(audit.get("artifact_readiness_issue_records")) if isinstance(x, dict)]
        for finding in mode_findings:
            if finding.get("review_closed"):
                continue
            rec = {
                "issue": "MODE_TRANSITION_ALLOCATION_INCONSISTENCY",
                **finding,
            }
            key = tuple(sorted(str(x) for x in rec.get("affected_srs_ids") or []))
            if not any(str(x.get("issue") or "") == "MODE_TRANSITION_ALLOCATION_INCONSISTENCY" and tuple(sorted(str(y) for y in x.get("affected_srs_ids") or [])) == key for x in review):
                review.append(rec); release_review.append(rec); artifact.append(rec)
        audit["review_issue_records"] = review
        audit["review_issue_count"] = len(review)
        audit["release_review_issue_records"] = release_review
        audit["release_review_issue_count"] = len(release_review)
        audit["artifact_readiness_issue_records"] = artifact
        audit["artifact_readiness_issue_count"] = len(artifact)
        if audit.get("tool_quality_gate_passed"):
            audit["artifact_readiness_gate_passed"] = False
            audit["artifact_readiness_gate_status"] = "REVIEW_REQUIRED"
            audit["release_gate_passed"] = False
            audit["audit_status"] = "PASS_WITH_REVIEW_ITEMS"


def finalize_verification_single_truth(data: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    existing = data.get("finalized_verification_bundle")
    if not force and isinstance(existing, dict) and existing.get("schema_version") == BUNDLE_SCHEMA_VERSION:
        return existing

    swe6_cases = build_swe6_cases(data)
    finalize_test_intent_coverage(data, swe6_cases)
    sys5_candidates = build_sys5_candidates(data)
    mode_findings = detect_mode_transition_allocation_findings(data)
    integrated_test_objects = build_integrated_test_objects(data, swe6_cases, sys5_candidates)
    e2e_evaluation_cases = build_e2e_evaluation_cases(data, integrated_test_objects)

    bundle: dict[str, Any] = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "swe6_cases": swe6_cases,
        "sys5_candidates": sys5_candidates,
        "integrated_test_objects": integrated_test_objects,
        "e2e_evaluation_cases": e2e_evaluation_cases,
        "mode_transition_allocation_findings": mode_findings,
    }
    bundle["single_truth_audit"] = _build_single_truth_audit(data, bundle)
    bundle["semantic_verification_quality_audit"] = build_semantic_verification_quality_audit(data, e2e_evaluation_cases)
    bundle["summary"] = {
        "swe6_tc_count": len(swe6_cases),
        "sys5_candidate_count": len(sys5_candidates),
        "integrated_test_object_count": len(integrated_test_objects),
        "e2e_evaluation_case_count": len(e2e_evaluation_cases),
        "test_object_type_counts": dict(Counter(str(x.get("test_object_type") or "") for x in integrated_test_objects)),
        "semantic_verification_quality_status": bundle["semantic_verification_quality_audit"].get("status"),
        "mode_transition_allocation_finding_count": len(mode_findings),
        "release_gate_status": bundle["single_truth_audit"].get("release_gate_status"),
    }
    data["finalized_verification_bundle"] = bundle
    data["integrated_single_truth_audit"] = bundle["single_truth_audit"]
    data["semantic_verification_quality_audit"] = bundle["semantic_verification_quality_audit"]
    _merge_into_swe6_audit(data, bundle["single_truth_audit"], mode_findings)
    return bundle
