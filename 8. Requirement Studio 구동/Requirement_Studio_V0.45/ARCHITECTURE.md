# Requirement Studio Architecture — v0.39

## 1. Product / Provider 경계

- 제품명은 `Requirement Studio`이다.
- `ALIRA / Qwen`, `H-Chat / GPT`, `H-Chat / Gemini`, `H-Chat / Claude(Skeleton)`, `기타 API`는 선택 가능한 Provider Adapter이다.
- Provider 선택 자체로 자동 Connection Test를 수행하지 않는다.
- Main 분석 Provider와 Vision Provider는 분리 가능하다.
- Vision은 `selected_provider_native`를 우선한다. Custom API는 사용자가 이미지 입력을 명시적으로 활성화한 경우에만 native image payload를 사용한다.

## 2. End-to-End 구조

```text
Source Document
   ↓
Local Document Normalizer
   ├─ Text / Table
   └─ Embedded Image → Visual Evidence
   ↓
Compact Prompt Builder
   + OUTPUT_AUTHORING_GUIDE.md
   + Policy / Contract / Reference
   ↓
AI Provider Adapter
   ↓
Requirement Candidate JSON
   ↓
Deterministic Merge
   + local SRS_001... assignment
   ↓
Canonical Requirement JSON  (Single Source of Truth)
   ├─ Existing Analysis DOCX
   ├─ SWE.1 Word Exporter
   └─ SWE.1 Excel Exporter

SWE.6 Exporter: V0.32 Local MVP implemented; V0.34 layout/naming refined
```

세 산출물마다 별도 AI 응답을 만들지 않는다. **Canonical Requirement가 기능 기준 Single Source**이며 Word/Excel은 그 View/Renderer이다.

## 3. SWE.1 Authoring Model

```text
Feature
 ├─ SRS_001
 │    ├─ BF1-1
 │    └─ BF1-2
 └─ SRS_002
```

- **Feature**: 관련 SRS를 묶는 상위 기능 단위
- **SRS**: 독립적으로 이해·변경·검증 가능한 Software Requirement
- **BF**: 한 SRS 내부의 Source-backed 상세 동작/순서

SRS 분할은 문장 수가 아니라 다음 의미 경계를 우선한다.

- 독립 Trigger
- 독립 Expected Result / Verification Point
- 독립 변경·삭제 가능성
- Functional / Non-functional 성격 차이
- 독립 Source Trace

단순 연속 Step은 하나의 SRS 안의 BF로 유지할 수 있다.

## 4. Source-First Authoring Rules

작성 규칙의 Single Source는 `reference/OUTPUT_AUTHORING_GUIDE.md`이다.

- 입력문서의 명시 분류를 우선한다.
- 미명시 기능/비기능 분류는 규칙 기반 추론을 허용하되 `분류 근거`를 남긴다.
- 애매하면 `검토 필요`로 유지한다.
- Trigger와 Pre-condition을 구분한다.
- Verification Criteria와 Evaluation Method를 구분한다.
- 평가 방안과 예외 조건은 Source에 근거가 있을 때만 작성한다.
- Source에 없으면 `입력문서에서 확인되지 않음`으로 표시하며 `없음`으로 단정하지 않는다.
- Related Artifact는 Source-backed reference만 기록한다.
- V0.32에서도 Source에 없는 상태/값/곡선/연결관계를 자동 그래프·도식으로 새로 생성하지 않는다.
- Gap/TBD/Conflict를 숨기지 않는다.

GUI의 `작성 기준 보기` 창과 Requirement Extraction Prompt가 같은 Guide 파일을 읽는다.

## 5. Canonical Requirement Contract

V0.32 Canonical schema는 `REQ-STUDIO-CANONICAL-REQ-1.1`을 사용한다.

주요 SWE.1 관련 필드:

- `srs_id` (merge 후 로컬 부여)
- `feature_name`
- `category`
- `classification_basis`
- `requirement_statement`
- `activation_trigger`
- `behavior_flows`
- `preconditions`
- `expected_results`
- `verification_criteria`
- `evaluation_method`
- `exception_conditions`
- `source_evidence`
- `related_artifacts`
- `gap_tbd`

`core/requirement_engine.py`가 deterministic merge 뒤 `SRS_001...`을 부여한다. 저장 Canonical JSON, SWE.1 Word, SWE.1 Excel이 같은 ID를 사용한다.

