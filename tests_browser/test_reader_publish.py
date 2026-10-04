"""v1.2 the publish build's phone page: PUBLISH_JS (scripts/render/reader/publish.py)
rebuilds each day's fold on one native scroller with position:sticky and turns the
day-to-day swipe into a stacked glide. These checks are the ones the approved prototype
(v5) passed, ported to the shipped page on the Hakodate fixture (tests/reader_fixture.py):

- at rest the publish page draws what the check build draws (pixel diff, threshold 8,
  baseline = the check build of the same trip), plus direct ink probes for what v4 lost
  and a band diff explained away -- the map card's side borders, the current stamp's
  glow -- and for the card cap's rounded corners over a deep-scrolled list;
- the fold settles open or folded, the card's cap stays 8 px under an open map, the
  steppers / 總覽 / stamps still lead where they did, only today shows, and the full-screen
  layers (zoomed map, 給司機看, zoomed photo) still cover the screen;
- touch (Chromium + CDP): a finger held mid-swipe (the header holds, swaps at the half,
  the cards glide with their borders), the 30 degree gate, commit past half or on a
  flick, the edges rubber-band, a two-month trip, a one-day trip, and the style-recalc
  cost of a swipe.

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


def _new(browser, viewport, url, dpr=2, touch=False, errors=None):
    """A fresh context and page at url. With `errors` (a list), page errors are collected
    into it from before the page loads: PUBLISH_JS restructures the DOM at load, and a
    listener attached after goto would miss whatever that throws."""
    kw = dict(viewport=viewport, device_scale_factor=dpr)
    if touch:
        kw.update(has_touch=True, is_mobile=True)
    ctx = browser.new_context(**kw)
    pg = ctx.new_page()
    if errors is not None:
        pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url)
    return ctx, pg


def _two_weeks(pg, day):
    """Give `day` a two-week calendar in the page (one more week row and --wk:2, what
    day.py draws for a trip over two weeks), so its fold is 98 where its neighbours' is 60.
    The shipped renderer never does this inside one trip -- day.py sets --wk from the whole
    trip (calendar.weeks(ctx.dates)), so every day page folds the same -- but PUBLISH_JS's
    hand-off must use the TARGET day's own fold height, and only unequal folds show which
    one it used."""
    pg.evaluate(f"""(s=>{{const g=s.querySelector('.pcal .mini .g');[...g.children].slice(-7).forEach(c=>g.appendChild(c.cloneNode(true)));
        s.style.setProperty('--wk','2')}})(document.querySelector('section[data-pg={day}]'))""")


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
          ("map folded", True, "F"), ("deep", False, "200"), ("map deep", True, "200"))


def _rest(b, url, scroller, mp, top, dpr, vp=PHONE, touch=False):
    ctx, pg = _new(b, vp, url, dpr, touch=touch)
    _go(pg, "pg-d2")
    if mp:
        pg.click("section[data-pg=d2] .mapc summary")
        pg.wait_for_timeout(300)
    t = "document.querySelector('section[data-pg=d2] .pcal .mini').offsetHeight" if top == "F" else top
    pg.evaluate(f"(L=>{{L.style.scrollBehavior='auto';L.scrollTop={t}}})(document.querySelector('{scroller}'))")
    pg.wait_for_timeout(700)
    boxes = {k: _rect(pg, f"section[data-pg=d2] {k}") for k in (".dn", ".pcal", ".lfoot", ".lcap")}
    im = _png(pg)
    ctx.close()
    return im, boxes


def _inside(x, y, box, dpr, pad=0):
    return box[0] * dpr - pad <= x < box[2] * dpr + pad and box[1] * dpr - pad <= y < box[3] * dpr + pad


def _rest_diff(b, publish_url, check_url, dpr, vp=PHONE, touch=False, states=STATES):
    """For each rest state: the pixels (device px) over threshold 8, outside day 2's `.dn`
    (the digits sit in PUBLISH_JS's rolling wrapper), each tagged corner / calendar-shift /
    other, and the largest delta."""
    out = {}
    for name, mp, top in states:
        a, boxes = _rest(b, publish_url, "section[data-pg=d2] .vs", mp, top, dpr, vp, touch)
        c, _ = _rest(b, check_url, "section[data-pg=d2] .plist", mp, top, dpr, vp, touch)
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


def _rest_diff_css(b, publish_url, check_url, vp, touch, dpr=2):
    """Chromium's rest diff at CSS-pixel resolution: [(x, y, delta)] per state outside
    day 2's `.dn`, after averaging each dpr x dpr block of both screenshots."""
    out = {}
    for name, mp, top in STATES:
        a, boxes = _rest(b, publish_url, "section[data-pg=d2] .vs", mp, top, dpr, vp, touch)
        c, _ = _rest(b, check_url, "section[data-pg=d2] .plist", mp, top, dpr, vp, touch)
        small = lambda im: im.resize((im.width // dpr, im.height // dpr), Image.BOX)
        out[name] = [q for q in _over(_chmax(small(a), small(c))) if not _inside(q[0], q[1], boxes[".dn"], 1)]
    return out


def test_rest_pixels_equal_the_check_build(browser, chromium, publish_url, check_url):
    """At rest, day 2 of the publish page is the check build's day 2, pixel for pixel
    (threshold 8 per channel), in six states: open, folded, map open, map folded, deep,
    map deep (deep = scroll 200, clamped to the list's end).

    Allowed, measured on this fixture (2026-10-04):
    - the `.dn` box (Day 2's digits sit in PUBLISH_JS's rolling wrapper; measured 0 px);
    - the card's two bottom corner curves (PUBLISH_JS draws the card's foot with .lfoot's
      ::after), AA only: at most 8 x dpr^2 pixels, delta <= 12 at 2x and <= 14 at 3x.
      Measured WebKit 2x: 5 / 5 / 9 / 5 / 25 (deep) / 5 px, delta 10-12 -- more pixels than
      the prototype's 4 on the demo trip (the brief's "<= 8"), every one inside the two 14 px
      corner squares and equal to the check build within 1 device px. WebKit 3x: 1 / 1 / 8 /
      1 / 48 / 1 px, delta 10-13 (13: map open) -- the same curve sampled finer;
    - WebKit at dpr 3 only: the calendar draws ~1 device px higher (it sits in a scroller
      layer snapped to device pixels; layout tops are equal), so inside `.pcal` a pixel may
      differ when it equals the check pixel 1 device px above or below. Measured open /
      map open: 1 628 px each (delta up to 197), every one matched by the 1 px shift;
      folded, the calendar is away and nothing differs. Not allowed at 2x (measured 0).
    - Chromium (no LCD text, see the `chromium` fixture), at 390 x 844 and at the Android
      size 360 x 780 (touch, mobile): the check build's list scroller starts at y 136.641
      (fractional; the title row is 25.641 tall) where the publish page's starts at y 39,
      so Chromium rasterises the scrolled content at another sub-pixel phase and
      antialiased curves (icons, dashed borders, the 導航 pills, card corners) differ in
      value, not in place. Device pixels measured 46-89 (390) and 131-287 (360) per state,
      delta <= 48. Compared instead at CSS-pixel resolution (each 2 x 2 device block
      averaged, threshold 8), where a phase difference averages out and a moved or lost
      line does not: measured 0-4 css px (390) and 12-33 (360), delta <= 18. Allowed: 40
      css px, delta <= 24, outside `.dn`. A lost side border (2 x 44 css px at delta ~25)
      or a cut glow fails; the ink probes below catch those directly too."""
    if browser.engine == "chromium":
        fails = []
        for vp, touch in ((PHONE, False), (ANDROID, True)):
            for name, bad in _rest_diff_css(chromium, publish_url, check_url, vp, touch).items():
                if len(bad) > 40 or max((v for *_, v in bad), default=0) > 24:
                    fails.append((vp["width"], name, len(bad), max(v for *_, v in bad), bad[:6]))
        assert not fails, fails
        return
    for dpr in (2, 3):
        res = _rest_diff(browser, publish_url, check_url, dpr)
        for name, tags in res.items():
            assert tags["other"] == [], (dpr, name, len(tags["other"]), tags["other"][:20])
            assert len(tags["corner"]) <= 8 * dpr * dpr and max(tags["corner"], default=0) <= {2: 12, 3: 14}[dpr], (dpr, name, tags["corner"])
            if dpr == 2:
                assert tags["calendar"] == [], (name, len(tags["calendar"]))


def _ink_at(im, x, y, dpr):
    """The darkest luminance within 2 device px of css x on css row y of the L image im."""
    return min(im.getpixel((xx, round(y * dpr))) for xx in range(round(x * dpr) - 2, round(x * dpr) + 3))


def _edge_ink(pg, dpr, sel="section[data-pg=d2] .mapc"):
    """The map card's side border (its 1 px outline): the darkest luminance within 2 device
    px of sel's left and right edges, on its summary row (top + min(22, height / 2)) --
    with the map open, the card's vertical middle is map image, whose own dark pixels
    would stand in for a missing border."""
    l, t, r, b = _rect(pg, sel)
    im = _png(pg).convert("L")
    y = t + min(22, (b - t) / 2)
    return tuple(_ink_at(im, e, y, dpr) for e in (l, r))


def test_map_card_borders_keep_their_ink(browser, publish_url, check_url):
    """v4 widened .pmap by 1 px and its outline went past the scroller's edge, clipped: the
    map card lost its side borders while a band diff was explained away. Probe the ink
    itself at five phone widths, @3x, map closed and open: equal to the check build +-3
    (measured 220 on both, both engines). Every width and state is checked before the
    assertion, so a failure names each one that lost its ink."""
    bad = []
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
            if not all(abs(p - c) <= 3 for p, c in zip(pa, ca)):
                bad.append((w, state, pa, ca))
    assert not bad, bad


def test_cap_corners_keep_the_check_builds_ink(browser, chromium, publish_url, check_url):
    """Deep-scrolled, the list passes under the card's cap (.lcap): its rounded top corners
    must show the curve and nothing in the wedge outside it. The card's straight side
    lines run on up there; PUBLISH_JS hides them with .pwrap::after (14 px of --bg under
    the cap). Probe both corners (the curve and the wedge, 18 x 18 css px from 2 px
    outside) in the deep and map-deep states at 390 x 844 and 360 x 780, @2x: equal to the
    check build, threshold 8 (measured 0 px in both engines; Chromium without LCD text)."""
    b = chromium if browser.engine == "chromium" else browser
    bad = []
    for vp, touch in ((PHONE, False), (ANDROID, True)):
        for name, mp, top in (("deep", False, "200"), ("map deep", True, "200")):
            a, boxes = _rest(b, publish_url, "section[data-pg=d2] .vs", mp, top, 2, vp, touch)
            c, cboxes = _rest(b, check_url, "section[data-pg=d2] .plist", mp, top, 2, vp, touch)
            assert boxes[".lcap"] == cboxes[".lcap"], (vp, name, boxes[".lcap"], cboxes[".lcap"])
            L, T, R, _b = boxes[".lcap"]
            for side, box in (("left", (L - 2, T - 2, L + 16, T + 16)), ("right", (R - 16, T - 2, R + 2, T + 16))):
                crop = tuple(round(v * 2) for v in box)
                over = _over(_chmax(a.crop(crop), c.crop(crop)))
                if over:
                    bad.append((vp["width"], name, side, len(over), max(v for *_, v in over)))
    assert not bad, bad


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
    assert not bad, bad
    ctx.close()


def test_steppers_and_home(browser, publish_url, two_month_url):
    """‹ › step a day (gliding), a day page's calendar stamp glides to its day, a folded ›
    hands the fold on at the next day's OWN height, 總覽 goes home, and the home's stamp
    opens that day with only it shown."""
    ctx, pg = _new(browser, PHONE, publish_url)
    _go(pg, "pg-d2")
    _tap(pg, "section[data-pg=d2] .dstep .sw:last-child label")
    assert pg.evaluate(CUR) == ["pg-d3", "d3", 0]
    _tap(pg, "section[data-pg=d3] .dstep .sw:first-child label")
    assert pg.evaluate(CUR) == ["pg-d2", "d2", 0]
    _tap(pg, 'section[data-pg=d2] .pcal label.stamp[for="pg-d1"]')
    assert pg.evaluate(CUR) == ["pg-d1", "d1", 0]
    _tap(pg, 'section[data-pg=d1] .pcal label.stamp[for="pg-d2"]')
    assert pg.evaluate(CUR) == ["pg-d2", "d2", 0]
    _tap(pg, "section[data-pg=d2] .back")
    assert _cur(pg) == "pg-home"
    _tap(pg, '.home .month label.stamp[for="pg-d1"]')
    assert pg.evaluate(CUR) == ["pg-d1", "d1", 0]
    ctx.close()
    # folded ›, into a day that folds by another height (see _two_weeks). Read as the
    # glide starts too: the label's click runs every change handler (CENTRE_JS's folded
    # radio and PUBLISH_JS's prep) synchronously, and CENTRE_JS's settle 140 ms after the
    # scroll would round a wrong hand-off (60 of 98, past half) up to the right end
    # before the tap's wait is over
    ctx, pg = _new(browser, PHONE, two_month_url)
    _go(pg, "pg-d2")
    _two_weeks(pg, "d3")
    src, dst = _fold(pg, "d2"), _fold(pg, "d3")
    assert (src, dst) == (60, 98)
    _scroll(pg, "d2", src)
    at_start = pg.evaluate(f"""(()=>{{[...document.querySelectorAll('section[data-pg=d2] .dstep .sw:last-child label')]
        .find(l=>getComputedStyle(l).visibility=='visible'&&l.getBoundingClientRect().width>0).click();return {_vs('d3')}.scrollTop}})()""")
    assert at_start == dst
    pg.wait_for_timeout(700)
    assert pg.evaluate(CUR) == ["pg-d3", "d3", 0]
    assert pg.evaluate(f"{_vs('d3')}.scrollTop") == dst
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


def _covers(pg, sel, probe):
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
    assert _covers(pg, f"section[data-pg=d2] .mv:has(#{zid})", (vw // 2, vh - 40)) == full
    pg.evaluate(f"document.getElementById('{zid}').click()")
    pg.wait_for_timeout(300)
    # the zoomed photo (day 2's 五稜郭公園): open its stop, then the photo
    sid = pg.evaluate("document.querySelector('section[data-pg=d2] .pz').closest('.stop').id")
    pg.evaluate(f"location.hash='#{sid}'")
    pg.wait_for_timeout(500)
    pid = pg.evaluate("document.querySelector('section[data-pg=d2] .pz').id")
    pg.evaluate(f"document.getElementById('{pid}').click()")
    pg.wait_for_timeout(400)
    assert _covers(pg, f"section[data-pg=d2] .bp:has(#{pid})", (vw // 2, vh // 2)) == full
    ctx.close()
    # 給司機看
    ctx, pg = _new(browser, PHONE, driver_url)
    _go(pg, "pg-d2")
    href = pg.evaluate("document.querySelector('section[data-pg=d2] .drvbtn').getAttribute('href')")
    pg.evaluate(f"location.hash='{href}'")
    pg.wait_for_timeout(500)
    assert _covers(pg, href, (vw // 2, 60)) == full
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


HEAD = """(d=>['.ymrow','.pcal','.dh'].map(q=>{const e=document.querySelector(`section[data-pg=${d}] ${q}`),r=e.getBoundingClientRect();
    return [q,+r.left.toFixed(2),+r.top.toFixed(2),+r.width.toFixed(2),+r.height.toFixed(2),getComputedStyle(e).opacity]}))"""


def test_mid_swipe_the_header_holds_and_the_cards_glide(chromium, publish_url, check_url):
    """A finger held mid-swipe (30 % and 70 % of the width, no release) from day 2 towards
    day 3, with the day open, folded and with its map open:
    - today's month row, calendar and title row stay where they rest (they never move);
    - before the half only today's header shows (the target's .ymrow/.pcal/.dh at opacity
      0), past it only the target's;
    - today's map card has moved left by the finger's travel (+-2 px);
    - the moving map cards keep their side border: today's right edge and the target's
      left edge carry the check build's border ink (+-3) on the summary row;
    then the release finishes cleanly (back to day 2 from 30 %, on to day 3 from 70 %, no
    .to, no inline translate, no page error)."""
    W = ANDROID["width"]
    ctx, pg = _new(chromium, ANDROID, check_url, touch=True)
    _go(pg, "pg-d2")
    ref = _edge_ink(pg, 2)              # the check build's map card border, (left, right)
    ctx.close()
    bad = []
    for state in ("open", "folded", "map open"):
        for dx in (round(W * .3), round(W * .7)):
            errors = []
            ctx, pg = _new(chromium, ANDROID, publish_url, touch=True, errors=errors)
            t = _touch(ctx, pg)
            _go(pg, "pg-d2")
            if state == "map open":
                pg.click("section[data-pg=d2] .mapc summary")
                pg.wait_for_timeout(300)
            if state == "folded":
                _scroll(pg, "d2", _fold(pg, "d2"))
            rest = pg.evaluate(f"{HEAD}('d2')")
            left0 = _rect(pg, "section[data-pg=d2] .mapc")[0]
            x0, y0 = 300, 600
            t("touchStart", x0, y0)
            for k in range(1, dx // 12 + 1):
                t("touchMove", x0 - 12 * k, y0)
                pg.wait_for_timeout(16)
            pg.wait_for_timeout(200)
            dx = 12 * (dx // 12)
            now, tgt = pg.evaluate(f"{HEAD}('d2')"), pg.evaluate(f"{HEAD}('d3')")
            if [r[:5] for r in now] != [r[:5] for r in rest]:
                bad.append((state, dx, "header moved", rest, now))
            past = dx > W / 2
            want = ("0", "1") if past else ("1", "0")
            if [r[5] for r in now] != [want[0]] * 3 or [r[5] for r in tgt] != [want[1]] * 3:
                bad.append((state, dx, "header opacity", now, tgt))
            m = _rect(pg, "section[data-pg=d2] .mapc")
            if abs(m[0] - (left0 - dx)) > 2:
                bad.append((state, dx, "map card left", left0, m[0]))
            im = _png(pg).convert("L")
            tm = _rect(pg, "section[data-pg=d3] .mapc")
            ink = (_ink_at(im, m[2], m[1] + min(22, (m[3] - m[1]) / 2), 2), _ink_at(im, tm[0], tm[1] + min(22, (tm[3] - tm[1]) / 2), 2))
            if abs(ink[0] - ref[1]) > 3 or abs(ink[1] - ref[0]) > 3:
                bad.append((state, dx, "border ink (today right, target left)", ink, ref))
            t("touchEnd")
            pg.wait_for_timeout(800)
            end = "pg-d3" if past else "pg-d2"
            if pg.evaluate(CUR) != [end, end[3:], 0]:
                bad.append((state, dx, "release", pg.evaluate(CUR)))
            left = pg.evaluate("[...document.querySelectorAll('.track :is(.pwrap,.lcap,.pcard,.lfoot)')].map(e=>e.style.translate).join('')")
            if left or errors:
                bad.append((state, dx, "leftovers", left, errors))
            ctx.close()
    assert not bad, bad


def test_swipe_between_days_of_different_fold_heights(chromium, two_month_url):
    """A folded day hands the fold to its neighbour at the NEIGHBOUR's own height: the
    guard is that prep() reads the TARGET day's fold, not the source's.

    The shipped renderer draws the same mini calendar on every day page of a trip (day.py
    sets --wk from calendar.weeks over all the trip's dates), so on this Aug/Sep trip
    every day folds by 60 and the two readings agree. The target day is therefore given a
    two-week calendar in the page (_two_weeks: fold 98) before the swipe."""
    ctx, pg = _new(chromium, ANDROID, two_month_url, touch=True)
    t = _touch(ctx, pg)
    _go(pg, "pg-d2")
    assert pg.evaluate("[...document.querySelectorAll('.track>.page.day')].map(s=>s.dataset.pg)") == ["d1", "d2", "d3"]
    assert pg.evaluate("document.querySelector('section[data-pg=d2] .ym').textContent").endswith("8～9 月")
    _two_weeks(pg, "d3")
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
    errors = []
    ctx, pg = _new(chromium, ANDROID, one_day_url, touch=True, errors=errors)
    t = _touch(ctx, pg)
    _go(pg, "pg-d1")
    for left in (True, False):
        _angled(pg, t, 10, 250, left=left)
        assert pg.evaluate(CUR) == ["pg-d1", "d1", 0], left
        assert pg.evaluate("[...document.querySelectorAll('section[data-pg=d1] :is(.pwrap,.lcap,.pcard,.lfoot)')].map(e=>e.style.translate).join('')") == ""
    assert errors == []
    ctx.close()


def test_swipe_cost_budget(chromium, publish_url):
    """A swipe restyles only its two pages' moving parts. Chromium's own RecalcStyleDuration
    over 25 moves of 8 px after 5 warm-up moves: <= 2.5 ms per move and <= 60 ms for the
    release (glide + swap).

    Measured locally (headless Chromium, desktop CPU): 0.78-0.85 ms per move, release
    15.6-17.1 ms; the prototype v5 0.76 / 15-17. CI runners are about 2x slower, so the
    budget sits between that and the regression it guards: v4 (one inherited variable on
    the track, every day restyled each frame) measured 4.2 ms / 78 ms locally, and the
    injected equivalent (paint() setting a variable on the track) 3.87-4.47 ms per move."""
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
    assert per_move <= 2.5, (per_move, release)
    assert release <= 60, (per_move, release)
    ctx.close()


def test_sub_pages_swipe_right_to_home(chromium, publish_url):
    errors = []
    ctx, pg = _new(chromium, ANDROID, publish_url, touch=True, errors=errors)
    t = _touch(ctx, pg)
    for sub in ("lodging", "advisory", "checklist"):
        _go(pg, f"pg-{sub}")
        _drag(pg, t, 60, 500, 120, 0)          # under half: stays
        assert _cur(pg) == f"pg-{sub}"
        _drag(pg, t, 60, 500, 260, 0)          # past half: home
        assert _cur(pg) == "pg-home"
        _go(pg, f"pg-{sub}")
        _drag(pg, t, 300, 500, -260, 0)        # left does nothing on a sub-page
        assert _cur(pg) == f"pg-{sub}"
        _go(pg, "pg-home")
    assert pg.evaluate("[...document.querySelectorAll('.page.sub,.page.home')].every(p=>!p.style.translate&&!p.style.position)")
    assert errors == []
    ctx.close()


# ---- v1.2 Task 7: theme carry, today (T1), history (B1) -- every width ----

DESKTOP = {"width": 1366, "height": 768}


def _fake_today(pg, iso):
    pg.add_init_script(f"(()=>{{const T=new Date('{iso}T10:00:00').getTime(),D=Date;"
                       "window.Date=class extends D{constructor(...a){super(...(a.length?a:[T]))}static now(){return T}}})()")


def test_theme_carries_and_is_saved(browser, publish_url):
    errs = []
    pg = browser.new_page(viewport=PHONE)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(publish_url)
    pg.evaluate("localStorage.setItem('tripwork-theme','dark')")
    pg.reload()
    pg.wait_for_timeout(300)
    assert pg.evaluate("document.getElementById('theme').checked")
    pg.click(".bubble")
    pg.wait_for_timeout(100)
    assert pg.evaluate("localStorage.getItem('tripwork-theme')") == "light"
    assert not errs
    pg.close()


def test_theme_carry_survives_storage_errors(browser, publish_url):
    errs = []
    pg = browser.new_page(viewport=PHONE)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new DOMException('denied','SecurityError')}})")
    pg.goto(publish_url)
    pg.wait_for_timeout(300)
    pg.click(".bubble")
    assert not errs and pg.evaluate("document.getElementById('theme').checked")
    pg.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP])
def test_opens_today_during_the_trip(browser, publish_url, viewport):
    from tests import reader_fixture as R
    errs = []
    d2 = R.itinerary()["days"][1]["date"]
    pg = browser.new_page(viewport=viewport)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    _fake_today(pg, d2)
    pg.goto(publish_url)
    pg.wait_for_timeout(500)
    assert _cur(pg) == "pg-d2" and not errs
    pg.close()


def test_a_link_target_beats_today(browser, publish_url):
    from tests import reader_fixture as R
    pg = browser.new_page(viewport=PHONE)
    _fake_today(pg, R.itinerary()["days"][1]["date"])
    pg.goto(publish_url + "#x")
    pg.wait_for_timeout(500)
    assert _cur(pg) == "pg-home"
    pg.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP])
def test_opens_home_outside_the_trip(browser, publish_url, viewport):
    errs = []
    pg = browser.new_page(viewport=viewport)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    _fake_today(pg, "2020-01-01")
    pg.goto(publish_url)
    pg.wait_for_timeout(500)
    assert _cur(pg) == "pg-home" and not errs
    pg.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP])
def test_back_always_returns_to_the_overview(browser, publish_url, viewport):
    errs = []
    pg = browser.new_page(viewport=viewport)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(publish_url)
    pg.wait_for_timeout(300)
    _go(pg, "pg-d1"); _go(pg, "pg-d2"); _go(pg, "pg-d3")
    pg.go_back()
    pg.wait_for_timeout(400)
    assert _cur(pg) == "pg-home"
    _go(pg, "pg-lodging")
    pg.go_back()
    pg.wait_for_timeout(400)
    assert _cur(pg) == "pg-home" and not errs
    pg.close()


def test_back_after_a_swipe_still_lands_on_the_overview(browser, chromium, publish_url):
    errs = []
    ctx, pg = _new(chromium, PHONE, publish_url, touch=True, errors=errs)
    pg.wait_for_timeout(300)
    t = _touch(ctx, pg)
    _go(pg, "pg-d2")
    _angled(pg, t, 0, 260, left=True)
    assert _cur(pg) == "pg-d3"
    pg.go_back()
    pg.wait_for_timeout(400)
    assert _cur(pg) == "pg-home" and not errs
    ctx.close()


# ---- Task 7 fix round 1: anchors do not stack history, T1 has an overview beneath, no accumulation ----

def _click(pg, sel, nth=0):
    pg.evaluate(f"document.querySelectorAll({sel!r})[{nth}].click()")
    pg.wait_for_timeout(250)


@pytest.fixture(scope="session")
def addr_url(tmp_path_factory):
    """The publish page of the same trip with one stop that has a local address, so it
    carries a 給司機看 button and its sheet (the shared fixture has none)."""
    import copy
    from scripts.render.reader import render_reader
    from tests import reader_fixture as R
    pm = copy.deepcopy(R.poi_map())
    pm["hak-asaichi"].update(address_local="函館市若松町9-19", address_source="https://example.invalid/")
    f = tmp_path_factory.mktemp("addr") / "publish.html"
    f.write_text(render_reader(R.itinerary(), pm, build="publish", **R.reader_kwargs()), encoding="utf-8")
    return f.as_uri()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP])
