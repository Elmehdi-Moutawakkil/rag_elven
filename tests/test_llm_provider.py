import unittest

from src.llm_provider import (
    GroqProvider,
    LLMRequest,
    MissingLLMKeyError,
    StaticLLMProvider,
    provider_from_name,
)


class LLMProviderTests(unittest.TestCase):
    def test_static_provider_is_deterministic(self):
        provider = StaticLLMProvider("fixed response")

        response = provider.generate(LLMRequest(prompt="hello", model="demo"))

        self.assertEqual(response.text, "fixed response")
        self.assertEqual(response.provider, "static")
        self.assertEqual(response.model, "demo")

    def test_provider_factory(self):
        self.assertIsInstance(provider_from_name("static"), StaticLLMProvider)

    def test_missing_groq_key_raises_clean_error(self):
        provider = GroqProvider(api_key="")

        with self.assertRaises(MissingLLMKeyError):
            provider.generate(LLMRequest(prompt="hello"))


if __name__ == "__main__":
    unittest.main()
