import json, pathlib, yaml
import jsonschema
import pytest

SCHEMAS = pathlib.Path(__file__).resolve().parent.parent / "schemas"
FIX = pathlib.Path(__file__).resolve().parent / "fixtures"

def _load_schema(name):
    return json.load(open(SCHEMAS / name))

def _load_yaml(p):
    return yaml.safe_load(open(p))

def test_verified_pois_sample_valid():
    schema = _load_schema("verified-pois.schema.json")
    data = _load_yaml(FIX / "verified-pois.sample.yaml")
    jsonschema.validate(data, schema)

def test_verified_pois_missing_geocode_rejected():
    schema = _load_schema("verified-pois.schema.json")
    bad = {"pois": [{
        "id": "x", "name_local": "x", "name_display": "x",
        "category": "restaurant", "district": "x",
        "sources": [{"url": "a", "lang": "ko"}, {"url": "b", "lang": "zh"}],
        "verify_status": "verified"
    }]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_verified_pois_single_source_rejected():
    schema = _load_schema("verified-pois.schema.json")
    bad = {"pois": [{
        "id": "x", "name_local": "x", "name_display": "x",
        "category": "restaurant", "district": "x",
        "geocode": {"lat": 1.0, "lng": 2.0},
        "sources": [{"url": "a", "lang": "ko"}],
        "verify_status": "verified"
    }]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_trip_brief_minimal_valid():
    schema = _load_schema("trip-brief.schema.json")
    data = {"slug": "2026-korea-maple", "dates": {"start": "2026-05-24", "end": "2026-05-28"},
            "members": [{"name": "mom", "notes": "elderly"}],
            "base": {"name": "Lotte Hotel World", "district": "잠실"},
            "must_do": ["maplestory park"], "constraints": [], "preferences": {}}
    jsonschema.validate(data, schema)

def test_trip_brief_max_hop_override_allowed():
    schema = _load_schema("trip-brief.schema.json")
    data = {"slug": "x", "dates": {"start": "2026-05-24", "end": "2026-05-28"},
            "members": [], "base": {"name": "h", "district": "d"},
            "must_do": [], "constraints": [], "preferences": {},
            "routing": {"max_hop_mins": 45}}
    jsonschema.validate(data, schema)

def test_routing_sample_valid():
    schema = _load_schema("routing.schema.json")
    data = _load_yaml(FIX / "routing.sample.yaml")
    jsonschema.validate(data, schema)

def test_advisory_requires_effective_date():
    schema = _load_schema("advisory.schema.json")
    bad = {"items": [{"topic": "battery", "rule": "no overhead bin",
                      "sources": [{"url": "a", "official": True}]}]}  # no effective_date
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_candidate_requires_name_local_and_sources():
    schema = _load_schema("candidates.schema.json")
    bad = {"candidates": [{"id": "x", "name_display": "X", "category": "restaurant"}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_candidate_with_name_local_and_sources_valid():
    schema = _load_schema("candidates.schema.json")
    ok = {"candidates": [{"id": "x", "name_local": "엑스", "name_display": "X",
                          "category": "restaurant",
                          "sources": [{"url": "a", "lang": "ko"}]}]}
    jsonschema.validate(ok, schema)

def test_advisory_requires_at_least_one_official_source():
    schema = _load_schema("advisory.schema.json")
    bad = {"items": [{"topic": "battery", "rule": "no overhead bin",
                      "effective_date": "2026-01-26",
                      "sources": [{"url": "blog", "official": False}]}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_advisory_one_official_source_passes():
    schema = _load_schema("advisory.schema.json")
    ok = {"items": [{"topic": "battery", "rule": "no overhead bin",
                     "effective_date": "2026-01-26",
                     "sources": [{"url": "airline", "official": True},
                                 {"url": "blog", "official": False}]}]}
    jsonschema.validate(ok, schema)

def test_gate_report_valid():
    schema = _load_schema("gate-report.schema.json")
    data = {"status": "pass", "checks": [{"name": "all_pois_geocoded", "passed": True}], "failures": []}
    jsonschema.validate(data, schema)

def test_trip_brief_region_radius_override_allowed():
    schema = _load_schema("trip-brief.schema.json")
    data = {"slug": "x", "dates": {"start": "2026-05-24", "end": "2026-05-28"},
            "members": [], "base": {"name": "h", "district": "d"},
            "must_do": [], "constraints": [], "preferences": {},
            "routing": {"max_hop_mins": 60, "region_radius_km": 3.0}}
    jsonschema.validate(data, schema)
