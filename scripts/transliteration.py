#!/usr/bin/env python3
"""Lightweight Gurmukhi -> roman transliteration utilities.

This is the deterministic, rule-based transliterator that generates the
corpus Roman layer at build time. It aims for readable ASCII phonetics
rather than strict academic transliteration.

Important:
    - It is approximate.
    - It does not try to exactly reproduce any external transliteration system.
    - It is designed to be dependency-free and easy to adjust.
"""

from __future__ import annotations

import re


VOWEL_SIGNS = {
    "ਾ": "aa",
    "ਿ": "i",
    "ੀ": "ee",
    "ੁ": "u",
    "ੂ": "oo",
    "ੇ": "e",
    "ੈ": "ai",
    "ੋ": "o",
    "ੌ": "au",
}

INDEPENDENT_VOWELS = {
    "ਅ": "a",
    "ਆ": "aa",
    "ਇ": "i",
    "ਈ": "ee",
    "ਉ": "u",
    "ਊ": "oo",
    "ਏ": "e",
    "ਐ": "ai",
    "ਓ": "o",
    "ਔ": "au",
}

CONSONANTS = {
    "ਕ": "k",
    "ਖ": "kh",
    "ਗ": "g",
    "ਘ": "gh",
    "ਙ": "ng",
    "ਚ": "ch",
    "ਛ": "chh",
    "ਜ": "j",
    "ਝ": "jh",
    "ਞ": "nj",
    "ਟ": "t",
    "ਠ": "th",
    "ਡ": "d",
    "ਢ": "dh",
    "ਣ": "n",
    "ਤ": "t",
    "ਥ": "th",
    "ਦ": "d",
    "ਧ": "dh",
    "ਨ": "n",
    "ਪ": "p",
    "ਫ": "ph",
    "ਬ": "b",
    "ਭ": "bh",
    "ਮ": "m",
    "ਯ": "y",
    "ਰ": "r",
    "ਲ": "l",
    "ਵ": "v",
    "ੜ": "R",
    "ਸ਼": "sh",
    "ਸ": "s",
    "ਹ": "h",
    "ਖ਼": "kh",
    "ਗ਼": "gh",
    "ਜ਼": "z",
    "ਫ਼": "f",
    "ਲ਼": "l",
}

GURMUKHI_DIGITS = str.maketrans("੦੧੨੩੪੫੬੭੮੯", "0123456789")
DANDA_CHARS = {"।", "॥"}
SPECIALS = {
    "ੴ": "ikOankaar",
}

WORD_BREAK_RE = re.compile(r"(\s+)")


def _is_gurmukhi(char: str) -> bool:
    return "\u0A00" <= char <= "\u0A7F"


def normalize_gurmukhi_text(text: str) -> str:
    """Remove source-specific punctuation noise before transliteration."""
    if not text:
        return ""

    normalized = text.replace("\u200d", "").replace("\u200c", "")
    # Shabad OS page data includes ASCII punctuation used as segmentation hints.
    # They harm roman output more than they help, so strip them here.
    normalized = re.sub(r"\s*[.;,]\s*", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _transliterate_word(word: str) -> str:
    result: list[str] = []
    double_next = False
    preserve_terminal_u = word.endswith("ਹੁ")
    preserve_terminal_i = word.endswith(("ਹਿ", "ੑਿ"))
    i = 0

    while i < len(word):
        char = word[i]

        if char == "ੱ":
            double_next = True
            i += 1
            continue

        if char in ("ੰ", "ਂ"):
            result.append("(n)")
            i += 1
            continue

        if char == "ਁ":
            result.append("(n)")
            i += 1
            continue

        if char == "ਃ":
            result.append("h")
            i += 1
            continue

        if char == "ੑ":
            if result and result[-1].endswith("a") and not result[-1].endswith(("aa", "ai", "au")):
                result[-1] = result[-1][:-1]
            result.append("h")
            i += 1
            continue

        if char == "ੵ":
            if result and result[-1].endswith("a") and not result[-1].endswith(("aa", "ai", "au")):
                result[-1] = result[-1][:-1]
            result.append("y")
            i += 1
            continue

        if char == "੍":
            i += 1
            continue

        if char in DANDA_CHARS:
            result.append("|" if char == "।" else "||")
            i += 1
            continue

        if char in SPECIALS:
            result.append(SPECIALS[char])
            i += 1
            continue

        if char in INDEPENDENT_VOWELS:
            result.append(INDEPENDENT_VOWELS[char])
            i += 1
            continue

        if char in CONSONANTS:
            base = CONSONANTS[char]
            if double_next and base:
                base = base[0] + base
                double_next = False

            vowel = "a"
            if i + 1 < len(word):
                nxt = word[i + 1]
                if nxt in VOWEL_SIGNS:
                    vowel = VOWEL_SIGNS[nxt]
                    i += 1
                elif nxt == "੍":
                    vowel = ""
                    i += 1

            result.append(base + vowel)
            i += 1
            continue

        if char in VOWEL_SIGNS:
            result.append(VOWEL_SIGNS[char])
            i += 1
            continue

        if char.isdigit():
            result.append(char)
            i += 1
            continue

        result.append(char)
        i += 1

    transliterated = "".join(result).translate(GURMUKHI_DIGITS)

    # Pronunciation-oriented cleanup. These are deliberately conservative and
    # target the common SGGS display style used by Open Granth.
    # Terminal ਹੁ and ਹਿ are meaningful verbal suffixes and are preserved;
    # other terminal -i and -u forms are stripped for readability.
    if not preserve_terminal_i:
        transliterated = re.sub(r"([kgcjtdnpbmyrlvshfzhR]+)i$", r"\1", transliterated)
    if not preserve_terminal_u:
        transliterated = re.sub(r"([kgcjtdnpbmyrlvshfzhR]+)u$", r"\1", transliterated)
    if len(transliterated) > 2:
        transliterated = re.sub(r"(?<!a)a$", "", transliterated)
    transliterated = re.sub(r"\|\|\s*\|", "||", transliterated)

    return transliterated


def transliterate_gurmukhi(text: str) -> str:
    """Convert Gurmukhi text to readable ASCII transliteration.

    Non-Gurmukhi text is passed through unchanged.
    """
    if not text:
        return ""

    text = normalize_gurmukhi_text(text)

    pieces: list[str] = []
    for token in WORD_BREAK_RE.split(text.strip()):
        if not token:
            continue
        if token.isspace():
            pieces.append(token)
            continue

        if any(_is_gurmukhi(ch) or ch in DANDA_CHARS for ch in token):
            pieces.append(_transliterate_word(token))
        else:
            pieces.append(token)

    out = "".join(pieces)
    out = re.sub(r"\s+([.,;:!?])", r"\1", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out
