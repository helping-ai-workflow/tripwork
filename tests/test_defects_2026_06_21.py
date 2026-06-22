"""Acceptance tests for the 9 consumer defects (docs 2026-06-21-tripwork-defects-design).

Written RED-first per the 8-step plugin pre-ship gate. One class per defect.
Not-yet-existing names / params are imported or exercised INSIDE each test so an
unimplemented defect reports its own RED rather than failing module collection.
"""
from urllib.parse import unquote

import pytest

from scripts.verify import classify_candidate, verify_poi
from scripts.geocode import resolve_place
from scripts.gate import run_gate
from scripts.export_gate import run_export_gate, run_html_gate
from scripts.render.gmaps_links import maps_url


# --- shared builders (mirror tests/test_gate.py conventions) -------------------
def _poi(pid, geo=True, status="verified", **extra):
    d = {"id": pid, "verify_status": status,
         "name_local": extra.pop("name_local", pid),
         "name_display": extra.pop("name_display", pid)}
    if geo:
        d["geocode"] = {"lat": 1.0, "lng": 2.0}
    d.update(extra)
    return d


def _meal(pid):
    return {"time": "12:00", "slot": "meal", "poi_id": pid, "text": "lunch"}


def _itin(rows, date="2026-07-01", lodging=None, **extra):
    day = {"date": date, "label": "D1", "rows": rows}
    if lodging is not None:
        day["lodging"] = lodging
    out = {"title": "t", "days": [day]}
    out.update(extra)
    return out


# ============================ P1 — operating (Gate 0) =========================
class TestP1Operating:
    def _cand(self, **extra):
        c = {"id": "x", "name_local": "店", "name_display": "店",
             "sources": [{"url": "https://a.example", "lang": "zh"},
                         {"url": "https://b.example", "lang": "zh"}],
             "geocode": {"lat": 1.0, "lng": 2.0}}
        c.update(extra)
        return c

    def test_closed_permanently_rejected_before_geocode(self):
        # Acceptance: a candidate whose source reports closed -> rejected (Gate 0).
        _, status, note = verify_poi(self._cand(business_status="CLOSED_PERMANENTLY"),
                                     geocoded=True, in_claimed_region=True)
        assert status == "rejected"
        assert "clos" in note.lower() or "defunct" in note.lower()

    def test_missing_business_status_is_unverified_not_verified(self):
        # Acceptance NEW: the operating signal must be obtained/passed, not defaulted;
        # an absent signal must NEVER silently verify.
        _, status, note = verify_poi(self._cand(), geocoded=True, in_claimed_region=True)
        assert status == "unverified"
        assert "operating" in note.lower() or "business_status" in note.lower()

    def test_operational_signal_allows_verified(self):
        _, status, _ = verify_poi(self._cand(business_status="OPERATIONAL"),
                                  geocoded=True, in_claimed_region=True)
        assert status == "verified"

    def test_classify_candidate_operating_false_still_rejected(self):
        s, _ = classify_candidate(self._cand(), geocoded=True, in_claimed_region=True,
                                  operating=False)
        assert s == "rejected"


# ============================ P2 — name/address match ========================
class TestP2NameMatch:
    def test_name_matches_true_for_contained_core(self):
        from scripts.geocode import name_matches
        assert name_matches("日月潭文武廟", "文武廟, 日月潭, 南投縣, 台灣") is True

    def test_name_matches_false_for_renamed_neighbour(self):
        # P2(b): "星月大地" must NOT match the renamed nearby "星月驛站".
        from scripts.geocode import name_matches
        assert name_matches("星月大地", "星月驛站, 后里區, 台中市") is False

    def test_classify_candidate_name_mismatch_conflicting(self):
        c = {"id": "x", "name_local": "星月大地",
             "sources": [{"url": "https://a.example", "lang": "zh"},
                         {"url": "https://b.example", "lang": "zh"}]}
        s, note = classify_candidate(c, geocoded=True, in_claimed_region=True,
                                     name_match=False)
        assert s == "conflicting"
        assert "name" in note.lower() and "mismatch" in note.lower()

    def test_verify_poi_resolved_name_mismatch_conflicting(self):
        c = {"id": "x", "name_local": "星月大地", "name_display": "星月大地",
             "business_status": "OPERATIONAL",
             "sources": [{"url": "https://a.example", "lang": "zh"},
                         {"url": "https://b.example", "lang": "zh"}],
             "geocode": {"lat": 1.0, "lng": 2.0}}
        _, status, note = verify_poi(c, geocoded=True, in_claimed_region=True,
                                     resolved_name="星月驛站, 后里區")
        assert status == "conflicting"
        assert "mismatch" in note.lower()


