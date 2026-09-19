# 00_AI_DEVELOPMENT_GOVERNANCE.md

> **Document Version:** v0.3  
> **Status:** Draft / Living Document  
> **Effective Date:** 2026-09-12  
> **Purpose:** 모든 AI 보조 개발 프로젝트에 적용할 공통 개발헌법과 Project ID별 고유 운영 규칙을 하나의 문서에서 관리한다.  
> **Registered Projects:** `PF` PassFail, `SE` Signal Export V2, `AM` Automation Manager, `GM` Git Manager, `BR` BoardRepo, `ALM` ALIRA Manual, `ALR` ALIRA Runtime / Tools  
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

## A17. Governance Carry-Forward와 패키지 기준선

`00_AI_DEVELOPMENT_GOVERNANCE.md`는 AI 보조 개발의 공통 기준 문서이며, 등록 프로젝트의 내부 개발 패키지에서는 다음 규칙을 따른다.

1. Automation Manager 통합 배포본 Root에는 본 파일을 반드시 포함한다.
2. Git Manager 및 BoardRepo 독립 Release에도 본 파일을 포함한다.
3. 이후 패키지를 이전 승인 패키지에서 파생할 때 본 파일을 자동 승계 대상으로 취급한다. 사용자가 동일 Governance 파일을 매번 별도 첨부할 필요는 없다.
4. 패키지 Manifest에는 Governance 파일명, Document Version, SHA-256을 기록한다.
5. Governance 파일이 누락된 패키지는 코드 실행 자체와 별개로 개발 기준선 불완전 상태로 표시하며, 다음 수정·Release 전에 복구한다.
6. 여러 Governance 사본이 발견되면 임의 병합하지 않는다. 통합 패키지 Root의 최신 승인 사본을 기준으로 차이를 검토한다.
7. Governance 변경은 Living Document 규칙에 따라 Document Version 또는 해당 Project Profile Version을 증가시키고 Change History에 기록한다.
8. 기능·입력·출력·판정·예외의 최종 기준은 계속 최신 승인 Requirements이며, Governance는 공통 개발 절차·AI 행동 통제·프로젝트 고유 운영 규칙의 기준이다.

따라서 사용자가 단순히 “기능 추가/수정”을 요청하더라도 AI는 패키지에 동봉된 Governance → 활성 Project Profile → 최신 Requirements → Architecture/Code/Test 순으로 영향과 충돌을 확인한 뒤 작업한다.

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
- 모든 유효 Requirement는 승인된 상위 시나리오에 연결한다.
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
| Profile Version | v1.1 |
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

- 기준일: 2026-09-07
- Requirements: `SignalAuto_Requirements_Management_rev59_V2.xlsx`
- 기준 배포: `Signal_Export_V2_260907_1.zip`
- 코드 기준: rev57 패키지의 Python/PYW 12개 파일과 동일
- 요구사항 구조: 사용자 시나리오 + AI_01~AI_10
- 사용자 시나리오: 24개, `검토중`
- 활성 FR: 142개
- 다음 신규 FR 참고값: `FR-152`
- 기능 논리 충돌: 0건

---

## C3. `[AM]` Automation Manager

### C3.1 프로필 정보

| 항목 | 값 |
|---|---|
| Project ID | `AM` |
| Project Name | Automation Manager |
| Status | `ACTIVE` |
| Profile Version | v1.0 |
| Requirements Mode | `CUSTOM` |
| Requirements Pattern | `Automation_Manager_Requirements_YYMMDD_N.xlsx` |
| Package Pattern | `Automation_Manager_YYMMDD_N.zip` |
| Primary Environment | Python/PYW, Windows, Git, BoardRepo |

### C3.2 핵심 운영 규칙

- Automation Manager는 Git Manager와 BoardRepo를 한 GUI에서 제공하는 통합 Launcher/Core이다.
- 자체를 별도 관리 Target으로 중복 등록하지 않는다.
- 공통 Target 정의는 `program_catalog.json`을 기준으로 한다.
- Git Manager와 BoardRepo 엔진의 책임 경계를 유지하고 상호 재귀 호출을 만들지 않는다.
- 통합 Release에는 본 Governance와 최신 Automation/Git/BoardRepo Requirements를 포함한다.

### C3.3 현재 관리 Target 기준

1. PassFail
2. SignalExport
3. WeeklyReport
4. Ext
5. Git Manager
6. BoardRepo
7. ALIRA Manual
8. ALIRA Runtime / Tools

