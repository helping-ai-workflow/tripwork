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
