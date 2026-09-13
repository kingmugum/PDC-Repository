# 00_AI_DEVELOPMENT_GOVERNANCE.md

> **Document Version:** v0.3  
> **Status:** ACTIVE / Living Document  
> **Effective Date:** 2026-09-12  
> **Purpose:** 모든 AI 보조 개발 프로젝트에 적용할 공통 개발헌법과 Project ID별 고유 운영 규칙을 하나의 문서에서 관리한다.  
> **Registered Projects:** `PF` PassFail, `SE` Signal Export V2  
> **Supersedes:** `00_AI_DEVELOPMENT_CONSTITUTION.md` + 프로젝트별 `01_PROJECT_RULES.md`

---

# 0. 이 문서를 사용하는 방법

AI는 개발·수정·분석 작업을 시작할 때 다음 순서를 따른다.

```text
사용자의 현재 지시 확인
        ↓
현재 작업의 Project ID 식별
        ↓
Part A 공통 개발헌법 적용
        ↓
Part B 프로젝트 선택·운영 규칙 적용
        ↓
Part C의 해당 Project ID 규칙만 적용
        ↓
최신 승인 Requirements / Architecture / Code / Test 확인
        ↓
작업 수행 및 검증
```

핵심 적용 원칙:

1. `Part A`는 등록된 모든 프로젝트에 공통 적용한다.
2. `Part C`에서는 현재 확정된 Project ID의 규칙만 적용한다.
3. 다른 Project ID의 규칙을 현재 프로젝트에 혼합하거나 유추 적용하지 않는다.
4. Project ID가 없거나 둘 이상으로 판단되면 임의로 선택하지 않는다.
5. 신규 프로젝트는 `DRAFT` 상태로 등록하고 사용자 승인 후 `ACTIVE`로 전환한다.
6. 본 문서가 존재하는 신규 패키지에서는 과거의 분리 문서인 `00_AI_DEVELOPMENT_CONSTITUTION.md`와 `01_PROJECT_RULES.md`를 중복 운영하지 않는다.

---

# Part A. 모든 프로젝트 공통 개발헌법

## A1. 목적과 문서 역할

본 Part는 AI가 소프트웨어를 구현·수정할 때 따라야 하는 공통 개발 원칙을 정의한다. 개별 기능 요구사항이나 프로젝트 고유 파일명을 복제하지 않는다.

| 문서·정보원 | 담당 질문 | 최종 기준이 되는 영역 |
|---|---|---|
| 승인된 Requirements | 무엇을 해야 하는가? | 기능, 사용자 동작, 입력·출력, 예외, 판정 기준 |
| 본 문서 Part A | 어떤 원칙으로 개발해야 하는가? | 개발 절차, AI 행동 통제, 변경·검증 원칙 |
| 본 문서 Part C | 이 프로젝트만의 규칙은 무엇인가? | 파일명, 환경, 패키지, 프로젝트 고유 경계 |
| `ARCHITECTURE.md` | 어디가 책임지고 어떻게 연결되는가? | 모듈 책임, Interface, Dependency, 실행 구조 |
| `CODING_STANDARD.md` | 코드를 어떤 방식으로 작성·검사하는가? | Coding Style, 정적분석, Metric, Runtime 규칙 |
| Manifest / Release 기록 | 현재 배포 기준은 무엇인가? | 실제 파일 목록, Hash, Revision, Package Sequence |

`ARCHITECTURE.md` 또는 `CODING_STANDARD.md`가 없는 프로젝트에서는 존재하지 않는 내용을 추정하지 않는다. 필요성이 확인되면 신규 문서 초안을 제안한다.

## A2. 문서 충돌 처리

문서 간 충돌은 하나의 고정된 서열만으로 처리하지 않고, 충돌한 내용의 권한 영역을 먼저 판단한다.

1. 사용자의 현재 명시적 지시
2. 해당 내용의 권한을 가진 최신 승인 정보원
3. 검증된 기존 동작과 시험 결과
4. 기존 코드, 주석, 과거 패키지와 기타 참고자료

영역별 기준:

- 기능, 입력·출력, 판정, 예외: 최신 승인 Requirements
- 공통 개발 절차와 AI 행동 통제: Part A
- 파일명, 실행 환경, 배포 구성과 프로젝트 고유 규칙: 활성 Project ID의 Part C
- 모듈 책임과 Interface: Requirements의 기능 의도를 확인한 후 Architecture
- 실제 구현 상태: Code와 Test 근거로 확인하되, 코드가 존재한다는 이유만으로 Requirement를 추정하지 않음

사용자의 일회성 지시는 그 작업에 우선 적용할 수 있지만, 영구 규칙 변경으로 자동 해석하지 않는다. 지속 적용이 필요한 변경은 Requirements 또는 본 문서에 기록한다.

## A3. 승인된 Requirements 준수

### A3.1 Single Source of Truth

각 프로젝트의 활성 프로필에서 지정한 최신 승인 Requirements를 기능 요구사항의 Single Source of Truth로 사용한다.

### A3.2 요구사항에 없는 기능 금지

AI는 요구사항에 없는 사용자 동작, 기능, 제약 완화 또는 안전 우회를 임의로 추가하지 않는다.

