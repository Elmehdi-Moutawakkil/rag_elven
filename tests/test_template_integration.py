import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TemplateIntegrationTests(unittest.TestCase):
    def test_agent_profiles_are_valid_and_tool_scoped(self):
        data = json.loads((PROJECT_ROOT / "prompts" / "agent_profiles.json").read_text(encoding="utf-8"))

        self.assertEqual(data["schema_version"], 1)
        self.assertGreaterEqual(len(data["profiles"]), 3)
        for profile in data["profiles"]:
            self.assertIn("id", profile)
            self.assertIn("allowed_tools", profile)
            self.assertTrue(profile["rules"])

    def test_template_report_exists(self):
        report = (PROJECT_ROOT / "reports" / "template_integration.md").read_text(encoding="utf-8")

        self.assertIn("Integrate Now", report)
        self.assertIn("Ignore", report)
        self.assertIn("MCP", report)


if __name__ == "__main__":
    unittest.main()
