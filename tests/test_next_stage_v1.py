"""v1.0 P3 — next_stage reads data/, compares reports in work/, names deliverables by stem."""
import os
import time

import yaml

from scripts.next_stage import next_stage
from scripts.paths import artifact_path, deliverable_paths, report_path
from tests.mech_fixtures import build_full_trip, write_artifact


def _gate_and_export(t, w):
    import subprocess, sys, pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    for cli in ("gate.py", "export_gate.py"):
        subprocess.run([sys.executable, str(root / "scripts" / cli), str(t)], check=False,
                       capture_output=True, text=True)


def test_a_full_v1_trip_completes(tmp_path):
    t, w = build_full_trip(tmp_path)
    _gate_and_export(t, w)
    assert report_path(w, "gate-report.yaml").is_file()
    assert not (t / "gate-report.yaml").exists()
    nxt, why = next_stage(t, w)
    assert nxt == "complete", why


def test_a_legacy_layout_stops_for_migration(tmp_path):
    t, w = build_full_trip(tmp_path)
    for p in sorted((t / "data").iterdir()):
        p.rename(t / p.name)
    (t / "data").rmdir()
    nxt, why = next_stage(t, w)
    assert nxt == "stop-and-ask" and "migrate_v1.py" in why


def test_an_edited_artifact_makes_the_work_report_stale(tmp_path):
    t, w = build_full_trip(tmp_path)
    _gate_and_export(t, w)
    later = time.time() + 5
    os.utime(artifact_path(t, "itinerary.yaml"), (later, later))
    nxt, why = next_stage(t, w)
    assert nxt == "tripwork:itinerary-gate" and "itinerary.yaml" in why


def test_a_missing_stem_deliverable_routes_to_export(tmp_path):
    t, w = build_full_trip(tmp_path)
    _gate_and_export(t, w)
    brief = yaml.safe_load(artifact_path(t, "trip-brief.yaml").read_text(encoding="utf-8"))
    deliverable_paths(t, brief)["md"].unlink()
    nxt, _ = next_stage(t, w)
    assert nxt == "tripwork:export-artifact"


def test_a_brief_without_short_name_routes_to_trip_brief(tmp_path):
    t, w = build_full_trip(tmp_path)
    _gate_and_export(t, w)
    p = artifact_path(t, "trip-brief.yaml")
    brief = yaml.safe_load(p.read_text(encoding="utf-8"))
    brief.pop("short_name")
    write_artifact(p, brief)
    # the gate report is now stale (brief newer) -> rule 13 first; fake a fresh report
    later = time.time() + 5
    os.utime(artifact_path(t, "advisory.yaml"), (later, later))   # keep rule 11 quiet
    for name in ("gate-report.yaml", "export-gate-report.yaml"):
        os.utime(report_path(w, name), (later, later))
    nxt, why = next_stage(t, w)
    assert nxt == "tripwork:trip-brief", why
