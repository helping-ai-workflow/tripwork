import json
from scripts.geocode_cache import cache_key, cache_get, cache_put, load_cache, save_cache


def test_cache_key_normalizes():
    assert cache_key("渡月橋", "Arashiyama", "Japan") == "渡月橋|arashiyama|japan"
    assert cache_key(" Fergburger ") == "fergburger||"
    assert cache_key("X", None, None) == "x||"


def test_cache_get_absent_vs_present():
    cache = {}
    assert cache_get(cache, "k") == (False, None)
    cache_put(cache, "k", {"lat": 1.0, "lng": 2.0})
    assert cache_get(cache, "k") == (True, {"lat": 1.0, "lng": 2.0})


def test_cache_get_negative_hit_is_a_hit():
    # a cached miss (None) must be a HIT, not an absent key
    cache = {}
    cache_put(cache, "k", None)
    assert cache_get(cache, "k") == (True, None)


def test_load_cache_missing_file_is_empty(tmp_path):
    assert load_cache(str(tmp_path / "nope.json")) == {}


def test_save_then_load_round_trip(tmp_path):
    path = str(tmp_path / "sub" / "geocode.json")   # parent dir does not exist yet
    save_cache(path, {"渡月橋||japan": {"lat": 35.0, "lng": 135.6, "source": "nominatim"}})
    assert load_cache(path) == {"渡月橋||japan": {"lat": 35.0, "lng": 135.6, "source": "nominatim"}}


def test_save_creates_parent_dirs(tmp_path):
    path = str(tmp_path / "a" / "b" / "geocode.json")
    save_cache(path, {})
    assert load_cache(path) == {}
