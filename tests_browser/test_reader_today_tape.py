"""v2.2 today's tape: during the trip the home calendar's stamp for today wears a strip of paper
tape (scripts/render/reader/tapes.py picks it, PUBLISH_JS says which day is today). Outside the
trip, in the check build, or with no script, no stamp wears one."""
import pytest
from conftest import DESKTOP, PHONE

TAPE = """(id=>{const r=[...document.querySelectorAll('.page.home label.stamp[for="'+id+'"]')].filter(e=>e.offsetParent)[0];
  const b=getComputedStyle(r,'::before'),sr=r.getBoundingClientRect();
  return {today:r.classList.contains('today'),content:b.content,w:parseFloat(b.width),h:parseFloat(b.height),
          mask:b.maskImage||b.webkitMaskImage,bg:b.backgroundImage,s:r.offsetWidth,cx:sr.x+sr.width/2,cy:sr.y+sr.height/2}})"""
TODAYS = "document.querySelectorAll('.page.home .stamp.today').length"


def _fake_today(pg, iso):
    pg.add_init_script(f"(()=>{{const T=new Date('{iso}T10:00:00').getTime(),D=Date;"
                       "window.Date=class extends D{constructor(...a){super(...(a.length?a:[T]))}static now(){return T}}})()")


def _home(browser, url, viewport, iso, js=True):
    pg = browser.new_page(viewport=viewport, java_script_enabled=js)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    if iso:
        _fake_today(pg, iso)
    pg.goto(url)
    pg.wait_for_timeout(400)
    if js:          # today opens its day page: come back to the overview, where the tape is
        pg.evaluate("(r=>{r.checked=true;r.dispatchEvent(new Event('change',{bubbles:true}))})(document.getElementById('pg-home'))")
        pg.wait_for_timeout(400)
    return pg, errs


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["phone", "desktop"])
def test_todays_stamp_wears_its_tape(browser, publish_url, viewport):
    from tests import reader_fixture as R
    pg, errs = _home(browser, publish_url, viewport, R.itinerary()["days"][1]["date"])
    assert pg.evaluate(TODAYS) == 1
    t = pg.evaluate(TAPE, "pg-d2")
    assert t["today"] and t["content"] not in ("none", "normal")
    assert "data:image/svg+xml" in t["mask"] and "gradient" in t["bg"]
    # 32 x 11 on the phone; on the desktop it grows with the stamp (70 x 23 for a 65 px stamp)
    want = (32, 11) if viewport is PHONE else (t["s"] * 70 / 65, t["s"] * 23 / 65)
    assert t["w"] == pytest.approx(want[0], abs=.5) and t["h"] == pytest.approx(want[1], abs=.5)
    for other in ("pg-d1", "pg-d3"):
        assert pg.evaluate(TAPE, other)["content"] in ("none", "normal")
    assert not errs
    pg.close()


def test_the_tape_sits_at_the_stamps_lower_right(browser, publish_url):
    """Below and right of the stamp's centre, clear of the date and the ring text above."""
    from tests import reader_fixture as R
    pg, _ = _home(browser, publish_url, PHONE, R.itinerary()["days"][1]["date"])
    r = pg.evaluate("""(()=>{const s=document.querySelector('.page.home .stamp.today'),t=getComputedStyle(s,'::before');
      return [parseFloat(t.left)+parseFloat(t.width)/2-s.clientWidth/2,parseFloat(t.top)+parseFloat(t.height)/2-s.clientHeight/2]})()""")
    assert r == pytest.approx([13, 13], abs=.5)
    pg.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["phone", "desktop"])
def test_no_tape_outside_the_trip(browser, publish_url, viewport):
    pg, errs = _home(browser, publish_url, viewport, "2026-01-05")
    assert pg.evaluate(TODAYS) == 0 and not errs
    pg.close()


def test_no_tape_without_script(browser, publish_url):
    """The no-script viewers (the iPhone Claude app's preview) cannot know the date."""
    from tests import reader_fixture as R
    pg, _ = _home(browser, publish_url, PHONE, R.itinerary()["days"][1]["date"], js=False)
    assert pg.evaluate(TODAYS) == 0
    pg.close()


def test_a_link_into_the_page_still_tapes_today(browser, publish_url):
    """A link that lands elsewhere keeps the overview where it is, and today still wears its tape."""
    from tests import reader_fixture as R
    pg = browser.new_page(viewport=PHONE)
    _fake_today(pg, R.itinerary()["days"][1]["date"])
    pg.goto(publish_url + "#t-d1-s1")
    pg.wait_for_timeout(400)
    assert pg.evaluate(TODAYS) == 1
    assert pg.evaluate("document.querySelector('.page.home .stamp.today').getAttribute('for')") == "pg-d2"
    pg.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["phone", "desktop"])
def test_the_dark_theme_deepens_the_tape(browser, publish_url, viewport):
    """Half-clear ink loses its colour on the dark page: the dark theme scales it up (--tk) and
    lightens the dots -- checked on the stamp the tape is painted from, in both engines."""
    from tests import reader_fixture as R
    pg, errs = _home(browser, publish_url, viewport, R.itinerary()["days"][1]["date"])
    tk = "getComputedStyle(document.querySelector('.page.home .stamp.today')).getPropertyValue('--tk').trim()"
    assert pg.evaluate(tk) == ""                               # light: the default, 1
    pg.evaluate("document.getElementById('theme').checked=true")
    pg.wait_for_timeout(100)
    assert pg.evaluate(tk) == "1.7" and not errs
    pg.close()
