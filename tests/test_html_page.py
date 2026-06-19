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


# ---------------------------------------------------------------------------
# Card-style upgrade (v0.17.0) — hero, overview, legend, lodge, alt, slot color
# ---------------------------------------------------------------------------
# Rich fixture: lodging that resolves, an alt (▸) row, every slot kind, 2 days.

POI_LODGE = {
    "id": "h1",
    "name_display": "京王プラザ",
    "name_zh": "京王廣場",
    "geocode": {"lat": 43.06, "lng": 141.34},
}

RICH_ITIN = {
    "title": "北海道行程 & 溫泉",
    "checklist": ["護照"],
    "days": [
        {
            "date": "2026-11-01",
            "label": "Day 1｜札幌",
            "lodging": "h1",
            "rows": [
                {"slot": "move", "text": "新千歲機場 → 札幌"},
                {"time": "12:00", "slot": "meal", "poi_id": "p1", "text": "午餐 & 海鮮"},
                {"time": "16:30", "slot": "lodging", "text": "check-in"},
                {"slot": "activity", "text": "▸ 備案｜雨天改室內逛街"},
            ],
        },
        {
            "date": "2026-11-02",
            "label": "Day 2｜小樽",
            "lodging": "h1",
            "rows": [
                {"time": "09:00", "slot": "visit", "poi_id": "p1", "text": "小樽運河"},
            ],
        },
    ],
}

RICH_MAP = {"p1": POI_P1, "h1": POI_LODGE}


class TestCardStyleScaffold:
    def setup_method(self):
        self.html = render_html_page(RICH_ITIN, RICH_MAP)

    def test_wrap_container(self):
        assert 'class="wrap"' in self.html

    def test_hero_present_with_title(self):
        assert 'class="hero"' in self.html
        # escaped title lives inside the hero h1
        assert "北海道行程 &amp; 溫泉" in self.html

    def test_hero_meta_date_span(self):
        # date span derived from days[].date — honest, not invented
        assert 'class="meta"' in self.html
        assert "2026/11/01" in self.html
        assert "2026/11/02" in self.html

    def test_footer_present(self):
        assert "<footer" in self.html

    def test_rwd_media_query_present(self):
        assert "@media" in self.html


class TestCardStyleDayCards:
    def setup_method(self):
        self.html = render_html_page(RICH_ITIN, RICH_MAP)

    def test_day_card_is_section(self):
        assert '<section class="day-card"' in self.html

    def test_day_card_count_unchanged(self):
        # gate-critical: one class="day-card" per day, nowhere else
        assert self.html.count('class="day-card"') == 2

    def test_day_number_badge(self):
        assert self.html.count('class="dnum"') == 2

    def test_rows_use_li_with_slot_class(self):
        assert 'class="rows"' in self.html
        assert "slot-meal" in self.html
        assert "slot-move" in self.html
        assert "slot-visit" in self.html


class TestCardStyleLodge:
    def test_lodge_line_present_and_linked_when_resolves(self):
        html = render_html_page(RICH_ITIN, RICH_MAP)
        # both days carry lodging h1 → two lodge lines
        assert html.count('class="lodge"') == 2
        # lodge name is a maps link (href first, https) so the gate accepts it
        assert '<a href="https://www.google.com/maps/search/' in html
        assert "京王" in html

    def test_lodge_line_absent_when_no_lodging(self):
        # ITIN days carry no lodging field → no lodge line at all
        html = render_html_page(ITIN, POI_MAP)
        assert 'class="lodge"' not in html

    def test_lodge_line_skipped_when_unresolved(self):
        # lodging id not in poi_map → skip silently, never emit empty href
        itin = {
            "title": "x",
            "days": [{"date": "2026-11-01", "label": "D1", "lodging": "ghost", "rows": []}],
        }
        html = render_html_page(itin, {})
        assert 'class="lodge"' not in html
        assert 'href=""' not in html


