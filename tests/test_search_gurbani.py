#!/usr/bin/env python3
"""Regression tests for search_gurbani phrase boundaries.

Python's \\b does not treat Gurmukhi combining vowel signs (e.g. U+0A41,
U+0A42) as word characters, so a phrase query ending in one (which is most
Gurmukhi words) used to fail its trailing boundary and return nothing.
These tests pin the fixed behavior and confirm that consonant-ending
Gurmukhi, transliteration, and English searches behave as before, and that
whole-word matching is still enforced.
"""

import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "mcp"))
sys.path.insert(1, str(REPO))

from server import _phrase_search, search_gurbani


def test_gurmukhi_query_ending_in_vowel_sign_finds_results():
    # ਵਾਹਿਗੁਰੂ ends in the vowel sign U+0A42 and appears on ang 1402.
    results = search_gurbani("ਵਾਹਿਗੁਰੂ", script="gurmukhi")
    assert results, "vowel-sign-ending query returned nothing (regression)"
    assert any(r["ang"] == 1402 for r in results)


def test_gurmukhi_multiword_query_ending_in_vowel_sign_finds_results():
    # ਸਤਿ ਨਾਮੁ ends in the vowel sign U+0A41 and opens ang 1.
    results = search_gurbani("ਸਤਿ ਨਾਮੁ", script="gurmukhi")
    assert results, "vowel-sign-ending phrase returned nothing (regression)"
    assert results[0]["ang"] == 1


def test_gurmukhi_consonant_ending_query_unchanged():
    # ਸਤਿਗੁਰ ends in a full consonant and worked before the fix; ang 8
    # carries it in the invocation line.
    results = search_gurbani("ਸਤਿਗੁਰ", script="gurmukhi")
    assert results
    assert any(r["ang"] == 8 for r in results)


def test_phrase_search_still_whole_word_in_gurmukhi():
    # The corpus contains ਵਾਹਿਗੁਰ only inside ਵਾਹਿਗੁਰੂ, never as its own
    # word, so a whole-word phrase search for the fragment must find
    # nothing. Guards against the boundary fix degrading into substring
    # matching.
    assert _phrase_search("ਵਾਹਿਗੁਰ", ["gurmukhi"], 20) == []


def test_phrase_search_rejects_vowel_sign_leading_fragment():
    # A fragment starting mid-word (leading vowel sign U+0A3E) is always
    # preceded by a consonant in real text, so the leading boundary must
    # reject it.
    assert _phrase_search("ਾਹਿਗੁਰੂ", ["gurmukhi"], 20) == []


def test_transliteration_search_unchanged():
    results = search_gurbani("vaahiguroo", script="transliteration")
    assert results
    assert any(r["ang"] == 1402 for r in results)


def test_english_search_unchanged():
    results = search_gurbani("true name", script="english")
    assert results
