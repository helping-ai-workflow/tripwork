"""v1.0 P3 — migrate_v1.py moves a pre-v1.0 trip into the v1.0 layout (spec §5.3)."""
import yaml

from scripts.migrate_v1 import main as migrate, plan_trip
from scripts.next_stage import next_stage
from scripts.paths import LEGACY_EXPORTS, artifact_path, data_dir, is_legacy_layout, report_path
from tests.mech_fixtures import build_full_trip


def _legacy(tmp_path):
    """build_full_trip, then fold it back into the v0.36 shape."""
    t, w = build_full_trip(tmp_path)
    for p in sorted(data_dir(t).iterdir()):
        p.rename(t / p.name)
    data_dir(t).rmdir()
    exports = t / "exports"
    exports.mkdir()
    for p in sorted(t.glob("*.md")) + sorted(t.glob("*.html")):
        p.rename(exports / p.name)
    (t / "itinerary.md").write_text("# 舊的重複成品\n", encoding="utf-8")
    (t / "北海道.pdf").write_bytes(b"%PDF-1.4\n")
    (t / "gate-report.yaml").write_text("status: pass\nchecks: []\nfailures: []\n", encoding="utf-8")
    return t, w


def test_dry_run_changes_nothing(tmp_path, capsys):
    t, _ = _legacy(tmp_path)
    before = sorted(p.name for p in t.rglob("*"))
    assert migrate([str(t.parent)]) == 0
    assert sorted(p.name for p in t.rglob("*")) == before
    assert "data/" in capsys.readouterr().out


def test_apply_produces_the_v1_layout(tmp_path):
    t, w = _legacy(tmp_path)
    assert migrate([str(t.parent), "--apply"]) == 0
    assert not is_legacy_layout(t)
    assert artifact_path(t, "itinerary.yaml").is_file()
    assert (data_dir(t) / "北海道.pdf").is_file()
    assert (data_dir(t) / LEGACY_EXPORTS / "itinerary.md").is_file()
    assert report_path(w, "gate-report.yaml").is_file()
    assert not (t / "exports").exists()


def test_every_top_level_file_lands_somewhere(tmp_path):
    t, w = _legacy(tmp_path)
    names = {p.name for p in t.iterdir() if p.is_file()}
    moves = {src.name for _action, src, _dst in plan_trip(t, w.parent)[0]}
    assert names <= moves


def test_a_second_run_changes_nothing(tmp_path):
    t, w = _legacy(tmp_path)
    migrate([str(t.parent), "--apply"])
    after = sorted(str(p) for p in tmp_path.rglob("*"))
    assert migrate([str(t.parent), "--apply"]) == 0
    assert sorted(str(p) for p in tmp_path.rglob("*")) == after


def test_the_migrated_trip_is_no_longer_stopped_for_migration(tmp_path):
    t, w = _legacy(tmp_path)
    migrate([str(t.parent), "--apply"])
    nxt, why = next_stage(t, w)
    assert "migrate_v1.py" not in why


def test_migration_never_rewrites_the_itinerary_and_lists_what_synthesis_converts(tmp_path, capsys):
    """P3 review C2/I3: attaching a ▸ row by its position is the signal spec §4.4
    names as wrong (trip-e D5), so migration moves itinerary.yaml untouched and
    only LISTS the ▸ rows and a trip-level contingency; the gate's `legacy …`
    classes route them to itinerary-synthesis, which reads the text."""
    t, w = _legacy(tmp_path)
    p = t / "itinerary.yaml"
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    doc["days"][0]["rows"].insert(2, {"slot": "activity", "poi_id": "poi-1",
                                      "text": "▸ 備案(下雨)｜改室內"})
    doc["contingency"] = [{"trigger": "颱風", "fallback": "延後一天"}]
    p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    before = p.read_bytes()
    assert migrate([str(t.parent), "--apply"]) == 0
    out = capsys.readouterr().out
    assert artifact_path(t, "itinerary.yaml").read_bytes() == before
    assert "1 inline ▸ row" in out and "trip-level contingency" in out


def test_two_legacy_files_with_one_name_both_survive(tmp_path):
    """P3 review C1: trip-f has a root itinerary.md AND exports/itinerary.md;
    both used to land on data/legacy-exports/itinerary.md and one was overwritten."""
    t, w = _legacy(tmp_path)
    (t / "exports" / "itinerary.md").write_text("# exports copy\n", encoding="utf-8")
    assert migrate([str(t.parent), "--apply"]) == 0
    kept = sorted(p.read_text(encoding="utf-8")
                  for p in (data_dir(t) / LEGACY_EXPORTS).glob("*itinerary.md"))
    assert "# exports copy\n" in kept and "# 舊的重複成品\n" in kept


def test_a_half_migrated_trip_is_still_stopped_and_finished_by_a_rerun(tmp_path):
    """P3 review I1: data/ existing must not mean "done" while artifacts remain at
    the root (an interrupted --apply, or a consumer script still writing there)."""
    t, w = _legacy(tmp_path)
    data_dir(t).mkdir()
    (t / "trip-brief.yaml").rename(artifact_path(t, "trip-brief.yaml"))
    assert is_legacy_layout(t)
    nxt, why = next_stage(t, w)
    assert nxt == "stop-and-ask" and "migrate_v1.py" in why
    assert migrate([str(t.parent), "--apply"]) == 0
    assert not is_legacy_layout(t) and artifact_path(t, "itinerary.yaml").is_file()


def test_a_single_trip_argument_still_moves_reports_into_the_workspace_work(tmp_path):
    """Found on the real corpus dry run: `migrate_v1.py trips/<slug>` put reports in
    trips/work/<slug>/ because the work root was derived from the argument, not from
    the trip (scripts/paths.py::work_dir_for is the one rule)."""
    t, w = _legacy(tmp_path)
    assert migrate([str(t), "--apply"]) == 0
    assert report_path(w, "gate-report.yaml").is_file()
    assert not (tmp_path / "trips" / "work").exists()


def test_an_existing_work_report_is_never_overwritten(tmp_path):
    t, w = _legacy(tmp_path)
    report_path(w, "gate-report.yaml").write_text("status: fail\nchecks: []\nfailures: [x]\n",
                                                  encoding="utf-8")
    assert migrate([str(t.parent), "--apply"]) == 0
    assert "fail" in report_path(w, "gate-report.yaml").read_text(encoding="utf-8")
    assert (data_dir(t) / LEGACY_EXPORTS / "gate-report.yaml").is_file()
