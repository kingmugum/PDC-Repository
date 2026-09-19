# Signal Export V2 → H-Chat API Reference for Requirement Studio v0.18

본 문서는 사용자가 제공한 `Signal_Export_V2_260912_1` 패키지의 실제 H-Chat 연동 구조를 ALR 프로젝트에서 재사용하기 위해 요약한 내부 Reference입니다.

## 확인한 실제 H-Chat 연결 방식

### 공통

- Base URL: `https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3`
- API Key는 프로그램 Root의 `API_Key`류 TXT/무확장자 파일에서 자동 탐색
- 여러 Key 파일이 있으면 최신 수정 파일 우선
- Key 값 자체는 GUI/로그에 평문 출력하지 않음
- 선택적으로 `X-Project-Id` Header 사용
- Retry 기본 3회

### GPT

Signal Export Step 5는 `AzureOpenAI`를 사용합니다.

```text
AzureOpenAI(
  azure_endpoint = H-Chat Base URL,
  api_key        = API Key,
  api_version    = 2025-04-01-preview,
  default_headers = {X-Project-Id: ...}  # optional
)

client.chat.completions.create(
  model = selected GPT model,
  messages = [system?, user]
)
```

확인된 Model 목록:

- `gpt-5.6-terra` (Signal Export 기본값)
- `gpt-5.4`
- `gpt-5.2`

### Gemini

Signal Export Step 5는 `requests.post()`를 사용합니다.

```text
POST {BASE_URL}/models/{gemini_model}:{generateContent}?key={API_KEY}
Content-Type: application/json
X-Project-Id: optional
```

기본 Model:

- `gemini-3.1-pro-preview`

Payload는 `contents[].parts[].text`를 사용하고, System Message가 있으면 `systemInstruction.parts[].text`에 전달합니다.

## Requirement Studio 적용 원칙

v0.16의 `providers/hchat_provider.py`는 위 Signal Export 구조를 직접 Reference로 삼습니다.

다만 Signal Export의 업무 Prompt/결과 Format은 복사하지 않습니다. Requirement Studio는 자체 공통 Prompt Builder와 Canonical Requirement Contract를 사용하고, H-Chat Adapter는 **전송 규격 차이만 처리**합니다.

```text
Document IR / Common Prompt
        ↓
Provider Adapter
   ├─ ALIRA Headless
   ├─ H-Chat GPT
   └─ H-Chat Gemini
        ↓
Canonical Requirement JSON
```

## 아직 확인하지 않은 항목

- H-Chat의 이미지/파일 직접 업로드 API
- H-Chat의 실제 사용자 Project ID 필요 여부
- 사용자 계정에서 사용 가능한 최종 Model 목록/권한
- Claude/기타 H-Chat 모델의 API 형식

위 항목은 실제 H-Chat 접근 권한이 확보된 뒤 확인하며 추정하여 구현하지 않습니다.
