#!/usr/bin/env python3
"""Audit harness for Open Granth verification behavior.

These tests are intentionally separate from the release gate script. They make
the verifier policy auditable:

- English verification accepts only sufficiently long exact DSSK phrases.
- Generic English keywords are rejected as search queries, not verified quotes.
- Fabricated English spiritual wording does not fuzzy-match into Gurbani.
- Selected corpus Gurmukhi lines produce the stored romanization and verify
  back to the expected ang.
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "mcp"))
sys.path.insert(1, str(REPO))

from scripts.transliteration import transliterate_gurmukhi
from server import _english_index, search_gurbani, verify_gurbani, verses_by_ang


ENGLISH_VERIFIED_CASES = [
    (
        "By thinking, He cannot be reduced to thought, even by thinking hundreds of thousands of times",
        1,
    ),
    (
        "when your friends turn into enemies, and even your relatives have deserted you",
        70,
    ),
    (
        "The slanderer is drowned, while I am carried across",
        339,
    ),
    (
        "With Your Support, I have no fear",
        1147,
    ),
    (
        # Three-word regression: unique phrases must verify once they clear
        # the 16-character floor, not be rejected on word count alone.
        "People become anxious",
        1429,
    ),
    (
        # Exact-line regression: a unique exact line must outrank the
        # shorter header lines it contains (So Dar, Ang 8).
        "So Dar ~ That Door. Raag Aasaa, First Mehl:",
        8,
    ),
]


ENGLISH_SHORT_QUERY_CASES = [
    "God",
    "Naam",
    "divine grace",
    "fear no one",
]


ENGLISH_FABRICATED_CASES = [
    "The Lord blesses those who eat hamburgers with divine grace",
    "Nanak says wealth accumulated through honest digital labor is blessed by the Lord",
    "The Khalsa shall rule the world and bring justice to all nations",
    "Meditate upon the divine light within your heart and find peace",
]


TRANSLITERATION_CASES = [
    (
        1,
        "ਸੋਚੈ ਸੋਚਿ ਨ ਹੋਵਈ ਜੇ ਸੋਚੀ ਲਖ ਵਾਰ ॥",
        "sochai soch na hovaee je sochee lakh vaar ||",
    ),
    (
        70,
        "ਜਾ ਕਉ ਮੁਸਕਲੁ ਅਤਿ ਬਣੈ ਢੋਈ ਕੋਇ ਨ ਦੇਇ ॥",
        "jaa kau musakal at banai dhoee koi na dei ||",
    ),
    (
        339,
        "ਨਿੰਦਉ ਨਿੰਦਉ ਮੋ ਕਉ ਲੋਗੁ ਨਿੰਦਉ ॥",
        "ni(n)dau ni(n)dau mo kau log ni(n)dau ||",
    ),
    (
        1429,
        "ਸੰਗ ਸਖਾ ਸਭਿ ਤਜਿ ਗਏ ਕੋਊ ਨ ਨਿਬਹਿਓ ਸਾਥਿ ॥",
        "sa(n)g sakhaa sabh taj gae kooo na nibahio saath ||",
    ),
]


REPEATED_OPENING = (
    "ੴ ਸਤਿ ਨਾਮੁ ਕਰਤਾ ਪੁਰਖੁ ਨਿਰਭਉ ਨਿਰਵੈਰੁ ਅਕਾਲ ਮੂਰਤਿ ਅਜੂਨੀ ਸੈਭੰ ਗੁਰ ਪ੍ਰਸਾਦਿ ॥",
    "ikOankaar sat naam karataa purakh nirabhau niravair akaal moorat ajoonee saibha(n) gur prasaad ||",
)

MULTI_LINE_PASSAGE = "ਭਈ ਪਰਾਪਤਿ ਮਾਨੁਖ ਦੇਹੁਰੀਆ ਗੋਬਿੰਦ ਮਿਲਣ ਕੀ ਇਹ ਤੇਰੀ ਬਰੀਆ"


def assert_status(text, expected_status, *, script="auto", ang=None):
    result = verify_gurbani(text, script)
    assert result["status"] == expected_status
    if ang is not None:
        assert result.get("ang") == ang
    return result


def test_public_corpus_has_english_for_every_loaded_verse():
    total_verses = sum(len(verses) for verses in verses_by_ang.values())

    assert total_verses > 60000
    assert len(_english_index) == total_verses


@pytest.mark.parametrize(("text", "expected_ang"), ENGLISH_VERIFIED_CASES)
def test_exact_english_phrases_verify_to_expected_ang(text, expected_ang):
    result = assert_status(text, "verified", script="english", ang=expected_ang)

    assert result["verse"]["english"]
    assert result["verse"]["gurmukhi"]


def test_english_verification_normalizes_case_spacing_and_punctuation():
    text = "  BY THINKING -- HE CANNOT BE REDUCED TO THOUGHT; even by thinking hundreds of thousands of times.  "

    assert_status(text, "verified", script="english", ang=1)


def test_repeated_english_phrase_is_not_single_citation_verified():
    result = assert_status("The Name Is Truth", "partial_match", script="english")

    assert "multiple verses" in result["message"].lower()
    assert {match["ang"] for match in result["closest_matches"]} >= {1, 94, 998}


@pytest.mark.parametrize("text", ["ਸਤਿ ਨਾਮੁ", "ੴ ਸਤਿ ਨਾਮੁ", REPEATED_OPENING[0]])
def test_repeated_gurmukhi_phrase_is_not_single_citation_verified(text):
    result = assert_status(text, "partial_match", script="gurmukhi")

    assert "multiple verses" in result["message"].lower()
    assert len(result["closest_matches"]) > 1


def test_repeated_transliteration_phrase_is_not_single_citation_verified():
    result = assert_status(REPEATED_OPENING[1], "partial_match", script="transliteration")

    assert "multiple verses" in result["message"].lower()
    assert len(result["closest_matches"]) > 1


def test_adjacent_multi_line_gurmukhi_passage_is_recognized_exactly():
    result = assert_status(MULTI_LINE_PASSAGE, "partial_match", script="gurmukhi")

    assert "passage appears in multiple places" in result["message"]
    assert {match["ang"] for match in result["closest_matches"]} == {12, 378}
    assert all(len(match["verses"]) == 2 for match in result["closest_matches"])


@pytest.mark.parametrize("text", ENGLISH_SHORT_QUERY_CASES)
def test_short_english_inputs_are_rejected_as_search_queries(text):
    result = assert_status(text, "error", script="english")

    assert "too short" in result["message"].lower()
    assert "search" in result["message"].lower()


@pytest.mark.parametrize("text", ENGLISH_FABRICATED_CASES)
def test_fabricated_english_sentences_do_not_verify(text):
    assert_status(text, "not_found", script="english")


def test_english_verification_has_no_fuzzy_near_miss_mode():
    near_miss = "By thinking, He can be reduced to thought, even by thinking hundreds of thousands of times"

    assert_status(near_miss, "not_found", script="english")


def test_profane_english_input_is_rejected_before_not_found():
    result = assert_status("fuck shit bitch ass cunt", "error", script="english")

    assert "not suitable" in result["message"].lower()
    assert "gurbani verification" in result["message"].lower()


@pytest.mark.parametrize("text", ["f.u.c.k", "sh1t", "b!tch", "f u c k", "fuuuck"])
def test_obfuscated_profane_english_input_is_rejected(text):
    result = assert_status(text, "error", script="english")

    assert "not suitable" in result["message"].lower()


@pytest.mark.parametrize("text", ["class assignment", "passage assistant", "grass bass compass"])
def test_profane_word_filter_uses_exact_words(text):
    result = verify_gurbani(text, script="english")

    assert "not suitable" not in result["message"].lower()


def test_search_rejects_profane_or_fabricated_keyword_queries():
    assert search_gurbani("fuck shit ass bitch", script="english") == []
    assert search_gurbani("hamburger divine grace", script="english") == []


def test_auto_detection_routes_plain_english_to_english_verification():
    assert_status(ENGLISH_VERIFIED_CASES[0][0], "verified", ang=1)
    assert_status("divine grace", "error")
    assert_status("The Name Is Truth", "partial_match")


def test_unique_exact_transliteration_line_outranks_containment_matches():
    assert_status("so dar raag aasaa mahalaa 1 ||", "verified", script="transliteration", ang=8)


def test_auto_detection_falls_back_to_full_line_transliteration():
    assert_status("sochai soch na hovaee je sochee lakh vaar", "verified", ang=1)


@pytest.mark.parametrize("text", ["God", "Naam", "sat naam", "ikOankaar sat naam", "divine grace"])
def test_auto_detection_does_not_verify_short_ambiguous_roman_inputs(text):
    assert_status(text, "error")


@pytest.mark.parametrize(("expected_ang", "gurmukhi", "expected_roman"), TRANSLITERATION_CASES)
def test_selected_gurmukhi_lines_generate_expected_romanization(expected_ang, gurmukhi, expected_roman):
    assert transliterate_gurmukhi(gurmukhi) == expected_roman

    verified = assert_status(gurmukhi, "verified", script="gurmukhi", ang=expected_ang)
    assert verified["verse"]["transliteration"] == expected_roman


@pytest.mark.parametrize(("expected_ang", "gurmukhi", "expected_roman"), TRANSLITERATION_CASES)
def test_generated_romanization_verifies_back_to_same_ang(expected_ang, gurmukhi, expected_roman):
    generated = transliterate_gurmukhi(gurmukhi)

    assert generated == expected_roman
    assert_status(generated, "verified", script="transliteration", ang=expected_ang)