## 6. Module Responsibility

| Module | Responsibility |
|---|---|
| `Requirement Studio.pyw` | 공식 Root Python-first 실행 진입점 |
| `app/ALIRA.pyw` | Legacy 호환 Python Bootstrap |
| `main.py` | PySide6 Dashboard, Provider/Model 선택, 실행 선택 UI, Modeless Authoring Guide, Pipeline Orchestration |
| `core/document_manager.py` | input 문서/Batch 목록 관리 |
| `core/document_normalizer.py` | PDF/DOCX/PPTX/XLSX/XLSM → Local Document IR + embedded image 추출 |
| `core/prompt_builder.py` | Compact Prompt + Authoring Guide/Policy/Schema 주입 + JSON Recovery용 Source 분할 |
| `core/ai_job_runner.py` | Normalize → Vision → Prompt → Provider → Parse/Recovery → Merge |
| `core/alira_setup.py` | Project-local ALIRA License 탐색, ALIRA_LICENSE_PATH 환경 구성, CLI 존재 검사, 사용자 승인 후 공식 install.bat 실행 |
| `core/visual_evidence.py` | Observed / Interpreted / Not Confirmed Visual Evidence |
| `core/requirement_engine.py` | Canonical Parse/Merge/Validate/SRS ID/Save |
| `core/result_exporter.py` | 기존 문서 분석 결과 DOCX |
| `core/swe1_exporter.py` | Canonical → SWE.1 Word / SWE.1 Excel |
| `providers/*` | Provider 공통 Interface 및 ALIRA/H-Chat/Custom API Adapter |
| `alira_license/` | 사용자가 배치하는 Project-local ALIRA *.lic 위치. 실제 License는 배포본에 포함하지 않음 |
| `reference/OUTPUT_AUTHORING_GUIDE.md` | 사람/AI 공통 SWE.1 작성 기준 Single Source |
| `policy/` | 수정 가능한 판단정책 + 보호 Invariant |
| `contracts/` | Canonical Requirement / SWE.1-SWE.6 Mapping 계약 |
| `reference_library/` | Reference Example |
| `work/` | Local IR / AI Request / Raw Response / Recovery 진단 Runtime |
| `output/` | Canonical JSON, 분석 DOCX, SWE.1 Word/Excel, 로그 Snapshot |

## 7. SWE.1 Output Architecture

### Word

```text
SWE.1 요구사항 정리_<source>_<YYMMDD>_<V버전>.docx
```

- Document metadata / Source-First 안내
- Feature별 Section
- SRS별 표
- Source Traceability와 Source-backed 기타 자료를 같은 SRS 단위로 표시

### Excel

```text
SWE.1 요구사항 명세_<source>_<YYMMDD>_<V버전>.xlsx
```

Sheet:

1. `00_Overview`
2. `01_SWE1`
3. `02_Traceability`

### SWE.6

`SWE.6 적격성 평가_<source>_<YYMMDD>_<V버전>.xlsx`를 실제 생성한다. SWE.6 Exporter는 Provider별 Prompt가 아니라 Canonical Requirement 이후 Local Mapping Rule로 동작한다.

## 8. Dashboard / Modeless Guide

상단:

```text
[ 파일 및 옵션 ] [ Compact AI 설정 ] [ 실행 ]
```

실행 Card:

- SWE.1 Word: 기본 On
- SWE.1 Excel: 기본 On
- SWE.6 Excel: Off/Disabled
- `작성 기준 보기`
- `분석 및 요구사항 추출 시작`

`작성 기준 보기`는 `QDialog`를 NonModal로 표시하며 `.show()`를 사용한다. 작성 기준 창이 열린 동안 Main Dashboard Control을 계속 사용할 수 있다.

## 9. Vision / Provider Boundary (V0.31)

```text
Embedded Image
   ↓ local extraction / common limits
Selected Provider Adapter
   ├─ H-Chat GPT / Gemini native image payload
   ├─ Custom API native image payload (explicit enable)
   └─ ALIRA/Qwen: V0.41 verified CLI Image Tool, supports_images=true
   ↓
Visual Evidence
  - Observed
  - Interpreted
  - Not Confirmed
```

