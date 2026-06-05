"""Itinerary-gate: mechanical structural checks. Content correctness is NOT
checked here (that is source-verify's job) — only structure.
"""

from scripts.facilities import stop_meets_required

POI_KEYS = ("meals", "activities", "visits")

def run_gate(pois, days, accommodations=None, facility_needs=None):
    """Return a gate-report dict: {status, checks, failures}.

    Checks:
      - every POI referenced by a day has a geocode
      - every day has at least one meal
      - (if accommodations provided) every overnight stop has chosen lodging
      - (if accommodations provided) chosen lodging meets required facilities
    """
    by_id = {p["id"]: p for p in pois}
    referenced = {pid for d in days for key in POI_KEYS for pid in d.get(key, [])}

    failures = []

    for pid in sorted(referenced):
        p = by_id.get(pid)
        if p is None:
            failures.append(f"day references unknown POI '{pid}'")
        elif "geocode" not in p:
            failures.append(f"POI '{pid}' missing geocode")

    for d in days:
        if not d.get("meals"):
            failures.append(f"day {d.get('date', '?')} has no meal")

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
        {"name": "referenced_pois_geocoded", "passed": not any("geocode" in f or "unknown POI" in f for f in failures)},
        {"name": "days_have_meals", "passed": not any("no meal" in f for f in failures)},
    ]
    if accommodations is not None:
        checks.append({"name": "overnight_stops_have_lodging",
                       "passed": not any("no chosen lodging" in f or "not in candidates" in f for f in failures)})
        checks.append({"name": "required_facilities_met",
                       "passed": not any("missing required facility" in f for f in failures)})
    return {"status": "pass" if not failures else "fail", "checks": checks, "failures": failures}
