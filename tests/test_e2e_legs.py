"""E2E closure for v0.8.0 inter-stop legs (spec §7 / CLAUDE.md step-7 fixture).

A mixed multi-city trip: rail legs (Tokyo->Kyoto->Osaka) carry service + last-service;
a same-day move after the last service is flagged missed_last_service; a self-drive leg
over the single-day max is flagged drive_too_long. Each leg classified by its own mode.
"""
import json, pathlib, jsonschema
from scripts.legs import classify_leg

ROOT = pathlib.Path(__file__).resolve().parent.parent

LEGS = {"legs": [
    {"from": "Tokyo", "to": "Kyoto", "mode": "rail", "duration_mins": 140, "status": "ok",
     "service": "Nozomi 21", "reserved": True, "transfers": 0, "last_service": "21:30",
     "pass_advice": "3 shinkansen legs -> JR Pass likely worth it",
     "sources": [{"url": "https://global.jr-central.co.jp", "official": True}]},
    {"from": "Kyoto", "to": "Osaka", "mode": "rail", "duration_mins": 15, "status": "ok",
     "service": "Special Rapid", "reserved": False, "transfers": 0, "last_service": "23:50",
     "sources": [{"url": "https://www.jr-odekake.net", "official": True}]},
]}

def test_legs_fixture_is_schema_valid():
    schema = json.load(open(ROOT / "schemas" / "legs.schema.json"))
    jsonschema.validate(LEGS, schema)  # must not raise

def test_each_leg_classified_by_its_own_mode():
    drive = {"mode": "drive", "duration_mins": 360}
    assert classify_leg(drive, 300)[0] == "drive_too_long"
    assert classify_leg(LEGS["legs"][1])[0] == "ok"

def test_same_day_move_after_last_service_is_flagged():
    late = {"mode": "rail", "depart": "22:10", "last_service": "21:30"}
    assert classify_leg(late)[0] == "missed_last_service"

def test_single_base_trip_has_no_legs():
    schema = json.load(open(ROOT / "schemas" / "legs.schema.json"))
    jsonschema.validate({"legs": []}, schema)  # no inter-stop legs, still valid
