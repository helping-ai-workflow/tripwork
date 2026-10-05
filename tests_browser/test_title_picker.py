"""v1.1 topic 7 (spec §7.3): the title picker in Chromium and WebKit, phone and desktop."""
import math

import pytest
from conftest import DESKTOP, PHONE

from scripts import title_picks
from tests import reader_fixture as R
from tests.mech_fixtures import brief_name_fields

VPS = pytest.mark.parametrize("vp", [PHONE, DESKTOP], ids=["phone", "desktop"])


def _pick(pg, i, n):
    pg.locator(f'.col[data-i="{i}"] input[type=radio][value="{n}"]').locator("..").click()


@VPS
def test_a_tapped_line_goes_round_the_stamp_centred_on_its_tilt(open_page, picker_url, vp):
    pg = open_page(vp, url=picker_url)
    _pick(pg, 1, 2)                                     # day 1: the stamp turns -6 degrees
    want = pg.locator('.col[data-i="1"] input[type=radio][value="2"]').get_attribute("data-t")
    assert pg.locator('.col[data-i="1"] textPath').text_content() == want
    # the line is centred above the stamp, turned by the stamp's tilt: the mean of its
    # first and last glyph's angles (0 = straight up) equals the tilt
    ang, tilt = pg.evaluate("""()=>{const c=document.querySelector('.col[data-i="1"]'),t=c.querySelector('.ring text'),
      s=c.querySelector('.st').getBoundingClientRect(),cx=s.left+s.width/2,cy=s.top+s.height/2,n=t.getNumberOfChars();
      const a=k=>{const e=t.getExtentOfChar(k),p=new DOMPoint(e.x+e.width/2,e.y+e.height/2).matrixTransform(t.getScreenCTM());
        return Math.atan2(p.x-cx,cy-p.y)*180/Math.PI};
      return [(a(0)+a(n-1))/2,parseFloat(getComputedStyle(c.querySelector('.seal')).getPropertyValue('--t'))]}""")
    assert tilt == -6 and abs(ang - tilt) < 2, (ang, tilt)


def _blank_page(tmp_path):
    """A picker for a trip whose days have no title yet (only their candidates)."""
    from scripts.title_picker import page
    itin = R.itinerary()
    for d in itin["days"]:
        for k in ("theme", "theme_user_written", "theme_refs"):
            d.pop(k, None)
    f = tmp_path / "blank.html"
    f.write_text(page(itin, dict(R.brief(), **brief_name_fields()), R.reader_kwargs()["accommodations"]), encoding="utf-8")
    return f.as_uri()


@VPS
def test_the_button_waits_for_every_day_then_copies_a_line_title_picks_reads(open_page, tmp_path, vp, browser):
    pg = open_page(vp, url=_blank_page(tmp_path))
    n = pg.locator(".col").count()
    btn = pg.locator("#copy")
    assert btn.is_disabled() and btn.text_content() == f"還差 {n} 天"
    _pick(pg, 1, 3)
    pg.locator('.col[data-i="2"] .mb').click()                                  # 再給我 3 個
    pg.locator('.col[data-i="3"] .own').fill("海邊的「風」")                     # own words, quotes dropped
    assert not btn.is_disabled() and btn.text_content() == "複製選擇"
    assert pg.locator('.mini[data-i="1"] span').text_content() != "還沒選"
    line = pg.locator("#line").text_content()
    assert line == 'tripwork 標題 D1=3 D2=+ D3="海邊的風"'
    itin, brief = R.itinerary(), dict(R.brief(), **brief_name_fields())
    more = title_picks.apply(itin, brief, title_picks.parse(line))
    assert more == {"days": [2], "headline": False}
    assert itin["days"][0]["theme"] == pg.locator('.col[data-i="1"] input[value="3"]').get_attribute("data-t")
    assert itin["days"][2]["theme"] == "海邊的風"
    btn.click()
    assert btn.text_content() == "已複製，貼回對話"


