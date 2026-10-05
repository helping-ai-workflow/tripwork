"""v1.1 topic 6 (user picks on the design board, 2026-10-01): the desktop day title sits
at the top of the list; the home is the phone month card zoomed x1.9 with each day's
theme on its stamp ring; a 旅程與費用 card; a zoom bar under the enlarged map."""
from bs4 import BeautifulSoup

from scripts.render.reader import render_reader
from tests.reader_fixture import itinerary, poi_map, reader_kwargs


def _soup(itin=None, **over):
    kw = reader_kwargs()
    kw.update(over)
    return BeautifulSoup(render_reader(itin or itinerary(), poi_map(), **kw), "html.parser")


def test_the_day_title_also_heads_the_list():
    d2 = _soup().select_one('section[data-pg="d2"]')
    head = d2.select_one(".plist > h2.dh.dh-list")
    assert head is not None and d2.select_one(".plist").contents[0] is head
    assert head.select_one(".dht").get_text() == d2.select_one(".pcal h2.dh .dht").get_text()


from scripts.render.reader import month_calendar


def test_the_home_month_card_has_its_own_panel_and_no_big_grid():
    s = _soup()
    home = s.select_one("section.page.home .hwrap")
    assert home.select_one(":scope > .hcal .months .month") is not None
    assert home.select_one(".hside .months") is None and s.select_one(".dh2") is None


def test_each_trip_stamp_carries_its_theme_on_a_ring():
    s = _soup()
    stamps = s.select(".hcal .stamp")
    themes = [d.get("theme") for d in itinerary()["days"]]
    assert [st.select_one("svg.ring textPath").get_text() for st in stamps] == themes
    tp = stamps[1].select_one("svg.ring textPath")
    assert tp["startoffset"] == "50%" and tp["text-anchor"] == "middle"     # html.parser lowercases names
    assert stamps[1].select_one("svg.ring text")["dominant-baseline"] == "text-after-edge"
    # the path starts at the bottom, so the top is its midpoint
    d = stamps[1].select_one("svg.ring path")["d"]
    assert d.startswith("M70,") and " 0 1,1 0,-" in d


def test_a_long_theme_ends_in_an_ellipsis():
    assert month_calendar.ring_text("一二三四五六七八九十一二三四五") == "一二三四五六七八九十一二三四五"   # 15 fits
    assert month_calendar.ring_text("一二三四五六七八九十一二三四五六") == "一二三四五六七八九十一二三四…"


def test_a_day_without_theme_rings_its_label_and_without_either_has_no_ring():
    itin = itinerary()
    itin["days"][0].pop("theme")
    itin["days"][0]["label"] = "Day 1 函館"
    itin["days"][1].pop("theme")
    itin["days"][1].pop("label", None)
    stamps = _soup(itin).select(".hcal .stamp")
    assert stamps[0].select_one("textPath").get_text() == "Day 1 函館"
    assert stamps[1].select_one("svg.ring") is None


def test_a_trip_across_months_rings_every_trip_stamp():
    itin = itinerary()
    for d, date in zip(itin["days"], ["2026-10-30", "2026-10-31", "2026-11-01"]):
        d["date"] = date
    assert len(_soup(itin).select(".hcal .stamp svg.ring")) == 3


def test_the_phone_never_draws_the_ring():
    from scripts.render.reader.theme import CSS
    assert ".ring{display:none}" in CSS.replace(" ", "")


def test_a_cost_line_item_can_name_its_lodging(tmp_path):
    import yaml
    from scripts.validate_artifact import validate_file
    f = tmp_path / "cost.yaml"
    f.write_text(yaml.safe_dump({"currency": "JPY", "total": 100, "by_category": {"lodging": 100},
                                 "as_of": "2026-10-01", "estimate_note": "估算",
                                 "line_items": [{"category": "lodging", "label": "x", "amount": 100, "poi_id": "hak-hotel"}]}),
                 encoding="utf-8")
    assert validate_file(str(f))[0] == 0, validate_file(str(f))[1]


def test_the_reader_takes_cost():
    from scripts.render.html_page import render_html_page
    render_html_page(itinerary(), poi_map(), cost={"currency": "JPY", "total": 0, "by_category": {}, "line_items": []},
                     **reader_kwargs())


def test_cost_rollup_says_lodging_items_carry_poi_id():
    import pathlib
    text = (pathlib.Path(__file__).resolve().parent.parent / "skills/cost-rollup/SKILL.md").read_text(encoding="utf-8")
    assert "poi_id" in text


# --- the 旅程與費用 card (topic 6, picks C2 + S) ---

COST = {"currency": "JPY", "total": 450000, "by_category": {"lodging": 543688, "transport": 107720},
        "pass_break_even": {"use_pass": True},
        "line_items": [{"category": "lodging", "label": "a", "amount": 120000, "poi_id": "hak-hotel"},
                       {"category": "transport", "label": "t", "amount": 107720}]}


def _card(itin=None, **over):
    return _soup(itin, **over).select_one(".hside section.trip")


