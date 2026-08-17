#!/usr/bin/env python3
"""Regressions for the split-layer search and the common-spelling
normalization table (metadata/search-normalization.json).

Background: English stemming applied to Roman queries turned "dayal" into
"day" (matching English translation text) and "ardas" into "arda" (substring
matching inside unrelated Roman words), producing confident wrong results.
The fix separates the layers: stemmed tokens match only English translation
text, raw normalized Roman tokens match only transliteration, and a reviewed
normalization table maps common spellings to corpus scheme spellings.

Table contract (reviewed): alternatives are OR within a query position,
positions are AND, and all positions must be satisfied within one text layer.
Phrase aliases are recognized on contiguous token windows BEFORE per-token
rules run. Compound aliases (satnam -> sat, naam) form ONE position whose
token sequence must appear contiguously and in order (issue #7); ordinary
multi-word queries remain independent unordered positions.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "mcp"))
sys.path.insert(1, str(REPO))

import server
from server import (
    NORMALIZATION,
    _word_search,
    expand_roman_query,
    roman_words,
)

ALL_FIELDS = ["english", "transliteration", "gurmukhi"]


def angs_for(query, limit=60):
    return [r["ang"] for r in _word_search(query.lower(), ALL_FIELDS, limit)]


# ---------------------------------------------------------------------------
# Table validation
# ---------------------------------------------------------------------------

def _corpus_roman_tokens():
    tokens = set()
    for verses in server.verses_by_ang.values():
        for verse in verses:
            tokens.update(roman_words(verse.get("transliteration", "")))
    return tokens


def test_every_table_target_exists_in_roman_layer():
    corpus = _corpus_roman_tokens()
    for key, targets in NORMALIZATION["token_aliases"].items():
        for t in targets:
            assert t in corpus, f"token alias target missing from corpus: {key} -> {t}"
    for key, targets in NORMALIZATION["phrase_aliases"].items():
        for t in targets:
            assert t in corpus, f"phrase alias target missing from corpus: {key} -> {t}"
    for key, seq in NORMALIZATION["compound_aliases"].items():
        for t in seq:
            assert t in corpus, f"compound token missing from corpus: {key} -> {t}"


def test_alias_keys_that_are_corpus_tokens_preserve_themselves():
    # Self-preservation rule: an alias must never hide a real corpus spelling
    # (dayaal, akal, and ram are genuine corpus tokens).
    corpus = _corpus_roman_tokens()
    for key, targets in NORMALIZATION["token_aliases"].items():
        if key in corpus:
            assert key in targets, (
                f"'{key}' exists in the corpus but its alias list {targets} "
                "does not preserve it"
            )


def test_no_alias_chains():
    aliases = NORMALIZATION["token_aliases"]
    for key, targets in aliases.items():
        for t in targets:
            if t in aliases and t != key:
                assert t in aliases[t], f"chained alias: {key} -> {t} -> {aliases[t]}"


# ---------------------------------------------------------------------------
# Query expansion semantics (reviewed implementation rules)
# ---------------------------------------------------------------------------

def test_phrase_alias_recognized_before_token_aliases():
    # "ik onkar" must be handled as a phrase window, not split into per-token
    # transformations first.
    positions = expand_roman_query("ik onkar")
    assert positions == [[["ikoankaar"]]]


def test_phrase_alias_inside_longer_query():
    positions = expand_roman_query("ik onkar dayal")
    assert positions[0] == [["ikoankaar"]]
    assert positions[1] == [["daiaal"]]


def test_satnam_is_one_contiguous_sequence_position():
    # Compound aliases form ONE position holding a token sequence that must
    # appear adjacently and in order (issue #7), never independent positions
    # and never alternatives.
    positions = expand_roman_query("satnam")
    assert positions == [[["sat", "naam"]]]


def test_tu_alias_preserves_literal_tu():
    positions = expand_roman_query("tu")
    assert positions == [[["tu"], ["too"], ["toon"]]]


# ---------------------------------------------------------------------------
# Search regressions (MCP surface)
# ---------------------------------------------------------------------------

def test_tu_dayal_finds_true_entries_and_excludes_ang_1377():
    angs = angs_for("Tu dayal")
    # 122 and 747 carry the confirmed toon daiaal entries; additional
    # legitimate too/toon + daiaal verses are correct behavior, so these are
    # required results, not exclusive ones.
    assert 122 in angs
    assert 747 in angs
    # Ang 1377 matched only via the old cross-layer stem collision
    # ("dayal" -> stem "day" -> English "Twenty-four hours a day").
    assert 1377 not in angs


def test_ih_ardas_finds_only_ang_747():
    assert angs_for("Ih ardas") == [747]


def test_waheguru_spelling_family_preserved():
    for spelling in ("waheguru", "wahiguru", "vaheguru", "vahiguru"):
        angs = angs_for(spelling)
        assert angs, f"{spelling} returned nothing"
        assert any(a in (1402, 1403) for a in angs), f"{spelling}: {angs}"


def test_paren_nasal_tokens_are_searchable():
    # The scheme writes a(n)mrit, gobi(n)d, sa(n)gat; (n) -> n normalization
    # makes them searchable. Before the fix these returned nothing.
    for query in ("amrit", "gobind", "sangat"):
        assert angs_for(query), f"{query} returned nothing"


def test_ik_onkar_and_ek_onkar_agree_and_find_ang_1():
    ik = angs_for("ik onkar")
    ek = angs_for("ek onkar")
    assert ik == ek
    assert 1 in ik


def test_satnam_finds_ang_1():
    assert 1 in angs_for("satnam")


def test_roman_stopword_lookalikes_are_searchable():
    # "so" and "man" are English stop words but genuine Roman corpus tokens
    # (ਸੋ ਦਰੁ, ਮਨ). The Roman layer must not apply English stop words.
    angs = angs_for("so dar")
    assert 8 in angs, f"'so dar' should find Ang 8: {angs}"


# ---------------------------------------------------------------------------
# Verify-card anchor facts (site build)
# ---------------------------------------------------------------------------

def test_ang_747_page_anchors_ardaas_verse_at_v12():
    """The site's #vN anchors are verse ordinals within the ang; source LINE
    markers are a different numbering (this verse is LINE:7 but v12). Verify
    result cards must link by verse_index, so the page must carry id="v12"
    on the ardaas verse."""
    page = (REPO / "site" / "ang" / "747" / "index.html").read_text(encoding="utf-8")
    anchor_pos = page.find('id="v12"')
    assert anchor_pos != -1, 'ang 747 page lacks id="v12"'
    window = page[anchor_pos:anchor_pos + 600]
    assert "ਇਹ ਅਰਦਾਸਿ ਹਮਾਰੀ" in window, "id=v12 does not anchor the ardaas verse"


# ---------------------------------------------------------------------------
# MCP cache integrity
# ---------------------------------------------------------------------------

def test_verse_caches_hold_all_60555_unique_identities():
    """The old (ang, line) cache key collided because source LINE markers
    repeat within an ang: 60,555 verses collapsed onto 26,566 keys and
    33,989 entries were overwritten. Both per-verse caches must now hold one
    entry per verse under unique (ang, verse_index) identities."""
    total_verses = sum(len(v) for v in server.verses_by_ang.values())
    assert total_verses == 60555
    assert len(server.roman_verse_words) == total_verses
    assert len(server.english_verse_words) == total_verses

    expected_keys = {
        (ang, verse["verse_index"])
        for ang, verses in server.verses_by_ang.items()
        for verse in verses
    }
    assert len(expected_keys) == total_verses, "verse_index ordinals are not unique per ang"
    assert set(server.roman_verse_words.keys()) == expected_keys
    assert set(server.english_verse_words.keys()) == expected_keys


def test_colliding_line_entries_are_individually_cached():
    # Find an ang where two verses share the same source LINE value and prove
    # both have distinct cache entries (the exact case the old key destroyed).
    for ang, verses in sorted(server.verses_by_ang.items()):
        seen_lines = {}
        for verse in verses:
            line = verse["line"]
            if line in seen_lines:
                first = seen_lines[line]
                key_a = (ang, first["verse_index"])
                key_b = (ang, verse["verse_index"])
                assert key_a != key_b
                assert key_a in server.roman_verse_words
                assert key_b in server.roman_verse_words
                return
            seen_lines[line] = verse
    raise AssertionError("no colliding LINE values found; corpus assumption changed")


def test_mcp_identities_match_site_verses_json_field_for_field():
    """Every (ang, verse_index) identity in the MCP index must agree with the
    site's verses.json on gurmukhi, transliteration, and english. The Verify
    cards link to site anchors by verse_index, so the two surfaces' ordinals
    and content must never drift."""
    site_verses = json.loads(
        (REPO / "site" / "data" / "verses.json").read_text(encoding="utf-8")
    )
    assert len(site_verses) == 60555

    site_by_key = {(v["ang"], v["verse_index"]): v for v in site_verses}
    assert len(site_by_key) == 60555, "site verses.json has duplicate identities"

    mismatches = 0
    for ang, verses in server.verses_by_ang.items():
        for verse in verses:
            key = (ang, verse["verse_index"])
            site_v = site_by_key.get(key)
            assert site_v is not None, f"MCP identity missing from site data: {key}"
            for field in ("gurmukhi", "transliteration", "english"):
                if verse.get(field, "") != site_v.get(field, ""):
                    mismatches += 1
    assert mismatches == 0, f"{mismatches} field mismatches between MCP and site data"


# ---------------------------------------------------------------------------
# Compound-alias adjacency (issue #7)
# ---------------------------------------------------------------------------

def test_satnam_requires_contiguous_sat_naam():
    """satnam must match only lines where sat naam occurs as an adjacent,
    ordered sequence. Angs 33, 129, and 153 contain separated sat and naam
    tokens and previously matched (issue #7)."""
    results = _word_search("satnam", ALL_FIELDS, 80)
    angs = [r["ang"] for r in results]
    assert 1 in angs
    for false_positive in (33, 129, 153):
        assert false_positive not in angs, f"Ang {false_positive} matched without adjacency"
    for r in results:
        toks = roman_words(r["transliteration"])
        joined = " ".join(toks)
        assert "sat naam" in joined, f"Ang {r['ang']} lacks contiguous sat naam: {joined}"


def test_plain_multiword_query_stays_unordered():
    # Adjacency applies only to compound aliases: the ordinary two-word query
    # "sat naam" keeps independent unordered positions, so Ang 33 (separated
    # sat ... naam) remains a legitimate keyword match.
    angs = [r["ang"] for r in _word_search("sat naam", ALL_FIELDS, 100)]
    assert 33 in angs


def test_compound_alias_composes_with_phrase_alias_in_one_query():
    # "ik onkar satnam" exercises a phrase alias and a compound alias as two
    # AND positions; Ang 1 verse 1 contains ikoankaar and contiguous sat naam.
    results = _word_search("ik onkar satnam", ALL_FIELDS, 20)
    assert (1, 1) in [(r["ang"], r["verse_index"]) for r in results]


def test_compound_alias_is_directional():
    # Adjacency is ordered: Angs 275 and 285 contain the adjacent reversed
    # pair "naam sat" but never "sat naam", so satnam must not match them.
    angs = [r["ang"] for r in _word_search("satnam", ALL_FIELDS, 80)]
    assert 275 not in angs
    assert 285 not in angs
