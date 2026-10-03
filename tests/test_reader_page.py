"""v1.0 P4 — the page as a whole: offline, script-free, escaped, subset fonts (spec §2 / §6.6)."""
import base64
import io
import re

from bs4 import BeautifulSoup
from fontTools.ttLib import TTFont

from scripts.render.reader import render_reader
from tests.reader_fixture import itinerary, poi_map, reader_kwargs


def _html(itin=None):
    return render_reader(itin or itinerary(), poi_map(), **reader_kwargs())


def test_one_document_no_script_offline_images():
    html = _html()
    assert html.lower().count("<html") == 1
    # v1.0 P6: the one script is the desktop centring constant (spec §6.9); nothing else
    from scripts.render.reader.centre import CENTRE_JS
    assert html.lower().count("<script") == 1 and f"<script>{CENTRE_JS}</script>" in html
    s = BeautifulSoup(html, "html.parser")
    assert s.select_one('meta[name="viewport"]')
    assert all(i["src"].startswith("data:") for i in s.select("img"))
    assert not s.select('link[rel="stylesheet"]')


def test_theme_toggle_and_page_radios():
    s = BeautifulSoup(_html(), "html.parser")
    assert s.select_one('input#theme[type="checkbox"]') and s.select_one('label.bubble[for="theme"]')
    radios = s.select('input[name="pg"]')
    # H1c2: each day also has pg-dNf, the day opened with its small calendar put away
    assert [r["id"] for r in radios] == ["pg-home", "pg-lodging", "pg-advisory", "pg-checklist",
                                         "pg-d1", "pg-d1f", "pg-d2", "pg-d2f", "pg-d3", "pg-d3f"]
    assert radios[0].has_attr("checked") and not any(r.has_attr("checked") for r in radios[1:])


def test_everything_starts_collapsed():
    s = BeautifulSoup(_html(), "html.parser")
    assert not s.select("details[open]")
    checked = [i["id"] for i in s.select('input[type="radio"][checked]')]
    assert checked == ["pg-home"]                                         # v1.1 §8.1: stops are anchors, not radios


def test_all_trip_text_is_escaped():
    itin = itinerary()
    itin["days"][1]["theme"] = '<b>早市&"蟹"'
    itin["days"][1]["rows"][1]["text"] = "<script>alert(1)</script>朝市"
    html = _html(itin)
    assert "<script>alert" not in html.lower() and "<b>早市" not in html
    assert html.lower().count("<script") == 1                    # only the centring script (P6)
    assert "&lt;b&gt;早市&amp;" in html


def test_fonts_are_embedded_subsets_of_the_page_text():
    html = _html()
    faces = re.findall(r"@font-face\{[^}]*url\(data:font/woff2;base64,([A-Za-z0-9+/=]+)\)", html)
    assert len(faces) == 4
    cmap = TTFont(io.BytesIO(base64.b64decode(faces[0]))).getBestCmap()
    assert ord("朝") in cmap and ord("鬱") not in cmap


def test_licences_are_stated():
    """v1.1 TW-D3: in a comment opening the file, not on screen (tests/test_v11_licence.py)."""
    note = re.match(r"<!doctype html><!--(.*?)-->", _html(), re.S).group(1)
    assert "SIL Open Font License" in note and "Lucide" in note and "ISC License" in note


def test_the_legacy_entrypoint_renders_the_reader():
    from scripts.render.html_page import render_html_page
    html = render_html_page(itinerary(), poi_map(), **reader_kwargs())
    assert 'section class="page home"' in html


def test_the_theme_toggle_uses_lucide_moon_and_sun():
    from bs4 import BeautifulSoup
    from scripts.render.reader.assets import ICONS_USED, icon
    b = BeautifulSoup(_html(), "html.parser").select_one("label.bubble")
    assert str(b.select_one(".moon svg")) == str(BeautifulSoup(icon("moon"), "html.parser").svg)
    assert b.select_one(".sun svg") and "☾" not in b.get_text() and "☀" not in b.get_text()
    assert {"moon", "sun"} <= set(ICONS_USED)
