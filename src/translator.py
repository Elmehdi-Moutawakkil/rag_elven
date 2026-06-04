"""
Full translation pipeline — English → Quenya sentence translation

Pipeline:
  1. Layer 1 (ir.py)         : parse English → SemanticIR
  2. Layer 2 (morphology.py) : compute Quenya word forms deterministically
  3. Layer 3 (syntax.py)     : assemble forms into Quenya sentence
  4. Layer 4 (LLM optional)  : stylistic polish only (no morphology recomputation)

The LLM's job (Layer 4) is ONLY:
  - stylistic register adjustment
  - optional poetic word order for dramatic effect
  - does NOT compute morphology or change case endings

All morphology is computed deterministically in Layer 2.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

from src.ir import SemanticIR, parse_english
from src.morphology import MorphResult, ConfidenceLevel, compute_noun_form, compute_verb_form
from src.syntax import realize_syntax, add_stylistic_polish, SyntaxResult

load_dotenv()

# ---------------------------------------------------------------------------
# Translation result
# ---------------------------------------------------------------------------

@dataclass
class TranslationResult:
    """The output of a full English → Quenya translation."""
    english_sentence: str
    quenya_sentence: str         # the final Quenya output
    morphed_forms: list[MorphResult]  # all pre-computed word forms (Layer 2)
    explanation: str             # explanation of choices made
    confidence_floor: ConfidenceLevel  # worst confidence level across all forms
    llm_used: bool               # True if LLM was called, False if fallback assembly
    warning: str = ""            # set if any forms had confidence=LOW


# ---------------------------------------------------------------------------
# Morphological computation from IR  (Layer 2 applied to full sentence)
# ---------------------------------------------------------------------------

def compute_all_forms(ir: SemanticIR) -> list[MorphResult]:
    """Compute Quenya word forms for every argument and the predicate.

    Processes:
      - Each argument noun (using its case and number from the IR)
      - The main verb (using tense, number, mood from the IR)

    Args:
        ir: SemanticIR produced by Layer 1

    Returns:
        List of MorphResult, one per word to be inflected
    """
    forms: list[MorphResult] = []

    # --- Nouns (arguments) ---
    for arg in ir.arguments:
        if arg.is_proper:
            # Proper nouns: transliterate rather than translate
            # Use nominative/bare form and flag it
            result = MorphResult(
                english_lemma=arg.lemma,
                quenya_lemma=arg.lemma,
                quenya_form=arg.lemma.capitalize(),  # keep as-is, capitalized
                feature=f"{arg.case} {arg.number} (proper noun — transliterated)",
                confidence_level=ConfidenceLevel.MEDIUM,
                source_note="proper nouns kept in original form",
                warning="proper noun: Quenya form may differ in attested texts",
            )
        else:
            result = compute_noun_form(arg.lemma, arg.case, arg.number)
        forms.append(result)

    # --- Verb (predicate) ---
    verb_result = compute_verb_form(
        ir.predicate.lemma,
        ir.predicate.tense,
        ir.predicate.number,
        ir.predicate.mood,
    )
    forms.append(verb_result)

    return forms


# ---------------------------------------------------------------------------
# LLM prompt construction  (Layer 4)
# ---------------------------------------------------------------------------

def build_translation_prompt(ir: SemanticIR, forms: list[MorphResult], syntax_result: SyntaxResult) -> str:
    """Build the prompt for Layer 4: stylistic polish only.

    The syntax layer (Layer 3) has already assembled the sentence deterministically.
    The LLM's ONLY job is stylistic register adjustment, NOT arrangement or morphology.

    Args:
        ir            : semantic representation of the source sentence
        forms         : pre-computed Quenya word forms from Layer 2
        syntax_result : pre-assembled Quenya sentence from Layer 3
    """
    # Format each computed form with confidence level
    form_lines = []
    for f in forms:
        confidence_badge = {
            ConfidenceLevel.HIGH: "🟢",
            ConfidenceLevel.MEDIUM: "🟡",
            ConfidenceLevel.LOW: "🔴",
        }.get(f.confidence_level, "⚪")
        line = f"  {confidence_badge} {f.quenya_form:15s} ← {f.english_lemma} ({f.feature})"
        if f.rule_id:
            line += f" [{f.rule_id}]"
        if f.warning:
            line += f"\n    ⚠️  {f.warning}"
        form_lines.append(line)
    forms_text = "\n".join(form_lines)

    # Worst confidence across all forms
    conf_levels = [f.confidence_level for f in forms]
    if ConfidenceLevel.LOW in conf_levels:
        conf_floor_text = "🔴 LOW"
    elif ConfidenceLevel.MEDIUM in conf_levels:
        conf_floor_text = "🟡 MEDIUM"
    else:
        conf_floor_text = "🟢 HIGH"

    return f"""You are an expert in Quenya stylistics, the High Elven language created by J.R.R. Tolkien.

The deterministic syntax engine (Layer 3) has ALREADY ASSEMBLED a Quenya sentence below.
The morphological engine (Layer 2) has already computed all word forms.

