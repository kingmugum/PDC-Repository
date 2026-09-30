import unittest

from core.quality_audit import apply_quality_audits


class QualitySidecarV051Tests(unittest.TestCase):
    def test_grouped_range_links_all_declarations_and_chunks(self):
        compact = """[SRC DOC-C1 | Paragraph 125 | text]\n[REQ02_11] A\n[SRC DOC-C2 | Paragraph 127 | text]\n[REQ02_12] B\n[SRC DOC-C3 | Paragraph 129 | text]\n[REQ02_13] C\n[SRC DOC-C4 | Paragraph 131 | text]\n[REQ02_14] D\n"""
        data = {"requirements": [{
            "candidate_id": "REQ-CAND-013", "srs_id": "SRS_013", "requirement": "Grouped behavior",
            "source_requirement_ids": ["REQ02_11", "REQ02_14"],
            "source_evidence": [{"location": "Paragraph 125-131", "text": "REQ02_11~REQ02_14 grouped behavior"}],
            "related_artifacts": [], "preconditions": [], "exception_conditions": [], "clarification_needed": "", "derivation_type": "explicit",
        }], "gaps": []}
        apply_quality_audits(data, compact)
        req = data["requirements"][0]
        self.assertEqual(set(req["source_requirement_ids"]), {"REQ02_11", "REQ02_12", "REQ02_13", "REQ02_14"})
        self.assertEqual(len(req["source_requirement_occurrence_ids"]), 4)
        self.assertEqual(set(req["source_chunk_ids"]), {"DOC-C1", "DOC-C2", "DOC-C3", "DOC-C4"})
        self.assertTrue(all(x["coverage_status"] == "Covered" for x in data["source_coverage"]["source_requirement_occurrences"] if x["occurrence_type"] == "declaration"))

    def test_conflict_complete_requires_direct_pair(self):
        compact = """[SRC DOC-C1 | Paragraph 188 | text]\n[REQ03_16] Input_MoodLpDrivemodeNvalue On(0x1)\n[SRC DOC-C2 | Table 5 / Row 29 | table]\nInput_MoodLpDrivemodeNvalue 0x1=Off 0x2=On\n"""
        data = {"requirements": [{
            "candidate_id": "REQ-CAND-021", "srs_id": "SRS_021", "requirement": "Drive mode",
            "source_requirement_ids": ["REQ03_16"],
            "source_evidence": [{"location": "Paragraph 188", "text": "[REQ03_16] Input_MoodLpDrivemodeNvalue On(0x1)"}],
            "related_artifacts": [], "preconditions": [], "exception_conditions": [], "clarification_needed": "", "derivation_type": "explicit",
        }], "gaps": [{
            "gap_id": "GAP_003", "description": "Input_MoodLpDrivemodeNvalue On 값 상충 0x1 / 0x2",
            "related_candidate_ids": ["REQ-CAND-021"], "related_srs_ids": ["SRS_021"], "related_source_requirement_ids": ["REQ03_16"],
        }]}
        apply_quality_audits(data, compact)
        conflicts = [x for x in data["conflict_register"] if x.get("evidence_status") == "Complete"]
        self.assertTrue(conflicts)
        c = conflicts[0]
        self.assertIn("Input_MoodLpDrivemodeNvalue", c["source_a"]["text"])
        self.assertIn("Input_MoodLpDrivemodeNvalue", c["source_b"]["text"])
        self.assertNotEqual(c["source_a"]["location"], c["source_b"]["location"])

    def test_external_dependency_only_when_source_mentions_it(self):
        compact = """[SRC DOC-C1 | Paragraph 309 | text]\n[REQ03_07] CAN DB에 주기 정의\n"""
        data = {"requirements": [{
            "candidate_id": "REQ-CAND-024", "srs_id": "SRS_024", "requirement": "Periodic output",
            "source_requirement_ids": ["REQ03_07"],
            "source_evidence": [{"location": "Paragraph 309", "text": "[REQ03_07] CAN DB에 주기 정의"}],
            "related_artifacts": [], "preconditions": [], "exception_conditions": [], "clarification_needed": "", "derivation_type": "explicit",
        }], "gaps": []}
        apply_quality_audits(data, compact)
        deps = data["requirements"][0]["external_dependencies"]
        self.assertTrue(any(x.get("name") == "CAN DB" and x.get("knowledge_state") == "KNOWN" for x in deps))


if __name__ == "__main__":
    unittest.main()
