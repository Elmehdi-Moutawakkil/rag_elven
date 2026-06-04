"""Retrieval hybride : FAISS pour le cours/lore, SQLite pour le vocabulaire.

Avec Query Rewriter (query_rewriter.py), le pipeline devient :

    question brute
        ↓ [AGENT] rewrite_query()  → {keyword: "forest", type: "vocabulary"}
        ↓
    Si type == "vocabulary" → SQLite (lookup_word + search_translation)
    Si type == "lore"       → FAISS uniquement (recherche sémantique)
    Toujours                → FAISS en parallèle pour le contexte

Le rewriter est la première couche d'intelligence agentique du système :
au lieu de règles codées en dur, un LLM décide de la stratégie de recherche.
"""

import json
import re                                             # expressions régulières
from pathlib import Path
from typing import Optional

import faiss                                          # moteur de recherche vectorielle
import numpy as np
from sentence_transformers import SentenceTransformer

from src.database import lookup_word, search_translation  # fonctions de recherche SQLite
from src.query_rewriter import rewrite_query               # agent d'analyse de la question

# ---------------------------------------------------------------------------
# Chemins vers les fichiers générés par embeddings.py
# ---------------------------------------------------------------------------

INDEX_PATH = Path("vector_db/faiss.index")    # index FAISS binaire
META_PATH  = Path("vector_db/metadata.json")  # metadata JSON parallèles à l'index

# ---------------------------------------------------------------------------
# Extraction du mot-clé depuis une question de vocabulaire
# ---------------------------------------------------------------------------

# Liste de patterns pour reconnaître les questions de vocabulaire
# et en extraire le mot cherché (anglais ET français)
_VOCAB_PATTERNS = [
    # --- Anglais ---
    re.compile(r"what does (.+?) mean",  re.IGNORECASE),  # "what does elda mean?"
    re.compile(r"what is (.+?)\??$",     re.IGNORECASE),  # "what is elda?"
    re.compile(r"translate (.+)",        re.IGNORECASE),  # "translate elda"
    re.compile(r"definition of (.+)",    re.IGNORECASE),  # "definition of elda"
    re.compile(r"meaning of (.+)",       re.IGNORECASE),  # "meaning of elda"
    # --- Français ---
    re.compile(r"c'est quoi (.+?)\??$",              re.IGNORECASE),  # "c'est quoi anda?"
    re.compile(r"qu(?:e|')est[-\s]ce que (.+?)\??$", re.IGNORECASE),  # "qu'est-ce que anda?"
    re.compile(r"que signifie (.+?)\??$",             re.IGNORECASE),  # "que signifie anda?"
    re.compile(r"(?:définis?|définition de) (.+)",    re.IGNORECASE),  # "définition de anda"
    re.compile(r"traduis? (.+)",                      re.IGNORECASE),  # "traduis anda"
    re.compile(r"signification de (.+?)\??$",         re.IGNORECASE),  # "signification de anda"
]


def extract_keyword(query: str) -> str:
    """Extrait le mot-clé d'une question de vocabulaire.

    Si la question correspond à un pattern connu, retourne uniquement le terme cherché.
    Sinon retourne la question entière (pour la recherche sur les traductions).

    Exemples :
        "what does anqualë mean?" → "anqualë"
        "who are the Noldor?"    → "who are the Noldor?" (inchangé, pas un pattern vocabulaire)
    """
    for pattern in _VOCAB_PATTERNS:       # on teste chaque pattern l'un après l'autre
        m = pattern.search(query)         # cherche le pattern dans la question
        if m:                             # si un pattern correspond
            return m.group(1).strip().rstrip("?").strip()  # retourne le groupe capturé (le mot entre parenthèses)
    return query  # aucun pattern reconnu → on retourne la question brute

# ---------------------------------------------------------------------------
# Chargement des ressources
# ---------------------------------------------------------------------------

