#!/usr/bin/env python3
"""Import SGGS angs from a local Shabad OS SQLite database into Open Granth markdown.

This script intentionally writes to a separate output directory so it does not
overwrite an existing corpus during import testing.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

from transliteration import normalize_gurmukhi_text, transliterate_gurmukhi


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE_DIR / "node_modules" / "@shabados" / "database" / "dist" / "master.sqlite"
DEFAULT_OUT = BASE_DIR / "corpus"


QUERY = """
with page_lines as (
    select distinct
        l.id as line_id,
        cast(json_extract(al.additional, '$.page') as integer) as page
    from lines l
    join line_groups lg on lg.id = l.line_group_id
    join sections s on s.id = lg.section_id
    join asset_lines al on al.line_id = l.id
    where s.source_id = 'SGGS'
      and al.type = 'primary'
      and cast(json_extract(al.additional, '$.page') as integer) between ? and ?
)
select
    pl.page as page,
    l.id as line_id,
    l.line_group_order as line_group_order,
    lg.section_order as section_order,
    s.source_order as source_order,
    a.name as author_name,
    s.name as section_name,
    al.type as asset_type,
    al.asset_id as asset_id,
    al.data as data,
    al.additional as additional
from lines l
join line_groups lg on lg.id = l.line_group_id
left join authors a on a.id = lg.author_id
join sections s on s.id = lg.section_id
join asset_lines al on al.line_id = l.id
join page_lines pl on pl.line_id = l.id
where s.source_id = 'SGGS'
order by
    pl.page,
    s.source_order,
    lg.section_order,
    l.line_group_order,
    case al.type when 'primary' then 0 when 'translation' then 1 when 'note' then 2 else 9 end,
    al.asset_id
"""


def parse_name(value: str | None, fallback: str = "Unknown") -> str:
    if not value:
        return fallback
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return (
                parsed.get("en")
                or parsed.get("Latn")
                or parsed.get("Guru")
                or next(iter(parsed.values()), fallback)
            )
    except json.JSONDecodeError:
        pass
    return value


def _physical_line_sort_key(item: tuple[str, dict]) -> tuple[int, int, int, int]:
    """Order verses as they appear on the physical ang.

    Section and line-group order are only tie-breakers. They cannot be the
    primary keys because more than one section may share an ang.
    """
    entry = item[1]
    return (
        entry["line_no"] if entry["line_no"] is not None else 10**9,
        entry["source_order"],
        entry["section_order"],
        entry["line_group_order"],
    )


def _build_page(
    page: int,
    rows: list[sqlite3.Row],
    translation_asset: str,
    include_english: bool,
) -> tuple[dict, list[dict]]:
    author_counts: Counter[str] = Counter()
    section_counts: Counter[str] = Counter()
    by_line: dict[str, dict] = {}

    for row in rows:
        line_id = row["line_id"]
        entry = by_line.setdefault(
            line_id,
            {
                "line_group_order": row["line_group_order"],
                "section_order": row["section_order"],
                "source_order": row["source_order"],
                "author": parse_name(row["author_name"]),
                "section": parse_name(row["section_name"]),
                "line_no": None,
                "gurmukhi": "",
                "translation": "",
            },
        )

        author_counts[entry["author"]] += 1
        section_counts[entry["section"]] += 1

        additional = {}
        if row["additional"]:
            additional = json.loads(row["additional"])

        if row["asset_type"] == "primary":
            entry["gurmukhi"] = normalize_gurmukhi_text(row["data"].strip())
            entry["line_no"] = additional.get("line")
        elif include_english and row["asset_type"] == "translation" and row["asset_id"] == translation_asset:
            if additional.get("language") == "en":
                entry["translation"] = row["data"].strip()

    verses = []
    for line_id, entry in sorted(
        by_line.items(),
        key=_physical_line_sort_key,
    ):
        if not entry["gurmukhi"]:
            continue
        verses.append(
            {
                "line_no": entry["line_no"] or len(verses) + 1,
                "gurmukhi": entry["gurmukhi"],
                "transliteration": transliterate_gurmukhi(entry["gurmukhi"]),
                "english": entry["translation"],
            }
        )

    meta = {
        "ang": page,
        "author": author_counts.most_common(1)[0][0],
        "raag": section_counts.most_common(1)[0][0],
        "lines": len(verses),
        "source": "Shabad OS Database",
        "transliteration": "generated locally via scripts/transliteration.py",
    }
    if include_english:
        meta["translation_source"] = translation_asset
    return meta, verses


def load_pages(
    conn: sqlite3.Connection,
    start: int,
    end: int,
    translation_asset: str,
    include_english: bool,
):
    """Yield (page, meta, verses) for each ang in [start, end].

    Executes a single bulk query against the SQLite database, then groups
    rows by page in Python. Avoids the 1,430x json_extract scan penalty
    that per-page queries incur.
    """
    rows = conn.execute(QUERY, (start, end)).fetchall()

    grouped: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(row["page"], []).append(row)

    for page in range(start, end + 1):
        page_rows = grouped.get(page)
        if not page_rows:
            raise ValueError(f"No SGGS rows found for ang {page}")
        meta, verses = _build_page(page, page_rows, translation_asset, include_english)
        yield page, meta, verses


def render_markdown(meta: dict, verses: list[dict]) -> str:
    out = [
        "---",
        f"ang: {meta['ang']}",
        f"author: {meta['author']}",
        f"raag: {meta['raag']}",
        f"lines: {meta['lines']}",
        f"source: {meta['source']}",
        f"transliteration: {meta['transliteration']}",
        "---",
        "",
    ]
    if "translation_source" in meta:
        out.insert(6, f"translation_source: {meta['translation_source']}")

    for verse in verses:
        out.append(f"<!-- LINE:{verse['line_no']} -->")
        out.append(f"**{verse['gurmukhi']}**")
        out.append("")
        if verse["transliteration"]:
            out.append(f"*{verse['transliteration']}*")
            out.append("")
        if verse["english"]:
            out.append(verse["english"])
            out.append("")
        out.append("---")
        out.append("")

    out.append("*ੴ ਸਤਿ ਨਾਮੁ*")
    out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import SGGS angs from Shabad OS into Open Granth markdown.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to Shabad OS master.sqlite")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT), help="Output directory for generated ang markdown")
    parser.add_argument("--translation-asset", default="DSSK", help="Translation asset ID to use (default: DSSK)")
    parser.add_argument("--no-english", action="store_true", help="Do not include English translation rows")
    parser.add_argument("--start", type=int, default=1, help="First ang to import")
    parser.add_argument("--end", type=int, default=None, help="Last ang to import (inclusive)")
    parser.add_argument("--dry-run", action="store_true", help="Print the first generated ang instead of writing files")
    args = parser.parse_args()

    db_path = Path(args.db)
    out_dir = Path(args.out_dir)
    end = args.end or args.start

    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    if args.start < 1 or end > 1430 or args.start > end:
        raise SystemExit("Ang range must be between 1 and 1430 and start <= end")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for ang, meta, verses in load_pages(
        conn, args.start, end, args.translation_asset, include_english=not args.no_english
    ):
        markdown = render_markdown(meta, verses)
        if args.dry_run:
            print(markdown)
            break
        out_path = out_dir / f"ang-{ang:04d}.md"
        out_path.write_text(markdown, encoding="utf-8")
        written += 1
        if written == 1 or written % 200 == 0 or ang == end:
            print(f"Wrote {out_path} ({written}/{end - args.start + 1})")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
