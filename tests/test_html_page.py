"""Tests for scripts/render/html_page.py — the HTML deliverable's entrypoint.

Since v1.0 (P4) `render_html_page` renders the reader (scripts/render/reader/,
spec §6). This file keeps every property the pre-v1.0 tests protected that the
reader still has — escaping, offline-safety, day pages, checklist, maps links,
photos with attribution, unique ids, the export-gate round trip — asserted
against the reader's structure. The component-level contract lives in
tests/test_reader_{home,day,page,assets}.py.

Retired with the pre-v1.0 layout (spec §6.1 / §6.3 replace them), not skipped:
hero banner + meta line, overview table, emoji legend and slot emoji, three-column
grid and its thumbnail column, dashed look-ahead grouping, boxed lodging line,
in-cell altbox for inline ▸ rows (alternatives are per-stop now), trip-level
contingency section (§6.1 不顯示整趟備案), move-row A→B directions chip (stops
carry the 導航 button), https photo sources and the checkbox lightbox (the page
is offline: photos are embedded and shown in the expanded stop).
"""
import re

from bs4 import BeautifulSoup

from scripts.export_gate import run_html_gate
from scripts.render.html_page import _html_escape, render_html_page

POI_P1 = {
    "id": "p1",
    "name_local": "だるま <本店>",
    "name_display": "だるま <本店>",
    "name_zh": "達摩 & 本店",
    "geocode": {"lat": 43.06, "lng": 141.35},
}

ITIN = {
    "title": "北海道 & 旅行",
    "checklist": ["護照", "JR Pass", "現金 <備用>"],
    "days": [
        {"date": "2026-03-01", "label": "Day 1 — 札幌",
         "rows": [{"slot": "move", "mode": "walk", "mins": 5},
                  {"time": "12:00", "slot": "lunch", "poi_id": "p1", "text": "必吃 & 推薦"},
                  {"slot": "move", "mode": "walk", "mins": 5}]},
        {"date": "2026-03-02", "label": "Day 2 — 小樽", "rows": []},
    ],
}
POI_MAP = {"p1": POI_P1}

POI_PHOTO = {
    "id": "pp", "name_display": "登別温泉", "name_zh": "登別溫泉",
    "geocode": {"lat": 42.49, "lng": 141.15},
    "photo": {"data": "data:image/jpeg;base64,/9j/FULLDATA", "width": 640, "height": 480},
    "photo_attribution": {"author": "Commons User <evil>", "license": "CC-BY-SA-4.0",
                          "source_url": "https://commons.wikimedia.org/wiki/File:X.jpg"},
    "photo_source": "wikimedia",
}
PHOTO_ITIN = {"title": "溫泉行", "days": [{"date": "2026-11-01", "label": "D1", "rows": [
    {"slot": "move", "mode": "taxi", "mins": 10, "km": 3},
    {"time": "10:00", "slot": "visit", "poi_id": "pp", "text": "泡湯"},
    {"slot": "move", "mode": "taxi", "mins": 10, "km": 3}]}]}
PHOTO_MAP = {"pp": POI_PHOTO}


def _soup(html):
    return BeautifulSoup(html, "html.parser")


class TestHtmlEscape:
    def test_basic_lt_gt_amp(self):
        assert _html_escape("a <b> & c") == "a &lt;b&gt; &amp; c"

    def test_quotes(self):
        result = _html_escape('"hello" & \'world\'')
        assert "&quot;" in result and "&#x27;" in result

    def test_no_double_escape_amp(self):
        assert _html_escape("a & b") == "a &amp; b"

    def test_amp_first_no_double_escape_for_lt(self):
        assert _html_escape("<x>") == "&lt;x&gt;"

    def test_plain_text_unchanged(self):
        assert _html_escape("hello world 123") == "hello world 123"

    def test_non_string_coerced(self):
        assert _html_escape(42) == "42"


class TestStructure:
    def setup_method(self):
        self.html = render_html_page(ITIN, POI_MAP)

    def test_starts_with_doctype(self):
        assert self.html.lower().startswith("<!doctype html>")

    def test_has_viewport_meta(self):
        assert _soup(self.html).select_one('meta[name="viewport"]')

    def test_no_external_src(self):
        assert not re.search(r'\ssrc="https?://', self.html)

    def test_no_external_stylesheet(self):
        assert not _soup(self.html).select('link[rel="stylesheet"]')

    def test_inline_style_present(self):
        assert _soup(self.html).select_one("head style")

    def test_one_day_page_per_day(self):
        assert len(_soup(self.html).select("section.page.day")) == 2

    def test_label_is_the_fallback_when_there_is_no_theme(self):
        heads = [h.get_text() for h in _soup(self.html).select(".pcal .dh .dht")]
        assert heads == ["Day 1 — 札幌", "Day 2 — 小樽"]

    def test_missing_title_defaults(self):
        html = render_html_page({"days": ITIN["days"]}, POI_MAP)
        assert _soup(html).select_one("title").get_text() == "行程"


