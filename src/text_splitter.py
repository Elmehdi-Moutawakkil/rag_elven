"""Chunking pour les documents non-dictionnaires (cours, lore).

Le "chunking" = découper un long document en petits morceaux (~800 caractères)
que le modèle d'embeddings peut traiter. Les dictionnaires sont exclus ici
car ils vont dans la base SQLite dictionnaire.

Pipeline :
    pages brutes
        ↓ extraction (pymupdf si dispo, sinon pypdf)
        ↓ nettoyage léger (en-têtes, URLs, sauts de ligne en trop)
        ↓ concaténation par source + mapping offset → page
        ↓ RecursiveCharacterTextSplitter avec séparateurs adaptés
    chunks propres avec metadata (source, page, type)
"""

import re
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

# On essaie d'importer le vrai splitter de LangChain.
# Si non disponible (pas installé), on utilise le fallback ci-dessous.
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:  # fallback minimal si langchain_text_splitters n'est pas dispo
    class RecursiveCharacterTextSplitter:  # type: ignore[no-redef]
        """Remplacement simplifié du splitter LangChain.

        Reproduit le comportement essentiel : découpe récursivement le texte
        en essayant les séparateurs dans l'ordre (paragraphe → ligne → phrase → mot).
        NB : cet fallback n'implémente pas l'overlap (chevauchement) entre chunks ;
        en production, le vrai langchain_text_splitters est utilisé.
        """

        def __init__(self, chunk_size, chunk_overlap, separators, length_function=len):
            self.chunk_size = chunk_size        # taille max d'un chunk en caractères
            self.chunk_overlap = chunk_overlap  # chevauchement entre chunks consécutifs
            self.separators = separators        # séparateurs à essayer dans l'ordre
            self.length_function = length_function  # fonction qui mesure la taille (len par défaut)

        def split_text(self, text: str):
            """Point d'entrée : découpe `text` en chunks en utilisant les séparateurs."""
            return self._recursive_split(text, self.separators)

        def _recursive_split(self, text, seps):
            """Découpe récursive : essaie chaque séparateur jusqu'à trouver des chunks assez petits."""
            if self.length_function(text) <= self.chunk_size:
                return [text] if text else []   # texte assez court → c'est déjà un chunk
            sep = seps[0] if seps else ""       # essaie le premier séparateur de la liste
            rest = seps[1:] if seps else []     # les séparateurs restants (pour la récursion)
            parts = text.split(sep) if sep else list(text)  # découpe selon le séparateur
            chunks = []
            buf = ""                            # tampon pour accumuler des parties
            for piece in parts:
                segment = (buf + sep + piece) if buf else piece  # essaie d'ajouter la partie au tampon
                if self.length_function(segment) <= self.chunk_size:
                    buf = segment              # le segment est assez petit → on l'accumule
                else:
                    if buf:
                        chunks.append(buf)     # le tampon est plein → on le sauvegarde comme chunk
                    if self.length_function(piece) > self.chunk_size and rest:
                        chunks.extend(self._recursive_split(piece, rest))  # partie trop grande → récursion avec séparateur plus fin
                        buf = ""
                    else:
                        buf = piece            # recommence avec cette partie comme nouveau tampon
            if buf:
                chunks.append(buf)             # sauvegarde le dernier tampon s'il reste du texte
            # NB: ce fallback n'applique pas d'overlap pour garder une
            # taille stable. Le vrai langchain_text_splitters gère l'overlap
            # correctement et est utilisé en production.
            return chunks

# pypdf est obligatoire (extraction PDF basique) ;
# pymupdf (fitz) est optionnel mais bien meilleur pour les PDF LaTeX
try:
    import fitz  # pymupdf : extraction PDF haute qualité, gère mieux les fonts spéciales
    _HAS_PYMUPDF = True   # flag : True si pymupdf est installé
except ImportError:
    _HAS_PYMUPDF = False  # flag : False → on utilisera pypdf comme fallback

from pypdf import PdfReader   # extraction PDF de base, toujours disponible


# ---------------------------------------------------------------------------
# Détection du type de document
# ---------------------------------------------------------------------------

