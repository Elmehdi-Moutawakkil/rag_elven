"""
Unit tests for morphology.py — Quenya declension and conjugation engine.

Tests are isolated: no DB, no spaCy, no LLM.
We call decline_noun() and conjugate_verb() directly with Quenya lemmas.

Attested forms verified against:
  - PE XVII (Parma Eldalamberon XVII)
  - Tolkien's Quenya grammar notes
  - LotR Appendix E

compute_noun_form() and compute_verb_form() are tested with a mocked lookup
so they don't require the SQLite vocabulary database to be present.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
from src.morphology import (
    MorphResult,
    classify_stem,
    classify_verb,
    decline_noun,
    conjugate_verb,
    compute_noun_form,
    compute_verb_form,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def check(result: MorphResult, expected_form: str, min_conf: float = 0.70):
    """Assert that the result has the expected form and meets the confidence floor."""
    assert result.quenya_form == expected_form, (
        f"Expected '{expected_form}', got '{result.quenya_form}' "
        f"(feature: {result.feature}, source: {result.source_note})"
    )
    assert result.confidence >= min_conf, (
        f"Confidence {result.confidence:.2f} below minimum {min_conf} "
        f"for form '{result.quenya_form}'"
    )


# ---------------------------------------------------------------------------
# TestClassifyStem
# ---------------------------------------------------------------------------

class TestClassifyStem:

    def test_a_stem_short(self):
        assert classify_stem("cirya") == "a_stem"

    def test_a_stem_vanda(self):
        assert classify_stem("vanda") == "a_stem"

    def test_e_stem_lasse(self):
        assert classify_stem("lassë") == "e_stem"

    def test_e_stem_taure(self):
        assert classify_stem("taurë") == "e_stem"

    def test_o_stem(self):
        assert classify_stem("osto") == "o_stem"

    def test_consonantal_ohtar(self):
        assert classify_stem("ohtar") == "consonantal"

    def test_consonantal_elen(self):
        assert classify_stem("elen") == "consonantal"

    def test_consonantal_aran(self):
        assert classify_stem("aran") == "consonantal"

    def test_i_stem(self):
        assert classify_stem("calli") == "i_stem"

    def test_u_stem_long(self):
        assert classify_stem("lú") == "u_stem"

    def test_u_stem_plain(self):
        assert classify_stem("nuru") == "u_stem"

    def test_empty_string(self):
        assert classify_stem("") == "consonantal"

    def test_long_vowel_e_stem(self):
        assert classify_stem("nórë") == "e_stem"


# ---------------------------------------------------------------------------
# TestClassifyVerb
# ---------------------------------------------------------------------------

class TestClassifyVerb:

    def test_a_verb_vanta(self):
        assert classify_verb("vanta") == "a_verb"

    def test_a_verb_orta(self):
        assert classify_verb("orta") == "a_verb"

    def test_ya_verb_orya(self):
        assert classify_verb("orya") == "ya_verb"

    def test_ya_verb_lelya(self):
        assert classify_verb("lelya") == "ya_verb"

    def test_basic_verb_car(self):
        assert classify_verb("car") == "basic_verb"

    def test_basic_verb_kir(self):
        assert classify_verb("kir") == "basic_verb"

    def test_empty_string(self):
        assert classify_verb("") == "basic_verb"


# ---------------------------------------------------------------------------
# TestDeclineNoun — A-stems (cirya "ship")
# ---------------------------------------------------------------------------

class TestDeclineNounAStem:

    def test_cirya_nom_sg(self):
        check(decline_noun("cirya", "nominative", "singular"), "cirya")

    def test_cirya_nom_pl(self):
        check(decline_noun("cirya", "nominative", "plural"), "ciryar")

    def test_cirya_gen_sg(self):
        check(decline_noun("cirya", "genitive", "singular"), "ciryo")

    def test_cirya_gen_pl(self):
        check(decline_noun("cirya", "genitive", "plural"), "ciryon")

    def test_cirya_all_sg(self):
        check(decline_noun("cirya", "allative", "singular"), "ciryanna")

    def test_cirya_all_pl(self):
        check(decline_noun("cirya", "allative", "plural"), "ciryannar")

    def test_cirya_loc_sg(self):
        check(decline_noun("cirya", "locative", "singular"), "ciryassë")

    def test_cirya_abl_sg(self):
        check(decline_noun("cirya", "ablative", "singular"), "ciryallo")

    def test_cirya_dat_sg(self):
        check(decline_noun("cirya", "dative", "singular"), "ciryan")

    def test_cirya_ins_sg(self):
        r = decline_noun("cirya", "instrumental", "singular")
        assert r.quenya_form == "ciryanën".replace("ciryanën", "ciryanen") or r.quenya_form == "cirya" + "nen"

    def test_vanda_all_sg(self):
        check(decline_noun("vanda", "allative", "singular"), "vandanna")


# ---------------------------------------------------------------------------
# TestDeclineNoun — E-stems (lassë "leaf", taurë "forest")
# ---------------------------------------------------------------------------

class TestDeclineNounEStem:

    def test_lasse_nom_pl(self):
        check(decline_noun("lassë", "nominative", "plural"), "lassi")

    def test_lasse_gen_sg(self):
        check(decline_noun("lassë", "genitive", "singular"), "lasso")

    def test_taure_all_sg(self):
        check(decline_noun("taurë", "allative", "singular"), "taurenna")

    def test_taure_all_pl(self):
        check(decline_noun("taurë", "allative", "plural"), "taurennar")

    def test_taure_nom_pl(self):
        check(decline_noun("taurë", "nominative", "plural"), "tauri")

    def test_taure_loc_sg(self):
        r = decline_noun("taurë", "locative", "singular")
        assert r.quenya_form == "taurëssë"

    def test_e_stem_gen_pl(self):
        check(decline_noun("lassë", "genitive", "plural"), "lasson")


# ---------------------------------------------------------------------------
# TestDeclineNoun — O-stems (osto "city-fortress")
# ---------------------------------------------------------------------------

class TestDeclineNounOStem:

    def test_osto_all_sg(self):
        check(decline_noun("osto", "allative", "singular"), "ostonna")

    def test_osto_nom_pl(self):
        check(decline_noun("osto", "nominative", "plural"), "osti")

    def test_osto_loc_sg(self):
        check(decline_noun("osto", "locative", "singular"), "ostossë")

    def test_osto_all_pl(self):
        check(decline_noun("osto", "allative", "plural"), "ostonnar")


# ---------------------------------------------------------------------------
# TestDeclineNoun — Consonantal stems
# ---------------------------------------------------------------------------

class TestDeclineNounConsonantal:

    def test_ohtar_nom_pl(self):
        check(decline_noun("ohtar", "nominative", "plural"), "ohtari")

    def test_ohtar_all_sg(self):
        check(decline_noun("ohtar", "allative", "singular"), "ohtarenna")

    def test_elen_nom_pl(self):
        check(decline_noun("elen", "nominative", "plural"), "eleni")

    def test_elen_loc_sg(self):
        check(decline_noun("elen", "locative", "singular"), "elenessë")

    def test_elen_all_sg(self):
        check(decline_noun("elen", "allative", "singular"), "elenenna")

    def test_aran_gen_sg(self):
        check(decline_noun("aran", "genitive", "singular"), "arano")

    def test_ohtar_dat_sg(self):
        check(decline_noun("ohtar", "dative", "singular"), "ohtaren")

    def test_ohtar_abl_sg(self):
        check(decline_noun("ohtar", "ablative", "singular"), "ohtarello")


# ---------------------------------------------------------------------------
# TestDeclineNoun — Unknown case (graceful degradation)
# ---------------------------------------------------------------------------

class TestDeclineNounFallback:

    def test_unknown_case_returns_base(self):
        r = decline_noun("cirya", "elative", "singular")  # elative not in Quenya
        assert r.quenya_form == "cirya"
        assert r.confidence < 0.50
        assert r.warning != ""

    def test_result_always_has_all_fields(self):
        r = decline_noun("ohtar", "nominative", "singular")
        assert r.english_lemma != ""
        assert r.quenya_lemma  != ""
        assert r.quenya_form   != ""
        assert r.feature       != ""
        assert r.source_note   != ""
        assert isinstance(r.attestation, str)


# ---------------------------------------------------------------------------
# TestConjugateVerb — A-verbs (vanta "walk")
# ---------------------------------------------------------------------------

class TestConjugateVerbAVerb:

    def test_vanta_pres_sg(self):
        check(conjugate_verb("vanta", "present", "singular"), "vanta")

    def test_vanta_pres_pl(self):
        check(conjugate_verb("vanta", "present", "plural"), "vantar")

    def test_vanta_past_sg(self):
        check(conjugate_verb("vanta", "past", "singular"), "vantanë")

    def test_vanta_past_pl(self):
        check(conjugate_verb("vanta", "past", "plural"), "vantaner")

    def test_vanta_future_sg(self):
        check(conjugate_verb("vanta", "future", "singular"), "vantuva")

    def test_vanta_future_pl(self):
        check(conjugate_verb("vanta", "future", "plural"), "vantuvar")

    def test_vanta_imperative(self):
        check(conjugate_verb("vanta", "present", "singular", mood="imperative"), "vanta")

    def test_mela_past_sg(self):
        check(conjugate_verb("mela", "past", "singular"), "melanë")


# ---------------------------------------------------------------------------
# TestConjugateVerb — Basic verbs (car "do/make")
# ---------------------------------------------------------------------------

class TestConjugateVerbBasic:

    def test_car_pres_sg(self):
        check(conjugate_verb("car", "present", "singular"), "cara")

    def test_car_pres_pl(self):
        check(conjugate_verb("car", "present", "plural"), "carir")

    def test_car_future_sg(self):
        check(conjugate_verb("car", "future", "singular"), "caruva")

    def test_car_past_sg(self):
        check(conjugate_verb("car", "past", "singular"), "carnë")


# ---------------------------------------------------------------------------
# TestConjugateVerb — Confidence levels
# ---------------------------------------------------------------------------

class TestConjugateVerbConfidence:

    def test_pres_sg_high_confidence(self):
        r = conjugate_verb("vanta", "present", "singular")
        assert r.confidence >= 0.85

    def test_future_pl_lower_confidence(self):
        r = conjugate_verb("vanta", "future", "plural")
        assert r.confidence < 0.90

    def test_unknown_tense_low_confidence(self):
        r = conjugate_verb("vanta", "conditional", "singular")
        assert r.confidence < 0.50
        assert r.warning != ""

    def test_result_always_has_all_fields(self):
        r = conjugate_verb("car", "present", "singular")
        assert r.english_lemma != ""
        assert r.quenya_form   != ""
        assert r.feature       != ""
        assert r.source_note   != ""


# ---------------------------------------------------------------------------
# TestMorphResultReliable
# ---------------------------------------------------------------------------

class TestMorphResultReliable:

    def test_high_confidence_no_warning_is_reliable(self):
        r = MorphResult(
            english_lemma="warrior", quenya_lemma="ohtar",
            quenya_form="ohtari", feature="nominative plural",
            confidence=0.90, source_note="PE XVII", attestation="reconstructed",
        )
        assert r.is_reliable() is True

    def test_low_confidence_not_reliable(self):
        r = MorphResult(
            english_lemma="x", quenya_lemma="x",
            quenya_form="x", feature="?",
            confidence=0.40, source_note="fallback",
        )
        assert r.is_reliable() is False

    def test_warning_makes_unreliable(self):
        r = MorphResult(
            english_lemma="x", quenya_lemma="x",
            quenya_form="x", feature="?",
            confidence=0.90, source_note="PE XVII",
            warning="something is uncertain",
        )
        assert r.is_reliable() is False

    def test_exactly_at_threshold_is_reliable(self):
        r = MorphResult(
            english_lemma="x", quenya_lemma="x",
            quenya_form="x", feature="?",
            confidence=0.70, source_note="PE XVII", attestation="reconstructed",
        )
        assert r.is_reliable() is True


# ---------------------------------------------------------------------------
# TestAttestation — attestation field
# ---------------------------------------------------------------------------

class TestAttestation:

    def test_result_has_attestation_field(self):
        r = decline_noun("cirya", "nominative", "singular")
        assert hasattr(r, "attestation")
        assert r.attestation in ("attested", "reconstructed", "neo-quenya")

    def test_default_attestation_is_reconstructed(self):
        r = MorphResult(
            english_lemma="x", quenya_lemma="x", quenya_form="x",
            feature="x", confidence=0.8, source_note="x",
        )
        assert r.attestation == "reconstructed"

    def test_unknown_case_is_neo_quenya(self):
        r = decline_noun("cirya", "elative", "singular")
        assert r.attestation == "neo-quenya"

    def test_verb_rule_result_is_reconstructed(self):
        r = conjugate_verb("vanta", "present", "singular")
        assert r.attestation == "reconstructed"


# ---------------------------------------------------------------------------
# TestComputeNounForm — mocked vocabulary lookup
# ---------------------------------------------------------------------------

class TestComputeNounForm:

    def test_found_in_db_applies_rules(self):
        with patch("src.morphology.lookup_quenya_lemma", return_value=("ohtar", "noun", 0.80)):
            r = compute_noun_form("warrior", "nominative", "plural")
        assert r.english_lemma == "warrior"
        assert r.quenya_lemma  == "ohtar"
        assert r.quenya_form   == "ohtari"

    def test_osto_allative(self):
        with patch("src.morphology.lookup_quenya_lemma", return_value=("osto", "noun", 0.80)):
            r = compute_noun_form("city", "allative", "singular")
        assert r.quenya_form == "ostonna"

    def test_not_found_returns_placeholder(self):
        with patch("src.morphology.lookup_quenya_lemma", return_value=("xyzzy", "unknown", 0.0)):
            r = compute_noun_form("xyzzy", "nominative", "singular")
        assert r.confidence == 0.0
        assert r.warning != ""
        assert "[" in r.quenya_form


# ---------------------------------------------------------------------------
# TestComputeVerbForm — mocked vocabulary lookup
# ---------------------------------------------------------------------------

class TestComputeVerbForm:

    def test_found_present_plural(self):
        with patch("src.morphology.lookup_quenya_lemma", return_value=("vanta", "verb", 0.80)):
            r = compute_verb_form("walk", "present", "plural")
        assert r.english_lemma == "walk"
        assert r.quenya_form   == "vantar"

    def test_found_past_singular(self):
        with patch("src.morphology.lookup_quenya_lemma", return_value=("vanta", "verb", 0.80)):
            r = compute_verb_form("walk", "past", "singular")
        assert r.quenya_form == "vantanë"

    def test_not_found_returns_placeholder(self):
        with patch("src.morphology.lookup_quenya_lemma", return_value=("xyz", "unknown", 0.0)):
            r = compute_verb_form("xyz", "present", "singular")
        assert r.confidence == 0.0
        assert r.warning != ""
        assert "[" in r.quenya_form
