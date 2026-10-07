from types import SimpleNamespace
from unittest.mock import patch

from src.query_rewriter import rewrite_query
from src.router import classify_request


def test_router_llm_fallback_uses_provider_abstraction():
    provider = SimpleNamespace(
        generate=lambda request: SimpleNamespace(
            text='{"route": "lore", "reason": "creative request"}'
        )
    )

    with patch("src.router.provider_from_name", return_value=provider) as factory:
        result = classify_request(
            "A curious request",
            api_key="test-key",
            provider_name="deepseek",
        )

    assert result["route"] == "lore"
    assert result["method"] == "llm"
    factory.assert_called_once_with("deepseek", api_key="test-key")


def test_query_rewriter_llm_uses_provider_abstraction():
    provider = SimpleNamespace(
        generate=lambda request: SimpleNamespace(
            text='{"keyword": "walk", "type": "vocabulary"}'
        )
    )

    with patch("src.query_rewriter.provider_from_name", return_value=provider) as factory:
        result = rewrite_query(
            'Comment se dit "marcher" en elfique ?',
            api_key="test-key",
            provider_name="deepseek",
        )

    assert result == {"keyword": "walk", "type": "vocabulary"}
    factory.assert_called_once_with("deepseek", api_key="test-key")