불명확한 내용은 추정하여 확정하지 않고 다음 중 하나로 표시한다.

- `TBD`
- `OPEN ISSUE`
- `ASSUMPTION`

### A3.3 Assumption 관리

- 가정을 암묵적으로 코드에 반영하지 않는다.
- 가정의 내용과 영향 범위를 기록한다.
- 사용자 또는 승인된 Requirement로 확정되기 전까지 임시 상태로 관리한다.
- 안전, 데이터 손실, 외부 전송, 비용 발생과 관련된 가정은 사용자 승인 없이 구현하지 않는다.

### A3.4 현행 동작과 Requirement의 차이

```text
승인 Requirement 확인
        ↓
현행 동작 확인
        ↓
차이점과 영향 식별
        ↓
의도된 변경인지 판단
        ↓
필요 시 사용자 확인 또는 문서 갱신
```

## A4. 기존 기능 보존과 최소 변경

변경 요구사항과 직접 관련 없는 기존 기능은 유지한다.

> 요청받은 변경보다 수정 범위를 불필요하게 넓히지 않는다.

- 리팩터링이 기존 동작에 영향을 줄 가능성이 있으면 별도 변경사항으로 취급한다.
- 중복 제거, 구조 정리, 가독성 개선도 요청 범위 안에서만 수행한다.
- 외부 동작 불변을 관련 회귀 시험으로 확인할 수 없는 리팩터링은 자동 수행하지 않는다.
- 기존 Interface, 데이터 Format, 외부 참조 식별자를 임의로 변경하지 않는다.

## A5. 변경 전 영향 분석

코드를 수정하기 전에 최소한 다음을 확인한다.

- 변경되는 Requirement와 상위 시나리오
- 영향받는 Module과 Responsibility
- 영향받는 Interface와 Dependency
- 입력·출력 및 데이터 Format
- 파일·설정·외부 시스템 영향
- 기존 기능에 대한 회귀 위험
- 추가·수정할 Test와 판정 기준
- 변경금지조건 또는 안전 Gate

## A6. Architecture 경계 보호

새 기능을 기존 Module에 추가하기 전에 다음을 확인한다.

1. 해당 기능이 그 Module의 책임 범위인지 확인한다.
2. 다른 책임이라면 별도 Module 또는 명시적 Interface 분리를 검토한다.
3. 다른 Module의 내부 구현에 직접 의존하지 않는다.
4. 공개 Interface와 데이터 계약을 우선 사용한다.
5. Architecture가 현행 코드와 다르면 차이를 기록하고 어느 쪽을 갱신할지 결정한다.

## A7. AI의 자율 판단 범위

AI가 비교적 자율적으로 판단할 수 있는 범위:

- 승인된 Requirement 안에서의 내부 구현 방식
- 요청 범위 내의 국소적 중복 제거
- 외부 동작과 Interface에 영향을 주지 않는 가독성 개선
- 검증 방법이 명확한 작은 구조 정리

AI가 임의로 결정할 수 없는 범위:

- Requirement 또는 사용자 동작 변경
- 파일·데이터 Format 변경
- Interface 변경
- 기존 기능 삭제 또는 비활성화
- 외부 Dependency·네트워크·서비스 추가
- 비가역적 데이터 변경
- 인증정보 처리 방식 변경
- 안전 Gate 완화
- 배포 방식과 호환 범위 변경

## A8. 외부 Dependency

새 Library, Framework, Package 또는 외부 서비스를 추가하기 전에 다음을 확인한다.

1. 해당 언어·플랫폼의 표준 기능 또는 기존 Dependency로 해결 가능한가?
2. 신규 Dependency가 반드시 필요한가?
3. 현재 배포 환경과 지원 버전에서 사용할 수 있는가?
4. License, 보안 취약점, 버전 고정, 장기 유지보수 부담은 적절한가?
5. 오프라인·사내망·고객 환경에서도 요구된 기능을 수행할 수 있는가?

외부 Dependency 추가는 사용자의 명시적 승인 또는 승인된 Requirement가 필요하다.

## A9. 파일·데이터·보안 보호

- 입력 원본 파일을 불필요하게 직접 수정하지 않는다.
- 삭제, 덮어쓰기, 비가역적 변경은 명시적으로 승인된 Requirement가 있을 때만 수행한다.
- 기존 파일 대체가 요구되지 않으면 별도 결과 파일 생성을 우선 검토한다.
- 데이터 변경 대상과 결과를 추적할 수 있어야 한다.
- API Key, 비밀번호, Token, 인증서와 개인정보를 코드·로그·보고서에 평문으로 기록하지 않는다.
- 사용자 승인 없이 프로젝트 데이터를 외부 시스템으로 전송하지 않는다.
- 민감정보, 고객 원본, 개인 PC 설정을 배포 패키지에 포함하지 않는다.
- 보호·암호화 파일의 보안을 임의로 우회하지 않는다.

## A10. 실패·예외·로그

예외를 무조건 무시하거나 성공처럼 숨기지 않는다.

실패 발생 시 가능한 범위에서 다음을 확인할 수 있어야 한다.

