"""User check (2026-10-02): the phone's 「‹ Day N ›」 stepper. It changes the day with no
script, and it is centred on the title by its ink -- the glyph pixels, not the boxes
(tripwork/CLAUDE.md, reader visual work) -- in a 4x screenshot."""
import io

import pytest
from conftest import DESKTOP, PHONE
from PIL import Image

K = 4


def _day(pg):
    return pg.evaluate("[...document.querySelectorAll('input[name=pg]')].find(r=>r.checked)?.id")


@pytest.mark.parametrize("vp,where", [(PHONE, ".pcal .dh"), (DESKTOP, ".plist .dh-list")], ids=["phone", "desktop"])
def test_the_stepper_holds_its_place_whatever_the_title(open_page, vp, where):
    """Pick F1: the stepper sits at the right end of the title row -- the same x on every
    day, however long the title (it used to follow the title's end)."""
    pg = open_page(vp, js=False)
    xs = []
    for i in range(1, pg.locator("section.page.day").count() + 1):
        pg.evaluate(f"document.getElementById('pg-d{i}').checked=true")
        pg.wait_for_timeout(100)
        xs.append(pg.evaluate(f"""(()=>{{const row=document.querySelector('section[data-pg=d{i}] {where}'),s=row.querySelector('.dstep');
            return [Math.round(s.getBoundingClientRect().right),Math.round(row.getBoundingClientRect().right-parseFloat(getComputedStyle(row).paddingRight))]}})()"""))
    assert len({x for x, _ in xs}) == 1 and all(abs(x - r) <= 1 for x, r in xs), xs


def test_the_desktop_arrows_change_the_day(open_page):
    pg = open_page(DESKTOP, js=False)
    pg.evaluate("document.getElementById('pg-d2').checked=true")
    pg.locator('section[data-pg="d2"] .plist .dh-list .dstep label[for="pg-d3"]').click()
    assert _day(pg) == "pg-d3"


def test_the_arrows_change_the_day_with_no_script(open_page):
    pg = open_page(PHONE, js=False)
    pg.evaluate("document.getElementById('pg-d2').checked=true")
    pg.locator('section[data-pg="d2"] .pcal .dstep label[for="pg-d3"]').click()
    assert _day(pg) == "pg-d3"
    pg.locator('section[data-pg="d3"] .pcal .dstep label[for="pg-d2"]').click()
    pg.locator('section[data-pg="d2"] .pcal .dstep label[for="pg-d1"]').click()
    assert _day(pg) == "pg-d1"
    assert pg.locator('section[data-pg="d1"] .pcal .dstep .off').count() == 1


def _rows(img, box, pred):
    x0, y0, x1, y1 = (int(v) for v in box)
    px = img.load()
    return [y for y in range(y0, y1) if any(pred(px[x, y]) for x in range(x0, x1))]


@pytest.mark.parametrize("vp,where,h", [(PHONE, ".pcal .dh", 25.5), (DESKTOP, ".plist .dh-list", 21)], ids=["phone", "desktop"])
def test_the_stepper_sits_on_the_title_by_its_ink(browser, page_url, vp, where, h):
    """Desktop: pill height = the 22 px title's ink (21). Phone: the user's pick T25b
    (2026-10-03) -- as tall as the title row (25.5 of 25.6 px, no taller or the row grows),
    with the desktop's glyphs (13 / 15 px); centred on the title by the ink all the same."""
    pg = browser.new_page(viewport=vp, device_scale_factor=K, java_script_enabled=False)
    pg.goto(page_url)
    pg.evaluate("document.getElementById('pg-d2').checked=true")
    pg.wait_for_timeout(300)
    sel = f'section[data-pg="d2"] {where}'
    box = lambda q: pg.eval_on_selector(q, "e=>{const r=e.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom]}")
    t, s = box(f"{sel} .dht"), box(f"{sel} .dstep")
    arrow = box(f"{sel} .dstep > :last-child")
    d = pg.evaluate(f"""(()=>{{const n=document.querySelector('{sel} .dstep .dn').firstChild,r=document.createRange();
        r.setStart(n,0);r.setEnd(n,1);const q=r.getBoundingClientRect();return [q.left,q.right]}})()""")
    img = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
    pg.close()
    title = _rows(img, (t[0] * K, (t[1] - 6) * K, t[2] * K, (t[3] + 6) * K), lambda c: sum(c) < 200)
    bg = img.getpixel((int((s[0] - 6) * K), int((s[1] - 4) * K)))     # the panel just beside the pill
    pill = _rows(img, ((s[0] + 4) * K, (s[1] - 4) * K, (s[0] + 30) * K, (s[3] + 4) * K),
                 lambda c: sum(abs(a - b) for a, b in zip(c, bg)) > 24)
    centre = lambda r: (r[0] + r[-1]) / 2 / K
    pc = centre(pill)
    arr = _rows(img, (arrow[0] * K + 1, (s[1] - 2) * K, arrow[2] * K - 1, (s[3] + 2) * K), lambda c: sum(c) < 300)
    txt = _rows(img, (d[0] * K + 1, (s[1] - 2) * K, d[1] * K - 1, (s[3] + 2) * K), lambda c: sum(c) < 500)
    # WebKit (the iPhone) decides: it holds 0.5 px wherever the title lands. Chromium snaps
    # glyphs to whole pixels, so its arrow reads 0.25-1.25 px depending on the title's
    # fractional y (probed 2026-10-02 by nudging the title in 0.25 px steps)
    tol = 0.5 if browser.engine == "webkit" else 1.25
    got = {"pill_h": (pill[-1] - pill[0]) / K, "pill": pc - centre(title), "arrow": centre(arr) - pc, "text": centre(txt) - pc}
    assert abs(got["pill_h"] - h) <= 0.75, got
    assert all(abs(got[k]) <= tol for k in ("pill", "arrow", "text")), got


def test_the_desktop_list_keeps_the_scrollbar_track_on_every_day(open_page, hakodate_url):
    """The user's check: Day 1's list did not scroll, had no bar, and its stepper sat one bar
    width further right than Day 2's. Every day shows the track (a day that does not scroll
    has nothing to drag), so the stepper holds the same x."""
    pg = open_page(DESKTOP, js=False, url=hakodate_url)
    # the fixture's days are alike; an opened stop (with its photo) makes D2 outgrow its panel
    pg.evaluate("document.getElementById('pg-d2').checked=true")
    sid = pg.eval_on_selector('section[data-pg="d2"] .plist .stop:has(figure.bp)', "e=>e.id")
    pg.evaluate(f"location.hash='#{sid}'")
    seen = {}
    for i in range(1, pg.locator("section.page.day").count() + 1):
        pg.evaluate(f"document.getElementById('pg-d{i}').checked=true")
        pg.wait_for_timeout(100)
        seen[i] = pg.evaluate(f"""(l=>[getComputedStyle(l).overflowY,l.offsetWidth-l.clientWidth,l.scrollHeight>l.clientHeight,
            Math.round(l.querySelector('.dstep').getBoundingClientRect().right)])(document.querySelector('section[data-pg=d{i}] .plist'))""")
    assert any(v[2] for v in seen.values()) and not all(v[2] for v in seen.values()), ("fixture: need a day that scrolls and one that does not", seen)
    assert all(v[0] == "scroll" for v in seen.values()), seen
    assert len({v[1] for v in seen.values()}) == 1 and len({v[3] for v in seen.values()}) == 1, seen
