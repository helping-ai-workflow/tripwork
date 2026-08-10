"""Verdict re-derivation: the artifact's own inputs must reproduce its verdict."""
import datetime
import pathlib

import pytest
import yaml

from scripts.rederive import run_rederivation, hop_km, rederive_closing, Outcome

BRIEF = {"dates": {"start": "2026-08-29", "end": "2026-08-31"},
         "routing": {"max_hop_mins": 60, "max_single_drive_mins": 300}}
ITIN = {"days": [{"date": "2026-08-29", "rows": []}]}


def _checks(res):
    return {c["name"]: c for c in res["checks"]}


def test_a_leg_recorded_ok_that_is_too_long_fails_verdicts_match():
    """classify_leg has always been able to say drive_too_long. Nothing ever
    asked it about a finished legs.yaml, so the status field was whatever the
    agent typed."""
    legs = {"legs": [{"from": "三重", "to": "嘉義市", "kind": "home",
                      "mode": "drive", "duration_mins": 400, "status": "ok"}]}
    res = run_rederivation(ITIN, {}, legs=legs, routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF)
    c = _checks(res)
    assert c["verdicts_match"]["passed"] is False
    # 2, not 1: the filler cost={total:0, line_items:[]} is itself a complete,
    # matching, verdict-bearing record (rederive_cost counts a present cost
    # artifact once, unconditionally — it is a single total, not a list like
    # legs/hops) so it is compared and counted alongside the one leg.
    assert c["verdicts_match"]["examined"] == 2
    assert any("drive_too_long" in f and "三重" in f for f in res["failures"])


def test_a_correctly_recorded_leg_passes():
    legs = {"legs": [{"from": "三重", "to": "嘉義市", "kind": "home",
                      "mode": "drive", "duration_mins": 190, "status": "ok"}]}
    res = run_rederivation(ITIN, {}, legs=legs, routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF)
    assert _checks(res)["verdicts_match"]["passed"] is True


def test_a_non_drive_leg_with_no_last_service_is_not_rederivable():
    """scripts/legs.py:56-58 returns 'ok' when depart/last_service are absent.
    Re-derivation reproduces that 'ok' exactly, so verdicts_match is blind here —
    only the rederivable axis can see it."""
    legs = {"legs": [{"from": "嘉義", "to": "台南", "mode": "rail",
                      "duration_mins": 40, "status": "ok"}]}
    res = run_rederivation(ITIN, {}, legs=legs, routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF)
    c = _checks(res)
    assert c["verdicts_match"]["passed"] is True          # blind, as designed
    assert c["verdicts_rederivable"]["passed"] is False
    assert any("last_service_exempt" in f for f in res["failures"])


def test_a_hop_recorded_ok_that_is_below_the_floor_fails_verdicts_match():
    routing = {"clusters": [{"district": "西區", "pois": [],
                             "centroid": {"lat": 23.47999, "lng": 120.44343}},
                            {"district": "太保市", "pois": [],
                             "centroid": {"lat": 23.4590, "lng": 120.3350}}],
               "hops": [{"from": "西區", "to": "太保市", "mins": 5, "mode": "drive",
                         "duration_source": "sourced_timetable", "flag": "ok"}]}
    res = run_rederivation(ITIN, {}, legs={"legs": []}, routing=routing,
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF)
    assert _checks(res)["verdicts_match"]["passed"] is False
    assert any("implausible" in f for f in res["failures"])


def test_a_hop_endpoint_with_no_centroid_is_not_rederivable():
    """Without both endpoints there is no km, so min_plausible_mins has no floor
    to apply — classify_hop would silently degrade to a threshold-only compare."""
    routing = {"clusters": [{"district": "西區", "pois": [],
                             "centroid": {"lat": 23.47999, "lng": 120.44343}},
                            {"district": "太保市", "pois": []}],
               "hops": [{"from": "西區", "to": "太保市", "mins": 30, "mode": "drive",
                         "duration_source": "map_estimate", "flag": "ok"}]}
    res = run_rederivation(ITIN, {}, legs={"legs": []}, routing=routing,
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF)
    c = _checks(res)
    assert c["verdicts_rederivable"]["passed"] is False
    # Extended (Step 8b): the message names the whole hop ("西區->太保市"), not
    # only the endpoint missing a centroid -- otherwise two failures for
    # different hops sharing a missing district would be indistinguishable.
    assert any("centroid" in f and "太保市" in f and "西區" in f
               for f in res["failures"])


def test_a_hop_with_no_mode_is_not_rederivable():
    """km/mode omission escape (Step 8b), the `mode` half: scripts/distance.py
    silently degrades to a threshold-only compare when mode is absent --
    rederive_hops closes that at the artifact layer instead of reproducing it."""
    routing = {"clusters": [{"district": "西區", "pois": [],
                             "centroid": {"lat": 23.47999, "lng": 120.44343}},
                            {"district": "太保市", "pois": [],
                             "centroid": {"lat": 23.4590, "lng": 120.3350}}],
               "hops": [{"from": "西區", "to": "太保市", "mins": 30, "flag": "ok"}]}
    res = run_rederivation(ITIN, {}, legs={"legs": []}, routing=routing,
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF)
    c = _checks(res)
    assert c["verdicts_rederivable"]["passed"] is False
    assert any("no mode" in f and "西區" in f and "太保市" in f
               for f in res["failures"])


def test_hop_recorded_unsourced_with_no_duration_source_does_not_falsely_mismatch():
    """Fix round 1, one-liner 1: the provenance-blind fold must not overwrite a
    CORRECTLY recorded 'unsourced' back to 'ok'. Absent duration_source
    defaults to agent_estimate, which IS what classify_hop returns for this
    hop (km/mode present, over the floor, under the cap, agent_estimate) --
    so 'unsourced' is the right answer and folding it to 'ok' would report
    'recorded flag 'unsourced' but classify_hop re-derives 'ok'' on the axis
    reserved for WRONG verdicts, exactly backwards from what the fold exists
    to prevent."""
    routing = {"clusters": [{"district": "西區", "pois": [],
                             "centroid": {"lat": 23.47999, "lng": 120.44343}},
                            {"district": "太保市", "pois": [],
                             "centroid": {"lat": 23.4590, "lng": 120.3350}}],
               "hops": [{"from": "西區", "to": "太保市", "mins": 30, "mode": "drive",
                         "flag": "unsourced"}]}
    res = run_rederivation(ITIN, {}, legs={"legs": []}, routing=routing,
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF)
    c = _checks(res)
    assert c["verdicts_rederivable"]["passed"] is False   # still missing duration_source
    assert c["verdicts_match"]["passed"] is True           # but NOT a false mismatch
    assert not any("recorded flag 'unsourced'" in f for f in res["failures"])


def test_hop_km_handles_explicit_null_clusters_without_crashing():
    """Fix round 1, one-liner 2: opt() (scripts/gate.py) does not schema-validate,
    so an explicit `clusters: null` in routing.yaml reaches hop_km verbatim.
    `.get("clusters", [])` only substitutes when the KEY is absent -- an
    explicit null survives the .get and crashes the dict comprehension with
    TypeError instead of producing a gate failure."""
    assert hop_km({"clusters": None}, {"from": "a", "to": "b"}) is None


