"""The REAL gate over the REAL corpus — the blind spot C1 lived in (I6), and
the rule 13.5 drain that proves feedback terminates (C2).

Every other corpus guard in this suite stubs at least one re-derivation axis:
tests/test_rederive.py's closing guard hand-builds `by_id`, its lodging guard
passes filler legs/routing/cost, and its legs/hops/cost guard passes
`accommodations={"stops": []}`. Each stub is individually defensible — it keeps
a test scoped to what it names — but the SET of them left no test running all
five axes together through `run_gate` itself. C1 shipped in exactly that gap:
`run_gate` folds chosen lodging into the POI pool (P4) and the closing guard did
not, so the guard measured 58 rows in scope while the gate measured 63, and the
5-row delta was five unsatisfiable demands on shipped consumer data.

Nothing here re-implements gate behaviour. Every number is read back off a real
`run_gate` report, so a change in any axis — or in the fold, or in the routing
table — moves a pinned figure instead of passing quietly.

CONDITIONAL: skipped without the consumer corpus (see mech_fixtures.CORPUS).
These guards do not run in CI.
"""
import collections
import copy

import pytest

from scripts.gate import poi_pool, run_gate
from scripts.orchestration import route_gate_failures
from tests.mech_fixtures import CORPUS, CORPUS_TRIPS, load_trip

pytestmark = pytest.mark.skipif(not CORPUS.is_dir(),
                                reason="consumer corpus not present")

# One marker per failure class the four clean trips actually produce. Asserting
# the classes PARTITION the failures (no leftovers) is what makes the per-trip
# counts below meaningful: a new class cannot hide inside an unchecked
# remainder.
CLASSES = (
    ("hop_no_duration_source", "no duration_source"),
    ("poi_no_hours", "carries neither hours.close"),
    ("row_no_closing_status", "no recorded closing_status"),
    ("lodging_no_resolved_name", "no resolved_name"),
    ("lodging_no_geocode_source", "no geocode.geocode_source"),
    ("lodging_verify_status_mismatch", "recorded verify_status"),
    ("ai_tone", "AI-tone "),
)

# Measured through the shipped run_gate after the C1 fix.
# (total, {class: count}) per trip.
EXPECTED = {
    "2026-06-yilan": (26, {"hop_no_duration_source": 8, "poi_no_hours": 5,
                           "row_no_closing_status": 11,
                           "lodging_no_resolved_name": 1,
                           "lodging_no_geocode_source": 1}),
    "2026-07-sun-moon-lake": (31, {"hop_no_duration_source": 3, "poi_no_hours": 12,
                                   "row_no_closing_status": 3,
                                   "lodging_no_resolved_name": 12,
                                   "lodging_verify_status_mismatch": 1}),
    "2026-08-chiayi": (32, {"hop_no_duration_source": 6, "row_no_closing_status": 10,
                            "lodging_no_resolved_name": 3, "ai_tone": 13}),
    "2026-09-northeast-coast": (36, {"hop_no_duration_source": 2, "poi_no_hours": 10,
                                     "row_no_closing_status": 5,
                                     "lodging_no_resolved_name": 2, "ai_tone": 17}),
}


def _gate(a):
    b = a["brief"]
    return run_gate(a["pois"]["pois"], a["itinerary"],
                    accommodations=a["accommodations"],
                    facility_needs=b.get("facility_needs"), calendar=a["calendar"],
                    advisory=a["advisory"], must_do=b.get("must_do"), legs=a["legs"],
                    routing=a["routing"], cost=a["cost"], trip_brief=b)


def _classify(failures):
    seen = collections.Counter()
    for f in failures:
        hits = [name for name, marker in CLASSES if marker in f]
        assert len(hits) == 1, f"failure matches {hits} classes, expected 1: {f}"
        seen[hits[0]] += 1
    return dict(seen)


@pytest.mark.parametrize("trip", CORPUS_TRIPS)
def test_the_real_gate_over_a_clean_trip_pins_its_failure_classes(trip):
    """I6: all five re-derivation axes, the AI-tone gate and the home-leg check
    running together through the SHIPPED run_gate — the pool built by the real
    P4 fold, not a hand-rolled one.

    The per-class counts are pinned rather than the bare total: a total alone
    stays green when one class silently doubles while another silently empties,
    which is how a gate stops examining things without anyone noticing.
    """
    report = _gate(load_trip(trip))
    total, expected = EXPECTED[trip]
    assert report["status"] == "fail"
    assert _classify(report["failures"]) == expected
    assert len(report["failures"]) == total
    assert sum(expected.values()) == total, "the classes must PARTITION the failures"


