"""v2.0.0 final-review fixes (Critical 1, Important 2-4, re-graded minors).

Critical 1: the R2-1 retry loop must work when the agent does exactly what the oracle
says -- fix the source, gate, EXPORT, export-gate -- and a repeat is only a repeat when
the inputs really changed between the two reports.
"""
import importlib
import os
import pathlib
import time

import pytest
import yaml

from tests import mech_fixtures as M
from tests.cli_helpers import run_main
from tests.test_rederive import _accom, _lodging_cand, _poi_rec, _sourced_business_status

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARK = "示意壞字"


def _next(t, w):
    from scripts.next_stage import next_stage
    return next_stage(str(t), str(w))


def _touch_later(path, secs=2):
    later = time.time() + secs
    os.utime(path, (later, later))


@pytest.fixture
def looped(tmp_path, monkeypatch):
    """A complete trip whose export-gate fails retryably while the md carries MARK --
    standing in for a source-text defect the itinerary-gate did not see."""
    from scripts import export_gate
    from scripts.paths import artifact_path
    t, w = M.build_full_trip(tmp_path)
    real = export_gate.run_export_gate

    def gate_md(md, pois, **kw):
        rep = real(md, pois, **kw)
        if MARK in md:
            rep["failures"] = rep["failures"] + ["naked '$' found; prices must be escaped as '\\$'"]
            rep["status"] = "fail"
            rep["retryable"] = True
        return rep
    monkeypatch.setattr(export_gate, "run_export_gate", gate_md)
    itin = M.itinerary()
    itin["days"][0]["rows"][1]["text"] = f"午餐 {MARK}"
    M.write_artifact(artifact_path(t, "itinerary.yaml"), itin)
    return t, w


def _follow(t, w, synthesis, limit=12):
    """Run the stage the oracle names until it completes or stops; `synthesis` stands in
    for the itinerary-synthesis agent. Returns the list of stages taken."""
    taken = []
    for _ in range(limit):
        nxt, why = _next(t, w)
        taken.append(nxt)
        if nxt in ("complete", "stop-and-ask"):
            return taken, why
        mod = {"tripwork:itinerary-gate": "scripts.gate", "tripwork:export-artifact": "scripts.export",
               "tripwork:export-gate": "scripts.export_gate"}.get(nxt)
        if mod:
            run_main(mod, [t, "--work-dir", w])
            time.sleep(0.02)
        elif nxt == "tripwork:itinerary-synthesis":
            synthesis(t)
        else:
            raise AssertionError(f"unexpected stage {nxt}: {why}")
    raise AssertionError(f"no end after {limit} stages: {taken}")


def _fix_source(t):
    from scripts.paths import artifact_path
    p = artifact_path(t, "itinerary.yaml")
    itin = yaml.safe_load(p.read_text(encoding="utf-8"))
    itin["days"][0]["rows"][1]["text"] = "午餐"
    time.sleep(0.05)                                   # newer than the last report, not in the future
    M.write_artifact(p, itin)


def _fix_something_else(t):
    from scripts.paths import artifact_path
    p = artifact_path(t, "itinerary.yaml")
    itin = yaml.safe_load(p.read_text(encoding="utf-8"))
    itin["days"][0]["rows"][1]["text"] = f"午餐（改過） {MARK}"
    time.sleep(0.05)
    M.write_artifact(p, itin)


def test_a_fixed_source_is_exported_again_and_completes(looped):
    t, w = looped
    taken, why = _follow(t, w, _fix_source)
    assert taken[-1] == "complete", (taken, why)
    after_fix = taken[taken.index("tripwork:itinerary-synthesis"):]
    assert "tripwork:export-artifact" in after_fix, taken


def test_an_unfixed_source_stops_as_a_likely_plugin_defect(looped):
    t, w = looped
    taken, why = _follow(t, w, _fix_something_else)
    assert taken[-1] == "stop-and-ask" and "likely a plugin render defect" in why, (taken, why)
    after_fix = taken[taken.index("tripwork:itinerary-synthesis"):]
    assert "tripwork:export-artifact" in after_fix, taken


def test_rerunning_the_export_gate_alone_is_not_a_repeat(looped):
    t, w = looped
    run_main("scripts.gate", [t, "--work-dir", w])
    run_main("scripts.export", [t, "--work-dir", w])
    run_main("scripts.export_gate", [t, "--work-dir", w])
    run_main("scripts.export_gate", [t, "--work-dir", w])
    rep = yaml.safe_load((w / "export-gate-report.yaml").read_text(encoding="utf-8"))
    assert rep["retryable"] is True and rep["repeat_of_previous"] is False


