"""v1.0 P5 — the day map card (spec §6.5 / §6.8). Expected pin positions come from
the shipped scripts/render/reader/maps.py::project, never re-derived here."""
import re
import copy

import pytest
from bs4 import BeautifulSoup

from scripts.render.reader import render_reader
from scripts.render.reader.maps import LABELS, MARGIN, project
from tests.reader_fixture import itinerary, poi_map, reader_kwargs

BBOX = {"north": 41.80, "south": 41.75, "east": 140.77, "west": 140.70}
YAMA_BOX = {"north": 41.763, "south": 41.756, "east": 140.709, "west": 140.700}


OVERVIEW = "data:image/png;base64,T1ZFUlZJRVc="
CLOSE = "data:image/png;base64,Q0xPU0VVUA=="


def side_file(days=("2026-10-13",), bbox=BBOX):
    seg = {"image": {"data": OVERVIEW, "width": 1000, "height": 800}, "bbox": bbox,
           "closeups": {"hak-yama": {"image": {"data": CLOSE, "width": 640, "height": 480},
                                     "bbox": YAMA_BOX}}}
    return {"attribution": "© OpenStreetMap contributors", "days": {d: [copy.deepcopy(seg)] for d in days}}


def _day(n, itin=None, maps="default", pm=None, **over):
    kw = reader_kwargs()
    kw.update(over)
    html = render_reader(itin or itinerary(), pm or poi_map(), maps=side_file() if maps == "default" else maps, **kw)
    return BeautifulSoup(html, "html.parser").select_one(f'section.page.day[data-pg="d{n}"]')


def _pin(view, pid):
    return view.select_one(f'g.pin[data-poi="{pid}"]')


def test_the_card_is_a_collapsed_map_row():
    card = _day(2).select_one("details.mapc")
    assert card and not card.has_attr("open")
    summary = card.select_one("summary")
    assert "地圖" in summary.get_text() and summary.select_one("svg") and summary.select_one(".cv")


def test_chips_jump_to_the_same_targets_as_the_list():
    d = _day(2)
    chips = d.select(".mapc .chips a.chip")
    assert [c.get_text() for c in chips] == ["全圖", LABELS["hotel_start"], "08:00", "10:00", "17:00",
                                             LABELS["hotel_end"]]
    assert [c["href"] for c in chips] == ["#t-d2-top", "#t-d2-start", "#t-d2-s1", "#t-d2-s3", "#t-d2-s5", "#t-d2-end"]
    for c in chips:                                                       # every chip lands somewhere real
        assert d.select_one(c["href"])


def test_one_view_per_selection():
    d = _day(2)
    views = [v["class"][1] for v in d.select(".mapc .mv")]
    assert views == ["mv-d2-all", "mv-d2-start", "mv-d2-s1", "mv-d2-s3", "mv-d2-s5", "mv-d2-end"]


def test_the_overview_pins_every_stop_and_one_hotel_capsule():
    allv = _day(2).select_one(".mv-d2-all")
    assert allv.select_one(".mimg")
    pins = allv.select("g.pin")
    assert sorted(p["data-poi"] for p in pins) == ["hak-asaichi", "hak-goryokaku", "hak-hotel", "hak-yama"]
    assert LABELS["hotel_merged"] in _pin(allv, "hak-hotel").get_text()
    assert _pin(allv, "hak-asaichi").select_one("text").get_text() == "08:00"
    assert not allv.select("polyline, path.route-line")                  # no visiting-order line


def test_pins_are_projected_through_the_shipped_function():
    c = _pin(_day(2).select_one(".mv-d2-all"), "hak-yama").select_one("circle")
    x, y = project(41.7594, 140.7045, BBOX, 1000, 800)
    assert (float(c["cx"]), float(c["cy"])) == (round(x, 1), round(y, 1))


def test_a_pin_near_the_edge_is_clamped_inside_the_margin():
    edge = {"north": 41.7970, "south": 41.75, "east": 140.77, "west": 140.70}   # goryokaku on the top edge
    c = _pin(_day(2, maps=side_file(bbox=edge)).select_one(".mv-d2-all"), "hak-goryokaku").select_one("circle")
    assert MARGIN <= float(c["cy"]) <= 800 - MARGIN


