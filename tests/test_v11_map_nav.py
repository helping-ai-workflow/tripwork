"""v1.1 topic 2 — TW-084: every end of a day's chain can be navigated to, the airport
included; TW-086: no all-day directions button (the user's call); the 移動列 and
路線列; icons; map labels; lone-stop close-ups."""
import copy
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from scripts.render.reader import render_reader
from tests.reader_fixture import itinerary, poi_map, reader_kwargs


def _soup(itin=None, **kw):
    args = reader_kwargs()
    args.update(kw)
    return BeautifulSoup(render_reader(itin or itinerary(), poi_map(), **args), "html.parser")


def _q(href):
    return parse_qs(urlparse(href).query)


# --- TW-084 ---------------------------------------------------------------------

def test_every_chain_end_has_a_navigation_button():
    s = _soup()
    ends = s.select("section.page.day .plist .anchor")
    assert len(ends) == 2 * len(s.select("section.page.day"))
    bare = [a.get("id") for a in ends if not a.select_one("a.navb")]
    assert bare == [], bare


def test_the_airport_ends_search_for_the_airport():
    s = _soup()
    first = s.select_one('section.page.day[data-pg="d1"] .anchor')
    last = s.select('section.page.day[data-pg="d3"] .anchor')[-1]
    assert "函館空港" in _q(first.select_one("a.navb")["href"])["query"][0]
    assert "函館空港" in _q(last.select_one("a.navb")["href"])["query"][0]


def test_an_arrival_by_a_long_leg_uses_the_legs_endpoint():
    """A day that opens with a legs.yaml leg has no `from` on its row: the leg's own
    `from` is the place the day starts."""
    itin = copy.deepcopy(itinerary())
    d1 = itin["days"][0]
    first = next(j for j, r in enumerate(d1["rows"]) if r.get("slot") == "move")
    d1["rows"][first] = {"slot": "move", "text": "從機場搭快速", "leg_index": 0}
    legs = {"legs": [{"from": "新千歳空港", "to": "札幌", "mode": "rail", "duration_mins": 40}]}
    s = _soup(itin, legs=legs)
    head = s.select_one('section.page.day[data-pg="d1"] .anchor')
    assert "新千歳空港" in head.get_text()
    assert "新千歳空港" in _q(head.select_one("a.navb")["href"])["query"][0]


# --- TW-086 ---------------------------------------------------------------------

def test_there_is_no_all_day_google_maps_button():
    """TW-086, closed by the user's call: the all-day directions button (too many
    waypoints for Google Maps on a phone) is removed -- every stop has its own 導航."""
    html = render_reader(itinerary(), poi_map(), **reader_kwargs())
    s = BeautifulSoup(html, "html.parser")
    assert not s.select("a.gbtn") and "/maps/dir/" not in html
    assert s.select("section.page.day .stop a.navb")


# --- the move capsule (user, 2026-10-01): mode + minutes + distance, nothing else ---

def test_a_capsule_carries_no_note_and_no_estimate_mark():
    for leg in _soup().select("section.page.day .leg:not(.zero)"):
        assert not leg.select(".lnote, a"), leg
        assert "估" not in leg.get_text(), leg.get_text()


def test_a_long_leg_shows_its_mode_minutes_and_distance():
    from scripts.render.reader.day import leg
    html = leg({"slot": "move", "leg_index": 0},
               [{"mode": "taxi", "duration_mins": 30, "km": 21.5, "service": "計程車 2 台（到達大廳外排班處…）"}])
    from scripts.render.reader.text import move_summary
    s = BeautifulSoup(html, "html.parser")
    assert s.select_one(".ltx").decode_contents() == move_summary("計程車", 30, 21.5)


def test_the_legs_schema_records_a_distance(tmp_path):
    import yaml
    from scripts.validate_artifact import validate_file
    f = tmp_path / "legs.yaml"
    f.write_text(yaml.safe_dump({"legs": [{"from": "a", "to": "b", "mode": "taxi", "status": "ok",
                                           "duration_mins": 30, "km": 21.5,
                                           "sources": [{"url": "https://x.example/", "official": True}]}]}), encoding="utf-8")
    assert validate_file(str(f))[0] == 0, validate_file(str(f))[1]


