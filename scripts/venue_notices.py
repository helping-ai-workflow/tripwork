"""Venue notices (#34): an airport, a station or a building with shops inside may
announce works or a closed passage for the trip dates on its own news page -- Places
never shows it. Which venues need a look follows from the itinerary itself; what was
found lives in itinerary.yaml's `venue_notices`."""
import datetime

# #34 (user's pick, 2026-11-18): a look counts when made this close to departure --
# works are announced months ahead, so an earlier look can miss a later notice.
NOTICE_FRESH_DAYS = 30


def venues(itinerary, by_id):
    """The venues to look up, in first-use order: a building a scheduled place is inside
    (#35), and every transfer point (#37) -- a security transfer is the airport."""
    out = []
    for d in (itinerary or {}).get("days") or []:
        for r in d.get("rows") or []:
            if not isinstance(r, dict):
                continue
            if r.get("slot") == "transfer":
                out.append(r.get("poi_id") or r.get("place"))
            parent = (by_id.get(r.get("poi_id")) or {}).get("inside")
            if parent:
                out.append(parent)
    return [v for v in dict.fromkeys(out) if v]


def _list(v):
    """The records of a list field; a hand-edited odd value reads as none."""
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def _entries(itinerary):
    return _list((itinerary or {}).get("venue_notices"))


def _date(s):
    try:
        return datetime.date.fromisoformat(str(s))
    except ValueError:
        return None


def _start(itinerary, brief):
    dates = (brief or {}).get("dates") if isinstance(brief, dict) else None
    start = _date(dates.get("start")) if isinstance(dates, dict) else None
    if start is None:
        days = (itinerary or {}).get("days") or []
        start = _date(days[0].get("date")) if days and isinstance(days[0], dict) else None
    return start


def venue_notices(itinerary, by_id, brief=None):
    """Venues with no look within NOTICE_FRESH_DAYS before departure -- one line; never a
    failure (many venues have no notice page at all)."""
    from scripts.gate import summary_notice
    start = _start(itinerary, brief)
    seen = {}
    for e in _entries(itinerary):
        if _date(e.get("checked")) and isinstance(e.get("venue"), str):
            seen[e.get("venue")] = max(seen.get(e.get("venue"), datetime.date.min), _date(e["checked"]))
    stale = [v for v in venues(itinerary, by_id)
             if v not in seen or (start is not None and (start - seen[v]).days > NOTICE_FRESH_DAYS)]
    return summary_notice(f"venues have no notice-page look within {NOTICE_FRESH_DAYS} days of departure",
                          stale, "check each venue's own news page and record venue_notices (also when it says nothing)")


def detour_warnings(itinerary):
    """A notice that says it changes a move's route, and that move not saying how it goes
    round it (`detour`) -- one line."""
    from scripts.gate import summary_notice
    rows = {(str(d.get("date")), r.get("time")): r for d in (itinerary or {}).get("days") or []
            for r in d.get("rows") or [] if isinstance(r, dict) and r.get("slot") == "move"}
    where = []
    for e in _entries(itinerary):
        for item in _list(e.get("items")):
            for a in _list(item.get("affects")):
                r = rows.get((str(a.get("date")), a.get("time")))
                if r is None or not str(r.get("detour") or "").strip():
                    where.append(f"{a.get('date')} {a.get('time')}")
    return summary_notice("moves a venue notice closes have no detour", where,
                          "write in `detour` how the move goes round the closure")
