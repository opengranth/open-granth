<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="branding/wordmark-inverse.svg">
    <img src="branding/wordmark.svg" alt="Open Granth ॥" width="420">
  </picture>
</p>

**Sri Guru Granth Sahib Ji in AI-ready Markdown.**

Open Granth is Markdown-first, with verification and MCP tooling built on top.

Three core layers in one repo:

- 1,430 angs of Gurbani in markdown (Gurmukhi, romanized transliteration, and English translation)
- A verification tool that checks any claimed Gurbani quote against source text
- An MCP server that lets AI models query the corpus instead of generating from memory

## Why

AI platforms are generating fabricated Gurbani. Wrong verses, wrong ang references, invented scripture presented as real. Open Granth gives an AI client a way to retrieve Gurbani from the released source files with ang and line citations instead of relying on model memory.

## Scope: first release

The first release ships:

- Gurmukhi corpus (all 1,430 angs)
- Romanized transliteration
- English translation from the DSSK asset in the Shabad OS database
- Static browsable site
- Citation-first verification tool
- MCP server for AI clients

English is an imported study aid, not Open Granth's own interpretation. Within Open Granth, the Gurmukhi is the source layer; the Roman and English layers are reading aids. See [FAQ.md](FAQ.md) and [NOTICE](NOTICE) for provenance and takedown handling.

## Versioning

Open Granth uses calendar versioning: a release is identified by the date its snapshot was finalized, in `YYYY.MM.DD` form, with a matching git tag (`v2026.08.16`). Each release names an exact dated snapshot of the corpus, site, verifier, and MCP tooling; behavioral changes and compatibility notes are documented with each release. In the unlikely event of two releases in one day, the second carries a `.1` suffix.

Development began independently in January 2026. The Open Granth v1 release snapshot was finalized on August 16, 2026.

## Built by Open Granth

Beyond the corpus, several components are original to this project:

- **Transliteration engine** (`scripts/transliteration.py`): rule-based, dependency-free Gurmukhi romanization. The Roman line is mechanically generated as an approximate companion to the Gurmukhi, not an authoritative pronunciation guide; the Gurmukhi is the source layer (see [docs/TRANSLITERATION.md](docs/TRANSLITERATION.md)). No external transliteration text was copied; the generated layer is dedicated to the public domain under CC0 1.0.
- **Citation-first verifier**: multi-pass matching (exact → passage → substring → space-insensitive) that returns ang and line, guarded by a frozen 49-test release gate.
- **Corpus format and parser**: one markdown file per ang, with a shared parser (`open_granth/parser.py`) used by the site build and search index. The MCP server currently embeds its own copy of the parsing logic.
- **MCP server**: seven tools that let AI clients retrieve text from the released source files instead of generating it.
- **Static site generator**: builds all 1,430 ang pages and the search index from the corpus alone, and preserves the separately authored verification page across rebuilds.

## What's Here

```
open-granth/
├── corpus/                 # Public build source (Gurmukhi + transliteration + DSSK English)
│
├── mcp/
│   └── server.py           # MCP server with 7 tools
│
├── site/                   # Static site (all 1,430 angs browsable)
│   ├── ang/                # Individual ang pages
│   ├── verify/             # Gurbani verification page
│   ├── search/             # Gurmukhi, transliteration, and English search
│   └── data/               # verses.json
│
├── metadata/
│   ├── authors.json        # 36 upstream author entries with text-entry counts
│   └── raags.json          # 31 raags + 13 sections
│
├── open_granth/
│   └── parser.py           # Shared markdown parser
│
├── scripts/
│   ├── build_site.py       # Static site generator
│   ├── import_shabados.py  # Corpus import from local Shabad OS database
│   └── transliteration.py  # Local Gurmukhi romanization
│
└── tests/
    ├── test_corpus_order.py       # Physical ang order, homepage anchors
    ├── test_parser.py             # Corpus markdown parser
    ├── test_search_gurbani.py     # Gurmukhi search boundaries
    ├── test_transliteration.py    # Romanization mappings
    ├── test_verify_gurbani.py     # Verifier audit harness
    └── verify_release_gate.py     # 49-test frozen release gate
```

## MCP Server

Seven tools for querying Sri Guru Granth Sahib Ji:

