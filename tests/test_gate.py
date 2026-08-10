# tests/test_gate.py
import datetime

from scripts.gate import run_gate
from tests.mech_fixtures import rederive_kwargs

# v0.33.0 (R4): explicit close + last_order + last_entry so a POI opted into the
# closing-buffer check (via _poi(..., hours=_HOURS)) is re-derivable for a row
# scheduled by either _meal (12:00) or _act (14:00). Not no_fixed_close: several
# call sites name their POI "rest1" (a restaurant) and a generic gate fixture
# should not model "genuinely no closing time" for something meal-shaped.
_HOURS = {"close": "22:00", "last_order": "21:30", "last_entry": "21:30",
         "typical_visit_mins": 60, "as_of": "2026-01-01"}


def _poi(pid, geo=True, status="verified", closed_days=None, hours=None):
    """v0.34.0 (TW-070): run_gate now threads `pois` into rederive_pois, so
    every call site in this file re-derives verify_status, not just the ones
    that opted into **rederive_kwargs(). No call site here ever overrides
    `status` away from the default "verified", so this fixture carries a
    sourced business_status + geocode_source + resolved_name by default —
    the minimum recorded-input set verify_poi needs to re-derive 'verified'
    for a generic, name-less single-letter test id — instead of every POI
    in this file landing in the 'superseded' bucket the moment it is
    examined.

    as_of is computed at CALL time, never a literal (the same trap Task 2's
    two hardcoded-as_of tests hit): OPERATING_MAX_AGE_DAYS is 90, so a fixed
    date would flip every 'verified' in this file to a stale-signal mismatch
    90 days after this file was edited, for a reason unrelated to whatever
    the test is actually exercising.

    resolved_name="NO_RESULT" is the real sentinel scripts/source_verify_run.py
    writes when the geocoder ran and returned no display_name — used here
    (rather than a hand-typed venue name) because these single-letter ids
    ("a", "b", "hotel1", ...) have no name_local/name_display to match
    against; NO_RESULT makes Gate 2b's name-match "not disputed" without
    inventing a name this fixture was never given.
    """
    d = {"id": pid, "verify_status": status}
    if geo:
        d["geocode"] = {"lat": 1.0, "lng": 2.0, "geocode_source": "nominatim"}
    d["business_status"] = {"status": "OPERATIONAL",
                            "source_url": "https://source.example/poi",
                            "as_of": datetime.date.today().isoformat()}
    d["resolved_name"] = "NO_RESULT"
    d["sources"] = [{"url": "https://a.example/poi", "lang": "zh"},
                    {"url": "https://b.example/poi", "lang": "en"}]
    if closed_days is not None:
        d["closed_days"] = closed_days
    if hours is not None:
        d["hours"] = hours
    return d

def _itin(rows, date="2026-06-12", lodging=None, checklist=None):
    day = {"date": date, "label": "Day 1", "rows": rows}
    if lodging is not None:
        day["lodging"] = lodging
    itin = {"title": "t", "days": [day]}
    if checklist is not None:
        itin["checklist"] = checklist
    return itin

def _meal(pid, closing_status=None):
    row = {"time": "12:00", "slot": "meal", "poi_id": pid, "text": "lunch"}
    if closing_status is not None:
        row["closing_status"] = closing_status
    return row

def _act(pid, closing_status=None):
    row = {"time": "14:00", "slot": "activity", "poi_id": pid, "text": "see"}
    if closing_status is not None:
        row["closing_status"] = closing_status
    return row

def test_gate_pass_when_all_verified_geocoded_with_meal():
    r = run_gate([_poi("a", hours=_HOURS)], _itin([_meal("a", closing_status="ok")]),
                 advisory={"items": []}, **rederive_kwargs())
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

# --- canonical content hygiene (jargon + kana-gloss): the PRIMARY guard that protects
#     every renderer (md / html / line-short / notion-via-md) at the source (0.20.0) ---

def _visit(pid, text): return {"time": "14:00", "slot": "visit", "poi_id": pid, "text": text}