- Local Python은 이미지 의미를 스스로 해석하지 않는다.
- Text/Table과 Vision이 충돌하면 임의 덮어쓰지 않고 Gap/TBD/Conflict로 남긴다.
- Vision 실패/미지원은 해당 자산만 failed/unsupported로 기록하고 Text/Table 분석을 계속한다.
- Base64 payload/API Key는 Runtime Log/Request Snapshot에 저장하지 않는다.

## 10. Batch / Runtime Robustness

- 지원 문서는 문서별 독립 Pipeline으로 순차 Batch 처리한다.
- 특정 문서 실패가 사용자 중지가 아니면 다음 문서를 계속 처리한다.
- Requirement JSON parse 실패 시 Raw를 보존하고 SOURCE를 작은 non-overlap 단위로 재추출한다.
- Recovery failure Popup에는 Raw 전체를 노출하지 않는다.
- Log Snapshot은 `output/logs`에 보존한다.
- Cooperative Stop은 외부 호출을 강제 Kill하지 않고 안전지점에서 종료한다.

## 11. Security / Distribution

- 원본 Source Document를 직접 수정하지 않는다.
- API Key/Token/license.lic을 배포 ZIP에 포함하지 않는다.
- Credential/Base64 이미지 본문을 로그에 남기지 않는다.
- 자체 제작 `.exe`를 배포하지 않는다.
- 공식 실행 진입점은 `Requirement Studio.pyw`이다.
- Defender/SmartScreen 비활성화·우회·예외등록 기능을 구현하지 않는다.

## 12. V0.31 Verification Boundary

제작 환경에서 확인:

- Python syntax compile
- deterministic SRS ID 합성 테스트
- SWE.1 Word/Excel exporter 합성 테스트
- 샘플 Word 렌더링 시각 검토
- 샘플 Excel 구조 inspect
- Requirements rev33 formula-error scan 0건

아직 사용자 환경 확인 필요:

- Windows Dashboard 실제 렌더
- `작성 기준 보기` Modeless 실제 GUI 조작
- 실제 ALIRA/H-Chat → Canonical → SWE.1 End-to-End
- 실제 그림 포함 문서 Vision 통합 Runtime
- 실제 입력문서에서 Authoring Rule semantic 품질

미확인 Runtime은 PASS로 기록하지 않는다.


## 13. Custom API Extension Point

`providers/custom_api_provider.py`는 회사별 API 연결을 위한 설정형 Adapter이다.

지원 Protocol Profile:
- `openai_compatible`: `/chat/completions` 형식
- `anthropic_messages`: `/v1/messages` 형식
- `gemini_generate_content`: `models/{model}:generateContent` 형식

비민감 설정(Profile/Base/Model/Vision 여부)은 `config/provider_config.json`에 저장할 수 있다. API Key는 저장하지 않고 현재 실행 메모리 또는 `REQUIREMENT_STUDIO_CUSTOM_API_KEY`에서만 읽는다.

Custom Provider가 이미지 입력을 지원하지 않는 경우 H-Chat fallback을 자동 적용하지 않는다. Cross-provider 데이터 라우팅은 별도 명시 정책이 있어야 한다.

위 3개 Profile과 호환되지 않는 독자 API는 `AIProvider` Interface를 구현한 별도 Adapter를 추가한다. Core Document/Requirement/SWE.1 Pipeline은 수정하지 않는다.

## 14. Result Tab Connector

선택 Result Tab은 Content Panel의 상단 Border 구간만 `resultTabConnector`로 덮어 하단선이 없는 연결형 Card로 표현한다. 비선택 Tab과 나머지 Content Border는 유지한다. 이 변경은 `QStackedWidget` index/결과 데이터 의미를 변경하지 않는 UI-only 개선이다.


## 14. ALIRA Wait Progress / Vision Diagnostics (V0.31)

### ALIRA 응답 대기
- Connection Test: 최대 60초 구간 기준으로 elapsed/max/timeout-ratio를 표시한다.
- Analysis/Requirement 호출: Provider timeout(기본 600초) 기준 Heartbeat를 약 4초 간격으로 전달한다.
- 이 비율은 LLM 내부 추론 진행률이 아니며 반드시 `timeout 기준`으로 표시한다.
- `AIProvider.generate(..., progress_callback=...)`을 통해 ALIRA Client 상태를 AIJobRunner Runtime Log로 전달한다.

