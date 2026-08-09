# tests/test_verify.py
from scripts.verify import classify_candidate, verify_poi

def _cand(sources, langs):
    # bare tokens -> distinct https domains so independence (distinct netloc) holds
    def _u(s):
        return s if str(s).startswith("http") else f"https://{s}.example"
    return {"id": "x", "sources": [{"url": _u(u), "lang": l} for u, l in zip(sources, langs)]}

def test_defunct_poi_rejected():   # TW-005
    c = _cand(["a", "b"], ["ko", "zh"])
    status, note = classify_candidate(c, geocoded=True, in_claimed_region=True, operating=False)
    assert status == "rejected"
    assert "closed" in note.lower() or "defunct" in note.lower()

def test_operating_defaults_true_keeps_verified():   # TW-005 default path
    c = _cand(["a", "b"], ["ko", "zh"])
    status, _ = classify_candidate(c, geocoded=True, in_claimed_region=True)
    assert status == "verified"

def test_single_source_is_unverified():
    c = _cand(["a"], ["ko"])
    status, note = classify_candidate(c, geocoded=True, in_claimed_region=True)
    assert status == "unverified"

def test_no_geocode_is_unverified():
    # D7: with sources sufficient (Gate 1 passes) but geocode unresolved,
    # degrade to 'unverified' (recorded for manual confirm), not 'rejected'.
    c = _cand(["a", "b"], ["ko", "zh"])
    status, note = classify_candidate(c, geocoded=False, in_claimed_region=False)
    assert status == "unverified"
    assert "geocode" in note.lower()

def test_geocode_outside_region_is_conflicting():
    c = _cand(["a", "b"], ["ko", "zh"])
    status, note = classify_candidate(c, geocoded=True, in_claimed_region=False)
    assert status == "conflicting"
    assert "region" in note.lower()

def test_two_sources_geocoded_in_region_is_verified():
    c = _cand(["a", "b"], ["ko", "zh"])
    status, note = classify_candidate(c, geocoded=True, in_claimed_region=True)
    assert status == "verified"

def test_two_sources_same_lang_still_needs_one_local():
    # both non-local language -> treat as insufficient (unverified)
    c = _cand(["a", "b"], ["zh", "zh"])
    status, note = classify_candidate(c, geocoded=True, in_claimed_region=True,
                                      local_lang="ko")
    assert status == "unverified"

def test_single_source_and_no_geocode_is_unverified():
    # I1: sources gate (Gate 1) must fire before geocode gate (Gate 2).
    # 1 source + geocoded=False → should be "unverified" (not "rejected")
    c = _cand(["a"], ["ko"])
    status, note = classify_candidate(c, geocoded=False, in_claimed_region=False)
    assert status == "unverified", (
        f"Expected 'unverified' (insufficient sources), got '{status}'"
    )

def test_cross_source_conflict_is_conflicting():
    # I2: conflict_detected=True with otherwise-passing inputs → "conflicting"
    c = _cand(["a", "b"], ["ko", "en"])
    status, note = classify_candidate(
        c, geocoded=True, in_claimed_region=True,
        local_lang="ko", conflict_detected=True
    )
    assert status == "conflicting"
    assert "cross-source" in note.lower() or "disagreement" in note.lower(), (
        f"Expected note mentioning cross-source/disagreement, got: {note!r}"
    )


def test_same_domain_sources_not_independent():   # TW-023
    c = {"sources": [{"url": "https://tripadvisor.com/a", "lang": "ko"},
                     {"url": "https://tripadvisor.com/b", "lang": "en"}]}
    status, note = classify_candidate(c, geocoded=True, in_claimed_region=True)
    assert status == "unverified"
    assert "independent" in note.lower() or "domain" in note.lower()


import datetime


def _sourced_poi(bs, **over):
    poi = {
        "id": "tsai-duck", "name_local": "蔡氏鴨庄", "name_display": "蔡氏鴨庄",
        "district": "嘉義市東區",
        "business_status": bs,
        "geocode": {"lat": 23.47, "lng": 120.45, "geocode_source": "nominatim"},
        "sources": [{"url": "https://a.example.tw/p", "lang": "zh"},
                    {"url": "https://b.example.com/q", "lang": "en"}],
    }
    poi.update(over)
    return poi


