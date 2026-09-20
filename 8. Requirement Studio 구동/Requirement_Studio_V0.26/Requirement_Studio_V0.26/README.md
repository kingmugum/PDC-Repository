# Requirement Studio V0.26

V0.26은 실제 ALIRA/Qwen 실행 중 확인된 긴 Requirement JSON 파싱 실패를 기반으로 **Runtime 안정성**을 강화한 버전입니다.

## 핵심 변경

- AI 연결 테스트 Popup에 **경과시간 + 진행률(%)**을 함께 표시합니다.
- 동일 Provider / Model / API 연결 Signature가 유지되는 동안 연결 테스트 성공상태를 보존합니다.
- Checklist 7개가 모두 정상일 때 하단 버튼을 **`모든 항목 확인됨`**으로 표시합니다.
- 결과영역에 **`로그 복사`** 버튼을 추가했습니다. Clipboard 복사와 `output/logs` TXT 저장을 동시에 수행합니다.
- 완료 / 부분완료 / 실패 시 진행 로그 Snapshot을 자동 저장합니다.
- Requirement JSON 파싱 실패 시 Raw 응답을 `work/recovery_failures`에 보존하고, 실패 SOURCE를 작은 **non-overlap** 단위로 자동 분할해 재추출합니다.
- 자동 복구가 실패해도 GUI에 긴 Raw JSON 전체를 표시하지 않고 실패 요약과 진단파일 위치를 안내합니다.
- AI request/response 파일명에 microsecond timestamp를 사용하여 빠른 Recovery 요청 간 덮어쓰기를 방지합니다.

## 실행

1. `Requirement Studio.exe` 실행을 먼저 시도합니다.
2. unsigned EXE가 Windows 보안제품에 의해 차단되면 `Requirement Studio.pyw`를 사용합니다.
3. 보안 기능을 끄거나 예외를 강제 등록하는 기능은 포함하지 않습니다.

## 문서

- Requirements: `Requirement_Studio_Requirements_Management_rev24.xlsx`
- Governance: `00_AI_DEVELOPMENT_GOVERNANCE.md`
- User Manual: `docs/Requirement_Studio_사용자_매뉴얼_v0.11_V0.26.docx`
- 다음 신규 FR: `FR-170`

## 검증 상태

- Python syntax/static: PASS
- Requirements formula scan: PASS
- Mock JSON truncation recovery: PASS
- Recovery failure concise-error path: PASS
- 실제 Windows GUI / Clipboard: 사용자 환경 확인 필요
- 실제 ALIRA/H-Chat에서 JSON Recovery 재현: 사용자 환경 확인 필요
