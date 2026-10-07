"""Offline regressions for provider failures shown in the application."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.llm import call_llm
from src.llm_provider import (
    DeepSeekProvider,
    GroqProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
    OpenAIProvider,
    generate_lore_text,
)
from inspector.app_bridge import call_qa_elvish, call_qa_terran
from src.lore_generator_generic import generate_lore_for_universe
from src.retrieval_adapter import RetrievalStatus
from src.settings import DEEPSEEK_LORE_MODEL, DEFAULT_GROQ_MODEL, GROQ_LORE_MODEL, resolve_groq_model


class FakeNotFoundError(Exception):
    status_code = 404


class FakeCreditError(Exception):
    status_code = 400


def test_deepseek_missing_model_is_a_safe_structured_error():
    with patch("openai.OpenAI") as deepseek:
        deepseek.return_value.chat.completions.create.side_effect = FakeNotFoundError(
            "model missing; key=deepseek-test-secret"
        )

        with pytest.raises(Exception) as raised:
            call_llm("question", api_key="test-deepseek-key")

    message = str(raised.value)
    assert "modèle" in message.lower()
    assert "DEEPSEEK_MODEL" in message
    assert "deepseek-test-secret" not in message
    assert "model missing" not in message


def test_lore_credit_error_is_safe_and_never_claims_success():
    retrieval = SimpleNamespace(
        status=RetrievalStatus.SUCCESS,
        hits=[{"text": "Canon excerpt."}],
        to_dict=lambda: {"status": "SUCCESS", "hits": []},
    )
    with patch("src.lore_generator_generic.retrieve_evidence_result", return_value=retrieval), patch(
        "src.lore_generator_generic.generate_lore_text",
        side_effect=FakeCreditError("credit balance too low; key=sk-ant-secret"),
    ):
        result = generate_lore_for_universe(
            "Write lore",
            "Test universe",
            api_key="sk-ant-secret",
            universe_id="tolkien",
        )

    assert result["success"] is False
    assert result["story"] is None
    assert "crédit" in result["error"].lower()
    assert "sk-ant-secret" not in result["error"]
    assert "credit balance too low" not in result["error"]


def test_explicit_groq_lore_provider_uses_its_own_model_without_fallback():
    response = LLMResponse(text="Generated lore", provider="groq", model=GROQ_LORE_MODEL)
    with patch.object(GroqProvider, "generate", return_value=response) as generate:
        text = generate_lore_text("Prompt", "groq", "gsk_test")

    assert text == "Generated lore"
    assert generate.call_args.args[0].model == GROQ_LORE_MODEL
    with pytest.raises(LLMProviderError, match="PROVIDER_UNSUPPORTED"):
        generate_lore_text("Prompt", "unknown", "key")


def test_explicit_deepseek_lore_provider_uses_its_own_model_without_fallback():
    response = LLMResponse(text="Generated lore", provider="deepseek", model=DEEPSEEK_LORE_MODEL)
    with patch.object(DeepSeekProvider, "generate", return_value=response) as generate:
        text = generate_lore_text("Prompt", "deepseek", "test-deepseek-key")

    assert text == "Generated lore"
    assert generate.call_args.args[0].model == DEEPSEEK_LORE_MODEL


def test_deepseek_error_is_safe_and_does_not_leak_provider_body():
    with patch("openai.OpenAI") as openai_client:
        openai_client.return_value.chat.completions.create.side_effect = FakeCreditError(
            "insufficient balance; key=deepseek-secret"
        )

        with pytest.raises(LLMProviderError) as raised:
            DeepSeekProvider(api_key="test-deepseek-key").generate(LLMRequest(prompt="hello"))

    message = str(raised.value)
    assert "DeepSeek" in message
    assert "deepseek-secret" not in message
    assert "insufficient balance" not in message


def test_openai_error_is_safe_and_does_not_leak_provider_body():
    with patch("openai.OpenAI") as openai_client:
        openai_client.return_value.chat.completions.create.side_effect = FakeCreditError(
            "request rejected; key=openai-test-secret"
        )

        with pytest.raises(LLMProviderError) as raised:
            OpenAIProvider(api_key="test-openai-key").generate(LLMRequest(prompt="hello"))

    message = str(raised.value)
    assert "Openai" in message
    assert "openai-test-secret" not in message
    assert "request rejected" not in message


def test_inspector_elvish_qa_never_exposes_raw_provider_error(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    with patch("inspector.app_bridge._get_embedding_model", return_value=object()), patch(
        "inspector.app_bridge._get_elvish_index", return_value=(object(), [])
    ), patch(
        "src.retrieval.retrieve", return_value={"faiss": [], "dictionary": []}
    ), patch(
        "src.llm.answer",
        side_effect=FakeCreditError("insufficient balance; key=inspector-secret"),
    ):
        result = call_qa_elvish("question")

    assert result["success"] is False
    assert "DeepSeek" in result["error"]
    assert "inspector-secret" not in result["error"]
    assert "insufficient balance" not in result["error"]


def test_inspector_terran_qa_never_exposes_raw_provider_error(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    with patch("inspector.app_bridge._get_embedding_model", return_value=object()), patch(
        "inspector.app_bridge._get_terran_index", return_value=(object(), [])
    ), patch("src.retrieval.search_faiss", return_value=[]), patch(
        "src.llm.call_llm",
        side_effect=FakeCreditError("insufficient balance; key=inspector-secret"),
    ):
        result = call_qa_terran("question")

    assert result["success"] is False
    assert "DeepSeek" in result["error"]
    assert "inspector-secret" not in result["error"]
    assert "insufficient balance" not in result["error"]


def test_generic_lore_generation_uses_deepseek_by_default():
    retrieval = SimpleNamespace(
        status=RetrievalStatus.SUCCESS,
        hits=[{"text": "Canon excerpt."}],
        to_dict=lambda: {"status": "SUCCESS", "hits": []},
    )
    with patch(
        "src.lore_generator_generic.retrieve_evidence_result", return_value=retrieval
    ), patch(
        "src.lore_generator_generic.generate_lore_text", return_value="DeepSeek lore"
    ) as generate:
        result = generate_lore_for_universe(
            "Write lore",
            "Test universe",
            api_key="test-deepseek-key",
            universe_id="tolkien",
        )

    assert result["success"] is True
    assert result["story"] == "DeepSeek lore"
    assert generate.call_args.args[1:] == ("deepseek", "test-deepseek-key")


def test_groq_model_configuration_strips_blanks_and_keeps_custom_override():
    default_model, default_warning = resolve_groq_model("   ")
    custom_model, custom_warning = resolve_groq_model("  provider/custom-model  ")

    assert default_model == DEFAULT_GROQ_MODEL
    assert default_warning is None
    assert custom_model == "provider/custom-model"
    assert custom_warning is None
