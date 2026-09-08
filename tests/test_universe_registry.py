import unittest

from src.universe_registry import (
    SELECTION_REQUIRED,
    UNIVERSE_REQUIRED,
    UNIVERSE_UNKNOWN,
    get_universe_registry,
    resolve_universe,
)


class UniverseRegistryTests(unittest.TestCase):
    def test_registry_reads_the_two_declared_manifests(self):
        registry = get_universe_registry()

        self.assertEqual(registry.ids(), ("terran_empire", "tolkien"))
        self.assertTrue(registry.require("terran_empire").text_chunks_path)
        self.assertTrue(registry.require("tolkien").semantic_index_path)

    def test_missing_unknown_and_traversal_universes_are_not_defaulted(self):
        self.assertEqual(resolve_universe(None).status, UNIVERSE_REQUIRED)
        self.assertEqual(resolve_universe("   ").status, UNIVERSE_REQUIRED)
        self.assertEqual(resolve_universe("missing").status, UNIVERSE_UNKNOWN)
        self.assertEqual(resolve_universe("../tolkien").status, UNIVERSE_UNKNOWN)

    def test_auto_needs_one_certain_candidate(self):
        self.assertEqual(resolve_universe("Auto", query="Who is Mirror Spock?").universe_id, "terran_empire")
        self.assertEqual(resolve_universe("Auto", query="Tell me about history").status, SELECTION_REQUIRED)
        self.assertEqual(
            resolve_universe("Auto", query="Compare Spock and Galadriel").status,
            SELECTION_REQUIRED,
        )

    def test_explicit_selection_precedes_detection(self):
        resolution = resolve_universe("tolkien", query="Who is Mirror Spock?")

        self.assertTrue(resolution.ok)
        self.assertEqual(resolution.universe_id, "tolkien")


if __name__ == "__main__":
    unittest.main()