def test_back_skips_in_page_anchors(browser, addr_url, viewport):
    publish_url = addr_url
    errs = []
    pg = browser.new_page(viewport=viewport)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(publish_url)
    pg.wait_for_timeout(300)
    _go(pg, "pg-d2")
    n0 = pg.evaluate("history.length")
    d = "section[data-pg=d2] "
    _click(pg, d + "a.hd-open", 0)                    # open a stop
    _click(pg, d + "a.hd-open", 1)                    # open another
    _click(pg, d + "a.hd-close", 1)                   # collapse it (-x)
    _click(pg, d + "a.drvbtn", 0)                     # 給司機看 opens
    assert pg.evaluate("document.querySelector(':target') && document.querySelector(':target').classList.contains('drv')")
    _click(pg, d + "a.drvx", 0)                       # ✕ closes it again
    assert not pg.evaluate("!!document.querySelector('.drv:target')")
    assert pg.evaluate("history.length") == n0
    pg.go_back()
    pg.wait_for_timeout(400)
    assert _cur(pg) == "pg-home" and not errs
    pg.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP])
def test_today_has_the_overview_beneath(browser, chromium, publish_url, viewport):
    """Per-engine: both engines pass after one click on the page (user activation).
    See the report for whether Chromium also passes without it."""
    from tests import reader_fixture as R
    errs = []
    pg = browser.new_page(viewport=viewport)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    _fake_today(pg, R.itinerary()["days"][1]["date"])
    pg.goto(publish_url)
    pg.wait_for_timeout(500)
    assert _cur(pg) == "pg-d2"
    pg.mouse.click(5, 5)
    pg.go_back()
    pg.wait_for_timeout(400)
    assert _cur(pg) == "pg-home" and not errs
    pg.close()


