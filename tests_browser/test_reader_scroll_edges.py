"""The user's check, pick T1 (+ B1's bar): on the desktop the list panel and the sub-screen
popups keep a thin scrollbar in the reader's colours and fade at the edges with gradients
of their own background laid over the content -- nothing is masked (a mask cut content
hard under the title and faded the bar). The top gradient hangs from the title once
scrolled; the bottom one goes at the end. The phone is unchanged."""
import pytest
from conftest import DESKTOP, PHONE

OP = "(q=>getComputedStyle(document.querySelector(q.split('::')[0]),q.includes('::')?'::'+q.split('::')[1]:null).opacity)"
LIST = "section[data-pg=d2] .plist"


# the fixture's D2 list and checklist both scroll over 100 px in this window; 40 px down is
# past the top gradient's 32 px range and short of the end
SHORT = {"width": 1366, "height": 300}
MID = 40


def _d2(open_page, vp=DESKTOP):
    pg = open_page(vp, js=False)
    pg.evaluate("document.getElementById('pg-d2').checked=true")
    pg.wait_for_timeout(200)
    return pg


def _op(pg, q, want, limit=2000):
    """The opacity q settles to: polled until it reads want or limit ms pass (WebKit can apply
    a scroll-driven value a frame or more after the scroll on a slow machine). Returns the last
    reading, so a gradient that never gets there still fails."""
    got, waited = None, 0
    while waited <= limit:
        got = float(pg.evaluate(f"{OP}('{q}')"))
        if got == want:
            break
        pg.wait_for_timeout(50); waited += 50
    return got


def _scroll(pg, sel, where):
    to = "e.scrollHeight" if where == "end" else str(where)
    pg.evaluate(f"(e=>{{e.scrollTop={to}}})(document.querySelector('{sel}'))")
    pg.wait_for_timeout(200)


def test_the_desktop_scrollers_have_a_thin_bar_and_no_mask(open_page):
    pg = _d2(open_page)
    for sel in (LIST, "section[data-pg=d2] .pmap .lgd"):
        s = pg.evaluate(f"(e=>{{const c=getComputedStyle(e);return [c.scrollbarWidth,c.maskImage||c.webkitMaskImage||'none']}})(document.querySelector('{sel}'))")
        assert s[0] == "thin" and s[1] == "none", (sel, s)


def test_a_list_that_does_not_scroll_draws_no_gradient(open_page):
    """An inactive scroll timeline leaves an element on its own style: both gradients
    must rest at opacity 0, or a short list keeps a fade under its title for nothing."""
    pg = _d2(open_page)
    assert pg.evaluate(f"(e=>e.scrollHeight<=e.clientHeight)(document.querySelector('{LIST}'))"), "fixture: should fit"
    assert float(pg.evaluate(f"{OP}('{LIST} > .dh-list::after')")) == 0 and float(pg.evaluate(f"{OP}('{LIST} > .fb')")) == 0


def test_the_list_fades_under_the_title_only_once_scrolled_and_not_at_the_end(open_page):
    pg = _d2(open_page, SHORT)
    assert pg.evaluate(f"(e=>e.scrollHeight>e.clientHeight+100)(document.querySelector('{LIST}'))"), "fixture: should scroll"
    top, bot = f"{LIST} > .dh-list::after", f"{LIST} > .fb"
    assert _op(pg, top, 0) == 0 and _op(pg, bot, 1) == 1
    _scroll(pg, LIST, MID)
    assert _op(pg, top, 1) == 1 and _op(pg, bot, 1) == 1
    _scroll(pg, LIST, "end")
    assert _op(pg, bot, 0) == 0


def test_a_sub_screen_fades_the_same_way(open_page):
    pg = open_page(SHORT, js=False)
    pg.evaluate("document.getElementById('pg-checklist').checked=true")
    pg.wait_for_timeout(200)
    pb = "section[data-pg=checklist] .pb"
    assert pg.evaluate(f"(e=>e.scrollHeight>e.clientHeight+100)(document.querySelector('{pb}'))"), "fixture: should scroll"
    assert _op(pg, f"{pb} > .ft", 0) == 0
    _scroll(pg, pb, MID)
    assert _op(pg, f"{pb} > .ft", 1) == 1 and _op(pg, f"{pb} > .fb", 1) == 1


def test_the_phone_draws_no_edge_gradients(open_page):
    pg = _d2(open_page, PHONE)
    assert pg.evaluate(f"getComputedStyle(document.querySelector('{LIST} > .fb')).display") == "none"


def test_the_bottom_gradient_sits_on_the_panels_edge(open_page):
    """The list has 60 px of bottom padding; a sticky gradient stops at the padding, so it sat
    59 px up (fading a move row while the card below stayed clear). It must meet the edge."""
    pg = _d2(open_page, SHORT)
    _scroll(pg, LIST, MID)
    gap = pg.evaluate(f"(l=>l.getBoundingClientRect().bottom-l.querySelector('.fb').getBoundingClientRect().bottom)(document.querySelector('{LIST}'))")
    assert abs(gap) <= 1.5, gap


@pytest.mark.parametrize("box,top,bottom", [(LIST, f"{LIST} > .dh-list::after", f"{LIST} > .fb"),
                                            (".page.sub .ovbox .pb", ".page.sub .ovbox .pb > .ft", ".page.sub .ovbox .pb > .fb")])
def test_both_fades_of_a_scroller_run_on_its_one_named_timeline(open_page, box, top, bottom):
    """The user's cross-test (2026-10-03): with both gradients on anonymous scroll(nearest y)
    timelines, the first scroll after opening a day stalled for seconds on their computer;
    either gradient alone did not, and both on the scroller's one named timeline (test I)
    did not. Both gradients read the timeline their scroller names."""
    pg = _d2(open_page)
    name = pg.evaluate(f"getComputedStyle(document.querySelector('{box}')).scrollTimelineName")
    assert name.startswith("--"), (box, name)
    for q in (top, bottom):
        tl = pg.evaluate(f"(q=>getComputedStyle(document.querySelector(q.split('::')[0]),q.includes('::')?'::'+q.split('::')[1]:null).animationTimeline)('{q}')")
        assert tl == name, (q, tl, name)
