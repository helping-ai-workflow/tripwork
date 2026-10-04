"""v1.2 the publish build's phone page: PUBLISH_JS (scripts/render/reader/publish.py)
rebuilds each day's fold on one native scroller with position:sticky and turns the
day-to-day swipe into a stacked glide. These checks are the ones the approved prototype
(v5) passed, ported to the shipped page on the Hakodate fixture (tests/reader_fixture.py):

- at rest the publish page draws what the check build draws (pixel diff, threshold 8,
  baseline = the check build of the same trip), plus direct ink probes for the two things
  v4 lost and a band diff explained away: the map card's side borders and the current
  stamp's glow;
- the fold settles open or folded, the card's cap stays 8 px under an open map, the
  steppers / 總覽 / stamps still lead where they did, only today shows, and the full-screen
  layers (zoomed map, 給司機看, zoomed photo) still cover the screen;
- touch (Chromium + CDP): the 30 degree gate, commit past half or on a flick, the edges
  rubber-band, a two-month trip, a one-day trip, and the style-recalc cost of a swipe.

The touch tests run once, on their own Chromium (`chromium`, launched from the session's
Playwright driver): touch events are dispatched through CDP, which WebKit has not."""
import io
import math

import pytest
from PIL import Image, ImageChops

PHONE = {"width": 390, "height": 844}
ANDROID = {"width": 360, "height": 780}

CUR = ("[document.querySelector('input[name=pg]:checked').id,"
       " [...document.querySelectorAll('.track .on')].map(s=>s.dataset.pg).join(),"
       " document.querySelectorAll('.track .to').length]")


def _go(pg, pid):
    pg.evaluate(f"(r=>{{r.checked=true;r.dispatchEvent(new Event('change',{{bubbles:true}}))}})(document.getElementById('{pid}'))")
    pg.wait_for_timeout(500)


def _cur(pg):
    return pg.evaluate("document.querySelector('input[name=pg]:checked').id")


def _vs(day):
    return f"document.querySelector('section[data-pg={day}] .vs')"


def _scroll(pg, day, top):
    pg.evaluate(f"(L=>{{L.style.scrollBehavior='auto';L.scrollTop={top}}})({_vs(day)})")
    pg.wait_for_timeout(700)


def _fold(pg, day):
    return pg.evaluate(f"document.querySelector('section[data-pg={day}] .pcal .mini').offsetHeight")


def _new(browser, viewport, url, dpr=2, touch=False):
    kw = dict(viewport=viewport, device_scale_factor=dpr)
    if touch:
        kw.update(has_touch=True, is_mobile=True)
    ctx = browser.new_context(**kw)
    pg = ctx.new_page()
    pg.goto(url)
    return ctx, pg


def _touch(ctx, pg):
    cdp = ctx.new_cdp_session(pg)

    def t(kind, x=0, y=0):
        cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [] if kind == "touchEnd" else [{"x": x, "y": y}]})
    return t


def _drag(pg, t, x0, y0, dx, dy, steps=15, ms=400):
    t("touchStart", x0, y0)
    for i in range(1, steps + 1):
        t("touchMove", x0 + dx * i / steps, y0 + dy * i / steps)
        if ms:
            pg.wait_for_timeout(ms / steps)
    t("touchEnd")
    pg.wait_for_timeout(800)


def _angled(pg, t, deg, dist, left=True, steps=15, ms=400, y0=600):
    """A drag `dist` px long at `deg` degrees above the horizontal, leftwards (to the next
    day) from x 280 or rightwards (to the previous day) from x 80."""
    sign = 1 if left else -1
    _drag(pg, t, 280 if left else 80, y0, -sign * dist * math.cos(math.radians(deg)),
          -dist * math.sin(math.radians(deg)), steps=steps, ms=ms)


