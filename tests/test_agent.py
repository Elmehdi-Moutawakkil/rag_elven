import unittest

from src.agent import plan_request, run_controlled_agent
from src.llm_provider import StaticLLMProvider


class AgentTests(unittest.TestCase):
    def test_plan_request_includes_retrieval_generation_validation(self):
        plan = plan_request("Tell me about Mirror Spock")
        tools = [step.tool for step in plan]

        self.assertEqual(tools, ["retrieve", "generate", "validate_output"])

    def test_controlled_agent_runs_with_trace_without_provider(self):
        run = run_controlled_agent("Mirror Spock reforms", universe_id="terran_empire")
        data = run.to_dict()

        self.assertTrue(data["sources"])
        self.assertTrue(data["final_output"])
        self.assertEqual(data["trace"][0]["tool"], "retrieve")
        self.assertEqual(data["trace"][-1]["tool"], "validate_output")

    def test_controlled_agent_uses_provider_when_given(self):
        provider = StaticLLMProvider("Mirror Spock implemented reforms that weakened the Terran Empire.")

        run = run_controlled_agent("Mirror Spock reforms", universe_id="terran_empire", provider=provider)

        self.assertEqual(run.final_output, "Mirror Spock implemented reforms that weakened the Terran Empire.")
        self.assertEqual(run.trace[1]["provider"], "static")


if __name__ == "__main__":
    unittest.main()