- 무엇이 실패했는가?
- 어떤 입력과 조건에서 실패했는가?
- 실패 원인은 무엇인가?
- 영향받은 결과는 무엇인가?
- 사용자가 어떤 조치를 취할 수 있는가?

기본 로그 수준:

| Level | 의미 |
|---|---|
| `INFO` | 정상 진행과 주요 상태 |
| `WARNING` | 예상과 다르지만 제한적으로 진행 가능 |
| `ERROR` | 기능 수행 실패 또는 결과 신뢰 불가 |
| `DEBUG` | 개발 및 원인 분석용 상세 정보 |

로그 위치, 보존기간, Format과 마스킹 규칙은 활성 프로젝트 프로필 또는 Requirement에서 정의한다.

## A11. Test와 Regression

변경 후 최소한 다음을 수행한다.

1. 변경 기능 Test
2. 관련 기존 기능 Regression Test
3. 실패·경고 원인 확인
4. 기존 동작의 의도치 않은 변경 여부 확인
5. 수행하지 못한 시험과 사유 기록

> 프로그램 실행 성공, Compile 성공, 정적 검증 성공과 Requirement 충족은 서로 다른 상태다.

검증 상태는 최소한 다음과 같이 구분한다.

- 문서 반영
- 코드 구현
- Compile / Import / Build 통과
- 정적·함수·합성 확인
- 자동·모의 회귀 확인
- 실제 입력자료·장비·외부 서비스 확인
- 실제 사용자·현장 확인
- 미수행 / 부분수행 / 수행불가

수행하지 않은 단계를 전체 PASS로 표현하지 않는다.

## A12. Date, Revision, Version과 Package

다음은 기본적으로 서로 다른 개념이다.

- 작업·생성 Date
- Governance / Requirements / Code Version 또는 Revision
- 배포 Package Sequence

각 프로젝트가 일부 Revision을 하나의 Baseline으로 묶을 수는 있지만, Package Sequence와 동일한 값으로 해석하지 않는다. 구체적인 명명·증가 규칙은 활성 프로젝트 프로필을 따른다.

기존 파일을 동일 이름으로 조용히 덮어쓰지 않는다.

## A13. Traceability

가능한 경우 다음 연결을 추적할 수 있어야 한다.

```text
사용자 시나리오
    ↓
상세 Requirement
    ↓
Architecture / Module / Interface
    ↓
Code 근거
    ↓
Test Case / Regression 결과
```

- 기존 Requirement ID는 재번호하지 않는다.
- 삭제·대체된 ID를 다른 요구사항에 재사용하지 않는다.
- 변경 이유, 대체 ID와 영향 범위를 기록한다.
- 요구사항에서 시나리오를 복원했다는 이유만으로 기존 Requirement를 자동 변경하지 않는다.

## A14. 문서 중복 방지

동일한 구체 요구사항을 여러 문서에 복제하지 않는다.

- Part A: 공통 원칙
- Part C: 프로젝트 고유 운영 규칙
- Requirements: 구체적인 기능과 판정 조건
- Architecture: 모듈 책임과 연결 구조
- Code / Test: 구현 및 검증 근거

다른 문서의 내용을 반복해야 할 때는 요약과 참조 위치를 기록하고, 원본 권한 영역을 명시한다.

## A15. 공통 Definition of Done

AI가 완료를 선언하기 전에 각 항목의 결과를 `완료`, `부분완료`, `미수행`, `해당 없음` 중 하나로 구분한다.

- [ ] 활성 Project ID 확정
- [ ] 공통 헌법과 활성 프로젝트 규칙 확인
- [ ] 최신 승인 Requirements 확인
- [ ] 상위 시나리오와 상세 Requirement 영향 확인
- [ ] Architecture / Interface / Data 영향 확인
- [ ] 요구사항 충돌·중복·누락 확인
- [ ] 코드 최소 변경
- [ ] 변경 기능 Test
- [ ] 관련 Regression Test
- [ ] 미수행·부분수행·수행불가 항목 기록
- [ ] 관련 Requirements / Architecture / Code 근거 갱신
- [ ] Date / Revision / Package 규칙 확인
- [ ] 배포 파일과 민감정보 포함 여부 확인
- [ ] 패키지 무결성 확인

실제 장비·차량·외부 API·고객 환경이 없어 수행할 수 없는 검증은 임의로 PASS 처리하지 않는다.

## A16. Living Governance

본 문서는 실제 프로젝트 적용 결과에 따라 점진적으로 개선한다.

- 공통 원칙 변경: `Document Version` 증가
- 특정 프로젝트 규칙 변경: 해당 `Profile Version` 증가
- 기존 규칙 삭제: 삭제보다 `DEPRECATED` 또는 대체 규칙 기록을 우선
- 변경 이유와 적용 프로젝트를 Change History에 기록

---

# Part B. Project ID 선택과 통합 문서 운영 규칙

## B1. Project ID 원칙

- Project ID는 영문 대문자 중심의 짧고 의미 있는 고유 식별자를 사용한다.
- 한번 활성화한 Project ID는 프로젝트명이 바뀌어도 재사용하거나 임의 변경하지 않는다.
- 단순 순번보다 `PF`, `SE`, `WMA`, `BR`, `RTC`와 같이 의미를 식별할 수 있는 약어를 권장한다.
- Scenario, Requirement, Architecture, Test ID에 Project ID를 사용할지는 프로젝트 프로필에서 정한다.