| Tool | What It Does |
|------|-------------|
| `search_gurbani` | Word-level search with stemming and relevance scoring |
| `lookup_ang` | Full ang by page number (1-1430) |
| `get_verse` | Specific verse by ang and line |
| `search_by_raag` | Find angs by raag (musical mode) |
| `search_by_author` | Find angs by author (Guru or Bhagat) |
| `random_ang` | Return a random ang |
| `verify_gurbani` | Check whether a claimed quote appears in the released source files |

Install and run locally:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
OPEN_GRANTH_SOURCE=corpus python mcp/server.py
```

Or connect it to an MCP client such as Claude Code. The server locates the corpus bundled beside it, so no extra configuration is needed:

```bash
claude mcp add open-granth -- /path/to/open-granth/.venv/bin/python /path/to/open-granth/mcp/server.py
```

Search behavior: transliteration searches follow Open Granth's romanization scheme, documented in [docs/TRANSLITERATION.md](docs/TRANSLITERATION.md). Search for `vaahiguroo` rather than `waheguru`. Author searches use corpus author names, such as `Guru Nanak`. Common-spelling and author-name normalization are planned improvements.

### Verify Tool

The trust layer. Pass any text claimed to be from Sri Guru Granth Sahib Ji and receive:

- **verified**: exact match found, with ang, line, author, raag, and full verse
- **partial_match**: multiple exact matches, or a close Gurmukhi match found
- **not_found**: no matching text was found in the released source files

Fuzzy matching is reserved for Gurmukhi only. English and transliteration use exact substring matching. If an exact phrase appears in multiple places, the verifier returns multiple matches instead of pretending one citation is definitive. "Verified" means one unambiguous source location.

## Static Site

Browse all 1,430 angs with Gurmukhi, transliteration, and English.

- Paste any text on the verify page to check it against the released corpus
- Search across Gurmukhi, transliteration, and English
- Self-hosted fonts, offline-capable core experience
- Content Security Policy on every page

## Testing

Run the full suite and the frozen release gate from the repo root (after the
venv setup shown above):

```bash
.venv/bin/python -m pytest
.venv/bin/python tests/verify_release_gate.py
```

What each suite protects:

- `test_corpus_order.py`: physical ang ordering, homepage deep links, and section anchors on shared-boundary angs
- `test_parser.py`: markdown line markers, corpus parsing, and English extraction
- `test_search_gurbani.py`: Gurmukhi whole-word search boundaries, with English and romanized search behavior pinned
- `test_transliteration.py`: character mappings, vowel endings, nasalization, digits, and uncommon Gurmukhi signs
- `test_verify_gurbani.py`: exact and repeated passages, fabricated-text rejection, and language detection
- `verify_release_gate.py`: 49 curated release-blocking cases covering genuine, altered, fabricated, and out-of-scope text plus citation accuracy; expected result is 49/49 passed

## Data Source

The public build is rendered from an independent corpus derived from the [Shabad OS database](https://github.com/shabados/database). Gurbani text and metadata come from Shabad OS data. Transliteration is generated locally by Open Granth. English translation is imported from the `DSSK` translation asset in the Shabad OS database, attributed there to Dr. Sant S. Khalsa.

Open Granth is independent and is not affiliated with Shabad OS or any Sikh institution. See [NOTICE](NOTICE) for full attribution, and [docs/provenance.md](docs/provenance.md) for the exact upstream assets and import process.

## Guiding Principles

- **Vand Chhako**: sharing with others
- **Naam Japo**: meditation on the Divine Name
- **Kirat Karo**: honest, earnest work
- No paywall, no ads, no sale of access to Gurbani
- No analytics cookies, no visitor profiling, no collection of Search or Verify text; only privacy-preserving aggregate traffic measurement
- Offline-first operation
- Attribution to upstream data stewards is explicit and persistent

## License

Project code and tooling are released under MIT. See [LICENSE](LICENSE). The MIT license governs the code only, not the scripture content or translation text. Open Granth does not claim copyright over Gurbani text or third-party translation text included from upstream sources.

The romanized transliteration layer in `corpus/` is generated locally by Open Granth and dedicated to the public domain under CC0 1.0 (see [docs/TRANSLITERATION.md](docs/TRANSLITERATION.md)), so the generated Roman layer remains freely reusable.

See [NOTICE](NOTICE) for attribution and [TAKEDOWN.md](TAKEDOWN.md) for the takedown request process.

---

ੴ ਸਤਿ ਨਾਮੁ

*Ik Onkar Satnam*