def detect_document_type(source: str) -> str:
    """Devine le type de document à partir de son chemin/nom de fichier.

    Retourne une des 4 valeurs : 'course', 'lore', 'dictionary', 'default'.
    Cette info sera stockée dans les metadata du chunk pour filtrer lors du retrieval.

    IMPORTANT — ordre de priorité :
        Le dossier parent est vérifié EN PREMIER. Ainsi, un fichier
        "data/lore/quenya_vs_sindarin.txt" est reconnu comme "lore"
        et non "dictionary" malgré la présence de "sindarin" dans le nom.

    Exemples :
        "data/course/lesson1.pdf"              → "course"
        "data/lore/quenya_vs_sindarin.txt"     → "lore"   (dossier gagne sur le nom)
        "data/dict/sindarin_dict.pdf"          → "dictionary"
        "data/misc/notes.txt"                  → "default"
    """
    p = Path(source)
    # Vérifie d'abord le dossier parent pour éviter les faux positifs sur le nom de fichier
    # Ex: "data/lore/quenya_vs_sindarin.txt" → parent = "lore" → retourne "lore"
    parent = p.parent.name.lower()
    if parent == "lore":
        return "lore"
    if parent == "course":
        return "course"

    s = str(source).lower()                                   # lowercase pour comparer sans tenir compte des majuscules
    if "dictionary" in s or "english_quenya" in s or "sindarin" in s:
        return "dictionary"    # les dictionnaires vont dans SQLite, pas dans FAISS
    if "course" in s:
        return "course"        # cours de grammaire elfique
    if "lore" in s:
        return "lore"          # articles de lore (histoire, personnages, etc.)
    return "default"           # type inconnu → config par défaut


# ---------------------------------------------------------------------------
# Configuration de chunking par type
# ---------------------------------------------------------------------------

# Séparateurs essayés dans l'ordre : d'abord les plus grands (paragraphes),
# puis de plus en plus petits (lignes, phrases, mots, caractères).
# Le splitter essaie le premier qui permet de rester sous chunk_size.
_DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]
_COURSE_SEPARATORS = ["\nLesson ", "\nChapter ", "\n\n", "\n", ". ", " ", ""]  # séparateurs spéciaux pour les cours structurés

CHUNK_CONFIG = {
    # chunk_size    : taille max d'un chunk en caractères (~800 chars ≈ 150-200 tokens)
    # chunk_overlap : les 150 derniers caractères d'un chunk sont répétés au début du suivant
    #                 → évite de couper une idée en plein milieu
    # separators    : ordre de priorité pour découper proprement
    "course": {"chunk_size": 800, "chunk_overlap": 150, "separators": _COURSE_SEPARATORS},
    "lore":   {"chunk_size": 800, "chunk_overlap": 150, "separators": _DEFAULT_SEPARATORS},
    "default":{"chunk_size": 800, "chunk_overlap": 150, "separators": _DEFAULT_SEPARATORS},
}


# ---------------------------------------------------------------------------
# Nettoyage
# ---------------------------------------------------------------------------

# Patterns de bruit issus du nettoyage dictionnaire historique :
# en-têtes/pieds de page, URLs, numéros de page seuls sur une ligne
_NOISE_PATTERNS = [
    re.compile(r"Helge K\.\s*Fauskanger.*?$", re.MULTILINE),         # nom auteur en en-tête
    re.compile(r"http\S+", re.IGNORECASE),                            # URLs
    re.compile(r"Wordlist last updated.*?$", re.MULTILINE),           # ligne de date
    re.compile(r"Presented by.*?$", re.MULTILINE),                    # ligne de présentation
    re.compile(r"ambar[-\s]?aldaron\.com.*?$", re.IGNORECASE | re.MULTILINE),  # nom du site source
    re.compile(r"ambar-eldaron\.com.*?$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*\d{1,4}\s*$", re.MULTILINE),  # numéros de page seuls sur une ligne
    # Lignes de table des matières : "1.2 The Noun . . . . . . . . . 65"
    # Inutiles pour le RAG (pas de contenu sémantique, que des pointillés et numéros de page)
    re.compile(r"^[^\n]*\.\s\.\s\..*?\d+\s*$", re.MULTILINE),
    # Guillemets LaTeX mal encodés par pypdf : \word" ou \word' → pypdf encode \ devant les quotes
    re.compile(r"\\(?=[a-zA-Z\"'])", re.MULTILINE),                   # supprime le \ parasite avant lettre/quote
]

