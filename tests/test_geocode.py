import pytest
from scripts.geocode import geocode, GeocodeResult, in_region

class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
    def json(self):
        return self._payload
    def raise_for_status(self):
        if self.status_code != 200:
            raise RuntimeError("http error")

def test_geocode_success(mocker):
    mocker.patch("scripts.geocode.requests.get",
                 return_value=_FakeResp([{"lat": "37.5636", "lon": "126.9869",
                                          "display_name": "Myeongdong, Seoul"}]))
    r = geocode("오다리집 명동")
    assert isinstance(r, GeocodeResult)
    assert r.lat == pytest.approx(37.5636)
    assert r.lng == pytest.approx(126.9869)

def test_geocode_no_results_returns_none(mocker):
    mocker.patch("scripts.geocode.requests.get", return_value=_FakeResp([]))
    assert geocode("nonexistent place xyz") is None

def test_in_region_true():
    # point near 명동, region centroid near 명동, within 5km
    assert in_region(37.5636, 126.9869, 37.5600, 126.9850, radius_km=5.0) is True

def test_in_region_false_cross_district():
    # 강남 point vs 잠실 region centroid -> far apart, outside radius
    assert in_region(37.4979, 127.0276, 37.5133, 127.1000, radius_km=3.0) is False

def test_in_region_radius_is_configurable():
    # a point ~4km away: inside default 5km, outside a tight 2km
    from scripts.geocode import in_region
    assert in_region(37.5400, 127.0000, 37.5040, 127.0000, radius_km=5.0) is True
    assert in_region(37.5400, 127.0000, 37.5040, 127.0000, radius_km=2.0) is False

def test_resolve_place_uses_structured_first(mocker):
    from scripts.geocode import resolve_place
    mocker.patch("scripts.geocode.requests.get",
                 return_value=_FakeResp([{"lat": "1.0", "lon": "2.0", "display_name": "X"}]))
    r, source = resolve_place("The Godley Hotel", district="Tekapo", country="New Zealand")
    assert r.lat == pytest.approx(1.0)
    assert source == "nominatim_structured"

def test_resolve_place_falls_back_to_freetext(mocker):
    from scripts.geocode import resolve_place
    mocker.patch("scripts.geocode.requests.get",
                 side_effect=[_FakeResp([]),
                              _FakeResp([{"lat": "3.0", "lon": "4.0", "display_name": "Y"}])])
    r, source = resolve_place("Arran Motel", district="Tekapo", country="New Zealand")
    assert r.lng == pytest.approx(4.0)
    assert source == "nominatim"

def test_resolve_place_none_when_all_miss(mocker):
    from scripts.geocode import resolve_place
    # P3: resolve_place now tries structured + several free-text attempts; every
    # request must miss for the overall result to be None.
    mocker.patch("scripts.geocode.requests.get", return_value=_FakeResp([]))
    r, source = resolve_place("nowhere", district="X", country="Y")
    assert r is None and source is None

def test_cluster_centroid_mean():
    from scripts.geocode import cluster_centroid
    assert cluster_centroid([(0.0, 0.0), (2.0, 4.0)]) == (1.0, 2.0)
    assert cluster_centroid([]) is None

def test_resolve_place_cache_hit_skips_network(mocker):
    from scripts.geocode import resolve_place
    from scripts.geocode_cache import cache_key
    m = mocker.patch("scripts.geocode.requests.get")  # must NOT be called
    key = cache_key("The Godley Hotel", "Tekapo", "New Zealand")
    cache = {key: {"lat": -44.0, "lng": 170.5, "display_name": "Godley", "source": "nominatim"}}
    r, source = resolve_place("The Godley Hotel", district="Tekapo", country="New Zealand", cache=cache)
    assert r.lat == pytest.approx(-44.0) and source == "nominatim"
    assert m.call_count == 0

