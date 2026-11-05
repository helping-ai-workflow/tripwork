"""The 移動列 shows its booking (reservation.road_line): booked / todo carry a label and the
first two details, a none with details shows them without one, everything else is the
one line it was before."""
from bs4 import BeautifulSoup

from scripts.render.reader import render_reader
from scripts.render.reader.day import leg
from tests import reservation_fixture as F


def _soup(res=None, itin=None, legs=None):
    return BeautifulSoup(render_reader(itin or F.itinerary(), F.poi_map(), legs=legs or F.legs(),
                                       reservations=res or F.reservations()), "html.parser")


def _legs(s, day):
    return s.select(f'section[data-pg="d{day}"] .leg')


def _vals(div):
    return [v.get_text() for v in div.select(".lrv")]


def _set(res, frm, to, **kw):
    for r in res["reservations"]:
        if r.get("from") == frm and r.get("to") == to:
            r.update(kw)
            for k in [k for k, v in kw.items() if v is None]:
                del r[k]
    return res


def test_booked_flight_leg_shows_label_and_two_values():
    s = _soup()
    div = _legs(s, 1)[0]                                     # SA 101, a leg_index row
    assert "lr" in div["class"]
    assert div.select_one(".lrk-booked").get_text() == "已訂"
    assert _vals(div) == ["32A・32B・32C", "每人託運 23 kg"]
    assert "K7Q2PX" not in str(div) and "••••" not in str(div)


def test_none_leg_with_details_has_values_no_label():
    div = _legs(_soup(), 1)[1]                               # 京急, none with one detail
    assert div.select_one(".lrk") is None
    assert _vals(div) == ["刷 IC 卡，不用買票"]


def test_none_leg_without_details_is_unchanged():
    itin, legs = F.itinerary(), F.legs()
    row = itin["days"][2]["rows"][0]                         # 淺草→羽田, none, no details
    div = _legs(_soup(), 3)[0]
    assert str(div) == str(BeautifulSoup(leg(row, legs["legs"]), "html.parser").div)
    assert "lr" not in div["class"]


def test_todo_leg_label():
    res = _set(F.reservations(), "羽田空港", "桃園機場", status="todo", ref=None)
    div = _legs(_soup(res), 3)[1]
    assert div.select_one(".lrk-todo").get_text() == "還要訂"
    assert _vals(div) == ["41A・41B・41C"]


def test_booked_without_details_label_only():
    res = _set(F.reservations(), "羽田空港", "桃園機場", details=None)
    div = _legs(_soup(res), 3)[1]
    assert div.select_one(".lrk-booked").get_text() == "已訂"
    assert div.select(".lrv") == []


def test_value_is_escaped():
    res = _set(F.reservations(), "羽田空港", "桃園機場", details=[{"label": "座位", "value": "<b>&</b>"}])
    div = _legs(_soup(res), 3)[1]
    assert _vals(div) == ["<b>&</b>"]
    assert "<b>&</b>" not in str(div)


def test_unmatched_leg_identical_to_310():
    itin, legs = F.itinerary(), F.legs()
    row = itin["days"][1]["rows"][3]                         # the taxi, no reservation
    div = _legs(_soup(), 2)[0]
    assert str(div) == str(BeautifulSoup(leg(row, legs["legs"]), "html.parser").div)