def _tap(pg, sel):
    """Click the centre of the first visible element matching sel (the ‹ › come in an open
    and a folded pair, one of them hidden)."""
    xy = pg.evaluate(f"""(l=>{{const r=l.getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]}})(
        [...document.querySelectorAll('{sel}')].find(l=>getComputedStyle(l).visibility=='visible'&&l.getBoundingClientRect().width>0))""")
    pg.mouse.click(*xy)
    pg.wait_for_timeout(700)
    return xy


def _rect(pg, sel):
    return pg.evaluate(f"(r=>[r.left,r.top,r.right,r.bottom])(document.querySelector('{sel}').getBoundingClientRect())")


def _png(pg):
    return Image.open(io.BytesIO(pg.screenshot())).convert("RGB")


def _chmax(a, b):
    """Per pixel, the largest channel difference between two RGB images (an L image)."""
    r, g, bl = ImageChops.difference(a, b).split()
    return ImageChops.lighter(ImageChops.lighter(r, g), bl)


def _over(d, threshold=8):
    """[(x, y, delta)] of the pixels of the difference image d above threshold."""
    box = d.point(lambda v: 255 if v > threshold else 0).getbbox()
    if not box:
        return []
    px = d.load()
    return [(x, y, px[x, y]) for y in range(box[1], box[3]) for x in range(box[0], box[2]) if px[x, y] > threshold]


@pytest.fixture(scope="module")
def chromium(pw):
    """The module's own Chromium, for the touch tests (CDP) and as the Chromium half of
    the rest-pixel diff. LCD (subpixel) text antialiasing is off: no phone draws it, and
    with it on every glyph of the check build (text in the root layer, LCD-AA) differs from
    the publish page's (text inside the fixed track's layer, grayscale) -- measured 36 535
    pixels over threshold at 390 x 844 @2x, all of them colour fringes on glyphs."""
    b = pw.chromium.launch(args=["--disable-lcd-text"])
    yield b
    b.close()


@pytest.fixture(scope="module")
def driver_url(tmp_path_factory):
    """The Hakodate fixture has no stop with an address, so no 給司機看 sheet: this copy
    gives 五稜郭公園 (day 2) a made-up local address."""
    import copy

    from scripts.render.reader import render_reader
    from tests import reader_fixture as R
    pm = copy.deepcopy(R.poi_map())
    pm["hak-goryokaku"]["address_local"] = "北海道函館市サンプル町1-1"
    f = tmp_path_factory.mktemp("publish-driver") / "driver.html"
    f.write_text(render_reader(R.itinerary(), pm, build="publish", **R.reader_kwargs()), encoding="utf-8")
    return f.as_uri()


# ---------------------------------------------------------------- rest pixels

STATES = (("open", False, "0"), ("folded", False, "F"), ("map open", True, "0"),
          ("map folded", True, "F"), ("deep", False, "200"))


def _rest(b, url, scroller, mp, top, dpr):
    ctx, pg = _new(b, PHONE, url, dpr)
    _go(pg, "pg-d2")
    if mp:
        pg.click("section[data-pg=d2] .mapc summary")
        pg.wait_for_timeout(300)
    t = "document.querySelector('section[data-pg=d2] .pcal .mini').offsetHeight" if top == "F" else top
    pg.evaluate(f"(L=>{{L.style.scrollBehavior='auto';L.scrollTop={t}}})(document.querySelector('{scroller}'))")
    pg.wait_for_timeout(700)
    boxes = {k: _rect(pg, f"section[data-pg=d2] {k}") for k in (".dn", ".pcal", ".lfoot")}
    im = _png(pg)
    ctx.close()
    return im, boxes


def _inside(x, y, box, dpr, pad=0):
    return box[0] * dpr - pad <= x < box[2] * dpr + pad and box[1] * dpr - pad <= y < box[3] * dpr + pad


