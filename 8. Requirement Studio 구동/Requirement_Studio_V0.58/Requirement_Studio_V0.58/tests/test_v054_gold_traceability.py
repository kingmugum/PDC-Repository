import json
import tempfile
import unittest
from pathlib import Path

from core.gold_source_registry import GoldSourceRegistry
from core.quality_audit import apply_quality_audits
from providers.config_store import ProviderConfigStore
from core.review_exchange import ReviewExchangeBuilder


class V054GoldAndTraceabilityTests(unittest.TestCase):
    def test_bundled_mlm_gold_source_is_registered(self):
        root = Path(__file__).resolve().parents[1]
        registry = GoldSourceRegistry(root)
        status = registry.status()
        self.assertGreaterEqual(status["count"], 1)
        contract, path = registry.find_contract("b9d58a87cc72b66919c6af7220b215b9e66e06ab426eae20e04a8642dbffb15c")
        self.assertIsNotNone(contract)
        self.assertTrue(path)
        self.assertEqual(contract["reference_version"], "v0.46")
        self.assertEqual(len(contract["behaviors"]), 24)


    def test_review_exchange_auto_selects_bundled_gold_source(self):
        root = Path(__file__).resolve().parents[1]
        builder = ReviewExchangeBuilder(root, app_version="v0.55")
        payload, path = builder._load_previous_review_package(
            "b9d58a87cc72b66919c6af7220b215b9e66e06ab426eae20e04a8642dbffb15c",
            root / "review_exchange" / "not_a_real_run",
        )
        self.assertIsNotNone(payload)
        self.assertIn("Gold Source Contract:", path)
        self.assertEqual(payload["run"]["requirement_studio_version"], "v0.46")
        self.assertGreaterEqual(len(payload["canonical_requirement"]["requirements"]), 24)

    def test_multiple_gold_sources_can_be_added_and_selected_by_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = parent / "Requirement_Studio_V0.55"
            root.mkdir()
            registry = GoldSourceRegistry(root)
            for idx, sha in enumerate(("a" * 64, "b" * 64), start=1):
                pkg = parent / f"pkg{idx}.json"
                pkg.write_text(json.dumps({
                    "run": {
                        "requirement_studio_version": "v0.46",
                        "source_sha256": sha,
                        "source_original_name": f"Gold{idx}.docx",
                        "provider": "H-Chat / GPT",
                        "provider_id": "hchat_gpt",
                        "model": "gpt-5.6-terra",
                    },
                    "canonical_requirement": {"requirements": [{
                        "candidate_id": "REQ-CAND-001",
                        "srs_id": "SRS_001",
                        "requirement": f"Behavior {idx}",
                        "source_requirement_ids": [f"REQ0{idx}_01"],
                        "source_evidence": [{"location": f"Paragraph {idx}", "text": f"[REQ0{idx}_01] behavior"}],
                    }]},
                }), encoding="utf-8")
                registry.install_review_package(pkg)
            self.assertEqual(registry.status()["count"], 2)
            contract, _ = registry.find_contract("b" * 64)
            self.assertEqual(contract["source_original_name"], "Gold2.docx")
            payload = registry.contract_to_review_payload(contract)
            self.assertEqual(payload["run"]["source_sha256"], "b" * 64)

    def test_source_evidence_location_repairs_occurrence_binding(self):
        data = {
            "requirements": [{
                "candidate_id": "REQ-CAND-001",
                "srs_id": "SRS_001",
                "requirement": "The controller shall perform the stated behavior.",
                "derivation_type": "explicit",
                "source_evidence": [{"document": "A.docx", "location": "Paragraph 10", "text": "controller behavior"}],
                "confidence": 0.95,
                "applicability": {},
                "clarification_needed": "",
            }],
            "gaps": [],
        }
        compact = "[DOCUMENT] A.docx\n[SRC DOC-C0001 | Paragraph 10 | text]\n[REQ01_01] controller behavior"
        out = apply_quality_audits(data, compact)
        req = out["requirements"][0]
        self.assertIn("REQ01_01", req["source_requirement_ids"])
        self.assertIn("SRC-OCC-0001", req["source_requirement_occurrence_ids"])
        self.assertIn("DOC-C0001", req["source_chunk_ids"])
        self.assertEqual(out["source_coverage"]["coverage_validity"], "VALID")
        self.assertEqual(out["source_coverage"]["covered"], ["SRC-OCC-0001"])

    def test_empty_global_binding_is_invalid_and_does_not_flood_missing_findings(self):
        data = {
            "requirements": [{
                "candidate_id": "REQ-CAND-001",
                "srs_id": "SRS_001",
                "requirement": "Unrelated current behavior.",
                "derivation_type": "explicit",
                "source_evidence": [{"document": "A.docx", "location": "Paragraph 999", "text": "unrelated evidence"}],
                "confidence": 0.95,
                "applicability": {},
                "clarification_needed": "",
            }],
            "gaps": [],
        }
        compact = "[DOCUMENT] A.docx\n[SRC DOC-C0001 | Paragraph 10 | text]\n[REQ01_01] controller behavior"
        out = apply_quality_audits(data, compact)
        self.assertEqual(out["source_coverage"]["coverage_validity"], "INVALID")
        findings = out.get("review_findings") or []
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["finding_id"], "RF-TRACEABILITY-BINDING-EMPTY")
        self.assertTrue(findings[0]["source_fact_confirmed"])
        self.assertFalse(findings[0]["canonical_link_confirmed"])

    def test_old_hchat_model_catalog_is_migrated_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config" / "provider_config.json").write_text(json.dumps({
                "hchat": {
                    "gpt_model": "gpt-5.2",
                    "gpt_model_options": ["gpt-5.2", "gpt-5.4"],
                    "gemini_model": "Gemini 2.5 Pro",
                    "gemini_model_options": ["Gemini 2.5 Pro"],
                    "claude_model": "Claude 3.5 Sonnet",
                    "claude_model_options": ["Claude 3.5 Sonnet"],
                }
            }), encoding="utf-8")
            cfg = ProviderConfigStore(root).load()["hchat"]
            self.assertEqual(cfg["gpt_model_options"], ["gpt-5.6-terra"])
            self.assertEqual(cfg["gemini_model_options"], ["gemini-3.7-flash"])
            self.assertEqual(cfg["claude_model_options"], ["claude-sonnet-5"])


if __name__ == "__main__":
    unittest.main()
