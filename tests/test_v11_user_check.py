"""v1.1 user check (2026-10-02, the user's picks on the board): the OSM credit is plain
text (the copyright link was tapped by accident) and the zoom bar opens the live map of
the area being viewed; no 路線列 above the map on either width."""
import math
import re

from bs4 import BeautifulSoup

from scripts.render.reader import render_reader
from tests.reader_fixture import itinerary, poi_map, reader_kwargs
from tests.test_reader_maps import BBOX, side_file

# the user (2026-10-03): the zoom bar opens Google Maps at the area shown, not OpenStreetMap
LIVE = re.compile(r"^https://www\.google\.com/maps/@(-?\d+\.\d+),(-?\d+\.\d+),(\d+)z$")


def _soup(**kw):
    return BeautifulSoup(render_reader(itinerary(), poi_map(), maps=side_file(), **dict(reader_kwargs(), **kw)),
                         "html.parser")


def test_every_osm_credit_is_plain_text():
    s = _soup()
    credits = s.select(".attrmini") + s.select(".attr")
    assert credits
    for el in credits:
        assert el.select("a") == [] and "OpenStreetMap" in el.get_text()


def test_the_zoom_bar_opens_the_live_map_of_the_area_shown():
    s = _soup()
    tiled = [mv for mv in s.select('section[data-pg="d2"] .mv') if mv.select_one(".mimg")]
    assert tiled
    allv = next(mv for mv in tiled if "-all" in " ".join(mv["class"]))
    a = allv.select_one(".zbar a.zlink")
    assert a.get_text() == "在 Google Maps 開這裡 ↗" and a["target"] == "_blank"
    lat, lon, z = LIVE.match(a["href"]).groups()
    assert abs(float(lat) - (BBOX["north"] + BBOX["south"]) / 2) < 1e-4
    assert abs(float(lon) - (BBOX["east"] + BBOX["west"]) / 2) < 1e-4
    # the whole box fits a phone screen at that zoom (390 px wide), one step closer does not
    span = math.radians(BBOX["east"] - BBOX["west"])
    fits = lambda zz: 256 * 2 ** zz * span / (2 * math.pi) <= 390
    assert fits(int(z)) and not fits(int(z) + 1) or int(z) == 18
    for mv in tiled:
        assert LIVE.match(mv.select_one(".zbar a.zlink")["href"])


def test_no_route_line_above_the_map():
    from tests.test_reader_maps import LEG, _day, _split_day
    d = _day(2, itin=_split_day(), maps=None, legs={"legs": [LEG]})
    assert d.select_one(".mapc") is not None and d.select(".mapc .route") == []


def test_the_gate_wants_the_credit_text_not_a_link():
    from scripts.export_gate import _OSM_TEXT, run_html_gate
    html = render_reader(itinerary(), poi_map(), maps=side_file(), **reader_kwargs())
    check = lambda h: {c["name"]: c["passed"] for c in run_html_gate(h, list(poi_map().values()), min_days=1)["checks"]}
    assert check(html)["map_attribution_present"] is True
    no_live = re.sub(r'<a class="zlink"[^>]*>[^<]*</a>', "", html)
    assert no_live != html and check(no_live)["map_attribution_present"] is True     # the live link is not the credit
    one_gone = html.replace(_OSM_TEXT, "", 1)
    assert check(one_gone)["map_attribution_present"] is False
    no_card = re.sub(r'<p class="attr">[^<]*</p>', "", html)
    assert no_card != html and check(no_card)["map_attribution_present"] is False


def test_the_phone_title_steps_to_the_neighbouring_days():
    """User check (pick S1; T25b): 「‹ Day 2 ›」 -- labels for the day radios, so it works
    with no script; the first and last days show a dimmed end; the desktop's list title
    keeps the plain Day chip (the calendar is always on screen there)."""
    s = BeautifulSoup(render_reader(itinerary(), poi_map(), **reader_kwargs()), "html.parser")
    n = len(s.select("section.page.day"))
    for i in range(1, n + 1):
        sec = s.select_one(f'section.page.day[data-pg="d{i}"]')
        step = sec.select_one(".pcal .dh .dstep")
        assert step.select_one(".dn").get_text() == f"Day {i}"
        prev, nxt = step.find_all(["label", "span"], recursive=False)[0], step.find_all(["label", "span"], recursive=False)[-1]
        # H1c2: an arrow is a pair (.sw) whose plain label (.so) opens the neighbour as usual
        arrow = lambda e: ("label", e.select_one("label.so")["for"]) if "sw" in (e.get("class") or []) else (e.name, e.get("for"))
        assert arrow(prev) == (("span", None) if i == 1 else ("label", f"pg-d{i - 1}"))
        assert arrow(nxt) == (("span", None) if i == n else ("label", f"pg-d{i + 1}"))
        # pick F1: the desktop's list title steps too
        lst = sec.select_one(".plist > .dh-list .dstep")
        assert lst.select_one(".dn").get_text() == f"Day {i}"
        assert [l.get("for") for l in lst.select("label")] == [f for f in (f"pg-d{i - 1}" if i > 1 else None,
                                                                           f"pg-d{i + 1}" if i < n else None) if f]


# --- H1c2 (2026-10-03): the stepper keeps a put-away calendar put away, with no script ---

def test_every_day_has_a_folded_radio_and_the_phone_arrows_carry_both():
    soup = _soup()
    days = [s["data-pg"] for s in soup.select("section.page.day")]
    assert len(days) >= 3
    for d in days:
        assert soup.select_one(f'input#pg-{d}f[type=radio][name=pg]'), d
    for d in days:
        sec = soup.select_one(f'section[data-pg="{d}"]')
        phone = sec.select_one(".pcal .dh .dstep")
        for sw in phone.select(".sw"):
            so, sf = sw.select_one("label.so"), sw.select_one("label.sf")
            assert so and sf and sf["for"] == so["for"] + "f", (d, str(sw))
        assert len(phone.select(".sw")) == 2 - (d in (days[0], days[-1])), d
        assert not sec.select(".plist .dh-list .dstep .sw"), d          # the desktop's stepper: one label per arrow
        unf = sec.select_one(".ymrow .ym label.unf")
        assert unf and unf["for"] == f"pg-{d}", d                        # the month opens this day's calendar
        lcap, plist, lfoot = sec.select_one(".lcap"), sec.select_one(".plist"), sec.select_one(".lfoot")
        assert lcap.find_next_sibling() is plist and plist.find_next_sibling() is lfoot, d
        assert lcap.get("aria-hidden") == "true" and lfoot.get("aria-hidden") == "true"


def test_each_day_page_carries_its_calendars_week_count():
    """The phone folds the mini calendar by its own height (theme.py --fold = 22 + 38 x --wk):
    the fixture's trip (10/12-10/14) sits inside one week."""
    from scripts.render.reader import calendar
    soup = _soup()
    secs = soup.select("section.page.day")
    assert secs and all(s.get("style") == "--wk:1" for s in secs), [s.get("style") for s in secs]
    assert len(calendar.weeks([__import__("datetime").date(2026, 10, 30), __import__("datetime").date(2026, 11, 2)])) == 2
