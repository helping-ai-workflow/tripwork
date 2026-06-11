"""Calendar logic — public-holiday + per-POI closure helpers.

Pure functions. The calendar-check skill supplies the public-holiday calendar
(via official-source WebSearch) and source-verify records each POI's
`closed_days`; these helpers decide weekday, crowd level, and whether a POI is
closed on a given trip day. Decision logic lives here so it is unit-testable,
mirroring the verify.py / distance.py split.
"""
import datetime

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday"]


def weekday_of(iso_date):
    """Lowercase weekday name for an ISO date string (e.g. '2026-05-26' -> 'tuesday')."""
    return WEEKDAYS[datetime.date.fromisoformat(iso_date).weekday()]


def holiday_on(iso_date, calendar):
    """Return the holiday dict for iso_date, or None. calendar is {'holidays': [...]}"""
    for h in (calendar or {}).get("holidays", []):
        if h.get("date") == iso_date:
            return h
    return None


def is_high_crowd(iso_date, calendar):
    """True if the date is a weekend, or a public holiday flagged crowds=True.

    Synthesis uses this to add a crowd note + earlier-start / off-peak-dining
    advice and to steer crowd-fragile POIs away from these days.
    """
    if weekday_of(iso_date) in ("saturday", "sunday"):
        return True
    h = holiday_on(iso_date, calendar)
    return bool(h and h.get("impact", {}).get("crowds"))


def poi_closed_on(poi, iso_date, calendar=None):
    """Return (closed: bool, reason: str) for a POI on a given trip day.

    A POI's `closed_days` may contain:
      - a weekday name ('tuesday')          -> weekly fixed closure
      - an ISO date ('2026-05-25')          -> one-off closure
      - the token 'public_holiday'          -> closed on any public holiday
                                               (requires `calendar` to resolve)

    Synthesis hard-avoids scheduling a POI on a day this returns closed=True;
    if a must_do POI is closed on every feasible trip day, stop and ask the user.
    """
    raw = poi.get("closed_days", []) or []
    closed_days = [str(x).strip().lower() for x in raw]
    wd = weekday_of(iso_date)

    if wd in closed_days:
        return True, f"closed on {wd}s"
    if iso_date.lower() in closed_days:
        return True, f"closed on {iso_date}"
    if "public_holiday" in closed_days:
        h = holiday_on(iso_date, calendar)
        if h:
            label = h.get("name_display") or h.get("name_local") or "public holiday"
            return True, f"closed on public holiday ({label})"
    return False, ""