def load_faiss(
    index_path: str = str(INDEX_PATH),
    meta_path:  str = str(META_PATH),
) -> tuple[faiss.Index, list[dict]]:
    """Charge l'index FAISS et les metadata depuis le disque."""
    index    = faiss.read_index(index_path)              # charge l'index vectoriel binaire
    metadata = json.loads(Path(meta_path).read_text())   # charge la liste de dicts JSON
    return index, metadata


def load_model(model_name: str = "all-MiniLM-L6-v2") -> SentenceTransformer:
    """Charge le modèle d'embeddings (depuis le cache local après la première fois)."""
    return SentenceTransformer(model_name)

# ---------------------------------------------------------------------------
# Recherche FAISS (sémantique)
# ---------------------------------------------------------------------------

def search_faiss(
    query: str,
    model: SentenceTransformer,
    index: faiss.Index,
    metadata: list[dict],
    k: int = 5,  # nombre de résultats à retourner
) -> list[dict]:
    """Trouve les k chunks dont le sens est le plus proche de la question.

    Principe : on transforme la question en vecteur, puis FAISS cherche
    les k vecteurs les plus proches dans l'index.

    Args:
        query    : question de l'utilisateur en texte libre
        model    : modèle d'embeddings pour vectoriser la question
        index    : index FAISS chargé (contient tous les vecteurs des chunks)
        metadata : liste parallèle à l'index avec les textes et infos de chaque chunk
        k        : combien de résultats retourner

    Returns:
        liste de dicts avec 'text', 'source', 'page', 'score'
        (score = distance L2 : plus petit = plus proche = plus pertinent)
    """
    # 1. transforme la question en vecteur (même espace mathématique que les chunks)
    query_vector = model.encode(
        [query],                      # encode attend une liste, même pour une seule question
        normalize_embeddings=True,    # normalisation cohérente avec les chunks
    ).astype("float32")               # float32 requis par FAISS

    # 2. cherche les k vecteurs les plus proches dans l'index
    distances, indices = index.search(query_vector, k)
    # distances : tableau des distances (plus petit = plus proche)
    # indices   : tableau des positions dans l'index correspondantes

    results = []
    for dist, idx in zip(distances[0], indices[0]):  # on itère sur les k résultats
        if idx == -1:              # FAISS retourne -1 si pas assez de résultats
            continue
        entry = metadata[idx]      # récupère les infos du chunk à cette position
        results.append({
            "text":   entry.get("text", ""),
            "source": entry.get("source", ""),
            "page":   entry.get("page"),
            "score":  float(dist),  # on conserve le score pour l'afficher dans l'interface
        })
    return results

# ---------------------------------------------------------------------------
# Recherche SQLite (exacte)
# ---------------------------------------------------------------------------

def search_dictionary(
    query: str,
    language: Optional[str] = None,
) -> list[dict]:
    """Cherche dans le dictionnaire SQLite.

    1. Extrait le mot-clé de la question (ex: "what does elda mean?" → "elda")
    2. Recherche exacte sur le mot elfique
    3. Si rien trouvé, recherche sur les traductions

    Args:
        query   : question de l'utilisateur (ou mot directement)
        language: filtre optionnel ('Quenya' ou 'Sindarin')

    Returns:
        liste de dicts avec 'word', 'language', 'translation', etc.
    """
    keyword = extract_keyword(query)        # extrait "elda" depuis "what does elda mean?"

    rows = lookup_word(keyword, language=language)  # cherche le mot exact dans la colonne word

    if not rows:                            # si aucun résultat exact
        rows = search_translation(keyword)  # cherche dans les traductions (ex: cherche "elf" dans la colonne translation)

    return [dict(row) for row in rows]      # convertit les objets sqlite3.Row en dicts Python simples

