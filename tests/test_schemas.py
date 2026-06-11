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


def _vp_item(**over):
    base = {"id": "x", "name_local": "x", "name_display": "x",
            "category": "restaurant", "district": "x",
            "geocode": {"lat": 1.0, "lng": 2.0},
            "sources": [{"url": "a", "lang": "ko"}, {"url": "b", "lang": "zh"}],
            "verify_status": "verified"}
    base.update(over)
    return {"pois": [base]}

def test_verified_pois_unverified_without_geocode_validates():  # TW-012
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_item(verify_status="unverified", status_reason="geocode unresolved",
                   sources=[{"url": "a", "lang": "ko"}])
    del doc["pois"][0]["geocode"]
    jsonschema.validate(doc, schema)  # must NOT raise

def test_verified_pois_unverified_missing_status_reason_rejected():  # TW-012
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_item(verify_status="unverified", sources=[{"url": "a", "lang": "ko"}])
    del doc["pois"][0]["geocode"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)

def test_verified_pois_closed_days_noncanonical_rejected():  # TW-001
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_item(closed_days=["Tuesday"])  # capitalized, non-canonical
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)

def test_verified_pois_closed_days_canonical_accepted():  # TW-001
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_item(closed_days=["tuesday", "2026-06-13", "public_holiday"])
    jsonschema.validate(doc, schema)  # must NOT raise

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

def test_routing_cluster_declares_centroid():
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "routing.schema.json"))
    cprops = schema["properties"]["clusters"]["items"]["properties"]
    assert "centroid" in cprops
    assert cprops["centroid"]["required"] == ["lat", "lng"]

def test_accommodations_schema_validates_a_stop():
    import json, pathlib, jsonschema
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "accommodations.schema.json"))
    doc = {"stops": [{
        "district": "Tekapo", "nights": 2, "chosen": "godley",
        "candidates": [{
            "id": "godley", "name_local": "The Godley Hotel", "name_display": "The Godley Hotel",
            "facilities": ["parking", "laundry"],
            "geocode": {"lat": -44.0, "lng": 170.4, "geocode_source": "cluster_fallback"},
            "sources": [{"url": "https://godley.example", "lang": "en", "official": True},
                        {"url": "https://review.example", "lang": "en"}],
            "verify_status": "verified",
        }],
    }]}
    jsonschema.validate(doc, schema)  # must not raise

def test_accommodations_schema_allows_null_chosen():
    import json, pathlib, jsonschema
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "accommodations.schema.json"))
    doc = {"stops": [{"district": "Wanaka", "nights": 2, "chosen": None, "candidates": []}]}
    jsonschema.validate(doc, schema)

def test_seasonal_schema_validates_items_and_daylight():
    import json, pathlib, jsonschema
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "seasonal.schema.json"))
    doc = {
        "items": [{
            "hazard": "road_closure", "note": "Crown Range may close in snow",
            "severity": "blocking",
            "sources": [{"url": "https://nzta.govt.nz", "official": True}],
        }],
        "daylight": [{"district": "Tekapo", "date": "2026-07-15", "sunset": "16:30",
                      "after_dark_arrival": True}],
    }
    jsonschema.validate(doc, schema)  # must not raise

def test_seasonal_schema_requires_official_source():
    import json, pathlib, jsonschema, pytest
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "seasonal.schema.json"))
    bad = {"items": [{"hazard": "heat", "note": "x", "severity": "info",
                      "sources": [{"url": "https://blog.example", "official": False}]}],
           "daylight": []}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_trip_brief_declares_transport():
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    props = json.load(open(root / "schemas" / "trip-brief.schema.json"))["properties"]
    assert "transport" in props
    assert props["transport"]["type"] == "string"

def test_legs_schema_validates_a_transit_leg():
    import json, pathlib, jsonschema
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "legs.schema.json"))
    doc = {"legs": [{
        "from": "Tokyo", "to": "Kyoto", "mode": "rail", "duration_mins": 140,
        "status": "ok", "service": "Nozomi 21", "reserved": True, "transfers": 0,
        "last_service": "21:30", "pass_advice": "3 shinkansen legs -> JR Pass likely worth it",
        "sources": [{"url": "https://global.jr-central.co.jp", "official": True}],
    }]}
    jsonschema.validate(doc, schema)  # must not raise

