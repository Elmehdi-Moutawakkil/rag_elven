"""Provider-neutral LLM interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from src.settings import (
    ANTHROPIC_API_KEY_ENV,
    ANTHROPIC_LORE_MODEL,
    GROQ_API_KEY_ENV,
    GROQ_MODEL,
    LM_STUDIO_BASE_URL,
    LOCAL_MODEL_NAME,
    env_value,
    missing_key_message,
)


@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    system: str | None = None
    model: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.2
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str
    usage: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


class LLMProvider(Protocol):
    provider_name: str

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text from a provider-specific backend."""


class MissingLLMKeyError(ValueError):
    """Raised when a provider requires a missing API key."""


class StaticLLMProvider:
    """Deterministic provider used in tests and offline demos."""

    provider_name = "static"

    def __init__(self, response_text: str = ""):
        self.response_text = response_text

    def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text=self.response_text or request.prompt,
            provider=self.provider_name,
            model=request.model or "static",
        )


class GroqProvider:
    provider_name = "groq"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def generate(self, request: LLMRequest) -> LLMResponse:
        key = self.api_key or env_value(GROQ_API_KEY_ENV)
        if not key:
            raise MissingLLMKeyError(missing_key_message(GROQ_API_KEY_ENV, "generation Groq"))
        from groq import Groq

        model = request.model or GROQ_MODEL
        client = Groq(api_key=key)
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        usage = getattr(response, "usage", None)
        return LLMResponse(
            text=response.choices[0].message.content or "",
            provider=self.provider_name,
            model=model,
            usage=usage.model_dump() if hasattr(usage, "model_dump") else {},
        )


class AnthropicProvider:
    provider_name = "anthropic"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def generate(self, request: LLMRequest) -> LLMResponse:
        key = self.api_key or env_value(ANTHROPIC_API_KEY_ENV)
        if not key:
            raise MissingLLMKeyError(missing_key_message(ANTHROPIC_API_KEY_ENV, "generation Anthropic"))
        import anthropic

        model = request.model or ANTHROPIC_LORE_MODEL
        client = anthropic.Anthropic(api_key=key)
        response = client.messages.create(
            model=model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=request.system or "",
            messages=[{"role": "user", "content": request.prompt}],
        )
        text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        usage = getattr(response, "usage", None)
        return LLMResponse(
            text=text,
            provider=self.provider_name,
            model=model,
            usage=usage.model_dump() if hasattr(usage, "model_dump") else {},
        )


class OpenAICompatibleProvider:
    """Local or hosted OpenAI-compatible endpoint provider."""

    provider_name = "openai_compatible"

    def __init__(self, base_url: str | None = None, api_key: str = "lm-studio"):
        self.base_url = base_url or LM_STUDIO_BASE_URL
        self.api_key = api_key

    def generate(self, request: LLMRequest) -> LLMResponse:
        import openai

        model = request.model or LOCAL_MODEL_NAME
        client = openai.OpenAI(base_url=self.base_url, api_key=self.api_key)
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        usage = getattr(response, "usage", None)
        return LLMResponse(
            text=response.choices[0].message.content or "",
            provider=self.provider_name,
            model=model,
            usage=usage.model_dump() if hasattr(usage, "model_dump") else {},
        )


def provider_from_name(name: str) -> LLMProvider:
    """Factory for supported providers."""
    normalized = name.lower().strip()
    if normalized == "groq":
        return GroqProvider()
    if normalized in {"anthropic", "claude"}:
        return AnthropicProvider()
    if normalized in {"local", "lm_studio", "openai_compatible"}:
        return OpenAICompatibleProvider()
    if normalized == "static":
        return StaticLLMProvider()
    raise ValueError(f"Unknown LLM provider: {name}")
