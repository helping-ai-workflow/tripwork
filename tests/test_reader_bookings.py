"""The reader's 交通 / 餐廳 tiles and screens (reservations.yaml), and 出入境規定."""
from bs4 import BeautifulSoup

from scripts.export_gate import run_html_gate
from scripts.render.reader import render_reader
from tests import reservation_fixture as F


def _html(res="fixture"):
    return render_reader(F.itinerary(), F.poi_map(), legs=F.legs(),
                         reservations=F.reservations() if res == "fixture" else res)


def _soup(res="fixture"):
    return BeautifulSoup(_html(res), "html.parser")


def _tiles(s):
    return {t["for"]: t.get_text(" ", strip=True) for t in s.select("section.page.home label.tile")}


def test_five_tiles_in_order():
    s = _soup()
    assert [t["for"] for t in s.select("section.page.home label.tile")] == [
        "pg-lodging", "pg-transport", "pg-meals", "pg-advisory", "pg-checklist"]
    adv = _tiles(s)["pg-advisory"]
    assert "出入境規定" in adv and "入境規定" not in adv.replace("出入境規定", "")
    assert s.select_one('section.page.sub[data-pg="advisory"] h2').get_text() == "出入境規定"


def test_tile_counts_and_todo():
    t = _tiles(_soup())
    assert "交通" in t["pg-transport"] and "4 段" in t["pg-transport"] and "待訂" not in t["pg-transport"]
    assert "餐廳" in t["pg-meals"] and "3 餐" in t["pg-meals"] and "1 待訂" in t["pg-meals"]


def test_without_reservations_the_tiles_say_zero_and_the_screens_are_empty():
    s = _soup(None)
    t = _tiles(s)
    assert "0 段" in t["pg-transport"] and "0 餐" in t["pg-meals"]
    assert s.select_one('section.page.sub[data-pg="transport"] .empty').get_text() == "這趟沒有記下長途交通的訂位。"
    assert s.select_one('section.page.sub[data-pg="meals"] .empty').get_text() == "這趟沒有記下餐廳。"


def test_transport_lists_only_reserved_moves():
    titles = [b.get_text() for b in _soup().select('section[data-pg="transport"] .bn')]
    assert titles == ["示意航空 SA 101", "京急線直通淺草線", "淺草線直通京急線", "示意航空 SA 102"]
    assert "計程車回飯店" not in _soup().select_one('section[data-pg="transport"]').get_text()


def test_rows_by_date_with_pill_and_masked_details():
    sec = _soup().select_one('section[data-pg="transport"]')
    assert [h.get_text() for h in sec.select("h3.bkd")] == ["5/12（二）", "5/14（四）"]
    first = sec.select_one("details.bkrow")
    assert first.select_one(".bt").get_text() == "08:50"
    assert first.select_one(".bs").get_text() == "桃園機場 08:50 → 羽田空港 13:00"
    assert first.select_one(".bk.bk-booked").get_text() == "已訂"
    dl = first.select_one("dl.bd").get_text()
    assert "••••PX" in dl and "32A・32B・32C" in dl
    assert [b.get_text() for b in sec.select(".bk")] == ["已訂", "不用訂", "不用訂", "已訂"]


def test_meals_states_and_self_subtitle():
    sec = _soup().select_one('section[data-pg="meals"]')
    assert [b.get_text() for b in sec.select(".bk")] == ["自理", "還要訂", "已訂"]
    assert sec.select_one(".bk-self").find_parent("details").select_one(".bs").get_text() == "居酒屋晚餐・建議，可換別家"


def test_no_full_number_anywhere():
    html = _html()
    assert not any(ref in html for ref in F.REFS)


def test_html_gate_passes():
    assert run_html_gate(_html(), list(F.poi_map().values()), min_days=3)["failures"] == []
