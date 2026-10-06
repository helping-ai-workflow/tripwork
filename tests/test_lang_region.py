"""v2.1.0 §1 (D3): a Chinese local language carries its region, and so must the source
that satisfies Gate 1b -- `zh` is never taken for Taiwan."""
import json
import pathlib
import re

import pytest
import yaml

from scripts.paths import artifact_path
from scripts.verify import classify_candidate, lang_matches, normalize_lang
from tests.cli_helpers import run_main
from tests.mech_fixtures import build_full_trip, trip_brief, write_artifact

ROOT = pathlib.Path(__file__).resolve().parent.parent
_BRIEF = json.loads((ROOT / "schemas" / "trip-brief.schema.json").read_text(encoding="utf-8"))
LANG_PATTERN = _BRIEF["properties"]["destination"]["properties"]["local_lang"]["pattern"]
REGIONS_MSG = "zh-TW / zh-HK / zh-CN / zh-SG / zh-MY"


@pytest.mark.parametrize("v", ["zh-TW", "zh-Hant-TW", "zh_TW", "ja", "ko-KR"])
def test_local_lang_pattern_accepts(v):
    assert re.match(LANG_PATTERN, v)


@pytest.mark.parametrize("v", ["zh", "ZH", "zh-Hant", "zh-Hans"])
def test_local_lang_pattern_rejects(v):
    assert not re.match(LANG_PATTERN, v)


def test_normalize_lang():
    assert normalize_lang("zh-Hant-TW") == ("zh", "TW")
    assert normalize_lang("ZH_tw") == ("zh", "TW")
    assert normalize_lang("ja") == ("ja", None)


def test_lang_matches_case_and_underscore():
    assert lang_matches("zh-TW", "ZH_tw") and lang_matches("zh-TW", "zh-hant-tw")


def test_lang_matches_region_differs():
    assert not lang_matches("zh-TW", "zh-CN")


def test_bare_zh_source_never_matches_chinese_trip():
    assert not lang_matches("zh-TW", "zh")


def test_ja_without_region_matches_ja_jp():
    assert lang_matches("ja", "ja-JP")


def _cand(lang):
    return {"sources": [{"url": "https://a.example/x", "lang": lang},
                        {"url": "https://b.example/y", "lang": lang}]}


def test_gate_1b_reason_asks_for_region():
    status, note = classify_candidate(_cand("zh"), True, True, local_lang="zh-TW")
    assert status == "unverified" and "標 zh、沒有地區" in note


def test_gate_1b_passes_with_tagged_source():
    status, _ = classify_candidate(_cand("zh-TW"), True, True, local_lang="zh-TW")
    assert status == "verified"


def test_non_chinese_trip_keeps_zh_sources_silent():
    status, note = classify_candidate(_cand("zh"), True, True, local_lang="ko")
    assert status == "unverified"
    assert note == "needs >=1 source in local language 'ko'"


def _next(t, w):
    r = run_main("scripts.next_stage", [str(t), "--work-dir", str(w)])
    assert r.returncode == 0, r.stderr
    return yaml.safe_load(r.stdout)


def test_rule_1_message_names_the_regions(tmp_path):
    t, w = build_full_trip(tmp_path)
    brief = trip_brief()
    brief["destination"] = {"country": "台灣", "city": "示意市", "local_lang": "zh"}
    write_artifact(artifact_path(t, "trip-brief.yaml"), brief)
    out = _next(t, w)
    assert out["next"] == "tripwork:trip-brief"
    assert REGIONS_MSG in out["reason"]


def test_rule_1_other_invalid_keeps_generic_message(tmp_path):
    t, w = build_full_trip(tmp_path)
    brief = trip_brief()
    del brief["dates"]
    write_artifact(artifact_path(t, "trip-brief.yaml"), brief)
    out = _next(t, w)
    assert out["next"] == "tripwork:trip-brief"
    assert out["reason"] == "rule 1: trip-brief.yaml exists but is not schema-valid"


def _legacy_trip(root):
    """A pre-v1.0 trip (artifacts at the trip root) carrying zh sources."""
    t = root / "trips" / "t"
    t.mkdir(parents=True)
    (root / "work").mkdir()
    (root / "work" / ".preflight-completed").touch()
    (t / "trip-brief.yaml").write_text(yaml.safe_dump(
        {"slug": "t", "destination": {"country": "台灣", "city": "示意市", "local_lang": "zh"}},
        allow_unicode=True), encoding="utf-8")
    (t / "candidates.yaml").write_text(yaml.safe_dump({"candidates": [{"id": "a", "sources": [
        {"url": "https://a.example.com.tw/", "lang": "zh"}, {"url": "https://b.example/", "lang": "zh"}]}]},
        allow_unicode=True), encoding="utf-8")
    return t


def test_migrate_dry_run_and_apply_list_same_counts(tmp_path, capsys):
    t = _legacy_trip(tmp_path)
    dry = run_main("scripts.migrate_v1", [str(t), "--work-root", str(tmp_path / "work")])
    assert dry.returncode == 0 and "lang: candidates 1" in dry.stdout
    assert "trip-brief 1" in dry.stdout
    app = run_main("scripts.migrate_v1", [str(t), "--work-root", str(tmp_path / "work"), "--apply"])
    assert app.returncode == 0 and "lang: candidates 1" in app.stdout
    data = yaml.safe_load((t / "data" / "candidates.yaml").read_text(encoding="utf-8"))
    assert [s["lang"] for s in data["candidates"][0]["sources"]] == ["zh-TW", "zh"]
    brief = yaml.safe_load((t / "data" / "trip-brief.yaml").read_text(encoding="utf-8"))
    assert brief["destination"]["local_lang"] == "zh-TW"


def test_migrate_tags_an_already_v1_trip(tmp_path):
    t = _legacy_trip(tmp_path)
    run_main("scripts.migrate_v1", [str(t), "--work-root", str(tmp_path / "work"), "--apply"])
    (t / "data" / "candidates.yaml").write_text(yaml.safe_dump({"candidates": [{"id": "a", "sources": [
        {"url": "https://x.example/zh-tw/", "lang": "zh"}]}]}), encoding="utf-8")
    r = run_main("scripts.migrate_v1", [str(t), "--work-root", str(tmp_path / "work"), "--apply"])
    assert "lang: candidates 1" in r.stdout
    data = yaml.safe_load((t / "data" / "candidates.yaml").read_text(encoding="utf-8"))
    assert data["candidates"][0]["sources"][0]["lang"] == "zh-TW"


def test_after_migrate_apply_next_stage_does_not_stop(tmp_path):
    t = _legacy_trip(tmp_path)
    run_main("scripts.migrate_v1", [str(t), "--work-root", str(tmp_path / "work"), "--apply"])
    assert _next(t, tmp_path / "work" / "t")["next"] != "stop-and-ask"
