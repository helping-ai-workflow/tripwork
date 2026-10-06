"""spec v1.1 — the phone reader holds still: measured in headless Chromium at 390 x 844
(and 360 x 640), with and without JavaScript."""
import pytest
from conftest import DESKTOP, PHONE

SMALL = {"width": 360, "height": 640}


def _fits(pg, vp):
    """Nothing hangs past the screen: a locked <html> always reports its own scrollHeight
    as the viewport (review I1), so measure the body and the visible page instead."""
    return pg.evaluate(f"""(()=>{{const p=[...document.querySelectorAll('.page')].find(e=>getComputedStyle(e).display!=='none');
      return document.body.scrollHeight<={vp["height"]}&&p.scrollHeight<=p.clientHeight+1&&p.getBoundingClientRect().bottom<={vp["height"]}+1}})()""")


def _scroller(pg, sec):
    """The phone day's scroller: the list card, the only thing that scrolls (topic 1; the
    user's pick H1c undid H1b's scrolling page)."""
    return f"{sec} .plist"


def _view_top(pg, sec):
    """Where the visible list starts: H1c's card cap (.lcap) -- the list's box sits a folded
    calendar higher than it looks, its top clipped -- or, without scroll timelines or with the
    map open, the list card's top."""
    return pg.evaluate(f"""(s=>{{const c=s.querySelector('.lcap');
        return (c&&getComputedStyle(c).display!=='none'?c:s.querySelector('.plist')).getBoundingClientRect().top}})(document.querySelector('{sec}'))""")


def _settle(pg, sel, still=6, step=50, limit=5000, lead=250):
    """Wait until sel's scrollTop -- and the fold it drives (its page's card cap) -- hold still
    (the anchor jump glides with scroll-behavior:smooth; a person taps again once it stops).
    The glide may start late on a slow machine (CI), so stillness counts after a short lead.
    Polled from Python: with JavaScript off the page runs no requestAnimationFrame of ours."""
    pg.wait_for_timeout(lead)
    probe = f"""(L=>{{const c=L.closest('.page')&&L.closest('.page').querySelector('.lcap');
        return L.scrollTop+'/'+(c?c.getBoundingClientRect().top:0)}})(document.querySelector('{sel}'))"""
    last, same, waited = None, 0, 0
    while waited < limit:
        now = pg.evaluate(probe)
        same = same + 1 if now == last else 0
        if same >= still:
            return
        last = now
        pg.wait_for_timeout(step); waited += step
    raise AssertionError(f"{sel} kept scrolling for {limit} ms")


def _box(pg, sel):
    return pg.evaluate(f"(()=>{{const r=document.querySelector('{sel}').getBoundingClientRect();return [r.left,r.top,r.right,r.bottom]}})()")


@pytest.mark.parametrize("js", [False, True])
def test_no_page_scrolls_and_the_chrome_stays_on_screen(open_page, js):
    pg = open_page(PHONE, js=js)
    assert _fits(pg, PHONE)
    for d in ("d1", "d2", "d3", "d4"):
        pg.click(f'.home .month label.stamp[for="pg-{d}"]')
        assert _fits(pg, PHONE), d
        # the scroller is the day (H1b, map closed) or the list (map open); either way it stays
        # on screen and the header with it, wherever it is scrolled
        sc = _scroller(pg, f"section[data-pg={d}]")
        for pos in ("0", "L.scrollHeight/2", "L.scrollHeight"):
            pg.evaluate(f"(()=>{{const L=document.querySelector('{sc}');L.scrollTop={pos}}})()")
            for sel in (f"section[data-pg={d}] .ymrow .back", f"section[data-pg={d}] .ymrow .ym", ".bubble"):
                l, t, r, b = _box(pg, sel)
                assert t >= 0 and b <= PHONE["height"] and l >= 0 and r <= PHONE["width"], (d, pos, sel)
        l, t, r, b = _box(pg, f"section[data-pg={d}] .plist")
        assert (round(l), round(r)) == (14, 376)
        assert _box(pg, sc)[3] <= PHONE["height"] - 12
        pg.click(f"section[data-pg={d}] .ymrow .back")


