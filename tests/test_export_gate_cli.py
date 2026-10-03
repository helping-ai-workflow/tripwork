"""D2: export-gate CLI merges media itself, gates md+html, writes the report."""
import pathlib
import subprocess
import sys

import yaml

from scripts.validate_artifact import validate_file
from tests.mech_fixtures import trip_brief, build_full_trip, write_artifact
from scripts.paths import artifact_path, deliverable_paths, report_path, work_dir_for

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "export_gate.py"


def _run(trip_dir):
    return subprocess.run([sys.executable, str(CLI), str(trip_dir)],
                          capture_output=True, text=True)


def _report(t):
    return yaml.safe_load((report_path(work_dir_for(t), "export-gate-report.yaml")).read_text(encoding="utf-8"))


def test_pass_writes_valid_report(tmp_path):
    t, _ = build_full_trip(tmp_path)
    r = _run(t)
    assert r.returncode == 0, r.stderr + r.stdout
    rep = _report(t)
    assert rep["status"] == "pass" and rep["retryable"] is True
    assert validate_file(report_path(work_dir_for(t), "export-gate-report.yaml"))[0] == 0


def test_naked_dollar_fails_retryable(tmp_path):
    t, _ = build_full_trip(tmp_path)
    md = deliverable_paths(t, trip_brief())["md"]
    md.write_text(md.read_text(encoding="utf-8") + "\n門票 $120 很划算\n",
                  encoding="utf-8")
    r = _run(t)
    assert r.returncode == 1
    rep = _report(t)
    assert rep["retryable"] is True          # render-fixable → re-render loop OK


def test_media_present_but_zero_img_fails(tmp_path):
    t, _ = build_full_trip(tmp_path)
    write_artifact(artifact_path(t, "verified-pois-media.yaml"), {"media": {"poi-1": {
        "photo": "https://img.example/goryokaku.jpg",
        "photo_attribution": {"author": "a", "license": "CC-BY-4.0",
                              "source_url": "https://img.example/page"},
        "photo_source": "wiki"}}})
    # html deliverable has 0 <img> — the P8 dropped-apply_media case
    r = _run(t)
    assert r.returncode == 1
    assert any("0 photos" in f for f in _report(t)["failures"])


def test_photo_without_attribution_fails_nonretryable(tmp_path):
    t, _ = build_full_trip(tmp_path)
    write_artifact(artifact_path(t, "verified-pois-media.yaml"), {"media": {"poi-1": {
        "photo": {"data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="}, "photo_source": "wiki"}}})
    html = deliverable_paths(t, trip_brief())["html"]
    html.write_text(html.read_text(encoding="utf-8")
                    + '<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==">',
                    encoding="utf-8")
    r = _run(t)
    assert r.returncode == 1
    rep = _report(t)
    assert rep["retryable"] is False         # DATA defect → stop-and-ask


def test_missing_deliverable_exits_two(tmp_path):
    t, _ = build_full_trip(tmp_path)
    (deliverable_paths(t, trip_brief())["md"]).unlink()
    assert _run(t).returncode == 2


def test_malformed_optional_artifact_exits_two_without_report(tmp_path):
    t, _ = build_full_trip(tmp_path)
    (artifact_path(t, "accommodations.yaml")).write_text(
        "stops:\n  bad indent: [\n", encoding="utf-8")
    (report_path(work_dir_for(t), "export-gate-report.yaml")).unlink(missing_ok=True)
    r = _run(t)
    assert r.returncode == 2, r.stderr + r.stdout
    assert not (report_path(work_dir_for(t), "export-gate-report.yaml")).exists()