def test_the_five_axes_together_pin_the_release_headline_figures():
    """The aggregate the CHANGELOG's Migration section quotes, read back off the
    same run_gate reports rather than from a separate hand-driven
    run_rederivation — the divergence C1 turned on.

    103 verdict-bearing records found, 47 of them with inputs complete enough to
    compare, and exactly ONE recorded verdict wrong (2026-07-sun-moon-lake's
    lodging candidate d2-6, pinned by id in tests/test_rederive.py).
    """
    found = compared = 0
    match_failed = []
    for trip in CORPUS_TRIPS:
        checks = {c["name"]: c for c in _gate(load_trip(trip))["checks"]}
        found += checks["verdicts_rederivable"]["examined"]
        compared += checks["verdicts_match"]["examined"]
        if not checks["verdicts_match"]["passed"]:
            match_failed.append(trip)
        assert checks["verdicts_rederivable"]["passed"] is False, trip
    assert (found, compared) == (103, 47)
    assert match_failed == ["2026-07-sun-moon-lake"]


@pytest.mark.parametrize("trip", CORPUS_TRIPS)
def test_no_failure_class_routes_to_a_stage_that_cannot_write_it(trip):
    """C2, stated as the invariant rather than as a simulation: the field a
    failure names must be writable by the stage it routes to.

    `hours` lives in verified-pois.yaml and only `tripwork:source-verify` writes
    that file — skills/source-verify/SKILL.md's closure-days paragraph ends
    "leave `close` absent and let the gate flag it", so the flag was always
    meant to reach that stage. Before the `_ROUTES` source-verify group it
    reached `tripwork:itinerary-synthesis`, which cannot write the field, and
    the feedback loop could not terminate.
    """
    report = _gate(load_trip(trip))
    for f in report["failures"]:
        if "carries neither hours.close" in f:
            assert route_gate_failures([f]) == "tripwork:source-verify", f
        if "AI-tone " in f:
            assert route_gate_failures([f]) == "tripwork:itinerary-synthesis", f


# --------------------------------------------------------------------------
# rule 13.5 drain: route, grant the routed stage its BEST possible fix, re-gate.
# --------------------------------------------------------------------------

def _fix_source_verify(a):
    """Records the closing times it left absent (SKILL.md's "go back and find
    the hours")."""
    for p in a["pois"]["pois"]:
        h = p.setdefault("hours", {})
        if not h.get("close") and not h.get("no_fixed_close"):
            h["close"], h["as_of"] = "18:00", "2026-08-01"


def _fix_routing(a):
    from scripts.distance import classify_hop
    from scripts.rederive import hop_km
    r = a["routing"] or {}
    known = {c.get("district") for c in r.get("clusters") or [] if c.get("centroid")}
    for hop in r.get("hops") or []:
        hop.setdefault("mode", "drive")
        hop["duration_source"] = "sourced_timetable"
        hop["source_url"] = "https://example.gov.tw/timetable"
        for end in ("from", "to"):
            if hop.get(end) not in known:
                r.setdefault("clusters", []).append(
                    {"district": hop.get(end), "pois": [],
                     "centroid": {"lat": 24.7, "lng": 121.7}})
                known.add(hop.get(end))
    for hop in r.get("hops") or []:
        hop["flag"] = classify_hop(hop.get("mins"), 60, km=hop_km(r, hop),
                                   mode=hop.get("mode"),
                                   duration_source=hop.get("duration_source"),
                                   source_url=hop.get("source_url"))


def _fix_legs(a):
    from scripts.legs import classify_leg
    for lg in (a["legs"] or {}).get("legs") or []:
        if lg.get("mode") == "drive":
            lg.setdefault("duration_mins", 60)
        else:
            lg["last_service_exempt"] = True
        lg["status"] = classify_leg(lg, 300)[0]


def _fix_accommodation(a):
    for stop in (a["accommodations"] or {}).get("stops") or []:
        for c in stop.get("candidates") or []:
            g = c.setdefault("geocode", {"lat": 24.7, "lng": 121.7})
            g["geocode_source"] = "nominatim"
            c["resolved_name"] = c.get("name_local") or c.get("name_display")
            srcs = c.setdefault("sources", [])
            while len({s.get("url", "").split("/")[2] for s in srcs if s.get("url")}) < 2:
                srcs.append({"url": f"https://s{len(srcs)}.example/x", "lang": "zh"})


def _fix_cost(a):
    from scripts.cost import sum_costs
    if a["cost"] is not None:
        summed = sum_costs(a["cost"].get("line_items") or [])
        a["cost"]["total"] = summed["total"]
        if "by_category" in a["cost"]:
            a["cost"]["by_category"] = summed["by_category"]


