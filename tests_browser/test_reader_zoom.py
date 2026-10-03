"""v1.1 topic 6 Z1-a + close rule A: the zoomed map and photo close on the image, the dark
layer or ✕; only the OSM / photo-source link opens a page. The small-map credit is plain
text, so tapping it zooms like the rest of the map."""
import pytest
from conftest import DESKTOP, PHONE


def _open_map(pg):
    pg.evaluate("document.getElementById('pg-d2').checked=true")
    pg.evaluate("(()=>{const d=document.querySelector('section[data-pg=d2] .pmap details');if(d)d.open=true})()")
    return pg.locator("section[data-pg=d2] .mframe:has(.attrmini)").filter(visible=True).first


@pytest.mark.parametrize("vp", [PHONE, DESKTOP], ids=["phone", "desktop"])
@pytest.mark.parametrize("how", ["map", "dark", "x"])
def test_the_zoomed_map_closes_three_ways(open_page, vp, how):
    pg = open_page(vp, js=False)
    f = _open_map(pg)
    zid = f.get_attribute("for")
    f.click(position={"x": 12, "y": 12})
    checked = f"document.getElementById('{zid}').checked"
    assert pg.evaluate(checked) is True
    if how == "map":
        pg.locator(f"label.mframe[for='{zid}']").filter(visible=True).first.click(position={"x": 12, "y": 12})
    elif how == "dark":
        pg.mouse.click(3, 3)
    else:
        pg.locator(f".zbar label.zx[for='{zid}']").filter(visible=True).click()
    assert pg.evaluate(checked) is False


@pytest.mark.parametrize("vp", [PHONE, DESKTOP], ids=["phone", "desktop"])
def test_the_osm_link_opens_and_keeps_the_zoom(open_page, vp):
    """The link is followed in a new page (target=_blank; its URL is pinned by the unit
    test) and the zoom stays as it was."""
    pg = open_page(vp, js=False)
    seen = []
    # Chromium routes the popup's request (and opens no page on a 204); WebKit opens the
    # page without routing it -- either one shows the link was followed
    pg.context.route("https://www.google.com/maps/**", lambda r: (seen.append("request"), r.fulfill(status=204)))
    pg.context.on("page", lambda _p: seen.append("page"))
    f = _open_map(pg)
    zid = f.get_attribute("for")
    f.click(position={"x": 12, "y": 12})
    pg.locator(f".mv:has(#{zid}) .zbar a.zlink").click()
    for _ in range(30):
        if seen:
            break
        pg.wait_for_timeout(100)
    assert seen, "the link was not followed"
    assert pg.evaluate(f"document.getElementById('{zid}').checked") is True


def test_tapping_the_small_credit_zooms(open_page):
    pg = open_page(PHONE, js=False)
    f = _open_map(pg)
    zid = f.get_attribute("for")
    f.locator(".attrmini").click()
    assert pg.evaluate(f"document.getElementById('{zid}').checked") is True


@pytest.mark.parametrize("how", ["photo", "dark", "x"])
def test_the_fullscreen_photo_closes_three_ways(open_page, hakodate_url, how):
    pg = open_page(PHONE, js=False, url=hakodate_url)
    pg.evaluate("document.getElementById('pg-d2').checked=true")
    stop = pg.locator("section[data-pg=d2] .stop:has(figure.bp)").first
    stop.locator("a.hd-open").click()
    pg.wait_for_timeout(300)                     # the stop opens with a transition
    lab = stop.locator("label.bpz")
    pid = lab.get_attribute("for")
    lab.click()
    pg.wait_for_timeout(300)
    checked = f"document.getElementById('{pid}').checked"
    assert pg.evaluate(checked) is True
    if how == "photo":
        lab.click(position={"x": 30, "y": 30})
    elif how == "dark":
        pg.mouse.click(3, 3)
    else:
        stop.locator(f".zbar label.zx[for='{pid}']").click()
    assert pg.evaluate(checked) is False


@pytest.mark.parametrize("vp", [PHONE, DESKTOP, {"width": 1024, "height": 700}], ids=["phone", "desktop", "1024x700"])
def test_a_click_anywhere_around_the_zoomed_map_closes_it(open_page, vp):
    """The user's check: on the desktop a click beside the enlarged map left it open --
    the frame's wrapper covered the window above the dark layer. Every point around the
    map, and the gap between the bar's two buttons, closes it."""
    pg = open_page(vp, js=False)
    f = _open_map(pg)
    zid = f.get_attribute("for")
    checked = f"document.getElementById('{zid}').checked"
    w, h = vp["width"], vp["height"]
    left_open = []
    for name, (x, y) in {"top-left": (10, 10), "top-right": (w - 10, 10), "bottom-left": (10, h - 10),
                         "bottom-right": (w - 10, h - 10), "left": (10, h / 2), "right": (w - 10, h / 2)}.items():
        f.click(position={"x": 12, "y": 12})
        assert pg.evaluate(checked) is True
        pg.mouse.click(x, y)
        if pg.evaluate(checked):
            left_open.append((name, pg.evaluate(f"(e=>e&&e.tagName+'.'+e.className)(document.elementFromPoint({x},{y}))")))
            pg.evaluate(f"document.getElementById('{zid}').checked=false")
    f.click(position={"x": 12, "y": 12})
    fr = pg.locator(f"label.mframe[for='{zid}']").filter(visible=True).first.bounding_box()
    for name, (x, y) in {"beside-left": (fr["x"] - 8, fr["y"] + fr["height"] / 2),
                         "beside-right": (fr["x"] + fr["width"] + 8, fr["y"] + fr["height"] / 2)}.items():
        if 0 < x < w:
            pg.mouse.click(x, y)
            if pg.evaluate(checked):
                left_open.append((name, pg.evaluate(f"(e=>e&&e.tagName+'.'+e.className)(document.elementFromPoint({x},{y}))")))
                pg.evaluate(f"document.getElementById('{zid}').checked=false")
            f.click(position={"x": 12, "y": 12})
    pg.locator(f".mv:has(#{zid}) .zbar").scroll_into_view_if_needed()   # a split day stacks two maps
    bar = pg.locator(f".mv:has(#{zid}) .zbar").bounding_box()
    a = pg.locator(f".mv:has(#{zid}) .zbar .zlink").bounding_box()
    x = pg.locator(f".mv:has(#{zid}) .zbar .zx").bounding_box()
    gap = ((a["x"] + a["width"] + x["x"]) / 2, bar["y"] + bar["height"] / 2)
    pg.mouse.click(*gap)
    if pg.evaluate(checked):
        left_open.append(("bar-gap", None))
    assert left_open == [], left_open