## B2. 활성 프로젝트 식별 순서

AI는 다음 순서로 현재 Project ID를 식별한다.

1. 사용자가 현재 요청에서 명시한 Project ID 또는 프로젝트명
2. `package_manifest.json` 등 Manifest의 `project_id`
3. 승인 Requirements의 프로젝트 식별 정보
4. 패키지명과 프로젝트별 고유 파일 Signature
5. 위 근거가 하나로 일치하지 않으면 사용자 확인

폴더명 하나만으로 Project ID를 확정하지 않는다.

## B3. 적용 격리

- 활성 Project ID의 프로필만 적용한다.
- 비활성 프로젝트 프로필은 현재 작업의 근거로 사용하지 않는다.
- 공통 헌법과 활성 프로필이 충돌하면 권한 영역을 판단하고, 해결되지 않으면 사용자에게 확인한다.
- 두 프로젝트의 파일이 한 작업공간에 섞여 있으면 각각의 변경 대상을 분리하고 교차 수정하지 않는다.

## B4. 신규 프로젝트 등록

등록되지 않은 신규 프로젝트를 작업하는 경우 AI는 다음 절차를 따른다.

```text
신규 프로젝트 확인
        ↓
의미 있는 Project ID 제안
        ↓
Part D 양식으로 DRAFT 프로필 생성
        ↓
파일명·요구사항·환경·배포·검증 규칙 작성
        ↓
사용자 검토
        ↓
승인 후 ACTIVE 전환
```

- 사용자가 신규 프로젝트 등록을 명시했거나 신규 프로젝트임이 명백할 때만 프로필을 생성한다.
- 단순히 알 수 없는 폴더나 파일을 발견했다는 이유로 자동 등록하지 않는다.
- DRAFT 상태에서 확정되지 않은 값은 `TBD`로 남긴다.
- DRAFT 규칙을 근거로 비가역적 변경이나 외부 배포를 수행하지 않는다.

## B5. 프로젝트 프로필 상태

| 상태 | 의미 |
|---|---|
| `DRAFT` | 생성·복원 중이며 사용자 승인이 필요함 |
| `ACTIVE` | 현재 작업에 적용 가능한 승인 프로필 |
| `INACTIVE` | 일시 중단되었으나 재개 가능함 |
| `ARCHIVED` | 종료·폐기되었으며 신규 개발에 적용하지 않음 |

## B6. 통합 문서 갱신 범위

- 공통 원칙을 변경하면 모든 프로젝트 영향도를 확인한다.
- 프로젝트 고유 변경은 해당 프로필만 수정한다.
- 한 프로젝트의 변경 때문에 다른 프로젝트의 현재 기준을 임의로 갱신하지 않는다.
- 프로젝트의 최신 Revision과 다음 Requirement ID 같은 가변 정보는 Requirements 또는 Manifest를 우선한다.
- 프로필의 현재 기준 정보가 실제 패키지와 다르면 실제 파일을 확인한 뒤 프로필을 갱신한다.

## B7. 내부 원본과 외부 배포

본 통합 문서에는 여러 프로젝트의 내부 규칙이 포함될 수 있다.

- 개인·사내 작업용 원본에는 등록된 프로젝트 프로필 전체를 유지할 수 있다.
- 고객·외부 전달 패키지에는 다른 프로젝트명, 내부 경로, 보안 규칙과 기준정보가 노출되지 않도록 한다.
- 외부 배포가 필요한 경우 `Part A + 활성 프로젝트 프로필`만 포함한 Project-resolved 사본 생성을 우선한다.
- 외부 배포용 사본도 원본의 Document Version과 Project ID를 표시한다.

## B8. 요구사항 이중 계층 표준

프로젝트 프로필에서 `DUAL_LAYER_XLSX_V1`을 사용하는 경우 다음 구조를 적용한다.

### 1층 — 사람용 사용자 시나리오

기본 시트명: `사용자 시나리오`

기본 열:

1. 시나리오 ID
2. 시나리오명
3. 사용자 목적·상황
4. 사용자 시나리오
5. 기대 결과
6. 관련 FR ID
7. 현황

기본 현황 값:

- `일치`
- `검토중`
- `불일치`
- `미확인`
- `폐기`

### 2층 — AI용 상세 계층

- `AI_01_문서목적·운영규칙`
- `AI_02_요구사항목록`
- `AI_03_판정기준`
- `AI_04_실패상황`
- `AI_05_변경금지조건`
- `AI_06_디버깅체크`
- `AI_07_회귀테스트`
- `AI_08_코드근거`
- `AI_09_AI작업규칙`
- `AI_10_요구사항충돌검토`

### 공통 추적성 규칙