7·8의 그룹웨어 Board URL은 사용자 확인으로 확정되었다.

- Target 7 ALIRA Manual: `https://gw.suresofttech.com/app/community/130/board/394`
- Target 8 ALIRA Runtime / Tools: `https://gw.suresofttech.com/app/community/130/board/395`

## C4. `[GM]` Git Manager

### C4.1 프로필 정보

| 항목 | 값 |
|---|---|
| Project ID | `GM` |
| Project Name | Git Manager |
| Status | `ACTIVE` |
| Profile Version | v1.0 |
| Requirements Mode | `CUSTOM` |
| Requirements Pattern | `GitManager_Requirements_YYMMDD_N.xlsx` |
| Package Pattern | `GitManager_YYMMDD_N.zip` |
| Primary Environment | Python/PYW, Windows, Git |

### C4.2 변경금지·안전 경계

- 기본 Branch는 승인된 Repository 설정의 `main`을 사용한다.
- Force Push, 자동 Conflict 해결, 파괴적 `reset --hard`/`clean`을 자동 수행하지 않는다.
- 현재 폴더 Git 연결/복구는 로컬 Working Tree를 우선 보존한다.
- 최신 Automation Manager ZIP만으로 self-bootstrap 복구가 가능해야 하며 Clone을 필수 단계로 되돌리지 않는다.
- Target 추가/순서 변경 시 숫자만으로 의미를 추정하지 않고 catalog key/alias를 사용한다.

## C5. `[BR]` BoardRepo

### C5.1 프로필 정보

| 항목 | 값 |
|---|---|
| Project ID | `BR` |
| Project Name | BoardRepo |
| Status | `ACTIVE` |
| Profile Version | v1.0 |
| Requirements Mode | `CUSTOM` |
| Requirements Pattern | `BoardRepo_Requirements_v*.xlsx` |
| Package Pattern | `BoardRepo_YYMMDD_N.zip` |
| Primary Environment | Python/PYW, Playwright, Windows, 그룹웨어 게시판 |

### C5.2 핵심 운영 규칙

- Target/Board/폴더/Release 규칙은 `program_catalog.json`을 단일 기준선으로 사용한다.
- 기존 Chromium 경로를 1순위로 보존하고 필요한 경우 설치된 Microsoft Edge를 fallback으로 사용한다.
- 외부 Browser 다운로드와 Online pip fallback은 승인 없이 자동 활성화하지 않는다.
- 게시판 상세 URL 진입과 본문·첨부 Ready를 구분하여 Polling한다.
- Ext는 파일명+SHA-256 정책을 유지한다.
- 하위 `01. old` 등은 versioned target의 최신 Release 탐색 대상에 포함하지 않는다.
- BoardRepo는 Git 복구 엔진을 직접 실행하지 않는다.

### C5.3 Governance Carry-Forward

- BoardRepo 및 Automation Manager Release에는 `00_AI_DEVELOPMENT_GOVERNANCE.md`를 포함한다.
- 다음 수정은 동봉된 Governance와 최신 승인 BoardRepo Requirements를 먼저 읽고 영향·충돌·회귀를 검토한다.
- Governance가 패키지에 있으므로 사용자가 동일 MD를 매 Release마다 별도로 다시 첨부하도록 요구하지 않는다.

## C6. `[ALM]` ALIRA Manual

### C6.1 프로필 정보

| 항목 | 값 |
|---|---|
| Project ID | `ALM` |
| Project Name | ALIRA Manual |
| Status | `DRAFT` |
| Profile Version | v0.3 |
| Requirements Mode | `TBD` |
| Requirements Pattern | `TBD` |
| Package Pattern | 고정 패키지 없음 — 일반 파일 Inbox (`file_hash`) |
| Primary Environment | DOCX/PDF/XLSX/PPTX/MD 등 문서·매뉴얼 및 일반 파일, Windows |

### C6.2 현재 승인 범위