class TestCardStyleOverview:
    def setup_method(self):
        self.html = render_html_page(RICH_ITIN, RICH_MAP)

    def test_overview_table_present(self):
        assert 'class="ov"' in self.html

    def test_overview_one_row_per_day(self):
        # one D-cell per day
        assert self.html.count('class="d"') == 2
        assert "D1" in self.html
        assert "D2" in self.html


class TestCardStyleLegendAndAlt:
    def setup_method(self):
        self.html = render_html_page(RICH_ITIN, RICH_MAP)

    def test_legend_present_with_emoji(self):
        assert 'class="legend"' in self.html
        for emoji in ("🍽", "📍", "🎯", "🚆", "🏨"):
            assert emoji in self.html
        assert "備案" in self.html

    def test_alt_row_is_altbox(self):
        # a row whose text starts with ▸ becomes an .altrow whose body is a full-width
        # .altbox card inside the 說明 cell (G3) — not a whole-row orange <li>.
        assert "altrow" in self.html
        assert self.html.count('class="altbox"') == 1


class TestCardStyleSlotEmoji:
    def test_each_slot_maps_to_emoji(self):
        html = render_html_page(RICH_ITIN, RICH_MAP)
        for emoji in ("🚆", "🍽", "🏨", "🎯", "📍"):
            assert emoji in html

    def test_unknown_slot_renders_gracefully(self):
        # ITIN fixture uses slot="lunch" (not in schema enum) — must not crash,
        # must still render the row body text
        html = render_html_page(ITIN, POI_MAP)
        assert "必吃 &amp; 推薦" in html


class TestCardStyleGateRoundTrip:
    def test_rich_page_passes_html_gate(self):
        from scripts.export_gate import run_html_gate

        html = render_html_page(RICH_ITIN, RICH_MAP)
        result = run_html_gate(html, pois=list(RICH_MAP.values()), min_days=2)
        assert result["status"] == "pass", result["failures"]
        assert result["failures"] == []


# ---------------------------------------------------------------------------
# Mobile RWD fail-safe (v0.17.0): long JP map labels must never force a
# horizontal overflow. flex children default to min-width:auto (won't shrink),
# so a long unbreakable link blows out page width and the page shifts left on
# phones. The body cell must shrink+wrap, the map chip must wrap, and the page
# clips any residual horizontal overflow as a backstop.
# ---------------------------------------------------------------------------

class TestRwdFailSafe:
    def setup_method(self):
        self.html = render_html_page(RICH_ITIN, RICH_MAP)

    def test_flex_body_can_shrink_and_wrap(self):
        assert "min-width:0" in self.html
        assert "overflow-wrap:anywhere" in self.html

    def test_map_link_wraps_not_nowrap(self):
        import re

        m = re.search(r"a\.map\{([^}]*)\}", self.html)
        assert m, "a.map CSS rule missing"
        rule = m.group(1)
        assert "white-space:nowrap" not in rule  # nowrap would overflow on mobile
        assert "word-break:break-word" in rule
        assert "max-width:100%" in rule

    def test_page_clips_horizontal_overflow(self):
        assert "overflow-x:hidden" in self.html

    def test_overview_cells_break_long_tokens(self):
        # the overview table sits OUTSIDE the .bd min-width:0 flex fix, so a long
        # space-free token in a 行程/住宿 cell could overflow — cells must wrap.
        import re

        m = re.search(r"table\.ov th,table\.ov td\{([^}]*)\}", self.html)
        assert m, "table.ov cell rule missing"
        assert "word-break:break-word" in m.group(1)


# ---------------------------------------------------------------------------
# Security: every interpolation point escaped, incl. the hero date-span sink.
# run_html_gate only catches a literal <script>, so an <img onerror=> smuggled
# through an unescaped field would pass the gate — the renderer is the only
# defence. (adversarial-verify finding #1, HIGH)
# ---------------------------------------------------------------------------

