"""Source-verify rule engine — pure classification of a candidate POI.

Encodes the three gates from the spec (multi-source, geocode, region match).
The geocode + region results are computed by the skill (using geocode.py) and
passed in; this function holds the decision logic so it is unit-testable.
"""

import datetime
from urllib.parse import urlsplit
from scripts.geocode import normalize_geocode_keys, name_matches


# Explicit "the geocoder ran and returned no name" marker. A caller must pass
# either a resolved display_name or this sentinel; omitting the argument used to
# mean "skip Gate 2b", which is silence dressed as a pass.
NO_RESOLVED_NAME = object()


def _distinct_netlocs(sources):
    """Set of distinct lower-cased domains across a candidate's source urls."""
    return {urlsplit(s.get("url", "")).netloc.lower() for s in sources if s.get("url")}


# Google Places `businessStatus` vocabulary — the operating signal source-verify
# must obtain for Gate 0. (P1)
_OPERATING_STATUS = {
    "OPERATIONAL": True,
    "CLOSED_TEMPORARILY": False,
    "CLOSED_PERMANENTLY": False,
}


# How old a sourced operating signal may be before it stops meaning anything.
# Shorter than hours' 12 months (skills/source-verify/SKILL.md:41) because a
# restaurant closes permanently faster than it changes its closing time.
OPERATING_MAX_AGE_DAYS = 90


def _parse_iso(d):
    try:
        return datetime.date.fromisoformat(str(d))
    except (TypeError, ValueError):
        return None


def operating_from_status(business_status, today=None):
    """Map a sourced operating signal to (operating, reason).

    Accepts the sourced object form
    ``{"status": <enum>, "source_url": "https://…", "as_of": "YYYY-MM-DD"}``
    and, for the transition, the legacy bare string — which is now treated as
    NOT a signal. That is the whole point of TW-063: the bare enum recorded a
    verdict with no way to record where it came from, so 17 of 17 dogfood POIs
    carried a hand-typed OPERATIONAL and review could not tell. The user caught
    a temporarily-closed restaurant by eye; Gate 0 did not.

    Returns (True | False | None, reason). None means "not established" and the
    caller MUST record `unverified` — never default to operating. (P1)
    """
    if business_status is None:
        return None, "no business_status signal obtained"
    if isinstance(business_status, str):
        key = business_status.strip().upper()
        if not key:
            return None, "no business_status signal obtained"
        return None, ("business_status is self-attested: a bare string records a "
                      "verdict with no source_url and no as_of, so it cannot be "
                      "reviewed. Record {status, source_url, as_of}")
    if not isinstance(business_status, dict):
        return None, "business_status is neither a status object nor a string"

    key = str(business_status.get("status") or "").strip().upper()
    if key not in _OPERATING_STATUS:
        return None, f"unrecognised business_status.status {key!r}"
    if not str(business_status.get("source_url") or "").strip():
        return None, "business_status has no source_url — the signal is unauditable"

    as_of = _parse_iso(business_status.get("as_of"))
    if as_of is None:
        return None, "business_status has no valid as_of date"
    ref = today or datetime.date.today()
    age = (ref - as_of).days
    if age > OPERATING_MAX_AGE_DAYS:
        return None, (f"business_status.as_of {as_of.isoformat()} is {age} days old "
                      f"(max {OPERATING_MAX_AGE_DAYS}) — stale, re-check before scheduling")
    return _OPERATING_STATUS[key], ""


def has_existence_proof(poi):
    """True when something independent of the coordinate says this place exists.

    A cluster centroid is the district's midpoint — it is a position, not
    evidence. Two proofs are accepted because source-verify already collects
    both: a source the skill flagged `official: true` (its own site or booking
    page), or a `gmaps_place_id` recorded while the operating check was open
    (skills/source-verify/SKILL.md:30). (TW-062)
    """
    if (poi.get("gmaps_place_id") or "").strip():
        return True
    return any(s.get("official") for s in (poi.get("sources") or []))


