"""Pure orchestration predicates used by the orchestrator's stage-selection
rules — kept here so the otherwise-prose decisions are unit-testable.
"""


def candidates_stale(candidate_ids, verified_ids):
    """True if verified-pois is stale w.r.t. candidates: at least one candidate id
    is absent from verified-pois. The orchestrator then re-runs source-verify for
    the missing ids only (reusing the geocode cache), instead of a later stage.
    """
    return any(cid not in set(verified_ids) for cid in candidate_ids)


# Rule 13.5 failure-class routing. Lodging/facility failures trace to the
# accommodation stage; everything else (meal / unknown POI / non-verified /
# geocode / closed-day / must_do / advisory-surface / hygiene) traces to the
# itinerary author. NOTE: "has no resolved lodging" (the always-on per-day
# floor) is itinerary-derived — a missing lodging ROW is a synthesis defect,
# so it deliberately routes to synthesis, not accommodation.
_ACCOM_MARKERS = ("chosen lodging", "required facility")


def route_gate_failures(failures):
    """Return the stage skill an itinerary-gate FAIL should route to."""
    if any(m in f for f in failures for m in _ACCOM_MARKERS):
        return "tripwork:accommodation-research"
    return "tripwork:itinerary-synthesis"