### Vision 처리 경로
- 시각 자산이 있으면 Main Provider와 실제 Vision Provider를 분리하여 로그에 표시한다.
- Provider ID가 같으면 Native, 다르면 Fallback으로 표시한다.
- Vision Provider Credential 상태도 함께 표시한다.
- Visual Evidence가 0개이면 asset별 vision_status와 `work/normalized/.../visual_evidence.json` 확인을 안내한다.
- Vision 실패는 Text/Table 분석을 중단하지 않지만 그림 미반영 사실을 숨기지 않는다.


## 15. SWE.6 Local Exporter (V0.32)

```text
Selected AI Provider
    ↓
Canonical Requirement (shared)
    ↓
Local SWE6Exporter
    ├─ Cover / Revision History
    ├─ Test Summary / Testability
    └─ Test Cases / Result Blank Fields
```

핵심 경계:
- Provider는 Canonical Requirement 품질에 영향을 줄 수 있지만 SWE.6 Workbook 구조/Mapping은 Provider와 독립적이다.
- `SWE6_AUTHORING_GUIDE.md`를 SWE.6 작성 기준으로 사용한다.
- Source에 없는 Test Tool/Tolerance/Signal을 생성하지 않는다.
- 실제 Output/PASS-FAIL/Comment/Capture는 생성하지 않는다.


## 16. V0.33 Result Tab / Progress Semantics

### Result Tab Connector
- Tab button과 Content Frame은 sibling hierarchy에 있으므로 선택 Tab 위치를 Global coordinate로 환산한다.
- Connector는 선택 Tab width 구간의 Content top border만 mask한다.
- 다른 Tab/인접 border는 유지한다.

### Progress Semantics
- `test_connection`: 연결 진단 목적이므로 elapsed/timeout heartbeat 유지.
- 실제 analysis/requirement runtime: timeout 경과율 heartbeat 제거.
- Overall progress: Local pipeline stage weight 기반 deterministic progress.
- Current progress during remote LLM wait: Indeterminate/Busy. 모델 내부 %를 추정하지 않는다.
- Runtime log: request sent / response wait / response received / result processing / stage completed Event 중심.
- Progress용 별도 server polling 금지. Provider가 공식 streaming/progress event를 제공할 때만 adapter로 연동.


## 17. V0.34 SWE.6 Layout / Naming
- SWE.6 Local Exporter remains downstream of Canonical Requirement and Provider-independent.
- Cover title spans the same three-row height as artifact ID / revision / revision date.
- Test Case Sheet uses grouped row 2 plus detailed row 3 headers.
- Detailed columns are reduced to 21 by removing Tolerance lower/upper and Capture Environment.
- N/A is applied only to unavailable derived Variable/Compare/Value cells, never to intentional result-entry blanks.
- Common final-output naming helper uses `YYMMDD_V0.0` for SWE.1 Word/Excel and SWE.6 Excel.


## 18. V0.35 SWE.1 Final View Simplification
- Canonical Requirement remains rich and may retain classification basis, gap/TBD/conflict, detailed BF and visual evidence.
- Final SWE.1 Word/Excel shows only 11 engineer-facing fields.
- Word requirement table uses approximately 24% label / 76% content width.
- Excel removes separate Behavior Flow and Gap/TBD sheets.
- `02_Traceability` is redesigned as Input Source -> SWE.1 SRS -> SWE.6 TC end-to-end view.
- Auxiliary source figures/diagrams/tables are surfaced through `기타`.


## 18. V0.36 Provider / Model Registry / Diagnostics / Progress

### 18.1 Provider / Model Registry

- GPT / Gemini / Claude / ALIRA / Custom은 모두 Provider 선택과 Model 선택을 분리한다.
- 현재 Model과 선택 가능한 Model 목록은 `config/provider_config.json`에서 관리한다.
- Model ID 추가/교체 시 Core Pipeline을 수정하지 않는 것을 원칙으로 한다.
- Claude는 회사 H-Chat 규격 확인 전 TBD Skeleton이며 False PASS를 허용하지 않는다.

### 18.2 Detachable ALIRA Vision Probe

