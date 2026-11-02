"""Reservations on the day cards, the 住宿 screen and the 行前清單 screen."""
from bs4 import BeautifulSoup

from scripts.render.reader import render_reader
from tests import reservation_fixture as F

SKY = {"kind": "預約", "task": "晴空塔線上預約時段票", "due": "2026-05-05", "due_is_hard": True, "poi_id": "skytree"}


def _soup(res="fixture", checklist=None, pm=None):
    itin = F.itinerary()
    if checklist is not None:
        itin["checklist"] = checklist
    return BeautifulSoup(render_reader(itin, pm or F.poi_map(), legs=F.legs(),
                                       reservations=F.reservations() if res == "fixture" else res), "html.parser")


def _stop(s, pid):
    return s.select_one(f'.stop[data-poi="{pid}"]')


def _row(stop, label):
    dt = next((d for d in stop.select("dt") if d.get_text() == label), None)
    return dt.find_next_sibling("dd").get_text() if dt else None


def test_self_meal_card_is_suggested():
    card = _stop(_soup(), "izakaya")
    assert "sug" in card["class"]
    assert [t.get_text() for t in card.select(".sgt")] == ["建議", "建議"]       # open and closed heads


def test_booked_dinner_has_a_reservation_row():
    card = _stop(_soup(), "kappo")
    assert _row(card, "訂位") == "已訂・預約編號 ••••8213・3 位・會席套餐・5/10 前免費取消"
    assert [d.get_text() for d in card.select("dt")].index("訂位") < [d.get_text() for d in card.select("dt")].index("來源")


def test_ticket_card_and_its_checklist_line():
    s = _soup(checklist=[SKY])
    assert _row(_stop(s, "skytree"), "訂位") == "已訂・預約編號 ••••30X1・17:00 入場・3 張"
    assert "晴空塔線上預約時段票" not in s.select_one('section[data-pg="checklist"]').get_text()


def test_lodging_screen_line():
    lbk = _soup().select_one('section[data-pg="lodging"] .lrow .lbk')
    assert lbk.select_one(".bk-booked").get_text() == "已訂"
    assert lbk.get_text() == "已訂訂房編號 ••••3907・15:00 起・三人房，含早餐"


def test_checklist_screen_derives_and_merges():
    pm = F.poi_map()
    for pid in ("kappo", "izakaya"):
        pm[pid]["geocode"]["geocode_source"] = "cluster_fallback"
    sec = _soup(pm=pm).select_one('section[data-pg="checklist"]')
    text = sec.get_text()
    assert "訂上野示意洋食 13:00，3 位" in text
    assert text.count("地圖只標到區域中心") == 1
    note = next(d for d in sec.select("details.ci") if "區域中心" in d.get_text())
    assert "淺草示意居酒屋" in note.get_text() and "押上示意割烹" in note.get_text()


def test_without_reservations_cards_and_lodging_are_unchanged():
    s = _soup(None)
    assert not s.select(".sug, .sgt, .lbk") and _row(_stop(s, "kappo"), "訂位") is None