def test_today_back_without_a_click(browser, publish_url):
    """Back from a T1-opened page with NO user activation also lands on the overview
    (measured: Chromium's skip-without-activation intervention does not bite here)."""
    from tests import reader_fixture as R
    pg = browser.new_page(viewport=PHONE)
    _fake_today(pg, R.itinerary()["days"][1]["date"])
    pg.goto(publish_url)
    pg.wait_for_timeout(500)
    pg.go_back()
    pg.wait_for_timeout(400)
    assert _cur(pg) == "pg-home"
    pg.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP])
def test_round_trips_do_not_grow_the_history(browser, publish_url, viewport):
    errs = []
    pg = browser.new_page(viewport=viewport)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(publish_url)
    pg.wait_for_timeout(300)
    n0 = pg.evaluate("history.length")
    for _ in range(3):
        _go(pg, "pg-d2")
        _go(pg, "pg-home")
        pg.wait_for_timeout(300)
    assert pg.evaluate("history.length") <= n0 + 1 and _cur(pg) == "pg-home"
    assert pg.evaluate("history.state.pg") == "home" and not errs
    pg.close()


# ---------------------------------------------------------------- Z1: pull down to close a zoom

def _open_zoom(pg, kind):
    """Day 2 has both a map with tiles and a photo; open the zoom and return its checkbox selector."""
    _go(pg, "pg-d2")
    if kind == "map":
        pg.click("section[data-pg=d2] .mapc summary")
        pg.wait_for_timeout(300)
        box = "section[data-pg=d2] .zck"
    else:
        sid = pg.evaluate("document.querySelector('section[data-pg=d2] .pz').closest('.stop').id")
        pg.evaluate(f"location.hash='#{sid}'")
        pg.wait_for_timeout(500)
        box = "section[data-pg=d2] .pz"
    pg.evaluate(f"document.querySelector('{box}').click()")
    pg.wait_for_timeout(400)
    return box


