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

    def test_google_photo_source_non_distributable_fails(self):
        pois = [_photo_poi({"photo_source": "google"})]
        r = run_html_gate(self._html(), pois=pois, min_days=1)
        assert r["status"] == "fail"
        assert any("non-distributable photo_source" in f for f in r["failures"])

    def test_new_check_names_present(self):
        r = run_html_gate(self._html(), pois=[], min_days=1)
        names = {c["name"] for c in r["checks"]}
        assert {"img_src_safe", "photo_has_attribution",
                "no_nondistributable_photo_source"} <= names
