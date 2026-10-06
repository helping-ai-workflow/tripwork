"""v2.1.0 D10 in both engines (WebKit is the iPhone): the first day's map starts at home,
the last day's ends there, and home's pin is drawn inside its frame."""
import pytest
import yaml

from tests_browser.conftest import PHONE, _tile


@pytest.fixture(scope="module")
def home_url(tmp_path_factory):
    from scripts.day_maps import build
    from scripts.paths import artifact_path
    from scripts.render.reader import render_reader
    from scripts.render.reader.maps import LABELS
    from tests.test_home_points import POIS, _trip_dir
    root = tmp_path_factory.mktemp("home")
    t = _trip_dir(root)
    maps = build(t, root / "work" / "t", fetch=_tile)
    load = lambda n: yaml.safe_load(artifact_path(t, n).read_text(encoding="utf-8"))
    page = root / "home.html"
    page.write_text(render_reader(load("itinerary.yaml"), POIS, brief=load("trip-brief.yaml"),
                                  legs=load("legs.yaml"), maps=maps), encoding="utf-8")
    return page.as_uri(), LABELS


def test_home_pin_on_first_and_last_day(open_page, home_url):
    url, labels = home_url
    pg = open_page(PHONE, js=False, url=url)
    for d, chip, pid in ((1, 1, "home-origin"), (2, -1, "home-return")):
        pg.evaluate(f"document.getElementById('pg-d{d}').checked=true;"
                    f"document.querySelector('section[data-pg=d{d}] .mapc').open=true")
        chips = pg.eval_on_selector_all(f"section[data-pg=d{d}] .mapc .chips a.chip", "es=>es.map(e=>e.textContent)")
        assert chips[chip] == (labels["home_start"] if d == 1 else labels["home_end"])
        inside = pg.evaluate(f"""(()=>{{const v=document.querySelector('section[data-pg=d{d}] .mv-d{d}-all');
            const p=v.querySelector('g.pin[data-poi="{pid}"] circle');if(!p)return null;
            const f=p.closest('.mframe').getBoundingClientRect(),c=p.getBoundingClientRect();
            return c.left>=f.left&&c.right<=f.right&&c.top>=f.top&&c.bottom<=f.bottom}})()""")
        assert inside is True, (d, inside)