@pytest.mark.parametrize("kind", ["map", "photo"])
def test_pull_down_closes_the_zoom(chromium, publish_url, kind):
    errs = []
    ctx, pg = _new(chromium, ANDROID, publish_url, touch=True, errors=errs)
    t = _touch(ctx, pg)
    box = _open_zoom(pg, kind)
    day = _cur(pg)
    top = pg.evaluate(f"{_vs('d2')}.scrollTop")
    _drag(pg, t, 180, 300, 0, 150)               # under half of 780: stays open
    assert pg.evaluate(f"document.querySelector('{box}').checked")
    assert _cur(pg) == day and pg.evaluate(f"{_vs('d2')}.scrollTop") == top   # the list underneath did not scroll
    _drag(pg, t, 180, 300, 0, 420)               # past half: closes
    assert not pg.evaluate(f"document.querySelector('{box}').checked")
    assert pg.evaluate("[...document.querySelectorAll('.mv,.bp,.zbg')].every(e=>!e.style.translate&&!e.style.opacity)")
    assert _cur(pg) == day
    assert not errs
    ctx.close()


def test_pull_down_flick_closes_and_sideways_or_link_does_not(chromium, publish_url):
    errs = []
    ctx, pg = _new(chromium, ANDROID, publish_url, touch=True, errors=errs)
    t = _touch(ctx, pg)
    box = _open_zoom(pg, "map")
    day = _cur(pg)
    _drag(pg, t, 180, 300, 200, 40)              # sideways: not a pull, and not a day swipe
    assert pg.evaluate(f"document.querySelector('{box}').checked") and _cur(pg) == day
    _drag(pg, t, 180, 300, 0, -150)              # upwards: not a pull
    assert pg.evaluate(f"document.querySelector('{box}').checked")
    link = pg.evaluate("(a=>{if(!a)return null;const r=a.getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]})"
                       "(document.querySelector('section[data-pg=d2] .mv:has(.zck:checked) .zbar a'))")
    if link:                                      # a touch that starts on the live-map link never pulls
        _drag(pg, t, link[0], link[1], 0, 500)
        assert pg.evaluate(f"document.querySelector('{box}').checked")
    _drag(pg, t, 180, 300, 0, 120, steps=3, ms=0)  # short flick: closes
    assert not pg.evaluate(f"document.querySelector('{box}').checked")
    assert not errs
    ctx.close()
