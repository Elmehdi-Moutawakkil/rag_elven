"""Appel au fournisseur LLM configuré avec contexte RAG enrichi.

Le LLM (Large Language Model) reçoit :
    - le contexte récupéré par le retrieval (chunks FAISS + entrées SQLite)
    - la question de l'utilisateur

Il génère une réponse en se basant uniquement sur ce contexte.

Pipeline :
    résultats retrieval
        ↓ build_prompt()   → assemble contexte + question en un seul texte
        ↓ call_llm()       → envoie au fournisseur configuré, reçoit la réponse
    réponse finale
"""

from typing import Optional

from src.llm_provider import LLMRequest, provider_from_name
from src.settings import QA_PROVIDER

# ---------------------------------------------------------------------------
# Configuration du modèle
# ---------------------------------------------------------------------------

MAX_TOKENS  = 1024                    # longueur maximale de la réponse (en tokens ≈ mots)
TEMPERATURE = 0.2                     # 0 = très factuel/répétable, 1 = créatif/aléatoire


# ---------------------------------------------------------------------------
# Construction du prompt
# ---------------------------------------------------------------------------

def build_prompt(
    question: str,
    faiss_results: list[dict],
    dict_results: list[dict],
    universe_name: str = "Tolkien's Middle-earth and Elvish languages",
) -> str:
    """Assemble le prompt envoyé au LLM.

    Un prompt RAG = instructions système + contexte récupéré + question.
    Le LLM doit répondre en se basant UNIQUEMENT sur le contexte fourni.

    Args:
        question     : question de l'utilisateur
        faiss_results: chunks cours/lore récupérés par FAISS
        dict_results : entrées de dictionnaire récupérées par SQLite
        universe_name: univers ou corpus à utiliser pour cadrer la réponse

    Returns:
        prompt complet sous forme de string
    """
    parts = []  # on construit le contexte section par section

    # --- section dictionnaire ---
    if dict_results:
        parts.append("=== Dictionary entries ===")
        for entry in dict_results[:5]:  # on limite à 5 entrées pour ne pas surcharger le prompt
            word        = entry.get("word", "")
            lang        = entry.get("language", "")
            translation = entry.get("translation", "")
            pos         = entry.get("part_of_speech", "")
            parts.append(f"- {word} ({lang}, {pos}): {translation}")

    # --- section cours/lore ---
    if faiss_results:
        parts.append("\n=== Relevant passages ===")
        for r in faiss_results[:3]:   # on limite à 3 chunks
            source = (r.get("source") or r.get("source_path") or "").split("/")[-1]  # garde uniquement le nom du fichier
            text   = r.get("text", "").strip()
            parts.append(f"[{source}]\n{text}")

    context = "\n".join(parts)  # assemble toutes les sections en un seul bloc de texte

    # --- prompt final ---
    # Les triple quotes """ permettent d'écrire sur plusieurs lignes
    prompt = f"""You are a lore and language assistant for this corpus: {universe_name}.
Answer the question using the context provided below as your primary source.
If the context is insufficient, say what is missing instead of switching to another fictional universe.
Never apologize because the corpus is not Tolkien; use the selected corpus and its sources.
Be precise and concise.
IMPORTANT: Always answer in the same language as the question (if the question is in French, answer in French; if in English, answer in English).

--- CONTEXT ---
{context}
--- END CONTEXT ---

Question: {question}
Answer:"""

    return prompt


# ---------------------------------------------------------------------------
# Appel au LLM
# ---------------------------------------------------------------------------

def call_llm(
    prompt: str,
    api_key: Optional[str] = None,
    provider_name: str | None = None,
) -> str:
    """Envoie le prompt au fournisseur choisi et retourne sa réponse.

    Args:
        prompt  : prompt complet avec contexte + question
        api_key      : clé explicite, sinon le provider lit sa variable d'environnement
        provider_name: fournisseur explicite, sinon QA_PROVIDER (DeepSeek par défaut)

    Returns:
        texte brut de la réponse du LLM
    """
    selected_provider = (provider_name or QA_PROVIDER).strip().lower()
    provider = provider_from_name(selected_provider, api_key=api_key)
    response = provider.generate(
        LLMRequest(
            prompt=prompt,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        )
    )
    return response.text


# ---------------------------------------------------------------------------
# Pipeline complète : question → réponse
# ---------------------------------------------------------------------------

def answer(
    question: str,
    faiss_results: list[dict],
    dict_results: list[dict],
    api_key: Optional[str] = None,
    universe_name: str = "Tolkien's Middle-earth and Elvish languages",
) -> str:
    """Construit le prompt et appelle le LLM. Retourne la réponse finale en texte."""
    prompt   = build_prompt(question, faiss_results, dict_results, universe_name=universe_name)  # assemble le contexte + question
    response = call_llm(prompt, api_key=api_key)
    return response


# ---------------------------------------------------------------------------
# Test rapide
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from src.embeddings import load_model
    from src.retrieval  import load_faiss, retrieve

    print("Chargement des ressources...")
    model            = load_model()
    index, metadata  = load_faiss()

    test_questions = [
        "How does the plural work in Quenya?",  # grammaire
        "Who are the Noldor?",                  # lore
        "What does elda mean?",                 # vocabulaire
    ]

    for question in test_questions:
        print(f"\nQuestion : {question}")
        results  = retrieve(question, model, index, metadata, k=3)
        response = answer(question, results["faiss"], results["dictionary"])
        print(f"Réponse  : {response}")
        print("-" * 60)