def test_header_is_centred_and_aligned(open_page):
    pg = open_page(PHONE, js=False)
    pg.click('.home .month label.stamp[for="pg-d2"]')
    l, t, r, b = _box(pg, "section[data-pg=d2] .ymrow .ym")
    assert abs((l + r) / 2 - 195) <= 1
    bl, bt, br, bb = _box(pg, ".bubble"); kl, kt, kr, kb = _box(pg, "section[data-pg=d2] .ymrow .back")
    assert abs((bt + bb) / 2 - (kt + kb) / 2) <= 1 and round(br) == 376


def test_a_short_day_still_fits(open_page):
    pg = open_page(PHONE, js=False)
    pg.click('.home .month label.stamp[for="pg-d3"]')              # the tour's D3: two stops
    assert _fits(pg, PHONE)


def test_small_phone_keeps_a_usable_list(open_page):
    pg = open_page(SMALL, js=False)
    pg.click('.home .month label.stamp[for="pg-d2"]')
    l, t, r, b = _box(pg, "section[data-pg=d2] .plist")
    assert b - t >= 200


@pytest.mark.parametrize("js", [False, True], ids=["no-script", "script"])
def test_an_opened_stop_lands_at_the_card_top(open_page, hakodate_url, js):
    """v1.1 §8.1, the user's own gesture: a stop's title near the bottom of the card, tap it.
    The anchor jump brings the title to the card's top with or without script (Quick Look
    and LINE run none)."""
    pg = open_page(SMALL, js=js, url=hakodate_url)                 # a short card, so most taps are measurable
    pg.click('.home .month label.stamp[for="pg-d2"]')
    tids = pg.eval_on_selector_all('section[data-pg="d2"] .plist .stop', "s => s.map(e => e.id)")
    measured = 0
    sec = "section[data-pg=d2]"
    for tid in tids[1:]:
        sc = _scroller(pg, sec)
        pg.evaluate(f"""(()=>{{const L=document.querySelector('{sc}'),h=document.querySelector('#{tid} .hd-open');
            L.style.scrollBehavior='auto';L.scrollTop+=h.getBoundingClientRect().top-(L.getBoundingClientRect().bottom-80);L.style.scrollBehavior=''}})()""")
        x, y = pg.evaluate(f"(()=>{{const r=document.querySelector('#{tid} .hd-open').getBoundingClientRect();return [r.left+60,r.top+r.height/2]}})()")
        pg.mouse.click(x, y)
        _settle(pg, sc)
        # CI's headless WebKit can go a few hundred ms without a frame mid-glide, which reads as
        # 'still' (t-d2-s3 measured 137-142 px short, twice, never locally even under full CPU
        # load): the check is where the glide ends, polled up to 5 s -- a stop that never
        # reaches the card's top still fails
        for _ in range(100):
            top = _view_top(pg, sec)
            m = pg.evaluate(f"""(()=>{{const L=document.querySelector('{sc}'),h=document.querySelector('#{tid} .hd-close').getBoundingClientRect();
                return {{head:h.top-{top},atEnd:L.scrollTop>=L.scrollHeight-L.clientHeight-1}}}})()""")
            if m["atEnd"] or 0 <= m["head"] <= 24:
                break
            pg.wait_for_timeout(50)
        # the list card's 12 px padding (H1c: measured from the card's visible top) + the stop's own inset
        assert m["atEnd"] or 0 <= m["head"] <= 24, (tid, m)
        measured += not m["atEnd"]
    assert measured >= 2


def test_photo_fullscreen_opens_and_closes(open_page, hakodate_url):
    pg = open_page(PHONE, js=False, url=hakodate_url)
    pg.click('.home .month label.stamp[for="pg-d2"]')
    tid = pg.eval_on_selector('section[data-pg="d2"] .stop:has(figure.bp)', "s => s.id")
    pg.click(f'section[data-pg="d2"] #{tid} a.hd-open')
    _settle(pg, 'section[data-pg="d2"] .plist')
    pg.click(f'section[data-pg="d2"] #{tid} label.bpz')
    assert _box(pg, 'section[data-pg="d2"] figure.bp:has(.pz:checked)') == [0, 0, PHONE["width"], PHONE["height"]]
    pg.click(f'section[data-pg="d2"] #{tid} label.bpz')
    assert pg.evaluate("document.querySelectorAll('.pz:checked').length") == 0