YOUR JOB IS ONLY TO REVIEW FOR STYLE:
  1. Check if the pre-assembled sentence reads well in Tolkienian register.
  2. Make ONLY stylistic improvements (word order for drama, poetic tone, etc.)
     — DO NOT change case endings or inflections.
  3. If something seems off, describe the issue (don't rewrite it).
  4. Briefly explain what you kept or adjusted, or "kept as-is" if it's already good.

DO NOT:
  - Recompute inflections or change case endings — those were computed in Layer 2.
  - Rearrange word order unless it serves poetic effect (rare).
  - Invent words not in the pre-computed forms below.

═══════════════════════════════════════════════════
ORIGINAL ENGLISH: {ir.raw_sentence}

PRE-ASSEMBLED QUENYA (from deterministic Layer 3):
  {syntax_result.quenya_sentence}

PRE-COMPUTED FORMS (reference only, from Layer 2):
{forms_text}

ASSEMBLY METADATA:
  Word order pattern: {syntax_result.word_order_rule}
  Particles added: {', '.join(syntax_result.particles_added) if syntax_result.particles_added else '(none)'}
  Lowest confidence level: {conf_floor_text}
═══════════════════════════════════════════════════

Respond in this exact format:
QUENYA: [final Quenya sentence]
POLISH: [your stylistic notes, or "kept as-is" if assembly is good]
"""


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _call_llm(prompt: str) -> str:
    """Call the configured LLM. Tries Groq first, then LM Studio (local), then fails gracefully."""

    # --- Try Groq ---
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            from groq import Groq  # type: ignore
            client = Groq(api_key=groq_key)
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
                temperature=0.4,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            # Fall through to LM Studio
            pass

    # --- Try LM Studio (local OpenAI-compatible server) ---
    try:
        import openai  # type: ignore
        client = openai.OpenAI(
            base_url="http://localhost:1234/v1",
            api_key="lm-studio",  # LM Studio ignores the key value
        )
        response = client.chat.completions.create(
            model="local-model",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        pass

    # --- No LLM available: return None so caller can fallback ---
    return ""


# ---------------------------------------------------------------------------
# Fallback: assemble sentence without LLM
# ---------------------------------------------------------------------------

def _assemble_without_llm(ir: SemanticIR, forms: list[MorphResult]) -> str:
    """Minimal assembly when no LLM is available.

    Arranges forms in Subject-Verb-Object order with no stylistic polishing.
    Good enough to show the morphological forms are working.
    """
    # Separate verb from noun forms
    noun_forms = forms[:-1]  # all but last
    verb_form  = forms[-1]   # verb is always added last by compute_all_forms

    # Group by role
    agents   = [f for f, a in zip(noun_forms, ir.arguments) if a.role == "agent"]
    patients = [f for f, a in zip(noun_forms, ir.arguments) if a.role == "patient"]
    others   = [f for f, a in zip(noun_forms, ir.arguments)
                if a.role not in ("agent", "patient")]

    parts = (
        [f.quenya_form for f in agents]
        + [verb_form.quenya_form]
        + [f.quenya_form for f in patients]
        + [f.quenya_form for f in others]
    )
    return " ".join(p for p in parts if p and not p.startswith("["))


# ---------------------------------------------------------------------------
# IR quality validation (before we touch the LLM)
# ---------------------------------------------------------------------------

def _validate_ir(ir: SemanticIR, sentence: str) -> str:
    """Check that the parsed IR is usable for translation.

    Returns an actionable error message if the IR is too broken to translate,
    or an empty string if everything looks fine.

    Failure signals:
      1. Predicate fell back to "be" AND no arguments — spaCy found no verb
         root. Almost always caused by a grammatical error in the English input.
      2. No arguments at all for a sentence long enough to have a subject —
         spaCy couldn't attach any noun phrase to the verb.
    """
    words = sentence.split()

    # Signal 1: full parsing failure (our fallback IR with lemma="be", args=[])
    if ir.predicate.lemma == "be" and not ir.arguments and len(words) > 3:
        hint = _guess_grammar_fix(sentence)
        return (
            "Could not parse the sentence structure. "
            "spaCy needs grammatically correct English to extract the subject, "
            f"verb and objects.\n{hint}"
        )

    # Signal 2: verb found but nothing attached (no subject, no object)
    if not ir.arguments and len(words) > 4:
        return (
            "Parsed the verb but could not find any subject or object. "
            "Try a clearer sentence structure, e.g. "
            "\"The warrior walks into the forest.\""
        )

    return ""   # IR looks usable


def _guess_grammar_fix(sentence: str) -> str:
    """Try to detect the most common English grammar error and suggest a fix.

    Most frequent cause: missing 3rd-person singular -s on the main verb
    (e.g. "The warrior walk" → "The warrior walks").
    """
    import re

    # Pattern: singular noun + bare verb (no -s, -ed, -ing)
    # e.g. "The warrior walk", "The king speak"
    m = re.search(
        r'\b(the\s+\w+)\s+([a-z]+(?<!s)(?<!ed)(?<!ing))\b',
        sentence,
        re.IGNORECASE,
    )
    if m:
        subject = m.group(1)
        verb    = m.group(2).lower()
        # Only suggest if it looks like a real verb (not a preposition/article)
        skip = {"in", "on", "at", "to", "a", "an", "the", "of", "and", "or"}
        if verb not in skip:
            fixed_verb = verb + ("es" if verb.endswith(("ch","sh","x","z","o")) else "s")
            return (
                f"Likely fix: \"{subject} **{fixed_verb}**...\" "
                f"('{verb}' → '{fixed_verb}' for a singular subject)"
            )

    return "Check verb conjugation and sentence structure."


# ---------------------------------------------------------------------------
# Main translation function
# ---------------------------------------------------------------------------

def translate(english_sentence: str) -> TranslationResult:
    """Translate an English sentence to Quenya using the full 4-layer pipeline.

    Layer 1 — parse English into SemanticIR
    Layer 2 — compute Quenya word forms deterministically
    Layer 3 — deterministic syntax: word order, particles, arrangement
    Layer 4 — LLM applies stylistic polish ONLY (optional)

    Args:
        english_sentence: any English sentence

    Returns:
        TranslationResult with the Quenya sentence and metadata.
        If IR validation fails, quenya_sentence is empty and warning explains why.
    """
    # --- Layer 1: parse ---
    ir = parse_english(english_sentence)

    # --- IR quality gate: stop here if parsing failed ---
    parse_error = _validate_ir(ir, english_sentence)
    if parse_error:
        return TranslationResult(
            english_sentence=english_sentence,
            quenya_sentence="",
            morphed_forms=[],
            explanation="",
            confidence_floor=0.0,
            llm_used=False,
            warning=parse_error,
        )

    # --- Layer 2: compute morphological forms ---
    forms = compute_all_forms(ir)

    # --- Confidence summary ---
    conf_levels    = [f.confidence_level for f in forms]
    missing_forms  = [f for f in forms if f.confidence_level == ConfidenceLevel.LOW and f.quenya_form.startswith("[")]

    if ConfidenceLevel.LOW in conf_levels:
        conf_floor = ConfidenceLevel.LOW
    elif ConfidenceLevel.MEDIUM in conf_levels:
        conf_floor = ConfidenceLevel.MEDIUM
    else:
        conf_floor = ConfidenceLevel.HIGH

    warning = (
        f"{len(missing_forms)} word(s) not in dictionary: "
        + ", ".join(f.english_lemma for f in missing_forms)
        if missing_forms else ""
    )

    # --- Layer 3: deterministic syntax assembly ---
    syntax_result = realize_syntax(ir, forms)

    # --- Layer 4: LLM stylistic polish (optional) ---
    prompt   = build_translation_prompt(ir, forms, syntax_result)
    llm_resp = _call_llm(prompt)

    if llm_resp:
        # Parse the structured LLM response
        quenya_sentence = _extract_field(llm_resp, "QUENYA")
        explanation     = _extract_field(llm_resp, "POLISH")
        if not explanation:
            explanation = _extract_field(llm_resp, "EXPLANATION")
        llm_used = True
    else:
        # No LLM available: use deterministic assembly as-is
        quenya_sentence = syntax_result.quenya_sentence
        explanation     = (
            f"Deterministic assembly (Layer 3): {syntax_result.word_order_rule} order. "
            f"No LLM available for stylistic polish."
        )
        llm_used = False

    return TranslationResult(
        english_sentence=english_sentence,
        quenya_sentence=quenya_sentence or syntax_result.quenya_sentence,
        morphed_forms=forms,
        explanation=explanation,
        confidence_floor=conf_floor,
        llm_used=llm_used,
        warning=warning,
    )


def _extract_field(text: str, field: str) -> str:
    """Extract a field value from the structured LLM response.

    Looks for lines starting with "FIELD:" and returns the rest.
    """
    for line in text.splitlines():
        if line.strip().startswith(f"{field}:"):
            return line.split(":", 1)[1].strip()
    return ""


# ---------------------------------------------------------------------------
# Standalone test  (requires DB + spaCy)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_sentences = [
        "The warriors walk into the city.",
        "A star shines in the dark forest.",
        "The king speaks to the elf.",
    ]
    for sent in test_sentences:
        print(f"\nInput : {sent}")
        try:
            result = translate(sent)
            print(f"Quenya: {result.quenya_sentence}")
            conf_badge = "🟢 HIGH" if result.confidence_floor == ConfidenceLevel.HIGH else \
                        "🟡 MEDIUM" if result.confidence_floor == ConfidenceLevel.MEDIUM else "🔴 LOW"
            print(f"Confidence floor: {conf_badge}")
            if result.warning:
                print(f"⚠️  {result.warning}")
            print("Forms:")
            for f in result.morphed_forms:
                conf_badge = "🟢" if f.confidence_level == ConfidenceLevel.HIGH else \
                            "🟡" if f.confidence_level == ConfidenceLevel.MEDIUM else "🔴"
                mark = "⚠️" if not f.is_reliable() else conf_badge
                rule_note = f" [{f.rule_id}]" if f.rule_id else ""
                print(f"  {mark} {f.english_lemma:10s} → {f.quenya_form} ({f.feature}){rule_note}")
        except Exception as e:
            print(f"  Error: {e}")
