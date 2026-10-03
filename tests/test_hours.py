"""Unit tests for scripts/hours.py — closing-buffer classification."""
from scripts.hours import to_minutes, closing_status


def test_to_minutes():
    assert to_minutes("00:00") == 0
    assert to_minutes("21:30") == 1290


def test_ok_with_ample_buffer():
    # arrive 18:00, last order 20:30, close 21:30, need 60 -> 210 min before close
    status, _ = closing_status("18:00", "21:30", last_call="20:30", need_mins=60)
    assert status == "ok"


def test_tight_buffer_flagged():
    # arrive 20:50, close 21:30 -> 40 min < need 60, but before last order? no last_call -> lc=close
    status, reason = closing_status("20:50", "21:30", need_mins=60)
    assert status == "tight"
    assert "40 min" in reason


def test_after_last_call():
    # arrive 20:45, last order 20:30 -> can't be seated
    status, reason = closing_status("20:45", "21:30", last_call="20:30", need_mins=30)
    assert status == "after_last_call"
    assert "20:30" in reason


def test_closed_after_close():
    status, reason = closing_status("21:40", "21:30", last_call="20:30", need_mins=0)
    assert status == "closed"
    assert "21:30" in reason


def test_last_call_defaults_to_close():
    # no last_call: admitted any time before close; 21:00 vs 21:30, need 0 -> ok
    status, _ = closing_status("21:00", "21:30", need_mins=0)
    assert status == "ok"


def test_last_call_clamped_to_close():
    # a bogus last_call later than close is clamped; 21:00 < close 21:30 -> ok
    status, _ = closing_status("21:00", "21:30", last_call="23:00", need_mins=0)
    assert status == "ok"


def test_sight_last_entry_buffer():
    # museum closes 17:00, last entry 16:30, arrive 16:50 -> after last entry
    status, _ = closing_status("16:50", "17:00", last_call="16:30", need_mins=20)
    assert status == "after_last_call"


def test_to_minutes_rejects_bad_string():   # TW-020
    import pytest
    from scripts.hours import to_minutes
    with pytest.raises(ValueError):
        to_minutes("nine")
    assert to_minutes("21:30") == 1290
    assert to_minutes(1290) == 1290           # PyYAML sexagesimal already in minutes

def test_closing_status_handles_overnight():   # TW-047
    from scripts.hours import closing_status
    # bar open till 02:00 (past midnight); a 23:00 arrival is NOT closed
    status, _ = closing_status("23:00", "02:00", need_mins=30)
    assert status in ("ok", "tight")
