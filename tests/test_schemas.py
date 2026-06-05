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

def test_candidate_empty_sources_rejected():
    schema = _load_schema("candidates.schema.json")
    bad = {"candidates": [{"id": "x", "name_local": "엑스", "name_display": "X",
                           "category": "restaurant", "sources": []}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

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

def test_calendar_sample_valid():
    schema = _load_schema("calendar.schema.json")
    ok = {"holidays": [{"date": "2026-05-25", "name_local": "대체공휴일",
                        "name_display": "Substitute Holiday", "type": "substitute",
                        "impact": {"crowds": True, "closures": False},
                        "sources": [{"url": "https://gov.kr", "official": True}]}]}
    jsonschema.validate(ok, schema)


def test_calendar_requires_official_source():
    schema = _load_schema("calendar.schema.json")
    bad = {"holidays": [{"date": "2026-05-25", "name_local": "x", "name_display": "x",
                         "sources": [{"url": "blog", "official": False}]}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_calendar_requires_date():
    schema = _load_schema("calendar.schema.json")
    bad = {"holidays": [{"name_local": "x", "name_display": "x",
                         "sources": [{"url": "gov", "official": True}]}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_verified_pois_closed_days_allowed():
    schema = _load_schema("verified-pois.schema.json")
    ok = {"pois": [{"id": "x", "name_local": "경복궁", "name_display": "Gyeongbokgung",
                    "category": "sight", "district": "종로",
                    "geocode": {"lat": 37.5796, "lng": 126.977},
                    "sources": [{"url": "a", "lang": "ko"}, {"url": "b", "lang": "zh"}],
                    "verify_status": "verified", "closed_days": ["tuesday"]}]}
    jsonschema.validate(ok, schema)


def test_verified_pois_hours_allowed():
    schema = _load_schema("verified-pois.schema.json")
    ok = {"pois": [{"id": "x", "name_local": "店", "name_display": "Shop",
                    "category": "restaurant", "district": "中区",
                    "geocode": {"lat": 1.0, "lng": 2.0},
                    "sources": [{"url": "a", "lang": "ja"}, {"url": "b", "lang": "zh"}],
                    "verify_status": "verified",
                    "hours": {"close": "21:30", "last_order": "20:30", "typical_visit_mins": 60}}]}
    jsonschema.validate(ok, schema)


def test_trip_brief_scheduling_override_allowed():
    schema = _load_schema("trip-brief.schema.json")
    data = {"slug": "x", "dates": {"start": "2026-05-24", "end": "2026-05-28"},
            "members": [], "base": {"name": "h", "district": "d"},
            "must_do": [], "constraints": [], "preferences": {},
            "scheduling": {"min_buffer_mins": 30, "default_visit_mins": 60}}
    jsonschema.validate(data, schema)


def test_trip_brief_region_radius_override_allowed():
    schema = _load_schema("trip-brief.schema.json")
    data = {"slug": "x", "dates": {"start": "2026-05-24", "end": "2026-05-28"},
            "members": [], "base": {"name": "h", "district": "d"},
            "must_do": [], "constraints": [], "preferences": {},
            "routing": {"max_hop_mins": 60, "region_radius_km": 3.0}}
    jsonschema.validate(data, schema)

def test_verified_pois_source_declares_official():
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "verified-pois.schema.json"))
    props = schema["properties"]["pois"]["items"]["properties"]["sources"]["items"]["properties"]
    assert "official" in props and props["official"]["type"] == "boolean"

def test_verified_pois_geocode_declares_source():
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "verified-pois.schema.json"))
    geo = schema["properties"]["pois"]["items"]["properties"]["geocode"]["properties"]
    assert "geocode_source" in geo
    assert geo["geocode_source"]["enum"] == ["nominatim", "nominatim_structured", "cluster_fallback"]

def test_trip_brief_declares_overnight_stops_and_facility_needs():
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    props = json.load(open(root / "schemas" / "trip-brief.schema.json"))["properties"]
    assert "overnight_stops" in props
    assert props["overnight_stops"]["items"]["required"] == ["district", "nights"]
    assert "facility_needs" in props
    assert "periodic" in props["facility_needs"]["properties"]
