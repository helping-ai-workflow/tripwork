"""v1.2.1: the cards of 住宿 / 入境規定 / 行前清單 draw their outline as a 1 px box-shadow
outside the box; the sub-page's scroller (.ovbox .pb) was exactly as wide as the cards, so
its overflow cut the side lines off and only the rounded corners showed. Measured on the
shipped page, phone and desktop, both engines, both themes."""
import pytest
from conftest import DESKTOP, PHONE

SUBS = {"pg-lodging": ".lrow", "pg-advisory": ".adv", "pg-checklist": ".ci"}

EDGES = """sel => [...document.querySelectorAll(sel)].filter(e => e.getBoundingClientRect().width > 0).map(e => {
  const r = e.getBoundingClientRect();
  let a = e.parentElement;
  while (a && a !== document.body) { const s = getComputedStyle(a); if (s.overflowX !== 'visible' || s.overflowY !== 'visible') break; a = a.parentElement }
  const ar = a.getBoundingClientRect(), s = getComputedStyle(a);
  return {left: r.left - 1, right: r.right + 1, min: ar.left + parseFloat(s.borderLeftWidth), max: ar.right - parseFloat(s.borderRightWidth)} })"""


@pytest.mark.parametrize("vp", [PHONE, DESKTOP], ids=["phone", "desktop"])
@pytest.mark.parametrize("dark", [False, True], ids=["light", "dark"])
@pytest.mark.parametrize("sub", list(SUBS))
def test_sub_page_cards_keep_their_side_lines(open_page, hakodate_url, vp, dark, sub):
    pg = open_page(vp, url=hakodate_url)
    if dark:
        pg.evaluate("document.getElementById('theme').checked=true")
    pg.evaluate(f"document.getElementById('{sub}').checked=true")
    pg.wait_for_timeout(300)
    cards = pg.evaluate(EDGES, SUBS[sub])
    assert cards, f"no {SUBS[sub]} on {sub}"
    cut = [c for c in cards if c["left"] < c["min"] - 0.01 or c["right"] > c["max"] + 0.01]
    assert not cut, cut
