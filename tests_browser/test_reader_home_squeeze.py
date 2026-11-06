"""The phone home gives its room back to 旅程與費用 (the user's picks on the design board:
H1 + T1 + W1). The month card draws only the weeks that hold trip days (the day pages'
mini calendar already does); the five tiles become two rows of 40 px bars -- 交通 / 餐廳
first, then 住宿 / 出入境 / 待辦 as wide as their words; the stay list keeps a floor of
two rows, below which the home scrolls instead. The desktop keeps its whole month,
its tiles and their full names. WebKit (the iPhone) decides where the engines differ."""
import io

import pytest
from conftest import DESKTOP, PHONE

SE = {"width": 390, "height": 667}
NARROW = {"width": 375, "height": 667}

ROWS = """(()=>{const g=document.querySelector('.page.home .months .g');
  return getComputedStyle(g).gridTemplateRows.split(' ').map(parseFloat)})()"""
WEEKS = """(()=>{const s=new Set();document.querySelectorAll('.page.home .months .g>:not(.wd)').forEach(e=>{
  const r=e.getBoundingClientRect();if(r.width>0&&!e.matches('.stamp'))s.add(Math.round(r.top))});
  return s.size})()"""


def _page(browser, url, vp, js=False):
    pg = browser.new_page(viewport=vp, java_script_enabled=js)
    pg.goto(url)
    return pg


# literals because these are the trips' calendars, counted by hand: bookings 5/12-14 (one
# week), many stays 11/9-19 (two), rings 8/17-31 (three), two months 8/30-9/1 (one, where
# the shipped page padded it to five)
@pytest.mark.parametrize("fx,weeks", [("bookings_url", 1), ("many_stays_url", 2), ("long_rings_url", 3),
                                      ("two_month_url", 1)])
def test_the_phone_month_card_draws_only_the_trip_weeks(browser, request, fx, weeks):
    pg = _page(browser, request.getfixturevalue(fx), PHONE)
    rows = pg.evaluate(ROWS)
    assert len(rows) == 1 + weeks, (browser.engine, fx, rows)          # the weekday row + the trip weeks
    pg.close()


def test_the_desktop_keeps_the_whole_month(browser, long_rings_url):
    pg = _page(browser, long_rings_url, DESKTOP)
    assert pg.evaluate(ROWS)[1:] and len(pg.evaluate(ROWS)) == 7, browser.engine     # August 2026: six weeks
    pg.close()


def test_a_week_of_stamps_keeps_its_row_height(browser, long_rings_url):
    """8/23-29 is all trip days: the row fell to the stamp's 34 px and the rings touched."""
    pg = _page(browser, long_rings_url, PHONE)
    weeks = pg.evaluate(ROWS)[1:]
    assert weeks and len(set(weeks)) == 1, (browser.engine, weeks)
    pg.close()


TILES = """(()=>[...document.querySelectorAll('.page.home .tiles .tile')].map(t=>{const r=t.getBoundingClientRect();
  return {pg:t.htmlFor,name:t.querySelector('b').innerText.trim(),x:r.left,y:r.top,w:r.width,h:r.height,
          clip:t.scrollWidth>t.clientWidth+0.5}}))()"""


@pytest.mark.parametrize("vp", [PHONE, NARROW, {"width": 844, "height": 390}, {"width": 1023, "height": 700}],
                         ids=["390", "375", "landscape", "1023"])
def test_the_phone_tiles_are_two_rows_of_bars(browser, bookings_url, vp):
    pg = _page(browser, bookings_url, vp)
    t = {x["pg"]: x for x in pg.evaluate(TILES)}
    top = [t["pg-transport"], t["pg-meals"]]
    low = [t["pg-lodging"], t["pg-advisory"], t["pg-checklist"]]
    assert all(round(x["h"]) == 40 for x in t.values()), (browser.engine, t)
    assert top[0]["y"] == top[1]["y"] < low[0]["y"] == low[1]["y"] == low[2]["y"], (browser.engine, t)
    assert abs(top[0]["w"] - top[1]["w"]) < 1 and top[0]["x"] < top[1]["x"], t
    assert low[0]["x"] < low[1]["x"] < low[2]["x"], t
    assert not [x for x in t.values() if x["clip"]], t
    pg.close()


def test_the_lower_row_is_as_wide_as_its_words(browser, bookings_url):
    pg = _page(browser, bookings_url, PHONE)
    t = {x["pg"]: x for x in pg.evaluate(TILES)}
    assert abs(t["pg-lodging"]["w"] - t["pg-checklist"]["w"]) < 1 and t["pg-checklist"]["w"] < t["pg-advisory"]["w"], t   # 住宿 / 待辦: two characters each
    pg.close()


TWO_DIGITS = """(()=>{const s=(p,v)=>{document.querySelector(`.page.home label.tile[for=${p}] small`).innerHTML=v};
  s('pg-lodging','12 間');s('pg-advisory','14 項');s('pg-checklist','28 項');
  s('pg-transport','16 段<i class="todo">・12 待訂</i>');s('pg-meals','24 餐<i class="todo">・12 待訂</i>')})()"""


