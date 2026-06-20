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
        "sources": [{"url": "https://a.example", "lang": "ko"}, {"url": "https://b.example", "lang": "zh"}],
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
        "sources": [{"url": "https://a.example", "lang": "ko"}],
        "verify_status": "verified"
    }]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_trip_brief_minimal_valid():
    schema = _load_schema("trip-brief.schema.json")
    data = {"slug": "2026-korea-maple", "dates": {"start": "2026-05-24", "end": "2026-05-28"},
            "members": [{"name": "mom", "notes": "elderly"}],
            "base": {"name": "Lotte Hotel World", "district": "잠실"},
            "must_do": ["maplestory park"], "constraints": [], "preferences": {}, "destination": {"country": "KR", "city": "Seoul", "local_lang": "ko"}}
    jsonschema.validate(data, schema)

def test_trip_brief_max_hop_override_allowed():
    schema = _load_schema("trip-brief.schema.json")
    data = {"slug": "x", "dates": {"start": "2026-05-24", "end": "2026-05-28"},
            "members": [], "base": {"name": "h", "district": "d"},
            "must_do": [], "constraints": [], "preferences": {}, "destination": {"country": "KR", "city": "Seoul", "local_lang": "ko"},
            "routing": {"max_hop_mins": 45}}
    jsonschema.validate(data, schema)

def test_routing_sample_valid():
    schema = _load_schema("routing.schema.json")
    data = _load_yaml(FIX / "routing.sample.yaml")
    jsonschema.validate(data, schema)

def test_advisory_requires_effective_date():
    schema = _load_schema("advisory.schema.json")
    bad = {"items": [{"topic": "battery", "rule": "no overhead bin",
                      "sources": [{"url": "https://a.example", "official": True}]}]}  # no effective_date
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
                          "sources": [{"url": "https://a.example", "lang": "ko"}]}]}
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
                      "sources": [{"url": "https://blog.example", "official": False}]}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_advisory_one_official_source_passes():
    schema = _load_schema("advisory.schema.json")
    ok = {"items": [{"topic": "battery", "rule": "no overhead bin",
                     "effective_date": "2026-01-26", "risk": "restricted",
                     "sources": [{"url": "https://airline.example", "official": True},
                                 {"url": "https://blog.example", "official": False}]}]}
    jsonschema.validate(ok, schema)

def test_gate_report_valid():
    schema = _load_schema("gate-report.schema.json")
    data = {"status": "pass", "checks": [{"name": "all_pois_geocoded", "passed": True}], "failures": []}
    jsonschema.validate(data, schema)