def test_cross_month_home_is_one_card(open_page):
    pg = open_page(PHONE, js=False)
    assert pg.eval_on_selector_all(".home .month", "m => m.length") == 1
    assert pg.eval_on_selector(".home .month h3", "h => h.textContent") == "2026 年 10～11 月"
    assert pg.eval_on_selector('.home .month label.stamp[for="pg-d3"] b', "b => b.textContent") == "11/1"


@pytest.mark.parametrize("sub", ["lodging", "advisory", "checklist"])
def test_a_sub_screen_scrolls_inside_and_keeps_its_way_back(open_page, sub):
    """Ruling (v1.1 Task 7): with the page locked, a long sub-screen scrolls in .pb, and
    its back label stays clear of the top-right toggle."""
    pg = open_page(PHONE, js=False)
    pg.click(f'.home .tiles label[for="pg-{sub}"]')
    assert _fits(pg, PHONE)
    pb = f'section[data-pg="{sub}"] .pb'
    assert pg.evaluate(f"getComputedStyle(document.querySelector('{pb}')).overflowY") == "auto"
    bl, bt, br, bb = _box(pg, ".bubble"); kl, kt, kr, kb = _box(pg, f'section[data-pg="{sub}"] .ph label.back')
    assert kr <= bl or kb <= bt, "the back label runs under the toggle"


@pytest.mark.parametrize("vp", [PHONE, SMALL], ids=["390x844", "360x640"])
def test_an_open_map_never_pushes_the_page_past_the_screen(open_page, vp):
    """Found on the real trip-e (v1.1 Task 11): on 360x640 an open map card made
    the page 725 px tall -- the list card fell off the locked screen."""
    pg = open_page(vp, js=False)
    for d in ("d1", "d2", "d3", "d4"):
        pg.click(f'.home .month label.stamp[for="pg-{d}"]')
        pg.click(f"section[data-pg={d}] details.mapc > summary")
        assert _fits(pg, vp), d
        l, t, r, b = _box(pg, f"section[data-pg={d}] .plist")
        assert b - t >= 118 and b <= vp["height"], (d, t, b)
        pg.click(f"section[data-pg={d}] details.mapc > summary")
        pg.click(f"section[data-pg={d}] .ymrow .back")


@pytest.mark.parametrize("dark", [True, False], ids=["moon", "sun"])
def test_the_toggle_icon_sits_in_the_centre_of_its_circle(open_page, dark):
    """User on a real phone: the moon sat off-centre. The v11 mockup centred the icon's
    wrapper (display:grid, line-height:0); the shipped sheet had dropped that rule, so
    the inline SVG rode the line box and its -.15em vertical-align."""
    pg = open_page(PHONE, js=False)
    if not dark:
        pg.click(".bubble")
    m = pg.evaluate("""(()=>{const b=document.querySelector('.bubble').getBoundingClientRect();
      const s=[...document.querySelectorAll('.bubble svg')].find(e=>e.getBoundingClientRect().width>0).getBoundingClientRect();
      return [(s.left+s.right)/2-(b.left+b.right)/2,(s.top+s.bottom)/2-(b.top+b.bottom)/2]})()""")
    assert abs(m[0]) <= 0.5 and abs(m[1]) <= 0.5, m


def test_a_stop_taller_than_the_card_keeps_its_title_in_view(open_page, hakodate_url):
    """Measured on the real trip-e: centring an opened stop that is taller than
    the list card pushed its title 17-40 px above the card's top edge."""
    # H1b gives the list the calendar's room once scrolled: at 360 x 520 the visible list is
    # 387 px and the photo stop 428 px (at 600 it fit)
    pg = open_page({"width": 360, "height": 520}, js=True, url=hakodate_url)
    pg.click('.home .month label.stamp[for="pg-d2"]')
    rid = pg.eval_on_selector('section[data-pg="d2"] .stop:has(figure.bp)', "s => s.id")
    pg.click(f'section[data-pg="d2"] #{rid} a.hd-open')
    pg.wait_for_timeout(900)
    sec = 'section[data-pg="d2"]'
    top = _view_top(pg, sec)
    view = pg.evaluate(f"document.querySelector('{_scroller(pg, sec)}').getBoundingClientRect().bottom") - top
    m = pg.evaluate(f"""(()=>{{const s=document.getElementById('{rid}'),h=s.querySelector('.hd-close').getBoundingClientRect();
        return {{tall:s.getBoundingClientRect().height>{view},head:h.top-{top}}}}})()""")
    assert m["tall"], "fixture: the photo stop must be taller than the phone's list card"
    assert -1 <= m["head"] <= 24, m                               # sub-pixel scroll rounding


