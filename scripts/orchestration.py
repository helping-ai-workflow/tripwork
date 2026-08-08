"""Pure orchestration predicates used by the orchestrator's stage-selection
rules — kept here so the otherwise-prose decisions are unit-testable.
"""
import hashlib
import json


def candidates_stale(candidate_ids, verified_ids):
    """True if verified-pois is stale w.r.t. candidates: at least one candidate id
    is absent from verified-pois. The orchestrator then re-runs source-verify for
    the missing ids only (reusing the geocode cache), instead of a later stage.
    """
    return any(cid not in set(verified_ids) for cid in candidate_ids)


# Rule 13.5 failure-class routing, in priority order. accommodation stays FIRST:
# scripts/orchestration.py's original note records a deliberate exception — "has
# no resolved lodging" is a missing itinerary ROW and routes to synthesis, not
# accommodation. None of the groups below contains "lodging", so that survives,
# but the ordering leaves it one careless marker away from inverting.
_ROUTES = (
    (("chosen lodging", "required facility"), "tripwork:accommodation-research"),
    (("legs[", "legs.yaml absent"), "tripwork:inter-stop-legs"),
    (("routing hop ", "routing.yaml absent"), "tripwork:routing-audit"),
    (("cost.total", "cost.by_category", "cost.yaml absent"), "tripwork:cost-rollup"),
)


def route_gate_failures(failures):
    """Return the stage skill an itinerary-gate FAIL should route to.

    A re-derivation failure names a field only its PRODUCING stage can write —
    synthesis cannot add `km` to a routing hop. Before v0.33.0 everything that
    was not a lodging defect fell through to synthesis, so feedback could never
    cross back past accommodation-research.
    """
    for markers, target in _ROUTES:
        if any(m in f for f in failures for m in markers):
            return target
    return "tripwork:itinerary-synthesis"


def input_fingerprint(doc, projection):
    """Stable hash of the projected fields of an upstream artifact.

    `projection` is a tuple of top-level keys; an empty tuple means the whole
    document. Normalisation: project, then JSON-serialise with sorted keys and
    no whitespace, so key order and YAML formatting cannot change the result.
    An absent key and an explicit null collapse to the same value — correct for
    trip-brief, where `airline` is simply omitted on a domestic trip.

    Why not mtime: rule 11 compared whole-file mtimes while its own comment named
    three fields, so editing must_do re-ran travel-advisory and rewrote a
    byte-identical advisory. This is a WIRE FORMAT — changing any step below
    silently invalidates every fingerprint in the wild and routes every trip
    backwards one stage. (TW-067)
    """
    keys = projection or tuple(sorted(doc or {}))
    projected = {k: (doc or {}).get(k) for k in sorted(keys)}
    blob = json.dumps(projected, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# Rule 11's projection: the three fields next_stage.py's own comment already
# named as the anchor. Kept beside the primitive so the two cannot drift.
ADVISORY_PROJECTION = ("airline", "dates", "destination")
