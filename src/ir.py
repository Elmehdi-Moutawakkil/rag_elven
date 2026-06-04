"""
Layer 1: English → Semantic Intermediate Representation (SemanticIR)

Uses spaCy to parse English sentences into a semantic structure:
  - Predicate (main verb)
  - Arguments (nouns with their thematic roles: agent, patient, location, etc.)
  - Each argument carries case and number hints for Quenya inflection

The IR is the bridge between natural English and deterministic Quenya morphology.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Argument:
    """A semantic argument (noun phrase) in a sentence.

    Attributes:
        role: thematic role ("agent", "patient", "location", "instrument", etc.)
        lemma: the base form of the noun
        number: "singular" or "plural"
        case: Quenya case hint ("nominative", "accusative", "genitive", "locative", etc.)
        is_proper: True if this is a proper noun (name)
    """
    role: str          # "agent", "patient", "location", "instrument", "beneficiary", etc.
    lemma: str         # base form
    number: str        # "singular" or "plural"
    case: str          # Quenya case to use
    is_proper: bool = False


@dataclass
class PredicateIR:
    """The main verb of the sentence.

    Attributes:
        lemma: base verb form
        tense: "present", "past", "future", etc.
        mood: "declarative", "imperative", "conditional", etc.
        number: "singular" or "plural" (agrees with subject)
    """
    lemma: str         # "walk", "speak", "see", etc.
    tense: str         # "present", "past", "future"
    mood: str          # "declarative", "imperative", "conditional", "subjunctive"
    number: str        # "singular" or "plural"


@dataclass
class SemanticIR:
    """Semantic Intermediate Representation of an English sentence.

    The result of Layer 1 (parsing). This IR is then passed to Layer 2.5 (morphology)
    and Layer 3 (arrangement).

    Attributes:
        predicate: the main verb
        arguments: list of semantic arguments
        raw_sentence: the original English input (for reference)
    """
    predicate: PredicateIR
    arguments: list[Argument] = field(default_factory=list)
    raw_sentence: str = ""


# ---------------------------------------------------------------------------
# spaCy parsing
# ---------------------------------------------------------------------------

def _get_spacy_model():
    """Load spaCy's English model. Lazy-loads on first call."""
    global _SPACY_MODEL
    if "_SPACY_MODEL" not in globals():
        try:
            import spacy  # type: ignore
            _SPACY_MODEL = spacy.load("en_core_web_sm")
        except Exception:
            _SPACY_MODEL = None
    return _SPACY_MODEL


def parse_english(sentence: str) -> SemanticIR:
    """Parse an English sentence using spaCy and extract semantic roles.

    Heuristic approach:
      1. Find the main verb (ROOT dependency)
      2. Find subject (nsubj) → agent
      3. Find direct object (dobj) → patient
      4. Find oblique arguments (prep) → location, instrument, etc.

    If spaCy fails completely, returns a fallback IR with predicate="be" and no arguments.

    Args:
        sentence: English sentence to parse

    Returns:
        SemanticIR with predicate, arguments, and raw_sentence
    """
    nlp = _get_spacy_model()
    if not nlp:
        # No spaCy available: fallback to minimal IR
        return SemanticIR(
            predicate=PredicateIR(
                lemma="be",
                tense="present",
                mood="declarative",
                number="singular",
            ),
            arguments=[],
            raw_sentence=sentence,
        )

    doc = nlp(sentence)

    # --- Find main verb (ROOT) ---
    root_token = None
    for token in doc:
        if token.dep_ == "ROOT" and token.pos_ in ("VERB", "AUX"):
            root_token = token
            break

    if not root_token:
        # No clear ROOT verb found: fallback
        return SemanticIR(
            predicate=PredicateIR(
                lemma="be",
                tense="present",
                mood="declarative",
                number="singular",
            ),
            arguments=[],
            raw_sentence=sentence,
        )

    # --- Extract predicate info ---
    verb_lemma = root_token.lemma_
    verb_tense = _infer_tense(root_token)
    verb_mood = _infer_mood(root_token)
    verb_number = _infer_number(root_token)

    predicate = PredicateIR(
        lemma=verb_lemma,
        tense=verb_tense,
        mood=verb_mood,
        number=verb_number,
    )

    # --- Extract arguments ---
    arguments = _extract_arguments(doc, root_token)

    return SemanticIR(
        predicate=predicate,
        arguments=arguments,
        raw_sentence=sentence,
    )


