# Requirement Studio 산출물 작성 기준 V0.2 — SWE.1

이 문서는 Requirement Studio가 SWE.1 Word/Excel을 어떤 원칙으로 작성하는지 설명하는 기준 문서입니다.
사람이 보는 `작성 기준` 팝업과 AI Requirement 추출 Prompt가 이 문서를 공통 기준으로 사용합니다.

## 1. 기본 원칙

### 1.1 Source First
- 입력문서가 factual Source of Truth입니다.
- 입력문서에 없는 신호명, 수치, 시간, 상태, 관계를 새로 만들지 않습니다.
- 정보가 부족하거나 충돌하더라도 AI가 임의로 완성하지 않습니다.

### 1.2 내부 데이터와 최종 산출물 분리
- Canonical Requirement 내부에는 분류 근거, Gap/TBD/Conflict, 세부 Behavior, Visual Evidence 등 분석·품질관리 정보를 유지할 수 있습니다.
- 최종 SWE.1 Word/Excel은 일반 엔지니어가 바로 읽고 검토할 핵심 정보만 표시합니다.
- 내부 분석정보를 최종 문서에 그대로 노출해야 한다고 가정하지 않습니다.

### 1.3 Feature / Parent SRS / Atomic Fact / 상세 동작
- Feature: 서로 관련된 SRS를 묶는 상위 기능 단위입니다.
- Parent SRS: 하나의 coherent function/responsibility/state relationship을 표현하는 Requirement 단위입니다.
- Atomic Fact: Parent SRS를 구성하는 Source-backed 최소 사실입니다. Fact가 여러 개라는 이유만으로 Parent SRS를 자동 분할하지 않습니다.
- SRS 분할은 서로 기능적으로 독립하거나 ownership/allocation/change/release를 별도로 관리해야 할 때 검토합니다.
- 상세 동작: 하나의 SRS 내부에서 수행되는 순서/처리를 표현합니다. 내부 Canonical에서는 Behavior Flow 구조를 유지할 수 있으나 최종 문서에서는 일반적인 번호 목록으로 표시할 수 있습니다.

## 2. SRS ID
- Canonical Requirement 순서에 따라 `SRS_001`, `SRS_002` ... 형식으로 부여합니다.
- SRS ID는 Parent Engineering Requirement를 식별하고, Atomic Fact/Fact Fragment는 별도 Trace ID로 관리할 수 있습니다.
- 상위 Feature 자체에 SRS ID를 부여하지 않습니다.

## 3. 분류 — 기능 / 비기능
- 입력문서가 기능/비기능을 명시하면 원문 분류를 우선합니다.
- 명시가 없으면 Requirement의 의무 성격을 기준으로 기능/비기능을 분류할 수 있습니다.
- 분류 판단 근거는 내부 Canonical에 유지할 수 있으나 최종 SWE.1 산출물에는 별도 `분류 근거` 필드로 표시하지 않습니다.
- 명확히 분류하기 어려우면 `검토 필요`로 유지합니다.

## 4. 최종 SWE.1 표시 필드
Word와 Excel의 핵심 표시 필드는 다음 11개를 공통으로 사용합니다.

1. SRS ID
2. 상위 기능
3. 분류
4. 요구사항 내역
5. 동작 조건 / Trigger
6. 작동 명세 정의
7. 사전 조건
8. 예상 결과
9. 검증 기준
10. 출처 / Traceability
11. 기타

## 5. 요구사항 내역
- Software가 무엇을 해야 하는지를 하나의 명확하고 검증 가능한 의무로 기술합니다.
- 원문의 의미를 확장하거나 새로운 동작을 창작하지 않습니다.

## 6. Trigger와 Pre-condition
- Trigger/Activation: Requirement 동작을 발생시키는 사건 또는 조건입니다.
- Pre-condition: Requirement 수행 전에 이미 성립해야 하는 상태입니다.
- 입력문서에 구분 근거가 없으면 임의로 만들어내지 않습니다.