def test_bare_string_business_status_is_no_longer_a_signal():
    """TW-063: 17/17 dogfood POIs carried a hand-typed OPERATIONAL. The schema
    had nowhere to record that it was hand-typed, so review could not see it."""
    _, status, note = verify_poi(_sourced_poi("OPERATIONAL"), geocoded=True,
                                 in_claimed_region=True, local_lang="zh",
                                 resolved_name="蔡氏鴨庄")
    assert status == "unverified"
    assert "self-attested" in note


def test_sourced_recent_business_status_verifies():
    today = datetime.date(2026, 8, 8)
    poi = _sourced_poi({"status": "OPERATIONAL",
                        "source_url": "https://places.example/x",
                        "as_of": "2026-07-20"})
    _, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name="蔡氏鴨庄",
                                 today=today)
    assert status == "verified"
    assert note == ""


def test_business_status_older_than_ninety_days_is_stale():
    today = datetime.date(2026, 8, 8)
    poi = _sourced_poi({"status": "OPERATIONAL",
                        "source_url": "https://places.example/x",
                        "as_of": "2026-01-01"})
    _, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name="蔡氏鴨庄",
                                 today=today)
    assert status == "unverified"
    assert "stale" in note or "as_of" in note


def test_closed_still_rejects_in_the_object_form():
    today = datetime.date(2026, 8, 8)
    poi = _sourced_poi({"status": "CLOSED_TEMPORARILY",
                        "source_url": "https://places.example/x",
                        "as_of": "2026-08-01"})
    _, status, _ = verify_poi(poi, geocoded=True, in_claimed_region=True,
                              local_lang="zh", resolved_name="蔡氏鴨庄",
                              today=today)
    assert status == "rejected"


def test_object_form_missing_source_url_is_not_a_signal():
    today = datetime.date(2026, 8, 8)
    poi = _sourced_poi({"status": "OPERATIONAL", "as_of": "2026-08-01"})
    _, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name="蔡氏鴨庄",
                                 today=today)
    assert status == "unverified"
    assert "source_url" in note


def test_tel_source_url_business_status_verifies():
    """TW-063 fix round 1 (Finding 1): the phone-confirmation route
    (SKILL.md:30 route 3, 行前電話確認) is the only one available without a
    Places API key; verify_poi must accept it like any other sourced signal."""
    today = datetime.date(2026, 8, 8)
    poi = _sourced_poi({"status": "OPERATIONAL",
                        "source_url": "tel:+886-5-2593133",
                        "as_of": "2026-08-01"})
    _, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name="蔡氏鴨庄",
                                 today=today)
    assert status == "verified"
    assert note == ""


def test_business_status_exactly_ninety_days_old_is_still_fresh():
    """TW-063 fix round 1 (boundary, worth doing): age is computed as
    `age > OPERATING_MAX_AGE_DAYS`, so exactly 90 days old is inclusive (still
    fresh), not stale. Locks in the strict-vs-inclusive choice at the boundary."""
    today = datetime.date(2026, 8, 8)
    poi = _sourced_poi({"status": "OPERATIONAL",
                        "source_url": "https://places.example/x",
                        "as_of": "2026-05-10"})  # exactly 90 days before today
    _, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name="蔡氏鴨庄",
                                 today=today)
    assert status == "verified"
    assert note == ""


def test_business_status_ninety_one_days_old_is_stale():
    """TW-063 fix round 1 (boundary, worth doing): one day past the ceiling
    must be stale — the other side of the same boundary."""
    today = datetime.date(2026, 8, 8)
    poi = _sourced_poi({"status": "OPERATIONAL",
                        "source_url": "https://places.example/x",
                        "as_of": "2026-05-09"})  # exactly 91 days before today
    _, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name="蔡氏鴨庄",
                                 today=today)
    assert status == "unverified"
    assert "stale" in note or "as_of" in note


