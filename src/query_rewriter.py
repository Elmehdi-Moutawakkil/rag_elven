"""Query Rewriter — première couche d'intelligence du RAG.

C'est le premier composant "agent" du système.

Problème sans ce module :
    L'utilisateur pose une question dans n'importe quelle langue, avec
    n'importe quelle formulation. Des règles regex codées en dur ne peuvent
    pas couvrir tous les cas : "c'est quoi le mot pour dire forêt ?",
    "how do I say walk in Quenya?", "keskeä tarkoittaa elda?" (finnois)...

Solution — déléguer l'analyse à un LLM :
    Au lieu de regex, on envoie la question brute à un LLM avec un prompt
    très ciblé. Le LLM retourne un JSON structuré :
        {
          "keyword": "forest",      ← mot-clé traduit en anglais
          "type":    "vocabulary"   ← ou "lore" selon l'intention
        }

    Le reste du pipeline utilise ce JSON pour décider quoi chercher et où.

Pourquoi c'est "agent" ?
    Un agent = un LLM qui prend des décisions sur les actions à faire.
    Ici le LLM ne génère pas une réponse finale — il analyse l'intention
    et choisit la stratégie de recherche. C'est une micro-décision autonome.

Pipeline :
    question (texte libre, n'importe quelle langue)
        ↓ rewrite_query()
    {keyword: str, type: "vocabulary" | "lore"}
        ↓ retrieval.py
    résultats SQLite ou FAISS selon le type
"""

import json                                # pour parser la réponse JSON du LLM
from typing import Optional

from dotenv import load_dotenv             # charge le fichier .env local
from groq import Groq                      # client Groq pour appeler le LLM
from src.settings import GROQ_API_KEY_ENV, GROQ_MODEL, env_value

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL       = GROQ_MODEL              # même modèle que le reste du projet
TEMPERATURE = 0.0   # 0 = déterministe : on veut toujours la même analyse pour la même question
MAX_TOKENS  = 80    # la réponse est un petit JSON, inutile d'allouer plus

# ---------------------------------------------------------------------------
# Prompt système du rewriter
# ---------------------------------------------------------------------------

# Ce prompt est la "carte de mission" du LLM-agent.
# Il définit exactement ce qu'on attend : un JSON avec deux champs,
# rien d'autre. Les exemples (few-shot) guident fortement le comportement.
_SYSTEM_PROMPT = """You are a query analyzer for a multi-universe RAG system with optional Elvish language support.

Given a user question in ANY language, return a JSON object with exactly two fields:
- "keyword": the word or concept to look up, always in English
  - vocabulary question → just the single word (e.g. "forest", "walk", "star", "eat")
  - lore/grammar question → a short English phrase (e.g. "plural form Quenya", "Noldor history", "Mirror Spock")
- "type": either "vocabulary" (user wants an Elvish word/definition) or "lore" (grammar, history, culture, characters, events, technologies)

Examples:
{"question": "c'est quoi le mot pour dire forêt?", "output": {"keyword": "forest", "type": "vocabulary"}}
{"question": "c'est quoi manger en elfique?",      "output": {"keyword": "eat",    "type": "vocabulary"}}
{"question": "que signifie elda?",                 "output": {"keyword": "elda",   "type": "vocabulary"}}
{"question": "what does elen mean?",               "output": {"keyword": "elen",   "type": "vocabulary"}}
{"question": "how does the plural work in Quenya?","output": {"keyword": "plural Quenya", "type": "lore"}}
{"question": "qui sont les Noldor?",               "output": {"keyword": "Noldor history", "type": "lore"}}
{"question": "comment se conjugue le verbe en Quenya?", "output": {"keyword": "verb conjugation Quenya", "type": "lore"}}
{"question": "c'est quoi anda?",                   "output": {"keyword": "anda",   "type": "vocabulary"}}
{"question": "Who is Mirror Spock?",               "output": {"keyword": "Mirror Spock", "type": "lore"}}
{"question": "Explique Terok Nor dans Star Trek",  "output": {"keyword": "Terok Nor Star Trek", "type": "lore"}}

Rules:
- ALWAYS translate the keyword to English, even if the question is in French or another language
- Use "vocabulary" only for explicit Quenya/Sindarin/Elvish word or definition lookups
- Use "lore" for Star Trek, Terran Empire, Tolkien history, characters, events, places, grammar, and general corpus questions
- If the user asks for a word in Elvish, extract the concept in English (e.g. "forêt" → "forest")
- If the user uses an Elvish word directly, keep it as-is (e.g. "elda", "anda")
- Respond ONLY with valid JSON. No explanation, no markdown, no code block."""