def test_resolve_place_cached_miss_skips_network(mocker):
    from scripts.geocode import resolve_place
    from scripts.geocode_cache import cache_key
    m = mocker.patch("scripts.geocode.requests.get")  # must NOT be called
    key = cache_key("Nowhere Motel", "Tekapo", "New Zealand")
    cache = {key: None}                                # cached miss
    r, source = resolve_place("Nowhere Motel", district="Tekapo", country="New Zealand", cache=cache)
    assert r is None and source is None
    assert m.call_count == 0

def test_resolve_place_populates_cache_on_hit(mocker):
    from scripts.geocode import resolve_place
    from scripts.geocode_cache import cache_key
    mocker.patch("scripts.geocode.requests.get",
                 return_value=_FakeResp([{"lat": "1.0", "lon": "2.0", "display_name": "X"}]))
    cache = {}
    r, source = resolve_place("Somewhere", district="D", country="C", cache=cache)
    assert source == "nominatim_structured"
    key = cache_key("Somewhere", "D", "C")
    assert cache[key]["lat"] == 1.0 and cache[key]["source"] == "nominatim_structured"

def test_resolve_place_populates_cache_on_miss(mocker):
    from scripts.geocode import resolve_place
    from scripts.geocode_cache import cache_key
    mocker.patch("scripts.geocode.requests.get",
                 return_value=_FakeResp([]))  # structured + all free-text attempts miss (P3)
    cache = {}
    r, source = resolve_place("Ghost Inn", district="D", country="C", cache=cache)
    assert r is None and source is None
    assert cache[cache_key("Ghost Inn", "D", "C")] is None    # negative cached


def test_resolve_place_rejects_empty_name():   # TW-045
    import pytest
    from scripts.geocode import resolve_place
    with pytest.raises(ValueError):
        resolve_place("", district="Gangnam")
    with pytest.raises(ValueError):
        resolve_place(None)


# --- normalize_geocode_keys (D1 dogfood fix) ---

def test_normalize_lon_to_lng():
    from scripts.geocode import normalize_geocode_keys
    result = normalize_geocode_keys({"lat": 42.0, "lon": 140.0})
    assert result == {"lat": 42.0, "lng": 140.0}

def test_normalize_long_to_lng():
    from scripts.geocode import normalize_geocode_keys
    result = normalize_geocode_keys({"lat": 42.0, "long": 140.0})
    assert result == {"lat": 42.0, "lng": 140.0}

def test_normalize_lng_passthrough():
    from scripts.geocode import normalize_geocode_keys
    result = normalize_geocode_keys({"lat": 42.0, "lng": 140.0})
    assert result == {"lat": 42.0, "lng": 140.0}

def test_normalize_conflict_raises_value_error():
    from scripts.geocode import normalize_geocode_keys
    with pytest.raises(ValueError):
        normalize_geocode_keys({"lat": 42.0, "lon": 140.0, "lng": 141.0})

def test_normalize_lon_lng_agree_collapses():
    from scripts.geocode import normalize_geocode_keys
    result = normalize_geocode_keys({"lat": 42.0, "lon": 140.0, "lng": 140.0})
    assert result == {"lat": 42.0, "lng": 140.0}

def test_normalize_none_returns_none():
    from scripts.geocode import normalize_geocode_keys
    assert normalize_geocode_keys(None) is None

def test_normalize_lon_long_disagree_raises():
    """lon and long both present but different values — must raise ValueError (D1)."""
    from scripts.geocode import normalize_geocode_keys
    with pytest.raises(ValueError):
        normalize_geocode_keys({"lat": 42.0, "lon": 140.0, "long": 141.0})

def test_normalize_lon_long_agree_collapses():
    """lon and long both present with same value — must collapse to lng cleanly."""
    from scripts.geocode import normalize_geocode_keys
    result = normalize_geocode_keys({"lat": 42.0, "lon": 140.0, "long": 140.0})
    assert result == {"lat": 42.0, "lng": 140.0}
