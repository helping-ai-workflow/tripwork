"""v2.1.0 §5: an official source is never a search engine's results page -- for the
bookable link in the deliverable, and for the four artifacts whose schema demands an
official source (advisory, calendar, seasonal, legs)."""
import pytest

from scripts.export_gate import run_export_gate
from scripts.gate import official_search_failures, run_gate
from scripts.orchestration import GATE_INPUTS, route_gate_failures
from scripts.render.markdown import render_markdown_page
from scripts.verify import official_source_url

SEARCH = "https://www.google.com/search?q=%E7%A4%BA%E6%84%8F"
SITE = "https://shiyi.example/booking"


def _poi():
    return {"id": "p1", "name_display": "示意食堂", "name_local": "示意食堂", "verify_status": "verified",
            "category": "restaurant", "booking": {"required": True},
            "geocode": {"lat": 25.0, "lng": 121.5, "geocode_source": "nominatim"},
            "sources": [{"url": SEARCH, "official": True, "lang": "zh-TW"},
                        {"url": SITE, "official": True, "lang": "zh-TW"}]}


def test_official_source_url_skips_search_pages():
    assert official_source_url(_poi()) == SITE
    assert official_source_url({"sources": [{"url": SEARCH, "official": True}]}) is None


def test_markdown_and_export_gate_pick_same_official():
    poi = _poi()
    itin = {"title": "示意", "days": [{"date": "2030-01-01", "label": "D1",
                                       "rows": [{"time": "12:00", "slot": "meal", "poi_id": "p1"}]}]}
    md = render_markdown_page(itin, {"p1": poi})
    assert SITE in md and SEARCH not in md
    report = run_export_gate(md, [poi])
    assert not any("bookable POI" in f for f in report["failures"])


@pytest.mark.parametrize("name,doc,prefix,stage", [
    ("advisory", {"items": [{"topic": "x", "sources": [{"url": SEARCH, "official": True}]}]},
     "advisory official source", "tripwork:travel-advisory"),
    ("calendar", {"holidays": [{"date": "2030-01-01", "sources": [{"url": SEARCH, "official": True}]}]},
     "calendar official source", "tripwork:calendar-check"),
    ("seasonal", {"items": [{"hazard": "x", "sources": [{"url": SEARCH, "official": True}]}]},
     "seasonal official source", "tripwork:seasonal-advisory"),
    ("legs", {"legs": [{"from": "A", "to": "B", "sources": [{"url": SEARCH, "official": True}]}]},
     "legs official source", "tripwork:inter-stop-legs"),
])
def test_each_artifact_search_official_fails_and_routes(name, doc, prefix, stage):
    out = official_search_failures(**{name: doc})
    assert len(out) == 1 and out[0].startswith(prefix)
    assert route_gate_failures(out) == stage


def test_a_real_official_beside_a_search_page_passes():
    doc = {"items": [{"sources": [{"url": SEARCH, "official": True}, {"url": SITE, "official": True}]}]}
    assert official_search_failures(advisory=doc) == []


def test_run_gate_reports_the_seasonal_failure():
    seasonal = {"items": [{"sources": [{"url": SEARCH, "official": True}]}]}
    report = run_gate([], {"days": []}, seasonal=seasonal)
    assert any(f.startswith("seasonal official source") for f in report["failures"])
    assert {"name": "official_sources_not_search", "passed": False} in report["checks"]


def test_gate_inputs_include_seasonal():
    assert "seasonal.yaml" in GATE_INPUTS
