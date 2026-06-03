from scripts.render.line_short import render_line_short

def test_line_short_has_header_and_days():
    itin = {
        "title": "韓國 5 天 4 夜",
        "days": [
            {"label": "Day 1（5/24）抵達", "items": [
                {"time": "17:00", "emoji": "🐠", "text": "水族館"},
                {"time": "19:00", "emoji": "🍽️", "text": "晚餐：이가서식당"}]},
        ],
    }
    out = render_line_short(itin)
    assert "韓國 5 天 4 夜" in out
    assert "Day 1（5/24）抵達" in out
    assert "🐠 水族館" in out
    assert "17:00" in out

def test_line_short_omits_urls():
    itin = {"title": "t", "days": [{"label": "Day 1", "items": [
        {"time": "10:00", "emoji": "🍁", "text": "AGIT"}]}]}
    out = render_line_short(itin)
    assert "http" not in out  # LINE version is plain, no links