def test_a_hop_with_null_clusters_is_not_rederivable_not_a_crash():
    """End-to-end sibling of the hop_km guard above: run_rederivation must not
    raise on an explicit `clusters: null` -- it must report the hop as not
    re-derivable, the same as an absent centroid."""
    routing = {"clusters": None, "hops": [{"from": "西區", "to": "太保市", "mins": 30,
                                           "mode": "drive", "flag": "ok"}]}
    res = run_rederivation(ITIN, {}, legs={"legs": []}, routing=routing,
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF)
    c = _checks(res)
    assert c["verdicts_rederivable"]["passed"] is False
    assert any("centroid" in f for f in res["failures"])


def test_a_wrong_cost_total_fails_verdicts_match():
    cost = {"currency": "TWD", "as_of": "2026-08-07", "total": 99999,
            "line_items": [{"category": "lodging", "label": "兆品", "amount": 5000},
                           {"category": "transport", "label": "油資", "amount": 1000}]}
    res = run_rederivation(ITIN, {}, legs={"legs": []},
                           routing={"clusters": [], "hops": []}, cost=cost,
                           trip_brief=BRIEF)
    assert _checks(res)["verdicts_match"]["passed"] is False
    assert any("cost.total" in f and "6000" in f for f in res["failures"])


def test_a_missing_artifact_is_a_rederivable_failure_not_a_skip():
    """rule 13 only fires after rules 4/6/10 produced their artifacts, so an
    absent one means the pipeline ran out of order. Skipping would be the exact
    vacuous-true class this module exists to close."""
    res = run_rederivation(ITIN, {}, legs=None, routing=None, cost=None,
                           trip_brief=BRIEF)
    c = _checks(res)
    assert c["verdicts_rederivable"]["passed"] is False
    for name in ("legs.yaml", "routing.yaml", "cost.yaml"):
        assert any(name in f and "not re-derivable" in f for f in res["failures"])


def test_examined_counts_are_two_different_numbers():
    """rederivable.examined counts every verdict-bearing record found;
    match.examined counts only those with complete inputs. The difference is how
    many records the input gaps hid."""
    legs = {"legs": [
        {"from": "a", "to": "b", "mode": "drive", "duration_mins": 100, "status": "ok"},
        {"from": "c", "to": "d", "mode": "rail", "duration_mins": 40, "status": "ok"},
    ]}
    res = run_rederivation(ITIN, {}, legs=legs, routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF)
    c = _checks(res)
    # 3/2, not 2/1: the filler cost is itself one complete, matching record
    # (found+compared), on top of the 2 legs found / 1 leg compared. The
    # DIFFERENCE (3-2==1) is still exactly the one record the input gap hid —
    # that is the invariant this test pins, not the absolute totals.
    assert c["verdicts_rederivable"]["examined"] == 3
    assert c["verdicts_match"]["examined"] == 2


def test_hop_km_resolves_endpoints_through_cluster_centroids():
    routing = {"clusters": [{"district": "西區", "pois": [],
                             "centroid": {"lat": 23.47999, "lng": 120.44343}},
                            {"district": "太保市", "pois": [],
                             "centroid": {"lat": 23.4590, "lng": 120.3350}}]}
    km = hop_km(routing, {"from": "西區", "to": "太保市"})
    assert km is not None and 9.0 < km < 14.0
    assert hop_km(routing, {"from": "西區", "to": "不存在"}) is None


# CONDITIONAL GUARDS (I3). The four tests below are the only ones pinning this
# release's headline measurements, and they read an EXTERNAL consumer corpus.
# `.github/workflows/ci.yml` checks out this repo alone, so all four SKIP in CI
# and "zero skipped" is a statement about a developer machine that has the
# corpus, not about every checkout. The path is read from TRIPWORK_CORPUS
# (default: the controller's workspace) so it is not pinned to one machine --
# before that it was a hardcoded absolute path and no other machine could run
# them even with a corpus in hand.
from tests.mech_fixtures import CORPUS, CORPUS_TRIPS as IN_SCOPE


@pytest.mark.skipif(not CORPUS.is_dir(), reason="consumer corpus not present")
def test_real_trips_have_zero_verdicts_match_failures():
    """CONDITIONAL guard -- skipped without the consumer corpus, so it does not
    run in CI (I3).

    False-positive budget, measured at fd053dd before implementation.

    verdicts_match: 29 records compared across the four trips, ZERO mismatches —
    6 legs, 19 hops, 4 cost totals. That is the whole claim of this mechanism:
    it costs nothing on data whose verdicts are right.

    The counts are asserted so a silent DROP in coverage fails too — a check that
    examines nothing is the defect this module exists to close.

    hokkaido-7d and nz-south-island are excluded: both already fail
    validate_artifact at HEAD (hokkaido routing carries far_hops/max_hop_mins/slug;
    nz clusters lack district), so they are not a baseline for anything.
    """
    legs_seen = hops_seen = costs_seen = compared = 0
    for trip in IN_SCOPE:
        d = CORPUS / trip
        legs = yaml.safe_load((d / "legs.yaml").read_text(encoding="utf-8"))
        routing = yaml.safe_load((d / "routing.yaml").read_text(encoding="utf-8"))
        cost = yaml.safe_load((d / "cost.yaml").read_text(encoding="utf-8"))
        brief = yaml.safe_load((d / "trip-brief.yaml").read_text(encoding="utf-8"))
        res = run_rederivation({"days": []}, {}, legs=legs, routing=routing,
                               cost=cost, trip_brief=brief)
        c = _checks(res)
        assert c["verdicts_match"]["passed"] is True, (trip, res["failures"])
        legs_seen += len(legs.get("legs") or [])
        hops_seen += len(routing.get("hops") or [])
        costs_seen += 1
        compared += c["verdicts_match"]["examined"]
    assert (legs_seen, hops_seen, costs_seen) == (6, 19, 4)
    assert compared == 29, "every one of the 29 records must be COMPARED, not skipped"


@pytest.mark.skipif(not CORPUS.is_dir(), reason="consumer corpus not present")
def test_real_trips_report_exactly_the_measured_rederivable_gap():
    """CONDITIONAL guard -- skipped without the consumer corpus, so it does not
    run in CI (I3).

    The other axis, and the honest half of the budget: the same four trips
    have 19 verdicts_rederivable failures, one per hop, all of them
    'no duration_source'.

    This is a TRUE positive, not noise. Those hops were written before TW-066
    existed, so nothing recorded where their durations came from. Pinning the
    number means a future change that quietly widens or narrows the gap fails
    here instead of drifting.

    It is also the km/mode omission escape closing at the artifact layer: a hop
    that omits mode, or whose endpoint has no centroid, lands in this same list.
    Today the corpus omits neither, so all 19 failures are provenance ones.

    accommodations={"stops": []} (I2): this test is scoped to legs/hops/cost --
    the corpus's OWN, separate lodging rederivable gap is pinned by
    test_real_trips_lodging_has_exactly_one_verdicts_match_failure below. Passing
    the real accommodations.yaml here would fold 19 more findings (1 missing
    geocode_source + 18 missing resolved_name) into this test's 19, doubling the
    number for a reason unrelated to what this test claims.
    """
    total_missing = provenance_missing = 0
    for trip in IN_SCOPE:
        d = CORPUS / trip
        res = run_rederivation(
            {"days": []}, {},
            legs=yaml.safe_load((d / "legs.yaml").read_text(encoding="utf-8")),
            routing=yaml.safe_load((d / "routing.yaml").read_text(encoding="utf-8")),
            cost=yaml.safe_load((d / "cost.yaml").read_text(encoding="utf-8")),
            trip_brief=yaml.safe_load((d / "trip-brief.yaml").read_text(encoding="utf-8")),
            accommodations={"stops": []})
        c = _checks(res)
        assert c["verdicts_rederivable"]["passed"] is False, trip
        assert c["verdicts_rederivable"]["examined"] == (
            len(yaml.safe_load((d / "legs.yaml").read_text(encoding="utf-8")).get("legs") or [])
            + len(yaml.safe_load((d / "routing.yaml").read_text(encoding="utf-8")).get("hops") or [])
            + 1), trip
        total_missing += len(res["failures"])
        provenance_missing += sum("no duration_source" in f for f in res["failures"])
    assert (total_missing, provenance_missing) == (19, 19)


