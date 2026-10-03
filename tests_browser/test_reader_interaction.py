"""spec §7 interaction checks, measured in headless Chromium on the release tour:
the anchor linkage table (§6.8, v1.1 §8.1), close controls inside the screen, no page widened
past the phone, the desktop dashboard not scrolling, the centring script (§6.9)
landing each stop in the middle without rebound, and the phone without script
showing none of the desktop blocks. Geometry comes from the DOM, never from
screenshots, so fonts and CI machines do not move the thresholds."""
import pytest

from conftest import DESKTOP, PHONE

DAYS = ("d1", "d2", "d3", "d4")


def _goto_day(pg, d, desktop):
    sel = f'.hcal label.stamp[for="pg-{d}"]' if desktop else f'.home .months label.stamp[for="pg-{d}"]'
    pg.click(sel)
    # the desktop forces the map card open only where ::details-content exists (spec v1.1
    # §3.1); elsewhere (Playwright WebKit today) it stays a working toggle -- open it
    forced_or_open = pg.evaluate(f"""(()=>{{const m=document.querySelector('section[data-pg="{d}"] details.mapc');
        return m.open||getComputedStyle(m.querySelector('summary')).pointerEvents==='none'}})()""")
    if not forced_or_open:
        pg.click(f'section[data-pg="{d}"] details.mapc > summary')


def _settle(pg, sel, still=6, step=50, limit=5000):
    """Wait until sel's scrollTop holds still (the anchor jump glides with
    scroll-behavior:smooth; a person taps again once it stops). Polled from Python:
    with JavaScript off the page runs no requestAnimationFrame of ours."""
    last, same, waited = None, 0, 0
    while waited < limit:
        now = pg.evaluate(f"document.querySelector('{sel}').scrollTop")
        same = same + 1 if now == last else 0
        if same >= still:
            return
        last = now
        pg.wait_for_timeout(step); waited += step
    raise AssertionError(f"{sel} kept scrolling for {limit} ms")


def _lit(pg, d):
    return pg.eval_on_selector_all(f'section[data-pg="{d}"] .mapc .chips a.chip',
                                   "ls => ls.filter(l => !['rgba(0, 0, 0, 0)', 'transparent']"
                                   ".includes(getComputedStyle(l).backgroundColor)).map(l => l.getAttribute('href'))")


def _shown(pg, sel):
    return pg.evaluate(f"""(()=>{{const e=document.querySelector('{sel}');if(!e)return false;
        const r=e.getBoundingClientRect();return getComputedStyle(e).display!=='none'&&r.width>0&&r.height>0}})()""")


@pytest.mark.parametrize("desktop", [True, False], ids=["desktop", "phone"])
@pytest.mark.parametrize("d", DAYS)
def test_every_chip_jumps_shows_its_view_and_opens_its_stop(open_page, d, desktop):
    """v1.1 §8.1: chips are anchors. JS off on the phone -- exactly what Quick Look runs."""
    pg = open_page(DESKTOP if desktop else PHONE, js=desktop)
    _goto_day(pg, d, desktop)
    chips = pg.eval_on_selector_all(f'section[data-pg="{d}"] .mapc .chips a.chip',
                                    "cs => cs.map(c => [c.getAttribute('href'), c.className])")
    assert chips
    for href, cls in chips[1:] + chips[:1]:
        # force: Playwright calls anything inside a closed <details> invisible, even where the
        # desktop's ::details-content rule shows it; the click still lands at the chip's centre
        pg.click(f'section[data-pg="{d}"] .mapc .chips a.chip[href="{href}"]', force=True)
        _settle(pg, f'section[data-pg="{d}"] .plist')
        key = [c for c in cls.split() if c.startswith(f"c-{d}-")][0][len(f"c-{d}-"):]
        views = pg.eval_on_selector_all(f'section[data-pg="{d}"] .mv', "vs => vs.filter(v => getComputedStyle(v).display !== 'none').map(v => v.classList[1])")
        assert views == [f"mv-{d}-{key}"], (href, views)
        lit = _lit(pg, d)
        assert lit == [href], (href, lit)                                 # that chip, and only it
        if pg.evaluate(f"!!document.querySelector('{href}').closest('.stop')"):
            assert _shown(pg, f'section[data-pg="{d}"] {href} .in'), href


