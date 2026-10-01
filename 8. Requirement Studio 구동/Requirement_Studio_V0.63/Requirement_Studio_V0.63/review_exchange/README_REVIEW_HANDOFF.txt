Requirement Studio V0.62 - Reviewer Hand-off
=============================================

Review Exchange는 같은 Run의 Source + Review Package를 유지하고,
평가 목적에 따라 03번 실제 산출물을 선택합니다.

SWE.1 Mode
----------
1) 01_SOURCE_<source>
2) 02_REQUIREMENT_STUDIO_REVIEW_PACKAGE.json
3) 03_<actual SWE.1 Word>.docx
4) 04_CHANGE_DECISION_V0.62_to_V0.62.txt
5) 05_REQUIREMENT_STUDIO_REVIEW_SUMMARY.txt

SWE.6 Mode
----------
1) 01_SOURCE_<source>
2) 02_REQUIREMENT_STUDIO_REVIEW_PACKAGE.json
3) 03_<actual SWE.6 Excel>.xlsx
4) 04_CHANGE_DECISION_V0.62_to_V0.62.txt
5) 05_REQUIREMENT_STUDIO_REVIEW_SUMMARY.txt

V0.62 SWE.6 평가에서 추가로 볼 항목
-----------------------------------
- Allocation Pending Deferred Intent / ALLOCATION_PENDING governance
- Child Intent Coverage / Deferred / Review disposition
- Cross-domain fact-level allocation
- Canonical Source fact provenance completeness
- DERIVED verification method 표시
- 4_Source_Intent_Audit Sheet

01/02/03이 동일 Run인지 반드시 확인하십시오.
04/05는 설계 의도 및 사람이 읽기 위한 보조자료입니다.

V0.62 추가 확인 항목
- Parent/Fact Allocation inheritance conflict
- Cross-domain primary verification domain / external dependency 분리
- Source Table Fact Join 및 Source Fact provenance
- Child Intent representation vs independent coverage
- SWE.6 Audit severity (blocking / release-review / advisory)
