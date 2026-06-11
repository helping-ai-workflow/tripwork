"""Inter-stop leg feasibility — pure classification of a city-to-city leg.

Mirrors the verify.py / distance.py pure-classifier style. The leg facts
(duration, last service, which train) are researched by the skill and passed in;
this module holds the feasibility decision so it is unit-testable.
"""
from scripts.hours import to_minutes


def drive_too_long(duration_mins, max_single_drive_mins=300):
    """True if a single-day drive leg exceeds the safe single-day maximum."""
    return duration_mins > max_single_drive_mins


def misses_last_service(planned_depart_hhmm, last_service_hhmm):
    """True if a planned same-day departure is later than the last service."""
    return to_minutes(planned_depart_hhmm) > to_minutes(last_service_hhmm)


def classify_leg(leg, max_single_drive_mins=300):
    """Return (status, reason).

    status is one of:
        'ok'                 — feasible as planned.
        'drive_too_long'     — a drive leg over the single-day maximum.
        'missed_last_service'— a transit leg whose planned same-day departure is
                               after the last train/bus.

    leg: dict with 'mode' and, per mode, 'duration_mins' (drive) or 'depart' +
    'last_service' (transit). Missing transit times mean the leg cannot fail the
    last-service check (returns 'ok').
    """
    if leg.get("mode") == "drive":
        dur = leg.get("duration_mins")
        if dur is None or dur == 0:
            raise ValueError(
                f"drive leg {leg.get('from','?')}->{leg.get('to','?')} has no measured "
                "duration_mins; cannot classify feasibility (never default to 0)")
        if drive_too_long(dur, max_single_drive_mins):
            return "drive_too_long", (
                f"drive leg {dur} min exceeds max {max_single_drive_mins} min for one day")
        return "ok", ""

    depart = leg.get("depart")
    last = leg.get("last_service")
    if depart and last and misses_last_service(depart, last):
        return "missed_last_service", f"departure {depart} is after the last service {last}"
    return "ok", ""