# 320x440: the home is 496 px tall once the licence line left it (v1.1 TW-D3)
@pytest.mark.parametrize("vp", [{"width": 844, "height": 390}, {"width": 320, "height": 440}],
                         ids=["landscape", "320x440"])
def test_a_home_taller_than_the_screen_scrolls_to_its_last_tile(open_page, vp):
    """Review I2: the body is locked, so a home taller than a short screen must scroll
    itself, or the sub-screen tiles below the fold cannot be reached."""
    pg = open_page(vp, js=False)
    tall = pg.evaluate("(()=>{const p=document.querySelector('.page.home');return p.scrollHeight>p.clientHeight+1})()")
    assert tall, "fixture no longer overflows this screen; pick a shorter one"
    pg.evaluate("(()=>{const p=document.querySelector('.page.home');p.scrollTop=p.scrollHeight})()")
    assert pg.evaluate("document.body.scrollHeight") <= vp["height"]
    for b in pg.eval_on_selector_all(".home .tiles label", "ls => ls.map(l => l.getBoundingClientRect().bottom)"):
        assert b <= vp["height"], (b, vp)


# The ring's inner edge sits border + any inset box-shadow ring in from the stamp's edge;
# the text's line boxes (date and area name) must stay inside it. Read from computed
# style, so a ring that moves back inside the circle turns this red.
_RING = """(sel)=>[...document.querySelectorAll(sel)].filter(s=>s.offsetWidth).map(s=>{
  const cs=getComputedStyle(s),r=s.getBoundingClientRect(),cx=r.left+r.width/2,cy=r.top+r.height/2;
  const inset=Math.max(0,...cs.boxShadow.split(/,(?![^(]*\\))/).filter(x=>x.includes('inset')).map(x=>parseFloat((x.match(/-?[\\d.]+px/g)||[])[3]||0)));
  const R=s.offsetWidth/2-parseFloat(cs.borderTopWidth)-inset;let worst=-99;
  for(const t of s.querySelectorAll('b,small')){if(getComputedStyle(t).display==='none')continue;
    const g=document.createRange();g.selectNodeContents(t);const b=g.getBoundingClientRect();
    for(const [x,y] of [[b.left,b.top],[b.right,b.top],[b.left,b.bottom],[b.right,b.bottom]])worst=Math.max(worst,Math.hypot(x-cx,y-cy)-R);}
  return [s.querySelector('b').textContent,+worst.toFixed(1)]})"""


@pytest.mark.parametrize("where", ["day-mini", "home", "desktop"])
def test_the_stamp_rings_stay_clear_of_the_text(open_page, hakodate_url, where):
    """v1.1 (user pick A): the inner ring moved outside the circle, so neither ring
    crosses the date or the area name at 30 px (day mini), 42 px (home) or 36 px."""
    from conftest import DESKTOP
    pg = open_page(DESKTOP if where == "desktop" else PHONE, js=False)
    sel = {"home": ".page.home .month .stamp", "desktop": ".hcal .stamp",
           "day-mini": 'section[data-pg="d2"] .pcal .mini .stamp'}[where]
    if where == "day-mini":
        pg.click('.home .month label.stamp[for="pg-d2"]')
    got = pg.evaluate(_RING, sel)
    assert len(got) >= 3, got
    # the corner of a line box is not ink: 2 px of corner slack, the old inner ring cut 5
    assert max(w for _, w in got) <= 2, got