def test_the_copy_lands_on_the_clipboard_or_says_to_copy_by_hand(browser, picker_url):
    """Chromium can read the clipboard back (with permission); WebKit cannot, so there the
    check is that the button reports an outcome and the line is on screen to copy."""
    chromium = browser.engine == "chromium"
    ctx = browser.new_context(viewport=DESKTOP, **({"permissions": ["clipboard-read", "clipboard-write"]} if chromium else {}))
    pg = ctx.new_page()
    pg.goto(picker_url)
    for i in range(1, pg.locator(".col").count() + 1):
        _pick(pg, i, 1)
    pg.locator("#copy").click()
    line = pg.locator("#line").text_content()
    assert line.startswith("tripwork 標題 D1=1") and pg.locator("#line").is_visible()
    if chromium:
        assert pg.evaluate("navigator.clipboard.readText()") == line
        assert pg.locator("#copy").text_content() == "已複製，貼回對話"
    else:
        assert pg.locator("#copy").text_content() in ("已複製，貼回對話", "請手動複製下面那行")
    ctx.close()


def test_changing_the_headline_adds_h_and_changing_back_removes_it(open_page, picker_url):
    pg = open_page(DESKTOP, url=picker_url)
    for i in range(1, pg.locator(".col").count() + 1):
        _pick(pg, i, 1)
    pg.locator('input[name=h][value="4"]').locator("..").click()
    assert " H=4 " in pg.locator("#line").text_content()
    assert pg.locator("#hn").text_content() == pg.locator('input[name=h][value="4"]').get_attribute("data-t")
    pg.locator('input[name=h][value="1"]').locator("..").click()
    assert " H=" not in pg.locator("#line").text_content()
    pg.locator("#h-more").locator("..").click()
    assert " H=+ " in pg.locator("#line").text_content()


@VPS
def test_without_scripts_it_is_a_numbered_list_with_the_reply_line(open_page, picker_url, vp):
    pg = open_page(vp, js=False, url=picker_url)
    assert pg.locator("#line").is_visible() and _shown(pg, "#line").startswith("tripwork 標題 D1=")
    assert pg.locator(".nsb").is_visible() and not pg.locator(".ns").count()
    assert pg.locator('.col[data-i="1"] .opt i').first.text_content() == "1"


def test_the_phone_scrolls_the_days_sideways_not_the_page(open_page, picker_url):
    pg = open_page(PHONE, url=picker_url)
    assert pg.evaluate("document.documentElement.scrollWidth<=innerWidth")
    assert pg.evaluate("(r=>r.scrollWidth>r.clientWidth)(document.querySelector('.row'))")
    # every line fits its column on one row
    assert pg.evaluate("[...document.querySelectorAll('.col .opt span')].every(s=>s.scrollWidth<=s.clientWidth+1)")


def test_a_regenerated_page_starts_on_every_days_current_title(open_page, tmp_path):
    from scripts.title_picker import page
    itin, brief = R.itinerary(), dict(R.brief(), **brief_name_fields())
    title_picks.apply(itin, brief, title_picks.parse('D1=2 D2="海邊的風" D3=+'))
    f = tmp_path / "again.html"
    f.write_text(page(itin, brief, R.reader_kwargs()["accommodations"]), encoding="utf-8")
    pg = open_page(DESKTOP, url=f.as_uri())
    assert pg.locator("#copy").text_content() == "複製選擇"
    assert pg.locator('.col[data-i="2"] textPath').text_content() == "海邊的風"
    assert pg.locator("#line").text_content() == f'tripwork 標題 D1=2 D2="海邊的風" D3="{itin["days"][2]["theme"]}"'
    _pick(pg, 3, 1)
    assert pg.locator("#line").text_content() == 'tripwork 標題 D1=2 D2="海邊的風" D3=1'
def test_each_ring_is_drawn_in_its_stamps_colour(open_page, picker_url):
    """The user's check: a blue (r1) stamp's ring text came out black."""
    pg = open_page(DESKTOP, url=picker_url)
    for i in range(1, pg.locator(".col").count() + 1):
        _pick(pg, i, 1)
    got = pg.evaluate("""[...document.querySelectorAll('.col')].map(c=>[getComputedStyle(c.querySelector('.ring text')).fill,
        getComputedStyle(c.querySelector('.st')).color])""")
    assert all(fill == colour for fill, colour in got), got


# --- the user's check: one sheet that does not scroll (pick L2, headline first) ---

SIZES = pytest.mark.parametrize("vp", [PHONE, {"width": 1024, "height": 700}, DESKTOP],
                                ids=["phone", "1024x700", "1366x768"])
MASK = "(e=>{const s=getComputedStyle(e);return (s.maskImage||s.webkitMaskImage||'')})"


