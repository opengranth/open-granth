#!/usr/bin/env python3
"""Regressions that execute the ACTUAL built site JavaScript.

tests/site_js_harness.mjs loads the main script block from the built pages
(site/search/index.html, site/verify/index.html) unmodified and drives the
page's own functions against the released verses.json, so these assertions
cover the shipped browser code path, not a Python re-implementation.

Requires Node. Skipped (not silently passed) when Node is unavailable, so a
corpus-only environment still runs the rest of the suite.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
HARNESS = REPO / "tests" / "site_js_harness.mjs"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(
    NODE is None, reason="node not available; built-site JS regressions need Node"
)


def run_harness(mode, query):
    proc = subprocess.run(
        [NODE, str(HARNESS), mode, query],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=REPO,
    )
    assert proc.returncode == 0, f"harness failed: {proc.stderr[:500]}"
    return json.loads(proc.stdout)


def test_site_js_tu_dayal_includes_122_and_747_excludes_1377():
    result = run_harness("search", "Tu dayal")
    angs = result["angs"]
    assert 122 in angs
    assert 747 in angs
    assert 1377 not in angs, (
        "Ang 1377 reappeared: cross-layer stem collision "
        "('dayal' -> 'day' -> English translation text)"
    )


def test_site_js_ih_ardas_finds_only_ang_747():
    result = run_harness("search", "Ih ardas")
    assert result["angs"] == [747]


def test_site_js_verify_card_links_ang_747_v12_and_excludes_1399():
    """The generated Verify result card must be a full anchor to the matched
    verse ordinal: /ang/747/#v12 (explicitly not #v7, the source LINE number),
    with Ang 1399's reverse-containment match absent."""
    result = run_harness("verify", "ih aradaas hamaaree")
    cards = result["cards"]
    assert len(cards) == 1, f"expected one card, got {cards}"
    card = cards[0]
    assert card["tag"] == "A"
    assert card["href"] == "../ang/747/#v12"
    assert card["href"] != "../ang/747/#v7"
    assert "1399" not in card["text"]


def test_site_js_english_reverse_containment_excluded():
    """English twin of the 'rad' defect: Ang 8 has a standalone English line
    'Salok'. The input 'in maajh and saloks' contains 'salok' mid-word, so the
    old reverse-containment branch returned Ang 8 alongside the real match.
    Boundary-respecting matching returns only the true containing line."""
    result = run_harness("verify-english", "in maajh and saloks")
    cards = result["cards"]
    assert len(cards) == 1, f"expected one card: {cards}"
    assert cards[0]["href"] == "../ang/137/#v26"
    assert "Ang 8 " not in cards[0]["text"]


def test_site_js_gurmukhi_reverse_containment_excluded():
    """Gurmukhi twin: Ang 8's standalone ਸਲੋਕੁ line must not match inside
    the phrase 'ਲਗਾ ਪੜਣਿ ਸਲੋਕੁ' (Ang 473)."""
    result = run_harness("verify-gurmukhi", "ਲਗਾ ਪੜਣਿ ਸਲੋਕੁ")
    cards = result["cards"]
    assert len(cards) == 1, f"expected one card: {cards}"
    assert cards[0]["href"] == "../ang/473/#v10"
    assert "Ang 8 " not in cards[0]["text"]


def test_site_js_multiline_passage_card_targets_first_verse():
    """A verified multi-line passage renders one anchor card whose href
    targets the FIRST contained verse's ordinal (Ang 747 v12+v13 -> #v12)."""
    passage = (
        "ਇਹ ਅਰਦਾਸਿ ਹਮਾਰੀ ਸੁਆਮੀ ਵਿਸਰੁ ਨਾਹੀ ਸੁਖਦਾਤੇ ॥੩॥ "
        "ਦਿਨੁ ਰੈਣਿ ਸਾਸਿ ਸਾਸਿ ਗੁਣ ਗਾਵਾ ਜੇ ਸੁਆਮੀ ਤੁਧੁ ਭਾਵਾ ॥"
    )
    result = run_harness("verify-gurmukhi", passage)
    cards = result["cards"]
    assert len(cards) == 1, f"expected one card: {cards}"
    card = cards[0]
    assert card["tag"] == "A"
    assert card["href"] == "../ang/747/#v12"
    assert "ਅਰਦਾਸਿ" in card["text"] and "ਦਿਨੁ ਰੈਣਿ" in card["text"]


def test_site_js_satnam_requires_contiguous_sat_naam():
    """Issue #7 on the built site JS: satnam matches only contiguous sat naam.
    Angs 33, 129, and 153 (separated tokens) are excluded; Ang 1 remains."""
    result = run_harness("search", "satnam")
    angs = result["angs"]
    assert 1 in angs
    for false_positive in (33, 129, 153):
        assert false_positive not in angs


def test_site_js_plain_sat_naam_query_stays_unordered():
    result = run_harness("search", "sat naam")
    assert 33 in result["angs"]
