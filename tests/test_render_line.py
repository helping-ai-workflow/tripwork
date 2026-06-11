from scripts.render.line_short import render_line_short

def test_line_short_from_itinerary_yaml():
    itin = {
        "title": "韓國 5 天 4 夜",
        "days": [
            {"label": "Day 1（5/24）抵達", "rows": [
                {"time": "17:00", "slot": "visit", "poi_id": "aqua", "text": "水族館"},
                {"time": "19:00", "slot": "meal", "poi_id": "iga", "text": "晚餐：이가서식당"}]},
        ],
    }
    out = render_line_short(itin)
    assert "韓國 5 天 4 夜" in out
    assert "Day 1（5/24）抵達" in out
    assert "📍 水族館" in out      # slot=visit -> 📍
    assert "🍽 晚餐：이가서식당" in out  # slot=meal -> 🍽
    assert "17:00" in out

def test_line_short_omits_urls():
    itin = {"title": "t", "days": [{"label": "Day 1", "rows": [
        {"time": "10:00", "slot": "activity", "poi_id": "agit", "text": "AGIT"}]}]}
    out = render_line_short(itin)
    assert "http" not in out  # LINE version is plain, no links
    assert "🎯 AGIT" in out    # slot=activity -> 🎯

def test_line_short_move_row_has_no_poi():
    itin = {"title": "t", "days": [{"label": "D1", "rows": [
        {"time": "09:00", "slot": "move", "text": "KTX 首爾→釜山"}]}]}
    out = render_line_short(itin)
    assert "🚆 KTX 首爾→釜山" in out
