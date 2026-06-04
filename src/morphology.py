"""
Layer 2.5: Deterministic morphological engine for Quenya

Handles inflection of nouns (declension) and verbs (conjugation) using:
  - 6 noun stem classes (a_stem, e_stem, o_stem, i_stem, u_stem, consonantal)
  - 8 cases (nominative, accusative, genitive, dative, locative, ablative,
             allative, instrumental)
  - 2 numbers (singular, plural)
  - 4 verb classes (a_verb, ya_verb, basic_verb, i_verb)
  - 3 tenses (present, past, future) + imperative mood

Every computed form carries:
  - confidence (0.0 = unknown, 0.70+ = reliable)
  - source_note (which Tolkien text or reconstruction method)
  - attestation ("attested", "reconstructed", or "neo-quenya")

Primary source: Parma Eldalamberon XVII (PE XVII) — Tolkien's Quenya grammar notes.
"""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# MorphResult dataclass
# ---------------------------------------------------------------------------

@dataclass
class MorphResult:
    """The result of morphological computation for a single word.

    Attributes:
        english_lemma : English base form (e.g. "warrior")
        quenya_lemma  : Quenya base form looked up in vocabulary (e.g. "ohtar")
        quenya_form   : the inflected form (e.g. "ohtarenna")
        feature       : human-readable description (e.g. "allative singular")
        confidence    : 0.0–1.0 (0 = not found; ≥ 0.70 = reliable)
        source_note   : provenance — PE XVII reference or reconstruction note
        attestation   : "attested" | "reconstructed" | "neo-quenya"
        warning       : optional warning message (e.g. vocab gap)
    """
    english_lemma: str
    quenya_lemma: str
    quenya_form: str
    feature: str
    confidence: float
    source_note: str
    attestation: str = "reconstructed"
    warning: str = ""

    def is_reliable(self) -> bool:
        """Return True if confidence ≥ 0.70 and no warning is set."""
        return self.confidence >= 0.70 and not self.warning


# ---------------------------------------------------------------------------
# Stem / verb class detection
# ---------------------------------------------------------------------------

def classify_stem(lemma: str) -> str:
    """Classify a Quenya noun lemma into its declension stem class.

    Handles plain and long/accented vowels (á, é, ë, í, ó, ú).

    Returns:
        One of: "a_stem", "e_stem", "o_stem", "i_stem", "u_stem", "consonantal"
    """
    lemma = lemma.lower().rstrip(".")
    if not lemma:
        return "consonantal"
    last = lemma[-1]
    if last in ("a", "á"):
        return "a_stem"
    if last in ("e", "é", "ë"):
        return "e_stem"
    if last in ("o", "ó"):
        return "o_stem"
    if last in ("i", "í"):
        return "i_stem"
    if last in ("u", "ú"):
        return "u_stem"
    return "consonantal"


def classify_verb(lemma: str) -> str:
    """Classify a Quenya verb lemma into its conjugation class.

    Returns:
        One of: "a_verb", "ya_verb", "basic_verb", "i_verb"
    """
    lemma = lemma.lower().rstrip(".")
    if not lemma:
        return "basic_verb"
    if lemma.endswith("ya"):
        return "ya_verb"
    if lemma.endswith("a"):
        return "a_verb"
    # Monosyllabic (basic) verbs: one or fewer vowels in the stem
    vowels = set("aeiouáéíóúë")
    if sum(1 for c in lemma if c in vowels) <= 1:
        return "basic_verb"
    return "i_verb"


# ---------------------------------------------------------------------------
# Noun declension rule tables
# ---------------------------------------------------------------------------
# Structure: NOUN_RULES[stem_class][case][number]
#            = (inflection_fn, confidence, source_note)
# inflection_fn: takes the Quenya lemma (str) and returns the inflected form.

