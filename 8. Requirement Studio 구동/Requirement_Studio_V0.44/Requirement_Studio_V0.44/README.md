# Requirement Studio V0.44

V0.44는 V0.43의 기능 동작을 유지하면서, **파일 및 옵션 설정 Card의 드롭 영역 높이만 축소하여 상단/중단 레이아웃을 더 컴팩트하게 정리한 UI 수정 버전**입니다.

## V0.44 AI 설정 최종 시안

- 과거 정렬 Requirement `FR-295`, `FR-304`, `FR-313`, `FR-314`는 rev46에서 제거했습니다.
- AI 연결 상태 Badge는 약 34px 높이의 compact pill로 제한합니다.
- AI Engine Row 아래 약 28px spacer를 두고 Model/API Key를 같은 Grid에 직접 배치합니다.
- 우측 3개 Provider Action은 154~166px 폭을 유지하고 본문 하단 기준으로 배치합니다.
- Header/Body가 남는 Card 높이를 강제로 차지하지 않도록 Card 하단 Stretch가 여유 공간을 흡수합니다.
- File Drop 안정화, Provider-aware Action, ALIRA Native Vision, SWE.1/SWE.6 동작은 변경하지 않습니다.
- 사용자 매뉴얼은 기능 변경이 없는 UI-only 수정이므로 기존 `v0.29 / V0.42`를 그대로 포함합니다.

## V0.41 ALIRA Native Vision 활성화

- 별도 `ALIRA Vision Verifier V0.3` 실제 사용자 시험에서 이미지 없는 Control은 정답을 회수하지 못했고, ALIRA CLI/general_agent Image Tool 경로는 randomized image-only fact **6/6 PASS**를 기록했습니다.
- V0.41은 이 실증 결과를 근거로 `alira.supports_images=true`, `alira.vision_transport=cli_image_tool`을 기본 적용합니다.
- 문서에서 추출한 이미지는 요청마다 `work/alira_vision_runtime/<run>/` 격리 폴더에 복사하고, ALIRA의 `--cwd`를 해당 폴더로 제한합니다.
- Headless에서는 Image Tool 권한 질문을 받을 수 없으므로 **ALIRA Native Vision 호출에만** `--no-permission-enabled`를 사용합니다. 일반 Text 호출/Connection Test 정책은 그대로 유지합니다.
- V0.37에 준비했던 추정 Direct API image payload 경로는 Main ALIRA Native Vision에서 사용하지 않습니다. 실제 시험에서 Direct API `/chat/completions` route가 404였고, 검증된 경로는 ALIRA CLI Image Tool이었기 때문입니다.
- ALIRA Native Vision이 실패하면 해당 Visual만 `failed`로 기록하고 Text/Table 분석은 계속합니다. 실패한 그림을 H-Chat 결과로 조용히 대체하지 않습니다.
- 즉시 원복이 필요하면 `config/provider_config.json`의 `alira.supports_images`를 `false`로 바꾸면 기존 configured Vision fallback 정책으로 돌아갈 수 있습니다.

## V0.41 AI 설정 / ALIRA 연결 설정

- AI 설정 우측 Action 3개는 Model~API Key 영역에 걸쳐 배치하고, 세 번째 버튼 하단을 API Key 입력칸 하단과 맞춥니다.
- GPT/Gemini/Claude: `API Key 폴더 열기` / `API Key 수동 입력` / `AI 연결 테스트`
- 기타(Custom): `기타 API 설정` / `API Key 수동 입력` / `AI 연결 테스트`
- ALIRA: `ALIRA 연결 설정` / `설정 폴더 열기` / `AI 연결 테스트`
- ALIRA를 선택했을 때 의미 없는 Disabled API Key 버튼을 남기지 않고 동일 슬롯을 Provider 전용 Action으로 전환합니다.

### ALIRA 연결 Wizard

Requirement Studio에서 사용하는 ALIRA 구조는 **로컬 ALIRA CLI + 사내 원격 Qwen/vLLM 서버**입니다. Qwen 모델 자체를 로컬에 설치하지 않습니다.

