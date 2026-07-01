"""Tests for run_html_gate — one-page HTML deliverable validation. (dogfood D4)

Uses the same fixture itin/poi_map as test_html_page.py to generate real HTML.
Strict TDD: tests written against the not-yet-implemented run_html_gate.
"""
import pytest

from scripts.export_gate import run_html_gate
from scripts.render.html_page import render_html_page

# ---------------------------------------------------------------------------
# Shared fixture (mirrors test_html_page.py)
# ---------------------------------------------------------------------------

POI_P1 = {
    "id": "p1",
    "name_display": "だるま <本店>",
    "name_zh": "達摩",
    "geocode": {"lat": 43.06, "lng": 141.35},
}

ITIN = {
    "title": "北海道 & 旅行",
    "checklist": ["護照", "JR Pass"],
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
    ],
}

POI_MAP = {"p1": POI_P1}


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestRunHtmlGate:

    def test_valid_page_passes(self):
        """Well-formed page from render_html_page with min_days=1 → status 'pass'."""
        html = render_html_page(ITIN, POI_MAP)
        result = run_html_gate(html, pois=[], min_days=1)
        assert result["status"] == "pass", result["failures"]
        assert result["failures"] == []

    def test_empty_string_fails(self):
        """Empty string → status 'fail' mentioning empty."""
        result = run_html_gate("", pois=[], min_days=None)
        assert result["status"] == "fail"
        assert any("empty" in f for f in result["failures"])

    def test_too_few_day_cards_fails(self):
        """Real page but min_days=5 → status 'fail' (only 1 day card)."""
        html = render_html_page(ITIN, POI_MAP)
        result = run_html_gate(html, pois=[], min_days=5)
        assert result["status"] == "fail"
        assert any("too few day cards" in f for f in result["failures"])

    def test_javascript_href_fails(self):
        """Page with javascript: href + a day-card → fail, failure mentions 'href'."""
        html = render_html_page(ITIN, POI_MAP)
        # Inject a javascript: href after the day-card div so the card count stays 1
        bad_html = html + '<a href="javascript:alert(1)">x</a>'
        result = run_html_gate(bad_html, pois=[], min_days=1)
        assert result["status"] == "fail"
        assert any("href" in f for f in result["failures"])

    def test_raw_script_tag_fails(self):
        """Page containing a <script> tag → status 'fail'."""
        html = render_html_page(ITIN, POI_MAP)
        bad_html = html + "<script>alert('xss')</script>"
        result = run_html_gate(bad_html, pois=[], min_days=1)
        assert result["status"] == "fail"
        assert any("script" in f.lower() for f in result["failures"])


# ---------------------------------------------------------------------------
# PR4: <img src> whitelist + attribution presence + distributability
# Injected AFTER the rendered html so the day-card count stays 1.
# ---------------------------------------------------------------------------

def _photo_poi(over=None):
    p = {"id": "p1", "photo": {"data": "data:image/png;base64,iVBORw0KGgo="},
         "photo_attribution": {"author": "A", "license": "CC0", "source_url": "https://a.example"},
         "photo_source": "wikimedia"}
    if over:
        p.update(over)
    return p


class TestRunHtmlGatePhoto:

    def _html(self, extra=""):
        return render_html_page(ITIN, POI_MAP) + extra

    def test_img_data_image_src_passes(self):
        html = self._html('<img src="data:image/png;base64,iVBORw0KGgo=" alt="x">')
        r = run_html_gate(html, pois=[], min_days=1)
        assert r["status"] == "pass", r["failures"]

    def test_img_https_src_passes(self):
        html = self._html('<img src="https://upload.wikimedia.org/x.jpg" alt="x">')
        r = run_html_gate(html, pois=[], min_days=1)
        assert r["status"] == "pass", r["failures"]

    def test_img_http_src_fails(self):
        html = self._html('<img src="http://insecure.example/x.jpg">')
        r = run_html_gate(html, pois=[], min_days=1)
        assert r["status"] == "fail"
        assert any("unsafe <img src>" in f for f in r["failures"])

    def test_img_javascript_src_fails(self):
        html = self._html('<img src="javascript:alert(1)">')
        r = run_html_gate(html, pois=[], min_days=1)
        assert r["status"] == "fail"
        assert any("unsafe <img src>" in f for f in r["failures"])

    def test_img_data_non_image_src_fails(self):
        html = self._html('<img src="data:text/html;base64,PHNjcmlwdD4=">')
        r = run_html_gate(html, pois=[], min_days=1)
        assert r["status"] == "fail"
        assert any("unsafe <img src>" in f for f in r["failures"])

    def test_photo_without_attribution_fails(self):
        pois = [{"id": "p1", "photo": {"data": "data:image/png;base64,iVB"}}]
        r = run_html_gate(self._html(), pois=pois, min_days=1)
        assert r["status"] == "fail"
        assert any("missing attribution" in f for f in r["failures"])

    def test_photo_with_attribution_passes(self):
        r = run_html_gate(self._html(), pois=[_photo_poi()], min_days=1)
        assert r["status"] == "pass", r["failures"]

    def test_google_photo_source_is_terminal_nondistributable(self):
        # P7 (MIGRATED): google photo -> clean terminal non-distributable, not a fail.
        pois = [_photo_poi({"photo_source": "google"})]
        r = run_html_gate(self._html(), pois=pois, min_days=1)
        assert r["status"] == "pass", r["failures"]
        assert r["distributable"] is False
        assert not any("non-distributable photo_source" in f for f in r["failures"])

    def test_new_check_names_present(self):
        r = run_html_gate(self._html(), pois=[], min_days=1)
        names = {c["name"] for c in r["checks"]}
        assert {"img_src_safe", "photo_has_attribution",
                "no_nondistributable_photo_source"} <= names