class TestCardStyleSecurity:
    def test_hero_date_span_escaped(self):
        itin = {
            "title": "T",
            "days": [
                {"date": "<img src=x onerror=alert(1)>", "label": "D1", "rows": []},
                {"date": "2026-11-07", "label": "D7", "rows": []},
            ],
        }
        html = render_html_page(itin, {})
        assert "<img src=x onerror=" not in html          # raw tag must not survive
        assert "&lt;img src=x onerror=" in html           # escaped form present

    def test_legit_date_span_unchanged_by_escaping(self):
        itin = {
            "title": "T",
            "days": [
                {"date": "2026-11-01", "label": "D1", "rows": []},
                {"date": "2026-11-07", "label": "D7", "rows": []},
            ],
        }
        html = render_html_page(itin, {})
        assert "2026/11/01–2026/11/07" in html


# ---------------------------------------------------------------------------
# Coverage round-out (adversarial-verify findings #3–#9)
# ---------------------------------------------------------------------------

POI_LODGE2 = {"id": "h2", "name_display": "乃の風", "name_zh": "乃之風",
              "geocode": {"lat": 42.55, "lng": 140.78}}


class TestGridLayout:
    """G1: 3-column CSS grid (時間 48 | 說明 1fr | 縮圖 64), reserved thumb cell,
    no separate emoji column."""

    def setup_method(self):
        self.html = render_html_page(RICH_ITIN, RICH_MAP)

    def test_grid_template_present(self):
        assert "grid-template-columns:48px 1fr 64px" in self.html

    def test_no_emoji_span(self):
        # the slot emoji folds into the 說明 cell; the dedicated .emo column is gone.
        assert 'class="emo"' not in self.html

    def test_row_emits_three_grid_cells(self):
        # every real <li class="row…"> carries exactly one .t, .bd and .thcol cell.
        for li in re.findall(r'<li class="row[^"]*">.*?</li>', self.html, re.S):
            assert li.count('<span class="t">') == 1, li
            assert li.count('<span class="bd"') == 1, li
            assert li.count('<span class="thcol"') == 1, li

    def test_photoless_row_has_empty_thcol(self):
        # RICH_ITIN rows carry no photos → every reserved thumb cell is empty.
        assert '<span class="thcol"></span>' in self.html
        assert "<img" not in self.html

    def test_t_track_has_no_fixed_width(self):
        # the grid track owns the time-column width; .t must not re-declare width.
        m = re.search(r"\.t\{([^}]*)\}", self.html)
        assert m and "width:" not in m.group(1)


class TestAltBox:
    """G3: 備案 rows render as a full-width .altbox INSIDE the 說明 cell only —
    empty .t, empty .thcol, never a thumbnail."""

    def _html(self, rows, pmap=None):
        itin = {"title": "T", "days": [{"date": "2026-11-01", "label": "D1",
                "rows": [dict(r) for r in rows]}]}
        return render_html_page(itin, pmap or {})

    def test_alt_row_is_altbox_in_cell(self):
        h = self._html([{"slot": "activity", "text": "▸ 備案｜改室內"}])
        assert 'class="altrow' in h
        assert '<span class="bd"><span class="altbox">' in h
        assert '<span class="t"></span>' in h         # empty time cell
        assert '<span class="thcol"></span>' in h     # empty reserved thumb cell
        assert "li.row.alt{" not in h                 # superseded whole-row <li> gone
        assert "row alt attached" not in h            # D11 attach machinery gone

    def test_alt_row_with_poi_no_thumbnail(self):
        # an alt row whose poi carries a photo emits NO <img> for that row (G3).
        h = self._html([{"slot": "visit", "poi_id": "pp", "text": "▸ 備案｜改泡湯"}],
                       {"pp": POI_PHOTO})
        assert 'class="altrow' in h
        assert "<img" not in h

    def test_alt_row_with_poi_still_gets_chip(self):
        h = self._html([{"slot": "activity", "poi_id": "p1", "text": "▸ 備案｜改去這裡"}],
                       POI_MAP)
        assert 'class="altrow' in h
        assert 'class="altbox"' in h
        assert 'class="map"' in h                      # chip rendered even on an alt row


