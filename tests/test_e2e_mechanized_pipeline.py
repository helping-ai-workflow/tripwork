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

import yaml

from scripts.validate_artifact import validate_file
from scripts.paths import artifact_path, deliverable_paths, report_path, work_dir_for
from tests.mech_fixtures import (SLUG, build_full_trip, write_artifact,
                                 trip_brief, advisory, candidates,
                                 verified_pois, routing, accommodations,
                                 legs, calendar, seasonal, transit, cost,
                                 itinerary, MD_DELIVERABLE, HTML_DELIVERABLE)
from tests.cli_helpers import run_main

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
    return run_main("scripts." + script.removesuffix(".py"), args)


def _next(t, w):
    """Returns the FULL {next, reason} dict, not just `next` -- F5 (v0.35.0
    review): the caller asserts only `next`, but a flaky mismatch's failure
    message must carry `reason` too, or diagnosing the next occurrence means
    re-running the suite dozens of times hunting for a repro. What is
    asserted is unchanged; only what a failure reports grows."""
    r = _cli("next_stage", t, "--work-dir", w)
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
            assert _cli("gate", t).returncode == 0
        elif step == "exports":
            (deliverable_paths(t, trip_brief())["md"]).write_text(
                MD_DELIVERABLE, encoding="utf-8")
            (deliverable_paths(t, trip_brief())["html"]).write_text(
                HTML_DELIVERABLE, encoding="utf-8")
        elif step == "egate":
            assert _cli("export_gate", t).returncode == 0
        elif step is not None:
            write_artifact(artifact_path(t, step), DOCS[step]())
        got = _next(t, w)
        assert got["next"] == expected, f"after {step}: {got}"


def test_all_artifacts_pass_validator(tmp_path):
    t, _ = build_full_trip(tmp_path)
    found = sorted(artifact_path(t, "x").parent.glob("*.yaml"))
    assert len(found) >= 12, found            # a glob that finds nothing proves nothing
    for p in found:
        code, msgs = validate_file(p)
        assert code == 0, f"{p.name}: {msgs}"


def test_injected_schema_violation_caught(tmp_path):
    t, _ = build_full_trip(tmp_path)
    doc = yaml.safe_load((artifact_path(t, "advisory.yaml")).read_text(encoding="utf-8"))
    del doc["items"][0]["effective_date"]
    write_artifact(artifact_path(t, "advisory.yaml"), doc)
    assert validate_file(artifact_path(t, "advisory.yaml"))[0] == 1


def test_gate_reports_written_by_clis_validate(tmp_path):
    t, _ = build_full_trip(tmp_path)
    assert _cli("gate", t).returncode == 0
    assert _cli("export_gate", t).returncode == 0
    assert validate_file(report_path(work_dir_for(t), "gate-report.yaml"))[0] == 0
    assert validate_file(report_path(work_dir_for(t), "export-gate-report.yaml"))[0] == 0