# Problème fréquent avec pypdf sur les PDF LaTeX : "theTolkien" au lieu de "the Tolkien"
# Ce pattern détecte une lettre minuscule collée à une majuscule → insère un espace
_RUNON_FIX = re.compile(r"([a-z])([A-Z])")


def clean_text(text: str, fix_runons: bool = False) -> str:
    """Supprime les motifs de pollution et normalise les espaces.

    Args:
        text      : texte brut extrait du PDF ou fichier TXT
        fix_runons: si True, insère un espace entre minuscule et majuscule collées
                    (nécessaire pour les PDF LaTeX extraits sans pymupdf)

    Returns:
        texte nettoyé, prêt pour le chunking
    """
    for pat in _NOISE_PATTERNS:
        text = pat.sub("", text)                    # supprime chaque pattern de bruit
    if fix_runons:
        text = _RUNON_FIX.sub(r"\1 \2", text)      # "theTolkien" → "the Tolkien"
    text = re.sub(r"[ \t]+", " ", text)             # plusieurs espaces/tabs → un seul espace
    text = re.sub(r"\n{3,}", "\n\n", text)          # 3+ sauts de ligne → exactement 2
    return text.strip()                             # supprime espaces en début/fin


# ---------------------------------------------------------------------------
# Extraction de texte par page
# ---------------------------------------------------------------------------

def _extract_pages_pymupdf(pdf_path: str) -> List[str]:
    """Extrait le texte page par page avec pymupdf (meilleure qualité).

    pymupdf (fitz) gère bien les PDF avec polices spéciales ou encodages complexes.
    Utilise un bloc try/finally pour garantir la fermeture du document, même en cas d'erreur.
    """
    doc = fitz.open(pdf_path)                              # ouvre le PDF
    try:
        return [doc[i].get_text() for i in range(len(doc))]  # extrait le texte de chaque page
    finally:
        doc.close()                                        # ferme toujours le fichier (libère la mémoire)


def _extract_pages_pypdf(pdf_path: str) -> List[str]:
    """Extrait le texte page par page avec pypdf (fallback basique).

    Moins précis que pymupdf, surtout sur les PDF LaTeX (peut coller des mots).
    `or ""` : si extract_text() retourne None (page vide/image), on renvoie une chaîne vide.
    """
    reader = PdfReader(pdf_path)
    return [(p.extract_text() or "") for p in reader.pages]


def extract_pages(pdf_path: str, prefer_pymupdf: bool = True) -> List[str]:
    """Choisit le meilleur extracteur disponible et retourne les pages en texte.

    Args:
        pdf_path      : chemin vers le PDF
        prefer_pymupdf: si True, utilise pymupdf quand disponible (True par défaut)

    Returns:
        liste de strings, un par page du PDF
    """
    if prefer_pymupdf and _HAS_PYMUPDF:
        return _extract_pages_pymupdf(pdf_path)   # pymupdf disponible et préféré → qualité maximale
    return _extract_pages_pypdf(pdf_path)          # fallback sur pypdf


# ---------------------------------------------------------------------------
# Concaténation pages → texte avec mapping offset → page
# ---------------------------------------------------------------------------

def concatenate_pages(pages: List[str], fix_runons: bool = False) -> Tuple[str, List[Tuple[int, int]]]:
    """Assemble les pages en un seul texte et mémorise où commence chaque page.

    On a besoin de ce mapping pour savoir sur quelle page se trouve un chunk.
    Les chunks n'alignent pas forcément sur les sauts de page : un chunk peut
    commencer page 3 et finir page 4 → on stocke la page de début du chunk.

    Args:
        pages      : liste de textes bruts (un par page)
        fix_runons : passe le flag à clean_text pour corriger les mots collés

    Returns:
        (full_text, offsets)
        - full_text : tout le texte concaténé en un seul bloc
        - offsets   : liste de (position_dans_full_text, numéro_de_page)
    """
    parts: List[str] = []
    offsets: List[Tuple[int, int]] = []
    cursor = 0                                         # position courante dans le texte final
    for i, page_text in enumerate(pages):
        cleaned = clean_text(page_text, fix_runons=fix_runons)
        if not cleaned:
            continue                                  # page vide ou que du bruit → on l'ignore
        offsets.append((cursor, i))                   # mémorise où commence cette page dans le texte global
        parts.append(cleaned)
        cursor += len(cleaned) + 2                    # +2 pour le "\n\n" qui séparera les pages
    full = "\n\n".join(parts)                         # assemble toutes les pages en un seul texte
    return full, offsets