- 하나의 시나리오는 여러 상세 Requirement와 연결할 수 있다.
- 모든 유효 Requirement는 존재하고 유효한 상위 시나리오에 연결한다.
- 역복원한 상위 시나리오가 사람 승인 전 `검토중`이어도 Traceability 연결은 유지할 수 있으며, `검토중` 상태만으로 기존 유효 Requirement를 무효화하지 않는다.
- 사용자 시나리오의 관련 ID와 상세 요구사항의 상위 시나리오 ID는 서로 일치해야 한다.
- AI는 상위 시나리오와 연결된 상세 Requirement를 함께 읽는다.
- 역복원한 시나리오는 사람의 승인 전까지 `검토중`으로 유지한다.
- 시나리오를 복원·수정했다는 이유만으로 기존 상세 Requirement를 자동 변경하지 않는다.

---

# Part C. Project Registry

## C1. `[PF]` PassFail / Oracle Checker

### C1.1 프로필 정보

| 항목 | 값 |
|---|---|
| Project ID | `PF` |
| Project Name | PassFail / Oracle Checker |
| Status | `ACTIVE` |
| Profile Version | v1.2 |
| Requirements Mode | `DUAL_LAYER_XLSX_V1` |
| Requirements Pattern | `PassFail_Requirements_Management_revXX.xlsx` |
| Package Pattern | `PassFail_YYMMDD_N.zip` |
| Primary Environment | Python/PYW, Windows, CANoe/CANalyzer COM, CAPL, DBC |

### C1.2 식별 Signature

다음 근거가 서로 일치할 때 `PF`로 식별한다.

- 패키지명 `PassFail_*.zip`
- 요구사항 파일 `PassFail_Requirements_Management_rev*.xlsx`
- Oracle Checker GUI/Core 모듈 또는 PassFail 고유 실행 파일
- Requirements 또는 Manifest의 Project ID `PF`

### C1.3 기능 변경 자동 절차

```text
통합 Governance 확인
        ↓
Project ID PF 확정
        ↓
최신 Requirements 확인
        ↓
관련 사용자 시나리오·FR·판정·실패상황 확인
        ↓
LOCK·안전 Gate·영향 Module 확인
        ↓
충돌·중복·회귀 영향 검토
        ↓
Requirements 갱신
        ↓
코드 최소 변경
        ↓
변경 기능 Test + 관련 Regression
        ↓
코드근거·회귀테스트·충돌검토 갱신
        ↓
패키지 생성 및 무결성 확인
```

코드만 수정하거나 Excel만 수정한 상태를 완료로 처리하지 않는다.

### C1.4 Package Naming

`PassFail_YYMMDD_N.zip`

1. `YYMMDD`는 Asia/Seoul 기준 실제 패키지 생성일이다.
2. `N`은 같은 날짜에 생성한 PassFail 전체 패키지 순번이다.
3. 기존 같은 날짜의 가장 큰 N 다음 번호를 사용한다.
4. 날짜가 바뀌면 `_1`부터 시작한다.
5. 기존 동일 이름 패키지를 조용히 덮어쓰지 않는다.

### C1.5 Baseline Revision

PassFail은 S/W Revision과 Requirements Document Revision을 하나의 Baseline Revision으로 통일한다.

```text
Baseline Revision = S/W rev = Requirements rev
Package Sequence  = PassFail_YYMMDD_N의 N
```

- 기능 또는 승인 Requirements 변경 시 Baseline Revision을 증가시킨다.
- Governance 문서만 변경한 경우 코드 기능을 바꾸지 않고 Revision rollover로 동일 Baseline을 유지할 수 있다.
- Rollover 시 모듈 파일명, Import, 로그, Template과 안내의 현재 Baseline 표기를 동기화한다.
- 과거 Revision과 요구사항 근거 번호는 역사 정보이므로 재작성하지 않는다.
- ZIP 순번은 Baseline Revision과 독립적이다.

### C1.6 배포 구성

필수:

- `00_AI_DEVELOPMENT_GOVERNANCE.md`
- 최신 `PassFail_Requirements_Management_revXX.xlsx`
- 해당 Baseline의 Python/PYW 모듈
- 필요한 CAPL Template
- 해당 Revision 안내문 또는 Manifest

기본 제외:

- 회사·고객 원본 DBC
- 실제 Runtime 로그와 현장 사용자 데이터
- `PF_Stimulus_Runtime` 사용자 데이터
- Python cache와 임시 파일
- 인증정보와 개인 PC 고유 설정
- 외부 전달 시 다른 Project ID의 내부 프로필

### C1.7 안정 기능과 실험 기능의 경계

`테스트용 P/F 차량 테스트 (1안)`은 실험 트랙이다.

- `oracle_checker_gui_replacement_revXX.py`
- `oracle_checker_replacement_revXX.py`

두 모듈을 제거해도 기본 PassFail이 ImportError로 종료되지 않아야 한다.

```text
1안 모듈 삭제 → 1안 탭만 제거 → 기존 기본 탭·기능 정상
```

Replacement 모듈을 기본 기능의 필수 Dependency로 만들지 않는다.

### C1.8 차량 Stimulus 안전 규칙

- Safety-critical TC 자동 Stimulus BLOCK 유지
- Body-comfort TC 경고·승인 정책 유지
- CRC, Alive, E2E 알고리즘을 근거 없이 추측하여 자동 계산하지 않음
- 반복 송신을 Source Replacement로 과장하지 않음
- DBC-Bridge Identity Mismatch Hard BLOCK 유지
- 사전 Runtime Bridge 생성은 실제 CAN 출력 없이 수행
- 사용자가 요청하지 않은 안전 Gate 완화 금지