@pytest.mark.parametrize("day", ["d1", "d2", "d3", "d4"])
def test_map_time_labels_never_overlap(open_page, day):
    """v1.1 (user pick on the board): bare labels (no pill, no leader line), each set in
    the nearest free spot -- none overlaps another, a dot, the frame edge or the credit."""
    pg = open_page(PHONE, js=False)
    pg.evaluate(f"document.getElementById('pg-{day}').checked=true")
    pg.evaluate(f"(()=>{{const d=document.querySelector('section[data-pg={day}] .pmap details');if(d)d.open=true}})()")
    got = pg.evaluate(f"""[...document.querySelectorAll('section[data-pg={day}] .mapc .mv .mframe')].filter(f=>f.offsetWidth).map(f=>{{
      const r=f.getBoundingClientRect(), cr=f.querySelector('.attrmini')?.getBoundingClientRect();
      const t=[...f.querySelectorAll('text.tl')].map(e=>e.getBoundingClientRect()), d=[...f.querySelectorAll('circle.pt')].map(e=>e.getBoundingClientRect());
      const ov=(a,b)=>a.left<b.right-.5&&b.left<a.right-.5&&a.top<b.bottom-.5&&b.top<a.bottom-.5;
      return {{n:t.length, pairs:t.flatMap((a,i)=>t.slice(i+1).filter(b=>ov(a,b))).length,
              dots:t.filter(a=>d.some(b=>ov(a,b))).length, credit:cr?t.filter(a=>ov(a,cr)).length:0,
              out:t.filter(a=>a.left<r.left-.5||a.right>r.right+.5||a.top<r.top-.5||a.bottom>r.bottom+.5).length,
              pills:f.querySelectorAll('rect.tag').length, leads:f.querySelectorAll('line').length}}}})""")
    assert got and all(g["n"] for g in got), got
    assert all((g["pairs"], g["dots"], g["credit"], g["out"], g["pills"], g["leads"]) == (0,) * 6 for g in got), got


def test_the_chip_row_hints_at_more_only_where_there_is_more(open_page, hakodate_url):
    """v1.1 (user pick S3): the right edge fades while chips remain to the right, the
    left edge while some are scrolled past; at either end that edge is crisp. A 320 px
    phone so the fixture's six chips overflow the row."""
    pg = open_page({"width": 320, "height": 640}, js=False, url=hakodate_url)
    pg.evaluate("document.getElementById('pg-d2').checked=true")
    pg.evaluate("(()=>{const d=document.querySelector('section[data-pg=d2] .pmap details');if(d)d.open=true})()")
    row = "section[data-pg=d2] .pmap .chips"
    assert pg.evaluate(f"(()=>{{const r=document.querySelector('{row}');return r.scrollWidth>r.clientWidth}})()")
    fades = {}
    for name, pos in (("start", "0"), ("middle", "r.scrollWidth/2-r.clientWidth/2"), ("end", "r.scrollWidth")):
        pg.evaluate(f"(()=>{{const r=document.querySelector('{row}');r.scrollLeft={pos}}})()")
        pg.wait_for_timeout(150)
        fades[name] = pg.evaluate(f"(()=>{{const s=getComputedStyle(document.querySelector('{row}'));"
                                  f"return [parseFloat(s.getPropertyValue('--fl')),parseFloat(s.getPropertyValue('--fr'))]}})()")
    assert fades["start"][0] == 0 and fades["start"][1] > 20, fades
    assert fades["middle"][0] > 20 and fades["middle"][1] > 20, fades
    assert fades["end"][0] > 20 and fades["end"][1] == 0, fades


def test_a_label_is_never_wider_than_its_reserved_box(open_page):
    """Review M-2: _label_w reserves each map label's space; a Latin name (a stop with
    no time is labelled by name) measured wider than its reservation, so two could
    overlap. Measured on the reader's own .tl font in this engine."""
    from scripts.render.reader.maps import _label_w
    pg = open_page(PHONE, js=False)
    samples = ["Sapporo Beer Museum", "JR Tower", "08:00", "出發・回家", "旅館", "Mt. Hakodate Ropeway"]
    widths = pg.evaluate("""(ts)=>{const s=document.createElementNS('http://www.w3.org/2000/svg','svg');
      s.setAttribute('class','pins');document.body.append(s);
      return ts.map(t=>{const e=document.createElementNS('http://www.w3.org/2000/svg','text');e.setAttribute('class','tl');
        e.textContent=t;s.append(e);return e.getBBox().width})}""", samples)
    over = {t: (round(w, 1), round(_label_w(t) - 6, 1)) for t, w in zip(samples, widths) if w > _label_w(t) - 6 + 0.5}
    assert over == {}, over                                   # measured text vs reserved text width


