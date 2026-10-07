"""v2.2 the photo layer (PUBLISH_JS, picks B + O2): a photo grows out of its thumbnail into the
page's own layer and goes back into it. The figure keeps its place, so nothing underneath moves
-- before, the checkbox turned the figure itself full screen, its card lost the photo's height,
and the base jumped back when the photo returned (a consumer trip, on the phone). A tap on the
photo, ✕, the dark layer, Esc, or a downward drag all close it the same way."""
import pytest
from conftest import DESKTOP, PHONE

FIG = "section[data-pg=d2] figure.bp"
BASE = f"""(()=>{{const f=document.querySelector('{FIG}'),st=f.closest('.stop'),nx=st.nextElementSibling,pl=st.closest('.plist'),
  r=e=>{{const b=e.getBoundingClientRect();return [b.x,b.y,b.width,b.height].map(v=>Math.round(v*10)/10)}};
  return {{thumb:r(f.querySelector('.bpz')),next:r(nx),stop:r(st),scroll:pl?pl.scrollTop:scrollY}}}})()"""
LAYER = "document.querySelectorAll('.pzx').length"
SEEK = "(t=>{const r=document.querySelector('.pzx');r.getAnimations({subtree:true}).forEach(a=>{a.pause();a.currentTime=t})})"
# the flying photo's drawn top / bottom: its cover-crop box through its transform, cut by the window
DRAWN = """(()=>{const r=document.querySelector('.pzx'),win=r.querySelector('.pzw'),h=win.firstChild,c=getComputedStyle(h),m=new DOMMatrix(c.transform);
  const q=s=>{if(s==='none')return [0,0,0,0];const n=s.match(/-?[\\d.]+/g).map(Number);return [n[0],n[1]??n[0],n[2]??n[0],n[3]??n[1]??n[0]]};
  const n=q(c.clipPath),w=q(getComputedStyle(win).clipPath);
  return [Math.max(m.f+n[0]*m.d,w[0]),Math.min(m.f+(parseFloat(h.style.height)-n[2])*m.d,innerHeight-w[2])]})()"""


def _go(pg, pid):
    pg.evaluate(f"(r=>{{r.checked=true;r.dispatchEvent(new Event('change',{{bubbles:true}}))}})(document.getElementById('{pid}'))")
    pg.wait_for_timeout(500)


def _day2_photo(pg, list_scroll=None):
    _go(pg, "pg-d2")
    sid = pg.evaluate(f"document.querySelector('{FIG}').closest('.stop').id")
    pg.evaluate(f"location.hash='#{sid}'")
    pg.wait_for_timeout(600)
    if list_scroll is not None:
        pg.evaluate(f"(L=>{{L.style.scrollBehavior='auto';L.scrollTop+={list_scroll}}})(document.querySelector('section[data-pg=d2] .plist'))")
        pg.wait_for_timeout(500)


def _in_full_view(pg):
    """Scroll the list so the whole thumbnail shows, below the map row and the list's cap."""
    pg.evaluate(f"""(()=>{{const L=document.querySelector('section[data-pg=d2] .plist'),b=document.querySelector('{FIG} .bpz').getBoundingClientRect(),
      cap=document.querySelector('section[data-pg=d2] .pmap').getBoundingClientRect().bottom;L.style.scrollBehavior='auto';L.scrollTop+=b.top-(cap+40)}})()""")
    pg.wait_for_timeout(500)


def _tap_photo(pg, top=0):
    """Where a finger would: the middle of the thumbnail's part below `top` (what covers it)."""
    b = pg.evaluate(f"(b=>[b.x+b.width/2,(Math.max(b.top,{top})+Math.min(b.bottom,innerHeight))/2])(document.querySelector('{FIG} .bpz').getBoundingClientRect())")
    pg.mouse.click(*b)
    pg.wait_for_selector(".pzx", state="attached")             # made once the photo has decoded


@pytest.fixture
def page(browser, publish_url):
    made = []

    def make(viewport=PHONE, **kw):
        ctx = browser.new_context(viewport=viewport, **kw)
        pg = ctx.new_page()
        pg.errs = []
        pg.on("pageerror", lambda e: pg.errs.append(str(e)))
        pg.goto(publish_url)
        made.append(ctx)
        return pg
    yield make
    for c in made:
        c.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["phone", "desktop"])