상세 판정·시간·대상 목록은 최신 Requirements를 따른다.

### C1.9 검증 상태

다음을 별도 상태로 구분한다.

- Python Compile / Import
- 자동·모의 회귀
- CANoe/CANalyzer 환경 확인
- 실제 차량 현장 확인

`AI_07_회귀테스트`에 미수행 또는 부분확인이 있으면 전체 현장 검증 PASS로 표현하지 않는다.

### C1.10 현재 참고 기준

> 아래 값은 프로필 식별을 위한 참고이며, 실제 최신 값은 패키지의 Requirements와 Manifest를 우선한다.

- 기준일: 2026-09-06
- Baseline: `rev87`
- 기준 배포: `PassFail_260906_2.zip`
- 요구사항 구조: 사용자 시나리오 + AI_01~AI_10
- 다음 신규 FR 참고값: `FR-160`

## C2. `[SE]` Signal Export V2

### C2.1 프로필 정보

| 항목 | 값 |
|---|---|
| Project ID | `SE` |
| Project Name | Signal Export V2 |
| Status | `ACTIVE` |
| Profile Version | v1.2 |
| Requirements Mode | `DUAL_LAYER_XLSX_V1` |
| Requirements Pattern | `SignalAuto_Requirements_Management_revXX_V2.xlsx` |
| Package Pattern | `Signal_Export_V2_YYMMDD_N.zip` |
| Primary Environment | Python/PYW, Windows, BLF/ASC, DBC, Excel, 선택적 외부 AI API |

### C2.2 식별 Signature

다음 근거가 서로 일치할 때 `SE`로 식별한다.

- 패키지명 `Signal_Export_V2_*.zip`
- 요구사항 파일 `SignalAuto_Requirements_Management_rev*_V2.xlsx`
- `Signal_Export_V2_Main`, GUI, Step1~7 모듈
- Requirements 또는 Manifest의 Project ID `SE`

### C2.3 기능 변경 자동 절차

```text
통합 Governance 확인
        ↓
Project ID SE 확정
        ↓
최신 Requirements 확인
        ↓
관련 사용자 시나리오·FR·판정·실패상황 확인
        ↓
LOCK·영향 Step·Interface·Data 확인
        ↓
충돌·중복·회귀 영향 검토
        ↓
Requirements 갱신
        ↓
코드 최소 변경
        ↓
변경 기능 Test + 관련 Regression
        ↓
코드근거·회귀테스트·충돌검토 갱신
        ↓
패키지 생성 및 무결성 확인
```

코드만 수정하거나 Excel만 수정한 상태를 완료로 처리하지 않는다.

### C2.4 Package Naming

`Signal_Export_V2_YYMMDD_N.zip`

1. `YYMMDD`는 Asia/Seoul 기준 실제 패키지 생성일이다.
2. `N`은 같은 날짜에 생성한 Signal Export V2 전체 ZIP의 순번이다.
3. 같은 날짜에는 기존 가장 큰 N 다음 번호를 사용한다.
4. 날짜가 바뀌면 `_1`부터 시작한다.
5. 기존 동일 이름 패키지를 조용히 덮어쓰지 않는다.

### C2.5 Revision 정책

다음은 서로 다른 축으로 관리한다.

- Requirements Document Revision
- Python/PYW Module별 Revision
- ZIP Package Sequence

- Requirements가 변경되면 문서 Revision을 증가시킨다.
- 코드가 변경된 Module만 Module Revision을 증가시킨다.
- 문서·Governance만 변경한 경우 Python/PYW Revision을 올리지 않는다.
- ZIP 순번은 문서·코드 Revision과 독립적이다.

### C2.6 배포 구성

필수:

- `00_AI_DEVELOPMENT_GOVERNANCE.md`
- `00_PACKAGE_NAMING_RULE.txt`
- `package_manifest.json`
- 최신 `SignalAuto_Requirements_Management_revXX_V2.xlsx`
- 현재 GUI, Main, Report, Excel Compat, Step1~7, GLOBAL Step3 모듈
- 해당 Revision 안내문

통합 Governance 적용 패키지에서는 과거 분리 문서인 `00_AI_DEVELOPMENT_CONSTITUTION.md`와 `01_PROJECT_RULES.md`를 중복 포함하지 않는다. 사내·개발 기준 패키지는 통합 원본 Governance를 포함할 수 있고, 고객·외부 전달은 Part B7에 따라 `Part A + SE 프로필`만 남긴 Project-resolved 사본을 사용한다.

기본 제외:

- 회사·고객 원본 DBC
- 실제 BLF, ASC, TestCase와 사용자 결과 데이터
- API Key, 인증정보와 개인 PC 설정
- Python cache와 임시 파일
- 외부 전달 시 다른 Project ID의 내부 프로필

### C2.7 Pipeline 경계

