"""Source-verify rule engine — pure classification of a candidate POI.

Encodes the three gates from the spec (multi-source, geocode, region match).
The geocode + region results are computed by the skill (using geocode.py) and
passed in; this function holds the decision logic so it is unit-testable.
"""

def classify_candidate(candidate, geocoded, in_claimed_region,
                        local_lang=None, conflict_detected=False):
    """Return (verify_status, note).

    Gates are evaluated in strict order (spec §5.1):

    Gate 1: >= 2 sources (else 'unverified').
            If local_lang given, at least one source must be in that lang (else 'unverified').
    Gate 2: geocode must resolve (else 'rejected').
    Gate 3a: conflict_detected — cross-source disagreement on rating/hours/address
             (else 'conflicting').  Computed by the skill and signalled via this param.
    Gate 3b: geocoded point must fall within the claimed region (else 'conflicting').

    Args:
        candidate:        dict with 'sources' list, each item having 'lang'.
        geocoded:         bool — True if coordinates were successfully resolved.
        in_claimed_region: bool — True if coordinates fall inside the claimed district.
        local_lang:       optional str, ISO-639 code for the destination's local language.
        conflict_detected: bool (default False) — True when the skill has detected
                          cross-source disagreement on rating/hours/address.
    """
    sources = candidate.get("sources", [])
    langs = {s.get("lang") for s in sources}

    # Gate 1a: must have >= 2 independent sources
    if len(sources) < 2:
        return "unverified", "needs >=2 independent sources"

    # Gate 1b: at least one source in destination's local language
    if local_lang is not None and local_lang not in langs:
        return "unverified", f"needs >=1 source in local language '{local_lang}'"

    # Gate 2: geocode must resolve
    if not geocoded:
        return "rejected", "geocode failed: could not resolve coordinates"

    # Gate 3: cross-source conflict or region mismatch
    if conflict_detected:
        return "conflicting", "cross-source disagreement on rating/hours/address"

    if not in_claimed_region:
        return "conflicting", "geocoded coordinates fall outside the claimed region"

    return "verified", ""