- ALIRA 프로젝트의 사용·운영 매뉴얼을 지속 작성·개정하는 독립 관리 대상이다.
- Automation Manager/BoardRepo Target 7로 배치한다.
- 그룹웨어 게시판 명칭은 `AI 스냅샷_ALIRA_매뉴얼`이다.
- 실제 Board URL은 `https://gw.suresofttech.com/app/community/130/board/394`로 확정한다.
- BoardRepo Target 7은 `file_hash` 일반 파일 Inbox로 운영한다.
- 압축파일만 요구하지 않으며 DOCX/PDF/XLSX/PPTX/MD/TXT/이미지/ZIP 등 일반 파일을 직접 보관할 수 있다.
- 각 파일은 파일명 + SHA-256으로 중복을 판정한다.
- 같은 파일명에 다른 SHA-256이면 자동 덮어쓰지 않고 확인 필요로 처리한다.
- 폴더 바로 아래의 일반 파일만 대상으로 하며 하위 폴더는 자동 재귀 업로드하지 않는다.

## C7. `[ALR]` Requirement Studio

### C7.1 프로필 정보

| 항목 | 값 |
|---|---|
| Project ID | `ALR` |
| Project Name | Requirement Studio |
| Status | `ACTIVE` |
| Profile Version | v0.19 |
| Requirements Mode | `DUAL_LAYER_XLSX_V1` |
| Requirements Pattern | `Requirement_Studio_Requirements_Management_revXX.xlsx` |
| Package Pattern | `Requirement_Studio_V<Major>.<Minor>.zip` |
| Primary Environment | Python, PySide6, Windows, AI Provider Adapters (ALIRA/Qwen, H-Chat/GPT, H-Chat/Gemini) |

### C7.2 현재 승인 범위

