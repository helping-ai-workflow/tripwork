"""v1.0 P6 — the desktop reader (spec §6.7–§6.9): the DH2 big calendar home, the V2
overlays for the three sub-screens, the day dashboard, and the one centring script.
The page is one DOM for both widths; these tests pin the desktop-only blocks and the
hooks the ≥1024px stylesheet lays out. Layout itself is measured with Playwright
(docs/superpowers/plans/2026-10-01-v1.0-p6-b-desktop.md Task 5)."""
import re

from bs4 import BeautifulSoup

from scripts.render.reader import render_reader
from scripts.render.reader.centre import CENTRE_JS
from scripts.render.reader.text import WEEKDAYS
from tests.reader_fixture import itinerary, poi_map, reader_kwargs


def _soup(itin=None, **over):
    kw = reader_kwargs()
    kw.update(over)
    return BeautifulSoup(render_reader(itin or itinerary(), poi_map(), **kw), "html.parser")


def _hcal(soup=None):
    return (soup or _soup()).select_one("section.page.home .hcal .g")


# ---- the month card, zoomed (v1.1 topic 6; replaced the DH2 grid) ----------------

def test_the_desktop_month_card_has_seven_weekday_columns():
    assert [w.get_text() for w in _hcal().select(".wd")] == list(WEEKDAYS)


def test_a_trip_stamp_opens_that_day():
    assert [s["for"] for s in _hcal().select(".stamp")] == ["pg-d1", "pg-d2", "pg-d3"]


def test_the_last_day_stamp_says_return():
    assert _hcal().select(".stamp")[-1].select_one("small").get_text() == "返程"


def test_a_one_day_trip_draws_its_whole_month():
    itin = itinerary()
    itin["days"] = itin["days"][:1]
    g = _hcal(_soup(itin))
    assert len(g.select(".stamp")) == 1 and len(g.select(".off")) >= 27


def test_the_side_column_keeps_title_and_the_three_buttons():
    home = _soup().select_one("section.page.home")
    assert home.select_one(".hside .headline")
    assert [t["for"] for t in home.select(".hside .tiles label.tile")] == ["pg-lodging", "pg-advisory", "pg-checklist"]


# ---- V2 overlays -----------------------------------------------------------------

def test_each_sub_screen_is_an_overlay_with_two_ways_out():
    s = _soup()
    for pg in ("lodging", "advisory", "checklist"):
        sec = s.select_one(f'section.page.sub[data-pg="{pg}"]')
        assert "ov" in sec["class"]
        assert sec.select_one('label.ovbg[for="pg-home"]')
        box = sec.select_one(".ovbox")
        assert box.select_one('.ph label.ovx[for="pg-home"]').get_text(strip=True) == "✕ 關閉"
        assert box.select_one('.ph label.back[for="pg-home"]').get_text(strip=True) == "‹ 總覽"   # the phone's way out
        assert box.select_one(".pb")


# ---- day dashboard ---------------------------------------------------------------

def test_a_day_page_is_a_three_panel_dashboard():
    day = _soup().select_one('section.page.day[data-pg="d2"]')
    dash = day.select_one(".dash")
    # the three panels; H1c's phone-only card cap and foot (.lcap / .lfoot, aria-hidden,
    # hidden on the desktop) flank the list
    assert [c["class"][0] for c in dash.find_all(recursive=False)] == ["pcal", "pmap", "lcap", "plist", "lfoot"]
    assert all(c.get("aria-hidden") == "true" for c in dash.select(":scope > .lcap, :scope > .lfoot"))
    assert dash.select_one(".pcal .mini") and dash.select_one(".pmap details.mapc")
    plist = dash.select_one(".plist")
    assert dash.select_one(".pcal .dh") and plist.select_one(".list .stop")   # v1.1: the title sits with the calendar


def test_a_day_without_map_points_still_has_the_panels():
    itin = itinerary()
    pm = poi_map()
    for p in pm.values():
        p.pop("geocode", None)
    html = render_reader(itin, pm, **reader_kwargs())
    dash = BeautifulSoup(html, "html.parser").select_one('section.page.day[data-pg="d2"] .dash')
    assert dash.select_one(".pmap") and not dash.select_one(".pmap .mapc")


# ---- the centring script -----------------------------------------------------------

def test_the_page_carries_exactly_the_centring_script():
    scripts = _soup().select("script")
    assert len(scripts) == 1 and scripts[0].string == CENTRE_JS


def test_the_script_polishes_the_anchor_jump():
    # v1.1 §8.1: the jump works without it; with it, a desktop glides the stop to centre
    assert "hashchange" in CENTRE_JS and "closest('.plist')" in CENTRE_JS
    assert "matchMedia('(min-width:1024px)')" in CENTRE_JS and "L.scrollTo({top:" in CENTRE_JS
    assert "scrollIntoView({block:'nearest'" in CENTRE_JS


