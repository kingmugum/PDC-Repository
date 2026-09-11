# 01_PROJECT_RULES.md — PassFail

> **Project:** PassFail / Oracle Checker  
> **Document Version:** v1.1  
> **Effective Date:** 2026-09-06  
> **Role:** PassFail 프로젝트에만 적용되는 개발·배포·요구사항 운영 규칙  
> **Governance Parent:** `00_AI_DEVELOPMENT_CONSTITUTION.md`

---

## 1. 목적

이 문서는 PassFail 개발에서 사용자가 매번 반복해서 지시하지 않아도 AI가 자동으로 적용해야 하는 프로젝트 고유 규칙을 정의한다.

사용자가 단순히 다음과 같이 요청하더라도:

> `XX 기능을 추가해줘.`  
> `이 동작을 수정해줘.`  
> `이 기능은 삭제해줘.`

AI는 본 문서와 개발헌법, 최신 요구사항 Excel을 먼저 확인하고 아래 절차와 규칙을 자동으로 적용한다.

---

## 2. 문서 권한과 우선순위

PassFail에서는 다음 역할을 구분한다.

1. **사용자의 현재 명시적 지시**
2. **`PassFail_Requirements_Management_revXX.xlsx`** — 기능/동작의 Single Source of Truth
3. **`00_AI_DEVELOPMENT_CONSTITUTION.md`** — 공통 개발 절차와 AI 행동 원칙
4. **`01_PROJECT_RULES.md`** — PassFail 고유 규칙
5. **검증된 기존 코드 및 회귀 결과**
6. 기타 안내문/주석/과거 패키지

기능 동작이 충돌하면 최신 승인 Requirements를 우선하고, 프로젝트 고유 파일명·배포 방식은 본 문서를 따른다.

---

## 3. 요구사항 이중 계층 구조

PassFail Requirements Excel은 다음 두 계층을 유지한다.

### 3.1 1층 — 사람용 사용자 시나리오

시트명:

`사용자 시나리오`

목적:

- 사용자가 기능 목적과 전체 흐름을 빠르게 검토
- 사용자 상황 / 동작 / 기대 결과를 상위 수준에서 관리
- 하나의 시나리오가 여러 상세 FR과 연결되는 1:N 구조 유지

### 3.2 2층 — AI용 상세 계층

시트명:

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

AI는 구현 시 상위 시나리오만 읽거나 상세 FR만 읽지 않는다. **관련 상위 시나리오와 상세 FR을 함께 읽는다.**

### 3.3 추적성 규칙

- 모든 유효 FR은 적어도 하나의 상위 시나리오와 연결되어야 한다.
- 상위 시나리오의 `관련 FR ID`와 AI_02의 `상위 시나리오 ID`는 서로 일치해야 한다.
- 기존 FR ID는 재번호하지 않는다.
- 신규 요구사항은 마지막 FR 번호 다음 번호부터 추가한다.
- 삭제가 필요하면 ID를 재사용하지 않고 `대체됨` 또는 `폐기` 상태와 대체 ID를 기록한다.

---

## 4. 기능 변경 시 자동 작업 순서

사용자가 PassFail 기능 추가·수정·삭제를 요청하면 AI는 별도 지시가 없어도 다음 순서를 수행한다.

```text
00_AI_DEVELOPMENT_CONSTITUTION.md 확인
        ↓
01_PROJECT_RULES.md 확인
        ↓
최신 Requirements Excel 확인
        ↓
관련 사용자 시나리오 확인
        ↓
관련 FR / 판정 / 실패상황 확인
        ↓
변경금지조건(LOCK) 확인
        ↓
기존 코드 / Interface / 영향 Module 분석
        ↓
요구사항 충돌·중복·회귀 영향 검토
        ↓
Requirements Excel 갱신
        ↓
코드 최소 변경
        ↓
변경 기능 Test + 관련 Regression
        ↓
코드근거 / 회귀테스트 / 충돌검토 갱신
        ↓
패키지 생성 및 무결성 확인
```

**코드만 수정하거나 Excel만 수정한 상태를 완료로 처리하지 않는다.**

---

## 5. PassFail ZIP 패키지 명명 규칙

