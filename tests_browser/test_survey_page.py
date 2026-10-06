"""v2.1.0 §10: the survey's list page on a phone, both engines, no script: it fits the
width, a card opens by its anchor, and its edges line up with the headings."""
import pytest

from tests_browser.conftest import PHONE


@pytest.fixture(scope="module")
def survey_url(tmp_path_factory):
    from scripts.render.survey_page import render
    from tests.test_survey_page import BRIEF, POIS
    f = tmp_path_factory.mktemp("survey") / "list.html"
    f.write_text(render(POIS, BRIEF), encoding="utf-8")
    return f.as_uri()


def test_the_list_fits_and_opens_without_script(open_page, survey_url):
    pg = open_page(PHONE, js=False, url=survey_url)
    m = pg.evaluate("""(()=>{const x=s=>{const r=document.querySelector(s).getBoundingClientRect();return [Math.round(r.left),Math.round(r.right)]};
      return {scroll:document.documentElement.scrollWidth,h1:x('h1'),sg:x('.sg'),card:x('.stop')}})()""")
    assert m["scroll"] <= PHONE["width"]
    assert m["h1"][0] == m["sg"][0] == m["card"][0] and m["sg"][1] == m["card"][1]
    first = pg.evaluate("document.querySelector('.stop').id")
    assert not pg.is_visible(f"#{first} .in dl")
    pg.click(f"#{first} .hd-open")
    assert pg.is_visible(f"#{first} .in dl")