def test_bare_string_business_status_still_validates_against_the_schema(tmp_path):
    """Guard, GREEN at HEAD: schema stays permissive so existing trips keep
    passing validate_artifact and get a ROUTED gate failure instead of a hard
    validation error when business_status is still the legacy bare string."""
    from scripts.validate_artifact import validate_file
    p = tmp_path / "verified-pois.yaml"
    p.write_text(
        "pois:\n"
        "  - id: x\n"
        "    name_local: 春燕\n"
        "    name_display: 春燕\n"
        "    category: meal\n"
        "    district: 西區\n"
        "    verify_status: unverified\n"
        "    status_reason: pending\n"
        "    business_status: OPERATIONAL\n"
        "    sources:\n"
        "      - url: https://a.example.tw/p\n"
        "        lang: zh\n",
        encoding="utf-8",
    )
    assert validate_file(str(p))[0] == 0


from scripts.verify import verify_poi


def _clean_poi(**over):
    """A POI that passes every other gate, so the only variable is the geocode
    provenance. business_status is the sourced object form (Task 4)."""
    poi = {
        "id": "chunyen-restaurant",
        "name_local": "春燕飯館",
        "name_display": "春燕飯館",
        "district": "嘉義市西區",
        "business_status": {"status": "OPERATIONAL",
                            "source_url": "https://example.gov.tw/x",
                            "as_of": "2026-08-01"},
        "geocode": {"lat": 23.47999, "lng": 120.44343,
                    "geocode_source": "cluster_fallback"},
        "sources": [
            {"url": "https://a.example.tw/p", "lang": "zh"},
            {"url": "https://b.example.com/q", "lang": "en"},
        ],
    }
    poi.update(over)
    return poi


def test_cluster_fallback_without_existence_proof_is_not_verified():
    """TW-062: a district centroid is a location, not evidence the place exists.

    Nominatim finding nothing must not be a BETTER outcome than Nominatim
    finding a name that disagrees (which is `conflicting`).

    Migrated for TW-072: `_clean_poi()`'s sourced `business_status` is now
    itself an existence proof (that is the whole point of the fix) — any
    business_status that gets `verify_poi` past Gate 0 (operating=True, via a
    dated, sourced statement) satisfies `has_existence_proof`'s third proof by
    the same read. So a POI that reaches Gate 2c through `verify_poi` with
    Gate 0 already passed can no longer arrive proof-less; that combination is
    now unreachable via the real entry point, which is the asymmetry closing,
    not a hole. This drops to `classify_candidate` directly, passing
    `operating=True` the way `verify_poi` would have derived it, on a
    candidate with no `business_status`, no official source and no
    `gmaps_place_id`, to keep exercising Gate 2c's own no-proof branch in
    isolation from Gate 0.

    This `operating=True`-bypass shape is not purely synthetic: it mirrors a
    genuinely live caller. `scripts/rederive.py::rederive_lodging` hard-codes
    `operating=True` and reaches `classify_candidate` without a real Gate 0 in
    front of it, because lodging has no `business_status` field yet (Task 6).
    So this test doubles as the regression guard for that path — a lodging
    `cluster_fallback` candidate with no proof still needs Gate 2c to refuse
    it today.
    """
    poi = _clean_poi()
    poi.pop("business_status", None)
    status, note = classify_candidate(poi, geocoded=True, in_claimed_region=True,
                                      local_lang="zh", operating=True,
                                      geocode_source="cluster_fallback")
    assert status == "unverified"
    assert "cluster_fallback" in note


def test_cluster_fallback_with_an_official_source_stays_verified():
    """Guard, GREEN at HEAD (over-blocking guard): an official page proves the
    venue exists, so the approximate coordinate is an acceptable position for
    it. Prevents Gate 2c from over-blocking a POI that has real existence
    proof — a regression here would wrongly downgrade a verifiable POI to
    unverified just because its geocode source is cluster_fallback."""
    poi = _clean_poi(sources=[
        {"url": "https://chunyen.example.tw/", "lang": "zh", "official": True},
        {"url": "https://b.example.com/q", "lang": "en"},
    ])
    _, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name="春燕飯館")
    assert status == "verified"
    assert note == ""


def test_cluster_fallback_with_a_place_id_stays_verified():
    """Guard, GREEN at HEAD (over-blocking guard): gmaps_place_id is the other
    existence proof source-verify already collects
    (skills/source-verify/SKILL.md:30). Prevents Gate 2c from over-blocking a
    POI whose existence proof is a place_id rather than an official source —
    a regression here would wrongly downgrade it to unverified."""
    poi = _clean_poi(gmaps_place_id="ChIJ5wJfhyWUbjQRG_DhFBgvW7g")
    _, status, _ = verify_poi(poi, geocoded=True, in_claimed_region=True,
                              local_lang="zh", resolved_name="春燕飯館")
    assert status == "verified"


