"""md day table: a move cell carries its booking by the reader's rule (reservation.road_line),
skipping a value its row text already spells out; the 交通 list never reads 「。，」."""
from scripts.render.markdown import render_markdown_page
from tests import reservation_fixture as F


def _md(itin=None, legs=None, res=None):
    return render_markdown_page(itin or F.itinerary(), F.poi_map(), legs=legs or F.legs(),
                                reservations=res or F.reservations())


def _line(md, needle):
    return next(l for l in md.splitlines() if l.startswith("|") and needle in l)


def _section(md, head):
    start = md.index(f"## {head}\n")
    end = md.find("\n## ", start + 3)
    return md[start:] if end < 0 else md[start:end]


def test_booked_flight_cell():
    assert _line(_md(), "SA 101").endswith("示意航空 SA 101（已訂・32A・32B・32C・每人託運 23 kg） |")


def test_none_cell_values_only():
    assert _line(_md(), "京急線直通淺草線").endswith("京急線直通淺草線（刷 IC 卡，不用買票） |")


def test_none_without_details_unchanged():
    assert "（" not in _line(_md(), "淺草線直通京急線")


def test_r2_drops_value_already_in_text():
    itin = F.itinerary()
    itin["days"][2]["rows"][1]["text"] = "示意航空 SA 102，座位 41A・41B・41C"
    assert _line(_md(itin=itin), "SA 102").endswith("座位 41A・41B・41C（已訂） |")


def test_r2_none_all_in_text_adds_nothing():
    itin = F.itinerary()
    itin["days"][0]["rows"][1]["text"] = "京急線直通淺草線，刷 IC 卡，不用買票"
    assert "（" not in _line(_md(itin=itin), "京急線直通淺草線")


def test_pipe_in_value_does_not_break_table():
    res = F.reservations()
    next(r for r in res["reservations"] if r.get("to") == "桃園機場")["details"] = [{"label": "座位", "value": "41A | 41B"}]
    md = _md(res=res)
    assert "41A" in _line(md, "SA 102")
    assert _line(md, "SA 102").count(" | ") == _line(md, "SA 101").count(" | ")


def test_transport_list_no_period_comma():
    itin, legs = F.itinerary(), F.legs()
    itin["days"][0]["rows"][1]["text"] = "京急線直通淺草線。"
    del legs["legs"][1]["service"]
    assert "。，" not in _section(_md(itin=itin, legs=legs), "交通")


def test_md_never_shows_ref():
    md = _md()
    assert not [r for r in F.REFS if r in md]


def test_r2_keeps_a_short_value_inside_a_longer_token():
    """「2A」 is not spelled out by 「12A」, nor 「10」 by 「2190」: the md must not drop a seat."""
    itin, res = F.itinerary(), F.reservations()
    itin["days"][2]["rows"][1]["text"] = "示意航空 SA 102，飛 2190 km，報到 12A 櫃台"
    next(r for r in res["reservations"] if r.get("to") == "桃園機場")["details"] = [
        {"label": "車廂", "value": "10"}, {"label": "座位", "value": "2A"}]
    assert _line(_md(itin=itin, res=res), "SA 102").endswith("櫃台（已訂・10・2A） |")