1. `[ALIRA 연결 설정]`을 누르면 Root의 `alira_license/` 폴더를 엽니다.
2. 사용자가 발급받은 `*.lic` 파일을 넣으면 Wizard가 감지합니다. 실제 License 파일은 배포 ZIP에 포함하지 않습니다.
3. License는 ALIRA 설치 폴더로 복사하지 않고 ALIRA subprocess에 `ALIRA_LICENSE_PATH`로 전달합니다.
4. 로컬 ALIRA CLI가 없으면 사용자에게 1회 확인한 뒤 사내 공식 `install.bat` 설치를 실행할 수 있습니다.
5. Config의 ALIRA Model/API Base를 적용하고, 준비가 끝나면 실제 최소 ALIRA→Qwen 연결 테스트를 수행합니다.
6. 실제 연결 테스트가 성공한 경우에만 Main 상태를 연결 정상으로 표시합니다.

기본 연결 정보는 현재 Config 기준 `hosted_vllm/Qwen/Qwen3.6-27B`, `http://10.10.10.200:19640/v1`입니다.

### 로그 복사 Feedback

- `[로그 복사]` 성공 시 약 1.9초간 `✓ 복사 완료` + 연한 초록 상태로 표시 후 자동 복귀합니다.
- 복사할 로그가 없으면 짧은 경고 상태 후 자동 복귀합니다.
- 반복 작업을 방해하는 별도 Popup은 사용하지 않습니다.

## 핵심 원칙

- 입력문서가 factual Source of Truth입니다.
- Canonical Requirement가 내부 Single Source of Truth입니다.
- SWE.1 Word / SWE.1 Excel / SWE.6 Excel은 동일 Canonical에서 파생합니다.
- Provider와 Model은 출력 형식과 분리합니다.
- Source에 없는 신호/수치/상태/시험방법을 임의 생성하지 않습니다.
- Gap/TBD/Conflict 등 품질정보는 내부 Canonical/Review 정보로 유지할 수 있으나 최종 산출물은 일반 엔지니어 관점으로 단순화합니다.
- 자체 제작 EXE는 포함하지 않으며 공식 실행 진입점은 `Requirement Studio.pyw`입니다.

## AI Engine / Model

Dashboard AI Engine:

- GPT (H-Chat)
- Gemini (H-Chat)
- Claude (H-Chat Skeleton)
- ALIRA / Qwen
- 기타(Custom API)

모든 Provider는 **현재 Model + 선택 가능한 Model 목록**을 Config에서 관리할 수 있습니다. AI Engine을 바꾸면 Model Dropdown도 해당 Provider의 목록으로 바뀝니다.

주요 Config:

- GPT: `hchat.gpt_model`, `hchat.gpt_model_options`
- Gemini: `hchat.gemini_model`, `hchat.gemini_model_options`
- Claude: `hchat.claude_model`, `hchat.claude_model_options`
- ALIRA: `alira.model`, `alira.model_options`
- 기타: `custom.model`, `custom.model_options`

Gemini/Claude의 실제 사내 최신 Model ID는 임의 추정하지 않습니다. 회사에서 확인한 ID를 Config에 추가/교체하는 구조입니다.

## H-Chat Claude Skeleton

V0.41은 `hchat_claude` Provider Skeleton을 제공합니다.

현재 회사 H-Chat Claude의 실제 Protocol/Base URL/Endpoint/Model 규격이 미확정이므로 기본값은 TBD입니다. TBD 상태에서 연결 테스트를 실행하면 설정이 필요하다는 오류를 반환하며 정상 연결로 표시하지 않습니다.

확인 후 교체할 항목:

- `claude_protocol`
- `claude_base_url`
- `claude_endpoint`
- `claude_model`
- `claude_model_options`
- `claude_api_version`
- `claude_supports_images`

## 기타(Custom API)

지원 Profile:

- OpenAI-compatible Chat Completions
- OpenAI Responses
- Anthropic Messages
- Gemini generateContent