def test_gate_fails_on_leaked_poi_id_in_row_text():
    pois = [_poi("hak-goryokaku")]
    itin = _itin([_meal("hak-goryokaku"), _visit("hak-goryokaku", "夜景(hak-goryokaku)好看")])
    r = run_gate(pois, itin, advisory={"items": []})
    assert r["status"] == "fail"
    assert {"name": "no_internal_jargon", "passed": False} in r["checks"]
    assert any("hak-goryokaku" in f and "leaked" in f for f in r["failures"])

def test_gate_fails_on_must_do_in_checklist():
    itin = _itin([_meal("a")], checklist=["訂 蟹会席 must_do"])
    r = run_gate([_poi("a")], itin, advisory={"items": []})
    assert r["status"] == "fail"
    assert {"name": "no_internal_jargon", "passed": False} in r["checks"]
    assert any("must_do" in f for f in r["failures"])

def test_gate_fails_on_ungloss_kana_in_row_text():
    itin = _itin([_meal("a"), _visit("a", "ジンギスカン 好吃")])
    r = run_gate([_poi("a")], itin, advisory={"items": []})
    assert r["status"] == "fail"
    assert {"name": "japanese_glossed", "passed": False} in r["checks"]
    assert any("gloss" in f for f in r["failures"])

def test_gate_passes_glossed_kana_and_clean_text():
    itin = _itin([_meal("a"), _visit("a", "ジンギスカン（成吉思汗）好吃")], checklist=["護照"])
    r = run_gate([_poi("a")], itin, advisory={"items": []})
    assert {"name": "no_internal_jargon", "passed": True} in r["checks"]
    assert {"name": "japanese_glossed", "passed": True} in r["checks"]

def test_gate_jargon_no_false_positive_on_romaji_paren():
    pois = [_poi("hak-goryokaku")]
    itin = _itin([_meal("hak-goryokaku"), _visit("hak-goryokaku", "烤肉(grilled-lamb)讚")])
    r = run_gate(pois, itin, advisory={"items": []})
    assert {"name": "no_internal_jargon", "passed": True} in r["checks"]

# canonical hygiene must scan EVERY authored free-text field a renderer surfaces — title,
# day label, and move endpoints (from/to) — not only row text/checklist. line-short renders
# title + label verbatim and has no gate of its own, so a leak there would otherwise ship.

def test_gate_fails_on_jargon_in_title():
    itin = {"title": "北海道 must_do 行程",
            "days": [{"date": "2026-06-12", "label": "D1", "rows": [_meal("a")]}]}
    r = run_gate([_poi("a")], itin, advisory={"items": []})
    assert {"name": "no_internal_jargon", "passed": False} in r["checks"]

def test_gate_fails_on_kana_in_day_label():
    itin = _itin([_meal("a")])
    itin["days"][0]["label"] = "D1 すすきの"          # ungloss kana day header → line-short banner
    r = run_gate([_poi("a")], itin, advisory={"items": []})
    assert {"name": "japanese_glossed", "passed": False} in r["checks"]

def test_gate_fails_on_jargon_in_day_label():
    itin = _itin([_meal("a")])
    itin["days"][0]["label"] = "D1 (hak-x)"
    r = run_gate([_poi("a"), _poi("hak-x")], itin, advisory={"items": []})
    assert {"name": "no_internal_jargon", "passed": False} in r["checks"]

def test_gate_fails_on_kana_in_move_endpoint():
    rows = [_meal("a"), {"slot": "move", "text": "移動", "from": "すすきの", "to": "小樽"}]
    r = run_gate([_poi("a")], _itin(rows), advisory={"items": []})
    assert {"name": "japanese_glossed", "passed": False} in r["checks"]

def test_gate_passes_clean_title_label_endpoints():
    rows = [_meal("a"), {"slot": "move", "text": "移動", "from": "すすきの（薄野）", "to": "小樽"}]
    itin = _itin(rows)
    itin["title"] = "北海道家庭遊"
    itin["days"][0]["label"] = "D1｜函館"
    r = run_gate([_poi("a")], itin, advisory={"items": []})
    assert {"name": "no_internal_jargon", "passed": True} in r["checks"]
    assert {"name": "japanese_glossed", "passed": True} in r["checks"]


