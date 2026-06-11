"""Booking lead-time feasibility — pure helper.

Gives the orchestrator's 'booking lead-time missed' halt an owning, testable
check: a booking that needs N days of lead time but the trip is fewer than N
days away can no longer be made in time.
"""
import datetime


def _days_until(today_iso, trip_start_iso):
    today = datetime.date.fromisoformat(today_iso)
    start = datetime.date.fromisoformat(trip_start_iso)
    return (start - today).days


def lead_time_missed(today_iso, trip_start_iso, lead_time_days):
    """True if there are fewer days until the trip than the booking needs.

    e.g. today 2026-06-11, trip 2026-06-18 (7 days out), lead_time_days 30 -> True.
    """
    return _days_until(today_iso, trip_start_iso) < lead_time_days
