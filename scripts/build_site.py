#!/usr/bin/env python3
"""
Build Open Granth static site from a markdown corpus directory.

Output shape:

    site/
      index.html
      about/index.html
      search/index.html
      ang/<N>/index.html
      data/verses.json

Usage:
    python scripts/build_site.py
    python scripts/build_site.py --source-dir corpus
    python scripts/build_site.py --site-dir /tmp/open-granth-site --serve
"""

from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import shutil
import socketserver
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import sys

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

from open_granth.parser import parse_corpus_file


DEFAULT_SOURCE_DIR = REPO / "corpus"
DEFAULT_SITE_DIR = REPO / "site"
DEFAULT_TEMPLATE_DIR = REPO / "templates"
DEFAULT_ASSETS_DIR = REPO / "site"


# Paths inside site/ that this builder owns. On a clean build these are
# wiped and regenerated. Anything else in site/ (hand-authored pages like
# verify/) is preserved across rebuilds.
#
# Add to this list when the builder starts producing a new output path.
BUILDER_OWNED = [
    "index.html",
    "about",
    "search",
    "ang",
    "data/verses.json",
    "style.css",
    "fonts",
]


def _clean_builder_paths(site_dir: Path) -> None:
    for rel in BUILDER_OWNED:
        p = site_dir / rel
        if p.is_dir():
            shutil.rmtree(p)
        elif p.is_file():
            p.unlink()


SECTION_RANGES: list[tuple[int, int, str]] = [
    (1, 8, "Japji Sahib"),
    (8, 13, "So Dar / So Purakh / Sohila"),
    (14, 93, "Raag Siree"),
    (94, 150, "Raag Maajh"),
    (151, 346, "Raag Gauree"),
    (347, 488, "Raag Aasaa"),
    (489, 526, "Raag Goojaree"),
    (527, 536, "Raag Devgandhaaree"),
    (537, 556, "Raag Bihaagra"),
    (557, 594, "Raag Vadahans"),
    (595, 659, "Raag Sorath"),
    (660, 695, "Raag Dhanaasaree"),
    (696, 710, "Raag Jaitsree"),
    (711, 718, "Raag Todee"),
    (719, 720, "Raag Bairaaree"),
    (721, 727, "Raag Tilang"),
    (728, 794, "Raag Soohee"),
    (795, 858, "Raag Bilaaval"),
    (859, 875, "Raag Gond"),
    (876, 974, "Raag Raamkalee"),
    (975, 983, "Raag Nat Naaraain"),
    (984, 988, "Raag Maale Gaaura"),
    (989, 1106, "Raag Maaru"),
    (1107, 1117, "Raag Tukhaari"),
    (1118, 1124, "Raag Kaydaaraa"),
    (1125, 1167, "Raag Bhairao"),
    (1168, 1196, "Raag Basant"),
    (1197, 1253, "Raag Saarang"),
    (1254, 1293, "Raag Malaar"),
    (1294, 1318, "Raag Kaanra"),
    (1319, 1326, "Raag Kalyaan"),
    (1327, 1351, "Raag Prabhaatee"),
    (1352, 1353, "Raag Jaijaavantee"),
    (1353, 1360, "Salok Sehskritee"),
    (1360, 1361, "Gaathaa"),
    (1361, 1363, "Phunhay"),
    (1363, 1364, "Chaubolas"),
    (1364, 1377, "Salok Bhagat Kabeer Ji"),
    (1377, 1384, "Salok Sheikh Fareed Ji"),
    (1385, 1409, "Svaiyay"),
    (1410, 1426, "Salok Vaaran Thay Vadheek"),
    (1426, 1429, "Salok Mahala 9"),
    (1429, 1429, "Mundaavanee"),
    (1429, 1430, "Raag Maalaa"),
]


def _find_asset(base: Path, rel: str) -> Path | None:
    """Resolve an asset path relative to the assets root."""
    path = base / rel
    return path if path.exists() else None


def _snapshot_assets(assets_dir: Path) -> tuple[bytes, list[tuple[str, bytes]]]:
    """Load style.css and fonts files into memory before cleaning output."""
    style_path = _find_asset(assets_dir, "style.css")
    fonts_dir = _find_asset(assets_dir, "fonts")
    if not style_path:
        raise FileNotFoundError("Could not find style.css in assets roots")
    if not fonts_dir or not fonts_dir.is_dir():
        raise FileNotFoundError("Could not find fonts/ directory in assets roots")

    style_bytes = style_path.read_bytes()
    font_files: list[tuple[str, bytes]] = []
    for p in sorted(fonts_dir.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(fonts_dir))
            font_files.append((rel, p.read_bytes()))
    return style_bytes, font_files