def _gpoi(pid, name_display, name_zh=None):
    p = {"id": pid, "verify_status": "verified", "geocode": {"lat": 1.0, "lng": 2.0},
         "name_display": name_display}
    if name_zh is not None:
        p["name_zh"] = name_zh
    return p

def test_gate_fails_on_scheduled_kana_poi_without_gloss():   # 0.21.0 forward guard
    itin = _itin([{"time": "12:00", "slot": "meal", "poi_id": "k", "text": "午餐"}])
    r = run_gate([_gpoi("k", "だるま 本店")], itin, advisory={"items": []})
    assert r["status"] == "fail"
    assert {"name": "referenced_pois_glossed", "passed": False} in r["checks"]
    assert any("k" in f and "name_zh" in f for f in r["failures"])

def test_gate_passes_kana_poi_with_gloss():
    itin = _itin([{"time": "12:00", "slot": "meal", "poi_id": "k", "text": "午餐"}])
    r = run_gate([_gpoi("k", "だるま 本店", "達摩本店")], itin, advisory={"items": []})
    assert {"name": "referenced_pois_glossed", "passed": True} in r["checks"]

def test_gate_fails_on_empty_display_kana_local_without_gloss():   # review finding
    poi = {"id": "k", "verify_status": "verified", "geocode": {"lat": 1.0, "lng": 2.0},
           "name_display": "", "name_local": "すすきの"}   # renders bare kana via fallback
    itin = _itin([{"time": "12:00", "slot": "meal", "poi_id": "k", "text": "午餐"}])
    r = run_gate([poi], itin, advisory={"items": []})
    assert {"name": "referenced_pois_glossed", "passed": False} in r["checks"]

def test_gate_glossed_check_passes_han_name():
    itin = _itin([{"time": "12:00", "slot": "meal", "poi_id": "h", "text": "午餐"}])
    r = run_gate([_gpoi("h", "五稜郭")], itin, advisory={"items": []})   # Han-only → exempt
    assert {"name": "referenced_pois_glossed", "passed": True} in r["checks"]


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
    r = run_gate(pois, itin, advisory={"items": []})
    assert not any("no resolved lodging" in f for f in r["failures"])
    assert all("advisory absent" not in f for f in r["failures"])


def test_floor_non_final_day_with_slot_lodging_row_passes():
    """Non-final day with a row slot=='lodging' -> no 'no resolved lodging' failure."""
    pois = [_poi("a")]
    lodging_row = {"time": "22:00", "slot": "lodging", "text": "Check in"}
    itin = _itin_multi([
        ("2026-06-12", [_meal("a"), lodging_row], None),  # non-final, slot:lodging row
        ("2026-06-13", [_meal("a")], None),               # final day
    ])
    r = run_gate(pois, itin, advisory={"items": []})
    assert not any("no resolved lodging" in f for f in r["failures"])
    assert all("advisory absent" not in f for f in r["failures"])


def test_floor_final_day_without_lodging_no_failure():
    """Final day has no lodging -> date NOT in any failure (departure day, no overnight)."""
    pois = [_poi("a"), _poi("hotel1")]
    itin = _itin_multi([
        ("2026-06-12", [_meal("a")], "hotel1"),  # non-final, has lodging
        ("2026-06-13", [_meal("a")], None),       # final, no lodging -> OK
    ])
    r = run_gate(pois, itin, advisory={"items": []})
    assert not any("2026-06-13" in f and "no resolved lodging" in f for f in r["failures"])
    assert all("advisory absent" not in f for f in r["failures"])


def test_floor_single_day_trip_passes():
    """Single-day trip -> no overnight days -> vacuous pass (no lodging floor fires)."""
    pois = [_poi("a")]
    itin = _itin_multi([
        ("2026-06-12", [_meal("a")], None),  # only day = final day, no overnight
    ])
    r = run_gate(pois, itin, advisory={"items": []})
    assert not any("no resolved lodging" in f for f in r["failures"])
    assert all("advisory absent" not in f for f in r["failures"])


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
    r = run_gate([_poi("a", hours=_HOURS)], _itin([_meal("a", closing_status="ok")]),
                 advisory={"items": []}, **rederive_kwargs())
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

