# tests/test_e2e_mechanized_pipeline.py
"""v0.29.0 e2e closure: every mechanized CLI over ONE fixture trip, plus the
full next_stage walk in the NEW stage order (advisory before research).

Deviation from the design spec (2026-07-06-tripwork-mechanized-gates-design.md
§9): the gate-CLI fail case (see tests/test_gate_cli.py) exercises a no-meal
defect instead of the spec's unglossed-kana row, because a schema-valid
unglossed-kana verified POI cannot be constructed — verified-pois.schema.json's
allOf forces the lodging path, which hits the known name_zh gap. The no-meal
defect exercises the same gate-report fail/exit-1 contract without that
construction problem."""
import pathlib
import subprocess
import sys

import yaml

from scripts.validate_artifact import validate_file
from tests.mech_fixtures import (SLUG, build_full_trip, write_artifact,
                                 trip_brief, advisory, candidates,
                                 verified_pois, routing, accommodations,
                                 legs, calendar, seasonal, transit, cost,
                                 itinerary, MD_DELIVERABLE, HTML_DELIVERABLE)

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

EXPECTED_WALK = [
    (None, "tripwork:workspace-shape-preflight"),
    ("stamp", "tripwork:trip-brief"),
    ("trip-brief.yaml", "tripwork:travel-advisory"),
    ("advisory.yaml", "tripwork:destination-research"),
    ("candidates.yaml", "tripwork:source-verify"),
    ("verified-pois.yaml", "tripwork:routing-audit"),
    ("routing.yaml", "tripwork:accommodation-research"),
    ("accommodations.yaml", "tripwork:inter-stop-legs"),
    ("legs.yaml", "tripwork:calendar-check"),
    ("calendar.yaml", "tripwork:seasonal-advisory"),
    ("seasonal.yaml", "tripwork:transit-detail"),
    ("transit.yaml", "tripwork:cost-rollup"),
    ("cost.yaml", "tripwork:itinerary-synthesis"),
    ("itinerary.yaml", "tripwork:itinerary-gate"),
    ("gate", "tripwork:export-artifact"),
    ("exports", "tripwork:export-gate"),
    ("egate", "complete"),
]

DOCS = {"trip-brief.yaml": trip_brief, "advisory.yaml": advisory,
        "candidates.yaml": candidates, "verified-pois.yaml": verified_pois,
        "routing.yaml": routing, "accommodations.yaml": accommodations,
        "legs.yaml": legs, "calendar.yaml": calendar, "seasonal.yaml": seasonal,
        "transit.yaml": transit, "cost.yaml": cost, "itinerary.yaml": itinerary}


def _cli(script, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / script),
                           *[str(a) for a in args]],
                          capture_output=True, text=True)


def _next(t, w):
    """Returns the FULL {next, reason} dict, not just `next` -- F5 (v0.35.0
    review): the caller asserts only `next`, but a flaky mismatch's failure
    message must carry `reason` too, or diagnosing the next occurrence means
    re-running the suite dozens of times hunting for a repro. What is
    asserted is unchanged; only what a failure reports grows."""
    r = _cli("next_stage.py", t, "--work-dir", w)
    assert r.returncode == 0, r.stderr
    return yaml.safe_load(r.stdout)


def test_full_walk_in_new_order(tmp_path):
    t = tmp_path / "trips" / SLUG
    w = tmp_path / "work" / SLUG
    t.mkdir(parents=True)
    w.mkdir(parents=True)
    for step, expected in EXPECTED_WALK:
        if step == "stamp":
            (tmp_path / "work" / ".preflight-completed").touch()
        elif step == "gate":
            assert _cli("gate.py", t).returncode == 0
        elif step == "exports":
            (t / "exports").mkdir(exist_ok=True)
            (t / "exports" / f"{SLUG}-itinerary.md").write_text(
                MD_DELIVERABLE, encoding="utf-8")
            (t / "exports" / f"{SLUG}-itinerary.html").write_text(
                HTML_DELIVERABLE, encoding="utf-8")
        elif step == "egate":
            assert _cli("export_gate.py", t).returncode == 0
        elif step is not None:
            write_artifact(t / step, DOCS[step]())
        got = _next(t, w)
        assert got["next"] == expected, f"after {step}: {got}"


def test_all_artifacts_pass_validator(tmp_path):
    t, _ = build_full_trip(tmp_path)
    for p in sorted(t.glob("*.yaml")):
        code, msgs = validate_file(p)
        assert code == 0, f"{p.name}: {msgs}"


def test_injected_schema_violation_caught(tmp_path):
    t, _ = build_full_trip(tmp_path)
    doc = yaml.safe_load((t / "advisory.yaml").read_text(encoding="utf-8"))
    del doc["items"][0]["effective_date"]
    write_artifact(t / "advisory.yaml", doc)
    assert validate_file(t / "advisory.yaml")[0] == 1


def test_gate_reports_written_by_clis_validate(tmp_path):
    t, _ = build_full_trip(tmp_path)
    assert _cli("gate.py", t).returncode == 0
    assert _cli("export_gate.py", t).returncode == 0
    assert validate_file(t / "gate-report.yaml")[0] == 0
    assert validate_file(t / "export-gate-report.yaml")[0] == 0
