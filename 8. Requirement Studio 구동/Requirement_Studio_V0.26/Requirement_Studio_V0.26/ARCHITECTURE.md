# Requirement Studio Architecture — v0.26

## Product / Provider 경계

- 제품명은 `Requirement Studio`이다.
- `ALIRA / Qwen`은 H-Chat/GPT, H-Chat/Gemini와 동등한 선택형 Provider 중 하나이다.
- 프로그램 시작 시 특정 Provider에 자동 연결하지 않는다.
- Provider/Model 선택 후 사용자가 수동 Connection Test를 하거나 실제 작업을 실행할 때 Provider가 사용된다.

## 1. 목표

Requirement Studio를 특정 AI 도구 전용 프로그램이 아니라 **교체 가능한 AI Provider를 사용하는 Requirement Engineering Pipeline**으로 구성한다.

```text
Source Document
   ↓
Local Document Normalizer
   ↓
Canonical Document IR (JSON/JSONL)
   ↓
Compact Prompt Builder
   ↓
AI Provider Adapter
   ├─ ALIRA / Qwen
   ├─ H-Chat / GPT
   └─ H-Chat / Gemini
   ↓
Canonical Requirement JSON
   ↓
Deterministic Validator
   ↓
Future: SWE.1 Renderer → TC Derivation → SWE.6 Renderer
```

## 2. 핵심 원칙

1. Source Document는 항상 로컬 원본을 유지하고 직접 수정하지 않는다.
2. AI Provider가 바뀌어도 판단정책, Reference, Canonical Contract는 동일하다.
3. Provider Adapter는 인증/전송/응답 차이만 담당한다.
4. H-Chat에 원본 파일을 직접 올리는 것을 기본으로 하지 않고, 먼저 로컬에서 Text/Table 중심 Document IR로 정규화한다.
5. H-Chat API Key는 Signal Export와 동일하게 Root의 `API_Key`류 파일에서 자동 탐색하며 Key 값은 로그/GUI에 노출하지 않는다.
6. v0.16의 Visual Asset는 감지만 하고 Text Provider로 직접 전송하지 않는다. 그림에 의존하는 사실은 추정하지 않고 Gap/TBD로 남긴다.
7. AI 응답은 Provider별 자유형 산출물이 아니라 동일 `REQ-STUDIO-CANONICAL-REQ-1.0` JSON으로 수렴한다.

## 3. Module Responsibility

| Module | Responsibility |
|---|---|
| `main.py` | PySide6 GUI, Provider 선택, 작업 Orchestration, 상태 표시 |
| `core/document_manager.py` | input 폴더와 복수 Source Document Batch 목록 관리 |
| `core/document_normalizer.py` | PDF/DOCX/PPTX/XLSX/XLSM → Local Document IR |
| `core/prompt_builder.py` | 공통 판단정책/Reference/Schema + Compact Source Prompt 생성, 안전 분할, JSON 실패 Recovery용 Source 소분할 |
| `core/ai_job_runner.py` | Normalize → Prompt → Provider → Raw Exchange → Parse/Recovery → Merge 흐름 |
| `core/requirement_engine.py` | Canonical JSON Parse/Merge/Structure Validate/Save |
| `providers/base.py` | Provider 공통 Interface/Metadata |
| `providers/alira_provider.py` | ALIRA Headless Adapter |
| `providers/hchat_provider.py` | Signal Export 구조를 참고한 H-Chat GPT/Gemini Adapter |
| `providers/hchat_credentials.py` | Signal Export와 동일한 Root API_Key류 파일 자동 탐색 |
| `providers/config_store.py` | 선택 Provider/Model/API 설정 보존 |
| `providers/factory.py` | Provider 생성 경계 |
| `core/result_exporter.py` | 분석 결과 DOCX 산출 |
| `policy/` | 사용자 수정 판단정책 + 보호 Invariant |
| `reference_library/` | SWE.1/SWE.6 Reference Example |
| `contracts/` | Canonical Requirement / SWE.1-SWE.6 Mapping 계약 |
| `work/normalized/` | 로컬 Document IR Runtime 영역 |
| `work/ai_requests/` | 실제 AI 전송용 Compact Text Runtime 기록 |
| `work/ai_responses/` | Raw AI 응답 Runtime 기록 |
| `work/recovery_failures/` | malformed/truncated JSON Raw 응답 및 Parser 오류 진단 보존 |
| `output/` | 승인 산출물/Canonical Requirement JSON/분석 DOCX/로그 Snapshot |

## 4. H-Chat Adapter

H-Chat 연동은 사용자가 제공한 Signal Export V2의 검증된 Step 5 구현을 Reference로 한다.

### GPT

```text
AzureOpenAI
  azure_endpoint = https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3
  api_version    = 2025-04-01-preview
  api_key        = Root API_Key류 TXT
  X-Project-Id   = optional

chat.completions.create(model, messages)
```

### Gemini

```text
POST {base_url}/models/{model}:generateContent?key={api_key}
Content-Type: application/json
X-Project-Id: optional
```

v0.16에서는 Signal Export에서 실제로 확인된 GPT/Gemini 경로만 구현한다. Claude/파일 직접 업로드/이미지 API는 실제 H-Chat 접근 후 확인하기 전까지 추정 구현하지 않는다.

## 5. Document IR와 Token 절감

로컬 보관은 JSON/JSONL을 사용한다.

```json
{"chunk_id":"DOC-C0001","kind":"text","location":"Page 3","text":"..."}
```

AI 전송 시에는 반복 JSON Key를 제거한 Compact Text로 바꾼다.

```text
[SRC DOC-C0001 | Page 3 | text]
...

[SRC DOC-C0002 | Page 4 | table]
...
```

