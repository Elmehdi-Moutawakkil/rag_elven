import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.llm_provider import (
    DeepSeekProvider,
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
from src.llm import call_llm
from src.settings import QA_PROVIDER


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
        self.assertIsInstance(provider_from_name("deepseek"), DeepSeekProvider)

    def test_missing_groq_key_raises_clean_error(self):
        provider = GroqProvider(api_key="")

        with self.assertRaises(MissingLLMKeyError):
            provider.generate(LLMRequest(prompt="hello"))

    def test_missing_openai_key_raises_clean_error(self):
        provider = OpenAIProvider(api_key="")

        with self.assertRaises(MissingLLMKeyError):
            provider.generate(LLMRequest(prompt="hello"))

    def test_missing_deepseek_key_raises_clean_error(self):
        provider = DeepSeekProvider(api_key="")

        with self.assertRaises(MissingLLMKeyError):
            provider.generate(LLMRequest(prompt="hello"))

    @patch("openai.OpenAI")
    def test_deepseek_uses_official_openai_compatible_endpoint(self, openai_client):
        openai_client.return_value.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="DeepSeek response"))],
            usage={"prompt_tokens": 12, "completion_tokens": 4},
        )

        response = DeepSeekProvider(api_key="test-deepseek-key").generate(
            LLMRequest(prompt="hello", system="Be precise")
        )

        openai_client.assert_called_once_with(
            api_key="test-deepseek-key",
            base_url="https://api.deepseek.com",
        )
        openai_client.return_value.chat.completions.create.assert_called_once_with(
            model="deepseek-flash",
            messages=[
                {"role": "system", "content": "Be precise"},
                {"role": "user", "content": "hello"},
            ],
            max_tokens=1024,
            temperature=0.2,
        )
        self.assertEqual(response.text, "DeepSeek response")
        self.assertEqual(response.provider, "deepseek")
        self.assertEqual(response.model, "deepseek-flash")
        self.assertEqual(response.usage["completion_tokens"], 4)

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

    @patch("src.llm.provider_from_name")
    def test_main_qa_uses_deepseek_provider_abstraction_by_default(self, factory):
        factory.return_value.generate.return_value = SimpleNamespace(text="QA response")

        result = call_llm("question", api_key="test-deepseek-key")

        self.assertEqual(QA_PROVIDER, "deepseek")
        factory.assert_called_once_with("deepseek", api_key="test-deepseek-key")
        request = factory.return_value.generate.call_args.args[0]
        self.assertEqual(request.prompt, "question")
        self.assertIsNone(request.model)
        self.assertEqual(result, "QA response")

    @patch("src.llm.provider_from_name")
    def test_main_qa_explicit_provider_does_not_fallback(self, factory):
        factory.return_value.generate.side_effect = RuntimeError("provider unavailable")

        with self.assertRaises(RuntimeError, msg="provider unavailable"):
            call_llm("question", api_key="explicit-key", provider_name="groq")

        factory.assert_called_once_with("groq", api_key="explicit-key")
        factory.return_value.generate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
