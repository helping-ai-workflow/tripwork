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
    Gate 2c retired). `found` (verdict-bearing records) is UNCHANGED by Task 6
    (Task 6 reclassifies lodging findings; it does not add or remove records
    to examine). compared moved from 69 (TW-070): most of the 18 lodging
    candidates that used to reach a comparison (17 matching + 1 mismatching,
    d2-6) now land in `superseded` before classify_candidate ever runs, since
    most do not carry a sourced business_status -- there is no `operating`
    value left to compare with for those (a candidate that does carry one
    stays in `compared`, same as any POI). What `compared` reads as today,
    corpus-wide across every axis, is in tests/corpus-baseline.json's
    gate_aggregate.compared below, not pinned in this docstring. That is also
    why the exactly-one-mismatch
    claim TW-070 pinned here is gone: this corpus has ZERO verdicts_match
    mismatches left on any axis (match_failed is empty), not because d2-6 was
    fixed, but because its defect moved from "wrong verdict" to "verdict
    produced under rules this release supersedes" -- a different, more
    precise claim about the same record (pinned by id in
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

    F11 (v0.35.0 review): the loop below is a DELIBERATE second
    implementation of tests/corpus_measure.py::_measure_gate_aggregate --
    kept as its own hand-written walk on purpose, not refactored to call that
    helper, because it is the ONLY cross-check that _measure_gate_aggregate
    itself computes correctly. Calling it from here instead would compare
    load_baseline()'s baked-in copy against itself -- green regardless of
    whether the aggregation logic is right. Do not fold this into a shared
    helper with corpus_measure.py.
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

    F11 (v0.35.0 review): `poi_ids`/`lodging_ids` below is a DELIBERATE second
    implementation of tests/corpus_measure.py::_axis_ids's identical string
    split (that helper's own docstring says as much: "切法與
    test_the_three_verdict_axes_partition_their_failures 原本的一致"). It is
    kept as its own literal here, not imported, because it is the ONLY
    cross-check that _axis_ids parses failure strings correctly -- calling
    _axis_ids from here would let a parsing bug in _axis_ids agree with
    itself via load_baseline()'s baked-in copy. Do not replace this with a
    call to _axis_ids.
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
def test_a_trips_failure_list_is_empty_only_when_the_baseline_says_so(trip):
    """C2's corpus-coupled half only: a clean trip really has zero failures
    on the real gate, and a dirty one really has some.

    G5 (v0.35.0 review wave 2): the ROUTING invariant this test used to check
    inline -- "the field a failure names must be writable by the stage it
    routes to" -- moved to
    tests/test_orchestration.py::test_every_corpus_measure_class_routes_to_the_stage_that_can_write_it.
    That version is corpus-INDEPENDENT (parametrized over
    tests/corpus_measure.py's CLASSES, not over CORPUS_TRIPS): for every
    marker CLASSES uses to classify a real failure message, it builds ONE
    genuine failure message by calling the real production re-derivation
    entrypoint (run_rederivation / ai_tone_failures) against a tiny synthetic
    fixture, then asserts route_gate_failures on that real message lands on
    the stage that owns the field. Leaving it here, parametrized per-trip,
    was strictly weaker: a trip only exercises whichever classes its OWN
    corpus data happens to produce today, so a class the corpus never
    triggers got zero routing coverage -- 2026-08-chiayi (today's one clean
    trip) iterated an EMPTY `report["failures"]` here and asserted nothing
    about routing at all, which the reviewer proved: the two `if` checks that
    used to live in this loop were also logically implied by nothing else in
    this file, and the F4 fix below (asserting the list's emptiness) did not
    change that -- injecting a bug that silently swallows the whole
    poi_no_hours failure class and regenerating the baseline left this whole
    file green.

    What is left here is genuinely corpus-coupled and worth its own test:
    does a CLEAN trip's real gate report an empty failure list, and does a
    DIRTY trip's list stay non-empty, exactly as the baseline recorded.
    """
    report = gate(load_trip(trip))
    # F4 (v0.35.0 review, wave 1): a clean trip (today: 2026-08-chiayi) used
    # to leave this test's loop body dead code (zero real failures, zero
    # assertions) -- asserting the list's emptiness against the baseline is
    # what gives that parametrized instance something to check.
    assert (report["failures"] == []) == (BASELINE["per_trip"][trip]["total"] == 0), trip


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
    # F10 (v0.35.0 review), corrected (G6, wave 2): this assertion is a
    # DIAGNOSTIC against a hand-edited baseline, not coverage of drain()
    # itself -- both `history` (computed above) and `drain_rounds` (baked
    # into the baseline) come from the SAME drain() helper on the SAME trip,
    # so a bug IN drain() moves both sides together and this equality cannot
    # see it: the reviewer broke drain() itself (`return True, history +
    # [0]`), regenerated the baseline, and this test still passed. That blind
    # spot is inherent to the baseline architecture -- CLAUDE.md's rule (d)
    # (commit the regenerated diff for human review) is the control here, not
    # a test; do not try to engineer a mechanical guard that cannot exist.
    # What this assertion DOES catch: a HAND-edited baseline value that no
    # longer matches what a fresh drain() run on this trip produces --
    # exactly what test_baseline_matches_a_fresh_measurement checks in bulk
    # across every field, given here as a second, narrower assertion site
    # scoped to this one figure.
    assert len(history) == BASELINE["per_trip"][trip]["drain_rounds"], trip
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
