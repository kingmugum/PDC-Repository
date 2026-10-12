# ALIRA Requirement Extraction Evaluation Guide

## 1. Reference / Edge / Blind split

- Reference Examples: ALIRA may read these to learn target structure/pattern.
- Edge-case Examples: intentionally ambiguous/missing/conflicting specs used to verify No Hallucination + Gap handling.
- Blind Evaluation: ALIRA must not see these beforehand; use them to test generalization.

Do not use one document as both a prompt reference and a blind evaluation target.

## 2. Suggested score (100)

- Source Traceability: 25
- No Hallucination / Gap handling: 25
- Atomicity / testability: 20
- Coverage of source behaviors: 20
- Contract/schema compliance: 10

Requirement count itself is not a quality score.

## 3. v0.14 automatic evaluation scope

The app can automatically evaluate:
- valid JSON/contract shape
- required fields
- Explicit/Implicit enum
- source evidence presence
- confidence format
- missing information representation

The app cannot automatically prove semantic completeness or absence of hallucination.
Those require source-aware ALIRA review and/or human/blind evaluation.

---

# V0.68 3-AI Automatic Evaluation

## Recommended flow
1. Generate the selected SWE.1 or SWE.6 artifact.
2. Build the Review Exchange from the same run.
3. Create `automatic_evaluation/06_EVALUATION_EVIDENCE.json` from Source + Review Package + actual artifact + change decision + summary.
4. Send the exact same evidence independently to GPT, Gemini and Claude.
5. Persist each provider JSON/TXT immediately when that reviewer completes; `00_EVALUATION_STATUS.*` remains visible during execution.
6. Build finding-level Consensus.
7. Build `05_EVALUATION_RESULT.json`.
8. Render the consolidated hand-off text and split it into `final_result/FINAL_RESULT_###.txt` at 150 lines per file.

## Consensus rule
- 3 reviewers: STRONG_CONSENSUS
- 2 reviewers: CONSENSUS
- 1 reviewer: SINGLE_REVIEWER
- A finding seen by only one reviewer is not discarded; it remains a review candidate.
- FAIL/HOLD cannot be hidden by a 2:1 vote.
- If fewer than all three configured reviewers complete, evaluation completeness is PARTIAL and Official Release is HOLD.

## Tool Quality vs Artifact Readiness
Keep these separate. A Source may correctly lack external criteria or independent observability; correct deferral can be Tool Quality PASS while Artifact Readiness remains REVIEW_REQUIRED.

## Deterministic-before-AI principle
Use code for facts that can be directly checked:
- XLSX result cells physically blank
- workbook headers/sheet presence
- TC/SRS identifier match
- Source Fact allocation conflict
- SHA-256
- schema/reference integrity
- regression baseline availability

Use AI reviewers for semantic judgments:
- Source fidelity / missing behavior
- fragment ownership appropriateness
- allocation rationale quality
- cross-domain semantic leakage
- test-intent quality / over-generation

## Final hand-off
The `final_result` folder is intended for direct upload into a subsequent development/review chat when one long TXT is inconvenient. The split changes only file boundaries, not finding semantics.


## V0.68 persistence completion contract
- `automatic_evaluation` must never stay empty after evaluation starts.
- `00_EVALUATION_STATUS.json/.txt` and `06_EVALUATION_EVIDENCE.json` are visible before all reviewers complete.
- `99_EVALUATION_COMPLETE.ok` is written only after required output files are re-opened/size-checked.
- The UI may log completion only after this verification succeeds.


## V0.69 GUI progress semantics

The `결과 품질 검토` tab treats `00_EVALUATION_STATUS.json` as the only progress truth. Percentages are workflow-stage percentages, not provider token percentages: 5 Evidence, 15-75 provider review, 82 Consensus, 90 final result, 96 output verification, 100 verified completion.


## V0.71 Unified evaluation scope

Default scope: `unified`. Review Source → Canonical → SWE.1 → Allocation → Child Intent → SWE.6 → actual artifacts as one chain. Do not issue a defect only because an artifact that the user did not select/generate is absent. Use `CROSS_OUTPUT` for loss, leakage or contradiction between outputs. Final hand-off remains only `final_result/FINAL_RESULT_###.txt`; parts are capped at 110 lines and include a completeness audit.


## V0.72 Handoff and provenance rules
- FINAL_RESULT is self-identifying; users only need to hand off all FINAL_RESULT_###.txt parts.
- Structured provenance tokens are collected from owned fragments/atoms/table facts/fact allocations via one value collector.
- Canonical critical facts have a separate fragment-ownership gate; broad provenance closure does not hide incomplete fragment ownership.
- REVIEW_NEEDED Semantic Units are OPEN dispositions, not terminal success states.


## V0.73 exact fragment ownership precision

- Treat exact ownership as the union of all exact Source Fact Fragments linked to the same SRS.
- Use `owned_fragment_fact_token_sources` as deterministic evidence for token-to-fragment ownership.
- Do not create an ownership finding merely because an identifier and timing constraint live in different fragments when the union proves both are owned.
- Do not accept broad structured roll-up values as exact ownership when the exact fragment literal does not contain them.
- Critical-fact completion is Source-bounded: only already-matched Source locations with literal critical-token evidence are eligible.
