from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_DIR = PROJECT_ROOT / "policy"
DECISION_REGISTRY_PATH = POLICY_DIR / "decision_example_registry.json"
RULE_REGISTRY_PATH = POLICY_DIR / "guideline_rule_registry.json"


def _load_json(path: Path, default: Any) -> Any:
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        return data
    except Exception:
        return default


def load_decision_examples() -> list[dict[str, Any]]:
    data=_load_json(DECISION_REGISTRY_PATH,{})
    return [x for x in data.get("examples",[]) if isinstance(x,dict)] if isinstance(data,dict) else []


def load_guideline_rules() -> list[dict[str, Any]]:
    data=_load_json(RULE_REGISTRY_PATH,{})
    return [x for x in data.get("rules",[]) if isinstance(x,dict)] if isinstance(data,dict) else []


def extract_decision_factors(example: dict[str, Any]) -> list[str]:
    """Extract stable, explainable factors from a user decision example.

    V0.93 intentionally keeps this deterministic and auditable. It is a Guideline Mining
    experiment, not model fine-tuning and not opaque preference learning.
    """
    text=" ".join(str(example.get(k) or "") for k in ("context","user_comment","candidate_facts")).lower()
    factors=[]
    checks=(
        ("DISTINCT_TIMING_CHECKPOINT", ("5초","15초","timeout","timing","이내")),
        ("INDEPENDENT_PASS_FAIL", ("독립","별도","각각","pass/fail","판정")),
        ("SEMANTIC_BRANCH", ("가능","불가능","branch","분기","0x0","0x1")),
        ("SAME_DECISION_FUNCTION", ("decision table","동일 함수","조합","vector")),
        ("SEQUENCE_NORMATIVE", ("순차","순서","sequence","step")),
        ("NORMAL_EXCEPTION_PATH", ("normal","exception","미응답","실패","error")),
        ("VARIANT_SPECIFIC", ("variant","차종","hev","phev","ev")),
        ("HUMAN_PRESENTATION", ("한글","번호","의미단위","가독성","표현")),
    )
    for name,tokens in checks:
        if any(t in text for t in tokens):
            factors.append(name)
    return factors


def mine_candidate_rules(examples: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Mine transparent candidate principles from explicit user decisions.

    Candidate mining never changes executable policy. Only rules marked HUMAN_APPROVED in the
    separate Rule Registry are allowed to influence generation.
    """
    examples=examples if examples is not None else load_decision_examples()
    grouped: dict[tuple[str,str], list[dict[str,Any]]] = defaultdict(list)
    for ex in examples:
        decision=str(ex.get("user_final_decision") or ex.get("decision_type") or "").upper()
        if not decision:
            continue
        for factor in extract_decision_factors(ex):
            grouped[(factor,decision)].append(ex)
    out=[]
    for i,((factor,decision),items) in enumerate(sorted(grouped.items()),1):
        counter=[]
        for ex in examples:
            if factor in extract_decision_factors(ex):
                other=str(ex.get("user_final_decision") or ex.get("decision_type") or "").upper()
                if other and other!=decision:
                    counter.append(str(ex.get("decision_example_id") or ""))
        support=[str(x.get("decision_example_id") or "") for x in items]
        out.append({
            "candidate_rule_id": f"GMC-{i:03d}",
            "factor": factor,
            "suggested_decision": decision,
            "support_count": len(items),
            "support_examples": support,
            "counterexample_count": len(counter),
            "counterexamples": counter,
            "classification": "GENERAL_RULE_CANDIDATE" if len(items)>=2 and not counter else "HEURISTIC_CANDIDATE",
            "auto_promoted": False,
        })
    return out


def build_guideline_mining_snapshot() -> dict[str, Any]:
    examples=load_decision_examples()
    rules=load_guideline_rules()
    mined=mine_candidate_rules(examples)
    return {
        "schema_version":"REQ-STUDIO-GUIDELINE-MINING-0.93",
        "mode":"EXPLICIT_USER_DECISION_RULE_INDUCTION",
        "decision_example_count":len(examples),
        "approved_rule_count":sum(1 for r in rules if str(r.get("state") or "").upper()=="HUMAN_APPROVED"),
        "candidate_rule_count":len(mined),
        "rules":rules,
        "mined_candidates":mined,
        "governance":[
            "User examples are evidence; mined candidates never auto-promote.",
            "Only HUMAN_APPROVED rules in guideline_rule_registry.json may affect generation.",
            "Counterexamples remain first-class evidence and can downgrade a candidate to a heuristic.",
            "Rule changes remain subject to Requirement governance and regression.",
        ],
    }


def is_rule_approved(rule_id: str) -> bool:
    for rule in load_guideline_rules():
        if str(rule.get("rule_id") or "")==rule_id:
            return str(rule.get("state") or "").upper()=="HUMAN_APPROVED"
    return False