def test_the_trip_card_lists_each_stay_with_its_cost():
    card = _card(cost=COST)
    rows = card.select("ol > li")
    assert [r.select_one("b").get_text() for r in rows] == ["函館", "返程"]
    assert rows[0].select_one("span").get_text() == "2 晚・函館示意飯店"
    assert rows[0].select_one("em").get_text() == "¥120,000" and "r1" in rows[0]["class"]
    assert rows[1].select_one("em") is None and "r0" in rows[1]["class"]
    assert card.select_one("h3").get_text() == "旅程與費用"
    assert card.select_one(".tt:not(.sum) span").get_text() == "交通（含周遊券）"
    assert card.select_one(".tt:not(.sum) em").get_text() == "¥107,720"
    assert card.select_one(".tt.sum em").get_text() == "¥450,000"
    assert card.select_one(".tn").get_text() == "估算，不含餐飲、門票"


def test_a_stay_without_a_linked_cost_shows_no_amount():
    old = dict(COST, line_items=[{k: v for k, v in li.items() if k != "poi_id"} for li in COST["line_items"]])
    card = _card(cost=old)
    assert all(li.select_one("em") is None for li in card.select("ol > li"))
    assert card.select_one(".tt.sum em").get_text() == "¥450,000"


def test_without_cost_the_card_is_the_route():
    card = _card(cost=None)
    assert card.select_one("h3").get_text() == "旅程" and card.select_one(".tt") is None


def test_a_trip_without_lodging_has_no_card():
    itin = itinerary()
    for d in itin["days"]:
        d.pop("lodging", None)
    assert _soup(itin, cost=COST).select_one("section.trip") is None


def test_an_incidental_allowance_changes_the_note():
    c = dict(COST, by_category=dict(COST["by_category"], incidental=1000))
    assert _card(cost=c).select_one(".tn").get_text() == "估算，餐飲等以每日零用計"


def test_no_pass_no_bracket():
    c = {k: v for k, v in COST.items() if k != "pass_break_even"}
    assert _card(cost=c).select_one(".tt:not(.sum) span").get_text() == "交通"


def test_the_dates_line_breaks_into_two_spans():
    from scripts.render.heading import dates_line
    from tests.reader_fixture import brief
    a, _, b = dates_line(brief(), itinerary()).partition("・")
    d = _soup().select_one(".hside .dates")
    assert [s.get_text() for s in d.select("span.dl")] == [a, b] and d.select_one(".dsep").get_text() == "・"


# --- the zoom bar (topic 6, Z1-a + close rule A) ---

def test_a_tiled_view_has_a_zoom_bar_with_the_osm_link_and_close():
    from tests.test_reader_maps import side_file
    s = _soup(maps=side_file())
    views = s.select('section[data-pg="d2"] .mv')
    assert views
    for mv in views:
        zid = mv.select_one("input.zck")["id"]
        assert mv.select_one(f'label.zbg[for="{zid}"]') is not None
        bar = mv.select_one(".zbar")
        assert bar.select_one(f'label.zx[for="{zid}"]').get_text() == "✕ 關閉"
        if mv.select_one(".mimg"):
            a = bar.select_one("a.zlink")                 # user check: the live map of this area
            assert a["href"].startswith("https://www.google.com/maps/@") and a.get_text() == "在 Google Maps 開這裡 ↗"
    assert s.select(".attrmini") and all(c.name == "span" for c in s.select(".attrmini"))   # plain text


def test_a_photo_has_the_same_bar():
    s = _soup()
    fig = s.select_one("figure.bp")
    pid = fig.select_one("input.pz")["id"]
    assert fig.select_one(f'label.zbg[for="{pid}"]') and fig.select_one(f'.zbar label.zx[for="{pid}"]').get_text() == "✕ 關閉"


def test_one_hotel_in_two_separate_stays_shows_each_stays_cost():
    """Review I1: 函館 -> 大沼 -> 函館 with the same hotel twice; each stay shows its own
    line item, not the hotel's sum."""
    import copy
    itin = itinerary()
    pm = copy.deepcopy(poi_map())
    pm["onuma"] = dict(pm["hak-hotel"], id="onuma", name_zh="大沼旅館")
    itin["days"][0]["lodging"], itin["days"][1]["lodging"], itin["days"][2]["lodging"] = "hak-hotel", "onuma", "hak-hotel"
    kw = reader_kwargs()
    stop = kw["accommodations"]["stops"][0]
    kw["accommodations"] = {"stops": [stop, dict(stop, area_label="大沼", chosen="onuma"), stop]}
    kw["cost"] = {"currency": "JPY", "total": 75000, "by_category": {"lodging": 75000},
                  "line_items": [{"category": "lodging", "label": "a", "amount": 20000, "poi_id": "hak-hotel"},
                                 {"category": "lodging", "label": "b", "amount": 25000, "poi_id": "onuma"},
                                 {"category": "lodging", "label": "c", "amount": 30000, "poi_id": "hak-hotel"}]}
    card = BeautifulSoup(render_reader(itin, pm, **kw), "html.parser").select_one("section.trip")
    assert [li.select_one("em").get_text() for li in card.select("ol > li") if li.select_one("em")] == ["¥20,000", "¥25,000", "¥30,000"]