NOUN_RULES: dict = {

    # ── A-stem nouns (end in -a / -á, e.g. cirya "ship", vanda "solemn promise")
    "a_stem": {
        "nominative": {
            "singular": (lambda s: s,                           0.95, "PE XVII: a-stem nom sg = bare stem"),
            "plural":   (lambda s: s + "r",                     0.92, "PE XVII: a-stem nom pl: + -r"),
        },
        "accusative": {
            "singular": (lambda s: s,                           0.90, "PE XVII: a-stem acc sg = nom sg"),
            "plural":   (lambda s: s + "r",                     0.88, "PE XVII: a-stem acc pl = nom pl"),
        },
        "genitive": {
            "singular": (lambda s: s[:-1] + "o",                0.92, "PE XVII: a-stem gen sg: -a → -o"),
            "plural":   (lambda s: s[:-1] + "on",               0.85, "PE XVII: a-stem gen pl: -a → -on"),
        },
        "dative": {
            "singular": (lambda s: s + "n",                     0.88, "PE XVII: a-stem dat sg: + -n"),
            "plural":   (lambda s: s + "in",                    0.82, "PE XVII: a-stem dat pl: + -in"),
        },
        "locative": {
            "singular": (lambda s: s + "ssë",                   0.90, "PE XVII: loc sg: + -ssë"),
            "plural":   (lambda s: s + "ssen",                  0.85, "PE XVII: loc pl: + -ssen"),
        },
        "allative": {
            "singular": (lambda s: s + "nna",                   0.92, "PE XVII: all sg: + -nna"),
            "plural":   (lambda s: s + "nnar",                  0.88, "PE XVII: all pl: + -nnar"),
        },
        "ablative": {
            "singular": (lambda s: s + "llo",                   0.90, "PE XVII: abl sg: + -llo"),
            "plural":   (lambda s: s + "llon",                  0.85, "PE XVII: abl pl: + -llon"),
        },
        "instrumental": {
            "singular": (lambda s: s + "nen",                   0.85, "PE XVII: ins sg: + -nen"),
            "plural":   (lambda s: s + "inen",                  0.80, "PE XVII: ins pl: + -inen"),
        },
    },

    # ── E-stem nouns (end in -ë / -é, e.g. lassë "leaf", taurë "forest")
    "e_stem": {
        "nominative": {
            "singular": (lambda s: s,                           0.95, "PE XVII: e-stem nom sg = bare stem"),
            "plural":   (lambda s: s[:-1] + "i",               0.92, "PE XVII: e-stem nom pl: -ë → -i"),
        },
        "accusative": {
            "singular": (lambda s: s,                           0.90, "PE XVII: e-stem acc sg = nom sg"),
            "plural":   (lambda s: s[:-1] + "i",               0.88, "PE XVII: e-stem acc pl = nom pl"),
        },
        "genitive": {
            "singular": (lambda s: s[:-1] + "o",               0.88, "PE XVII: e-stem gen sg: -ë → -o"),
            "plural":   (lambda s: s[:-1] + "on",              0.82, "PE XVII: e-stem gen pl: -ë → -on"),
        },
        "dative": {
            "singular": (lambda s: s + "n",                    0.85, "PE XVII: e-stem dat sg: + -n"),
            "plural":   (lambda s: s[:-1] + "in",              0.80, "PE XVII: e-stem dat pl: -ë → -in"),
        },
        "locative": {
            "singular": (lambda s: s + "ssë",                  0.88, "PE XVII: e-stem loc sg: + -ssë"),
            "plural":   (lambda s: s[:-1] + "issen",           0.82, "PE XVII: e-stem loc pl: -ë → -issen"),
        },
        "allative": {
            "singular": (lambda s: s[:-1] + "enna",            0.90, "PE XVII: e-stem all sg: -ë + -enna"),
            "plural":   (lambda s: s[:-1] + "ennar",           0.85, "PE XVII: e-stem all pl: -ë + -ennar"),
        },
        "ablative": {
            "singular": (lambda s: s + "llo",                  0.85, "PE XVII: e-stem abl sg: + -llo"),
            "plural":   (lambda s: s + "llon",                 0.80, "PE XVII: e-stem abl pl: + -llon"),
        },
        "instrumental": {
            "singular": (lambda s: s + "nen",                  0.82, "PE XVII: e-stem ins sg: + -nen"),
            "plural":   (lambda s: s[:-1] + "inen",            0.78, "PE XVII: e-stem ins pl: -ë → -inen"),
        },
    },

    # ── O-stem nouns (end in -o / -ó, e.g. osto "city-fortress", collo "cloak")
    "o_stem": {
        "nominative": {
            "singular": (lambda s: s,                           0.95, "PE XVII: o-stem nom sg = bare stem"),
            "plural":   (lambda s: s[:-1] + "i",               0.85, "reconstructed: o-stem pl: -o → -i"),
        },
        "accusative": {
            "singular": (lambda s: s,                           0.90, "PE XVII: o-stem acc sg = nom sg"),
            "plural":   (lambda s: s[:-1] + "i",               0.82, "reconstructed: o-stem acc pl = nom pl"),
        },
        "genitive": {
            "singular": (lambda s: s + "n",                    0.80, "reconstructed: o-stem gen sg: + -n"),
            "plural":   (lambda s: s + "n",                    0.75, "reconstructed: o-stem gen pl"),
        },
        "dative": {
            "singular": (lambda s: s + "n",                    0.80, "reconstructed: o-stem dat sg: + -n"),
            "plural":   (lambda s: s[:-1] + "in",              0.75, "reconstructed: o-stem dat pl"),
        },
        "locative": {
            "singular": (lambda s: s + "ssë",                  0.85, "PE XVII: o-stem loc sg: + -ssë"),
            "plural":   (lambda s: s + "ssen",                 0.78, "PE XVII: o-stem loc pl: + -ssen"),
        },
        "allative": {
            "singular": (lambda s: s + "nna",                  0.90, "PE XVII: o-stem all sg: + -nna → -onna"),
            "plural":   (lambda s: s + "nnar",                 0.85, "PE XVII: o-stem all pl: + -nnar"),
        },
        "ablative": {
            "singular": (lambda s: s + "llo",                  0.85, "PE XVII: o-stem abl sg: + -llo"),
            "plural":   (lambda s: s + "llon",                 0.78, "PE XVII: o-stem abl pl: + -llon"),
        },
        "instrumental": {
            "singular": (lambda s: s + "nen",                  0.80, "PE XVII: o-stem ins sg: + -nen"),
            "plural":   (lambda s: s[:-1] + "inen",            0.72, "reconstructed: o-stem ins pl"),
        },
    },

    # ── Consonantal nouns (end in a consonant, e.g. ohtar "warrior", elen "star", aran "king")
    "consonantal": {
        "nominative": {
            "singular": (lambda s: s,                           0.95, "PE XVII: consonantal nom sg = bare stem"),
            "plural":   (lambda s: s + "i",                    0.90, "PE XVII: consonantal pl: + -i"),
        },
        "accusative": {
            "singular": (lambda s: s,                           0.90, "PE XVII: consonantal acc sg = nom sg"),
            "plural":   (lambda s: s + "i",                    0.85, "PE XVII: consonantal acc pl = nom pl"),
        },
        "genitive": {
            "singular": (lambda s: s + "o",                    0.88, "PE XVII: consonantal gen sg: + -o"),
            "plural":   (lambda s: s + "ion",                  0.82, "PE XVII: consonantal gen pl: + -ion"),
        },
        "dative": {
            "singular": (lambda s: s + "en",                   0.85, "PE XVII: consonantal dat sg: + -en"),
            "plural":   (lambda s: s + "in",                   0.80, "PE XVII: consonantal dat pl: + -in"),
        },
        "locative": {
            "singular": (lambda s: s + "essë",                 0.88, "PE XVII: consonantal loc sg: + -essë"),
            "plural":   (lambda s: s + "essen",                0.82, "PE XVII: consonantal loc pl: + -essen"),
        },
        "allative": {
            "singular": (lambda s: s + "enna",                 0.90, "PE XVII: consonantal all sg: + -enna"),
            "plural":   (lambda s: s + "ennar",                0.85, "PE XVII: consonantal all pl: + -ennar"),
        },
        "ablative": {
            "singular": (lambda s: s + "ello",                 0.85, "PE XVII: consonantal abl sg: + -ello"),
            "plural":   (lambda s: s + "ellon",                0.80, "PE XVII: consonantal abl pl: + -ellon"),
        },
        "instrumental": {
            "singular": (lambda s: s + "inen",                 0.82, "PE XVII: consonantal ins sg: + -inen"),
            "plural":   (lambda s: s + "inen",                 0.75, "PE XVII: consonantal ins pl: + -inen"),
        },
    },

    # ── I-stem nouns (end in -i / -í — uncommon as independent nouns)
    "i_stem": {
        "nominative": {
            "singular": (lambda s: s,                           0.88, "reconstructed: i-stem nom sg"),
            "plural":   (lambda s: s + "r",                    0.80, "reconstructed: i-stem pl: + -r"),
        },
        "accusative": {
            "singular": (lambda s: s,                           0.85, "reconstructed: i-stem acc sg"),
            "plural":   (lambda s: s + "r",                    0.78, "reconstructed: i-stem acc pl"),
        },
        "genitive": {
            "singular": (lambda s: s + "o",                    0.78, "reconstructed: i-stem gen sg"),
            "plural":   (lambda s: s + "on",                   0.72, "reconstructed: i-stem gen pl"),
        },
        "dative": {
            "singular": (lambda s: s + "n",                    0.78, "reconstructed: i-stem dat sg"),
            "plural":   (lambda s: s + "n",                    0.70, "reconstructed: i-stem dat pl"),
        },
        "locative": {
            "singular": (lambda s: s + "ssë",                  0.78, "reconstructed: i-stem loc sg"),
            "plural":   (lambda s: s + "ssen",                 0.72, "reconstructed: i-stem loc pl"),
        },
        "allative": {
            "singular": (lambda s: s + "nna",                  0.80, "reconstructed: i-stem all sg"),
            "plural":   (lambda s: s + "nnar",                 0.75, "reconstructed: i-stem all pl"),
        },
        "ablative": {
            "singular": (lambda s: s + "llo",                  0.78, "reconstructed: i-stem abl sg"),
            "plural":   (lambda s: s + "llon",                 0.72, "reconstructed: i-stem abl pl"),
        },
        "instrumental": {
            "singular": (lambda s: s + "nen",                  0.75, "reconstructed: i-stem ins sg"),
            "plural":   (lambda s: s + "inen",                 0.68, "reconstructed: i-stem ins pl"),
        },
    },

    # ── U-stem nouns (end in -u / -ú, e.g. lú "time")
    "u_stem": {
        "nominative": {
            "singular": (lambda s: s,                           0.88, "reconstructed: u-stem nom sg"),
            "plural":   (lambda s: s + "r",                    0.80, "reconstructed: u-stem pl: + -r"),
        },
        "accusative": {
            "singular": (lambda s: s,                           0.85, "reconstructed: u-stem acc sg"),
            "plural":   (lambda s: s + "r",                    0.78, "reconstructed: u-stem acc pl"),
        },
        "genitive": {
            "singular": (lambda s: s + "o",                    0.78, "reconstructed: u-stem gen sg"),
            "plural":   (lambda s: s + "on",                   0.72, "reconstructed: u-stem gen pl"),
        },
        "dative": {
            "singular": (lambda s: s + "n",                    0.78, "reconstructed: u-stem dat sg"),
            "plural":   (lambda s: s + "in",                   0.70, "reconstructed: u-stem dat pl"),
        },
        "locative": {
            "singular": (lambda s: s + "ssë",                  0.78, "reconstructed: u-stem loc sg"),
            "plural":   (lambda s: s + "ssen",                 0.72, "reconstructed: u-stem loc pl"),
        },
        "allative": {
            "singular": (lambda s: s + "nna",                  0.80, "reconstructed: u-stem all sg"),
            "plural":   (lambda s: s + "nnar",                 0.75, "reconstructed: u-stem all pl"),
        },
        "ablative": {
            "singular": (lambda s: s + "llo",                  0.78, "reconstructed: u-stem abl sg"),
            "plural":   (lambda s: s + "llon",                 0.72, "reconstructed: u-stem abl pl"),
        },
        "instrumental": {
            "singular": (lambda s: s + "nen",                  0.75, "reconstructed: u-stem ins sg"),
            "plural":   (lambda s: s + "inen",                 0.68, "reconstructed: u-stem ins pl"),
        },
    },
}


