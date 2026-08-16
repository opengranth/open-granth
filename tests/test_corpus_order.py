import re
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
LINE_MARKER = re.compile(r"<!-- LINE:(\d+) -->")
DEEP_LINK = re.compile(r'href="ang/(\d+)/#(v\d+)"')

sys.path.insert(0, str(REPO / "scripts"))
from import_shabados import _physical_line_sort_key
from build_site import _section_label_for_ang

sys.path.insert(0, str(REPO))
from open_granth.parser import parse_corpus_file


def test_released_angs_follow_physical_page_order():
    """Source line numbers must never move backwards within an ang."""
    files = sorted((REPO / "corpus").glob("ang-*.md"))
    assert len(files) == 1430

    violations = []
    for path in files:
        line_numbers = [int(value) for value in LINE_MARKER.findall(path.read_text(encoding="utf-8"))]
        if line_numbers != sorted(line_numbers):
            violations.append(path.name)

    assert violations == []


def test_importer_orders_physical_lines_before_sections():
    entries = {
        "later_section": {
            "line_no": 2,
            "source_order": 20,
            "section_order": 1,
            "line_group_order": 1,
        },
        "earlier_line": {
            "line_no": 1,
            "source_order": 30,
            "section_order": 99,
            "line_group_order": 99,
        },
    }

    ordered = [line_id for line_id, _ in sorted(entries.items(), key=_physical_line_sort_key)]
    assert ordered == ["earlier_line", "later_section"]


def test_homepage_deep_links_resolve():
    homepage = (REPO / "site" / "index.html").read_text(encoding="utf-8")
    links = DEEP_LINK.findall(homepage)
    assert links

    for ang, anchor in links:
        target = (REPO / "site" / "ang" / ang / "index.html").read_text(encoding="utf-8")
        assert f'id="{anchor}"' in target, f"Missing target: ang/{ang}/#{anchor}"


def test_section_start_anchors_match_expected_gurmukhi():
    expected = {
        (8, 39): "ਸੋ ਦਰੁ ਰਾਗੁ ਆਸਾ ਮਹਲਾ ੧ ॥",
        (10, 26): "ਰਾਗੁ ਆਸਾ ਮਹਲਾ ੪ ਸੋ ਪੁਰਖੁ ॥",
        (12, 23): "ਸੋਹਿਲਾ ਰਾਗੁ ਗਉੜੀ ਦੀਪਕੀ ਮਹਲਾ ੧ ॥",
        (537, 2): "ਰਾਗੁ ਬਿਹਾਗੜਾ ਚਉਪਦੇ ਮਹਲਾ ੫ ਘਰੁ ੨ ॥",
        (557, 2): "ਰਾਗੁ ਵਡਹੰਸੁ ਮਹਲਾ ੧ ਘਰੁ ੧ ॥",
        (595, 2): "ਸੋਰਠਿ ਮਹਲਾ ੧ ਘਰੁ ੧ ਚਉਪਦੇ ॥",
        (660, 1): "ਧਨਾਸਰੀ ਮਹਲਾ ੧ ਘਰੁ ੧ ਚਉਪਦੇ ॥",
        (1353, 6): "ਸਲੋਕ ਸਹਸਕ੍ਰਿਤੀ ਮਹਲਾ ੧ ॥",
        (1360, 7): "ਮਹਲਾ ੫ ਗਾਥਾ ॥",
        (1361, 25): "ਫੁਨਹੇ ਮਹਲਾ ੫ ॥",
        (1363, 35): "ਚਉਬੋਲੇ ਮਹਲਾ ੫ ॥",
        (1364, 19): "ਸਲੋਕ ਭਗਤ ਕਬੀਰ ਜੀਉ ਕੇ ॥",
        (1377, 27): "ਸਲੋਕ ਸੇਖ ਫਰੀਦ ਕੇ ॥",
        (1426, 17): "ਸਲੋਕ ਮਹਲਾ ੯ ॥",
        (1429, 22): "ਮੁੰਦਾਵਣੀ ਮਹਲਾ ੫ ॥",
        (1429, 34): "ਰਾਗ ਮਾਲਾ ॥",
    }

    for (ang, verse_index), gurmukhi in expected.items():
        _, verses = parse_corpus_file(REPO / "corpus" / f"ang-{ang:04d}.md")
        assert verses[verse_index - 1]["gurmukhi"] == gurmukhi


def test_shared_boundary_angs_do_not_get_a_misleading_single_section_label():
    for ang in (8, 1353, 1360, 1361, 1363, 1364, 1377, 1426, 1429):
        assert _section_label_for_ang(ang) is None

    assert _section_label_for_ang(537) == "Raag Bihaagra"
    assert _section_label_for_ang(1430) == "Raag Maalaa"