- Requirement Studio는 특정 AI 도구에 종속되지 않는 Requirement Engineering Pipeline을 개발·관리한다.
- 사용자는 PySide6 GUI에서 AI Provider/Model을 선택하고 문서 분석·요구사항 추출을 수행한다.
- ALIRA/Qwen, H-Chat/GPT, H-Chat/Gemini는 동등한 Provider Adapter로 취급한다.
- 프로그램 시작 또는 Provider/Model 선택만으로 자동 AI Connection Test를 수행하지 않는다.
- 필요 시 사용자가 `AI 연결 테스트`를 수동 실행하며, 실제 분석/추출 시 선택 Provider가 사용된다.
- v0.1에서 `Python → ALIRA Headless → 사내 Qwen → Python → GUI` 연결 체인을 실제 사용자 환경에서 확인하였다.
- v0.2에서 `input` 폴더 기반 단일 문서 분석 기능을 구현하였다. 실제 문서 런타임 검증은 현재 Baseline에서도 아직 미확인 상태로 관리한다.
- v0.4에서 프로젝트 Root의 `ALIRA_실행.bat` Launcher를 추가하여 명령어 입력 없이 더블클릭으로 앱을 시작할 수 있도록 한다.
- v0.5에서 앱형 이름의 실행 진입점, 바로가기 생성 helper, 문서 분석 시험용 가상 샘플 4종을 추가하였다.
- v0.6에서 input 새로고침/분석 안내 UX를 개선하고 Office `~$` 임시 파일을 제외하며, 표시명 `ALIRA`의 전용 아이콘 Shortcut 생성 정책을 적용하였다.
- v0.7에서 `ALIRA.lnk`를 배포 ZIP에 기본 포함하고, Target/Icon을 Shortcut 위치 기준 상대 경로로 저장하여 압축 해제 직후 사용 가능한 Portable Shortcut을 기준으로 적용하였다.
- v0.8에서 Root 기본 실행 진입점을 Native `ALIRA.exe`로 변경하였다. EXE에 아이콘을 내장하고 자신의 실행 위치에서 프로젝트 Root를 계산하며, 아이콘 원본/환경 구성 Script는 `assets/`와 `tools/`로 분리한다.
- v0.9에서 사용자 실제 실행 실패와 미서명 EXE 경고를 근거로 Native Launcher를 폐기하고, 표준 Python `ALIRA.pyw` Bootstrap으로 전환하였다. `.venv` 미구성 시 Tkinter 초기 설정 UI에서 환경을 준비한 뒤 PySide6 앱으로 전환한다.
- v0.10에서 Python-first Bootstrap은 유지하면서, 사용자에게는 전용 아이콘이 내장된 최소 `ALIRA.exe` Wrapper를 제공한다. Wrapper는 CMD/BAT/설치 로직 없이 `pythonw.exe → app/ALIRA.pyw` 실행과 `.pyw` Fallback만 담당한다.
- v0.11에서 ALIRA 연결 상태를 Connection Card Header에 통합하고, 최초 화면 표시 직후 실제 ALIRA → 사내 Qwen 연결을 자동 1회 확인한다. Connection 상세는 기본 접힘이며 +/− Toggle로 실행 경로, Model/API Base, 수동 연결 테스트와 결과 지우기를 표시한다.
- v0.12에서 Connection 단계 기반 진행률(%)과 전용 Connection Result 로그를 추가하고, 문서 분석 결과를 DOCX로 `output/`에 저장하는 기능을 추가한다. DOCX 출력용 `python-docx`를 승인 Dependency로 등록한다.
- v0.13에서 Connection Result/환경정보/수동 버튼을 모두 +/− 상세 영역 안으로 이동하여 기본 접힘 시 Header만 남기고, Analysis Result 제목 영역의 최소 폭을 확대한다. 요구사항 추출 기능은 다음 기능 버전으로 순연한다.
- v0.14에서 PassFail/SignalAuto/SWE.6 샘플을 기반으로 수정 가능한 판단정책, 보호 Invariant, Compact Reference, Canonical Requirement Contract를 도입하고 [요구사항 추출] → JSON 저장 → 구조평가 흐름을 추가한다. 현재 문서는 사실의 Source of Truth이며 Reference는 패턴 참고용이다.
- v0.15에서 사용자 실제 화면에서 확인된 Connection 100% 최종상태 Race와 [+] 상세 영역 압축/잘림 문제를 수정한다. 100%는 성공 상태 전용이며 Worker lifecycle을 명시적으로 유지하고 상세 영역은 자연 최소크기를 확보한다.
- v0.16에서 AI Provider Adapter, H-Chat API Reference, Local Document Normalizer 및 Provider-independent Pipeline을 도입하였다.
- v0.17에서 제품명을 `Requirement Studio`로 변경하고 ALIRA를 선택형 Provider 중 하나로 재정의하였다. 프로그램 시작 및 Provider 변경 시 자동 Connection Test를 제거하고 수동 `AI 연결 테스트` 기능만 유지한다.
- v0.18에서 업무 중심 Dashboard를 도입하고 Provider Radio, API Key 파일/수동 입력, Connection Test Popup, 7단계 Pipeline, 2중 Progress, Checklist/상세 원인, Timestamp Log를 통합하였다.
- v0.19에서 사용자 승인 Dashboard 시안을 시각 기준으로 적용하되 실제 기능 항목은 최신 Requirements를 우선한다. Provider 선택 파란 원형 표시, 정돈된 Model Dropdown, 일반 텍스트 음영 제거, 정확한 `분석 & 요구사항 추출 시작` 문구, 1.8초 후 Cooperative Stop 버튼 전환, 단계 상태색, 결과영역 상단 Output 접근, 분석 DOCX 자동 저장, Drag & Drop 입력을 반영한다.
- Automation Manager/BoardRepo Target 8로 배치하며, 그룹웨어 게시판 명칭은 `AI 스냅샷_ALIRA_구동`이다.
- 실제 Board URL은 `https://gw.suresofttech.com/app/community/130/board/395`로 유지한다.

### C7.3 Package Naming과 Version 정책

정식 패키지명은 다음 형식을 사용한다.

```text
Requirement_Studio_V<Major>.<Minor>.zip
```

예:

```text
Requirement_Studio_V0.17.zip
Requirement_Studio_V0.18.zip
Requirement_Studio_V0.19.zip
```

1. `Major.Minor`는 ALR 프로젝트의 배포 Baseline Version이다.
2. 신규 기능, 승인 Requirements 변경 또는 Governance Baseline 적용으로 새 배포 기준선이 생기면 Version을 증가시킨다.
3. 동일 Version 패키지를 조용히 덮어쓰지 않는다.
4. Requirements Revision과 Package Version은 별도 축으로 관리한다.
5. 코드 내부 Module Revision이 필요해지는 경우 Package Version과 자동으로 동일시하지 않고 프로젝트 규칙에 별도 정의한다.
6. `ALIRA_V0.3.zip`을 Governance/Requirements가 정식 포함되는 최초 Baseline으로 사용한다.
7. `ALIRA_V0.5.zip`부터 앱형 실행 진입점과 샘플 입력 문서를 포함한다.

### C7.4 Requirements와 Traceability

