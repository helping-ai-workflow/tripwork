"""Transfer points between two moves (#37) and the waits around them.

A traveller who steps off one vehicle and onto the next is somewhere: a station, a
stop, an airport. Two move rows straight after each other hide that place, and the
wait between them (a 65-minute wait for an express was invisible in one trip). A
`slot: transfer` row names it; these helpers measure the wait and find the joins that
still have none.
"""


def minutes(hhmm):
    """'HH:MM' -> minutes after midnight, or None (the reader's rule; a copy because the
    reader package imports this module)."""
    try:
        h, m = str(hhmm).split(":")
        return int(h) * 60 + int(m)
    except (TypeError, ValueError):
        return None

# #37 (user's pick, 2026-11-18): a wait longer than this with no transfer point is a
# warning; shorter ones are an ordinary change of vehicle.
TRANSFER_WAIT_WARN_MINS = 15


def _end(row):
    t, m = minutes(row.get("time")), row.get("mins")
    if t is None or not isinstance(m, (int, float)) or isinstance(m, bool):
        return None
    return t + m


def wait_mins(rows, j):
    """Minutes between the move before row j arriving and the move after it leaving, or
    None when a time or duration is missing."""
    if not (0 < j < len(rows) - 1):
        return None
    end, nxt = _end(rows[j - 1]), minutes(rows[j + 1].get("time"))
    return None if end is None or nxt is None else nxt - end


def bare_joins(itinerary):
    """[(date, time, gap_or_None)] for every two move rows straight after each other.
    A join next to a flight is left to the airport check (#23)."""
    out = []
    for d in (itinerary or {}).get("days") or []:
        rows = [r for r in d.get("rows") or [] if isinstance(r, dict)]
        for j in range(1, len(rows)):
            a, b = rows[j - 1], rows[j]
            if a.get("slot") != "move" or b.get("slot") != "move":
                continue
            if "flight" in (a.get("mode"), b.get("mode")):
                continue
            end, nxt = _end(a), minutes(b.get("time"))
            gap = None if end is None or nxt is None else nxt - end
            out.append((str(d.get("date")), b.get("time") or "", gap))
    return out


def transfer_notices(itinerary):
    from scripts.gate import summary_notice
    return summary_notice("joins of two moves have no transfer point",
                          [f"{d} {t}".strip() for d, t, _g in bare_joins(itinerary)],
                          "add a `slot: transfer` row naming where the traveller changes")


def transfer_warnings(itinerary):
    from scripts.gate import summary_notice
    long_waits = [f"{d} {t} ({g} min)" for d, t, g in bare_joins(itinerary)
                  if g is not None and g > TRANSFER_WAIT_WARN_MINS]
    return summary_notice(f"waits over {TRANSFER_WAIT_WARN_MINS} min have no transfer point",
                          long_waits, "name the station or stop the traveller waits at")


def _with_en(local, en):
    return f"{local}（{en}）" if local and en and en not in local else (local or en or "")


def move_facts(row):
    """[(label, value)] a move row records for the platform (#32), each name with the
    operator's official English beside it when recorded (#22). [] for a row with none."""
    out = []
    for label, key in (("上車", "board_at"), ("車次", "route"), ("下車", "alight_at")):
        v = _with_en(row.get(key), row.get(f"{key}_en"))
        if v:
            out.append((label, v))
    for label, key in (("付款", "pay"), ("錯過", "next_service")):
        if row.get(key):
            out.append((label, row[key]))
    return out


def machine_line(row):
    """#22: what to pick on an English ticket machine -- 'Sapporo → Asahikawa，Lilac 11' --
    or '' when the row lacks the official English names."""
    a, b = row.get("board_at_en"), row.get("alight_at_en")
    if not (a and b):
        return ""
    return f"{a} → {b}" + (f"，{row['route_en']}" if row.get("route_en") else "")


def transfer_line(rows, j):
    """A transfer row read aloud: '旭川駅（6番のりば・等 18 分）'."""
    r = rows[j]
    extra = [r["platform"]] if r.get("platform") else []
    w = wait_mins(rows, j)
    if w is not None and w > 0:
        extra.append(f"等 {w} 分")
    return f"{r.get('place') or ''}" + (f"（{'・'.join(extra)}）" if extra else "")


def missing_en_notices(itinerary):
    """#22: rail and flight moves without the operator's English names -- one line."""
    from scripts.gate import summary_notice
    where = []
    for d in (itinerary or {}).get("days") or []:
        for r in d.get("rows") or []:
            if isinstance(r, dict) and r.get("slot") == "move" and r.get("mode") in ("rail", "flight") \
                    and not (r.get("board_at_en") and r.get("alight_at_en")):
                where.append(f"{d.get('date')} {r.get('time') or ''}".strip())
    return summary_notice("rail/flight moves have no official English station names", where,
                          "record board_at_en / alight_at_en from the operator's English page")


def bare_transit_notices(itinerary):
    """#32: a bus or rail move with neither words nor any recorded fact -- one line. A row
    whose text carries the stop and route is fine as it is."""
    from scripts.gate import summary_notice
    where = []
    for d in (itinerary or {}).get("days") or []:
        for r in d.get("rows") or []:
            if isinstance(r, dict) and r.get("slot") == "move" and r.get("mode") in ("bus", "rail") \
                    and not str(r.get("text") or "").strip() and not move_facts(r):
                where.append(f"{d.get('date')} {r.get('time') or ''}".strip())
    return summary_notice("bus/rail moves say nothing about where to board or which line", where,
                          "write the stop and route in the row, or board_at / route")
