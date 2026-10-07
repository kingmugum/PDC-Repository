# Reference Contract Evaluation — v0.14

## 결론

PassFail rev87과 SignalAuto rev60은 서로 다른 업무 도구임에도 동일한 **이중 계층 요구사항 관리 패턴**을 사용하고 있어,
ALIRA의 SWE.1 Target Contract를 만드는 기준으로 사용하기에 적합합니다.

## 확인된 공통점

1. 두 파일 모두 `사용자 시나리오` + `AI_01~AI_10`의 11개 시트 구조를 사용합니다.
2. 두 파일의 `AI_02_요구사항목록`은 동일한 24개 열 구조를 사용합니다.
3. 상위 Scenario와 상세 FR을 연결하여 사람용 맥락과 AI용 원자 요구사항을 분리합니다.
4. 입력/전제 → 처리/동작 → 출력 → 판정 기준 → 실패 상황 → 변경 금지 → 테스트/근거까지 추적합니다.
5. 요구사항 수를 기능 수나 문장 수와 1:1로 고정하지 않는 구조입니다.

## 중요한 설계 결정

기존 `요구사항 유형` 열은 실제 예제에서 `유지/변경` 의미로 사용됩니다.
따라서 새 ALIRA 프로젝트에서 Explicit/Implicit을 이 열에 덮어쓰면 기존 의미와 충돌합니다.

v0.14는 Canonical Requirement에 별도 `derivation_type = explicit | implicit` 필드를 두고,
향후 생성 SWE.1에는 `도출 유형(Explicit/Implicit)` 열을 별도로 추가하는 방향으로 정의했습니다.

## SWE.6 샘플에서 확인한 사항

업로드된 SWE.6 결과서는 하나의 SW 요구사항에서 여러 Test Case가 파생되며,
`요구사항 기반 테스트`, `경계값 분석`과 같은 Test Method,
Preparation / Execution / Expected Result의 Variable·Compare·Value 구조를 사용합니다.

또한 해당 파일은 **시험 결과서**이므로 Output Value와 PASS/FAIL 값까지 존재합니다.
ALIRA가 시험 전 Test Specification을 생성할 때에는 이러한 실행 결과 필드를 임의로 채우면 안 됩니다.

## v0.14에서 채택한 방식

- 전체 대형 Excel을 매 Prompt에 그대로 넣지 않고, 대표 SWE.1 5건 + SWE.6 5건을 compact reference JSON으로 제공합니다.
- 원본 PassFail/SignalAuto Requirements는 `reference_library/raw/`에 보존합니다.
- Reference는 산출물 구조/패턴만 알려주며, 현재 입력 문서의 사실을 대신하지 못합니다.
- 사용자 판단 원칙은 `policy/requirement_judgment_policy.json`에서 수정할 수 있습니다.
- No Hallucination / Source Traceability 같은 보호 원칙은 `policy/protected_invariants.json`에 분리합니다.

## 현재 평가 한계

이 평가는 **Reference Contract/구조 설계 평가**입니다.
실제 Qwen이 새로운 문서에서 요구사항을 얼마나 잘 추출하는지는 이 환경에서 사내 ALIRA/Qwen Runtime을 호출할 수 없으므로
사용자 PC에서 v0.14의 `[요구사항 추출]`을 실행한 결과로 평가해야 합니다.