def _load_angs(source_dir: Path) -> list[tuple[int, Path]]:
    out: list[tuple[int, Path]] = []
    for path in sorted(source_dir.glob("ang-*.md")):
        try:
            ang = int(path.stem.split("-")[1])
        except (IndexError, ValueError):
            continue
        out.append((ang, path))
    return sorted(out, key=lambda x: x[0])


def _to_template_lines(verses: list[dict]) -> list[dict]:
    lines: list[dict] = []
    for v in verses:
        lines.append(
            {
                "gurmukhi": v.get("gurmukhi", ""),
                "transliteration": v.get("transliteration", ""),
                "english": v.get("english", ""),
            }
        )
    return lines


def _display_lines(lines: list[dict]) -> list[dict]:
    """Copy of lines for HTML rendering only: a danda (॥ in Gurmukhi, || in
    the Roman line) is joined to the preceding word with a non-breaking
    space so it never wraps alone on narrow viewports. verses.json and the
    corpus keep the plain space."""
    return [
        dict(
            line,
            gurmukhi=line["gurmukhi"].replace(" ॥", "\u00a0॥"),
            transliteration=line["transliteration"].replace(" ||", "\u00a0||"),
        )
        for line in lines
    ]


def _section_label_for_ang(ang: int) -> str | None:
    matches = [label for start, end, label in SECTION_RANGES if start <= ang <= end]
    # Shared boundary angs contain more than one section. Their imported
    # frontmatter is more precise than choosing one supplementary label here.
    return matches[0] if len(matches) == 1 else None


def _source_profile(source_dir: Path) -> dict[str, str]:
    """Return the source labels shared by the page templates."""
    return {
        "source_mode": "default",
        "source_label": "Shabad OS data",
        "footer_attribution": "Source text derived from Shabad OS data",
    }


