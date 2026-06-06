"""Intra-city transit comfort checks — pure functions. Mirrors the
calendar.py / season.py / legs.py style; reuses hours.to_minutes for HH:MM compares.
"""
from scripts.hours import to_minutes


def in_peak(hhmm, peak_windows):
    """True if `hhmm` falls within any peak window (inclusive of both ends).

    peak_windows: [{"start": "HH:MM", "end": "HH:MM", ...}, ...].
    """
    t = to_minutes(hhmm)
    for w in peak_windows:
        if to_minutes(w["start"]) <= t <= to_minutes(w["end"]):
            return True
    return False


def walk_too_far(mins, max_walk_mins=15):
    """True if a station-to-POI walk exceeds the comfortable maximum (elderly/luggage)."""
    return mins > max_walk_mins
