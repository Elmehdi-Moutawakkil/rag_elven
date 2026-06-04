"""Génération des embeddings et construction de l'index FAISS.

Un embedding = transformer un texte en tableau de nombres qui représente son sens.
FAISS = bibliothèque qui stocke ces tableaux et permet de chercher les plus proches voisins.

Pipeline :
    chunks (texte + metadata)
        ↓ modèle sentence-transformers
    vecteurs numpy (tableaux de 384 nombres)
        ↓ FAISS IndexFlatL2
    index FAISS + metadata JSON  →  sauvegardés dans vector_db/
"""

import json                                          # pour sauvegarder les metadata en JSON
from pathlib import Path                             # manipulation de chemins
from typing import List

import faiss                                         # moteur de recherche vectorielle (Meta)
import numpy as np                                   # tableaux numériques haute performance
from sentence_transformers import SentenceTransformer  # modèle qui transforme texte → vecteur

from src.text_splitter import split_corpus           # fonction qui produit les chunks depuis data/

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_NAME   = "all-MiniLM-L6-v2"              # modèle léger, gratuit, tourne en local (384 dimensions)
VECTOR_DB_DIR = Path("vector_db")              # dossier de stockage de l'index
INDEX_PATH    = VECTOR_DB_DIR / "faiss.index"  # fichier binaire de l'index FAISS
META_PATH     = VECTOR_DB_DIR / "metadata.json"  # fichier JSON avec les textes et metadata parallèles


def load_model(model_name: str = MODEL_NAME) -> SentenceTransformer:
    """Charge le modèle d'embeddings depuis le cache local (ou le télécharge la première fois)."""
    print(f"Chargement du modèle : {model_name}")
    return SentenceTransformer(model_name)  # télécharge le modèle si absent, sinon charge depuis le cache


def encode_chunks(
    chunks: List[dict],
    model: SentenceTransformer,
    batch_size: int = 64,  # nombre de textes envoyés au modèle en même temps (64 = bon compromis vitesse/RAM)
) -> np.ndarray:
    """Transforme les textes des chunks en vecteurs numériques.

    Args:
        chunks    : liste de dicts avec les clés 'text' et 'metadata'
        model     : modèle sentence-transformers chargé
        batch_size: traite les textes par lots pour économiser la mémoire

    Returns:
        tableau numpy de shape (nombre_de_chunks, 384)
        ex: 1500 chunks → tableau de 1500 lignes × 384 colonnes
    """
    texts = [c["text"] for c in chunks]  # on extrait uniquement le texte de chaque chunk

    vectors = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,      # affiche une barre de progression dans le terminal
        normalize_embeddings=True,   # normalise les vecteurs → permet d'utiliser le produit scalaire comme similarité
    )
    return np.array(vectors, dtype="float32")  # FAISS exige le type float32 (nombre décimal 32 bits)


def save_index(vectors: np.ndarray, chunks: List[dict]) -> None:
    """Sauvegarde l'index FAISS et les metadata associées sur le disque."""
    VECTOR_DB_DIR.mkdir(exist_ok=True)  # crée vector_db/ si le dossier n'existe pas

    dimension = vectors.shape[1]  # taille d'un vecteur (384 pour all-MiniLM-L6-v2)

    # IndexFlatL2 = index de recherche par distance euclidienne exacte
    # "Flat" = pas de compression, recherche exhaustive → précise mais adaptée aux petits corpus
    index = faiss.IndexFlatL2(dimension)
    index.add(vectors)                          # ajoute tous les vecteurs en une seule opération
    faiss.write_index(index, str(INDEX_PATH))  # sauvegarde l'index dans un fichier binaire

    # FAISS ne stocke pas les textes ni les metadata → on les sauvegarde en parallèle dans un JSON
    # L'ordre doit être identique : metadata[i] correspond au vecteur i dans l'index
    metadata = [c["metadata"] | {"text": c["text"]} for c in chunks]  # fusionne metadata + texte
    META_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))  # sauvegarde en JSON lisible

    print(f"Index sauvegardé : {index.ntotal} vecteurs → {INDEX_PATH}")
    print(f"Metadata sauvegardées → {META_PATH}")


def load_index() -> tuple[faiss.Index, List[dict]]:
    """Charge l'index FAISS et les metadata depuis le disque (pour le retrieval)."""
    if not INDEX_PATH.exists():
        raise FileNotFoundError(f"Index introuvable : {INDEX_PATH}. Lance d'abord build_vector_store()")

    index    = faiss.read_index(str(INDEX_PATH))     # charge l'index binaire
    metadata = json.loads(META_PATH.read_text())     # charge le JSON des metadata
    return index, metadata


def build_vector_store(data_dir: str = "data") -> None:
    """Pipeline complète : chunks → vecteurs → sauvegarde FAISS."""
    print("[1/3] Génération des chunks...")
    chunks = split_corpus(data_dir)          # découpe tous les documents non-dictionnaires
    print(f"  {len(chunks)} chunks produits")

    if not chunks:
        print("Aucun chunk trouvé, abandon.")
        return

    print("[2/3] Encodage des chunks...")
    model   = load_model()
    vectors = encode_chunks(chunks, model)   # transforme les textes en vecteurs
    print(f"  Vecteurs : {vectors.shape}")   # affiche ex: (1518, 384)

    print("[3/3] Sauvegarde de l'index...")
    save_index(vectors, chunks)
    print("Terminé.")


if __name__ == "__main__":
    build_vector_store()  # lance la pipeline complète si on exécute ce fichier directement