def _strip_tone(text):
    from scripts.text_hygiene import ai_tone_failures
    out = "".join(ch for ch in (text or "") if ch not in "—*")
    return out if not ai_tone_failures(out) else "行程"


def _fix_synthesis(a):
    """Rewrites the itinerary: a closing_status per in-scope row, a row for
    every home leg, tone-clean text, a meal on every day."""
    from scripts.hours import closing_status
    from scripts.rederive import _last_call_for, _need_mins
    by = poi_pool(a["pois"]["pois"], a["accommodations"])
    legs_list = (a["legs"] or {}).get("legs") or []
    days = a["itinerary"].get("days") or []
    for d in days:
        for row in d.get("rows") or []:
            for key in ("text", "from", "to"):
                if row.get(key):
                    row[key] = _strip_tone(row[key])
            t, pid = row.get("time"), row.get("poi_id")
            if not t or not pid or pid not in by or row.get("slot") == "lodging":
                row.pop("closing_status", None)
                continue
            hours = by[pid].get("hours") or {}
            if hours.get("no_fixed_close"):
                row["closing_status"] = "ok"
            elif hours.get("close"):
                row["closing_status"] = closing_status(
                    t, hours["close"], _last_call_for(row.get("slot"), hours),
                    _need_mins(hours, 30, 60))[0]
    a["itinerary"]["title"] = _strip_tone(a["itinerary"].get("title"))
    a["itinerary"]["checklist"] = [_strip_tone(c)
                                   for c in a["itinerary"].get("checklist") or []]
    for c in a["itinerary"].get("contingency") or []:
        for key in ("trigger", "fallback", "note"):
            if c.get(key):
                c[key] = _strip_tone(c[key])
    if days:
        for i, lg in enumerate(legs_list):
            if lg.get("kind") == "home":
                days[0].setdefault("rows", []).append(
                    {"slot": "move", "text": "移動", "leg_index": i})
    for d in days:
        if not any(r.get("slot") == "meal" for r in d.get("rows") or []):
            d.setdefault("rows", []).append({"slot": "meal", "text": "用餐"})


_FIX = {"tripwork:source-verify": _fix_source_verify,
        "tripwork:routing-audit": _fix_routing,
        "tripwork:inter-stop-legs": _fix_legs,
        "tripwork:accommodation-research": _fix_accommodation,
        "tripwork:cost-rollup": _fix_cost,
        "tripwork:itinerary-synthesis": _fix_synthesis}


def _drain(trip, max_rounds=10):
    """Returns (terminated, per-round failure counts)."""
    a = copy.deepcopy(load_trip(trip))
    history = []
    for _ in range(max_rounds):
        report = _gate(a)
        history.append(len(report["failures"]))
        if report["status"] == "pass":
            return True, history
        _FIX[route_gate_failures(report["failures"])](a)
    return False, history


@pytest.mark.parametrize("trip", CORPUS_TRIPS)
def test_rule_13_5_drains_instead_of_looping(trip):
    """C2: grant every routed stage its best possible fix and the gate reaches
    `pass`. This is the property the CHANGELOG's own deferred-R5 bullet names as
    the reason R5 was withheld — "a calendar-driven non-terminating loop" — and
    which R4 shipped carrying for the no-hours class.

    A round that does not reduce the count is not a loop as long as the failure
    CLASS changes: after source-verify records the hours, five "carries neither
    hours.close" failures become five "no recorded closing_status" failures,
    which are synthesis's to write. The termination assertion is what
    distinguishes the two; the counterfactual below is what proves this test
    would have gone red before the fix.
    """
    terminated, history = _drain(trip)
    assert terminated, f"{trip} did not drain: {history}"
    assert history[-1] == 0 and history[0] == EXPECTED[trip][0]


def test_removing_the_source_verify_route_reproduces_the_non_terminating_drain(
        monkeypatch):
    """The mutation that proves the guard above is load-bearing rather than
    tautological. With the `_ROUTES` source-verify group deleted — the exact
    shape this branch shipped — the no-hours failures fall through to
    itinerary-synthesis, which cannot write `hours`, and the drain reaches a
    fixed point instead of passing.
    """
    import scripts.orchestration as orchestration

    monkeypatch.setattr(orchestration, "_ROUTES", tuple(
        g for g in orchestration._ROUTES if g[1] != "tripwork:source-verify"))
    terminated, history = _drain("2026-06-yilan")
    assert terminated is False
    # A genuine fixed point, not merely slow progress: the tail repeats.
    assert history[-1] == history[-2] == 5
    assert history[-1] > 0
