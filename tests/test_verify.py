# tests/test_verify.py
from scripts.verify import classify_candidate

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
