# tests/test_verify_geocode_discipline.py
"""D1 dogfood defects:
  (a) geocode key normalisation: lon/long -> lng
  (b) name_local == district rejection (cluster_fallback town-name bug)
"""
from scripts.verify import normalize_and_validate_poi


def test_geocode_lon_key_normalised_to_lng():
    """poi with legacy 'lon' key -> out geocode has 'lng', no 'lon'; reason None."""
    poi = {
        "name_local": "洞爺湖ウィンザーホテル",
        "district": "洞爺湖温泉",
        "geocode": {"lat": 43.0, "lon": 141.3},
    }
    out, reason = normalize_and_validate_poi(poi)
    assert out["geocode"]["lng"] == 141.3, "lng must be set"
    assert "lon" not in out["geocode"], "legacy 'lon' key must be removed"
    assert reason is None


def test_name_local_equals_district_rejected():
    """poi name_local == district -> reason is not None and mentions name_local."""
    poi = {
        "name_local": "洞爺湖温泉",
        "district": "洞爺湖温泉",
        "geocode": {"lat": 42.5, "lng": 140.7},
    }
    out, reason = normalize_and_validate_poi(poi)
    assert reason is not None, "should produce a rejection reason"
    assert "洞爺湖温泉" in reason or "name_local" in reason


def test_distinct_name_local_and_district_passes():
    """poi with distinct name_local and district -> reason None."""
    poi = {
        "name_local": "洞爺湖ウィンザーホテル",
        "district": "洞爺湖温泉",
        "geocode": {"lat": 42.5, "lng": 140.7},
    }
    out, reason = normalize_and_validate_poi(poi)
    assert reason is None


def test_no_geocode_key_passes_without_error():
    """poi with no geocode field -> normalize_and_validate_poi does not crash; reason None."""
    poi = {
        "name_local": "某餐廳",
        "district": "札幌",
    }
    out, reason = normalize_and_validate_poi(poi)
    assert reason is None


def test_geocode_none_passes_without_error():
    """poi with geocode: None -> no crash; reason None."""
    poi = {
        "name_local": "某餐廳",
        "district": "札幌",
        "geocode": None,
    }
    out, reason = normalize_and_validate_poi(poi)
    assert reason is None


def test_original_poi_not_mutated():
    """normalize_and_validate_poi must not mutate the input poi dict."""
    poi = {
        "name_local": "洞爺湖ウィンザーホテル",
        "district": "洞爺湖温泉",
        "geocode": {"lat": 43.0, "lon": 141.3},
    }
    import copy
    original = copy.deepcopy(poi)
    normalize_and_validate_poi(poi)
    assert poi == original


# --- verify_poi wiring tests ---

from scripts.verify import verify_poi


def _cand(sources, langs):
    def _u(s):
        return s if str(s).startswith("http") else f"https://{s}.example"
    return {"id": "x", "sources": [{"url": _u(u), "lang": l} for u, l in zip(sources, langs)]}


def test_verify_poi_name_local_equals_district_returns_rejected():
    """verify_poi: name_local==district -> status=='rejected', reason mentions name_local."""
    poi = _cand(["a", "b"], ["ja", "zh"])
    poi["name_local"] = "洞爺湖温泉"
    poi["district"] = "洞爺湖温泉"
    poi["geocode"] = {"lat": 42.5, "lng": 140.7}
    normalised, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True)
    assert status == "rejected"
    assert "洞爺湖温泉" in note or "name_local" in note


def test_verify_poi_geocode_key_normalised_and_clean_passes_through():
    """verify_poi: lon key normalised; clean poi proceeds to classify gates."""
    poi = _cand(["a", "b"], ["ja", "en"])
    poi["name_local"] = "洞爺湖ウィンザーホテル"
    poi["district"] = "洞爺湖温泉"
    poi["geocode"] = {"lat": 42.5, "lon": 140.7}
    poi["business_status"] = "OPERATIONAL"   # P1: Gate 0 needs a sourced operating signal
    normalised, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True)
    assert status == "verified"
    assert normalised["geocode"]["lng"] == 140.7
    assert "lon" not in normalised["geocode"]