# ---------------------------------------------------------------------------
# G6: no internal jargon (poi-id tokens / must_do) in user-facing HTML
# Injected AFTER the rendered html so the day-card count stays 1.
# ---------------------------------------------------------------------------

class TestRunHtmlGateJargon:

    def _html(self, extra=""):
        return render_html_page(ITIN, POI_MAP) + extra

    def test_html_gate_fails_on_leaked_poi_id(self):
        html = self._html("<div>改五稜郭(hak-goryokaku)夜景</div>")
        r = run_html_gate(html, pois=[{"id": "hak-goryokaku"}], min_days=1)
        assert r["status"] == "fail"
        assert any("hak-goryokaku" in f and "leaked" in f for f in r["failures"])

    def test_html_gate_fails_on_must_do(self):
        html = self._html("<div>蟹会席 must_do</div>")
        r = run_html_gate(html, pois=[], min_days=1)
        assert r["status"] == "fail"
        assert any("must_do" in f for f in r["failures"])

    def test_html_gate_clean_passes_jargon(self):
        r = run_html_gate(self._html(), pois=[{"id": "hak-goryokaku"}], min_days=1)
        assert any(c["name"] == "no_internal_jargon" and c["passed"] for c in r["checks"])

    def test_html_gate_jargon_check_present(self):
        r = run_html_gate(self._html(), pois=[], min_days=1)
        assert "no_internal_jargon" in [c["name"] for c in r["checks"]]


# ---------------------------------------------------------------------------
# D2 (2026-07-01 gmaps-deadlink): maps_link_resolvable_form
# Every www.google.com/maps href must be a resolvable canonical form; the dead
# 0.23.0 `maps/place/?q=place_id:` form (still https://) is rejected. Injected
# AFTER the rendered html so the day-card count stays 1.
# ---------------------------------------------------------------------------

class TestRunHtmlGateMapsForm:

    _DEAD = "https://www.google.com/maps/place/?q=place_id:ChIJ_abc123"

    def _html(self, extra=""):
        return render_html_page(ITIN, POI_MAP) + extra

    def _passed(self, r):
        return any(c["name"] == "maps_link_resolvable_form" and c["passed"] for c in r["checks"])

    def test_dead_maps_place_id_href_fails(self):
        html = self._html(f'<a href="{self._DEAD}">x</a>')
        r = run_html_gate(html, pois=[], min_days=1)
        assert r["status"] == "fail"
        assert self._passed(r) is False
        assert any("place_id" in f for f in r["failures"])

    def test_real_rendered_page_maps_hrefs_pass(self):
        # render_html_page emits canonical /maps/search hrefs (html-escaped &amp;) —
        # the maps-form check normalises &amp; so the real page is NOT false-failed.
        r = run_html_gate(self._html(), pois=[], min_days=1)
        assert r["status"] == "pass", r["failures"]
        assert self._passed(r) is True

    def test_canonical_dir_href_passes(self):
        html = self._html('<a href="https://www.google.com/maps/dir/?api=1&amp;origin=A&amp;destination=B">go</a>')
        r = run_html_gate(html, pois=[], min_days=1)
        assert self._passed(r) is True

    def test_non_maps_host_href_not_flagged(self):
        html = self._html('<a href="https://jr.example/booking">官網</a>')
        r = run_html_gate(html, pois=[], min_days=1)
        assert self._passed(r) is True

    def test_resolvable_place_share_href_not_flagged(self):
        # a real /maps/place/<name>/@ share link (e.g. a POI official source) is
        # resolvable and must NOT be rejected. (adversarial-verify FP)
        html = self._html('<a href="https://www.google.com/maps/place/Kinosaki+Onsen/@35.6,134.8,15z">官網</a>')
        r = run_html_gate(html, pois=[], min_days=1)
        assert self._passed(r) is True

    def test_empty_query_href_fails(self):
        # html-escaped &amp; is normalised before the check, so an empty-query search
        # href is still caught in the rendered page
        html = self._html('<a href="https://www.google.com/maps/search/?api=1&amp;query=">x</a>')
        r = run_html_gate(html, pois=[], min_days=1)
        assert r["status"] == "fail"
        assert self._passed(r) is False

    def test_maps_form_check_present(self):
        r = run_html_gate(self._html(), pois=[], min_days=1)
        assert "maps_link_resolvable_form" in [c["name"] for c in r["checks"]]