배포/다운로드용 전체 패키지는 항상 다음 형식을 사용한다.

`PassFail_YYMMDD_N.zip`

예:

- `PassFail_260906_1.zip`
- `PassFail_260906_2.zip`
- `PassFail_260907_1.zip`

규칙:

1. `YYMMDD`는 **Asia/Seoul 기준 패키지 생성일**이다.
2. `N`은 같은 날짜에 생성한 PassFail 전체 ZIP 패키지의 순번이다.
3. 같은 날짜의 기존 최신 패키지 중 가장 큰 `N`을 확인하고 다음 번호를 자동 사용한다.
4. 날짜가 바뀌면 순번은 다시 `_1`부터 시작한다.
5. 사용자가 패키지 번호를 별도로 말하지 않아도 AI가 자동 적용한다.
6. 기존 동일 이름 패키지를 조용히 덮어쓰지 않는다.

---

## 6. Baseline Revision과 Package Sequence 분리

PassFail에서는 앞으로 **S/W revision과 Requirements document revision을 하나의 `Baseline Revision`으로 통일**한다.

예:

- **PassFail Baseline Revision**: `rev87`
  - Python/PYW/CAPL Template의 current revision = `rev87`
  - Requirements document revision = `rev87`
- **ZIP package sequence**: `_1`, `_2`, `_3` ...

규칙:

1. S/W와 Requirements는 항상 동일한 `revXX`를 사용한다.
2. 기능 변경으로 Requirements가 갱신되면 다음 Baseline Revision으로 올리고 코드 모듈도 같은 rev로 갱신한다.
3. governance/document 변경 때문에 배포 기준 Requirements revision을 올려야 하는 경우에도 코드 기능을 임의 변경하지 않고 **revision rollover**만 수행하여 동일 rev로 맞춘다.
4. revision rollover 시 모듈 파일명, import 경로, 현재 baseline을 나타내는 로그/안내/Template 표기를 함께 동기화한다.
5. 과거 revision 이력과 과거 요구사항의 근거 번호는 역사 정보이므로 임의로 재작성하지 않는다.
6. ZIP 순번은 Baseline Revision과 관계없이 같은 날짜 패키지 생성 횟수로 증가한다.
7. ZIP 파일명의 `_N`을 내부 Baseline Revision으로 해석하지 않는다.

즉 다음 두 축만 관리한다.

```text
Baseline Revision = S/W rev = Requirements rev
Package Sequence  = PassFail_YYMMDD_N의 N
```

---

## 7. 배포 ZIP 필수 구성

향후 PassFail 전체 배포 ZIP에는 가능한 한 다음을 포함한다.

### 필수 Governance

- `00_AI_DEVELOPMENT_CONSTITUTION.md`
- `01_PROJECT_RULES.md`

### 필수 개발 기준

- 최신 `PassFail_Requirements_Management_revXX.xlsx`
- 해당 S/W revision의 실행 Python/PYW 모듈
- 필요한 CAPL Template
- 해당 revision 안내 문서

### 제외 원칙

특별한 요구사항이 없는 한 다음은 배포 ZIP에 넣지 않는다.

- 회사 원본 DBC
- 사용자가 생성한 실제 runtime 로그
- `PF_Stimulus_Runtime`의 현장 사용자 데이터
- Python cache / 임시 파일
- 개인 PC 고유 설정·비밀정보

---

## 8. Requirements 변경 규칙

기능이 추가·변경·삭제되면 Requirements Excel을 반드시 함께 갱신한다.

최소 확인 항목:

- 상위 사용자 시나리오 신규/변경 여부
- 상세 FR 신규/변경 여부
- 판정 기준 영향
- 실패상황 영향
- 변경금지조건 영향
- 디버깅 체크 영향
- Regression Test 영향
- 코드 근거 갱신
- AI 작업규칙 갱신 필요 여부
- 요구사항 충돌 검토

기존 요구사항과 신규 요청 사이에 충돌이 발견되면 **코드 수정 전에 충돌을 먼저 기록·해소한다.**

---

## 9. 검증 상태 표현 규칙

다음은 서로 다른 상태다.

