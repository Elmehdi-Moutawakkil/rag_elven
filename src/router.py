"""Agent routeur — analyse la requête et décide vers quel pipeline la diriger.

Stratégie :
  1. Fast path déterministe (mots-clés) — 0 appel API, < 1 ms
  2. LLM fallback (Groq llama-3.1-8b) pour les cas ambigus

Routes :
  "qa"        → Phase 1 : Q&A (FAISS + SQLite + Groq)
  "translate" → Phase 2 : Traduction Quenya (pipeline déterministe)
  "lore"      → Phase 3 : Génération de lore (Claude + KG validation)
"""

import json
import os
from typing import Optional

from dotenv import load_dotenv
from groq import Groq
from src.settings import GROQ_API_KEY_ENV, GROQ_MODEL, env_value

load_dotenv()

# ==============================================================================
# LAYER TRACES — affichées à l'utilisateur après routing
# ==============================================================================

LAYER_TRACES: dict[str, list[str]] = {
    "qa": [
        "🔄 Query Rewriter (LLM)",
        "🔍 FAISS Semantic Search",
        "📚 SQLite Dictionary Lookup",
        "💬 Answer Generation (Groq LLM)",
    ],
    "translate": [
        "🔤 spaCy NLP Parser (déterministe)",
        "⚙️  Morphology Engine — formes Quenya (déterministe)",
        "🧩 SOV Syntax Assembler (déterministe)",
        "✨ LLM Polish — optionnel (Groq)",
    ],
    "lore": [
        "📍 Context Extractor (Regex/Keyword)",
        "🔍 FAISS Retrieval — chunks pertinents",
        "📋 Constraint Builder (Algo)",
        "📖 Story Generation (Claude LLM)",
        "🗂️  KG Validator (déterministe — SQLite)",
    ],
}

ROUTE_LABELS: dict[str, str] = {
    "qa":        "Phase 1 — Q&A",
    "translate": "Phase 2 — Traduction Quenya",
    "lore":      "Phase 3 — Génération de Lore",
}

# ==============================================================================
# RÈGLES DÉTERMINISTES (fast path)
# ==============================================================================

# Mots-clés Q&A — ont priorité sur les autres si présents
_QA_PRIORITY_KEYWORDS = [
    "how does", "how do the", "how do elves", "what is the grammar",
    "explain", "tell me about", "who is", "who are", "what are",
    "when did", "where is", "why did", "what does", "what do",
    "comment fonctionne", "explique", "qu'est-ce",
]

_TRANSLATE_KEYWORDS = [
    "translate", "translation",
    "how do you say", "how to say",
    "quenya for", "sindarin for",
    "word for", "say in elvish",
    "in quenya:", "in sindarin:",   # colon = translation request
    # français
    "traduis", "traduction", "traduire",
    "comment dit-on", "comment dire",
    "en quenya:", "en sindarin:",
]

_LORE_KEYWORDS = [
    "invent", "create a", "imagine", "generate", "make up",
    "write a story", "write lore", "what if there was", "what if there were",
    "a new tribe", "a tribe of", "a kingdom of", "a clan of",
    "an elf ", "a dwarf ", "a hobbit ",
    # français
    "invente", "créé une", "crée une", "génère", "imagine",
    "écris", "une tribu", "un royaume", "une histoire",
]


def _fast_classify(text: str) -> Optional[str]:
    """Keyword-based classifier. Returns route or None if ambiguous."""
    t = text.lower()

    # Q&A priority check — these patterns override translate/lore keywords
    for kw in _QA_PRIORITY_KEYWORDS:
        if kw in t:
            return "qa"

    for kw in _TRANSLATE_KEYWORDS:
        if kw in t:
            return "translate"

    for kw in _LORE_KEYWORDS:
        if kw in t:
            return "lore"

    return None  # ambiguous → needs LLM


# ==============================================================================
# LLM FALLBACK (Groq)
# ==============================================================================

_ROUTER_PROMPT = """\
You are a request classifier for a Tolkien Elvish language app.

Classify the user request into ONE category:
- "qa"        : questions about Tolkien lore, Elvish languages, grammar, vocabulary, history, characters
- "translate" : requests to translate English words or sentences into Quenya or Sindarin
- "lore"      : requests to INVENT or GENERATE new stories, tribes, kingdoms, characters within Tolkien's universe

User request: "{request}"

Reply with ONLY valid JSON and nothing else:
{{"route": "qa" or "translate" or "lore", "reason": "one short sentence"}}\
"""


def _llm_classify(text: str, api_key: str) -> dict:
    """Groq LLM classification for ambiguous requests."""
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": _ROUTER_PROMPT.format(request=text)}],
            max_tokens=80,
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        result["method"] = "llm"
        return result
    except Exception as e:
        # If LLM fails for any reason, default to Q&A
        return {"route": "qa", "reason": f"LLM fallback failed ({e}) — defaulting to Q&A", "method": "rules"}


# ==============================================================================
# PUBLIC API
# ==============================================================================

def classify_request(user_input: str, api_key: Optional[str] = None) -> dict:
    """Analyse la requête et retourne la route appropriée.

    Args:
        user_input : texte libre de l'utilisateur
        api_key    : clé Groq (optionnel — utilisée uniquement si la classification
                     par mots-clés est ambiguë)

    Returns:
        {
            "route"  : "qa" | "translate" | "lore",
            "reason" : str,
            "method" : "rules" | "llm",
            "layers" : list[str],
            "label"  : str,
        }
    """
    groq_key = api_key or env_value(GROQ_API_KEY_ENV)

    # 1. Fast path
    fast_route = _fast_classify(user_input)
    if fast_route:
        result = {
            "route":  fast_route,
            "reason": "Keyword detection",
            "method": "rules",
        }
    else:
        # 2. LLM fallback
        if groq_key:
            result = _llm_classify(user_input, groq_key)
        else:
            result = {"route": "qa", "reason": "No API key — defaulting to Q&A", "method": "rules"}

    result["layers"] = LAYER_TRACES[result["route"]]
    result["label"]  = ROUTE_LABELS[result["route"]]
    return result
