"""v2.0.0 (R2-1, round-2 #7): export is a fixed program, so re-rendering can never fix a
retryable export-gate failure. A retryable fail goes back to itinerary-synthesis to fix
the source text; the same failures twice in a row stop and ask (a plugin render defect).
The repeat is decided by comparing reports, not by the agent's memory."""
import pytest
import yaml

from tests import mech_fixtures as M


@pytest.fixture
def trip(tmp_path):
    from scripts import gate
    from scripts.paths import deliverable_paths
    t, w = M.build_full_trip(tmp_path)
    assert gate.main([str(t), "--work-dir", str(w)]) == 0
    md = deliverable_paths(t, M.trip_brief())["md"]
    return t, w, md


def _gate(t, w):
    from scripts import export_gate
    export_gate.main([str(t), "--work-dir", str(w)])
    return yaml.safe_load((w / "export-gate-report.yaml").read_text(encoding="utf-8"))


def _next(t, w):
    from scripts.next_stage import next_stage
    return next_stage(str(t), str(w))


def test_first_retryable_fail_routes_to_synthesis(trip):
    t, w, md = trip
    md.write_text(md.read_text(encoding="utf-8") + "\n門票 $5\n", encoding="utf-8")
    rep = _gate(t, w)
    assert rep["status"] == "fail" and rep["retryable"] is True and rep["repeat_of_previous"] is False
    nxt, why = _next(t, w)
    assert nxt == "tripwork:itinerary-synthesis"
    assert "fix the source text" in why


def test_same_failure_twice_stops(trip):
    t, w, md = trip
    md.write_text(md.read_text(encoding="utf-8") + "\n門票 $5\n", encoding="utf-8")
    _gate(t, w)
    rep = _gate(t, w)
    assert rep["retryable"] is False and rep["repeat_of_previous"] is True
    nxt, why = _next(t, w)
    assert nxt == "stop-and-ask"
    assert "likely a plugin render defect" in why


def test_different_failure_second_time_is_still_retryable(trip):
    t, w, md = trip
    base = md.read_text(encoding="utf-8")
    md.write_text(base + "\n門票 $5\n", encoding="utf-8")
    _gate(t, w)
    md.write_text(base + "\n[地圖](https://maps.example/x)\n", encoding="utf-8")
    rep = _gate(t, w)
    assert rep["status"] == "fail" and rep["retryable"] is True and rep["repeat_of_previous"] is False


def test_a_pass_resets_the_repeat(trip):
    t, w, md = trip
    base = md.read_text(encoding="utf-8")
    md.write_text(base + "\n門票 $5\n", encoding="utf-8")
    _gate(t, w)
    md.write_text(base, encoding="utf-8")
    assert _gate(t, w)["status"] == "pass"
    md.write_text(base + "\n門票 $5\n", encoding="utf-8")
    rep = _gate(t, w)
    assert rep["retryable"] is True and rep["repeat_of_previous"] is False
