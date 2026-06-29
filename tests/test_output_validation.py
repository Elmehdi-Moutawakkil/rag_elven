import unittest

from src.output_validation import evaluate_source_coverage, validate_generated_output
from src.retrieval_hybrid import search_corpus


class OutputValidationTests(unittest.TestCase):
    def test_evaluate_source_coverage_marks_supported_claim(self):
        hits = [
            {
                "text": "Mirror Spock implemented reforms that weakened the Terran Empire.",
                "source_path": "source.txt",
            }
        ]

        coverage = evaluate_source_coverage(
            "Mirror Spock implemented reforms that weakened the Terran Empire. [1]",
            hits,
        )

        self.assertEqual(len(coverage), 1)
        self.assertTrue(coverage[0].supported)
        self.assertIn("spock", coverage[0].matched_terms)
        self.assertEqual(coverage[0].citation_ids, [1])
        self.assertFalse(coverage[0].missing_citation)
        self.assertEqual(coverage[0].claim_type, "canon_supported")

    def test_validate_generated_output_flags_unsupported_claims(self):
        hits = search_corpus("Mirror Spock reforms", universe_id="terran_empire", k=2)
        result = validate_generated_output(
            "Mirror Spock implemented reforms that weakened the Empire. A hidden moon dragon crowned him.",
            universe_id="terran_empire",
            retrieval_hits=hits,
            check_kg=False,
        )

        self.assertEqual(result["status"], "needs_human_review")
        self.assertEqual(len(result["unsupported_claims"]), 1)
        self.assertEqual(result["claim_type_summary"]["invention_or_unsupported"], 1)
        self.assertTrue(result["human_review_required"])

    def test_validate_generated_output_requires_citations_for_supported_claims(self):
        hits = search_corpus("Mirror Spock reforms", universe_id="terran_empire", k=2)
        result = validate_generated_output(
            "Mirror Spock implemented reforms that weakened the Empire.",
            universe_id="terran_empire",
            retrieval_hits=hits,
            check_kg=False,
        )

        self.assertEqual(result["status"], "needs_citation")
        self.assertEqual(len(result["uncited_supported_claims"]), 1)

    def test_validate_generated_output_accepts_supported_cited_claim(self):
        hits = search_corpus("Mirror Spock reforms", universe_id="terran_empire", k=2)
        result = validate_generated_output(
            "Mirror Spock implemented reforms that weakened the Empire. [1]",
            universe_id="terran_empire",
            retrieval_hits=hits,
            check_kg=False,
        )

        self.assertEqual(result["status"], "validated")
        self.assertEqual(result["claim_type_summary"]["canon_supported"], 1)
        self.assertFalse(result["human_review_required"])

    def test_validate_generated_output_uses_kg(self):
        result = validate_generated_output(
            "Mirror Spock was a human officer of the democratic Terran Empire.",
            universe_id="terran_empire",
            retrieval_hits=[],
        )

        self.assertEqual(result["status"], "hard_contradiction")
        self.assertGreaterEqual(result["kg"]["hard_violations"], 1)

    def test_validate_generated_output_flags_constraint_violation(self):
        result = validate_generated_output(
            "Mirror Spock implemented reforms.",
            universe_id="terran_empire",
            retrieval_hits=[],
            constraints={"must_include": ["Terran Empire"]},
            check_kg=False,
            require_citations=False,
        )

        self.assertEqual(result["status"], "constraint_violation")
        self.assertEqual(result["failed_constraints"][0]["kind"], "must_include")

    def test_validate_generated_output_reports_style_warning_after_core_checks(self):
        result = validate_generated_output(
            "Mirror Spock implemented reforms. [1]",
            universe_id="terran_empire",
            retrieval_hits=[{"text": "Mirror Spock implemented reforms.", "source_path": "source.txt"}],
            style_rules={"required_tone": "scholarly"},
            check_kg=False,
        )

        self.assertEqual(result["status"], "style_warning")
        self.assertTrue(result["failed_style"])

    def test_validate_generated_output_reports_multimodal_sources(self):
        result = validate_generated_output(
            "A source image is available for later review.",
            universe_id="terran_empire",
            retrieval_hits=[
                {
                    "document_id": "doc_image",
                    "asset_id": "asset_123",
                    "modality": "image",
                    "source_path": "assets/frame.png",
                    "text": "",
                }
            ],
            check_kg=False,
            require_citations=False,
        )

        self.assertEqual(result["source_modalities"], {"image": 1})
        self.assertEqual(result["multimodal_sources"][0]["asset_id"], "asset_123")
        self.assertFalse(result["multimodal_sources"][0]["has_extracted_text"])
        self.assertIn("Some multimodal sources have no extracted text yet", result["warnings"])


if __name__ == "__main__":
    unittest.main()
