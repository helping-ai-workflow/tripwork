"""Headless-Chromium interaction checks for the reader (spec §7). Not part of the
default `pytest` sweep (testpaths = tests): run with `python -m pytest tests_browser`
after `pip install -e ".[dev,browser]"` and `python -m playwright install --with-deps chromium webkit`.
CI runs them in .github/workflows/browser.yml when the reader, export-gate, fonts or
icons change.

The page under test is the release e2e tour (tests/e2e_v1_fixture.py) rendered by the
shipped reader with a day-maps side-file built by the shipped generator from injected
tiles -- the same page tests/test_e2e_v1_release.py gates."""
import io
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PHONE = {"width": 390, "height": 844}
DESKTOP = {"width": 1366, "height": 768}


def _tile(z, x, y):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (256, 256), ((x * 67) % 256, (y * 131) % 256, 180)).save(buf, "PNG")
    return buf.getvalue()


def build_pages(root):
    """Write the two pages under test into root and return their paths. A plain
    function so tests/test_browser_workflow.py can build exactly these pages and see
    which modules that loads."""
    from scripts.day_maps import build
    from scripts.gate import chosen_lodging_pois
    from scripts.paths import artifact_path
    from scripts.render.reader import render_reader
    from tests import e2e_v1_fixture as F
    from tests import mech_fixtures as M
    from tests import reader_fixture as R

    root = pathlib.Path(root)
    t, w = M.build_full_trip(root, slug="2026-10-hokkaido")
    acc = F.accommodations()
    for name, doc in (("verified-pois.yaml", {"pois": F.pois()}), ("accommodations.yaml", acc),
                      ("legs.yaml", F.LEGS), ("itinerary.yaml", F.tour())):
        M.write_artifact(artifact_path(t, name), doc)
    maps = build(t, w, fetch=_tile)
    pm = {p["id"]: p for p in F.pois() + chosen_lodging_pois(acc)}
    tour = root / "tour.html"
    tour.write_text(render_reader(F.tour(), pm, brief=F.tour_brief(), accommodations=acc,
                                  advisory=R.ADVISORY, legs=F.LEGS, maps=maps), encoding="utf-8")
    # the Hakodate D2 (photo, four stops, an alternative) is long enough that the list
    # really scrolls at 1366x768, which the centring check needs -- on a list that
    # fits, every stop is 'bounded' and nothing is measured
    hakodate = root / "hakodate.html"
    hakodate.write_text(render_reader(R.itinerary(), R.poi_map(), **R.reader_kwargs()), encoding="utf-8")
    many = root / "many-stays.html"
    m_itin, m_pm, m_kw = _many_stays(R)
    many.write_text(render_reader(m_itin, m_pm, **m_kw), encoding="utf-8")
    rings = root / "rings.html"
    r_itin, r_pm, r_kw = _long_rings(R)
    rings.write_text(render_reader(r_itin, r_pm, **r_kw), encoding="utf-8")
    picker = root / "picker.html"                        # v1.1 topic 7: the title picker
    from scripts.title_picker import page as picker_page
    from tests.mech_fixtures import brief_name_fields
    picker.write_text(picker_page(R.itinerary(), dict(R.brief(), **brief_name_fields()),
                                  R.reader_kwargs()["accommodations"]), encoding="utf-8")
    # v1.2: the publish build's phone page (PUBLISH_JS), the check build of the same
    # fixture as its pixel baseline, a trip across two months (the calendar's fold height
    # differs per day) and a one-day trip (no neighbour to swipe to)
    import copy
    import datetime
    pub = root / "publish.html"
    pub.write_text(render_reader(R.itinerary(), R.poi_map(), build="publish", **R.reader_kwargs()), encoding="utf-8")
    chk = root / "check.html"
    chk.write_text(render_reader(R.itinerary(), R.poi_map(), **R.reader_kwargs()), encoding="utf-8")
    two = copy.deepcopy(R.itinerary())
    while len(two["days"]) < 3:
        two["days"].append(copy.deepcopy(two["days"][1]))
    for k, d in enumerate(two["days"]):
        d["date"] = (datetime.date(2026, 8, 30) + datetime.timedelta(days=k)).isoformat()
    two_month = root / "two-month.html"
    two_month.write_text(render_reader(two, R.poi_map(), build="publish", **R.reader_kwargs()), encoding="utf-8")
    one = dict(copy.deepcopy(R.itinerary()), days=copy.deepcopy(R.itinerary()["days"][:1]))
    one_day = root / "one-day.html"
    one_day.write_text(render_reader(one, R.poi_map(), build="publish", **R.reader_kwargs()), encoding="utf-8")
    return {"tour": tour, "hakodate": hakodate, "many": many, "rings": rings, "picker": picker,
            "publish": pub, "check": chk, "two_month": two_month, "one_day": one_day}


