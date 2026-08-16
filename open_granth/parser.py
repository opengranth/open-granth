"""
Open Granth markdown parser.

This module is the single source of truth for parsing the corpus ang files
(corpus/ang-NNNN.md). Verses are joined to their position on the physical
saroop page by the `<!-- LINE:n -->` marker convention; a marker may carry
an explicit `<!-- LINE:n V:m -->` to disambiguate multiple verses on the
same physical line.

Join key
--------

The (line, v) tuple. When a LINE marker is repeated, the parser implicitly
assigns v = 1, 2, 3, ... in document order; an explicit V:m is honored.

Functions
---------

parse_corpus_file(path) -> (frontmatter, verses)
    Returns the YAML frontmatter dict and a list of verse dicts. Each verse:
    {line, v, gurmukhi, transliteration, english}.

parse_marker_blocks(body) -> iterator of (line, v_explicit, content)
    Lower-level primitive. Splits a markdown body on LINE/V markers and
    yields one tuple per marker block. v_explicit is None if the marker did
    not specify V:n.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator, Optional

import yaml


# Match: <!-- LINE:5 --> or <!-- LINE:5 V:2 -->
# Tolerates extra whitespace inside the comment.
MARKER_RE = re.compile(r"<!--\s*LINE:(\d+)(?:\s+V:(\d+))?\s*-->")


# ---------------------------------------------------------------------------
# Frontmatter helper
# ---------------------------------------------------------------------------

def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a markdown file into (frontmatter_dict, body_text).

    Returns ({}, text) if there is no YAML frontmatter.
    """
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    front = yaml.safe_load(parts[1]) or {}
    body = parts[2]
    return front, body


# ---------------------------------------------------------------------------
# Marker block iterator
# ---------------------------------------------------------------------------

def parse_marker_blocks(body: str) -> Iterator[tuple[int, Optional[int], str]]:
    """Yield (line, v_explicit, content) for each marker block in body.

    v_explicit is None if the marker omitted V:n. The caller decides how to
    resolve missing v (corpus parsing uses positional inference).
    """
    blocks = MARKER_RE.split(body)
    # blocks[0] = text before first marker
    # then alternating: line, v, content, line, v, content, ...
    # MARKER_RE has 2 capture groups, so split inserts 2 values per match.

    for i in range(1, len(blocks) - 2, 3):
        line_num = int(blocks[i])
        v_raw = blocks[i + 1]
        v_explicit = int(v_raw) if v_raw else None
        content = (blocks[i + 2] or "").strip()
        yield line_num, v_explicit, content


# ---------------------------------------------------------------------------
# Corpus parser
# ---------------------------------------------------------------------------

def parse_corpus_file(path: Path) -> tuple[dict, list[dict]]:
    """Parse a corpus ang file.

    Returns (frontmatter, verses). Each verse dict has:
        line: int (physical saroop line number)
        v:    int (1-based position within that line)
        gurmukhi: str
        transliteration: str
        english: str

    The v index is inferred from document order within a repeated LINE.
    """
    text = Path(path).read_text(encoding="utf-8")
    front, body = _split_frontmatter(text)

    verses: list[dict] = []
    line_v_counter: dict[int, int] = {}

    for line_num, v_explicit, content in parse_marker_blocks(body):
        if v_explicit is not None:
            v = v_explicit
        else:
            line_v_counter[line_num] = line_v_counter.get(line_num, 0) + 1
            v = line_v_counter[line_num]

        if not content or content.startswith("*ੴ"):
            continue

        gurmukhi, transliteration, english = _extract_corpus_fields(content)
        if gurmukhi:
            verses.append({
                "line": line_num,
                "v": v,
                "gurmukhi": gurmukhi,
                "transliteration": transliteration,
                "english": english,
            })

    return front, verses


def _extract_corpus_fields(content: str) -> tuple[str, str, str]:
    """Extract (gurmukhi, transliteration, english) from a corpus marker block.

    Corpus blocks contain bold gurmukhi (**...**) and italic transliteration
    (*...*). Any non-marker plain-text line is treated as english. Other lines
    (separators, blanks) are ignored.
    """
    gurmukhi = ""
    transliteration = ""
    english_parts: list[str] = []

    lines = [l.strip() for l in content.split("\n") if l.strip()]
    lines = [l for l in lines if l != "---"]

    for line in lines:
        # Footer marker should never be treated as transliteration.
        if line.startswith("*ੴ"):
            continue

        if line.startswith("**") and line.endswith("**"):
            if not gurmukhi:
                gurmukhi = line[2:-2]
        elif line.startswith("*") and line.endswith("*"):
            if not transliteration:
                transliteration = line[1:-1]
        else:
            english_parts.append(line)

    english = " ".join(english_parts).strip()
    return gurmukhi, transliteration, english
