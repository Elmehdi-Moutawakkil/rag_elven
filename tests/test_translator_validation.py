"""
Unit tests for translator.py — IR validation and grammar fix detection.

Tests are isolated: no DB, no spaCy, no LLM.
We build SemanticIR objects directly to test _validate_ir() and _guess_grammar_fix().
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ir import SemanticIR, PredicateIR, Argument
from src.translator import _validate_ir, _guess_grammar_fix


# ---------------------------------------------------------------------------
# Helpers to build IR fixtures without spaCy
# ---------------------------------------------------------------------------

def make_ir(predicate_lemma, arguments=None, sentence="test sentence with words"):
    return SemanticIR(
        predicate=PredicateIR(
            lemma=predicate_lemma,
            tense="present",
            mood="declarative",
            number="singular",
        ),
        arguments=arguments or [],
        raw_sentence=sentence,
    )

def make_arg(role="agent", lemma="warrior", case="nominative", number="singular"):
    return Argument(role=role, lemma=lemma, number=number, case=case)


# ---------------------------------------------------------------------------
# _validate_ir — failure cases
# ---------------------------------------------------------------------------

class TestValidateIR:

    def test_fallback_be_with_no_args_is_failure(self):
        """'be' + no arguments + long sentence = parsing failure."""
        ir = make_ir("be", arguments=[], sentence="The warrior walk in the forest")
        error = _validate_ir(ir, "The warrior walk in the forest")
        assert error != ""
        assert "parse" in error.lower() or "structure" in error.lower()

    def test_fallback_be_short_sentence_is_ok(self):
        """'be' + no args is acceptable for a very short sentence (≤3 words)."""
        ir = make_ir("be", arguments=[], sentence="He is")
        error = _validate_ir(ir, "He is")
        assert error == ""

    def test_real_verb_no_args_long_sentence_is_failure(self):
        """Verb found but no arguments attached for a long sentence."""
        ir = make_ir("walk", arguments=[], sentence="The warrior walks quickly into the forest")
        error = _validate_ir(ir, "The warrior walks quickly into the forest")
        assert error != ""

    def test_real_verb_no_args_short_sentence_is_ok(self):
        """Verb with no args is fine for a short sentence (≤4 words)."""
        ir = make_ir("walk", arguments=[], sentence="He walks fast")
        error = _validate_ir(ir, "He walks fast")
        assert error == ""

    def test_valid_ir_passes(self):
        """A properly parsed IR with subject and verb clears validation."""
        args = [make_arg("agent", "warrior", "nominative", "singular")]
        ir = make_ir("walk", arguments=args, sentence="The warrior walks")
        error = _validate_ir(ir, "The warrior walks")
        assert error == ""

    def test_valid_ir_with_location_passes(self):
        """Subject + verb + location passes."""
        args = [
            make_arg("agent",    "warrior", "nominative", "plural"),
            make_arg("location", "forest",  "locative",   "singular"),
        ]
        ir = make_ir("walk", arguments=args, sentence="The warriors walk in the forest")
        error = _validate_ir(ir, "The warriors walk in the forest")
        assert error == ""


# ---------------------------------------------------------------------------
# _validate_ir — error message content
# ---------------------------------------------------------------------------

class TestValidateIRMessage:

    def test_error_is_actionable(self):
        """Error message should contain a suggestion, not just say 'error'."""
        ir = make_ir("be", arguments=[], sentence="The warrior walk in the forest")
        error = _validate_ir(ir, "The warrior walk in the forest")
        # Must contain something useful, not just a bare error code
        assert len(error) > 20

    def test_error_contains_hint(self):
        """Error for 'be' fallback should mention grammar or structure."""
        ir = make_ir("be", arguments=[], sentence="The warrior walk in the forest")
        error = _validate_ir(ir, "The warrior walk in the forest")
        lower = error.lower()
        assert any(word in lower for word in ("grammar", "english", "structure", "verb", "subject"))


# ---------------------------------------------------------------------------
# _guess_grammar_fix
# ---------------------------------------------------------------------------

class TestGuessGrammarFix:

    def test_singular_verb_missing_s(self):
        """'The warrior walk' → suggests 'walks'."""
        hint = _guess_grammar_fix("The warrior walk in the forest")
        assert "walk" in hint.lower()
        assert "walks" in hint.lower()

    def test_singular_verb_missing_es(self):
        """Verbs ending in -ch/-sh/-x get -es."""
        hint = _guess_grammar_fix("The king watch the stars")
        assert "watches" in hint.lower()

    def test_plural_subject_no_suggestion(self):
        """'The warriors walk' is grammatically correct — no strong suggestion needed."""
        # We just check it doesn't crash and returns a string
        hint = _guess_grammar_fix("The warriors walk in the forest")
        assert isinstance(hint, str)

    def test_always_returns_string(self):
        """Never raises — always returns a string."""
        for sentence in [
            "Hello",
            "",
            "???",
            "The king",
            "walk walk walk",
        ]:
            result = _guess_grammar_fix(sentence)
            assert isinstance(result, str)
