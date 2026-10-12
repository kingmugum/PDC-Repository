# Requirement Studio H-Chat API Reference — V0.52

본 문서는 Requirement Studio의 H-Chat Provider 전송 규격 요약입니다.
V0.52의 Gemini/Claude 부분은 사용자가 제공한 H-Chat v3 API Spec을 기준으로 갱신했습니다.

## 공통
- Base URL: `https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3`
- API Key는 Root/api_keys에서 탐색하거나 GUI에서 런타임 수동 입력
- Project API Key일 때 `X-Project-Id` Header 사용
- Key 평문은 로그/산출물에 노출하지 않음

## GPT
기존 AzureOpenAI 기반 Requirement Studio H-Chat GPT Adapter를 유지합니다.

## Gemini 3.7 Flash
Model ID:
- `gemini-3.7-flash`

Endpoint:
```text
POST {BASE_URL}/models/gemini-3.7-flash:generateContent
Authorization: Bearer <API_KEY>
X-Project-Id: optional
Content-Type: application/json
```

REST Payload는 `contents`, `systemInstruction`, `inlineData`, `mimeType` 등 Camel Case를 사용합니다.
Gemini Thinking Part에서 `thought=true`인 text는 최종 응답으로 합치지 않습니다.

## Claude Sonnet 5
Model ID:
- `claude-sonnet-5`

Endpoint:
```text
POST {BASE_URL}/claude/messages
Authorization: Bearer <API_KEY>
X-Project-Id: optional
Content-Type: application/json
```

Payload 핵심:
- model
- messages
- max_tokens
- system (optional)
- thinking (optional)

Sonnet 5에서는 비기본 temperature/top_p를 전송하지 않습니다.
V0.52는 Requirement JSON 출력 안정성을 위해 thinking=disabled를 기본값으로 사용하며 config에서 adaptive로 변경 가능합니다.

Image 입력은 Messages content의 base64 image block으로 전송합니다.

## Requirement Studio 적용 원칙
Provider Adapter는 전송 규격만 처리합니다.
Requirement Prompt, Canonical Schema, Coverage/Regression 정책은 Provider 교체 때문에 변경하지 않습니다.
Provider/Model이 달라지면 run_compatibility에서 cross-model 변수로 기록합니다.
