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


# --- P9: gmaps_place_id -> Maps URLs API &query_place_id deep-link refinement
# (RESTORED to the PR2 append form; the 0.23.0 maps/place/?q=place_id form was a
# dead link Google does not resolve — consumer regression) ---

def test_maps_url_place_id_uses_query_place_id_refinement():
    """gmaps_place_id present -> name-search query + &query_place_id=<id> (exact place)."""
    poi = {"name_local": "登別温泉", "district": "Noboribetsu",
           "gmaps_place_id": "ChIJ_abc-123"}
    url = maps_url(poi)
    assert url.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert "&query_place_id=ChIJ_abc-123" in url
    assert "/maps/place/" not in url   # NOT the dead deep-link form

def test_maps_url_place_id_refines_pin_exact():
    """place_id REFINES the pin_exact (coord) branch — coord stays, suffix appended."""
    poi = {"name_local": "x", "district": "d",
           "geocode": {"lat": 42.47, "lng": 141.1, "pin_exact": True},
           "gmaps_place_id": "PLACE123"}
    url = maps_url(poi)
    assert url.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert "42.47" in unquote(url)                 # coord visible query preserved
    assert url.endswith("&query_place_id=PLACE123")

def test_maps_url_no_place_id_no_query_place_id():
    """No gmaps_place_id -> name-search form, no &query_place_id. (regression)"""
    poi = {"name_local": "大通公園"}
    url = maps_url(poi)
    assert url.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert "query_place_id" not in url

def test_maps_url_place_id_is_fully_url_quoted():
    """place_id special chars are percent-encoded (safe='')."""
    poi = {"name_local": "x", "gmaps_place_id": "a b/c+d"}
    url = maps_url(poi)
    assert url.endswith("&query_place_id=a%20b%2Fc%2Bd")


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


# --- G2: directions URL helper (no &travelmode → user picks car/transit) ---

def test_dir_url_shape():
    from scripts.render.gmaps_links import dir_url
    assert dir_url("A", "B") == "https://www.google.com/maps/dir/?api=1&origin=A&destination=B"

def test_dir_url_no_travelmode():
    from scripts.render.gmaps_links import dir_url
    assert "travelmode" not in dir_url("函館空港", "函館駅")

def test_dir_url_encodes_endpoints():
    from scripts.render.gmaps_links import dir_url
    url = dir_url("函館空港", "函館駅")
    o = url.split("origin=", 1)[1].split("&destination=", 1)[0]
    d = url.split("&destination=", 1)[1]
    assert unquote(o) == "函館空港" and unquote(d) == "函館駅"

def test_dir_url_encodes_space_and_parens():
    from scripts.render.gmaps_links import dir_url
    url = dir_url("New York", "A(B)")
    assert "origin=New%20York" in url       # space percent-encoded (safe="")
    assert "destination=A%28B%29" in url     # ')' encoded so a markdown link target is safe
