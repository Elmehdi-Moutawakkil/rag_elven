"""Layer Registry — Inventaire des layers atomiques du pipeline RAG Elfique.

Chaque layer est une unité indépendante avec une interface standardisée :
    run(input, context) -> LayerResult

Le context contient :
    context["user_input"]         — requête brute de l'utilisateur
    context["outputs"]            — dict {layer_id: LayerResult} de toutes les layers déjà exécutées
    context["resources"]["model"] — modèle SentenceTransformer (chargé une fois)
    context["resources"]["index"] — index FAISS
    context["resources"]["meta"]  — metadata FAISS
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()


# ==============================================================================
# Types de données
# ==============================================================================

@dataclass
class LayerResult:
    output: Any
    output_type: str
    label: str  # description lisible de ce qui s'est passé (pour la trace)


@dataclass
class LayerMeta:
    id: str
    name: str
    emoji: str
    description: str         # une phrase : ce que la layer fait concrètement
    input_types: list[str]   # types acceptés en entrée (vide = accepte tout)
    output_type: str
    cost: str                # "free" | "groq" | "claude"
    deterministic: bool
    available: bool = True   # False = phase future, layer non implémentée


# ==============================================================================
# Métadonnées de l'inventaire — 13 layers
# ==============================================================================

LAYER_META: dict[str, LayerMeta] = {
    "L01": LayerMeta(
        id="L01", name="Query Rewriter", emoji="🔄",
        description="Envoie la requête brute à un LLM qui en extrait le mot-clé en anglais et détecte si c'est une question de vocabulaire ou de lore.",
        input_types=["text"], output_type="json_rewrite",
        cost="groq", deterministic=False,
    ),
    "L02": LayerMeta(
        id="L02", name="FAISS Semantic Search", emoji="🔍",
        description="Transforme la requête en vecteur et cherche les 5 passages les plus proches sémantiquement dans les 1 512 chunks du corpus Tolkien.",
        input_types=["text", "json_rewrite"], output_type="json_chunks",
        cost="free", deterministic=True,
    ),
    "L03": LayerMeta(
        id="L03", name="SQLite Dictionary", emoji="📚",
        description="Cherche le mot dans les 8 022 entrées du dictionnaire elfique (Quenya + Sindarin) et retourne définition, catégorie grammaticale et exemples.",
        input_types=["text", "json_rewrite"], output_type="json_dict",
        cost="free", deterministic=True,
    ),
    "L04": LayerMeta(
        id="L04", name="spaCy NLP Parser", emoji="🌿",
        description="Analyse grammaticalement la phrase anglaise avec spaCy et construit une représentation structurée (sujet, verbe, compléments, temps, mode).",
        input_types=["text"], output_type="semantic_ir",
        cost="free", deterministic=True,
    ),
    "L05": LayerMeta(
        id="L05", name="Morphology Engine", emoji="⚙️",
        description="Applique plus de 80 règles déterministes pour décliner les noms et conjuguer les verbes en Quenya selon la classe de radical (voyelle, consonne, etc.).",
        input_types=["semantic_ir"], output_type="morph_forms",
        cost="free", deterministic=True,
    ),
    "L06": LayerMeta(
        id="L06", name="SOV Syntax Assembler", emoji="🧩",
        description="Prend les formes morphologiques calculées et les assemble dans l'ordre Sujet-Objet-Verbe du Quenya, en ajoutant les particules et marqueurs de cas.",
        input_types=["morph_forms"], output_type="syntax_result",
        cost="free", deterministic=True,
    ),
    "L07": LayerMeta(
        id="L07", name="Constraint Builder", emoji="📐",
        description="Lit les chunks FAISS récupérés et en extrait les faits établis du canon Tolkien qui devront être respectés lors de la génération de lore.",
        input_types=["json_chunks"], output_type="text_constraints",
        cost="free", deterministic=True,
    ),
    "L08": LayerMeta(
        id="L08", name="Story Generation", emoji="✨",
        description="Envoie à Claude (Anthropic) le contexte et les contraintes canon pour générer une histoire ou un lore inédit mais cohérent avec l'univers Tolkien.",
        input_types=["text_constraints", "text"], output_type="json_story",
        cost="claude", deterministic=False,
    ),
    "L09": LayerMeta(
        id="L09", name="KG Validator", emoji="🛡️",
        description="Vérifie la cohérence du lore généré contre un graphe de connaissances SQLite (126 entités, 131 relations, 12 règles canon) et signale les contradictions.",
        input_types=["json_story", "text"], output_type="json_story",
        cost="free", deterministic=True,
    ),
    "L10": LayerMeta(
        id="L10", name="CLIP Image Search", emoji="🖼️",
        description="Encode la requête avec CLIP et retrouve les images les plus proches sémantiquement dans un index visuel (illustrations Tolkien).",
        input_types=["text"], output_type="json_images",
        cost="free", deterministic=True, available=False,
    ),
    "L11": LayerMeta(
        id="L11", name="Image Generator", emoji="🎨",
        description="Génère une illustration de scène ou de personnage elfique via Stable Diffusion à partir d'un prompt textuel.",
        input_types=["text"], output_type="image",
        cost="gpu", deterministic=False, available=False,
    ),
    "L12": LayerMeta(
        id="L12", name="TTS Quenya", emoji="🔊",
        description="Synthétise la prononciation elfique d'un texte Quenya en audio (Text-To-Speech adapté aux phonèmes elfiques).",
        input_types=["text", "syntax_result"], output_type="audio",
        cost="free", deterministic=True, available=False,
    ),
    "L13": LayerMeta(
        id="L13", name="Answer LLM", emoji="💬",
        description="Prend le contexte FAISS et les entrées de dictionnaire récupérés et les soumet à Groq (llama-3.1-8b) pour synthétiser une réponse finale en langage naturel.",
        input_types=["json_chunks", "json_dict", "text"], output_type="text",
        cost="groq", deterministic=False,
    ),
}

# Ordre logique des layers dans l'inventaire (pour l'UI) — toutes les 13 layers
LAYER_ORDER = ["L01", "L02", "L03", "L04", "L05", "L06", "L07", "L08", "L09", "L10", "L11", "L12", "L13"]


# ==============================================================================
# Implémentations des layers
# ==============================================================================

def _run_L01(input: Any, context: dict) -> LayerResult:
    from src.query_rewriter import rewrite_query
    query = context["user_input"]
    result = rewrite_query(query)
    label = f"keyword={result.get('keyword', '?')} · type={result.get('type', '?')}"
    return LayerResult(output=result, output_type="json_rewrite", label=label)


def _run_L02(input: Any, context: dict) -> LayerResult:
    from src.retrieval import search_faiss
    resources = context.get("resources", {})
    model = resources.get("model")
    index = resources.get("index")
    meta  = resources.get("meta")
    if model is None or index is None:
        return LayerResult(output=[], output_type="json_chunks", label="FAISS non disponible")

    # Construire la query : utilise le keyword normalisé si L01 a tourné
    prev_L01 = context["outputs"].get("L01")
    if prev_L01 and prev_L01.output_type == "json_rewrite":
        query = prev_L01.output.get("keyword", context["user_input"])
    elif isinstance(input, dict) and "keyword" in input:
        query = input["keyword"]
    else:
        query = context["user_input"]

    chunks = search_faiss(query, model, index, meta, k=5)
    return LayerResult(output=chunks, output_type="json_chunks", label=f"{len(chunks)} chunks trouvés")


def _run_L03(input: Any, context: dict) -> LayerResult:
    from src.retrieval import search_dictionary
    prev_L01 = context["outputs"].get("L01")
    if prev_L01 and prev_L01.output_type == "json_rewrite":
        query = prev_L01.output.get("keyword", context["user_input"])
    else:
        query = context["user_input"]
    entries = search_dictionary(query)
    return LayerResult(output=entries, output_type="json_dict", label=f"{len(entries)} entrées dictionnaire")


def _run_L04(input: Any, context: dict) -> LayerResult:
    from src.ir import parse_english
    sentence = context["user_input"]
    ir = parse_english(sentence)
    label = f"prédicat={ir.predicate.lemma if ir.predicate else '?'} · {len(ir.arguments)} arguments"
    return LayerResult(output=ir, output_type="semantic_ir", label=label)


def _run_L05(input: Any, context: dict) -> LayerResult:
    from src.translator import compute_all_forms
    prev_L04 = context["outputs"].get("L04")
    if prev_L04 and prev_L04.output_type == "semantic_ir":
        ir = prev_L04.output
    elif hasattr(input, "predicate"):
        ir = input
    else:
        return LayerResult(output=[], output_type="morph_forms", label="Erreur : L04 requis avant L05")
    forms = compute_all_forms(ir)
    return LayerResult(output=forms, output_type="morph_forms", label=f"{len(forms)} formes morphologiques")


def _run_L06(input: Any, context: dict) -> LayerResult:
    from src.syntax import realize_syntax
    prev_L04 = context["outputs"].get("L04")
    prev_L05 = context["outputs"].get("L05")
    if not prev_L04 or not prev_L05:
        return LayerResult(output=None, output_type="syntax_result", label="Erreur : L04 + L05 requis avant L06")
    ir    = prev_L04.output
    forms = prev_L05.output
    result = realize_syntax(ir, forms)
    label = f"Quenya : {result.quenya_sentence}"
    return LayerResult(output=result, output_type="syntax_result", label=label)


def _run_L07(input: Any, context: dict) -> LayerResult:
    from src.lore_generator import build_constraints_from_chunks
    prev_L02 = context["outputs"].get("L02")
    if prev_L02 and prev_L02.output_type == "json_chunks":
        chunks = prev_L02.output
    elif isinstance(input, list):
        chunks = input
    else:
        chunks = []
    constraints = build_constraints_from_chunks(chunks)
    return LayerResult(output=constraints, output_type="text_constraints", label=f"{len(chunks)} chunks → contraintes extraites")


def _run_L08(input: Any, context: dict) -> LayerResult:
    from anthropic import Anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return LayerResult(
            output={"story": "[ANTHROPIC_API_KEY manquante]", "warnings": []},
            output_type="json_story",
            label="Clé API Claude manquante",
        )

    # Universe comes from resources (set by Lab Mode selector or defaults to Tolkien)
    universe = context["resources"].get("universe", "Tolkien's Middle-earth")

    user_request = context["user_input"]

    # Constraints from L07 if available, else from raw chunks
    prev_L07 = context["outputs"].get("L07")
    constraints = prev_L07.output if (prev_L07 and prev_L07.output_type == "text_constraints") else ""

    prev_L02 = context["outputs"].get("L02")
    chunks = prev_L02.output if (prev_L02 and prev_L02.output_type == "json_chunks") else []
    context_text = "\n\n".join(c["text"] for c in chunks[:4])

    prompt = f"""You are a creative lore writer for the {universe} universe.

