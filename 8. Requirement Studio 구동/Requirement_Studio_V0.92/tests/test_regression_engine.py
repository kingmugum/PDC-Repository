import unittest

from core.regression_engine import build_regression_report


def baseline(reqs, *, provider="GPT", model="model-a"):
    return {
        "run": {
            "requirement_studio_version": "v0.46",
            "source_sha256": "same-source",
            "provider": provider,
            "provider_id": provider.lower(),
            "model": model,
        },
        "canonical_requirement": {"requirements": reqs},
    }


def req(cid, srs, sid, loc, text):
    return {
        "candidate_id": cid,
        "srs_id": srs,
        "requirement": text,
        "source_evidence": [{"document": "x.docx", "location": loc, "text": f"[{sid}] {text}"}],
    }


def occ(oid, sid, loc, status, srs=None, cid=None):
    return {
        "occurrence_id": oid,
        "occurrence_type": "declaration",
        "source_req_id": sid,
        "source_location": loc,
        "source_excerpt": f"[{sid}] behavior",
        "coverage_status": status,
        "linked_srs_ids": [srs] if srs else [],
        "linked_candidate_ids": [cid] if cid else [],
        "linked_gap_issue_ids": [],
        "disposition_reason": "covered" if status == "Covered" else "",
    }


class RegressionReliabilityTests(unittest.TestCase):
    def current_run(self, model="model-a"):
        return {
            "requirement_studio_version": "v0.51",
            "source_sha256": "same-source",
            "provider": "GPT",
            "provider_id": "gpt",
            "model": model,
            "extraction_core_profile": "v0.46-compatible-1.1",
        }

    def test_baseline_behavior_absent_fails(self):
        prev = baseline([req("REQ-CAND-001", "SRS_001", "REQ02_18", "Paragraph 143", "Not-P timing")])
        cur = {
            "requirements": [],
            "source_coverage": {"source_requirement_occurrences": [occ("SRC-OCC-1", "REQ02_18", "Paragraph 143", "Missing")]},
        }
        report = build_regression_report(cur, prev, "baseline.json", current_run=self.current_run())
        self.assertEqual(report["regression_gate"]["status"], "FAIL")
        self.assertTrue(any(x.get("classification") == "Baseline behavior absent" for x in report["findings"]))

    def test_behavior_exists_but_occurrence_link_missing_requires_review(self):
        prev = baseline([req("REQ-CAND-001", "SRS_001", "REQ03_16", "Paragraph 188", "Drive mode output")])
        cur_req = req("REQ-CAND-021", "SRS_021", "REQ03_16", "Paragraph 188", "Drive mode output")
        cur = {"requirements": [cur_req], "source_coverage": {"source_requirement_occurrences": []}}
        report = build_regression_report(cur, prev, "baseline.json", current_run=self.current_run())
        self.assertEqual(report["regression_gate"]["status"], "HUMAN_REVIEW_NEEDED")
        self.assertTrue(any(x.get("classification") == "Traceability linkage regression" for x in report["findings"]))

    def test_grouped_requirement_with_links_can_pass(self):
        prev = baseline([
            req("REQ-CAND-001", "SRS_001", "REQ02_11", "Paragraph 125", "Foot lamp step A"),
            req("REQ-CAND-002", "SRS_002", "REQ02_12", "Paragraph 127", "Foot lamp step B"),
        ])
        grouped = {
            "candidate_id": "REQ-CAND-010", "srs_id": "SRS_010", "requirement": "Grouped foot lamp behavior",
            "source_requirement_ids": ["REQ02_11", "REQ02_12"],
            "source_requirement_occurrence_ids": ["SRC-OCC-1", "SRC-OCC-2"],
            "source_evidence": [{"document": "x.docx", "location": "Paragraph 125-127", "text": "REQ02_11 REQ02_12 grouped behavior"}],
        }
        cur = {
            "requirements": [grouped],
            "source_coverage": {"source_requirement_occurrences": [
                occ("SRC-OCC-1", "REQ02_11", "Paragraph 125", "Covered", "SRS_010", "REQ-CAND-010"),
                occ("SRC-OCC-2", "REQ02_12", "Paragraph 127", "Covered", "SRS_010", "REQ-CAND-010"),
            ]},
        }
        report = build_regression_report(cur, prev, "baseline.json", current_run=self.current_run())
        self.assertEqual(report["regression_gate"]["status"], "PASS")

    def test_cross_model_cannot_silently_pass(self):
        prev = baseline([req("REQ-CAND-001", "SRS_001", "REQ01_01", "Paragraph 10", "Behavior")], model="model-old")
        cur_req = req("REQ-CAND-001", "SRS_001", "REQ01_01", "Paragraph 10", "Behavior")
        cur = {"requirements": [cur_req], "source_coverage": {"source_requirement_occurrences": [occ("SRC-OCC-1", "REQ01_01", "Paragraph 10", "Covered", "SRS_001", "REQ-CAND-001")]}}
        report = build_regression_report(cur, prev, "baseline.json", current_run=self.current_run(model="model-new"))
        self.assertEqual(report["regression_gate"]["status"], "HUMAN_REVIEW_NEEDED")
        self.assertEqual(report["run_compatibility"]["comparison_mode"], "cross_model")


if __name__ == "__main__":
    unittest.main()