def test_nothing_underneath_moves(page, viewport):
    pg = page(viewport)
    _day2_photo(pg)
    before = pg.evaluate(BASE)
    _tap_photo(pg)
    pg.wait_for_timeout(500)
    assert pg.evaluate(LAYER) == 1
    assert pg.evaluate(BASE) == before                         # open: the card keeps the photo's place
    cover = pg.evaluate("(b=>[b.x,b.y,b.width,b.height])(document.querySelector('.pzx').getBoundingClientRect())")
    assert cover == [0, 0, viewport["width"], viewport["height"]]
    pg.mouse.click(viewport["width"] // 2, viewport["height"] // 2)
    pg.wait_for_timeout(700)
    assert pg.evaluate(LAYER) == 0 and pg.evaluate(BASE) == before
    assert pg.evaluate(f"getComputedStyle(document.querySelector('{FIG}')).visibility") == "visible"
    assert not pg.errs


@pytest.mark.parametrize("how", ["photo", "x", "dark", "esc"])
def test_every_way_out_goes_back_into_the_thumbnail(page, how):
    pg = page()
    _day2_photo(pg)
    _tap_photo(pg)
    pg.wait_for_timeout(500)
    if how == "photo":
        pg.mouse.click(PHONE["width"] // 2, PHONE["height"] // 2)
    elif how == "x":
        pg.click(".pzx .zx")
    elif how == "dark":
        pg.mouse.click(4, 4)
    else:
        pg.keyboard.press("Escape")
    pg.wait_for_timeout(150)                                   # mid-way: still flying, not gone
    assert pg.evaluate(LAYER) == 1
    pg.wait_for_timeout(600)
    assert pg.evaluate(LAYER) == 0 and not pg.errs


def test_the_photo_lands_on_its_thumbnail(page):
    """The last frame of the way back is the thumbnail: same place, same crop."""
    pg = page()
    _day2_photo(pg)
    _in_full_view(pg)
    _tap_photo(pg)
    pg.wait_for_timeout(500)
    thumb = pg.evaluate(f"(b=>[b.top,b.bottom])(document.querySelector('{FIG} .bpz').getBoundingClientRect())")
    pg.keyboard.press("Escape")
    pg.evaluate(SEEK + "(339.9)")
    top, bot = pg.evaluate(DRAWN)
    assert top == pytest.approx(thumb[0], abs=1) and bot == pytest.approx(thumb[1], abs=1)


def test_a_thumbnail_half_under_the_cap_flies_under_it(page):
    """The photo is cropped to the part of its thumbnail that shows -- the reported case: half
    under the list's top cap, it flew back over the cap and was cut at the last frame."""
    pg = page()
    _day2_photo(pg, list_scroll=0)
    thumb = pg.evaluate(f"(b=>[b.top,b.bottom])(document.querySelector('{FIG} .bpz').getBoundingClientRect())")
    cap = pg.evaluate("document.querySelector('section[data-pg=d2] .pmap').getBoundingClientRect().bottom")
    pg.evaluate(f"(L=>{{L.style.scrollBehavior='auto';L.scrollTop+={thumb[0] - cap + (thumb[1] - thumb[0]) / 2}}})(document.querySelector('section[data-pg=d2] .plist'))")
    pg.wait_for_timeout(500)
    thumb = pg.evaluate(f"(b=>[b.top,b.bottom])(document.querySelector('{FIG} .bpz').getBoundingClientRect())")
    assert thumb[0] < cap < thumb[1]                           # the set-up: half under the cap
    _tap_photo(pg, top=cap + 20)
    pg.evaluate(SEEK + "(0)")
    top, _ = pg.evaluate(DRAWN)
    assert top >= cap - 1                                      # it grows from the shown part only
    # let the opening play out (not seeked to its very end: WebKit then never says it finished)
    pg.evaluate(SEEK + "(290)")
    pg.evaluate("document.querySelector('.pzx').getAnimations({subtree:true}).forEach(a=>a.play())")
    pg.wait_for_timeout(400)
    pg.keyboard.press("Escape")
    assert pg.evaluate("document.querySelector('.pzx .pzi').getAnimations().length") == 1     # it is on its way back
    for t in range(160, 341, 20):                              # from 45 % of the way back: never over the cap
        pg.evaluate(SEEK + f"({t})")
        assert pg.evaluate(DRAWN)[0] >= cap - 1, t
    assert pg.evaluate(DRAWN)[1] == pytest.approx(thumb[1], abs=1)                       # and it lands on the thumbnail


def test_it_plays_with_reduced_motion_on(page):
    """The user's pick M1: their phone has reduced motion on, and the photo still flies --
    it is short and only answers their own tap or drag."""
    pg = page(reduced_motion="reduce")
    assert pg.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
    _day2_photo(pg)
    _tap_photo(pg)
    # the four parts of the opening (photo, window, dark layer, bar), each 300 ms -- counted, so a
    # zero-length opening (finished and gone at once) cannot pass as "all 300"
    assert pg.evaluate("document.querySelector('.pzx').getAnimations({subtree:true}).map(a=>a.effect.getTiming().duration)") == [300] * 4
    pg.wait_for_timeout(500)
    pg.keyboard.press("Escape")
    assert pg.evaluate("document.querySelector('.pzx .pzi').getAnimations().map(a=>a.effect.getTiming().duration)") == [340]
    pg.wait_for_timeout(150)
    assert pg.evaluate(LAYER) == 1                             # still on its way back
    pg.wait_for_timeout(600)
    assert pg.evaluate(LAYER) == 0


def test_the_source_link_leaves_the_photo_open(page):
    pg = page()
    pg.context.route("https://commons.example/**", lambda r: r.fulfill(status=204))
    _day2_photo(pg)
    _tap_photo(pg)
    pg.wait_for_timeout(500)
    assert pg.evaluate("!!document.querySelector('.pzx .zc a[href^=\"https://\"]')")
    pg.evaluate("document.querySelector('.pzx .zc a').addEventListener('click',e=>e.preventDefault())")
    pg.click(".pzx .zc a")
    pg.wait_for_timeout(500)
    assert pg.evaluate(LAYER) == 1


def test_no_script_keeps_the_checkbox(browser, publish_url):
    """The no-script viewers (the iPhone Claude app's preview) keep the full-screen checkbox."""
    pg = browser.new_page(viewport=PHONE, java_script_enabled=False)
    pg.goto(publish_url)
    pg.evaluate("document.getElementById('pg-d2').checked=true")
    sid = pg.evaluate(f"document.querySelector('{FIG}').closest('.stop').id")
    pg.evaluate(f"location.hash='#{sid}'")
    pg.wait_for_timeout(600)
    pg.locator(f"{FIG} label.bpz").click()
    pg.wait_for_timeout(300)
    assert pg.evaluate(f"document.querySelector('{FIG} .pz').checked") and pg.evaluate(LAYER) == 0
    pg.close()


# ---- the drag (touch, Chromium + CDP: WebKit has no touch input to drive)

@pytest.fixture(scope="module")
def touch(pw, publish_url):
    b = pw.chromium.launch()
    made = []

    def make():
        ctx = b.new_context(viewport={"width": 360, "height": 780}, has_touch=True, is_mobile=True)
        pg = ctx.new_page()
        pg.errs = []
        pg.on("pageerror", lambda e: pg.errs.append(str(e)))
        pg.goto(publish_url)
        cdp = ctx.new_cdp_session(pg)
        made.append(ctx)

        def drag(x0, y0, dy, ms, steps=15, dx=0):
            send = lambda kind, x=0, y=0: cdp.send("Input.dispatchTouchEvent", {
                "type": kind, "touchPoints": [] if kind == "touchEnd" else [{"x": x, "y": y}]})
            send("touchStart", x0, y0)
            for i in range(1, steps + 1):
                send("touchMove", x0 + dx * i / steps, y0 + dy * i / steps)
                pg.wait_for_timeout(ms / steps)
            send("touchEnd")
        pg.drag = drag
        pg.tap = lambda x, y: (cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]}),
                               cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}))
        return pg
    yield make
    for c in made:
        c.close()
    b.close()