def test_nominatim_resolved_geocode_is_unaffected():
    """Guard, GREEN at HEAD (regression guard): the normal path must not
    tighten. Prevents Gate 2c from firing on a real Nominatim-resolved
    geocode — a regression here would wrongly downgrade every ordinary
    verified POI, not just cluster_fallback ones."""
    poi = _clean_poi(geocode={"lat": 23.4, "lng": 120.4,
                              "geocode_source": "nominatim"})
    _, status, _ = verify_poi(poi, geocoded=True, in_claimed_region=True,
                              local_lang="zh", resolved_name="春燕飯館")
    assert status == "verified"


def test_omitting_resolved_name_no_longer_silently_skips_gate_2b():
    """Same root cause as TW-062, different gate: a check that does not run is
    indistinguishable from a check that passed.

    verify.py:163 read `name_match = True if resolved_name is None else ...`, so a
    caller that forgot the argument got a green POI with Gate 2b never executed —
    no error, no warning, nothing in the artifact. Every hand-written consumer
    driver was one omission away from it (TW-068).
    """
    poi = _clean_poi(geocode={"lat": 23.4, "lng": 120.4,
                              "geocode_source": "nominatim"})
    _, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang="zh")
    assert status == "unverified"
    assert "resolved_name" in note


def test_an_explicit_unresolved_marker_is_how_d7_is_recorded():
    """The escape hatch D7 needs: Nominatim genuinely returned nothing. Passing
    the sentinel is a CLAIM that the lookup ran and found nothing; omitting the
    argument is silence, and silence is what this change outlaws."""
    from scripts.verify import NO_RESOLVED_NAME
    poi = _clean_poi(geocode={"lat": 23.4, "lng": 120.4,
                              "geocode_source": "nominatim"})
    _, status, note = verify_poi(poi, geocoded=False, in_claimed_region=True,
                                 local_lang="zh", resolved_name=NO_RESOLVED_NAME)
    assert status == "unverified"
    assert "geocode unresolved" in note


def test_no_resolved_name_sentinel_passes_gate_2b_when_geocode_actually_resolved():
    """I5: the sentinel's meaning was untested. The test above passes
    geocoded=False, so Gate 2 ('geocode unresolved') returns FIRST and Gate 2b
    -- the branch that actually reads NO_RESOLVED_NAME -- never runs; it pins
    Gate 2's message, not the sentinel's effect. Mutation proof: flipping
    verify.py's `name_match = True` to `False` for the NO_RESOLVED_NAME branch
    left all pre-existing tests green.

    Here geocoded=True and geocode_source='nominatim' (not cluster_fallback,
    so Gate 2c's existence-proof sub-check does not confound the result), so
    execution reaches Gate 2b. NO_RESOLVED_NAME must make it PASS -- not skip,
    not fail -- all the way through to 'verified'.
    """
    from scripts.verify import NO_RESOLVED_NAME
    poi = _clean_poi(geocode={"lat": 23.4, "lng": 120.4,
                              "geocode_source": "nominatim"})
    _, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name=NO_RESOLVED_NAME)
    assert status == "verified", note


def test_missing_resolved_name_does_not_preempt_earlier_gates():
    """Review Round 1 (Finding 1): the Gate 2b refusal must obey
    skills/source-verify/SKILL.md:28's documented strict order — 'Gate 0 fires
    before Gate 1, Gate 1 before Gate 2' — not short-circuit ahead of it.

    A POI with only ONE source and an unresolved geocode has TWO problems more
    fundamental than a missing resolved_name: Gate 1 (sources) and Gate 2
    (geocoded). The caller should be told about the sources problem first —
    the one closer to the front of the pipeline — not sent to fix
    resolved_name, rerun, and only then discover the real blocker.
    """
    poi = _clean_poi(
        sources=[{"url": "https://a.example.tw/p", "lang": "zh"}],
        geocode={"lat": 23.4, "lng": 120.4, "geocode_source": "nominatim"},
    )
    _, status, note = verify_poi(poi, geocoded=False, in_claimed_region=True,
                                 local_lang="zh")
    assert status == "unverified"
    assert "independent sources" in note
    assert "resolved_name" not in note


