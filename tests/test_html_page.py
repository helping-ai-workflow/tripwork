"""Tests for scripts/render/html_page.py — self-contained one-page HTML renderer.

Covers:
- _html_escape: correct escaping, ampersand-first (no double-escape)
- render_html_page: DOCTYPE, viewport meta, no external src, offline-safe
- POI names with special chars are escaped; Maps link generated
- Day card count, checklist items
"""
import re
import pytest

from scripts.render.html_page import _html_escape, render_html_page


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

POI_P1 = {
    "id": "p1",
    "name_display": "だるま <本店>",
    "name_zh": "達摩",
    "geocode": {"lat": 43.06, "lng": 141.35},
}

ITIN = {
    "title": "北海道 & 旅行",
    "checklist": ["護照", "JR Pass", "現金 <備用>"],
    "days": [
        {
            "date": "2026-03-01",
            "label": "Day 1 — 札幌",
            "rows": [
                {
                    "time": "12:00",
                    "slot": "lunch",
                    "poi_id": "p1",
                    "text": "必吃 & 推薦",
                },
            ],
        },
        {
            "date": "2026-03-02",
            "label": "Day 2 — 小樽",
            "rows": [],
        },
    ],
}

POI_MAP = {"p1": POI_P1}


# ---------------------------------------------------------------------------
# _html_escape
# ---------------------------------------------------------------------------

class TestHtmlEscape:
    def test_basic_lt_gt_amp(self):
        assert _html_escape("a <b> & c") == "a &lt;b&gt; &amp; c"

    def test_quotes(self):
        result = _html_escape('"hello" & \'world\'')
        assert "&quot;" in result
        assert "&#39;" in result

    def test_no_double_escape_amp(self):
        # "a & b" must become "a &amp; b" exactly, NOT "a &amp;amp; b"
        result = _html_escape("a & b")
        assert result == "a &amp; b"

    def test_amp_first_no_double_escape_for_lt(self):
        # "<" must become "&lt;" not "&amp;lt;"
        result = _html_escape("<x>")
        assert result == "&lt;x&gt;"

    def test_plain_text_unchanged(self):
        assert _html_escape("hello world 123") == "hello world 123"

    def test_non_string_coerced(self):
        assert _html_escape(42) == "42"


# ---------------------------------------------------------------------------
# render_html_page — structural
# ---------------------------------------------------------------------------

class TestRenderHtmlPageStructure:
    def setup_method(self):
        self.html = render_html_page(ITIN, POI_MAP)

    def test_starts_with_doctype(self):
        assert self.html.lower().lstrip().startswith("<!doctype html")

    def test_has_viewport_meta(self):
        assert '<meta name="viewport"' in self.html

    def test_no_external_src(self):
        # must not contain src="http or src='http (no CDN or external assets)
        assert 'src="http' not in self.html
        assert "src='http" not in self.html

    def test_no_external_link_href_css(self):
        # no <link rel="stylesheet" href="http..."> (external CSS)
        assert not re.search(r'<link[^>]+href=["\']http', self.html)

    def test_inline_style_present(self):
        assert "<style>" in self.html


# ---------------------------------------------------------------------------
# render_html_page — day cards
# ---------------------------------------------------------------------------

class TestRenderHtmlPageDayCards:
    def setup_method(self):
        self.html = render_html_page(ITIN, POI_MAP)

    def test_day_card_count(self):
        # Two days → two day-card divs
        assert self.html.count('class="day-card"') == 2

    def test_day_label_appears(self):
        assert "Day 1" in self.html
        assert "Day 2" in self.html


# ---------------------------------------------------------------------------
# render_html_page — checklist
# ---------------------------------------------------------------------------

class TestRenderHtmlPageChecklist:
    def setup_method(self):
        self.html = render_html_page(ITIN, POI_MAP)

    def test_checklist_items_present(self):
        assert "護照" in self.html
        assert "JR Pass" in self.html

    def test_checklist_item_with_special_char_escaped(self):
        # "現金 <備用>" must be escaped
        assert "&lt;備用&gt;" in self.html
        assert "<備用>" not in self.html


# ---------------------------------------------------------------------------
# render_html_page — POI with special chars
# ---------------------------------------------------------------------------

class TestRenderHtmlPagePoiEscape:
    def setup_method(self):
        self.html = render_html_page(ITIN, POI_MAP)

    def test_maps_link_present(self):
        assert '<a href="https://www.google.com/maps/search/' in self.html

    def test_poi_display_name_escaped(self):
        # "<本店>" in name_display must NOT appear as raw HTML tag
        assert "<本店>" not in self.html
        assert "&lt;本店&gt;" in self.html

    def test_poi_zh_gloss_present(self):
        assert "達摩" in self.html

    def test_title_amp_escaped(self):
        # title "北海道 & 旅行" → "北海道 &amp; 旅行"
        assert "北海道 &amp; 旅行" in self.html
        # raw & from data must not survive in title
        assert "<title>北海道 & 旅行</title>" not in self.html

    def test_row_text_amp_escaped(self):
        # row text "必吃 & 推薦" → "&amp;" in output
        assert "必吃 &amp; 推薦" in self.html


# ---------------------------------------------------------------------------
# render_html_page — empty checklist
# ---------------------------------------------------------------------------

class TestRenderHtmlPageNoChecklist:
    def test_no_checklist_section_when_empty(self):
        itin_no_cl = {**ITIN, "checklist": []}
        html = render_html_page(itin_no_cl, POI_MAP)
        assert "行前清單" not in html