| Module | Responsibility |
|---|---|
| GUI | 사용자 설정, 상태, 로그, 실행 제어 |
| Main | `PipelineConfig` 최종 소유, 최신 Module 선택, 단계 실행 |
| Step1 | BLF→ASC 변환과 파일명 정리 |
| Step2 | DBC 기반 Message Group 생성과 선택적 AI 보강 |
| Step3 | ASC 디코딩과 Message·Signal 변화 추출 |
| Step4 | TestCase 매핑과 AI 문의 생성 |
| Step5 | AI 호출·재시도·응답 정규화 |
| Step6 | 선정 신호의 상세 변화 복원 |
| Step7 | Input·Output·Excluded 분류 |
| GLOBAL Step3 | 전체 ASC 디코딩과 변경 요약 |
| Report | 산출물과 오류 보고서 생성 |
| Excel Compat | XLS/XLSX와 보호 문서 입력 처리 |

각 Step의 `run(config)` 진입점과 Main의 `PipelineConfig` 중심 전달 구조를 유지한다.

### C2.8 Category 규칙

- 일반 Category는 12개를 유지한다.
- CONNECT 정식 Prefix는 `12. Connect UX 사양서 기반 TC 검토 초안`이다.
- CONNECT Keyword는 `커넥트`, `UX`, `Connect`, `connect`를 사용한다.
- `connect`는 CONNECT, `connected`는 BLUELINK_CCS로 구분한다.
- GUI, Main, Step1, TestCase 시트 선택의 Category 정의를 서로 다르게 하드코딩하지 않는다.
- 기존 Sender Include 56개, Message-name Include 36개와 TP/DEV Exclude 규칙을 근거 없이 축소·완화하지 않는다.

### C2.9 CAN·DBC 매핑

- 활성 CAN1~CAN4 각각 정확히 하나의 DBC를 사용한다.
- 논리 CAN과 DBC 관계를 관리하며 VN1640A 물리 Channel 번호를 자동 추정하지 않는다.
- 자동 감지는 파일명 근거만 사용한다.
- 모든 활성 CAN 매핑이 하나로 확정될 때만 전체를 일괄 적용한다.
- 누락·중복·모호함이 있으면 일부만 적용하지 않고 기존 설정 전체를 유지한다.
- DBC 내용 유사도, Message 포함 여부 또는 물리 CH→CAN 추측으로 매핑하지 않는다.

### C2.10 Step2 AI 보강

- 기본값은 OFF이다.
- 선택 상태를 다음 실행에 자동 저장하지 않는다.
- AI 후보는 규칙 기반 결과에 추가만 한다.
- Hard Exclude와 기존 제외 정책은 AI보다 우선한다.
- API 실패·응답 오류·정규화 실패 시 규칙 기반 결과로 Fallback한다.
- AI가 기존 Rule 후보를 삭제하거나 제외 규칙을 우회하지 못하게 한다.

### C2.11 파일·데이터·비밀정보

- 원본 BLF, ASC, DBC, TestCase를 직접 수정하지 않는다.
- 산출물은 정의된 결과 폴더에 별도 생성한다.
- 미해결 Error·Warning을 성공처럼 숨기거나 임의 삭제하지 않는다.
- 성공한 동일 Case의 Stale Error만 승인 Requirement에 따라 정리한다.
- API Key를 로그, 설정 미리보기, Error, Report에 평문으로 출력하지 않는다.
- 보호·암호화 Excel을 우회 해제하거나 손상시키지 않는다.

### C2.12 검증 상태

다음을 별도 상태로 구분한다.

- Python Compile
- 정적·합성·함수 확인
- 실제 DBC·BLF·ASC·TestCase 회귀
- 외부 AI API 호출 확인
- 실제 사용자 환경 확인

Compile 또는 정적 감사 PASS를 전체 기능 검증 PASS로 표현하지 않는다.

### C2.13 현재 참고 기준

> 아래 값은 프로필 식별을 위한 참고이며, 실제 최신 값은 패키지의 Requirements와 Manifest를 우선한다.

- 기준일: 2026-09-12
- Requirements: `SignalAuto_Requirements_Management_rev60_V2.xlsx`
- 기준 배포: `Signal_Export_V2_260912_1.zip`
- 코드 기준: rev57 패키지의 Python/PYW 12개 파일과 동일
- 요구사항 구조: 사용자 시나리오 + AI_01~AI_10
- 사용자 시나리오: 24개, `검토중`
- 활성 FR: 142개
- 다음 신규 FR 참고값: `FR-152`
- 기능 논리 충돌: 0건
- Governance 기준: 통합 `00_AI_DEVELOPMENT_GOVERNANCE.md` 단일 운영, 구 Constitution/Project Rules는 대체됨


### C2.14 통합 Governance 전환 시 보존한 Signal Export 고유 규칙

2026-09-12부터 Signal Export 패키지는 과거의 `00_AI_DEVELOPMENT_CONSTITUTION.md` + `01_PROJECT_RULES.md` 분리 운영을 종료하고 본 통합 Governance만 사용한다. 전환 시 기존 Signal Export 규칙 중 공통 Part A/B만으로는 충분히 특정되지 않는 아래 항목을 SE 프로필에 명시적으로 보존한다.

