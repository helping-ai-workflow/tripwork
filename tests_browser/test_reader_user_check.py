"""v1.1 user check after topic 7 (2026-10-02): the reader opens light; the phone map card
has no route line (the move rows already say it)."""
import pytest
from conftest import DESKTOP, PHONE

BG = "getComputedStyle(document.body).backgroundColor"


@pytest.mark.parametrize("vp", [PHONE, DESKTOP], ids=["phone", "desktop"])
def test_the_reader_opens_light_and_the_bubble_turns_it_dark(open_page, vp):
    pg = open_page(vp, js=False)
    light = pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()")
    assert light == "#f6f3ea"
    assert pg.evaluate("getComputedStyle(document.documentElement).colorScheme") == "light"
    pg.locator("label.bubble").click()
    assert pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()") == "#1b1814"


@pytest.mark.parametrize("vp", [PHONE, DESKTOP], ids=["phone", "desktop"])
def test_no_route_line_on_either_width(open_page, vp):
    """User check: the 路線列 repeated the move rows and showed only on some days."""
    pg = open_page(vp, js=False)
    assert pg.locator(".mapc .route, .pmap .route").count() == 0
    assert pg.locator(".mapc .chips").count() > 0


@pytest.mark.parametrize("vp", [{"width": 1024, "height": 700}, DESKTOP, {"width": 1920, "height": 1080}],
                         ids=["1024x700", "1366x768", "1920x1080"])
@pytest.mark.parametrize("pgid", ["home", "d2"])
def test_the_desktop_theme_button_sits_bottom_right(open_page, vp, pgid):
    """User pick W: the window's bottom-right corner (it was bottom-left)."""
    pg = open_page(vp, js=False)
    if pgid != "home":
        pg.evaluate(f"document.getElementById('pg-{pgid}').checked=true")
    b = pg.locator("label.bubble").bounding_box()
    assert vp["width"] - (b["x"] + b["width"]) <= 32 and vp["height"] - (b["y"] + b["height"]) <= 32, b


def test_the_phone_theme_button_stays_top_right(open_page):
    pg = open_page(PHONE, js=False)
    b = pg.locator("label.bubble").bounding_box()
    assert b["y"] < 60 and PHONE["width"] - (b["x"] + b["width"]) <= 24, b


@pytest.mark.parametrize("where", ["name", "address", "top-left", "bottom", "centre-gap"])
def test_a_tap_anywhere_on_the_driver_sheet_closes_it(open_page, tmp_path, where):
    """User check: on the phone the 給司機看 sheet closes wherever it is tapped, not only
    on ✕ -- and lands back on the stop, still open."""
    import copy
    from scripts.render.reader import render_reader
    from tests.reader_fixture import itinerary, poi_map, reader_kwargs
    pm = copy.deepcopy(poi_map())
    pm["hak-asaichi"].update(address_local="函館市若松町9-19", address_source="https://www.hakodate-asaichi.com/")
    f = tmp_path / "drv.html"
    f.write_text(render_reader(itinerary(), pm, **reader_kwargs()), encoding="utf-8")
    pg = open_page(PHONE, js=False, url=f.as_uri())
    pg.evaluate("document.getElementById('pg-d2').checked=true")
    st = pg.eval_on_selector('section[data-pg="d2"] .stop[data-poi="hak-asaichi"]', "e => e.id")
    pg.evaluate(f"location.hash='#{st}-drv'")
    pg.wait_for_timeout(200)
    sheet = pg.locator(f"#{st}-drv")
    assert sheet.is_visible()
    box = {"name": lambda: pg.locator(f"#{st}-drv .drvn").bounding_box(),
           "address": lambda: pg.locator(f"#{st}-drv .drva").bounding_box()}
    if where in box:
        b = box[where]()
        x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    else:
        x, y = {"top-left": (12, 12), "bottom": (PHONE["width"] / 2, PHONE["height"] - 20),
                "centre-gap": (PHONE["width"] / 2, PHONE["height"] / 2 + 140)}[where]
    pg.mouse.click(x, y)
    pg.wait_for_timeout(250)
    assert not sheet.is_visible()
    assert pg.evaluate(f"getComputedStyle(document.querySelector('#{st} .in')).display") != "none"
