"""Itinerary-gate: mechanical structural + verification-status checks.

Consumes the canonical itinerary dict (schemas/itinerary.schema.json) — NOT an
LLM-reconstructed days list. Every referenced POI must be verified+geocoded; no
POI may be scheduled on a closed day; every must_do must be covered; every
banned/restricted advisory item must be surfaced. Content correctness of the
sources themselves is source-verify's job; this gate checks the assembled plan.
"""
from scripts.facilities import stop_meets_required
from scripts.calendar import poi_closed_on

def _referenced_ids(days):
    ids = set()
    for d in days:
        for row in d.get("rows", []):
            pid = row.get("poi_id")
            if pid:
                ids.add(pid)
        if d.get("lodging"):
            ids.add(d["lodging"])
    return ids

def _day_has_meal(day):
    return any(r.get("slot") == "meal" for r in day.get("rows", []))

def _day_has_lodging(day):
    """Return True if the day has a non-empty lodging field OR a row with slot=='lodging'."""
    if day.get("lodging"):
        return True
    return any(r.get("slot") == "lodging" for r in day.get("rows", []))

def _itinerary_text(itinerary):
    """All free text an advisory topic could be surfaced in: checklist + row texts."""
    parts = list(itinerary.get("checklist", []))
    for d in itinerary.get("days", []):
        for row in d.get("rows", []):
            parts.append(row.get("text", ""))
    return " \n ".join(parts)

def run_gate(pois, itinerary, accommodations=None, facility_needs=None,
             calendar=None, advisory=None, must_do=None):
    """Return a gate-report dict: {status, checks, failures}.

    Args:
        pois:       verified-pois list.
        itinerary:  canonical itinerary dict ({title, checklist, days:[{date,label,rows,lodging}]}).
        calendar:   optional calendar dict; when given, the closed-day check runs.
        advisory:   optional advisory dict; when given, banned/restricted items must be surfaced.
        must_do:    optional list of POI ids that MUST be scheduled.
    """
    by_id = {p["id"]: p for p in pois}
    days = itinerary.get("days", [])
    referenced = _referenced_ids(days)

    failures = []

    for pid in sorted(referenced):
        p = by_id.get(pid)
        if p is None:
            failures.append(f"day references unknown POI '{pid}'")
            continue
        if p.get("verify_status") != "verified":
            failures.append(f"day references non-verified POI '{pid}' ({p.get('verify_status')})")
        if p.get("geocode") is None:
            failures.append(f"POI '{pid}' missing geocode")

    for d in days:
        if not _day_has_meal(d):
            failures.append(f"day {d.get('date', '?')} has no meal")

    # Always-on lodging floor: every non-final day must have resolved lodging.
    # Final day = departure day, no overnight needed.
    for d in days[:-1]:
        if not _day_has_lodging(d):
            failures.append(f"day {d.get('date', '?')} has no resolved lodging")

    closed_check = calendar is not None
    if closed_check:
        for d in days:
            date = d.get("date", "?")
            for row in d.get("rows", []):
                pid = row.get("poi_id")
                p = by_id.get(pid) if pid else None
                if p is None:
                    continue
                closed, reason = poi_closed_on(p, date, calendar)
                if closed:
                    failures.append(f"POI '{pid}' scheduled on closed day {date}: {reason}")

    must_do_check = must_do is not None
    if must_do_check:
        for pid in must_do:
            if pid not in referenced:
                failures.append(f"must_do POI '{pid}' not scheduled in any day")

    # Mandatory-safety-artifact-presence floor (D2-class): an absent advisory is a
    # GATE FAILURE, not a skip. The banned/restricted list lives ONLY inside
    # advisory.yaml — if it is absent we cannot derive what is banned, so the gate
    # cannot verify banned/restricted items are surfaced. Treat as a safety fail.
    advisory_check = advisory is not None
    if not advisory_check:
        failures.append(
            "advisory absent — mandatory safety gate cannot verify "
            "banned/restricted items are surfaced")
    if advisory_check:
        text = _itinerary_text(itinerary)
        for item in advisory.get("items", []):
            if item.get("risk") in ("banned", "restricted"):
                topic = item.get("topic", "")
                if topic and topic not in text:
                    failures.append(
                        f"advisory item '{topic}' ({item.get('risk')}) not surfaced in itinerary")

    if accommodations is not None:
        required = (facility_needs or {}).get("required", [])
        for stop in accommodations.get("stops", []):
            where = stop.get("district", "?")
            chosen_id = stop.get("chosen")
            if chosen_id is None:
                failures.append(f"overnight stop '{where}' has no chosen lodging")
                continue
            chosen = next((c for c in stop.get("candidates", []) if c.get("id") == chosen_id), None)
            if chosen is None:
                failures.append(f"overnight stop '{where}' chosen lodging '{chosen_id}' not in candidates")
                continue
            ok, missing = stop_meets_required(chosen.get("facilities", []), required)
            if not ok:
                failures.append(f"chosen lodging at '{where}' missing required facility: {', '.join(missing)}")

    checks = [
        {"name": "referenced_pois_verified",
         "passed": not any("non-verified POI" in f or "unknown POI" in f for f in failures)},
        {"name": "referenced_pois_geocoded",
         "passed": not any("missing geocode" in f or "unknown POI" in f for f in failures)},
        {"name": "days_have_meals",
         "passed": not any("no meal" in f for f in failures)},
        {"name": "overnight_days_have_lodging",
         "passed": not any("no resolved lodging" in f for f in failures)},
        {"name": "advisory_present",
         "passed": not any("advisory absent" in f for f in failures)},
    ]
    if closed_check:
        checks.append({"name": "no_closed_day_violation",
                       "passed": not any("closed day" in f for f in failures)})
    if must_do_check:
        checks.append({"name": "must_do_covered",
                       "passed": not any("must_do POI" in f for f in failures)})
    if advisory_check:
        checks.append({"name": "advisory_items_surfaced",
                       "passed": not any("not surfaced in itinerary" in f for f in failures)})
    if accommodations is not None:
        checks.append({"name": "overnight_stops_have_lodging",
                       "passed": not any("no chosen lodging" in f or "not in candidates" in f for f in failures)})
        checks.append({"name": "required_facilities_met",
                       "passed": not any("missing required facility" in f for f in failures)})

    return {"status": "pass" if not failures else "fail", "checks": checks, "failures": failures}
