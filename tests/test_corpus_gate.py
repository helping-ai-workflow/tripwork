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

量測機件（CLASSES / classify / gate / drain / FIX）住在 tests/corpus_measure.py，
與產生 tests/corpus-baseline.json 的那條路徑共用同一份（TW-074）。
"""
import pytest

from scripts.orchestration import route_gate_failures
from tests.mech_fixtures import CORPUS, CORPUS_TRIPS, load_trip
from tests.corpus_measure import CLASSES, FIX, classify, drain, gate
from tests.corpus_measure import load_baseline

pytestmark = pytest.mark.skipif(not CORPUS.is_dir(),
                                reason="consumer corpus not present")

# TW-074: every corpus-derived number below is read from the regenerable
# tests/corpus-baseline.json (produced by `python -m tests.corpus_measure
# --write`), not hand-copied into this file. Only structural invariants --
# properties that must hold no matter what the corpus looks like -- stay
# inline: classes must partition failures, axis ids must be a subset of
# their own artifact's raw ids, the drain must terminate.
BASELINE = load_baseline()


@pytest.mark.parametrize("trip", CORPUS_TRIPS)
def test_the_real_gate_over_a_clean_trip_pins_its_failure_classes(trip):
    """I6: all five re-derivation axes, the AI-tone gate and the home-leg check
    running together through the SHIPPED run_gate — the pool built by the real
    P4 fold, not a hand-rolled one.

    The per-class counts are pinned rather than the bare total: a total alone
    stays green when one class silently doubles while another silently empties,
    which is how a gate stops examining things without anyone noticing.

    TW-074: counts are read from tests/corpus-baseline.json (regenerable), no
    longer literals in this file. The partition property (classes must sum to
    total) is an invariant and stays here.
    """
    expected = BASELINE["per_trip"][trip]
    report = gate(load_trip(trip))
    assert report["status"] == expected["status"]
    assert classify(report["failures"]) == expected["classes"]
    assert len(report["failures"]) == expected["total"]
    assert sum(expected["classes"].values()) == expected["total"], \
        "the classes must PARTITION the failures"


def test_the_six_axes_together_pin_the_release_headline_figures():
    """The aggregate the CHANGELOG's Migration section quotes, read back off the
    same run_gate reports rather than from a separate hand-driven
    run_rederivation — the divergence C1 turned on.

    Re-measured for v0.34.0 Task 6 (real Gate 0 threaded into rederive_lodging,
    Gate 2c retired). `found` (verdict-bearing records) is UNCHANGED by Task 6:
    Task 6 reclassifies lodging findings between buckets, it does not add or
    remove records to examine. `compared` DROPS at Task 6, because every
    lodging candidate that used to reach a comparison (the TW-070 baseline
    included 2026-07-sun-moon-lake's `d2-6`, a cluster_fallback centroid with
    no existence proof) now lands in `superseded` before classify_candidate
    ever runs, since none of them carries a sourced business_status -- there
    is no `operating` value left to compare with. That is also why the
    exactly-one-mismatch claim TW-070 pinned here is gone: this corpus can
    have ZERO verdicts_match mismatches left on any axis (`match_failed`
    empty), not because `d2-6` was fixed, but because its defect moved from
    "wrong verdict" to "verdict produced under rules this release supersedes"
    -- a different, more precise claim about the same record (pinned by id in
    tests/test_rederive.py::test_real_trips_lodging_axis_matches_the_baseline).

    The sixth axis's OWN headline number is the third assertion:
    `examined_rule_current` (POI-found + lodging-found, by id count, Step 4a)
    against how many of those land in `superseded` (verdicts_rule_current) --
    Task 6 moved both the numerator (lodging candidates newly counted) and
    the denominator (`examined` now sums poi_outcome.found +
    lodging_outcome.found, not poi_outcome.found alone) at once, so neither
    reads as a bare regression against the pre-Task-6 figures. A change that
    moved findings between trips while preserving the sums would pass
    unnoticed if only a total were pinned, so the totals are pinned here
    explicitly, counted the same way _classify already counts each trip's
    failures by class -- what those totals equal today lives in
    tests/corpus-baseline.json, read below, not in this docstring.

    TW-074: the totals above and the per-trip `checks_passed` comparison
    below are both read from tests/corpus-baseline.json rather than hand-
    copied literals. The per-trip loop used to assert
    `checks["verdicts_rederivable"]["passed"] is False` and
    `checks["verdicts_rule_current"]["passed"] is False` directly -- an
    assumption that the corpus always has a gap on those two axes, which
    2026-08-chiayi has already disproved. That is replaced by a dict
    equality against the baseline's `checks_passed`, which covers every
    check by name, not just those two.
    """
    found = compared = examined_rule_current = 0
    super_poi = super_lodging = 0
    match_failed = []
    for trip in CORPUS_TRIPS:
        report = gate(load_trip(trip))
        checks = {c["name"]: c for c in report["checks"]}
        found += checks["verdicts_rederivable"]["examined"]
        compared += checks["verdicts_match"]["examined"]
        examined_rule_current += checks["verdicts_rule_current"]["examined"]
        classes = classify(report["failures"])
        super_poi += classes.get("poi_verdict_superseded", 0)
        super_lodging += classes.get("lodging_verdict_superseded", 0)
        if not checks["verdicts_match"]["passed"]:
            match_failed.append(trip)
        assert {c["name"]: bool(c["passed"]) for c in report["checks"]} == \
            BASELINE["per_trip"][trip]["checks_passed"], trip
    agg = BASELINE["gate_aggregate"]
    assert (found, compared) == (agg["found"], agg["compared"])
    assert (super_poi, super_lodging) == (agg["super_poi"], agg["super_lodging"])
    assert examined_rule_current == agg["examined_rule_current"], \
        "Step 4a: poi_outcome.found + lodging_outcome.found"
    assert match_failed == agg["match_failed"]


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

    TW-074: the non-emptiness assertions are replaced by equality against the
    baseline. A trip legitimately having zero POI-axis findings (chiayi, once
    the consumer's business_status is sourced) is no longer a failure; a
    vacuous subset check is caught by the baseline's count instead.
    """
    for trip in CORPUS_TRIPS:
        a = load_trip(trip)
        report = gate(a)
        raw_poi_ids = {p.get("id") for p in a["pois"]["pois"]}
        raw_lodging_ids = {c.get("id")
                           for stop in (a["accommodations"] or {}).get("stops") or []
                           for c in stop.get("candidates") or []}
        poi_ids = {f.split("'")[1] for f in report["failures"] if f.startswith("pois[")}
        lodging_ids = {f.split("'")[3] for f in report["failures"]
                       if f.startswith("accommodations ")}
        per = BASELINE["per_trip"][trip]
        assert len(poi_ids) == per["poi_axis_findings"], trip
        assert len(lodging_ids) == per["lodging_axis_findings"], trip
        # Invariant: neither axis's failures may name an id that is not a
        # genuine member of ITS OWN artifact.
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
    report = gate(load_trip(trip))
    for f in report["failures"]:
        if "carries neither hours.close" in f:
            assert route_gate_failures([f]) == "tripwork:source-verify", f
        if "AI-tone " in f:
            assert route_gate_failures([f]) == "tripwork:itinerary-synthesis", f


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
    terminated, history = drain(trip)
    assert terminated, f"{trip} did not drain: {history}"
    assert history[-1] == 0
    assert history[0] == BASELINE["per_trip"][trip]["total"]


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
    terminated, history = drain("2026-06-yilan")
    cf = BASELINE["counterfactual"]
    assert terminated is cf["yilan_without_source_verify_terminated"]
    # A genuine fixed point, not merely slow progress: the tail repeats.
    assert history[-1] == history[-2] == cf["yilan_without_source_verify_fixed_point"]
    assert history[-1] > 0