def test_gate_2c_refuses_when_geocode_source_is_not_recorded():
    """I3: Gate 2c's trigger (`geocode.geocode_source`) is itself optional, so a
    POI that never records where its coordinate came from could skip Gate 2c
    entirely by omission -- 19 of 127 real POIs across the four schema-clean
    trips do exactly this.

    RED at HEAD: `verify_poi`'s `geo_source = (... or {}).get("geocode_source")
    or ""` coerces the absent field to `""`, which never equals
    `"cluster_fallback"`, so Gate 2c's sub-check never runs and this POI (no
    existence proof, resolvable name, otherwise clean) reaches 'verified'.
    """
    poi = _clean_poi(geocode={"lat": 23.47999, "lng": 120.44343})
    _, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name="春燕飯館")
    assert status == "unverified"
    assert "geocode_source" in note


def test_recording_geocode_source_still_runs_gate_2c_as_before():
    """Guard, GREEN at HEAD: prevents the new GEOCODE_SOURCE_MISSING branch
    from swallowing the branch it sits beside. A POI that DOES record
    geocode_source must still run Gate 2c's existing cluster_fallback
    sub-check exactly as before -- centroid + no proof -> unverified with the
    existing centroid message, nominatim -> verified.

    First half migrated for TW-072, same reason as
    test_cluster_fallback_without_existence_proof_is_not_verified:
    `_clean_poi()`'s sourced business_status now doubles as existence proof
    once it clears Gate 0, so `verify_poi` can no longer land on this POI with
    Gate 0 passed and no proof at the same time. Drops to classify_candidate
    directly (operating=True, no business_status/official/place_id) to keep
    testing the cluster_fallback sub-check itself. The second half
    (geocode_source='nominatim') never touches has_existence_proof at all —
    it stays on verify_poi, unmigrated, exactly as before.

    Same live-caller note as test_cluster_fallback_without_existence_proof_is_
    not_verified: this operating=True bypass mirrors rederive_lodging (Task 6
    has not given lodging a business_status field yet), so this half also
    doubles as that path's regression guard.
    """
    fallback = _clean_poi(geocode={"lat": 23.47999, "lng": 120.44343,
                                   "geocode_source": "cluster_fallback"})
    fallback.pop("business_status", None)
    status, note = classify_candidate(fallback, geocoded=True, in_claimed_region=True,
                                      local_lang="zh", operating=True,
                                      geocode_source="cluster_fallback")
    assert status == "unverified"
    assert "cluster_fallback" in note

    resolved = _clean_poi(geocode={"lat": 23.47999, "lng": 120.44343,
                                   "geocode_source": "nominatim"})
    _, status, note = verify_poi(resolved, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name="春燕飯館")
    assert status == "verified"
    assert note == ""


def test_direct_classify_candidate_callers_that_never_pass_geocode_source_are_unaffected():
    """Guard, GREEN at HEAD: the refusal is threaded from verify_poi, NOT made
    classify_candidate's default -- 19 direct classify_candidate call sites
    never pass the geocode_source keyword at all and must keep their current
    meaning. Same split Part 1 used for name_match (verify.py:253-267).
    """
    c = _cand(["a", "b"], ["ko", "zh"])
    status, note = classify_candidate(c, geocoded=True, in_claimed_region=True)
    assert status == "verified"


def test_cluster_fallback_does_not_preempt_earlier_gates():
    """Review Round 2: Gate 2's cluster_fallback sub-check must also obey
    skills/source-verify/SKILL.md:28's documented strict order, mirroring
    Round 1's Gate 2b fix — it is a Gate 2 concern, so Gate 1 (sources) must
    still fire first.

    A POI with only ONE source and a cluster_fallback centroid (no existence
    proof) has a more fundamental problem than the unproven centroid: Gate 1
    (sources). The caller should be told about the sources problem first, not
    sent to add an official source or gmaps_place_id, rerun, and only then
    discover the real blocker.
    """
    poi = _clean_poi(sources=[{"url": "https://a.example.tw/p", "lang": "zh"}])
    _, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name="春燕飯館")
    assert status == "unverified"
    assert "independent sources" in note
    assert "cluster_fallback" not in note


