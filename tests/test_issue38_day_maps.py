"""#38 day maps (M2 M3 M4 M5) and #35's one dot per building, on a made-up Kamakura day
trip (public landmarks, 示意 shops) whose hotel is about 49 km away. Tiles are a blank
stand-in; nothing is fetched."""
import sys, pathlib

from bs4 import BeautifulSoup

from scripts.render.reader import render_reader
from scripts.render.reader.maps import FAR_KM, FAR_RATIO, far_ends
from tests.test_day_maps import _tile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "docs" / "images" / "readme"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import demo_trip as D                                                     # noqa: E402


def _kamakura(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("kp", pathlib.Path(__file__).parent / "kamakura_fixture.py")
    kp = importlib.util.module_from_spec(spec); spec.loader.exec_module(kp)
    return kp.build(tmp_path, fetch=lambda z, x, y: _tile())


def test_far_ends_need_both_the_ratio_and_the_distance():
    p = lambda key, kind, lat, lng: {"key": key, "kind": kind, "poi": {"geocode": {"lat": lat, "lng": lng}}}
    stops = [p("s1", "visit", 35.3259, 139.5566), p("s2", "visit", 35.3125, 139.5332)]
    assert far_ends(stops + [p("start", "lodging", 35.7113, 139.7953)]) == {"start"}        # ~49 km
    assert far_ends(stops + [p("start", "lodging", 35.3400, 139.5500)]) == set()            # ~2 km
    tight = [p("s1", "visit", 35.0, 139.0), p("s2", "visit", 35.0005, 139.0)]
    assert far_ends(tight + [p("end", "lodging", 35.04, 139.0)]) == set()                   # 4.4 km < 10
    assert (FAR_RATIO, FAR_KM) == (3, 10)


def test_the_overview_leaves_the_far_hotel_out_and_points_at_it(tmp_path):
    doc, html = _kamakura(tmp_path)
    entry = doc["days"]["2026-05-14"][0]
    assert entry["far"] == ["end", "start"] and entry["bbox"]["north"] < 35.40       # frame stays in Kamakura
    view = BeautifulSoup(html, "html.parser").select_one('section[data-pg="d3"] .mv-d3-all')
    edge = view.select(".pin.edge")
    assert len(edge) == 1 and "約 49 km" in edge[0].get_text()                         # one arrow per hotel


def test_stops_are_numbered_and_joined(tmp_path):
    _doc, html = _kamakura(tmp_path)
    view = BeautifulSoup(html, "html.parser").select_one('section[data-pg="d3"] .mv-d3-all')
    nos = [t.get_text() for t in view.select(".pin .no")]
    assert nos[:5] == ["1", "2", "3", "4", "5"] and "×2" in nos and "9" in nos
    assert view.select_one("path.seqline")


def test_shared_spots_fan_out_and_a_building_is_one_dot(tmp_path):
    _doc, html = _kamakura(tmp_path)
    view = BeautifulSoup(html, "html.parser").select_one('section[data-pg="d3"] .mv-d3-all')
    assert len(view.select("circle.apx")) == 1                                         # the 3 street shops
    spots = {(c["cx"], c["cy"]) for c in view.select(".pin:not(.edge) circle.pt")}
    assert len(spots) == len(view.select(".pin:not(.edge) circle.pt"))                 # nothing stacked
    merged = [g for g in view.select(".pin") if g.select_one(".no") and g.select_one(".no").get_text() == "×2"]
    assert "示意百貨 6–7" in merged[0].get_text()


def test_a_close_up_shows_the_neighbours_dimmed(tmp_path):
    _doc, html = _kamakura(tmp_path)
    s = BeautifulSoup(html, "html.parser").select_one('section[data-pg="d3"] .mv-d3-s5')
    assert s.select_one(".pin.hl") and len(s.select(".pin.dim")) >= 2