def _rest_diff(b, publish_url, check_url, dpr):
    """For each rest state: the pixels (device px) over threshold 8, outside day 2's `.dn`
    (the digits sit in PUBLISH_JS's rolling wrapper), each tagged corner / calendar-shift /
    other, and the largest delta."""
    out = {}
    for name, mp, top in STATES:
        a, boxes = _rest(b, publish_url, "section[data-pg=d2] .vs", mp, top, dpr)
        c, _ = _rest(b, check_url, "section[data-pg=d2] .plist", mp, top, dpr)
        d = _chmax(a, c)
        # the check pixel one device px above or below (WebKit 3x's calendar snap)
        shifted = ImageChops.darker(_chmax(a, ImageChops.offset(c, 0, 1)), _chmax(a, ImageChops.offset(c, 0, -1))).load()
        L, _t, R, B = boxes[".lfoot"]
        corners = ((L - 1, B - 14, L + 14, B + 1), (R - 14, B - 14, R + 1, B + 1))   # the card's bottom curves
        tags = {"corner": [], "calendar": [], "other": []}
        for x, y, v in _over(d):
            if _inside(x, y, boxes[".dn"], dpr):
                continue
            if any(_inside(x, y, k, dpr) for k in corners):
                tags["corner"].append(v)
            elif _inside(x, y, boxes[".pcal"], dpr) and shifted[x, y] <= 8:
                tags["calendar"].append(v)
            else:
                tags["other"].append((round(x / dpr, 1), round(y / dpr, 1), v))
        out[name] = tags
    return out


def test_rest_pixels_equal_the_check_build(browser, chromium, publish_url, check_url):
    """At rest, day 2 of the publish page is the check build's day 2, pixel for pixel
    (threshold 8 per channel), in five states: open, folded, map open, map folded, deep.

    Allowed, measured on this fixture (2026-10-04):
    - the `.dn` box (Day 2's digits sit in PUBLISH_JS's rolling wrapper; measured 0 px);
    - the card's two bottom corner curves (PUBLISH_JS draws the card's foot with .lfoot's
      ::after), AA only: at most 8 x dpr^2 pixels, delta <= 12 at 2x and <= 14 at 3x.
      Measured WebKit 2x: 5 / 5 / 9 / 5 / 25 px (deep), delta 10-12 -- more pixels than the
      prototype's 4 on the demo trip (the brief's "<= 8"), every one inside the two 14 px
      corner squares and equal to the check build within 1 device px. WebKit 3x: 1 / 1 / 8 /
      1 / 48 px, delta 10-13 (13: map open) -- the same curve sampled finer;
    - WebKit at dpr 3 only: the calendar draws ~1 device px higher (it sits in a scroller
      layer snapped to device pixels; layout tops are equal), so inside `.pcal` a pixel may
      differ when it equals the check pixel 1 device px above or below. Measured open /
      map open: 1 628 px each (delta up to 197), every one matched by the 1 px shift;
      folded, the calendar is away and nothing differs. Not allowed at 2x (measured 0).
    - Chromium (no LCD text, see the `chromium` fixture): the check build's list scroller
      starts at y 136.641 (fractional; the title row is 25.641 tall) where the publish
      page's starts at y 39, so Chromium rasterises the scrolled content at another
      sub-pixel phase and antialiased curves (icons, dashed borders, card corners) differ
      in value, not in place. Measured 68-89 px per state (33-47 of them at the bottom
      corners), delta <= 41: allowed up to 120 px with delta <= 48 anywhere. A lost border line (the v4 defect: 2 sides x 44 px x
      2 device px) or a cut glow is several hundred and fails; the ink probes below catch
      those directly."""
    if browser.engine == "chromium":
        res = _rest_diff(chromium, publish_url, check_url, 2)
        for name, tags in res.items():
            vals = tags["corner"] + tags["calendar"] + [v for *_, v in tags["other"]]
            assert len(vals) <= 120 and max(vals, default=0) <= 48, (name, len(vals), max(vals, default=0), tags["other"][:20])
        return
    for dpr in (2, 3):
        res = _rest_diff(browser, publish_url, check_url, dpr)
        for name, tags in res.items():
            assert tags["other"] == [], (dpr, name, len(tags["other"]), tags["other"][:20])
            assert len(tags["corner"]) <= 8 * dpr * dpr and max(tags["corner"], default=0) <= {2: 12, 3: 14}[dpr], (dpr, name, tags["corner"])
            if dpr == 2:
                assert tags["calendar"] == [], (name, len(tags["calendar"]))