# ---------------------------------------------------------------------------
# Fallback regex local
# ---------------------------------------------------------------------------

def _regex_extract(query: str) -> str:
    """Minimal no-API keyword extraction used when Groq is unavailable."""
    patterns = [
        r"what does (.+?) mean",
        r"what is (.+?)\??$",
        r"translate (.+)",
        r"definition of (.+)",
        r"meaning of (.+)",
        r"c'est quoi (.+?)\??$",
        r"qu(?:e|')est[-\s]ce que (.+?)\??$",
        r"que signifie (.+?)\??$",
        r"(?:définis?|définition de) (.+)",
        r"traduis? (.+)",
        r"signification de (.+?)\??$",
    ]
    import re
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip("?").strip()
    return query


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def rewrite_query(question: str, api_key: Optional[str] = None) -> dict:
    """Analyse la question et retourne le mot-clé normalisé + le type de requête.

    Envoie la question à un LLM qui décide :
        - quel mot chercher (traduit en anglais)
        - si c'est une question de vocabulaire ou de lore/grammaire

    En cas d'erreur (API indisponible, JSON invalide...), retourne un fallback
    basé sur les anciens patterns regex pour ne pas bloquer le pipeline.

    Args:
        question : question brute de l'utilisateur (n'importe quelle langue)
        api_key  : clé Groq optionnelle (sinon lue depuis GROQ_API_KEY)

    Returns:
        dict avec :
            "keyword" (str)  : mot ou phrase à rechercher, en anglais
            "type"    (str)  : "vocabulary" ou "lore"

    Exemples :
        rewrite_query("c'est quoi le mot pour dire forêt?")
        → {"keyword": "forest", "type": "vocabulary"}

        rewrite_query("qui sont les Noldor?")
        → {"keyword": "Noldor history", "type": "lore"}
    """
    key = api_key or env_value(GROQ_API_KEY_ENV)
    if not key:
        # Pas de clé API → fallback immédiat sans appel réseau
        return _safe_fallback(question)

    try:
        client = Groq(api_key=key)

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},  # instructions de l'agent
                {"role": "user",   "content": question},         # question brute
            ],
            temperature=TEMPERATURE,  # 0 = réponse stable et reproductible
            max_tokens=MAX_TOKENS,    # JSON court attendu
        )

        raw = response.choices[0].message.content.strip()   # texte brut de la réponse
        result = json.loads(raw)                             # parse le JSON

        # Validation minimale : les deux champs doivent être présents
        if "keyword" not in result or "type" not in result:
            return _safe_fallback(question)

        # Normalisation : "type" doit être "vocabulary" ou "lore" uniquement
        if result["type"] not in ("vocabulary", "lore"):
            result["type"] = "lore"   # valeur par défaut si le LLM hallucine un autre type

        return result

    except json.JSONDecodeError:
        # Le LLM n'a pas retourné un JSON valide (ça arrive rarement avec TEMPERATURE=0)
        return _safe_fallback(question)

    except Exception:
        # Toute autre erreur (réseau, quota Groq, etc.) → fallback silencieux
        return _safe_fallback(question)


def _safe_fallback(question: str) -> dict:
    """Fallback regex quand le LLM est inaccessible.

    Réutilise l'ancien système extract_keyword() pour rester fonctionnel
    même sans appel API. Si aucun pattern regex ne matche, traite la
    question comme une requête lore (recherche sémantique FAISS).

    Args:
        question : question brute de l'utilisateur

    Returns:
        dict avec "keyword" et "type"
    """
    keyword = _regex_extract(question)   # tente l'extraction par regex
    # Si le keyword est identique à la question → aucun pattern n'a matché → lore
    query_type = "vocabulary" if keyword != question else "lore"
    return {"keyword": keyword, "type": query_type}