def test_the_move_format_is_the_users_pick():
    """The user picked the bracket of four on the design board (2026-10-01)."""
    from scripts.render.reader.text import move_summary
    s = BeautifulSoup(move_summary("計程車", 30, 9.7), "html.parser")
    assert s.get_text() == "計程車 30 分（9.7 km）" and s.select_one("b").get_text() == "計程車 30 分"
    assert BeautifulSoup(move_summary("步行", 2, None), "html.parser").get_text() == "步行 2 分"


def test_every_bundled_icon_keeps_its_shapes():
    """icon() strips the root <svg>'s fixed size so CSS sizes it; it stripped every
    child's width / height too, so cable-car's cabin and bus-front's body (<rect>)
    vanished -- the user's 'unreadable ropeway icon'. Each child element must come
    out with exactly the attributes the Lucide file gives it."""
    import re
    from scripts.render.reader.assets import ICON_DIR, ICONS_USED, icon
    kids = lambda svg: [(m.group(1), sorted(re.findall(r'(\w[\w-]*)="([^"]*)"', m.group(2))))
                        for m in re.finditer(r"<(?!svg\b)(\w+)([^>]*)/?>", svg)]
    bad = {}
    for name in ICONS_USED:
        src = re.sub(r"<!--.*?-->", "", (ICON_DIR / f"{name}.svg").read_text(encoding="utf-8"), flags=re.S)
        if kids(icon(name)) != kids(src):
            bad[name] = kids(icon(name))
    assert bad == {}, bad
    assert 'width="16"' in icon("cable-car") and not re.search(r"<svg[^>]*\swidth=", icon("cable-car"))


def test_vehicle_icons_are_the_ones_the_user_chose():
    """v1.0 spec §6.3 (the user's pick on the leg-icon mockup): train front, a SIDE-view
    bus, footprints, a side-view car. A literal because the choice itself is the
    source; the bus had shipped as bus-front (front view) since v1.0."""
    from scripts.render.reader.assets import MODE_ICON
    assert {k: MODE_ICON[k] for k in ("rail", "bus", "walk", "taxi", "drive")} == {
        "rail": "train-front", "bus": "bus", "walk": "footprints", "taxi": "car", "drive": "car"}


# --- a stop alone in its segment (trip-e D3/D4 出發: the hotel, then a long train) ---

LAVISTA_BOX = {"north": 41.78, "south": 41.76, "east": 140.73, "west": 140.71}


def _lone_start():
    from tests.test_reader_maps import CLOSE, side_file
    itin = copy.deepcopy(itinerary())
    itin["days"][1]["rows"][0] = {"slot": "move", "text": "特急", "leg_index": 0}   # leave the hotel by a long leg
    legs = {"legs": [{"from": "函館", "to": "洞爺", "mode": "rail", "duration_mins": 110}]}
    close = {"image": {"data": CLOSE, "width": 640, "height": 480}, "bbox": LAVISTA_BOX}
    return itin, legs, side_file, close


def test_a_lone_stop_uses_the_side_files_shared_close_up():
    itin, legs, side_file, close = _lone_start()
    sf = side_file()
    sf["closeups"] = {"hak-hotel": close}
    view = _soup(itin, maps=sf, legs=legs).select_one('section[data-pg="d2"] .mv-d2-start')
    assert view.select_one(".mimg"), "the 出發 view fell back to the blank schematic"


def test_a_lone_stop_borrows_its_close_up_from_another_day():
    itin, legs, side_file, close = _lone_start()
    sf = side_file(days=("2026-10-12", "2026-10-13"))
    sf["days"]["2026-10-12"][0]["closeups"]["hak-hotel"] = close
    view = _soup(itin, maps=sf, legs=legs).select_one('section[data-pg="d2"] .mv-d2-start')
    assert view.select_one(".mimg")


def test_the_side_file_schema_takes_shared_close_ups(tmp_path):
    import yaml
    from scripts.validate_artifact import validate_file
    from tests.test_reader_maps import CLOSE
    f = tmp_path / "day-maps.yaml"
    f.write_text(yaml.safe_dump({"attribution": "© OpenStreetMap contributors", "days": {},
                                 "closeups": {"hak-hotel": {"image": {"data": CLOSE, "width": 640, "height": 480},
                                                              "bbox": LAVISTA_BOX}}}), encoding="utf-8")
    assert validate_file(str(f))[0] == 0, validate_file(str(f))[1]
