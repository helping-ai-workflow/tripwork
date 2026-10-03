"""v1.1 topic 6: the desktop home stamp is the phone stamp zoomed x1.9 with whole-px
lines; the theme hugs the outer ring 3 px out, centred on the tilt."""
import pytest
from conftest import DESKTOP, PHONE


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_desktop_stamp_geometry_and_ring(open_page, scheme):
    pg = open_page(DESKTOP, js=False)
    pg.emulate_media(color_scheme=scheme)
    got = pg.evaluate("""(()=>{const s=document.querySelector('.hcal .stamp[for=pg-d2]'),c=getComputedStyle(s);
      const t=s.querySelector('svg.ring text'),tp=t.querySelector('textPath');
      const r=s.getBoundingClientRect(),cx=r.left+r.width/2,cy=r.top+r.height/2,n=tp.getNumberOfChars();
      const mid=t.getExtentOfChar(Math.floor(n/2)),m=t.getScreenCTM();
      const p=new DOMPoint(mid.x+mid.width/2,mid.y+mid.height).matrixTransform(m);
      const path=s.querySelector('svg.ring path'),L=path.getTotalLength(),q=path.getPointAtLength(L/2);
      const top=new DOMPoint(q.x,q.y).matrixTransform(path.getScreenCTM());
      return {w:s.offsetWidth,b:c.borderTopWidth,o:c.outlineWidth,off:c.outlineOffset,fill:getComputedStyle(t).fill,col:c.color,
              ang:Math.atan2(p.x-cx,cy-p.y)*180/Math.PI,dist:Math.hypot(top.x-cx,top.y-cy),tilt:parseFloat(s.style.getPropertyValue('--t'))}})()""")
    assert got["w"] == 65 and (got["b"], got["o"], got["off"]) == ("3px", "2px", "3px"), got
    assert got["fill"] == got["col"], got                                  # same colour as the stamp
    assert abs(got["ang"] - got["tilt"]) < 4, got                          # centred at the tilted top
    # the text hangs by its em-box bottom on this path (text-after-edge): 3 px outside the
    # outer ring's edge (37.3 px). Glyph boxes vary with the font, the path does not.
    assert abs(got["dist"] - (37.3 + 3)) < 0.5, got


def test_the_phone_home_has_no_ring(open_page):
    pg = open_page(PHONE, js=False)
    assert pg.evaluate("[...document.querySelectorAll('.home svg.ring')].every(r=>getComputedStyle(r).display==='none')")


# --- the 旅程與費用 card (topic 6, picks C2 + S) ---

def _fits(pg):
    return pg.evaluate("(()=>{const h=document.querySelector('.page.home');return h.scrollHeight<=h.clientHeight+1})()")


def test_phone_home_fits_one_screen_with_the_card(open_page, many_stays_url):
    pg = open_page(PHONE, js=False, url=many_stays_url)
    assert pg.evaluate("document.querySelectorAll('.home .trip ol>li').length") == 11
    assert _fits(pg)


@pytest.mark.parametrize("vp", [PHONE, DESKTOP], ids=["phone", "desktop"])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_card_list_scrolls_inside_and_fades_where_there_is_more(open_page, many_stays_url, vp, scheme):
    """S picked: bottom fades while stays remain below, top while scrolled past, crisp at the ends."""
    pg = open_page(vp, js=False, url=many_stays_url)
    pg.emulate_media(color_scheme=scheme)
    ol = "document.querySelector('.home .trip ol')"
    assert pg.evaluate(f"{ol}.scrollHeight>{ol}.clientHeight+1"), "the list should scroll inside the card"
    mask = f"(getComputedStyle({ol}).maskImage||getComputedStyle({ol}).webkitMaskImage)"
    pg.evaluate(f"{ol}.scrollTop=0"); pg.wait_for_timeout(120)
    top = pg.evaluate(mask)
    pg.evaluate(f"{ol}.scrollTop={ol}.scrollHeight"); pg.wait_for_timeout(120)
    end = pg.evaluate(mask)
    assert top != end, (top, end)
    if vp is PHONE:
        assert _fits(pg)


def test_the_desktop_card_fills_the_left_column(open_page, many_stays_url):
    pg = open_page(DESKTOP, js=False, url=many_stays_url)
    got = pg.evaluate("""(()=>{const s=document.querySelector('.hside'),c=document.querySelector('.hside .trip');
      const a=s.getBoundingClientRect(),b=c.getBoundingClientRect();return [a.bottom-b.bottom, s.scrollHeight<=s.clientHeight+1]})()""")
    assert 0 <= got[0] <= 80 and got[1], got