설정 항목:

- API Base / Endpoint
- Model / Model 목록
- API Key 사용 여부
- Auth Mode: Auto / Bearer / x-api-key / Query Key / None
- API Key Header/Query 이름
- 선택적 API Version Header
- 이미지 입력 여부

`profile_flags`로 Profile을 개별 활성/비활성할 수 있어 신규 확장 Profile을 롤백해도 기존 Profile을 유지할 수 있습니다. 실제 API Key 값은 config/log에 평문 저장하지 않습니다.

완전히 독자적인 요청/응답 규격은 별도 Provider Adapter가 필요합니다.

## ALIRA Vision 검증 도구

`diagnostics/ALIRA_Vision_Probe/`는 본체와 분리된 진단 폴더로 유지합니다. V0.41의 제품 Native Vision 활성화 근거는 별도 배포된 `ALIRA Vision Verifier V0.3` 사용자 실행 결과입니다.

`diagnostics/ALIRA_Vision_Probe/`

본체는 이 모듈을 import하지 않으므로 폴더 전체를 삭제해도 Requirement Studio의 정상 기능에 영향이 없습니다.

Probe 목적:

1. 환경/ALIRA CLI 도움말 확인
2. Direct API Image 입력 시험
3. 실제 확인된 CLI Image Argument 시험
4. Text-only와 Image 입력 A/B 비교
5. 검증 후 `alira.supports_images=true/false`를 명시적으로 전환

별도 Verifier V0.3의 실제 사용자 시험에서 ALIRA CLI Image Tool 경로 6/6 PASS가 확인되었습니다. V0.41 제품 기본값은 `supports_images=true`이며, Requirement Studio End-to-End만 사용자 환경에서 추가 확인합니다.

## 진행 상태 UI

- `전체 진행률`: Local Pipeline STEP 기반 실제 Overall % 표시
- `현재 단계 상태`: 짧은 업무 상태 문구 표시
- 실행 중: 3개의 점이 순차 강조되는 Activity Indicator
- 완료/오류/대기: Activity Indicator 정지
- 현재 단계에 별도의 모델 내부 % 또는 Busy Progress Bar를 표시하지 않습니다.
- AI 연결 테스트의 ALIRA elapsed heartbeat는 연결 진단용으로 유지합니다.
- 실제 분석 실행은 요청 전송 → 응답 대기 → 응답 수신 → 결과 정리 → 단계 완료 Event 중심입니다.
- Progress 표시만을 위한 별도 서버 Polling은 추가하지 않습니다.

## SWE.1

### Word

`SWE.1 요구사항 정리_<원본문서>_<YYMMDD>_<V버전>.docx`

최종 표시 11개 필드:

- SRS ID
- 상위 기능
- 분류
- 요구사항 내역
- 동작 조건 / Trigger
- 작동 명세 정의
- 사전 조건
- 예상 결과
- 검증 기준
- 출처 / Traceability
- 기타

Word 표는 항목 약 24% / 내용 약 76% 폭을 사용합니다.

### Excel

`SWE.1 요구사항 명세_<원본문서>_<YYMMDD>_<V버전>.xlsx`

기본 Sheet:

- `00_Overview`
- `01_SWE1`
- `02_Traceability`

Traceability는 Input Source → SWE.1 SRS → SWE.6 TC 연결을 우선합니다.

## SWE.6

`SWE.6 적격성 평가_<원본문서>_<YYMMDD>_<V버전>.xlsx`

SWE.6는 선택 AI가 Excel을 직접 쓰는 방식이 아니라 Canonical 이후 Local Exporter가 공통 규칙으로 생성합니다.

기본 Sheet:

- `표지`
- `0_변경이력`
- `1_테스트요약`
- `2_테스트 케이스`

Test Case Sheet는 6개 Group Header + 21개 상세열을 사용합니다. `Tolerance lower`, `Tolerance upper`, `Capture Environment`는 생성하지 않습니다.

## 실행