def _long_rings(R):
    """Review I3: the worst case for the desktop stamp rings -- 15 trip days in a six-week
    month (August 2026 starts on a Saturday), side by side and stacked, each theme at the
    ring's 15-character cap."""
    import copy
    import datetime
    base = R.itinerary()
    days = []
    for k in range(15):
        d = copy.deepcopy(base["days"][1])
        d["date"] = (datetime.date(2026, 8, 17) + datetime.timedelta(days=k)).isoformat()
        d["theme"] = "看熊看地獄谷，晚上吃壽司配啤酒"[:15]
        days.append(d)
    return dict(base, days=days), copy.deepcopy(R.poi_map()), R.reader_kwargs()


def _many_stays(R):
    """v1.1 topic 6: a made-up 11-day loop with ten one-night stays (each its own area
    and lodging), so the home's 旅程與費用 card has to scroll inside itself."""
    import copy
    import datetime
    base = R.itinerary()
    pm = copy.deepcopy(R.poi_map())
    lodge = pm["hak-hotel"]
    days, stops, items = [], [], []
    for k in range(11):
        d = copy.deepcopy(base["days"][1])
        d["date"] = (datetime.date(2026, 11, 9) + datetime.timedelta(days=k)).isoformat()
        d["theme"] = f"第{k + 1}天的標題"
        if k < 10:
            lid = f"lodge-{k}"
            pm[lid] = dict(lodge, id=lid, name_zh=f"第{k + 1}間旅館")
            d["lodging"] = lid
            stops.append({"area_label": f"地區{k + 1}", "chosen": lid, "nights": 1, "candidates": [dict(lodge, id=lid)]})
            items.append({"category": "lodging", "label": lid, "amount": 10000 + k, "poi_id": lid})
        else:
            d.pop("lodging", None)
        days.append(d)
    itin = dict(base, days=days)
    kw = R.reader_kwargs()
    kw["accommodations"] = {"stops": stops}
    kw["cost"] = {"currency": "JPY", "total": 200000, "by_category": {"lodging": 100045, "transport": 99955},
                  "line_items": items + [{"category": "transport", "label": "t", "amount": 99955}]}
    return itin, pm, kw


@pytest.fixture(scope="session")
def pages(tmp_path_factory):
    return build_pages(tmp_path_factory.mktemp("reader"))


@pytest.fixture(scope="session")
def page_url(pages):
    return pages["tour"].as_uri()


@pytest.fixture(scope="session")
def hakodate_url(pages):
    return pages["hakodate"].as_uri()


@pytest.fixture(scope="session")
def many_stays_url(pages):
    return pages["many"].as_uri()


@pytest.fixture(scope="session")
def long_rings_url(pages):
    return pages["rings"].as_uri()


@pytest.fixture(scope="session")
def picker_url(pages):
    return pages["picker"].as_uri()


@pytest.fixture(scope="session")
def publish_url(pages):
    return pages["publish"].as_uri()


@pytest.fixture(scope="session")
def check_url(pages):
    return pages["check"].as_uri()


@pytest.fixture(scope="session")
def two_month_url(pages):
    return pages["two_month"].as_uri()


@pytest.fixture(scope="session")
def one_day_url(pages):
    return pages["one_day"].as_uri()


@pytest.fixture(scope="session")
def pw():
    """One Playwright driver for the session: the sync API refuses a second one in the
    same thread, so every browser -- the engine pair below and a test module's own
    Chromium (test_reader_publish.py's touch tests) -- is launched from this one."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session", params=["chromium", "webkit"])
def browser(request, pw):
    """Both engines: WebKit is the one iPhone previews (Files, LINE) run, and with
    JavaScript off it stands in for them (calibrated 2026-10-01 against the user's phone:
    same no-centring on v1.1 radios, same 1-in-3 on scroll-snap)."""
    b = getattr(pw, request.param).launch()
    b.engine = request.param
    yield b
    b.close()


@pytest.fixture
def open_page(browser, page_url):
    pages = []

    def make(viewport, js=True, url=None):
        pg = browser.new_page(viewport=viewport, java_script_enabled=js)
        pg.goto(url or page_url)
        pages.append(pg)
        return pg
    yield make
    for pg in pages:
        pg.close()
