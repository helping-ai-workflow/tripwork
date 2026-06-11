# tests/test_render_gmaps.py
from scripts.render.gmaps_links import maps_url, link_markdown

def test_maps_url_uses_local_name():
    poi = {"name_local": "오다리집", "name_display": "烏達里家"}
    url = maps_url(poi)
    assert url.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert "%EC%98%A4%EB%8B%A4%EB%A6%AC%EC%A7%91" in url  # url-encoded 오다리집

def test_maps_url_falls_back_to_display_when_no_local():
    poi = {"name_display": "Lotte World"}
    url = maps_url(poi)
    assert "Lotte" in url

def test_link_markdown_format():
    poi = {"name_local": "명동", "name_display": "明洞"}
    md = link_markdown(poi)
    assert md.startswith("[明洞](https://www.google.com/maps/search/?api=1&query=")
    assert md.endswith(")")


def test_maps_url_pins_coordinates_when_geocode_present():   # TW-048
    poi = {"name_local": "x", "name_display": "X", "geocode": {"lat": 37.5, "lng": 127.0}}
    url = maps_url(poi)
    assert "37.5" in url and "127.0" in url   # coordinate-pinned, not name-only

def test_maps_url_adds_district_when_no_geocode():   # TW-048
    poi = {"name_local": "스타벅스", "name_display": "Starbucks", "district": "Gangnam"}
    url = maps_url(poi)
    assert "Gangnam" in url   # disambiguated by district

def test_link_markdown_escapes_label():   # TW-022
    poi = {"name_display": "A]B|C$D", "name_local": "x", "geocode": {"lat": 1, "lng": 2}}
    md = link_markdown(poi)
    label = md[1:md.index("](")]
    assert "\\]" in label and "\\|" in label and "\\$" in label