# --- v0.30.0: kana-named lodging gloss (product-gap closure) ---

def _kana_hotel_accom(name_zh=None):
    # geocode_source + resolved_name (I2, v0.33.0) + business_status (Task 6,
    # v0.34.0): so rederive_lodging re-derives h1 to the recorded 'verified'
    # instead of flagging it as a verdicts_rederivable / verdicts_rule_current
    # gap -- this fixture predates all three fields. as_of computed at call
    # time, never a literal (OPERATING_MAX_AGE_DAYS is 90).
    c = {"id": "h1", "name_local": "駅前ホテル", "name_display": "駅前ホテル",
         "verify_status": "verified",
         "geocode": {"lat": 1, "lng": 2, "geocode_source": "nominatim"},
         "resolved_name": "駅前ホテル",
         "business_status": {"status": "OPERATIONAL",
                             "source_url": "https://a.example",
                             "as_of": datetime.date.today().isoformat()},
         "facilities": [],
         "sources": [{"url": "https://a.example", "lang": "ja"},
                     {"url": "https://b.example", "lang": "zh"}]}
    if name_zh:
        c["name_zh"] = name_zh
    return {"stops": [{"district": "d", "nights": 1, "chosen": "h1",
                       "candidates": [c]}]}

def test_gate_kana_lodging_with_name_zh_passes():   # v0.30.0
    r = run_gate([_poi("a", hours=_HOURS)], _itin([_meal("a", closing_status="ok")], lodging="h1"),
                 advisory={"items": []},
                 facility_needs={"required": []},
                 **rederive_kwargs(accommodations=_kana_hotel_accom("車站前旅館")))
    assert not any("name_zh" in f for f in r["failures"])
    assert r["status"] == "pass"

def test_gate_kana_lodging_without_name_zh_fails():   # v0.30.0
    r = run_gate([_poi("a")], _itin([_meal("a")], lodging="h1"),
                 advisory={"items": []}, accommodations=_kana_hotel_accom(),
                 facility_needs={"required": []})
    assert r["status"] == "fail"
    assert any("h1" in f and "name_zh" in f for f in r["failures"])


# --- fix round 1, Important 2: the wiring seam (run_gate must SURFACE
#     verdict re-derivation, not just accept the kwargs). All 12 rederive.py
#     unit tests call run_rederivation directly; the 10 migrated call sites
#     only prove **rederive_kwargs() keeps a passing gate passing. Nothing
#     asserted that a re-derivation failure actually reaches run_gate's
#     output -- deleting `checks.extend(rd["checks"])` / `failures.extend(
#     rd["failures"])` in scripts/gate.py would leave the rest of the suite
#     green. This is the seam that most needs a test: the mechanism's
#     user-visible contract IS the gate report.

def test_gate_surfaces_rederivation_match_failure_in_report():
    """examined is 3, not 2 (pre-v0.34.0): _poi("a") now carries a sourced
    business_status (TW-070) and correctly re-derives 'verified', adding one
    more COMPARED record on the POI axis on top of the pre-existing
    legs-mismatch + cost-match pair -- one more true (matching) comparison,
    not a bug in this test."""
    legs = {"legs": [{"from": "三重", "to": "嘉義市", "mode": "drive",
                      "duration_mins": 400, "status": "ok"}]}
    r = run_gate([_poi("a")], _itin([_meal("a")]), advisory={"items": []},
                 legs=legs, routing={"clusters": [], "hops": [], "warnings": []},
                 cost={"currency": "TWD", "as_of": "2026-08-07", "total": 0,
                       "line_items": []},
                 trip_brief={"dates": {"start": "2026-08-29", "end": "2026-08-31"}})
    assert r["status"] == "fail"
    assert {"name": "verdicts_match", "passed": False, "examined": 3} in r["checks"]
    assert any("drive_too_long" in f and "三重" in f for f in r["failures"])


