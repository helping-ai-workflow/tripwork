"""D3: stage-selection oracle — one fixture state per orchestrator rule."""
import os
import pathlib
import subprocess
import sys

import yaml

from scripts.orchestration import ADVISORY_PROJECTION, input_fingerprint
from tests.mech_fixtures import build_full_trip, write_artifact

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "next_stage.py"

# (artifact-to-remove-from-here-on, expected next) — walking backwards from full
WALK = [
    ("trip-brief.yaml", "tripwork:trip-brief"),
    ("advisory.yaml", "tripwork:travel-advisory"),          # rule 1.5 (D4)
    ("candidates.yaml", "tripwork:destination-research"),
    ("verified-pois.yaml", "tripwork:source-verify"),
    ("routing.yaml", "tripwork:routing-audit"),
    ("accommodations.yaml", "tripwork:accommodation-research"),
    ("legs.yaml", "tripwork:inter-stop-legs"),
    ("calendar.yaml", "tripwork:calendar-check"),
    ("seasonal.yaml", "tripwork:seasonal-advisory"),
    ("transit.yaml", "tripwork:transit-detail"),
    ("cost.yaml", "tripwork:cost-rollup"),
    ("itinerary.yaml", "tripwork:itinerary-synthesis"),
]

PASS_REPORT = {"status": "pass", "checks": [{"name": "x", "passed": True}],
               "failures": []}