@pytest.mark.skipif(not CORPUS.is_dir(), reason="consumer corpus not present")
def test_real_trips_lodging_is_entirely_superseded_today():
    """CONDITIONAL guard -- skipped without the consumer corpus, so it does not
    run in CI (I3).

    Migrated for Task 6 (v0.34.0). Previously (fd053dd, task-9-brief.md's
    table, 2026-08-09): 18 lodging candidates, all recorded 'verified',
    rederive_lodging hardcoded operating=True and found exactly one
    verdicts_match failure -- 2026-07-sun-moon-lake's d2-6, a cluster_fallback
    centroid with no existence proof, re-deriving 'unverified' via Gate 2c.

    Re-measured after Step 4 threads a REAL Gate 0 into rederive_lodging: every
    one of the 18 candidates predates business_status (none of the four
    schema-clean trips has been re-run through accommodation-research since),
    so all 18 now land in `superseded`, not `mismatches` -- none of them ever
    reaches classify_candidate, so Gate 2c (retired in this same task, Step 4b)
    never gets a chance to run on any of them either. d2-6's old defect is now
    ONE of these 18 superseded findings, asserted by id so a bare count would
    not stay green if a DIFFERENT candidate stopped being found. verdicts_match
    is vacuously green for lodging today (0 compared) -- the honest state of
    an un-migrated corpus, not a hidden gap: surfacing that explicitly, instead
    of folding it into a false all-clear, is the whole point of `superseded`
    as its own axis (verdicts_rule_current, Task 3/4a).

    The other 19 findings are unchanged from before this task and still fire
    regardless of superseded status (the missing-input checks run before the
    Gate 0 check, see rederive_lodging): 1 candidate omits geocode_source
    entirely (a second, pre-TW-062 gap on the same 2026-06-yilan hotel) and 0
    of 18 carry resolved_name (the field is new in an earlier release, so
    every candidate is missing it) -- 1 + 18 == 19.
    """
    found = 0
    superseded = []
    other = []
    for trip in IN_SCOPE:
        d = CORPUS / trip
        accommodations = yaml.safe_load(
            (d / "accommodations.yaml").read_text(encoding="utf-8"))
        brief = yaml.safe_load((d / "trip-brief.yaml").read_text(encoding="utf-8"))
        res = run_rederivation({"days": []}, {}, legs={"legs": []},
                               routing={"clusters": [], "hops": []},
                               cost={"currency": "TWD", "line_items": [], "total": 0},
                               trip_brief=brief, accommodations=accommodations)
        c = _checks(res)
        assert c["verdicts_match"]["passed"] is True, (trip, res["failures"])
        found += sum(len(stop.get("candidates") or [])
                     for stop in accommodations.get("stops") or [])
        superseded.extend(f for f in res["failures"] if "superseded rules" in f)
        other.extend(f for f in res["failures"] if "superseded rules" not in f)
    assert found == 18
    assert len(superseded) == 18, superseded
    assert any("'d2-6'" in f for f in superseded), superseded
    assert len(other) == 19, other

    missing_geocode_source = sum("no geocode.geocode_source" in f for f in other)
    missing_resolved_name = sum("no resolved_name" in f for f in other)
    assert missing_geocode_source == 1
    assert missing_resolved_name == 18


def _poi(**over):
    p = {"id": "p1", "name_display": "花磚博物館", "verify_status": "verified",
         "hours": {"close": "17:30", "last_entry": "17:00",
                   "typical_visit_mins": 60, "as_of": "2026-08-01"}}
    p.update(over)
    return p


def _itin(time, slot="visit", pid="p1"):
    return {"days": [{"date": "2026-08-29",
                      "rows": [{"time": time, "slot": slot, "poi_id": pid,
                                "text": "花磚博物館"}]}]}


def test_a_row_scheduled_past_last_entry_fails_verdicts_match():
    """The closing-buffer iron rule (using-tripwork/SKILL.md:48) had no gate.
    A visit booked at 17:10 against a 17:00 last entry passed every check."""
    itin = _itin("17:10")
    itin["days"][0]["rows"][0]["closing_status"] = "ok"
    res = run_rederivation(itin, {"p1": _poi()}, legs={"legs": []},
                           routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF)
    c = _checks(res)
    assert c["verdicts_match"]["passed"] is False
    assert any("closing_status" in f and "17:10" in f for f in res["failures"])


def test_a_row_with_no_recorded_closing_status_is_not_rederivable():
    res = run_rederivation(_itin("13:15"), {"p1": _poi()}, legs={"legs": []},
                           routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF)
    c = _checks(res)
    assert c["verdicts_rederivable"]["passed"] is False
    assert any("no recorded closing_status" in f for f in res["failures"])


def test_an_open_air_poi_declares_no_fixed_close_instead_of_faking_one():
    """Guard, GREEN at HEAD: guards the `hours.no_fixed_close` short-circuit
    branch in `rederive_closing` — if that branch is ever dropped, this exact
    row (hours with no `close`, but `no_fixed_close: True`) falls through to
    the "neither close nor no_fixed_close" path and starts failing
    `verdicts_rederivable`, which is the false positive this test exists to
    prove does not happen.

    Genuine false positive, designed around rather than skipped: of the 10
    yilan POIs carrying hours with no `close`, the beaches, lakes and old streets
    among them genuinely have no closing time. Demanding hours.close there is
    wrong; a recorded CLAIM that there is none is not. (The eateries in that same
    group are a data gap, not a claim — see this task's opening note.)"""
    poi = _poi(hours={"typical_visit_mins": 45, "as_of": "2026-08-01",
                      "no_fixed_close": True})
    itin = _itin("17:10")
    itin["days"][0]["rows"][0]["closing_status"] = "ok"
    # accommodations={"stops": []} (I2): keeps this closing-status guard scoped
    # to what it names -- an absent accommodations.yaml is itself now a
    # verdicts_rederivable finding and would falsely flip the assertion below.
    res = run_rederivation(itin, {"p1": poi}, legs={"legs": []},
                           routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF, accommodations={"stops": []})
    c = _checks(res)
    assert c["verdicts_match"]["passed"] is True
    assert c["verdicts_rederivable"]["passed"] is True


