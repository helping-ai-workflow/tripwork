"""Itinerary-gate: mechanical structural checks. Content correctness is NOT
checked here (that is source-verify's job) — only structure.
"""

POI_KEYS = ("meals", "activities", "visits")

def run_gate(pois, days):
    """Return a gate-report dict: {status, checks, failures}.

    Checks:
      - every POI referenced by a day has a geocode
      - every day has at least one meal
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

    checks = [
        {"name": "referenced_pois_geocoded", "passed": not any("geocode" in f or "unknown POI" in f for f in failures)},
        {"name": "days_have_meals", "passed": not any("no meal" in f for f in failures)},
    ]
    return {"status": "pass" if not failures else "fail", "checks": checks, "failures": failures}
