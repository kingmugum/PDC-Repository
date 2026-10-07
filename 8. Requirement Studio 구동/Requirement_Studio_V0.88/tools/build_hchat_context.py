from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_CONTEXT_LINES = 3900

# Curated reviewer-facing implementation surface. This is intentionally not a whole-source dump.
SYMBOLS: dict[str, list[str]] = {
    "core/requirement_engine.py": [
        "RequirementEngine.evaluate_structure",
        "RequirementEngine.merge_results",
        "RequirementEngine.apply_quality_audits",
    ],
    "core/cross_document_semantics.py": [
        "_inferred_controller_software_behavior_evidence",
        "_semantic_review_shortcut",
        "apply_allocation_gate",
        "_disambiguate_shared_semantic_unit_ownership",
        "_reconcile_swe6_fact_scope",
        "attach_semantic_traceability",
    ],
    "core/verification_single_truth.py": [
        "_mode_family_key",
        "detect_mode_transition_allocation_findings",
        "build_integrated_test_objects",
        "build_e2e_evaluation_cases",
        "build_semantic_verification_quality_audit",
        "_state_transition_model",
        "_build_single_truth_audit",
        "finalize_verification_single_truth",
    ],
    "core/review_decision_registry.py": [
        "load_mode_transition_decisions",
        "record_mode_transition_decision",
    ],
    "core/swe6_exporter.py": [
        "build_swe6_cases",
        "build_sys5_candidates",
    ],
    "core/e2e_exporter.py": [
        "E2EExporter.export_requirements_word",
        "E2EExporter.export_requirements_excel",
        "E2EExporter.export_evaluation_excel",
        "E2EExporter._verify_evaluation_artifact",
    ],
    "core/integrated_exporter.py": [
        "_excel_scalar",
        "_linked_objects_for_fact",
        "IntegratedExporter.export_requirements_excel",
        "IntegratedExporter.export_tests_excel",
        "IntegratedExporter._enforce_and_verify_blank_results",
        "IntegratedExporter._verify_integrated_ids",
    ],
    "core/review_exchange.py": [
        "ReviewExchangeBuilder._evaluation_request",
        "ReviewExchangeBuilder.build",
    ],
    "core/evaluation_orchestrator.py": [
        "MultiModelEvaluationOrchestrator.build_evidence_package",
        "MultiModelEvaluationOrchestrator._build_situation_check",
        "MultiModelEvaluationOrchestrator._finding_concepts",
        "MultiModelEvaluationOrchestrator._same_finding",
        "MultiModelEvaluationOrchestrator._consensus",
        "MultiModelEvaluationOrchestrator._apply_unified_artifact_contract",
        "MultiModelEvaluationOrchestrator._final_result",
    ],
    "core/human_policy.py": [
        "HumanPolicyRegistry.resolve_guide_report",
        "HumanPolicyRegistry.write_run_snapshot",
    ],
    "main.py": [
        "MainWindow._build_ai_card",
        "MainWindow._build_execution_card",
        "MainWindow._build_quality_review_box",
        "MainWindow._collect_quality_review_config",
        "MainWindow._update_quality_review_ui_state",
    ],
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _version() -> str:
    text = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
    m = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)', text, flags=re.M)
    return (m.group(1) if m else "v0.00").upper()


def _module_imports(tree: ast.Module, source_lines: list[str]) -> list[str]:
    ranges: list[tuple[int, int]] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            ranges.append((node.lineno, getattr(node, "end_lineno", node.lineno)))
    out: list[str] = []
    for a, b in ranges:
        out.extend(source_lines[a - 1:b])
    return out


def _find_symbol(tree: ast.Module, dotted: str) -> ast.AST | None:
    parts = dotted.split(".")
    if len(parts) == 1:
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == parts[0]:
                return node
        return None
    if len(parts) == 2:
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == parts[0]:
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == parts[1]:
                        return child
    return None


def _extract_file(rel: str, symbols: list[str]) -> tuple[list[str], dict[str, str]]:
    path = PROJECT_ROOT / rel
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines()
    tree = ast.parse(src)
    out = [f"----- BEGIN FILE: {rel} -----", f"SHA-256: {_sha256(path)}", ""]
    imports = _module_imports(tree, lines)
    if imports:
        out += ["[Imports]"] + imports + [""]
    status: dict[str, str] = {}
    for symbol in symbols:
        node = _find_symbol(tree, symbol)
        if node is None:
            status[symbol] = "NOT_FOUND"
            out += [f"# [SYMBOL NOT FOUND] {symbol}", ""]
            continue
        a, b = node.lineno, getattr(node, "end_lineno", node.lineno)
        status[symbol] = f"L{a}-L{b}"
        out += [f"# [SYMBOL] {symbol} ({status[symbol]})"] + lines[a - 1:b] + [""]
    out += [f"----- END FILE: {rel} -----", ""]
    return out, status


def _recent_changes(version: str) -> str:
    doc = PROJECT_ROOT / "docs" / f"{version}_MANUAL_DELTA.txt"
    if doc.is_file():
        return doc.read_text(encoding="utf-8", errors="replace").strip()
    return f"{version} manual delta file not found."