def test_gate_surfaces_rederivation_rederivable_failure_in_report():
    """Sibling of the match-axis guard above: a record with GAPS (not wrong,
    just unverifiable) must also surface as a gate-report FAILURE via
    verdicts_rederivable, never silently absorbed.

    examined is 4, not 3 (pre-v0.34.0): _poi("a") here deliberately carries no
    `hours` and _meal("a") no `closing_status`, so on top of the leg gap this
    row is now ALSO a genuine, separate rederivable gap (R4) -- one more true
    finding on the same axis. TW-070 adds a further +1: _poi("a")'s own
    sourced business_status now makes it a correctly-rederivable POI-axis
    record too (found, not missing), so it is counted here without adding a
    new failure of its own -- see verdicts_rule_current below."""
    legs = {"legs": [{"from": "嘉義", "to": "台南", "mode": "rail",
                      "duration_mins": 40, "status": "ok"}]}
    r = run_gate([_poi("a")], _itin([_meal("a")]), advisory={"items": []},
                 legs=legs, routing={"clusters": [], "hops": [], "warnings": []},
                 cost={"currency": "TWD", "as_of": "2026-08-07", "total": 0,
                       "line_items": []},
                 trip_brief={"dates": {"start": "2026-08-29", "end": "2026-08-31"}})
    assert r["status"] == "fail"
    assert {"name": "verdicts_rederivable", "passed": False, "examined": 4} in r["checks"]
    assert any("last_service_exempt" in f for f in r["failures"])
    assert any("closing_status is not re-derivable" in f for f in r["failures"])


# --- home_legs_rendered (TW-069 fix round 1, Important 1) ------------------
# The reviewer proved Step 5b's original test (render_day_table on a hand-built
# move row) was already green, unmodified, at a3e26f6 -- it proved nothing this
# task did. This is the real mechanism: a kind:home leg is checked (rederive_legs)
# and its fare is summed (cost-rollup), but neither proves it reached the reader.

def _home_leg(frm="三重", to="嘉義市", duration_mins=190):
    return {"legs": [{"from": frm, "to": to, "kind": "home", "mode": "drive",
                      "duration_mins": duration_mins, "status": "ok"}]}


def test_gate_home_leg_rendered_passes_when_referenced():
    move_row = {"slot": "move", "from": "三重", "to": "嘉義市", "text": "自駕南下",
                "leg_index": 0}
    itin = _itin([_meal("a", closing_status="ok"), move_row])
    r = run_gate([_poi("a", hours=_HOURS)], itin, advisory={"items": []},
                 **rederive_kwargs(legs=_home_leg()))
    assert r["status"] == "pass", r["failures"]
    assert next(c["passed"] for c in r["checks"] if c["name"] == "home_legs_rendered") is True
    assert not any("has no move row" in f for f in r["failures"])


def test_gate_home_leg_rendered_fails_when_unreferenced():
    itin = _itin([_meal("a")])   # no row carries leg_index -> the leg is unrendered
    r = run_gate([_poi("a")], itin, advisory={"items": []},
                 **rederive_kwargs(legs=_home_leg()))
    assert r["status"] == "fail"
    assert next(c["passed"] for c in r["checks"] if c["name"] == "home_legs_rendered") is False
    assert any("home leg 0 (三重->嘉義市) has no move row" in f for f in r["failures"])
    # the failure message must NOT contain 'legs[' (scripts/orchestration.py's
    # _ROUTES routes that marker to tripwork:inter-stop-legs -- the wrong
    # destination for a synthesis-side rendering gap).
    assert not any("legs[" in f for f in r["failures"])


def test_gate_home_leg_rendered_ignores_non_home_legs():
    """A kind:inter_stop (or absent-kind, default) leg is NOT subject to this
    check. Measured before specifying the fix: across the four schema-clean
    corpus trips, 6 legs, all kind-absent (defaulting to inter_stop) -- so this
    check fires on nothing at HEAD, zero fallout."""
    legs = {"legs": [{"from": "嘉義", "to": "台南", "mode": "rail",
                      "duration_mins": 40, "status": "ok"}]}
    itin = _itin([_meal("a")])
    r = run_gate([_poi("a")], itin, advisory={"items": []},
                 **rederive_kwargs(legs=legs))
    assert next(c["passed"] for c in r["checks"] if c["name"] == "home_legs_rendered") is True