def classify_candidate(candidate, geocoded, in_claimed_region,
                        local_lang=None, conflict_detected=False, operating=True,
                        name_match=True):
    """Return (verify_status, note).

    Gates are evaluated in strict order (spec §5.1):

    Gate 0: must be operating — a permanently/temporarily closed (defunct) place
            is 'rejected'. The skill determines `operating` via `operating_from_status`
            (this module) from the POI's sourced `business_status` object
            ({status, source_url, as_of}, TW-063) — never from a bare hand-typed
            string, and never by reading a Google Maps card or inferring closure
            from a site 404 (both measured dead in dogfood). (TW-005)
    Gate 1: >= 2 sources (else 'unverified').
            If local_lang given, at least one source must be in that lang (else 'unverified').
    Gate 2: geocode must resolve (else 'unverified', D7).
    Gate 2b: name_match must be determined and true (else 'unverified' when
             undetermined, 'conflicting' when a real mismatch — see below).
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
        name_match:       True (matches / not disputed), False (a real mismatch ->
                          'conflicting'), or None (undetermined — the caller never
                          supplied a resolved_name to compare against -> 'unverified',
                          not a silent pass). Default True keeps existing callers that
                          never pass this argument unaffected.
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

    # Gate 2b (P2): the resolved place must actually correspond to the queried
    # venue. A wrong-but-plausible top hit (renamed nearby place, name drift) is
    # 'conflicting', never 'verified'. The skill computes name_match via
    # geocode.name_matches(queried name, resolved display_name).
    # name_match is None when the caller never supplied a resolved_name to compare
    # (TW-062/2): that's "cannot run", not "passed" — 'unverified', not the 'False'
    # case's 'conflicting'. None and False must not collapse to the same branch.
    if name_match is None:
        return (
            "unverified",
            "no resolved_name supplied — Gate 2b (name match) cannot run. Pass the "
            "geocoder's display_name, or verify.NO_RESOLVED_NAME if it returned none",
        )
    if not name_match:
        return "conflicting", "name mismatch: resolved place does not correspond to the queried venue"

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
               local_lang=None, conflict_detected=False, resolved_name=None,
               today=None):
    """Normalise a POI and classify it in one call.

    Runs normalize_and_validate_poi first (geocode key fix + name_local discipline).
    A non-None reason from the pre-check flips the result to ('rejected', reason)
    immediately, using the same verify_status vocabulary as classify_candidate.

    Gate 0 (P1) is enforced HERE, not defaulted: the operating signal is read from
    the POI's `business_status` field (the consumer/agent records it from Google
    Places or an official-site check). An absent/unknown signal -> 'unverified'
    (never a silent 'verified'); a CLOSED signal -> 'rejected' before geocode gates.
    Otherwise delegates to classify_candidate with the normalised POI.

    Returns (normalised_poi, verify_status, note).
    """
    normalised, reason = normalize_and_validate_poi(poi)
    if reason is not None:
        return normalised, "rejected", reason

    operating, why = operating_from_status(normalised.get("business_status"), today=today)
    if operating is None:
        return (normalised, "unverified",
                f"operating status not established: {why} (Gate 0 cannot pass)")
    if not operating:
        return normalised, "rejected", "permanently/temporarily closed (defunct)"

    # Gate 2b (P2) input. Omitting resolved_name used to set name_match=True, so a
    # caller that forgot the argument got a verified POI with this gate never
    # executed — the same failure shape as TW-062's Gate 2, one gate over. The
    # default is now refusal: pass the resolved display_name, or NO_RESOLVED_NAME
    # to state that the lookup ran and produced none. Left as None here (rather
    # than returning early) so classify_candidate's gate ORDER decides when this
    # fires — Gate 1 (sources) and Gate 2 (geocoded) must still fire first per
    # skills/source-verify/SKILL.md:28's documented strict order.
    queried = normalised.get("name_local") or normalised.get("name_display") or ""
    if resolved_name is None:
        name_match = None
    elif resolved_name is NO_RESOLVED_NAME:
        name_match = True
    else:
        name_match = name_matches(queried, resolved_name)

    # Gate 2c (TW-062): a centroid fallback is not a geocode. Nominatim finding
    # nothing must not outrank Nominatim finding a name that disagrees — which is
    # `conflicting`. Without this, the incentive inverts: the POIs that cannot be
    # resolved are the easiest to pass. Dogfood 2026-08: 8 of 17 chiayi POIs took
    # this path, five of them sharing verbatim-identical coordinates.
    geo_source = ((normalised.get("geocode") or {}).get("geocode_source") or "")
    if geo_source == "cluster_fallback" and not has_existence_proof(normalised):
        return (normalised, "unverified",
                "geocode is a cluster_fallback centroid with no existence proof — "
                "record an official: true source or a gmaps_place_id, or leave the "
                "POI unverified for manual confirmation")

    status, note = classify_candidate(
        normalised, geocoded=geocoded, in_claimed_region=in_claimed_region,
        local_lang=local_lang, conflict_detected=conflict_detected, operating=operating,
        name_match=name_match,
    )
    return normalised, status, note