# ---------------------------------------------------------------------------
# Verb conjugation rule tables
# ---------------------------------------------------------------------------
# Structure: VERB_RULES[verb_class][tense][number]
#            = (inflection_fn, confidence, source_note)
# Imperative mood handled separately (always same as present sg).

VERB_RULES: dict = {

    # ── A-verbs (end in -a, e.g. vanta "walk", orta "raise", mapa "seize")
    "a_verb": {
        "present": {
            "singular": (lambda s: s,              0.90, "PE XVII: a-verb pres sg = base form"),
            "plural":   (lambda s: s + "r",        0.88, "PE XVII: a-verb pres pl: + -r"),
        },
        "past": {
            "singular": (lambda s: s + "në",       0.88, "PE XVII: a-verb past sg: + -në"),
            "plural":   (lambda s: s + "ner",      0.85, "PE XVII: a-verb past pl: + -ner"),
        },
        "future": {
            "singular": (lambda s: s[:-1] + "uva", 0.88, "PE XVII: a-verb future: -a → -uva"),
            "plural":   (lambda s: s[:-1] + "uvar",0.82, "PE XVII: a-verb future pl: -a → -uvar"),
        },
    },

    # ── Ya-verbs (end in -ya, e.g. orya "rise", lelya "travel")
    "ya_verb": {
        "present": {
            "singular": (lambda s: s,                  0.85, "PE XVII: ya-verb pres sg = base form"),
            "plural":   (lambda s: s + "r",            0.82, "PE XVII: ya-verb pres pl: + -r"),
        },
        "past": {
            "singular": (lambda s: s[:-2] + "ë",       0.75, "reconstructed: ya-verb past: -ya → -ë"),
            "plural":   (lambda s: s[:-2] + "ër",      0.70, "reconstructed: ya-verb past pl"),
        },
        "future": {
            "singular": (lambda s: s[:-2] + "iuva",    0.72, "reconstructed: ya-verb future"),
            "plural":   (lambda s: s[:-2] + "iuvar",   0.68, "reconstructed: ya-verb future pl"),
        },
    },

    # ── Basic verbs (monosyllabic consonantal stem, e.g. car "do/make", kir "cleave", mel "love")
    "basic_verb": {
        "present": {
            "singular": (lambda s: s + "a",        0.90, "PE XVII: basic verb pres sg: + -a"),
            "plural":   (lambda s: s + "ir",       0.88, "PE XVII: basic verb pres pl: + -ir"),
        },
        "past": {
            "singular": (lambda s: s + "në",       0.85, "PE XVII: basic verb past sg: + -në"),
            "plural":   (lambda s: s + "ner",      0.82, "PE XVII: basic verb past pl: + -ner"),
        },
        "future": {
            "singular": (lambda s: s + "uva",      0.88, "PE XVII: basic verb future: + -uva"),
            "plural":   (lambda s: s + "uvar",     0.82, "PE XVII: basic verb future pl: + -uvar"),
        },
    },

    # ── I-verbs (rare class, mixed i/e stems)
    "i_verb": {
        "present": {
            "singular": (lambda s: s + "a",        0.75, "reconstructed: i-verb pres sg"),
            "plural":   (lambda s: s + "ar",       0.70, "reconstructed: i-verb pres pl"),
        },
        "past": {
            "singular": (lambda s: s + "në",       0.72, "reconstructed: i-verb past sg"),
            "plural":   (lambda s: s + "ner",      0.68, "reconstructed: i-verb past pl"),
        },
        "future": {
            "singular": (lambda s: s + "uva",      0.72, "reconstructed: i-verb future"),
            "plural":   (lambda s: s + "uvar",     0.68, "reconstructed: i-verb future pl"),
        },
    },
}