def test_gate_home_leg_index_out_of_range_fails():
    itin = _itin([{"slot": "move", "text": "自駕", "leg_index": 5}])
    r = run_gate([], itin, advisory={"items": []},
                 **rederive_kwargs(legs={"legs": []}))
    assert r["status"] == "fail"
    assert next(c["passed"] for c in r["checks"] if c["name"] == "home_legs_rendered") is False
    assert any("leg_index 5 does not match any recorded leg" in f for f in r["failures"])


def test_gate_a_non_integer_leg_index_is_a_gate_failure_not_a_traceback():
    """Reviewer triage, fix now: `leg_index: "0"` (a string, the shape
    hand-authored YAML produces) used to raise TypeError out of `run_gate`.
    `scripts/gate.py::main` does not catch TypeError around run_gate, so the CLI
    died with a traceback instead of the documented exit 2 — and a gate that
    CRASHES on bad input is strictly worse than one that fails it, because the
    consumer gets no failure list at all.

    The schema forbids a non-integer, but `opt()` deliberately does not
    schema-validate (that is what lets the gate report a fixable failure instead
    of exiting 2 on a dirty trip), so the value reaches this code verbatim.
    """
    itin = _itin([{"slot": "move", "text": "自駕", "leg_index": "0"}])
    r = run_gate([], itin, advisory={"items": []},
                 **rederive_kwargs(legs=_home_leg()))
    assert r["status"] == "fail"
    assert next(c["passed"] for c in r["checks"] if c["name"] == "home_legs_rendered") is False
    assert any("leg_index is a str, not an integer" in f for f in r["failures"])
    # routes like every other unrendered-home-leg defect: synthesis wrote the row.
    from scripts.orchestration import route_gate_failures
    assert route_gate_failures(r["failures"]) == "tripwork:itinerary-synthesis"


def test_gate_a_malformed_leg_index_cannot_choose_its_own_route():
    """The failure string above is routed by SUBSTRING match
    (scripts/orchestration.py::_ROUTES), so interpolating the trip-authored
    value into it would let an itinerary pick the stage its own defect routes
    to. Reproduced before this was tightened: `leg_index: "legs.yaml absent"`
    routed to inter-stop-legs and `"cost.total"` to cost-rollup — both wrong,
    and both chosen by trip content rather than by the defect.

    Every one of these is a synthesis defect (synthesis wrote the row), so every
    one must route there regardless of what the row says."""
    from scripts.orchestration import route_gate_failures

    for hostile in ("legs.yaml absent", "cost.total", "routing hop ",
                    "accommodations.yaml absent", "AI-tone ",
                    "carries neither hours.close"):
        itin = _itin([{"slot": "move", "text": "自駕", "leg_index": hostile}])
        r = run_gate([], itin, advisory={"items": []},
                     **rederive_kwargs(legs=_home_leg()))
        assert route_gate_failures(r["failures"]) == "tripwork:itinerary-synthesis", hostile
        assert not any(hostile in f for f in r["failures"]), hostile


def test_gate_leg_index_with_no_legs_yaml_still_reports_the_dangling_reference():
    """Guard, GREEN at HEAD: docstring reconciliation (reviewer triage, fix
    now). The docstring said a
    `legs=None` means "no home-leg data to check either way", but the
    out-of-range loop still ran with n_legs == 0, so a row carrying a leg_index
    DID produce a failure. The behaviour is right — a row pointing at leg 0 of a
    file that is not there is a real dangling reference — so the docstring was
    corrected to match rather than the loop suppressed. This pins the behaviour
    the prose now describes.
    """
    itin = _itin([{"slot": "move", "text": "自駕", "leg_index": 0}])
    r = run_gate([], itin, advisory={"items": []},
                 **rederive_kwargs(legs=None))
    assert any("leg_index 0 does not match any recorded leg" in f
               for f in r["failures"])


def test_gate_home_legs_rendered_check_always_present():
    """always-on, per the fix spec: appears in checks even when legs is None."""
    r = run_gate([_poi("a")], _itin([_meal("a")]), advisory={"items": []})
    assert "home_legs_rendered" in [c["name"] for c in r["checks"]]


