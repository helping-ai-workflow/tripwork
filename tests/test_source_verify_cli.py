"""The batch driver source-verify never had, and the domain list it never owned."""
import datetime
import pathlib
import subprocess
import sys

import yaml

# Tests derive the repo root from the file's own location, not a hardcoded
# absolute path — a hardcoded ROOT breaks the moment this repo is checked out
# anywhere else, and subprocess.run's cwd= needs a real, portable directory.
ROOT = str(pathlib.Path(__file__).resolve().parents[1])


def _stub_resolve_place(table):
    """Build a scripts.geocode.resolve_place-shaped fake from {name:
    (GeocodeResult_or_None, source_or_None)}. Any name not in `table` is an
    unresolvable lookup (None, None) — the same shape a real Nominatim miss
    returns. Used to drive scripts.source_verify_run's real (non-offline)
    geocode path deterministically, without a network."""
    def fake(name, district=None, country=None, timeout=10, cache=None, name_roman=None):
        return table.get(name, (None, None))
    return fake


def _brief(local_lang="zh"):
    return {"destination": {"country": "TW", "city": "嘉義市", "local_lang": local_lang}}


def _candidate(id_, name, claimed_district=None, sources=None):
    cand = {
        "id": id_, "name_local": name, "name_display": name,
        "business_status": {"status": "OPERATIONAL",
                            "source_url": "https://a.example.com/p",
                            "as_of": datetime.date.today().isoformat()},
        "sources": sources or [{"url": "https://a.example.com/p", "lang": "zh"},
                               {"url": "https://b.example.com/q", "lang": "en"}],
    }
    if claimed_district is not None:
        cand["claimed_district"] = claimed_district
    return cand


def test_the_cli_cannot_be_the_only_thing_forwarding_resolved_name():
    """Guard, GREEN at HEAD: Part 1 Task 3 already landed the refusal, so this
    test asserts existing behaviour rather than exercising anything TW-068 adds
    — verify_poi itself refuses when resolved_name is absent, so a hand-written
    driver cannot skip Gate 2b either.

    A CLI only protects its own callers, and the hand-written consumer drivers
    were exactly the callers nobody was protecting. This asserts the function-level
    half holds, so the CLI test below is about forwarding, not about safety.
    """
    from scripts.verify import verify_poi
    poi = {"id": "x", "name_local": "星月大地", "name_display": "星月大地",
           "district": "嘉義市西區",
           "business_status": {"status": "OPERATIONAL",
                               "source_url": "https://e.example/x",
                               "as_of": "2026-08-01"},
           "geocode": {"lat": 23.4, "lng": 120.4, "geocode_source": "nominatim"},
           "sources": [{"url": "https://a.example.tw/p", "lang": "zh"},
                       {"url": "https://b.example.com/q", "lang": "en"}]}
    today = datetime.date(2026, 8, 8)
    _, with_name, _ = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang="zh", resolved_name="星月驛站", today=today)
    _, without, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                  local_lang="zh", today=today)
    assert with_name == "conflicting"
    assert without == "unverified"
    assert "resolved_name" in note


def test_official_domain_decision_lives_in_the_plugin():
    """The chiayi consumer hardcoded OFFICIAL_DOMAINS in its own driver and had to
    edit it again to flag one hotel's site. grep -rn OFFICIAL_DOMAINS across the
    plugin returns nothing at HEAD."""
    from scripts.verify import is_official_url
    assert is_official_url("https://south.npm.gov.tw/") is True
    assert is_official_url("https://chiayi.maisondechinehotel.com/tw/") is False
    assert is_official_url("https://chiayi.maisondechinehotel.com/tw/",
                           extra_suffixes=("maisondechinehotel.com",)) is True