def page_for_offset(offset: int, page_offsets: List[Tuple[int, int]]) -> Optional[int]:
    """Retrouve le numéro de page qui contient la position `offset` dans le texte global.

    Même logique que le nettoyage dictionnaire historique : on cherche la dernière page
    dont le début est avant ou à la position donnée.

    Args:
        offset      : position caractère dans le texte global
        page_offsets: liste de (position_début, numéro_page) produite par concatenate_pages

    Returns:
        numéro de page (int) ou None si la liste est vide
    """
    page = None
    for off, p in page_offsets:
        if off <= offset:
            page = p    # cette page commence avant notre position → candidat valide
        else:
            break       # la page suivante commence après → on s'arrête
    return page


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------

def split_pdf(pdf_path: str) -> List[dict]:
    """Découpe un PDF en chunks prêts pour les embeddings.

    Chaque chunk est un dict avec deux clés :
        - 'text'    : le texte du chunk (≤ 800 caractères)
        - 'metadata': infos sur l'origine (source, type, page, config de chunking)

    Les dictionnaires sont exclus ici (ils vont dans SQLite).

    Args:
        pdf_path: chemin vers le fichier PDF

    Returns:
        liste de chunks (dicts), ou liste vide si c'est un dictionnaire
    """
    doc_type = detect_document_type(pdf_path)
    if doc_type == "dictionary":
        return []                                  # dictionnaire → SQLite, pas FAISS

    cfg = CHUNK_CONFIG.get(doc_type, CHUNK_CONFIG["default"])  # récupère la config de chunking pour ce type

    # Rustine pour les PDF LaTeX extraits sans pymupdf : les mots sont parfois collés
    fix_runons = (doc_type == "course") and (not _HAS_PYMUPDF)
    pages = extract_pages(pdf_path, prefer_pymupdf=True)           # extrait les pages
    full_text, offsets = concatenate_pages(pages, fix_runons=fix_runons)  # assemble en un bloc
    if not full_text:
        return []                                  # PDF vide ou illisible

    # Initialise le splitter avec la config du type de document
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg["chunk_size"],              # taille max d'un chunk
        chunk_overlap=cfg["chunk_overlap"],        # chevauchement entre chunks consécutifs
        separators=cfg["separators"],              # séparateurs essayés dans l'ordre
        length_function=len,                       # mesure la taille en nombre de caractères
    )

    # Découpe le texte en chunks, puis retrouve la page d'origine de chaque chunk
    # en cherchant sa position dans le texte global (les chunks sont produits dans l'ordre)
    chunks_text = splitter.split_text(full_text)   # liste de strings (les chunks)
    chunks: List[dict] = []
    cursor = 0                                     # position de recherche dans full_text (optimisation : on ne repart pas du début)
    for ct in chunks_text:
        # Cherche la position de ce chunk dans le texte global (en avançant depuis le dernier chunk)
        found = full_text.find(ct, cursor)
        if found == -1:
            found = full_text.find(ct)             # fallback : cherche depuis le début si introuvable en avançant
        page = page_for_offset(found if found >= 0 else 0, offsets)  # retrouve la page
        if found >= 0:
            cursor = found + max(1, len(ct) - cfg["chunk_overlap"])  # avance le curseur (en soustrayant l'overlap)
        chunks.append(
            {
                "text": ct,                        # texte du chunk
                "metadata": {
                    "source": str(pdf_path),       # chemin du fichier source
                    "doc_type": doc_type,          # type de document (course/lore/default)
                    "page": page,                  # numéro de page d'origine
                    "chunk_size": cfg["chunk_size"],
                    "chunk_overlap": cfg["chunk_overlap"],
                },
            }
        )
    return chunks


