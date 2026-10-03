"""The user's pick H1c (2026-10-03), replacing H1b: on the phone the day page stays still --
the topic-1 decision: the list card is fixed to the screen's foot and is the only thing that
scrolls -- yet scrolling the card up first puts the small calendar away (98 px), the title,
the map row and the card's top rising with it, the content moving 1:1 with the finger.
Every day can do it, a short one (10/12) too. With the map card open nothing folds.

H1c2: the day stepper keeps a put-away calendar put away, with no script (LINE and the Files
app run none): each day has a second radio, pg-dNf, and the stepper's arrows target it once
the calendar is mostly away. A day opened that way shows its list from the top with the
calendar away; at the top of that list, the month opens the calendar again."""
import io

import pytest
from conftest import DESKTOP, PHONE
from PIL import Image

FOLD = 98                            # the small calendar's height (two weeks + weekdays), measured
SHORT = {"width": 390, "height": 480}   # the fixture's D2 scrolls 200+ px here


def _sec(d):
    return f"section[data-pg={d}]"


def _open(open_page, d="d2", vp=SHORT, js=False):
    pg = open_page(vp, js=js)
    pg.evaluate(f"document.getElementById('pg-{d}').checked=true")
    pg.wait_for_timeout(200)
    return pg


def _top(pg, sel):
    return pg.evaluate(f"document.querySelector('{sel}').getBoundingClientRect().top")


def _scroll(pg, d, y):
    pg.evaluate(f"(L=>{{L.style.scrollBehavior='auto';L.scrollTop={y};L.style.scrollBehavior=''}})(document.querySelector('{_sec(d)} .plist'))")
    pg.wait_for_timeout(150)


def _checked(pg):
    return pg.evaluate("document.querySelector('input[name=pg]:checked').id")


def _days(pg):
    return pg.eval_on_selector_all("section.page.day", "s => s.map(e => e.dataset.pg)")


def _tap_arrow(pg, d, which):
    """A real tap where the arrow is drawn: whichever of its two labels shows takes it."""
    x, y = pg.eval_on_selector(f"{_sec(d)} .pcal .dstep .sw:{which}-child",
                               "e=>{const r=e.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]}")
    pg.mouse.click(x, y)
    pg.wait_for_timeout(250)


def test_the_page_stays_and_only_the_card_scrolls(open_page):
    pg = open_page(PHONE, js=False)
    for d in _days(pg):
        pg.evaluate(f"document.getElementById('pg-{d}').checked=true")
        m = pg.evaluate(f"""(s=>{{const D=s.querySelector('.dash'),L=s.querySelector('.plist');
            return [D.scrollHeight-D.clientHeight,getComputedStyle(L).overflowY,L.getBoundingClientRect().bottom,
                    document.documentElement.scrollHeight-innerHeight,D.scrollWidth-D.clientWidth]}})(document.querySelector('{_sec(d)}'))""")
        assert m[0] <= 0 and m[1] == "auto" and m[3] <= 0 and m[4] <= 0, (d, m)
        assert m[2] <= PHONE["height"] - 12, (d, m)                 # the card's foot on screen


def test_scrolling_the_card_puts_the_calendar_away_first(open_page):
    """Where a script runs the fold follows the finger 1:1 (with none it jumps at half its
    height: test_with_no_script_the_calendar_is_open_or_folded_never_between). Each position
    is read before the stopped-between scroll settles (140 ms)."""
    pg = _open(open_page, js=True)
    stop = f"{_sec('d2')} .plist .stop:nth-of-type(3)"
    at = {}
    for s in (0, 49, FOLD, 200):
        pg.evaluate(f"(L=>{{L.style.scrollBehavior='auto';L.scrollTop={s}}})(document.querySelector('{_sec('d2')} .plist'))")
        pg.wait_for_timeout(30)
        at[s] = {k: _top(pg, sel) for k, sel in (("ym", f"{_sec('d2')} .ymrow"), ("dh", f"{_sec('d2')} .pcal .dh"),
                                                  ("map", f"{_sec('d2')} .pmap"), ("card", f"{_sec('d2')} .lcap"), ("stop", stop))}
    for s in (49, FOLD, 200):
        up = min(s, FOLD)
        assert abs(at[s]["ym"] - at[0]["ym"]) <= .5, s                      # the 總覽 row stays
        for k in ("dh", "map", "card"):
            assert abs((at[0][k] - at[s][k]) - up) <= 1, (s, k, at)          # rise with the calendar, then hold
        assert abs((at[0]["stop"] - at[s]["stop"]) - s) <= 1, (s, at)       # the content: 1:1 with the finger


