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


CORPUS = pathlib.Path("/home/user/hp_workspace/tripwork-workspace/trips")
IN_SCOPE = ("2026-06-yilan", "2026-07-sun-moon-lake", "2026-08-chiayi",
            "2026-09-northeast-coast")


@pytest.mark.skipif(not CORPUS.is_dir(), reason="consumer corpus not present")
def test_real_trips_have_zero_verdicts_match_failures():
    """False-positive budget, measured at fd053dd before implementation.

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
    """The other axis, and the honest half of the budget: the same four trips
    have 19 verdicts_rederivable failures, one per hop, all of them
    'no duration_source'.

    This is a TRUE positive, not noise. Those hops were written before TW-066
    existed, so nothing recorded where their durations came from. Pinning the
    number means a future change that quietly widens or narrows the gap fails
    here instead of drifting.

    It is also the km/mode omission escape closing at the artifact layer: a hop
    that omits mode, or whose endpoint has no centroid, lands in this same list.
    Today the corpus omits neither, so all 19 failures are provenance ones.
    """
    total_missing = provenance_missing = 0
    for trip in IN_SCOPE:
        d = CORPUS / trip
        res = run_rederivation(
            {"days": []}, {},
            legs=yaml.safe_load((d / "legs.yaml").read_text(encoding="utf-8")),
            routing=yaml.safe_load((d / "routing.yaml").read_text(encoding="utf-8")),
            cost=yaml.safe_load((d / "cost.yaml").read_text(encoding="utf-8")),
            trip_brief=yaml.safe_load((d / "trip-brief.yaml").read_text(encoding="utf-8")))
        c = _checks(res)
        assert c["verdicts_rederivable"]["passed"] is False, trip
        assert c["verdicts_rederivable"]["examined"] == (
            len(yaml.safe_load((d / "legs.yaml").read_text(encoding="utf-8")).get("legs") or [])
            + len(yaml.safe_load((d / "routing.yaml").read_text(encoding="utf-8")).get("hops") or [])
            + 1), trip
        total_missing += len(res["failures"])
        provenance_missing += sum("no duration_source" in f for f in res["failures"])
    assert (total_missing, provenance_missing) == (19, 19)


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
    res = run_rederivation(itin, {"p1": poi}, legs={"legs": []},
                           routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF)
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
    res = run_rederivation(itin, {"p1": _poi()}, legs={"legs": []},
                           routing={"clusters": [], "hops": []},
                           cost={"currency": "TWD", "line_items": [], "total": 0},
                           trip_brief=BRIEF)
    c = _checks(res)
    assert c["verdicts_rederivable"]["passed"] is True
    # examined unchanged by the ghost row: legs=0 + hops=0 + cost=1(present,
    # filler) + closing=0 (all three itinerary rows are out of scope) == 1.
    assert c["verdicts_rederivable"]["examined"] == 1


@pytest.mark.skipif(not CORPUS.is_dir(), reason="consumer corpus not present")
def test_real_trips_closing_status_is_entirely_a_rederivable_gap():
    """Measured by the controller at fd053dd (task-2-brief.md's corrected table,
    2026-08-09 — the original draft conflated 'no hours at all' with the scope
    denominator and got 29 of 94; the real denominator is 58, not 94):

        94 itinerary rows total across the four schema-clean trips
      - 31 carry a `time` but no `poi_id` (move rows, free-text meals)
      -  5 carry a `poi_id` that does not resolve in verified-pois
      = 58 in scope (`time` AND a resolving `poi_id`)

    Of the 58: 24 POIs have no `hours` at all, 5 have `hours` but no `close`
    (29 total land on 'neither close nor no_fixed_close'), and every one of the
    remaining 29 lands on 'no recorded closing_status' -- 0 rows in the corpus
    carry a closing_status today, so verdicts_match never gets anything to
    compare. This is the honest half of the same budget Task 1 Step 8 pinned
    for legs/hops/cost: 58 verdicts_rederivable failures, 0 verdicts_match
    failures, 0 compared.
    """
    total = Outcome()
    rows_total = has_time_no_pid = unresolved_pid = 0
    for trip in IN_SCOPE:
        d = CORPUS / trip
        itin = yaml.safe_load((d / "itinerary.yaml").read_text(encoding="utf-8"))
        pois = yaml.safe_load((d / "verified-pois.yaml").read_text(encoding="utf-8"))
        by_id = {p["id"]: p for p in pois.get("pois") or []}
        for day in itin.get("days") or []:
            for row in day.get("rows") or []:
                rows_total += 1
                t, pid = row.get("time"), row.get("poi_id")
                if t and not pid:
                    has_time_no_pid += 1
                elif t and pid and pid not in by_id:
                    unresolved_pid += 1
        total.merge(rederive_closing(itin, by_id))
    assert (rows_total, has_time_no_pid, unresolved_pid) == (94, 31, 5)
    assert total.found == 58, "58 rows must be IN SCOPE, not skipped"
    assert len(total.missing) == 58
    assert len(total.mismatches) == 0
    assert total.compared == 0, "nothing is comparable while 0 rows carry closing_status"
