import tempfile
import unittest
from pathlib import Path

from src.memory_store import (
    create_memory_item,
    list_memory_items,
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


if __name__ == "__main__":
    unittest.main()