def test_a_point_outside_a_stale_image_falls_back_to_the_schematic():
    # the itinerary moved on after day_maps.py ran: goryokaku is north of the stored image
    tight = {"north": 41.79, "south": 41.75, "east": 140.77, "west": 140.70}
    allv = _day(2, maps=side_file(bbox=tight)).select_one(".mv-d2-all")
    assert allv.select_one("svg.grid") and not allv.select(".mimg")


def test_a_segment_written_for_other_stops_falls_back_to_the_schematic():
    sf = side_file()
    sf["days"]["2026-10-13"][0]["poi_ids"] = ["hak-hotel", "hak-asaichi"]
    allv = _day(2, maps=sf).select_one(".mv-d2-all")
    assert allv.select_one("svg.grid") and not allv.select(".mimg")
    sf["days"]["2026-10-13"][0]["poi_ids"] = ["hak-hotel", "hak-asaichi", "hak-goryokaku", "hak-yama"]
    assert _day(2, maps=sf).select_one(".mv-d2-all .mimg")


def test_a_closeup_that_no_longer_holds_its_stop_is_not_used():
    sf = side_file()
    sf["days"]["2026-10-13"][0]["closeups"]["hak-yama"]["bbox"] = {
        "north": 41.80, "south": 41.79, "east": 140.76, "west": 140.75}          # around goryokaku
    yama = _day(2, maps=sf).select_one(".mv-d2-s5")
    assert yama.select_one(".mframe")["data-w"] == "1000"                      # the overview instead


def test_a_stop_with_a_closeup_shows_it_and_one_without_highlights_the_overview():
    d = _day(2)
    yama = d.select_one(".mv-d2-s5")
    assert yama.select_one(".mimg") and _pin(yama, "hak-yama")
    assert d.select_one(".mv-d2-s5 .mframe")["data-w"] == "640"
    gor = d.select_one(".mv-d2-s3")
    assert "hl" in _pin(gor, "hak-goryokaku")["class"]


def test_previous_and_next_cycle():
    d = _day(2)
    assert d.select_one(".mv-d2-s3 a.prev")["href"] == "#t-d2-s1"
    assert d.select_one(".mv-d2-s3 a.next")["href"] == "#t-d2-s5"
    assert d.select_one(".mv-d2-all a.prev")["href"] == "#t-d2-end"
    assert d.select_one(".mv-d2-end a.next")["href"] == "#t-d2-top"


def test_tap_opens_fullscreen_without_script():
    d = _day(2)
    z = d.select_one("input#z-d2-all")
    assert z["type"] == "checkbox" and not z.has_attr("checked")
    assert d.select_one('.mv-d2-all label.mframe[for="z-d2-all"]')


def test_the_legend_lists_every_stop():
    # v1.1: the all-day Google Maps button is gone (each stop has its own 導航)
    card = _day(2).select_one(".mapc")
    assert not card.select("a.gbtn")
    assert [li.get_text(" ", strip=True) for li in card.select(".lgd li")] == [
        f"{LABELS['hotel_start']} 函館示意飯店", "08:00 函館朝市", "10:00 五稜郭公園", "17:00 函館山",
        f"{LABELS['hotel_end']} 函館示意飯店"]


def test_attribution_with_tiles_and_a_schematic_without():
    assert "OpenStreetMap" in _day(2).select_one(".mapc").get_text()
    plain = _day(2, maps=None).select_one(".mapc")
    assert plain.select_one("svg.grid") and not plain.select(".mimg") and "OpenStreetMap" not in plain.get_text()


def test_a_day_missing_from_the_side_file_falls_back():
    d1 = _day(1)
    assert d1.select_one(".mapc svg.grid") and not d1.select(".mapc .mimg")


def test_a_one_stop_day_has_no_empty_closeups():
    d1 = _day(1, maps=None)
    views = d1.select(".mapc .mv")
    assert [v["class"][1] for v in views] == ["mv-d1-all", "mv-d1-s1", "mv-d1-end"]
    assert all(v.select("g.pin") for v in views)
    assert [c.get_text() for c in d1.select(".mapc .chips a.chip")] == ["全圖", "12:00", LABELS["hotel_end"]]


