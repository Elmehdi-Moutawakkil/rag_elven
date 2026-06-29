import unittest

from src.llm_provider import (
    GroqProvider,
    LLMRequest,
    MissingLLMKeyError,
    OpenAICompatibleProvider,
    OpenAIProvider,
    StaticLLMProvider,
    estimate_cost_usd,
    generate_with_trace,
    provider_from_name,
)


class LLMProviderTests(unittest.TestCase):
    def test_static_provider_is_deterministic(self):
        provider = StaticLLMProvider("fixed response")

        response = provider.generate(LLMRequest(prompt="hello", model="demo"))

        self.assertEqual(response.text, "fixed response")
        self.assertEqual(response.provider, "static")
        self.assertEqual(response.model, "demo")
        self.assertGreater(response.usage["prompt_tokens"], 0)

    def test_provider_factory(self):
        self.assertIsInstance(provider_from_name("static"), StaticLLMProvider)
        self.assertIsInstance(provider_from_name("openai"), OpenAIProvider)
        self.assertIsInstance(provider_from_name("lm_studio"), OpenAICompatibleProvider)
        ollama = provider_from_name("ollama")
        self.assertIsInstance(ollama, OpenAICompatibleProvider)
        self.assertEqual(ollama.provider_name, "ollama")

    def test_missing_groq_key_raises_clean_error(self):
        provider = GroqProvider(api_key="")

        with self.assertRaises(MissingLLMKeyError):
            provider.generate(LLMRequest(prompt="hello"))

    def test_missing_openai_key_raises_clean_error(self):
        provider = OpenAIProvider(api_key="")

        with self.assertRaises(MissingLLMKeyError):
            provider.generate(LLMRequest(prompt="hello"))

    def test_generate_with_trace_captures_success(self):
        trace = generate_with_trace(StaticLLMProvider("fixed response"), LLMRequest(prompt="hello world"))

        self.assertTrue(trace.ok)
        self.assertEqual(trace.provider, "static")
        self.assertIsNotNone(trace.response)
        self.assertGreaterEqual(trace.duration_ms, 0)
        self.assertEqual(trace.response.text, "fixed response")

    def test_generate_with_trace_captures_errors(self):
        trace = generate_with_trace(GroqProvider(api_key=""), LLMRequest(prompt="hello"))

        self.assertFalse(trace.ok)
        self.assertIn("MissingLLMKeyError", trace.error)
        self.assertGreaterEqual(trace.duration_ms, 0)

    def test_cost_estimate_uses_known_token_prices(self):
        cost = estimate_cost_usd(
            "openai",
            "gpt-4o-mini",
            {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000},
        )

        self.assertEqual(cost, 0.75)


if __name__ == "__main__":
    unittest.main()
