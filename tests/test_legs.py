"""Unit tests for scripts/legs.py — inter-stop leg feasibility classification."""
from scripts.legs import drive_too_long, misses_last_service, classify_leg


def test_drive_too_long_boundary():
    assert drive_too_long(300, 300) is False   # equal is OK
    assert drive_too_long(301, 300) is True
    assert drive_too_long(240, 300) is False


def test_drive_too_long_custom_max():
    assert drive_too_long(200, 180) is True
    assert drive_too_long(180, 180) is False


def test_misses_last_service():
    assert misses_last_service("21:30", "21:00") is True
    assert misses_last_service("20:30", "21:00") is False
    assert misses_last_service("21:00", "21:00") is False  # equal makes it


def test_classify_drive_leg():
    assert classify_leg({"mode": "drive", "duration_mins": 360}, 300)[0] == "drive_too_long"
    assert classify_leg({"mode": "drive", "duration_mins": 240}, 300)[0] == "ok"


def test_classify_transit_leg():
    late = {"mode": "rail", "depart": "22:00", "last_service": "21:00"}
    assert classify_leg(late)[0] == "missed_last_service"
    fine = {"mode": "rail", "depart": "20:00", "last_service": "21:00"}
    assert classify_leg(fine)[0] == "ok"


def test_classify_transit_without_times_is_ok():
    assert classify_leg({"mode": "rail"})[0] == "ok"


def test_classify_drive_leg_without_duration_raises():   # TW-010
    import pytest
    with pytest.raises(ValueError):
        classify_leg({"mode": "drive", "from": "Tekapo", "to": "Te Anau"}, 300)
    with pytest.raises(ValueError):
        classify_leg({"mode": "drive", "duration_mins": None}, 300)


def test_classify_transit_mode_misses_last_service():   # TW-026
    status, _ = classify_leg({"mode": "transit", "depart": "21:45", "last_service": "21:30"})
    assert status == "missed_last_service"
