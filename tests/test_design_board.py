"""The design board (2026-10-03): any agent puts visual choices in front of the user as one
offline HTML file -- no Claude artifact needed. A YAML of topics in, a page out; each card
shows its key; a pick works with no script (radios); 「複製選擇」 makes a line to paste back."""
import base64
import pathlib
import re

import pytest
import yaml
from bs4 import BeautifulSoup

from scripts import design_board as db

ROOT = pathlib.Path(__file__).resolve().parent.parent
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def _spec(tmp_path, **over):
    (tmp_path / "shot.png").write_bytes(PNG)
    spec = {"title": "測試看板", "intro": "選一個。",
            "topics": [{"id": "photos", "question": "照片從哪裡來？", "recommend": "P1",
                        "why": "社群挑過的代表照。",
                        "options": [{"key": "P1", "title": "Wikidata 代表圖", "note": "先查 P18。", "image": "shot.png"},
                                    {"key": "P2", "title": "搜尋第一張", "note": "現在的做法。",
                                     "html": "<p class='x'>預覽</p>"}]},
                       {"id": "pill", "question": "按鈕多高？", "recommend": "T25b", "why": "跟標題同高。",
                        "options": [{"key": "T20", "title": "20px", "html": "<b>20</b>"},
                                    {"key": "T25b", "title": "25.5px", "html": "<b>25</b>"}]}]}
    spec.update(over)
    p = tmp_path / "board.yaml"
    p.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")
    return p


def test_the_board_is_one_offline_file_with_every_key(tmp_path):
    html = db.build(_spec(tmp_path))
    s = BeautifulSoup(html, "html.parser")
    assert [t["data-topic"] for t in s.select(".topic")] == ["photos", "pill"]
    keys = [k.get_text() for k in s.select(".card .k")]
    assert keys == ["P1", "P2", "T20", "T25b"]                          # the key is on every card
    assert s.select_one('.card[data-key="P1"] img')["src"].startswith("data:image/png;base64,")
    assert s.select_one('.card[data-key="P2"] .pv p.x').get_text() == "預覽"
    # nothing reaches out: no http(s) source or link anywhere
    assert not re.search(r'(src|href)\s*=\s*["\']https?:', html)
    assert "@font-face" in html                                          # the reader's fonts, embedded


def test_a_pick_is_a_radio_and_the_recommendation_is_marked(tmp_path):
    s = BeautifulSoup(db.build(_spec(tmp_path)), "html.parser")
    radios = s.select('.topic[data-topic="photos"] input[type=radio]')
    assert [(r["name"], r["value"]) for r in radios] == [("photos", "P1"), ("photos", "P2")]
    assert s.select_one('.card[data-key="P1"]').get("data-rec") == "1"
    assert s.select_one('.card[data-key="P2"]').get("data-rec") is None
    assert "社群挑過的代表照" in s.select_one('.topic[data-topic="photos"] .rec').get_text()
    assert s.select_one("noscript") and "代號" in s.select_one("noscript").get_text()


@pytest.mark.parametrize("bad,msg", [
    ({"key": "P1"}, "duplicate key P1"),
    ({"key": "P3", "image": "missing.png"}, "missing.png"),
])
def test_a_broken_spec_is_refused_with_its_reason(tmp_path, bad, msg):
    p = _spec(tmp_path)
    spec = yaml.safe_load(p.read_text(encoding="utf-8"))
    spec["topics"][0]["options"].append(dict({"title": "壞"}, **({"html": "x"} if "image" not in bad else {}), **bad))
    p.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match=re.escape(msg)):
        db.build(p)


def test_an_unknown_recommendation_is_refused(tmp_path):
    p = _spec(tmp_path)
    spec = yaml.safe_load(p.read_text(encoding="utf-8"))
    spec["topics"][1]["recommend"] = "T99"
    p.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="recommends T99"):
        db.build(p)


def test_the_board_is_written_where_git_never_tracks_it(tmp_path, monkeypatch):
    out = db.default_output(ROOT, _spec(tmp_path))
    assert out.parent == ROOT / ".design-board" and out.suffix == ".html"
    assert ".design-board/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_the_command_line_writes_the_board(tmp_path):
    """Run as `python scripts/design_board.py` (how agents call it): scripts/ then heads
    sys.path, where scripts/calendar.py shadowed the standard library's calendar and the
    font subsetter crashed. The command must work as a file, not only as an import."""
    import subprocess
    import sys
    out = tmp_path / "out.html"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "design_board.py"), str(_spec(tmp_path)), "-o", str(out)],
                       capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr[-800:]
    assert out.is_file() and "樣式看板" in out.read_text(encoding="utf-8") and r.stdout.strip() == str(out)


def test_an_option_can_show_several_captioned_shots(tmp_path):
    """A behaviour is a sequence (scroll, then open the map, then zoom): an option may give
    `images: [{image, caption}, ...]`, shown side by side, each with its caption."""
    (tmp_path / "a.png").write_bytes(PNG)
    (tmp_path / "b.png").write_bytes(PNG)
    spec = {"title": "多張", "topics": [{"id": "seq", "question": "?", "recommend": "A", "why": "w",
            "options": [{"key": "A", "title": "a", "images": [{"image": "a.png", "caption": "① 收起"}, {"image": "b.png", "caption": "② 打開"}]},
                        {"key": "B", "title": "b", "html": "<p>b</p>"}]}]}
    p = tmp_path / "s.yaml"
    p.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")
    s = BeautifulSoup(db.build(p), "html.parser")
    figs = s.select('.card[data-key="A"] .pv figure')
    assert [f.figcaption.get_text() for f in figs] == ["① 收起", "② 打開"]
    assert all(f.img["src"].startswith("data:image/png;base64,") for f in figs)
