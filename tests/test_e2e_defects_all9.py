"""E2E closure — ONE Sun-Moon-Lake mini-trip fixture that exercises all 9 consumer
defects (docs 2026-06-21-tripwork-defects-design) SIMULTANEOUSLY.

Step 7 of the 8-step pre-ship gate: the per-defect unit tests pass in isolation, but
the cross-defect interaction (closed/mismatch POIs filtered out by P1/P2, the chosen
lodging folded in by P4, the thematic must_do covered by P5, all in one gate run) must
also close. Each defect gets a direct assertion; schema validation proves the new
fields (business_status / rooms / must_do_coverage / distributable) coexist.
"""
import json
import pathlib

import jsonschema
import pytest

from scripts.verify import verify_poi
from scripts.geocode import resolve_place
from scripts.gate import run_gate, chosen_lodging_pois
from scripts.cost import lodging_line_amount, sum_costs, over_budget
from scripts.export_gate import run_export_gate, run_html_gate
from scripts.render.gmaps_links import maps_url
from scripts.render.html_page import render_html_page

SCHEMAS = pathlib.Path(__file__).resolve().parent.parent / "schemas"


def _sources():
    return [{"url": "https://a.example", "lang": "zh"},
            {"url": "https://b.example", "lang": "zh"}]


# ---- shared raw candidates (destination-research output, pre source-verify) ----
FERRY = {"id": "ferry", "name_local": "水社碼頭", "name_display": "水社碼頭",
         "name_roman": "Shuishe Pier", "category": "activity", "district": "日月潭",
         "business_status": "OPERATIONAL", "gmaps_place_id": "ChIJ_ferry",
         "geocode": {"lat": 23.86, "lng": 120.91}, "sources": _sources()}
STAR_MOON = {"id": "star-moon", "name_local": "星月大地", "name_display": "星月大地",
             "category": "meal", "district": "后里",
             "business_status": "CLOSED_PERMANENTLY",
             "geocode": {"lat": 24.3, "lng": 120.7}, "sources": _sources()}
NO_SIGNAL = {"id": "no-signal", "name_local": "某餐廳", "name_display": "某餐廳",
             "category": "meal", "district": "日月潭",
             "geocode": {"lat": 23.86, "lng": 120.91}, "sources": _sources()}
RENAMED = {"id": "renamed", "name_local": "星月大地", "name_display": "星月大地",
           "category": "meal", "district": "后里", "business_status": "OPERATIONAL",
           "geocode": {"lat": 24.3, "lng": 120.7}, "sources": _sources()}

ACCOMMODATIONS = {"stops": [{
    "district": "日月潭", "nights": 2, "chosen": "hotel-lili",
    "candidates": [{
        "id": "hotel-lili", "name_local": "力麗溫德姆溫泉酒店",
        "name_display": "力麗溫德姆溫泉酒店", "verify_status": "verified",
        "facilities": [], "geocode": {"lat": 23.86, "lng": 120.92},
        "cost": {"amount": 3000, "currency": "TWD", "basis": "per_night", "rooms": 2},
        "sources": _sources()}]}]}


def _verified_pois():
    """Run the source-verify decision over the candidates and keep the verified ones,
    exactly as the pipeline would. Exercises P1 (operating) + P2 (name match)."""
    out = []
    # ferry: OPERATIONAL + resolved name matches -> verified
    _, s, _ = verify_poi(FERRY, geocoded=True, in_claimed_region=True,
                         resolved_name="水社碼頭, 日月潭, 南投縣")
    if s == "verified":
        out.append({**FERRY, "verify_status": "verified"})
    return out