class TestDashedGrouping:
    """G4: the dashed bottom border is opt-in per a look-ahead rule that visually
    binds a 備案 to the slot it follows (superseding D11's ↳ attach connector).

      real→alt  : NO dashed  (備案 attaches to the slot above)
      alt →real : dashed     (group ends)
      alt →alt  : NO dashed  (consecutive 備案 stay grouped)
      real→real : dashed
      *  →last  : NO dashed
    """

    def _classes(self, rows):
        itin = {"title": "T", "days": [{"date": "2026-11-01", "label": "D1",
                "rows": [{"slot": s, "text": t} for s, t in rows]}]}
        html = render_html_page(itin, {})
        return re.findall(r'<li class="([^"]*)">', html)

    def test_real_then_alt_no_dashed(self):
        cls = self._classes([("visit", "看夜景"), ("activity", "▸ 備案"), ("meal", "晚餐")])
        assert "dashed" not in cls[0]      # real→alt
        assert "dashed" in cls[1]          # alt→real

    def test_alt_then_alt_no_dashed(self):
        cls = self._classes([("visit", "x"), ("activity", "▸ A"),
                             ("activity", "▸ B"), ("move", "送迎")])
        assert "dashed" not in cls[0]      # real→alt
        assert "dashed" not in cls[1]      # alt→alt
        assert "dashed" in cls[2]          # alt→real

    def test_real_then_real_dashed(self):
        cls = self._classes([("visit", "a"), ("meal", "b"), ("move", "c")])
        assert "dashed" in cls[0] and "dashed" in cls[1]   # real→real

    def test_last_row_never_dashed(self):
        cls = self._classes([("visit", "a"), ("meal", "b")])
        assert "dashed" not in cls[-1]                     # *→last
        cls2 = self._classes([("visit", "a"), ("activity", "▸ tail")])
        assert "dashed" not in cls2[-1]                    # trailing alt is also last


class TestLodgeBox:
    """G5: the lodging line is a distinct light-blue rounded box."""

    def test_lodge_is_box(self):
        html = render_html_page(RICH_ITIN, RICH_MAP)
        m = re.search(r"\.lodge\{([^}]*)\}", html)
        assert m, "lodge rule missing"
        rule = m.group(1)
        assert "background:#f0f9fb" in rule
        assert "border:1px solid #cdeaf0" in rule
        assert "border-radius:10px" in rule
        assert "padding:8px 12px" in rule


