# tests/test_render_markdown.py
from scripts.render.markdown import render_day_table, md_escape

def test_day_table_links_pois():
    day = {"label": "Day 4", "rows": [
        {"time": "13:30", "slot": "meal", "poi_id": "odari", "text": "醬蟹"},
        {"time": "18:20", "slot": "activity", "text": "夜景"},
    ]}
    poi_map = {"odari": {"name_local": "오다리집", "name_display": "烏達里家"}}
    md = render_day_table(day, poi_map)
    assert "### Day 4" in md
    assert "| 13:30 |" in md
    assert "[烏達里家](https://www.google.com/maps/search/?api=1&query=" in md
    assert "夜景" in md  # row with no POI still renders

def test_day_table_header_row_present():
    md = render_day_table({"label": "Day 1", "rows": []}, {})
    assert "| 時段 | 行程 |" in md

def test_md_escape_escapes_dollar_and_pipe():
    assert md_escape("$180-260") == "\\$180-260"
    assert md_escape("a|b") == "a\\|b"
    assert md_escape("x") == "x"  # plain text untouched

def test_day_table_escapes_price_in_free_text():
    day = {"label": "Day 1", "rows": [{"time": "12:00", "slot": "meal", "text": "午餐 $180-260"}]}
    md = render_day_table(day, {})
    assert "\\$180-260" in md
    assert "$180" not in md.replace("\\$180", "")  # no bare $ remains

def test_day_table_appends_official_source_link():
    day = {"label": "Day 1", "rows": [{"time": "13:00", "slot": "meal", "poi_id": "ferg", "text": "漢堡"}]}
    poi_map = {"ferg": {
        "name_local": "Fergburger", "name_display": "Fergburger",
        "sources": [
            {"url": "https://review.example", "lang": "en"},
            {"url": "https://fergburger.com", "lang": "en", "official": True},
        ],
    }}
    md = render_day_table(day, poi_map)
    assert "[Fergburger](https://www.google.com/maps/search/?api=1&query=Fergburger)" in md
    assert "· [官網](https://fergburger.com)" in md  # official, not the review url

def test_day_table_falls_back_to_first_source_when_no_official():
    day = {"label": "Day 1", "rows": [{"time": "13:00", "slot": "meal", "poi_id": "x", "text": "漢堡"}]}
    poi_map = {"x": {"name_local": "X", "name_display": "X",
                     "sources": [{"url": "https://only.example", "lang": "en"}]}}
    md = render_day_table(day, poi_map)
    assert "· [官網](https://only.example)" in md

def test_day_table_no_source_link_when_poi_has_no_sources():
    day = {"label": "Day 1", "rows": [{"time": "13:00", "slot": "activity", "poi_id": "y", "text": "夜景"}]}
    poi_map = {"y": {"name_local": "Y", "name_display": "Y"}}
    md = render_day_table(day, poi_map)
    assert "官網" not in md

def test_day_table_unresolvable_poi_id_renders_text_only():
    day = {"label": "Day 1", "rows": [{"time": "13:00", "slot": "meal", "poi_id": "ghost", "text": "午餐"}]}
    md = render_day_table(day, {})
    assert "午餐" in md
    assert "官網" not in md


def test_poi_cell_source_url_escapes_paren():   # TW-022
    from scripts.render.markdown import render_day_table
    day = {"label": "D", "rows": [{"time": "12:00", "slot": "meal", "poi_id": "x", "text": "t"}]}
    poi_map = {"x": {"name_local": "x", "name_display": "x",
                     "sources": [{"url": "https://e.example/a(b)c", "official": True}]}}
    md = render_day_table(day, poi_map)
    assert "(b)" not in md.split("官網")[1][:40]   # ')' in url must not break the link