- 기능 요구사항의 Single Source of Truth는 최신 승인 `Requirement_Studio_Requirements_Management_revXX.xlsx`이다.
- Requirements 구조는 `DUAL_LAYER_XLSX_V1`을 사용한다.
- 사람용 `사용자 시나리오`와 AI용 `AI_01`~`AI_10` 상세 계층을 유지한다.
- 사용자 시나리오와 상세 FR ID를 양방향으로 추적 가능하게 유지한다.
- 기능 추가·변경 시 기존 Requirement와 충돌·중복·누락을 먼저 검토하고, 필요한 Requirement를 갱신한 뒤 코드를 수정한다.
- 최초 승인 Requirements Baseline은 `ALIRA_Requirements_Management_rev01.xlsx`이다.

### C7.5 Architecture와 Module 책임 경계

현재 v0.19 기준 책임 경계는 다음과 같다.

| 영역 | 책임 |
|---|---|
| `Requirement Studio.exe` | 사용자가 더블클릭하는 Root 실행 진입점 |
| `app/ALIRA.pyw` | Legacy 호환용 Python Bootstrap 파일명. 사용자 표시명은 Requirement Studio |
| `main.py` | PySide6 Dashboard, Provider/Model 선택, 파일 Drag & Drop, Checklist, Step/Progress, Connection Popup, Start/Stop Orchestration |
| `providers/base.py` | Provider 공통 Interface |
| `providers/factory.py` | 선택 Provider Adapter 생성 |
| `providers/alira_provider.py` | ALIRA/Qwen Headless Adapter |
| `providers/hchat_provider.py` | H-Chat GPT/Gemini API Adapter |
| `core/document_normalizer.py` | Source Document → Local Document IR |
| `core/prompt_builder.py` | Provider 독립 Compact Prompt 생성 |
| `core/ai_job_runner.py` | Normalize → Prompt → Provider → Local Result Pipeline |
| `core/requirement_engine.py` | Canonical Requirement JSON 파싱·병합·구조검사 |
| `policy/` | 사용자 조정 판단정책 + 보호 Invariant |
| `reference_library/` | SWE.1/SWE.6 Reference Example |
| `input/` | 사용자 원본 문서 입력 |
| `work/` | Local IR / AI Request / Raw Response Runtime 영역 |
| `output/` | Canonical JSON 및 승인 산출물 저장 |

- GUI가 특정 Provider의 API 세부 구현을 직접 소유하지 않는다.
- Provider별 차이는 Adapter에 제한하고 판단정책·Prompt Contract·Canonical Output은 공통으로 유지한다.
- 원본 Source Document를 직접 수정하지 않는다.
- Internal legacy filename은 호환성 목적으로만 유지하고 사용자 UI/제품명으로 노출하지 않는다.

### C7.6 파일·권한·보안 경계

- `input`의 사용자 원본 문서를 직접 수정·삭제·덮어쓰지 않는다.
- `license.lic`, API Key, Token, 개인 PC 인증정보를 배포 ZIP에 포함하지 않는다.
- 승인된 AI Provider(ALIRA/Qwen, H-Chat/GPT, H-Chat/Gemini) 외의 Provider를 승인 없이 추가하지 않는다.
- Headless 실행의 `--no-permission-enabled` 사용은 현재 `document_analyzer`의 읽기 전용 문서 분석 경로로 제한한다.
- `document_analyzer`에는 `Write`, `Edit`, `Bash`를 노출하지 않고 문서 읽기 목적의 Tool/Skill만 사용한다.
- 향후 쓰기·삭제·외부 전송 기능에 `--no-permission-enabled`를 확대 적용하려면 별도 Requirement와 사용자 승인이 필요하다.

### C7.7 검증 상태와 완료 조건

다음 검증 수준을 구분하여 기록한다.

- Python Syntax / Import 확인
- PySide6 GUI 실행 확인
- ALIRA 설치·라이선스·Model 연결 확인
- 실제 사내 Qwen 질의/응답 확인
- `input` 문서 탐색·단일 문서 Gate 확인
- 실제 PDF/DOCX/PPTX/XLSX 문서 분석 확인
- 원본 파일 무변경 확인
- 변경 기능 Test와 관련 Regression 확인

v0.5 Baseline에서 확인된 상태:

