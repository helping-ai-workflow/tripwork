"""v1.0 P3 — the one place trip paths are decided (spec §5.1)."""
from scripts.brief_names import deliverable_stem
from scripts.paths import (REPORTS, artifact_names, artifact_path, data_dir, deliverable_paths,
                           is_legacy_layout, report_path, work_dir_for)
from scripts.validate_artifact import SCHEMA_BY_BASENAME

BRIEF = {"dates": {"start": "2026-10-12", "end": "2026-10-19"}, "short_name": "北海道"}


def test_artifacts_live_under_data(tmp_path):
    t = tmp_path / "trips" / "hokkaido"
    assert data_dir(t) == t / "data"
    assert artifact_path(t, "itinerary.yaml") == t / "data" / "itinerary.yaml"


def test_reports_live_in_work(tmp_path):
    t = tmp_path / "trips" / "hokkaido"
    w = work_dir_for(t)
    assert w == (tmp_path / "work" / "hokkaido").resolve()
    assert report_path(w, "gate-report.yaml") == w / "gate-report.yaml"


def test_deliverables_are_named_by_the_stem(tmp_path):
    t = tmp_path / "trips" / "hokkaido"
    stem = deliverable_stem(BRIEF)
    assert deliverable_paths(t, BRIEF) == {"md": t / f"{stem}.md", "html": t / f"{stem}.html"}


def test_artifact_names_are_the_validator_table_minus_work_files():
    assert set(artifact_names()) == set(SCHEMA_BY_BASENAME) - set(REPORTS) - {"stage-state.yaml"}


def test_legacy_layout_detection(tmp_path):
    t = tmp_path / "trips" / "old"
    t.mkdir(parents=True)
    assert not is_legacy_layout(t)                       # empty: not legacy
    (t / "itinerary.yaml").write_text("days: []\n", encoding="utf-8")
    assert is_legacy_layout(t)
    data_dir(t).mkdir()
    assert is_legacy_layout(t)                           # data/ + a root artifact: half-migrated
    (t / "itinerary.yaml").rename(data_dir(t) / "itinerary.yaml")
    assert not is_legacy_layout(t)                       # nothing left at the root: v1