def test_gate_report_pass_with_failures_rejected():  # TW-009
    schema = _load_schema("gate-report.schema.json")
    bad = {"status": "pass", "checks": [{"name": "x", "passed": True}], "failures": ["boom"]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_gate_report_pass_with_empty_checks_rejected():  # TW-009
    schema = _load_schema("gate-report.schema.json")
    bad = {"status": "pass", "checks": [], "failures": []}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_gate_report_valid_fail():
    schema = _load_schema("gate-report.schema.json")
    ok = {"status": "fail", "checks": [{"name": "x", "passed": False}], "failures": ["boom"]}
    jsonschema.validate(ok, schema)

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
                         "sources": [{"url": "https://blog.example", "official": False}]}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_calendar_requires_date():
    schema = _load_schema("calendar.schema.json")
    bad = {"holidays": [{"name_local": "x", "name_display": "x",
                         "sources": [{"url": "https://gov.example", "official": True}]}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_verified_pois_closed_days_allowed():
    schema = _load_schema("verified-pois.schema.json")
    ok = {"pois": [{"id": "x", "name_local": "경복궁", "name_display": "Gyeongbokgung",
                    "category": "sight", "district": "종로",
                    "geocode": {"lat": 37.5796, "lng": 126.977},
                    "sources": [{"url": "https://a.example", "lang": "ko"}, {"url": "https://b.example", "lang": "zh"}],
                    "verify_status": "verified", "closed_days": ["tuesday"]}]}
    jsonschema.validate(ok, schema)


def _itin(rows, date="2026-06-12", **day_over):
    day = {"date": date, "label": "Day 1", "rows": rows}
    day.update(day_over)
    return {"title": "t", "days": [day]}

def test_itinerary_valid_minimal():  # TW-017
    schema = _load_schema("itinerary.schema.json")
    jsonschema.validate(_itin([{"time": "12:00", "slot": "meal", "poi_id": "x", "text": "lunch"}]), schema)

def test_itinerary_rejects_bad_date():
    schema = _load_schema("itinerary.schema.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_itin([{"slot": "meal", "text": "l"}], date="06/12/2026"), schema)

def test_itinerary_rejects_bad_time():
    schema = _load_schema("itinerary.schema.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_itin([{"time": "25:99", "slot": "meal", "text": "l"}]), schema)

def test_itinerary_rejects_unknown_slot():
    schema = _load_schema("itinerary.schema.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_itin([{"slot": "brunch", "text": "l"}]), schema)

def test_itinerary_rejects_extra_key():
    schema = _load_schema("itinerary.schema.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_itin([{"slot": "meal", "text": "l", "typo": 1}]), schema)

def test_itinerary_accepts_from_to_on_move_row():   # G2 — optional endpoint fields
    schema = _load_schema("itinerary.schema.json")
    jsonschema.validate(
        _itin([{"slot": "move", "text": "A→B", "from": "函館空港", "to": "函館駅"}]), schema)

def test_itinerary_from_to_optional_backward_compat():   # G2 — pre-feature rows still valid
    schema = _load_schema("itinerary.schema.json")
    jsonschema.validate(_itin([{"slot": "move", "text": "A→B"}]), schema)   # no from/to

def test_itinerary_additionalproperties_intact_with_from_to():   # G2 — seal stays honest
    schema = _load_schema("itinerary.schema.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            _itin([{"slot": "move", "text": "x", "from": "A", "to": "B", "typo": 1}]), schema)

def test_itinerary_checklist_accepted():  # TW-034 surface support
    schema = _load_schema("itinerary.schema.json")
    doc = _itin([{"slot": "meal", "text": "l"}])
    doc["checklist"] = ["lithium battery: carry-on only", "book restaurant 1 week ahead"]
    jsonschema.validate(doc, schema)

def _vp_item(**over):
    base = {"id": "x", "name_local": "x", "name_display": "x",
            "category": "restaurant", "district": "x",
            "geocode": {"lat": 1.0, "lng": 2.0},
            "sources": [{"url": "https://a.example", "lang": "ko"}, {"url": "https://b.example", "lang": "zh"}],
            "verify_status": "verified"}
    base.update(over)
    return {"pois": [base]}

def test_verified_pois_unverified_without_geocode_validates():  # TW-012
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_item(verify_status="unverified", status_reason="geocode unresolved",
                   sources=[{"url": "https://a.example", "lang": "ko"}])
    del doc["pois"][0]["geocode"]
    jsonschema.validate(doc, schema)  # must NOT raise

def test_verified_pois_unverified_missing_status_reason_rejected():  # TW-012
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_item(verify_status="unverified", sources=[{"url": "https://a.example", "lang": "ko"}])
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
                    "sources": [{"url": "https://a.example", "lang": "ja"}, {"url": "https://b.example", "lang": "zh"}],
                    "verify_status": "verified",
                    "hours": {"close": "21:30", "last_order": "20:30", "typical_visit_mins": 60}}]}
    jsonschema.validate(ok, schema)


def test_trip_brief_scheduling_override_allowed():
    schema = _load_schema("trip-brief.schema.json")
    data = {"slug": "x", "dates": {"start": "2026-05-24", "end": "2026-05-28"},
            "members": [], "base": {"name": "h", "district": "d"},
            "must_do": [], "constraints": [], "preferences": {}, "destination": {"country": "KR", "city": "Seoul", "local_lang": "ko"},
            "scheduling": {"min_buffer_mins": 30, "default_visit_mins": 60}}
    jsonschema.validate(data, schema)


def test_trip_brief_region_radius_override_allowed():
    schema = _load_schema("trip-brief.schema.json")
    data = {"slug": "x", "dates": {"start": "2026-05-24", "end": "2026-05-28"},
            "members": [], "base": {"name": "h", "district": "d"},
            "must_do": [], "constraints": [], "preferences": {}, "destination": {"country": "KR", "city": "Seoul", "local_lang": "ko"},
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
                          "note": "commuter crush",
                          "sources": [{"url": "https://jreast.example"}]}],
        "ic_card": {"name": "Suica", "where_to_buy": "any JR machine", "top_up": "cash at machines",
                    "covers": "trains + buses + convenience stores",
                    "sources": [{"url": "https://www.jreast.co.jp/suica"}]},
        "walks": [{"poi_id": "sensoji", "station": "Asakusa", "mins": 5, "note": "flat",
                   "sources": [{"url": "https://jreast.example"}]}],
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


# ---- Wave 2 (v0.13.0) schema-strictness acceptance guards ----

def _vp_verified(**over):
    base = {"id": "x", "name_local": "x", "name_display": "x", "category": "c",
            "district": "d", "geocode": {"lat": 37.5, "lng": 127.0},
            "sources": [{"url": "https://a.example", "lang": "ko"},
                        {"url": "https://b.example", "lang": "en"}],
            "verify_status": "verified"}
    base.update(over)
    return {"pois": [base]}

def test_verified_kana_name_requires_name_zh():   # 0.21.0 forward guard
    schema = _load_schema("verified-pois.schema.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_vp_verified(name_display="だるま 本店"), schema)   # kana, no name_zh

def test_verified_kana_name_with_zh_ok():
    schema = _load_schema("verified-pois.schema.json")
    jsonschema.validate(_vp_verified(name_display="だるま 本店", name_zh="達摩本店"), schema)

def test_verified_kana_name_empty_zh_rejected():
    schema = _load_schema("verified-pois.schema.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_vp_verified(name_display="だるま", name_zh=""), schema)   # minLength

def test_verified_han_name_no_zh_ok():
    schema = _load_schema("verified-pois.schema.json")
    jsonschema.validate(_vp_verified(name_display="五稜郭塔"), schema)   # Han-only → exempt

def test_unverified_kana_name_no_zh_ok():
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_item(verify_status="unverified", status_reason="single source",
                   name_display="だるま", sources=[{"url": "https://a.example", "lang": "ja"}])
    del doc["pois"][0]["geocode"]
    jsonschema.validate(doc, schema)   # unverified is exempt — never rendered


def test_tw013_additionalproperties_rejects_typo_key():
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_verified(close_days=["monday"])   # typo of closed_days
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)

def test_tw043_swapped_coords_rejected_everywhere():
    for name, build in [
        ("verified-pois.schema.json", lambda: _vp_verified(geocode={"lat": 126.98, "lng": 37.58})),
        ("accommodations.schema.json", lambda: {"stops": [{"district": "d", "nights": 1, "chosen": None,
            "candidates": [{"id": "h", "name_local": "h", "name_display": "h", "facilities": [],
                "geocode": {"lat": 126.98, "lng": 37.58},
                "sources": [{"url": "https://a.example", "lang": "en"}, {"url": "https://b.example", "lang": "en"}],
                "verify_status": "verified"}]}]}),
        ("routing.schema.json", lambda: {"clusters": [{"district": "d", "pois": [],
            "centroid": {"lat": 126.98, "lng": 37.58}}], "hops": [], "warnings": []}),
    ]:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(build(), _load_schema(name))

def test_tw008_source_url_must_be_http():
    schema = _load_schema("advisory.schema.json")
    bad = {"items": [{"topic": "battery", "rule": "x", "effective_date": "2026-01-01", "risk": "info",
                      "sources": [{"url": "airline", "official": True}, {"url": "https://b.example", "official": False}]}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_tw006_advisory_requires_risk_and_two_sources():
    schema = _load_schema("advisory.schema.json")
    no_risk = {"items": [{"topic": "t", "rule": "r", "effective_date": "2026-01-01",
                          "sources": [{"url": "https://a.example", "official": True},
                                      {"url": "https://b.example", "official": False}]}]}
    one_src = {"items": [{"topic": "t", "rule": "r", "effective_date": "2026-01-01", "risk": "info",
                          "sources": [{"url": "https://a.example", "official": True}]}]}
    for bad in (no_risk, one_src):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)

def test_tw007_non_iso_dates_rejected():
    cal = _load_schema("calendar.schema.json")
    bad_cal = {"holidays": [{"date": "2026/05/25", "name_local": "x", "name_display": "x",
                             "impact": {"crowds": True, "closures": False},
                             "sources": [{"url": "https://gov.example", "official": True}]}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad_cal, cal)

def test_tw040_calendar_impact_required():
    cal = _load_schema("calendar.schema.json")
    bad = {"holidays": [{"date": "2026-05-25", "name_local": "x", "name_display": "x",
                         "sources": [{"url": "https://gov.example", "official": True}]}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, cal)

def test_tw041_cost_requires_as_of_and_leg_fare_currency():
    cost = _load_schema("cost.schema.json")
    bad_cost = {"currency": "JPY", "line_items": [{"category": "x", "label": "y", "amount": 1}],
                "total": 1, "estimate_note": "e"}   # no as_of
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad_cost, cost)
    legs = _load_schema("legs.schema.json")
    bad_leg = {"legs": [{"from": "a", "to": "b", "mode": "rail", "status": "ok",
                         "fare": {"amount": 15000},
                         "sources": [{"url": "https://jr.example", "official": True}]}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad_leg, legs)

def test_tw042_transit_walk_requires_sources():
    schema = _load_schema("transit.schema.json")
    bad = {"peak_windows": [], "walks": [{"poi_id": "p", "station": "s", "mins": 5}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_tw011_trip_brief_requires_destination_local_lang():
    schema = _load_schema("trip-brief.schema.json")
    bad = {"slug": "x", "dates": {"start": "2026-05-24", "end": "2026-05-28"},
           "members": [], "base": {"name": "h", "district": "d"},
           "must_do": [], "constraints": [], "preferences": {},
           "destination": {"country": "KR", "city": "Seoul"}}   # missing local_lang
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_tw010_legs_mode_enum_and_drive_duration():
    schema = _load_schema("legs.schema.json")
    bad_mode = {"legs": [{"from": "a", "to": "b", "mode": "self_drive", "status": "ok",
                          "sources": [{"url": "https://x.example", "official": True}]}]}
    drive_no_dur = {"legs": [{"from": "a", "to": "b", "mode": "drive", "status": "ok",
                              "sources": [{"url": "https://x.example", "official": True}]}]}
    for bad in (bad_mode, drive_no_dur):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)


# ---- Wave 3 (v0.14.0) ----

def test_stage_state_schema_validates_fixture():   # TW-055
    schema = _load_schema("stage-state.schema.json")
    data = _load_yaml(FIX / "stage-state.sample.yaml")
    jsonschema.validate(data, schema)
    bad = {"decisions": [{"stage": "x", "flag": "far"}]}   # missing subject/decision/decided_at
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_verified_pois_booking_lead_time_days():   # TW-030
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_verified(booking={"required": True, "lead_time": "1 week", "lead_time_days": 7})
    jsonschema.validate(doc, schema)   # must not raise


# ---- Photo-enrichment: gmaps_place_id + photo + attribution + side-file (PR1) ----

def test_poi_gmaps_place_id_accepted():   # PR1
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_verified(gmaps_place_id="ChIJN1t_tDeuEmsRUsoyG83frY4")
    jsonschema.validate(doc, schema)   # must not raise

def test_poi_photo_with_attribution_valid():   # PR1
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_verified(
        photo={"data": "data:image/jpeg;base64,/9j/AAAA", "width": 640, "height": 480,
               "thumb": {"data": "data:image/jpeg;base64,/9j/BBBB", "width": 160, "height": 120}},
        photo_attribution={"author": "Jane Doe", "license": "CC-BY-SA",
                           "source_url": "https://commons.wikimedia.org/wiki/File:X.jpg"},
        photo_source="wikimedia",
    )
    jsonschema.validate(doc, schema)   # must not raise

def test_poi_photo_https_url_valid():   # PR1
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_verified(
        photo={"url": "https://upload.wikimedia.org/x.jpg"},
        photo_attribution={"author": "A", "license": "CC0", "source_url": "https://a.example"},
        photo_source="openverse",
    )
    jsonschema.validate(doc, schema)   # must not raise

def test_poi_photo_without_attribution_rejected():   # PR1 — conditional photo => attribution
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_verified(photo={"data": "data:image/png;base64,iVBORw0AAA"})
    with pytest.raises(jsonschema.ValidationError) as exc:
        jsonschema.validate(doc, schema)
    # Must fail for the RIGHT reason (missing photo_attribution), NOT merely because
    # `photo` is an un-whitelisted key — that would be a surprise-green masking the bug.
    assert "photo_attribution" in str(exc.value)

def test_poi_photo_attribution_requires_author_license_source():   # PR1
    schema = _load_schema("verified-pois.schema.json")
    cases = [
        {"license": "CC0", "source_url": "https://a.example"},                 # no author
        {"author": "A", "source_url": "https://a.example"},                    # no license
        {"author": "A", "license": "CC0"},                                     # no source_url
        {"author": "", "license": "CC0", "source_url": "https://a.example"},   # empty author
    ]
    for bad_attr in cases:
        doc = _vp_verified(photo={"url": "https://upload.wikimedia.org/x.jpg"},
                           photo_attribution=bad_attr, photo_source="wikimedia")
        with pytest.raises(jsonschema.ValidationError) as exc:
            jsonschema.validate(doc, schema)
        # right reason: a constraint INSIDE photo_attribution, not the POI-level seal
        assert exc.value.validator in ("required", "minLength")

def test_poi_photo_data_must_be_image():   # PR1 — F1 scheme guard at schema layer
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_verified(
        photo={"data": "data:text/html;base64,PHNjcmlwdD4="},
        photo_attribution={"author": "A", "license": "CC0", "source_url": "https://a.example"},
        photo_source="wikimedia",
    )
    with pytest.raises(jsonschema.ValidationError) as exc:
        jsonschema.validate(doc, schema)
    assert exc.value.validator == "pattern"   # right reason, not additionalProperties

def test_poi_photo_url_must_be_https():   # PR1 — F1 scheme guard at schema layer
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_verified(
        photo={"url": "http://insecure.example/x.jpg"},
        photo_attribution={"author": "A", "license": "CC0", "source_url": "https://a.example"},
        photo_source="wikimedia",
    )
    with pytest.raises(jsonschema.ValidationError) as exc:
        jsonschema.validate(doc, schema)
    assert exc.value.validator == "pattern"

def test_poi_photo_source_enum_rejects_unknown():   # PR1
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_verified(
        photo={"url": "https://upload.wikimedia.org/x.jpg"},
        photo_attribution={"author": "A", "license": "CC0", "source_url": "https://a.example"},
        photo_source="flickr",
    )
    with pytest.raises(jsonschema.ValidationError) as exc:
        jsonschema.validate(doc, schema)
    assert exc.value.validator == "enum"   # right reason, not additionalProperties

def test_canonical_yaml_still_rejects_photo_typo_key():   # PR1 — seal stays honest
    schema = _load_schema("verified-pois.schema.json")
    doc = _vp_verified(photoo={"url": "https://x.example"})   # typo of photo
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)


# ---- Photo side-file schema (verified-pois-media.schema.json) (PR1) ----

def _media_doc(**entry_over):
    entry = {
        "photo": {"data": "data:image/jpeg;base64,/9j/AAAA", "width": 640, "height": 480},
        "photo_attribution": {"author": "Jane Doe", "license": "CC-BY-SA",
                              "source_url": "https://commons.wikimedia.org/wiki/File:X.jpg"},
        "photo_source": "wikimedia",
    }
    entry.update(entry_over)
    return {"media": {"poi-001": entry}}

def test_media_sidefile_sample_valid():   # PR1
    schema = _load_schema("verified-pois-media.schema.json")
    data = _load_yaml(FIX / "verified-pois-media.sample.yaml")
    jsonschema.validate(data, schema)   # must not raise

def test_media_sidefile_entry_valid():   # PR1
    schema = _load_schema("verified-pois-media.schema.json")
    jsonschema.validate(_media_doc(), schema)   # must not raise

def test_media_sidefile_entry_requires_attribution():   # PR1
    schema = _load_schema("verified-pois-media.schema.json")
    bad = _media_doc()
    del bad["media"]["poi-001"]["photo_attribution"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_media_sidefile_entry_requires_photo_source():   # PR1
    schema = _load_schema("verified-pois-media.schema.json")
    bad = _media_doc()
    del bad["media"]["poi-001"]["photo_source"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_media_sidefile_unknown_photo_source_rejected():   # PR1
    schema = _load_schema("verified-pois-media.schema.json")
    bad = _media_doc(photo_source="flickr")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)

def test_media_sidefile_rejects_unknown_top_key():   # PR1 — own seal (matrix OOS-4)
    schema = _load_schema("verified-pois-media.schema.json")
    bad = _media_doc()
    bad["unexpected"] = 1
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)