# Controls a person taps (stamps, chips, toggles, buttons): a tap must not flash the
# browser's grey highlight box nor select their text (user report, iPhone).
CONTROLS = ('.home .month label.stamp', 'section[data-pg="d2"] .pcal .mini .stamp',
            'section[data-pg="d2"] .plist a.hd-open', '.home .tiles label', '.bubble')


@pytest.mark.parametrize("sel", CONTROLS)
def test_a_tapped_control_neither_selects_nor_flashes(open_page, sel):
    pg = open_page(PHONE, js=False)
    if "d2" in sel:
        pg.evaluate("document.getElementById('pg-d2').checked=true")
    el = pg.locator(sel).first
    style = el.evaluate("e=>{const s=getComputedStyle(e);return [s.webkitTapHighlightColor||'', s.webkitUserSelect||s.userSelect]}")
    assert style[0] in ("rgba(0, 0, 0, 0)", "transparent") and style[1] == "none", (sel, style)
    if "hd-open" in sel:
        # opening or closing a stop moves it by design (H1b scrolls the day to it), so the
        # second tap of a double-tap lands on other text and cannot measure the control.
        # What keeps a stop's header from selecting is its style -- held on both of them.
        close = pg.locator('section[data-pg="d2"] .plist a.hd-close').first
        style = close.evaluate("e=>{const s=getComputedStyle(e);return [s.webkitTapHighlightColor||'', s.webkitUserSelect||s.userSelect]}")
        assert style[0] in ("rgba(0, 0, 0, 0)", "transparent") and style[1] == "none", ("hd-close", style)
        return
    if "tiles" not in sel:          # a tile's first tap opens its screen; the second lands there
        el.dblclick(force=True)
        assert pg.evaluate("String(getSelection())").strip() == "", sel


@pytest.mark.parametrize("vp", [PHONE, {"width": 1366, "height": 768}], ids=["phone", "desktop"])
def test_the_driver_sheet_opens_full_screen_and_closes_back_to_the_open_stop(open_page, tmp_path, vp):
    """TW-096 (pick A2), no script: 給司機看 fills the screen with the local name and
    address; ✕ returns to the stop, still open; the address row wraps, never cut."""
    import copy
    from scripts.render.reader import render_reader
    from tests.reader_fixture import itinerary, poi_map, reader_kwargs
    pm = copy.deepcopy(poi_map())
    pm["hak-asaichi"].update(name_zh="函館早市", address_local="函館市若松町9-19 函館朝市ビル2階（長い建物名のテスト）",
                             address_source="https://www.hakodate-asaichi.com/")
    f = tmp_path / "addr.html"
    f.write_text(render_reader(itinerary(), pm, **reader_kwargs()), encoding="utf-8")
    pg = open_page(vp, js=False, url=f.as_uri())
    pg.evaluate("document.getElementById('pg-d2').checked=true")
    st = pg.eval_on_selector('section[data-pg="d2"] .stop[data-poi="hak-asaichi"]', "e => e.id")
    pg.evaluate(f"location.hash='#{st}'")
    pg.wait_for_timeout(300)
    dd = pg.evaluate(f"""(()=>{{const b=document.querySelector('#{st} .drvbtn').getBoundingClientRect(),
        d=document.querySelector('#{st} .drvbtn').closest('dd');return [d.scrollWidth<=d.clientWidth+1, b.right<=window.innerWidth]}})()""")
    assert dd == [True, True], dd
    pg.click(f"#{st} .drvbtn", force=True)
    pg.wait_for_timeout(300)
    box = pg.evaluate(f"(()=>{{const r=document.getElementById('{st}-drv').getBoundingClientRect();"
                      f"return [Math.round(r.width),Math.round(r.height),getComputedStyle(document.getElementById('{st}-drv')).display]}})()")
    assert box == [vp["width"], vp["height"], "flex"], box
    # the sheet is a target inside the stop: the map keeps showing this stop's view
    shown = pg.evaluate("[...document.querySelectorAll('section[data-pg=d2] .mapc .mv')].filter(v=>getComputedStyle(v).display!=='none').map(v=>v.className)")
    assert shown and all("-all" not in c for c in shown), shown
    pg.click(f"#{st}-drv .drvx", force=True)
    pg.wait_for_timeout(300)
    assert pg.evaluate(f"getComputedStyle(document.getElementById('{st}-drv')).display") == "none"
    assert pg.evaluate(f"getComputedStyle(document.querySelector('#{st} .in')).display") != "none"   # stop still open