def test_the_script_stays_about_ten_lines():
    assert len([l for l in CENTRE_JS.splitlines() if l.strip()]) <= 12


def test_the_stylesheet_lays_out_the_desktop_at_1024():
    css = _soup().select_one("style").string
    desk = css[css.index("@media (min-width:1024px)"):]
    for needle in (".dash{", "height:100vh", "max-width:1240px",
                   "grid-template-columns:minmax(360px,440px) minmax(0,1fr)", ".hcal", ".ov"):
        assert needle in desk, needle
    # 65 px stamps, shrunk only where the grid cell is too small for the rings (review I3);
    # the browser suite measures the 65 px at 1366x768
    assert re.search(r"\.hcal \.stamp\{[^}]*--s:max\(36px,min\(65px,[^}]*width:var\(--s\)", desk)


def test_long_unbroken_text_in_the_sub_screens_wraps():
    # a URL-length token in an entry rule or a checklist item must wrap, not widen the
    # phone page or the desktop overlay (Review Focus 5; measured 3312 px before)
    from scripts.render.reader.theme import CSS
    wrapping = set()
    for sels, body in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS):
        if "overflow-wrap:anywhere" in body:
            wrapping.update(s.strip() for s in sels.split(","))
    for sel in (".adv p", ".ci p", ".tk", ".lt small"):
        assert sel in wrapping, sel


# ---- stylesheet structure (review P6: substring needles stayed green when rules were removed)

def _rules(css):
    """[(context, selector list, body)] -- context is the chain of @-blocks around a rule."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out, stack, buf, i = [], [], "", 0
    while i < len(css):
        ch = css[i]
        if ch == "{":
            head = buf.strip()
            if head.startswith("@"):
                stack.append(head)
            else:
                j = css.index("}", i)
                out.append((tuple(stack), [s.strip() for s in head.split(",")], css[i + 1:j]))
                i = j
            buf = ""
        elif ch == "}":
            if stack:
                stack.pop()
            buf = ""
        else:
            buf += ch
        i += 1
    return out


def _has(sel, prop, media=None, supports=None):
    from scripts.render.reader.theme import CSS
    for ctx, sels, body in _rules(CSS):
        in_media = any(c.startswith("@media (min-width:1024px)") for c in ctx)
        in_sup = any(c.startswith("@supports") and supports in c for c in ctx) if supports else True
        if sel in sels and prop in body and (media is None or media == in_media) and in_sup:
            return True
    return False


def test_phone_stacks_the_dashboard_and_only_the_list_scrolls():
    # v1.1 §3: the v1.0 phone dissolved .pcal/.pmap/.plist (display:contents); now they
    # stack and .plist is the one scroller (tests/test_reader_phone_css.py has the rest)
    assert not _has(".pcal", "display:contents")
    from tests.css_rules import has
    assert has(".plist", "overflow-y:auto", media="max")


def test_the_desktop_forces_the_map_open_only_where_it_can():
    assert _has(".pmap .mapc::details-content", "content-visibility:visible", media=True,
                supports="selector(::details-content)")
    assert _has(".pmap .mapc>summary", "pointer-events:none", media=True, supports="selector(::details-content)")


def test_the_overlay_is_fixed_over_the_calendar():
    assert _has(".page.sub", "position:fixed", media=True)
    assert _has(".ovbox", "max-height", media=True)


def test_a_zoomed_multi_segment_map_stacks_instead_of_sharing_the_panel():
    assert _has(".mv:has(.zck:checked) .seg", "flex:none", media=True)


def test_a_long_legend_cannot_squeeze_the_map_away():
    assert _has(".pmap .lgd", "max-height", media=True) and _has(".pmap .lgd", "overflow", media=True)
    assert _has(".pmap .views", "min-height:160px", media=True)


def test_a_day_without_a_map_gives_the_list_the_room():
    assert _has(".dash:not(:has(.mapc)) .pmap", "display:none", media=True)


def test_a_broken_first_date_cannot_blow_up_the_calendar():
    itin = itinerary()
    itin["days"][0]["date"] = "2026-13-45"          # the gate rejects this upstream; the reader must not
    cells = _hcal(_soup(itin)).select(":scope > *")
    assert len(cells) <= 7 * 7


def test_an_alternative_names_the_stop_it_belongs_to():
    d2 = _soup().select_one('section.page.day[data-pg="d2"]')
    alt = d2.select_one("details.altrow")
    assert alt["data-stop"] == "t-d2-s5" and d2.select_one("div.stop#t-d2-s5")
    assert "dataset.stop" in CENTRE_JS


def test_a_zoomed_view_taller_than_the_screen_scrolls_from_its_top():
    # centre alignment pushes the overflow above the scroll origin, out of reach
    assert _has(".mv:has(.zck:checked)", "justify-content:safe center")
