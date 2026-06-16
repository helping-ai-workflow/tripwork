"""Source-verify rule engine — pure classification of a candidate POI.

Encodes the three gates from the spec (multi-source, geocode, region match).
The geocode + region results are computed by the skill (using geocode.py) and
passed in; this function holds the decision logic so it is unit-testable.
"""

from urllib.parse import urlsplit
from scripts.geocode import normalize_geocode_keys


def _distinct_netlocs(sources):
    """Set of distinct lower-cased domains across a candidate's source urls."""
    return {urlsplit(s.get("url", "")).netloc.lower() for s in sources if s.get("url")}


def classify_candidate(candidate, geocoded, in_claimed_region,
                        local_lang=None, conflict_detected=False, operating=True):
    """Return (verify_status, note).

    Gates are evaluated in strict order (spec §5.1):

    Gate 0: must be operating — a permanently/temporarily closed (defunct) place
            is 'rejected'. The skill determines `operating` from Google Maps
            ('永久停業' / 'Permanently closed') or an official-site 404. (TW-005)
    Gate 1: >= 2 sources (else 'unverified').
            If local_lang given, at least one source must be in that lang (else 'unverified').
    Gate 2: geocode must resolve (else 'unverified', D7).
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

    # Gate 0: permanently/temporarily closed (defunct) -> rejected.
    if not operating:
        return "rejected", "permanently/temporarily closed (defunct)"

    # Gate 1a: must have >= 2 INDEPENDENT sources. Independence is by distinct domain —
    # two pages of the same site are one source, not two. (TW-023)
    if len(_distinct_netlocs(sources)) < 2:
        return "unverified", "needs >=2 independent sources (distinct domains)"

    # Gate 1b: at least one source in destination's local language
    if local_lang is not None and local_lang not in langs:
        return "unverified", f"needs >=1 source in local language '{local_lang}'"

    # Gate 2: geocode must resolve. D7: a real place Nominatim can't pin is recorded
    # for manual confirmation ('unverified'), never silently dropped ('rejected').
    if not geocoded:
        return "unverified", "geocode unresolved: could not resolve coordinates"

    # Gate 3: cross-source conflict or region mismatch
    if conflict_detected:
        return "conflicting", "cross-source disagreement on rating/hours/address"

    if not in_claimed_region:
        return "conflicting", "geocoded coordinates fall outside the claimed region"

    return "verified", ""


def normalize_and_validate_poi(poi):
    """Canonicalise geocode keys and enforce name_local discipline before a POI
    is treated as verified. Returns (poi, reason); reason None when clean. (dogfood D1)

    Two checks:
    (a) If the POI has a geocode dict, run it through normalize_geocode_keys to
        rename legacy 'lon'/'long' keys to 'lng'. The input dict is NOT mutated.
    (b) If name_local is non-empty and equals district, the POI is flagged —
        name_local must be the venue's real name, not the area
        (cluster_fallback town-name bug, dogfood D1).
    """
    out = dict(poi)
    if out.get("geocode") is not None:
        out["geocode"] = normalize_geocode_keys(out["geocode"])
    name_local = (out.get("name_local") or "").strip()
    district = (out.get("district") or "").strip()
    if name_local and name_local == district:
        return out, (f"name_local '{name_local}' equals district — must be the POI's "
                     f"real name, not the area (cluster_fallback town-name bug)")
    return out, None


def verify_poi(poi, geocoded, in_claimed_region,
               local_lang=None, conflict_detected=False, operating=True):
    """Normalise a POI and classify it in one call.

    Runs normalize_and_validate_poi first (geocode key fix + name_local discipline).
    A non-None reason from the pre-check flips the result to ('rejected', reason)
    immediately, using the same verify_status vocabulary as classify_candidate.
    Otherwise delegates to classify_candidate with the normalised POI.

    Returns (normalised_poi, verify_status, note).
    """
    normalised, reason = normalize_and_validate_poi(poi)
    if reason is not None:
        return normalised, "rejected", reason
    status, note = classify_candidate(
        normalised, geocoded=geocoded, in_claimed_region=in_claimed_region,
        local_lang=local_lang, conflict_detected=conflict_detected, operating=operating,
    )
    return normalised, status, note
