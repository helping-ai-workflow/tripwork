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
    r = run_gate([_poi("a")], _itin([_meal("a")]), advisory={"items": []})
    assert r["status"] == "pass"
    assert r["failures"] == []

def test_gate_fail_referenced_conflicting_poi_with_geocode():   # TW-002 core
    pois = [{"id": "x", "verify_status": "conflicting", "geocode": {"lat": 37.5, "lng": 127.0}}]
    r = run_gate(pois, _itin([_meal("x")]))
    assert r["status"] == "fail"
    assert any("x" in f and "conflicting" in f for f in r["failures"])
    assert {"name": "referenced_pois_verified", "passed": False} in r["checks"]

def test_gate_pass_marks_verified_check_true():
    r = run_gate([_poi("a")], _itin([_meal("a")]), advisory={"items": []})
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
    r = run_gate([_poi("a")], _itin([_meal("a")]), advisory={"items": []})
    assert all(c["name"] != "no_closed_day_violation" for c in r["checks"])

def test_gate_fail_must_do_not_covered():   # TW-038
    r = run_gate([_poi("a"), _poi("b")], _itin([_meal("a")]), must_do=["b"])
    assert r["status"] == "fail"
    assert any("b" in f and "must_do" in f.lower() for f in r["failures"])
    assert {"name": "must_do_covered", "passed": False} in r["checks"]

def test_gate_pass_must_do_covered():
    r = run_gate([_poi("a")], _itin([_meal("a")]), must_do=["a"], advisory={"items": []})
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
    r = run_gate([_poi("a")], _itin([_meal("a")]), advisory={"items": []})
    if r["status"] == "pass":
        assert all(c["passed"] for c in r["checks"])
        assert r["failures"] == []

# --- accommodation checks (migrated to itinerary 2nd arg) ---

def _accom(chosen, facilities):
    return {"stops": [{"district": "Tekapo", "nights": 2, "chosen": chosen,
                       "candidates": [{"id": "godley", "facilities": facilities}]}]}

def test_gate_skips_accommodation_when_absent():
    r = run_gate([_poi("a")], _itin([_meal("a")]), advisory={"items": []})
    assert all(c["name"] not in ("overnight_stops_have_lodging", "required_facilities_met")
               for c in r["checks"])

def test_gate_fails_stop_without_chosen_lodging():
    r = run_gate([_poi("a")], _itin([_meal("a")]), advisory={"items": []},
                 accommodations=_accom(None, []), facility_needs={"required": []})
    assert r["status"] == "fail"
    assert next(c["passed"] for c in r["checks"] if c["name"] == "overnight_stops_have_lodging") is False

def test_gate_fails_missing_required_facility():
    r = run_gate([_poi("a")], _itin([_meal("a")]), advisory={"items": []},
                 accommodations=_accom("godley", ["wifi"]), facility_needs={"required": ["parking"]})
    assert r["status"] == "fail"
    assert next(c["passed"] for c in r["checks"] if c["name"] == "required_facilities_met") is False

def test_gate_passes_lodging_with_required_facility():
    r = run_gate([_poi("a")], _itin([_meal("a")]), advisory={"items": []},
                 accommodations=_accom("godley", ["parking", "wifi"]), facility_needs={"required": ["parking"]})
    assert next(c["passed"] for c in r["checks"] if c["name"] == "overnight_stops_have_lodging") is True
    assert next(c["passed"] for c in r["checks"] if c["name"] == "required_facilities_met") is True


# --- overnight_days_have_lodging floor (always-on, independent of accommodations.yaml) ---

def _itin_multi(days_spec):
    """Build a multi-day itinerary from a list of (date, rows, lodging) tuples.
    lodging=None means field absent; lodging="" means field absent (same as None).
    Pass lodging=<str> to set the lodging field.
    """
    days = []
    for date, rows, lodging in days_spec:
        day = {"date": date, "label": f"Day {date}", "rows": rows}
        if lodging:
            day["lodging"] = lodging
        days.append(day)
    return {"title": "t", "days": days}


def test_floor_non_final_day_without_lodging_fails():
    """Non-final day with no lodging field and no slot:lodging row -> status fail."""
    pois = [_poi("a")]
    itin = _itin_multi([
        ("2026-06-12", [_meal("a")], None),   # non-final, no lodging
        ("2026-06-13", [_meal("a")], None),   # final day, no lodging needed
    ])
    r = run_gate(pois, itin)
    assert r["status"] == "fail"
    assert any("no resolved lodging" in f and "2026-06-12" in f for f in r["failures"])


