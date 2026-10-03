"""v1.0 P1 e2e closure: one trip carries all eight reader-data defects at once;
the real gate CLI must flag every one, route them in _ROUTES order, and pass once
each producing stage's file is restored."""
import pathlib
import subprocess
import sys

import yaml

from scripts.orchestration import route_gate_failures
from tests.mech_fixtures import build_full_trip
from scripts.paths import artifact_path, deliverable_paths, report_path, work_dir_for

ROOT = pathlib.Path(__file__).resolve().parents[1]
NEW = ("day_chain_complete", "moves_recorded", "alternatives_valid", "day_theme_valid",
       "checklist_structured", "sources_complete", "lodging_area_labelled", "brief_names_valid")


def _gate(t):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "gate.py"), str(t)],
                       capture_output=True, text=True)
    return r.returncode, yaml.safe_load((report_path(work_dir_for(t), "gate-report.yaml")).read_text(encoding="utf-8"))


def _edit(t, name, fn):
    p = artifact_path(t, name)
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    fn(doc)
    p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_eight_defects_are_flagged_routed_in_order_and_drain(tmp_path):
    t, _ = build_full_trip(tmp_path)
    code, rep = _gate(t)
    assert code == 0, rep["failures"]
    snap = {n: artifact_path(t, n).read_text(encoding="utf-8")
            for n in ("itinerary.yaml", "verified-pois.yaml", "accommodations.yaml", "trip-brief.yaml")}

    _edit(t, "itinerary.yaml", lambda d: d["days"][0]["rows"].pop(0))
    _edit(t, "itinerary.yaml", lambda d: d["days"][1]["rows"][0].pop("mode"))
    _edit(t, "itinerary.yaml", lambda d: d["days"][0].__setitem__("alternatives", [
        {"kind": "備案", "applies_to": "zzz", "trigger": "t", "fallback": "f", "poi_id": "poi-1"}]))
    _edit(t, "itinerary.yaml", lambda d: d["days"][1].pop("theme"))
    _edit(t, "itinerary.yaml", lambda d: d.__setitem__(
        "checklist", ["battery: spare lithium batteries carry-on only"]))
    _edit(t, "verified-pois.yaml", lambda d: d["pois"][0]["sources"][0].pop("site"))
    _edit(t, "accommodations.yaml", lambda d: d["stops"][0].pop("area_label"))
    _edit(t, "trip-brief.yaml", lambda d: d.pop("short_name"))

    code, rep = _gate(t)
    assert code == 1
    passed = {c["name"]: c["passed"] for c in rep["checks"]}
    assert [n for n in NEW if passed[n] is not False] == []

    for stage, name in (("tripwork:accommodation-research", "accommodations.yaml"),
                        ("tripwork:source-verify", "verified-pois.yaml"),
                        ("tripwork:trip-brief", "trip-brief.yaml"),
                        ("tripwork:itinerary-synthesis", "itinerary.yaml")):
        assert route_gate_failures(rep["failures"]) == stage, rep["failures"]
        (artifact_path(t, name)).write_text(snap[name], encoding="utf-8")      # the stage's fix
        code, rep = _gate(t)
    assert code == 0 and rep["status"] == "pass", rep["failures"]
