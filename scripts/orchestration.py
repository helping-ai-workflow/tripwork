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
#
# "accommodations stop " / "accommodations.yaml absent" (I2) are rederive_lodging's
# own markers (scripts/rederive.py) -- a re-derived verify_status mismatch or a
# missing geocode_source/resolved_name/accommodations.yaml itself all name the
# candidate this way, and only accommodation-research can fix any of them.
_ROUTES = (
    (("chosen lodging", "required facility", "accommodations stop ",
      "accommodations.yaml absent"), "tripwork:accommodation-research"),
    (("legs[", "legs.yaml absent"), "tripwork:inter-stop-legs"),
    (("routing hop ", "routing.yaml absent"), "tripwork:routing-audit"),
    (("cost.total", "cost.by_category", "cost.yaml absent"), "tripwork:cost-rollup"),
    (("AI-tone ",), "tripwork:itinerary-synthesis"),
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


WHOLE_DOC = ()

# _DEPS[<produced artifact>] = {<upstream artifact>: <projection tuple>}
#
# DERIVED, not authored: every row is the producing skill's Stage Contract Input
# row. tests/test_deps_table.py re-parses those rows and asserts equality, so the
# table and the documentation cannot drift apart.
#
# A projection tuple means "only these top-level keys of the upstream invalidate
# me"; WHOLE_DOC means any change does. Narrow projections matter: chiayi's three
# brief edits fired 12 of its 35 edges under a whole-document rule.
_DEPS = {
    "advisory.yaml": {"trip-brief.yaml": ADVISORY_PROJECTION},
    "candidates.yaml": {"trip-brief.yaml": WHOLE_DOC},
    "verified-pois.yaml": {"candidates.yaml": WHOLE_DOC, "trip-brief.yaml": WHOLE_DOC},
    "routing.yaml": {"verified-pois.yaml": WHOLE_DOC, "trip-brief.yaml": WHOLE_DOC},
    "accommodations.yaml": {"routing.yaml": WHOLE_DOC, "trip-brief.yaml": WHOLE_DOC},
    "legs.yaml": {"trip-brief.yaml": WHOLE_DOC, "routing.yaml": WHOLE_DOC,
                  "accommodations.yaml": WHOLE_DOC},
    "calendar.yaml": {"trip-brief.yaml": WHOLE_DOC},
    "seasonal.yaml": {"trip-brief.yaml": WHOLE_DOC, "routing.yaml": WHOLE_DOC,
                      "accommodations.yaml": WHOLE_DOC},
    "transit.yaml": {"trip-brief.yaml": WHOLE_DOC, "verified-pois.yaml": WHOLE_DOC},
    "cost.yaml": {"trip-brief.yaml": WHOLE_DOC, "accommodations.yaml": WHOLE_DOC,
                  "legs.yaml": WHOLE_DOC},
    "itinerary.yaml": {},   # synthesis reads nine artifacts; see the note below
}

# The artifacts each gate CLI actually opens. Rule 13 and rule 15 compare their
# report against every one of these — not against a single marker file.
GATE_INPUTS = ("itinerary.yaml", "verified-pois.yaml", "trip-brief.yaml",
               "accommodations.yaml", "calendar.yaml", "advisory.yaml",
               "legs.yaml", "routing.yaml", "cost.yaml")
EXPORT_GATE_INPUTS = ("itinerary.yaml", "verified-pois.yaml", "accommodations.yaml",
                      "verified-pois-media.yaml")


def deps_stale(load, artifact):
    """Names of upstreams whose projected content no longer matches what
    `artifact` recorded. FAIL-OPEN: an artifact with no input_fingerprints
    predates the mechanism and is never called stale.

    Fail-open is deliberate and measured. A naive mtime rule fires on 37 of 174
    edges across the six real trips and starts a non-terminating cascade on
    chiayi — destination-research rewrites candidates.yaml with a newer mtime,
    which invalidates verified-pois.yaml, and so on. Treating an absent
    fingerprint as stale would reproduce exactly that. The pressure to record
    fingerprints belongs on the gate (verdicts_rederivable), not on the router.
    """
    doc = load(artifact) or {}
    recorded = doc.get("input_fingerprints") or {}
    out = []
    for upstream, projection in (_DEPS.get(artifact) or {}).items():
        want = recorded.get(upstream)
        if want is None:
            continue
        if want != input_fingerprint(load(upstream) or {}, projection):
            out.append(upstream)
    return out
