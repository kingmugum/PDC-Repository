from core.cross_document_semantics import _structured_source_facts, _disambiguate_shared_fragment_ownership
from core.quality_audit import _extract_fact_tokens


def test_structured_identifier_extraction_survives_korean_particles():
    fact = _structured_source_facts("SVM_Typ2의 bit 1 값과 ICMU_RealTimeMonStat를 확인한다.")[0]
    assert "SVM_Typ2" in fact["identifiers"]
    assert "ICMU_RealTimeMonStat" in fact["identifiers"]


def test_exact_fact_token_extraction_survives_korean_suffixes():
    tokens = {x.lower().replace(" ", "") for x in _extract_fact_tokens(
        "SVM_Typ2의 상태를 확인하고 피드백 5초동안 미수신이면 1회재시도한다."
    )}
    assert "svm_typ2" in tokens
    assert "5초" in tokens
    assert "1회" in tokens


def test_dominant_parent_cleanup_preserves_shared_critical_retry_fact():
    frag = {
        "source_fact_fragment_id": "F-RETRY",
        "source_excerpt": "캡처에 실패한 경우 1회 재시도한다.",
    }
    outdoor = {
        "srs_id": "SRS_OUTDOOR",
        "requirement": "실외 이미지 캡처에 실패한 경우 1회 재시도하고 실패하면 종료한다.",
        "source_fact_fragments": [dict(frag)],
        "source_backed_atomic_behaviors": [{"source_fact_fragment_id": "F-RETRY", "behavior_text": frag["source_excerpt"]}],
        "fact_level_allocations": [{"source_fact_fragment_id": "F-RETRY"}],
    }
    indoor = {
        "srs_id": "SRS_INDOOR",
        "requirement": "실내 이미지 캡처 실패 시 1회 재시도한다.",
        "source_fact_fragments": [dict(frag)],
        "source_backed_atomic_behaviors": [{"source_fact_fragment_id": "F-RETRY", "behavior_text": frag["source_excerpt"]}],
        "fact_level_allocations": [{"source_fact_fragment_id": "F-RETRY"}],
    }
    records = _disambiguate_shared_fragment_ownership([outdoor, indoor])
    assert outdoor["source_fact_fragments"]
    assert indoor["source_fact_fragments"]
    assert records
    assert records[0]["resolution"] in {"SHARED_CRITICAL_FACT_PRESERVED", "SHARED_REVIEW_REQUIRED"}