def test_a_stop_without_geocode_is_left_off_the_map():
    pm = poi_map()
    pm["hak-goryokaku"].pop("geocode")
    d = _day(2, pm=pm)
    assert "10:00" not in [c.get_text() for c in d.select(".mapc .chips a.chip")]
    assert not d.select('.mapc g.pin[data-poi="hak-goryokaku"]')
    assert d.select_one('.stop[data-poi="hak-goryokaku"]')


LEG = {"from": "函館", "to": "函館山麓", "mode": "rail", "duration_mins": 40, "service": "特急北斗",
       "status": "ok", "sources": [{"url": "https://jr.example/", "official": True}]}


def _split_day(first_stop=True):
    itin = itinerary()
    rows = itin["days"][1]["rows"]
    long_move = {"slot": "move", "text": "特急", "leg_index": 0}
    itin["days"][1]["rows"] = ([rows[0], rows[1], long_move] if first_stop else [rows[0], long_move]) + rows[3:]
    return itin


def test_a_hotel_change_day_splits_at_the_long_move():
    d = _day(2, itin=_split_day(), maps=None, legs={"legs": [LEG]})
    assert len(d.select(".mv-d2-all .seg")) == 2
    assert d.select(".mapc .route") == []           # user check: the 路線列 is gone, the move rows say it


def test_a_one_point_segment_draws_no_map():
    d = _day(2, itin=_split_day(first_stop=False), maps=None, legs={"legs": [LEG]})
    assert len(d.select(".mv-d2-all .seg")) == 1


def test_a_tag_near_the_edge_stays_inside_the_frame():
    import re
    from scripts.render.reader.maps import PHONE_W, _label_w
    edge = {"north": 41.80, "south": 41.7594, "east": 140.77, "west": 140.7045}   # yama at the SW corner
    allv = _day(2, maps=side_file(bbox=edge)).select_one(".mv-d2-all")
    s = 1000 / PHONE_W
    for g in allv.select("g.pin"):
        tx, ty = map(float, re.match(r"translate\(([-\d.]+),([-\d.]+)\)", g.select_one("g")["transform"]).groups())
        half = _label_w(g.select_one("text").get_text()) / 2 * s      # v1.1: bare text, sized by the shipped helper
        assert half <= tx <= 1000 - half, g["data-poi"]
        assert 10 * s <= ty <= 800 - 10 * s, g["data-poi"]


def test_projection_is_anchored_north_up():
    # an absolute anchor: comparing against project() itself cannot see a flipped axis
    assert project(BBOX["north"], BBOX["west"], BBOX, 1000, 800) == pytest.approx((0, 0), abs=1e-6)
    assert project(BBOX["south"], BBOX["east"], BBOX, 1000, 800) == pytest.approx((1000, 800), abs=1e-6)
    allv = _day(2).select_one(".mv-d2-all")
    cy = {pid: float(_pin(allv, pid).select_one("circle")["cy"]) for pid in ("hak-goryokaku", "hak-yama")}
    assert cy["hak-goryokaku"] < cy["hak-yama"]                     # goryokaku is north of the mountain


def test_pins_land_where_the_generator_drew_the_tile_pixel():
    # scripts/day_maps.py places tiles by world pixels and stores the bbox; the reader
    # projects by bbox. Both are shipped: a point must land on the same image pixel.
    from scripts.day_maps import _bbox, _world
    z, w, h = 15, 1343, 1291
    lat, lng = 41.7594, 140.7045
    wx, wy = _world(lat, lng, z)
    left, top = wx - 300.25, wy - 1000.75                      # the point sits off-centre, low-left
    box = _bbox(z, left, top, w, h)
    x, y = project(lat, lng, box, w, h)
    assert (x, y) == pytest.approx((wx - left, wy - top), abs=0.5)


def test_each_map_image_is_embedded_once():
    sf = side_file(days=("2026-10-12", "2026-10-13", "2026-10-14"))
    html = render_reader(itinerary(), poi_map(), maps=sf, **reader_kwargs())
    assert html.count(OVERVIEW) == 1 and html.count(CLOSE) == 1
    soup = BeautifulSoup(html, "html.parser")
    assert len(soup.select(".mimg")) > 2


def test_image_and_pins_share_one_box_even_when_the_frame_is_squeezed():
    d = _day(2)
    assert d.select_one(".mv-d2-all svg.pins")["preserveaspectratio"] == "none"
    css = BeautifulSoup(render_reader(itinerary(), poi_map(), maps=side_file(), **reader_kwargs()),
                        "html.parser").select_one("style").string
    assert ".mv:has(.zck:checked) .mframe{flex:none" in css
    assert "background-size:100% 100%" in css


