import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inspector.run_tests import _distribute_test_counts
from inspector.reporter import build_daily_report
from src.database import search_translation
from src.ir import Argument, PredicateIR, SemanticIR
from src.knowledge_graph import KnowledgeGraph
from src.morphology import ConfidenceLevel, MorphResult
from src.pipeline_executor import format_final_output


class RegressionTests(unittest.TestCase):
    def test_pipeline_formatter_uses_existing_semantic_ir_fields(self):
        ir = SemanticIR(
            predicate=PredicateIR("walk", "present", "declarative", "singular"),
            arguments=[Argument("agent", "warrior", "singular", "nominative")],
            raw_sentence="The warrior walks",
        )

        self.assertIn("warrior", format_final_output({
            "final_output": ir,
            "final_type": "semantic_ir",
            "error": None,
        }))

    def test_pipeline_formatter_uses_morph_feature_field(self):
        forms = [
            MorphResult(
                english_lemma="warrior",
                quenya_lemma="ohtar",
                quenya_form="ohtar",
                feature="nominative singular",
                confidence_level=ConfidenceLevel.HIGH,
                source_note="test",
            )
        ]

        self.assertIn("nominative singular", format_final_output({
            "final_output": forms,
            "final_type": "morph_forms",
            "error": None,
        }))

    def test_search_translation_escapes_regex_input(self):
        with tempfile.NamedTemporaryFile(suffix=".sqlite") as tmp:
            with sqlite3.connect(tmp.name) as conn:
                conn.execute(
                    """CREATE TABLE dictionary_entries (
                        word TEXT,
                        language TEXT,
                        direction TEXT,
                        translation TEXT,
                        part_of_speech TEXT,
                        plural_form TEXT,
                        source TEXT,
                        notes TEXT
                    )"""
                )
                conn.execute(
                    """INSERT INTO dictionary_entries
                       (word, language, direction, translation, part_of_speech, plural_form, source, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    ("elen", "Quenya", "quenya->english", "star", "noun", "", "test", ""),
                )

            self.assertEqual(search_translation("[", tmp.name), [])
            self.assertEqual(search_translation(".*", tmp.name), [])

    def test_inspector_distribution_matches_requested_total(self):
        self.assertEqual(_distribute_test_counts(["a", "b", "c", "d", "e"], 24), {
            "a": 5,
            "b": 5,
            "c": 5,
            "d": 5,
            "e": 4,
        })

    def test_daily_report_can_filter_to_one_run_id(self):
        rows = [
            {
                "run_id": "new",
                "feature_id": "qa",
                "universe": "U",
                "feature": "F",
                "question": "Q1",
                "verdict": "CORRECT",
                "score": 1.0,
                "judge_notes": "",
            },
            {
                "run_id": "old",
                "feature_id": "qa",
                "universe": "U",
                "feature": "F",
                "question": "Q2",
                "verdict": "ERROR",
                "score": 0.0,
                "judge_notes": "boom",
            },
        ]
        with patch("inspector.reporter.get_runs_by_run_id", return_value=[rows[0]]):
            report = build_daily_report(run_id="new")

        self.assertIn("Tests exécutés | 1", report)
        self.assertIn("Q1", report)
        self.assertNotIn("Q2", report)

    def test_knowledge_graph_canon_fact_patterns_are_enforced(self):
        with tempfile.NamedTemporaryFile(suffix=".sqlite") as tmp:
            with KnowledgeGraph(Path(tmp.name)) as kg:
                kg.add_canon_fact(
                    "The Terran Empire is not a democracy.",
                    r"(?i)\bterran empire\b.{0,80}\bdemocracy\b",
                    "HARD",
                )
                result = kg.validate_story("The Terran Empire was a peaceful democracy.")

        self.assertFalse(result["is_valid"])
        self.assertEqual(len(result["violations"]), 1)


if __name__ == "__main__":
    unittest.main()
