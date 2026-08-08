"""route_gate_failures: fix round 1, Important 1.

Before this file, `route_gate_failures` had zero tests -- the coupling between
each `_ROUTES` marker string in scripts/orchestration.py and the exact f-string
each producing function emits (scripts/gate.py's accommodation block,
scripts/rederive.py's rederive_legs/rederive_hops/rederive_cost) was verified
only by inspection. Every input below is built from a REAL failure string
produced by the actual producing function -- never a hand-typed literal --
so a rename on either side of the file boundary (e.g. "routing hop X->Y" ->
"hop X->Y") fails here instead of silently reverting to the itinerary-synthesis
fall-through this release exists to end.
"""
from scripts.gate import run_gate
from scripts.orchestration import route_gate_failures
from scripts.rederive import run_rederivation
from tests.mech_fixtures import rederive_kwargs

ITIN = {"days": [{"date": "2026-08-29", "rows": []}]}


def test_accommodation_marker_routes_to_accommodation_research():
    r = run_gate([], {"days": []},
                 accommodations={"stops": [{"district": "X", "nights": 1,
                                            "chosen": None, "candidates": []}]},
                 facility_needs={"required": []})
    assert any("chosen lodging" in f for f in r["failures"])
    assert route_gate_failures(r["failures"]) == "tripwork:accommodation-research"


def test_legs_marker_routes_to_inter_stop_legs():
    legs = {"legs": [{"from": "三重", "to": "嘉義市", "mode": "drive",
                      "duration_mins": 400, "status": "ok"}]}
    res = run_rederivation(ITIN, {}, legs=legs, routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0})
    assert any("legs[" in f for f in res["failures"])
    assert route_gate_failures(res["failures"]) == "tripwork:inter-stop-legs"


def test_routing_marker_routes_to_routing_audit():
    routing = {"clusters": [{"district": "西區", "pois": [],
                             "centroid": {"lat": 23.47999, "lng": 120.44343}},
                            {"district": "太保市", "pois": [],
                             "centroid": {"lat": 23.4590, "lng": 120.3350}}],
               "hops": [{"from": "西區", "to": "太保市", "mins": 5, "mode": "drive",
                         "duration_source": "sourced_timetable", "flag": "ok"}]}
    res = run_rederivation(ITIN, {}, legs={"legs": []}, routing=routing,
                           cost={"currency": "TWD", "line_items": [], "total": 0})
    assert any("routing hop " in f for f in res["failures"])
    assert route_gate_failures(res["failures"]) == "tripwork:routing-audit"


def test_cost_marker_routes_to_cost_rollup():
    cost = {"currency": "TWD", "as_of": "2026-08-07", "total": 99999,
            "line_items": [{"category": "lodging", "label": "兆品", "amount": 5000},
                           {"category": "transport", "label": "油資", "amount": 1000}]}
    res = run_rederivation(ITIN, {}, legs={"legs": []},
                           routing={"clusters": [], "hops": []}, cost=cost)
    assert any("cost.total" in f for f in res["failures"])
    assert route_gate_failures(res["failures"]) == "tripwork:cost-rollup"


def test_no_resolved_lodging_still_routes_to_synthesis_not_accommodation():
    """The documented exception: 'has no resolved lodging' is the always-on
    per-day floor (a missing itinerary ROW, scripts/gate.py's _day_has_lodging
    check) -- NOT in any _ROUTES group, so it must fall through to synthesis.
    Pass **rederive_kwargs() so the rederivation axes stay clean and this
    failure is the ONLY one in the report, isolating the exception."""
    pois = [{"id": "a", "verify_status": "verified", "geocode": {"lat": 1, "lng": 2}}]
    itin = {"title": "t", "days": [
        {"date": "2026-06-12", "rows": [{"slot": "meal", "poi_id": "a", "text": "lunch"}]},
        {"date": "2026-06-13", "rows": [{"slot": "meal", "poi_id": "a", "text": "lunch"}]},
    ]}
    r = run_gate(pois, itin, advisory={"items": []}, **rederive_kwargs())
    assert any("no resolved lodging" in f for f in r["failures"])
    assert route_gate_failures(r["failures"]) == "tripwork:itinerary-synthesis"


def test_accommodation_marker_wins_priority_over_a_later_group():
    """Priority-ordering guard: scripts/orchestration.py's comment says
    accommodation stays FIRST in _ROUTES on purpose. This combines two
    independently-real failure lists (a legs mismatch + an accommodation
    defect) and pins that accommodation wins regardless of which failure
    appears first in the list -- because route_gate_failures iterates
    _ROUTES groups in table order, not list order. Reordering the tuple to
    put "legs[" before the accommodation markers would flip this silently,
    with the rest of the suite still green."""
    legs = {"legs": [{"from": "三重", "to": "嘉義市", "mode": "drive",
                      "duration_mins": 400, "status": "ok"}]}
    legs_res = run_rederivation(ITIN, {}, legs=legs, routing={"clusters": [], "hops": []},
                                cost={"currency": "TWD", "line_items": [], "total": 0})
    accom = run_gate([], {"days": []},
                     accommodations={"stops": [{"district": "X", "nights": 1,
                                                "chosen": None, "candidates": []}]},
                     facility_needs={"required": []})
    combined = legs_res["failures"] + accom["failures"]
    assert route_gate_failures(combined) == "tripwork:accommodation-research"
