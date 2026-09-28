# Requirement Studio — H-Chat API Key Guide

## 권장 방식

Requirement Studio Root 아래 `api_keys/` 폴더에 `API_Key` 문자열이 포함된 TXT 파일을 배치합니다.

```text
Requirement_Studio_V0.37/
├─ api_keys/
│  ├─ README_API_KEY_사용법.txt
│  └─ 260919_API_Key_1차.txt
└─ ...
```

TXT 내용은 Key 값 한 줄 또는 `API_KEY=<value>` 형식을 사용할 수 있습니다. 여러 Key 파일이 있으면 가장 최근 수정된 유효 파일을 우선 사용합니다. `README`, `사용법`, `GUIDE`, `샘플` 등의 설명 파일은 후보에서 자동 제외됩니다. 또한 Key 값은 공백 없는 printable ASCII token인지 사전 검증합니다.

Signal Export 호환성을 위해 프로젝트 Root의 API_Key류 파일도 계속 검색합니다.

## 수동 입력

H-Chat Provider(GPT/Gemini/Claude)를 선택한 상태에서 `[API Key 수동 입력]`을 누르면 Key를 직접 입력할 수 있습니다. 이 값은 현재 실행 메모리에만 보관하고 파일이나 config에 저장하지 않습니다.

## 보안 원칙

- Key 평문을 GUI, 로그, Prompt, 결과 문서, package manifest에 기록하지 않습니다.
- 배포 ZIP에 실제 API Key 파일을 포함하지 않습니다.
- Key가 누락되면 체크리스트에서 `미확인`으로 표시합니다.


## Claude Skeleton 주의

V0.37에는 H-Chat Claude 선택 골격이 포함되어 있으나 회사의 실제 Claude Protocol/Base URL/Endpoint/Model 규격은 아직 TBD입니다.
실제 연결 규격을 확인한 뒤 `config/provider_config.json`의 Claude 항목을 갱신합니다. H-Chat API Key가 동일 Credential을 사용하는지 여부도 회사 규격 확인 후 확정합니다.
TBD 상태에서는 연결 테스트가 설정 필요 오류를 반환하는 것이 정상입니다.
