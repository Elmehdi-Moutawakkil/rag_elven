"""Provider-neutral LLM interface."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import perf_counter
from typing import Any
from typing import Protocol

from src.settings import (
    ANTHROPIC_API_KEY_ENV,
    ANTHROPIC_LORE_MODEL,
    GROQ_API_KEY_ENV,
    GROQ_LORE_MODEL,
    GROQ_MODEL,
    LM_STUDIO_BASE_URL,
    LOCAL_MODEL_NAME,
    OLLAMA_BASE_URL,
    OPENAI_API_KEY_ENV,
    OPENAI_MODEL,
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
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    duration_ms: int | None = None
    cost_estimate_usd: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LLMRunTrace:
    provider: str
    model: str | None
    ok: bool
    duration_ms: int
    usage: dict[str, Any] = field(default_factory=dict)
    cost_estimate_usd: float | None = None
    error: str | None = None
    response: LLMResponse | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.response:
            data["response"] = self.response.to_dict()
        return data


class LLMProvider(Protocol):
    provider_name: str

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text from a provider-specific backend."""


class MissingLLMKeyError(ValueError):
    """Raised when a provider requires a missing API key."""


class LLMProviderError(RuntimeError):
    """A safe, user-facing failure from an external LLM provider."""


def provider_error_message(provider: str, error: BaseException) -> str:
    """Translate an SDK failure without exposing a provider response body."""
    provider_name = provider.strip().lower()
    provider_label = {"groq": "Groq", "anthropic": "Anthropic"}.get(provider_name, provider.title())
    status_code = getattr(error, "status_code", None)
    error_text = str(error).casefold()

    if provider_name == "anthropic" and any(
        marker in error_text
        for marker in ("credit balance", "insufficient credit", "balance too low", "insufficient funds")
    ):
        return "Le crédit Anthropic est insuffisant pour générer du lore."
    if status_code == 404:
        if provider_name == "groq":
            return "Le modèle Groq configuré est introuvable. Vérifiez GROQ_MODEL."
        return f"Le modèle configuré pour {provider_label} est introuvable."
    if status_code in {401, 403}:
        return f"L'accès à {provider_label} a été refusé. Vérifiez la clé API configurée."
    if status_code == 429:
        return f"{provider_label} limite temporairement les requêtes. Réessayez plus tard."
    if status_code is not None and 400 <= status_code < 500:
        return f"{provider_label} a refusé la requête. Vérifiez sa configuration puis réessayez."
    return f"{provider_label} est temporairement indisponible. Réessayez plus tard."


def safe_provider_error(provider: str, error: BaseException) -> LLMProviderError:
    """Convert provider SDK exceptions to the public error contract."""
    if isinstance(error, LLMProviderError):
        return error
    if isinstance(error, MissingLLMKeyError):
        return LLMProviderError(str(error))
    return LLMProviderError(provider_error_message(provider, error))


PRICE_PER_MILLION_TOKENS_USD: dict[tuple[str, str], tuple[float, float]] = {
    ("openai", "gpt-4o-mini"): (0.15, 0.60),
    ("groq", "openai/gpt-oss-20b"): (0.075, 0.30),
}


def _usage_tokens(usage: dict[str, Any]) -> tuple[int, int]:
    input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    return input_tokens, output_tokens


def estimate_cost_usd(provider: str, model: str, usage: dict[str, Any]) -> float | None:
    """Estimate USD cost from token usage when a known price exists."""
    input_tokens, output_tokens = _usage_tokens(usage)
    if input_tokens == 0 and output_tokens == 0:
        return None
    prices = PRICE_PER_MILLION_TOKENS_USD.get((provider, model))
    if prices is None:
        return None
    input_price, output_price = prices
    return round((input_tokens * input_price + output_tokens * output_price) / 1_000_000, 8)


def _usage_to_dict(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    return {}


def generate_with_trace(provider: LLMProvider, request: LLMRequest) -> LLMRunTrace:
    """Generate with timing, usage, cost estimate, and clean error capture."""
    started = perf_counter()
    provider_name = getattr(provider, "provider_name", provider.__class__.__name__)
    try:
        response = provider.generate(request)
        duration_ms = int((perf_counter() - started) * 1000)
        cost = response.cost_estimate_usd
        if cost is None:
            cost = estimate_cost_usd(response.provider, response.model, response.usage)
        response = LLMResponse(
            text=response.text,
            provider=response.provider,
            model=response.model,
            usage=response.usage,
            raw=response.raw,
            duration_ms=response.duration_ms or duration_ms,
            cost_estimate_usd=cost,
        )
        return LLMRunTrace(
            provider=response.provider,
            model=response.model,
            ok=True,
            duration_ms=duration_ms,
            usage=response.usage,
            cost_estimate_usd=cost,
            response=response,
        )
    except MissingLLMKeyError as exc:
        duration_ms = int((perf_counter() - started) * 1000)
        return LLMRunTrace(
            provider=provider_name,
            model=request.model,
            ok=False,
            duration_ms=duration_ms,
            error=f"MissingLLMKeyError: {exc}",
        )
    except Exception as exc:
        duration_ms = int((perf_counter() - started) * 1000)
        public_error = safe_provider_error(provider_name, exc)
        return LLMRunTrace(
            provider=provider_name,
            model=request.model,
            ok=False,
            duration_ms=duration_ms,
            error=str(public_error),
        )


class StaticLLMProvider:
    """Deterministic provider used in tests and offline demos."""

    provider_name = "static"

    def __init__(self, response_text: str = ""):
        self.response_text = response_text

    def generate(self, request: LLMRequest) -> LLMResponse:
        usage = {
            "prompt_tokens": len(request.prompt.split()),
            "completion_tokens": len((self.response_text or request.prompt).split()),
        }
        return LLMResponse(
            text=self.response_text or request.prompt,
            provider=self.provider_name,
            model=request.model or "static",
            usage=usage,
        )


class GroqProvider:
    provider_name = "groq"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def generate(self, request: LLMRequest) -> LLMResponse:
        key = env_value(GROQ_API_KEY_ENV) if self.api_key is None else self.api_key.strip()
        if not key:
            raise MissingLLMKeyError(missing_key_message(GROQ_API_KEY_ENV, "generation Groq"))
        from groq import Groq

        model = request.model or GROQ_MODEL
        client = Groq(api_key=key)
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )
        except Exception as exc:
            raise safe_provider_error(self.provider_name, exc) from None
        usage = _usage_to_dict(getattr(response, "usage", None))
        return LLMResponse(
            text=response.choices[0].message.content or "",
            provider=self.provider_name,
            model=model,
            usage=usage,
            cost_estimate_usd=estimate_cost_usd(self.provider_name, model, usage),
        )


