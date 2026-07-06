"""D1: runtime schema validator CLI — exit 0 pass / 1 schema fail / 2 usage error."""
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "validate_artifact.py"


def _run(*args):
    return subprocess.run([sys.executable, str(CLI), *[str(a) for a in args]],
                          capture_output=True, text=True)


def _write(tmp_path, name, doc):
    p = tmp_path / name
    p.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return p


GOOD_ADVISORY = {"items": [{
    "topic": "battery", "rule": "spare lithium batteries carry-on only",
    "effective_date": "2026-01-01", "risk": "restricted",
    "sources": [
        {"url": "https://gov.example/battery", "official": True},
        {"url": "https://intl.example/battery", "official": False},
    ],
}]}

GOOD_CALENDAR = {"holidays": []}


def test_pass_exits_zero(tmp_path):
    p = _write(tmp_path, "advisory.yaml", GOOD_ADVISORY)
    r = _run(p)
    assert r.returncode == 0, r.stderr
    assert "PASS" in r.stdout


def test_schema_violation_exits_one_with_error_path(tmp_path):
    bad = {"items": [{"topic": "battery", "rule": "x", "risk": "restricted",
                      "sources": [{"url": "https://gov.example", "official": True}]}]}
    p = _write(tmp_path, "advisory.yaml", bad)          # missing effective_date
    r = _run(p)
    assert r.returncode == 1
    assert "effective_date" in r.stderr


def test_verified_poi_without_geocode_fails(tmp_path):
    bad = {"pois": [{"id": "x", "name_local": "x", "name_display": "x",
                     "category": "restaurant", "district": "d",
                     "sources": [{"url": "https://a.example", "lang": "ja"},
                                 {"url": "https://b.example", "lang": "zh"}],
                     "verify_status": "verified"}]}
    p = _write(tmp_path, "verified-pois.yaml", bad)
    r = _run(p)
    assert r.returncode == 1


def test_unknown_basename_exits_two(tmp_path):
    p = _write(tmp_path, "mystery.yaml", {"a": 1})
    r = _run(p)
    assert r.returncode == 2
    assert "unknown artifact" in r.stderr


def test_missing_file_exits_two(tmp_path):
    r = _run(tmp_path / "calendar.yaml")
    assert r.returncode == 2


def test_bad_yaml_exits_two(tmp_path):
    p = tmp_path / "calendar.yaml"
    p.write_text("holidays: [unclosed", encoding="utf-8")
    r = _run(p)
    assert r.returncode == 2


def test_explicit_schema_override(tmp_path):
    p = _write(tmp_path, "whatever.yaml", GOOD_CALENDAR)
    r = _run(p, "--schema", ROOT / "schemas" / "calendar.schema.json")
    assert r.returncode == 0


def test_nonexistent_schema_exits_two(tmp_path):
    p = _write(tmp_path, "whatever.yaml", GOOD_CALENDAR)
    r = _run(p, "--schema", tmp_path / "no-such.schema.json")
    assert r.returncode == 2
    assert "cannot load schema" in r.stderr


def test_malformed_schema_json_exits_two(tmp_path):
    p = _write(tmp_path, "whatever.yaml", GOOD_CALENDAR)
    bad_schema = tmp_path / "broken.schema.json"
    bad_schema.write_text("{not valid json", encoding="utf-8")
    r = _run(p, "--schema", bad_schema)
    assert r.returncode == 2
    assert "cannot load schema" in r.stderr


def test_export_gate_report_shares_gate_report_schema(tmp_path):
    doc = {"status": "pass", "checks": [{"name": "x", "passed": True}], "failures": []}
    p = _write(tmp_path, "export-gate-report.yaml", doc)
    assert _run(p).returncode == 0


def test_every_pipeline_basename_is_mapped():
    from scripts.validate_artifact import SCHEMA_BY_BASENAME
    expected = {"trip-brief.yaml", "candidates.yaml", "verified-pois.yaml",
                "verified-pois-media.yaml", "routing.yaml", "accommodations.yaml",
                "legs.yaml", "calendar.yaml", "seasonal.yaml", "transit.yaml",
                "cost.yaml", "advisory.yaml", "itinerary.yaml", "gate-report.yaml",
                "export-gate-report.yaml", "stage-state.yaml"}
    assert set(SCHEMA_BY_BASENAME) == expected
