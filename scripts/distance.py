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

# Where a hop's duration came from. `agent_estimate` is the default because an
# unlabelled number IS an agent estimate — defaulting to anything better would
# launder a guess into a source. (TW-066)
DURATION_SOURCES = ("agent_estimate", "map_estimate", "sourced_timetable")


def classify_hop(mins, max_hop_mins=60, km=None, mode=None,
                 duration_source="agent_estimate"):
    """Classify a hop as ok / far / implausible / unsourced.

    Precedence (project-owner ruling, TW-066 fix-round-1):
    implausible > far > unsourced > ok. Physics first, then the user-visible
    feasibility problem, then provenance. `far` carries a defined user action
    (stop and ask whether to keep or replace the POI) while `unsourced` only
    routes back for a source; if `unsourced` won first, an over-cap hop
    carrying only an unlabelled agent guess would be recorded as `unsourced`
    -- schema-valid, but not `far` -- and silently skip the far-hop
    stop-on-confirmation halt. That is the same silent escape TW-066 exists
    to close, through a different exit. And a hop over the cap is over the
    cap whether or not someone later cites a timetable for it, so `far` is
    checked before duration_source regardless of source.

    `implausible` fires when the claimed duration is below what the geometry
    allows (min_plausible_mins), for EVERY duration_source -- physics is not
    repealed by a citation. TW-056 added that floor; TW-066 closes the hole
    it left: SKILL.md offered "re-estimate the hop OR cite a timetable", and
    re-estimating needs no evidence, so an agent could clear the floor by
    raising its own guess. A hop that clears BOTH the floor and the cap but
    carries only an `agent_estimate` is `unsourced` — the number is plausible
    but nothing corroborates it.

    Without km+mode there is no floor, so provenance cannot change the verdict
    and the legacy 2-arg form keeps its exact meaning.

    `duration_source` must be one of DURATION_SOURCES; an unrecognized value
    raises ValueError rather than silently taking the sourced path (which
    would skip the `unsourced` safeguard) or being silently coerced.
    """
    if duration_source not in DURATION_SOURCES:
        raise ValueError(f"unknown duration_source: {duration_source!r}")
    if km is not None and mode is not None and mins < min_plausible_mins(km, mode):
        return "implausible"
    if mins > max_hop_mins:
        return "far"
    if km is not None and mode is not None and duration_source == "agent_estimate":
        return "unsourced"
    return "ok"
