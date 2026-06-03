"""Source-verify rule engine — pure classification of a candidate POI.

Encodes the three gates from the spec (multi-source, geocode, region match).
The geocode + region results are computed by the skill (using geocode.py) and
passed in; this function holds the decision logic so it is unit-testable.
"""

def classify_candidate(candidate, geocoded, in_claimed_region, local_lang=None):
    """Return (verify_status, note).

    Gate 1: >= 2 sources, at least one in local_lang (if local_lang given).
    Gate 2: geocode must resolve, else rejected.
    Gate 3: geocode must fall in claimed region, else conflicting.
    """
    sources = candidate.get("sources", [])
    langs = {s.get("lang") for s in sources}

    if not geocoded:
        return "rejected", "geocode failed: could not resolve coordinates"

    if len(sources) < 2:
        return "unverified", "needs >=2 independent sources"

    if local_lang is not None and local_lang not in langs:
        return "unverified", f"needs >=1 source in local language '{local_lang}'"

    if not in_claimed_region:
        return "conflicting", "geocoded coordinates fall outside the claimed region"

    return "verified", ""
