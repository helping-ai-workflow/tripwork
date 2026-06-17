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


# --- PR2: &query_place_id deep-link append ---

def test_maps_url_appends_query_place_id_when_present():
    """gmaps_place_id present -> &query_place_id appended; query stays the NAME."""
    poi = {"name_local": "登別温泉", "district": "Noboribetsu",
           "gmaps_place_id": "ChIJ_abc-123"}
    url = maps_url(poi)
    assert "&query_place_id=ChIJ_abc-123" in url
    query = unquote(url.split("query=", 1)[1].split("&query_place_id=", 1)[0])
    assert query == "登別温泉 Noboribetsu"   # NOT coord-pinned
    assert "42." not in url

def test_maps_url_place_id_appended_on_pin_exact_too():
    """place_id refines the pin_exact (coord) branch as well."""
    poi = {"name_local": "x", "district": "d",
           "geocode": {"lat": 42.47, "lng": 141.1, "pin_exact": True},
           "gmaps_place_id": "PLACE123"}
    url = maps_url(poi)
    assert "&query_place_id=PLACE123" in url
    query = unquote(url.split("query=", 1)[1].split("&query_place_id=", 1)[0])
    assert query == "42.47,141.1"

def test_maps_url_no_place_id_no_query_place_id_param():
    """No gmaps_place_id -> URL unchanged, no query_place_id param. (regression)"""
    poi = {"name_local": "大通公園"}
    url = maps_url(poi)
    assert "query_place_id" not in url

def test_maps_url_place_id_is_fully_url_quoted():
    """place_id special chars are percent-encoded (safe='')."""
    poi = {"name_local": "x", "gmaps_place_id": "a b/c+d"}
    url = maps_url(poi)
    assert "&query_place_id=a%20b%2Fc%2Bd" in url


# --- dogfood D3: name_zh Chinese gloss ---

def test_link_markdown_with_name_zh_shows_gloss():
    """POI with name_zh -> label is 'name_display（name_zh）'. (dogfood D3)"""
    poi = {
        "name_display": "ジンギスカン だるま",
        "name_local": "ジンギスカン だるま",
        "name_zh": "成吉思汗烤羊肉",
        "district": "Sapporo",
    }
    md = link_markdown(poi)
    label = md[1:md.index("](")]
    assert "成吉思汗烤羊肉" in label
    assert "ジンギスカン だるま" in label
    assert label == "ジンギスカン だるま（成吉思汗烤羊肉）"

def test_link_markdown_no_name_zh_plain_label():
    """POI without name_zh -> no gloss, no '（' in label. (dogfood D3)"""
    poi = {"name_display": "Clock Tower", "name_local": "Clock Tower"}
    md = link_markdown(poi)
    label = md[1:md.index("](")]
    assert "（" not in label

def test_link_markdown_name_zh_same_as_display_no_redundant_gloss():
    """POI where name_zh == name_display -> no redundant gloss appended. (dogfood D3)"""
    poi = {"name_display": "大通公園", "name_local": "大通公園", "name_zh": "大通公園"}
    md = link_markdown(poi)
    label = md[1:md.index("](")]
    assert label == "大通公園"
    assert "（" not in label
