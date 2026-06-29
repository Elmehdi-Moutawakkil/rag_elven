import unittest

from src.agent import (
    assess_request_risk,
    available_tools,
    build_generation_prompt,
    plan_request,
    run_controlled_agent,
)
from src.llm_provider import StaticLLMProvider


class AgentTests(unittest.TestCase):
    def test_plan_request_includes_retrieval_generation_validation(self):
        plan = plan_request("Tell me about Mirror Spock")
        tools = [step.tool for step in plan]

        self.assertEqual(tools, ["retrieve", "generate", "validate_output"])
        self.assertTrue(all(step.risk_level in {"low", "medium", "high"} for step in plan))

    def test_controlled_agent_runs_with_trace_without_provider(self):
        run = run_controlled_agent("Mirror Spock reforms", universe_id="terran_empire")
        data = run.to_dict()

        self.assertTrue(data["sources"])
        self.assertTrue(data["final_output"])
        self.assertEqual(data["trace"][0]["tool"], "assess_risk")
        self.assertEqual(data["trace"][1]["tool"], "retrieve")
        self.assertEqual(data["trace"][-1]["tool"], "validate_output")
        self.assertEqual(data["risk_level"], "low")

    def test_controlled_agent_uses_provider_when_given(self):
        provider = StaticLLMProvider("Mirror Spock implemented reforms that weakened the Terran Empire.")

        run = run_controlled_agent("Mirror Spock reforms", universe_id="terran_empire", provider=provider)
        generate_trace = next(item for item in run.trace if item["tool"] == "generate")

        self.assertEqual(run.final_output, "Mirror Spock implemented reforms that weakened the Terran Empire.")
        self.assertEqual(generate_trace["provider"], "static")

    def test_generation_prompt_requires_source_citations(self):
        prompt = build_generation_prompt(
            "Mirror Spock reforms",
            [{"source_path": "source.txt", "text": "Mirror Spock implemented reforms."}],
        )

        self.assertIn("Cite every factual claim", prompt)
        self.assertIn("[1]", prompt)

    def test_available_tools_are_read_only_or_confirmation_gated(self):
        tools = available_tools()

        self.assertGreaterEqual(len(tools), 5)
        for tool in tools:
            self.assertIn("risk_level", tool)
            if not tool["read_only"]:
                self.assertTrue(tool["requires_confirmation"])

    def test_risky_request_requires_human_confirmation(self):
        risk = assess_request_risk("save this as canon and push it")

        self.assertEqual(risk["risk_level"], "high")
        self.assertTrue(risk["requires_human_confirmation"])
        self.assertIn("push", risk["triggers"])

    def test_controlled_agent_blocks_risky_request_before_tools(self):
        run = run_controlled_agent("save this as canon and push it", universe_id="terran_empire")
        data = run.to_dict()

        self.assertEqual(data["validation"]["status"], "blocked_pending_confirmation")
        self.assertTrue(data["requires_human_confirmation"])
        self.assertEqual(data["trace"][-1]["tool"], "request_confirmation")
        self.assertFalse(data["sources"])


if __name__ == "__main__":
    unittest.main()
