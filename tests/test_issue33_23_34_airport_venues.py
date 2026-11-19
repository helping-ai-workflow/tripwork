"""#33 side of security, #23 when to be at the airport, #34 venue notices. Placeholder
places and dates; every check calls the shipped function."""
from scripts.airport import (CHECK_IN_BUFFER_MINS, be_at_airport, check_in_failures, check_in_notices,
                             security_failures, security_notices)
from scripts.venue_notices import NOTICE_FRESH_DAYS, detour_warnings, venue_notices, venues
from tests.test_issue37_transfer import mv

SEC = {"slot": "transfer", "place": "示意空港", "security": True, "text": "過安檢"}
BY_ID = {"land": {"security_zone": "landside"}, "air": {"security_zone": "airside"},
         "unk": {"security_zone": "unknown"}, "shop": {"inside": "store"}, "store": {}}


def stop(pid):
    return {"slot": "visit", "poi_id": pid, "text": "逛"}


def it(rows, **top):
    return dict({"days": [{"date": "2030-01-09", "rows": rows}]}, **top)


def test_security_order_passes_landside_then_airside():
    rows = [mv("10:00", 50, "drive"), stop("land"), mv("12:00", 5, "walk"), SEC, mv("12:30", 5, "walk"),
            stop("air"), mv("14:00", 200, "flight")]
    assert security_failures(it(rows), BY_ID) == []


def test_security_order_catches_each_wrong_side():
    rows = [mv("10:00", 50, "drive"), stop("air"), mv("12:00", 5, "walk"), SEC, mv("12:30", 5, "walk"),
            stop("land"), mv("14:00", 200, "flight")]
    f = security_failures(it(rows), BY_ID)
    assert len(f) == 2 and "before passing security" in f[0] and "after passing security" in f[1]
    assert all(m.startswith("security zone order:") for m in f)


def test_airside_without_a_security_row_fails():
    rows = [mv("10:00", 50, "drive"), stop("air"), mv("14:00", 200, "flight")]
    assert "no security transfer row" in security_failures(it(rows), BY_ID)[0]


def test_unknown_side_on_a_flight_day_is_one_notice():
    rows = [mv("10:00", 50, "drive"), stop("unk"), mv("14:00", 200, "flight")]
    assert len(security_notices(it(rows), BY_ID)) == 1
    assert security_notices(it([mv("10:00", 5, "walk"), stop("unk"), mv("11:00", 5, "walk")]), BY_ID) == []


def test_be_at_airport_follows_the_published_advice_then_the_buffer():
    assert be_at_airport({"time": "12:00", "arrive_by_mins": 150}) == 12 * 60 - 150
    assert be_at_airport({"time": "12:00", "check_in_close_mins": 60}) == 12 * 60 - 60 - 60
    assert be_at_airport({"time": "12:00", "check_in_close_mins": 30, "international": False}) == 12 * 60 - 60
    assert be_at_airport({"time": "12:00"}) is None
    assert CHECK_IN_BUFFER_MINS == {True: 60, False: 30}


def test_the_upper_end_of_the_estimate_decides():
    ok = [mv("08:40", 50, "drive", mins_max=65), mv("12:00", 210, "flight", check_in_close_mins=60)]
    assert check_in_failures(it(ok)) == []                      # 09:45 <= 10:00
    late = [mv("08:40", 50, "drive", mins_max=85), mv("12:00", 210, "flight", check_in_close_mins=60)]
    f = check_in_failures(it(late))
    assert len(f) == 1 and f[0].startswith("check-in missed:") and "10:05" in f[0] and "10:00" in f[0]


def test_a_flight_from_legs_and_a_transfer_before_it():
    legs = {"legs": [{"mode": "flight", "from": "A", "to": "B", "check_in_close_mins": 45,
                      "international": False}]}
    rows = [mv("10:00", 60, "rail"), {"slot": "transfer", "place": "示意空港", "text": "x"},
            dict(mv("11:30", 90), leg_index=0, mode=None)]
    assert len(check_in_failures(it(rows), legs)) == 1       # 11:00 > 11:30-45-30=10:15
    assert check_in_notices(it(rows), legs) == []


def test_a_flight_without_check_in_data_is_one_notice():
    assert len(check_in_notices(it([mv("08:00", 30, "drive"), mv("12:00", 210, "flight")]))) == 1


def test_venues_come_from_buildings_and_transfer_points():
    rows = [mv("10:00", 5, "walk"), stop("shop"), mv("11:00", 5, "walk"), SEC, mv("11:30", 5, "walk")]
    assert venues(it(rows), BY_ID) == ["store", "示意空港"]


def test_a_look_counts_only_close_to_departure():
    rows = [mv("10:00", 5, "walk"), stop("shop"), mv("11:00", 5, "walk")]
    brief = {"dates": {"start": "2030-01-09"}}
    fresh = it(rows, venue_notices=[{"venue": "store", "checked": "2029-12-20", "source_url": "https://s.example/n"}])
    stale = it(rows, venue_notices=[{"venue": "store", "checked": "2029-11-01", "source_url": "https://s.example/n"}])
    assert venue_notices(fresh, BY_ID, brief) == []
    assert len(venue_notices(stale, BY_ID, brief)) == 1 and len(venue_notices(it(rows), BY_ID, brief)) == 1
    assert NOTICE_FRESH_DAYS == 30


def test_a_closure_that_changes_a_move_needs_its_detour():
    notice = [{"venue": "store", "checked": "2030-01-01", "source_url": "https://s.example/n",
               "items": [{"text": "連絡通道封閉", "affects": [{"date": "2030-01-09", "time": "11:00"}]}]}]
    rows = [mv("10:00", 5, "walk"), stop("shop"), mv("11:00", 5, "walk")]
    assert len(detour_warnings(it(rows, venue_notices=notice))) == 1
    rows[2] = mv("11:00", 9, "walk", detour="改走一樓外側")
    assert detour_warnings(it(rows, venue_notices=notice)) == []


def test_the_markdown_flight_row_says_when_to_be_at_the_airport():
    from scripts.render.markdown import render_day_table
    row = dict(mv("12:00", 210, "flight", check_in_close_mins=60), **{"from": "A", "to": "B"})
    assert "到機場 10:00 前" in render_day_table({"label": "D1", "rows": [row]}, {})
    bare = dict(mv("12:00", 210, "flight"), **{"from": "A", "to": "B"})
    assert "報到截止時間未查" in render_day_table({"label": "D1", "rows": [bare]}, {})
