"""
Open Granth MCP Server

Provides agent-accessible tools for searching and reading Sri Guru Granth Sahib Ji.
Reads a local corpus of ang-NNNN.md markdown files. The markdown IS the data. No database.

The corpus is not bundled with this package. Point the server at a local corpus:
    1. --source-dir /path/to/corpus    (CLI argument)
    2. OPEN_GRANTH_SOURCE=/path/to/corpus  (environment variable)
    3. ./corpus                         (current directory fallback)

Open Granth v1 defaults to the independent corpus (ShabadOS-derived Gurmukhi
and metadata, locally generated transliteration, and DSSK English translation).

Usage:
    python mcp/server.py --source-dir /path/to/corpus
    OPEN_GRANTH_SOURCE=/path/to/corpus python mcp/server.py
"""

import json
import os
import random
import re
import sys
from pathlib import Path

import yaml

from mcp.server.fastmcp import FastMCP


def _resolve_source_dir() -> Path:
    """Resolve corpus directory from CLI args, env var, or default."""
    # 1. CLI argument: --source-dir
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--source-dir" and i < len(sys.argv) - 1:
            return Path(sys.argv[i + 1])
        if arg.startswith("--source-dir="):
            return Path(arg.split("=", 1)[1])

    # 2. Environment variable
    env = os.environ.get("OPEN_GRANTH_SOURCE")
    if env:
        return Path(env)

    # 3. ./corpus relative to current working directory
    cwd_corpus = Path.cwd() / "corpus"
    if cwd_corpus.exists():
        return cwd_corpus

    # 4. ../corpus relative to this file; lets the server find its bundled
    #    corpus no matter which directory it is launched from. Without this the
    #    server only works when cwd happens to be the project root, so launching
    #    it from another project (e.g. a different .mcp.json) fails to load any
    #    angs. A packaged install with no sibling corpus falls through to (5).
    script_corpus = Path(__file__).resolve().parent.parent / "corpus"
    if script_corpus.exists():
        return script_corpus

    # 5. Nothing found; return the cwd default so startup reports the error.
    return cwd_corpus


SOURCE_DIR = _resolve_source_dir()

mcp = FastMCP("open-granth")


# ---------------------------------------------------------------------------
# Data structures, built at startup from the markdown files
# ---------------------------------------------------------------------------

# ang number → {author, raag, lines, file_path}
metadata: dict[int, dict] = {}

# ang number → list of parsed verse dicts
verses_by_ang: dict[int, list[dict]] = {}

# Split word indexes: English stems and Roman tokens never mix, so English
# stemming cannot collide with Roman words (the "Tu dayal" defect class).
# stemmed English word → set of ang numbers
english_word_index: dict[str, set[int]] = {}
# normalized Roman token → set of ang numbers
roman_word_index: dict[str, set[int]] = {}

# (ang, verse_index) → per-layer token sets for scoring. verse_index is the
# per-ang verse ordinal (matches the site's #vN anchors). The previous
# (ang, line) key collided: LINE markers repeat within an ang, which collapsed
# 60,555 verses onto 26,566 keys and overwrote 33,989 entries.
english_verse_words: dict[tuple[int, int], set[str]] = {}
roman_verse_words: dict[tuple[int, int], set[str]] = {}


def _load_normalization() -> dict:
    """Common-spelling table shared with the site search page. Single source:
    metadata/search-normalization.json. Contract: alternatives are OR within a
    position, positions are AND, all positions satisfied within one layer."""
    for base in (Path(__file__).resolve().parent.parent, SOURCE_DIR.resolve().parent):
        p = base / "metadata" / "search-normalization.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {"token_aliases": {}, "phrase_aliases": {}, "token_expansions": {}}


NORMALIZATION: dict = _load_normalization()


ENGLISH_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "have", "he", "her", "hers", "him", "his", "i", "in", "is", "it",
    "its", "me", "my", "of", "on", "or", "our", "ours", "she", "so", "that",
    "the", "their", "theirs", "them", "they", "this", "to", "us", "was",
    "we", "were", "with", "you", "your", "yours",
}

PROFANE_WORDS = {
    "fuck", "fucks", "fucked", "fucking",
    "fucker", "fuckers", "motherfucker", "motherfuckers",
    "fuk", "fuks", "fck",
    "shit", "shits", "shitty", "bullshit", "bullshits",
    "dipshit", "dipshits", "horseshit",
    "bitch", "bitches", "bitching", "biatch",
    "ass", "asshole", "assholes",
    "cunt", "cunts",
}

PROFANE_COLLAPSED_WORDS = {w for w in PROFANE_WORDS if w != "ass"}
PROFANE_TRANSLATION = str.maketrans({
    "@": "a", "4": "a",
    "$": "s", "5": "s",
    "!": "i", "1": "i", "|": "i",
    "0": "o",
    "3": "e",
    "7": "t",
})


# ---------------------------------------------------------------------------
# Stemming: lightweight suffix stripping for English search
# ---------------------------------------------------------------------------

