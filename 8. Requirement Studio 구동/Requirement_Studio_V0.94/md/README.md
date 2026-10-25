# Requirement Studio V0.94

V0.94 keeps the V0.93 user-guided Guideline Mining loop and hardens both human-facing E2E Requirements and Basic Functional semantic integrity.

## Human-facing requirement changes
- Behavior Definition shows actions only; duplicated Source excerpts and internal `step/action` authoring tokens are removed.
- Traceability is location-first and labels evidence as `[문서]` or `[그림]`.
- Multi-criterion / O-X acceptance logic is structured in the same cell.

## Semantic integrity hardening
- Request/Response enum pairs must preserve Source semantic mapping.
- Generated identifiers and enum values must respect literal lexical boundaries.
- Split timing checkpoints retain the complete Source-backed prerequisite chain.
- Exact Fact Trace does not imply semantic correctness; semantic mismatch routes to REVIEW_REQUIRED.

## Guideline Mining boundary
Decision Example → Factors → Candidate/Counterexample remains auditable. Only HUMAN_APPROVED rules affect generation. No opaque auto-promotion or self-modification is allowed.

V0.94 still does **not** auto-expand EP/BVA/Fault Injection.

See `START_HERE.txt`, `docs/V0.94_MANUAL_DELTA.txt`, and `Requirement_Studio_Requirements_Management_rev78.xlsx`.
