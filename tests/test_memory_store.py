import tempfile
import unittest
from pathlib import Path

from src.memory_store import (
    create_memory_candidate_from_validation,
    create_memory_item,
    edit_memory_item,
    list_memory_items,
    memory_history,
    rollback_memory_item,
    transition_memory_item,
)


class MemoryStoreTests(unittest.TestCase):
    def test_memory_item_requires_validation_before_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = create_memory_item(
                universe_id="terran_empire",
                content="A draft rebel cell note.",
                summary="Draft note",
                sources=["source#chunk"],
                actor="test",
                root=root,
            )

            reusable = list_memory_items(universe_id="terran_empire", reusable_only=True, root=root)
            self.assertEqual(reusable, [])

            transition_memory_item(
                item["memory_id"],
                universe_id="terran_empire",
                new_status="pending",
                actor="reviewer",
                root=root,
            )
            validated = transition_memory_item(
                item["memory_id"],
                universe_id="terran_empire",
                new_status="validated",
                actor="reviewer",
                note="sources checked",
                root=root,
            )
            reusable = list_memory_items(universe_id="terran_empire", reusable_only=True, root=root)

        self.assertEqual(validated["status"], "validated")
        self.assertEqual(validated["reviewer"], "reviewer")
        self.assertIsNotNone(validated["validated_at"])
        self.assertEqual(len(reusable), 1)
        self.assertEqual(reusable[0]["memory_id"], item["memory_id"])
        self.assertEqual(len(reusable[0]["events"]), 3)

    def test_invalid_transition_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = create_memory_item(
                universe_id="terran_empire",
                content="A draft rebel cell note.",
                summary="Draft note",
                sources=[],
                actor="test",
                root=root,
            )

            with self.assertRaises(ValueError):
                transition_memory_item(
                    item["memory_id"],
                    universe_id="terran_empire",
                    new_status="validated",
                    actor="reviewer",
                    root=root,
                )

    def test_pending_and_validated_require_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = create_memory_item(
                universe_id="terran_empire",
                content="Unsupported draft note.",
                summary="Draft note",
                sources=[],
                actor="test",
                root=root,
            )

            with self.assertRaisesRegex(ValueError, "requires at least one source"):
                transition_memory_item(
                    item["memory_id"],
                    universe_id="terran_empire",
                    new_status="pending",
                    actor="reviewer",
                    root=root,
                )

    def test_hard_contradiction_cannot_be_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = create_memory_item(
                universe_id="terran_empire",
                content="Contradicted note.",
                summary="Draft note",
                sources=["source#chunk"],
                kg_validation={"status": "hard_contradiction"},
                actor="test",
                root=root,
            )
            transition_memory_item(
                item["memory_id"],
                universe_id="terran_empire",
                new_status="pending",
                actor="reviewer",
                root=root,
            )

            with self.assertRaisesRegex(ValueError, "hard contradiction"):
                transition_memory_item(
                    item["memory_id"],
                    universe_id="terran_empire",
                    new_status="validated",
                    actor="reviewer",
                    root=root,
                )

            reusable = list_memory_items(universe_id="terran_empire", reusable_only=True, root=root)
            self.assertEqual(reusable, [])

    def test_edit_resets_validated_memory_to_draft_and_keeps_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = create_memory_item(
                universe_id="terran_empire",
                content="Original supported note.",
                summary="Original",
                sources=["source#chunk"],
                actor="test",
                root=root,
            )
            transition_memory_item(item["memory_id"], universe_id="terran_empire", new_status="pending", actor="reviewer", root=root)
            transition_memory_item(item["memory_id"], universe_id="terran_empire", new_status="validated", actor="reviewer", root=root)

            edited = edit_memory_item(
                item["memory_id"],
                universe_id="terran_empire",
                content="Edited supported note.",
                summary="Edited",
                actor="editor",
                note="fix wording",
                root=root,
            )
            reusable = list_memory_items(universe_id="terran_empire", reusable_only=True, root=root)

        self.assertEqual(edited["status"], "draft")
        self.assertEqual(edited["version"], 2)
        self.assertIsNone(edited["validated_at"])
        self.assertEqual(reusable, [])
        self.assertEqual(edited["events"][-1]["event_type"], "edited")
        self.assertEqual(edited["events"][-1]["payload"]["previous_item"]["content"], "Original supported note.")

    def test_rollback_restores_previous_content_as_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = create_memory_item(
                universe_id="terran_empire",
                content="Original supported note.",
                summary="Original",
                sources=["source#chunk"],
                actor="test",
                root=root,
            )
            edited = edit_memory_item(
                item["memory_id"],
                universe_id="terran_empire",
                content="Bad edit.",
                summary="Bad",
                actor="editor",
                root=root,
            )
            rolled_back = rollback_memory_item(
                edited["memory_id"],
                universe_id="terran_empire",
                actor="reviewer",
                root=root,
            )
            history = memory_history(item["memory_id"], universe_id="terran_empire", root=root)

        self.assertEqual(rolled_back["status"], "draft")
        self.assertEqual(rolled_back["content"], "Original supported note.")
        self.assertEqual(rolled_back["summary"], "Original")
        self.assertEqual(rolled_back["version"], 3)
        self.assertEqual(history[-1]["event_type"], "rolled_back")

    def test_validation_can_create_pending_candidate_but_not_auto_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = create_memory_candidate_from_validation(
                universe_id="terran_empire",
                content="Mirror Spock's reforms weakened the Terran Empire.",
                summary="Spock reforms note",
                sources=["history_and_origins.txt#chunk"],
                validation={"status": "validated", "kg": {"status": "validated"}, "source_count": 1},
                actor="validator",
                root=root,
            )
            reusable = list_memory_items(universe_id="terran_empire", reusable_only=True, root=root)

        self.assertEqual(candidate["status"], "pending")
        self.assertEqual(reusable, [])

    def test_hard_contradiction_cannot_create_memory_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "hard contradiction"):
                create_memory_candidate_from_validation(
                    universe_id="terran_empire",
                    content="Mirror Spock was human.",
                    summary="Bad note",
                    sources=["source#chunk"],
                    validation={"status": "hard_contradiction", "kg": {"status": "hard_contradiction"}},
                    root=Path(tmp),
                )


if __name__ == "__main__":
    unittest.main()