- PySide6 GUI 실행: 실제 사용자 환경 확인 완료
- ALIRA 연결 테스트: 실제 사용자 환경 확인 완료
- 사내 Qwen 응답 GUI 표시: 실제 사용자 환경 확인 완료
- 문서 분석 기능: 코드 구현 완료, 실제 문서 Runtime 검증 미수행
- 더블클릭 Launcher: 코드 구현 완료, 실제 Windows 더블클릭 검증 미수행
- 앱형 실행 진입점과 바로가기 생성 helper: 코드/정적 구성 완료, 실제 Windows 더블클릭 검증 미수행
- 샘플 문서 4종: 생성 완료, 문서 렌더링 확인 완료, ALIRA Runtime 분석 미수행

미수행 항목을 전체 PASS로 표현하지 않는다.

v0.19 정합성 완료본 검증 상태:

- Python Syntax Compile: 확인 완료
- Requirements rev17 formula error scan: 확인 완료
- V0.19 UI/동작 Requirements 코드 정합성: 정적 확인 완료
- 실제 Windows PySide6 Dashboard 렌더: 미수행
- 실제 ALIRA/H-Chat Provider 통합 실행: 미수행
- 실제 실행 중 Cooperative Stop Timing: 미수행

동일 Version 정합성 수정은 최초 V0.19 산출물이 다운로드 안내 및 Governance/Requirements 동기화 이전에 생성된 점을 명시적으로 기록하며, 이번 패키지를 V0.19 정합성 완료본으로 취급한다.

### C7.8 배포 구성

필수:

- `00_AI_DEVELOPMENT_GOVERNANCE.md`
- 최신 `Requirement_Studio_Requirements_Management_revXX.xlsx`
- `package_manifest.json`
- `README.md`
- `ARCHITECTURE.md`
- 사용자 매뉴얼: `docs/Requirement_Studio_사용자_매뉴얼_v0.4_V0.19.docx`
- Root 실행 파일: `Requirement Studio.exe`
- Python Bootstrap: `app/ALIRA.pyw` (legacy compatibility)
- Launcher 진단 도구: `tools/RequirementStudio_launcher_diagnostic.py`
- 애플리케이션 아이콘 자산: `assets/RequirementStudio.ico`, `assets/RequirementStudio.png`
- `providers/`, `core/`, `policy/`, `contracts/`, `reference_library/`
- `sample_inputs/`의 가상 샘플 문서와 사용 안내
- 빈 `input/`, `output/`, `work/` 구조

기본 제외:

- `.venv/`
- `__pycache__/`, `*.pyc`
- `license.lic`, API Key, Token, Credentials
- 실제 사용자 입력 문서와 분석 결과 데이터
- 개인 PC 전용 Runtime 로그

### C7.9 현재 참고 기준

> 아래 값은 현재 Baseline 식별을 위한 참고이며, 기능의 최종 기준은 최신 승인 Requirements와 실제 Package Manifest를 우선한다.

