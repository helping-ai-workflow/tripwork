"""v1.0 P3 — both gate CLIs read data/ and write their reports into work/<slug>/."""
import pathlib
import shutil
import subprocess
import sys

from scripts.paths import report_path, work_dir_for
from tests.mech_fixtures import build_full_trip

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _run(cli, t):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / cli), str(t)],
                          capture_output=True, text=True)


def test_gate_writes_its_report_into_work(tmp_path):
    t, w = build_full_trip(tmp_path)
    r = _run("gate.py", t)
    assert r.returncode == 0, r.stdout + r.stderr
    assert report_path(w, "gate-report.yaml").is_file()
    assert not (t / "gate-report.yaml").exists()


def test_export_gate_reads_the_stem_deliverables_and_writes_into_work(tmp_path):
    t, w = build_full_trip(tmp_path)
    r = _run("export_gate.py", t)
    assert r.returncode == 0, r.stdout + r.stderr
    assert report_path(w, "export-gate-report.yaml").is_file()
    assert not (t / "export-gate-report.yaml").exists()


def test_the_cli_creates_the_work_dir(tmp_path):
    t, w = build_full_trip(tmp_path)
    shutil.rmtree(work_dir_for(t))
    assert _run("gate.py", t).returncode == 0
    assert report_path(work_dir_for(t), "gate-report.yaml").is_file()
