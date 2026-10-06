"""An opened stop lands below the sticky title row + map + card top (publish build, phone).

PUBLISH_JS makes each day one scroller whose title row, map row and the card's top edge stick
(.stk). Opening a stop is an anchor jump; with no scroll padding it put the stop 8 px under the
scroller's top -- under .stk, its title row hidden (a consumer trip: 「點開行程有時候不會把上緣
顯示在卡片裡面」, then 「框線上緣還是被遮住」 -- the card's top edge and fade hang below .stk). The scroller's padding follows .stk's height, the map row open or not."""
import pytest
from conftest import PHONE

# `under`: the lowest thing covering the list's top -- the card's top edge and its fade hang below
# .stk (.lcap's ::after / ::before), measured from the page
AT = """(id=>{const s=document.getElementById(id),d=s.closest('section'),l=d.querySelector('.lcap'),vs=d.querySelector('.vs');
  const top=l.getBoundingClientRect().top,ends=['::before','::after'].map(k=>{const c=getComputedStyle(l,k);return top+(parseFloat(c.top)||0)+(parseFloat(c.height)||0)});
  return {top:s.getBoundingClientRect().top,under:Math.max(...ends),scroll:vs.scrollTop,max:vs.scrollHeight-vs.clientHeight}})"""


def _go(pg, pid):
    pg.evaluate(f"(r=>{{r.checked=true;r.dispatchEvent(new Event('change',{{bubbles:true}}))}})(document.getElementById('{pid}'))")
    pg.wait_for_timeout(500)


def _open(pg, sid):
    pg.evaluate("(L=>{L.style.scrollBehavior='auto';L.scrollTop=0;L.style.scrollBehavior=''})(document.querySelector('section[data-pg=d2] .vs'))")
    pg.wait_for_timeout(400)
    pg.locator(f"#{sid} a.hd-open").click()
    pg.wait_for_timeout(1200)                       # the jump is a smooth scroll
    return pg.evaluate(AT, sid)


@pytest.fixture
def day2(browser, publish_url):
    pg = browser.new_page(viewport=PHONE)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(publish_url)
    pg.wait_for_timeout(500)
    _go(pg, "pg-d2")
    yield pg
    assert not errs
    pg.close()


@pytest.mark.parametrize("sid", ["t-d2-s1", "t-d2-s3"])
def test_an_opened_stop_lands_below_the_sticky_rows(day2, sid):
    a = _open(day2, sid)
    assert a["top"] == pytest.approx(a["under"] + 8, abs=1.5), a      # its scroll-margin, below the edge and its fade


def test_a_stop_near_the_end_shows_whole(day2):
    """The list cannot scroll far enough to bring the last stops up: they stay where they are,
    still below the sticky rows."""
    a = _open(day2, "t-d2-s5")
    assert a["top"] >= a["under"], a


def test_with_the_map_open_the_stop_still_lands_below(day2):
    day2.click("section[data-pg=d2] .mapc summary")
    day2.wait_for_timeout(500)
    a = _open(day2, "t-d2-s3")
    assert a["under"] > 200                                           # the map row is open: .stk is tall
    assert a["top"] >= a["under"], a
