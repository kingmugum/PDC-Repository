# Requirement Studio 산출물 작성 기준 V0.1 — SWE.6

이 문서는 Requirement Studio가 SWE.1의 Canonical Requirement를 기반으로 SWE.6 Software Qualification Test Excel을 어떤 원칙으로 생성하는지 정의합니다.
SWE.6 파일 생성은 AI Provider별 별도 Prompt가 아니라 Requirement Studio의 공통 Local Exporter에서 수행합니다.

## 1. 목적과 범위
- SWE.6는 SWE.1 Software Requirement를 검증하기 위한 Test Specification 초안을 생성합니다.
- Requirement Studio는 Test Specification 영역까지만 자동 작성합니다.
- 실제 시험 후의 Output Value, PASS/FAIL, Comment, Capture는 사람이 작성하며 최초 생성 시 공란으로 둡니다.
- SWE.1과 SWE.6는 SRS ID를 기준으로 추적성을 유지합니다.

## 2. 공통 원칙
### 2.1 Source First
- Canonical Requirement와 그 Source Evidence가 factual Source of Truth입니다.
- Source에 없는 Signal Name, 수치, 시간, 상태, 시험 Tool, Tolerance를 새로 만들지 않습니다.
- 부족하거나 애매한 정보는 공란 또는 `검토 필요`로 유지합니다.

### 2.2 Provider 독립성
- GPT, Gemini, ALIRA, 기타 Provider 중 무엇을 사용했는지와 무관하게 같은 SWE.6 Exporter를 사용합니다.
- AI Provider는 Canonical Requirement를 만드는 단계에 영향을 줄 수 있지만, Canonical Requirement 이후의 SWE.6 Workbook 구조와 Mapping Rule은 동일합니다.
- Test Case ID, Sheet 구조, Result 공란 정책, Test Design Technique 선정 규칙은 Local Rule로 적용합니다.

### 2.3 Traceability
- 하나의 SRS는 0개, 1개 또는 여러 개의 Test Case로 파생될 수 있습니다.
- 각 Test Case는 주된 SW Requirement ID를 반드시 유지합니다.
- 정보 부족으로 Test Case 생성이 어려운 Requirement는 버리지 않고 `검토 필요`로 남깁니다.

## 3. Workbook 구조
SWE.6 V0.1은 다음 4개 Sheet를 사용합니다.
1. `표지`
2. `0_변경이력`
3. `1_테스트요약`
4. `2_테스트 케이스`

## 4. 표지 작성 기준
- 문서명: `SWE.6 소프트웨어 적격성 테스트`
- 본문 제목: `소프트웨어 적격성 테스트`
- 영문 제목: `Software Qualification Test`
- 산출물 ID: 입력문서에 명확한 ID가 있을 때만 작성합니다. ID 안에 명시적인 SWE.1 표기가 있으면 SWE.6 표기로 변환할 수 있습니다. 식별 근거가 없으면 공란입니다.
- 개정번호: 최초 `V.0.0`
- 개정일자: 파일 생성일
- 차종/OEM: 입력문서에서 명시적으로 식별되는 경우만 작성합니다.
- 프로젝트명: `프로젝트명`, `Project Name`처럼 명시적으로 식별되는 짧은 명칭만 사용합니다. 서술형 문장을 프로젝트명으로 추정하지 않습니다.
- 작성/검토/승인: 공란
- 문서 상태: Dropdown `Draft / Released / Restricted / Expired`, 최초값 `Draft`
- 배포 날짜: 최초 공란

## 5. 변경이력 작성 기준
- 번호 1~10 행을 기본 제공합니다.
- 1번 행: 생성일 / `V.0.0` / `초안 작성` / 개정자 공란
- 2~10번 행: 번호만 유지하고 나머지는 공란으로 둡니다.

## 6. 테스트 요약 작성 기준
### 6.1 평가 대상
- Project Name: 표지와 동일한 명시 프로젝트명
- Test Level: `소프트웨어 적격성 테스트`
- Hardware / Software / Mechanical: 입력문서에 명시된 경우만 작성하고 없으면 공란
- 입력물: `소프트웨어 요구사항 명세(SWE.1)`

