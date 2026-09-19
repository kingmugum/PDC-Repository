# Requirement Studio V0.19

## V0.19 정합성 완료본

이 패키지는 사용자 승인 Dashboard 시안을 기준으로 UI를 정리하고, 최신 개발헌법 및 Requirements rev17과 동기화한 V0.19 정합성 완료본입니다.

# Requirement Studio V0.19

## V0.19 주요 변경
- 대시보드 UI를 샘플 시안 기준으로 재구성했습니다.
- ALIRA / GPT / Gemini 선택 UI를 개선했습니다.
- 분석 진행 단계 카드 및 2중 진행률 막대를 적용했습니다.
- 필수 항목 확인 체크리스트와 상세 원인 확인 팝업을 유지했습니다.
- output 폴더 열기 버튼을 상단 고정으로 이동했습니다.
- 분석 결과 DOCX 자동 저장을 적용했습니다.
- 분석 실행 후 안전 중지 요청 기능을 추가했습니다.

# Requirement Studio v0.17

v0.17은 제품의 중심을 특정 AI 도구에서 분리하기 위한 **Brand/UI Refactoring Baseline**입니다.

## 핵심 변경

제품명은 다음으로 통일합니다.

```text
Requirement Studio
```

ALIRA는 이제 제품명이 아니라 선택 가능한 AI Provider 중 하나입니다.

```text
AI Provider
├─ ALIRA / Qwen
├─ H-Chat / GPT
└─ H-Chat / Gemini
```

## 시작 시 Connection 동작 변경

v0.16까지는 프로그램 실행 직후 선택된 Provider에 자동 연결 테스트를 수행했습니다.

v0.17부터는:

```text
프로그램 시작
   ↓
Provider / Model 선택
   ↓
AI 연결 확인 전
   ↓
필요 시 [+] → [AI 연결 테스트]
   또는
문서 분석 / 요구사항 추출 실행
```

으로 변경합니다.

즉 **프로그램 시작 자체가 ALIRA 연결을 의미하지 않습니다.**

Provider나 Model을 변경해도 자동으로 API/CLI 요청을 보내지 않습니다.
연결 상태는 다시 `AI 연결 확인 전`으로 초기화됩니다.

## AI Connection

수동 연결 테스트 기능은 그대로 유지합니다.

```text
AI Connection                 ● AI 연결 확인 전   [+]

[+] 펼침
  Provider
  Model
  API Base
  Credential
  [AI 연결 테스트]
  [결과 지우기]
  Connection Result
```

선택한 Provider에 대해서만 연결 테스트가 수행됩니다.

## Visible Launcher

사용자가 실행하는 Root 파일도 제품명에 맞게 변경했습니다.

```text
Requirement Studio.exe
```

Python Bootstrap 내부의 legacy 파일명 `app/ALIRA.pyw`는 기존 Launcher Binary 호환성을 위해 이번 버전에서 유지합니다.
사용자 화면에는 `Requirement Studio`로 표시됩니다.

## 현재 기능 구조

```text
Source Document
      ↓
Local Document Normalizer
      ↓
Compact Prompt
      ↓
선택 AI Provider
      ↓
Canonical Requirement JSON
      ↓
Local Validator
      ↓
향후 SWE.1 / SWE.6
```

## 검증 상태

```text
Requirement Studio branding                 ✅ 정적 확인
Root Requirement Studio.exe                 ✅
초기 자동 연결 테스트 제거                  ✅ 정적 확인
Provider 변경 시 자동 연결 제거              ✅ 정적 확인
수동 AI 연결 테스트 유지                     ✅
ALIRA / H-Chat Provider 구조 유지             ✅
실제 Windows UI                             ⏳ 사용자 환경 확인 필요
ALIRA / H-Chat 실제 Provider Runtime         ⏳ 각 환경에서 확인 필요
```
