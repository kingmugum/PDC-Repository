# Requirement Studio — H-Chat API Key Guide (V0.58)

## Key 배치
Requirement Studio Root의 `api_keys/` 폴더에 파일명에 `API_Key`가 포함된 TXT 파일을 배치합니다.
TXT 내용은 Key 한 줄 또는 `API_KEY=<value>` 형식을 사용할 수 있습니다.
설명/README/샘플 파일은 Key 후보에서 제외됩니다.

## 수동 입력
H-Chat Provider를 선택한 상태에서 `[API Key 수동 입력]`으로 입력할 수 있습니다.
수동 Key는 현재 실행 메모리에만 저장하며 config/로그/산출물에 기록하지 않습니다.

## H-Chat v3 인증
Gemini 3.7 Flash와 Claude Sonnet 5는 사용자 제공 H-Chat v3 사양에 따라 다음 Header를 사용합니다.

Personal API Key:
```text
Authorization: Bearer <H_CHAT_API_KEY>
```

Project API Key:
```text
Authorization: Bearer <H_CHAT_API_KEY>
X-Project-Id: <project_id>
```

## 현재 H-Chat 모델
- GPT: 기존 Requirement Studio GPT Catalog 유지
- Gemini: `gemini-3.7-flash`
- Claude: `claude-sonnet-5`

## 보안 원칙
- Key 평문을 GUI/로그/Prompt/결과 문서/package manifest에 기록하지 않습니다.
- 실제 API Key 파일을 배포 ZIP에 포함하지 않습니다.


## V0.58 API KEY 상태 표시

H-Chat Provider에서는 API Key 탐색 결과를 폴더 버튼에 직접 표시합니다.

- `API KEY 없음 (폴더 열기)`: 주황색
- `API KEY 확인 됨 (폴더 열기)`: 옅은 초록색

`api_keys` 폴더 변경은 QFileSystemWatcher로 자동 감지합니다.
