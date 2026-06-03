# tests/test_render_markdown.py
from scripts.render.markdown import render_day_table

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
