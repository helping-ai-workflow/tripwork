"""The traveller's reservations (reservations.yaml): matching, masking, wording.

One owner for every rule: the itinerary gate, export-gate, the reader and the md page all
call these functions, and so do the tests. The file is the traveller's own data -- written
only by record-reservation, never by synthesis -- so a re-planned itinerary cannot drop a
booking silently: an entry that no longer matches a row is a gate failure.
"""
import re

STATUSES = ("booked", "todo", "none", "self")
LABEL = {"booked": "已訂", "todo": "還要訂", "none": "不用訂", "self": "自理"}
REF_LABEL = {"move": "訂位編號", "stop": "預約編號", "lodging": "訂房編號"}
MASK = "••••"


def mask_ref(ref):
    """At most the last four characters, and never fewer than four hidden (a 6-character
    PNR shows two). The fixed prefix does not give away the length."""
    code = re.sub(r"[^0-9A-Za-z]", "", str(ref or ""))
    n = max(0, min(4, len(code) - 4))
    return MASK + (code[-n:] if n else "")


def kind_of(res):
    if res.get("from") and res.get("to"):
        return "move"
    if res.get("lodging"):
        return "lodging"
    return "stop"


def entries(reservations):
    return [r for r in (reservations or {}).get("reservations") or [] if isinstance(r, dict)]


def _name(poi):
    return (poi or {}).get("name_zh") or (poi or {}).get("name_display") or (poi or {}).get("name_local") or ""


def what(res, poi_map=None):
    """How a message names the entry: the place, the stay, or the move's two ends."""
    k = kind_of(res)
    if k == "move":
        return f"{res['from']}→{res['to']}"
    pid = res.get("lodging") if k == "lodging" else res.get("poi_id")
    return _name((poi_map or {}).get(pid)) or str(pid)


def _ends(row, legs):
    li = row.get("leg_index")
    items = (legs or {}).get("legs") or []
    leg = items[li] if isinstance(li, int) and not isinstance(li, bool) and 0 <= li < len(items) else {}
    return row.get("from") or leg.get("from"), row.get("to") or leg.get("to")


def lodging_starts(itinerary):
    """{(check-in date, lodging id): day index} -- one per run of consecutive nights."""
    out, prev = {}, None
    for i, day in enumerate(itinerary.get("days") or []):
        lid = day.get("lodging")
        if lid and lid != prev:
            out[(str(day.get("date")), lid)] = i
        prev = lid
    return out


def _candidates(itinerary, legs, res):
    k = kind_of(res)
    if k == "lodging":
        i = lodging_starts(itinerary).get((res["date"], res["lodging"]))
        return [(i, None)] if i is not None else []
    out = []
    for i, day in enumerate(itinerary.get("days") or []):
        if str(day.get("date")) != res["date"]:
            continue
        for j, row in enumerate(day.get("rows") or []):
            if not isinstance(row, dict):
                continue
            if k == "move":
                if row.get("slot") == "move" and _ends(row, legs) == (res["from"], res["to"]):
                    out.append((i, j))
            elif row.get("poi_id") == res.get("poi_id") and (not res.get("time") or row.get("time") == res["time"]):
                out.append((i, j))
    return out


def match(itinerary, legs, reservations, poi_map=None):
    """(pairs, failures). A pair is {res, kind, date, day, row} (row is None for a stay).
    Every failure starts with 'reservation ' -- the route marker to record-reservation."""
    pairs, failures, taken = [], [], {}
    days = itinerary.get("days") or []
    for res in entries(reservations):
        name = f"{res.get('date')} {what(res, poi_map)}"
        found = _candidates(itinerary, legs, res)
        if not found:
            failures.append(f"reservation has no row: {name}")
            continue
        if len(found) > 1:
            failures.append(f"reservation matches several rows: {name} -- add its time")
            continue
        day, row = found[0]
        if (day, row) in taken:
            failures.append(f"reservation duplicates another on the same row: {name}")
            continue
        taken[(day, row)] = res
        if res.get("status") == "self" and (row is None or days[day]["rows"][row].get("slot") != "meal"):
            failures.append(f"reservation self is for meals only: {name}")
            continue
        pairs.append({"res": res, "kind": kind_of(res), "date": res["date"], "day": day, "row": row})
    return pairs, failures