- 코드 구현됨
- 정적 검증 통과
- Python compile/import 통과
- 자동/모의 회귀 확인
- CANoe/CANalyzer 환경 확인
- 실제 차량 현장 확인

따라서:

> **정적 검증 PASS ≠ 전체 기능 현장 검증 PASS**

`AI_07_회귀테스트`에 `미수행` 또는 `부분확인`이 남아 있으면 전체 기능이 모두 검증됐다고 표현하지 않는다.

---

## 10. 최소 변경과 기존 기능 보존

- 사용자 요청과 직접 관련 없는 기능을 불필요하게 수정하지 않는다.
- 리팩터링이 기존 동작에 영향을 줄 수 있으면 별도 변경사항으로 취급한다.
- 안정적으로 동작하던 판정 Core와 차량 Stimulus 실험 기능의 경계를 보존한다.
- 새로운 편의 기능 때문에 기존 안전 gate를 우회하지 않는다.

---

## 11. 1안 Replacement 기능 격리 규칙

`테스트용 P/F 차량 테스트 (1안)`은 실험 트랙이다.

다음 원칙을 유지한다.

- `oracle_checker_gui_replacement_revXX.py`
- `oracle_checker_replacement_revXX.py`

두 파일을 제거해도 기본 PassFail 프로그램이 ImportError로 종료되지 않아야 한다.

즉:

> 1안 파일 삭제 → 1안 탭만 제거 → 기존 기본 탭/기능 정상

신규 기능을 구현하면서 replacement 모듈을 안정 기능의 필수 dependency로 만들지 않는다.

---

## 12. 차량 Stimulus 안전 규칙

기존 Requirements의 상세 안전 요구사항을 그대로 따른다.

특히:

- safety-critical TC 자동 Stimulus BLOCK 유지
- body-comfort TC 경고/승인 정책 유지
- CRC/Alive/E2E 알고리즘을 근거 없이 추측해 자동 계산하지 않음
- 반복 송신을 source replacement로 과장하지 않음
- DBC-Bridge identity mismatch hard BLOCK 유지
- 사전 Runtime Bridge 생성은 실제 CAN 출력 없이 수행
- 사용자가 요청하지 않은 안전 gate 완화 금지

상세 동작은 최신 Requirements Excel을 Single Source of Truth로 사용한다.

---

## 13. AI의 자동 준수 선언

향후 PassFail 패키지에 본 파일이 포함되어 있으면 AI는 사용자의 기능 요청에 대해 다음 문장을 별도로 요구하지 않는다.

- “요구사항 Excel도 갱신해줘.”
- “기존 요구사항과 충돌 확인해줘.”
- “회귀 테스트 해줘.”
- “패키지 날짜 규칙 지켜줘.”
- “오늘 같은 날짜면 다음 ZIP 순번으로 해줘.”
- “개발헌법을 준수해줘.”
- “1안 삭제 가능 구조 유지해줘.”

이 항목들은 **PassFail 개발의 기본 작업 계약**으로 자동 적용한다.

---

## 14. 완료 조건

AI가 새 PassFail 패키지를 완료했다고 판단하기 전 최소한 다음을 확인한다.

- [ ] 개발헌법 확인
- [ ] PROJECT_RULES 확인
- [ ] 최신 Requirements 확인
- [ ] 상위 사용자 시나리오/FR 영향 확인
- [ ] 요구사항 충돌 확인
- [ ] 코드 최소 변경
- [ ] Python compile/import 확인
- [ ] 관련 Regression 확인
- [ ] 미수행/부분확인 항목 구분
- [ ] Requirements Excel 갱신
- [ ] Governance 문서 ZIP 포함
- [ ] ZIP 날짜/순번 자동 계산
- [ ] ZIP 무결성 확인
- [ ] S/W rev / 문서 rev / ZIP 순번 분리 확인

---

## 15. 현재 기준

2026-09-06 기준:

- S/W 기준: `rev87`
- Requirements 기준: `rev87`
- 기준 배포: `PassFail_260906_2.zip`
- 요구사항 구조: 사용자 시나리오 1층 + AI_01~AI_10 2층
- 다음 신규 FR 번호: `FR-160`

이 값들은 향후 변경 시 최신 배포 기준으로 갱신한다.
