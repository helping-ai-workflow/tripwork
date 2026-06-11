"""Pure orchestration predicates used by the orchestrator's stage-selection
rules — kept here so the otherwise-prose decisions are unit-testable.
"""


def candidates_stale(candidate_ids, verified_ids):
    """True if verified-pois is stale w.r.t. candidates: at least one candidate id
    is absent from verified-pois. The orchestrator then re-runs source-verify for
    the missing ids only (reusing the geocode cache), instead of a later stage.
    """
    return any(cid not in set(verified_ids) for cid in candidate_ids)
