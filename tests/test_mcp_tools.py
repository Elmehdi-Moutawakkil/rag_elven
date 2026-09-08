import unittest

from src.mcp_tools import call_tool


class MCPToolsTests(unittest.TestCase):
    def test_list_tools_exposes_read_only_contracts(self):
        result = call_tool("list_tools")

        self.assertEqual(result["status"], "ok")
        names = {tool["name"] for tool in result["data"]}
        self.assertIn("search_corpus", names)
        self.assertIn("read_document", names)
        self.assertIn("validate_assertion", names)
        self.assertIn("validate_generated_output", names)
        self.assertTrue(all(tool["read_only"] for tool in result["data"]))
        self.assertFalse(any(tool["side_effects"] for tool in result["data"]))

    def test_list_universes_tool(self):
        result = call_tool("list_universes")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"][0]["universe_id"], "terran_empire")

    def test_search_corpus_tool(self):
        result = call_tool("search_corpus", {"query": "Mirror Spock reforms", "universe_id": "terran_empire", "k": 2})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["status"], "SUCCESS")
        self.assertTrue(result["data"]["hits"])
        self.assertIn("citation", result["data"]["hits"][0])

    def test_read_document_tool(self):
        search = call_tool("search_corpus", {"query": "Mirror Spock reforms", "universe_id": "terran_empire", "k": 1})
        source_path = search["data"]["hits"][0]["source_path"]

        result = call_tool("read_document", {"universe_id": "terran_empire", "source_path": source_path})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["source_path"], source_path)
        self.assertIn("clean_content", result["data"])

    def test_read_document_missing_universe_is_clean_not_found(self):
        result = call_tool("read_document", {"universe_id": "missing", "source_path": "missing.md"})

        self.assertEqual(result["status"], "error")
        self.assertTrue(result["warnings"])

    def test_get_entity_tool(self):
        result = call_tool("get_entity", {"name": "Mirror Spock", "universe_id": "terran_empire"})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["name"], "Mirror Spock")

    def test_validate_assertion_tool(self):
        result = call_tool(
            "validate_assertion",
            {
                "assertion": "Mirror Spock was a human officer of the democratic Terran Empire.",
                "universe_id": "terran_empire",
            },
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["status"], "hard_contradiction")

    def test_validate_generated_output_tool(self):
        search = call_tool("search_corpus", {"query": "Mirror Spock reforms", "universe_id": "terran_empire", "k": 2})
        result = call_tool(
            "validate_generated_output",
            {
                "text": "Mirror Spock implemented reforms that weakened the Empire. [1]",
                "universe_id": "terran_empire",
                "retrieval_hits": search["data"]["hits"],
                "check_kg": False,
            },
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["status"], "validated")
        self.assertEqual(result["data"]["claim_type_summary"]["canon_supported"], 1)

    def test_resolve_citation_returns_exact_current_excerpt(self):
        search = call_tool("search_corpus", {"query": "Mirror Spock reforms", "universe_id": "terran_empire", "k": 1})
        citation = search["data"]["hits"][0]["citation"]

        result = call_tool("resolve_citation", {"citation": citation, "universe_id": "terran_empire"})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["citation"], citation)

    def test_resolve_citation_refuses_legacy_identity(self):
        result = call_tool("resolve_citation", {"citation": "source.txt#unsafe", "universe_id": "terran_empire"})

        self.assertEqual(result["status"], "not_found")

    def test_unknown_tool_is_clean_error(self):
        result = call_tool("missing_tool")

        self.assertEqual(result["status"], "error")
        self.assertTrue(result["warnings"])


if __name__ == "__main__":
    unittest.main()
