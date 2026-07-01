"""E2E closure for the 2026-07-01 gmaps dead-link incident (D2).

One fixture reproducing the 0.23.0 incident — a POI carrying a gmaps_place_id whose
map link rendered as the dead `maps/place/?q=place_id:<id>` form and passed BOTH gates
green while 38 links were dead. Asserts the D2 fix closes every axis at once:

  1. maps_url NEVER emits the dead form (D1 lock; green by design since 0.24.0).
  2. a real 0.24.0-rendered md deliverable passes export-gate (maps-form check green).
  3. a real 0.24.0-rendered html deliverable passes html-gate (maps-form check green).
  4. the SAME deliverables with the 0.23.0 dead form injected now FAIL both gates on
     maps_link_resolvable_form (previously blind) and stay retryable (re-render fixes it).
"""
from scripts.export_gate import run_export_gate, run_html_gate
from scripts.render.markdown import render_day_table
from scripts.render.html_page import render_html_page, _html_escape
from scripts.render.gmaps_links import maps_url

# One POI carrying a gmaps_place_id — the exact 0.23.0 trigger.
POI = {
    "id": "odori", "name_local": "大通公園", "name_display": "大通公園",
    "name_zh": "大通公園", "district": "Sapporo",
    "gmaps_place_id": "ChIJ_odori-123",
    "geocode": {"lat": 43.06, "lng": 141.35},
}
POI_MAP = {"odori": POI}

DAY = {"label": "Day 1 — 札幌", "rows": [
    {"time": "09:00", "slot": "visit", "poi_id": "odori", "text": "散步"}]}
ITIN = {"title": "北海道", "days": [
    {"date": "2026-03-01", "label": "Day 1 — 札幌", "rows": DAY["rows"]}]}

# The banned single-param deep-link form Google does not resolve (the D1 regression).
DEAD = "https://www.google.com/maps/place/?q=place_id:ChIJ_odori-123"


def _check(r, name):
    return next(c["passed"] for c in r["checks"] if c["name"] == name)


def test_d1_maps_url_never_emits_dead_form():
    url = maps_url(POI)
    assert "/maps/place/" not in url
    assert "query_place_id=ChIJ_odori-123" in url


def test_clean_md_deliverable_passes_maps_form():
    md = render_day_table(DAY, POI_MAP)
    r = run_export_gate(md, [POI], min_days=1)
    assert r["status"] == "pass", r["failures"]
    assert _check(r, "maps_link_resolvable_form") is True


def test_clean_html_deliverable_passes_maps_form():
    html = render_html_page(ITIN, POI_MAP)
    r = run_html_gate(html, pois=[POI], min_days=1)
    assert r["status"] == "pass", r["failures"]
    assert _check(r, "maps_link_resolvable_form") is True


def test_injected_0230_dead_form_now_fails_export_gate():
    # simulate the 0.23.0 regression: canonical link swapped for the dead form
    md = render_day_table(DAY, POI_MAP).replace(maps_url(POI), DEAD)
    assert DEAD in md                              # the dead form is really present
    r = run_export_gate(md, [POI], min_days=1)
    assert r["status"] == "fail"
    assert _check(r, "maps_link_resolvable_form") is False
    assert any("place_id" in f for f in r["failures"])
    assert r["retryable"] is True                  # re-render fixes it (the real remedy)


def test_resolvable_place_share_official_source_does_not_block_export():
    # a verified POI whose OFFICIAL SOURCE is a real, resolvable /maps/place/<name>/@
    # share link renders as [官網](…) and must NOT trip the maps-form gate — else a
    # legitimate export is blocked (the adversarial-verify false-positive, 2026-07-01).
    poi = {**POI, "booking": {"required": False},
           "sources": [{"url": "https://www.google.com/maps/place/Odori+Park/@43.06,141.35,15z",
                        "official": True, "lang": "ja"}]}
    md = render_day_table(DAY, {"odori": poi})
    assert "/maps/place/Odori+Park/@" in md          # the share link really rendered
    r = run_export_gate(md, [poi], min_days=1)
    assert r["status"] == "pass", r["failures"]
    assert _check(r, "maps_link_resolvable_form") is True


def test_injected_0230_dead_form_now_fails_html_gate():
    # html-escapes '&' in hrefs; DEAD carries none, so it is its own escaped form
    html = render_html_page(ITIN, POI_MAP).replace(_html_escape(maps_url(POI)), DEAD)
    assert DEAD in html
    r = run_html_gate(html, pois=[POI], min_days=1)
    assert r["status"] == "fail"
    assert _check(r, "maps_link_resolvable_form") is False
    assert any("place_id" in f for f in r["failures"])
    assert r["retryable"] is True