Using the canon excerpts below as your foundation, generate an original story or lore piece
that fits seamlessly within this universe. Respect its tone, terminology, and established facts.

CANON CONTEXT:
{context_text}

{"CONSTRAINTS FROM CORPUS:" + chr(10) + constraints if constraints else ""}

USER REQUEST:
{user_request}

Write the lore now, staying true to the {universe} universe."""

    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    story = message.content[0].text
    return LayerResult(output={"story": story, "warnings": []}, output_type="json_story", label="Lore généré par Claude")


def _run_L09(input: Any, context: dict) -> LayerResult:
    from src.lore_generator import validate_coherence
    prev_L02 = context["outputs"].get("L02")
    chunks = prev_L02.output if (prev_L02 and prev_L02.output_type == "json_chunks") else []

    if isinstance(input, dict) and "story" in input:
        story_data = input
    elif isinstance(context["outputs"].get("L08"), object):
        prev = context["outputs"].get("L08")
        story_data = prev.output if prev and prev.output_type == "json_story" else {"story": str(input), "warnings": []}
    else:
        story_data = {"story": str(input), "warnings": []}

    chunks_text = "\n\n".join([c["text"] for c in chunks[:3]])
    api_key = context["resources"].get("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY", "")
    warnings = validate_coherence(story_data["story"], chunks_text, api_key)
    story_data = dict(story_data)
    story_data["warnings"] = warnings if isinstance(warnings, list) else []
    label = f"{'⚠️ ' + str(len(story_data['warnings'])) + ' avertissements' if story_data['warnings'] else '✅ cohérent'}"
    return LayerResult(output=story_data, output_type="json_story", label=label)


def _run_L13(input: Any, context: dict) -> LayerResult:
    from src.llm import answer
    question = context["user_input"]

    prev_L02 = context["outputs"].get("L02")
    prev_L03 = context["outputs"].get("L03")
    faiss_results = prev_L02.output if (prev_L02 and prev_L02.output_type == "json_chunks") else []
    dict_results  = prev_L03.output if (prev_L03 and prev_L03.output_type == "json_dict") else []

    response = answer(question, faiss_results, dict_results)
    return LayerResult(output=response, output_type="text", label="Réponse Groq générée")


# ==============================================================================
# Registre des runners
# ==============================================================================

LAYER_RUNNERS: dict[str, Any] = {
    "L01": _run_L01,
    "L02": _run_L02,
    "L03": _run_L03,
    "L04": _run_L04,
    "L05": _run_L05,
    "L06": _run_L06,
    "L07": _run_L07,
    "L08": _run_L08,
    "L09": _run_L09,
    "L13": _run_L13,
}