def _edge_ink(pg, dpr):
    """The darkest luminance within 2 device px of `.mapc`'s left and right edges, at its
    vertical middle: the map card's side border (its 1 px outline)."""
    l, t, r, b = _rect(pg, "section[data-pg=d2] .mapc")
    im = _png(pg).convert("L")
    y = round((t + b) / 2 * dpr)
    return tuple(min(im.getpixel((x, y)) for x in range(round(e * dpr) - 2, round(e * dpr) + 3)) for e in (l, r))


def test_map_card_borders_keep_their_ink(browser, publish_url, check_url):
    """v4 widened .pmap by 1 px and its outline went past the scroller's edge, clipped: the
    map card lost its side borders while a band diff was explained away. Probe the ink
    itself at five phone widths, @3x, map closed and open: equal to the check build +-3."""
    for w in (360, 390, 393, 402, 430):
        got = {}
        for name, url in (("publish", publish_url), ("check", check_url)):
            ctx, pg = _new(browser, {"width": w, "height": 844}, url, dpr=3)
            _go(pg, "pg-d2")
            closed = _edge_ink(pg, 3)
            pg.click("section[data-pg=d2] .mapc summary")
            pg.wait_for_timeout(300)
            got[name] = (closed, _edge_ink(pg, 3))
            ctx.close()
        for (pa, ca), state in zip(zip(got["publish"], got["check"]), ("closed", "open")):
            assert all(abs(p - c) <= 3 for p, c in zip(pa, ca)), (w, state, got)


def _glow(b, url, scroller, folded):
    ctx, pg = _new(b, PHONE, url, 2)
    _go(pg, "pg-d2")
    if folded:
        pg.evaluate(f"(L=>{{L.style.scrollBehavior='auto';L.scrollTop=document.querySelector('section[data-pg=d2] .pcal .mini').offsetHeight}})(document.querySelector('{scroller}'))")
        pg.wait_for_timeout(700)
    s = _rect(pg, "section[data-pg=d2] .stamp.cur")
    ym = _rect(pg, "section[data-pg=d2] .ymrow")
    im = _png(pg)
    ctx.close()
    if folded:      # the 20 px under the month row, where a folded glow would hang
        box = (s[0] - 30, ym[3], s[2] + 30, ym[3] + 20)
    else:
        box = (s[0] - 30, s[1] - 30, s[2] + 30, s[3] + 30)
    return im.crop(tuple(round(v * 2) for v in box)), box


def test_current_stamp_glow_matches_and_hides_when_folded(browser, chromium, publish_url, check_url):
    """The current day's stamp glows past the calendar's foot over the title row: open, the
    crop around it (+-30 px) equals the check build's; folded, the 20 px under the month
    row equal the check build's (no glow hanging under the scroller's top). v4 gave the
    title row an opaque background and the glow read as cut. Chromium runs without LCD
    text (see the `chromium` fixture)."""
    b = chromium if browser.engine == "chromium" else browser
    for folded in (False, True):
        a, box = _glow(b, publish_url, "section[data-pg=d2] .vs", folded)
        c, box2 = _glow(b, check_url, "section[data-pg=d2] .plist", folded)
        assert box == box2, (folded, box, box2)
        bad = _over(_chmax(a, c))
        assert bad == [], (folded, len(bad), bad[:20])


# ---------------------------------------------------------------- behaviour

