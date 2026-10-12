# Requirement Studio V0.93

## User-guided Guideline Mining + Test Decomposition Refinement
V0.93 keeps the V0.92 Source-backed structured Basic Functional design and adds the first explicit user-decision Guideline Mining loop.

- human-facing review reasons are localized to Korean while raw Trace/JSON values stay unchanged
- E2E Requirement `요구사항 내역` is numbered by semantic unit inside the same cell (① ② ③...)
- explicit binary semantic branches may split into independent TCs when each branch has a Source-backed verdict
- distinct timing checkpoints are split into independent TCs when each timing window has its own Source-backed start/acceptance logic
- approved decision rules live in `policy/guideline_rule_registry.json`
- explicit decision examples live in `policy/decision_example_registry.json`
- `core/guideline_mining.py` extracts factors, mines candidate principles and searches counterexamples
- mined candidates never auto-promote; only HUMAN_APPROVED registry rules affect generation
- exact-field trace gate is hardened so a grouped property cannot PASS when one populated vector lacks an exact Fact Fragment
- mojibake README TXT files are removed from `api_keys/` and `input/`; both folders retain `.gitkeep`

V0.93 still does **not** auto-expand EP/BVA/Fault Injection.

See `START_HERE.txt`, `docs/V0.93_MANUAL_DELTA.txt`, and `Requirement_Studio_Requirements_Management_rev77.xlsx`.