def build_site(
    source_dir: Path,
    site_dir: Path,
    template_dir: Path,
    assets_dir: Path,
    clean: bool = True,
    cache_bust: bool = False,
) -> None:
    style_bytes, font_files = _snapshot_assets(assets_dir)

    ang_files = _load_angs(source_dir)
    if not ang_files:
        raise RuntimeError(f"No ang files found in: {source_dir}")

    if clean and site_dir.exists():
        _clean_builder_paths(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(loader=FileSystemLoader(str(template_dir)))
    ang_template = env.get_template("ang.html")
    index_template = env.get_template("index.html")
    about_template = env.get_template("about.html")
    search_template = env.get_template("search.html")
    notfound_template = env.get_template("404.html")
    source_profile = _source_profile(source_dir)
    # Optional cache busting (--cache-bust): stylesheet URL carries a content
    # hash so browsers never serve stale styles. Off by default so the main
    # distribution ships clean URLs and CSS tweaks don't churn all 1,430 pages.
    css_version = hashlib.md5(style_bytes).hexdigest()[:8] if cache_bust else ""
    source_profile["css_version"] = css_version

    # Core pages
    (site_dir / "index.html").write_text(index_template.render(**source_profile), encoding="utf-8")
    (site_dir / "about").mkdir(parents=True, exist_ok=True)
    (site_dir / "about" / "index.html").write_text(about_template.render(**source_profile), encoding="utf-8")
    (site_dir / "search").mkdir(parents=True, exist_ok=True)
    # Search normalization table: single machine-readable source shared with the
    # MCP server (metadata/search-normalization.json) so the two surfaces cannot drift.
    normalization_path = Path(__file__).resolve().parent.parent / "metadata" / "search-normalization.json"
    normalization_json = json.dumps(json.loads(normalization_path.read_text(encoding="utf-8")), ensure_ascii=True, separators=(",", ":"))
    (site_dir / "search" / "index.html").write_text(
        search_template.render(**source_profile, normalization_json=normalization_json), encoding="utf-8")
    # Top-level 404.html: without it Cloudflare Pages treats the site as an
    # SPA and serves the homepage with HTTP 200 for unknown URLs.
    (site_dir / "404.html").write_text(notfound_template.render(**source_profile), encoding="utf-8")

    # Assets
    (site_dir / "style.css").write_bytes(style_bytes)
    fonts_out = site_dir / "fonts"
    fonts_out.mkdir(parents=True, exist_ok=True)
    for rel, data in font_files:
        p = fonts_out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    all_search_verses: list[dict] = []
    ang_numbers = [ang for ang, _ in ang_files]
    ang_index = {ang: i for i, ang in enumerate(ang_numbers)}

    built = 0
    for ang, path in ang_files:
        front, verses = parse_corpus_file(path)
        if not verses:
            continue

        lines = _to_template_lines(verses)
        i = ang_index[ang]
        prev_ang = ang_numbers[i - 1] if i > 0 else None
        next_ang = ang_numbers[i + 1] if i < len(ang_numbers) - 1 else None

        context = {
            "css_version": css_version,
            "ang": front.get("ang", ang),
            "author": front.get("author", "Unknown"),
            "raag": front.get("raag", "Unknown"),
            "section_label": _section_label_for_ang(front.get("ang", ang)),
            "source_label": front.get("source", ""),
            "lines": _display_lines(lines),
            "prev_ang": prev_ang,
            "next_ang": next_ang,
        }

        ang_dir = site_dir / "ang" / str(ang)
        ang_dir.mkdir(parents=True, exist_ok=True)
        (ang_dir / "index.html").write_text(ang_template.render(**context), encoding="utf-8")

        for idx, line in enumerate(lines, start=1):
            gurmukhi = (line.get("gurmukhi") or "").strip()
            translit = (line.get("transliteration") or "").strip()
            if gurmukhi or translit:
                all_search_verses.append(
                    {
                        "ang": context["ang"],
                        "verse_index": idx,
                        "author": context["author"],
                        "gurmukhi": gurmukhi,
                        "transliteration": translit,
                        "english": (line.get("english") or "").strip(),
                    }
                )

        built += 1
        if built % 200 == 0:
            print(f"  Built {built} ang pages (current: {ang})")

    data_dir = site_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "verses.json").write_text(
        json.dumps(all_search_verses, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    size_mb = (data_dir / "verses.json").stat().st_size / 1024 / 1024
    print()
    print(f"Built {built} ang pages from {source_dir}")
    print(f"Search index: {len(all_search_verses):,} verses ({size_mb:.1f} MB)")
    print(f"Output: {site_dir}")


def serve(site_dir: Path, port: int) -> None:
    handler = http.server.SimpleHTTPRequestHandler
    cwd = Path.cwd()
    try:
        os_dir = str(site_dir)
        import os

        os.chdir(os_dir)
        with socketserver.TCPServer(("", port), handler) as httpd:
            print(f"Serving {site_dir} at http://localhost:{port}")
            httpd.serve_forever()
    finally:
        import os

        os.chdir(str(cwd))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR))
    parser.add_argument("--site-dir", default=str(DEFAULT_SITE_DIR))
    parser.add_argument("--template-dir", default=str(DEFAULT_TEMPLATE_DIR))
    parser.add_argument("--assets-dir", default=str(DEFAULT_ASSETS_DIR))
    parser.add_argument("--no-clean", action="store_true", help="Do not remove site-dir before build")
    parser.add_argument("--cache-bust", action="store_true", help="Append a content-hash ?v= to the stylesheet URL (off for the main distribution)")
    parser.add_argument("--serve", action="store_true", help="Serve the built site over HTTP")
    parser.add_argument("--port", type=int, default=8080, help="Port for --serve (default: 8080)")
    args = parser.parse_args()

    source_dir = Path(args.source_dir).resolve()
    site_dir = Path(args.site_dir).resolve()
    template_dir = Path(args.template_dir).resolve()
    assets_dir = Path(args.assets_dir).resolve()

    print("Open Granth: Build Site")
    print(f"  source:   {source_dir}")
    print(f"  templates:{template_dir}")
    print(f"  assets:   {assets_dir}")
    print(f"  output:   {site_dir}")

    build_site(
        source_dir=source_dir,
        site_dir=site_dir,
        template_dir=template_dir,
        assets_dir=assets_dir,
        clean=not args.no_clean,
        cache_bust=args.cache_bust,
    )

    if args.serve:
        serve(site_dir, args.port)


if __name__ == "__main__":
    main()