def test_a_sourced_business_status_is_an_existence_proof():
    """TW-072: Gate 2c's stated job is existence — "something independent of the
    coordinate says this place exists". A dated, sourced first-party statement
    that the venue is OPERATING is exactly that. Accepting it dissolves the
    keyless asymmetry by construction, because Gate 0 already guarantees two
    keyless routes (a dated official/social statement, or a tel: confirmation).

    `as_of` is computed at run time, not hard-coded: `has_existence_proof`
    reads recency against wall-clock (the deliberate design decision), so a
    literal past date would silently flip this test to FAIL once real time
    crosses OPERATING_MAX_AGE_DAYS past it — same fuse
    tests/test_e2e_v033_closure.py:87-96's `_sourced_status()` docstring warns
    about, same fix."""
    import datetime
    from scripts.verify import has_existence_proof
    poi = {"id": "x", "sources": [{"url": "https://a.example.tw/p", "lang": "zh"}],
           "business_status": {"status": "OPERATIONAL",
                               "source_url": "https://a.example.tw/p",
                               "as_of": datetime.date.today().isoformat()}}
    assert has_existence_proof(poi) is True


def test_has_existence_proof_today_anchors_the_sourced_business_status_proof():
    """TW-070 fix round 1. `has_existence_proof`'s third proof (a sourced
    business_status) reads wall-clock by DEFAULT (today=None, unchanged from
    before this parameter existed — Task 2's deliberate design, a statement
    nobody has re-checked in three months is no longer reviewable). But a
    caller re-deriving a FINISHED artifact's own recorded verdict
    (scripts/rederive.py::rederive_pois) must be able to anchor the recency
    check to the record's own `business_status.as_of` era instead, exactly the
    way Gate 0's `operating_from_status` already does — otherwise a statement
    correct when written silently expires purely from elapsed real time, with
    no artifact change. A literal past `as_of` is safe here (unlike the sibling
    test above): the point of this test IS the gap between wall-clock and the
    anchored date, not incidental to it."""
    from scripts.verify import has_existence_proof
    poi = {"id": "x", "sources": [{"url": "https://a.example.tw/p", "lang": "zh"}],
           "business_status": {"status": "OPERATIONAL",
                               "source_url": "https://a.example.tw/p",
                               "as_of": "2020-01-01"}}
    assert has_existence_proof(poi) is False                      # wall-clock: stale
    assert has_existence_proof(poi, today="2020-01-01") is True   # anchored: fresh


def test_classify_candidate_threads_today_into_gate_2c():
    """TW-070 fix round 1. Before this, `classify_candidate` had no `today`
    parameter at all, so any caller passing Gate 0 a non-wall-clock `today`
    (verify_poi's artifact-anchored callers) still had Gate 2c's
    has_existence_proof reading real wall-clock underneath — the two gates
    disagreed on which clock to read for the SAME business_status. A
    cluster_fallback candidate with no proof but a sourced business_status,
    fresh only relative to itself, must clear Gate 2c when `today` is threaded
    through, and does not without it (regression half asserted directly, not
    just via the fix-round report)."""
    from scripts.verify import classify_candidate
    c = {"id": "x", "sources": [{"url": "https://a.example.tw/p", "lang": "zh"},
                                {"url": "https://b.example.com/q", "lang": "en"}],
         "business_status": {"status": "OPERATIONAL",
                             "source_url": "https://a.example.tw/p",
                             "as_of": "2020-01-01"}}
    status, note = classify_candidate(c, geocoded=True, in_claimed_region=True,
                                      operating=True, geocode_source="cluster_fallback",
                                      today="2020-01-01")
    assert status == "verified", note
    status_blind, note_blind = classify_candidate(
        c, geocoded=True, in_claimed_region=True, operating=True,
        geocode_source="cluster_fallback")   # today omitted -> wall-clock, stale
    assert status_blind == "unverified" and "cluster_fallback" in note_blind


