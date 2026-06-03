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