def test_fold_settles_open_or_folded(browser, publish_url):
    """A scroll that stops between settles to the nearer end: 20 -> open, fold-20 -> folded."""
    ctx, pg = _new(browser, PHONE, publish_url)
    _go(pg, "pg-d2")
    fold = _fold(pg, "d2")
    assert fold > 40, fold
    for top, want in ((20, 0), (fold - 20, fold)):
        _scroll(pg, "d2", top)
        pg.wait_for_timeout(300)
        got = pg.evaluate(f"{_vs('d2')}.scrollTop")
        assert abs(got - want) <= 1, (top, want, got)
    ctx.close()


def test_cap_stays_8px_under_the_map(browser, publish_url):
    """Map open, at every scroll from open to deep the card's cap sits 8 px under the map
    (the .pwrap band): sticky and scrolling are the browser's, nothing drifts."""
    ctx, pg = _new(browser, PHONE, publish_url)
    _go(pg, "pg-d2")
    pg.click("section[data-pg=d2] .mapc summary")
    pg.wait_for_timeout(300)
    bad = []
    for top in (0, 10, 25, 45, 60, 90, 150, 300):
        pg.evaluate(f"(L=>{{L.style.scrollBehavior='auto';L.scrollTop={top}}})({_vs('d2')})")
        pg.wait_for_timeout(30)
        gap = pg.evaluate("""(s=>s.querySelector('.lcap').getBoundingClientRect().top-s.querySelector('.pmap').getBoundingClientRect().bottom)(
            document.querySelector('section[data-pg=d2]'))""")
        if abs(gap - 8) > 0.5:
            bad.append((top, gap))
    assert bad == []
    ctx.close()


def test_steppers_and_home(browser, publish_url):
    """‹ › step a day (gliding), a folded › keeps the fold, 總覽 goes home, and the home's
    stamp opens that day with only it shown."""
    ctx, pg = _new(browser, PHONE, publish_url)
    _go(pg, "pg-d2")
    _tap(pg, "section[data-pg=d2] .dstep .sw:last-child label")
    assert pg.evaluate(CUR) == ["pg-d3", "d3", 0]
    _tap(pg, "section[data-pg=d3] .dstep .sw:first-child label")
    assert pg.evaluate(CUR) == ["pg-d2", "d2", 0]
    fold = _fold(pg, "d2")
    _scroll(pg, "d2", fold)
    _tap(pg, "section[data-pg=d2] .dstep .sw:last-child label")
    c = pg.evaluate(CUR)
    assert c[0] == "pg-d3" and c[1] == "d3", c
    assert pg.evaluate(f"{_vs('d3')}.scrollTop") == _fold(pg, "d3")
    _tap(pg, "section[data-pg=d3] .back")
    assert _cur(pg) == "pg-home"
    _go(pg, "pg-d1")
    assert pg.evaluate(CUR) == ["pg-d1", "d1", 0]
    ctx.close()


def test_only_today_is_visible_and_tappable(browser, publish_url):
    """The neighbours stay in the track for the swipe, invisible and out of the way: only
    today's page is opaque, and a tap on its › lands on today's page."""
    ctx, pg = _new(browser, PHONE, publish_url)
    _go(pg, "pg-d2")
    ops = pg.evaluate("[...document.querySelectorAll('.track>.page.day')].map(s=>[s.dataset.pg,s.classList.contains('on'),getComputedStyle(s).opacity])")
    assert [d for d, on, o in ops if o == "1"] == ["d2"] and [d for d, on, o in ops if on] == ["d2"], ops
    for sel in (".dstep .sw:last-child label", ".dstep .sw:first-child label"):
        hit = pg.evaluate(f"""(l=>{{const r=l.getBoundingClientRect(),e=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
            return e&&e.closest('section.page')?e.closest('section.page').dataset.pg:null}})(
            [...document.querySelectorAll('section[data-pg=d2] {sel}')].find(l=>getComputedStyle(l).visibility=='visible'&&l.getBoundingClientRect().width>0))""")
        assert hit == "d2", (sel, hit)
    ctx.close()