class TestCardStyleCoverage:
    def test_missing_title_defaults(self):
        html = render_html_page({"days": [{"date": "2026-11-01", "label": "D1", "rows": []}]}, {})
        assert "<title>行程</title>" in html

    def test_lodging_flow_collapses_with_count(self):
        itin = {"title": "T", "days": [
            {"date": "2026-11-01", "label": "D1", "lodging": "h1", "rows": []},
            {"date": "2026-11-02", "label": "D2", "lodging": "h1", "rows": []},
            {"date": "2026-11-03", "label": "D3", "lodging": "h2", "rows": []},
        ]}
        html = render_html_page(itin, {"h1": POI_LODGE, "h2": POI_LODGE2})
        assert 'class="flow"' in html
        assert "×2" in html and "×1" in html
        assert "→" in html

    def test_overview_lodging_dash_when_absent(self):
        # ITIN days carry no lodging → overview 住宿 cell shows —
        html = render_html_page(ITIN, POI_MAP)
        assert "<td>—</td>" in html

    def test_date_span_single_day(self):
        itin = {"title": "T", "days": [{"date": "2026-11-01", "label": "D1", "rows": []}]}
        html = render_html_page(itin, {})
        assert "📅 2026/11/01</span>" in html   # single date, no range dash

    def test_alt_row_with_poi_gets_box_and_chip(self):
        itin = {"title": "T", "days": [{"date": "2026-11-01", "label": "D1", "rows": [
            {"slot": "activity", "poi_id": "p1", "text": "▸ 備案｜改去這裡"},
        ]}]}
        html = render_html_page(itin, POI_MAP)
        assert 'class="altrow' in html            # full-width 備案 row (G3)
        assert 'class="altbox"' in html
        assert 'class="map"' in html              # chip rendered even on an alt row

    def test_lodging_name_special_chars_escaped(self):
        evil = {"id": "h", "name_display": "Hotel <b>", "name_zh": "飯店&",
                "geocode": {"lat": 43.0, "lng": 141.0}}
        itin = {"title": "T", "days": [
            {"date": "2026-11-01", "label": "D1", "lodging": "h", "rows": []},
        ]}
        html = render_html_page(itin, {"h": evil})
        assert "<b>" not in html                  # no raw tag (lodge line + flow + overview)
        assert "&lt;b&gt;" in html
        assert "飯店&amp;" in html                 # ampersand escaped everywhere it appears

    def test_row_without_time_emits_empty_t(self):
        # a timeless row still emits its .t grid cell (empty) so columns stay aligned.
        itin = {"title": "T", "days": [{"date": "2026-11-01", "label": "D1", "rows": [
            {"slot": "move", "text": "go"},
        ]}]}
        html = render_html_page(itin, {})
        assert '<span class="t"></span>' in html


# ---------------------------------------------------------------------------
# PR3: POI photo slot + pure-CSS checkbox-hack lightbox + attribution caption.
# Separate fixture (POI_MAP above is deliberately photo-less so the
# no-external-src / gate-round-trip tests stay asset-free).
# ---------------------------------------------------------------------------

POI_PHOTO = {
    "id": "pp",
    "name_display": "登別温泉",
    "name_zh": "登別溫泉",
    "geocode": {"lat": 42.49, "lng": 141.15},
    "photo": {
        "data": "data:image/jpeg;base64,/9j/FULLDATA",
        "width": 640, "height": 480,
        "thumb": {"data": "data:image/jpeg;base64,/9j/THUMB", "width": 160, "height": 120},
    },
    "photo_attribution": {
        "author": "Commons User <evil>",
        "license": "CC-BY-SA-4.0",
        "source_url": "https://commons.wikimedia.org/wiki/File:X.jpg",
    },
    "photo_source": "wikimedia",
}

PHOTO_ITIN = {
    "title": "溫泉行",
    "days": [{"date": "2026-11-01", "label": "D1", "rows": [
        {"time": "10:00", "slot": "visit", "poi_id": "pp", "text": "泡湯"},
    ]}],
}
PHOTO_MAP = {"pp": POI_PHOTO}


