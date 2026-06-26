import unittest

from src.mcp_tools import call_tool


class MCPToolsTests(unittest.TestCase):
    def test_list_universes_tool(self):
        result = call_tool("list_universes")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"][0]["universe_id"], "terran_empire")

    def test_search_corpus_tool(self):
        result = call_tool("search_corpus", {"query": "Mirror Spock reforms", "k": 2})

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["data"])
        self.assertIn("citation", result["data"][0])

    def test_get_entity_tool(self):
        result = call_tool("get_entity", {"name": "Mirror Spock"})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["name"], "Mirror Spock")

    def test_validate_assertion_tool(self):
        result = call_tool(
            "validate_assertion",
            {"assertion": "Mirror Spock was a human officer of the democratic Terran Empire."},
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["status"], "hard_contradiction")

    def test_unknown_tool_is_clean_error(self):
        result = call_tool("missing_tool")

        self.assertEqual(result["status"], "error")
        self.assertTrue(result["warnings"])


if __name__ == "__main__":
    unittest.main()
