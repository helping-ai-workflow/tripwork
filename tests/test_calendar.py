"""Unit tests for scripts/calendar.py — holiday + per-POI closure logic.

Pure functions: the skill supplies the calendar (public holidays) and each
POI's closed_days; these helpers decide weekday, crowd level, and whether a
POI is closed on a given trip day. Mirrors the verify.py / distance.py split.
"""
from scripts.calendar import weekday_of, holiday_on, is_high_crowd, poi_closed_on

CAL = {
    "holidays": [
        {"date": "2026-05-24", "name_local": "부처님 오신 날", "name_display": "Buddha's Birthday",
         "type": "national", "impact": {"crowds": True, "closures": False}},
        {"date": "2026-05-25", "name_local": "대체공휴일", "name_display": "Substitute Holiday",
         "type": "substitute", "impact": {"crowds": True, "closures": False}},
    ]
}


def test_weekday_of():
    assert weekday_of("2026-05-24") == "sunday"     # Buddha's birthday 2026 is a Sun
    assert weekday_of("2026-05-25") == "monday"
    assert weekday_of("2026-05-26") == "tuesday"


def test_holiday_on_hit_and_miss():
    assert holiday_on("2026-05-25", CAL)["type"] == "substitute"
    assert holiday_on("2026-05-26", CAL) is None


def test_is_high_crowd_weekend():
    # 2026-05-23 is a Saturday — weekend is high crowd even without a holiday
    assert is_high_crowd("2026-05-23", {"holidays": []}) is True


def test_is_high_crowd_public_holiday():
    # Substitute holiday on a Monday — high crowd because the holiday flags crowds
    assert is_high_crowd("2026-05-25", CAL) is True


def test_is_high_crowd_ordinary_weekday():
    assert is_high_crowd("2026-05-26", CAL) is False   # plain Tuesday, no holiday


def test_poi_closed_weekly():
    # 景福宮 closed every Tuesday — must not be scheduled on 2026-05-26 (Tue)
    poi = {"id": "gyeongbok", "closed_days": ["tuesday"]}
    closed, reason = poi_closed_on(poi, "2026-05-26", CAL)
    assert closed is True
    assert "tuesday" in reason.lower()


def test_poi_open_on_non_closed_weekday():
    poi = {"id": "gyeongbok", "closed_days": ["tuesday"]}
    closed, _ = poi_closed_on(poi, "2026-05-24", CAL)   # Sunday
    assert closed is False


def test_poi_closed_specific_date():
    poi = {"id": "shop", "closed_days": ["2026-05-25"]}
    closed, reason = poi_closed_on(poi, "2026-05-25", CAL)
    assert closed is True
    assert "2026-05-25" in reason


def test_poi_closed_on_public_holiday_token():
    # A shop that closes on any public holiday — closed on the substitute holiday
    poi = {"id": "shop", "closed_days": ["public_holiday"]}
    closed, reason = poi_closed_on(poi, "2026-05-25", CAL)
    assert closed is True
    assert "holiday" in reason.lower()


def test_poi_no_closed_days_always_open():
    poi = {"id": "park"}
    closed, _ = poi_closed_on(poi, "2026-05-26", CAL)
    assert closed is False
