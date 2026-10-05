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


# --- Task 2: an address point is a recorded, approximate geocode source ---------------

def _src(lang, url):
    return {"url": url, "lang": lang}


def test_schemas_accept_an_address_point():
    import json
    import pathlib
    import jsonschema
    root = pathlib.Path(__file__).resolve().parent.parent / "schemas"
    for name in ("verified-pois.schema.json", "accommodations.schema.json"):
        text = (root / name).read_text(encoding="utf-8")
        assert '"nominatim_address"' in text, name
    schema = json.loads((root / "verified-pois.schema.json").read_text(encoding="utf-8"))
    geo = schema["properties"]["pois"]["items"]["properties"]["geocode"]
    jsonschema.validate({"lat": 43.19, "lng": 141.0, "geocode_source": "nominatim_address"}, geo)


def test_verify_accepts_an_address_point():
    from scripts.verify import classify_candidate
    cand = {"sources": [_src("ja", "https://a.example/x"), _src("zh-TW", "https://b.example/y")]}
    status, note = classify_candidate(cand, True, True, local_lang="ja", geocode_source="nominatim_address")
    assert status == "verified", note


def test_an_address_point_is_disclosed_like_a_centroid():
    from scripts.render.centroid import centroid_items, centroid_note
    poi = {"id": "cafe", "name_display": "示意咖啡", "geocode": {"lat": 43.19, "lng": 141.0,
                                                               "geocode_source": "nominatim_address"}}
    itin = {"days": [{"rows": [{"poi_id": "cafe"}]}]}
    assert centroid_items(itin, {"cafe": poi}) == [poi]
    assert "地址" in centroid_note(poi) and "不是它本身的位置" in centroid_note(poi)
    cpoi = dict(poi, geocode=dict(poi["geocode"], geocode_source="cluster_fallback"))
    assert "所在區域的中心點" in centroid_note(cpoi)                       # unchanged


def test_rederive_does_not_judge_an_address_point_by_the_straight_line():
    from scripts.rederive import _centroid_only
    by_id = {"cafe": {"geocode": {"lat": 1, "lng": 2, "geocode_source": "nominatim_address"}},
             "shrine": {"geocode": {"lat": 1, "lng": 2, "geocode_source": "nominatim"}}}
    assert _centroid_only(by_id, "cafe") and not _centroid_only(by_id, "shrine")


# --- Task 3: source-verify -- the name first, the sourced address as its check -------

HAKODATE = (41.7958, 140.7538)                 # 五稜郭町 (the address point)
FAR = (36.124, 137.824)                        # a namesake in another prefecture
NEAR = (41.7969, 140.7570)                     # ~0.3 km from the address point


def _run(monkeypatch, name_hit, address_hit, address="北海道函館市五稜郭町43-9", centroid=HAKODATE):
    from scripts import source_verify_run as svr
    calls = {"address": 0}

    def resolve(name, district, country, cache, name_roman=None, area=False):
        return (G.GeocodeResult(*name_hit, "示意咖啡, 某町"), "nominatim") if name_hit else (None, None)

    def addr(a, country, cache):
        calls["address"] += 1
        return (G.GeocodeResult(*address_hit, "五稜郭町, 函館市"), "北海道函館市五稜郭町") if address_hit else (None, None)
    monkeypatch.setattr(svr, "_rate_limited_resolve", resolve)
    monkeypatch.setattr(svr, "_rate_limited_address", addr)
    monkeypatch.setattr(svr, "_district_centroid", lambda *a, **k: centroid)
    cand = {"id": "cafe", "name_local": "示意カフェ", "claimed_district": "函館市五稜郭町"}
    if address:
        cand["address_local"] = address
    out = svr._geocode_candidate(cand, "日本", {}, False, {}, 5.0)
    return out, calls


def test_a_namesake_far_from_the_address_gives_way_to_the_address(monkeypatch):
    from scripts.verify import NO_RESOLVED_NAME
    (geo, geocoded, inside, resolved, checked), _ = _run(monkeypatch, FAR, HAKODATE)
    assert (geo["lat"], geo["lng"]) == HAKODATE and geo["geocode_source"] == "nominatim_address"
    assert geocoded and inside and checked and resolved is NO_RESOLVED_NAME
    assert geo["query"]["address"] == "北海道函館市五稜郭町43-9"


def test_a_name_hit_near_the_address_keeps_its_exact_point(monkeypatch):
    (geo, _, inside, resolved, _), calls = _run(monkeypatch, NEAR, HAKODATE)
    assert (geo["lat"], geo["lng"]) == NEAR and geo["geocode_source"] == "nominatim" and inside
    assert resolved == "示意咖啡, 某町" and calls["address"] == 1


