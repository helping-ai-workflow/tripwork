"""v1.1 topic 4 — TW-D3: the licence line leaves the page (the user's pick A). OFL FAQ
1.10 / 1.12: a font embedded in a document needs no licence text; ISC (Lucide) needs
its copyright and permission notice *in* every copy, not on screen. So the notices go
into a comment at the top of the file, taken from the files the plugin ships. The map
credits linked to openstreetmap.org/copyright until the user's check (2026-10-02) made
them plain text."""
import pathlib
import re

from bs4 import BeautifulSoup, Comment

from scripts.render.reader import render_reader
from tests.reader_fixture import itinerary, poi_map, reader_kwargs

ROOT = pathlib.Path(__file__).resolve().parent.parent
OSM_COPYRIGHT = "https://www.openstreetmap.org/copyright"


def _html(**kw):
    args = reader_kwargs()
    args.update(kw)
    return render_reader(itinerary(), poi_map(), **args)


def _ws(s):
    return re.sub(r"\s+", " ", s).strip()


def test_no_licence_line_on_the_page():
    s = BeautifulSoup(_html(), "html.parser")
    assert s.select_one(".licence") is None
    for c in s.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()
    text = s.body.get_text()
    assert "SIL Open Font License" not in text and "ISC" not in text


def test_the_notices_open_the_file():
    html = _html()
    m = re.match(r"<!doctype html><!--(.*?)-->", html, re.S)
    assert m, html[:80]
    note = _ws(m.group(1))
    # the shipped licence files are the source, not a copy kept here
    assert _ws((ROOT / "assets/icons/lucide/LICENSE").read_text(encoding="utf-8")) in note
    ofl = (ROOT / "assets/fonts/OFL.txt").read_text(encoding="utf-8")
    header = ofl.split("-----", 1)[0]                # the per-font copyright list, above the licence body
    assert header.count("Copyright") == 3
    for line in re.findall(r"^\s+(.*Copyright.*)$", header, re.M):
        assert _ws(line) in note, line
    assert "SIL Open Font License, Version 1.1" in note
    assert "copied below" not in note                # the OFL body is not in the comment (review M-1)
    assert "--" not in m.group(1)                    # nothing can end the comment early


def test_every_map_credit_names_openstreetmap_in_plain_text():
    """Topic 4 linked every credit to openstreetmap.org/copyright; the user's check
    (2026-10-02) made them plain text -- the link was tapped by accident. The page still
    names the copyright page in its licence comment."""
    from tests.test_reader_maps import side_file
    html = _html(maps=side_file())
    s = BeautifulSoup(html, "html.parser")
    minis, cards = s.select(".attrmini"), s.select(".attr")
    assert minis and cards
    for el in minis:
        assert el.name == "span" and el.get_text() == "© OpenStreetMap"
    for el in cards:
        assert el.select("a") == [] and el.get_text() == "© OpenStreetMap contributors"
    assert OSM_COPYRIGHT in html.split("-->", 1)[0]

def test_the_gate_wants_the_whole_notice_not_two_words():
    """Review M-2: ISC needs the copyright and permission notice itself; a comment that
    only names the licences must fail."""
    from scripts.export_gate import run_html_gate
    html = _html()
    thin = re.sub(r"<!--.*?-->", "<!-- SIL Open Font License ISC License -->", html, count=1, flags=re.S)
    assert thin != html
    checks = {c["name"]: c["passed"] for c in run_html_gate(thin, list(poi_map().values()), min_days=1)["checks"]}
    assert checks["licences_present"] is False
