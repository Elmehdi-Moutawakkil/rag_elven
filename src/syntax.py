"""
Layer 2.8: Deterministic Quenya syntax realizer

Takes pre-computed word forms (from Layer 2.5 morphology) and arranges them
into a Quenya sentence using deterministic rules:

  1. Word order: SOV (Subject-Object-Verb) is primary, VSO alternative
  2. Grammatical particles: i (the), ar (and), etc.
  3. Adjective placement: before nouns
  4. Oblique arguments: typically after verb
  5. Copula handling: often omitted in Quenya

The LLM receives the pre-assembled sentence and only adjusts register/style.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.ir import SemanticIR, Argument
from src.morphology import MorphResult


@dataclass
class SyntaxResult:
    """Result of deterministic syntax realization.

    Attributes:
        quenya_sentence: the fully assembled Quenya sentence
        word_order_rule: which word order pattern was applied
        particles_added: list of particles inserted
        confidence: overall confidence in the arrangement (0.0–1.0)
        notes: explanation of choices made
    """
    quenya_sentence: str
    word_order_rule: str
    particles_added: list[str]
    confidence: float
    notes: str = ""


def realize_syntax(ir: SemanticIR, morphed_forms: list[MorphResult]) -> SyntaxResult:
    """Arrange pre-computed Quenya forms into a sentence using deterministic rules.

    Pipeline:
      1. Separate subject, object, verb, and oblique arguments
      2. Apply word order (SOV primary)
      3. Add definite article (i) if needed
      4. Add coordinating particles (ar) if needed
      5. Position oblique arguments
      6. Handle copula (may be omitted)

    Args:
        ir: semantic IR with predicate and arguments
        morphed_forms: pre-computed word forms (Layer 2.5)

    Returns:
        SyntaxResult with fully assembled sentence and metadata
    """
    # --- Partition forms by role ---
    subject_forms = []
    object_forms = []
    verb_form = None
    oblique_forms = []  # location, direction, instrument, etc.

    # Last form is always the verb (added by compute_all_forms)
    if morphed_forms:
        verb_form = morphed_forms[-1]
        noun_forms = morphed_forms[:-1]
    else:
        return SyntaxResult(
            quenya_sentence="",
            word_order_rule="error: no forms",
            particles_added=[],
            confidence=0.0,
            notes="No morphed forms provided",
        )

    # Map forms back to arguments by matching English lemmas
    form_to_arg = {}
    for i, arg in enumerate(ir.arguments):
        if i < len(noun_forms):
            form_to_arg[noun_forms[i].english_lemma] = arg

    for form in noun_forms:
        arg = form_to_arg.get(form.english_lemma)
        if not arg:
            continue

        if arg.role == "agent":
            subject_forms.append(form)
        elif arg.role == "patient":
            object_forms.append(form)
        else:  # location, direction, instrument, etc.
            oblique_forms.append((arg, form))

    # --- Choose word order pattern ---
    # Primary: SOV (Subject-Object-Verb)
    # Fallback: VSO if no clear subject
    word_order = "SOV" if subject_forms else "VSO"

    # --- Assemble main clause ---
    particles = []

    if word_order == "SOV":
        parts = []

        # Subject (nominative)
        for form in subject_forms:
            # Add definite article "i" before subject
            if not form.quenya_form.startswith("["):
                parts.append("i")
                parts.append(form.quenya_form)
                particles.append("i (def. article before subject)")

        # Object (accusative)
        for form in object_forms:
            if not form.quenya_form.startswith("["):
                parts.append(form.quenya_form)

        # Verb
        if verb_form and not verb_form.quenya_form.startswith("["):
            parts.append(verb_form.quenya_form)

    else:  # VSO
        parts = []

        # Verb
        if verb_form and not verb_form.quenya_form.startswith("["):
            parts.append(verb_form.quenya_form)

        # Subject
        for form in subject_forms:
            if not form.quenya_form.startswith("["):
                parts.append(form.quenya_form)

        # Object
        for form in object_forms:
            if not form.quenya_form.startswith("["):
                parts.append(form.quenya_form)

    # --- Oblique arguments (typically after verb) ---
    for arg, form in oblique_forms:
        if not form.quenya_form.startswith("["):
            # Oblique arguments keep their case marking (locative, allative, etc.)
            parts.append(form.quenya_form)

    # --- Join and clean ---
    sentence = " ".join(p for p in parts if p)

    # --- Confidence: based on form confidence ---
    valid_confs = [f.confidence for f in morphed_forms if f.confidence > 0]
    confidence = min(valid_confs) if valid_confs else 0.5

    return SyntaxResult(
        quenya_sentence=sentence,
        word_order_rule=word_order,
        particles_added=particles,
        confidence=confidence,
        notes=f"Applied {word_order} word order with {len(particles)} particle(s)",
    )


def add_stylistic_polish(ir: SemanticIR, syntax_result: SyntaxResult, llm_response: Optional[str] = None) -> str:
    """Apply stylistic register adjustments to the assembled sentence.

    If LLM response is provided, extract any adjustments it suggests.
    Otherwise, apply basic register rules:
      - Elevated/poetic tone for formal contexts
      - Remove redundant articles
      - Invert word order for dramatic effect (optional)

    Args:
        ir: semantic IR (for context)
        syntax_result: the deterministically assembled sentence
        llm_response: optional LLM response with stylistic suggestions

    Returns:
        Final Quenya sentence with stylistic polish
    """
    sentence = syntax_result.quenya_sentence

    if llm_response:
        # Extract any suggested adjustments from LLM (if it provides them)
        # For now, we just use the deterministic assembly
        pass

    # Basic register rules:
    # - Keep definite articles as-is (they're intentional)
    # - No further polishing without explicit instruction

    return sentence


# ---------------------------------------------------------------------------
# Particle insertion rules
# ---------------------------------------------------------------------------

def should_add_definite_article(arg: Argument) -> bool:
    """Determine if a definite article (i) should precede this argument."""
    # Proper nouns don't usually take the article
    if arg.is_proper:
        return False
    # Heuristic: add "i" before subject agents
    if arg.role == "agent" and arg.case == "nominative":
        return True
    return False


def should_add_conjunction(arg1: Argument, arg2: Argument) -> str:
    """Return conjunction particle if needed between two arguments."""
    # If both are objects or both are subjects, could add "ar" (and)
    # For now, minimal conjunction logic
    return ""  # TODO: implement more sophisticated coordination


# ---------------------------------------------------------------------------
# Copula handling
# ---------------------------------------------------------------------------

def is_copula_verb(lemma: str) -> bool:
    """Check if the verb is 'to be' (copula)."""
    return lemma.lower() in ("be", "na", "nar")  # English + Quenya forms


def should_omit_copula(ir: SemanticIR) -> bool:
    """Determine if the copula should be omitted in Quenya."""
    if not is_copula_verb(ir.predicate.lemma):
        return False

    # Quenya often omits the copula in declarative mood
    if ir.predicate.mood == "declarative":
        return True

    return False


# ---------------------------------------------------------------------------
# Adjective positioning (simplified)
# ---------------------------------------------------------------------------

def needs_adjective_agreement(ir: SemanticIR) -> list[tuple[str, str]]:
    """Identify adjectives that need agreement with nouns.

    Returns list of (adjective, target_noun) pairs that need inflection.
    (Simplified: not yet implemented in full)
    """
    # TODO: implement adjective parsing from IR
    return []
