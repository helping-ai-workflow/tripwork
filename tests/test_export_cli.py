"""v2.0.0 spec §1 export (Q3, round-2 #4-#6/#8/#18): `tripwork.py export <slug>` renders
the md + html from the one inputs function, refuses a missing / failed / stale gate
or a pre-v1.0 trip, and writes both files or neither."""
import importlib
import os
import pathlib
import time

import pytest
import yaml

from tests import mech_fixtures as M

SLUG = M.SLUG


@pytest.fixture
def ws(tmp_path, monkeypatch):
    from scripts import gate
    t, w = M.build_full_trip(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert gate.main([str(t), "--work-dir", str(w)]) == 0
    return tmp_path, t, w


def _export(argv):
    return importlib.import_module("scripts.export").main(argv)


def _snapshot(t):
    return {str(p.relative_to(t)): (p.stat().st_mtime_ns, p.read_bytes())
            for p in sorted(t.rglob("*")) if p.is_file()}


def test_export_matches_direct_render(ws):
    from scripts.paths import artifact_path, deliverable_paths
    from scripts.render.html_page import render_html_page
    from scripts.render.markdown import render_markdown_page
    from scripts.trip_inputs import trip_inputs
    root, t, w = ws
    assert _export([str(t), "--work-dir", str(w)]) == 0
    itin, poi_map, kw, _ = trip_inputs(t)
    paths = deliverable_paths(t, yaml.safe_load(artifact_path(t, "trip-brief.yaml").read_text(encoding="utf-8")))
    assert paths["md"].read_text(encoding="utf-8") == render_markdown_page(itin, poi_map, kw["cost"], brief=kw["brief"])
    assert paths["html"].read_text(encoding="utf-8") == render_html_page(itin, poi_map, build="check", **kw)


def test_export_prints_both_paths(ws, capsys):
    root, t, w = ws
    _export([str(t), "--work-dir", str(w)])
    out = capsys.readouterr().out
    assert "md: " in out and "html: " in out


def _gate_fail(t, w):
    p = w / "gate-report.yaml"
    rep = yaml.safe_load(p.read_text(encoding="utf-8"))
    rep["status"] = "fail"
    p.write_text(yaml.safe_dump(rep, allow_unicode=True), encoding="utf-8")


def _gate_stale(t, w):
    from scripts.paths import artifact_path
    later = time.time() + 5
    os.utime(artifact_path(t, "itinerary.yaml"), (later, later))


def _no_gate_report(t, w):
    (w / "gate-report.yaml").unlink()


def _no_itinerary(t, w):
    from scripts.paths import artifact_path
    artifact_path(t, "itinerary.yaml").unlink()


def _legacy(t, w):
    from scripts.paths import artifact_path
    src = artifact_path(t, "itinerary.yaml")
    (t / "itinerary.yaml").write_bytes(src.read_bytes())   # an artifact at the trip root = pre-v1.0


@pytest.mark.parametrize("break_it,code,hint", [
    (_legacy, 2, "tripwork.py migrate"),
    (_no_itinerary, 2, None),
    (_gate_fail, 1, "tripwork.py gate"),
    (_gate_stale, 1, "tripwork.py gate"),
    (_no_gate_report, 1, "tripwork.py gate"),
], ids=["legacy", "no-itinerary", "gate-fail", "gate-stale", "no-gate-report"])
def test_export_refuses(ws, capsys, break_it, code, hint):
    root, t, w = ws
    break_it(t, w)
    before = _snapshot(t)
    assert _export([str(t), "--work-dir", str(w)]) == code
    err = capsys.readouterr().err
    assert "Traceback" not in err
    if hint:
        assert hint in err
    assert _snapshot(t) == before


def test_export_writes_nothing_when_html_fails(ws, monkeypatch):
    root, t, w = ws
    mod = importlib.import_module("scripts.export")

    def boom(*a, **k):
        raise RuntimeError("render failed")
    monkeypatch.setattr(mod, "render_html_page", boom)
    before = _snapshot(t)
    with pytest.raises(RuntimeError):
        _export([str(t), "--work-dir", str(w)])
    assert _snapshot(t) == before


def test_export_then_export_gate_then_complete(ws):
    from scripts import export_gate
    from scripts.next_stage import next_stage
    root, t, w = ws
    assert _export([str(t), "--work-dir", str(w)]) == 0
    assert export_gate.main([str(t), "--work-dir", str(w)]) == 0
    assert next_stage(str(t), str(w))[0] == "complete"
