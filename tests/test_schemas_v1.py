"""v1.0 P1 — schema 可選欄位：新形狀 valid、舊形狀仍 valid、錯的 enum/相依被擋。"""
import copy
import json
import pathlib

import jsonschema
import pytest

from scripts.validate_artifact import SCHEMAS, validate_file
from tests.mech_fixtures import (accommodations, build_full_trip, itinerary, trip_brief,
                                 verified_pois)


def _errors(schema_name, doc):
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    return list(jsonschema.Draft7Validator(schema).iter_errors(doc))


def test_the_full_v1_fixture_trip_is_schema_valid(tmp_path):
    # Positive control that cannot pass vacuously: the fixture must actually CARRY
    # the v1 fields before "it validates" means anything.
    assert all("theme" in d for d in itinerary()["days"])
    assert "area_label" in accommodations()["stops"][0]
    assert "headline_candidates" in trip_brief()
    from scripts.paths import data_dir
    t, _ = build_full_trip(tmp_path)
    found = sorted(data_dir(t).glob("*.yaml"))
    assert len(found) >= 12, found            # a glob that finds nothing proves nothing
    for p in found:
        code, msgs = validate_file(p)
        assert code == 0, (p.name, msgs)


def test_a_pre_v1_itinerary_is_still_schema_valid():
    old = {"title": "舊行程", "checklist": ["護照效期"],
           "contingency": [{"trigger": "雨", "fallback": "室內"}],
           "days": [{"date": "2026-08-01", "label": "D1",
                     "rows": [{"slot": "move", "text": "移動", "from": "A", "to": "B"},
                              {"slot": "meal", "time": "12:00", "poi_id": "p", "text": "午餐"}]}]}
    assert _errors("itinerary.schema.json", old) == []


def test_pre_v1_sources_and_stops_are_still_valid():
    pois = verified_pois()
    for s in pois["pois"][0]["sources"]:
        for k in ("site", "site_local"):
            s.pop(k, None)
    assert _errors("verified-pois.schema.json", pois) == []
    acc = accommodations()
    acc["stops"][0].pop("area_label", None)
    assert _errors("accommodations.schema.json", acc) == []


def _itin_with(mutate):
    doc = itinerary()
    mutate(doc)
    return doc


# Each case names the validator that must reject it. Asserting only "some error"
# would pass before Task 2 for the WRONG reason (additionalProperties rejects the
# unknown key), which is exactly the surprise-green the pre-ship gate forbids.
@pytest.mark.parametrize("mutate,validator", [
    (lambda d: d["days"][0]["rows"][0].__setitem__("mode", "train"), "enum"),
    (lambda d: d["days"][0]["rows"][0].__setitem__("basis", "guess"), "enum"),
    (lambda d: d.__setitem__("checklist", [{"kind": "打包"}]), "oneOf"),
    (lambda d: d.__setitem__("checklist", [{"kind": "買東西", "task": "x"}]), "oneOf"),
    (lambda d: d["days"][0].__setitem__("alternatives", [{"kind": "plan-b", "applies_to": "poi-1",
                                                           "trigger": "t", "fallback": "f",
                                                           "poi_id": "poi-1"}]), "enum"),
    (lambda d: d["days"][0].__setitem__("theme_refs", "poi-1"), "type"),
])
def test_bad_itinerary_values_are_rejected(mutate, validator):
    assert _errors("itinerary.schema.json", itinerary()) == []
    errs = _errors("itinerary.schema.json", _itin_with(mutate))
    assert any(e.validator == validator for e in errs), [(e.validator, e.message) for e in errs]


def test_opens_at_needs_its_source_and_intro_needs_its_source():
    pois = verified_pois()
    pois["pois"][0]["booking"] = {"opens_at": "2026-10-17 08:00"}
    assert _errors("verified-pois.schema.json", pois)
    pois["pois"][0]["booking"]["opens_at_source"] = "https://official.example/r"
    assert _errors("verified-pois.schema.json", pois) == []
    pois["pois"][0]["intro"] = "函館的地標"
    assert _errors("verified-pois.schema.json", pois)
    pois["pois"][0]["intro_source"] = "https://official.example/goryokaku"
    assert _errors("verified-pois.schema.json", pois) == []


def test_brief_headline_device_enum():
    b = trip_brief()
    b["headline_candidates"][0]["device"] = "rhyme"
    assert _errors("trip-brief.schema.json", b)