# ============================ P3 — CJK geocode resilience =====================
class TestP3GeocodeResilience:
    LANDMARKS = [
        ("日月潭文武廟", "Wenwu Temple"),
        ("日月潭纜車", "Sun Moon Lake Ropeway"),
        ("九族文化村", "Formosan Aboriginal Culture Village"),
        ("向山遊客中心", "Xiangshan Visitor Center"),
        ("水社碼頭", "Shuishe Pier"),
    ]

    def test_landmarks_resolve_first_pass(self, monkeypatch):
        """Street-slot structured query AND the current '<name> <district> <country>'
        free-text both MISS for these POIs; only the bare core name or the roman name
        resolves. ≥90% must resolve on the first resolve_place call."""
        import scripts.geocode as g
        bare = {n for n, _ in self.LANDMARKS}
        romans = {r for _, r in self.LANDMARKS}

        def fake_structured(name, city=None, country=None, timeout=10):
            return None  # street-slot misses for non-address POIs

        def fake_geocode(query, timeout=10):
            if query in bare or query in romans:
                return g.GeocodeResult(23.8, 120.9, f"{query} result")
            return None  # the combined "<name> <district> <country>" query misses

        monkeypatch.setattr(g, "geocode_structured", fake_structured)
        monkeypatch.setattr(g, "geocode", fake_geocode)

        resolved = sum(
            1 for name, roman in self.LANDMARKS
            if resolve_place(name, district="日月潭", country="Taiwan",
                             name_roman=roman)[0] is not None
        )
        assert resolved / len(self.LANDMARKS) >= 0.9

    def test_bare_core_name_attempt_when_combined_misses(self, monkeypatch):
        """Even without name_roman, a plain free-text core-name attempt must be made."""
        import scripts.geocode as g

        def fake_structured(name, city=None, country=None, timeout=10):
            return None

        def fake_geocode(query, timeout=10):
            if query == "九族文化村":  # only the bare core name resolves
                return g.GeocodeResult(23.8, 120.9, "九族文化村 result")
            return None

        monkeypatch.setattr(g, "geocode_structured", fake_structured)
        monkeypatch.setattr(g, "geocode", fake_geocode)
        res, _ = resolve_place("九族文化村", district="日月潭", country="Taiwan")
        assert res is not None


# ============================ P4 — lodging in gate/render pool ================
class TestP4LodgingPool:
    def _acc(self):
        return {"stops": [{"district": "日月潭", "nights": 2, "chosen": "hotel-a",
            "candidates": [{
                "id": "hotel-a", "name_local": "力麗溫德姆", "name_display": "力麗溫德姆",
                "verify_status": "verified", "geocode": {"lat": 1.0, "lng": 2.0},
                "facilities": [],
                "sources": [{"url": "https://x.example", "lang": "zh"},
                            {"url": "https://y.example", "lang": "zh"}]}]}]}

    def test_chosen_lodging_pois_helper(self):
        from scripts.gate import chosen_lodging_pois
        ids = {p["id"] for p in chosen_lodging_pois(self._acc())}
        assert "hotel-a" in ids

    def test_gate_passes_with_lodging_only_in_accommodations(self):
        # Acceptance: gate passes when day.lodging is an accommodations chosen id,
        # with only verified-pois + accommodations as inputs (no manual merge).
        r = run_gate([_poi("rest1")], _itin([_meal("rest1")], lodging="hotel-a"),
                     accommodations=self._acc(), advisory={"items": []})
        assert r["status"] == "pass", r["failures"]
        assert not any("unknown POI 'hotel-a'" in f for f in r["failures"])

    def test_html_renders_chosen_lodging_from_accommodations(self):
        from scripts.render.html_page import render_html_page
        from scripts.gate import chosen_lodging_pois
        poi_map = {p["id"]: p for p in [_poi("rest1")]}
        poi_map.update({p["id"]: p for p in chosen_lodging_pois(self._acc())})
        html = render_html_page(_itin([_meal("rest1")], lodging="hotel-a"), poi_map)
        assert "力麗溫德姆" in html  # lodging rendered, not the "—" blank


# ============================ P5 — must_do thematic coverage ==================
class TestP5MustDo:
    def test_thematic_must_do_covered_passes(self):
        r = run_gate([_poi("ferry")],
                     _itin([_meal("ferry")], must_do_coverage={"日月潭遊湖賞景": ["ferry"]}),
                     must_do=["日月潭遊湖賞景"], advisory={"items": []})
        assert r["status"] == "pass", r["failures"]
        assert {"name": "must_do_covered", "passed": True} in r["checks"]

    def test_thematic_must_do_uncovered_fails(self):
        r = run_gate([_poi("ferry")],
                     _itin([_meal("ferry")], must_do_coverage={}),
                     must_do=["日月潭遊湖賞景"], advisory={"items": []})
        assert r["status"] == "fail"
        assert any("日月潭遊湖賞景" in f and "must_do" in f.lower() for f in r["failures"])
        assert {"name": "must_do_covered", "passed": False} in r["checks"]

    def test_id_based_must_do_still_works(self):
        # Back-compat: a scheduled POI id self-covers.
        r = run_gate([_poi("a")], _itin([_meal("a")]), must_do=["a"],
                     advisory={"items": []})
        assert {"name": "must_do_covered", "passed": True} in r["checks"]