def test_floor_non_final_day_with_lodging_field_passes():
    """Non-final day with lodging field set -> no 'no resolved lodging' failure."""
    pois = [_poi("a"), _poi("hotel1")]
    itin = _itin_multi([
        ("2026-06-12", [_meal("a")], "hotel1"),  # non-final, lodging field set
        ("2026-06-13", [_meal("a")], None),       # final day
    ])
    r = run_gate(pois, itin)
    assert not any("no resolved lodging" in f for f in r["failures"])


def test_floor_non_final_day_with_slot_lodging_row_passes():
    """Non-final day with a row slot=='lodging' -> no 'no resolved lodging' failure."""
    pois = [_poi("a")]
    lodging_row = {"time": "22:00", "slot": "lodging", "text": "Check in"}
    itin = _itin_multi([
        ("2026-06-12", [_meal("a"), lodging_row], None),  # non-final, slot:lodging row
        ("2026-06-13", [_meal("a")], None),               # final day
    ])
    r = run_gate(pois, itin)
    assert not any("no resolved lodging" in f for f in r["failures"])


def test_floor_final_day_without_lodging_no_failure():
    """Final day has no lodging -> date NOT in any failure (departure day, no overnight)."""
    pois = [_poi("a"), _poi("hotel1")]
    itin = _itin_multi([
        ("2026-06-12", [_meal("a")], "hotel1"),  # non-final, has lodging
        ("2026-06-13", [_meal("a")], None),       # final, no lodging -> OK
    ])
    r = run_gate(pois, itin)
    assert not any("2026-06-13" in f and "no resolved lodging" in f for f in r["failures"])


def test_floor_single_day_trip_passes():
    """Single-day trip -> no overnight days -> vacuous pass (no lodging floor fires)."""
    pois = [_poi("a")]
    itin = _itin_multi([
        ("2026-06-12", [_meal("a")], None),  # only day = final day, no overnight
    ])
    r = run_gate(pois, itin)
    assert not any("no resolved lodging" in f for f in r["failures"])


def test_floor_check_entry_always_present():
    """Gate report always contains a check named 'overnight_days_have_lodging'."""
    pois = [_poi("a")]
    itin = _itin_multi([
        ("2026-06-12", [_meal("a")], None),
        ("2026-06-13", [_meal("a")], None),
    ])
    r = run_gate(pois, itin)
    names = [c["name"] for c in r["checks"]]
    assert "overnight_days_have_lodging" in names


# --- advisory_present floor (D2-class: absent advisory FAILS the safety gate) ---

def test_gate_fail_advisory_absent():
    """advisory omitted (None) -> status fail with an 'advisory absent' failure."""
    r = run_gate([_poi("a")], _itin([_meal("a")]))  # advisory defaults to None
    assert r["status"] == "fail"
    assert any("advisory absent" in f for f in r["failures"])


def test_gate_advisory_present_check_always_in_report_when_absent():
    """The 'advisory_present' check entry is present even when advisory is absent."""
    r = run_gate([_poi("a")], _itin([_meal("a")]))
    assert {"name": "advisory_present", "passed": False} in r["checks"]


def test_gate_advisory_present_check_always_in_report_when_present():
    """The 'advisory_present' check entry is present (passed) when advisory is given."""
    r = run_gate([_poi("a")], _itin([_meal("a")]), advisory={"items": []})
    assert {"name": "advisory_present", "passed": True} in r["checks"]


def test_gate_pass_with_empty_advisory():
    """advisory={"items": []} -> no 'advisory absent' failure; otherwise-valid plan passes."""
    r = run_gate([_poi("a")], _itin([_meal("a")]), advisory={"items": []})
    assert not any("advisory absent" in f for f in r["failures"])
    assert r["status"] == "pass"
    assert r["failures"] == []


def test_gate_banned_item_not_surfaced_still_fails_with_present_advisory():
    """advisory present with an unsurfaced banned item still fails advisory_items_surfaced
    (existing per-item surfacing behaviour intact; advisory_present passes)."""
    adv = {"items": [{"topic": "spare lithium battery", "rule": "carry-on only",
                      "effective_date": "2026-01-01", "risk": "banned",
                      "sources": [{"url": "https://airline", "official": True}]}]}
    r = run_gate([_poi("a")], _itin([_meal("a")]), advisory=adv)
    assert r["status"] == "fail"
    assert any("spare lithium battery" in f and "surface" in f.lower() for f in r["failures"])
    assert {"name": "advisory_items_surfaced", "passed": False} in r["checks"]
    assert {"name": "advisory_present", "passed": True} in r["checks"]