def test_cli_writes_a_schema_valid_artifact_and_forwards_both_gate_arguments(tmp_path):
    trip, work = tmp_path / "trip", tmp_path / "work"
    trip.mkdir(); work.mkdir()
    (trip / "trip-brief.yaml").write_text(yaml.safe_dump(
        {"slug": "t", "destination": {"country": "TW", "city": "嘉義市",
                                      "local_lang": "zh"},
         "dates": {"start": "2026-08-29", "end": "2026-08-31"}},
        allow_unicode=True), encoding="utf-8")
    # business_status is a sourced object dated "today" (Gate 0, already-shipped
    # P1/TW-005) so the candidate clears Gate 0 and reaches Gate 1b — otherwise
    # Gate 0 fires first ("operating status not established") and the assertion
    # below about 'local language' would never be exercised. Gate 0 fires
    # unconditionally before Gate 1 in classify_candidate's documented order
    # (skills/source-verify/SKILL.md:28); an as_of-less/absent business_status
    # was verified to short-circuit there before this fixture was written.
    (trip / "candidates.yaml").write_text(yaml.safe_dump({"candidates": [
        {"id": "en-only", "name_local": "花磚博物館", "name_display": "花磚博物館",
         "claimed_district": "嘉義市西區",
         "business_status": {"status": "OPERATIONAL",
                             "source_url": "https://a.example.com/p",
                             "as_of": datetime.date.today().isoformat()},
         "sources": [{"url": "https://a.example.com/p", "lang": "en"},
                     {"url": "https://b.example.com/q", "lang": "en"}]},
    ]}, allow_unicode=True), encoding="utf-8")

    r = subprocess.run([sys.executable, "scripts/source_verify_run.py",
                        str(trip), "--work-dir", str(work), "--offline"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    out = yaml.safe_load((trip / "verified-pois.yaml").read_text(encoding="utf-8"))
    by_id = {p["id"]: p for p in out["pois"]}
    # Gate 1b fired => local_lang really was forwarded.
    assert by_id["en-only"]["verify_status"] == "unverified"
    assert "local language" in by_id["en-only"]["status_reason"]

    from scripts.validate_artifact import validate_file
    assert validate_file(str(trip / "verified-pois.yaml"))[0] == 0


def test_no_claimed_district_is_unverified_not_conflicting(tmp_path, monkeypatch):
    """Important finding 1 (fix round 1): a candidate with no claimed_district
    has nothing to region-check against — destination-research SKILL.md:15
    explicitly sanctions omitting claimed_district when no source states a
    location, so this is a routine shape, not malformed input. Before the fix,
    _geocode_candidate collapsed "never checked" into in_region_flag=False,
    which Gate 3b (scripts/verify.py:221-222) reports as a genuine region
    mismatch — a false statement, since no region comparison ever ran. Must
    come back 'unverified' (undetermined), never 'conflicting' (determined
    false) — the same undetermined-vs-false split Gate 2b's name_match=None
    and Gate 2c's GEOCODE_SOURCE_MISSING already enforce one gate over."""
    from scripts import source_verify_run as svr
    from scripts.geocode import GeocodeResult

    monkeypatch.setattr(svr.time, "sleep", lambda *_: None)
    monkeypatch.setattr(svr, "resolve_place", _stub_resolve_place({
        "花磚博物館": (GeocodeResult(23.481, 120.441, "花磚博物館"), "nominatim"),
    }))

    trip, work = tmp_path / "trip", tmp_path / "work"
    trip.mkdir(); work.mkdir()
    (trip / "trip-brief.yaml").write_text(yaml.safe_dump(_brief(), allow_unicode=True),
                                          encoding="utf-8")
    (trip / "candidates.yaml").write_text(yaml.safe_dump(
        {"candidates": [_candidate("no-district", "花磚博物館")]}, allow_unicode=True),
        encoding="utf-8")

    code, msgs, out_path, pois = svr.run(str(trip), str(work), offline=False)
    assert code == 0, msgs
    poi = {p["id"]: p for p in pois}["no-district"]
    assert poi["verify_status"] == "unverified"
    assert "region" in poi["status_reason"]


def test_unresolvable_claimed_district_is_unverified_not_conflicting(tmp_path, monkeypatch):
    """Important finding 1, second sub-case: claimed_district IS present but its
    own centroid lookup misses (a real Nominatim outcome for an obscure/
    misspelled district name). Same undetermined-not-false requirement as the
    no-district case above — the venue's own geocode is clean, there is simply
    nothing to compare it against."""
    from scripts import source_verify_run as svr
    from scripts.geocode import GeocodeResult

    monkeypatch.setattr(svr.time, "sleep", lambda *_: None)
    monkeypatch.setattr(svr, "resolve_place", _stub_resolve_place({
        "花磚博物館": (GeocodeResult(23.481, 120.441, "花磚博物館"), "nominatim"),
        # "嘉義市西區" deliberately absent from the table -> district lookup misses.
    }))

    trip, work = tmp_path / "trip", tmp_path / "work"
    trip.mkdir(); work.mkdir()
    (trip / "trip-brief.yaml").write_text(yaml.safe_dump(_brief(), allow_unicode=True),
                                          encoding="utf-8")
    (trip / "candidates.yaml").write_text(yaml.safe_dump(
        {"candidates": [_candidate("bad-district", "花磚博物館",
                                   claimed_district="嘉義市西區")]}, allow_unicode=True),
        encoding="utf-8")

    code, msgs, out_path, pois = svr.run(str(trip), str(work), offline=False)
    assert code == 0, msgs
    poi = {p["id"]: p for p in pois}["bad-district"]
    assert poi["verify_status"] == "unverified"
    assert "region" in poi["status_reason"]


def test_cli_forwards_resolved_name_and_geocode_source_through_the_real_geocode_path(
        tmp_path, monkeypatch):
    """Important finding 2: every shipped test reaches _geocode_candidate's
    non-offline branch through --offline=False... except none of them did —
    every prior test used --offline, which never touches resolve_place at all,
    so resolved_name/geocode_source/in_claimed_region forwarding had zero
    coverage. This drives the real (non-network, monkeypatched at the
    resolve_place name binding) geocode path end to end and checks the
    geocoder's actual display_name and source both reached the written
    artifact — not just that *some* verify_status came out the other end."""
    from scripts import source_verify_run as svr
    from scripts.geocode import GeocodeResult

    monkeypatch.setattr(svr.time, "sleep", lambda *_: None)
    monkeypatch.setattr(svr, "resolve_place", _stub_resolve_place({
        "嘉義市西區": (GeocodeResult(23.48, 120.44, "嘉義市西區"), "nominatim_structured"),
        "花磚博物館": (GeocodeResult(23.481, 120.441, "花磚博物館"), "nominatim"),
    }))

    trip, work = tmp_path / "trip", tmp_path / "work"
    trip.mkdir(); work.mkdir()
    (trip / "trip-brief.yaml").write_text(yaml.safe_dump(_brief(), allow_unicode=True),
                                          encoding="utf-8")
    (trip / "candidates.yaml").write_text(yaml.safe_dump(
        {"candidates": [_candidate("verified-path", "花磚博物館",
                                   claimed_district="嘉義市西區")]}, allow_unicode=True),
        encoding="utf-8")

    code, msgs, out_path, pois = svr.run(str(trip), str(work), offline=False)
    assert code == 0, msgs
    poi = {p["id"]: p for p in pois}["verified-path"]
    assert poi["verify_status"] == "verified", poi
    # geocode_source forwarded from the geocoder's own return value, not hardcoded.
    assert poi["geocode"]["geocode_source"] == "nominatim"
    assert poi["geocode"]["lat"] == 23.481 and poi["geocode"]["lng"] == 120.441


def test_cli_forwards_in_claimed_region_through_the_real_geocode_path(tmp_path, monkeypatch):
    """Important finding 2, third forwarding: a venue that genuinely geocodes
    far outside its claimed district's centroid (a real Gate 3b determined-
    false, distinct from the two undetermined tests above, whose district DOES
    resolve) must come back 'conflicting', proving in_region's real result —
    not a hardcoded True — reaches verify_poi."""
    from scripts import source_verify_run as svr
    from scripts.geocode import GeocodeResult

    monkeypatch.setattr(svr.time, "sleep", lambda *_: None)
    monkeypatch.setattr(svr, "resolve_place", _stub_resolve_place({
        "嘉義市西區": (GeocodeResult(23.48, 120.44, "嘉義市西區"), "nominatim_structured"),
        # ~14.6km from the district centroid — well outside the 5km default radius.
        "花磚博物館": (GeocodeResult(23.60, 120.50, "花磚博物館"), "nominatim"),
    }))

    trip, work = tmp_path / "trip", tmp_path / "work"
    trip.mkdir(); work.mkdir()
    (trip / "trip-brief.yaml").write_text(yaml.safe_dump(_brief(), allow_unicode=True),
                                          encoding="utf-8")
    (trip / "candidates.yaml").write_text(yaml.safe_dump(
        {"candidates": [_candidate("far-away", "花磚博物館",
                                   claimed_district="嘉義市西區")]}, allow_unicode=True),
        encoding="utf-8")

    code, msgs, out_path, pois = svr.run(str(trip), str(work), offline=False)
    assert code == 0, msgs
    poi = {p["id"]: p for p in pois}["far-away"]
    assert poi["verify_status"] == "conflicting", poi
    assert "region" in poi["status_reason"]