@SIZES
def test_the_page_is_one_sheet_that_does_not_scroll(open_page, picker_url, vp):
    pg = open_page(vp, url=picker_url)
    assert pg.evaluate("document.documentElement.scrollHeight<=innerHeight+1")
    assert pg.evaluate("Math.round(document.querySelector('.bar').getBoundingClientRect().bottom)") == vp["height"]


@SIZES
def test_the_headline_is_the_first_card_and_every_card_scrolls_inside(open_page, picker_url, vp):
    pg = open_page(vp, url=picker_url)
    first = pg.locator(".row > .card").first
    assert "hcard" in first.get_attribute("class") and first.locator("input[name=h]").count() == 6
    assert pg.locator(".row > .card.col").count() == pg.locator(".mini").count()
    # the lines scroll inside each card with the trip card's fade; the row with the chips' fade
    assert pg.evaluate(f"[...document.querySelectorAll('.card .lines')].every(l=>getComputedStyle(l).overflowY==='auto'&&{MASK}(l).includes('gradient'))")
    assert "gradient" in pg.evaluate(f"{MASK}(document.querySelector('.row'))")


def _longest_page(tmp_path):
    """The widest line a day can have: 13 characters with a rhyme tag (燈 ㄉㄥ / 星 ㄒㄧㄥ)."""
    from scripts.title_picker import page
    itin = R.itinerary()
    itin["days"][0]["theme_candidates"][5]["text"] = "湖邊冷冷的燈，山頂的一顆星"
    f = tmp_path / "long.html"
    f.write_text(page(itin, dict(R.brief(), **brief_name_fields()), R.reader_kwargs()["accommodations"]), encoding="utf-8")
    return f.as_uri()


@SIZES
def test_no_line_is_cut(open_page, tmp_path, vp):
    pg = open_page(vp, url=_longest_page(tmp_path))
    assert pg.locator('.col[data-i="1"] .opt:has-text("一顆星") .rm').count() == 1     # its tag is drawn
    # two ways a line gets cut: its box runs past the card's edge, or the card squeezes the
    # box and the text runs out of it (scrollWidth) -- check both
    cut = pg.evaluate("""[...document.querySelectorAll('.card')].flatMap(c=>{const r=c.getBoundingClientRect().right;
        return [...c.querySelectorAll('.opt span')].filter(s=>s.getBoundingClientRect().right>r-1||s.scrollWidth>s.clientWidth+1).map(s=>s.textContent)})""")
    assert cut == [], cut


# --- v1.2.1: a preview that runs no script (the Claude Code app's HTML preview, LINE,
# iPhone Files) showed every day picked while the button stayed at 還差 N 天: the picks
# are CSS, the button and the line were script. The line now follows the picks in CSS.

def _shown(pg, sel):
    return pg.locator(sel).inner_text().strip()


@VPS
def test_without_scripts_the_line_follows_the_picks_and_copies_by_hand(open_page, picker_url, vp):
    pg = open_page(vp, js=False, url=picker_url)
    days = pg.locator(".col").count()
    for i in range(1, days + 1):
        _pick(pg, i, 2)
    want = "tripwork 標題 " + " ".join(f"D{i}=2" for i in range(1, days + 1))
    assert _shown(pg, "#line") == want
    # selecting the line and copying gives exactly that line (hidden pieces stay out)
    got = pg.evaluate("(()=>{const s=getSelection();s.selectAllChildren(document.getElementById('line'));return s.toString().trim()})()")
    assert got == want
    assert not pg.locator("#copy").is_visible()              # a button that can never work is not shown
    for i in range(1, days + 1):
        title = pg.locator(f'.col[data-i="{i}"] input[type=radio][value="2"]').get_attribute("data-t")
        assert _shown(pg, f'.mini[data-i="{i}"]').endswith(title)


@VPS
def test_without_scripts_the_line_carries_more_own_words_and_the_headline(open_page, picker_url, vp):
    pg = open_page(vp, js=False, url=picker_url)
    days = pg.locator(".col").count()
    for i in range(1, days + 1):
        if i != 2:
            _pick(pg, i, 1)
    pg.locator('.col[data-i="1"] .mb').click()                # 再給我 3 個
    # own words (typed in the reply). Without a script a tap cannot empty the box, so a
    # line tapped on the same day would win over editing the words the page started with
    pg.locator('.col[data-i="2"] .own').fill("海邊的風")
    pg.locator('input[name=h][value="2"]').locator("..").click()
    line = _shown(pg, "#line")
    assert line.startswith("tripwork 標題 H=2 D1=+ D2=\""), line
    assert " D2=1" not in line