def test_a_poi_with_neither_close_nor_no_fixed_close_is_not_rederivable():
    poi = _poi(hours={"typical_visit_mins": 45, "as_of": "2026-08-01"})
    itin = _itin("13:15")
    itin["days"][0]["rows"][0]["closing_status"] = "ok"
    res = run_rederivation(itin, {"p1": poi}, legs={"legs": []},
                           routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF)
    assert _checks(res)["verdicts_rederivable"]["passed"] is False
    assert any("no_fixed_close" in f for f in res["failures"])


def test_rows_without_a_time_or_a_resolving_poi_are_out_of_scope():
    """Guard, GREEN at HEAD: guards the `not t or not pid` scope filter in
    `rederive_closing` — if that filter regresses, move rows and free-text
    meals (rows with no `time` or no `poi_id`) get pulled into `examined`,
    burying the real closing-buffer signal under noise that was never
    schedulable against a POI's hours in the first place.

    Measured: of 94 corpus rows, 31 carry a `time` but no `poi_id` (move rows,
    free-text meals) and 5 carry a `poi_id` that does not resolve in
    verified-pois. Counting either in `examined` would bury the signal.

    The third row below (`time` + a `poi_id` that is NOT in `by_id`) exercises
    the `pid not in (by_id or {})` disjunct directly — otherwise that branch
    is reachable only through the corpus test, which is `skipif`-guarded on
    an external directory absent from every checkout that isn't the
    controller's."""
    itin = {"days": [{"date": "2026-08-29", "rows": [
        {"slot": "move", "from": "三重", "to": "嘉義市", "text": "自駕"},
        {"time": "12:00", "slot": "meal", "text": "朋友選定的店"},
        {"time": "12:00", "slot": "visit", "poi_id": "ghost", "text": "已刪除的景點"},
    ]}]}
    # accommodations={"stops": []} (I2): keeps this scope guard scoped to what
    # it names -- an absent accommodations.yaml is itself now a
    # verdicts_rederivable finding and would falsely flip the assertion below.
    res = run_rederivation(itin, {"p1": _poi()}, legs={"legs": []},
                           routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF, accommodations={"stops": []})
    c = _checks(res)
    assert c["verdicts_rederivable"]["passed"] is True
    # examined unchanged by the ghost row: legs=0 + hops=0 + cost=1(present,
    # filler) + closing=0 + accommodations=0(stops:[], present) == 1.
    assert c["verdicts_rederivable"]["examined"] == 1


def test_a_timed_lodging_row_is_out_of_closing_scope():
    """C1 (final whole-branch review): `run_gate` folds each stop's chosen
    lodging into `by_id` (the P4 rule, scripts/gate.py::chosen_lodging_pois), so
    a timed `slot: lodging` row RESOLVES — and `rederive_closing` then demanded
    `hours.close` / `hours.no_fixed_close` from a record that has nowhere legal
    to put either. `schemas/accommodations.schema.json`'s candidate items are
    `additionalProperties: false` with no `hours` property, so the only way to
    satisfy the demand fails `validate_artifact`
    (test_an_accommodations_candidate_cannot_legally_carry_hours below pins
    that). 5 unsatisfiable rows shipped on real consumer data: 2026-06-yilan 2,
    2026-08-chiayi 3.

    The cut is on `slot`, deliberately NOT on "did this id come only from the
    accommodations fold". Measured over the four schema-clean trips: 7 timed
    lodging rows resolve, and 2 of them (2026-07-sun-moon-lake `lealea` and
    `d2-2`) resolve through verified-pois.yaml because the consumer copied the
    hotels there. Those two carry no `hours` either — the same defect in
    different clothing — so a fold-membership cut would leave them demanding a
    closing time from a hotel.

    Nothing is lost by the skip: the lodging arrival check is a DIFFERENT,
    already-shipped mechanism reading a DIFFERENT field —
    `scripts/facilities.py::reception_ok` against `reception: {close,
    late_checkin}`, which accommodations.schema.json does declare, owned by
    accommodation-research (skills/accommodation-research/SKILL.md:73-74).
    `rederive_closing` transcribes the visit/meal rule (`last_order` /
    `last_entry` plus a `need_mins` buffer, skills/itinerary-synthesis/SKILL.md),
    which has no meaning for a check-in and none at all for chiayi's two
    CHECKOUT rows (08:30 breakfast-before-checkout, 10:45 check out by 11:00).
    """
    hotel = {"id": "maison-de-chine", "name_display": "兆品酒店嘉義",
             "verify_status": "verified",
             "geocode": {"lat": 23.47, "lng": 120.44,
                         "geocode_source": "nominatim"}}
    itin = _itin("15:00", slot="lodging", pid="maison-de-chine")
    res = run_rederivation(itin, {"maison-de-chine": hotel}, legs={"legs": []},
                           routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF, accommodations={"stops": []})
    c = _checks(res)
    assert c["verdicts_rederivable"]["passed"] is True, res["failures"]
    # examined == 1: the filler cost record only. The lodging row is out of
    # scope, so it never reaches `found`.
    assert c["verdicts_rederivable"]["examined"] == 1


def test_a_lodging_row_is_skipped_even_when_it_records_a_closing_status():
    """The skip is a SCOPE cut, not a special case of the missing-hours branch.
    A half-fix that only suppressed the "neither close nor no_fixed_close"
    message would still pull a lodging row into `compared` the moment someone
    hand-wrote a closing_status onto it, re-coupling the check to a record whose
    schema cannot describe closing time at all."""
    hotel = {"id": "h1", "name_display": "旅店", "verify_status": "verified",
             "hours": {"close": "23:30", "typical_visit_mins": 30,
                       "as_of": "2026-08-01"}}
    itin = _itin("15:00", slot="lodging", pid="h1")
    itin["days"][0]["rows"][0]["closing_status"] = "ok"
    res = run_rederivation(itin, {"h1": hotel}, legs={"legs": []},
                           routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF, accommodations={"stops": []})
    c = _checks(res)
    assert c["verdicts_match"]["examined"] == 1      # the filler cost only
    assert c["verdicts_rederivable"]["examined"] == 1


def test_an_accommodations_candidate_cannot_legally_carry_hours():
    """The premise C1 rests on, pinned mechanically rather than asserted in
    prose: there is NO legal place to answer `rederive_closing`'s demand on a
    lodging record. If a future release adds `hours` to
    schemas/accommodations.schema.json this test goes red, which is the signal
    to revisit the scope cut above rather than discover it on consumer data."""
    import tempfile

    from scripts.validate_artifact import SCHEMAS, validate_file

    cand = {"id": "d2-6", "name_local": "日月潭旅店", "name_display": "日月潭旅店",
            "facilities": [], "sources": [{"url": "https://a.example/x", "lang": "zh"},
                                          {"url": "https://b.example/x", "lang": "zh"}],
            "geocode": {"lat": 23.86, "lng": 120.91},
            "verify_status": "verified",
            "hours": {"close": "23:30"}}

    def _check(c):
        body = {"stops": [{"district": "日月潭", "nights": 1, "chosen": "d2-6",
                           "candidates": [c]}]}
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "accommodations.yaml"
            p.write_text(yaml.safe_dump(body, allow_unicode=True), encoding="utf-8")
            return validate_file(p, SCHEMAS / "accommodations.schema.json")

    rc, msgs = _check(cand)
    assert rc != 0, "accommodations.schema.json must still forbid `hours`"
    assert len(msgs) == 1 and "'hours' was unexpected" in msgs[0], msgs
    # Differential: the SAME candidate without `hours` is valid, so the failure
    # above is attributable to `hours` alone and not to a malformed fixture.
    clean = {k: v for k, v in cand.items() if k != "hours"}
    assert _check(clean)[0] == 0, _check(clean)


