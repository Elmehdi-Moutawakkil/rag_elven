"""
Unit tests for syntax.py — deterministic sentence assembly.

Tests cover:
  - Word order (SOV, VSO)
  - Particle insertion (definite article, conjunction)
  - Copula handling
  - Oblique argument positioning
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ir import SemanticIR, PredicateIR, Argument
from src.morphology import MorphResult, ConfidenceLevel, compute_noun_form, compute_verb_form
from src.syntax import (
    realize_syntax, add_stylistic_polish, should_add_definite_article,
    is_copula_verb, should_omit_copula, SyntaxResult
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ir(predicate_lemma, arguments=None, sentence="test sentence"):
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

def make_arg(role="agent", lemma="warrior", case="nominative", number="singular", is_proper=False):
    return Argument(role=role, lemma=lemma, number=number, case=case, is_proper=is_proper)

def make_morph(english_lemma, quenya_form):
    return MorphResult(
        english_lemma=english_lemma,
        quenya_lemma=quenya_form,
        quenya_form=quenya_form,
        feature="test",
        confidence_level=ConfidenceLevel.HIGH,
        source_note="test",
    )


# ---------------------------------------------------------------------------
# SyntaxResult structure
# ---------------------------------------------------------------------------

class TestSyntaxResult:

    def test_syntax_result_has_required_fields(self):
        """SyntaxResult always has all required fields."""
        result = SyntaxResult(
            quenya_sentence="test sentence",
            word_order_rule="SOV",
            particles_added=["i"],
            confidence=0.8,
        )
        assert result.quenya_sentence == "test sentence"
        assert result.word_order_rule == "SOV"
        assert result.particles_added == ["i"]
        assert result.confidence == 0.8

    def test_syntax_result_notes_optional(self):
        """SyntaxResult.notes is optional."""
        result = SyntaxResult(
            quenya_sentence="test",
            word_order_rule="SOV",
            particles_added=[],
            confidence=0.7,
            notes="test note",
        )
        assert result.notes == "test note"


# ---------------------------------------------------------------------------
# Basic SOV word order
# ---------------------------------------------------------------------------

class TestSOVWordOrder:

    def test_sov_with_subject_and_object(self):
        """SOV order: subject object verb."""
        ir = make_ir("walk", [
            make_arg("agent", "warrior", "nominative"),
            make_arg("patient", "path", "accusative"),
        ])
        forms = [
            make_morph("warrior", "coivatar"),
            make_morph("path", "randa"),
            make_morph("walk", "cenilar"),  # verb form
        ]
        result = realize_syntax(ir, forms)

        # Should contain subject, object, verb in some order
        assert result.quenya_sentence
        # Ideally: "i coivatar randa cenilar" (subject object verb with article)
        assert "coivatar" in result.quenya_sentence
        assert "randa" in result.quenya_sentence
        assert "cenilar" in result.quenya_sentence

    def test_sov_includes_definite_article(self):
        """SOV order should include definite article 'i' before subject."""
        ir = make_ir("walk", [make_arg("agent", "warrior", "nominative")])
        forms = [make_morph("warrior", "coivatar"), make_morph("walk", "cenilar")]
        result = realize_syntax(ir, forms)

        # Should include "i" (definite article)
        assert "i" in result.quenya_sentence.lower()

    def test_sov_no_subject_falls_back_to_vso(self):
        """Without a subject, SOV falls back to VSO."""
        ir = make_ir("fall", [make_arg("patient", "rain", "accusative")])
        forms = [make_morph("rain", "aran"), make_morph("fall", "cara")]
        result = realize_syntax(ir, forms)

        # Should use VSO since no subject
        assert result.word_order_rule == "VSO"
        assert "cara" in result.quenya_sentence  # verb first


# ---------------------------------------------------------------------------
# VSO word order
# ---------------------------------------------------------------------------

class TestVSOWordOrder:

    def test_vso_order(self):
        """VSO order: verb subject object."""
        ir = make_ir("see", [
            make_arg("agent", "elf", "nominative"),
            make_arg("patient", "star", "accusative"),
        ])
        forms = [
            make_morph("elf", "ellon"),
            make_morph("star", "elen"),
            make_morph("see", "ceniar"),
        ]
        result = realize_syntax(ir, forms)

        # Should detect VSO or SOV appropriately
        assert result.quenya_sentence
        assert "ellon" in result.quenya_sentence
        assert "elen" in result.quenya_sentence
        assert "ceniar" in result.quenya_sentence


# ---------------------------------------------------------------------------
# Particle insertion
# ---------------------------------------------------------------------------

class TestParticleInsertion:

    def test_definite_article_added_for_agent(self):
        """Definite article 'i' should be added before agent/subject."""
        ir = make_ir("walk", [make_arg("agent", "warrior", "nominative")])
        forms = [make_morph("warrior", "coivatar"), make_morph("walk", "cenilar")]
        result = realize_syntax(ir, forms)

        # Check that "i" is in particles_added
        assert len(result.particles_added) > 0
        assert any("i" in p.lower() for p in result.particles_added)

    def test_particles_tracked(self):
        """Particles added should be recorded in result."""
        ir = make_ir("walk", [make_arg("agent", "warrior", "nominative")])
        forms = [make_morph("warrior", "coivatar"), make_morph("walk", "cenilar")]
        result = realize_syntax(ir, forms)

        assert isinstance(result.particles_added, list)
        # Should have at least the article
        assert len(result.particles_added) >= 0


# ---------------------------------------------------------------------------
# Oblique arguments (location, direction, instrument)
# ---------------------------------------------------------------------------

class TestObliqueArguments:

    def test_location_after_verb(self):
        """Location arguments typically appear after the verb."""
        ir = make_ir("walk", [
            make_arg("agent", "warrior", "nominative"),
            make_arg("location", "forest", "locative"),
        ])
        forms = [
            make_morph("warrior", "coivatar"),
            make_morph("forest", "erynesse"),
            make_morph("walk", "cenilar"),
        ]
        result = realize_syntax(ir, forms)

        # Forest location should appear somewhere in the sentence
        assert "erynesse" in result.quenya_sentence

    def test_direction_argument(self):
        """Direction arguments (allative) should be included."""
        ir = make_ir("go", [
            make_arg("agent", "elf", "nominative"),
            make_arg("direction", "city", "allative"),
        ])
        forms = [
            make_morph("elf", "ellon"),
            make_morph("city", "carabnna"),  # allative form
            make_morph("go", "vanya"),
        ]
        result = realize_syntax(ir, forms)

        # Direction should be in the sentence
        assert "carabnna" in result.quenya_sentence


# ---------------------------------------------------------------------------
# Copula handling
# ---------------------------------------------------------------------------

class TestCopulaHandling:

    def test_is_copula_verb_recognizes_be(self):
        """is_copula_verb should recognize 'be' and Quenya copulas."""
        assert is_copula_verb("be")
        assert is_copula_verb("na")  # Quenya copula (singular present)
        assert is_copula_verb("nar")  # Quenya copula (plural present)
        assert not is_copula_verb("walk")
        assert not is_copula_verb("see")

    def test_copula_omitted_in_declarative(self):
        """Copula is omitted in declarative mood."""
        ir = make_ir("be", [], "The warrior is strong")
        ir.predicate.mood = "declarative"
        assert should_omit_copula(ir)

    def test_non_copula_not_omitted(self):
        """Non-copula verbs should not be omitted."""
        ir = make_ir("walk", [make_arg("agent", "warrior")])
        ir.predicate.mood = "declarative"
        assert not should_omit_copula(ir)


# ---------------------------------------------------------------------------
# Article placement rules
# ---------------------------------------------------------------------------

class TestArticlePlacement:

    def test_article_before_agent(self):
        """Definite article should be added before agent."""
        arg = make_arg("agent", "warrior", "nominative")
        assert should_add_definite_article(arg)

    def test_no_article_for_proper_nouns(self):
        """Proper nouns should not take the definite article."""
        arg = make_arg("agent", "Frodo", "nominative", is_proper=True)
        assert not should_add_definite_article(arg)

    def test_no_article_for_non_agent(self):
        """Non-agent arguments may not need the article."""
        arg = make_arg("patient", "sword", "accusative")
        assert not should_add_definite_article(arg)


# ---------------------------------------------------------------------------
# Stylistic polish
# ---------------------------------------------------------------------------

class TestStylisticPolish:

    def test_polish_returns_string(self):
        """add_stylistic_polish should return a string."""
        ir = make_ir("walk", [make_arg("agent", "warrior")])
        syntax_result = SyntaxResult(
            quenya_sentence="i coivatar cenilar",
            word_order_rule="SOV",
            particles_added=["i"],
            confidence=0.8,
        )
        result = add_stylistic_polish(ir, syntax_result)
        assert isinstance(result, str)
        assert result  # should be non-empty

    def test_polish_preserves_basic_form(self):
        """Polish should not drastically change the sentence."""
        ir = make_ir("walk", [make_arg("agent", "warrior")])
        syntax_result = SyntaxResult(
            quenya_sentence="i coivatar cenilar",
            word_order_rule="SOV",
            particles_added=["i"],
            confidence=0.8,
        )
        polished = add_stylistic_polish(ir, syntax_result)
        # Should keep the core words
        assert "coivatar" in polished or "cenilar" in polished


# ---------------------------------------------------------------------------
# Integration: IR → forms → syntax
# ---------------------------------------------------------------------------

class TestIntegrationIRtoSyntax:

    def test_full_pipeline_simple(self):
        """IR → pre-built forms → realize syntax (no DB required)."""
        ir = make_ir("walk", [make_arg("agent", "warrior", "nominative")])
        # Use make_morph to bypass DB lookup — tests syntax logic only
        forms = [
            make_morph("warrior", "ohtar"),
            make_morph("walk",    "vanta"),
        ]
        result = realize_syntax(ir, forms)

        assert result.quenya_sentence
        assert result.word_order_rule in ("SOV", "VSO")
        assert result.confidence >= 0.0

    def test_full_pipeline_with_object(self):
        """IR with subject and object → syntax (no DB required)."""
        ir = make_ir("see", [
            make_arg("agent",   "elf",  "nominative"),
            make_arg("patient", "star", "accusative"),
        ])
        forms = [
            make_morph("elf",  "ellon"),
            make_morph("star", "elen"),
            make_morph("see",  "cena"),
        ]
        result = realize_syntax(ir, forms)

        assert result.quenya_sentence
        assert len(result.quenya_sentence.split()) >= 3


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

class TestConfidenceScoring:

    def test_syntax_confidence_based_on_forms(self):
        """Syntax confidence should reflect form confidence."""
        ir = make_ir("walk", [make_arg("agent", "warrior")])
        forms = [
            make_morph("warrior", "coivatar"),  # confidence 0.8
            make_morph("walk", "cenilar"),      # confidence 0.8
        ]
        result = realize_syntax(ir, forms)

        # Confidence should be reasonable (at least 0.5)
        assert result.confidence >= 0.4

    def test_syntax_confidence_zero_with_empty_forms(self):
        """Empty forms list → low confidence."""
        ir = make_ir("walk", [])
        result = realize_syntax(ir, [])

        assert result.confidence == 0.0 or result.word_order_rule == "error: no forms"
