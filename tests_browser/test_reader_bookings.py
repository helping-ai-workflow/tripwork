"""交通 / 餐廳 on the shipped reader, both engines (WebKit is the iPhone): the five home tiles
keep the old tile's size, the status pill sits on its name's line (ink, not boxes), the
desktop overlay keeps the home behind it, and the four pills stay apart in the dark theme."""
import io

import pytest
from conftest import DESKTOP, PHONE

RECT = "sel => [...document.querySelectorAll(sel)].filter(e => e.offsetParent).map(e => { const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height] })"
# a day page sits in a fixed box on the phone, where offsetParent is null: take the first with a size
ONE = "sel => [...document.querySelectorAll(sel)].map(e => e.getBoundingClientRect()).filter(r => r.width).map(r => [r.x, r.y, r.width, r.height])[0]"


def _go(pg, pid):
    pg.evaluate(f"document.getElementById('{pid}').checked=true")
    pg.wait_for_timeout(300)


# 86 / 45: the tile heights before this change, measured on the shipped reader (the phone's
# tall tile, the desktop's bar) -- literals because the sizes to keep are the old ones. The
# phone's second row takes the desktop's bar (the user's pick C): the home must fit one screen.
@pytest.mark.parametrize("vp,heights", [(PHONE, [86, 86, 86, 45, 45]), (DESKTOP, [45] * 5)], ids=["phone", "desktop"])
def test_five_tiles_keep_the_old_tile_heights(browser, bookings_url, vp, heights):
    pg = browser.new_page(viewport=vp)
    pg.goto(bookings_url)
    tiles = pg.evaluate(RECT, ".page.home label.tile")
    assert len(tiles) == 5
    assert [round(t[3]) for t in tiles] == heights, tiles
    if vp is PHONE:                     # 3 + 2: the second row spans the first row's outer edges
        a, b, c, d, e = tiles
        assert d[0] == pytest.approx(a[0], abs=.5) and e[0] + e[2] == pytest.approx(c[0] + c[2], abs=.5)
        assert d[2] == pytest.approx(e[2], abs=.5) and a[1] == b[1] == c[1] < d[1] == e[1]
    pg.close()


def test_the_phone_home_with_a_cost_card_fits_one_screen(browser, bookings_url):
    pg = browser.new_page(viewport=PHONE, java_script_enabled=False)
    pg.goto(bookings_url)
    assert pg.evaluate("(()=>{const h=document.querySelector('.page.home');return h.scrollHeight<=h.clientHeight+1})()")
    pg.close()


def _ink_centre(pg, rect, dpr, thr=110):
    """Vertical centre (CSS px) of the glyph ink (pixels darker than thr) inside rect, from a
    screenshot; thr 170 for the grey (--mut) icons."""
    from PIL import Image
    x, y, w, h = rect
    im = Image.open(io.BytesIO(pg.screenshot(clip={"x": x, "y": y - 4, "width": w, "height": h + 8}))).convert("L")
    rows = [r for r in range(im.height) if any(im.getpixel((c, r)) < thr for c in range(im.width))]
    return y - 4 + (rows[0] + rows[-1] + 1) / 2 / dpr


def test_the_pill_sits_on_its_names_ink(browser, bookings_url):
    dpr = 3
    pg = browser.new_page(viewport=PHONE, device_scale_factor=dpr)
    pg.goto(bookings_url)
    _go(pg, "pg-transport")
    name = pg.evaluate(RECT, 'section[data-pg="transport"] .bkrow:nth-of-type(2) .bn')[0]
    pill = pg.evaluate(RECT, 'section[data-pg="transport"] .bkrow:nth-of-type(2) .bk')[0]
    ink = _ink_centre(pg, [name[0], name[1], min(name[2], 120), name[3]], dpr)
    drawn = pill[1] + pill[3] / 2                      # the outlined pill: its drawn shape is its box
    assert abs(ink - drawn) <= 1.0, (browser.engine, ink, drawn)
    icon = pg.evaluate(ONE, 'section[data-pg="transport"] .bkrow:nth-of-type(2) .bh .lu')    # an <svg>: no offsetParent
    assert abs(_ink_centre(pg, icon, dpr, thr=170) - ink) <= 1.0, browser.engine     # was 1.2 / 1.5 px high
    _go(pg, "pg-d1")
    pg.evaluate("document.querySelector('.stop[data-poi=izakaya]').scrollIntoView({block:'center'})")
    pg.wait_for_timeout(300)
    tag = pg.evaluate(ONE, '.stop[data-poi=izakaya] .hd-open .sgt')
    name = pg.evaluate(ONE, '.stop[data-poi=izakaya] .hd-open .n')
    name_ink = _ink_centre(pg, [tag[0] + tag[2] + 4, name[1], 80, name[3]], dpr)
    assert abs(tag[1] + tag[3] / 2 - name_ink) <= 1.0, browser.engine               # was 1.2 / 1.3 px high
    pg.close()


@pytest.mark.parametrize("vp,home", [(DESKTOP, True), (PHONE, False)], ids=["desktop", "phone"])
def test_the_overlay_keeps_the_home_behind_it_on_the_desktop_only(browser, bookings_url, vp, home):
    pg = browser.new_page(viewport=vp)
    pg.goto(bookings_url)
    for sub in ("transport", "meals"):
        _go(pg, f"pg-{sub}")
        shown = pg.evaluate("getComputedStyle(document.querySelector('.page.home')).display !== 'none'")
        assert shown is home, (sub, browser.engine)
    pg.close()


def test_dark_theme_keeps_the_four_pills_apart(browser, bookings_url):
    pg = browser.new_page(viewport=PHONE)
    pg.goto(bookings_url)
    pg.evaluate("document.getElementById('theme').checked=true")
    _go(pg, "pg-meals")
    look = pg.evaluate("""() => { const g = s => getComputedStyle(document.querySelector(s));
      const t = document.querySelector('section[data-pg=transport] .bk-none');
      return {booked: g('section[data-pg=meals] .bk-booked').backgroundColor, todo: g('.bk-todo').color,
              self: g('.bk-self').color, none: getComputedStyle(t).color} }""")
    assert len(set(look.values())) == 4, look
    pg.close()


EDGES = """sel => [...document.querySelectorAll(sel)].filter(e => e.getBoundingClientRect().width > 0).map(e => {
  const r = e.getBoundingClientRect(); let a = e.parentElement;
  while (a && a !== document.body) { const s = getComputedStyle(a); if (s.overflowX !== 'visible' || s.overflowY !== 'visible') break; a = a.parentElement }
  const ar = a.getBoundingClientRect(), s = getComputedStyle(a);
  return {left: r.left - 1, right: r.right + 1, min: ar.left + parseFloat(s.borderLeftWidth), max: ar.right - parseFloat(s.borderRightWidth)} })"""


@pytest.mark.parametrize("vp", [PHONE, DESKTOP], ids=["phone", "desktop"])
@pytest.mark.parametrize("sub", ["pg-transport", "pg-meals"])
def test_booking_cards_keep_their_side_lines(browser, bookings_url, vp, sub):
    pg = browser.new_page(viewport=vp)
    pg.goto(bookings_url)
    _go(pg, sub)
    cards = pg.evaluate(EDGES, f'section[data-pg="{sub[3:]}"] .bkrow')
    assert cards, sub
    assert not [c for c in cards if c["left"] < c["min"] - .01 or c["right"] > c["max"] + .01], cards
    pg.close()
