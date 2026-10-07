"""住宿 / 入境規定: the first card's top line shows.

A card's outline is a 1px box-shadow outside its box, and the scroller (.ovbox .pb) clips at its
padding box: its sides had a pixel of room (margin-inline:-1px, padding-inline:1px) but its top
and bottom did not, so the first card's top line was cut off (a consumer trip: 「第一個項目上緣被
切掉」). The room is now on all four sides, the cards where they were."""
import pytest
from conftest import DESKTOP, PHONE

ROOM = """(sec=>{const pb=document.querySelector('section[data-pg='+sec+'] .pb')||document.querySelector('.ovbox:has(#'+sec+') .pb');
  const kids=[...pb.children].filter(e=>e.offsetHeight&&getComputedStyle(e).position!=='sticky');const f=kids[0],l=kids[kids.length-1];
  const b=pb.getBoundingClientRect(),cs=getComputedStyle(pb),top=b.top+parseFloat(cs.borderTopWidth),
        sh=parseFloat((getComputedStyle(f).boxShadow.match(/0px 0px 0px ([\\d.]+)px/)||[0,0])[1]);
  pb.scrollTop=pb.scrollHeight;const lb=l.getBoundingClientRect().bottom,bottom=pb.getBoundingClientRect().bottom-parseFloat(cs.borderBottomWidth);
  pb.scrollTop=0;return {first:f.getBoundingClientRect().top,top,shadow:sh,last:lb,bottom}})"""


def _go(pg, pid):
    pg.evaluate(f"(r=>{{r.checked=true;r.dispatchEvent(new Event('change',{{bubbles:true}}))}})(document.getElementById('{pid}'))")
    pg.wait_for_timeout(500)


# 行前清單 is left out: each of its groups opens with a heading, so no card meets the scroller's edge
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["phone", "desktop"])
@pytest.mark.parametrize("screen", ["lodging", "advisory"])
def test_the_first_cards_top_line_is_inside_the_scroller(browser, many_stays_url, viewport, screen):
    pg = browser.new_page(viewport=viewport)
    pg.goto(many_stays_url)
    _go(pg, f"pg-{screen}")
    r = pg.evaluate(ROOM, screen)
    assert r["shadow"] >= 1, r                                   # the outline is the shadow, outside the box
    assert r["first"] - r["shadow"] >= r["top"] - .01, r          # its top line is not clipped
    assert r["last"] + r["shadow"] <= r["bottom"] + .01, r        # nor the last card's bottom line
    pg.close()


@pytest.mark.parametrize("screen", ["lodging", "advisory"])
def test_the_cards_stay_where_they_were(browser, many_stays_url, screen):
    """The pixel of room comes from the scroller reaching out by it, not from the cards moving."""
    pg = browser.new_page(viewport=PHONE)
    pg.goto(many_stays_url)
    _go(pg, f"pg-{screen}")
    first = pg.evaluate(ROOM, screen)["first"]
    head = pg.evaluate(f"document.querySelector('section[data-pg={screen}] .pb').previousElementSibling.getBoundingClientRect().bottom")
    # 48: where the first card sat before the fix (under the 48 px title bar) -- a literal because
    # the place it must keep is the old one, which no shipped constant names
    assert first == pytest.approx(48, abs=.01) and head <= first, (first, head)
    pg.close()