@pytest.mark.parametrize("vp", [PHONE, DESKTOP], ids=["phone", "desktop"])
def test_one_day_title_shows_per_width(open_page, vp):
    """v1.1 topic 6 D2: the phone keeps its title in the fixed header; the desktop shows
    it at the top of the list, sticky, and hides the header copy."""
    pg = open_page(vp, js=False)
    pg.evaluate("document.getElementById('pg-d2').checked=true")
    shown = pg.evaluate("""[...document.querySelectorAll('section[data-pg=d2] h2.dh')]
        .filter(h=>getComputedStyle(h).display!=='none').map(h=>h.closest('.plist')?'list':'header')""")
    assert shown == (["header"] if vp is PHONE else ["list"]), shown
    if vp is DESKTOP:
        pg.evaluate("document.querySelector('section[data-pg=d2] .plist').scrollTop=400")
        top = pg.evaluate("(()=>{const l=document.querySelector('section[data-pg=d2] .plist'),h=l.querySelector('h2.dh-list');return h.getBoundingClientRect().top-l.getBoundingClientRect().top})()")
        assert -1 <= top <= 2, top                      # sticky at the list's top edge


def test_home_stamps_keep_the_mini_calendar_proportion(open_page):
    """v1.1 topic 6 P1: the home stamp was 42 px with a 14 px date (33 %) and 3-4 px
    between stamps; the day page's 30 px stamp the user liked has 40 %. 34 px with the
    same 14 px date, and room between neighbours."""
    pg = open_page(PHONE, js=False)
    got = pg.evaluate("""(()=>{const s=[...document.querySelectorAll('.home .months .stamp')];
      const w=s[0].offsetWidth,b=parseFloat(getComputedStyle(s[0].querySelector('b')).fontSize);
      const r=s.map(x=>x.getBoundingClientRect());const gap=r[1].left-r[0].right;return [w,b,gap]})()""")
    assert got[0] == 34 and got[1] == 14 and got[2] >= 10, got


_OVERLAP = """()=>[...document.querySelectorAll('.page.day .pmap .mv .mframe')].filter(f=>f.offsetWidth).map(f=>{
  const cr=f.querySelector('.attrmini')?.getBoundingClientRect();if(!cr)return 0;
  const ov=(a,b)=>a.left<b.right-.5&&b.left<a.right-.5&&a.top<b.bottom-.5&&b.top<a.bottom-.5;
  return [...f.querySelectorAll('text.tl')].map(e=>e.getBoundingClientRect()).filter(a=>ov(a,cr)).length})"""


@pytest.mark.parametrize("vp", [{"width": 1024, "height": 700}, {"width": 1280, "height": 720},
                                {"width": 1366, "height": 640}, DESKTOP],
                         ids=["1024x700", "1280x720", "1366x640", "1366x768"])
def test_map_labels_clear_the_credit_on_the_desktop(open_page, vp):
    """Topic-2 review M-1, measured 0 on trip-e at six desktop sizes (topic 6): on a
    short desktop window the frame shrinks while the credit keeps its size; no time label
    may sit under it, in any day's overview or any chip's view."""
    pg = open_page(vp, js=False)
    days = pg.eval_on_selector_all("section.page.day", "s => s.map(e => e.dataset.pg)")
    hits = []
    for day in days:
        pg.evaluate(f"document.getElementById('pg-{day}').checked=true")
        targets = [None] + pg.eval_on_selector_all(f"section[data-pg={day}] .pmap .chips a.chip", "a => a.map(e => e.getAttribute('href'))")
        for h in targets:
            if h:
                pg.evaluate(f"location.hash='{h}'")
            n = sum(pg.evaluate(_OVERLAP))
            if n:
                hits.append((day, h, n))
    assert hits == [], hits
    # the desktop names OpenStreetMap once, under the map (the frames' corner badge is hidden)
    pg.evaluate("document.getElementById('pg-d2').checked=true;location.hash=''")
    assert pg.evaluate("[...document.querySelectorAll('section[data-pg=d2] .pmap .attr')].some(a=>a.offsetWidth&&a.textContent.includes('OpenStreetMap'))")