def build() -> tuple[Path, Path, Path]:
    version = _version()
    out_dir = PROJECT_ROOT / "for_h_chat"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Keep the distribution folder focused on the current reviewer pack. Historical deltas remain in docs/.
    for pattern in ("00_RECENT_CHANGES_V*.txt", "Requirement_Studio_HChat_Context_V*.txt"):
        for stale in out_dir.glob(pattern):
            try:
                stale.unlink()
            except OSError:
                pass
    recent_path = out_dir / f"00_RECENT_CHANGES_{version}.txt"
    context_path = out_dir / f"Requirement_Studio_HChat_Context_{version}.txt"
    readme_path = out_dir / "README_FOR_H_CHAT.txt"

    recent = _recent_changes(version)
    recent_path.write_text(recent + "\n", encoding="utf-8")

    lines: list[str] = [
        "=" * 78,
        "Requirement Studio H-Chat Context Pack",
        f"Version: {version}",
        "Purpose: 3-file-limited H-Chat reviewer/developer context; NOT a complete source dump.",
        "=" * 78,
        "",
        "[HOW TO USE IN H-CHAT]",
        "Recommended 3 files:",
        "1) Source input document (DOCX/PDF/etc.)",
        "2) Result/output document to review (prefer E2E Requirements or E2E Evaluation when relevant)",
        f"3) {context_path.name}",
        "",
        "Ask H-Chat to distinguish Source facts, Output artifacts, and Program logic. This pack is supporting implementation context only.",
        "",
        "[NON-NEGOTIABLE REVIEW RULES]",
        "- Not SWE.1 != Not Requirement.",
        "- Not SWE.6 != Not Verifiable.",
        "- Do not invent Source-missing signals, DB values, timing, thresholds, variants, test data, or execution results.",
        "- REVIEW_REQUIRED/HOLD remains visible; visibility does not equal Official Release approval.",
        "- Mixed-domain executable scope is fact-fragment allocation bounded.",
        "- Trigger/condition alone is not positive SW allocation evidence.",
        "- Unified AI evaluation must inspect legacy SWE.1/SWE.6 plus E2E Requirements Word/Excel and the complete E2E Evaluation workbook in recommended Unified mode.",
        "",
        "[CURRENT DATA FLOW]",
        "Source → Semantic Source Unit → Fact Fragment → Canonical Engineering Requirement → Fact-level Allocation",
        "→ SYS.1/SWE.1/native Requirement Views → SYS.5/SWE.6/Deferred/native Verification Objects",
        "→ E2E Requirements / E2E Evaluation → Review Exchange → 3-AI Evaluation → Human Review / Gold Regression",
        "",
        "[CURRENT VERSION DELTA]",
    ]
    lines.extend(recent.splitlines())
    lines += ["", "[CURATED IMPLEMENTATION EXCERPTS]"]

    symbol_status: dict[str, dict[str, str]] = {}
    for rel, symbols in SYMBOLS.items():
        section, status = _extract_file(rel, symbols)
        if len(lines) + len(section) > MAX_CONTEXT_LINES - 80:
            lines += [f"[CONTEXT LINE BUDGET REACHED BEFORE {rel}; remaining source omitted intentionally.]", ""]
            break
        lines.extend(section)
        symbol_status[rel] = status

    lines += [
        "[CONTEXT INTEGRITY]",
        f"Context line budget: <= {MAX_CONTEXT_LINES}",
        f"Actual lines before footer: {len(lines)}",
        "Included files/symbols are curated. Absence from this pack does NOT prove absence from the full program.",
        "Do not infer API keys, credentials, private endpoint values, or omitted implementation details.",
        "",
        "[INCLUDED FILE HASHES]",
    ]
    for rel in SYMBOLS:
        path = PROJECT_ROOT / rel
        if path.is_file():
            lines.append(f"- {rel}: {_sha256(path)}")
    lines += ["", "[SYMBOL INDEX]"]
    for rel, status in symbol_status.items():
        lines.append(f"- {rel}")
        for sym, loc in status.items():
            lines.append(f"    {sym}: {loc}")

    if len(lines) > MAX_CONTEXT_LINES:
        lines = lines[:MAX_CONTEXT_LINES - 2] + ["[TRUNCATED TO LINE BUDGET]", ""]
    context_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    readme_path.write_text(
        "Requirement Studio — for_h_chat\n"
        "================================\n"
        "This folder supports ad-hoc review in an internal H-Chat environment with a 3-file upload limit.\n\n"
        "Recommended upload set:\n"
        "1. Source input document\n"
        "2. One output/result document you want reviewed\n"
        f"3. {context_path.name}\n\n"
        f"00_RECENT_CHANGES_{version}.txt is a quick version-delta reference.\n"
        "The Context Pack is deliberately curated and size-bounded; it is not authoritative source evidence and is not a full source-code archive.\n",
        encoding="utf-8",
    )
    return recent_path, context_path, readme_path


if __name__ == "__main__":
    for path in build():
        print(path)