# ---------------------------------------------------------------------------
# Low-level inflection functions
# ---------------------------------------------------------------------------

def decline_noun(quenya_lemma: str, case: str, number: str) -> MorphResult:
    """Apply Quenya noun declension rules to a Quenya lemma.

    Args:
        quenya_lemma: the Quenya base form (e.g. "cirya", "ohtar")
        case        : one of the 8 Quenya cases
        number      : "singular" or "plural"

    Returns:
        MorphResult with the inflected form and metadata.
        If case/number combination is not in the rules, returns the bare lemma
        with low confidence.
    """
    stem_class = classify_stem(quenya_lemma)
    rules_for_class = NOUN_RULES.get(stem_class, {})
    rules_for_case  = rules_for_class.get(case, {})
    rule            = rules_for_case.get(number)

    if rule:
        inflect_fn, conf, note = rule
        form = inflect_fn(quenya_lemma)
        return MorphResult(
            english_lemma=quenya_lemma,  # caller replaces with real English lemma
            quenya_lemma=quenya_lemma,
            quenya_form=form,
            feature=f"{case} {number}",
            confidence=conf,
            source_note=note,
            attestation="reconstructed",
        )

    # Unknown case or number — return bare form with minimal confidence
    return MorphResult(
        english_lemma=quenya_lemma,
        quenya_lemma=quenya_lemma,
        quenya_form=quenya_lemma,
        feature=f"{case} {number} (unknown)",
        confidence=0.30,
        source_note="no rule available for this case/number combination",
        attestation="neo-quenya",
        warning=f"no declension rule for {stem_class}/{case}/{number}",
    )


