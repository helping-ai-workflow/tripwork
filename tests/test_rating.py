"""v2.1.0 §11: an optional, sourced rating rides from research to the table; it never
stops, demotes or conflicts a place."""
import datetime
import json
import pathlib

import jsonschema
import pytest

from scripts import source_verify_run as svr
from scripts import survey_table as st
from scripts.verify import classify_candidate

ROOT = pathlib.Path(__file__).resolve().parent.parent
RATING = {"platform": "示意評分網", "score": 4.6, "count": 12, "source_url": "https://r.example/p",
          "as_of": "2030-01-01"}


def _schema(name, key):
    s = json.loads((ROOT / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
    return s["properties"][key]["items"]["properties"]["rating"]


@pytest.mark.parametrize("name,key", [("candidates", "candidates"), ("verified-pois", "pois")])
def test_rating_schema_requires_its_source(name, key):
    schema = _schema(name, key)
    jsonschema.validate(RATING, schema)
    jsonschema.validate({**RATING, "note": "分數高但遊記多抱怨等太久"}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({k: v for k, v in RATING.items() if k != "source_url"}, schema)


def test_build_poi_carries_the_rating():
    cand = {"id": "p", "name_local": "示意食堂", "sources": [], "rating": RATING}
    assert svr._build_poi(cand, (), None)["rating"] == RATING


def test_rating_is_not_a_carried_overlay():
    assert "rating" not in svr._carried_keys()


def test_rating_never_changes_a_verdict():
    base = {"sources": [{"url": "https://a.example/p", "lang": "zh-TW"},
                        {"url": "https://b.example/p", "lang": "zh-TW"}]}
    assert classify_candidate({**base, "rating": RATING}, True, True, local_lang="zh-TW") == \
        classify_candidate(base, True, True, local_lang="zh-TW")


def test_conflict_reason_no_longer_names_rating():
    _, note = classify_candidate({"sources": [{"url": "https://a.example/p", "lang": "zh-TW"},
                                              {"url": "https://b.example/p", "lang": "zh-TW"}]},
                                 True, True, local_lang="zh-TW", conflict_detected=True)
    assert "rating" not in note and note == "cross-source disagreement on hours/address"


def test_few_reviews_warning_and_note():
    p = {"verify_status": "verified", "name_display": "示意食堂", "rating": {**RATING, "note": "口碑不一"}}
    row = st.render_table([p], ["評分", "評論數", "評分警訊"], {})
    assert row.splitlines()[-1] == "| 4.6（示意評分網） | 12 | 評論少；口碑不一 |"


def test_no_rating_leaves_blank_cells():
    row = st.render_table([{"verify_status": "verified"}], ["評分", "評論數", "評分警訊"], {})
    assert row.splitlines()[-1] == "|  |  |  |"