class TestChecklist:
    def test_legacy_string_items_render_escaped(self):
        html = render_html_page(ITIN, POI_MAP)
        tasks = [t.get_text() for t in _soup(html).select('[data-pg="checklist"] .tk')]
        assert tasks == ["護照", "JR Pass", "現金 <備用>"]
        assert "現金 &lt;備用&gt;" in html

    def test_no_checklist_says_so(self):
        itin = dict(ITIN, checklist=[])
        html = render_html_page(itin, POI_MAP)
        assert _soup(html).select_one('[data-pg="checklist"] .empty')


class TestPoiAndText:
    def setup_method(self):
        self.html = render_html_page(ITIN, POI_MAP)

    def test_maps_link_present(self):
        assert _soup(self.html).select_one('a.navb[href^="https://www.google.com/maps/"]')

    def test_poi_names_are_escaped(self):
        assert "だるま &lt;本店&gt;" in self.html and "達摩 &amp; 本店" in self.html
        assert "<本店>" not in self.html

    def test_title_and_row_text_escaped(self):
        assert "北海道 &amp; 旅行" in self.html and "必吃 &amp; 推薦" in self.html

    def test_unknown_slot_renders(self):
        assert _soup(self.html).select_one('.stop[data-poi="p1"]')

    def test_row_without_time_renders(self):
        itin = {"title": "T", "days": [{"date": "2026-11-01", "label": "D1", "rows": [
            {"slot": "move", "mode": "walk", "mins": 3},
            {"slot": "visit", "poi_id": "p1", "text": "x"},
            {"slot": "move", "mode": "walk", "mins": 3}]}]}
        head = _soup(render_html_page(itin, POI_MAP)).select_one(".stop .hd-open .t b")
        assert head.get_text() == ""

    def test_unresolved_lodging_never_leaks_its_id(self):
        itin = {"title": "T", "days": [dict(ITIN["days"][0], lodging="ghost-hotel-id")]}
        assert "ghost-hotel-id" not in render_html_page(itin, POI_MAP)


class TestPhoto:
    def setup_method(self):
        self.html = render_html_page(PHOTO_ITIN, PHOTO_MAP)

    def test_embedded_photo_shown_in_the_stop(self):
        # since v1.0 P7 a CSS background, one rule per distinct image
        ph = _soup(self.html).select_one('.stop[data-poi="pp"] figure.bp .bpi')
        cls = [c for c in ph["class"] if c.startswith("mi-")][0]
        assert f'.{cls}{{background-image:url("data:image/jpeg;base64,/9j/FULLDATA")}}' in self.html
        assert ph["aria-label"] == "登別溫泉"

    def test_attribution_visible_and_escaped(self):
        cap = _soup(self.html).select_one("figure.bp figcaption").get_text()
        assert "Commons User <evil>" in cap and "CC-BY-SA-4.0" in cap
        assert "Commons User &lt;evil&gt;" in self.html

    def test_https_only_photo_is_not_rendered(self):
        remote = dict(POI_PHOTO, photo={"url": "https://upload.wikimedia.org/x.jpg"})
        html = render_html_page(PHOTO_ITIN, {"pp": remote})
        assert "<img" not in html and 'class="bpi' not in html and "upload.wikimedia.org" not in html

    def test_no_photo_no_img(self):
        html = render_html_page(PHOTO_ITIN, {"pp": {k: v for k, v in POI_PHOTO.items()
                                                    if not k.startswith("photo")}})
        assert "<img" not in html and 'class="bpi' not in html

    def test_photo_page_passes_html_gate(self):
        r = run_html_gate(self.html, list(PHOTO_MAP.values()), min_days=1, media_count=1)
        assert r["status"] == "pass", r["failures"]


class TestIdsAndGate:
    def test_ids_are_unique_when_a_poi_is_a_stop_and_the_lodging(self):
        itin = {"title": "T", "days": [{"date": "2026-11-01", "label": "D1", "lodging": "pp",
                                        "rows": PHOTO_ITIN["days"][0]["rows"]}]}
        ids = re.findall(r'\sid="([^"]+)"', render_html_page(itin, PHOTO_MAP))
        assert len(ids) == len(set(ids))

    def test_rich_page_passes_html_gate(self):
        r = run_html_gate(render_html_page(ITIN, POI_MAP), list(POI_MAP.values()), min_days=2)
        assert r["status"] == "pass", r["failures"]