def test_no_name_hit_takes_the_address_point(monkeypatch):
    (geo, geocoded, *_), _ = _run(monkeypatch, None, HAKODATE)
    assert geocoded and geo["geocode_source"] == "nominatim_address"


def test_without_an_address_nothing_changes(monkeypatch):
    (geo, *_), calls = _run(monkeypatch, FAR, HAKODATE, address=None)
    assert (geo["lat"], geo["lng"]) == FAR and geo["geocode_source"] == "nominatim" and calls["address"] == 0
    assert "address" not in geo["query"]


def test_an_address_point_outside_the_district_is_not_in_region(monkeypatch):
    (geo, _, inside, _, checked), _ = _run(monkeypatch, None, HAKODATE, centroid=FAR)
    assert geo["geocode_source"] == "nominatim_address" and checked and not inside


def test_neither_falls_back_to_the_district_centroid(monkeypatch):
    (geo, *_), _ = _run(monkeypatch, None, None)
    assert geo["geocode_source"] == "cluster_fallback"


# --- Task 4: one rule for venues and hotels -------------------------------------------

def test_pick_point_keeps_a_near_name_hit_and_drops_a_namesake():
    near, far, ref = G.GeocodeResult(*NEAR, "n"), G.GeocodeResult(*FAR, "f"), G.GeocodeResult(*HAKODATE, "a")
    assert G.pick_point(near, "nominatim", ref) == (near, "nominatim")
    assert G.pick_point(far, "nominatim", ref) == (ref, "nominatim_address")
    assert G.pick_point(None, None, ref) == (ref, "nominatim_address")
    assert G.pick_point(far, "nominatim", None) == (far, "nominatim")
    assert G.pick_point(None, None, None) == (None, None)


def test_the_lodging_skill_uses_the_same_rule():
    import pathlib
    text = (pathlib.Path(__file__).resolve().parent.parent / "skills" / "accommodation-research" / "SKILL.md").read_text(encoding="utf-8")
    geo = text[text.index("**Geocode"):]
    geo = geo[:geo.index("\n- **")] if "\n- **" in geo else geo
    assert "address_point" in geo and "pick_point" in geo and "nominatim_address" in geo
    assert geo.index("pick_point") < geo.index("cluster_fallback")       # the centroid only after both miss


# --- Task 5: local + Taiwan traveller sources -------------------------------------------

def _skill(name):
    import pathlib
    return (pathlib.Path(__file__).resolve().parent.parent / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def test_research_runs_a_local_and_a_taiwan_track():
    text = _skill("destination-research")
    assert "local track" in text and "Taiwan track" in text and "zh-TW" in text
    assert "Taiwanese travellers" in text


def test_source_verify_says_a_taiwan_page_is_one_source():
    gate1 = _skill("source-verify").split("1. **Multi-source** (Gate 1)")[1].split("\n2. ")[0]
    assert "zh-TW" in gate1 and "never replaces" in gate1 and "sub-domain" in gate1


def test_two_taiwan_pages_without_a_local_source_are_not_enough():
    from scripts.verify import classify_candidate
    cand = {"sources": [_src("zh-TW", "https://a.example/trip"), _src("zh-TW", "https://b.example/trip")]}
    status, note = classify_candidate(cand, True, True, local_lang="ja", geocode_source="nominatim")
    assert status == "unverified" and "local language" in note


def test_a_taiwan_page_and_a_local_source_pass():
    from scripts.verify import classify_candidate
    cand = {"sources": [_src("zh-TW", "https://a.example/trip"), _src("ja", "https://shop.example.jp/")]}
    assert classify_candidate(cand, True, True, local_lang="ja", geocode_source="nominatim")[0] == "verified"


def test_two_travellers_on_one_platform_are_two_sources():
    from scripts.verify import classify_candidate
    cand = {"sources": [_src("zh-TW", "https://amy.blog.example/okinawa"), _src("ja", "https://bob.blog.example/x")]}
    assert classify_candidate(cand, True, True, local_lang="ja", geocode_source="nominatim")[0] == "verified"


def test_source_verify_says_the_address_checks_the_name():
    text = _skill("source-verify")
    assert "pick_point" in text and "nominatim_address" in text


# --- Task 6: the corpus counts what the new rule works on -----------------------------

def test_the_corpus_measurement_counts_addresses_sources_and_geocode_sources():
    from tests.corpus_measure import measure_corpus
    from tests.mech_fixtures import CORPUS_TRIPS
    m = measure_corpus()["sources"]
    assert sorted(m) == sorted(CORPUS_TRIPS)
    for trip, row in m.items():
        assert set(row) == {"pois", "with_address", "geocode_source", "source_lang"}, trip
        assert row["with_address"] <= row["pois"] and sum(row["geocode_source"].values()) <= row["pois"]