def detail_pairs(res, kind):
    """[(label, value)]: the masked number first, then the traveller's details in order."""
    out = [(REF_LABEL[kind], mask_ref(res["ref"]))] if res.get("ref") else []
    out += [(d["label"], d["value"]) for d in res.get("details") or [] if isinstance(d, dict)]
    return out


def summary(res, kind):
    """'已訂・訂房編號 ••••3907・15:00 起・三人房，含早餐' -- status, masked number, detail values."""
    parts = [LABEL.get(res.get("status"), "")]
    if res.get("ref"):
        parts.append(f"{REF_LABEL[kind]} {mask_ref(res['ref'])}")
    parts += [d["value"] for d in res.get("details") or [] if isinstance(d, dict)]
    return "・".join(p for p in parts if p)


def texts(reservations):
    """Every traveller-written string a renderer shows, for the gate's text checks. Never the ref."""
    out = []
    for res in entries(reservations):
        for d in res.get("details") or []:
            if isinstance(d, dict):
                out += [str(d.get("label") or ""), str(d.get("value") or "")]
    return [s for s in out if s]


def _row(itinerary, pair):
    return None if pair["row"] is None else itinerary["days"][pair["day"]]["rows"][pair["row"]]


def _booking_name(itinerary, legs, pair, poi_map):
    res, row = pair["res"], _row(itinerary, pair)
    if pair["kind"] == "move":
        li = (row or {}).get("leg_index")
        items = (legs or {}).get("legs") or []
        leg = items[li] if isinstance(li, int) and 0 <= li < len(items) else {}
        return leg.get("service") or (row or {}).get("text") or what(res)
    return what(res, poi_map)


def _people(res):
    return next((d["value"] for d in res.get("details") or [] if isinstance(d, dict) and d.get("label") == "人數"), "")


def visible_checklist(itinerary, legs, reservations, poi_map):
    """The checklist the traveller sees: a 預約 line for something already booked is gone
    (linked by poi_id / leg_index; an old line with neither is matched by its due ==
    the place's booking.opens_at), and a booking still to make adds one line unless a
    written line already points at it. Derived at render time, never written back."""
    items = [it if isinstance(it, dict) else {"kind": "出發前確認", "task": str(it)}
             for it in itinerary.get("checklist") or []]
    pairs = match(itinerary, legs, reservations, poi_map)[0]
    days = itinerary.get("days") or []

    def target(pair):
        row = _row(itinerary, pair)
        if pair["kind"] == "move":
            return ("leg", (row or {}).get("leg_index"))
        return ("poi", pair["res"].get("poi_id") or pair["res"].get("lodging"))
    booked = {target(p) for p in pairs if p["res"].get("status") == "booked"}
    opens = {((poi_map.get(pid) or {}).get("booking") or {}).get("opens_at")
             for kind, pid in booked if kind == "poi"} - {None}

    def points_at(it):
        if it.get("poi_id"):
            return ("poi", it["poi_id"])
        if isinstance(it.get("leg_index"), int):
            return ("leg", it["leg_index"])
        return None

    out = []
    for it in items:
        if it.get("kind") == "預約":
            t = points_at(it)
            if t in booked or (t is None and it.get("due") in opens):
                continue
        out.append(it)
    written = {points_at(it) for it in items if it.get("kind") == "預約"}
    for p in pairs:
        if p["res"].get("status") != "todo" or target(p) in written:
            continue
        row = _row(itinerary, p) or {}
        head = f"訂{_booking_name(itinerary, legs, p, poi_map)}" + (f" {row['time']}" if row.get("time") else "")
        people = _people(p["res"])
        y, m, d = str(days[p["day"]].get("date")).split("-")
        out.append({"kind": "預約", "task": head + (f"，{people}" if people else ""),
                    "origin": f"D{p['day'] + 1}・{int(m)}/{int(d)}"})
    return out
