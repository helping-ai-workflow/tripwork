"""Daylight (sunrise/sunset) approximation — pure solar geometry, no API key.

Solar-declination + hour-angle model. Uses local SOLAR time (solar noon = 12:00),
ignoring longitude-within-timezone and the equation of time, so sunset is accurate
to ~±15-20 min — adequate for an advisory, never presented as exact. Mirrors the
pure-function style of distance.py / hours.py.
"""
import math
from datetime import date


def _day_of_year(date_iso):
    y, m, d = (int(x) for x in date_iso.split("-"))
    return date(y, m, d).timetuple().tm_yday


def daylight_hours(date_iso, lat):
    """Approximate daylight length in hours for an ISO date at latitude `lat`.

    Clamps the hour-angle cosine to [-1, 1] so polar night returns ~0h and polar
    day returns ~24h instead of raising on the acos domain.
    """
    n = _day_of_year(date_iso)
    decl = 23.44 * math.sin(math.radians(360.0 / 365.0 * (n - 81)))
    cos_h = -math.tan(math.radians(lat)) * math.tan(math.radians(decl))
    cos_h = max(-1.0, min(1.0, cos_h))
    half_arc_deg = math.degrees(math.acos(cos_h))  # half-day arc
    return 2.0 * half_arc_deg / 15.0               # 15 deg of rotation per hour


def approx_sunset(date_iso, lat):
    """Approximate local-solar sunset 'HH:MM' = 12:00 + daylight_hours/2.

    Advisory only (~±15-20 min vs civil sunset). Clamps to 23:59 for polar day.
    """
    total_min = round((12.0 + daylight_hours(date_iso, lat) / 2.0) * 60)
    total_min = min(total_min, 23 * 60 + 59)
    hh, mm = divmod(total_min, 60)
    return f"{hh:02d}:{mm:02d}"


def after_dark(arrival_hhmm, date_iso, lat):
    """True if `arrival_hhmm` ('HH:MM') is later than the approximate sunset."""
    ah, am = (int(x) for x in arrival_hhmm.split(":"))
    sh, sm = (int(x) for x in approx_sunset(date_iso, lat).split(":"))
    return (ah * 60 + am) > (sh * 60 + sm)
