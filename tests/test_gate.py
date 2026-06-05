# tests/test_gate.py
from scripts.gate import run_gate

def _poi(pid, geo=True, status="verified"):
    d = {"id": pid, "verify_status": status}
    if geo:
        d["geocode"] = {"lat": 1.0, "lng": 2.0}
    return d

def test_gate_pass_when_all_geocoded_and_days_have_meals():
    pois = [_poi("a"), _poi("b")]
    days = [{"date": "2026-05-24", "meals": ["a"]}, {"date": "2026-05-25", "meals": ["b"]}]
    report = run_gate(pois, days)
    assert report["status"] == "pass"
    assert report["failures"] == []

def test_gate_fail_when_poi_missing_geocode():
    pois = [_poi("a", geo=False)]
    days = [{"date": "2026-05-24", "meals": ["a"]}]
    report = run_gate(pois, days)
    assert report["status"] == "fail"
    assert any("geocode" in f for f in report["failures"])

def test_gate_fail_when_day_has_no_meal():
    pois = [_poi("a")]
    days = [{"date": "2026-05-24", "meals": []}]
    report = run_gate(pois, days)
    assert report["status"] == "fail"
    assert any("meal" in f.lower() for f in report["failures"])

def test_gate_ignores_non_verified_pois_for_geocode_check():
    # a rejected POI without geocode should not appear in itinerary days anyway;
    # gate only checks POIs referenced by days
    pois = [_poi("a"), _poi("b", geo=False, status="rejected")]
    days = [{"date": "2026-05-24", "meals": ["a"]}]
    report = run_gate(pois, days)
    assert report["status"] == "pass"

def test_gate_checks_activities_keys_too():
    pois = [{"id": "a", "verify_status": "verified", "geocode": {"lat": 1, "lng": 2}},
            {"id": "b", "verify_status": "verified"}]  # b lacks geocode
    days = [{"date": "2026-05-24", "meals": ["a"], "activities": ["b"]}]
    report = run_gate(pois, days)
    assert report["status"] == "fail"
    assert any("b" in f and "geocode" in f for f in report["failures"])

def test_gate_meal_check_still_requires_food():
    pois = [{"id": "a", "verify_status": "verified", "geocode": {"lat": 1, "lng": 2}}]
    days = [{"date": "2026-05-24", "activities": ["a"]}]  # no meals
    report = run_gate(pois, days)
    assert report["status"] == "fail"
    assert any("meal" in f.lower() for f in report["failures"])

def _accom(chosen, facilities):
    return {"stops": [{
        "district": "Tekapo", "nights": 2, "chosen": chosen,
        "candidates": [{"id": "godley", "facilities": facilities}],
    }]}

def test_gate_skips_accommodation_when_absent():
    # backward-compat: no accommodations arg -> only the original checks run
    r = run_gate([], [])
    assert all(c["name"] not in ("overnight_stops_have_lodging", "required_facilities_met")
               for c in r["checks"])

def test_gate_fails_stop_without_chosen_lodging():
    r = run_gate([], [], accommodations=_accom(None, []), facility_needs={"required": []})
    assert r["status"] == "fail"
    assert next(c["passed"] for c in r["checks"] if c["name"] == "overnight_stops_have_lodging") is False

def test_gate_fails_missing_required_facility():
    r = run_gate([], [], accommodations=_accom("godley", ["wifi"]),
                 facility_needs={"required": ["parking"]})
    assert r["status"] == "fail"
    assert next(c["passed"] for c in r["checks"] if c["name"] == "required_facilities_met") is False

def test_gate_passes_lodging_with_required_facility():
    r = run_gate([], [], accommodations=_accom("godley", ["parking", "wifi"]),
                 facility_needs={"required": ["parking"]})
    assert next(c["passed"] for c in r["checks"] if c["name"] == "overnight_stops_have_lodging") is True
    assert next(c["passed"] for c in r["checks"] if c["name"] == "required_facilities_met") is True
