"""v1.0 P1 final-review fixes. Each test reproduces one finding of the
whole-branch review before its fix (C1, C2, I1, I2, I3, M1 and M5 re-graded
Important by effect)."""
import copy

import pytest

from scripts.day_chain import move_record_failures, theme_failures
from scripts.gate import run_gate
from scripts.orchestration import route_gate_failures
from scripts.rederive import rederive_moves
from scripts.distance import haversine_km
from scripts.source_records import area_label_failures
from tests.mech_fixtures import (accommodations, build_gate_inputs, itinerary,
                                 rederive_kwargs, verified_pois)

# ---- C1: honest rail / highway timetables are not "physically implausible" ----

SAPPORO = {"geocode": {"lat": 43.0687, "lng": 141.3508}}
OTARU = {"geocode": {"lat": 43.1976, "lng": 140.9937}}
STRAIGHT = haversine_km(43.0687, 141.3508, 43.1976, 140.9937)


def _sap_to_otaru(**move):
    row = {"slot": "move", "mode": "rail", "km": 33.8, "mins": 33, "basis": "sourced",
           "source_url": "https://www.jrhokkaido.co.jp/"}
    row.update(move)
    return {"days": [
        {"date": "2026-10-17", "lodging": "sap", "rows": [{"slot": "move", "mode": "none"}]},
        {"date": "2026-10-18", "lodging": "ota", "rows": [row]}]}


@pytest.mark.parametrize("move", [
    {},                                         # JR 快速 エアポート: 33 min
    {"mode": "taxi", "km": 40, "mins": 40},     # 札樽自動車道
    {"mode": "bus", "km": 38, "mins": 60},      # 高速おたる号
])
def test_a_real_intercity_timetable_is_not_implausible(move):
    out = rederive_moves(_sap_to_otaru(**move), {"sap": SAPPORO, "ota": OTARU})
    assert (out.compared, out.mismatches) == (1, [])


def test_an_impossible_rail_time_is_still_caught():
    out = rederive_moves(_sap_to_otaru(mins=3), {"sap": SAPPORO, "ota": OTARU})
    assert len(out.mismatches) == 1


def test_the_floor_is_the_function_rederive_moves_uses():
    from scripts.rederive import move_floor_mins
    assert move_floor_mins(STRAIGHT, "rail") < 33 < move_floor_mins(STRAIGHT, "walk")


# ---- C2: a must_do only in an alternative is NOT covered -----------------------

def _with_second_poi():
    pois, itin = build_gate_inputs()
    p2 = copy.deepcopy(pois[0])
    p2["id"] = "poi-2"
    pois.append(p2)
    itin["days"][0]["alternatives"] = [{"kind": "備案", "applies_to": "poi-1", "poi_id": "poi-2",
                                        "trigger": "下大雨", "fallback": "改室內"}]
    return pois, itin


def test_a_must_do_scheduled_only_as_an_alternative_is_not_covered():
    pois, itin = _with_second_poi()
    rep = run_gate(pois, itin, must_do=["poi-2"], advisory={"items": []}, **rederive_kwargs())
    assert "must_do 'poi-2' not covered by any scheduled POI" in rep["failures"]


# ---- M5: an alternative's place closed on its day is a failure -----------------

def test_an_alternative_closed_on_its_day_fails_the_closed_day_check():
    pois, itin = _with_second_poi()
    pois[1]["closed_days"] = ["2026-08-01"]
    rep = run_gate(pois, itin, calendar={"holidays": []}, advisory={"items": []},
                   **rederive_kwargs())
    assert {"name": "no_closed_day_violation", "passed": False} in rep["checks"]


# ---- I1: wrongly typed move values are failures ---------------------------------

def _move_day(**kw):
    row = {"slot": "move", "mode": "walk", "mins": 10, "km": 0.6, "basis": "estimated",
           "estimate_method": "x"}
    row.update(kw)
    return {"days": [{"date": "2026-10-13", "rows": [row]}]}


