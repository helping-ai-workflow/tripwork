"""E2E closure for v0.11.0 transit polish (spec §7 / CLAUDE.md step-7 fixture).

A Tokyo elderly-family trip: a move at 08:00 is in the morning peak; a POI 20 min on foot
exceeds the 15-min comfortable walk; a transit.yaml with a Suica ic_card validates.
"""
import json, pathlib, jsonschema
from scripts.transit import in_peak, walk_too_far

ROOT = pathlib.Path(__file__).resolve().parent.parent

PEAKS = [{"label": "morning", "start": "07:30", "end": "09:30"},
         {"label": "evening", "start": "17:30", "end": "19:30"}]

def test_morning_move_is_flagged_in_peak():
    assert in_peak("08:00", PEAKS) is True
    assert in_peak("10:30", PEAKS) is False     # mid-morning move is fine

def test_long_station_walk_is_flagged():
    assert walk_too_far(20, 15) is True         # 20-min walk with elders -> flag
    assert walk_too_far(5, 15) is False

def test_transit_yaml_fixture_is_schema_valid():
    schema = json.load(open(ROOT / "schemas" / "transit.schema.json"))
    doc = {
        "peak_windows": PEAKS,
        "ic_card": {"name": "Suica", "where_to_buy": "JR ticket machines",
                    "top_up": "cash at machines / convenience stores",
                    "covers": "trains, buses, conbini",
                    "sources": [{"url": "https://www.jreast.co.jp/multi/en/pass/suica.html"}]},
        "walks": [{"poi_id": "sensoji", "station": "Asakusa", "mins": 5},
                  {"poi_id": "teamlab", "station": "Toyosu", "mins": 20, "note": "long walk"}],
    }
    jsonschema.validate(doc, schema)  # must not raise
    flagged = [w for w in doc["walks"] if walk_too_far(w["mins"], 15)]
    assert [w["poi_id"] for w in flagged] == ["teamlab"]
