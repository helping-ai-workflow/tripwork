"""E2E closure for v0.7.0 seasonal advisory (spec §7 / CLAUDE.md step-7 fixture).

Reproduces the NZ South Island snow-season self-drive: short winter daylight is
computed for a -44 lat stop in July, an after-dark driving leg is detected, and a
seasonal.yaml carrying a blocking road_closure + a chains advisory validates.
"""
import json, pathlib, jsonschema
from scripts.season import daylight_hours, approx_sunset, after_dark

ROOT = pathlib.Path(__file__).resolve().parent.parent

def test_nz_winter_daylight_is_short():
    assert daylight_hours("2026-07-15", -44.0) < 11.0
    s = approx_sunset("2026-07-15", -44.0)
    hh, mm = (int(x) for x in s.split(":"))
    assert 16 * 60 <= hh * 60 + mm <= 17 * 60 + 30

def test_after_dark_leg_flagged_in_winter():
    assert after_dark("18:30", "2026-07-15", -44.0) is True
    assert after_dark("14:00", "2026-07-15", -44.0) is False

def test_seasonal_fixture_validates_with_blocking_and_advisory():
    schema = json.load(open(ROOT / "schemas" / "seasonal.schema.json"))
    seasonal = {
        "items": [
            {"hazard": "road_closure", "note": "Crown Range closed in heavy snow",
             "severity": "blocking", "applies_to": "Wanaka->Queenstown",
             "sources": [{"url": "https://www.journeys.nzta.govt.nz", "official": True}]},
            {"hazard": "chains_required", "note": "Carry snow chains for alpine roads",
             "severity": "advisory",
             "sources": [{"url": "https://www.nzta.govt.nz", "official": True}]},
        ],
        "daylight": [
            {"district": "Tekapo", "date": "2026-07-15",
             "sunset": approx_sunset("2026-07-15", -44.0), "after_dark_arrival": True},
        ],
    }
    jsonschema.validate(seasonal, schema)  # must not raise
    blocking = [i for i in seasonal["items"] if i["severity"] == "blocking"]
    assert len(blocking) == 1  # would trigger stop-on-confirmation
