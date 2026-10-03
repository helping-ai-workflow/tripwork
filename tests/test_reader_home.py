"""v1.0 P4 — mobile home (N1) and its three sub-screens (spec §6.1 / §6.2)."""
import copy

from bs4 import BeautifulSoup

from scripts.render.reader import render_reader
from tests.reader_fixture import itinerary, poi_map, reader_kwargs


def _soup(itin=None, **over):
    kw = reader_kwargs()
    kw.update(over)
    return BeautifulSoup(render_reader(itin or itinerary(), poi_map(), **kw), "html.parser")


def _home(s):
    return s.select_one('section.page.home[data-pg="home"]')


def test_the_headline_and_the_date_line():
    h = _home(_soup())
    assert h.select_one("h1.headline").get_text(strip=True) == reader_kwargs()["brief"]["headline"]["text"]
    dates = h.select_one("p.dates").get_text()
    assert "測試 3天2夜" in dates and "10/12（一）" in dates and "10/14（三）" in dates


def test_the_stamp_calendar():
    h = _home(_soup())
    assert len(h.select(".month")) == 1
    assert [w.get_text() for w in h.select(".g .wd")] == list("日一二三四五六")
    stamps = h.select("label.stamp")
    assert [s["for"] for s in stamps] == ["pg-d1", "pg-d2", "pg-d3"]
    assert all("--t:" in s["style"] for s in stamps)
    assert "r1" in stamps[0]["class"] and "r1" in stamps[1]["class"]      # same area, same colour
    assert "r0" in stamps[2]["class"] and "返程" in stamps[2].get_text()
    assert "函館" in stamps[0].get_text() and "12" in stamps[0].get_text()
    offs = h.select(".g .off")
    assert offs and all(o.name == "span" for o in offs)                  # not clickable
    assert any("sun" in o["class"] and o.get_text() == "11" for o in offs)


def test_the_three_tiles():
    h = _home(_soup())
    tiles = {t["for"]: t.get_text(" ", strip=True) for t in h.select("label.tile")}
    assert "住宿" in tiles["pg-lodging"] and "1 間" in tiles["pg-lodging"]
    assert "入境規定" in tiles["pg-advisory"] and "2 項" in tiles["pg-advisory"]
    assert "行前清單" in tiles["pg-checklist"] and "3 項" in tiles["pg-checklist"]


def test_the_lodging_screen():
    p = _soup().select_one('section.page.sub[data-pg="lodging"]')
    assert p.select_one('label.back[for="pg-home"]').get_text(strip=True) == "‹ 總覽"
    rows = p.select(".lrow")
    assert len(rows) == 1
    text = rows[0].get_text(" ", strip=True)
    assert "函館示意飯店" in text and "10/12 → 10/14" in text and "2 晚" in text
    assert rows[0].select_one("a.navb") and not p.select("details")


def test_the_advisory_screen():
    p = _soup().select_one('section.page.sub[data-pg="advisory"]')
    items = p.select("details.adv")
    assert len(items) == 2 and not any(d.has_attr("open") for d in items)
    assert "risk-banned" in items[0]["class"] and items[0].select_one(".rk").get_text() == "禁止"
    assert "所有肉製品禁止攜入日本" in items[0].select_one("summary .do").get_text()
    assert items[0].select_one('a[href="https://www.maff.go.jp/aqs/"]')
    assert "risk-info" in items[1]["class"] and items[1].select_one(".rk").get_text() == "須知"


def test_the_checklist_screen():
    p = _soup().select_one('section.page.sub[data-pg="checklist"]')
    assert [g.select_one("h3").get_text() for g in p.select(".ckg")] == ["預約", "出發前確認", "打包"]
    items = p.select(".ci")
    hard = items[0]
    assert hard.name == "details" and not hard.has_attr("open")
    assert "hard" in hard.select_one(".due")["class"]
    assert hard.select_one(".origin").get_text() == "D2・10/13"
    assert hard.select_one('a[href="https://334.co.jp/"]')
    assert items[1].name == "div" and not items[1].select(".cv")      # nothing to open, no ⌄


def test_empty_subscreens_say_so():
    itin = itinerary()
    itin["checklist"] = []
    s = _soup(itin, advisory={"items": []})
    tiles = {t["for"]: t.get_text(" ", strip=True) for t in _home(s).select("label.tile")}
    assert "0 項" in tiles["pg-advisory"] and "0 項" in tiles["pg-checklist"]
    for pg in ("advisory", "checklist"):
        assert s.select_one(f'section.page.sub[data-pg="{pg}"] .empty')


def test_a_same_day_trip_has_one_stamp():
    itin = itinerary()
    day = itin["days"][2]
    day["date"] = "2026-10-12"
    itin["days"] = [day]
    kw = reader_kwargs()
    kw["brief"]["dates"] = {"start": "2026-10-12", "end": "2026-10-12"}
    s = _soup(itin, brief=kw["brief"])
    assert len(_home(s).select("label.stamp")) == 1


def test_a_cross_month_trip_is_one_card():
    itin = itinerary()
    for d, date in zip(itin["days"], ("2026-11-30", "2026-12-01", "2026-12-02")):
        d["date"] = date
    kw = reader_kwargs()
    kw["brief"]["dates"] = {"start": "2026-11-30", "end": "2026-12-02"}
    s = _soup(itin, brief=kw["brief"])
    # v1.1 §6.2: one card for a trip across months (was two months side by side)
    assert len(_home(s).select(".month")) == 1
    assert _home(s).select_one(".month h3").get_text() == "2026 年 11～12 月"
    mini = s.select_one('section.page.day[data-pg="d2"] .mini')
    assert len(mini.select(".g > :not(.wd)")) == 7          # only the one week holding trip days


def test_a_cross_month_trip_draws_each_stamp_once():
    """P4 review I1: a trip across a month boundary drew its stamps in both months."""
    itin = itinerary()
    for d, date in zip(itin["days"], ("2026-11-30", "2026-12-01", "2026-12-02")):
        d["date"] = date
    kw = reader_kwargs()
    kw["brief"]["dates"] = {"start": "2026-11-30", "end": "2026-12-02"}
    h = _home(_soup(itin, brief=kw["brief"]))
    assert [s["for"] for s in h.select("label.stamp")] == ["pg-d1", "pg-d2", "pg-d3"]
    assert h.select_one('label.stamp[for="pg-d2"] b').get_text() == "12/1"      # v1.1: M/1 across months


def test_every_input_opts_out_of_form_state_restore():
    """P4 review (re-graded): a browser restoring radio/checkbox state on reload would
    reopen the light theme or a stop; spec §6.6 opens dark every time."""
    s = _soup()
    assert all(i.get("autocomplete") == "off" for i in s.select("input"))
