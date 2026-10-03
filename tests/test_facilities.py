"""Unit tests for scripts/facilities.py — accommodation facility checks."""
from scripts.facilities import stop_meets_required, coverage_gaps, reception_ok


def test_required_all_present():
    ok, missing = stop_meets_required(["parking", "wifi"], ["parking"])
    assert ok is True and missing == []


def test_required_missing_token():
    ok, missing = stop_meets_required(["wifi"], ["parking", "kitchen"])
    assert ok is False and missing == ["parking", "kitchen"]


def test_required_empty_need_is_ok():
    ok, missing = stop_meets_required([], [])
    assert ok is True and missing == []


def test_coverage_no_gap_within_cadence():
    # CHC 1✓ Tekapo 2✗ Wanaka 2✓ TeAnau 2✗ Queenstown 3✓ ; max_gap 2 -> no gap
    stops = [
        {"nights": 1, "has_facility": True},
        {"nights": 2, "has_facility": False},
        {"nights": 2, "has_facility": True},
        {"nights": 2, "has_facility": False},
        {"nights": 3, "has_facility": True},
    ]
    assert coverage_gaps(stops, max_gap_nights=2) == []


def test_coverage_reports_overlong_run():
    stops = [{"nights": 3, "has_facility": False}]
    gaps = coverage_gaps(stops, max_gap_nights=2)
    assert len(gaps) == 1 and gaps[0]["run_nights"] == 3


def test_coverage_trailing_run_counted():
    stops = [{"nights": 1, "has_facility": True}, {"nights": 4, "has_facility": False}]
    gaps = coverage_gaps(stops, max_gap_nights=2)
    assert len(gaps) == 1 and gaps[0]["run_nights"] == 4


def test_reception_ok_before_close():
    assert reception_ok("19:00", "20:00", late_checkin=False) is True


def test_reception_locked_out_after_close():
    assert reception_ok("21:00", "20:00", late_checkin=False) is False


def test_reception_late_checkin_overrides():
    assert reception_ok("23:30", "20:00", late_checkin=True) is True