@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_anchor_target_shows_its_view(n):
    """nav_css is the map half of §6.8: each target the list or a chip can jump to must
    have a rule showing its view (the overview when there is no target)."""
    import re
    from scripts.render.reader.maps import day_points, target, view_of_row
    from scripts.render.reader.page import _context
    kw = reader_kwargs()
    html = render_reader(itinerary(), poi_map(), maps=side_file(), **kw)
    soup = BeautifulSoup(html, "html.parser")
    css = soup.select_one("style").string
    ctx = _context(itinerary(), poi_map(), kw.get("brief"), kw.get("accommodations"), kw.get("advisory"),
                   kw.get("legs"), side_file())
    day = ctx.days[n - 1]
    expect = {pt["key"]: pt["key"] for _, pt in day_points(ctx, n, day)}
    expect.update({rid.split("-", 1)[1]: key for rid, key in view_of_row(ctx, n, day).items()})
    page = soup.select_one(f'section.page.day[data-pg="d{n}"]')
    assert expect, "no targets measured"
    for node, key in expect.items():
        tid = target(n, node)
        assert page.select_one(f"#{tid}"), tid
        assert re.search(rf"#{tid}:target,#{tid} :target:not\(\.tx\)\) \.mv-d{n}-{key}\{{display:", css), tid
        assert page.select_one(f".mv-d{n}-{key}"), tid
    assert re.search(rf':not\(:has\(\.plist :target:not\(\.tx\)\)\) \.mv-d{n}-all\{{display:', css)


@pytest.mark.parametrize("data", ['data:image/png;base64,AAAA");}</style><script>x()</script>',
                                  "data:image/svg+xml;base64,PHN2Zz4=", "https://tile.example/1.png"])
def test_an_image_that_is_not_plain_base64_is_never_put_in_the_stylesheet(data):
    sf = side_file()
    sf["days"]["2026-10-13"][0]["image"]["data"] = data
    sf["days"]["2026-10-13"][0]["closeups"] = {}
    html = render_reader(itinerary(), poi_map(), maps=sf, **reader_kwargs())
    assert data not in html and "<script>x()" not in html
    assert BeautifulSoup(html, "html.parser").select_one('section.page.day[data-pg="d2"] .mv-d2-all svg.grid')


def test_every_tiled_frame_carries_its_own_credit_and_a_canvas():
    d = _day(2)
    tiled = [f for f in d.select(".mapc label.mframe") if f.select_one(".mimg")]
    assert tiled
    for f in tiled:
        assert f.select_one(".mcanvas .mimg") and f.select_one(".mcanvas svg.pins")
        assert f.select_one(".attrmini").get_text() == "© OpenStreetMap"   # review I5: OSMF forbids "OSM"


def test_only_a_43_image_is_marked_for_cover_cropping():
    sf = side_file()
    sf["days"]["2026-10-13"][0]["image"].update(width=1000, height=750)
    assert "cover" in _day(2, maps=sf).select_one(".mv-d2-all .mframe")["class"]


def test_an_old_non_43_overview_is_not_cropped():
    d = _day(2)                                                   # side_file() overview is 1000x800 (5:4)
    assert "cover" not in d.select_one(".mv-d2-all .mframe")["class"]


def test_no_has_is_nested_in_a_has():
    """Review I-1: CSS forbids :has() inside :has(); inside a forgiving :is() the inner
    one is silently dropped, so the rule stops matching rather than erroring. Walk
    every :has( in the shipped stylesheet (theme + per-page nav_css)."""
    html = render_reader(itinerary(), poi_map(), maps=side_file(), **reader_kwargs())
    css = BeautifulSoup(html, "html.parser").select_one("style").string
    nested = []
    for m in re.finditer(r":has\(", css):
        depth, i = 1, m.end()
        while depth and i < len(css):
            if css.startswith(":has(", i):
                nested.append(css[max(0, m.start() - 40):i + 30]); break
            depth += {"(": 1, ")": -1}.get(css[i], 0); i += 1
    assert css.count(":has(") > 10 and not nested, nested[:3]