def test_a_deliverable_older_than_the_gate_report_is_exported_again(tmp_path):
    t, w = M.build_full_trip(tmp_path)
    run_main("scripts.gate", [t, "--work-dir", w])
    _touch_later(w / "gate-report.yaml")
    assert _next(t, w)[0] == "tripwork:export-artifact"


# --- Important 2: Gate 1b counts only the sources that count -------------------------

@pytest.mark.parametrize("path", ["verify_poi", "rederive_lodging", "rederive_pois"])
def test_a_search_page_is_not_the_local_language_source(path):
    from scripts.rederive import rederive_lodging, rederive_pois
    from scripts.verify import verify_poi
    srcs = [{"url": "https://a.example.com/p", "lang": "en"}, {"url": "https://b.example.org/q", "lang": "en"},
            {"url": "https://search.naver.com/search.naver?query=x", "lang": "ko"}]
    bs = {"status": "OPERATIONAL", "source_url": "https://a.example.com/p", "as_of": "2026-08-05"}
    if path == "verify_poi":
        rec = _poi_rec(sources=srcs, business_status=bs)
        _, status, note = verify_poi(rec, True, True, local_lang="ko", resolved_name=rec["resolved_name"], today="2026-08-05")
        assert status == "unverified" and "local language" in note
    elif path == "rederive_pois":
        out = rederive_pois([_poi_rec(sources=srcs, business_status=bs)], local_lang="ko")
        assert out.mismatches or out.superseded
    else:
        cand = _lodging_cand(sources=srcs, business_status={**bs, "as_of": _sourced_business_status()["as_of"]},
                             resolved_name="日月潭旅店",
                             geocode={"lat": 23.86, "lng": 120.91, "geocode_source": "nominatim"})
        out = rederive_lodging(_accom(cand), local_lang="ko")
        assert out.mismatches or out.superseded


# --- Important 3: a brand-new workspace reaches the oracle ---------------------------

@pytest.mark.parametrize("stamp", [False, True])
def test_next_runs_before_trips_exists(tmp_path, monkeypatch, capsys, stamp):
    monkeypatch.chdir(tmp_path)
    if stamp:
        (tmp_path / "work").mkdir()
        (tmp_path / "work" / ".preflight-completed").touch()
    tw = importlib.import_module("scripts.tripwork")
    assert tw.main(["next", "tokyo-2027"]) == 0
    want = "tripwork:trip-brief" if stamp else "tripwork:workspace-shape-preflight"
    assert yaml.safe_load(capsys.readouterr().out)["next"] == want


# --- Important 4: the layout is fixed and the skills say so --------------------------

def test_using_tripwork_states_the_fixed_layout():
    s = (ROOT / "skills" / "using-tripwork" / "SKILL.md").read_text(encoding="utf-8")
    assert "do not hardcode layout" not in s
    assert "the layout is fixed" in s


def test_preflight_states_the_fixed_layout():
    s = (ROOT / "skills" / "workspace-shape-preflight" / "SKILL.md").read_text(encoding="utf-8")
    assert "per the target repo CLAUDE.md convention" not in s
    assert "the layout is fixed" in s


# --- re-graded: validate with nothing to validate; publish checks before the password -

def test_validate_with_no_artifacts_is_not_a_pass(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "trips" / "empty").mkdir(parents=True)
    tw = importlib.import_module("scripts.tripwork")
    assert tw.main(["validate", "empty"]) == 2
    assert "no artifacts" in capsys.readouterr().err


def test_validate_on_a_legacy_trip_points_at_migrate(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    t = tmp_path / "trips" / "old"
    t.mkdir(parents=True)
    (t / "itinerary.yaml").write_text("days: []\n", encoding="utf-8")
    tw = importlib.import_module("scripts.tripwork")
    assert tw.main(["validate", "old"]) == 2
    assert "tripwork.py migrate" in capsys.readouterr().err


def test_publish_checks_the_trip_before_asking_for_a_password(tmp_path, monkeypatch, capsys):
    import getpass
    from scripts import publish
    t = tmp_path / "trips" / "old"
    t.mkdir(parents=True)
    (t / "itinerary.yaml").write_text("days: []\n", encoding="utf-8")
    monkeypatch.delenv("TRIPWORK_PUBLISH_PASSWORD", raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(getpass, "getpass", lambda *a, **k: (_ for _ in ()).throw(AssertionError("asked")))
    assert publish.main(["build", str(t)]) == 2
    assert "tripwork.py migrate" in capsys.readouterr().err
