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
            "Mirror Spock implemented reforms that weakened the Terran Empire.",
            hits,
        )

        self.assertEqual(len(coverage), 1)
        self.assertTrue(coverage[0].supported)
        self.assertIn("spock", coverage[0].matched_terms)

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

    def test_validate_generated_output_uses_kg(self):
        result = validate_generated_output(
            "Mirror Spock was a human officer of the democratic Terran Empire.",
            universe_id="terran_empire",
            retrieval_hits=[],
        )

        self.assertEqual(result["status"], "hard_contradiction")
        self.assertGreaterEqual(result["kg"]["hard_violations"], 1)


if __name__ == "__main__":
    unittest.main()
