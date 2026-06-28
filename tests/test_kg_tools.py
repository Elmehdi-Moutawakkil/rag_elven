import unittest

from src.kg_tools import (
    export_knowledge_graph,
    find_entity,
    list_entities,
    list_relations,
    source_evidence_for_entity,
    validate_assertion,
)


class KGToolsTests(unittest.TestCase):
    def test_list_and_find_entity(self):
        entities = list_entities("terran_empire", entity_type="character")
        names = {entity["name"] for entity in entities}

        self.assertIn("Mirror Spock", names)
        entity = find_entity("Emperor Spock", "terran_empire")
        self.assertIsNotNone(entity)
        self.assertEqual(entity["name"], "Mirror Spock")
        self.assertIsInstance(entity["aliases"], list)

    def test_list_relations_for_entity(self):
        relations = list_relations("Mirror Spock", universe_id="terran_empire")
        relation_types = {relation["relation_type"] for relation in relations}

        self.assertIn("initiated", relation_types)

    def test_source_evidence_for_entity_uses_chunks(self):
        evidence = source_evidence_for_entity("Mirror Spock", universe_id="terran_empire", k=2)

        self.assertTrue(evidence)
        self.assertIn("source_path", evidence[0])
        self.assertIn("citation", evidence[0])

    def test_validate_assertion_reports_hard_contradiction(self):
        result = validate_assertion(
            "Mirror Spock was a human officer of the democratic Terran Empire.",
            universe_id="terran_empire",
        )

        self.assertEqual(result["status"], "hard_contradiction")
        self.assertGreaterEqual(result["hard_violations"], 1)
        self.assertIn("Mirror Spock", result["source_evidence"])

    def test_validate_assertion_allows_supported_statement(self):
        result = validate_assertion(
            "Mirror Spock initiated reforms that weakened the Terran Empire.",
            universe_id="terran_empire",
        )

        self.assertEqual(result["status"], "validated")
        self.assertEqual(result["hard_violations"], 0)

    def test_kg_export_contains_counts_and_provenance_limits(self):
        export = export_knowledge_graph("terran_empire")

        self.assertEqual(export["universe_id"], "terran_empire")
        self.assertEqual(export["stats"]["entities"], 42)
        self.assertEqual(export["stats"]["relations"], 33)
        self.assertEqual(export["stats"]["canon_facts"], 12)
        self.assertEqual(export["provenance"]["entity_source_file"], "available")
        self.assertEqual(export["provenance"]["canon_fact_source_file"], "not structured yet")
        self.assertTrue(any(entity["name"] == "Mirror Spock" for entity in export["entities"]))
        self.assertTrue(any(relation["relation_type"] == "initiated" for relation in export["relations"]))


if __name__ == "__main__":
    unittest.main()