def _accom(candidate):
    return {"stops": [{"district": "日月潭", "nights": 1, "chosen": candidate["id"],
                       "candidates": [candidate]}]}


def _lodging_cand(**over):
    """Two distinct-domain, non-official sources; cluster_fallback geocode; no
    gmaps_place_id, no business_status -- the exact shape measured at fd053dd
    for 2026-07-sun-moon-lake candidate d2-6: recorded verified, no sourced
    operating signal at all. Since Step 4 (v0.34.0), a candidate in exactly
    this shape never reaches classify_candidate -- rederive_lodging routes it
    to `superseded` first (see test_a_bare_string_lodging_business_status_is_
    superseded). Callers that want to exercise classify_candidate's OTHER
    gates (1 / 2b) must pass a sourced business_status explicitly, e.g. via
    _sourced_business_status()."""
    c = {"id": "d2-6", "name_local": "日月潭旅店", "name_display": "日月潭旅店",
         "sources": [{"url": "https://a.example/d2-6", "lang": "zh"},
                     {"url": "https://b.example/d2-6", "lang": "zh"}],
         "geocode": {"lat": 23.86, "lng": 120.91, "geocode_source": "cluster_fallback"},
         "verify_status": "verified"}
    c.update(over)
    return c


def _sourced_business_status(**over):
    """Gate 0's object form, `as_of` computed at build time -- not a literal,
    same fuse tests/test_e2e_v033_closure.py:87-96's `_sourced_status()` warns
    about."""
    bs = {"status": "OPERATIONAL", "source_url": "https://a.example/d2-6",
         "as_of": datetime.date.today().isoformat()}
    bs.update(over)
    return bs


def test_a_cluster_fallback_lodging_candidate_with_a_sourced_business_status_verifies():
    """Migrated for the Gate 2c retirement (2026-08-09 user ruling, Step 4b).
    Before this task, a cluster_fallback candidate with no official source and
    no gmaps_place_id failed Gate 2c ('unverified') -- this test used to pin
    that failure (test_a_cluster_fallback_lodging_candidate_with_no_existence_
    proof_fails_verdicts_match). It cannot pass any more, and not only because
    the code branch was deleted: Step 4 threads a REAL Gate 0 into
    rederive_lodging, and a sourced business_status IS Gate 2c's existence
    proof (TW-072) -- so any candidate that reaches classify_candidate through
    rederive_lodging at all (i.e. is not already `superseded`) already clears
    Gate 2c's old cluster_fallback check by construction, with neither an
    official source nor a gmaps_place_id. The corpus's real d2-6 (no
    business_status recorded at all, the shape _lodging_cand() now models) is
    the other half of the story: it is `superseded`, not a verdicts_match
    failure -- see test_a_bare_string_lodging_business_status_is_superseded
    and the corpus guard test_real_trips_lodging_is_entirely_superseded_today
    below."""
    cand = _lodging_cand(business_status=_sourced_business_status(),
                         resolved_name="日月潭旅店")
    res = run_rederivation(ITIN, {}, legs={"legs": []}, routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF, accommodations=_accom(cand))
    c = _checks(res)
    assert c["verdicts_match"]["passed"] is True
    assert res["failures"] == []


def test_a_lodging_candidate_with_an_official_source_still_passes():
    """An official source is no longer WHY this passes -- Gate 2c is retired,
    so it is merely harmless. The sourced business_status alone is sufficient;
    see test_a_cluster_fallback_lodging_candidate_with_a_sourced_business_
    status_verifies for the identical claim with no official source at all."""
    cand = _lodging_cand(sources=[{"url": "https://a.example/d2-6", "lang": "zh", "official": True},
                                  {"url": "https://b.example/d2-6", "lang": "zh"}],
                         business_status=_sourced_business_status())
    res = run_rederivation(ITIN, {}, legs={"legs": []}, routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF, accommodations=_accom(cand))
    assert _checks(res)["verdicts_match"]["passed"] is True


def test_lodging_with_no_geocode_source_is_not_rederivable():
    # A sourced business_status on both variants: without one, both would land
    # in `superseded` before classify_candidate ever runs, and the "blind
    # compare" claim below would hold vacuously (nothing compared either way)
    # rather than for the reason this test names.
    with_gs = _accom(_lodging_cand(geocode={"lat": 23.86, "lng": 120.91,
                                            "geocode_source": "nominatim"},
                                   business_status=_sourced_business_status()))
    no_gs = _accom(_lodging_cand(geocode={"lat": 23.86, "lng": 120.91},
                                 business_status=_sourced_business_status()))
    res_with = run_rederivation(ITIN, {}, legs={"legs": []}, routing={"clusters": [], "hops": []},
                                cost={"currency": "TWD", "line_items": [], "total": 0},
                                trip_brief=BRIEF, accommodations=with_gs)
    res_no = run_rederivation(ITIN, {}, legs={"legs": []}, routing={"clusters": [], "hops": []},
                              cost={"currency": "TWD", "line_items": [], "total": 0},
                              trip_brief=BRIEF, accommodations=no_gs)
    c_no = _checks(res_no)
    assert c_no["verdicts_rederivable"]["passed"] is False
    assert any("geocode_source" in f for f in res_no["failures"])
    # blind-compare rule: the omission must not flip verdicts_match either way
    assert c_no["verdicts_match"]["passed"] == _checks(res_with)["verdicts_match"]["passed"]
    assert c_no["verdicts_match"]["passed"] is True, "both must be REAL compares, not vacuous"


def test_lodging_with_no_resolved_name_is_not_rederivable():
    cand = _lodging_cand(sources=[{"url": "https://a.example/d2-6", "lang": "zh", "official": True},
                                  {"url": "https://b.example/d2-6", "lang": "zh"}],
                         business_status=_sourced_business_status())
    res = run_rederivation(ITIN, {}, legs={"legs": []}, routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF, accommodations=_accom(cand))
    c = _checks(res)
    assert c["verdicts_rederivable"]["passed"] is False
    assert any("resolved_name" in f for f in res["failures"])
    # not demoted by the missing field: this candidate is otherwise 'verified'
    assert c["verdicts_match"]["passed"] is True


def test_a_bare_string_lodging_business_status_is_superseded():
    """Lodging Gate 0 was deferred in 0.33.0 for want of the field. It exists
    now, so a hotel gets the same treatment a POI does."""
    from scripts.rederive import rederive_lodging
    cand = _lodging_cand(geocode={"lat": 23.86, "lng": 120.91, "geocode_source": "nominatim"},
                         resolved_name="日月潭旅店", business_status="OPERATIONAL")
    out = rederive_lodging(_accom(cand), local_lang="zh")
    assert len(out.superseded) == 1 and "d2-6" in out.superseded[0]


