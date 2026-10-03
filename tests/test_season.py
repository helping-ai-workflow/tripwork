import pytest
from scripts.season import daylight_hours, approx_sunset, after_dark

def test_equator_is_about_twelve_hours():
    assert daylight_hours("2026-06-21", 0.0) == pytest.approx(12.0, abs=0.1)
    assert daylight_hours("2026-12-21", 0.0) == pytest.approx(12.0, abs=0.1)

def test_southern_winter_is_short_day():
    assert daylight_hours("2026-07-15", -44.0) < 11.0

def test_southern_summer_is_long_day():
    assert daylight_hours("2026-01-15", -44.0) > 13.0

def test_polar_night_and_day_clamp():
    assert daylight_hours("2026-01-15", 80.0) == pytest.approx(0.0, abs=0.5)
    assert daylight_hours("2026-07-15", 80.0) == pytest.approx(24.0, abs=0.5)

def test_approx_sunset_is_noon_plus_half_daylight():
    assert approx_sunset("2026-06-21", 0.0) == "18:00"
    s = approx_sunset("2026-07-15", -44.0)
    hh, mm = (int(x) for x in s.split(":"))
    assert hh * 60 + mm < 17 * 60 + 30

def test_after_dark_compares_to_sunset():
    assert after_dark("18:00", "2026-07-15", -44.0) is True
    assert after_dark("15:00", "2026-07-15", -44.0) is False


def test_approx_sunset_civil_correction():   # TW-050
    from scripts.season import approx_sunset
    # Tokyo (lng 139.7, UTC+9): solar-only sunset is ~24 min earlier than civil.
    solar = approx_sunset("2026-06-21", 35.68)
    civil = approx_sunset("2026-06-21", 35.68, lng=139.7, utc_offset_hours=9)
    assert solar != civil   # correction applied when lng+offset given
