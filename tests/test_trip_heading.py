"""v1.0 spec §4.5: itinerary.title is retired -- the reader and the markdown (the LINE
text was retired in v1.1) both head the trip with the brief's KUSO headline plus the dates line, from one
helper (scripts/render/heading.py). A pre-v1.0 itinerary without a brief still falls
back to its old title."""
from bs4 import BeautifulSoup

from scripts.render.heading import dates_line, trip_title
from scripts.render.markdown import render_markdown_page
from scripts.render.reader import render_reader
from tests.reader_fixture import brief, itinerary, poi_map, reader_kwargs


def test_the_headline_names_the_trip():
    b = brief()
    assert trip_title(b, itinerary()) == b["headline"]["text"]
    assert trip_title({}, {"title": "舊標題"}) == "舊標題"
    assert trip_title({}, {}) == "行程"


def test_the_dates_line_is_short_name_length_and_span():
    assert dates_line(brief(), itinerary()) == "測試 3天2夜・10/12（一） – 10/14（三）"


def test_the_markdown_heads_with_headline_and_dates():
    b = brief()
    lines = render_markdown_page(itinerary(), poi_map(), None, brief=b).splitlines()
    assert lines[0] == f"# {b['headline']['text']}"
    assert lines[2] == dates_line(b, itinerary())
    assert "函館三天" not in "\n".join(lines[:3])            # the retired title is not the heading


def test_the_reader_uses_the_same_helper():
    soup = BeautifulSoup(render_reader(itinerary(), poi_map(), **reader_kwargs()), "html.parser")
    assert soup.select_one("h1.headline").get_text() == trip_title(brief(), itinerary())
    assert soup.select_one(".home .dates").get_text() == dates_line(brief(), itinerary())
    assert soup.select_one("title").get_text() == trip_title(brief(), itinerary())