def conjugate_verb(quenya_lemma: str, tense: str, number: str,
                   mood: str = "declarative") -> MorphResult:
    """Apply Quenya verb conjugation rules to a Quenya verb lemma.

    Args:
        quenya_lemma: the Quenya infinitive/base form (e.g. "vanta", "car")
        tense       : "present", "past", or "future"
        number      : "singular" or "plural"
        mood        : "declarative" (default) or "imperative"

    Returns:
        MorphResult with the conjugated form and metadata.
    """
    verb_class = classify_verb(quenya_lemma)

    # Imperative: same as present singular for all verb classes
    if mood == "imperative":
        rules = VERB_RULES.get(verb_class, {}).get("present", {})
        rule  = rules.get("singular")
        if rule:
            inflect_fn, conf, note = rule
            return MorphResult(
                english_lemma=quenya_lemma,
                quenya_lemma=quenya_lemma,
                quenya_form=inflect_fn(quenya_lemma),
                feature=f"imperative {number}",
                confidence=conf,
                source_note=note + " (imperative = present sg)",
                attestation="reconstructed",
            )

    rules_for_class  = VERB_RULES.get(verb_class, {})
    rules_for_tense  = rules_for_class.get(tense, {})
    rule             = rules_for_tense.get(number)

    if rule:
        inflect_fn, conf, note = rule
        return MorphResult(
            english_lemma=quenya_lemma,
            quenya_lemma=quenya_lemma,
            quenya_form=inflect_fn(quenya_lemma),
            feature=f"{tense} {number} {mood}",
            confidence=conf,
            source_note=note,
            attestation="reconstructed",
        )

    # Fallback: return bare lemma with very low confidence
    return MorphResult(
        english_lemma=quenya_lemma,
        quenya_lemma=quenya_lemma,
        quenya_form=quenya_lemma,
        feature=f"{tense} {number} {mood} (unknown)",
        confidence=0.30,
        source_note="no conjugation rule for this tense/number/mood",
        attestation="neo-quenya",
        warning=f"no conjugation rule for {verb_class}/{tense}/{number}/{mood}",
    )