@pytest.mark.parametrize("d", DAYS)
def test_picking_a_stop_in_the_list_lights_its_chip(open_page, d):
    pg = open_page(DESKTOP)
    _goto_day(pg, d, True)
    tids = pg.eval_on_selector_all(f'section[data-pg="{d}"] .plist .stop', "s => s.map(e => e.id)")
    for tid in tids:
        pg.click(f'section[data-pg="{d}"] #{tid} a.hd-open')
        assert _shown(pg, f'section[data-pg="{d}"] #{tid} .in')
        if pg.query_selector(f'section[data-pg="{d}"] .chips a.chip[href="#{tid}"]'):
            assert _lit(pg, d) == [f"#{tid}"], tid


def _inside(pg, sel, vp):
    r = pg.evaluate(f"(()=>{{const r=document.querySelector('{sel}').getBoundingClientRect();return [r.left,r.top,r.right,r.bottom]}})()")
    return r[0] >= 0 and r[1] >= 0 and r[2] <= vp["width"] and r[3] <= vp["height"]


@pytest.mark.parametrize("sub", ["lodging", "advisory", "checklist"])
def test_the_overlay_close_control_is_on_screen_and_both_ways_close(open_page, sub):
    pg = open_page(DESKTOP)
    pg.click(f'.hside label.tile[for="pg-{sub}"]')
    assert _shown(pg, f'section[data-pg="{sub}"] .ovbox') and _shown(pg, ".page.home")
    assert _inside(pg, f'section[data-pg="{sub}"] label.ovx', DESKTOP)
    pg.click(f'section[data-pg="{sub}"] label.ovx')
    assert not _shown(pg, f'section[data-pg="{sub}"]')
    pg.click(f'.hside label.tile[for="pg-{sub}"]')
    pg.mouse.click(10, DESKTOP["height"] - 10)            # the dimmed background
    assert not _shown(pg, f'section[data-pg="{sub}"]')


@pytest.mark.parametrize("vp", [PHONE, {"width": 844, "height": 390}], ids=["portrait", "landscape"])
def test_a_fullscreen_map_fits_the_screen_and_closes_on_tap(open_page, vp):
    pg = open_page(vp, js=False)
    _goto_day(pg, "d2", False)
    pg.click('section[data-pg="d2"] .mv-d2-all .seg >> nth=0 >> label.mframe')
    frame = 'section[data-pg="d2"] .mv-d2-all .seg .mframe'
    assert pg.evaluate("getComputedStyle(document.querySelector('.mv-d2-all')).position") == "fixed"
    assert _inside(pg, frame, vp)
    pg.click('section[data-pg="d2"] .mv-d2-all .seg >> nth=0 >> label.mframe')
    assert pg.evaluate("getComputedStyle(document.querySelector('.mv-d2-all')).position") != "fixed"


_WIDTH = """(()=>{const p=[...document.querySelectorAll('.page')].find(e=>getComputedStyle(e).display!=='none'),
  L=p.querySelector('.plist,.pb')||p;return Math.max(document.body.scrollWidth,p.scrollWidth,L.scrollWidth-L.clientWidth+%d)})()"""


# .c3 clips (overflow:hidden), so an over-wide stop is cut off rather than widening the
# page: also take the right edge of everything in the opened stop (bar sideways scrollers)
_SPILL = """(id)=>{const s=document.getElementById(id),L=s.closest('.plist'),lim=L.getBoundingClientRect().right;
  let r=0;for(const e of s.querySelectorAll('*')){const b=e.getBoundingClientRect();if(!b.width||!b.height)continue;
  if(e.parentElement.closest('.plist [style*="overflow"],.plist .chips'))continue;r=Math.max(r,b.right)}
  return Math.round(r>lim?r-lim+innerWidth:0)}"""