def test_a_bare_string_business_status_is_not_an_existence_proof():
    """Guard, GREEN at HEAD: the bare form is self-attested — no source_url, no
    as_of, nothing to review. It must not become a back door into Gate 2c."""
    from scripts.verify import has_existence_proof
    poi = {"id": "x", "sources": [{"url": "https://a.example.tw/p", "lang": "zh"}],
           "business_status": "OPERATIONAL"}
    assert has_existence_proof(poi) is False


def test_a_blank_gmaps_place_id_is_not_an_existence_proof():
    """gmaps_place_id is agent-authored: grep shows the plugin READS it
    (verify.py, render/gmaps_links.py) and writes it NOWHERE. It stays an
    accepted proof but gains a minimum shape so a stray value cannot clear the
    gate."""
    from scripts.verify import has_existence_proof
    assert has_existence_proof({"id": "x", "gmaps_place_id": "   ", "sources": []}) is False
    assert has_existence_proof({"id": "x", "gmaps_place_id": "y", "sources": []}) is False


def test_operating_from_status_accepts_an_iso_string_today():
    """TW-073: as_of goes through _parse_iso (tolerant), today went straight into
    date subtraction, so a string raised TypeError from the arithmetic rather
    than the entry. No production caller is affected —
    scripts/source_verify_run.py passes a datetime.date — this removes the
    tripwire for a future --today flag."""
    import datetime
    from scripts.verify import operating_from_status
    bs = {"status": "OPERATIONAL", "source_url": "https://a.example.tw/p",
          "as_of": "2026-08-05"}
    assert (operating_from_status(bs, today="2026-08-09")
            == operating_from_status(bs, today=datetime.date(2026, 8, 9)))


def test_verify_status_does_not_depend_on_having_an_api_key():
    """The invariant TW-072 exists to restore: the same candidate verified with
    and without a gmaps_place_id must reach the same verify_status, because the
    keyless route now supplies its own proof.

    `as_of` is computed at run time, not hard-coded, for the same reason as
    test_a_sourced_business_status_is_an_existence_proof above: a literal past
    date would flip only the keyless side of this comparison to FAIL once real
    time aged it past OPERATING_MAX_AGE_DAYS — the `gmaps_place_id` proof on
    the keyed side never expires, so the break would look like the invariant
    itself failing rather than a stale fixture.

    CORRECTION (TW-070 fix round 1): this docstring previously claimed
    `has_existence_proof` reads wall-clock "regardless of the `today` this
    test passes to verify_poi's Gate 0". That is no longer true on THIS call
    path — `verify_poi` now threads its own `today` through classify_candidate
    into has_existence_proof (see scripts/verify.py), so both Gate 0 and Gate
    2c read the SAME anchor here. The claim was true only about
    has_existence_proof's OWN default (today=None, unchanged — see
    test_has_existence_proof_today_anchors_the_sourced_business_status_proof),
    not about calls that flow through verify_poi. This test's own assertion is
    unaffected either way: `as_of` (real "now", computed at run time) is always
    >= the fixed `today=date(2026, 8, 9)` anchor below as real time only moves
    forward, so age is always <= 0 <= OPERATING_MAX_AGE_DAYS on both readings —
    the keyless side stays fresh whether it reads wall-clock or the threaded
    anchor, which is exactly why this fixture never needed to change."""
    import datetime
    from scripts.verify import verify_poi
    base = {"id": "x", "name_local": "源興御香屋", "name_display": "源興御香屋",
            "district": "嘉義市西區",
            "business_status": {"status": "OPERATIONAL",
                                "source_url": "https://a.example.tw/p",
                                "as_of": datetime.date.today().isoformat()},
            "geocode": {"lat": 23.48, "lng": 120.44,
                        "geocode_source": "cluster_fallback"},
            "sources": [{"url": "https://a.example.tw/p", "lang": "zh"},
                        {"url": "https://b.example.com/q", "lang": "en"}]}
    keyed = dict(base, gmaps_place_id="ChIJxxxxxxxxxxxxxxx")
    today = datetime.date(2026, 8, 9)
    kw = dict(geocoded=True, in_claimed_region=True, local_lang="zh",
              resolved_name="源興御香屋", today=today)
    assert verify_poi(dict(base), **kw)[1] == verify_poi(keyed, **kw)[1]