# ---------------------------------------------------------------------------
# Vocabulary lookup  (English → Quenya lemma, via SQLite dictionary)
# ---------------------------------------------------------------------------

_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "vector_db", "dictionary.sqlite",
)


def _is_indirect_match(word: str, translation: str) -> bool:
    """Return True if the translation only contains `word` in a multi-word phrase.

    Example: word="give", translation="will give" → True (indirect).
    We accept it only when `word` appears as a standalone token.
    """
    auxiliaries = r"\b(?:will|shall|can|may|must|to|did|would|could|should)\s+"
    pattern = auxiliaries + re.escape(word) + r"\b"
    return bool(re.search(pattern, translation, re.IGNORECASE))


def _rank_lookup_results(word: str, rows: list) -> list:
    """Rank DB rows so the best match for a common noun comes first.

    Scoring (higher is better):
      +3  exact translation match (word == translation, case-insensitive)
      -2  indirect match (word appears in a multi-word phrase)
      -1  proper noun (starts with uppercase or pos contains "name"/"place")
      -0.5 long translation (prefer short, precise entries)
    """
    def score(row) -> float:
        w, lang, direction, trans, pos = row[0], row[1], row[2], row[3], row[4]
        trans = (trans or "").strip()
        pos   = (pos or "").lower()
        s = 0.0
        if trans.lower() == word.lower():
            s += 3.0
        if _is_indirect_match(word, trans):
            s -= 2.0
        if w and w[0].isupper():
            s -= 1.0
        if any(p in pos for p in ("name", "place", "proper")):
            s -= 1.0
        s -= len(trans) * 0.01
        return s

    return sorted(rows, key=score, reverse=True)


