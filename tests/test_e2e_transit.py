"""E2E closure for v0.11.0 transit polish (spec §7 / CLAUDE.md step-7 fixture).

A Tokyo elderly-family trip: a move at 08:00 is in the morning peak; a POI 20 min on foot
exceeds the 15-min comfortable walk; a transit.yaml with a Suica ic_card validates.
"""
import json, pathlib, jsonschema
from scripts.transit import in_peak, walk_too_far

ROOT = pathlib.Path(__file__).resolve().parent.parent

_SRC = [{"url": "https://www.jreast.co.jp/multi/en/"}]
PEAKS = [{"label": "morning", "start": "07:30", "end": "09:30", "sources": _SRC},
         {"label": "evening", "start": "17:30", "end": "19:30", "sources": _SRC}]

def test_morning_move_is_flagged_in_peak():
    assert in_peak("08:00", PEAKS) is True
    assert in_peak("10:30", PEAKS) is False     # mid-morning move is fine

def test_long_station_walk_is_flagged():
    assert walk_too_far(20, 15) is True         # 20-min walk with elders -> flag
    assert walk_too_far(5, 15) is False

def test_walk_ceiling_is_configurable_per_trip():
    # trip-brief.routing.max_walk_mins drives the flag: a frail-elder trip lowering it to
    # 10 flags an 12-min walk that the default 15 would have allowed.
    assert walk_too_far(12, 15) is False        # default ceiling: fine
    assert walk_too_far(12, 10) is True         # tighter ceiling: flagged

def test_transit_yaml_fixture_is_schema_valid():
    schema = json.load(open(ROOT / "schemas" / "transit.schema.json"))
    doc = {
        "peak_windows": PEAKS,
        "ic_card": {"name": "Suica", "where_to_buy": "JR ticket machines",
                    "top_up": "cash at machines / convenience stores",
                    "covers": "trains, buses, conbini",
                    "sources": [{"url": "https://www.jreast.co.jp/multi/en/pass/suica.html"}]},
        "walks": [{"poi_id": "sensoji", "station": "Asakusa", "mins": 5, "sources": _SRC},
                  {"poi_id": "teamlab", "station": "Toyosu", "mins": 20, "note": "long walk", "sources": _SRC}],
    }
    jsonschema.validate(doc, schema)  # must not raise
    flagged = [w for w in doc["walks"] if walk_too_far(w["mins"], 15)]
    assert [w["poi_id"] for w in flagged] == ["teamlab"]
