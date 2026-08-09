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
