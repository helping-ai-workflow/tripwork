"""住宿 / 入境規定 / 行前清單 on the phone (the user's pick C1): 「‹ 總覽」 sits at the top left where
a day page has it, the title is centred on the screen, and nothing covers the list's first item
-- the list starts where it did."""
import pytest
from conftest import PHONE

BACK = "(b=>[b.x,b.y,b.width,b.height])(document.querySelector('{sel}').getBoundingClientRect())"
SUB = """(sec=>{const s=document.querySelector('section[data-pg='+sec+']'),ph=s.querySelector('.ph'),h=ph.querySelector('h2'),b=ph.querySelector('.back');
  const pb=s.querySelector('.pb'),first=[...pb.children].find(e=>e.offsetHeight&&getComputedStyle(e).position!=='sticky');
  const r=e=>{const q=e.getBoundingClientRect();return [q.x,q.y,q.width,q.height]};
  const sh=parseFloat((getComputedStyle(first).boxShadow.match(/0px 0px 0px ([\\d.]+)px/)||[0,0])[1]);
  return {back:r(b),title:r(h),head:ph.getBoundingClientRect().bottom,first:first.getBoundingClientRect().top,shadow:sh,list:pb.getBoundingClientRect().top}})"""


def _go(pg, pid):
    pg.evaluate(f"(r=>{{r.checked=true;r.dispatchEvent(new Event('change',{{bubbles:true}}))}})(document.getElementById('{pid}'))")
    pg.wait_for_timeout(500)


@pytest.mark.parametrize("screen", ["lodging", "advisory", "checklist"])
def test_the_back_pill_is_where_a_day_has_it_and_the_title_is_centred(browser, many_stays_url, screen):
    pg = browser.new_page(viewport=PHONE)
    pg.goto(many_stays_url)
    _go(pg, "pg-d1")
    day_back = pg.evaluate(BACK.format(sel="section[data-pg=d1] .ymrow .back"))
    _go(pg, f"pg-{screen}")
    m = pg.evaluate(SUB, screen)
    assert m["back"] == pytest.approx(day_back, abs=.05), (m["back"], day_back)
    cx = m["title"][0] + m["title"][2] / 2
    assert cx == pytest.approx(PHONE["width"] / 2, abs=.5), m["title"]
    # nothing covers the first item: the row ends above it (its outline included), the list where it was
    assert m["head"] <= m["first"] - m["shadow"], m
    assert m["list"] == pytest.approx(47, abs=.5), m       # 47: where the list began before C1 -- a literal
    pg.close()                                             # because the place to keep is the old one