따라서 **로컬 구조화 = JSON**, **AI 전송 = Compact Text**, **AI 반환 = Strict JSON**으로 역할을 분리한다.

## 6. Large Document

Signal Export의 H-Chat Prompt 안전 분할 기준을 참고해 요청 1개를 약 `90,000 chars` 이하로 구성한다.

큰 문서는 Chunk 묶음별로 AI 요청을 수행하고, Local Requirement Engine이 Candidate/Scenario/Gap을 다시 번호화하여 하나의 Canonical JSON으로 병합한다.

현재 병합은 결정론적 Exact-source 기반이며, Chunk 간 의미적 중복 통합은 향후 별도 Semantic Merge 단계로 확장한다.

## 7. Visual Asset

v0.16:

- DOCX/PPTX/XLSX embedded media 존재 여부 감지
- PDF page image 존재 여부 best-effort 감지
- `VISUAL_ASSET_COUNT`와 경고를 Prompt에 포함
- 이미지를 AI에 직접 보내지 않음
- 그림 의존 정보는 Gap/TBD 우선

향후 H-Chat 이미지/파일 API가 실제 확인되면 Provider Capability에 `supports_images`를 추가하여 확장한다.

## 8. 검증 상태

- Document Normalizer: 샘플 PDF/DOCX/PPTX/XLSX 4종 로컬 변환 확인
- Prompt Builder: Compact Prompt/90k 안전 분할 정적·합성 확인
- Provider Factory: ALIRA/H-Chat GPT/H-Chat Gemini 생성 정적 확인
- Mock Provider: Normalize → Prompt → Canonical JSON → Structure Score 100 합성 확인
- ALIRA 실제 Runtime: 기존 사용자 환경 확인 이력 있음, v0.16 공통 Prompt 경로는 사용자 재확인 필요
- H-Chat 실제 Runtime: 접근권한/실 API 호출 미확인


## V0.20 Dashboard UX

- 상단 좌측: 파일 및 옵션 설정 (Drag & Drop / 파일 선택 / 폴더 열기 / 새로고침)
- 상단 우측: AI 설정 (ALIRA/GPT/Gemini Radio, Model Dropdown, API Key 상태, Connection Test, Primary Action)
- 중단 좌측: 실제 Pipeline STEP 1~7 + 전체/현재 단계 2중 Progress
- 중단 우측: 7개 필수 Checklist + 상세 원인 확인 Popup
- 하단: 진행 로그 / 문서 분석 결과 / 요구사항 후보 Tab, Global `output 폴더 열기`
- 성공 시 분석 결과 DOCX와 Canonical Requirement JSON을 자동 저장한다.
- 실행 후 1.8초 arming 뒤 `중지`로 전환하며, 중지는 외부 AI 호출 강제 Kill이 아닌 Cooperative Stop을 사용한다.


## Multi-document Batch

V0.20부터 input 폴더는 지원문서를 1개 이상 허용한다.

```text
input/
 ├─ spec_A.pdf
 ├─ spec_B.docx
 └─ spec_C.xlsx
       ↓
문서별 독립 Pipeline (순차)
       ↓
A: IR → Prompt → AI → Canonical JSON → DOCX
B: IR → Prompt → AI → Canonical JSON → DOCX
C: IR → Prompt → AI → Canonical JSON → DOCX
```

- 여러 문서를 하나의 거대한 Prompt로 합치지 않는다.
- 전체 Progress는 Batch 전체 기준, 현재 Progress는 현재 문서/Step 기준이다.
- 문서 수와 총 분량이 늘어나면 실행 시간과 AI 호출량은 거의 비례해 증가한다.
- 한 문서가 실패해도 사용자 중지가 아니라면 다음 문서를 계속 처리한다.
- 서로 다른 문서를 하나의 통합 Spec으로 Cross-reference하는 Bundle Mode는 아직 지원하지 않는다.

## V0.26 Runtime Robustness

### Connection State

- Connection Test Popup은 Provider progress와 실제 경과시간을 함께 표시한다.
- 연결 성공 상태는 Provider ID / Model / API Base / Credential source signature가 동일한 동안 유지한다.
- 단순 분석 시작을 위한 Provider 객체 재생성은 연결 상태를 초기화하지 않는다.
- Provider/Model/Signature가 달라질 때만 `AI 연결 확인 전`으로 되돌린다.

### Requirement JSON Recovery

```text
Requirement AI Response
        ↓
Strict JSON Parse
   ├─ Success → Merge / Validate
   └─ Fail
        ↓
Raw Response Archive
(work/recovery_failures)
        ↓
Failed SOURCE only
non-overlap small split
        ↓
AI re-extraction per split
        ↓
Strict JSON Parse
        ↓
Deterministic Merge
```

- 잘린 JSON을 로컬에서 임의로 완성하지 않는다.
- 정상 응답에는 Recovery 추가 호출이 발생하지 않는다.
- Parse 실패 때만 작은 Source 단위로 재추출하여 AI 출력 길이를 줄인다.
- Recovery가 다시 실패하면 GUI에는 전체 Raw JSON 대신 실패 개수/Parser 요약/진단파일 위치만 표시한다.
- Request/Response 파일명은 microsecond timestamp를 사용하여 빠른 Recovery 요청 간 덮어쓰기를 방지한다.

### Runtime Log

- `로그 복사`는 Clipboard 복사와 `output/logs` TXT Snapshot을 동시에 수행한다.
- 완료/부분완료/실패 시에도 Log Snapshot을 자동 보존한다.
- Credential 평문은 기존 정책대로 Log에 기록하지 않는다.

