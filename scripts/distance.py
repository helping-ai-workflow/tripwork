"""Geographic distance + hop classification helpers."""
import math

EARTH_RADIUS_KM = 6371.0

def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance in km between two lat/lng points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))

# Conservative door-to-door speed floors (km/h) including transfers/walking.
# An agent estimate faster than this for the haversine distance is implausible.
_SPEED_FLOOR_KMH = {"walk": 4.5, "transit": 15.0, "bus": 20.0, "drive": 40.0, "flight": 400.0}

def min_plausible_mins(km, mode):
    """Minimum believable door-to-door minutes for `km` straight-line by `mode`.

    Uses a conservative speed floor (urban transit ~15 km/h incl. transfers), so an
    agent-estimated time below this is physically implausible and should be re-sourced.
    """
    speed = _SPEED_FLOOR_KMH.get(mode, 15.0)
    return km / speed * 60.0

def classify_hop(mins, max_hop_mins=60, km=None, mode=None):
    """Classify an inter-POI travel time.

    When `km` and `mode` are given and `mins` is below `min_plausible_mins(km, mode)`,
    the estimate is physically impossible -> 'implausible' (re-estimate / cite a
    timetable). Otherwise <= threshold is 'ok', else 'far'.
    """
    if km is not None and mode is not None and mins < min_plausible_mins(km, mode):
        return "implausible"
    return "ok" if mins <= max_hop_mins else "far"
