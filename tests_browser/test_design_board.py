"""The design board in a browser: a pick and a note become the line to paste back to any
agent; with no script the cards still show and a pick still lights its card."""
import pathlib

import pytest
import yaml
from conftest import DESKTOP, PHONE

from scripts import design_board as db


@pytest.fixture()
def board(tmp_path):
    spec = {"title": "測試看板", "topics": [
        {"id": "photos", "question": "照片？", "recommend": "P1", "why": "代表照。",
         "options": [{"key": "P1", "title": "代表圖", "html": "<p>一</p>"}, {"key": "P2", "title": "搜尋", "html": "<p>二</p>"}]},
        {"id": "pill", "question": "高度？", "recommend": "T25b", "why": "同高。",
         "options": [{"key": "T20", "title": "20", "html": "<p>三</p>"}, {"key": "T25b", "title": "25.5", "html": "<p>四</p>"}]}]}
    p = tmp_path / "b.yaml"
    p.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")
    out = tmp_path / "board.html"
    out.write_text(db.build(p), encoding="utf-8")
    return out.as_uri()


@pytest.mark.parametrize("vp", [PHONE, DESKTOP], ids=["phone", "desktop"])
def test_picks_and_a_note_become_the_line_to_paste(open_page, board, vp):
    pg = open_page(vp, js=True, url=board)
    pg.locator('.card[data-key="P2"]').click()
    pg.locator('.card[data-key="T25b"]').click()
    pg.locator('.topic[data-topic="pill"] textarea').fill("再細一點")
    pg.locator("#copy").click()
    line = pg.locator("#line").text_content()
    assert line == "樣式看板「測試看板」：photos=P2；pill=T25b（再細一點）", line
    assert pg.locator("#copy").text_content() in ("已複製，貼回對話", "請手動複製下面那行")


def test_with_no_script_a_pick_still_lights_its_card(open_page, board):
    pg = open_page(PHONE, js=False, url=board)
    assert pg.locator(".card").count() == 4
    pg.locator('.card[data-key="P1"]').click()
    on = pg.eval_on_selector('.card[data-key="P1"]', "e=>getComputedStyle(e).boxShadow")
    off = pg.eval_on_selector('.card[data-key="P2"]', "e=>getComputedStyle(e).boxShadow")
    assert on != off, (on, off)
