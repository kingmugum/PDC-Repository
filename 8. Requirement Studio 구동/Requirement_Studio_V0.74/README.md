# Requirement Studio V0.74


## V0.74 Source-bounded Critical Facts / Parent Containment / Visual Gap

V0.74 keeps the Unified End-to-End evaluation flow and refines V0.73 trace ownership based on the next blind run.

- Timing literals such as `5초`, `5 초`, `500ms` are recognized without misclassifying communication bitrate such as `500 Kbit/s`.
- Critical Fact completion may recover a literal fragment from a neighboring Semantic Unit only when it is on an explicitly cited Source location and contains the missing critical token.
- Clear shared-fragment leakage is resolved to the materially dominant parent SRS; ambiguous legitimate sharing stays `SHARED_REVIEW_REQUIRED`.
- Requirements already declaring diagram/image dependency receive `UNANALYZED_VISUAL_ASSET` Gap/TBD records when Vision evidence is unavailable; visual semantics remain UNKNOWN.
- Explicit OPEN/non-terminal `REVIEW_NEEDED` is treated as Artifact Readiness/Release Governance rather than Tool Quality defect by itself.
- Current Requirements baseline is `Requirement_Studio_Requirements_Management_rev58.xlsx`; rev57 approved rows were preserved and V0.74 requirements were appended.

## V0.73 Exact Fact Fragment Ownership Precision

V0.73 keeps the Unified End-to-End evaluation flow and hardens Source Fact Fragment ownership precision based on V0.72 FINAL_RESULT findings.

- Exact critical-fact ownership is evaluated over the union of all exact Source Fact Fragments linked to one SRS.
- Audit evidence exposes `owned_fragment_fact_token_sources` so every owned signal/timing/enum/retry token can be traced to one or more fragment IDs.
- Critical-fact-aware completion may add a missing fragment only inside already-matched Source Semantic Units / explicitly cited Source locations and only when the literal critical token is present.
- Broad structured roll-up data cannot create exact ownership for a value absent from the exact fragment literal.
- OPEN Semantic Units, pending SW allocation, unresolved Source conflicts, and missing approved Gold remain review/governance states and are never auto-closed.
- Historical V0.73 baseline was `Requirement_Studio_Requirements_Management_rev57.xlsx`; current V0.74 baseline is rev58.

## V0.72 Unified End-to-End 3-AI Evaluation

V0.72 retains the removal of the old manual H-Chat three-file evaluation constraint from the automatic review path. The default review scope is now `Unified End-to-End`: Source → Canonical/SRS → SWE.1 Word/Excel → Allocation/Eligibility → Child Intent → SWE.6 Excel → Actual Artifact/QA/Regression.

- SWE.1/SWE.6 focused modes remain available only for targeted debugging.
- Automatic evaluation can include every generated review artifact; there is no three-file hand-off limit.
- The evaluator builds one compact Trace/Evidence Graph and artifact snapshots to reduce duplicate token use.
- DOCX table contents are included in evidence, not only paragraphs.
- Missing artifacts that were not selected/generated are not treated as defects.
- `FINAL_RESULT` includes a Completeness Audit proving provider finding occurrences were mapped into consensus.
- `final_result` is split at a maximum of 110 lines per TXT.

## V0.69 결과 품질 검토 진행상황 / SWE.6 평가 Finding 보완

V0.69는 메인 STEP 1~7과 별도로, `결과 품질 검토` 탭에서 3-AI 자동평가의 후속 진행상황을 확인할 수 있게 합니다.

- 단계 기반 자동평가 진행률: Evidence 5% → Reviewer 15~75% → Consensus 82% → Final Result 90% → 파일 검증 96% → 완료 100%
- GPT / Gemini / Claude 각각 `대기 / 진행 중 / 완료 / 실패 / 비활성` 상태 표시
- 완료 후 Tool Quality / Artifact Readiness / Official Release Gate 표시
- `final_result` part 개수와 `final_result 열기` 버튼 제공
- `00_EVALUATION_STATUS.json`을 단일 진행상태 Source로 사용
- V0.68 FINAL_RESULT에서 확인된 `최초B+` Korean/ASCII token boundary ownership 누락 방지
- Mixed-domain Parent expected-result 문구가 SWE.6 TC 설명에 다시 섞이는 경로 차단
- Requirements baseline `rev55`는 byte-for-byte 변경 없음

## V0.68 자동평가 저장 신뢰성 / Gold 외부 폴더 정리

V0.68은 V0.67의 단일 3-AI 자동평가 구조를 유지하면서 실제 사용자 Run에서 확인된 결과 저장 가시성/완료 검증 문제를 보강합니다.

- 자동평가 시작 즉시 `automatic_evaluation/00_EVALUATION_STATUS.json/.txt` 생성
- `06_EVALUATION_EVIDENCE.json`도 `automatic_evaluation` 내부에 저장
- GPT/Gemini/Claude가 각각 끝나는 즉시 JSON/TXT 저장
- 결과 파일은 atomic write + flush/fsync 후 공개
- 모든 필수 파일/크기 검증 후에만 `3-AI 자동 평가 완료` 로그 출력
- 검증 완료 시 `99_EVALUATION_COMPLETE.ok` 생성
- `final_result` 150줄 분할 유지
- 프로그램 바깥 `Requirement_Studio_Gold_Sources` 폴더 생성 제거
- 선택적 Gold 등록은 프로그램 내부 `review_exchange/gold_sources/user_registered` 사용
- Requirements baseline `rev55`는 내용 변경 없이 그대로 유지

자동평가 진행 중에는 폴더가 비어 있지 않아야 하며, 상태는 `00_EVALUATION_STATUS.txt`에서 바로 확인할 수 있습니다.