def _cur(pg):
    return pg.evaluate("document.querySelector('input[name=pg]:checked').id")


def test_a_short_slow_drag_springs_back_a_longer_one_closes(touch):
    pg = touch()
    _day2_photo(pg)
    before = pg.evaluate(BASE)
    b = pg.evaluate(f"(b=>[b.x+b.width/2,b.y+b.height/2])(document.querySelector('{FIG} .bpz').getBoundingClientRect())")
    pg.tap(*b)
    pg.wait_for_timeout(500)
    assert pg.evaluate(LAYER) == 1
    pg.drag(180, 300, 60, 900)                     # 60 px, slow: back to full screen
    pg.wait_for_timeout(500)
    assert pg.evaluate(LAYER) == 1
    assert pg.evaluate("getComputedStyle(document.querySelector('.pzx .pzb')).opacity") == "1"
    pg.drag(180, 300, 220, 400)                    # moving down when let go: back into the thumbnail
    pg.wait_for_timeout(800)
    assert pg.evaluate(LAYER) == 0
    assert pg.evaluate(BASE) == before and _cur(pg) == "pg-d2" and not pg.errs


def test_a_sideways_drag_neither_closes_nor_turns_the_day(touch):
    """A fast drag across the open photo is not the day swipe underneath, and not a close."""
    pg = touch()
    _day2_photo(pg)
    b = pg.evaluate(f"(b=>[b.x+b.width/2,b.y+b.height/2])(document.querySelector('{FIG} .bpz').getBoundingClientRect())")
    pg.tap(*b)
    pg.wait_for_timeout(500)
    pg.drag(300, 400, 10, 250, dx=-240)            # a leftward flick: what turns the day when no photo is open
    pg.wait_for_timeout(700)
    assert pg.evaluate(LAYER) == 1 and _cur(pg) == "pg-d2" and not pg.errs
