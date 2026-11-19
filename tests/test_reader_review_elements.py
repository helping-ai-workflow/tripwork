"""The reader's new elements from the 2026-11-18 review, at the user's picks (2026-11-19):
M1 move notes open, X1 transfer dot, A4 no-address sheet, D1 dining row, C1 cancel
banner, W3 weather in the 地圖 row, B theme button hidden under 給司機看. The prototype
trip of the design board, rendered by the shipped reader."""
import copy
import datetime

from bs4 import BeautifulSoup

from scripts.render.reader import render_reader
from scripts.render.reader.theme import CSS
from tests.reader_fixture import _mv

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "docs" / "images" / "readme"))
import demo_trip as D                                     # noqa: E402

TZ = datetime.timezone(datetime.timedelta(hours=9))


def _trip(fetched=None):
    itin = D.itinerary()
    d2 = itin["days"][1]["rows"]
    k = next(i for i, r in enumerate(d2) if r.get("text", "").startswith("銀座線＋淺草線"))
    d2[k:k + 1] = [
        dict(_mv("rail", 3, 12, basis="sourced", text="銀座線 往淺草方向", source_url="https://rail.example/g"),
             time="15:40", board_at="上野広小路駅 2番線", board_at_en="Ueno-hirokoji", alight_at="浅草駅",
             alight_at_en="Asakusa", route="銀座線", route_en="Ginza Line", pay="刷 IC 卡"),
        {"slot": "transfer", "place": "浅草駅（淺草站）", "platform": "淺草線 1番線", "text": "跟藍色指標走"},
        dict(_mv("rail", 1.5, 3, basis="sourced", text="都營淺草線", source_url="https://rail.example/a"), time="16:20")]
    pois = copy.deepcopy(D.POIS)
    for p in pois:
        if p["id"] == "ameyoko":
            src = "https://ameyoko.example/"
            p["dining"] = {"order": {"value": "ticket_machine", "source_url": src},
                           "payment": {"value": ["cash"], "source_url": src},
                           "self_service": {"value": True, "source_url": src}}
    res = copy.deepcopy(D.RESERVATIONS)
    res["reservations"].append({"date": "2026-05-13", "from": "上野", "to": "鎌倉", "status": "cancel",
                                "ref": "ZX99812", "cancel_by": "2026-05-12 18:00", "cancel_how": "到窗口退"})
    fc = {"fetched_at": (fetched or datetime.datetime.now(TZ)).isoformat(timespec="minutes"), "days": [
        {"date": "2026-05-13", "tmin": 15, "tmax": 19, "weather": "多雲短暫雨", "rain": True,
         "kind": "official", "source": "示意", "source_url": "https://jma.example/"}]}
    html = render_reader(itin, {p["id"]: p for p in pois + [D.HOTEL]}, brief=D.brief(), accommodations=D.ACC,
                         advisory=D.R.ADVISORY, legs=D.LEGS, cost=D.COST, reservations=res, forecast=fc)
    return BeautifulSoup(html, "html.parser")


def test_move_notes_are_open_with_one_fact_a_line():
    s = _trip().select_one('section[data-pg="d2"]')
    leg = next(l for l in s.select(".leg") if "Ginza Line" in l.get_text())
    facts = [f.select_one("b").get_text() for f in leg.select(".lfa .lf")]
    assert facts == ["上車", "車次", "下車", "付款", "售票機"]
    assert leg.select_one(".lnt").get_text() == "銀座線 往淺草方向" and not leg.select("details")


def test_a_transfer_is_a_dot_on_the_line_with_its_wait():
    t = _trip().select_one('section[data-pg="d2"] .tfr')
    assert t.select_one(".tdot") and t.select_one(".tn").get_text() == "浅草駅（淺草站）"
    assert t.select_one(".twt").get_text() == "等 28 分" and "淺草線 1番線" in t.get_text()


def test_no_address_sheet_names_the_place_and_points_at_navigation():
    s = _trip().select_one('section[data-pg="d1"] .stop[data-poi="izakaya"]')
    sheet = s.select_one(".drv").get_text()
    assert "浅草サンプル居酒屋" in sheet and "淺草" in sheet and "按「導航」用 Google 地圖" in sheet


def test_dining_is_a_row_of_the_opened_stop():
    s = _trip().select_one('section[data-pg="d2"] .stop[data-poi="ameyoko"]')
    rows = {dt.get_text(): dd.get_text() for dt, dd in zip(s.select("dl > dt"), s.select("dl > dd"))}
    assert rows["用餐"] == "餐券機點餐・只收現金・吃完自己收餐具" and not s.select(".hd .dng")


def test_cash_only_joins_the_checklist_and_the_cancel_shows_twice():
    soup = _trip()
    text = soup.select_one('[data-pg="checklist"]').get_text()
    assert "準備現金" in text and "取消 上野→鎌倉 的訂位" in text
    banner = soup.select_one('section[data-pg="d2"] .cnls .cnl')
    assert "要取消" in banner.get_text() and "2026-05-12 18:00 前" in banner.get_text()
    assert "ZX99812" not in str(soup)                               # masked as every number is


def test_weather_takes_no_height_of_its_own():
    s = _trip().select_one('section[data-pg="d2"]')
    assert s.select_one(".mapc > summary .wxs").get_text() == "15～19°雨"
    assert s.select_one(".mapc > .wx")["data-at"].endswith(":00+09:00")   # Safari-parsable
    assert not s.select(".pcal .wx") and not s.select(".dh .wxs")


def test_the_theme_button_hides_under_the_drivers_sheet():
    assert ":root:has(.drv:target) .bubble{display:none}" in CSS
