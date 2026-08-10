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
import datetime

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
    # Narrowed from the bare "recorded verify_status" (v0.34.0, TW-070): the
    # POI/lodging superseded messages ALSO contain that phrase ("...: recorded
    # verify_status 'verified' was produced under superseded rules ..."), so
    # the bare marker would double-match every superseded record and break
    # _classify's exactly-one invariant. "but classify_candidate re-derives"
    # is unique to rederive_lodging's own MISMATCH message (as opposed to its
    # superseded message, which never reaches classify_candidate at all).
    #
    # v0.34.0 Task 6 retired this class from the corpus entirely: it fires
    # only when a lodging candidate reaches classify_candidate AND its
    # recorded verdict does not match, which now requires a sourced
    # business_status to reach classify_candidate in the first place. None of
    # the 18 real lodging candidates carry one, so all 18 (including the one
    # that used to land here, 2026-07-sun-moon-lake's d2-6) now land in
    # lodging_verdict_superseded below instead. The marker is kept, unfired,
    # as a live regression guard: a future corpus update that adds a sourced-
    # but-wrong business_status would need this class again, and a silently
    # absent marker would let _classify swallow it into "unattributed".
    ("lodging_verify_status_mismatch", "but classify_candidate re-derives"),
    # POI axis (TW-070) and lodging axis (v0.34.0 Task 6) each get their own
    # marker, discriminated by each message's own tail -- both share "was
    # produced under superseded rules" as a common substring (see above), but
    # POI's ends "...re-run source-verify for this POI" and lodging's ends
    # "...re-run accommodation-research for this candidate". Every corpus hit
    # on EITHER axis today is the SAME subtype -- a bare-string or absent
    # business_status, superseded by TW-063's/TW-072's sourced object form
    # (105 of 127 POI records, 18 of 18 lodging candidates, across these four
    # trips; see scripts/rederive.py::rederive_pois / rederive_lodging's
    # docstrings). No corpus hit today is the 'missing' or 'mismatch'
    # subtype on either axis, so this module carries no marker for them -- if
    # a future corpus update produces one, _classify's assert surfaces it as
    # an unattributed failure instead of silently absorbing it.
    ("poi_verdict_superseded", "re-run source-verify for this POI"),
    ("lodging_verdict_superseded", "re-run accommodation-research for this candidate"),
    ("ai_tone", "AI-tone "),
)