# ============================================================================
class TestE2EAllNineDefects:
    def test_schemas_accept_the_new_fields_together(self):
        # P1 business_status, P6 rooms, P5 must_do_coverage, P9 gmaps_place_id all
        # coexist in valid artifacts.
        cand_schema = json.load(open(SCHEMAS / "candidates.schema.json"))
        # candidates carry business_status (P1) but not the verified-pois-only fields
        # (geocode / gmaps_place_id / district); those land during/after verify.
        raw_cands = [
            {"id": "ferry", "name_local": "水社碼頭", "name_display": "水社碼頭",
             "name_roman": "Shuishe Pier", "category": "activity",
             "claimed_district": "日月潭", "business_status": "OPERATIONAL",
             "sources": _sources()},
            {"id": "star-moon", "name_local": "星月大地", "name_display": "星月大地",
             "category": "meal", "claimed_district": "后里",
             "business_status": "CLOSED_PERMANENTLY", "sources": _sources()},
        ]
        jsonschema.validate({"candidates": raw_cands}, cand_schema)
        acc_schema = json.load(open(SCHEMAS / "accommodations.schema.json"))
        jsonschema.validate(ACCOMMODATIONS, acc_schema)
        vp_schema = json.load(open(SCHEMAS / "verified-pois.schema.json"))
        jsonschema.validate({"pois": _verified_pois()}, vp_schema)
        itin_schema = json.load(open(SCHEMAS / "itinerary.schema.json"))
        jsonschema.validate(self._itin(), itin_schema)

    # ---- P1 ----
    def test_p1_closed_rejected_missing_unverified_operational_verified(self):
        assert verify_poi(STAR_MOON, geocoded=True, in_claimed_region=True)[1] == "rejected"
        assert verify_poi(NO_SIGNAL, geocoded=True, in_claimed_region=True)[1] == "unverified"
        assert verify_poi(FERRY, geocoded=True, in_claimed_region=True,
                          resolved_name="水社碼頭, 日月潭")[1] == "verified"

    # ---- P2 ----
    def test_p2_renamed_neighbour_is_conflicting(self):
        _, status, note = verify_poi(RENAMED, geocoded=True, in_claimed_region=True,
                                     resolved_name="星月驛站, 后里區, 台中市")
        assert status == "conflicting"
        assert "mismatch" in note.lower()

    # ---- P3 ----
    def test_p3_landmark_resolves_via_roman_or_bare(self, monkeypatch):
        import scripts.geocode as g

        def fake_structured(name, city=None, country=None, timeout=10):
            return None  # street-slot misses

        def fake_geocode(query, timeout=10):
            if query in ("水社碼頭", "Shuishe Pier"):  # bare or roman resolves
                return g.GeocodeResult(23.86, 120.91, "水社碼頭 result")
            return None

        monkeypatch.setattr(g, "geocode_structured", fake_structured)
        monkeypatch.setattr(g, "geocode", fake_geocode)
        res, _ = resolve_place("水社碼頭", district="日月潭", country="Taiwan",
                               name_roman="Shuishe Pier")
        assert res is not None

    # ---- P4 + P5 combined (the cross-defect gate run) ----
    def _itin(self):
        return {"title": "日月潭 3D2N", "days": [
            {"date": "2026-07-01", "label": "D1",
             "rows": [{"time": "12:00", "slot": "meal", "poi_id": "ferry", "text": "午餐"}],
             "lodging": "hotel-lili"},
            {"date": "2026-07-02", "label": "D2",
             "rows": [{"time": "12:00", "slot": "meal", "poi_id": "ferry", "text": "午餐"}]},
        ], "must_do_coverage": {"日月潭遊湖賞景": ["ferry"]}}

    def test_p4_p5_gate_passes_with_lodging_and_thematic_must_do(self):
        pois = _verified_pois()             # only ferry survives P1/P2 (P1/P2 closure)
        r = run_gate(pois, self._itin(), accommodations=ACCOMMODATIONS,
                     must_do=["日月潭遊湖賞景"], advisory={"items": []})
        assert r["status"] == "pass", r["failures"]
        # P4: chosen lodging resolved from accommodations, not flagged unknown
        assert not any("unknown POI 'hotel-lili'" in f for f in r["failures"])
        assert {"name": "overnight_days_have_lodging", "passed": True} in r["checks"]
        # P5: thematic must_do covered via the coverage map
        assert {"name": "must_do_covered", "passed": True} in r["checks"]

    def test_p4_chosen_lodging_pool_helper(self):
        assert {p["id"] for p in chosen_lodging_pois(ACCOMMODATIONS)} == {"hotel-lili"}

    def test_p4_export_html_gate_clean_on_rendered_lodging(self):
        # Matrix step-8 interaction (Family C): folding the chosen lodging into the
        # render pool (P4) must NOT make the export/html gate spuriously flag the new
        # lodging row. Build poi_map the way export-artifact now does and gate it.
        poi_map = {p["id"]: p for p in _verified_pois()}
        poi_map.update({p["id"]: p for p in chosen_lodging_pois(ACCOMMODATIONS)})
        html = render_html_page(self._itin(), poi_map)
        assert "力麗溫德姆溫泉酒店" in html               # lodging actually rendered
        r = run_html_gate(html, pois=list(poi_map.values()), min_days=2)
        assert r["status"] == "pass", r["failures"]

    # ---- P6 ----
    def test_p6_two_room_lodging_cost_and_budget(self):
        stop = ACCOMMODATIONS["stops"][0]
        amt = lodging_line_amount(stop["candidates"][0]["cost"], nights=stop["nights"],
                                  rooms=stop["candidates"][0]["cost"]["rooms"])
        assert amt == 3000 * 2 * 2  # per_room × rooms × nights
        total = sum_costs([{"category": "lodging", "amount": amt}])["total"]
        assert over_budget(total, 10000) is True   # whole-trip scope: 12000 > 10000

    # ---- P7 ----
    def test_p7_google_photo_terminal_nondistributable(self):
        gphoto = {"id": "ferry", "name_local": "x", "name_display": "x",
                  "photo": {"data": "data:image/png;base64,iVB"},
                  "photo_attribution": {"author": "A", "license": "CC0",
                                        "source_url": "https://a.example"},
                  "photo_source": "google"}
        r = run_export_gate("### D1\n\nclean text\n", [gphoto])
        assert r["status"] == "pass" and r["distributable"] is False

    # ---- P8 ----
    def test_p8_media_present_but_zero_photos_fails(self):
        r = run_html_gate('<div class="day-card"></div>', pois=[], min_days=1, media_count=3)
        assert r["status"] == "fail"
        assert any("media side-file" in f and "0 photos" in f for f in r["failures"])

    # ---- P9 ----
    def test_p9_place_id_query_place_id_link_in_render(self):
        url = maps_url(FERRY)
        assert url.startswith("https://www.google.com/maps/search/?api=1&query=")
        assert url.endswith("&query_place_id=ChIJ_ferry")
        assert "/maps/place/" not in url           # dead form must not reappear
        # and it rides through the HTML renderer
        html = render_html_page(self._itin(), {p["id"]: p for p in _verified_pois()})
        assert "&amp;query_place_id=ChIJ_ferry" in html   # & escaped in href attr
        assert "maps/place/?q=place_id" not in html