# ---------------------------------------------------------------------------
# Retrieval combiné
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    model: SentenceTransformer,
    index: faiss.Index,
    metadata: list[dict],
    k: int = 5,
    language: Optional[str] = None,
) -> dict:
    """Point d'entrée principal du retrieval — pipeline agentique.

    Étapes :
        1. [AGENT] rewrite_query() analyse l'intention et normalise le mot-clé
        2. Si vocabulaire → SQLite avec le mot-clé normalisé (en anglais)
        3. FAISS toujours → contexte sémantique complémentaire
        4. Retourne les deux sources combinées pour le LLM

    Args:
        query    : question brute de l'utilisateur (n'importe quelle langue)
        model    : modèle d'embeddings
        index    : index FAISS
        metadata : metadata FAISS
        k        : nombre de chunks FAISS à retourner
        language : filtre langue pour SQLite (optionnel)

    Returns:
        dict avec :
            'faiss'       → chunks cours/lore pertinents
            'dictionary'  → entrées de dictionnaire correspondantes
            'rewriter'    → ce que l'agent a analysé (pour débogage)
    """
    # --- Étape 1 : l'agent analyse la question ---
    # rewrite_query() envoie la question à un LLM qui retourne :
    #   {"keyword": "forest", "type": "vocabulary"}
    # En cas d'erreur API, il bascule automatiquement sur les regex (fallback)
    analysis = rewrite_query(query)
    keyword   = analysis.get("keyword", query)    # mot-clé normalisé en anglais
    query_type = analysis.get("type", "lore")     # "vocabulary" ou "lore"

    # --- Étape 2 : SQLite uniquement si c'est une question de vocabulaire ---
    # Pour une question de lore/grammaire, la recherche SQLite ne sert à rien
    if query_type == "vocabulary":
        # On cherche d'abord le mot elfique exact, puis dans les traductions anglaises
        rows = lookup_word(keyword, language=language)
        if not rows:
            rows = search_translation(keyword)
        dict_results = [dict(row) for row in rows]
    else:
        dict_results = []   # question de lore → pas de recherche dictionnaire

    # --- Étape 3 : FAISS toujours en parallèle ---
    # Pour les questions de lore : on envoie le keyword EN ANGLAIS (extrait par le rewriter)
    # plutôt que la question originale. Raison : all-MiniLM-L6-v2 est un modèle principalement
    # anglais. Une question en français ("C'est quoi Noldor") produit un vecteur qui correspond
    # mieux aux exercices du cours qu'au fichier noldor.txt, même si ce fichier parle directement
    # du sujet. En envoyant "Noldor history" (anglais), le vecteur se rapproche du contenu lore.
    # Pour les questions de vocabulaire : on garde la question originale car FAISS sert à donner
    # du contexte complémentaire, pas à trouver la définition principale (qui vient de SQLite).
    faiss_query   = keyword if query_type == "lore" else query
    faiss_results = search_faiss(faiss_query, model, index, metadata, k=k)

    return {
        "faiss":      faiss_results,    # contexte sémantique (cours, lore)
        "dictionary": dict_results,     # entrées de dictionnaire exactes
        "rewriter":   analysis,         # analyse de l'agent (utile pour déboguer)
    }

# ---------------------------------------------------------------------------
# Test rapide
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Chargement des ressources...")
    model           = load_model()
    index, metadata = load_faiss()
    print(f"Index chargé : {index.ntotal} vecteurs\n")

    # trois types de questions pour couvrir les deux sources
    test_queries = [
        "How does the plural work in Quenya?",  # grammaire → FAISS
        "Who are the Noldor?",                  # lore → FAISS
        "elda",                                 # vocabulaire → SQLite
    ]

    for query in test_queries:
        print(f"Question : {query}")
        results = retrieve(query, model, index, metadata, k=3)

        print("  FAISS (cours/lore) :")
        for r in results["faiss"]:
            print(f"    [{r['score']:.3f}] {r['text'][:100].replace(chr(10), ' ')}...")

        print("  SQLite (dictionnaire) :")
        if results["dictionary"]:
            for r in results["dictionary"][:3]:
                print(f"    {r.get('word')} ({r.get('language')}) → {r.get('translation')}")
        else:
            print("    (aucun résultat)")
        print()
