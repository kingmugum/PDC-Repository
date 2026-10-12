# ALIRA Connection Setup — Requirement Studio V0.40

## 목적

Requirement Studio에서 ALIRA를 선택한 사용자가 발급받은 License를 프로젝트 폴더에 배치한 뒤, 로컬 ALIRA CLI와 사내 원격 Qwen/vLLM 연결을 순서대로 준비하는 절차를 정의한다.

## 확인된 구조

- ALIRA CLI는 Windows 사용자 PC에 설치된다.
- Windows 기본 설치 위치는 `%LOCALAPPDATA%\Programs\alira`이다.
- License는 기본적으로 ALIRA binary 옆 `license.lic`를 사용할 수 있고, 다른 위치는 `ALIRA_LICENSE_PATH`로 지정할 수 있다.
- Model/API Base는 ALIRA 실행 설정으로 전달할 수 있다.
- 현재 Requirement Studio 기본값은 `hosted_vllm/Qwen/Qwen3.6-27B`, `http://10.10.10.200:19640/v1`이다.
- 즉, 사용자 PC에는 ALIRA CLI가 있고 Qwen 추론은 사내 원격 vLLM 서버를 사용한다.

## Requirement Studio V0.40 정책

1. Root의 `alira_license/`를 Project-local License Drop Folder로 사용한다.
2. 실제 *.lic는 배포 ZIP에 넣지 않는다.
3. 사용자가 넣은 *.lic를 설치 폴더로 복사하지 않고 `ALIRA_LICENSE_PATH`로 전달한다.
4. CLI가 없으면 사용자에게 설치 여부를 확인한다.
5. 사용자가 승인한 경우에만 사내 공식 Windows `install.bat`을 실행한다.
6. Qwen Model 자체를 로컬 설치하지 않는다.
7. CLI / License / Model / API Server가 모두 준비된 뒤 실제 최소 Connection Test를 수행한다.
8. 실제 요청 성공 전에는 연결 정상으로 표시하지 않는다.

## Wizard 상태

- ALIRA CLI
- License
- Model
- API Server
- Connection Test

## Vision 통합

이 Wizard는 ALIRA 실행환경과 원격 LLM 연결을 구성합니다. 별도 ALIRA Vision Verifier V0.3 사용자 시험에서 CLI/general_agent Image Tool 경로가 randomized fixture 6/6 PASS로 확인되어 V0.40은 `supports_images=true`, `vision_transport=cli_image_tool`을 기본 사용합니다.

Native Vision 요청은 추출 이미지를 `work/alira_vision_runtime/<run>`으로 복사한 뒤 해당 폴더를 `--cwd`로 사용하고, Headless Image Tool 실행을 위해 Vision 호출에만 `--no-permission-enabled`를 적용합니다. Direct Qwen API endpoint를 추정하여 호출하지 않습니다. 필요 시 `supports_images=false`로 기존 fallback 정책에 즉시 복귀할 수 있습니다.