- 사용자 시나리오 시트는 기본 7열 구조를 유지하고, 시나리오명에는 `[설정]`, `[Step1]`, `[AI]`, `[GUI]`, `[배포]` 등 짧은 분류 말머리를 사용할 수 있다. 별도의 기능 분류 열은 기본 구조에 추가하지 않는다.
- Signal Export Requirements는 `사용자 시나리오` + `AI_01`~`AI_10`의 11개 시트를 기본 구조로 유지한다. 변경영향·요구사항 충돌은 `AI_10`, 현재 코드 기준선·코드근거는 `AI_08`, AI 작업 규칙은 `AI_09`, 배포 기준은 본 Governance와 Manifest에서 관리한다.
- 모든 유효 FR은 하나의 상위 시나리오에 귀속하고 사용자 시나리오의 `관련 FR ID`와 `AI_02`의 `상위 시나리오 ID`를 양방향으로 맞춘다. 역복원 시나리오가 `검토중`이어도 기존 FR의 유효성을 자동 변경하지 않는다.
- rev57 활성 목록에서 사용되지 않았고 과거 삭제·폐기 이력이 확인되지 않은 `FR-023`, `FR-041`, `FR-042`, `FR-044`, `FR-051`, `FR-053`, `FR-060`, `FR-071`, `FR-073`은 신규 요구사항에 재사용하지 않는다. 다음 신규 FR은 최신 Requirements의 기준값을 우선하며 현재 참고값은 `FR-152`이다.
- 사용자가 기능 추가·수정·삭제만 요청해도 C2.3의 자동 절차를 기본 작업 계약으로 적용한다. Requirements 갱신, 시나리오·FR 추적성, LOCK, Regression, 코드근거, 충돌검토, Package Naming을 매 요청마다 다시 지시하도록 요구하지 않는다.
- 통합 Governance 전환은 기능·Pipeline 동작 변경이 아니다. 별도의 기능 요구가 없는 한 Python/PYW Module Revision은 올리지 않는다.

---

# Part D. 신규 프로젝트 프로필 양식

신규 프로젝트는 아래 양식을 복사하여 Project Registry에 추가한다.

```markdown
## CX. `[PROJECT_ID]` Project Name

### 프로필 정보

| 항목 | 값 |
|---|---|
| Project ID | `<PROJECT_ID>` |
| Project Name | `<PROJECT_NAME>` |
| Status | `DRAFT` |
| Profile Version | v0.1 |
| Requirements Mode | `DUAL_LAYER_XLSX_V1` / `CUSTOM` / `TBD` |
| Requirements Pattern | `<REQUIREMENTS_FILENAME_OR_PATTERN>` |
| Package Pattern | `<PACKAGE_PATTERN>` |
| Primary Environment | `<LANGUAGE_TOOL_OS_EXTERNAL_SYSTEM>` |

### 식별 Signature

- Package Pattern
- Requirements Filename
- Main Code / Module Signature
- Manifest Project ID

### 기능 변경 자동 절차

- Requirements 확인
- 영향 분석
- 문서 갱신
- 코드 최소 변경
- Test / Regression
- 패키지 생성과 무결성 확인

### Revision과 Package 규칙

- `<REVISION_POLICY>`
- `<PACKAGE_SEQUENCE_POLICY>`

### 배포 필수·제외 구성

- 필수: `<REQUIRED_FILES>`
- 제외: `<EXCLUDED_AND_SENSITIVE_FILES>`

### Architecture와 변경금지 경계

- `<MODULE_RESPONSIBILITIES>`
- `<LOCKS_AND_SAFETY_GATES>`

### 검증 상태와 완료 조건

- `<STATIC_TEST_INTEGRATION_FIELD_LEVELS>`

### 현재 참고 기준

- 기준일: `<YYYY-MM-DD>`
- Requirements: `<CURRENT_REQUIREMENTS>`
- 기준 배포: `<CURRENT_PACKAGE>`
- 다음 Requirement ID: `<NEXT_ID>`
```

---

# Part E. Change History

| Governance Version | Date | Change | Affected Scope |
|---|---|---|---|
| v0.1 | 2026-09-06 | 공통 개발헌법 초안 작성 | 모든 프로젝트 |
| v0.2 | 2026-09-11 | 공통 헌법과 Project Rules를 단일 Governance로 통합, Project ID 선택·격리·신규 등록 규칙 추가, PF·SE 프로필 등록 | 모든 프로젝트, PF, SE |
| v0.3 | 2026-09-12 | 통합 Governance를 ACTIVE 기준으로 채택, 검토중 역복원 시나리오와 유효 FR의 추적성 규칙 충돌 해소, SE Profile v1.2로 구 Project Rules의 고유 운영 규칙 이관 | 모든 프로젝트(B8), SE |

---

# 최종 실행 원칙

> 공통 헌법은 모든 프로젝트에 적용한다.  
> 프로젝트 고유 규칙은 활성 Project ID의 프로필만 적용한다.  
> 기능의 최종 기준은 최신 승인 Requirements이다.  
> AI는 모르는 내용을 추정하여 구현하지 않는다.  
> 변경은 최소화하고 영향과 Regression을 확인한다.  
> 정적 확인과 실제 환경 검증을 구분한다.  
> 신규 프로젝트는 DRAFT로 등록하고 사용자 승인 후 ACTIVE로 전환한다.  
> 외부 배포 시 다른 프로젝트의 내부 프로필을 노출하지 않는다.