- `diagnostics/ALIRA_Vision_Probe`는 본체가 import하지 않는 독립 진단 영역이다.
- 환경/CLI help → Direct API Image → 검증된 CLI Image Argument 순으로 전달 계층을 분리한다.
- Probe fixture는 Prompt만으로 알 수 없는 코드/색상/방향/수치/공간관계를 포함한다.
- 검증 결과는 `alira.supports_images` Config Flag로 명시적으로 반영한다.
- Probe 폴더 삭제가 Main Runtime에 영향을 주어서는 안 된다.

### 18.3 Custom API V0.36

- 기존 OpenAI-compatible / Anthropic / Gemini profile을 유지한다.
- OpenAI Responses profile을 additive하게 추가한다.
- Auth Mode와 Profile Flag를 Config로 관리하여 신규 Profile을 독립적으로 롤백할 수 있게 한다.
- 실제 Secret Key 값은 저장하지 않는다.

### 18.4 Progress UI

- Overall Progress는 Local Pipeline STEP 기반 0~100%를 유지한다.
- Current Step은 별도 %/Busy Progress Bar를 사용하지 않고 짧은 상태 문구와 3-dot Activity Indicator를 사용한다.
- 실제 분석 Runtime에서는 timeout 경과율을 진행률로 표시하지 않는다.
- 연결 테스트 elapsed heartbeat는 진단 목적에 한해 유지한다.
- Progress 확보만을 위한 추가 Server Polling은 사용하지 않는다.


## 19. V0.37 Credential Validation / Vision Quick Probe

### 19.1 H-Chat Credential Discovery
- `providers/hchat_credentials.py` excludes documentation/sample filenames even when they contain `API_KEY`.
- Accepted H-Chat keys must be a single printable ASCII token without whitespace; no provider-specific prefix is hard-coded.
- Manual H-Chat key entry uses the same validation function.

### 19.2 ALIRA Native Vision Quick Test
- `diagnostics/ALIRA_Vision_Probe` remains completely detachable; main/core/providers/app do not import it.
- `RUN_ALIRA_VISION_PROBE.cmd` runs inspect + deterministic fixture + direct configured ALIRA/Qwen API image test.
- Direct API PASS checks image-only facts before optional CLI-layer testing.
- Capability remains one config flag: `alira.supports_images=true/false`.
- `AliraProvider.generate_with_images` routes to `AliraClient.run_vision_prompt`, which stages images and invokes the verified ALIRA CLI Image Tool path.


## 18. V0.38 ALIRA Connection Setup Boundary

```text
Requirement Studio
   ├─ AI Settings / Provider-aware Action
   │    └─ ALIRA 연결 설정
   ↓
AliraSetupDialog (modeless)
   ├─ CLI 확인
   ├─ License 확인
   ├─ Model 확인
   ├─ API Server 확인
   └─ Connection Test
        ↓
core/alira_setup.py
   ├─ alira_license/*.lic 탐색
   ├─ ALIRA_LICENSE_PATH 구성
   ├─ %LOCALAPPDATA%/Programs/alira/alira.exe 확인
   └─ CLI 미설치 시 사용자 승인 후 official install.bat
        ↓
Local ALIRA CLI
        ↓
Remote corporate vLLM / Qwen
```

설계 원칙:

- Qwen/LLM을 사용자 PC에 설치하는 기능이 아니다. 로컬에는 ALIRA CLI만 준비하고 Model/API Base로 원격 추론 서버를 사용한다.
- Project-local License는 설치 폴더로 복사하지 않고 subprocess 환경의 `ALIRA_LICENSE_PATH`로 연결한다.
- 실제 `*.lic`는 Package에 포함하지 않는다.
- CLI 설치는 시스템 변경이므로 사용자가 명시적으로 승인한 뒤에만 실행한다.
- Wizard prerequisite가 준비되어도 실제 Connection Test가 성공하기 전에는 연결 정상으로 표시하지 않는다.
- ALIRA Setup Wizard와 Vision Probe는 역할이 다르다. Setup Wizard는 실행환경/License/원격 연결을 준비하고, Vision Probe는 Native image capability를 독립 진단한다.

## 19. V0.38 AI Action / Clipboard Feedback

- AI Settings의 3개 Action Slot은 위치를 유지하면서 Provider에 맞게 Label/Handler를 교체한다.
- Action Stack은 API Key/Credential Row와 시각적으로 정렬한다.
- `로그 복사` 성공은 Modal Popup 대신 약 1.9초 `✓ 복사 완료` 상태로 표시하고 자동 복귀한다.
- GUI layout/animation은 실제 Windows PySide6 환경에서 최종 확인한다.


