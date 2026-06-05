"""Accommodation facility logic — required-facility match, periodic coverage,
and reception-hours arrival check. Pure functions, mirroring the
verify.py / hours.py / distance.py split.
"""
from scripts.hours import closing_status


def stop_meets_required(facilities, required):
    """Return (ok, missing): does `facilities` contain every `required` token?"""
    have = set(facilities or [])
    missing = [t for t in (required or []) if t not in have]
    return (not missing, missing)


def coverage_gaps(stops, max_gap_nights):
    """Runs of consecutive nights without the facility that exceed max_gap_nights.

    Args:
        stops: ordered list of {"nights": int, "has_facility": bool}.
        max_gap_nights: max tolerated consecutive nights without the facility.

    Returns list of {"after_index": int, "run_nights": int}. A stop WITH the
    facility resets the run. Advisory data — the caller decides how to surface it.
    """
    gaps = []
    run = 0
    run_start = 0
    for i, s in enumerate(stops):
        if s.get("has_facility"):
            if run > max_gap_nights:
                gaps.append({"after_index": run_start, "run_nights": run})
            run = 0
            run_start = i + 1
        else:
            run += int(s.get("nights", 0))
    if run > max_gap_nights:
        gaps.append({"after_index": run_start, "run_nights": run})
    return gaps


def reception_ok(arrival, reception_close, late_checkin=False):
    """True if check-in is possible: late check-in allowed, or arrival before close.

    Reuses hours.closing_status; arrival at/after reception close with no late
    check-in is a lock-out.
    """
    if late_checkin:
        return True
    status, _ = closing_status(arrival, reception_close)
    return status not in ("closed", "after_last_call")
