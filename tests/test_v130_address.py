"""v1.3.0: the venue's sourced street address (address_local) as the check on its name
lookup. Nominatim resolves a Japanese address down to the 丁目, never the block number
(probed 2026-10-05 on public addresses), so the address gives a reference point a few
hundred metres wide. Examples are public places or made up."""
import pytest

from scripts import geocode as G
from scripts.geocode_cache import cache_key


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


def _nominatim(answers):
    seen = []

    def get(url, params=None, headers=None, timeout=None):
        seen.append(dict(params or {}))
        return _Resp(answers(params or {}))
    return get, seen


JP = [{"lat": "36", "lon": "138", "display_name": "日本", "address": {"country_code": "jp"}}]


# --- the strings an address is tried as -----------------------------------------------

@pytest.mark.parametrize("address,want", [
    ("東京都台東区浅草2-3-1 浅草ビル5F", ["東京都台東区浅草2-3-1", "東京都台東区浅草2丁目", "東京都台東区浅草"]),
    ("東京都台東区浅草２－３－１", ["東京都台東区浅草2-3-1", "東京都台東区浅草2丁目", "東京都台東区浅草"]),
    ("東京都千代田区丸の内二丁目7番2号", ["東京都千代田区丸の内二丁目7番2号", "東京都千代田区丸の内二丁目", "東京都千代田区丸の内"]),
    ("北海道函館市元町1220-5", ["北海道函館市元町1220-5", "北海道函館市元町"]),          # 1220: a 番地, not a 丁目
    ("北海道小樽市堺町7-26", ["北海道小樽市堺町7-26", "北海道小樽市堺町7丁目", "北海道小樽市堺町"]),
])
def test_japanese_address_variants(address, want):
    assert G.address_variants(address, "jp") == want


def test_other_addresses_try_the_whole_then_without_the_number():
    assert G.address_variants("嘉義市西區民族路100號2樓", "tw") == ["嘉義市西區民族路100號2樓", "嘉義市西區民族路"]
    assert G.address_variants("12 Example Street, Queenstown", "nz") == ["12 Example Street, Queenstown"]
    assert G.address_variants("  ", "jp") == []


# --- the cache key kinds ---------------------------------------------------------------

def test_cache_key_kinds_are_apart_and_area_still_works():
    assert cache_key("堺町", None, "日本", area=True) == cache_key("堺町", None, "日本", kind="area")
    assert len({cache_key("堺町", None, "日本"), cache_key("堺町", None, "日本", kind="area"),
                cache_key("堺町", None, "日本", kind="address")}) == 3


# --- the reference point ---------------------------------------------------------------

def test_the_first_variant_that_resolves_is_the_point(monkeypatch):
    def answers(p):
        if p.get("featureType") == "country":
            return JP
        if p.get("q") == "東京都台東区浅草2丁目":
            return [{"lat": "35.715", "lon": "139.7957", "display_name": "浅草二丁目, 浅草, 台東区"}]
        return []
    get, seen = _nominatim(answers)
    monkeypatch.setattr(G.requests, "get", get)
    r, variant = G.address_point("東京都台東区浅草2-3-1 浅草ビル5F", country="日本")
    assert (r.lat, variant) == (35.715, "東京都台東区浅草2丁目")
    asked = [p["q"] for p in seen if p.get("featureType") != "country"]
    assert asked == ["東京都台東区浅草2-3-1", "東京都台東区浅草2丁目"]          # the town is not asked
    assert all(p.get("countrycodes") == "jp" for p in seen if p.get("featureType") != "country")


def test_the_point_is_cached_per_variant_and_paced(monkeypatch):
    get, seen = _nominatim(lambda p: JP if p.get("featureType") == "country" else
                           ([{"lat": "43.19", "lon": "141.0", "display_name": "堺町"}] if p.get("q") == "北海道小樽市堺町" else []))
    monkeypatch.setattr(G.requests, "get", get)
    cache, paced = {}, []
    r, v = G.address_point("北海道小樽市堺町7-26", country="日本", cache=cache, pace=lambda: paced.append(1))
    assert v == "北海道小樽市堺町" and len(paced) == len(seen) == 4      # country + three variants
    seen.clear()
    r2, v2 = G.address_point("北海道小樽市堺町7-26", country="日本", cache=cache, pace=lambda: paced.append(1))
    assert (r2.lat, v2) == (r.lat, v) and seen == []                     # every variant, misses too, cached


def test_no_variant_resolves(monkeypatch):
    get, _ = _nominatim(lambda p: JP if p.get("featureType") == "country" else [])
    monkeypatch.setattr(G.requests, "get", get)
    assert G.address_point("北海道小樽市堺町7-26", country="日本") == (None, None)
    assert G.address_point("", country="日本") == (None, None)