@pytest.mark.parametrize("vp", [PHONE, DESKTOP], ids=["phone", "desktop"])
def test_a_list_that_fits_does_not_fade_its_last_row(open_page, vp):
    """Review I2: with nothing to scroll there is nothing below -- the bottom edge is crisp
    (trip-e's 返程 row had faded to half on the phone)."""
    pg = open_page(vp, js=False)
    ol = "document.querySelector('.home .trip ol')"
    assert pg.evaluate(f"{ol}.scrollHeight<={ol}.clientHeight+1"), "fixture: this list should fit"
    assert pg.evaluate(f"getComputedStyle({ol}).getPropertyValue('--fb').trim()") == "0px"


_RING_GLYPHS = """()=>[...document.querySelectorAll('.page.home .hcal .ring text')].filter(t=>t.getNumberOfChars()).map(t=>{
  const m=t.getScreenCTM(),out=[];
  for(let i=0;i<t.getNumberOfChars();i++){const e=t.getExtentOfChar(i),p=new DOMPoint(e.x+e.width/2,e.y+e.height/2).matrixTransform(m);out.push([p.x,p.y])}
  return out})"""
_STAMPS = "()=>[...document.querySelectorAll('.page.home .hcal .stamp')].map(s=>{const r=s.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom]})"


@pytest.mark.parametrize("vp", [{"width": 1024, "height": 700}, {"width": 1280, "height": 720},
                                {"width": 1366, "height": 640}, DESKTOP],
                         ids=["1024x700", "1280x720", "1366x640", "1366x768"])
def test_ring_text_clears_its_neighbours(open_page, long_rings_url, vp):
    """Review I3: a ring's theme reaches past its column on a narrow desktop and collides
    with the next stamp's (1024 wide), or with the stamp above (a short window, six weeks).
    No glyph of one ring may come within 11 px of another ring's glyph, nor sit inside
    another stamp."""
    pg = open_page(vp, js=False, url=long_rings_url)
    assert pg.locator(".hcal .g .wd").count() == 7 and pg.locator(".hcal .stamp").count() == 15
    rings, stamps = pg.evaluate(_RING_GLYPHS), pg.evaluate(_STAMPS)
    assert rings, "fixture: no rings drawn"
    close = [(a, b) for a in range(len(rings)) for b in range(a + 1, len(rings))
             if any(((x1 - x2) ** 2 + (y1 - y2) ** 2) ** .5 < 11 for x1, y1 in rings[a] for x2, y2 in rings[b])]
    # a stamp is round: a glyph is "on" it within its radius plus the 3+2 px outline
    inside = [(a, s) for a, g in enumerate(rings) for s, (l, t, r, bt) in enumerate(stamps)
              if any(((x - (l + r) / 2) ** 2 + (y - (t + bt) / 2) ** 2) ** .5 < (r - l) / 2 + 5 for x, y in g)]
    assert close == [] and inside == [], (close, inside)


_UNDER_BUBBLE = """()=>{const b=document.querySelector('.bubble').getBoundingClientRect();
  const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),out=[];
  for(let n;(n=w.nextNode());){if(!n.textContent.trim()||n.parentElement.closest('.bubble'))continue;
    const r=document.createRange();r.selectNodeContents(n);
    for(const q of r.getClientRects())if(q.width&&q.left<b.right&&b.left<q.right&&q.top<b.bottom&&b.top<q.bottom)out.push(n.textContent.trim().slice(0,20))}
  return out}"""


@pytest.mark.parametrize("vp", [{"width": 1024, "height": 700}, {"width": 1280, "height": 560},
                                {"width": 1280, "height": 720}, DESKTOP],
                         ids=["1024x700", "1280x560", "1280x720", "1366x768"])
@pytest.mark.parametrize("pgid", ["home", "d2"])
def test_the_theme_button_covers_no_text(open_page, many_stays_url, vp, pgid):
    """Review I4: on a narrow or short desktop window the page has no left gutter, and the
    bottom-left theme button sat over 合計 (home) -- and would over the map credit (day)."""
    pg = open_page(vp, js=False, url=many_stays_url)
    if pgid != "home":
        pg.evaluate(f"document.getElementById('pg-{pgid}').checked=true")
    assert pg.evaluate(_UNDER_BUBBLE) == []
