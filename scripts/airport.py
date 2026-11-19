"""Airports: which side of security a shop is on (#33) and when to be at the airport
for a flight (#23). Both read the itinerary's rows in order; messages carry dates, row
ordinals and POI ids only (day_chain's rule: free text never picks a route)."""
from scripts.transfer import minutes

# #23 (user's pick, 2026-11-18): with no published advice, be at the airport this long
# before check-in closes.
CHECK_IN_BUFFER_MINS = {True: 60, False: 30}       # international / domestic


def _rows(day):
    return [r for r in day.get("rows") or [] if isinstance(r, dict)]


def _flies(day, legs):
    return any(r.get("slot") == "move" and _fields(r, legs).get("mode") == "flight" for r in _rows(day))


def _fields(row, legs):
    """A move row's flight fields: its leg's when it renders one, else its own."""
    li = row.get("leg_index")
    items = (legs or {}).get("legs") or []
    if isinstance(li, int) and not isinstance(li, bool) and 0 <= li < len(items) and isinstance(items[li], dict):
        return dict(items[li], **{k: v for k, v in row.items() if k in ("time",)})
    return row


def security_failures(itinerary, by_id):
    """#33: an airside shop before passing security, a landside one after it, or an
    airside shop on a day with no security transfer row to tell before from after."""
    out = []
    for d in (itinerary or {}).get("days") or []:
        rows = _rows(d)
        gate = next((j for j, r in enumerate(rows) if r.get("slot") == "transfer" and r.get("security")), None)
        for j, r in enumerate(rows):
            zone = (by_id.get(r.get("poi_id")) or {}).get("security_zone")
            where = f"security zone order: {d.get('date')} row {j} ({r.get('poi_id')})"
            if zone == "airside" and gate is None:
                out.append(f"{where} is airside but the day has no security transfer row")
            elif zone == "airside" and j < gate:
                out.append(f"{where} is airside but comes before passing security")
            elif zone == "landside" and gate is not None and j > gate:
                out.append(f"{where} is landside but comes after passing security")
    return out


def security_notices(itinerary, by_id, legs=None):
    """#33: a shop whose side of security no source says, on a day with a flight."""
    from scripts.gate import summary_notice
    ids = []
    for d in (itinerary or {}).get("days") or []:
        if not _flies(d, legs):
            continue
        ids += [r.get("poi_id") for r in _rows(d)
                if (by_id.get(r.get("poi_id")) or {}).get("security_zone") == "unknown"]
    return summary_notice("airport places on a flight day have no known side of security", ids,
                          "record security_zone from a source that says before or after security")


def be_at_airport(flight):
    """Minutes after midnight to be at the airport for `flight` (a row's or leg's fields
    with its departure `time`/`depart`), or None when neither the published advice nor
    the check-in close is recorded."""
    dep = minutes(flight.get("time") or flight.get("depart"))
    if dep is None:
        return None
    if isinstance(flight.get("arrive_by_mins"), int):
        return dep - flight["arrive_by_mins"]
    if isinstance(flight.get("check_in_close_mins"), int):
        intl = flight.get("international", True) is not False
        return dep - flight["check_in_close_mins"] - CHECK_IN_BUFFER_MINS[intl]
    return None


def _arrive(row, legs):
    f = _fields(row, legs)
    t = minutes(row.get("time"))
    m = row.get("mins_max", row.get("mins", f.get("duration_mins")))
    if t is None or not isinstance(m, (int, float)) or isinstance(m, bool):
        return None
    return t + m


def check_in_failures(itinerary, legs=None):
    """#23: the move to the airport, at the upper end of its estimate (mins_max), arrives
    after the time to be there. The traveller decides what gives (stop: check_in_missed)."""
    out = []
    for d in (itinerary or {}).get("days") or []:
        rows = _rows(d)
        for j, r in enumerate(rows):
            if r.get("slot") != "move" or _fields(r, legs).get("mode") != "flight":
                continue
            need = be_at_airport(_fields(r, legs))
            k = j - 1
            while k >= 0 and rows[k].get("slot") == "transfer":
                k -= 1
            if need is None or k < 0 or rows[k].get("slot") != "move":
                continue
            arrive = _arrive(rows[k], legs)
            if arrive is not None and arrive > need:
                out.append(f"check-in missed: {d.get('date')} row {j} flight -- the move before it "
                           f"reaches the airport at {arrive // 60:02d}:{arrive % 60:02d}, "
                           f"later than {need // 60:02d}:{need % 60:02d}")
    return out


def check_in_notices(itinerary, legs=None):
    """#23: flights with no check-in close and no published arrival advice."""
    from scripts.gate import summary_notice
    where = []
    for d in (itinerary or {}).get("days") or []:
        for r in _rows(d):
            if r.get("slot") == "move" and _fields(r, legs).get("mode") == "flight" \
                    and be_at_airport(_fields(r, legs)) is None:
                where.append(f"{d.get('date')} {r.get('time') or ''}".strip())
    return summary_notice("flights have no check-in close time", where,
                          "record check_in_close_mins from the airline's page (no default is assumed)")