## V0.67 Reviewer 기능 단일화

V0.67은 V0.66의 실제 3-AI 자동 평가와 V0.45부터 남아 있던 Legacy Reviewer 설정 UI가 중복되는 문제를 정리합니다.

- 실제 Reviewer E2E를 수행하지 않던 `표준 검토` / `중복 검토` / `정밀 검토` 및 1차·2차·3차 Reviewer 선택 UI 제거
- 평가 모드는 `3-AI 자동 평가` / `수동 평가 패키지만 생성` / `평가하지 않음`으로 단일화
- 자동: Review Exchange + GPT/Gemini/Claude 독립 평가 + Consensus/final_result
- 수동: Review Exchange만 생성, 외부 전송 없음
- 없음: Review Exchange/평가용 추가 산출물/외부 호출 모두 생략
- Requirements Baseline을 예외적으로 `rev55`로 갱신하고 FR-316을 실제 동작 기준으로 교체, FR-362~365 추가


V0.66은 V0.65 SWE.6 평가에서 남은 **Fragment Trace / 최소 Ownership / Cross-domain TC Scope**를 보강하고,
수동 H-Chat 평가 절차를 **GPT + Gemini + Claude 독립 3-AI 자동 평가**로 연결한 Hardening Build입니다.

핵심 원칙은 동일합니다.

> Source에 없는 사실은 만들지 않고, Source에 존재하는 사실은 Fragment → Canonical/SRS → Child Intent → SWE.6까지 동일한 identity로 전달하며, 평가 AI는 생성 AI와 독립적으로 동일 Evidence를 검토합니다.

## V0.66 핵심 변경

1. **Fragment → Child Intent Trace 완결**
   - 기존 Atomic Behavior가 Source Fragment와 일치하면 `source_fact_fragment_id`를 강제 전파합니다.
   - Fragment를 소유하면서 Child Intent에 Fragment ID가 없으면 Tool Quality finding으로 검출합니다.

2. **Minimum Material Fragment Ownership**
   - Composite paragraph 전체를 소유하지 않고 Canonical behavior와 직접 관련된 최소 Fragment만 소유합니다.
   - receive/store 또는 receive/control처럼 하나의 요구사항을 구성하는 상보적인 clause는 함께 보존할 수 있습니다.

3. **Mixed-domain SWE.6 TC Scope 제한**
   - 한 SRS에 SWE.6 + SYS.5/External/Allocation Pending fact가 섞여 있어도 TC는 SWE.6 Eligible fact만 주장합니다.
   - 제외된 fact는 Audit/Deferred 근거로 남습니다.

4. **Capture Export Contract**
   - R:U Result boundary 유지.
   - U열 `Capture CANoe (Optional)` header 존재 자체를 실제 XLSX에서 검증합니다.
   - Output Value / PASS-FAIL / Comment / Capture는 실행 전 모두 물리적 Blank여야 합니다.

5. **3-AI 자동 평가**
   - Review Package 생성 후 GPT / Gemini / Claude가 동일 Evidence를 독립 평가합니다.
   - 기본 transport는 기존 H-Chat입니다.
   - `config/evaluation_api_config.json`에서 `direct_api`로 변경할 수 있습니다.
   - API Key는 ZIP에 포함하지 않습니다.

6. **Structured Result + Consensus**
   - 각 Reviewer의 JSON/TXT를 저장합니다.
   - Consensus Finding을 3/3, 2/3, 1/3으로 구분합니다.
   - 일부 Reviewer만 성공한 경우 자동 Official Release PASS를 금지합니다.

7. **final_result 110줄 자동 분할**
   - `automatic_evaluation/final_result/FINAL_RESULT_001.txt ...`
   - 파일당 최대 110줄.
   - `manifest.json`에 line count와 SHA-256을 기록합니다.

## 자동 평가 결과 위치

```text
review_exchange/<run>/automatic_evaluation/
├─ 01_GPT_EVALUATION.json / .txt
├─ 02_GEMINI_EVALUATION.json / .txt
├─ 03_CLAUDE_EVALUATION.json / .txt
├─ 04_EVALUATION_CONSENSUS.json / .txt
├─ 05_EVALUATION_RESULT.json
├─ AUTOMATIC_EVALUATION_MANIFEST.json
└─ final_result/
   ├─ FINAL_RESULT_001.txt
   ├─ FINAL_RESULT_002.txt ...
   └─ manifest.json
```

## 설정

- GUI 기본값: `3-AI 자동 검토 (추천)` + 자동 평가 ON
- 자동 평가 OFF: Review Package까지만 생성, 외부/H-Chat 전송 없음
- 기본 transport: `hchat`
- direct API: `config/evaluation_api_config.json` 참고
- 상세: `docs/V0.68_AUTOMATED_EVALUATION_SETUP.txt`

## Regression

- 전체 Python regression: 95 tests
- 신규: `tests/test_v066_evaluation_automation_traceability.py`
- 실제 Official Release 판단은 신규 Source E2E + 승인 Gold regression 결과와 별도로 수행해야 합니다.


## V0.72 Traceability / Handoff hardening
- FINAL_RESULT self-identifies Version, Evaluation Mode, Source filename/SHA-256, Run ID, evaluated artifacts and Evidence SHA-256.
- Every 110-line FINAL_RESULT part repeats compact identity metadata, so no separate sample title/message is required.
- Provenance token audit uses one structured Source-fact value stream and no longer serializes metadata keys as facts.
- Critical Canonical signal/timing/enum/retry facts must be owned by an exact Fact Fragment or fragment-linked Child Intent.
- Eligible Semantic Units with REVIEW_NEEDED are explicitly OPEN/non-terminal until linked or intentionally dispositioned.