def test_no_page_is_wider_than_the_phone(open_page):
    """The locked <html> reports the viewport as its own width (review I1), so measure the
    body, the visible page and its scrolling card, with every stop and 來源 opened in
    turn (review I-2: the radio-era loop matched nothing and opened no stop)."""
    pg = open_page(PHONE, js=False)
    w = _WIDTH % PHONE["width"]
    widths = {"home": pg.evaluate(w)}
    for sub in ("lodging", "advisory", "checklist"):
        pg.click(f'.home label.tile[for="pg-{sub}"]')
        for s in pg.query_selector_all(f'section[data-pg="{sub}"] details > summary'):
            s.click()
        widths[sub] = pg.evaluate(w)
        pg.click(f'section[data-pg="{sub}"] label.back')
    opened = 0
    for d in DAYS:
        _goto_day(pg, d, False)
        for sid in pg.eval_on_selector_all(f'section[data-pg="{d}"] .plist .stop', "s => s.map(e => e.id)"):
            for tid in (sid, f"{sid}-src"):
                if pg.query_selector(f"#{tid}"):
                    pg.evaluate(f"location.hash='#{tid}'")
                    widths[f"{d}/{tid}"] = max(pg.evaluate(w), pg.evaluate(_SPILL, sid))
                    opened += 1
        pg.click(f"section[data-pg={d}] .ymrow .back")
    assert opened >= 10
    assert {k: v for k, v in widths.items() if v > PHONE["width"]} == {}


@pytest.mark.parametrize("vp", [DESKTOP, {"width": 1366, "height": 600}, {"width": 1024, "height": 600}],
                         ids=["1366x768", "1366x600", "1024x600"])
def test_the_dashboard_never_scrolls_the_page(open_page, vp):
    pg = open_page(vp)
    for d in DAYS:
        pg.click('label.back >> visible=true') if d != "d1" else None
        _goto_day(pg, d, True)
        assert pg.evaluate("document.body.scrollHeight") <= vp["height"], d
        for tid in pg.eval_on_selector_all(f'section[data-pg="{d}"] .plist .stop', "s => s.map(e => e.id)"):
            pg.click(f'section[data-pg="{d}"] #{tid} a.hd-open')
        pg.wait_for_timeout(600)
        assert pg.evaluate("document.documentElement.scrollTop + document.body.scrollTop") == 0, d
        assert pg.evaluate(f"""(()=>{{const f=[...document.querySelectorAll('section[data-pg="{d}"] .pmap .mframe')]
            .find(x=>x.getBoundingClientRect().height>0);return !f||f.getBoundingClientRect().height>=100}})()"""), d