def test_every_day_can_put_its_calendar_away(open_page):
    """10/12 on the real trip fits the screen; it still scrolls at least the calendar's height."""
    pg = open_page(PHONE, js=False)
    for d in _days(pg):
        pg.evaluate(f"document.getElementById('pg-{d}').checked=true")
        rng = pg.evaluate(f"(L=>L.scrollHeight-L.clientHeight)(document.querySelector('{_sec(d)} .plist'))")
        assert rng >= FOLD, (d, rng)


def _shot(pg):
    return Image.open(io.BytesIO(pg.screenshot())).convert("RGB")


def _far(a, b, d=12):
    return sum(abs(x - y) for x, y in zip(a, b)) > d


@pytest.mark.parametrize("s", [0, 60, 200])
def test_the_card_keeps_its_whole_outline(browser, page_url, s):
    """The card is its own card (the user's check): top line, round corners and both sides,
    open, half-folded and folded -- on the pixels. Its clipped top is drawn by the cap."""
    pg = browser.new_page(viewport=SHORT, device_scale_factor=2, java_script_enabled=False)
    pg.goto(page_url)
    pg.evaluate("document.getElementById('pg-d2').checked=true")
    _scroll(pg, "d2", s)
    l, t, r = pg.eval_on_selector(f"{_sec('d2')} .lcap", "e=>{const r=e.getBoundingClientRect();return [r.left,r.top,r.right]}")
    mb = pg.eval_on_selector(f"{_sec('d2')} .pmap", "e=>e.getBoundingClientRect().bottom")
    img = _shot(pg)
    pg.close()
    page_bg = img.getpixel((2, int((mb + 4) * 2)))                         # in the gap under the map row
    mid = int((l + r) / 2 * 2)
    assert _far(img.getpixel((mid, int((t - .5) * 2))), page_bg), ("top line", s)
    for x in (l - .5, r + .5):
        assert _far(img.getpixel((int(x * 2), int((t + 40) * 2))), page_bg), ("side", s, x)
    assert abs(t - (mb + 8)) <= .5, (t, mb)                                 # the 8 px gap: two cards


def test_the_current_days_glow_is_whole_open_and_gone_folded(browser, page_url):
    """The current day's stamp glows 15 px around. Open, the glow reaches past the calendar's
    foot as it always has (the user saw it cut by a hard line); folded, nothing of it shows
    between the month and the title (the user saw 15/16 leak there)."""
    pg = browser.new_page(viewport=SHORT, device_scale_factor=2, java_script_enabled=False)
    pg.goto(page_url)
    pick = None
    for d in pg.eval_on_selector_all("section.page.day", "s => s.map(e => e.dataset.pg)"):
        pg.evaluate(f"document.getElementById('pg-{d}').checked=true")
        last = pg.evaluate(f"""(s=>{{const c=s.querySelector('.pcal .stamp.cur').getBoundingClientRect(),
            all=[...s.querySelectorAll('.pcal .mini .stamp')].map(e=>e.getBoundingClientRect().bottom);
            return c.bottom>=Math.max(...all)-1}})(document.querySelector('{_sec(d)}'))""")
        if last:
            pick = d
            break
    assert pick, "fixture: needs a day whose stamp is in the calendar's last week"
    c = pg.eval_on_selector(f"{_sec(pick)} .pcal .stamp.cur", "e=>{const r=e.getBoundingClientRect();return [r.left+r.width/2,r.bottom]}")
    mini = pg.eval_on_selector(f"{_sec(pick)} .pcal .mini", "e=>e.getBoundingClientRect().bottom")
    img = _shot(pg)
    bg = img.getpixel((2, int((mini + 3) * 2)))
    assert c[1] + 3 > mini - 1, "fixture: the stamp must sit at the calendar's foot"
    assert _far(img.getpixel((int(c[0] * 2), int((mini + 2) * 2))), bg, 6), "the glow is cut at the calendar's foot"
    _scroll(pg, pick, 300)
    ym = pg.eval_on_selector(f"{_sec(pick)} .ymrow", "e=>e.getBoundingClientRect().bottom")
    dh = _top(pg, f"{_sec(pick)} .pcal .dh")
    img = _shot(pg)
    pg.close()
    bg = img.getpixel((2, int((ym + 2) * 2)))
    band = [img.getpixel((x, y)) for x in range(int(110 * 2), int(280 * 2), 2) for y in range(int(ym * 2) + 2, int(dh * 2))]
    assert band and not any(_far(p, bg, 6) for p in band), "the calendar leaks between the month and the title"


