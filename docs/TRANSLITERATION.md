# Open Granth Transliteration Scheme

Open Granth's romanized transliteration layer is generated locally by
`scripts/transliteration.py`. It is an original work of this project. It does
not reproduce, and does not attempt to reproduce, any external transliteration
system, including those distributed by other Gurbani databases or apps.

## Design goals

1. Readable ASCII phonetics for readers who cannot read Gurmukhi script.
2. Deterministic output: the same Gurmukhi input always yields the same roman
   output, so the layer is reproducible from the corpus at any time.
3. Dependency-free: plain Python, no external transliteration libraries.

This is a practical reading aid, not an academic romanization. It does not use
ISO 15919, IAST, or diacritics. Within Open Granth, the Gurmukhi is the source
layer in every corpus file.

## How it is generated

Each corpus line's Gurmukhi text is passed through
`normalize_gurmukhi_text()` (whitespace and punctuation normalization) and then
`transliterate_gurmukhi()` (character mapping plus word-level ending rules).
The output is stored in the corpus markdown as the italic line under each bold
Gurmukhi line, and each ang file's frontmatter records the provenance:
`transliteration: generated locally via scripts/transliteration.py`.

## Character mappings

### INDEPENDENT_VOWELS
| Gurmukhi | Roman |
| --- | --- |
| ਅ | a |
| ਆ | aa |
| ਇ | i |
| ਈ | ee |
| ਉ | u |
| ਊ | oo |
| ਏ | e |
| ਐ | ai |
| ਓ | o |
| ਔ | au |

### VOWEL_SIGNS
| Gurmukhi | Roman |
| --- | --- |
| ਾ | aa |
| ਿ | i |
| ੀ | ee |
| ੁ | u |
| ੂ | oo |
| ੇ | e |
| ੈ | ai |
| ੋ | o |
| ੌ | au |

### CONSONANTS
| Gurmukhi | Roman |
| --- | --- |
| ਕ | k |
| ਖ | kh |
| ਗ | g |
| ਘ | gh |
| ਙ | ng |
| ਚ | ch |
| ਛ | chh |
| ਜ | j |
| ਝ | jh |
| ਞ | nj |
| ਟ | t |
| ਠ | th |
| ਡ | d |
| ਢ | dh |
| ਣ | n |
| ਤ | t |
| ਥ | th |
| ਦ | d |
| ਧ | dh |
| ਨ | n |
| ਪ | p |
| ਫ | ph |
| ਬ | b |
| ਭ | bh |
| ਮ | m |
| ਯ | y |
| ਰ | r |
| ਲ | l |
| ਵ | v |
| ੜ | R |
| ਸ਼ | sh |
| ਸ | s |
| ਹ | h |
| ਖ਼ | kh |
| ਗ਼ | gh |
| ਜ਼ | z |
| ਫ਼ | f |
| ਲ਼ | l |

## Word-level rules

Beyond character mapping, the transliterator applies ending rules that are
covered by unit tests in `tests/test_transliteration.py`, including:

- Nasalization signs render as `(n)`.
- Gurmukhi digits render as ASCII digits.
- Source punctuation noise is removed during normalization.
- Terminal `u` and `i` vowel endings are preserved or stripped according to
  the generator's documented rules (see the test cases for the exact behavior).

## Quality and limitations

- The scheme is approximate. It favors readability over phonetic precision and
  does not mark vowel length, tone, or subjoined consonant nuances beyond the
  mappings above.
- Retroflex and dental consonants collapse to the same Latin letters: both
  ਟ and ਤ render as `t`, both ਡ and ਦ as `d`, both ਠ and ਥ as `th`, and both
  ਢ and ਧ as `dh`. The Roman line is a reading aid, not an authoritative
  phonetic transliteration. Within Open Granth, the Gurmukhi is the source layer.
- The layer was quality-checked against publicly available Gurbani
  transliterations as a reference during development. No external
  transliteration text was copied into this project.
- Corrections are welcome. Open an issue or see TAKEDOWN.md for concerns.

## Planned improvements

- Common-spelling normalization for MCP search, so familiar spellings such as
  `waheguru` find the corpus form `vaahiguroo`. This could be a deterministic
  alias table rather than approximate matching. Deferred past the first
  release because search behavior in a verification-focused project deserves
  careful design, not a launch-day patch.
- A deliberate decision on the long-term transliteration standard before any
  regeneration of the corpus Roman layer. Shabad OS Latin (the
  pronunciation-oriented scheme, not the mechanical LatinScholar) is the
  leading candidate under evaluation. Any migration would be post-release
  and atomic: pin a library version, generate side by side for all corpus
  lines, review a representative sample with pronunciation experience,
  update provenance and licensing language, and regenerate the whole layer
  in a versioned release.

## License

The transliteration generator is MIT-licensed with the rest of the project
code. The generated transliteration layer in `corpus/` is dedicated to the
public domain under CC0 1.0, consistent with the project's aim that every
layer of the corpus be freely reusable.