def test_a_sourced_lodging_business_status_is_not_superseded():
    """`as_of` is computed at build time (not a literal) so this test does not
    flip PASS->FAIL 90 days after it was written, the same fuse
    tests/test_e2e_v033_closure.py:87-96's `_sourced_status()` warns about."""
    from scripts.rederive import rederive_lodging
    cand = _lodging_cand(
        geocode={"lat": 23.86, "lng": 120.91, "geocode_source": "nominatim"},
        resolved_name="日月潭旅店", business_status=_sourced_business_status())
    out = rederive_lodging(_accom(cand), local_lang="zh")
    assert out.superseded == []


def test_a_closed_lodging_candidate_is_rejected_not_silently_operating():
    """Step 4 removes the hardcoded operating=True bypass: a sourced but CLOSED
    business_status must now demote the candidate through Gate 0, exactly like
    a POI (TW-005). Before this task every hotel was treated as open no matter
    what its business_status said."""
    from scripts.rederive import rederive_lodging
    cand = _lodging_cand(
        geocode={"lat": 23.86, "lng": 120.91, "geocode_source": "nominatim"},
        resolved_name="日月潭旅店",
        business_status=_sourced_business_status(status="CLOSED_PERMANENTLY"))
    out = rederive_lodging(_accom(cand), local_lang="zh")
    assert out.superseded == []
    assert len(out.mismatches) == 1 and "rejected" in out.mismatches[0]


def test_lodging_gate_0_anchors_to_the_records_own_era_not_wall_clock():
    """Regression lock, mirroring test_gate_2c_stays_unreachable_on_the_poi_
    path_for_a_very_stale_as_of on the POI axis.

    Rebuilt (v0.34.0 Task 6 fix round 1, I3): the original version of this
    test used a stale `as_of` with `status: OPERATIONAL`, and it was GREEN
    with or without the anchor -- a surprise-GREEN, this project's own
    step-4 hard-halt condition, meaning the fixture was wrong, not the code.
    Reviewer's measurement (reproduced): under the fail-open this module had
    before M1 (`operating is not False`, which mapped `operating_from_status`
    returning `None` -- "not established", the shape a wall-clock read of a
    stale record produces -- to `operating=True` in classify_candidate), an
    OPERATIONAL-but-stale record reads as "verified" whether the clock is
    anchored or not: anchored, `operating_from_status` returns `(True, "")`
    directly; wall-clock, it returns `(None, "stale")`, which the fail-open
    then ALSO turned into "proceed as operating". Same final verdict either
    way -- the test could not tell the two code paths apart.

    A stale record with `status: CLOSED_PERMANENTLY` does discriminate, and
    keeps discriminating after M1 closed the fail-open (`if operating is
    None: superseded`, unconditionally): anchored (today=as_of, age=0), the
    status is unambiguous and classify_candidate correctly demotes the
    recorded 'verified' to a MISMATCH ('rejected'), because Gate 0 CAN be
    evaluated -- the record's own era says closed, full stop. Wall-clock
    (hypothetically, without the anchor), the SAME stale `as_of` trips the
    age>90 branch inside `operating_from_status` regardless of status,
    returning `None` -- which post-M1 means `superseded`, not a mismatch. A
    genuinely-recorded-closed hotel would then be filed as "not enough
    information" instead of "the recorded verdict is wrong", which is a
    real loss of signal, not merely calendar-driven noise on some OTHER
    verdict -- confirmed empirically by temporarily reverting the anchor
    (`today=as_of` -> omitted) and re-running this exact test: it goes RED
    (`superseded=1, mismatches=0` instead of the asserted `superseded=0,
    mismatches=1`). See task-6-report.md's I3 section for the pasted
    before/after."""
    from scripts.rederive import rederive_lodging
    cand = _lodging_cand(
        geocode={"lat": 23.86, "lng": 120.91, "geocode_source": "nominatim"},
        resolved_name="日月潭旅店", verify_status="verified",
        business_status=_sourced_business_status(
            status="CLOSED_PERMANENTLY", as_of="2020-01-01"))
    out = rederive_lodging(_accom(cand), local_lang="zh")
    assert out.superseded == [], out.superseded
    assert out.missing == []
    assert len(out.mismatches) == 1 and "d2-6" in out.mismatches[0]
    assert "'rejected'" in out.mismatches[0]
    assert out.compared == 1


def test_absent_accommodations_is_a_rederivable_failure_not_a_skip():
    res = run_rederivation(ITIN, {}, legs={"legs": []}, routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF, accommodations=None)
    c = _checks(res)
    assert c["verdicts_rederivable"]["passed"] is False
    assert any("accommodations.yaml" in f and "not re-derivable" in f for f in res["failures"])