def _next(t, w):
    r = subprocess.run(
        [sys.executable, str(CLI), str(t), "--work-dir", str(w)],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return yaml.safe_load(r.stdout)


def _bump(path, offset):
    st = os.stat(path)
    os.utime(path, (st.st_atime, st.st_mtime + offset))


def _full(tmp_path):
    t, w = build_full_trip(tmp_path)
    write_artifact(t / "gate-report.yaml", PASS_REPORT)
    write_artifact(t / "export-gate-report.yaml", PASS_REPORT)
    # deliverables/reports must be newer than their inputs
    _bump(t / "gate-report.yaml", 60)
    _bump(t / "export-gate-report.yaml", 120)
    return t, w


def _build_trip_through_cost(tmp_path):
    """Trip with every rule 1-10 chain artifact present and schema-valid —
    i.e. everything through cost.yaml — but no itinerary.yaml. That is the
    minimum fixture rule 11 needs: it is decided before rule 12 ever looks at
    the itinerary, so building further (gate-report, export) would be inert
    for these tests."""
    t, w = build_full_trip(tmp_path)
    (t / "itinerary.yaml").unlink()
    return t, w


def test_rule0_preflight(tmp_path):
    t, w = _full(tmp_path)
    (tmp_path / "work" / ".preflight-completed").unlink()
    assert _next(t, w)["next"] == "tripwork:workspace-shape-preflight"


def test_chain_missing_artifact_routes_to_producer(tmp_path):
    for name, expected in reversed(WALK):
        t, w = _full(tmp_path / name.replace(".", "_"))
        (t / name).unlink()
        got = _next(t, w)
        assert got["next"] == expected, f"removed {name}: {got}"


def test_schema_invalid_artifact_not_ready(tmp_path):
    t, w = _full(tmp_path)
    (t / "routing.yaml").write_text("clusters: []\n", encoding="utf-8")  # missing hops/warnings
    got = _next(t, w)
    assert got["next"] == "tripwork:routing-audit"
    assert "schema" in got["reason"]


def test_zero_verified_pois_not_ready(tmp_path):
    t, w = _full(tmp_path)
    write_artifact(t / "verified-pois.yaml", {"pois": [{
        "id": "poi-1", "name_local": "五稜郭", "name_display": "五稜郭",
        "category": "sight", "district": "函館",
        "sources": [{"url": "https://guide.example", "lang": "zh"}],
        "verify_status": "unverified", "status_reason": "single source"}]})
    assert _next(t, w)["next"] == "tripwork:source-verify"


def test_stale_candidates_reverify(tmp_path):
    t, w = _full(tmp_path)
    doc = yaml.safe_load((t / "candidates.yaml").read_text(encoding="utf-8"))
    doc["candidates"].append({"id": "poi-2", "name_local": "新店",
                              "name_display": "新店", "category": "food",
                              "sources": [{"url": "https://x.example"}]})
    write_artifact(t / "candidates.yaml", doc)
    assert _next(t, w)["next"] == "tripwork:source-verify"


def test_rule11_ignored_edit_does_not_derail_to_travel_advisory(tmp_path):
    """TW-067 migration, fix round 1 (was test_rule11_rebrief_re_runs_advisory,
    which encoded the pre-fix 'any mtime bump fires' behaviour; an interim
    revision fixed that but left it a near-duplicate of
    test_rule11_fires_when_the_destination_changes). Rule 11 itself decides
    identically regardless of fixture depth — it returns before rule 12 ever
    reads itinerary.yaml/gate-report.yaml/export-gate-report.yaml, so fixture
    depth cannot change which branch of rule 11 executes. What full depth CAN
    show, and the through-cost fixture cannot, is the actual dogfood scenario:
    a harmless-to-ADVISORY brief edit made AFTER an otherwise-COMPLETE pipeline
    (itinerary synthesized, both gates passed) must not derail it BACK TO
    TRAVEL-ADVISORY. test_rule11_ignores_a_must_do_edit cannot demonstrate this
    because its fixture never reaches 'complete' in the first place.

    trip-brief.yaml is bumped newer than advisory.yaml on purpose: under the
    pre-fix whole-file-mtime rule that alone would fire rule 11 and the
    pipeline would never reach 'complete', so this fixture also discriminates
    the fix the same way test_rule11_ignores_a_must_do_edit does.

    Task 7 migration (v0.33.0): this used to assert the whole pipeline stays
    'complete'. It no longer does, and that is CORRECT, not a regression —
    trip-brief.yaml is also a genuine `GATE_INPUTS` member now (the gate reads
    trip_brief for must_do_covered), and the edit above adds a real must_do
    item the already-passed gate-report never checked. The widened rule 13
    (mtime, report-tier — see scripts/orchestration.py::GATE_INPUTS) correctly
    routes back to itinerary-gate instead of silently reporting 'complete' on
    a report that never saw the new must_do. What must still hold, and is the
    actual point of this test, is that it does NOT go to travel-advisory."""
    t, w = _full(tmp_path)
    brief = yaml.safe_load((t / "trip-brief.yaml").read_text(encoding="utf-8"))
    fp = input_fingerprint(brief, ADVISORY_PROJECTION)
    adv = yaml.safe_load((t / "advisory.yaml").read_text(encoding="utf-8"))
    adv["input_fingerprints"] = {"trip-brief.yaml": fp}
    write_artifact(t / "advisory.yaml", adv)

    brief["must_do"] = ["雞肉飯", "花磚"]
    write_artifact(t / "trip-brief.yaml", brief)
    _bump(t / "trip-brief.yaml", 3600)           # rewritten well after advisory

    got = _next(t, w)
    assert got["next"] != "tripwork:travel-advisory", got["reason"]
    # And: the widened rule 13 is what actually fires, not some other rule.
    assert got["next"] == "tripwork:itinerary-gate", got["reason"]
    assert "trip-brief.yaml" in got["reason"]


def test_rule11_ignores_a_must_do_edit(tmp_path):
    """TW-067: dogfood edited trip-brief 3 times and rewrote a byte-identical
    277-byte advisory each time, updating only its mtime. That teaches the
    agent to satisfy an oracle by touching a file — and rules 13/15 have
    mtimes that really are load-bearing."""
    t, w = _build_trip_through_cost(tmp_path)
    brief = yaml.safe_load((t / "trip-brief.yaml").read_text(encoding="utf-8"))
    fp = input_fingerprint(brief, ADVISORY_PROJECTION)
    write_artifact(t / "advisory.yaml",
                   {"items": [], "input_fingerprints": {"trip-brief.yaml": fp}})

    brief["must_do"] = ["雞肉飯", "花磚"]
    write_artifact(t / "trip-brief.yaml", brief)
    _bump(t / "trip-brief.yaml", 3600)

    got = _next(t, w)
    assert got["next"] != "tripwork:travel-advisory", got["reason"]


def test_rule11_fires_when_the_destination_changes(tmp_path):
    """Fix round 1: advisory.yaml is bumped provably NEWER than trip-brief.yaml
    (not the reverse) so the old whole-file-mtime rule would read this as
    "not stale". The only way this test can still fire is the content check —
    proving the trigger is the fingerprint mismatch, not mtime."""
    t, w = _build_trip_through_cost(tmp_path)
    brief = yaml.safe_load((t / "trip-brief.yaml").read_text(encoding="utf-8"))
    fp = input_fingerprint(brief, ADVISORY_PROJECTION)
    write_artifact(t / "advisory.yaml",
                   {"items": [], "input_fingerprints": {"trip-brief.yaml": fp}})

    brief["destination"]["city"] = "台南市"
    write_artifact(t / "trip-brief.yaml", brief)
    _bump(t / "advisory.yaml", 999999)           # advisory provably newer

    got = _next(t, w)
    assert got["next"] == "tripwork:travel-advisory"
    assert "rule 11" in got["reason"]


def test_rule11_ignores_a_bare_touch(tmp_path):
    t, w = _build_trip_through_cost(tmp_path)
    brief = yaml.safe_load((t / "trip-brief.yaml").read_text(encoding="utf-8"))
    fp = input_fingerprint(brief, ADVISORY_PROJECTION)
    write_artifact(t / "advisory.yaml",
                   {"items": [], "input_fingerprints": {"trip-brief.yaml": fp}})
    _bump(t / "trip-brief.yaml", 3600)           # rewritten, but content unchanged

    got = _next(t, w)
    assert got["next"] != "tripwork:travel-advisory"


def test_rule11_still_fires_when_no_fingerprint_was_recorded(tmp_path):
    """Fail-OPEN would be wrong here: an advisory with no fingerprint predates
    the mechanism, and rule 11 is the safety gate that surfaces a `banned`
    regulation. Fall back to the old mtime comparison."""
    t, w = _build_trip_through_cost(tmp_path)
    write_artifact(t / "advisory.yaml", {"items": []})
    _bump(t / "trip-brief.yaml", 3600)

    got = _next(t, w)
    assert got["next"] == "tripwork:travel-advisory"
    assert "rule 11" in got["reason"]


def test_rule13_itinerary_newer_than_gate_report(tmp_path):
    t, w = _full(tmp_path)
    _bump(t / "itinerary.yaml", 600)             # regenerated after gate ran
    assert _next(t, w)["next"] == "tripwork:itinerary-gate"


def test_rule13_5_fail_routes_synthesis(tmp_path):
    t, w = _full(tmp_path)
    write_artifact(t / "gate-report.yaml", {
        "status": "fail", "checks": [{"name": "days_have_meals", "passed": False}],
        "failures": ["day 2026-08-01 has no meal"]})
    _bump(t / "gate-report.yaml", 60)
    assert _next(t, w)["next"] == "tripwork:itinerary-synthesis"


def test_rule13_5_lodging_fail_routes_accommodation(tmp_path):
    t, w = _full(tmp_path)
    write_artifact(t / "gate-report.yaml", {
        "status": "fail",
        "checks": [{"name": "overnight_stops_have_lodging", "passed": False}],
        "failures": ["overnight stop '函館' has no chosen lodging"]})
    _bump(t / "gate-report.yaml", 60)
    assert _next(t, w)["next"] == "tripwork:accommodation-research"


def test_rule13_corrupt_gate_report_reruns_gate(tmp_path):
    t, w = _full(tmp_path)
    (t / "gate-report.yaml").write_text("status: fail\n  bad indent: [\n",
                                        encoding="utf-8")
    _bump(t / "gate-report.yaml", 60)
    got = _next(t, w)
    assert got["next"] == "tripwork:itinerary-gate"
    assert "rule 13" in got["reason"]


def test_rule13_bogus_status_gate_report_reruns_gate(tmp_path):
    t, w = _full(tmp_path)
    write_artifact(t / "gate-report.yaml", {
        "status": "bogus", "checks": [], "failures": []})
    _bump(t / "gate-report.yaml", 60)
    got = _next(t, w)
    assert got["next"] == "tripwork:itinerary-gate"
    assert "rule 13" in got["reason"]


def test_rule15_corrupt_export_gate_report_reruns_gate(tmp_path):
    t, w = _full(tmp_path)
    (t / "export-gate-report.yaml").write_text(
        "status: fail\n  bad indent: [\n", encoding="utf-8")
    _bump(t / "export-gate-report.yaml", 120)
    got = _next(t, w)
    assert got["next"] == "tripwork:export-gate"


def test_rule15_bogus_status_export_gate_report_reruns_gate(tmp_path):
    t, w = _full(tmp_path)
    write_artifact(t / "export-gate-report.yaml", {
        "status": "bogus", "checks": [], "failures": []})
    _bump(t / "export-gate-report.yaml", 120)
    got = _next(t, w)
    assert got["next"] == "tripwork:export-gate"


def test_rule15_retryable_fail_rerenders(tmp_path):
    t, w = _full(tmp_path)
    write_artifact(t / "export-gate-report.yaml", {
        "status": "fail", "retryable": True, "distributable": True,
        "checks": [{"name": "no_naked_dollar", "passed": False}],
        "failures": ["naked '$' found; prices must be escaped as '\\$'"]})
    _bump(t / "export-gate-report.yaml", 120)
    assert _next(t, w)["next"] == "tripwork:export-artifact"


def test_rule15_nonretryable_fail_stops(tmp_path):
    t, w = _full(tmp_path)
    write_artifact(t / "export-gate-report.yaml", {
        "status": "fail", "retryable": False, "distributable": True,
        "checks": [{"name": "photo_has_attribution", "passed": False}],
        "failures": ["photo for 'poi-1' missing attribution"]})
    _bump(t / "export-gate-report.yaml", 120)
    got = _next(t, w)
    assert got["next"] == "stop-and-ask"


def test_rule16_complete_and_nondistributable_label(tmp_path):
    t, w = _full(tmp_path)
    assert _next(t, w)["next"] == "complete"
    write_artifact(t / "export-gate-report.yaml", {
        "status": "pass", "retryable": True, "distributable": False,
        "checks": [{"name": "no_nondistributable_photo_source", "passed": False}],
        "failures": []})
    _bump(t / "export-gate-report.yaml", 120)
    got = _next(t, w)
    assert got["next"] == "complete" and "勿散布" in got["reason"]


def test_corrupt_scalar_report_routes_back_to_gate(tmp_path):   # v0.30.0 backlog (a)
    # A report file that parses as a YAML scalar (not a dict) — e.g. truncated to
    # the bare word `status` — must route back to the producing gate, not crash.
    t, w = _full(tmp_path)
    (t / "gate-report.yaml").write_text("status", encoding="utf-8")
    _bump(t / "gate-report.yaml", 60)
    got = _next(t, w)
    assert got["next"] == "tripwork:itinerary-gate"


def test_rule13_reruns_the_gate_when_any_gate_input_is_newer(tmp_path):
    """Red at HEAD: rule 13 compares gate-report against itinerary.yaml only, so
    a re-verify that demotes a scheduled POI leaves the oracle reporting
    'complete' on a report that never saw it. Measured on the real corpus: four
    such gaps across four trips, all true positives (e.g. yilan's
    verified-pois.yaml is 527 seconds newer than the gate-report that
    supposedly gated it)."""
    t, w = _full(tmp_path)
    assert _next(t, w)["next"] == "complete"

    _bump(t / "verified-pois.yaml", 999999)   # re-verify after the gate ran
    got = _next(t, w)
    assert got["next"] == "tripwork:itinerary-gate", got["reason"]
    assert "rule 13" in got["reason"]


def test_rule15_reruns_the_export_gate_when_any_export_gate_input_is_newer(tmp_path):
    """Same widening applied to rule 15 against EXPORT_GATE_INPUTS. Measured 0
    extra fires on the real corpus (unlike rule 13's 4), but the predicate is
    exercised here with verified-pois-media.yaml specifically because it is the
    one EXPORT_GATE_INPUTS member that is NOT also in GATE_INPUTS — bumping any
    of the other three would make rule 13 fire first and this test would never
    reach rule 15 at all."""
    t, w = _full(tmp_path)
    assert _next(t, w)["next"] == "complete"

    write_artifact(t / "verified-pois-media.yaml", {"media": {}})
    _bump(t / "verified-pois-media.yaml", 999999)
    got = _next(t, w)
    assert got["next"] == "tripwork:export-gate", got["reason"]
    assert "rule 15" in got["reason"]