### 6.2 테스트 환경
- Source에 명시된 Test Environment 텍스트가 있으면 해당 내용을 우선 사용합니다.
- 원본의 시험환경 사진/구성도 자동 선택 및 재배치는 후속 고도화 대상으로 둡니다.
- 환경정보가 없으면 `테스트 환경 구성도 또는 대표 사진이 필요합니다.`라는 Placeholder를 표시합니다.
- AI가 임의로 PC/CANoe/Oscilloscope 등의 시험환경 그림을 새로 만들지 않습니다.

### 6.3 기능/비기능 Requirement 요약
- SWE.1에서 확정된 SRS를 기능/비기능 영역으로 분리합니다.
- 컬럼: `번호 / 분류 1 / 분류 2 / 분류 3 / 식별자 / 테스트`
- 분류1은 상위 Feature를 우선 사용합니다.
- 분류2/분류3 계층이 Source나 Canonical 구조에 없으면 억지로 채우지 않습니다.
- 식별자는 SWE.1의 SRS ID를 사용합니다.
- 테스트 상태는 `대상 / 비대상 / 검토 필요`를 사용합니다.
- 불명확한 항목을 임의로 `비대상`으로 버리지 않고 `검토 필요`로 남깁니다.

## 7. Test Case 작성 기준
### 7.1 SW Requirement ID
- SWE.1의 SRS ID를 그대로 사용합니다.

### 7.2 Test Case ID
- 별도 Naming Rule이 없으면 `TC_001`, `TC_002` ... 순차 ID를 사용합니다.
- 회사별 Naming Rule은 후속 Config로 교체할 수 있도록 유지합니다.

### 7.3 Methods for Testing / Method for deriving TC
- 기본 Method는 `요구사항 기반 테스트`입니다.
- 세부 Test Design Technique은 Requirement 성격을 보고 Local Rule로 선택합니다.
  - Threshold/Timing/Min/Max: `경계값 분석`
  - Valid/Invalid/Range: `동등분할`
  - State/Mode Transition: `상태전이 테스트`
  - 별도 기법이 명확하지 않으면 `요구사항 기반 테스트`만 사용합니다.
- 모든 Requirement에 경계값 분석을 강제하지 않습니다.

### 7.4 Test Case Name
- 기능과 검증 목적을 몇 단어로 요약합니다.
- 원문 Requirement 제목이 충분히 짧으면 재사용할 수 있습니다.

### 7.5 Test Case Description
- 무엇을, 어떤 조건에서, 어떤 결과로 검증하는지 설명합니다.
- Source 의미를 확장하지 않습니다.

### 7.6 Test Preparation
- SWE.1의 Pre-condition / Initial State / Input Condition을 Test 준비상태로 Mapping합니다.
- 구조: `Description / Variable / Compare / Value`
- Source에 Variable/Signal Name이 없으면 임의 이름을 만들지 않습니다.
- Description은 존재하지만 Variable/Compare/Value를 Source에서 직접 도출할 수 없으면 해당 셀은 `N/A`로 표시합니다. 의도적으로 사용자 입력용으로 비워 둔 영역에는 `N/A`를 넣지 않습니다.

### 7.7 Test Execution
- SWE.1의 Trigger 및 Behavior를 시험 행위 관점으로 Mapping합니다.
- 구조: `Description / Variable / Compare / Value`
- BF를 단순 복사하지 않고 실제 시험에서 인가/변화시키는 조건 중심으로 표현합니다.

### 7.8 Expected Result
- SWE.1의 Expected Result와 Verification Criteria를 기반으로 작성합니다.
- 구조: `Description / Variable / Compare / Value`
- Compare/Value는 Source에서 직접 판단 가능한 경우에만 작성합니다.
- `Tolerance lower / Tolerance upper` 컬럼은 V0.34에서 제거합니다.

## 8. Test Result 작성 기준
다음 항목은 최초 생성 시 반드시 공란입니다.
- Output Value
- PASS / FAIL
- Comment
- Capture CANoe (Optional)

V0.34에서는 `Capture Environment` 컬럼을 제거합니다.

Requirement Studio는 시험 수행 전 PASS/FAIL을 미리 판정하지 않습니다.

## 9. Gap / Testability 처리
- 검증 가능 정보가 충분하면 `대상`으로 처리합니다.
- 범위에서 명시적으로 제외된 근거가 있을 때만 `비대상`을 사용할 수 있습니다.
- 정보 부족 또는 모호성 때문에 검증방법을 확정하기 어려우면 `검토 필요`로 둡니다.
- 부족한 사양을 AI 상식으로 채워 Test Case를 완성하지 않습니다.

