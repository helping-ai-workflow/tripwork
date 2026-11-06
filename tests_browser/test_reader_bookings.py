"""交通 / 餐廳 on the shipped reader, both engines (WebKit is the iPhone): the five home tiles
keep their bar heights, the status pill sits on its name's line (ink, not boxes), the
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


# 45: the desktop's bar, kept; the phone's tiles are two rows of 40 px bars since the user's
# picks T1 + W1 (their geometry: tests_browser/test_reader_home_squeeze.py)
@pytest.mark.parametrize("vp,heights", [(PHONE, [40] * 5), (DESKTOP, [45] * 5)], ids=["phone", "desktop"])
def test_five_tiles_keep_their_heights(browser, bookings_url, vp, heights):
    pg = browser.new_page(viewport=vp)
    pg.goto(bookings_url)
    tiles = pg.evaluate(RECT, ".page.home label.tile")
    assert len(tiles) == 5
    assert [round(t[3]) for t in tiles] == heights, tiles
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


SPILL = """(()=>{const c=document.querySelector('.page.home .trip'),r=c.getBoundingClientRect(),cs=getComputedStyle(c);
  const out=[...c.children].filter(e=>e.getClientRects().length).some(e=>{const q=e.getBoundingClientRect();return q.bottom>r.bottom+1||q.top<r.top-1});
  return out && cs.overflowY==='visible'})()"""


# the user's call: the 旅程與費用 card may get shorter on a short screen, but its text never
# draws outside it -- its stay list scrolls inside it down to a floor of two rows (H1), below
# which the home scrolls (tests_browser/test_reader_home_squeeze.py)
@pytest.mark.parametrize("vp", [{"width": 390, "height": 844}, {"width": 390, "height": 750},
                                {"width": 390, "height": 667}, {"width": 844, "height": 390}],
                         ids=["844", "750", "667", "landscape"])
def test_the_trip_card_text_stays_inside_the_card(browser, bookings_url, vp):
    pg = browser.new_page(viewport=vp, java_script_enabled=False)
    pg.goto(bookings_url)
    assert not pg.evaluate(SPILL), (browser.engine, vp)
    pg.close()


def test_the_move_label_sits_on_its_line(browser, bookings_url):
    """A booked 移動列 (the user's pick M1): the 已訂 label is no taller than the line it sits
    in (20.8 px) and centres on 「飛機 190 分」's ink -- WebKit within 1 px, Chromium within 2
    (the board measured 0.05 / 1.8 px) -- the icon still sits on that ink, and the detail
    lines stay inside the row."""
    dpr = 3
    pg = browser.new_page(viewport=PHONE, device_scale_factor=dpr)
    pg.goto(bookings_url)
    _go(pg, "pg-d1")
    pg.evaluate("document.querySelector('section[data-pg=d1] .leg.lr').scrollIntoView({block:'center'})")
    pg.wait_for_timeout(300)
    pill = pg.evaluate(ONE, "section[data-pg=d1] .leg.lr .lrk")
    b = pg.evaluate(ONE, "section[data-pg=d1] .leg.lr .lrh b")
    assert 16 <= pill[3] <= 20.8, (browser.engine, pill)
    ink = _ink_centre(pg, b, dpr)
    tol = 1.0 if browser.engine == "webkit" else 2.0
    assert abs(pill[1] + pill[3] / 2 - ink) <= tol, (browser.engine, ink, pill)
    icon = pg.evaluate(ONE, "section[data-pg=d1] .leg.lr .lu")
    # Chromium: 3.1.0's one-line row already drew the icon 2.39 px below the text's ink (WebKit
    # 0.16); the new row must be no worse (measured 1.33 / -0.4). WebKit decides.
    assert abs(_ink_centre(pg, icon, dpr, thr=170) - ink) <= (1.0 if browser.engine == "webkit" else 2.5), browser.engine
    row = pg.evaluate(ONE, "section[data-pg=d1] .leg.lr")
    lines = pg.evaluate("sel => [...document.querySelector(sel).querySelectorAll('.lrv')].map(e => { const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height] })",
                        "section[data-pg=d1] .leg.lr")
    assert len(lines) == 2 and all(x + w <= row[0] + row[2] + 0.5 for x, _, w, _ in lines), (browser.engine, lines, row)
    pg.close()
