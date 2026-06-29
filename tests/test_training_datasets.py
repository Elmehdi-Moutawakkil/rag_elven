import json
import tempfile
import unittest
from pathlib import Path

from src.memory_store import create_memory_item, transition_memory_item
from src.training_datasets import build_training_dataset, training_strategy, write_training_dataset


class TrainingDatasetTests(unittest.TestCase):
    def test_strategy_defers_training_until_validated_data_exists(self):
        strategy = training_strategy()

        self.assertEqual(strategy["status"], "deferred_until_validated_data")
        self.assertTrue(strategy["minimum_before_training"]["baseline_required"])
        self.assertIn("lore_generation_style", {item["task"] for item in strategy["trainable_tasks"]})

    def test_empty_dataset_is_blocked_without_validated_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = build_training_dataset(universe_id="terran_empire", root=Path(tmp))

        self.assertEqual(dataset["status"], "blocked_no_validated_examples")
        self.assertEqual(dataset["example_count"], 0)
        self.assertEqual(dataset["examples"], [])

    def test_dataset_uses_only_reusable_validated_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = create_memory_item(
                universe_id="terran_empire",
                content="Draft unsupported style sample.",
                summary="Draft",
                sources=["source#1"],
                root=root,
            )
            validated = create_memory_item(
                universe_id="terran_empire",
                content="Mirror Spock's validated reforms weakened the Empire.",
                summary="Validated Spock reforms",
                sources=["history_and_origins.txt#chunk"],
                kg_validation={"status": "validated"},
                actor="author",
                root=root,
            )
            transition_memory_item(validated["memory_id"], universe_id="terran_empire", new_status="pending", actor="reviewer", root=root)
            transition_memory_item(validated["memory_id"], universe_id="terran_empire", new_status="validated", actor="reviewer", root=root)

            dataset = build_training_dataset(universe_id="terran_empire", root=root)

        self.assertEqual(draft["status"], "draft")
        self.assertEqual(dataset["status"], "ready_for_baseline")
        self.assertEqual(dataset["example_count"], 1)
        self.assertEqual(dataset["examples"][0]["output"]["content"], "Mirror Spock's validated reforms weakened the Empire.")
        self.assertEqual(dataset["examples"][0]["validation"]["memory_status"], "validated")

    def test_write_training_dataset_outputs_jsonl_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = create_memory_item(
                universe_id="terran_empire",
                content="Validated note for later baseline comparison.",
                summary="Validated note",
                sources=["source#1"],
                kg_validation={"status": "validated"},
                root=root,
            )
            transition_memory_item(item["memory_id"], universe_id="terran_empire", new_status="pending", actor="reviewer", root=root)
            transition_memory_item(item["memory_id"], universe_id="terran_empire", new_status="validated", actor="reviewer", root=root)

            manifest = write_training_dataset(universe_id="terran_empire", root=root)
            examples_path = root / manifest["examples_path"]
            rows = [json.loads(line) for line in examples_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(manifest["example_count"], 1)
        self.assertEqual(manifest["status"], "ready_for_baseline")
        self.assertEqual(rows[0]["task"], "lore_generation_style")


if __name__ == "__main__":
    unittest.main()
