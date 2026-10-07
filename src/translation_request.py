"""Typed parsing and lexical normalization for translation requests."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from src.database import search_translation
from src.llm_provider import LLMProviderError, LLMRequest, provider_from_name, safe_provider_error
from src.settings import QA_PROVIDER


@dataclass(frozen=True)
class TranslationRequest:
    kind: str
    source_text: str
    source_language: str
    target_language: str


class TranslationRequestError(ValueError):
    """The user input is not a supported translation request."""


class TranslationNormalizationError(LLMProviderError):
    """A safe public error produced while normalizing a lexical gloss."""


_FRENCH_LEXICAL = re.compile(
    r"^comment\s+(?:se\s+)?dit(?:-on)?\s+[\"“”']?(.+?)[\"“”']?\s+en\s+"
    r"(elfique|quenya|sindarin)\s*\??$",
    re.IGNORECASE,
)
_ENGLISH_LEXICAL = re.compile(
    r"^how\s+do\s+you\s+say\s+[\"“”']?(.+?)[\"“”']?\s+in\s+"
    r"(elvish|quenya|sindarin)\s*\??$",
    re.IGNORECASE,
)


def _kind_for_source(source_text: str, *, quoted: bool) -> str:
    text = source_text.strip()
    if quoted and len(text.split()) <= 3:
        return "lexical"
    if len(text.split()) == 1:
        return "lexical"
    return "sentence"


def parse_translation_request(user_input: str) -> TranslationRequest:
    """Parse a translation request without an LLM call."""
    text = user_input.strip()
    for pattern, language in ((_FRENCH_LEXICAL, "fr"), (_ENGLISH_LEXICAL, "en")):
        match = pattern.match(text)
        if match:
            source = match.group(1).strip().strip('"“”\'')
            target = match.group(2).lower()
            if target == "elfique":
                target = "elvish"
            quoted = any(mark in text for mark in ('"', "'", "“", "”"))
            return TranslationRequest(
                kind=_kind_for_source(source, quoted=quoted),
                source_text=source,
                source_language=language,
                target_language=target,
            )

    normalized = re.sub(
        r"^(?:translate|traduis|traduction)[:\s]+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip().strip('"“”\'')
    if not normalized:
        raise TranslationRequestError("La requête de traduction est vide.")
    return TranslationRequest(
        kind="lexical" if len(normalized.split()) == 1 else "sentence",
        source_text=normalized,
        source_language="en",
        target_language="elvish",
    )


_NORMALIZATION_SYSTEM = """You normalize one lexical gloss for dictionary lookup.
Return exactly one JSON object with exactly one field named \"gloss\".
The gloss must be a concise lowercase English dictionary lemma.
Do not translate into Quenya or Sindarin. Do not add markdown or explanation."""


def normalize_lexical_gloss(
    request: TranslationRequest,
    *,
    provider_name: str = QA_PROVIDER,
    api_key: str | None = None,
) -> str:
    """Normalize a lexical request to an English gloss through one provider."""
    if request.kind != "lexical":
        raise TranslationRequestError("La normalisation lexicale exige un mot ou une locution courte.")
    provider_key = provider_name.strip().lower()
    try:
        provider = provider_from_name(provider_key, api_key=api_key)
        response = provider.generate(
            LLMRequest(
                system=_NORMALIZATION_SYSTEM,
                prompt=json.dumps(
                    {
                        "source_text": request.source_text,
                        "source_language": request.source_language,
                        "target_language": request.target_language,
                    },
                    ensure_ascii=False,
                ),
                max_tokens=40,
                temperature=0.0,
                metadata={"purpose": "translation_gloss_normalization"},
            )
        )
    except Exception as exc:
        raise TranslationNormalizationError(str(safe_provider_error(provider_key, exc))) from None

    try:
        payload = json.loads(response.text)
    except (json.JSONDecodeError, TypeError):
        raise TranslationNormalizationError(
            "Le fournisseur de traduction n'a pas renvoyé le JSON attendu."
        ) from None
    if set(payload) != {"gloss"} or not isinstance(payload["gloss"], str):
        raise TranslationNormalizationError(
            "Le fournisseur de traduction n'a pas renvoyé le JSON attendu."
        )
    gloss = payload["gloss"].strip().lower()
    if not gloss or not re.fullmatch(r"[a-z][a-z -]*", gloss):
        raise TranslationNormalizationError(
            "Le fournisseur de traduction a renvoyé un glossaire anglais invalide."
        )
    return gloss


def lookup_lexical_translation(request: TranslationRequest, gloss: str) -> list[dict]:
    """Return dictionary entries for a normalized English gloss."""
    language = {
        "quenya": "Quenya",
        "sindarin": "Sindarin",
    }.get(request.target_language)
    entries = [dict(row) for row in search_translation(gloss)]
    if language:
        entries = [entry for entry in entries if entry.get("language") == language]
    return entries