# Measured through the shipped run_gate after the C1 fix, then again after the
# TW-070 POI axis was wired in (v0.34.0), then again after Task 6 threads a
# real Gate 0 into rederive_lodging and retires Gate 2c: every count below
# except lodging_verdict_superseded (new) and lodging_verify_status_mismatch
# (now zero everywhere -- see the CLASSES comment above) is UNCHANGED from
# the TW-070 measurement. Task 6 does not alter or remove any OTHER
# pre-existing finding; it only reclassifies lodging's own.
# (total, {class: count}) per trip.
EXPECTED = {
    "2026-06-yilan": (58, {"hop_no_duration_source": 8, "poi_no_hours": 5,
                           "row_no_closing_status": 11,
                           "lodging_no_resolved_name": 1,
                           "lodging_no_geocode_source": 1,
                           "lodging_verdict_superseded": 1,
                           "poi_verdict_superseded": 31}),
    "2026-07-sun-moon-lake": (71, {"hop_no_duration_source": 3, "poi_no_hours": 12,
                                   "row_no_closing_status": 3,
                                   "lodging_no_resolved_name": 12,
                                   "lodging_verdict_superseded": 12,
                                   "poi_verdict_superseded": 29}),
    "2026-08-chiayi": (53, {"hop_no_duration_source": 6, "row_no_closing_status": 10,
                            "lodging_no_resolved_name": 3,
                            "lodging_verdict_superseded": 3, "ai_tone": 13,
                            "poi_verdict_superseded": 18}),
    "2026-09-northeast-coast": (65, {"hop_no_duration_source": 2, "poi_no_hours": 10,
                                     "row_no_closing_status": 5,
                                     "lodging_no_resolved_name": 2,
                                     "lodging_verdict_superseded": 2, "ai_tone": 17,
                                     "poi_verdict_superseded": 27}),
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


def test_the_six_axes_together_pin_the_release_headline_figures():
    """The aggregate the CHANGELOG's Migration section quotes, read back off the
    same run_gate reports rather than from a separate hand-driven
    run_rederivation — the divergence C1 turned on.

    Re-measured for v0.34.0 Task 6 (real Gate 0 threaded into rederive_lodging,
    Gate 2c retired). 230 verdict-bearing records found is UNCHANGED (Task 6
    reclassifies lodging findings; it does not add or remove records to
    examine). compared drops from 69 (TW-070) to 51: the 18 lodging
    candidates that used to reach a comparison (17 matching + 1 mismatching,
    d2-6) now land in `superseded` before classify_candidate ever runs, since
    none of them carries a sourced business_status -- there is no `operating`
    value left to compare with. That is also why the exactly-one-mismatch
    claim TW-070 pinned here is gone: this corpus has ZERO verdicts_match
    mismatches left on any axis (match_failed is empty), not because d2-6 was
    fixed, but because its defect moved from "wrong verdict" to "verdict
    produced under rules this release supersedes" -- a different, more
    precise claim about the same record (pinned by id in
    tests/test_rederive.py::test_real_trips_lodging_is_entirely_superseded_
    today).

    The sixth axis's OWN headline number is the third assertion: 123 of the
    145 examined records (105 POI + 18 lodging, both by id count) were
    produced under superseded rules (verdicts_rule_current) -- up from 105 of
    127 pre-Task-6, both in numerator (the 18 lodging candidates newly
    counted) and denominator (Step 4a: `examined` now sums poi_outcome.found +
    lodging_outcome.found, not poi_outcome.found alone). Today these totals
    are only recoverable by hand-summing EXPECTED's per-trip
    poi_verdict_superseded / lodging_verdict_superseded values -- a change
    that moved findings between trips while preserving the sums would pass
    unnoticed, so they are pinned here as explicit totals instead, counted
    the same way _classify already counts each trip's failures by class.
    """
    found = compared = examined_rule_current = 0
    super_poi = super_lodging = 0
    match_failed = []
    for trip in CORPUS_TRIPS:
        report = _gate(load_trip(trip))
        checks = {c["name"]: c for c in report["checks"]}
        found += checks["verdicts_rederivable"]["examined"]
        compared += checks["verdicts_match"]["examined"]
        examined_rule_current += checks["verdicts_rule_current"]["examined"]
        classes = _classify(report["failures"])
        super_poi += classes.get("poi_verdict_superseded", 0)
        super_lodging += classes.get("lodging_verdict_superseded", 0)
        if not checks["verdicts_match"]["passed"]:
            match_failed.append(trip)
        assert checks["verdicts_rederivable"]["passed"] is False, trip
        assert checks["verdicts_rule_current"]["passed"] is False, trip
    assert (found, compared) == (230, 51)
    assert (super_poi, super_lodging, super_poi + super_lodging) == (105, 18, 123)
    assert examined_rule_current == 145, "Step 4a: poi_outcome.found (127) + lodging_outcome.found (18)"
    assert match_failed == []


def test_the_three_verdict_axes_partition_their_failures():
    """No corpus record may be misattributed to the wrong verdict axis.

    The naive form of this guard -- assert poi_ids and lodging_ids never
    intersect -- is FALSE on this corpus: 2026-07-sun-moon-lake's
    verified-pois.yaml genuinely duplicates two hotels ('lealea', 'd2-2')
    that are ALSO the chosen lodging candidates in accommodations.yaml --
    the consumer copied them there (rederive_closing's own docstring names
    this exact pair) so both copies fail independently, for unrelated
    reasons (the POI copy's business_status is superseded; the lodging
    copy's resolved_name is missing). That is two real, separately-authored
    records about the same hotel, not one record counted twice, and no
    assertion should treat it as a defect.

    The invariant that DOES hold everywhere, and is what TW-070 fix round 1's
    synthetic fixture (tests/test_gate.py:672) actually guards against, is
    narrower: neither axis's failures may name an id that is not a genuine
    member of ITS OWN artifact. Under the fold bug that guard catches --
    run_gate passing poi_pool's folded by_id.values() into rederive_pois
    instead of the raw pois list -- a chosen lodging candidate NOT
    independently duplicated in verified-pois.yaml leaks into the POI axis
    under an id absent from that trip's raw pois list. Reproduced directly
    against rederive_pois for 2026-06-yilan: the bug phantom-flags
    'lodging-xiangshouyixia' (its chosen candidate id, present in neither
    that trip's nor any trip's raw verified-pois.yaml), which the subset
    assertions below catch.
    """
    for trip in CORPUS_TRIPS:
        a = load_trip(trip)
        report = _gate(a)
        raw_poi_ids = {p.get("id") for p in a["pois"]["pois"]}
        raw_lodging_ids = {c.get("id")
                           for stop in (a["accommodations"] or {}).get("stops") or []
                           for c in stop.get("candidates") or []}
        poi_ids = {f.split("'")[1] for f in report["failures"] if f.startswith("pois[")}
        lodging_ids = {f.split("'")[3] for f in report["failures"]
                       if f.startswith("accommodations ")}
        assert poi_ids, f"{trip}: no POI-axis findings to discriminate against"
        assert lodging_ids, f"{trip}: no lodging-axis findings to discriminate against"
        assert poi_ids <= raw_poi_ids, (trip, poi_ids - raw_poi_ids)
        assert lodging_ids <= raw_lodging_ids, (trip, lodging_ids - raw_lodging_ids)


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
    the hours"), and re-verifies every POI (TW-070, v0.34.0): a sourced
    business_status + geocode_source + resolved_name -- what a real
    source-verify re-run records -- then RECOMPUTES verify_status from those
    inputs and overwrites the recorded value, the same "recompute and
    overwrite" pattern _fix_legs/_fix_routing already use for their own
    mismatch classes.

    Scoped to every POI, not just the ones this round's report flagged
    'superseded': a POI recorded 'unverified'/'conflicting' for the CORRECT
    reason (Gate 0 never established, since business_status was absent) would
    otherwise still match on this round and only surface its real verdict
    after business_status is sourced -- exactly what a real re-run does in one
    visit, not one field at a time. as_of is computed at CALL time, never a
    literal (OPERATING_MAX_AGE_DAYS is 90) -- and `today=` is threaded through
    the SAME value into the recompute, so Gate 2c's existence-proof recency
    check reads the identical era, not wall-clock underneath a synthetic date.
    """
    from scripts.verify import verify_poi
    today = datetime.date.today().isoformat()
    for p in a["pois"]["pois"]:
        h = p.setdefault("hours", {})
        if not h.get("close") and not h.get("no_fixed_close"):
            h["close"], h["as_of"] = "18:00", "2026-08-01"
        if not isinstance(p.get("business_status"), dict):
            p["business_status"] = {"status": "OPERATIONAL",
                                    "source_url": "https://places.example/v1/place",
                                    "as_of": today}
        g = p.setdefault("geocode", {})
        g.setdefault("geocode_source", "nominatim")
        if "resolved_name" not in p:
            p["resolved_name"] = p.get("name_local") or p.get("name_display")
        _, status, _note = verify_poi(p, geocoded=bool(p.get("geocode")),
                                      in_claimed_region=True,
                                      resolved_name=p["resolved_name"], today=today)
        p["verify_status"] = status


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
    """Records what a real accommodation-research re-run would (I2, v0.33.0),
    plus a sourced business_status (v0.34.0 Task 6): a lodging candidate can
    now land in `superseded` exactly like a POI can, and re-running
    accommodation-research is the only stage that can supply the field. as_of
    is computed at CALL time, never a literal (OPERATING_MAX_AGE_DAYS is 90)."""
    today = datetime.date.today().isoformat()
    for stop in (a["accommodations"] or {}).get("stops") or []:
        for c in stop.get("candidates") or []:
            g = c.setdefault("geocode", {"lat": 24.7, "lng": 121.7})
            g["geocode_source"] = "nominatim"
            c["resolved_name"] = c.get("name_local") or c.get("name_display")
            if not isinstance(c.get("business_status"), dict):
                c["business_status"] = {"status": "OPERATIONAL",
                                        "source_url": "https://places.example/v1/place",
                                        "as_of": today}
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
    shape this branch shipped — the no-hours failures AND the POI-axis
    superseded failures (v0.34.0, TW-070 -- both live in verified-pois.yaml,
    both only source-verify can fix) fall through to itinerary-synthesis,
    which cannot write either field, and the drain reaches a fixed point
    instead of passing.

    36, not 5 (pre-TW-070): the fixed point now also strands yilan's 31
    poi_verdict_superseded failures alongside its original 5 no-hours ones.
    Still 36, not 37, after Task 6 (v0.34.0): yilan's own lodging_verdict_
    superseded finding (1, see EXPECTED) is unaffected by this mutation --
    only the `tripwork:source-verify` route is deleted, and lodging supersession
    routes to `tripwork:accommodation-research`, a different stage this
    mutation leaves intact. `_fix_accommodation` still resolves it normally,
    so it never reaches the fixed point.
    """
    import scripts.orchestration as orchestration

    monkeypatch.setattr(orchestration, "_ROUTES", tuple(
        g for g in orchestration._ROUTES if g[1] != "tripwork:source-verify"))
    terminated, history = _drain("2026-06-yilan")
    assert terminated is False
    # A genuine fixed point, not merely slow progress: the tail repeats.
    assert history[-1] == history[-2] == 36
    assert history[-1] > 0
