# Provenance

This document records the public v1 provenance for Open Granth.

## Public v1 Corpus

The public corpus in `corpus/` is generated from the local Shabad OS SQLite
database package at:

```text
node_modules/@shabados/database/dist/master.sqlite
```

The importer is:

```text
scripts/import_shabados.py
```

The v1 import command is:

```bash
python3 scripts/import_shabados.py --translation-asset DSSK --out-dir corpus --start 1 --end 1430
```

## Upstream Database and Assets

The v1 import reads `@shabados/database` version 5.0.0-next.0 and selects its
`SGGS` source (Sri Guru Granth Sahib).

- Gurmukhi: the importer selects rows typed `primary`. Within the SGGS source,
  all 60,555 primary rows come from the `SSA2` asset, identified in the
  upstream database as Shabadaarth and attributed there to the SGPC Committee,
  Sri Amritsar, publication dates 2009-2012, 4 volumes.
- English: the `DSSK` asset, selected explicitly by the import command. It
  supplies 60,555 rows, one per primary line, and is attributed in the
  upstream database to Dr. Sant S. Khalsa, publication date 2013-03.

These counts match the public corpus exactly: 1,430 angs, 60,555 primary text entries.

## Layers

- Gurmukhi text and metadata: imported from Shabad OS data.
- Romanized transliteration: generated locally by Open Granth via
  `scripts/transliteration.py`.
- English translation: imported from the `DSSK` translation asset in the
  Shabad OS database. The local Shabad OS asset metadata attributes DSSK to
  Dr. Sant S. Khalsa, publication date 2013-03.

The English layer is an imported study aid. It is not Open Granth's own
interpretation. Within Open Granth, the
Gurmukhi is the source layer; the Roman and English layers are reading aids.

## Generated Site

The static site in `site/` is generated from `corpus/` by:

```bash
python3 scripts/build_site.py --source-dir corpus
```

The generated `site/data/verses.json` is a search and verification payload
derived from the same corpus.

## Corrections and Takedown

Corrections, attribution concerns, and takedown requests are handled through
`TAKEDOWN.md`.
