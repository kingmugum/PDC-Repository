# Requirement Studio V0.58

V0.58은 V0.57 Cross-Document 평가에서 남은 **allocation 적용 누락, Main SWE.1 scope 오염, Semantic disposition 부재, Gap 전역 fan-out, numeric normative-strength 강화**를 일반 규칙으로 마무리한 Hardening 버전입니다.

Protected V0.46-compatible Compact Extraction Core와 핵심 정책은 유지합니다.

> 명시된 사실은 놓치지 않고, 없는 내용은 만들지 않으며, 확인할 수 없는 내용은 Gap/TBD/Dependency/Conflict/Review Needed로 남긴다.

## V0.58 핵심 변경

- High-confidence Cross-domain Allocation 실제 적용 강화
  - `MECHANICAL_CONNECTOR_REQUIREMENT`
  - `MANUFACTURING_PROCESS_REQUIREMENT`
  - `ELECTRICAL_REQUIREMENT`
  - `ENVIRONMENTAL_QUALIFICATION_REQUIREMENT`
  - `EXTERNAL_STANDARD_REFERENCE`
- `제어기`의 “제어”, `동작 전압`의 “동작”처럼 명사/복합어를 behavior로 잘못 보는 false-positive 완화
- Main SWE.1 물리 분리
  - `Eligible`만 Main SWE.1 본문에 포함
  - `Review Needed` → Allocation Review Annex
  - `Not Applicable` → Cross-domain Allocation Annex
- Semantic Source Unit Disposition Matrix
  - eligible semantic unit 전체에 disposition status/reason을 기록
  - linked / Not-SW / External Reference / Review Needed / Potential Extraction Loss 구분
- Semantic Provenance Invariant
  - no-ID SWE.1 Eligible item은 Semantic Source Unit + Source-backed Atomic Behavior 필요
  - pending/not-SW는 SW behavior를 억지 생성하지 않고 Source Fact/Verification Domain을 보존
- Gap Scope Link Filter
  - dedupe 이후 enrichment 단계에서 다시 발생하던 broad fan-out 차단
  - section gap은 deterministic anchor가 있는 Requirement만 연결
- Numeric Comparator / Normative Strength Preservation
  - `MAX 100mA`, `암전류 규제 : 0.1mA` 등을 자동으로 `<=`, `=` requirement로 강화하지 않음
  - source literal / normalized value / relation confidence를 분리
- Semantic Unit eligibility classifier 보완
  - 목차/문서 목적/단순 규격목록은 coverage denominator에서 제외
  - connector/solder/electrical/environmental 같은 terse constraint는 review object로 보존
- Local QA 명칭 정리
  - `explicit_count` → `explicit_statement_candidate_count`
  - Explicit Source ID count와 문장 강도 분류를 혼동하지 않음

## Contract

- Canonical Schema: `REQ-STUDIO-CANONICAL-REQ-1.6`
- Review Package Schema: `1.9`
- Protected Extraction Schema: `REQ-STUDIO-CANONICAL-REQ-1.1`
- Extraction Core: `v0.46-compatible-1.1`

## 과적합 방지

V0.58은 특정 시스템사양서의 SRS 번호, Paragraph 번호, Signal/Parameter명 또는 ES 규격번호를 Production Logic에 하드코딩하지 않습니다.
High-confidence cross-domain 분류는 Source evidence의 domain pattern과 software evidence를 함께 보고, 애매한 system behavior는 계속 `SYSTEM_REQUIREMENT_PENDING_SW_ALLOCATION`으로 남깁니다.

Semantic classifier의 false-positive/false-negative 비율은 사람 라벨 Gold Set 없이 숫자로 만들어내지 않습니다. V0.58은 관측 가능한 unit/disposition count만 QA 지표로 기록합니다.

## AI 평가 Hand-off

핵심 3개 파일:
1. `01_SOURCE_*`
2. `02_REQUIREMENT_STUDIO_REVIEW_PACKAGE.json`
3. `03_SWE.1 요구사항 정리_*.docx`

동반 파일:
4. `04_CHANGE_DECISION_V0.57_to_V0.58.txt`
5. `05_REQUIREMENT_STUDIO_REVIEW_SUMMARY.txt`

V0.58도 Official Release PASS를 자동 선언하지 않습니다. 기존 MLM Gold A와 Cross-Document Source를 실제 H-Chat 환경에서 다시 실행해 회귀/일반화 결과를 확인해야 합니다.