def test_with_scripts_the_line_shows_while_days_are_missing(open_page, picker_url):
    pg = open_page(DESKTOP, url=picker_url)
    days = pg.locator(".col").count()
    for i in range(1, days + 1):
        pg.evaluate(f"setDay({i},null)")
    _pick(pg, 1, 2)
    assert _shown(pg, "#line") == "tripwork 標題 D1=2 " + " ".join(f"D{i}=?" for i in range(2, days + 1))


def test_without_scripts_a_day_not_picked_reads_as_a_question_mark(open_page, tmp_path):
    from scripts.title_picker import page
    itin, brief = R.itinerary(), dict(R.brief(), **brief_name_fields())
    for d in itin["days"]:
        d.pop("theme", None)
        d.pop("theme_user_written", None)
    f = tmp_path / "fresh.html"
    f.write_text(page(itin, brief, R.reader_kwargs()["accommodations"]), encoding="utf-8")
    pg = open_page(DESKTOP, js=False, url=f.as_uri())
    days = pg.locator(".col").count()
    assert _shown(pg, "#line") == "tripwork 標題 " + " ".join(f"D{i}=?" for i in range(1, days + 1))
    assert _shown(pg, '.mini[data-i="1"]').endswith("還沒選")
    _pick(pg, 1, 3)
    assert _shown(pg, "#line").startswith("tripwork 標題 D1=3 D2=?")
    assert not _shown(pg, '.mini[data-i="1"]').endswith("還沒選")


# --- v1.2.1 (the user): the bar's stamps were cut at the edges and had no place name,
# unlike the real stamp. They are the reader's day-page mini stamp now.

STAMP = """e => { const s = getComputedStyle(e), b = getComputedStyle(e.querySelector('b')), sm = e.querySelector('small');
  return {w: e.offsetWidth, border: s.borderTopWidth + ' ' + s.borderTopStyle, outline: s.outlineWidth + ' ' + s.outlineStyle,
          offset: s.outlineOffset, bg: s.backgroundColor, color: s.color, transform: s.transform, date: b.fontSize,
          area: sm ? getComputedStyle(sm).fontSize : null, text: sm ? sm.textContent : null} }"""


@VPS
def test_the_bars_stamps_are_the_readers_mini_stamps(browser, picker_url, hakodate_url, vp):
    reader = browser.new_page(viewport=PHONE)
    reader.goto(hakodate_url)
    reader.evaluate("document.getElementById('pg-d1').checked=true")
    reader.wait_for_timeout(300)
    picker = browser.new_page(viewport=vp)
    picker.goto(picker_url)
    days = picker.locator(".mini").count()
    for i in range(1, days + 1):
        # day 1's page draws day i's stamp; the current day is filled, so compare the others
        page = "d2" if i == 1 else "d1"
        reader.evaluate(f"document.getElementById('pg-{page}').checked=true")
        reader.wait_for_timeout(300)
        want = reader.evaluate(STAMP, reader.locator(f"section[data-pg={page}] .pcal .mini .stamp[for=pg-d{i}]").element_handle())
        got = picker.evaluate(STAMP, picker.locator(f'.mini[data-i="{i}"] i').element_handle())
        assert got == want, (i, got, want)
    reader.close()
    picker.close()


@VPS
def test_no_stamp_in_the_bar_is_cut(open_page, picker_url, vp):
    pg = open_page(vp, url=picker_url)
    cut = pg.evaluate("""(() => { const st = document.querySelector('.strip'), r = st.getBoundingClientRect();
      return [...document.querySelectorAll('.mini i')].map(i => { const b = i.getBoundingClientRect(), s = getComputedStyle(i),
        ring = parseFloat(s.outlineOffset) + parseFloat(s.outlineWidth), cx = (b.left + b.right) / 2, cy = (b.top + b.bottom) / 2,
        rad = i.offsetWidth / 2 + ring;
        return {top: cy - rad - r.top, bottom: r.bottom - (cy + rad), left: cx - rad - r.left} })
        .filter(x => x.top < -0.01 || x.bottom < -0.01 || x.left < -0.01) })()""")
    assert not cut, cut
