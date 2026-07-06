# tests/test_gate_cli.py
"""D2: gate CLI loads the trip dir itself, writes gate-report.yaml, exits 0/1/2."""
import pathlib
import subprocess
import sys

import yaml

from scripts.validate_artifact import validate_file
from tests.mech_fixtures import build_full_trip, write_artifact, itinerary

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "gate.py"


def _run(trip_dir):
    return subprocess.run([sys.executable, str(CLI), str(trip_dir)],
                          capture_output=True, text=True)


def test_pass_writes_valid_report_and_exits_zero(tmp_path):
    t, _ = build_full_trip(tmp_path)
    r = _run(t)
    assert r.returncode == 0, r.stderr + r.stdout
    report = yaml.safe_load((t / "gate-report.yaml").read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert validate_file(t / "gate-report.yaml")[0] == 0


def test_fail_writes_report_and_exits_one(tmp_path):
    t, _ = build_full_trip(tmp_path)
    doc = itinerary()
    doc["days"][0]["rows"] = [r for r in doc["days"][0]["rows"]
                              if r["slot"] != "meal"]          # day loses its meal
    write_artifact(t / "itinerary.yaml", doc)
    r = _run(t)
    assert r.returncode == 1
    report = yaml.safe_load((t / "gate-report.yaml").read_text(encoding="utf-8"))
    assert report["status"] == "fail"
    assert any("no meal" in f for f in report["failures"])


def test_missing_required_artifact_exits_two_without_report(tmp_path):
    t, _ = build_full_trip(tmp_path)
    (t / "verified-pois.yaml").unlink()
    (t / "gate-report.yaml").unlink(missing_ok=True)
    r = _run(t)
    assert r.returncode == 2
    assert not (t / "gate-report.yaml").exists()


def test_malformed_optional_artifact_exits_two_without_report(tmp_path):
    t, _ = build_full_trip(tmp_path)
    (t / "calendar.yaml").write_text("closed_days:\n  bad indent: [\n",
                                     encoding="utf-8")
    (t / "gate-report.yaml").unlink(missing_ok=True)
    r = _run(t)
    assert r.returncode == 2, r.stderr + r.stdout
    assert not (t / "gate-report.yaml").exists()


def test_null_pois_exits_two_without_report(tmp_path):
    t, _ = build_full_trip(tmp_path)
    doc = yaml.safe_load((t / "verified-pois.yaml").read_text(encoding="utf-8"))
    doc["pois"] = None
    write_artifact(t / "verified-pois.yaml", doc)
    (t / "gate-report.yaml").unlink(missing_ok=True)
    r = _run(t)
    assert r.returncode == 2, r.stderr + r.stdout
    assert not (t / "gate-report.yaml").exists()


def test_missing_advisory_fails_gate_not_usage(tmp_path):
    # advisory is a mandatory GATE input (advisory_present floor) — its absence
    # is a gate FAIL (exit 1), not a usage error.
    t, _ = build_full_trip(tmp_path)
    (t / "advisory.yaml").unlink()
    r = _run(t)
    assert r.returncode == 1
    report = yaml.safe_load((t / "gate-report.yaml").read_text(encoding="utf-8"))
    assert any("advisory" in f for f in report["failures"])
