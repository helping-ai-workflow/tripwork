"""v2.1.0 §4 (D6): a lookup result counts only when its name matches the venue, and a
bare-name hit only inside the claimed district -- otherwise it is no hit, next tier.
Made-up venues; Nominatim is a fake that records every query."""
import pytest

from scripts import geocode as G
from scripts.geocode_cache import cache_key, cache_put

HERE = (25.10, 121.50)                     # the claimed district's centre
REGION = (*HERE, 5.0)
FAR = (25.50, 121.90)                      # ~58 km away


class _Resp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def _hit(name, at=HERE):
    return {"lat": str(at[0]), "lon": str(at[1]), "display_name": f"{name}, 示意區, 臺北市, 臺灣"}


@pytest.fixture
def fake(monkeypatch):
    """fake(answer) -> list of every issued params; answer(params) gives the JSON list."""
    def install(answer):
        seen = []

        def get(url, params=None, headers=None, timeout=None):
            seen.append(dict(params or {}))
            return _Resp(answer(dict(params or {})))
        monkeypatch.setattr(G.requests, "get", get)
        return seen
    return install


def _tier(p):
    """Which resolve_place tier issued `p` (country lookups excluded by the caller)."""
    if "street" in p:
        return 1
    q = p.get("q", "")
    return {"示意食堂 示意區 TW": 2, "示意食堂": 3, "Shiyi Diner 示意區 TW": 4, "Shiyi Diner": 5}.get(q)


def test_namesake_far_away_rejected_on_bare_name_tier(fake):
    fake(lambda p: [_hit("示意食堂", FAR)] if _tier(p) == 3 else [])
    assert G.resolve_place("示意食堂", district="示意區", country="TW", region=REGION) == (None, None)


def test_name_mismatch_rejected_on_every_tier(fake):
    seen = fake(lambda p: [_hit("別家小館")] if _tier(p) == 1 else
                [_hit("示意食堂")] if _tier(p) == 2 else [])
    r, source = G.resolve_place("示意食堂", district="示意區", country="TW", region=REGION)
    assert source == "nominatim" and r.display_name.startswith("示意食堂")
    assert [_tier(p) for p in seen] == [1, 2]


def test_second_of_five_results_accepted(fake):
    seen = fake(lambda p: [_hit("別家小館"), _hit("示意食堂")] if _tier(p) == 1 else [])
    r, source = G.resolve_place("示意食堂", district="示意區", country="TW", region=REGION)
    assert source == "nominatim_structured" and r.display_name.startswith("示意食堂")
    assert seen[0]["limit"] == 5 and len(seen) == 1


def test_roman_name_matches_roman_tier(fake):
    fake(lambda p: [_hit("Shiyi Diner")] if _tier(p) == 4 else [])
    r, _ = G.resolve_place("示意食堂", district="示意區", country="TW", name_roman="Shiyi Diner",
                           region=REGION)
    assert r is not None and r.display_name.startswith("Shiyi Diner")


def test_no_region_rejects_bare_name_tiers(fake):
    fake(lambda p: [_hit("示意食堂")] if _tier(p) in (3, 5) else [])
    assert G.resolve_place("示意食堂", district="示意區", country="TW", name_roman="Shiyi Diner") == (None, None)


def test_area_lookup_skips_acceptance(fake):
    fake(lambda p: [_hit("另一個名字", FAR)] if p.get("featureType") == "settlement" else [])
    r, _ = G.resolve_place("示意區", country="TW", area=True)
    assert r is not None


def test_precise_tier_out_of_region_still_returned(fake):
    fake(lambda p: [_hit("示意食堂", FAR)] if _tier(p) == 1 else [])
    r, source = G.resolve_place("示意食堂", district="示意區", country="TW", region=REGION)
    assert source == "nominatim_structured" and (r.lat, r.lng) == FAR     # Gate 3b says conflicting


def test_old_cache_requeries_once_then_stable(fake):
    cache = {}
    cache_put(cache, cache_key("示意食堂", "示意區", "TW"),
              {"lat": FAR[0], "lng": FAR[1], "display_name": "示意食堂, 他區", "source": "nominatim"})
    seen = fake(lambda p: [_hit("示意食堂")] if _tier(p) == 1 else [])
    r, _ = G.resolve_place("示意食堂", district="示意區", country="TW", cache=cache, region=REGION)
    assert (r.lat, r.lng) == HERE and len(seen) == 1
    seen.clear()
    r, _ = G.resolve_place("示意食堂", district="示意區", country="TW", cache=cache, region=REGION)
    assert (r.lat, r.lng) == HERE and seen == []


def test_old_cached_miss_requeries_once_then_stable(fake):
    cache = {}
    cache_put(cache, cache_key("示意食堂", "示意區", "TW"), None)
    seen = fake(lambda p: [])
    assert G.resolve_place("示意食堂", district="示意區", country="TW", cache=cache, region=REGION) == (None, None)
    assert seen
    seen.clear()
    assert G.resolve_place("示意食堂", district="示意區", country="TW", cache=cache, region=REGION) == (None, None)
    assert seen == []


def test_cached_wrong_namesake_is_requeried(fake):
    cache = {}
    cache_put(cache, cache_key("示意食堂", "示意區", "TW"),
              {"v": 2, "lat": FAR[0], "lng": FAR[1], "display_name": "示意食堂, 他區",
               "source": "nominatim", "tier": 3})      # a bare-name hit an earlier run accepted
    seen = fake(lambda p: [_hit("示意食堂", FAR)] if _tier(p) == 3 else [])
    assert G.resolve_place("示意食堂", district="示意區", country="TW", cache=cache, region=REGION) == (None, None)
    assert seen, "a cached bare-name hit outside the district is looked up again"


def test_accept_is_the_one_rule():
    r = G.GeocodeResult(*FAR, "示意食堂, 他區")
    assert G.accept(r, 1, "示意食堂", None, REGION)
    assert not G.accept(r, 3, "示意食堂", None, REGION)
    assert not G.accept(G.GeocodeResult(*HERE, "別家"), 2, "示意食堂", None, REGION)


def test_verify_passes_the_district_centre_as_region(monkeypatch):
    from scripts import source_verify_run as svr
    monkeypatch.setattr(svr.time, "sleep", lambda *_: None)
    monkeypatch.setattr(svr, "_district_centroid", lambda *a, **kw: HERE)
    seen = {}

    def fake(name, district=None, country=None, timeout=10, cache=None, name_roman=None,
             pace=None, area=False, region=None):
        seen["region"] = region
        return None, None
    monkeypatch.setattr(svr, "resolve_place", fake)
    svr._geocode_candidate({"name_local": "示意食堂", "claimed_district": "示意區"}, "TW", {}, False, {}, 5.0)
    assert seen["region"] == (*HERE, 5.0)


def test_a_branch_inside_the_district_beats_one_elsewhere(fake):
    """Final review: a chain's two branches in one result list -- the one inside the claimed
    district wins over an earlier one 58 km off."""
    fake(lambda p: [_hit("示意食堂", FAR), _hit("示意食堂")] if _tier(p) == 1 else [])
    r, source = G.resolve_place("示意食堂", district="示意區", country="TW", region=REGION)
    assert source == "nominatim_structured" and (r.lat, r.lng) == HERE


def test_without_an_inside_branch_the_first_match_stands(fake):
    fake(lambda p: [_hit("別家", HERE), _hit("示意食堂", FAR)] if _tier(p) == 1 else [])
    r, _ = G.resolve_place("示意食堂", district="示意區", country="TW", region=REGION)
    assert (r.lat, r.lng) == FAR                                            # may have moved: Gate 3b asks
