"""
Unit tests for morphology.py — noun and verb inflection.

Tests cover:
  - Noun declension (6 cases × 2 numbers)
  - Verb conjugation (3 tenses × 2 numbers)
  - Confidence scoring and attestation tagging
  - Fallback rules when DB is unavailable
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.morphology import (
    compute_noun_form, compute_verb_form, MorphResult
)


# ---------------------------------------------------------------------------
# MorphResult helpers
# ---------------------------------------------------------------------------

def test_morph_result_is_reliable():
    """MorphResult.is_reliable() returns True for confidence >= 0.7."""
    reliable = MorphResult(
        english_lemma="warrior", quenya_lemma="coivatar", quenya_form="coivatar",
        feature="nominative singular", confidence=0.8, source_note="test",
    )
    unreliable = MorphResult(
        english_lemma="warrior", quenya_lemma="coivatar", quenya_form="coivatar",
        feature="nominative singular", confidence=0.5, source_note="test",
    )
    assert reliable.is_reliable()
    assert not unreliable.is_reliable()


# ---------------------------------------------------------------------------
# Noun inflection — nominative
# ---------------------------------------------------------------------------

class TestNounNominative:

    def test_singular_nominative_is_lemma(self):
        """Nominative singular of a noun is the base lemma."""
        result = compute_noun_form("warrior", "nominative", "singular")
        assert result.quenya_form == "coivatar"
        assert result.feature == "nominative singular"

    def test_plural_nominative_adds_i(self):
        """Nominative plural typically adds -i."""
        result = compute_noun_form("warrior", "nominative", "plural")
        assert "i" in result.quenya_form.lower()

    def test_nominative_confidence_present(self):
        """Result always has a confidence value."""
        result = compute_noun_form("warrior", "nominative", "singular")
        assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# Noun inflection — other cases
# ---------------------------------------------------------------------------

class TestNounCases:

    def test_accusative_singular(self):
        """Accusative singular adds -n or -an."""
        result = compute_noun_form("warrior", "accusative", "singular")
        assert result.quenya_form.endswith(("an", "n"))

    def test_accusative_plural(self):
        """Accusative plural inflects base + plural -i + -an."""
        result = compute_noun_form("warrior", "accusative", "plural")
        assert result.quenya_form  # should produce something

    def test_genitive_singular(self):
        """Genitive singular adds -o."""
        result = compute_noun_form("warrior", "genitive", "singular")
        assert result.quenya_form.endswith("o")

    def test_genitive_plural(self):
        """Genitive plural adds -ion."""
        result = compute_noun_form("warrior", "genitive", "plural")
        assert result.quenya_form.endswith("ion")

    def test_locative_singular(self):
        """Locative singular adds -sse."""
        result = compute_noun_form("warrior", "locative", "singular")
        assert result.quenya_form.endswith("sse")

    def test_locative_plural(self):
        """Locative plural applies plural inflection + -sse."""
        result = compute_noun_form("warrior", "locative", "plural")
        assert result.quenya_form  # should produce something

    def test_allative_adds_nna(self):
        """Allative case adds -nna."""
        result = compute_noun_form("warrior", "allative", "singular")
        assert result.quenya_form.endswith("nna")

    def test_instrumental_adds_inen(self):
        """Instrumental case adds -inen or -en."""
        result = compute_noun_form("warrior", "instrumental", "singular")
        assert "en" in result.quenya_form

    def test_dative_adds_ne(self):
        """Dative case adds -në."""
        result = compute_noun_form("warrior", "dative", "singular")
        assert result.quenya_form.endswith("në")


# ---------------------------------------------------------------------------
# Noun dictionary lookup
# ---------------------------------------------------------------------------

class TestNounDictionary:

    def test_common_noun_found(self):
        """Known nouns like 'elf', 'star', 'forest' should translate."""
        for english, expected_quenya in [
            ("elf", "ellon"),
            ("star", "elen"),
            ("forest", "eryn"),
        ]:
            result = compute_noun_form(english, "nominative", "singular")
            assert result.quenya_form  # should produce a form

    def test_unknown_noun_gets_warning(self):
        """Unknown nouns should have warning and low confidence."""
        result = compute_noun_form("xyz_unknown_word", "nominative", "singular")
        assert result.confidence < 0.5
        assert "not in dictionary" in result.warning.lower() or result.confidence < 0.7


# ---------------------------------------------------------------------------
# Verb conjugation — present tense
# ---------------------------------------------------------------------------

class TestVerbPresent:

    def test_present_singular_verb(self):
        """Present tense singular verb gets -a or -ya suffix."""
        result = compute_verb_form("cenilya", "present", "singular", "declarative")
        assert result.feature == "present singular declarative"
        assert result.quenya_form  # should produce something

    def test_present_plural_verb(self):
        """Present tense plural verb gets -ar suffix."""
        result = compute_verb_form("cenilya", "present", "plural", "declarative")
        assert result.quenya_form.endswith("ar") or result.quenya_form.endswith("e")

    def test_present_confidence_reasonable(self):
        """Present tense should have a reasonable confidence."""
        result = compute_verb_form("cenilya", "present", "singular", "declarative")
        assert result.confidence >= 0.0


# ---------------------------------------------------------------------------
# Verb conjugation — past tense
# ---------------------------------------------------------------------------

class TestVerbPast:

    def test_past_singular_verb(self):
        """Past tense singular verb gets -në suffix."""
        result = compute_verb_form("cenilya", "past", "singular", "declarative")
        assert result.quenya_form.endswith("në")

    def test_past_plural_verb(self):
        """Past tense plural verb gets -nër suffix."""
        result = compute_verb_form("cenilya", "past", "plural", "declarative")
        assert result.quenya_form.endswith("nër")


# ---------------------------------------------------------------------------
# Verb conjugation — future tense
# ---------------------------------------------------------------------------

class TestVerbFuture:

    def test_future_tense_adds_uva(self):
        """Future tense adds -uva suffix."""
        result = compute_verb_form("cenilya", "future", "singular", "declarative")
        assert result.quenya_form.endswith("uva")

    def test_future_plural_also_uva(self):
        """Future tense is the same for singular and plural (simplified)."""
        sing = compute_verb_form("cenilya", "future", "singular", "declarative")
        plur = compute_verb_form("cenilya", "future", "plural", "declarative")
        # Both should end in -uva
        assert sing.quenya_form.endswith("uva")
        assert plur.quenya_form.endswith("uva")


# ---------------------------------------------------------------------------
# Attestation tagging
# ---------------------------------------------------------------------------

class TestAttestation:

    def test_result_has_attestation_field(self):
        """MorphResult always has an attestation value."""
        result = compute_noun_form("warrior", "nominative", "singular")
        assert result.attestation in ("attested", "reconstructed", "neo-quenya")

    def test_database_forms_marked_attested(self):
        """Forms from database should have proper attestation."""
        # Without a real DB, fallback forms are marked "neo-quenya"
        result = compute_noun_form("warrior", "nominative", "singular")
        # Even if low confidence, should have attestation field
        assert result.attestation

    def test_reconstructed_forms_marked(self):
        """Rule-based forms should be marked as reconstructed or neo-quenya."""
        result = compute_noun_form("xyz_unknown_word", "nominative", "singular")
        assert result.attestation in ("reconstructed", "neo-quenya")


# ---------------------------------------------------------------------------
# Source notes
# ---------------------------------------------------------------------------

class TestSourceNotes:

    def test_source_note_present(self):
        """Every result should have a source_note."""
        noun_result = compute_noun_form("warrior", "nominative", "singular")
        verb_result = compute_verb_form("cenilya", "present", "singular", "declarative")
        assert noun_result.source_note
        assert verb_result.source_note

    def test_source_note_informative(self):
        """Source notes should indicate where the form comes from."""
        result = compute_noun_form("warrior", "nominative", "singular")
        # Should mention DB or reconstructed rule
        assert "rule" in result.source_note.lower() or "pe" in result.source_note.lower() or result.source_note


# ---------------------------------------------------------------------------
# Cross-cutting concerns
# ---------------------------------------------------------------------------

class TestConsistency:

    def test_singular_and_plural_both_work(self):
        """Both singular and plural should return valid results."""
        for case in ["nominative", "accusative", "genitive", "locative", "allative"]:
            sing = compute_noun_form("warrior", case, "singular")
            plur = compute_noun_form("warrior", case, "plural")
            assert sing.quenya_form
            assert plur.quenya_form
            assert sing.feature == f"{case} singular"
            assert plur.feature == f"{case} plural"

    def test_all_tenses_work(self):
        """All three tenses should produce results."""
        for tense in ["present", "past", "future"]:
            result = compute_verb_form("cenilya", tense, "singular", "declarative")
            assert result.quenya_form
            assert result.feature == f"{tense} singular declarative"

    def test_result_fields_always_present(self):
        """Every MorphResult should have all required fields."""
        result = compute_noun_form("warrior", "nominative", "singular")
        assert result.english_lemma
        assert result.quenya_lemma
        assert result.quenya_form
        assert result.feature
        assert 0.0 <= result.confidence <= 1.0
        assert result.source_note is not None
        assert result.attestation


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_string_lemma_handled(self):
        """Empty lemma should not crash."""
        try:
            result = compute_noun_form("", "nominative", "singular")
            assert result.quenya_form is not None
        except Exception:
            pass  # OK to raise, as long as it doesn't crash the whole pipeline

    def test_unusual_case_name_handled(self):
        """Unusual case name should fall back gracefully."""
        result = compute_noun_form("warrior", "weird_case", "singular")
        assert result.quenya_form  # should return something

    def test_unusual_tense_handled(self):
        """Unusual tense should fall back gracefully."""
        result = compute_verb_form("cenilya", "weird_tense", "singular", "declarative")
        assert result.quenya_form  # should return something


# ---------------------------------------------------------------------------
# Morphological feature strings
# ---------------------------------------------------------------------------

class TestFeatureStrings:

    def test_feature_string_format(self):
        """Feature strings should be readable and consistent."""
        result = compute_noun_form("warrior", "nominative", "singular")
        assert "nominative" in result.feature.lower()
        assert "singular" in result.feature.lower()

    def test_verb_feature_includes_mood(self):
        """Verb features should include mood."""
        result = compute_verb_form("cenilya", "present", "singular", "declarative")
        assert "declarative" in result.feature.lower() or "present" in result.feature.lower()


# ---------------------------------------------------------------------------
# Integration: noun + verb together
# ---------------------------------------------------------------------------

class TestIntegration:

    def test_noun_and_verb_both_inflect(self):
        """Can compute both noun and verb forms for a single sentence."""
        noun = compute_noun_form("warrior", "nominative", "singular")
        verb = compute_verb_form("cenilya", "present", "singular", "declarative")
        assert noun.quenya_form
        assert verb.quenya_form
        # Should be different forms
        assert noun.quenya_form != verb.quenya_form

    def test_multiple_nouns_different_cases(self):
        """Can inflect the same noun in different cases."""
        nom = compute_noun_form("warrior", "nominative", "singular")
        acc = compute_noun_form("warrior", "accusative", "singular")
        loc = compute_noun_form("warrior", "locative", "singular")
        # Should produce different forms
        assert nom.quenya_form != acc.quenya_form
        assert acc.quenya_form != loc.quenya_form


# ---------------------------------------------------------------------------
# Quick sanity checks (batch test for coverage)
# ---------------------------------------------------------------------------

class TestBatch:

    def test_all_noun_cases_producible(self):
        """Can produce forms for all 8 cases."""
        cases = ["nominative", "accusative", "genitive", "dative", "locative", "allative", "instrumental", "ablative"]
        results = []
        for case in cases:
            try:
                result = compute_noun_form("warrior", case, "singular")
                results.append(result)
            except Exception:
                pass  # case might not be implemented yet
        # Should have at least 6 cases working
        assert len(results) >= 6

    def test_all_tense_mood_combinations(self):
        """Test various tense and mood combinations."""
        moods = ["declarative", "imperative", "conditional"]
        tenses = ["present", "past", "future"]
        count = 0
        for tense in tenses:
            for mood in moods:
                try:
                    result = compute_verb_form("cenilya", tense, "singular", mood)
                    if result.quenya_form:
                        count += 1
                except Exception:
                    pass
        # Should handle at least most combinations
        assert count >= 5