def test_a_jumped_to_stop_lands_at_the_cards_top(open_page):
    pg = _open(open_page)
    ids = pg.eval_on_selector_all(f"{_sec('d2')} .plist .stop[id]", "e => e.map(x => x.id)")
    for target in (ids[0], ids[len(ids) // 2]):
        _scroll(pg, "d2", 0)
        pg.evaluate(f"location.hash='#{target}'")
        pg.wait_for_timeout(700)
        gap = _top(pg, f"#{target}") - _top(pg, f"{_sec('d2')} .lcap")
        assert 0 <= gap <= 24, (target, gap)


def test_opening_the_map_keeps_the_calendar_where_it_is(open_page):
    """The user's check (2026-10-03): opening the map card brought a folded calendar back.
    H1c folded only with the map closed -- an H1b-era guard (the open map's height is
    unknown to CSS), moot since the fold moves by transform. A folded calendar stays
    folded with the map open, the list keeps its place, and closing the map changes
    nothing either; an open calendar stays open."""
    pg = _open(open_page)
    sec, summ = _sec("d2"), f"{_sec('d2')} .mapc > summary"
    map_open_cal = _top(pg, f"{sec} .pmap")
    _scroll(pg, "d2", 200)
    folded = _top(pg, f"{sec} .pmap")
    assert abs(folded - (map_open_cal - FOLD)) <= 1, "fixture: should fold"
    pg.locator(summ).click()
    pg.wait_for_timeout(250)
    assert pg.eval_on_selector(f"{sec} .mapc", "e=>e.open")
    assert abs(_top(pg, f"{sec} .pmap") - folded) <= 1, "the map opened and the calendar came back"
    assert pg.evaluate(f"document.querySelector('{sec} .plist').scrollTop") == 200
    pg.locator(summ).click()
    pg.wait_for_timeout(250)
    assert abs(_top(pg, f"{sec} .pmap") - folded) <= 1
    _scroll(pg, "d2", 0)
    pg.locator(summ).click()
    pg.wait_for_timeout(250)
    assert abs(_top(pg, f"{sec} .pmap") - map_open_cal) <= 1, "an open calendar stays open"


def test_the_zoomed_map_covers_the_screen_with_the_calendar_folded(open_page):
    """Zoomed, the map view is a position:fixed layer inside the map row -- which carries
    the fold's transform, and a transform makes itself the fixed layer's frame. Folded,
    the zoomed map must still cover the screen and close on a tap anywhere."""
    pg = _open(open_page, vp=PHONE)
    sec = _sec("d2")
    pg.evaluate(f"(L=>{{L.style.paddingBottom='600px'}})(document.querySelector('{sec} .plist'))")
    _scroll(pg, "d2", 200)
    pg.locator(f"{sec} .mapc > summary").click()
    pg.wait_for_timeout(250)
    frame = pg.locator(f"{sec} .mv .mframe").filter(visible=True).first
    frame.click(position={"x": 12, "y": 12})
    pg.wait_for_timeout(300)
    box = pg.evaluate(f"""(()=>{{const m=[...document.querySelectorAll('{sec} .mv')].find(v=>v.querySelector('.zck:checked'));
        const r=m.getBoundingClientRect();return [r.left,r.top,r.width,r.height]}})()""")
    assert box[0] <= 0.5 and box[1] <= 0.5 and box[2] >= PHONE["width"] - 1 and box[3] >= PHONE["height"] - 1, box
    pg.mouse.click(PHONE["width"] / 2, PHONE["height"] - 20)       # far from the frame: closes
    pg.wait_for_timeout(250)
    assert pg.evaluate(f"document.querySelectorAll('{sec} .zck:checked').length") == 0


# --- H1c2: the stepper keeps the calendar put away, with no script ---

def _folded(pg, d):
    """The calendar is away: the title sits a calendar higher than when open."""
    return pg.evaluate(f"(s=>s.querySelector('.pmap').getBoundingClientRect().top)(document.querySelector('{_sec(d)}'))")


def test_the_stepper_keeps_a_put_away_calendar_put_away(open_page):
    pg = _open(open_page)
    open_map = _folded(pg, "d2")
    _scroll(pg, "d2", 200)
    _tap_arrow(pg, "d2", "last")
    assert _checked(pg) == "pg-d3f"
    assert abs(_folded(pg, "d3") - (open_map - FOLD)) <= 1                   # arrives with it away
    first = pg.eval_on_selector(f"{_sec('d3')} .plist .list>*", "e=>e.getBoundingClientRect().top")
    assert 0 <= first - _top(pg, f"{_sec('d3')} .lcap") <= 16                 # its list from the top
    _tap_arrow(pg, "d3", "first")                                              # and on, still away
    assert _checked(pg) == "pg-d2f" and abs(_folded(pg, "d2") - (open_map - FOLD)) <= 1


@pytest.mark.parametrize("s,want", [(0, "pg-d3"), (30, "pg-d3"), (70, "pg-d3f")])
def test_the_stepper_follows_how_far_the_calendar_is_away(open_page, s, want):
    pg = _open(open_page)
    _scroll(pg, "d2", s)
    _tap_arrow(pg, "d2", "last")
    assert _checked(pg) == want


def test_the_month_opens_a_put_away_calendar_at_the_top(open_page):
    pg = _open(open_page)
    open_map = _folded(pg, "d2")
    _scroll(pg, "d2", 200)
    _tap_arrow(pg, "d2", "last")
    unf = f"{_sec('d3')} .ymrow .unf"
    assert pg.eval_on_selector(unf, "e=>getComputedStyle(e).visibility") == "visible"
    _scroll(pg, "d3", 120)
    assert pg.eval_on_selector(unf, "e=>getComputedStyle(e).visibility") == "hidden"   # scrolled: not a button
    _scroll(pg, "d3", 0)
    pg.locator(f"{_sec('d3')} .ymrow .ym").click()
    pg.wait_for_timeout(200)
    assert _checked(pg) == "pg-d3"
    assert abs(_folded(pg, "d3") - open_map) <= 1                             # the calendar is back


def test_a_short_day_opened_folded_still_offers_the_month(open_page):
    """iOS seemed to read a zero scroll range as 'at the end' and hid the month's ⌄ on the
    days that fit (the user's check): a folded day always keeps a little range."""
    pg = open_page(PHONE, js=False)
    for d in _days(pg):
        pg.evaluate(f"document.getElementById('pg-{d}f').checked=true")
        pg.wait_for_timeout(80)
        m = pg.evaluate(f"""(s=>{{const L=s.querySelector('.plist'),u=s.querySelector('.ymrow .unf');
            return [L.scrollHeight-L.clientHeight,getComputedStyle(u).display,getComputedStyle(u).visibility]}})(document.querySelector('{_sec(d)}'))""")
        assert m[0] > 0 and m[1] != "none" and m[2] == "visible", (d, m)


def test_the_desktop_has_one_stepper_and_no_fold(open_page):
    pg = open_page(DESKTOP, js=False)
    pg.evaluate("document.getElementById('pg-d2').checked=true")
    assert pg.locator(f"{_sec('d2')} .plist .dh-list .dstep .sf").count() == 0
    pg.evaluate("document.getElementById('pg-d2f').checked=true")             # a folded day on a wide screen
    pg.wait_for_timeout(100)
    assert pg.eval_on_selector(_sec("d2"), "e=>getComputedStyle(e).display") != "none"
    assert pg.eval_on_selector(f"{_sec('d2')} .lcap", "e=>getComputedStyle(e).display") == "none"


# --- the fold is the calendar's own height (found on the README's 1-week demo trip) ---

@pytest.mark.parametrize("url", ["hakodate_url", "page_url", "long_rings_url"], ids=["1-week", "2-week", "many-week"])
def test_the_fold_is_the_calendars_own_height(browser, request, url):
    """H1c first folded a fixed 98 px -- two weeks of calendar, trip-e's. A trip inside
    one week has a 60 px calendar: folding 98 pushed the title up over the month row. A trip
    across more weeks has a taller one, which 98 px did not put away. The fold is the mini
    calendar's height, whatever its weeks."""
    pg = browser.new_page(viewport={"width": 390, "height": 480}, java_script_enabled=False)
    pg.goto(request.getfixturevalue(url))
    pg.evaluate("document.getElementById('pg-d2').checked=true")
    pg.wait_for_timeout(200)
    sec = _sec("d2")
    h = pg.eval_on_selector(f"{sec} .pcal .mini", "e=>e.getBoundingClientRect().height")
    map0 = _top(pg, f"{sec} .pmap")
    rng = pg.evaluate(f"(L=>L.scrollHeight-L.clientHeight)(document.querySelector('{sec} .plist'))")
    assert rng >= h, ("every day scrolls at least its calendar's height", rng, h)
    _scroll(pg, "d2", h + 40)
    # CI's headless WebKit can apply the scroll-driven fold a few frames late on the heavy
    # many-week page (it read 0 once): wait for it, up to 3 s -- a fold that never comes fails
    for _ in range(60):
        rose = map0 - _top(pg, f"{sec} .pmap")
        if abs(rose - h) <= 1:
            break
        pg.wait_for_timeout(50)
    ym = pg.eval_on_selector(f"{sec} .ymrow", "e=>e.getBoundingClientRect().bottom")
    dh = _top(pg, f"{sec} .pcal .dh")
    pg.close()
    assert abs(rose - h) <= 1, ("the card rises by the calendar's height", rose, h)
    assert dh >= ym - .5, ("the title stays below the month row", dh, ym)


# --- open or folded, never between (the user's call, 2026-10-04) ---
# No script (Files / LINE previews): the fold jumps at half its height. With a script (a
# browser -- e.g. the password-protected copy a family opens in Safari): the fold follows
# the finger 1:1 as it always did, and a scroll that stops between settles to the nearer end.

def _cal(pg, d="d2"):
    return pg.evaluate(f"(s=>[s.querySelector('.pcal .mini').offsetHeight,s.querySelector('.pmap').getBoundingClientRect().top])(document.querySelector('{_sec(d)}'))")


def test_with_no_script_the_calendar_is_open_or_folded_never_between(open_page):
    pg = _open(open_page)                                   # js off
    h, open_map = _cal(pg)
    for s, want in ((h / 2 - 2, open_map), (h / 2 + 2, open_map - h), (h, open_map - h), (4, open_map)):
        _scroll(pg, "d2", s)
        assert abs(_cal(pg)[1] - want) <= 1, (s, _cal(pg)[1], want)


def _settled(pg, d="d2", limit=3000):
    last, same, waited = None, 0, 0
    while waited < limit:
        now = pg.evaluate(f"document.querySelector('{_sec(d)} .plist').scrollTop")
        same = same + 1 if now == last else 0
        if same >= 6:
            return now
        last = now
        pg.wait_for_timeout(50); waited += 50
    return now


def test_with_a_script_the_fold_follows_the_finger_then_settles(open_page):
    pg = _open(open_page, js=True)
    h, open_map = _cal(pg)
    L = f"document.querySelector('{_sec('d2')} .plist')"
    pg.evaluate(f"(L=>{{L.style.scrollBehavior='auto';L.scrollTop={h / 4}}})({L})")
    pg.wait_for_timeout(30)                                   # mid-gesture: 1:1, not a jump
    assert abs(_cal(pg)[1] - (open_map - h / 4)) <= 1.5, (_cal(pg)[1], open_map - h / 4)
    assert _settled(pg) == 0                                  # stopped a quarter in: opens
    pg.evaluate(f"(L=>{{L.style.scrollBehavior='auto';L.scrollTop={round(h * .7)}}})({L})")
    assert abs(_settled(pg) - h) <= 1                         # stopped past half: folds
    pg.evaluate(f"(L=>{{L.style.scrollBehavior='auto';L.scrollTop={h + 80}}})({L})")
    assert _settled(pg) == h + 80                             # reading the list: left alone


def test_with_a_script_a_day_opened_folded_can_still_be_pulled_open(open_page):
    """The user's check: in the script version, Day 3 reached by › with the calendar away
    could not be pulled open -- the day opened on pg-d3f, whose list keeps no room above
    (only the month opens it, the no-script design). Where a script runs, that day opens on
    its plain radio scrolled to the fold: it looks the same, and pulling down unfolds."""
    pg = _open(open_page, js=True)
    h, open_map = _cal(pg)
    pg.evaluate(f"(L=>{{L.style.scrollBehavior='auto';L.scrollTop={h + 40}}})(document.querySelector('{_sec('d2')} .plist'))")
    pg.wait_for_timeout(300)
    _tap_arrow(pg, "d2", "last")
    pg.wait_for_timeout(200)
    assert _checked(pg) == "pg-d3"
    assert abs(_cal(pg, "d3")[1] - (open_map - h)) <= 1                 # arrives folded
    assert pg.evaluate(f"document.querySelector('{_sec('d3')} .plist').scrollTop") == h
    pg.evaluate(f"(L=>{{L.style.scrollBehavior='auto';L.scrollTop=0}})(document.querySelector('{_sec('d3')} .plist'))")
    pg.wait_for_timeout(200)
    assert abs(_cal(pg, "d3")[1] - open_map) <= 1                       # pulled down: open
