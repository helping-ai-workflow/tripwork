"""Verdict re-derivation: the artifact's own inputs must reproduce its verdict."""
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
def test_real_trips_lodging_has_exactly_one_verdicts_match_failure():
    """CONDITIONAL guard -- skipped without the consumer corpus, so it does not
    run in CI (I3).

    Measured at fd053dd (task-9-brief.md's table, 2026-08-09) across the four
    schema-clean trips: 18 lodging candidates, all 18 recorded verify_status
    'verified', 14 of them geocode_source cluster_fallback. rederive_lodging
    re-derives Gates 1/2/2b/2c for each -- this is the whole justification for
    the task: accommodation-research calls classify_candidate directly and
    passes none of Part 1's arguments, so operating/name_match/geocode_source
    all took their permissive defaults and TW-062/TW-063 never applied to
    hotels at all.

    The one real defect this finds: 2026-07-sun-moon-lake candidate d2-6 is a
    cluster_fallback centroid with no existence proof (no official: true
    source, no gmaps_place_id), recorded verified, re-derives unverified. The
    id is asserted explicitly -- a bare count would stay green if a DIFFERENT
    candidate started failing instead.

    The other 18 findings are all on the rederivable axis, not the match axis:
    1 candidate omits geocode_source entirely (a second, pre-TW-062 gap on the
    same 2026-06-yilan hotel) and 0 of 18 carry resolved_name (the field is
    new in this release, so every candidate is missing it) -- 1 + 18 == 19.
    """
    found = compared = 0
    mismatches = []
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
        found += sum(len(stop.get("candidates") or [])
                     for stop in accommodations.get("stops") or [])
        compared += sum(1 for f in res["failures"]
                        if "recorded verify_status" in f)
        mismatches.extend(f for f in res["failures"] if "recorded verify_status" in f)
    assert found == 18
    assert len(mismatches) == 1, mismatches
    assert "'d2-6'" in mismatches[0] and "re-derives 'unverified'" in mismatches[0]
    assert "existence proof" in mismatches[0]

    missing_geocode_source = missing_resolved_name = 0
    for trip in IN_SCOPE:
        d = CORPUS / trip
        accommodations = yaml.safe_load(
            (d / "accommodations.yaml").read_text(encoding="utf-8"))
        res = run_rederivation({"days": []}, {}, legs={"legs": []},
                               routing={"clusters": [], "hops": []},
                               cost={"currency": "TWD", "line_items": [], "total": 0},
                               accommodations=accommodations)
        missing_geocode_source += sum("no geocode.geocode_source" in f
                                      for f in res["failures"])
        missing_resolved_name += sum("no resolved_name" in f for f in res["failures"])
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
    gmaps_place_id -- the exact shape measured at fd053dd for
    2026-07-sun-moon-lake candidate d2-6: recorded verified, no existence proof."""
    c = {"id": "d2-6", "name_local": "日月潭旅店", "name_display": "日月潭旅店",
         "sources": [{"url": "https://a.example/d2-6", "lang": "zh"},
                     {"url": "https://b.example/d2-6", "lang": "zh"}],
         "geocode": {"lat": 23.86, "lng": 120.91, "geocode_source": "cluster_fallback"},
         "verify_status": "verified"}
    c.update(over)
    return c


def test_a_cluster_fallback_lodging_candidate_with_no_existence_proof_fails_verdicts_match():
    res = run_rederivation(ITIN, {}, legs={"legs": []}, routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF, accommodations=_accom(_lodging_cand()))
    c = _checks(res)
    assert c["verdicts_match"]["passed"] is False
    assert any("d2-6" in f and "unverified" in f for f in res["failures"])


def test_a_lodging_candidate_with_an_official_source_still_passes():
    cand = _lodging_cand(sources=[{"url": "https://a.example/d2-6", "lang": "zh", "official": True},
                                  {"url": "https://b.example/d2-6", "lang": "zh"}])
    res = run_rederivation(ITIN, {}, legs={"legs": []}, routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF, accommodations=_accom(cand))
    assert _checks(res)["verdicts_match"]["passed"] is True


def test_lodging_with_no_geocode_source_is_not_rederivable():
    with_gs = _accom(_lodging_cand(geocode={"lat": 23.86, "lng": 120.91,
                                            "geocode_source": "nominatim"}))
    no_gs = _accom(_lodging_cand(geocode={"lat": 23.86, "lng": 120.91}))
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


def test_lodging_with_no_resolved_name_is_not_rederivable():
    cand = _lodging_cand(sources=[{"url": "https://a.example/d2-6", "lang": "zh", "official": True},
                                  {"url": "https://b.example/d2-6", "lang": "zh"}])
    res = run_rederivation(ITIN, {}, legs={"legs": []}, routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF, accommodations=_accom(cand))
    c = _checks(res)
    assert c["verdicts_rederivable"]["passed"] is False
    assert any("resolved_name" in f for f in res["failures"])
    # not demoted by the missing field: this candidate is otherwise 'verified'
    assert c["verdicts_match"]["passed"] is True


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
    #     poi_pool now" would be unfalsifiable prose. The fold adds exactly 5
    #     hotel ids the corpus's verified-pois.yaml files do not carry.
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
