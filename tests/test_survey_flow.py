"""v2.1.0 §10: a survey (collect + verify, no itinerary) stops after verify with a list
page; upgrading it to a trip carries on from rule 1.5 without re-verifying."""
import json
import os
import pathlib

import jsonschema
import pytest
import yaml

from scripts.brief_names import deliverable_stem, is_survey, name_failures
from scripts.paths import artifact_path, deliverable_paths
from tests.cli_helpers import run_main
from tests.mech_fixtures import build_full_trip, candidates, trip_brief, verified_pois, write_artifact

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schemas" / "trip-brief.schema.json").read_text(encoding="utf-8"))


def survey_brief(**kw):
    return {"slug": "t", "mode": "survey", "short_name": "府城散步",
            "destination": {"country": "台灣", "city": "臺南市中西區", "local_lang": "zh-TW"},
            "categories": ["吃的", "溫泉"], **kw}


def _valid(doc):
    return not list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(doc))


def test_survey_brief_valid_without_dates_members():
    assert _valid(survey_brief())


def test_survey_brief_needs_short_name_and_categories():
    b = survey_brief()
    del b["short_name"]
    assert not _valid(b)
    b = survey_brief()
    del b["categories"]
    assert not _valid(b)


def test_non_survey_brief_still_requires_dates():
    b = trip_brief()
    del b["dates"]
    assert not _valid(b)
    assert _valid(trip_brief())


def test_survey_stem_has_no_date():
    assert is_survey(survey_brief()) and not is_survey(trip_brief())
    assert deliverable_stem(survey_brief()) == "府城散步 清單"


def test_survey_name_failures_need_no_dates():
    assert name_failures(survey_brief()) == []
    assert name_failures(survey_brief(short_name="這個名字實在太長了啦")) != []


def _survey_trip(tmp_path):
    root = tmp_path
    t, w = root / "trips" / "t", root / "work" / "t"
    w.mkdir(parents=True)
    (root / "work" / ".preflight-completed").touch()
    write_artifact(artifact_path(t, "trip-brief.yaml"), survey_brief())
    return t, w


def _next(t, w):
    r = run_main("scripts.next_stage", [str(t), "--work-dir", str(w)])
    assert r.returncode == 0, r.stderr
    return yaml.safe_load(r.stdout)


def _bump(path, offset):
    st = os.stat(path)
    os.utime(path, (st.st_atime, st.st_mtime + offset))


def test_survey_skips_advisory(tmp_path):
    t, w = _survey_trip(tmp_path)
    assert _next(t, w)["next"] == "tripwork:destination-research"


def _verified(t):
    write_artifact(artifact_path(t, "candidates.yaml"), dict(candidates(), must_do_searched=[]))
    write_artifact(artifact_path(t, "verified-pois.yaml"), verified_pois())
    _bump(artifact_path(t, "verified-pois.yaml"), 10)


def test_survey_after_verify_routes_to_export_artifact(tmp_path):
    t, w = _survey_trip(tmp_path)
    _verified(t)
    out = _next(t, w)
    assert out == {"next": "tripwork:export-artifact", "reason": "survey：清單頁不存在或舊於 verified-pois"}


def test_survey_page_older_than_pois_routes_again(tmp_path):
    t, w = _survey_trip(tmp_path)
    _verified(t)
    page = deliverable_paths(t, survey_brief())["html"]
    page.write_text("<html></html>", encoding="utf-8")
    _bump(page, -60)
    assert _next(t, w)["next"] == "tripwork:export-artifact"


def test_survey_complete_when_page_fresh(tmp_path):
    t, w = _survey_trip(tmp_path)
    _verified(t)
    page = deliverable_paths(t, survey_brief())["html"]
    page.write_text("<html></html>", encoding="utf-8")
    _bump(page, 60)
    assert _next(t, w) == {"next": "complete", "reason": "survey：清單完成"}


def _upgraded(tmp_path, searched, must_do):
    t, w = build_full_trip(tmp_path)
    for name in ("routing.yaml", "accommodations.yaml", "legs.yaml", "calendar.yaml",
                 "seasonal.yaml", "transit.yaml", "cost.yaml", "itinerary.yaml"):
        artifact_path(t, name).unlink()
    brief = trip_brief()
    brief["must_do"] = must_do
    write_artifact(artifact_path(t, "trip-brief.yaml"), brief)
    cands = candidates()
    cands["must_do_searched"] = searched
    write_artifact(artifact_path(t, "candidates.yaml"), cands)
    _bump(artifact_path(t, "verified-pois.yaml"), 10)
    return t, w


def test_upgrade_new_must_do_returns_to_destination_research(tmp_path):
    t, w = _upgraded(tmp_path, searched=[], must_do=["函館山夜景"])
    out = _next(t, w)
    assert out["next"] == "tripwork:destination-research" and "函館山夜景" in out["reason"]


def test_upgrade_with_searched_must_do_goes_on(tmp_path):
    t, w = _upgraded(tmp_path, searched=["函館山夜景"], must_do=["函館山夜景"])
    assert _next(t, w)["next"] == "tripwork:routing-audit"


def test_candidates_without_the_record_never_loop(tmp_path):
    t, w = _upgraded(tmp_path, searched=None, must_do=["函館山夜景"])
    cands = candidates()
    write_artifact(artifact_path(t, "candidates.yaml"), cands)       # no must_do_searched key
    _bump(artifact_path(t, "verified-pois.yaml"), 10)
    assert _next(t, w)["next"] == "tripwork:routing-audit"


def test_a_survey_must_record_must_do_searched(tmp_path):
    """Final review: an upgrade can only find a new must_do if the survey recorded what it
    searched; the oracle asks research for the record (an empty list when none)."""
    t, w = _survey_trip(tmp_path)
    write_artifact(artifact_path(t, "candidates.yaml"), candidates())          # no must_do_searched
    out = _next(t, w)
    assert out["next"] == "tripwork:destination-research" and "must_do_searched" in out["reason"]
    cands = candidates()
    cands["must_do_searched"] = []
    write_artifact(artifact_path(t, "candidates.yaml"), cands)
    assert _next(t, w)["next"] == "tripwork:source-verify"


def test_destination_research_says_to_always_record_it():
    text = (ROOT / "skills" / "destination-research" / "SKILL.md").read_text(encoding="utf-8")
    assert "must_do_searched" in text and "`[]`" in text
