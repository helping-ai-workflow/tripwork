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
    provenance. business_status is the sourced object form (Task 4). `as_of`
    is computed at call time, not a literal (OPERATING_MAX_AGE_DAYS is 90) --
    the same fuse tests/test_e2e_v033_closure.py:87-96's `_sourced_status()`
    warns about; a fixed 2026-08-01 would silently turn this fixture's
    'verified' outcomes into 'unverified' 90 days after it was written, for a
    reason unrelated to whatever the test in question is checking."""
    poi = {
        "id": "chunyen-restaurant",
        "name_local": "春燕飯館",
        "name_display": "春燕飯館",
        "district": "嘉義市西區",
        "business_status": {"status": "OPERATIONAL",
                            "source_url": "https://example.gov.tw/x",
                            "as_of": datetime.date.today().isoformat()},
        "geocode": {"lat": 23.47999, "lng": 120.44343,
                    "geocode_source": "cluster_fallback"},
        "sources": [
            {"url": "https://a.example.tw/p", "lang": "zh"},
            {"url": "https://b.example.com/q", "lang": "en"},
        ],
    }
    poi.update(over)
    return poi


def test_cluster_fallback_with_a_bare_string_business_status_is_still_unverified():
    """TW-062 safety argument for the Gate 2c retirement (2026-08-09 user
    ruling, v0.34.0 Task 6): retiring a gate one version after adding it needs
    a regression test, not just a docstring claim. This is that test.

    Migrated from test_cluster_fallback_without_existence_proof_is_not_verified,
    which pinned Gate 2c's own no-proof branch by calling classify_candidate
    directly with a hand-supplied `operating=True` bypass. That branch is
    deleted now (scripts/verify.py::classify_candidate no longer carries the
    cluster_fallback-without-proof sub-check), so the old shape cannot be
    pinned any more — the bypass itself was never the real entry point, and
    the REAL entry point (verify_poi) never reaches classify_candidate with
    `operating=True` unless Gate 0 has already been satisfied by a genuine
    sourced business_status.

    WHAT THIS TEST PROVES, stated precisely (docstring corrected in the final
    v0.34.0 fix wave, I2 -- the assertion below was always right; this
    paragraph's REASONING was not, and it ran a true clause and a false one
    together, which is the exact conflation I2 named):

      TRUE -- the retirement is VERDICT-NEUTRAL, and this test is the
        regression lock for that. A cluster_fallback POI whose business_status
        is the bare, self-attested string never gets far enough to need Gate
        2c at all: it fails Gate 0 first, through the REAL entry point
        (verify_poi), with no `operating=True` bypass involved. The evidence
        VOCABULARY also narrowed -- Gate 0 demands a DATED, SOURCED statement,
        strictly more than Gate 2c ever asked for (an undated official link or
        a bare place_id both satisfied Gate 2c; neither satisfies Gate 0).

      FALSE -- "TW-062 stays closed". It does not, and the cause is TW-072
        (Task 2), not this retirement. Once a sourced business_status counts
        as an existence proof, a cluster_fallback POI whose ONLY evidence is
        that statement reaches 'verified' with a district-centroid coordinate
        -- TW-062's exact shape. Gate 2c would have PASSED those records too
        had it been left in place. Measured: 5 corpus records do this after
        migration (4 chiayi POIs + sun-moon-lake's d2-6), all flipping
        has_existence_proof False -> True on the new proof alone.
        `test_cluster_fallback_with_no_extra_proof_still_verifies_once_gate_0_
        passes` below asserts that permitted outcome directly.

    So: this test pins that the bare-string path still refuses. It does NOT
    show that a district centroid can no longer ride into 'verified' -- with a
    sourced business_status it now can, deliberately. Whether that coordinate
    deserves the verdict is the coordinate-trustworthiness question v0.34.0
    explicitly declines to answer (CHANGELOG "What stays out")."""
    poi = _clean_poi(business_status="OPERATIONAL")   # bare string: self-attested
    _, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name="春燕飯館")
    assert status == "unverified"
    assert "self-attested" in note


def test_cluster_fallback_with_an_official_source_stays_verified():
    """Guard, GREEN at HEAD. Migrated for the Gate 2c retirement (v0.34.0 Task
    6): an official source is no longer WHY this passes -- Gate 2c (which used
    to treat it as one of two accepted existence proofs) is retired, so it is
    merely harmless now. `_clean_poi()`'s sourced business_status is what
    clears Gate 0, and that alone is sufficient; see
    test_cluster_fallback_with_no_extra_proof_still_verifies_once_gate_0_
    passes for the identical claim with no official source and no
    gmaps_place_id at all."""
    poi = _clean_poi(sources=[
        {"url": "https://chunyen.example.tw/", "lang": "zh", "official": True},
        {"url": "https://b.example.com/q", "lang": "en"},
    ])
    _, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name="春燕飯館")
    assert status == "verified"
    assert note == ""


def test_cluster_fallback_with_a_place_id_stays_verified():
    """Guard, GREEN at HEAD. Migrated for the Gate 2c retirement (v0.34.0 Task
    6): gmaps_place_id is no longer WHY this passes -- Gate 2c (which used to
    treat it as one of two accepted existence proofs) is retired, so it is
    merely harmless now. `_clean_poi()`'s sourced business_status is what
    clears Gate 0, and that alone is sufficient; see
    test_cluster_fallback_with_no_extra_proof_still_verifies_once_gate_0_
    passes for the identical claim with no place_id and no official source at
    all."""
    poi = _clean_poi(gmaps_place_id="ChIJ5wJfhyWUbjQRG_DhFBgvW7g")
    _, status, _ = verify_poi(poi, geocoded=True, in_claimed_region=True,
                              local_lang="zh", resolved_name="春燕飯館")
    assert status == "verified"


def test_cluster_fallback_with_no_extra_proof_still_verifies_once_gate_0_passes():
    """The direct statement of the Gate 2c retirement (v0.34.0 Task 6,
    2026-08-09 user ruling): a cluster_fallback POI with NEITHER an official
    source NOR a gmaps_place_id -- the exact shape that used to fail Gate 2c
    (test_cluster_fallback_with_a_bare_string_business_status_is_still_
    unverified's predecessor, before migration) -- now verifies on the
    strength of `_clean_poi()`'s sourced business_status alone, because that
    sourced statement IS what Gate 0 demands and there is no separate
    existence-proof gate left to ask for anything more."""
    poi = _clean_poi()   # sourced business_status; no official source, no place_id
    _, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name="春燕飯館")
    assert status == "verified"
    assert note == ""


def test_nominatim_resolved_geocode_is_unaffected():
    """Guard, GREEN at HEAD (regression guard): the normal path must not
    tighten. A real Nominatim-resolved geocode (not cluster_fallback) was
    never subject to the retired Gate 2c sub-check even while it existed —
    this pins that a regression anywhere in this area (Gate 0's business_
    status threading, the geocode_source presence check, the now-removed
    cluster_fallback branch) does not wrongly downgrade an ordinary verified
    POI, not just cluster_fallback ones."""
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

    Here geocoded=True and geocode_source='nominatim' (not cluster_fallback --
    irrelevant now that Gate 2c's existence-proof sub-check is retired, but
    keeping the non-cluster_fallback shape means this test's claim is only
    ever about Gate 2b, unconfounded by any lodging/geocode-source concern),
    so execution reaches Gate 2b. NO_RESOLVED_NAME must make it PASS -- not
    skip, not fail -- all the way through to 'verified'.
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


def test_geocode_source_missing_refuses_when_not_recorded():
    """I3, originally named test_gate_2c_refuses_when_geocode_source_is_not_
    recorded -- renamed (v0.34.0 Task 6 fix round 1) because the mechanism
    this pins is NOT Gate 2c: it is the separate GEOCODE_SOURCE_MISSING
    refusal, which stayed live through the Gate 2c retirement (only the
    cluster_fallback-specific proof sub-check was removed; "was geocode_
    source recorded at all" is a distinct, still-enforced requirement). A POI
    that never records where its coordinate came from is a provenance gap on
    its own -- 19 of 127 real POIs across the four schema-clean trips do
    exactly this.

    RED at TW-070-era HEAD (I3's original finding, historical): `verify_poi`'s
    `geo_source = (... or {}).get("geocode_source") or ""` used to coerce the
    absent field to `""`, which never equalled the GEOCODE_SOURCE_MISSING
    sentinel, so the refusal never ran and this POI (resolvable name,
    otherwise clean) reached 'verified' regardless of provenance.
    """
    poi = _clean_poi(geocode={"lat": 23.47999, "lng": 120.44343})
    _, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name="春燕飯館")
    assert status == "unverified"
    assert "geocode_source" in note


def test_recording_geocode_source_prevents_the_missing_branch_from_firing():
    """Guard, GREEN at HEAD: prevents the GEOCODE_SOURCE_MISSING branch from
    swallowing the branch it sits beside. A POI that DOES record
    geocode_source -- any value, cluster_fallback included -- must not hit
    the 'geocode_source not recorded' refusal.

    Migrated for the Gate 2c retirement (v0.34.0 Task 6, formerly
    test_recording_geocode_source_still_runs_gate_2c_as_before): the
    cluster_fallback VALUE itself no longer demands extra proof (see
    test_cluster_fallback_with_no_extra_proof_still_verifies_once_gate_0_
    passes), so recording 'cluster_fallback' now behaves exactly like
    recording any other geocode_source string as far as THIS branch is
    concerned -- both simply skip the missing-field refusal and proceed. No
    operating=True bypass needed any more either: both halves now go through
    the real entry point, verify_poi, on `_clean_poi()`'s sourced
    business_status."""
    fallback = _clean_poi(geocode={"lat": 23.47999, "lng": 120.44343,
                                   "geocode_source": "cluster_fallback"})
    _, status, note = verify_poi(fallback, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name="春燕飯館")
    assert status == "verified"
    assert "geocode_source" not in note

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

# test_classify_candidate_threads_today_into_gate_2c (later renamed
# test_classify_candidate_today_is_now_inert_since_gate_2c_retired) is
# REMOVED as of v0.34.0 Task 6 fix round 1 (M2), not rewritten: its own fix
# round 1 predecessor pinned that `today` no longer changed
# classify_candidate's output, but M2 deletes the parameter outright
# (`classify_candidate` raises TypeError on an unexpected `today` kwarg now),
# so there is no "accepted but inert" behaviour left to assert -- the
# parameter does not exist. The real anchoring concern lives entirely at
# Gate 0 now, pinned by test_sourced_recent_business_status_verifies /
# test_business_status_older_than_ninety_days_is_stale above and by
# tests/test_rederive.py::
# test_gate_2c_stays_unreachable_on_the_poi_path_for_a_very_stale_as_of and
# test_lodging_gate_0_anchors_to_the_records_own_era_not_wall_clock.


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
