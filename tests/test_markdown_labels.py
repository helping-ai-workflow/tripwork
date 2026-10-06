"""v2.1.0 §6 (D7): the Markdown deliverable names a non-official source by its site (the
user's pick S1) and marks each move by its mode, one emoji per icon the reader draws (M1)."""
import pytest
import yaml

from scripts.render.markdown import ICON_EMOJI, MODE_MARK, render_markdown_page
from scripts.render.reader.assets import MODE_ICON


def _poi(pid, sources):
    return {"id": pid, "name_display": pid, "name_local": pid, "verify_status": "verified",
            "geocode": {"lat": 25.0, "lng": 121.5, "geocode_source": "nominatim"}, "sources": sources}


def _md(rows, pois, legs=None):
    itin = {"title": "示意", "days": [{"date": "2030-01-07", "label": "D1", "rows": rows}]}
    return render_markdown_page(itin, {p["id"]: p for p in pois}, legs=legs)


def test_official_source_says_official():
    md = _md([{"time": "10:00", "slot": "visit", "poi_id": "a"}],
             [_poi("a", [{"url": "https://a.example/", "official": True, "site": "示意官網"}])])
    assert "[官網](https://a.example/)" in md


def test_non_official_source_says_its_site():
    md = _md([{"time": "10:00", "slot": "visit", "poi_id": "a"}],
             [_poi("a", [{"url": "https://guide.example/a", "site": "旅遊指南"}])])
    assert "[旅遊指南](https://guide.example/a)" in md and "官網" not in md


def test_non_official_source_without_a_site_name_says_its_domain():
    md = _md([{"time": "10:00", "slot": "visit", "poi_id": "a"}],
             [_poi("a", [{"url": "https://www.guide.example/a"}])])
    assert "[guide.example](https://www.guide.example/a)" in md


def test_every_reader_icon_has_its_emoji():
    assert set(MODE_ICON.values()) <= set(ICON_EMOJI)
    assert MODE_MARK["taxi"] == MODE_MARK["drive"]                   # one car icon in the reader too


@pytest.mark.parametrize("mode", sorted(MODE_ICON))
def test_a_move_row_carries_its_mode(mode):
    md = _md([{"slot": "move", "from": "甲", "to": "乙", "mode": mode, "text": "移動"}], [])
    assert f"[{MODE_MARK[mode]} 甲→乙]" in md


def test_a_move_without_mode_has_no_mark():
    md = _md([{"slot": "move", "from": "甲", "to": "乙", "mode": "none", "text": "同一棟"}], [])
    assert "[甲→乙]" in md and not any(e in md for e in ICON_EMOJI.values())


def test_a_leg_row_reads_its_mode_from_legs():
    legs = {"legs": [{"from": "台北", "to": "礁溪", "mode": "drive", "kind": "home"}]}
    md = _md([{"slot": "move", "leg_index": 0, "text": "國道五號"}], [], legs=legs)
    assert f"[{MODE_MARK['drive']} 台北→礁溪]" in md


def test_export_writes_the_marks(tmp_path, monkeypatch):
    """The shipped caller passes legs: the deliverable on disk carries the leg's mode."""
    from tests.test_export_cli import _export
    from tests import mech_fixtures as M
    from scripts.paths import artifact_path, deliverable_paths, report_path
    t, w = M.build_full_trip(tmp_path)
    itin = yaml.safe_load(artifact_path(t, "itinerary.yaml").read_text(encoding="utf-8"))
    legs = {"legs": [{"from": "甲站", "to": "乙站", "mode": "ferry", "status": "ok",
                      "sources": [{"url": "https://ferry.example/"}]}]}
    M.write_artifact(artifact_path(t, "legs.yaml"), legs)
    li = 0
    itin["days"][0]["rows"].insert(0, {"slot": "move", "leg_index": li, "text": "移動"})
    M.write_artifact(artifact_path(t, "itinerary.yaml"), itin)
    M.write_artifact(report_path(w, "gate-report.yaml"), {"status": "pass", "checks": [], "failures": []})
    assert _export([str(t), "--work-dir", str(w)]) == 0
    brief = yaml.safe_load(artifact_path(t, "trip-brief.yaml").read_text(encoding="utf-8"))
    md = deliverable_paths(t, brief)["md"].read_text(encoding="utf-8")
    assert MODE_MARK[legs["legs"][li]["mode"]] in md