@pytest.mark.skipif(not CORPUS.is_dir(), reason="consumer corpus not present")
def test_real_trips_closing_status_is_entirely_a_rederivable_gap():
    """CONDITIONAL guard -- skipped without the consumer corpus, so it does not
    run in CI (I3).

    Re-measured after the C1 fix (final v0.33.0 whole-branch review), and now
    against the pool the SHIPPED GATE resolves rows with.

    This guard used to build `by_id` from verified-pois.yaml alone. `run_gate`
    folds each stop's chosen lodging in (P4), so the guard measured 58 rows in
    scope while the gate measured 63 — and the 5-row delta WAS C1: five lodging
    rows the gate demanded `hours.close` from, with nowhere legal to record it.
    The guard could not see the defect because it was measuring a different
    pool. It now calls `scripts/gate.py::poi_pool`, the same helper `run_gate`
    calls, so the two cannot diverge again.

        94 itinerary rows total across the four schema-clean trips
      - 31 carry a `time` but no `poi_id` (move rows, free-text meals)
      -  0 carry a `poi_id` that resolves in NEITHER source
      -  7 are `slot: lodging` rows (out of scope, C1 — 5 resolve only through
           the accommodations fold, 2 through verified-pois.yaml because the
           consumer copied the hotels there; all 7 carry no `hours`)
      = 56 in scope (`time` AND a resolving `poi_id` AND not lodging)

    Of the 56: every one lands on the rederivable axis and 0 on the match axis —
    22 POIs have no `hours` at all and 5 have `hours` but no `close` (27 land on
    'neither close nor no_fixed_close'), and the remaining 29 land on 'no
    recorded closing_status', because 0 corpus rows carry a closing_status
    today. 56 verdicts_rederivable failures, 0 verdicts_match failures, 0
    compared — the honest half of the same budget Task 1 Step 8 pinned for
    legs/hops/cost. (The pre-C1 figures were 24/5/29 against 58 rows; the two
    that moved are sun-moon-lake's `lealea` and `d2-2`, hotels sitting in
    verified-pois.yaml with no `hours` — now out of scope as lodging rows.)
    """
    from scripts.gate import poi_pool

    total = Outcome()
    rows_total = has_time_no_pid = unresolved_pid = lodging_rows = 0
    no_hours_at_all = hours_but_no_close = no_closing_status = 0
    for trip in IN_SCOPE:
        d = CORPUS / trip
        itin = yaml.safe_load((d / "itinerary.yaml").read_text(encoding="utf-8"))
        pois = yaml.safe_load((d / "verified-pois.yaml").read_text(encoding="utf-8"))
        acc = yaml.safe_load((d / "accommodations.yaml").read_text(encoding="utf-8"))
        by_id = poi_pool(pois.get("pois") or [], acc)
        for day in itin.get("days") or []:
            for row in day.get("rows") or []:
                rows_total += 1
                t, pid = row.get("time"), row.get("poi_id")
                if t and not pid:
                    has_time_no_pid += 1
                elif t and pid and pid not in by_id:
                    unresolved_pid += 1
                elif t and pid and row.get("slot") == "lodging":
                    lodging_rows += 1
                elif t and pid:
                    hours = by_id[pid].get("hours") or {}
                    if not hours:
                        no_hours_at_all += 1
                    elif not hours.get("close") and not hours.get("no_fixed_close"):
                        hours_but_no_close += 1
                    elif "closing_status" not in row:
                        no_closing_status += 1
        total.merge(rederive_closing(itin, by_id))
    assert (rows_total, has_time_no_pid, unresolved_pid) == (94, 31, 0)
    assert lodging_rows == 7, "C1: every timed lodging row must be out of scope"
    assert (no_hours_at_all, hours_but_no_close, no_closing_status) == (22, 5, 29)
    assert total.found == 56, "56 rows must be IN SCOPE, not skipped"
    assert len(total.missing) == 56
    assert len(total.mismatches) == 0
    assert total.compared == 0, "nothing is comparable while 0 rows carry closing_status"
    # C1's regression lock, in two halves.
    #
    # (a) The guard really is exercising the FOLDED pool — otherwise "we call
    #     poi_pool now" would be unfalsifiable prose. The fold adds 3 hotel ids
    #     the corpus's verified-pois.yaml files do not carry
    #     (yilan lodging-xiangshouyixia, chiayi maison-de-chine, northeast
    #     fullon-fulong), and those 3 ids back 5 timed rows — 2 in yilan, 3 in
    #     chiayi, 0 for northeast's, whose hotel is never scheduled by id. Ids
    #     and rows are different counts; the assertion below counts IDS.
    #     sun-moon-lake adds none: its two hotels were copied into
    #     verified-pois.yaml, which is why the `slot` cut and not a
    #     fold-membership cut is what closes C1.
    #
    # (b) With lodging out of scope, closing scope is now fold-INVARIANT: both
    #     pools put the same 56 rows in scope. That equality is the property C1
    #     restored — before the fix the folded pool put 63 rows in scope against
    #     the un-folded 58, and the 5-row delta was five unsatisfiable demands.
    #     If a future change makes these two numbers differ again, the shipped
    #     gate has started asking a lodging record for a field its schema
    #     forbids, and this fails instead of the consumer finding out.
    folded_only = 0
    unfolded = Outcome()
    for trip in IN_SCOPE:
        d = CORPUS / trip
        itin = yaml.safe_load((d / "itinerary.yaml").read_text(encoding="utf-8"))
        pois = yaml.safe_load((d / "verified-pois.yaml").read_text(encoding="utf-8"))
        acc = yaml.safe_load((d / "accommodations.yaml").read_text(encoding="utf-8"))
        bare = {p["id"]: p for p in pois.get("pois") or []}
        folded_only += len(set(poi_pool(pois.get("pois") or [], acc)) - set(bare))
        unfolded.merge(rederive_closing(itin, bare))
    assert folded_only == 3, "the P4 fold must really be adding hotel ids here"
    assert unfolded.found == total.found == 56


def _poi_rec(**over):
    # NOTE: verified-pois.schema.json carries an allOf conditional —
    # verify_status: verified REQUIRES `geocode` and sources.minItems 2, and any
    # other status REQUIRES `status_reason`. An earlier draft of this plan omitted
    # both and its fixtures failed validation for a reason unrelated to the field
    # under test. Keep them.
    p = {"id": "p1", "name_local": "花磚博物館", "name_display": "花磚博物館",
         "category": "sight", "district": "嘉義市西區",
         "verify_status": "verified",
         "business_status": {"status": "OPERATIONAL",
                             "source_url": "https://a.example.tw/p",
                             "as_of": "2026-08-05"},
         "geocode": {"lat": 23.48, "lng": 120.44, "geocode_source": "nominatim"},
         "resolved_name": "花磚博物館",
         "sources": [{"url": "https://a.example.tw/p", "lang": "zh"},
                     {"url": "https://b.example.com/q", "lang": "en"}]}
    p.update(over)
    return p


def test_a_bare_string_business_status_is_superseded_not_a_mismatch():
    """TW-070 bucket 1. The input is PRESENT — it is simply in a form 0.32.0
    superseded — so calling it a missing input would misreport it, and calling it
    a wrong verdict would blame the agent for a rule change. Measured: 105 of 127
    corpus POIs land here and nothing else does."""
    from scripts.rederive import rederive_pois
    out = rederive_pois([_poi_rec(business_status="OPERATIONAL")])
    assert out.found == 1
    assert len(out.superseded) == 1 and "p1" in out.superseded[0]
    assert out.mismatches == [] and out.missing == []


def test_an_absent_resolved_name_is_a_rederivable_gap():
    """Bucket 2: the input needed to recompute Gate 2b is not recorded at all."""
    from scripts.rederive import rederive_pois
    rec = _poi_rec()
    del rec["resolved_name"]
    out = rederive_pois([rec])
    assert len(out.missing) == 1 and "resolved_name" in out.missing[0]
    assert out.superseded == [] and out.mismatches == []


def test_a_resolved_name_naming_another_venue_is_a_mismatch():
    """Bucket 3: every input is present and the recorded verdict does not follow
    from them. This is the only bucket that accuses the artifact of being wrong.

    ⚠ An earlier draft used a cluster_fallback POI with no existence proof. That
    shape can no longer produce a mismatch: Task 2 made a sourced business_status
    an existence proof, so any POI that clears Gate 0 also clears Gate 2c, and a
    POI that fails Gate 0 lands in bucket 1 instead. Gate 2b is what still
    discriminates here.

    "Gate 2c is unreachable on the POI path" holds for ANY business_status.as_of,
    not merely the fixtures this file happens to use — but only as of TW-070 fix
    round 1. Before that fix, `has_existence_proof` read wall-clock regardless of
    the anchored `today` verify_poi threaded into Gate 0, so a stale-but-
    artifact-anchored-fresh POI (Gate 0 passing via `today=as_of`) could still
    fail Gate 2c independently and land in THIS bucket — the exact
    calendar-driven mismatch this axis exists to prevent, one gate deeper than
    Gate 0. See scripts/verify.py::has_existence_proof's `today` note and
    scripts/verify.py::classify_candidate's Gate 2c call site — both now thread
    the same anchored `today` verify_poi received, so Gate 0 and Gate 2c can
    never disagree on the same business_status. This fixture (geocode_source
    'nominatim', not cluster_fallback) does not exercise that fix directly; it
    only proves Gate 2b still discriminates. The general claim is proved by
    scripts/rederive.py's own re-derivation over the corpus (found=127,
    superseded=105, mismatches=0) and pinned directly by
    test_gate_2c_stays_unreachable_on_the_poi_path_for_a_very_stale_as_of below,
    not by this test.
    """
    from scripts.rederive import rederive_pois
    out = rederive_pois([_poi_rec(resolved_name="嘉義公園")])   # a different venue
    assert len(out.mismatches) == 1 and "p1" in out.mismatches[0]
    assert "conflicting" in out.mismatches[0]
    assert out.superseded == [] and out.missing == []