class TestPhotoRender:
    def setup_method(self):
        self.html = render_html_page(PHOTO_ITIN, PHOTO_MAP)

    def test_thumb_img_emitted(self):
        assert 'class="thumb"' in self.html
        assert "data:image/jpeg;base64,/9j/THUMB" in self.html      # thumbnail src

    def test_lightbox_full_image_emitted(self):
        assert "data:image/jpeg;base64,/9j/FULLDATA" in self.html   # full src

    def test_lightbox_is_pure_css_no_script_no_anchor(self):
        assert 'type="checkbox"' in self.html
        assert "<script" not in self.html.lower()
        assert 'href="#' not in self.html                            # no #anchor toggle

    def test_attribution_caption_visible_and_escaped(self):
        assert "CC-BY-SA-4.0" in self.html
        assert "Commons User &lt;evil&gt;" in self.html              # author escaped
        assert "<evil>" not in self.html                             # raw tag gone
        assert 'href="https://commons.wikimedia.org/wiki/File:X.jpg"' in self.html

    def test_photo_img_src_is_safe_scheme(self):
        srcs = re.findall(r'<img[^>]*\bsrc="([^"]*)"', self.html)
        assert srcs
        for s in srcs:
            assert s.startswith("data:image/") or s.startswith("https://")

    def test_no_photo_no_img(self):
        html = render_html_page(ITIN, POI_MAP)
        assert "<img" not in html

    def test_photo_render_passes_html_gate(self):
        from scripts.export_gate import run_html_gate
        result = run_html_gate(self.html, pois=list(PHOTO_MAP.values()), min_days=1)
        assert result["status"] == "pass", result["failures"]
        assert result["failures"] == []

    def test_https_url_photo_rendered(self):
        poi = {"id": "u", "name_display": "X",
               "photo": {"url": "https://upload.wikimedia.org/x.jpg"},
               "photo_attribution": {"author": "A", "license": "CC0",
                                     "source_url": "https://a.example"},
               "photo_source": "openverse"}
        itin = {"title": "T", "days": [{"date": "2026-11-01", "label": "D1",
                "rows": [{"slot": "visit", "poi_id": "u", "text": "x"}]}]}
        html = render_html_page(itin, {"u": poi})
        assert 'src="https://upload.wikimedia.org/x.jpg"' in html

    def test_lodging_photo_inside_lodge_div(self):   # D10/G1: lodging thumb right-aligned
        itin = {"title": "T", "days": [{"date": "2026-11-01", "label": "D1",
                "lodging": "pp", "rows": []}]}
        html = render_html_page(itin, PHOTO_MAP)   # pp = POI_PHOTO (has photo)
        # the photo thumb is nested INSIDE the .lodge div (a flex child, so
        # .lodge .thumb{margin-left:auto} right-aligns it), not a sibling after </div>.
        lodge_seg = html.split('class="lodge"', 1)[1].split("</div>", 1)[0]
        assert 'class="thumb"' in lodge_seg

    def test_lodge_css_is_flex(self):   # D10
        import re
        m = re.search(r"\.lodge\{([^}]*)\}", self.html)
        assert m and "display:flex" in m.group(1) and "align-items:center" in m.group(1)

    def test_row_phcap_removed(self):   # D9: no duplicate row caption blowing the column
        assert 'class="phcap"' not in self.html

    def test_thumb_has_title_attribution(self):   # D9: 署名 moves to title/hover
        assert 'title="📷 Commons User &lt;evil&gt; / CC-BY-SA-4.0"' in self.html

    def test_lightbox_caption_centered_column(self):   # D9: lbcap centered under image
        assert "flex-direction:column;align-items:center}" in self.html   # .lbbox
        assert ".lbimg{display:block" in self.html
        assert ".lbcap{" in self.html and "text-align:center" in self.html

    def test_thumb_in_reserved_thcol_cell(self):   # D8/G1: thumb lives in the grid cell
        # the thumb occupies the reserved .thcol grid cell — the last of the three
        # row cells, immediately after .bd — instead of a margin-left:auto flex sibling.
        assert '</span><span class="thcol">' in self.html

    def test_thumb_css_small_square(self):   # D8/G1
        assert "width:60px;height:60px" in self.html
        assert "object-fit:cover" in self.html
        assert "margin-left:auto" in self.html   # .lodge .thumb right-align (G5)

    def test_unique_checkbox_id_when_poi_is_row_and_lodging(self):
        itin = {"title": "T", "days": [{"date": "2026-11-01", "label": "D1",
                "lodging": "pp", "rows": [
                    {"slot": "visit", "poi_id": "pp", "text": "x"}]}]}
        html = render_html_page(itin, PHOTO_MAP)
        ids = re.findall(r'<input[^>]*id="(ph-[^"]*)"', html)
        assert len(ids) == 2
        assert len(set(ids)) == 2                                    # no duplicate id
