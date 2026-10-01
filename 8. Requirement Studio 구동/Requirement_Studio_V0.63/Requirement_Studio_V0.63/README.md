# Requirement Studio V0.63

V0.63은 두 SWE.6 Reference Source에서 반복 확인된 single-truth/audit 잔여 문제를 일반 규칙으로 마무리하는 Evidence Hardening Build입니다. **Source에 없는 값은 만들지 않되, Source에 이미 존재하는 fact는 clause-level provenance와 value-role을 유지한 채 Canonical → Test Intent → SWE.6로 전달**하는 것이 핵심입니다.

## V0.63 핵심 변경

- SWE.6 실행 결과 4개 필드(Output Value / PASS·FAIL / Comment / Capture) 생성 시 항상 Blank
- Source Table `Value Role` 도입: Single Required / Timing / Enum / Range / Invalid / Encoding / Literal
- Enum/Range/Encoding의 임의 member를 TC 값으로 자동 선택하지 않음
- 복합 Semantic Source Unit을 stable Source Fact Fragment로 분리하여 SRS별 clause ownership 보존
- Structured Source Fact 전체를 provenance token collector에 반영하여 100ms류 false-gap 방지
- Unsupported Generation Audit에서 JSON/schema metadata key 제외
- 페이지 번호가 붙은 Heading과 terse bitrate/NM interface fact classifier 보강
- 명시적 Software structural constraint가 extraction에서 누락된 경우 exact Source clause 기반 Review Candidate recovery
- Child Intent의 INDEPENDENTLY_COVERED는 해당 child와 관련된 structured observation이 있을 때만 인정
- SWE.6 Audit에 `release_gate_passed` 추가

## Contract
- Canonical Schema: `REQ-STUDIO-CANONICAL-REQ-2.0`
- Review Package Schema: `2.4`
- SWE.1/SWE.6 Mapping Contract: `2.1`
- Protected Extraction Core: `v0.46-compatible-1.1`

## 과적합 방지
V0.63 Production Logic은 특정 문서명, SRS ID, REQ ID, Paragraph, Signal/Parameter 이름을 하드코딩하지 않습니다.

이번 Generic Fix의 근거는 다음입니다.
- 두 Source에서 반복된 Parent/Fact Allocation 충돌
- 두 Source에서 반복된 Cross-domain/Provenance 문제
- Source에 이미 존재하는 Table Fact를 SWE.6가 활용하지 못하는 일반적인 구조 문제
- Explicit-ID Missing recovery는 반복 동등 declaration이라는 Source evidence 조건을 요구

## Official Release
V0.63는 Hardening Build입니다.
Official Release는 기존 Explicit-ID Gold 실제 회귀 및 추가 Gold/Silver Source 일반화 검증 후 판단합니다.
