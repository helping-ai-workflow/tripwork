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


# Threaded by verify_poi when the POI's geocode object records no geocode_source.
# Distinct from None, which keeps its existing meaning: "this caller does not
# supply the field at all" — 19 direct classify_candidate call sites pass nothing
# and must stay unaffected. Same split as NO_RESOLVED_NAME one gate over. (I3)
GEOCODE_SOURCE_MISSING = object()


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


# Google place ids are opaque but never this short; the field is agent-authored
# and nothing in the plugin writes it, so a shape check is the only thing
# standing between a stray value and a cleared gate. (TW-072) Measured on the
# corpus: 86 POIs carry a gmaps_place_id, every one exactly 27 characters, none
# shorter than 8, and zero lodging candidates carry one at all — the floor
# demotes nothing real.
_MIN_PLACE_ID_LEN = 8


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
    ref = _parse_iso(today) or datetime.date.today()
    age = (ref - as_of).days
    if age > OPERATING_MAX_AGE_DAYS:
        return None, (f"business_status.as_of {as_of.isoformat()} is {age} days old "
                      f"(max {OPERATING_MAX_AGE_DAYS}) — stale, re-check before scheduling")
    return _OPERATING_STATUS[key], ""


def has_existence_proof(poi, today=None):
    """True when something independent of the coordinate says this place exists.

    A cluster centroid is the district's midpoint — it is a position, not
    evidence. Three proofs are accepted:

      * a source the skill flagged `official: true` (its own site or booking page)
      * a `gmaps_place_id` of plausible shape
      * a SOURCED `business_status` — the object form {status, source_url, as_of}

    The third was added in 0.34.0 (TW-072) and is what made the check this
    function used to back (Gate 2c, retired later in the same release — see
    classify_candidate's old call site) keyless-reachable while it still ran.
    Gate 0 documents three routes and only the Places API route yields a
    place_id, so before this a keyless consumer's cluster_fallback POI had one
    possible proof (an official source) and cluster_fallback's trigger population
    is precisely the small venues least likely to have one. Two machines reached
    different verify_status values for the same restaurant and the artifact did
    not show it. A dated first-party statement that the venue is operating is
    evidence that it exists, which is what this function claims to test. (TW-072)

    The bare-string business_status is deliberately NOT accepted: it is
    self-attested, carries no source_url and no as_of, and admitting it would
    reopen TW-063 through this gate.

    `today` (TW-070 fix round 1): the third proof's recency check reads
    wall-clock by DEFAULT (`today=None`, unchanged from before this parameter
    existed) — a statement nobody has re-checked in three months is no longer
    reviewable, Task 2's deliberate design. A caller that re-derives a FINISHED
    artifact's own recorded verdict must anchor to the record's own
    `business_status.as_of` era instead, the same way `verify_poi` (Gate 0)
    and `scripts/rederive.py::rederive_lodging` (Gate 0, since Task 6) already
    do — otherwise a verdict correct when written silently turns into a false
    'conflicting'/'unverified' mismatch as real time passes with no artifact
    change.

    NOT called from `classify_candidate` any more (v0.34.0 Task 6): the
    cluster_fallback sub-check that called it there is retired — see the
    comment at its old call site in `classify_candidate` for why it became
    unreachable through every real caller. This function is retained because
    tests/test_verify.py exercises it directly as a unit (its own behaviour is
    unchanged), and because it is still a reasonable general-purpose
    "does independent evidence say this exists" primitive even with no
    current production caller.
    """
    place_id = (poi.get("gmaps_place_id") or "").strip()
    if len(place_id) >= _MIN_PLACE_ID_LEN:
        return True
    if any(s.get("official") for s in (poi.get("sources") or [])):
        return True
    operating, _ = operating_from_status(poi.get("business_status"), today=today)
    return operating is True