- 기준일: 2026-09-19
- Package Baseline: `Requirement_Studio_V0.19.zip`
- Requirements: `Requirement_Studio_Requirements_Management_rev17.xlsx`
- 기능 기반: Provider-independent Pipeline + Local Normalizer + Canonical Requirement + v0.19 Dashboard/Start-Stop/Auto-save UX
- 실제 확인 완료: v0.1 연결 PoC / GUI / 사내 Qwen 응답
- 미확인: v0.19 Windows Dashboard 실제 렌더/Drag & Drop/Stop Timing / ALIRA·H-Chat 실제 Provider Runtime / Requirement Extraction semantic quality / 향후 SWE.1 Renderer 및 SWE.6 TC Derivation
- 다음 신규 FR: `FR-127`
| v0.3 (Profile Update) | 2026-09-19 | Requirement Studio v0.19: 승인 Dashboard 시안 기반 UI 정리, Provider/Model UX, Cooperative Stop, Stage/Progress, Global Output, 자동 저장, Checklist 7항목, Requirements rev17 정합성 완료 | ALR |

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
| v0.3 | 2026-09-12 | Governance Carry-Forward/Manifest 기준 추가, AM·GM·BR 프로필 ACTIVE 등록, ALIRA Manual(ALM)·Runtime(ALR) DRAFT 등록, Automation Manager Target 7·8 확장 기준 추가 | 모든 프로젝트, AM, GM, BR, ALM, ALR |
| v0.3 (Profile Update) | 2026-09-12 | ALM·ALR Profile v0.2: 실제 그룹웨어 Board URL board/394·395 확정 | ALM, ALR |
| v0.3 (Profile Update) | 2026-09-12 | ALM Profile v0.3: Target 7을 압축 Release 방식에서 일반 파일 Inbox(file_hash, 파일명+SHA-256) 방식으로 변경 | ALM |
| v0.3 (Profile Update) | 2026-09-13 | ALR Profile v0.3: ACTIVE 전환, DUAL_LAYER_XLSX_V1 및 `ALIRA_V<Major>.<Minor>.zip` 패키지 규칙 확정, v0.3 Governance/Requirements Baseline 정의 | ALR |
| v0.3 (Profile Update) | 2026-09-13 | ALR Profile v0.4: `ALIRA_실행.bat` 더블클릭 Launcher, Requirements rev02, 최초 실행 `.venv`/PySide6 구성 정책과 Launcher 검증 상태 추가 | ALR |
| v0.3 (Profile Update) | 2026-09-13 | ALR Profile v0.5: 앱형 실행 진입점, 바로가기 생성 helper, sample_inputs 샘플 4종 추가, Requirements rev03 반영 | ALR |
| v0.3 (Profile Update) | 2026-09-13 | ALR Profile v0.6: input 새로고침/분석 UX 개선, Office `~$` 임시 파일 제외, 전용 ALIRA 아이콘 및 표시명 `ALIRA` Shortcut 정책, Requirements rev04 반영 | ALR |
| v0.3 (Profile Update) | 2026-09-13 | ALR Profile v0.7: Portable `ALIRA.lnk`를 ZIP에 기본 포함, 상대 Target/Icon 경로 적용, Shortcut 생성 helper를 복구 도구로 이동, Requirements rev05 반영 | ALR |
| v0.3 (Profile Update) | 2026-09-13 | ALR Profile v0.8: v0.7 Portable LNK 방식 폐기, 전용 아이콘 내장 Native `ALIRA.exe` Root Launcher로 전환, 보조 실행 Script를 tools로 이동, Requirements rev06 반영 | ALR |
| v0.3 (Profile Update) | 2026-09-13 | ALR Profile v0.9: 사용자 환경의 v0.8 Native EXE 실행 실패/보안 경고를 반영하여 `ALIRA.pyw` Python-first Bootstrap으로 전환, Tkinter 최초 설정 UI 및 오류 가시성 정책 추가, Requirements rev07 반영 | ALR |
| v0.3 (Profile Update) | 2026-09-13 | ALR Profile v0.10: v0.9 Python Bootstrap을 `app/ALIRA.pyw`로 유지하고, Root에 전용 아이콘 최소 `ALIRA.exe` Wrapper 추가, CMD/BAT 미사용 실행 경계 및 Requirements rev08 반영 | ALR |
| v0.3 (Profile Update) | 2026-09-13 | ALR Profile v0.11: 최초 자동 ALIRA 연결 확인, Connection Card 상태 LED/텍스트 통합, 기본 접힘 +/− 상세 Toggle, 연결 결과와 Analysis Result 분리, Requirements rev09 반영 | ALR |
| v0.3 (Profile Update) | 2026-09-13 | ALR Profile v0.12: 연결 확인 단계 기반 진행률/Connection Result 로그, 분석 결과 DOCX output 저장, python-docx Dependency/Bootstrap 반영, Requirements rev10 적용 | ALR |
| v0.3 (Profile Update) | 2026-09-13 | ALR Profile v0.13: Connection Result를 상세 접힘 영역 내부로 이동, 수동 연결 테스트 버튼 가시성 보강, Analysis Result Header 폭 개선, Requirements rev11 반영 | ALR |
| v0.3 (Profile Update) | 2026-09-13 | ALR Profile v0.14: 사용자 조정 판단정책, 보호 Invariant, PF/SE/SWE6 Reference, Canonical Requirement JSON, 요구사항 추출 GUI/구조평가, Requirements rev12 반영 | ALR |
| v0.3 (Profile Update) | 2026-09-13 | ALR Profile v0.15: Connection 100% final-state race, Worker lifecycle, expanded-detail layout clipping 수정 및 Requirements rev13 반영 | ALR |

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
| v0.3 (Profile Update) | 2026-09-19 | Requirement Studio v0.17: 제품명 일반화, ALIRA를 선택형 Provider로 재정의, 시작/Provider 변경 시 자동 Connection 제거, 수동 AI Connection Test 유지, Requirements rev15 반영 | ALR |