def stem(word: str) -> str:
    """Basic English suffix stripping. Not perfect, but catches the common cases
    that matter for Gurbani translations (slanderer->slander, forsaken->forsak, etc.)."""
    if len(word) <= 3:
        return word
    # Order matters: try longest suffixes first
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    for suffix in ("ering", "ness", "ment", "tion", "sion", "ious", "eous",
                    "ting", "ing", "ful", "ous", "ble", "ers", "est",
                    "ier", "ely", "ens", "ern", "er", "ed", "ly", "en",
                    "es", "al", "ty"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 4:
        return word[:-1]
    return word


def searchable_words(text: str) -> list[str]:
    """Lowercase English/Romanized words, minus high-noise function words."""
    words = re.findall(r"[a-z]+", text.lower())
    return [w for w in words if w not in ENGLISH_STOPWORDS]


def stemmed_words(text: str) -> list[str]:
    return [stem(w) for w in searchable_words(text)]


def roman_words(text: str) -> list[str]:
    """Roman-layer tokens. The scheme writes nasals as (n), e.g. a(n)mrit:
    replace (n) with n (never delete the sequence) before tokenizing, or words
    like anmrit and gobind are unfindable. No stemming, no stop words: Roman
    text legitimately contains tokens like "so" and "man"."""
    return re.findall(r"[a-z]+", text.lower().replace("(n)", "n"))


def english_words(text: str) -> list[str]:
    """English-layer tokens: stop-word filtered and stemmed. The stemmer is
    English-only and must never touch Roman queries or Roman corpus text."""
    return [stem(w) for w in re.findall(r"[a-z]+", text.lower())
            if w not in ENGLISH_STOPWORDS]


def expand_roman_query(query: str) -> list[list[str]]:
    """Build Roman query positions from the normalization table.

    Order matters (reviewed rule): exact phrase aliases are recognized on
    contiguous token windows BEFORE any per-token alias or expansion runs, so
    "ik onkar" cannot be split and transformed token-by-token first. Token
    expansions (satnam -> sat, naam) create separate required positions,
    never alternatives. Each returned position is a list of OR-alternatives;
    positions are AND."""
    tokens: list = roman_words(query)
    for pk in sorted(NORMALIZATION.get("phrase_aliases", {}), key=len, reverse=True):
        key_toks = pk.split(" ")
        i = 0
        while i + len(key_toks) <= len(tokens):
            window = tokens[i:i + len(key_toks)]
            if all(isinstance(w, str) for w in window) and window == key_toks:
                tokens[i:i + len(key_toks)] = [tuple(NORMALIZATION["phrase_aliases"][pk])]
            i += 1
    positions: list[list[str]] = []
    for tok in tokens:
        if isinstance(tok, tuple):
            positions.append(list(tok))
            continue
        expansion = NORMALIZATION.get("token_expansions", {}).get(tok)
        if expansion:
            positions.extend([[t] for t in expansion])
            continue
        positions.append(list(NORMALIZATION.get("token_aliases", {}).get(tok, [tok])))
    return positions


def _token_sequence_in_line(input_tokens: list[str], line_tokens: list[str]) -> bool:
    """Boundary-respecting containment for verification: the complete
    submitted phrase must appear as a contiguous token sequence within the
    corpus line. Replaces raw substring tests in both directions; reverse
    containment (a short corpus line found inside the input, e.g. "rad"
    inside "a-rad-aas") is removed entirely per review."""
    n = len(input_tokens)
    if n == 0:
        return False
    for s in range(len(line_tokens) - n + 1):
        if line_tokens[s:s + n] == input_tokens:
            return True
    return False


def in_order_bonus_alts(positions: list[list[str]], verse_tokens: list[str]) -> int:
    """In-order bonus where each query position is a list of OR-alternatives."""
    if len(positions) < 2:
        return 0
    pos = -1
    matched = 0
    for alts in positions:
        found = -1
        for j in range(pos + 1, len(verse_tokens)):
            if verse_tokens[j] in alts:
                found = j
                break
        if found == -1:
            continue
        pos = found
        matched += 1
    if matched == len(positions):
        return 3
    if matched >= 2:
        return 1
    return 0


def in_order_bonus(query_stems: list[str], verse_stems: list[str]) -> int:
    """Prefer verses where query words appear in the same order."""
    if len(query_stems) < 2:
        return 0
    pos = -1
    matched = 0
    for qs in query_stems:
        try:
            pos = verse_stems.index(qs, pos + 1)
        except ValueError:
            continue
        matched += 1
    if matched == len(query_stems):
        return 3
    if matched >= 2:
        return 1
    return 0


def contains_profane_words(text: str) -> bool:
    tokens = re.findall(r"[a-z0-9@#$!|*_.-]+", (text or "").lower())
    normalized_tokens = []

    for token in tokens:
        normalized = token.translate(PROFANE_TRANSLATION)
        normalized = re.sub(r"[^a-z]", "", normalized)
        if not normalized:
            continue
        normalized_tokens.append(normalized)
        if normalized in PROFANE_WORDS:
            return True

        collapsed = re.sub(r"(.)\1+", r"\1", normalized)
        if collapsed in PROFANE_COLLAPSED_WORDS:
            return True

    # Catch deliberately spaced words like "f u c k" without treating normal
    # words such as "class" or "passage" as profanity.
    for start in range(len(normalized_tokens)):
        joined = ""
        for token in normalized_tokens[start:start + 12]:
            if len(token) != 1:
                break
            joined += token
            if joined in PROFANE_WORDS:
                return True
            collapsed = re.sub(r"(.)\1+", r"\1", joined)
            if collapsed in PROFANE_COLLAPSED_WORDS:
                return True

    return False


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

def parse_ang_file(file_path: Path) -> tuple[dict, list[dict]]:
    """Parse an ang markdown file into frontmatter metadata and verse list.

    Returns:
        (frontmatter_dict, list_of_verse_dicts)
    """
    text = file_path.read_text(encoding="utf-8")

    # Split frontmatter from body
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, []

    front = yaml.safe_load(parts[1])
    body = parts[2]

    # Split body into verse blocks on <!-- LINE:n --> markers
    blocks = re.split(r"<!--\s*LINE:(\d+)\s*-->", body)
    # blocks[0] is text before first marker (usually empty)
    # then alternating: line_number, verse_text, line_number, verse_text...

    verses = []
    for i in range(1, len(blocks) - 1, 2):
        line_num = int(blocks[i])
        verse_text = blocks[i + 1].strip()

        # Skip footer line (ੴ ਸਤਿ ਨਾਮੁ)
        if not verse_text or verse_text.startswith("*ੴ"):
            continue

        # Parse the triplet: bold Gurmukhi, italic transliteration, plain English
        gurmukhi = ""
        transliteration = ""
        english = ""

        lines = [l.strip() for l in verse_text.split("\n") if l.strip()]
        # Remove trailing --- separator if present
        lines = [l for l in lines if l != "---"]

        english_parts = []
        for line in lines:
            # Skip the closing Gurmukhi footer *ੴ ਸਤਿ ਨਾਮੁ*; it is a page
            # decoration, not a verse's transliteration.
            if line.startswith("*ੴ"):
                continue
            if line.startswith("**") and line.endswith("**"):
                gurmukhi = line[2:-2]
            elif line.startswith("*") and line.endswith("*"):
                transliteration = line[1:-1]
            elif not line.startswith("<!--"):
                english_parts.append(line)
        english = " ".join(english_parts)

        if gurmukhi or english:
            verses.append({
                "line": line_num,
                "gurmukhi": gurmukhi,
                "transliteration": transliteration,
                "english": english,
            })

    return front, verses


def build_index():
    """Walk the corpus directory and build in-memory indexes from markdown."""
    ang_files = sorted(SOURCE_DIR.glob("ang-*.md"))

    for file_path in ang_files:
        front, verses = parse_ang_file(file_path)
        if not front or "ang" not in front:
            continue

        ang_num = int(front["ang"])
        metadata[ang_num] = {
            "author": front.get("author", "Unknown"),
            "raag": front.get("raag", "Unknown"),
            "lines": front.get("lines", 0),
        }
        verses_by_ang[ang_num] = verses

        # Split-layer indexing: English stems and Roman tokens never mix.
        # verse_index is the per-ang ordinal, unique within the ang (the old
        # (ang, line) key collided because LINE markers repeat within an ang).
        for ordinal, verse in enumerate(verses, start=1):
            verse["verse_index"] = ordinal
            key = (ang_num, ordinal)

            eng = set(english_words(verse.get("english", "")))
            rom = set(roman_words(verse.get("transliteration", "")))
            english_verse_words[key] = eng
            roman_verse_words[key] = rom

            for word in eng:
                english_word_index.setdefault(word, set()).add(ang_num)
            for word in rom:
                roman_word_index.setdefault(word, set()).add(ang_num)

    print(f"Indexed {len(metadata)} angs, {sum(len(v) for v in verses_by_ang.values())} verses", file=sys.stderr)


# ---------------------------------------------------------------------------
# Tool 1: lookup_ang
# ---------------------------------------------------------------------------

@mcp.tool()
def lookup_ang(ang: int, fields: str = "all") -> dict:
    """Look up a full ang (page) of Sri Guru Granth Sahib Ji by page number.

    Args:
        ang: Ang (page) number, 1-1430.
        fields: Which verse fields to include: "all" (default), "gurmukhi",
            "transliteration", or comma-separated like "gurmukhi,transliteration".
            The "english" field is returned when present in the corpus. The
            public v1 corpus includes DSSK English imported from Shabad OS.

    Returns:
        Full ang with metadata and all verses.
    """
    if ang < 1 or ang > 1430:
        return {"error": f"Ang must be between 1 and 1430, got {ang}"}

    if ang not in metadata:
        return {"error": f"Ang {ang} not found in source files"}

    meta = metadata[ang]
    verses = verses_by_ang.get(ang, [])

    # Filter verse fields if requested
    if fields != "all":
        requested = {f.strip() for f in fields.split(",")}
        # Always include line number
        requested.add("line")
        verses = [{k: v for k, v in verse.items() if k in requested} for verse in verses]

    return {
        "ang": ang,
        "author": meta["author"],
        "raag": meta["raag"],
        "total_verses": len(verses_by_ang.get(ang, [])),
        "verses": verses,
    }


# ---------------------------------------------------------------------------
# Tool 2: search_gurbani
# ---------------------------------------------------------------------------

# Word characters for phrase boundaries: regex \w plus the Gurmukhi block.
# Python's \b does not count Gurmukhi combining vowel signs (e.g. ੁ, ੂ, ਿ)
# as word characters, which inverted the trailing boundary for queries
# ending in them and silently broke most Gurmukhi phrase searches.
_BOUNDARY_CHAR = r"[\w\u0A00-\u0A7F]"  # \w + Gurmukhi Unicode block


def _phrase_search(query_lower: str, fields: list[str], limit: int) -> list[dict]:
    """Whole-word phrase match across verses."""
    pattern = re.compile(
        r"(?<!" + _BOUNDARY_CHAR + r")" + re.escape(query_lower)
        + r"(?!" + _BOUNDARY_CHAR + r")",
        re.IGNORECASE,
    )
    results = []
    for ang_num in sorted(verses_by_ang.keys()):
        for verse in verses_by_ang[ang_num]:
            for field in fields:
                if pattern.search(verse.get(field, "")):
                    results.append({
                        "ang": ang_num,
                        "author": metadata[ang_num]["author"],
                        "raag": metadata[ang_num]["raag"],
                        **verse,
                    })
                    break
            if len(results) >= limit:
                break
        if len(results) >= limit:
            break
    return results


def _word_search(query_lower: str, fields: list[str], limit: int) -> list[dict]:
    """Two-layer word search. Roman positions (normalization-table
    OR-alternatives, AND across positions) match Roman tokens; stemmed English
    tokens match the English layer. A verse matches if either requested layer
    completes on its own; layers are never blended, so English stems cannot
    collide with Roman words (the "Tu dayal" defect class)."""
    roman_active = "transliteration" in fields
    english_active = "english" in fields

    roman_positions = expand_roman_query(query_lower) if roman_active else []
    eng_stems = english_words(query_lower) if english_active else []

    if not roman_positions and not eng_stems:
        return []

    # Candidate angs: any ang containing any alternative of any position
    candidate_angs: set[int] = set()
    for alts in roman_positions:
        for alt in alts:
            candidate_angs.update(roman_word_index.get(alt, set()))
    for qs in eng_stems:
        candidate_angs.update(english_word_index.get(qs, set()))
    if not candidate_angs:
        return []

    scored: list[tuple[int, int, dict, int]] = []  # (rank, score, verse, ang_num)
    for ang_num in candidate_angs:
        for verse in verses_by_ang.get(ang_num, []):
            key = (ang_num, verse["verse_index"])
            rank = 0
            score = 0

            if roman_positions:
                rset = roman_verse_words.get(key, set())
                if all(any(alt in rset for alt in alts) for alts in roman_positions):
                    rlist = roman_words(verse.get("transliteration", ""))
                    rank = (len(roman_positions) * 10) + in_order_bonus_alts(roman_positions, rlist)
                    score = len(roman_positions)

            if eng_stems:
                eset = english_verse_words.get(key, set())
                if all(qs in eset for qs in eng_stems):
                    elist = english_words(verse.get("english", ""))
                    exact_bonus = 5 if query_lower in verse.get("english", "").lower() else 0
                    e_rank = (len(eng_stems) * 10) + in_order_bonus(eng_stems, elist) + exact_bonus
                    if e_rank > rank:
                        rank = e_rank
                        score = len(eng_stems)

            if rank > 0:
                scored.append((rank, score, verse, ang_num))

    # Sort by rank descending, then by ang and verse ordinal for stability
    scored.sort(key=lambda x: (-x[0], x[3], x[2]["verse_index"]))

    results = []
    for rank, score, verse, ang_num in scored[:limit]:
        results.append({
            "ang": ang_num,
            "author": metadata[ang_num]["author"],
            "raag": metadata[ang_num]["raag"],
            "score": score,
            "matched_of": score,
            **verse,
        })

    return results


@mcp.tool()
def search_gurbani(query: str, script: str = "all") -> list[dict]:
    """Search Sri Guru Granth Sahib Ji for verses matching a query.

    Tries exact phrase match first. If no results, falls back to word-level
    search with stemming and relevance scoring.

    Args:
        query: Search term (case-insensitive). Multi-word queries will first
            try exact phrase match, then fall back to finding verses with the
            most matching words.
        script: Which text to search: "gurmukhi", "transliteration", "english",
            or "all" (default). English search uses the corpus English layer
            when present; public v1 includes DSSK English from Shabad OS.

    Returns:
        Up to 20 matching verses ranked by relevance, with ang number, line,
        and verse text (Gurmukhi and transliteration; English when present).
    """
    query_lower = query.lower()
    limit = 20
    if contains_profane_words(query):
        return []

    # Determine which fields to search
    fields = []
    if script in ("all", "english"):
        fields.append("english")
    if script in ("all", "transliteration"):
        fields.append("transliteration")
    if script in ("all", "gurmukhi"):
        fields.append("gurmukhi")

    # Try exact phrase match first
    results = _phrase_search(query_lower, fields, limit)
    if results:
        return results

    # Fall back to word intersection search with stemming
    return _word_search(query_lower, fields, limit)


# ---------------------------------------------------------------------------
# Tool 3: get_verse
# ---------------------------------------------------------------------------

@mcp.tool()
def get_verse(ang: int, line: int) -> dict:
    """Get a specific verse by ang (page) and line number.

    Args:
        ang: Ang (page) number, 1-1430.
        line: Line number on the ang.

    Returns:
        Single verse with Gurmukhi and transliteration. English is returned
        when the corpus contains it; public v1 includes DSSK English.
    """
    if ang < 1 or ang > 1430:
        return {"error": f"Ang must be between 1 and 1430, got {ang}"}

    verses = verses_by_ang.get(ang, [])
    matching = [v for v in verses if v["line"] == line]

    if not matching:
        return {"error": f"No verses found at ang {ang}, line {line}"}

    meta = metadata[ang]
    return {
        "ang": ang,
        "author": meta["author"],
        "raag": meta["raag"],
        "verses": matching,
    }


# ---------------------------------------------------------------------------
# Tool 4: search_by_raag
# ---------------------------------------------------------------------------

@mcp.tool()
def search_by_raag(raag: str) -> list[dict]:
    """Find angs by raag (musical mode).

    Args:
        raag: Raag name or partial name (case-insensitive, e.g. "Asa", "Gauree").

    Returns:
        List of matching angs with raag name, author, and first verse.
    """
    raag_lower = raag.lower()
    results = []

    for ang_num in sorted(metadata.keys()):
        meta = metadata[ang_num]
        if raag_lower in meta["raag"].lower():
            first_verse = verses_by_ang[ang_num][0] if verses_by_ang.get(ang_num) else {}
            results.append({
                "ang": ang_num,
                "raag": meta["raag"],
                "author": meta["author"],
                "first_verse_gurmukhi": first_verse.get("gurmukhi", ""),
                "first_verse_transliteration": first_verse.get("transliteration", ""),
            })

    return results


# ---------------------------------------------------------------------------
# Tool 5: search_by_author
# ---------------------------------------------------------------------------

@mcp.tool()
def search_by_author(author: str) -> list[dict]:
    """Find angs by author (Guru or Bhagat).

    Args:
        author: Author name or partial name (case-insensitive, e.g. "Nanak", "Kabeer").

    Returns:
        List of matching angs grouped by author with counts.
    """
    author_lower = author.lower()

    # Group by exact author name
    by_author: dict[str, list[int]] = {}
    for ang_num in sorted(metadata.keys()):
        meta = metadata[ang_num]
        if author_lower in meta["author"].lower():
            name = meta["author"]
            if name not in by_author:
                by_author[name] = []
            by_author[name].append(ang_num)

    results = []
    for name, angs in by_author.items():
        results.append({
            "author": name,
            "ang_count": len(angs),
            "angs": angs[:50],  # Cap at 50 to keep response reasonable
            "note": f"Showing first 50 of {len(angs)} angs" if len(angs) > 50 else None,
        })

    return results


# ---------------------------------------------------------------------------
# Tool 6: random_ang
# ---------------------------------------------------------------------------

@mcp.tool()
def random_ang() -> dict:
    """Get a random ang (page) of Sri Guru Granth Sahib Ji.

    Returns:
        A random full ang with all verses and metadata.
    """
    ang_num = random.choice(list(metadata.keys()))
    return lookup_ang(ang_num)


# ---------------------------------------------------------------------------
# Tool 7: verify_gurbani
# ---------------------------------------------------------------------------

def _normalize_gurmukhi(text: str) -> str:
    """Normalize Gurmukhi text for comparison: strip punctuation, extra spaces,
    and common variation characters."""
    # Remove Gurbani-specific punctuation (double dandas, single dandas, digits for pause markers)
    text = re.sub(r"[॥।੦੧੨੩੪੫੬੭੮੯\d]", "", text)
    # Remove common markup artifacts
    text = re.sub(r"[|(){}\[\]]", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _similarity(a: str, b: str) -> float:
    """Simple character-level similarity ratio between two strings.
    Returns 0.0 to 1.0. Optimized for Gurmukhi comparison."""
    if not a or not b:
        return 0.0
    # Use longest common subsequence ratio
    len_a, len_b = len(a), len(b)
    if len_a == 0 or len_b == 0:
        return 0.0
    # For performance, skip very long comparisons
    if abs(len_a - len_b) > max(len_a, len_b) * 0.5:
        return 0.0
    # Simple bigram overlap (fast, good enough for Gurmukhi)
    def bigrams(s):
        return set(s[i:i+2] for i in range(len(s) - 1)) if len(s) > 1 else {s}
    bg_a = bigrams(a)
    bg_b = bigrams(b)
    if not bg_a or not bg_b:
        return 0.0
    overlap = len(bg_a & bg_b)
    return (2.0 * overlap) / (len(bg_a) + len(bg_b))


# Pre-built normalized index for verification (built after build_index)
# Maps normalized Gurmukhi -> list of (ang, line, verse_dict)
_gurmukhi_index: list[tuple[str, int, int, dict]] = []
# Maps normalized English -> list of (ang, line, verse_dict)
_english_index: list[tuple[str, int, int, dict]] = []


def _verify_match(ang_num: int, line: int, verse: dict) -> dict:
    meta = metadata[ang_num]
    return {
        "ang": ang_num,
        "line": line,
        "author": meta["author"],
        "raag": meta["raag"],
        "verse": verse,
    }


def _multiple_exact_matches_message(script_name: str) -> str:
    return (
        f"This {script_name} phrase appears in multiple verses. It is an exact "
        "phrase match, but not specific enough for a single verified citation. "
        "Use the original Gurmukhi or paste a longer phrase."
    )


def _passage_match(ang_num: int, start_line: int, end_line: int, passage_verses: list[dict]) -> dict:
    meta = metadata[ang_num]
    return {
        "ang": ang_num,
        "line": start_line,
        "end_line": end_line,
        "author": meta["author"],
        "raag": meta["raag"],
        "verse": passage_verses[0],
        "verses": passage_verses,
    }


def _find_gurmukhi_passage_matches(normalized: str, max_window: int = 8) -> list[dict]:
    """Find exact adjacent multi-verse Gurmukhi passage matches.

    Many shared quotes span two or more displayed verse rows. Verification
    should recognize those as exact passage matches instead of treating each
    component row as an unrelated substring hit.
    """
    matches = []
    for ang_num in sorted(verses_by_ang.keys()):
        verses = verses_by_ang[ang_num]
        normalized_verses = [_normalize_gurmukhi(v.get("gurmukhi", "")) for v in verses]
        for start in range(len(verses)):
            parts = []
            for end in range(start, min(start + max_window, len(verses))):
                if not normalized_verses[end]:
                    break
                parts.append(normalized_verses[end])
                if len(parts) < 2:
                    continue
                combined = " ".join(parts)
                if len(combined) > len(normalized) * 1.25:
                    break
                if combined == normalized:
                    passage_verses = verses[start:end + 1]
                    matches.append(_passage_match(
                        ang_num,
                        passage_verses[0]["line"],
                        passage_verses[-1]["line"],
                        passage_verses,
                    ))
                    break
    return matches


def _build_verify_index():
    """Build normalized text indexes for verification matching."""
    for ang_num in sorted(verses_by_ang.keys()):
        for verse in verses_by_ang[ang_num]:
            g = _normalize_gurmukhi(verse.get("gurmukhi", ""))
            if g:
                _gurmukhi_index.append((g, ang_num, verse["line"], verse))
            e = verse.get("english", "").strip().lower()
            if e:
                _english_index.append((e, ang_num, verse["line"], verse))


@mcp.tool()
def verify_gurbani(text: str, script: str = "auto") -> dict:
    """Check whether a claimed Gurbani quote appears in the released source files.

    Pass any text that claims to be from Sri Guru Granth Sahib Ji and receive
    verification with exact source location, or a warning that the quote could
    not be found. Use this tool BEFORE presenting any Gurbani to a user.
    Citation-first: results always return ang and line numbers for verified
    matches. Original Gurmukhi is the most reliable input.

    Args:
        text: The claimed Gurbani text to verify. Best results with original
            Gurmukhi. Transliteration and English work when the corpus
            contains those layers; public v1 includes DSSK English.
        script: Which script the text is in: "gurmukhi", "transliteration",
            "english", or "auto" (default, tries to detect).

    Returns:
        Verification result with status ("verified", "partial_match", or
        "not_found"), source location if found, and closest matches for
        partial results.
    """
    text = text.strip()
    if not text:
        return {"status": "error", "message": "No text provided"}
    if len(text) > 1000:
        return {"status": "error", "message": "Input too long. Maximum 1000 characters."}
    if contains_profane_words(text):
        return {
            "status": "error",
            "message": (
                "Input contains language that is not suitable for Gurbani "
                "verification. Remove unrelated or profane wording and paste "
                "the claimed Gurbani text."
            ),
        }

    # Auto-detect script
    if script == "auto":
        # If it contains Gurmukhi Unicode range (U+0A00-U+0A7F), it's Gurmukhi
        if any("\u0A00" <= ch <= "\u0A7F" for ch in text):
            script = "gurmukhi"
        else:
            # Check for English: if it contains common English words, it's English
            text_lower = text.lower()
            english_markers = (" the ", " and ", " of ", " is ", " are ", " was ",
                             " his ", " her ", " who ", " with ", " from ", " not ",
                             " shall ", " those ", " this ", " that ")
            if any(m in f" {text_lower} " for m in english_markers):
                script = "english"
            # Otherwise check for transliteration patterns
            elif "||" in text or "(n)" in text:
                script = "transliteration"
            else:
                # Ambiguous roman text: try English first, then conservative
                # transliteration fallback below if the phrase is long enough.
                script = "english_then_transliteration"

    if script == "gurmukhi":
        return _verify_gurmukhi(text)
    elif script == "english":
        return _verify_english(text)
    elif script == "english_then_transliteration":
        english_result = _verify_english(text)
        if english_result["status"] == "verified":
            return english_result

        words = re.findall(r"[a-z0-9]+", text.lower())
        if len(words) >= 4 and len(" ".join(words)) >= 16:
            transliteration_result = _verify_transliteration(text)
            if transliteration_result["status"] == "verified":
                return transliteration_result

        return english_result
    else:
        return _verify_transliteration(text)


def _verify_gurmukhi(text: str) -> dict:
    """Verify Gurmukhi text against source."""
    normalized = _normalize_gurmukhi(text)
    if not normalized:
        return {"status": "error", "message": "No Gurmukhi text after normalization"}

    passage_matches = _find_gurmukhi_passage_matches(normalized)
    if len(passage_matches) == 1:
        return {
            "status": "verified",
            "message": "Exact multi-line passage found in the Open Granth source files.",
            **passage_matches[0],
        }

    if len(passage_matches) > 1:
        return {
            "status": "partial_match",
            "message": "This Gurmukhi passage appears in multiple places. It is an exact passage match, but not specific enough for a single verified citation.",
            "closest_matches": passage_matches[:5],
        }

    # Pass 1: exact match on normalized Gurmukhi.
    exact_matches = []
    for g, ang_num, line, verse in _gurmukhi_index:
        if normalized == g:
            exact_matches.append(_verify_match(ang_num, line, verse))

    if len(exact_matches) == 1:
        return {
            "status": "verified",
            "message": "Exact match found in the Open Granth source files.",
            **exact_matches[0],
        }

    if len(exact_matches) > 1:
        return {
            "status": "partial_match",
            "message": _multiple_exact_matches_message("Gurmukhi"),
            "closest_matches": exact_matches[:5],
        }

    # Pass 2: token-sequence match. The claimed text must appear as a
    # contiguous, boundary-respecting token sequence within a verse. Reverse
    # containment (verse inside input) removed per review.
    substring_matches = []
    _input_toks = normalized.split()
    for g, ang_num, line, verse in _gurmukhi_index:
        if _token_sequence_in_line(_input_toks, g.split()):
            substring_matches.append(_verify_match(ang_num, line, verse))

    if len(substring_matches) == 1:
        return {
            "status": "verified",
            "message": "Text found as part of a verse in the Open Granth source files.",
            **substring_matches[0],
        }

    if len(substring_matches) > 1:
        return {
            "status": "partial_match",
            "message": _multiple_exact_matches_message("Gurmukhi"),
            "closest_matches": substring_matches[:5],
        }

    # Pass 3: fuzzy match; find closest matches by bigram similarity
    candidates = []
    for g, ang_num, line, verse in _gurmukhi_index:
        sim = _similarity(normalized, g)
        if sim > 0.5:
            candidates.append((sim, ang_num, line, verse))

    if candidates:
        candidates.sort(key=lambda x: -x[0])
        best = candidates[:3]
        matches = []
        for sim, ang_num, line, verse in best:
            meta = metadata[ang_num]
            matches.append({
                "similarity": round(sim, 2),
                "ang": ang_num,
                "line": line,
                "author": meta["author"],
                "raag": meta["raag"],
                "verse": verse,
            })
        return {
            "status": "partial_match",
            "message": "No exact match found. These verses are the closest matches. The quoted text may be altered or incorrectly transcribed.",
            "closest_matches": matches,
        }

    return {
        "status": "not_found",
        "message": "No matching text was found in the Open Granth source files. It may be fabricated, from a different source, or too heavily altered to match.",
    }


def _verify_english(text: str) -> dict:
    """Verify English translation text against source."""
    text_clean = _normalize_english_verification_text(text)
    words = re.findall(r"[a-z0-9]+", text_clean)
    if len(words) < 3 or len(text_clean) < 16:
        return {
            "status": "error",
            "message": "English input is too short to verify reliably. Use Search for keywords, or paste a longer exact translation phrase.",
        }

    # Pass 1: exact whole-line match outranks containment. A unique exact
    # line must not be drowned by shorter lines contained in the input
    # (e.g. the So Dar header on Ang 8 versus the Rehras headers it contains).
    exact_matches = []
    matches = []
    for e, ang_num, line, verse in _english_index:
        e_clean = _normalize_english_verification_text(e)
        if e_clean == text_clean:
            exact_matches.append(_verify_match(ang_num, line, verse))
        elif _token_sequence_in_line(words, re.findall(r"[a-z0-9]+", e_clean)):
            # Boundary-respecting token sequence only. Reverse containment
            # (a short corpus line inside the input) removed per review.
            matches.append(_verify_match(ang_num, line, verse))

    if len(exact_matches) == 1:
        return {
            "status": "verified",
            "message": "English translation found in the Open Granth English study layer.",
            **exact_matches[0],
        }

    if len(exact_matches) > 1:
        return {
            "status": "partial_match",
            "message": _multiple_exact_matches_message("English"),
            "closest_matches": exact_matches[:5],
        }

    # Pass 2: exact normalized substring match. English verification must not
    # silently choose the first hit for a phrase that appears in multiple places.
    if len(matches) == 1:
        match = matches[0]
        return {
            "status": "verified",
            "message": "English translation found in the Open Granth English study layer.",
            **match,
        }

    if len(matches) > 1:
        return {
            "status": "partial_match",
            "message": _multiple_exact_matches_message("English"),
            "closest_matches": matches[:5],
        }

    # A three-word miss is weak evidence of absence (paraphrase or spacing
    # variant); only 4+ word misses earn a confident not_found verdict.
    if len(words) < 4:
        return {
            "status": "error",
            "message": "English input is too short to verify reliably. Use Search for keywords, or paste a longer exact translation phrase.",
        }

    # No fuzzy matching for English. Exact substring or not_found.
    # Fuzzy English causes false partial_match on common religious vocabulary.
    # For best results, verify with the original Gurmukhi.
    return {
        "status": "not_found",
        "message": "This English text does not exactly match a verse translation. If this is rough or alternate wording, use Search. For verification, use the original Gurmukhi when possible.",
    }


def _normalize_english_verification_text(text: str) -> str:
    """Normalize English for strict phrase verification.

    English verification intentionally avoids fuzzy matching. This normalizer
    only absorbs punctuation/case/spacing differences so exact translation
    phrases still match while generic spiritual wording does not.
    """
    t = (text or "").lower().strip()
    t = re.sub(r"\|\|.*?\|\|", " ", t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _verify_transliteration(text: str) -> dict:
    """Verify transliteration text against source."""
    text_lower = text.lower().strip()
    text_clean = re.sub(r"\|\|.*?\|\|", "", text_lower).strip()

    # Pass 1: exact whole-line match outranks containment, mirroring the
    # Gurmukhi and English matchers.
    exact_matches = []
    matches = []
    for ang_num in sorted(verses_by_ang.keys()):
        for verse in verses_by_ang[ang_num]:
            translit = verse.get("transliteration", "").lower()
            translit_clean = re.sub(r"\|\|.*?\|\|", "", translit).strip()
            if len(translit_clean) < 10:
                continue
            if translit_clean == text_clean:
                exact_matches.append(_verify_match(ang_num, verse["line"], verse))
            elif _token_sequence_in_line(
                re.findall(r"[a-z]+", text_clean),
                re.findall(r"[a-z]+", translit_clean),
            ):
                # Boundary-respecting token sequence only. Reverse containment
                # (a short corpus line inside the input, e.g. "rad" inside
                # "a-rad-aas") removed per review; the old <10 length guard
                # merely hid that defect for short lines.
                matches.append(_verify_match(ang_num, verse["line"], verse))

    if len(exact_matches) == 1:
        return {
            "status": "verified",
            "message": "Transliteration matches a line in the Open Granth Roman layer.",
            **exact_matches[0],
        }

    if len(exact_matches) > 1:
        return {
            "status": "partial_match",
            "message": _multiple_exact_matches_message("transliteration"),
            "closest_matches": exact_matches[:5],
        }

    # Pass 2: containment (require minimum length to avoid short-verse false matches)
    if len(matches) == 1:
        return {
            "status": "verified",
            "message": "Transliteration matches a line in the Open Granth Roman layer.",
            **matches[0],
        }

    if len(matches) > 1:
        return {
            "status": "partial_match",
            "message": _multiple_exact_matches_message("transliteration"),
            "closest_matches": matches[:5],
        }

    # No fuzzy matching for transliteration. Exact substring or not_found.
    # Transliteration spelling varies too much between systems for reliable fuzzy.
    return {
        "status": "not_found",
        "message": "This transliteration does not match any line in the Open Granth Roman layer.",
    }


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

# Validate corpus exists before indexing
if not SOURCE_DIR.exists():
    print(f"Error: Corpus directory not found: {SOURCE_DIR}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Open Granth requires a local SGGS corpus (ang-NNNN.md files).", file=sys.stderr)
    print("Provide the path via one of:", file=sys.stderr)
    print("  --source-dir /path/to/source", file=sys.stderr)
    print("  OPEN_GRANTH_SOURCE=/path/to/source", file=sys.stderr)
    print("  or run from a directory containing corpus/", file=sys.stderr)
    sys.exit(1)

if not list(SOURCE_DIR.glob("ang-*.md")):
    print(f"Error: No ang-*.md files found in {SOURCE_DIR}", file=sys.stderr)
    sys.exit(1)

print(f"Corpus: {SOURCE_DIR}", file=sys.stderr)
build_index()
_build_verify_index()
print(f"Verify index: {len(_gurmukhi_index)} Gurmukhi entries, {len(_english_index)} English entries", file=sys.stderr)

if __name__ == "__main__":
    mcp.run(transport="stdio")
