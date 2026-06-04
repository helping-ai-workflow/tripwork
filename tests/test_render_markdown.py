# tests/test_render_markdown.py
from scripts.render.markdown import render_day_table, md_escape

def test_day_table_links_pois():
    day = {"label": "Day 4", "rows": [
        {"time": "13:30", "text": "醬蟹", "poi": {"name_local": "오다리집", "name_display": "烏達里家"}},
        {"time": "18:20", "text": "夜景", "poi": None},
    ]}
    md = render_day_table(day)
    assert "### Day 4" in md
    assert "| 13:30 |" in md
    assert "[烏達里家](https://www.google.com/maps/search/?api=1&query=" in md
    assert "夜景" in md  # row with no POI still renders

def test_day_table_header_row_present():
    day = {"label": "Day 1", "rows": []}
    md = render_day_table(day)
    assert "| 時段 | 行程 |" in md

def test_md_escape_escapes_dollar_and_pipe():
    assert md_escape("$180-260") == "\\$180-260"
    assert md_escape("a|b") == "a\\|b"
    assert md_escape("x") == "x"  # plain text untouched

def test_day_table_escapes_price_in_free_text():
    day = {"label": "Day 1", "rows": [
        {"time": "12:00", "text": "午餐 $180-260", "poi": None},
    ]}
    md = render_day_table(day)
    assert "\\$180-260" in md
    assert "$180" not in md.replace("\\$180", "")  # no bare $ remains