## 10. SWE.1 → SWE.6 Mapping
- SRS ID → SW Requirement ID
- Feature → 분류 1/2
- Requirement 핵심 → 분류 3 / Test Case Name
- Trigger → Test Execution
- Pre-condition → Test Preparation
- Behavior/BF → Test Execution Sequence
- Expected Result → Expected Result Description
- Verification Criteria → Compare / Value
- Signal/Parameter → Variable
- Threshold → Value / Test Design Technique
- Variable/Compare/Value 미도출 → 해당 설명이 존재하는 경우 `N/A`
- Gap/TBD → 검토 필요 / TC 생성 보류

## 11. V0.34 MVP 경계
- SWE.6 Excel 실제 생성을 지원합니다.
- 표지/변경이력/테스트요약/테스트케이스 4개 Sheet를 생성합니다.
- 표지 상단 제목 블록은 산출물 ID/개정번호/개정일자의 3행 높이와 맞춰 정렬합니다.
- 테스트케이스는 2행 Group Header(Test ID / Test Input / Test Execution / Test Expect Result / Test Result / Etc)와 3행 상세 Header의 2단 구조를 사용합니다.
- `Tolerance lower`, `Tolerance upper`, `Capture Environment` 3개 컬럼은 사용하지 않습니다.
- Variable/Compare/Value 컬럼이 데이터 전체에서 `N/A`만 가지면 열 너비를 약 8로 축소합니다.
- Test Case Draft는 Canonical Requirement를 기반으로 Local Rule로 생성합니다.
- 원본 Test Environment 이미지의 자동 선택/삽입, 복잡한 다중 TC 최적화, 회사별 TC Naming Config는 후속 고도화 대상입니다.
- 실제 Test Result는 생성하지 않습니다.


## 12. V0.34 산출물 파일명
- 최종 SWE.1 Word / SWE.1 Excel / SWE.6 Excel 파일명 끝은 `YYMMDD_V0.0` 형식을 사용합니다.
- 예: `SWE.6 적격성 평가_<원본문서>_260926_V0.0.xlsx`
- 세부 시각/마이크로초 숫자는 붙이지 않습니다. 같은 원본문서/날짜/버전으로 다시 생성하면 동일 경로를 사용합니다.

## 13. V0.60 SWE.6 품질 감사 / Deferred Intent

### 13.1 03번 평가 산출물 선택
V0.60부터 Review Exchange의 03번 산출물은 SWE.1 Word 또는 SWE.6 Excel 중 하나를 선택할 수 있습니다.
SWE.6 Mode에서는 Source + Review Package + 실제 SWE.6 Excel을 비교합니다.

### 13.2 Interface Fact Allocation Gate
CAN/LIN/Ethernet bitrate, NM support처럼 Source가 interface fact만 제공하는 경우 Software implementation responsibility가 명시되지 않았다면 SWE.6 TC를 자동 생성하지 않습니다.
`INTERFACE_FACT_PENDING_SW_ALLOCATION`으로 보류하고 System/Interface allocation review 대상으로 남깁니다.

### 13.3 Parent/Child Atomic Intent
하나의 SRS에 여러 Source-backed Atomic Behavior가 있더라도 자동으로 SRS/TC를 기계적으로 분리하지 않습니다.
대신 각 Atomic Behavior를 `source_backed_child_intents`로 보존하여 하나의 generic TC PASS가 모든 behavior를 검증한 것으로 오해되지 않도록 합니다.

### 13.4 Expected Result Source Fidelity
Expected Result Description은 Source-backed 핵심 behavior/value/prohibition을 가능한 범위에서 직접 보존합니다.
Source에 없는 Signal, DB 값, timeout, failure injection 값은 생성하지 않습니다.

### 13.5 Deferred Intent Reason Code
Dedicated concrete TC를 만들지 못한 Test Intent는 다음 reason code를 사용합니다.
- `SOURCE_INSUFFICIENT`
- `EXTERNAL_SPEC_REQUIRED`
- `ALLOCATION_PENDING`
- `EXPORTER_CAPABILITY_PENDING`
- `HUMAN_REVIEW_REQUIRED`