## 7. 작동 명세 정의
- Source에 상세 동작 순서가 있을 때 구조화합니다.
- 내부 Canonical의 BF ID를 최종 문서에 반드시 노출하지 않아도 됩니다. 일반 엔지니어가 읽기 쉽게 `1.`, `2.`, `3.` 순서로 표현할 수 있습니다.
- 상세 Flow가 없으면 `입력문서에서 추가 작동 명세를 확인할 수 없음`으로 표시할 수 있습니다.

## 8. 예상 결과 / 검증 기준
- 예상 결과는 수행 후 Source에서 확인되는 Output, State Change, Status, Message 등을 기록합니다.
- 검증 기준은 Pass/Fail을 판단할 수 있는 수치, 상태, 조건, 허용범위 등입니다.
- Source에 없는 기대값이나 기준을 상식으로 보완하지 않습니다.

## 9. 출처 / Traceability
- 각 SRS는 가능한 범위에서 Source Document, Source Location, Source Evidence를 유지합니다.
- Excel의 `02_Traceability`는 `입력 Source → SWE.1 SRS → SWE.6 Test Case` 연결을 한눈에 확인하는 End-to-End View로 사용합니다.

## 10. 기타
- Requirement와 직접 관련된 원본 Figure, Diagram, Table, 기타 보조자료가 있으면 기입합니다.
- 원본 자료를 우선 사용하며 Source에 없는 상태, 값, 연결관계를 새로 만들지 않습니다.
- 관련 자료가 없으면 공란으로 둘 수 있습니다.

## 11. 최종 산출물에서 제거되는 정보
다음 항목은 V0.35부터 최종 SWE.1 Word/Excel의 별도 필드로 표시하지 않습니다.
- 분류 근거
- 평가 방안
- 예외 조건
- 관련 자료 (기타로 통합)
- Gap / TBD

단, 필요한 정보 자체를 폐기하는 것은 아닙니다.
- 분류 근거와 Gap/TBD/Conflict는 내부 Canonical/Review Flag로 유지할 수 있습니다.
- 평가 방법은 SWE.6 Test Specification 영역에서 다룹니다.
- 독립적으로 검증해야 하는 예외 동작은 별도 Requirement로 분리하는 것을 우선합니다.

## 12. SWE.1 Excel Workbook
V0.35 기본 Sheet는 다음 3개입니다.
- `00_Overview`
- `01_SWE1`
- `02_Traceability`

별도 `Behavior_Flow`, `Gap_TBD` Sheet는 생성하지 않습니다. Behavior 정보와 품질관리 정보는 Canonical 내부에서 유지합니다.

## 13. V0.35 산출물 범위
- `SWE.1 문서 (Word 파일)`: 실제 DOCX를 생성합니다.
- `SWE.1 문서 (엑셀 양식)`: 실제 XLSX를 생성합니다.
- `SWE.6 문서 (엑셀 양식)`: 동일 Canonical Requirement를 입력으로 Local SWE.6 Exporter에서 실제 XLSX를 생성합니다.
- 세 산출물은 동일 Canonical Requirement에서 파생됩니다.

## 14. 파일명 규칙
- SWE.1 Word/Excel 결과 파일명 끝은 `YYMMDD_V0.0` 형식을 사용합니다.
- 예: `SWE.1 요구사항 정리_<원본문서>_260926_V0.0.docx`
- 예: `SWE.1 요구사항 명세_<원본문서>_260926_V0.0.xlsx`


## V0.82 Integrated Output Authoring

- Legacy SWE.1/SWE.6 outputs remain domain-specific artifacts and are not replaced.
- `통합_요구사항 명세서` preserves Canonical requirements across SYS.1/SWE.1/native domains.
- `통합_테스트 명세서` preserves SYS.5/SWE.6/deferred/allocation-pending/external/native verification objects.
- Parent requirement text is traceability context; executable scope is fact-fragment authoritative.
- Source-missing test values, thresholds, DB values, variants, or results are never synthesized.
- Output Value / PASS-FAIL / Comment / Capture stay physically blank before execution.