1. ZIP 압축을 해제합니다.
2. `Requirement Studio.pyw`를 더블클릭합니다.
3. `.pyw` 연결이 없는 환경에서는 `pythonw "Requirement Studio.pyw"` 또는 `pyw "Requirement Studio.pyw"`를 사용합니다.
4. 실제 H-Chat 사용 시 `api_keys/` 또는 프로젝트 Root의 기존 H-Chat API Key TXT 형식을 사용할 수 있습니다.

## 기준 문서

- Package: `Requirement_Studio_V0.44.zip`
- Requirements: `Requirement_Studio_Requirements_Management_rev43.xlsx`
- User Manual: `docs/Requirement_Studio_사용자_매뉴얼_v0.27_V0.41.docx`
- SWE.1 Guide: `reference/OUTPUT_AUTHORING_GUIDE.md`
- SWE.6 Guide: `reference/SWE6_AUTHORING_GUIDE.md`
- Next FR: `FR-313`

## 검증 경계

제작 환경에서 정적/합성 검증 가능한 항목은 Package Manifest에 기록합니다.

사용자 환경 확인이 필요한 항목:

- Windows PySide6 실제 Dashboard / 3-dot Animation 렌더
- 실제 H-Chat Claude 연결
- Requirement Studio V0.41 ALIRA Native Vision End-to-End (그림 포함 문서 → Visual Evidence > 0)
- 최신 사내 Gemini Model ID
- 실제 고객사/외부 Custom API End-to-End
- 실제 Windows ALIRA Setup Wizard 렌더 및 사내 공식 install.bat 실행
- 실제 Project-local License 검증 및 ALIRA→Qwen 자동 연결 테스트

미확인 Runtime은 PASS로 기록하지 않습니다.


## V0.39 UI 안정화 (유지)

- AI 설정 우측 3개 Action은 Model~API Key 영역에 걸쳐 배치하고, `AI 연결 테스트` 하단을 API Key 입력칸 하단과 맞추도록 V0.38보다 위로 조정합니다.
- Action 버튼 가로폭을 약 5% 확대하여 `API Key 폴더 열기` 등 한글 Label의 시각적 잘림을 완화합니다.
- File Drop Zone은 최소 276x174 및 Expanding SizePolicy를 사용하고 File Card 최소폭을 유지하여 문서 인식 전/후 크기가 갑자기 줄어들지 않게 합니다.
- 별도 `ALIRA Vision Verifier V0.3`은 메인 Package에 포함하지 않는 독립 증빙 도구이며, 실제 사용자 실행 6/6 결과가 V0.41 Native Vision 활성화 근거입니다.


## V0.41 ALIRA Native Vision Runtime Flow

```text
DOCX/PDF/PPTX/XLSX embedded image
  ↓
Document Normalizer extraction
  ↓
work/normalized/.../visuals
  ↓
ALIRA Provider (supports_images=true)
  ↓
work/alira_vision_runtime/<run>/image_001.* staging
  ↓
ALIRA CLI / general_agent / isolated --cwd
  + --no-permission-enabled (Vision call only)
  ↓
EncodeImage or equivalent Image Tool
  ↓
Visual Evidence JSON
  ↓
Text/Table/Visual 통합 분석
```

Expected log when ALIRA is selected:

`Vision 경로 · Main=ALIRA / Qwen ... · Vision=ALIRA / Qwen ... (Native)`

V0.41 build environment에서는 CLI command/staging/output-envelope을 synthetic 검증합니다. 실제 회사 PC의 그림 포함 문서 End-to-End는 사용자 Runtime 확인 후 PASS 처리합니다.


## V0.41 UI alignment
- AI 설정 우측 Action Stack은 fixed top margin 대신 provider field 영역 하단 기준 Layout alignment를 사용합니다.
- `AI 연결 테스트` 하단이 API Key 영역 하단과 자연스럽게 맞도록 하며 버튼 폭은 154~166px 범위로 유지합니다.
- V0.40의 ALIRA Native Vision 기능과 산출물 구조는 변경하지 않습니다.