`Intent Coverage` 수치가 낮다는 이유만으로 TC를 추가하지 않습니다. 왜 Deferred인지 audit 가능해야 합니다.

### 13.6 `3_Deferred Intent` Sheet
V0.60 SWE.6 Workbook은 다음 5개 Sheet를 사용합니다.
1. `표지`
2. `0_변경이력`
3. `1_테스트요약`
4. `2_테스트 케이스`
5. `3_Deferred Intent`

`3_Deferred Intent`는 SRS ID, Test Intent, Reason Code, Reason Detail, Source/External Dependency, Human Review Required를 표시합니다.

### 13.7 SWE.6 Export Preservation Audit
Review Package는 `swe6_export_preservation_audit`를 통해 아래 항목을 점검합니다.
- Eligible SRS와 Generated TC의 scope
- Source Semantic Unit / Atomic Behavior provenance
- Test Intent / Deferred reason code
- SRS → TC Trace
- 실제 Excel의 TC ID / SRS ID 정합성
- 생성 시 Output Value / PASS-FAIL 공란 유지

## 14. V0.61 Deferred Governance / Fact-level Allocation / Child Intent Audit

V0.61은 SWE.6 초안의 `TC 존재 여부`와 `검증 의도/보류 이유의 완결성`을 분리합니다.

### 14.1 Allocation Pending
`swe6_eligibility = Deferred pending SW allocation`이면 최소 하나 이상의 Deferred Intent를 생성합니다.
빈 배열은 완료 상태가 아닙니다. reason code는 `ALLOCATION_PENDING`이어야 합니다.

### 14.2 Cross-domain Source Fact
Electrical / Environmental / Manufacturing / Mechanical Fact가 한 Parent에 함께 있어도 자동 SRS Split하지 않습니다.
각 Source Fact는 `fact_level_allocations`로 별도 Verification Domain을 보존하며, 복수 domain bundle은 Review 대상으로 표시합니다.

### 14.3 Child Intent Disposition
Parent TC 하나가 모든 Atomic/Child Intent를 자동으로 검증한 것으로 보지 않습니다.
Child Intent는 `COVERED_BY_GENERIC_TC`, `DEFERRED`, `REVIEW_REQUIRED` 중 하나의 상태를 가지며 related TC / reason 정보를 유지합니다.

### 14.4 DERIVED Verification Method
Static Analysis / Code Review / Configuration Review 등 Source에 직접 적히지 않은 검증 방법은 `DERIVED 후보`로만 제안합니다.
Source Requirement 또는 Source Fact로 표현하지 않습니다.

### 14.5 Workbook
V0.61 Workbook은 다음 6개 Sheet를 사용합니다.
- 표지
- 0_변경이력
- 1_테스트요약
- 2_테스트 케이스
- 3_Deferred Intent
- 4_Source_Intent_Audit

## 15. V0.62 Source Fact Single-Truth / Allocation Inheritance

V0.62는 `Source에 없는 값은 생성하지 않는다` 원칙을 유지하면서, Source Table에 이미 존재하는 Signal/Parameter/Enum/Timing/Range를 놓치지 않도록 Fact Index를 사용합니다.

### 15.1 Parent / Fact Allocation
- Parent Pending이면 Fact도 기본 Pending 상속
- Explicit SW Allocation Evidence가 있을 때만 Fact-level Eligible Override 허용
- Parent 자동 Split 금지

### 15.2 Source Table Fact Join
HIGH-confidence 자동 Join 조건:
- linked Semantic Source Unit 또는
- exact identifier overlap

숫자 coincidence만으로 Join하지 않습니다.

### 15.3 Child Intent Status
- REPRESENTED_IN_GENERIC_TC
- INDEPENDENTLY_COVERED
- DEFERRED
- REVIEW_REQUIRED

Representation과 독립 검증 완료를 같은 의미로 사용하지 않습니다.

### 15.4 Workbook
V0.62 Workbook은 다음 Audit Sheet를 사용합니다.
- 3_Deferred Intent
- 4_Source_Intent_Audit
- 5_Source_Fact_Audit

### 15.5 Audit Status
- PASS
- PASS_WITH_REVIEW_ITEMS
- FAIL

Critical Source numeric/timing/interface provenance gap은 Release Review 대상으로 관리합니다.