def test_legs_schema_requires_official_source():
    import json, pathlib, jsonschema, pytest
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "legs.schema.json"))
    bad = {"legs": [{"from": "A", "to": "B", "mode": "rail", "status": "ok",
                     "sources": [{"url": "https://blog.example", "official": False}]}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_legs_schema_allows_empty_legs():
    import json, pathlib, jsonschema
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "legs.schema.json"))
    jsonschema.validate({"legs": []}, schema)  # single-base trip

def test_trip_brief_declares_leg_mode_and_max_single_drive():
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    props = json.load(open(root / "schemas" / "trip-brief.schema.json"))["properties"]
    assert "leg_mode" in props["overnight_stops"]["items"]["properties"]
    assert "max_single_drive_mins" in props["routing"]["properties"]

def test_cost_schema_validates_a_rollup():
    import json, pathlib, jsonschema
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "cost.schema.json"))
    doc = {
        "currency": "JPY",
        "line_items": [
            {"category": "accommodation", "label": "4 nights", "amount": 60000},
            {"category": "transport", "label": "Tokyo-Kyoto-Osaka", "amount": 28000},
            {"category": "incidental", "label": "5 days @ 6000", "amount": 30000},
        ],
        "total": 118000,
        "budget": {"amount": 120000, "over": False, "delta": 2000},
        "pass_break_even": {"name": "JR Pass 7d", "pass_price": 50000,
                            "individual_total": 28000, "use_pass": False, "saving": 22000},
        "as_of": "2026-06-05", "estimate_note": "estimate; prices vary",
    }
    jsonschema.validate(doc, schema)  # must not raise

def test_cost_schema_requires_currency_and_total():
    import json, pathlib, jsonschema, pytest
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "cost.schema.json"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"line_items": []}, schema)  # missing currency + total

def test_accommodations_candidate_declares_cost():
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "accommodations.schema.json"))
    cand = schema["properties"]["stops"]["items"]["properties"]["candidates"]["items"]["properties"]
    assert "cost" in cand
    assert cand["cost"]["properties"]["basis"]["enum"] == ["per_night", "total"]

def test_legs_declare_fare_and_pass():
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "legs.schema.json"))
    leg_props = schema["properties"]["legs"]["items"]["properties"]
    assert "fare" in leg_props
    assert "pass" in schema["properties"]
    assert "price" in schema["properties"]["pass"]["properties"]

def test_trip_brief_declares_cost_fields():
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    props = json.load(open(root / "schemas" / "trip-brief.schema.json"))["properties"]
    assert "budget" in props
    assert "daily_incidental" in props
    assert "home_currency" in props

def test_transit_schema_validates_a_doc():
    import json, pathlib, jsonschema
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "transit.schema.json"))
    doc = {
        "peak_windows": [{"label": "morning", "start": "07:30", "end": "09:30",
                          "note": "commuter crush"}],
        "ic_card": {"name": "Suica", "where_to_buy": "any JR machine", "top_up": "cash at machines",
                    "covers": "trains + buses + convenience stores",
                    "sources": [{"url": "https://www.jreast.co.jp/suica"}]},
        "walks": [{"poi_id": "sensoji", "station": "Asakusa", "mins": 5, "note": "flat"}],
    }
    jsonschema.validate(doc, schema)  # must not raise

def test_transit_schema_empty_arrays_ok_and_ic_card_optional():
    import json, pathlib, jsonschema
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "transit.schema.json"))
    jsonschema.validate({"peak_windows": [], "walks": []}, schema)  # cash-only / walk-everywhere

def test_transit_schema_ic_card_requires_source():
    import json, pathlib, jsonschema, pytest
    root = pathlib.Path(__file__).resolve().parent.parent
    schema = json.load(open(root / "schemas" / "transit.schema.json"))
    bad = {"peak_windows": [], "walks": [],
           "ic_card": {"name": "Suica", "sources": []}}   # no source
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_trip_brief_routing_declares_max_walk_mins():
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    props = json.load(open(root / "schemas" / "trip-brief.schema.json"))["properties"]
    assert "max_walk_mins" in props["routing"]["properties"]
