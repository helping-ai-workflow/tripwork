"""D3: stage-selection oracle — one fixture state per orchestrator rule."""
import os
import pathlib
import subprocess
import sys

import yaml

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


def test_rule11_rebrief_re_runs_advisory(tmp_path):
    t, w = _full(tmp_path)
    _bump(t / "trip-brief.yaml", 3600)           # re-briefed after advisory
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
