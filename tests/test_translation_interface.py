from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from src.normal_mode import run_normal_translation
from src.translation_request import (
    TranslationNormalizationError,
    normalize_lexical_gloss,
    parse_translation_request,
)


def test_french_lexical_request_is_parsed_without_router_llm():
    request = parse_translation_request('Comment se dit "marcher" en elfique ?')

    assert request.kind == "lexical"
    assert request.source_text == "marcher"
    assert request.source_language == "fr"
    assert request.target_language == "elvish"


def test_lexical_gloss_normalization_uses_deepseek_provider_and_strict_json():
    provider = SimpleNamespace(
        generate=lambda request: SimpleNamespace(text='{"gloss": "walk"}')
    )
    parsed = parse_translation_request('Comment se dit "marcher" en elfique ?')

    with patch("src.translation_request.provider_from_name", return_value=provider) as factory:
        gloss = normalize_lexical_gloss(
            parsed,
            provider_name="deepseek",
            api_key="test-key",
        )

    assert gloss == "walk"
    factory.assert_called_once_with("deepseek", api_key="test-key")


def test_lexical_gloss_accepts_single_json_code_fence_for_provider_compatibility():
    provider = SimpleNamespace(
        generate=lambda request: SimpleNamespace(text='  ```json\n{"gloss":"walk"}\n```  ')
    )
    parsed = parse_translation_request('Comment se dit "marcher" en elfique ?')

    with patch("src.translation_request.provider_from_name", return_value=provider):
        gloss = normalize_lexical_gloss(parsed, api_key="test-key")

    assert gloss == "walk"


def test_lexical_gloss_retries_once_after_invalid_json():
    provider = SimpleNamespace()
    provider.generate = Mock(
        side_effect=[
            SimpleNamespace(text="not-json first-private-body"),
            SimpleNamespace(text='{"gloss":"walk"}'),
        ]
    )
    parsed = parse_translation_request('Comment se dit "marcher" en elfique ?')

    with patch("src.translation_request.provider_from_name", return_value=provider):
        gloss = normalize_lexical_gloss(parsed, api_key="test-key")

    assert gloss == "walk"
    assert provider.generate.call_count == 2
    first_request, retry_request = [call.args[0] for call in provider.generate.call_args_list]
    assert first_request.response_format == "json_object"
    assert first_request.max_tokens >= 128
    assert '{"gloss":"walk"}' in (first_request.system or "")
    assert retry_request.response_format == "json_object"
    assert "previous response" in retry_request.prompt.lower()


def test_lexical_gloss_retries_once_after_empty_content():
    provider = SimpleNamespace(
        generate=Mock(
            side_effect=[
                SimpleNamespace(text=""),
                SimpleNamespace(text='{"gloss":"walk"}'),
            ]
        )
    )
    parsed = parse_translation_request('Comment se dit "marcher" en elfique ?')

    with patch("src.translation_request.provider_from_name", return_value=provider):
        gloss = normalize_lexical_gloss(parsed, api_key="test-key")

    assert gloss == "walk"
    assert provider.generate.call_count == 2


def test_lexical_gloss_double_invalid_does_not_leak_provider_text_or_key():
    provider = SimpleNamespace(generate=Mock(side_effect=[
        SimpleNamespace(text="not-json secret-provider-body"),
        SimpleNamespace(text='{"gloss":"walk","secret":"second-private-body"}'),
    ]))
    parsed = parse_translation_request('Comment se dit "marcher" en elfique ?')

    with patch("src.translation_request.provider_from_name", return_value=provider):
        with pytest.raises(TranslationNormalizationError) as raised:
            normalize_lexical_gloss(parsed, api_key="test-secret")

    assert "JSON" in str(raised.value)
    assert "secret-provider-body" not in str(raised.value)
    assert "second-private-body" not in str(raised.value)
    assert "test-secret" not in str(raised.value)
    assert provider.generate.call_count == 2


def test_french_lexical_translation_returns_quenya_and_sindarin_dictionary_entries():
    provider = SimpleNamespace(generate=Mock(return_value=SimpleNamespace(text='{"gloss": "walk"}')))

    with patch("src.translation_request.provider_from_name", return_value=provider):
        result = run_normal_translation(
            'Comment se dit "marcher" en elfique ?',
            api_key="test-key",
        )

    assert result["status"] == "SUCCESS"
    assert result["kind"] == "lexical"
    assert result["normalized_gloss"] == "walk"
    request = provider.generate.call_args.args[0]
    assert request.response_format == "json_object"
    assert request.max_tokens >= 128
    assert any(
        entry["language"] == "Quenya" and entry["word"].strip(" -") == "vanta"
        for entry in result["entries"]
    )
    assert any(
        entry["language"] == "Sindarin" and entry["word"] == "pada"
        for entry in result["entries"]
    )


def test_english_sentence_translation_keeps_l04_l06_pipeline():
    with patch("src.normal_mode.execute_pipeline", return_value={"error": None}) as execute:
        result = run_normal_translation(
            "The warrior walks.",
            resources={"universe_id": "tolkien"},
        )

    assert result == {"error": None}
    execute.assert_called_once_with(
        ["L04", "L05", "L06"],
        "The warrior walks.",
        resources={"universe_id": "tolkien"},
    )