def _infer_tense(token) -> str:
    """Infer tense from spaCy token attributes."""
    # Simple heuristic based on lemma and tag
    tag = token.tag_
    text = token.text.lower()

    # Past tense markers
    if tag in ("VBD", "VBN"):
        return "past"
    # Future tense (will)
    if text == "will" or token.lemma_ == "will":
        return "future"
    # Present is default
    return "present"


def _infer_mood(token) -> str:
    """Infer mood from context. For now, assume declarative."""
    # TODO: detect conditional, imperative, subjunctive from syntax
    return "declarative"


def _infer_number(token) -> str:
    """Infer number from morphology."""
    tag = token.tag_
    # VBZ is 3rd person singular present
    # VBP is base form (plural or first/second person)
    if tag in ("VBZ", "VBD"):
        return "singular"
    return "plural"


def _extract_arguments(doc, root_token) -> list[Argument]:
    """Extract semantic arguments from the sentence around the main verb."""
    arguments = []
    processed_tokens = set()

    # Helper: recursively collect tokens under a head
    def collect_subtree(token):
        """Collect all tokens in a subtree."""
        result = [token]
        for child in token.children:
            result.extend(collect_subtree(child))
        return result

    # --- Subject (agent) ---
    for child in root_token.children:
        if child.dep_ in ("nsubj", "nsubjpass"):
            noun_lemma = child.lemma_
            number = "plural" if child.tag_ in ("NNS", "NNPS") else "singular"
            is_proper = child.pos_ == "PROPN" or child.tag_ in ("NNP", "NNPS")
            arguments.append(Argument(
                role="agent",
                lemma=noun_lemma,
                number=number,
                case="nominative",
                is_proper=is_proper,
            ))
            processed_tokens.update(t.i for t in collect_subtree(child))

    # --- Direct object (patient) ---
    for child in root_token.children:
        if child.dep_ in ("dobj", "obj", "attr"):
            noun_lemma = child.lemma_
            number = "plural" if child.tag_ in ("NNS", "NNPS") else "singular"
            is_proper = child.pos_ == "PROPN" or child.tag_ in ("NNP", "NNPS")
            arguments.append(Argument(
                role="patient",
                lemma=noun_lemma,
                number=number,
                case="accusative",
                is_proper=is_proper,
            ))
            processed_tokens.update(t.i for t in collect_subtree(child))

    # --- Oblique arguments (prepositional phrases) ---
    for child in root_token.children:
        if child.dep_ in ("prep",):  # prepositional phrase
            prep_lemma = child.lemma_  # the preposition
            role = _role_from_preposition(prep_lemma)

            # Find noun under the preposition
            for pobj in child.children:
                if pobj.dep_ in ("pobj", "obj"):
                    noun_lemma = pobj.lemma_
                    number = "plural" if pobj.tag_ in ("NNS", "NNPS") else "singular"
                    is_proper = pobj.pos_ == "PROPN" or pobj.tag_ in ("NNP", "NNPS")

                    # Map role to Quenya case
                    case = _case_from_role(role, prep_lemma)

                    arguments.append(Argument(
                        role=role,
                        lemma=noun_lemma,
                        number=number,
                        case=case,
                        is_proper=is_proper,
                    ))
                    processed_tokens.update(t.i for t in collect_subtree(pobj))

    return arguments


def _role_from_preposition(prep_lemma: str) -> str:
    """Map English prepositions to thematic roles."""
    prep = prep_lemma.lower()

    location_preps = {"in", "on", "at", "inside", "outside", "near", "beside", "under", "over"}
    if prep in location_preps:
        return "location"

    direction_preps = {"to", "toward", "into", "onto", "off", "from"}
    if prep in direction_preps:
        return "direction"

    instrument_preps = {"with", "by"}
    if prep in instrument_preps:
        return "instrument"

    beneficiary_preps = {"for", "to"}
    if prep in beneficiary_preps:
        return "beneficiary"

    # Default
    return "oblique"


def _case_from_role(role: str, prep_lemma: str = "") -> str:
    """Map semantic role to Quenya case."""
    if role == "agent":
        return "nominative"
    elif role == "patient":
        return "accusative"
    elif role == "location":
        return "locative"
    elif role == "direction":
        return "allative"
    elif role == "instrument":
        return "instrumental"
    elif role == "beneficiary":
        return "dative"
    elif role == "oblique":
        # Default to genitive or locative depending on preposition
        if prep_lemma and prep_lemma.lower() in ("of", "from"):
            return "genitive"
        return "locative"
    else:
        return "nominative"