# ============================ P6 — rooms multiply ============================
class TestP6Cost:
    def test_lodging_line_amount_per_night_times_rooms(self):
        from scripts.cost import lodging_line_amount
        # per_room 3000 × 2 rooms × 2 nights
        assert lodging_line_amount({"amount": 3000, "basis": "per_night"},
                                   nights=2, rooms=2) == 12000

    def test_lodging_line_amount_total_times_rooms(self):
        from scripts.cost import lodging_line_amount
        # per_room total 5000 × 2 rooms
        assert lodging_line_amount({"amount": 5000, "basis": "total"},
                                   nights=3, rooms=2) == 10000

    def test_lodging_line_amount_default_one_room(self):
        from scripts.cost import lodging_line_amount
        assert lodging_line_amount({"amount": 3000, "basis": "per_night"},
                                   nights=2) == 6000


# ============================ P7 — distributable terminal =====================
class TestP7Distributable:
    CLEAN = "### Day 1\n\nsome text without prices\n"

    def _photo(self, src):
        return {"id": "p1", "name_local": "x", "name_display": "x",
                "photo": {"data": "data:image/png;base64,iVB"},
                "photo_attribution": {"author": "A", "license": "CC0",
                                      "source_url": "https://a.example"},
                "photo_source": src}

    def test_google_photo_is_terminal_nondistributable_not_fail(self):
        # Acceptance: a personal (google-photo) deliverable reaches a clean terminal
        # "complete, non-distributable" state — NOT a fail that re-export loops on.
        r = run_export_gate(self.CLEAN, [self._photo("google")])
        assert r["status"] == "pass", r["failures"]
        assert r["distributable"] is False
        assert {"name": "no_nondistributable_photo_source", "passed": False} in r["checks"]

    def test_wikimedia_photo_is_distributable_pass(self):
        r = run_export_gate(self.CLEAN, [self._photo("wikimedia")])
        assert r["status"] == "pass", r["failures"]
        assert r["distributable"] is True

    def test_real_render_defect_still_fails_and_loops(self):
        dirty = self.CLEAN + "\nprice is $5 today\n"  # naked $ = genuine render defect
        r = run_export_gate(dirty, [self._photo("google")])
        assert r["status"] == "fail"
        assert r["distributable"] is False

    def test_html_google_photo_terminal_nondistributable(self):
        html = ('<div class="day-card"></div>'
                '<img src="data:image/png;base64,iVB">')
        r = run_html_gate(html, [self._photo("google")], min_days=1)
        assert r["status"] == "pass", r["failures"]
        assert r["distributable"] is False


# ============================ P8 — media landed cross-check ===================
class TestP8MediaLanded:
    def test_media_present_but_zero_photos_fails(self):
        html = '<div class="day-card"></div>'  # 0 <img>
        r = run_html_gate(html, pois=[], min_days=1, media_count=2)
        assert r["status"] == "fail"
        assert any("media side-file" in f.lower() and "0 photo" in f.lower()
                   for f in r["failures"])

    def test_media_present_with_photos_passes(self):
        html = ('<div class="day-card"></div>'
                '<img src="data:image/png;base64,iVB">')
        r = run_html_gate(html, pois=[], min_days=1, media_count=2)
        assert r["status"] == "pass", r["failures"]

    def test_no_media_count_no_check(self):
        # Back-compat: callers that don't declare a side-file are not P8-checked.
        r = run_html_gate('<div class="day-card"></div>', pois=[], min_days=1)
        assert r["status"] == "pass", r["failures"]


# ============================ P9 — place_id canonical link ====================
class TestP9MapsPlaceId:
    def test_place_id_uses_query_place_id_refinement(self):
        url = maps_url({"name_local": "文武廟", "gmaps_place_id": "ChIJ_abc-123"})
        assert url.startswith("https://www.google.com/maps/search/?api=1&query=")
        assert "&query_place_id=ChIJ_abc-123" in url
        assert "/maps/place/" not in url

    def test_place_id_refines_pin_exact(self):
        url = maps_url({"name_local": "x", "gmaps_place_id": "P1",
                        "geocode": {"lat": 1.0, "lng": 2.0, "pin_exact": True}})
        assert url.startswith("https://www.google.com/maps/search/?api=1&query=")
        assert "1.0,2.0" in unquote(url)            # coord branch preserved
        assert url.endswith("&query_place_id=P1")

    def test_no_place_id_falls_back_to_name_search(self):
        url = maps_url({"name_local": "明洞", "district": "中區"})
        assert url.startswith("https://www.google.com/maps/search/?api=1&query=")
