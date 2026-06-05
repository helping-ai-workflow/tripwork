"""E2E closure for v0.6.0 accommodation (spec §7 / CLAUDE.md step-7 fixture).

A 6-town NZ self-drive: every overnight stop ends with a verified chosen lodging,
parking (required) is met, the laundry coverage advisory is computed, and the gate
passes. Reproduces the field run that found D1/D7.
"""
from scripts.gate import run_gate
from scripts.facilities import coverage_gaps, reception_ok
from scripts.verify import classify_candidate

FACILITY_NEEDS = {"required": ["parking"],
                  "periodic": [{"facility": "laundry", "max_gap_nights": 2}]}

def _lodge(_id, facilities):
    return {"id": _id, "facilities": facilities}

# CHC 1✓ Tekapo 2✗ Wanaka 2✓ TeAnau 2✗ Queenstown 3✓  (laundry coverage)
ACCOM = {"stops": [
    {"district": "Christchurch", "nights": 1, "chosen": "sudima",
     "candidates": [_lodge("sudima", ["parking", "laundry"])]},
    {"district": "Tekapo", "nights": 2, "chosen": "godley",
     "candidates": [_lodge("godley", ["parking"])]},
    {"district": "Wanaka", "nights": 2, "chosen": "edgewater",
     "candidates": [_lodge("edgewater", ["parking", "laundry"])]},
    {"district": "Te Anau", "nights": 2, "chosen": "distinction",
     "candidates": [_lodge("distinction", ["parking"])]},
    {"district": "Queenstown", "nights": 3, "chosen": "novotel",
     "candidates": [_lodge("novotel", ["parking", "laundry"])]},
]}

def test_every_stop_has_verified_lodging_and_parking():
    r = run_gate([], [], accommodations=ACCOM, facility_needs=FACILITY_NEEDS)
    assert r["status"] == "pass", r["failures"]
    assert next(c["passed"] for c in r["checks"] if c["name"] == "overnight_stops_have_lodging")
    assert next(c["passed"] for c in r["checks"] if c["name"] == "required_facilities_met")

def test_laundry_coverage_within_cadence():
    stops = [{"nights": s["nights"],
              "has_facility": "laundry" in s["candidates"][0]["facilities"]}
             for s in ACCOM["stops"]]
    assert coverage_gaps(stops, max_gap_nights=2) == []  # advisory clean

def test_small_hotel_centroid_fallback_stays_verified():
    # The Godley Hotel can't geocode on Nominatim; cluster-centroid fallback means
    # geocoded=True, in-region=True -> verified (D7 enables D1).
    cand = {"id": "godley", "sources": [{"url": "a", "lang": "en"}, {"url": "b", "lang": "en"}]}
    status, _ = classify_candidate(cand, geocoded=True, in_claimed_region=True, local_lang="en")
    assert status == "verified"

def test_late_arrival_without_late_checkin_is_blocked():
    assert reception_ok("21:30", "20:00", late_checkin=False) is False
    assert reception_ok("21:30", "20:00", late_checkin=True) is True

def test_missing_parking_fails_the_gate():
    bad = {"stops": [{"district": "X", "nights": 1, "chosen": "h",
                      "candidates": [_lodge("h", ["wifi"])]}]}
    r = run_gate([], [], accommodations=bad, facility_needs=FACILITY_NEEDS)
    assert r["status"] == "fail"
    assert next(c["passed"] for c in r["checks"] if c["name"] == "required_facilities_met") is False
