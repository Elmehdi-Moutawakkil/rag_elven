"""Gestion de la base de données SQLite pour les entrées de dictionnaire elfique.

SQLite est une base de données stockée dans un simple fichier local — pas besoin de serveur.
Ce fichier contient toutes les fonctions pour créer, remplir et interroger cette base.
"""

import sqlite3  # module Python intégré pour utiliser SQLite
import re       # module pour les expressions régulières (recherche avancée dans du texte)
from pathlib import Path                              # manipulation de chemins de fichiers
from typing import Iterable, Optional, Sequence      # types pour rendre le code plus lisible

DB_PATH = "vector_db/dictionary.sqlite"  # chemin du fichier SQLite sur le disque

# Schéma SQL : définit la structure de la table et les index
# CREATE TABLE IF NOT EXISTS = crée la table seulement si elle n'existe pas déjà
SCHEMA = """
CREATE TABLE IF NOT EXISTS dictionary_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,  -- identifiant unique auto-incrémenté
    word            TEXT NOT NULL,                      -- le mot elfique (ex: "elda")
    language        TEXT NOT NULL,                      -- "Quenya" ou "Sindarin"
    direction       TEXT NOT NULL,                      -- "quenya->english" ou "sindarin->english"
    translation     TEXT,                               -- traduction principale (ex: "elf")
    part_of_speech  TEXT,                               -- catégorie grammaticale (noun, verb, adj...)
    plural_form     TEXT,                               -- forme plurielle si disponible
    source          TEXT,                               -- nom du fichier PDF source
    page            INTEGER,                            -- numéro de page dans le PDF
    raw_text        TEXT                                -- texte brut original de l'entrée (backup)
);
CREATE INDEX IF NOT EXISTS idx_word        ON dictionary_entries(word);         -- accélère la recherche par mot
CREATE INDEX IF NOT EXISTS idx_translation ON dictionary_entries(translation);  -- accélère la recherche par traduction
CREATE INDEX IF NOT EXISTS idx_lang        ON dictionary_entries(language);     -- accélère le filtre par langue
CREATE INDEX IF NOT EXISTS idx_dir         ON dictionary_entries(direction);    -- accélère le filtre par direction
"""


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Ouvre (ou crée) la connexion au fichier SQLite et la retourne."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)  # crée vector_db/ si le dossier n'existe pas
    conn = sqlite3.connect(db_path)         # ouvre le fichier SQLite (le crée s'il n'existe pas)
    conn.row_factory = sqlite3.Row          # permet d'accéder aux colonnes par leur nom : row["word"] au lieu de row[0]
    return conn


def init_db(db_path: str = DB_PATH, reset: bool = False) -> None:
    """Initialise la base de données (crée la table et les index).

    Args:
        reset: si True, supprime la base existante avant de recréer (repart de zéro)
    """
    if reset and Path(db_path).exists():  # si reset demandé et que le fichier existe
        Path(db_path).unlink()            # supprime le fichier SQLite pour repartir propre
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)  # exécute toutes les instructions SQL du schéma d'un coup
    conn.commit()               # sauvegarde les changements
    conn.close()                # ferme la connexion (libère le fichier)


def insert_entries(entries: Iterable[dict], db_path: str = DB_PATH) -> int:
    """Insère une liste d'entrées de dictionnaire dans la base.

    Args:
        entries: liste de dicts, chacun représentant une entrée (word, language, translation, etc.)

    Returns:
        nombre d'entrées insérées
    """
    conn = get_connection(db_path)

    # on construit la liste de tuples à insérer (un tuple = une ligne dans la table)
    rows = [
        (
            e.get("word", ""),
            e.get("language", ""),
            e.get("direction", ""),
            e.get("translation"),
            e.get("part_of_speech"),
            e.get("plural_form"),
            e.get("source"),
            e.get("page"),
            e.get("raw_text"),
        )
        for e in entries  # on parcourt chaque entrée et on extrait les valeurs dans le bon ordre
    ]

    # executemany insère toutes les lignes en une seule opération (bien plus rapide qu'une boucle)
    conn.executemany(
        """INSERT INTO dictionary_entries
           (word, language, direction, translation, part_of_speech,
            plural_form, source, page, raw_text)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",  # les ? sont des placeholders remplacés par les valeurs de rows
        rows,
    )
    conn.commit()   # sauvegarde
    n = len(rows)   # nombre de lignes insérées
    conn.close()
    return n


def count_entries(db_path: str = DB_PATH) -> int:
    """Retourne le nombre total d'entrées dans la base."""
    conn = get_connection(db_path)
    n = conn.execute("SELECT COUNT(*) FROM dictionary_entries").fetchone()[0]  # fetchone() récupère la première (et unique) ligne
    conn.close()
    return n


def count_by_direction(db_path: str = DB_PATH) -> dict:
    """Retourne le nombre d'entrées par direction (quenya->english, etc.)."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT direction, COUNT(*) AS n FROM dictionary_entries GROUP BY direction"  # GROUP BY regroupe par valeur unique
    ).fetchall()
    conn.close()
    return {r["direction"]: r["n"] for r in rows}  # transforme le résultat en dict Python


def lookup_word(
    word: str, language: Optional[str] = None, db_path: str = DB_PATH
) -> Sequence[sqlite3.Row]:
    """Recherche exacte d'un mot dans la base.

    Args:
        word    : le mot à chercher (ex: "elda")
        language: filtre optionnel par langue ("Quenya" ou "Sindarin")

    Returns:
        liste de lignes SQLite correspondantes
    """
    conn = get_connection(db_path)
    if language:  # si une langue est précisée, on filtre dessus aussi
        rows = conn.execute(
            "SELECT * FROM dictionary_entries WHERE word = ? AND language = ?",
            (word, language),
        ).fetchall()
    else:  # sans filtre de langue, on cherche dans toutes les langues
        rows = conn.execute(
            "SELECT * FROM dictionary_entries WHERE word = ?", (word,)
        ).fetchall()
    conn.close()
    return rows


def search_translation(query: str, db_path: str = DB_PATH) -> Sequence[sqlite3.Row]:
    """Cherche dans les traductions avec correspondance mot entier uniquement.

    Utilise une regex pour éviter les faux positifs :
    "elda" ne doit pas matcher "Eldar" ou "Eldarin".
    """
    conn = get_connection(db_path)

    # \b = limite de mot (word boundary) : assure qu'on matche le mot exact, pas une sous-chaîne
    # (?i) = insensible à la casse (Elda = elda)
    pattern = rf"(?i)\b{re.escape(query)}\b"

    # SQLite ne supporte pas REGEXP nativement — on lui ajoute la fonction via Python
    conn.create_function("REGEXP", 2, lambda pat, val: (
        bool(re.search(pat, val or ""))  # retourne True si le pattern est trouvé dans val
    ))

    rows = conn.execute(
        "SELECT * FROM dictionary_entries WHERE translation REGEXP ?",
        (pattern,),
    ).fetchall()
    conn.close()
    return rows


if __name__ == "__main__":
    init_db(reset=True)  # recrée une base vide pour tester
    print(f"DB initialisée à : {DB_PATH}")
    print(f"Entrées actuelles : {count_entries()}")  # doit afficher 0 après reset
