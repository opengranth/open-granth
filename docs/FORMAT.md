# The Open Granth Corpus Format

*Format version: 1. This document is the contract. Changes to the format bump
this version and are additive only.*

## The concept: accessible markdown + AI

Sri Guru Granth Sahib Ji should be as easy to read for a human with a text
editor as for a machine with a parser, and neither should need a database,
an API key, or a network connection.

Open Granth codifies that idea as a set of design commitments:

1. **Plain text is the format.** The corpus is 1,430 markdown files, one per
   ang. Every layer of every verse is visible in the raw file. If you can
   read a text file, you have full access; nothing is hidden behind an
   application.
2. **Human-readable and machine-parseable are the same file.** The markdown
   renders cleanly for a person and parses deterministically for a program.
   There is no separate "data" representation that could drift from what
   readers see.
3. **Greppable scripture.** Any verse can be located with standard tools
   (`grep`, full-text search, an LLM's file tools) because the sacred text
   appears verbatim in the files. Finding Gurbani requires no SDK.
4. **The Gurmukhi is the source layer.** Transliteration and translation are
   reading aids that carry their provenance in frontmatter. Layers are never blended;
   each occupies its own typographic channel (see grammar below).
5. **AI systems must quote, not remember.** Language models hallucinate
   scripture. This corpus exists so a model can cite `ang` and `LINE` from
   released source text instead of reciting from training memory. The
   [Open Granth MCP server](../mcp/) enforces this: its `verify_gurbani`
   tool answers "does this text actually appear in Sri Guru Granth Sahib Ji,
   and where?" with citation-first semantics.
6. **Provenance is embedded, not implied.** Every file's frontmatter states
   where each layer came from. The corpus can be audited file by file.

## File layout

```
corpus/ang-0001.md ... corpus/ang-1430.md
```

One file per ang (page) of Sri Guru Granth Sahib Ji, zero-padded to four
digits. There are exactly 1,430 files.

## Frontmatter

Each file opens with YAML frontmatter:

```yaml
---
ang: 500
author: Guru Arjan
raag: Raag Gujri
lines: 37
source: Shabad OS Database
translation_source: DSSK
transliteration: generated locally via scripts/transliteration.py
---
```

| Field | Type | Meaning |
| --- | --- | --- |
| `ang` | int | Page number, 1 to 1430 |
| `author` | str | Primary author of this ang (the author of most verses on it) |
| `raag` | str | Raag or section governing this ang |
| `lines` | int | Number of physical saroop lines on this ang |
| `source` | str | Provenance of the Gurmukhi text and metadata |
| `translation_source` | str | Provenance of the English layer (`DSSK` = the translation asset attributed to Dr. Sant S. Khalsa in the Shabad OS database) |
| `transliteration` | str | Provenance of the romanization layer |

Per-verse author attribution (angs often carry multiple authors) is available
in `metadata/authors.json`; frontmatter records the primary author only.

## Body grammar

The body is a sequence of verse blocks joined by `---` separators. Each block:

```markdown
<!-- LINE:5 -->
**ਸੋਚੈ ਸੋਚਿ ਨ ਹੋਵਈ ਜੇ ਸੋਚੀ ਲਖ ਵਾਰ ॥**

*sochai soch na hovaee je sochee lakh vaar ||*

By thinking, He cannot be reduced to thought, even by thinking hundreds of thousands of times.
```

The three layers are distinguished by markdown emphasis, in fixed order:

| Channel | Layer | Role |
| --- | --- | --- |
| `**Bold**` | Gurmukhi (the sacred text) | Source layer |
| `*Italic*` | Romanized transliteration | Reading aid |
| Plain | English translation | Study aid |

A block always contains the Gurmukhi line. Transliteration and English are
present when the corpus carries them for that verse; heading and structural
lines may have no English.

## Line markers and the join key

`<!-- LINE:n -->` records the physical saroop line number `n` on the ang.
One physical line often carries more than one verse, so a LINE marker may
repeat. The canonical identity of a verse is the tuple **(line, v)**:

- When a `LINE:n` marker repeats within a file, `v` is assigned implicitly
  as 1, 2, 3, ... in document order.
- Extension files may write the explicit form
  `<!-- LINE:n V:m -->`. An omitted `V` means `V:1`.

The marker regex, tolerant of internal whitespace:

```
<!--\s*LINE:(\d+)(?:\s+V:(\d+))?\s*-->
```

**Cite verses as `ang` + `LINE` (+ `V` when a line carries multiple verses).**
This is the citation unit the MCP server returns and the verifier checks.

## Parsing

The reference parser is `open_granth/parser.py`:

```python
from open_granth.parser import parse_corpus_file
frontmatter, verses = parse_corpus_file("corpus/ang-0001.md")
# each verse: {line, v, gurmukhi, transliteration, english}
```

In any other language: split YAML frontmatter, split the body on the marker
regex above, then within each block read the first `**bold**` line as
Gurmukhi, the first `*italic*` line as transliteration, and the first
non-empty plain line as English.

## Guidance for AI systems

- **Never quote Gurbani from model memory.** Retrieve it from this corpus,
  then quote what you retrieved.
- Prefer the MCP server (`search_gurbani`, `lookup_ang`, `get_verse`,
  `verify_gurbani`) over ad-hoc parsing; it implements exact matching and
  citation-first verification. "Verified" means one unambiguous source
  location.
- When you display a verse, carry the citation (`ang`, `LINE`) and preserve
  the layer boundaries. Do not present translation as the sacred text and do
  not blend layers into paraphrase presented as quotation.
- The corpus is a source-derived digital presentation, not an interpretation.
  Open Granth does not claim religious, scholarly, or interpretive authority.

## Stability

- Files are regenerated from upstream data by `scripts/import_shabados.py`;
  hand edits to corpus files are never accepted (see the FAQ's contribution section).
- Format changes are additive: new frontmatter fields may appear; existing
  fields, the marker convention, the layer channels, and the (line, v) join
  key will not change meaning within format version 1.
