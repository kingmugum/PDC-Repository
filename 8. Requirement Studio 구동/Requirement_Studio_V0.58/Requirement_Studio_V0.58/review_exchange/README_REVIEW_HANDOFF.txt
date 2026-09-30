Requirement Studio V0.58 - Reviewer Hand-off
============================================

평가 AI/사람 Reviewer의 핵심 비교 대상은 다음 3개입니다.
1) 01_SOURCE_<source>.<ext>
2) 02_REQUIREMENT_STUDIO_REVIEW_PACKAGE.json
3) 03_<actual SWE.1 Word>.docx

동반 판단 자료:
4) 04_CHANGE_DECISION_V0.57_to_V0.58.txt
5) 05_REQUIREMENT_STUDIO_REVIEW_SUMMARY.txt

V0.58 추가 확인:
- Main SWE.1 본문에는 Eligible만 존재하고 Review Needed/Not-SW는 Annex로 분리되는지
- Semantic eligible unit 전체에 disposition record가 있는지
- section Gap이 최종 단계에서 전 SRS로 fan-out되지 않는지
- MAX/규제값의 comparator가 Source보다 강화되지 않는지
- Explicit Requirement ID가 없으면 Explicit-ID Coverage가 N/A인지
- Paragraph/Table Row 기반 Semantic Source Unit이 JSON과 Word에서 같은 provenance를 사용하는지
- requirement_level / allocation_status / SWE.1·SWE.6 eligibility / verification_domain이 보존되는지
- Not-SW Source fact가 삭제되지 않고 Allocation Annex/Review JSON에 남는지
- Document-level Gap이 모든 SRS로 fan-out되지 않는지

Gold Regression은 Source SHA가 등록된 경우에만 수행합니다.
새 Cross-Document Source는 사람 검토·승인 전 자동 Gold 등록하지 않습니다.