def test_the_chosen_stop_is_centred_without_rebound(open_page, hakodate_url):
    """Desktop with script: the anchor jump, then the script glides the stop to centre."""
    pg = open_page(DESKTOP, url=hakodate_url)
    _goto_day(pg, "d2", True)
    tids = pg.eval_on_selector_all('section[data-pg="d2"] .plist .stop', "s => s.map(e => e.id)")
    order = []
    for tid in tids + tids[::-1] + tids[::2]:
        if not order or order[-1] != tid:
            order.append(tid)
    measured = 0
    for n, tid in enumerate(order):
        chip = pg.query_selector(f'section[data-pg="d2"] .chips a.chip[href="#{tid}"]')
        (chip if n % 3 == 2 and chip else pg.query_selector(f'section[data-pg="d2"] #{tid} a.hd-open')).click(force=True)
        _settle(pg, 'section[data-pg="d2"] .plist')
        m = pg.evaluate(f"""(()=>{{const L=document.querySelector('section[data-pg="d2"] .plist'),
            s=document.getElementById('{tid}'),lr=L.getBoundingClientRect(),sr=s.getBoundingClientRect();
            return {{err:(sr.top+sr.height/2)-(lr.top+lr.height/2),top:L.scrollTop,max:L.scrollHeight-L.clientHeight,
                     tall:sr.height>lr.height,head:s.querySelector('.hd-close').getBoundingClientRect().top-lr.top}}}})()""")
        pg.wait_for_timeout(400)
        after = pg.evaluate("document.querySelector('section[data-pg=\\\"d2\\\"] .plist').scrollTop")
        assert abs(after - m["top"]) <= 1, (tid, "rebound", m, after)
        assert m["head"] >= -1, (tid, "title pushed above the list", m)
        bounded = m["top"] <= 0 or m["top"] >= m["max"] - 1 or m["tall"]
        assert bounded or abs(m["err"]) <= 2, (tid, m)
        measured += not bounded
    assert measured >= 3, "the list barely scrolls: centring was not measured"


def test_an_open_alternative_of_the_chosen_stop_stays_open(open_page):
    pg = open_page(DESKTOP)
    _goto_day(pg, "d2", True)
    alt = pg.query_selector('section[data-pg="d2"] details.altrow')
    if alt is None:
        pytest.fail("the tour's D2 carries no alternative; the fixture changed")
    tid = alt.get_attribute("data-stop")
    alt.query_selector("summary").click()
    pg.click(f'section[data-pg="d2"] #{tid} a.hd-open')
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.querySelector('section[data-pg=\\\"d2\\\"] details.altrow').open")


def test_the_phone_without_script_shows_no_desktop_block(open_page):
    pg = open_page(PHONE, js=False)
    for sel in (".hcal .ring", ".ovbg", ".ovx"):
        shown = pg.eval_on_selector_all(sel, "es => es.filter(e => getComputedStyle(e).display !== 'none').length")
        assert pg.query_selector(sel) and shown == 0, sel
    _goto_day(pg, "d2", False)
    tops = pg.evaluate("""(()=>{const d=document.querySelector('section[data-pg="d2"]');
        return ['.ymrow','.mini','.dh','.mapc','.plist'].map(s=>d.querySelector(s).getBoundingClientRect().top)})()""")
    assert tops == sorted(tops)


@pytest.mark.parametrize("js", [False, True])
def test_opening_a_stops_sources_keeps_its_map_view(open_page, js):
    """Review I-1 (v1.1 anchors): 來源 is a target inside its stop, so the stop's view and
    chip must stay up while it is open (a :has() nested in :has() is dropped by CSS,
    which blanked the map)."""
    pg = open_page(PHONE, js=js)
    checked = 0
    for d in DAYS:
        _goto_day(pg, d, False)
        for sid in pg.eval_on_selector_all(f'section[data-pg="{d}"] .plist .stop', "s => s.map(e => e.id)"):
            src = pg.query_selector(f"#{sid}-src")
            if not src:
                continue
            pg.evaluate(f"location.hash='#{sid}'")
            _settle(pg, f'section[data-pg="{d}"] .plist')
            views, lit = _views(pg, d), _lit(pg, d)
            pg.evaluate(f"location.hash='#{sid}-src'")
            _settle(pg, f'section[data-pg="{d}"] .plist')
            assert _views(pg, d) == views and len(views) == 1, (sid, views, _views(pg, d))
            assert _lit(pg, d) == lit, (sid, lit, _lit(pg, d))
            checked += 1
        pg.click(f"section[data-pg={d}] .ymrow .back")
    assert checked >= 3


def _views(pg, d):
    return pg.eval_on_selector_all(f'section[data-pg="{d}"] .mapc .mv',
                                   "vs => vs.filter(v => getComputedStyle(v).display !== 'none')"
                                   ".map(v => [...v.classList].find(c => c.startsWith('mv-d')))")
