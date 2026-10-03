"""Intra-city transit comfort checks — pure functions. Mirrors the
calendar.py / season.py / legs.py style; reuses hours.to_minutes for HH:MM compares.
"""
from scripts.hours import to_minutes


WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def in_peak(hhmm, peak_windows, date=None, area=None):
    """True if `hhmm` falls within any peak window (inclusive of both ends).

    peak_windows: [{"start": "HH:MM", "end": "HH:MM", "days": [...], "areas": [...], ...}].
    A window may be scoped (TW-093): `days` (mon..sun) and `areas` (the area names it
    covers; one matches when either name contains the other). A scope only excludes
    when the caller says where and when: with no `date` / `area` given the window
    cannot be ruled out, so it applies as an unscoped one does.
    """
    t = to_minutes(hhmm)
    for w in peak_windows:
        if not to_minutes(w["start"]) <= t <= to_minutes(w["end"]):
            continue
        if date is not None and w.get("days") and WEEKDAYS[date.weekday()] not in w["days"]:
            continue
        if area and w.get("areas") and not any(a in area or area in a for a in w["areas"]):
            continue
        return True
    return False


def walk_too_far(mins, max_walk_mins=15):
    """True if a station-to-POI walk exceeds the comfortable maximum (elderly/luggage)."""
    return mins > max_walk_mins