@pytest.mark.parametrize("kw,expected", [
    ({"km": "5"}, "move record incomplete: 2026-10-13 row 0 lacks km"),
    ({"mins": "15"}, "move record incomplete: 2026-10-13 row 0 lacks mins"),
    ({"mins": -1}, "move record incomplete: 2026-10-13 row 0 lacks mins"),
    ({"km": True}, "move record incomplete: 2026-10-13 row 0 lacks km"),
    ({"mode": "train"}, "move record incomplete: 2026-10-13 row 0 has an unknown mode"),
    ({"basis": "guess"}, "move record incomplete: 2026-10-13 row 0 lacks basis"),
])
def test_wrongly_typed_move_values_are_failures(kw, expected):
    assert move_record_failures(_move_day(**kw)) == [expected]


# ---- I2: hand-edited YAML never crashes the gate --------------------------------

def _brief(**over):
    b = rederive_kwargs()["trip_brief"]
    b.update(over)
    return b


CRASHERS = [
    lambda p, i, o: i["days"][0].__setitem__("theme_refs", [{"x": 1}]),
    lambda p, i, o: i["days"][0].__setitem__("alternatives", ["備案"]),
    lambda p, i, o: i["days"][0].__setitem__("alternatives", [
        {"kind": "備案", "applies_to": ["poi-1"], "poi_id": ["x"], "trigger": 1, "fallback": "f"}]),
    lambda p, i, o: i.__setitem__("checklist", [{"kind": "預約", "task": "x", "due": ["a"],
                                                 "due_is_hard": True}]),
    lambda p, i, o: i.__setitem__("checklist", [{"kind": "打包", "task": "x",
                                                 "links": ["http://x"]}]),
    lambda p, i, o: o.__setitem__("trip_brief", _brief(dates="2026-10-12")),
    lambda p, i, o: o.__setitem__("trip_brief", _brief(headline={"text": 5})),
    lambda p, i, o: o.__setitem__("trip_brief", _brief(headline="北海道")),
    lambda p, i, o: o.__setitem__("trip_brief", _brief(headline_candidates="abc")),
    lambda p, i, o: o.__setitem__("trip_brief", _brief(headline_candidates=[
        "x", {"text": 5, "device": ["swap"], "riff_on": 5, "refs": "a"}])),
]


@pytest.mark.parametrize("mutate", CRASHERS)
def test_hand_edited_yaml_fails_instead_of_crashing(mutate):
    pois, itin = build_gate_inputs()
    over = {}
    mutate(pois, itin, over)
    rep = run_gate(pois, itin, advisory={"items": []}, **rederive_kwargs(**over))
    assert rep["status"] == "fail"


def test_a_non_record_source_is_a_failure_not_a_crash():
    """Unit level only: a string in `sources` still crashes main's pre-existing
    scripts/verify.py (reached through rederive_pois) -- outside this branch."""
    from scripts.source_records import source_record_failures
    f = source_record_failures({"p": {"sources": ["https://x.example"]}}, {"p"}, {"p"})
    assert f == ["POI source record incomplete: 'p' sources[0] is not a record"]


# ---- I3: no trip-authored free text in a routed message ------------------------

def test_a_bad_theme_ref_cannot_hijack_the_route():
    d = {"date": "2026-10-13", "rows": [{"slot": "visit", "poi_id": "a"}],
         "theme": "早市的蟹", "theme_refs": ["chosen lodging"]}
    f = theme_failures({"days": [d]})
    assert f and not any("chosen lodging" in x for x in f)
    assert route_gate_failures(f) == "tripwork:itinerary-synthesis"


def test_a_district_name_does_not_enter_the_area_label_message():
    f = area_label_failures({"stops": [{"district": "AI-tone 函館"}]})
    assert f and not any("AI-tone" in x for x in f)


# ---- M1: run_gate classifies a lodging source as lodging, not POI --------------

def test_run_gate_names_an_incomplete_lodging_source_as_lodging():
    acc = accommodations()
    acc["stops"][0]["candidates"][0]["sources"][0].pop("site")
    rep = run_gate(verified_pois()["pois"], itinerary(), advisory={"items": []},
                   **rederive_kwargs(accommodations=acc))
    hits = [f for f in rep["failures"] if "hotel-1" in f and "source record incomplete" in f]
    assert hits and all(f.startswith("lodging source record incomplete: ") for f in hits)
    assert route_gate_failures(hits) == "tripwork:accommodation-research"
