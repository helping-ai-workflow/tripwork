# tests/test_render_gmaps.py
from urllib.parse import unquote
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


# --- NEW CONTRACT: name-search-first, coord pin only with pin_exact ---

def test_maps_url_area_poi_numeric_geocode_no_pin_exact_uses_name():
    """Area POI with numeric geocode but NO pin_exact -> name search, not coords. (D1)"""
    poi = {
        "name_local": "登別温泉",
        "district": "Noboribetsu",
        "geocode": {"lat": 42.47, "lng": 141.1},
    }
    url = maps_url(poi)
    query = unquote(url.split("query=", 1)[1])
    assert query == "登別温泉 Noboribetsu"
    assert "42.47" not in url  # must NOT be coord-pinned

def test_maps_url_pin_exact_true_uses_coords():
    """POI with pin_exact==True -> coord pin, not name search. (D1)"""
    poi = {
        "name_local": "登別温泉",
        "district": "Noboribetsu",
        "geocode": {"lat": 42.47, "lng": 141.1, "pin_exact": True},
    }
    url = maps_url(poi)
    query = unquote(url.split("query=", 1)[1])
    assert query == "42.47,141.1"

def test_maps_url_no_geocode_uses_name_and_district():
    """POI with NO geocode -> name + district search. (D1)"""
    poi = {
        "name_local": "スタバ",
        "district": "Sapporo",
    }
    url = maps_url(poi)
    query = unquote(url.split("query=", 1)[1])
    assert query == "スタバ Sapporo"

def test_maps_url_no_geocode_no_district_bare_name():
    """POI with name_local but no district -> bare name search. (D1)"""
    poi = {"name_local": "大通公園"}
    url = maps_url(poi)
    query = unquote(url.split("query=", 1)[1])
    assert query == "大通公園"


# --- Migrated from TW-048 coord-first (now name-first) ---

def test_maps_url_numeric_geocode_without_pin_exact_uses_name():
    """MIGRATED from TW-048 test_maps_url_pins_coordinates_when_geocode_present.
    Old contract: coords in URL. New contract: name-search-first, coords only
    when pin_exact=True. Numeric geocode alone must NOT produce coord pin. (D1)"""
    poi = {"name_local": "x", "name_display": "X", "geocode": {"lat": 37.5, "lng": 127.0}}
    url = maps_url(poi)
    query = unquote(url.split("query=", 1)[1])
    # name_local is "x", no district -> bare name search
    assert query == "x"
    assert "37.5" not in url

def test_maps_url_adds_district_when_no_geocode():   # TW-048 — unchanged behaviour
    poi = {"name_local": "스타벅스", "name_display": "Starbucks", "district": "Gangnam"}
    url = maps_url(poi)
    assert "Gangnam" in url   # disambiguated by district

def test_link_markdown_escapes_label():   # TW-022
    poi = {"name_display": "A]B|C$D", "name_local": "x", "geocode": {"lat": 1, "lng": 2}}
    md = link_markdown(poi)
    label = md[1:md.index("](")]
    assert "\\]" in label and "\\|" in label and "\\$" in label