def test_gate_2c_stays_unreachable_on_the_poi_path_for_a_very_stale_as_of():
    """Fix round 1 (TW-070) regression lock. Before threading `today` into
    has_existence_proof, a cluster_fallback POI whose business_status.as_of was
    old relative to REAL wall-clock -- but fresh relative to ITSELF, since
    rederive_pois always anchors today=as_of -- cleared Gate 0 (age 0 against
    its own era) and then independently failed Gate 2c (has_existence_proof
    read real wall-clock, saw the same as_of as ancient, found no proof). That
    produced a false 'conflicting'/'unverified' MISMATCH on a verdict that was
    correct when written -- the exact calendar-driven redness this axis exists
    to prevent, one gate deeper than Gate 0. as_of=2020-01-01 is deliberately
    far enough in the past that this stays a real regression guard for the
    life of this test, not a fuse that only happens to pass today."""
    from scripts.rederive import rederive_pois
    poi = _poi_rec(
        business_status={"status": "OPERATIONAL",
                         "source_url": "https://a.example.tw/p",
                         "as_of": "2020-01-01"},
        geocode={"lat": 23.48, "lng": 120.44, "geocode_source": "cluster_fallback"},
    )
    out = rederive_pois([poi])
    assert (out.superseded, out.missing, out.mismatches) == ([], [], [])
    assert out.compared == 1


def test_a_correctly_recorded_poi_produces_nothing():
    from scripts.rederive import rederive_pois
    out = rederive_pois([_poi_rec()])
    assert out.found == 1 and out.compared == 1
    assert (out.mismatches, out.missing, out.superseded) == ([], [], [])


def test_a_recorded_unverified_poi_is_not_flagged_merely_for_being_unverified():
    """The axis reports a verdict that CHANGES, not a verdict that is unwelcome.
    Measured: 22 of 127 corpus POIs are recorded unverified and re-derive
    unverified; flagging them would bury the 105 that actually moved."""
    from scripts.rederive import rederive_pois
    out = rederive_pois([_poi_rec(verify_status="unverified",
                                  business_status="OPERATIONAL")])
    assert (out.mismatches, out.missing, out.superseded) == ([], [], [])


def test_run_rederivation_emits_the_third_check():
    from scripts.rederive import run_rederivation
    res = run_rederivation({"days": []}, {}, legs={"legs": []},
                           routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF, accommodations={"stops": []},
                           pois=[_poi_rec(business_status="OPERATIONAL")])
    c = {x["name"]: x for x in res["checks"]}
    assert c["verdicts_rule_current"]["passed"] is False
    assert c["verdicts_rule_current"]["examined"] == 1
    assert c["verdicts_match"]["passed"] is True


def test_verdicts_rule_current_examined_sums_poi_and_lodging_found_counts():
    """Step 4a (v0.34.0, Task 6). Task 3 shipped `examined: poi_outcome.found`,
    correct only while rederive_pois was the sole axis that could produce a
    `superseded` entry. Step 4 breaks that invariant: rederive_lodging now
    threads a real Gate 0 too, so a lodging candidate can ALSO land in
    `superseded` -- and a fixture carrying one alongside a superseded POI
    proves `examined` must count both axes' found records, not the POI axis
    alone (which would then report a lodging failure on a check that claims
    not to have examined lodging at all -- the exact self-inconsistency this
    release exists to close). NOT total.found (2 legs would also be found by
    rederive_legs here but neither can ever produce `superseded`, so folding
    them in would inflate the denominator with records this check cannot
    speak to)."""
    from scripts.rederive import run_rederivation
    legs = {"legs": [{"from": "a", "to": "b", "mode": "drive",
                      "duration_mins": 100, "status": "ok"}]}
    lodging_cand = _lodging_cand(
        geocode={"lat": 23.86, "lng": 120.91, "geocode_source": "nominatim"},
        resolved_name="日月潭旅店", business_status="OPERATIONAL")  # bare string: superseded
    res = run_rederivation({"days": []}, {}, legs=legs,
                           routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF, accommodations=_accom(lodging_cand),
                           pois=[_poi_rec(business_status="OPERATIONAL")])  # bare string too
    c = {x["name"]: x for x in res["checks"]}
    assert c["verdicts_rule_current"]["passed"] is False
    assert c["verdicts_rule_current"]["examined"] == 2          # 1 poi + 1 lodging
    assert c["verdicts_rule_current"]["examined"] != c["verdicts_rederivable"]["examined"], (
        "must not silently equal total.found (2 legs + 1 poi + 1 lodging == 4)")
    assert len(res["failures"]) == 2   # both superseded, no missing/mismatch noise


def test_an_absent_pois_list_is_a_rederivable_failure_not_a_skip():
    """Fix round 1 (TW-070): rederive_pois's first cut looped `pois or []`, so
    `pois=None` (verified-pois.yaml itself never loaded) silently reported 0
    found and a green check -- the exact vacuous-true class this module's own
    opening doctrine exists to close (rederive_legs/hops/cost/lodging all
    already fail loudly on their artifact being None; this one didn't).
    Mirrors test_absent_accommodations_is_a_rederivable_failure_not_a_skip."""
    from scripts.rederive import run_rederivation
    res = run_rederivation({"days": []}, {}, legs={"legs": []},
                           routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF, accommodations={"stops": []},
                           pois=None)
    c = {x["name"]: x for x in res["checks"]}
    assert c["verdicts_rederivable"]["passed"] is False
    assert any("verified-pois.yaml" in f and "not re-derivable" in f
              for f in res["failures"])


def test_omitting_pois_entirely_is_lenient_not_a_forced_failure():
    """Fix round 1 (TW-070), the asymmetry `run_rederivation`'s own docstring
    documents: `pois` defaults to `()`, not `None`, unlike legs/routing/cost/
    accommodations. Those four are always threaded through by
    scripts/gate.py::run_gate, so a `None` default is safe -- `pois` is not
    threaded yet (Task 4's wiring; run_gate already receives its own `pois`
    argument but does not forward it to run_rederivation at all). Had this
    default matched the other four, EVERY existing run_gate call -- and every
    real gate run in production, today -- would report a false
    'verified-pois.yaml absent' failure on an artifact that plainly is not
    absent. Omitting `pois=` must stay silent; only an EXPLICIT `pois=None`
    (test_an_absent_pois_list_is_a_rederivable_failure_not_a_skip, above) means
    'the artifact is genuinely absent' and reaches the hard failure."""
    from scripts.rederive import run_rederivation
    res = run_rederivation({"days": []}, {}, legs={"legs": []},
                           routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF, accommodations={"stops": []})
    c = {x["name"]: x for x in res["checks"]}
    assert c["verdicts_rederivable"]["passed"] is True
    assert c["verdicts_rule_current"]["examined"] == 0
