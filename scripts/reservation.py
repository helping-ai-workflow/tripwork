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
