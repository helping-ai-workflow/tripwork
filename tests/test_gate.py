# tests/test_gate.py
from scripts.gate import run_gate

def _poi(pid, geo=True, status="verified", closed_days=None):
    d = {"id": pid, "verify_status": status}
    if geo:
        d["geocode"] = {"lat": 1.0, "lng": 2.0}
    if closed_days is not None:
        d["closed_days"] = closed_days
    return d

def _itin(rows, date="2026-06-12", lodging=None, checklist=None):
    day = {"date": date, "label": "Day 1", "rows": rows}
    if lodging is not None:
        day["lodging"] = lodging
    itin = {"title": "t", "days": [day]}
    if checklist is not None:
        itin["checklist"] = checklist
    return itin

def _meal(pid): return {"time": "12:00", "slot": "meal", "poi_id": pid, "text": "lunch"}
def _act(pid):  return {"time": "14:00", "slot": "activity", "poi_id": pid, "text": "see"}

def test_gate_pass_when_all_verified_geocoded_with_meal():
    r = run_gate([_poi("a")], _itin([_meal("a")]))
    assert r["status"] == "pass"
    assert r["failures"] == []

def test_gate_fail_referenced_conflicting_poi_with_geocode():   # TW-002 core
    pois = [{"id": "x", "verify_status": "conflicting", "geocode": {"lat": 37.5, "lng": 127.0}}]
    r = run_gate(pois, _itin([_meal("x")]))
    assert r["status"] == "fail"
    assert any("x" in f and "conflicting" in f for f in r["failures"])
    assert {"name": "referenced_pois_verified", "passed": False} in r["checks"]

def test_gate_pass_marks_verified_check_true():
    r = run_gate([_poi("a")], _itin([_meal("a")]))
    assert {"name": "referenced_pois_verified", "passed": True} in r["checks"]

def test_gate_fail_geocode_null():   # TW-002 same-point: None must fail
    pois = [{"id": "a", "verify_status": "verified", "geocode": None}]
    r = run_gate(pois, _itin([_meal("a")]))
    assert r["status"] == "fail"
    assert any("geocode" in f for f in r["failures"])

def test_gate_fail_unknown_poi():
    r = run_gate([], _itin([_meal("ghost")]))
    assert r["status"] == "fail"
    assert any("ghost" in f for f in r["failures"])

def test_gate_fail_day_without_meal():
    r = run_gate([_poi("a")], _itin([_act("a")]))
    assert r["status"] == "fail"
    assert any("meal" in f.lower() for f in r["failures"])

def test_gate_fail_closed_day_violation():   # TW-018  (2026-06-12 is a Friday)
    cal = {"holidays": []}
    pois = [_poi("a", closed_days=["friday"])]
    r = run_gate(pois, _itin([_meal("a")], date="2026-06-12"), calendar=cal)
    assert r["status"] == "fail"
    assert any("a" in f and "closed" in f for f in r["failures"])
    assert {"name": "no_closed_day_violation", "passed": False} in r["checks"]

def test_gate_closed_day_check_absent_without_calendar():
    r = run_gate([_poi("a")], _itin([_meal("a")]))
    assert all(c["name"] != "no_closed_day_violation" for c in r["checks"])

def test_gate_fail_must_do_not_covered():   # TW-038
    r = run_gate([_poi("a"), _poi("b")], _itin([_meal("a")]), must_do=["b"])
    assert r["status"] == "fail"
    assert any("b" in f and "must_do" in f.lower() for f in r["failures"])
    assert {"name": "must_do_covered", "passed": False} in r["checks"]

def test_gate_pass_must_do_covered():
    r = run_gate([_poi("a")], _itin([_meal("a")]), must_do=["a"])
    assert {"name": "must_do_covered", "passed": True} in r["checks"]

def test_gate_lodging_poi_is_referenced():
    pois = [_poi("a"),
            {"id": "h", "verify_status": "unverified",
             "geocode": {"lat": 1, "lng": 2}, "status_reason": "x"}]
    r = run_gate(pois, _itin([_meal("a")], lodging="h"))
    assert r["status"] == "fail"
    assert any("h" in f for f in r["failures"])

def test_gate_fail_banned_advisory_not_surfaced():   # TW-034 (deviation: surface-check)
    adv = {"items": [{"topic": "spare lithium battery", "rule": "carry-on only",
                      "effective_date": "2026-01-01", "risk": "banned",
                      "sources": [{"url": "https://airline", "official": True}]}]}
    r = run_gate([_poi("a")], _itin([_meal("a")]), advisory=adv)
    assert r["status"] == "fail"
    assert any("spare lithium battery" in f and "surface" in f.lower() for f in r["failures"])
    assert {"name": "advisory_items_surfaced", "passed": False} in r["checks"]

def test_gate_pass_banned_advisory_surfaced_in_checklist():   # TW-034
    adv = {"items": [{"topic": "spare lithium battery", "rule": "carry-on only",
                      "effective_date": "2026-01-01", "risk": "banned",
                      "sources": [{"url": "https://airline", "official": True}]}]}
    itin = _itin([_meal("a")], checklist=["spare lithium battery: carry-on only"])
    r = run_gate([_poi("a")], itin, advisory=adv)
    assert {"name": "advisory_items_surfaced", "passed": True} in r["checks"]

def test_gate_info_advisory_need_not_surface():
    adv = {"items": [{"topic": "tap water drinkable", "rule": "ok", "effective_date": "x",
                      "risk": "info", "sources": [{"url": "https://gov", "official": True}]}]}
    r = run_gate([_poi("a")], _itin([_meal("a")]), advisory=adv)
    assert {"name": "advisory_items_surfaced", "passed": True} in r["checks"]

def test_gate_invariant_pass_implies_all_checks_passed():
    r = run_gate([_poi("a")], _itin([_meal("a")]))
    if r["status"] == "pass":
        assert all(c["passed"] for c in r["checks"])
        assert r["failures"] == []

# --- accommodation checks (migrated to itinerary 2nd arg) ---

def _accom(chosen, facilities):
    return {"stops": [{"district": "Tekapo", "nights": 2, "chosen": chosen,
                       "candidates": [{"id": "godley", "facilities": facilities}]}]}

def test_gate_skips_accommodation_when_absent():
    r = run_gate([_poi("a")], _itin([_meal("a")]))
    assert all(c["name"] not in ("overnight_stops_have_lodging", "required_facilities_met")
               for c in r["checks"])

def test_gate_fails_stop_without_chosen_lodging():
    r = run_gate([_poi("a")], _itin([_meal("a")]),
                 accommodations=_accom(None, []), facility_needs={"required": []})
    assert r["status"] == "fail"
    assert next(c["passed"] for c in r["checks"] if c["name"] == "overnight_stops_have_lodging") is False

def test_gate_fails_missing_required_facility():
    r = run_gate([_poi("a")], _itin([_meal("a")]),
                 accommodations=_accom("godley", ["wifi"]), facility_needs={"required": ["parking"]})
    assert r["status"] == "fail"
    assert next(c["passed"] for c in r["checks"] if c["name"] == "required_facilities_met") is False

def test_gate_passes_lodging_with_required_facility():
    r = run_gate([_poi("a")], _itin([_meal("a")]),
                 accommodations=_accom("godley", ["parking", "wifi"]), facility_needs={"required": ["parking"]})
    assert next(c["passed"] for c in r["checks"] if c["name"] == "overnight_stops_have_lodging") is True
    assert next(c["passed"] for c in r["checks"] if c["name"] == "required_facilities_met") is True
