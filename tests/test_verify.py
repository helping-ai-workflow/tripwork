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