def _covers(pg, sel, vp, probe):
    """sel's box is the whole screen and the element hit at `probe` is inside it."""
    return pg.evaluate(f"""(e=>{{const r=e.getBoundingClientRect(),h=document.elementFromPoint({probe[0]},{probe[1]});
        return [Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height),!!(h&&e.contains(h))]}})(document.querySelector('{sel}'))""")


def test_full_screen_layers_cover_the_screen(browser, publish_url, driver_url):
    """Fixed layers inside the moving parts must still be fixed to the screen: anything
    that makes .pwrap / .pcard a containing block at rest (a transform, a will-change on
    translate) shrinks the zoomed map, 給司機看 and the zoomed photo into their card."""
    vw, vh = PHONE["width"], PHONE["height"]
    full = [0, 0, vw, vh, True]
    ctx, pg = _new(browser, PHONE, publish_url)
    _go(pg, "pg-d2")
    pg.click("section[data-pg=d2] .mapc summary")
    pg.wait_for_timeout(300)
    zid = pg.evaluate("document.querySelector('section[data-pg=d2] .zck').id")
    pg.evaluate(f"document.getElementById('{zid}').click()")
    pg.wait_for_timeout(400)
    assert _covers(pg, f"section[data-pg=d2] .mv:has(#{zid})", PHONE, (vw // 2, vh - 40)) == full
    pg.evaluate(f"document.getElementById('{zid}').click()")
    pg.wait_for_timeout(300)
    # the zoomed photo (day 2's 五稜郭公園): open its stop, then the photo
    sid = pg.evaluate("document.querySelector('section[data-pg=d2] .pz').closest('.stop').id")
    pg.evaluate(f"location.hash='#{sid}'")
    pg.wait_for_timeout(500)
    pid = pg.evaluate("document.querySelector('section[data-pg=d2] .pz').id")
    pg.evaluate(f"document.getElementById('{pid}').click()")
    pg.wait_for_timeout(400)
    assert _covers(pg, f"section[data-pg=d2] .bp:has(#{pid})", PHONE, (vw // 2, vh // 2)) == full
    ctx.close()
    # 給司機看
    ctx, pg = _new(browser, PHONE, driver_url)
    _go(pg, "pg-d2")
    href = pg.evaluate("document.querySelector('section[data-pg=d2] .drvbtn').getAttribute('href')")
    pg.evaluate(f"location.hash='{href}'")
    pg.wait_for_timeout(500)
    assert _covers(pg, href, PHONE, (vw // 2, 60)) == full
    ctx.close()


# ---------------------------------------------------------------- touch (Chromium, CDP)

def test_touch_gate_commit_flick_edges(chromium, publish_url):
    """Sideways only within 30 degrees of horizontal; commit past half the width or on a
    flick; the first day rubber-bands; a steep drag is the day's own scroll."""
    ctx, pg = _new(chromium, ANDROID, publish_url, touch=True)
    t = _touch(ctx, pg)
    cases = ((10, 250, True, 15, 400, "pg-d3"),     # past half -> next
             (35, 200, True, 15, 400, "pg-d2"),     # outside the gate -> no change
             (10, 110, True, 15, 400, "pg-d2"),     # short and slow -> back
             (10, 120, True, 3, 0, "pg-d3"),        # short flick -> next
             (10, 250, False, 15, 400, "pg-d1"))    # rightwards -> previous
    for deg, dist, left, steps, ms, want in cases:
        _go(pg, "pg-d2")
        _scroll(pg, "d2", 0)
        _angled(pg, t, deg, dist, left=left, steps=steps, ms=ms)
        c = pg.evaluate(CUR)
        assert c == [want, want[3:], 0], (deg, dist, left, steps, c)
    _go(pg, "pg-d1")
    _angled(pg, t, 10, 250, left=False)
    assert pg.evaluate(CUR) == ["pg-d1", "d1", 0]
    _go(pg, "pg-d2")
    _scroll(pg, "d2", 0)
    _angled(pg, t, 80, 250)
    assert pg.evaluate(CUR) == ["pg-d2", "d2", 0]
    assert pg.evaluate(f"{_vs('d2')}.scrollTop") > 0
    ctx.close()


def test_swipe_between_days_of_different_fold_heights(chromium, two_month_url):
    """A folded day hands the fold to its neighbour at the NEIGHBOUR's own height.

    Every day page of a trip draws the same mini calendar (calendar.weeks over all trip
    dates, day.py's --wk), so the shipped renderer never gives two days of one trip
    different folds -- on this Aug/Sep trip both are 60. To make the hand-off measurable
    the target day is given a two-week calendar in the page (one more week row and --wk:2,
    what day.py draws for a two-week trip), so its fold (98) differs from the source's."""
    ctx, pg = _new(chromium, ANDROID, two_month_url, touch=True)
    t = _touch(ctx, pg)
    _go(pg, "pg-d2")
    assert pg.evaluate("[...document.querySelectorAll('.track>.page.day')].map(s=>s.dataset.pg)") == ["d1", "d2", "d3"]
    assert pg.evaluate("document.querySelector('section[data-pg=d2] .ym').textContent").endswith("8～9 月")
    pg.evaluate("""(s=>{const g=s.querySelector('.pcal .mini .g');[...g.children].slice(-7).forEach(c=>g.appendChild(c.cloneNode(true)));
        s.style.setProperty('--wk','2')})(document.querySelector('section[data-pg=d3]'))""")
    src, dst = _fold(pg, "d2"), _fold(pg, "d3")
    assert (src, dst) == (60, 98)
    _scroll(pg, "d2", src)
    assert pg.evaluate(f"{_vs('d2')}.scrollTop") == src
    _angled(pg, t, 10, 250)
    assert pg.evaluate(CUR) == ["pg-d3", "d3", 0]
    assert pg.evaluate(f"{_vs('d3')}.scrollTop") == dst
    ctx.close()


def test_single_day_trip_only_rubber_bands(chromium, one_day_url):
    """No neighbour: both ways the page gives a little and comes back, nothing throws."""
    ctx, pg = _new(chromium, ANDROID, one_day_url, touch=True)
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    t = _touch(ctx, pg)
    _go(pg, "pg-d1")
    for left in (True, False):
        _angled(pg, t, 10, 250, left=left)
        assert pg.evaluate(CUR) == ["pg-d1", "d1", 0], left
        assert pg.evaluate("[...document.querySelectorAll('section[data-pg=d1] :is(.pwrap,.lcap,.pcard,.lfoot)')].map(e=>e.style.translate).join('')") == ""
    assert errors == []
    ctx.close()


def test_swipe_cost_budget(chromium, publish_url):
    """A swipe restyles only its two pages' moving parts: style recalc per move <= 1.0 ms
    and <= 25 ms for the release (glide + swap), Chromium's own metrics over 25 moves of
    8 px after 5 warm-up moves. Prototype v5 measured 0.76 ms/move and 15-17 ms; v4 (one
    inherited variable on the track restyling every day each frame) 4.2 / 78."""
    ctx, pg = _new(chromium, ANDROID, publish_url, touch=True)
    t = _touch(ctx, pg)
    cdp = ctx.new_cdp_session(pg)
    cdp.send("Performance.enable")

    def recalc():
        return {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}["RecalcStyleDuration"] * 1000

    _go(pg, "pg-d2")
    x, y = 300, 600
    t("touchStart", x, y)
    for _ in range(5):
        x -= 8
        t("touchMove", x, y)
        pg.wait_for_timeout(16)
    m0 = recalc()
    for _ in range(25):
        x -= 8
        t("touchMove", x, y)
        pg.wait_for_timeout(16)
    m1 = recalc()
    t("touchEnd")
    pg.wait_for_timeout(600)
    m2 = recalc()
    per_move, release = (m1 - m0) / 25, m2 - m1
    assert pg.evaluate(CUR) == ["pg-d3", "d3", 0]
    assert per_move <= 1.0, (per_move, release)
    assert release <= 25, (per_move, release)
    ctx.close()
