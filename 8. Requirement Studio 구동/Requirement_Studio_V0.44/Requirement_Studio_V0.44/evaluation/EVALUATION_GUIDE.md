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