## 20. V0.39 UI Geometry Stabilization

### 20.1 AI Action Stack
- Provider-aware Action 동작은 V0.38을 그대로 유지한다.
- Action Stack top margin은 V0.38보다 줄여 Model~API Key 영역에 3개 버튼이 자연스럽게 배치되도록 한다.
- 3번째 연결 테스트 버튼 하단과 API Key field 하단의 시각적 정렬을 우선한다.
- Action button width는 약 5% 확대하고 기능/handler는 변경하지 않는다.

### 20.2 File Drop State Geometry
- Ready/Empty 상태 전환은 text/style change이며 geometry change가 아니다.
- `FileDropZone`은 최소 크기와 Expanding SizePolicy를 갖고, File Card도 최소폭을 유지한다.
- `문서 n개가 준비되었습니다.`와 `파일 다시 선택` 문구는 그대로 사용한다.

### 20.3 External ALIRA Vision Verifier
- `ALIRA Vision Verifier V0.3`은 Requirement Studio Package에 포함하지 않는 독립 증빙 도구이며 V0.41 활성화 근거를 제공했다.
- 별도 프로그램은 Requirement Studio 코드를 import하지 않으며, 실제 ALIRA CLI/EncodeImage Vision 경로의 증빙을 Run folder로 보존한다.
- Main Package 내부 detachable Probe와 별도 Verifier는 역할이 다르다. Main Probe는 개발 진단용, 별도 Verifier는 증거 보존형 독립 검증 도구다.


## 21. V0.41 Verified ALIRA Native Vision

V0.41 changes ALIRA image transport from the dormant guessed Direct API path to the user-verified ALIRA CLI Image Tool path.

```text
Normalized image
  -> isolated work/alira_vision_runtime/<run>/image_NNN
  -> AliraClient.run_vision_prompt()
  -> general_agent + isolated --cwd + --no-permission-enabled
  -> EncodeImage/equivalent tool
  -> --output-format json envelope
  -> _extract_output_json()
  -> Visual Evidence parser
```

Rules:
- `alira.supports_images=true` and `vision_transport=cli_image_tool` are V0.41 defaults.
- Permission bypass is limited to the Native Vision subprocess call.
- Main ALIRA text generation and connection test behavior are unchanged.
- Direct gateway `/chat/completions` is not part of the ALIRA Native Vision production path.
- Native failure is recorded per visual and does not silently switch provider mid-run.
- Setting `supports_images=false` restores configured fallback selection without code changes.


### V0.41 Provider action layout
Provider action buttons are wrapped in `providerActionPanel` and bottom-aligned to the provider field grid. This removes the DPI/font-sensitive fixed top-margin positioning used previously.


## 22. V0.42 AI Settings Model/API Key Fine Alignment

V0.42 is a UI-only patch. The Provider row and provider Action Panel introduced in V0.41 remain unchanged.
Only the `Model` / `API Key` label-input pair is placed inside a dedicated `modelApiBlock` with an 8px top margin.
This isolates the requested vertical offset from provider selection, action buttons, connection badge, and runtime behavior.
The user manual is intentionally not revised for this cosmetic-only change.


## 23. V0.44 AI Settings Final Layout Reset

V0.44 removes the accumulated alignment constraints from FR-295, FR-304, FR-313, and FR-314 and replaces them with a single final-layout rule.

```text
AI Settings Card
  Header
    Title
    compact connection badge (34px)
  Body
    left provider grid
      AI Engine row
      explicit 28px spacer
      Model row
      API Key row
    right provider action panel
      Provider-aware Action 1
      Provider-aware Action 2
      AI connection test
  bottom stretch absorbs spare card height
```

The key correction is layout ownership: extra vertical space is no longer distributed into the header/status badge, and Model/API Key are no longer isolated in a V0.42-only `modelApiBlock`.
Runtime Provider behavior, ALIRA Native Vision, file-drop geometry, SWE.1 and SWE.6 are unchanged.


## 24. V0.44 Compact File Card

V0.44 keeps the V0.43 AI Settings / Execution layout unchanged and only reduces the vertical footprint of the file drop area inside the File & Options card. The goal is to pull the middle progress/check section upward without altering approved AI card geometry.