@pytest.mark.parametrize("vp", [PHONE, NARROW], ids=["390", "375"])
def test_two_digit_counts_still_fit_two_rows(browser, bookings_url, vp):
    """The user's catch on the board: with two-digit counts 行前清單 fell to a third row."""
    pg = _page(browser, bookings_url, vp, js=True)
    pg.evaluate(TWO_DIGITS)
    t = pg.evaluate(TILES)
    assert len({round(x["y"]) for x in t}) == 2 and not [x for x in t if x["clip"]], (browser.engine, t)
    pad = pg.evaluate("""(()=>[...document.querySelectorAll('.page.home .tiles .tile')].map(t=>{const r=t.getBoundingClientRect();
      const k=[...t.children].map(c=>c.getBoundingClientRect()).filter(c=>c.width);
      return Math.min(Math.min(...k.map(c=>c.left))-r.left, r.right-Math.max(...k.map(c=>c.right)))}))()""")
    assert min(pad) >= 10, (browser.engine, pad)                # the board measured 12.8 px at 375
    pg.close()


@pytest.mark.parametrize("vp,names", [(PHONE, ["住宿", "交通", "餐廳", "出入境", "待辦"]),
                                      (DESKTOP, ["住宿", "交通", "餐廳", "出入境規定", "行前清單"])],
                         ids=["phone", "desktop"])
def test_the_tile_names(browser, bookings_url, vp, names):
    """W1: the phone's tiles say 出入境 / 待辦; the desktop and both screens' titles keep the full names."""
    pg = _page(browser, bookings_url, vp)
    assert [x["name"] for x in pg.evaluate(TILES)] == names, browser.engine
    pg.evaluate("document.getElementById('pg-checklist').checked=true")
    assert pg.evaluate("document.querySelector('section[data-pg=checklist] h2').innerText") == "行前清單"
    pg.close()


def _ink(pg, rect, dpr, thr):
    from PIL import Image
    x, y, w, h = rect
    im = Image.open(io.BytesIO(pg.screenshot(clip={"x": x, "y": y - 4, "width": w, "height": h + 8}))).convert("L")
    rows = [r for r in range(im.height) if any(im.getpixel((c, r)) < thr for c in range(im.width))]
    return y - 4 + (rows[0] + rows[-1] + 1) / 2 / dpr


ONE = "sel => { const r = document.querySelector(sel).getBoundingClientRect(); return [r.x, r.y, r.width, r.height] }"


def test_each_tile_centres_its_ink(browser, bookings_url):
    """Icon, name and count share the bar's centre: the board measured them within 0.7 px in
    WebKit (Chromium 1.0) once the bar's foot took 2 px (the CJK ink sat 1.3 px low)."""
    dpr = 3
    pg = browser.new_page(viewport=PHONE, device_scale_factor=dpr, java_script_enabled=False)
    pg.goto(bookings_url)
    for p in ("pg-lodging", "pg-transport", "pg-meals", "pg-advisory", "pg-checklist"):
        s = f".page.home label.tile[for={p}]"
        t = pg.evaluate(ONE, s)
        mid = t[1] + t[3] / 2
        sm = pg.evaluate(ONE, s + " small")
        got = [_ink(pg, pg.evaluate(ONE, s + " .lu"), dpr, 170), _ink(pg, pg.evaluate(ONE, s + " b"), dpr, 110),
               _ink(pg, [sm[0], sm[1], 20, sm[3]], dpr, 200)]
        assert all(abs(g - mid) <= 1.0 for g in got), (browser.engine, p, [round(g - mid, 2) for g in got])
    pg.close()


LIST = """(()=>{const H=innerHeight,c=document.querySelector('.page.home .trip'),ol=c.querySelector('ol'),
  sum=c.querySelector('.tt.sum'),home=document.querySelector('.page.home');const o=ol.getBoundingClientRect();
  const li=ol.querySelector('li').getBoundingClientRect().height;
  return {rows:ol.clientHeight/li,all:ol.scrollHeight<=ol.clientHeight+1,
          sum:sum.getBoundingClientRect().bottom<=H+1,scrolls:home.scrollHeight>home.clientHeight+1}})()"""


@pytest.mark.parametrize("vp", [PHONE, {"width": 390, "height": 750}, SE], ids=["844", "750", "667"])
def test_the_stay_list_keeps_two_rows_and_the_total(browser, many_stays_url, vp):
    """Ten stays: the list scrolls inside itself, but never below two rows, and the total
    stays on the screen on every iPhone height."""
    pg = _page(browser, many_stays_url, vp)
    m = pg.evaluate(LIST)
    assert m["rows"] >= 2 - 0.05 and m["sum"] and not m["scrolls"], (browser.engine, vp, m)
    pg.close()


def test_a_screen_too_short_for_the_floor_scrolls_the_home(browser, many_stays_url):
    """Held sideways the floor does not fit: the home scrolls rather than squeeze the list."""
    pg = _page(browser, many_stays_url, {"width": 844, "height": 390})
    m = pg.evaluate(LIST)
    assert m["rows"] >= 2 - 0.05 and m["scrolls"], (browser.engine, m)
    # the card's floor is summed from its parts' type (theme.py): it must end where its note ends
    gap = pg.evaluate("""(()=>{const c=document.querySelector('.page.home .trip'),r=c.getBoundingClientRect();
      return r.bottom-parseFloat(getComputedStyle(c).paddingBottom)-c.lastElementChild.getBoundingClientRect().bottom})()""")
    assert abs(gap) <= 0.5, (browser.engine, gap)
    pg.close()


def test_a_short_stay_list_shows_whole(browser, bookings_url):
    """The one-stay card fits whole with no inner scroll (nothing faded away)."""
    pg = _page(browser, bookings_url, PHONE)
    assert pg.evaluate(LIST)["all"], browser.engine
    pg.close()