class AnthropicProvider:
    provider_name = "anthropic"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def generate(self, request: LLMRequest) -> LLMResponse:
        key = env_value(ANTHROPIC_API_KEY_ENV) if self.api_key is None else self.api_key.strip()
        if not key:
            raise MissingLLMKeyError(missing_key_message(ANTHROPIC_API_KEY_ENV, "generation Anthropic"))
        import anthropic

        model = request.model or ANTHROPIC_LORE_MODEL
        client = anthropic.Anthropic(api_key=key)
        try:
            response = client.messages.create(
                model=model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                system=request.system or "",
                messages=[{"role": "user", "content": request.prompt}],
            )
        except Exception as exc:
            raise safe_provider_error(self.provider_name, exc) from None
        text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        usage = _usage_to_dict(getattr(response, "usage", None))
        return LLMResponse(
            text=text,
            provider=self.provider_name,
            model=model,
            usage=usage,
            cost_estimate_usd=estimate_cost_usd(self.provider_name, model, usage),
        )


class OpenAIProvider:
    provider_name = "openai"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def generate(self, request: LLMRequest) -> LLMResponse:
        key = env_value(OPENAI_API_KEY_ENV) if self.api_key is None else self.api_key.strip()
        if not key:
            raise MissingLLMKeyError(missing_key_message(OPENAI_API_KEY_ENV, "generation OpenAI"))
        import openai

        model = request.model or OPENAI_MODEL
        client = openai.OpenAI(api_key=key)
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
        usage = _usage_to_dict(getattr(response, "usage", None))
        return LLMResponse(
            text=response.choices[0].message.content or "",
            provider=self.provider_name,
            model=model,
            usage=usage,
            cost_estimate_usd=estimate_cost_usd(self.provider_name, model, usage),
        )


class OpenAICompatibleProvider:
    """Local or hosted OpenAI-compatible endpoint provider."""

    provider_name = "openai_compatible"

    def __init__(self, base_url: str | None = None, api_key: str = "lm-studio", provider_name: str | None = None):
        self.base_url = base_url or LM_STUDIO_BASE_URL
        self.api_key = api_key
        if provider_name:
            self.provider_name = provider_name

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
        usage = _usage_to_dict(getattr(response, "usage", None))
        return LLMResponse(
            text=response.choices[0].message.content or "",
            provider=self.provider_name,
            model=model,
            usage=usage,
            cost_estimate_usd=estimate_cost_usd(self.provider_name, model, usage),
        )


def provider_from_name(name: str) -> LLMProvider:
    """Factory for supported providers."""
    normalized = name.lower().strip()
    if normalized == "groq":
        return GroqProvider()
    if normalized in {"anthropic", "claude"}:
        return AnthropicProvider()
    if normalized in {"openai", "chatgpt"}:
        return OpenAIProvider()
    if normalized in {"local", "lm_studio", "openai_compatible"}:
        return OpenAICompatibleProvider()
    if normalized == "ollama":
        return OpenAICompatibleProvider(base_url=OLLAMA_BASE_URL, api_key="ollama", provider_name="ollama")
    if normalized == "static":
        return StaticLLMProvider()
    raise ValueError(f"Unknown LLM provider: {name}")


def generate_lore_text(prompt: str, provider_name: str, api_key: str | None) -> str:
    """Generate lore through an explicitly selected provider, with no fallback."""
    normalized = provider_name.strip().lower()
    if normalized == "anthropic":
        provider: LLMProvider = AnthropicProvider(api_key=api_key)
        model = ANTHROPIC_LORE_MODEL
    elif normalized == "groq":
        provider = GroqProvider(api_key=api_key)
        model = GROQ_LORE_MODEL
    else:
        raise LLMProviderError("PROVIDER_UNSUPPORTED: fournisseur de lore non pris en charge.")

    response = provider.generate(
        LLMRequest(prompt=prompt, model=model, max_tokens=1024, temperature=0.2)
    )
    if not response.text.strip():
        raise LLMProviderError("Le fournisseur de lore n'a renvoyé aucun texte.")
    return response.text