# --- verdicts_rule_current (POI axis, v0.34.0): the wiring seam --------------

def test_gate_surfaces_a_superseded_poi_verdict_in_its_report():
    """The wiring seam. Every rederive_pois test calls the function directly;
    deleting the `pois=pois` argument in gate.py would leave all of them green.
    The gate report IS the mechanism's user-visible contract.

    advisory={"items": []} is not decoration: without it run_gate fails for an
    unrelated reason and the assertions below would pass on a gate that never
    ran the new axis at all.
    """
    from scripts.gate import run_gate
    from tests.mech_fixtures import build_gate_inputs, rederive_kwargs
    pois, itin = build_gate_inputs()
    pois[0]["business_status"] = "OPERATIONAL"      # the superseded bare form
    pois[0]["verify_status"] = "verified"
    rep = run_gate(pois, itin, advisory={"items": []}, **rederive_kwargs())
    checks = {c["name"]: c for c in rep["checks"]}
    assert rep["status"] == "fail"
    assert checks["verdicts_rule_current"]["passed"] is False
    assert checks["verdicts_rule_current"]["examined"] >= 1
    assert any(pois[0]["id"] in f and "superseded" in f for f in rep["failures"])


def test_gate_does_not_re_derive_a_chosen_lodging_on_both_axes():
    """run_gate folds each stop's chosen lodging into by_id (P4). Passing that
    folded pool to rederive_pois instead of the pois LIST would count every
    chosen hotel twice — once here and once on rederive_lodging — silently
    inflating every migration figure the CHANGELOG quotes.

    fix round 1 (reviewer finding): rederive_kwargs()'s DEFAULT accommodations
    is {"stops": []} -- no chosen candidate is ever folded into by_id, so the
    original version of this test (bare **rederive_kwargs()) had nothing to
    double-count regardless of which pool gate.py passed, and stayed green
    even with the bug (pois=list(by_id.values())) injected. This version
    supplies a REAL accommodations doc with a chosen candidate so poi_pool
    actually folds something in.

    'hotel-x' is built to fail EXACTLY ONE axis under the fix and BOTH axes
    under the bug: it deliberately omits resolved_name, so rederive_lodging
    always flags it (Gate 2b not re-derivable) regardless of which pool gate.py
    uses. It also carries no business_status (accommodations.schema.json has
    no such field) and a recorded verify_status of 'verified' -- so if it were
    ALSO folded into the pois axis (the bug), Gate 0 would fail to establish
    'operating' (business_status is absent) and rederive_pois would flag the
    SAME id as an unrelated 'superseded' failure, landing 'hotel-x' in BOTH
    poi_axis and lodging_axis. Under the fix, only the real `pois` list (never
    hotel-x) reaches rederive_pois, so poi_axis stays empty and the two axes
    cannot share an id."""
    from scripts.gate import run_gate
    from tests.mech_fixtures import build_gate_inputs, rederive_kwargs
    pois, itin = build_gate_inputs()
    accommodations = {"stops": [{
        "district": "測試區", "nights": 1, "chosen": "hotel-x",
        "candidates": [{
            "id": "hotel-x", "name_local": "測試旅館", "name_display": "測試旅館",
            "verify_status": "verified", "facilities": [],
            "geocode": {"lat": 1.0, "lng": 2.0, "geocode_source": "nominatim"},
            # resolved_name deliberately ABSENT -- the discriminator (see
            # docstring above).
            "sources": [{"url": "https://a.example/hotel-x", "lang": "zh"},
                        {"url": "https://b.example/hotel-x", "lang": "en"}],
        }],
    }]}
    rep = run_gate(pois, itin, advisory={"items": []},
                   **rederive_kwargs(accommodations=accommodations))
    poi_axis = [f for f in rep["failures"] if f.startswith("pois[")]
    lodging_axis = [f for f in rep["failures"] if f.startswith("accommodations ")]
    assert lodging_axis, "fixture must produce a real lodging-axis finding to discriminate against"
    ids = [f.split("'")[1] for f in poi_axis]
    assert len(ids) == len(set(ids))
    assert not (set(ids) & {f.split("'")[3] for f in lodging_axis if "'" in f})