def split_text_file(txt_path: str) -> List[dict]:
    """Découpe un fichier texte (.txt) en chunks.

    Même logique que split_pdf mais plus simple : pas d'extraction PDF,
    on lit directement le contenu du fichier texte.
    Utilisé pour les fichiers de lore écrits en .txt.

    Args:
        txt_path: chemin vers le fichier .txt

    Returns:
        liste de chunks (dicts), ou liste vide si c'est un dictionnaire
    """
    doc_type = detect_document_type(txt_path)
    if doc_type == "dictionary":
        return []                                  # dictionnaire → pas de chunking ici
    cfg = CHUNK_CONFIG.get(doc_type, CHUNK_CONFIG["default"])
    text = clean_text(Path(txt_path).read_text(encoding="utf-8"))  # lit le fichier et nettoie
    if not text:
        return []                                  # fichier vide
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg["chunk_size"],
        chunk_overlap=cfg["chunk_overlap"],
        separators=cfg["separators"],
        length_function=len,
    )
    # list comprehension : crée un dict par chunk produit par split_text()
    return [
        {
            "text": t,
            "metadata": {
                "source": str(txt_path),
                "doc_type": doc_type,
                "page": None,                      # pas de notion de page dans un .txt
                "chunk_size": cfg["chunk_size"],
                "chunk_overlap": cfg["chunk_overlap"],
            },
        }
        for t in splitter.split_text(text)         # splitter.split_text() retourne une liste de strings
    ]


# ---------------------------------------------------------------------------
# Pipeline complet
# ---------------------------------------------------------------------------

def discover_non_dictionary_files(data_dir: str = "data") -> Iterator[str]:
    """Parcourt data/ récursivement et yield les chemins des fichiers à chunker.

    Exclut automatiquement les dictionnaires (détectés par detect_document_type).
    Seuls les .pdf et .txt sont traités.

    Args:
        data_dir: dossier racine des données (par défaut "data")

    Yields:
        chemins de fichiers (str) à passer à split_pdf() ou split_text_file()
    """
    for path in Path(data_dir).rglob("*"):         # rglob("*") = tous les fichiers récursivement
        if not path.is_file():
            continue                               # ignore les dossiers
        if path.suffix.lower() not in {".pdf", ".txt"}:
            continue                               # ignore les fichiers qui ne sont pas PDF ou TXT
        if detect_document_type(str(path)) == "dictionary":
            continue                               # ignore les dictionnaires (→ SQLite)
        yield str(path)                            # yield = retourne un par un (générateur, économise la mémoire)


def split_corpus(data_dir: str = "data") -> List[dict]:
    """Point d'entrée principal : produit tous les chunks du corpus non-dictionnaire.

    Appelle discover_non_dictionary_files() pour trouver les fichiers,
    puis split_pdf() ou split_text_file() selon l'extension.

    Args:
        data_dir: dossier racine des données

    Returns:
        liste complète de tous les chunks (dicts) de tous les documents
    """
    chunks: List[dict] = []
    for path in discover_non_dictionary_files(data_dir):
        if path.lower().endswith(".pdf"):
            chunks.extend(split_pdf(path))          # PDF → split_pdf()
        else:
            chunks.extend(split_text_file(path))    # TXT → split_text_file()
    return chunks


if __name__ == "__main__":
    # Test rapide : affiche le nombre de chunks produits et un exemple
    print(f"pymupdf disponible : {_HAS_PYMUPDF}")
    chunks = split_corpus()
    print(f"Total chunks produits : {len(chunks)}")
    by_type: dict = {}
    for c in chunks:
        by_type[c["metadata"]["doc_type"]] = by_type.get(c["metadata"]["doc_type"], 0) + 1  # compte les chunks par type
    print(f"Par type : {by_type}")
    if chunks:
        print("\nExemple de chunk (premier) :")
        print("  metadata:", chunks[0]["metadata"])
        print("  text   :", chunks[0]["text"][:300])
