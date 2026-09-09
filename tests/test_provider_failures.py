"""Offline regressions for provider failures shown in the application."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.llm import call_llm
from src.llm_provider import GroqProvider, LLMProviderError, LLMResponse, generate_lore_text
from src.lore_generator_generic import generate_lore_for_universe
from src.retrieval_adapter import RetrievalStatus
from src.settings import DEFAULT_GROQ_MODEL, GROQ_LORE_MODEL, resolve_groq_model


class FakeNotFoundError(Exception):
    status_code = 404


class FakeCreditError(Exception):
    status_code = 400


def test_groq_missing_model_is_a_safe_structured_error():
    with patch("src.llm.Groq") as groq:
        groq.return_value.chat.completions.create.side_effect = FakeNotFoundError(
            "model missing; key=gsk_live_secret"
        )

        with pytest.raises(Exception) as raised:
            call_llm("question", api_key="gsk_live_secret")

    message = str(raised.value)
    assert "modèle" in message.lower()
    assert "GROQ_MODEL" in message
    assert "gsk_live_secret" not in message
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


def test_groq_model_configuration_strips_blanks_and_keeps_custom_override():
    default_model, default_warning = resolve_groq_model("   ")
    custom_model, custom_warning = resolve_groq_model("  provider/custom-model  ")

    assert default_model == DEFAULT_GROQ_MODEL
    assert default_warning is None
    assert custom_model == "provider/custom-model"
    assert custom_warning is None
