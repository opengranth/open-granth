"""
Tests for open_granth.parser.

These pin down the parser behaviors that the site, search, and MCP server
depend on. The most important cases:

1. Repeated <!-- LINE:n --> in a corpus file: implicit V positioning.
2. Frontmatter parsing.
3. Gurmukhi, transliteration, and English field extraction.
4. The ੴ ਸਤਿ ਨਾਮੁ closing footer is correctly skipped in corpus parsing.

Run from repo root:
    python -m pytest tests/test_parser.py -v
"""

import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

import pytest

from open_granth.parser import (
    MARKER_RE,
    parse_corpus_file,
    parse_marker_blocks,
)


# ---------------------------------------------------------------------------
# MARKER_RE: low-level pattern
# ---------------------------------------------------------------------------

class TestMarkerRegex:
    def test_matches_bare_line(self):
        m = MARKER_RE.search("<!-- LINE:5 -->")
        assert m is not None
        assert m.group(1) == "5"
        assert m.group(2) is None

    def test_matches_line_with_v(self):
        m = MARKER_RE.search("<!-- LINE:5 V:2 -->")
        assert m is not None
        assert m.group(1) == "5"
        assert m.group(2) == "2"

    def test_tolerates_extra_spaces(self):
        m = MARKER_RE.search("<!--  LINE:12   V:3  -->")
        assert m is not None
        assert m.group(1) == "12"
        assert m.group(2) == "3"

    def test_no_match_outside_comment(self):
        assert MARKER_RE.search("LINE:5") is None


# ---------------------------------------------------------------------------
# parse_marker_blocks: low-level iteration primitive
# ---------------------------------------------------------------------------

class TestMarkerBlocks:
    def test_yields_each_block_in_order(self):
        body = """
<!-- LINE:1 -->
first

<!-- LINE:2 -->
second

<!-- LINE:3 -->
third
"""
        blocks = list(parse_marker_blocks(body))
        assert len(blocks) == 3
        assert blocks[0][0] == 1
        assert blocks[1][0] == 2
        assert blocks[2][0] == 3

    def test_v_explicit_is_none_when_omitted(self):
        body = "<!-- LINE:5 -->\ncontent"
        blocks = list(parse_marker_blocks(body))
        assert len(blocks) == 1
        assert blocks[0][1] is None

    def test_v_explicit_returned_when_present(self):
        body = "<!-- LINE:5 V:2 -->\ncontent"
        blocks = list(parse_marker_blocks(body))
        assert len(blocks) == 1
        assert blocks[0][1] == 2


# ---------------------------------------------------------------------------
# parse_corpus_file: implicit V positioning on repeated LINE
# ---------------------------------------------------------------------------

CORPUS_REPEATED_LINE = """\
---
ang: 1
author: Test
---

<!-- LINE:5 -->
**ਸੋਚੈ ਸੋਚਿ ਨ ਹੋਵਈ ਜੇ ਸੋਚੀ ਲਖ ਵਾਰ ॥**

*sochai soch na hovaee je sochee lakh vaar ||*

---

<!-- LINE:5 -->
**ਚੁਪੈ ਚੁਪ ਨ ਹੋਵਈ ਜੇ ਲਾਇ ਰਹਾ ਲਿਵ ਤਾਰ ॥**

*chupai chup na hovaee je laai rahaa liv taar ||*

---

<!-- LINE:5 -->
**ਭੁਖਿਆ ਭੁਖ ਨ ਉਤਰੀ ਜੇ ਬੰਨਾ ਪੁਰੀਆ ਭਾਰ ॥**

*bhukhiaa bhukh na utaree je ba(n)naa pureeaa bhaar ||*

---

<!-- LINE:6 -->
**ਸਹਸ ਸਿਆਣਪਾ ਲਖ ਹੋਹਿ ਤ ਇਕ ਨ ਚਲੈ ਨਾਲਿ ॥**

*sahas siaanapaa lakh hoh ta ik na chalai naal ||*

---
"""


class TestCorpusParser:
    def test_repeated_line_assigns_sequential_v(self, tmp_path):
        """Three verses on LINE:5 should get v=1, v=2, v=3."""
        path = tmp_path / "ang-0001.md"
        path.write_text(CORPUS_REPEATED_LINE, encoding="utf-8")

        front, verses = parse_corpus_file(path)

        assert front["ang"] == 1
        assert front["author"] == "Test"
        assert len(verses) == 4

        # Three verses on line 5
        line_5 = [v for v in verses if v["line"] == 5]
        assert len(line_5) == 3
        assert line_5[0]["v"] == 1
        assert line_5[1]["v"] == 2
        assert line_5[2]["v"] == 3

        # Different gurmukhi for each
        assert "ਸੋਚੈ" in line_5[0]["gurmukhi"]
        assert "ਚੁਪੈ" in line_5[1]["gurmukhi"]
        assert "ਭੁਖਿਆ" in line_5[2]["gurmukhi"]

        # New line resets the counter
        line_6 = [v for v in verses if v["line"] == 6]
        assert len(line_6) == 1
        assert line_6[0]["v"] == 1

    def test_extracts_gurmukhi_and_transliteration(self, tmp_path):
        path = tmp_path / "ang-0001.md"
        path.write_text(CORPUS_REPEATED_LINE, encoding="utf-8")

        _, verses = parse_corpus_file(path)

        first = verses[0]
        assert first["gurmukhi"] == "ਸੋਚੈ ਸੋਚਿ ਨ ਹੋਵਈ ਜੇ ਸੋਚੀ ਲਖ ਵਾਰ ॥"
        assert first["transliteration"] == "sochai soch na hovaee je sochee lakh vaar ||"
        assert first["english"] == ""

    def test_extracts_english_when_present(self, tmp_path):
        text = """\
---
ang: 1
author: Test
---

<!-- LINE:1 -->
**ੴ ਸਤਿ ਨਾਮੁ ਕਰਤਾ ਪੁਰਖੁ ॥**

*ikOankaar sat naam karataa purakh ||*

One Universal Creator God.
"""
        path = tmp_path / "ang-0001.md"
        path.write_text(text, encoding="utf-8")

        _, verses = parse_corpus_file(path)
        assert len(verses) == 1
        assert verses[0]["english"] == "One Universal Creator God."

    def test_skips_closing_footer(self, tmp_path):
        """The *ੴ ਸਤਿ ਨਾਮੁ* footer should not be parsed as a verse."""
        path = tmp_path / "ang-0008.md"
        path.write_text(
            CORPUS_REPEATED_LINE + "\n*ੴ ਸਤਿ ਨਾਮੁ*\n",
            encoding="utf-8",
        )

        _, verses = parse_corpus_file(path)
        # Should still be 4 verses, footer not added
        assert len(verses) == 4

    def test_real_corpus_ang_1(self):
        """Smoke test against the actual corpus/ang-0001.md."""
        path = REPO / "corpus" / "ang-0001.md"
        if not path.exists():
            pytest.skip("corpus/ang-0001.md not present")

        front, verses = parse_corpus_file(path)
        assert front["ang"] == 1
        assert len(verses) == 23  # known count for Japji ang 1

        # Check that LINE:5 has 3 verses with v=1, 2, 3
        line_5 = [v for v in verses if v["line"] == 5]
        assert len(line_5) == 3
        assert [v["v"] for v in line_5] == [1, 2, 3]