def lookup_quenya_lemma(
    english_word: str,
    pos_hint: Optional[str] = None,
) -> Tuple[str, str, float]:
    """Look up the Quenya lemma for an English word in the vocabulary database.

    Args:
        english_word: English base form to look up (e.g. "warrior")
        pos_hint    : optional part-of-speech hint ("noun", "verb", etc.)

    Returns:
        (quenya_lemma, part_of_speech, confidence)
        If not found: (english_word, "unknown", 0.0)
    """
    if not os.path.exists(_DB_PATH):
        return english_word, "unknown", 0.0

    try:
        conn = sqlite3.connect(_DB_PATH)
        cursor = conn.cursor()

        # Search by translation (English meaning) in Quenya entries
        cursor.execute(
            """SELECT word, language, direction, translation, part_of_speech
               FROM dictionary_entries
               WHERE language = 'Quenya'
                 AND direction LIKE '%english%'
                 AND translation LIKE ?
               LIMIT 20""",
            (f"%{english_word}%",),
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return english_word, "unknown", 0.0

        # Rank and pick best match
        rows = _rank_lookup_results(english_word, rows)
        best = rows[0]
        word, _lang, _dir, trans, pos = best

        # Reject if best match is still indirect
        if _is_indirect_match(english_word, trans or ""):
            return english_word, "unknown", 0.0

        # Confidence: exact match → high; partial → lower
        conf = 0.80 if (trans or "").lower() == english_word.lower() else 0.65
        return word or english_word, pos or "noun", conf

    except Exception:
        return english_word, "unknown", 0.0


# ---------------------------------------------------------------------------
# High-level compute functions  (called by translator.py)
# ---------------------------------------------------------------------------

def compute_noun_form(english_lemma: str, case: str, number: str) -> MorphResult:
    """Compute the Quenya noun form for a given English word.

    Pipeline:
      1. Look up Quenya lemma in vocabulary database
      2. Classify stem class
      3. Apply declension rule from NOUN_RULES

    Args:
        english_lemma: English word (e.g. "warrior")
        case         : target Quenya case (e.g. "allative")
        number       : "singular" or "plural"

    Returns:
        MorphResult — always returns something (may be low-confidence).
    """
    quenya_lemma, pos, lookup_conf = lookup_quenya_lemma(english_lemma, pos_hint="noun")

    if lookup_conf == 0.0:
        # Not in vocabulary: return placeholder
        return MorphResult(
            english_lemma=english_lemma,
            quenya_lemma=f"[{english_lemma}?]",
            quenya_form=f"[{english_lemma}?]",
            feature=f"{case} {number}",
            confidence=0.0,
            source_note="word not in Quenya vocabulary database",
            attestation="neo-quenya",
            warning=f"'{english_lemma}' not found in dictionary — LLM must supply Quenya form",
        )

    # Apply declension
    result = decline_noun(quenya_lemma, case, number)

    # Patch: restore correct English lemma and combine confidences
    combined_conf = round(min(lookup_conf, result.confidence), 3)
    return MorphResult(
        english_lemma=english_lemma,
        quenya_lemma=quenya_lemma,
        quenya_form=result.quenya_form,
        feature=result.feature,
        confidence=combined_conf,
        source_note=result.source_note,
        attestation=result.attestation,
        warning=result.warning,
    )


def compute_verb_form(
    english_lemma: str,
    tense: str,
    number: str,
    mood: str = "declarative",
) -> MorphResult:
    """Compute the Quenya verb form for a given English verb.

    Pipeline:
      1. Look up Quenya verb lemma in vocabulary database
      2. Classify verb class
      3. Apply conjugation rule from VERB_RULES

    Args:
        english_lemma: English verb (e.g. "walk")
        tense        : "present", "past", or "future"
        number       : "singular" or "plural"
        mood         : "declarative" or "imperative"

    Returns:
        MorphResult — always returns something (may be low-confidence).
    """
    quenya_lemma, pos, lookup_conf = lookup_quenya_lemma(english_lemma, pos_hint="verb")

    if lookup_conf == 0.0:
        return MorphResult(
            english_lemma=english_lemma,
            quenya_lemma=f"[{english_lemma}?]",
            quenya_form=f"[{english_lemma}?]",
            feature=f"{tense} {number} {mood}",
            confidence=0.0,
            source_note="verb not in Quenya vocabulary database",
            attestation="neo-quenya",
            warning=f"'{english_lemma}' not found in dictionary — LLM must supply Quenya form",
        )

    result = conjugate_verb(quenya_lemma, tense, number, mood)

    combined_conf = round(min(lookup_conf, result.confidence), 3)
    return MorphResult(
        english_lemma=english_lemma,
        quenya_lemma=quenya_lemma,
        quenya_form=result.quenya_form,
        feature=result.feature,
        confidence=combined_conf,
        source_note=result.source_note,
        attestation=result.attestation,
        warning=result.warning,
    )