def classify_candidate(candidate, geocoded, in_claimed_region,
                        local_lang=None, conflict_detected=False, operating=True,
                        name_match=True, geocode_source=None):
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
    Gate 2: geocode must resolve (else 'unverified', D7). geocode_source must
            be RECORDED (else 'unverified' — the GEOCODE_SOURCE_MISSING
            sentinel, I3); a `cluster_fallback` value itself no longer demands
            extra proof (TW-062's own sub-check retired in v0.34.0 — see the
            comment at its old call site — because Gate 0 now demands strictly
            more than that sub-check ever did).
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
        geocode_source:   `candidate["geocode"]["geocode_source"]` (TW-062), now only
                          checked for PRESENCE (I3): GEOCODE_SOURCE_MISSING
                          (threaded by verify_poi when the POI's geocode carries
                          no geocode_source) refuses -> 'unverified'; any string
                          value ('nominatim' / 'nominatim_structured' /
                          'cluster_fallback') is accepted without further
                          distinction — the `cluster_fallback` sub-check that
                          used to demand extra proof for that one value is
                          retired (v0.34.0 Task 6, see the comment at its old
                          call site). The default None never equals
                          GEOCODE_SOURCE_MISSING, so existing callers that never
                          pass this argument at all are unaffected, and a
                          caller that reads the field itself and passes
                          `gs or ""` (`scripts/rederive.py::rederive_lodging`)
                          also stays unaffected either way.

    No `today` parameter (removed fix round 1, M2 — v0.34.0 Task 6 had first
    kept it as a dead parameter, "no longer read but kept for callers that
    still pass it"; that was itself a defect, since a dead-but-accepted
    kwarg silently invites a caller to believe it still does something).
    Its sole reader was the now-retired Gate 2c `has_existence_proof` call.
    `verify_poi` still has its OWN `today` argument (Gate 0's recency
    anchor) and `rederive_lodging` still anchors its own
    `operating_from_status` call the same way — neither forwards it here
    any more, because there is nothing left here to forward it to.
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

    # geocode_source's presence is its own requirement, independent of the
    # now-retired cluster_fallback sub-check below (I3): a POI that never
    # records where its coordinate came from is a provenance gap on its own —
    # the identical shape Part 1 closed for resolved_name. 19 of 127 real POIs
    # omit the field.
    if geocode_source is GEOCODE_SOURCE_MISSING:
        return ("unverified",
                "geocode_source not recorded — record geocode.geocode_source: "
                "nominatim / nominatim_structured / cluster_fallback")

    # Gate 2's cluster_fallback sub-check (TW-062) is RETIRED as of v0.34.0
    # Task 6 (user ruling, 2026-08-09), not merely inactive. It required an
    # existence proof independent of the coordinate (an official source, a
    # gmaps_place_id, or — since TW-072 — a sourced business_status). Once
    # TW-072 made a sourced business_status count as that proof, this branch
    # became unreachable through every real caller: verify_poi's Gate 0
    # already refuses any POI whose business_status is not sourced, and any
    # POI it does NOT refuse necessarily carries the same proof this branch
    # would have checked for — reading the identical field through the
    # identical `operating_from_status`, anchored to the identical recency
    # era (`verify_poi`'s own `today` argument at its Gate 0 call site; this
    # function no longer accepts a `today` parameter at all, M2).
    # scripts/rederive.py::rederive_lodging hard-coded `operating=True` and
    # bypassed Gate 0 entirely, which is why the branch stayed reachable for
    # lodging alone; that bypass is removed in the same task (Step 4), so
    # nothing left in this codebase can reach this branch. Retiring it rather
    # than shipping a check that cannot fail is the point of this release —
    # see rederive.py's module docstring and CHANGELOG v0.34.0.
    #
    # Safety argument (why this does not reopen TW-062): TW-062 was a district
    # centroid riding into 'verified' with no independent evidence the place
    # exists. That path is now blocked by Gate 0 itself, which demands a
    # DATED, SOURCED statement — strictly more than this branch ever asked
    # for (an undated official link or a bare place_id both satisfied it).
    # Pinned by tests/test_verify.py::
    # test_cluster_fallback_with_a_bare_string_business_status_is_still_unverified.
    #
    # has_existence_proof() itself is NOT deleted — tests/test_verify.py
    # exercises it directly as a unit — only this call site is gone.

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

    `today` anchors Gate 0's operating-signal recency (TW-070 fix round 1) —
    a caller re-deriving a finished artifact against the record's own era
    (e.g. scripts/rederive.py::rederive_pois) passes the record's own
    `business_status.as_of` here instead of leaving this to read real
    wall-clock, so a verdict correct when written cannot flip to a false
    mismatch purely from elapsed real time. Default None reads wall-clock.

    Historical note (stale through fix round 1, v0.34.0 Task 6): this
    docstring used to say `today` ALSO anchored Gate 2c's existence-proof
    recency via classify_candidate. Gate 2c (and the has_existence_proof call
    that read `today`) is retired — see the comment at classify_candidate's
    old call site — so `today` is no longer forwarded there at all;
    classify_candidate does not even accept the parameter any more (M2).

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

    # geocode_source's presence check (I3) also lives inside classify_candidate
    # now, for the identical reason Gate 2b's input does: an early return here
    # would fire ahead of Gate 1 (sources) and Gate 2 (geocoded), which
    # skills/source-verify/SKILL.md:28 documents as running first. Only the
    # geocode_source STRING (or the GEOCODE_SOURCE_MISSING sentinel) is
    # computed here and threaded down. classify_candidate's cluster_fallback
    # sub-check (TW-062, and the has_existence_proof(candidate) call it used
    # to make) is retired as of v0.34.0 Task 6 — see the comment at its old
    # call site in classify_candidate.
    geo_source = (normalised.get("geocode") or {}).get("geocode_source") or None
    if geo_source is None:
        geo_source = GEOCODE_SOURCE_MISSING

    status, note = classify_candidate(
        normalised, geocoded=geocoded, in_claimed_region=in_claimed_region,
        local_lang=local_lang, conflict_detected=conflict_detected, operating=operating,
        name_match=name_match, geocode_source=geo_source,
    )
    return normalised, status, note


# Domain suffixes that are official by construction. Deliberately small and
# structural — government, academic and transit authorities — rather than an
# enumeration of venue sites, which cannot be maintained centrally. A trip adds
# its own venues via extra_suffixes; before this existed, each consumer kept the
# whole list in its own driver and grew it whenever a gate needed a hotel's site
# flagged. (TW-068)
OFFICIAL_DOMAIN_SUFFIXES = (
    ".gov.tw", ".gov", ".edu.tw", ".edu", ".go.jp", ".lg.jp", ".govt.nz",
    ".org.tw",
)


def is_official_url(url, extra_suffixes=()):
    """True when a source URL is the venue's own or an authority's.

    `sources[].official` should be set explicitly by the research stage at the
    moment it fetches an official page — this is the fallback for URLs where that
    was not recorded, not a replacement for it.
    """
    host = urlsplit(url or "").netloc.lower().split(":")[0]
    if not host:
        return False
    for suf in tuple(OFFICIAL_DOMAIN_SUFFIXES) + tuple(extra_suffixes):
        s = suf if suf.startswith(".") else "." + suf
        if host.endswith(s) or host == s.lstrip("."):
            return True
    return False
