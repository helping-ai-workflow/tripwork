import pytest

from scripts.render.reader import render_reader
from scripts.render.reader.centre import CENTRE_JS
from scripts.render.reader.publish import PUBLISH_JS
from scripts.export_gate import run_html_gate
from tests import reader_fixture as R


def _page(build):
    return render_reader(R.itinerary(), R.poi_map(), build=build, **R.reader_kwargs())


def test_check_build_carries_only_the_centring_script():
    html = _page("check")
    assert html.count("<script>") == 1 and CENTRE_JS in html and PUBLISH_JS not in html


def test_publish_build_appends_the_publish_script_once():
    html = _page("publish")
    assert html.count("<script>") == 2 and html.count(PUBLISH_JS) == 1
    assert html.index(CENTRE_JS) < html.index(PUBLISH_JS)


def test_publish_build_is_the_check_build_plus_one_script():
    assert _page("publish").replace(f"<script>{PUBLISH_JS}</script>", "") == _page("check")


def test_unknown_build_is_refused():
    with pytest.raises(ValueError):
        _page("preview")


def test_export_gate_admits_the_publish_page():
    rep = run_html_gate(_page("publish"), list(R.poi_map().values()))
    assert not [f for f in rep["failures"] if "script" in f]


def test_export_gate_refuses_a_tampered_publish_script():
    html = _page("publish").replace(PUBLISH_JS, PUBLISH_JS.replace("ANG=", "ANG2="))
    rep = run_html_gate(html, list(R.poi_map().values()))
    assert any("script not on the whitelist" in f for f in rep["failures"])
