"""v2.0.0 (spec §1 export, round-2 #3/#4/#17): one inputs function for everything that
renders or judges the deliverables -- publish, export and export-gate -- and one
gate-freshness predicate shared by the oracle and `export`."""
import ast
import os
import pathlib
import time

import pytest

from tests import mech_fixtures as M

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_one_inputs_function():
    from scripts import publish, trip_inputs
    assert publish.trip_inputs is trip_inputs.trip_inputs
    assert publish.TripInputError is trip_inputs.TripInputError


def test_export_gate_does_not_assemble_its_own_pool():
    tree = ast.parse((ROOT / "scripts" / "export_gate.py").read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    names = {n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", None)
             for n in ast.walk(main) if isinstance(n, ast.Call)}
    assert "poi_pool" not in names and "apply_media" not in names
    assert "trip_inputs" in names


def test_export_gate_calls_the_shared_function(tmp_path, monkeypatch):
    from scripts import export_gate, trip_inputs
    t, w = M.build_full_trip(tmp_path)
    seen = []
    real = trip_inputs.trip_inputs

    def spy(trip_dir):
        seen.append(trip_dir)
        return real(trip_dir)
    monkeypatch.setattr(trip_inputs, "trip_inputs", spy)
    export_gate.main([str(t), "--work-dir", str(w)])
    assert seen


def test_export_gate_and_publish_see_the_same_pool(tmp_path, monkeypatch):
    """The media overlay must reach the gate exactly as it reaches the renderers."""
    from scripts import export_gate, trip_inputs
    from scripts.paths import artifact_path
    t, w = M.build_full_trip(tmp_path)
    photo = {"photo": {"data": "data:image/png;base64,UEhPVE8=", "width": 640, "height": 480},
             "photo_attribution": {"author": "示意", "license": "CC-BY-4.0",
                                   "source_url": "https://commons.example/x"},
             "photo_source": "wikimedia"}
    M.write_artifact(artifact_path(t, "verified-pois-media.yaml"), {"media": {"poi-1": photo}})
    _, poi_map, _, _ = trip_inputs.trip_inputs(t)
    gated = []
    real_md = export_gate.run_export_gate

    def spy(md, pois, **kw):
        gated.append({p["id"]: p for p in pois})
        return real_md(md, pois, **kw)
    monkeypatch.setattr(export_gate, "run_export_gate", spy)
    export_gate.main([str(t), "--work-dir", str(w)])
    assert gated and gated[0]["poi-1"].get("photo") == poi_map["poi-1"].get("photo")


@pytest.mark.parametrize("missing", ["itinerary.yaml", "verified-pois.yaml"])
def test_missing_input_exits_2(tmp_path, capsys, monkeypatch, missing):
    from scripts import export_gate, publish
    from scripts.paths import artifact_path
    t, w = M.build_full_trip(tmp_path)
    artifact_path(t, missing).unlink()
    assert export_gate.main([str(t), "--work-dir", str(w)]) == 2
    monkeypatch.setenv("TRIPWORK_PUBLISH_PASSWORD", "pw")
    assert publish.main(["build", str(t)]) == 2
    assert "Traceback" not in capsys.readouterr().err


def test_gate_report_stale(tmp_path):
    from scripts import gate
    from scripts.next_stage import gate_report_stale
    from scripts.paths import artifact_path
    t, w = M.build_full_trip(tmp_path)
    assert gate_report_stale(t, w) == ["gate-report.yaml"]
    gate.main([str(t), "--work-dir", str(w)])
    assert gate_report_stale(t, w) == []
    later = time.time() + 5
    os.utime(artifact_path(t, "itinerary.yaml"), (later, later))
    assert gate_report_stale(t, w) == ["itinerary.yaml"]
