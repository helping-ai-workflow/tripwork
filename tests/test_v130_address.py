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


def _run(monkeypatch, name_hit, address_hit, address="北海道函館市五稜郭町4-9", centroid=HAKODATE,
         variant="北海道函館市五稜郭町4丁目"):
    from scripts import source_verify_run as svr
    calls = {"address": 0}

    def resolve(name, district, country, cache, name_roman=None, area=False, region=None):
        return (G.GeocodeResult(*name_hit, "示意咖啡, 某町"), "nominatim") if name_hit else (None, None)

    def addr(a, country, cache):
        calls["address"] += 1
        if not address_hit:
            return None, False
        return G.GeocodeResult(*address_hit, "五稜郭町, 函館市"), G.address_is_fine(a, variant, "jp")
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
    assert geo["query"]["address"] == "北海道函館市五稜郭町4-9"


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


# e2e on a consumer trip (2026-10-05): a full-text address can match far away (one landed
# 1285 km off, one 58 km off and dropped a correct name hit), and a town-level point is too
# coarse to judge a name hit (one dropped a correct hit 2.9 km from its town centre)

def test_an_address_point_outside_the_district_is_ignored(monkeypatch):
    (geo, _, inside, _, _), _ = _run(monkeypatch, NEAR, HAKODATE, centroid=FAR)
    assert geo["geocode_source"] == "nominatim" and (geo["lat"], geo["lng"]) == NEAR     # the name hit stands
    (geo, *_), _ = _run(monkeypatch, None, HAKODATE, centroid=FAR)
    assert geo["geocode_source"] == "cluster_fallback"


def test_a_town_level_address_point_neither_vetoes_nor_stands_in(monkeypatch):
    town = "北海道函館市五稜郭町"
    (geo, *_), _ = _run(monkeypatch, FAR, HAKODATE, variant=town, centroid=FAR)
    assert geo["geocode_source"] == "nominatim"
    (geo, *_), _ = _run(monkeypatch, None, HAKODATE, variant=town)
    assert geo["geocode_source"] == "cluster_fallback"


def test_without_a_district_centre_the_address_point_is_not_trusted(monkeypatch):
    (geo, *_), _ = _run(monkeypatch, FAR, HAKODATE, centroid=None)
    assert geo["geocode_source"] == "nominatim"


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
    assert "zh-TW" in gate1 and "never replaces" in gate1 and "keep every traveller write-up in sources" in gate1


def test_two_taiwan_pages_without_a_local_source_are_not_enough():
    from scripts.verify import classify_candidate
    cand = {"sources": [_src("zh-TW", "https://a.example/trip"), _src("zh-TW", "https://b.example/trip")]}
    status, note = classify_candidate(cand, True, True, local_lang="ja", geocode_source="nominatim")
    assert status == "unverified" and "local language" in note


def test_a_taiwan_page_and_a_local_source_pass():
    from scripts.verify import classify_candidate
    cand = {"sources": [_src("zh-TW", "https://a.example/trip"), _src("ja", "https://shop.example.jp/")]}
    assert classify_candidate(cand, True, True, local_lang="ja", geocode_source="nominatim")[0] == "verified"


def test_two_travellers_on_one_unlisted_platform_are_one_source():
    """v2.0.0 Q1 reverses v1.3.0: write-ups on one blog platform the Public Suffix List
    does not list count as one site (the user: keep collecting them, they just do not
    count twice). A PSL-listed platform keeps one site per author -- see
    tests/test_source_independence.py::test_distinct_sites_are_two_sources."""
    from scripts.verify import classify_candidate
    cand = {"sources": [_src("zh-TW", "https://amy.blog.example/okinawa"), _src("ja", "https://bob.blog.example/x")]}
    status, note = classify_candidate(cand, True, True, local_lang="ja", geocode_source="nominatim")
    assert status == "unverified" and "blog.example" in note


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


def test_only_the_address_or_its_chome_is_fine():
    a = "東京都台東区浅草2-3-1 浅草ビル5F"
    assert G.address_is_fine(a, "東京都台東区浅草2-3-1", "jp") and G.address_is_fine(a, "東京都台東区浅草2丁目", "jp")
    assert not G.address_is_fine(a, "東京都台東区浅草", "jp")
    assert G.address_is_fine("嘉義市西區民族路100號2樓", "嘉義市西區民族路100號2樓", "tw")
    assert not G.address_is_fine("嘉義市西區民族路100號2樓", "嘉義市西區民族路", "tw")
    assert G.address_is_fine("12 Example Street, Queenstown", "12 Example Street, Queenstown", "nz")


# --- v1.3.0 (the user's call): a district the settlement lookup misses -----------------
# (e2e: 首里赤田町 / 西洲 / 嘉数-like districts exist in OSM only as their 丁目; a plain query
# returns a parking lot, a pump station, a bus stop)

def _district_run(monkeypatch, answers, district="函館市元町"):
    from scripts import source_verify_run as svr
    monkeypatch.setattr(svr.time, "sleep", lambda *_: None)
    get, seen = _nominatim(answers)
    monkeypatch.setattr(G.requests, "get", get)
    return svr._district_centroid(district, "日本", {}, False, {}), seen


def test_a_district_found_only_as_a_place_by_a_plain_query(monkeypatch):
    def answers(p):
        if p.get("featureType") == "country":
            return JP
        if p.get("featureType") == "settlement":
            return []
        if p.get("q") == "函館市元町":
            return [{"lat": "41.70", "lon": "140.70", "class": "highway", "display_name": "元町, 某バス停"},
                    {"lat": "41.76", "lon": "140.71", "class": "place", "display_name": "元町, 函館市, 北海道"}]
        return []
    centre, seen = _district_run(monkeypatch, answers)
    assert centre == (41.76, 140.71)                     # the place, not the bus stop named after it


def test_a_district_found_only_as_its_first_chome(monkeypatch):
    def answers(p):
        if p.get("featureType") == "country":
            return JP
        if p.get("q") == "函館市元町一丁目" and "featureType" not in p:
            return [{"lat": "41.761", "lon": "140.712", "class": "place", "display_name": "元町一丁目, 函館市"}]
        if p.get("q") == "函館市元町" and "featureType" not in p:
            return [{"lat": "41.70", "lon": "140.70", "class": "amenity", "display_name": "元町駐車場, 元町一丁目"}]
        return []
    centre, _ = _district_run(monkeypatch, answers)
    assert centre == (41.761, 140.712)


def test_a_building_named_after_the_district_is_still_not_its_centre(monkeypatch):
    def answers(p):
        if p.get("featureType") == "country":
            return JP
        return [{"lat": "41.70", "lon": "140.70", "class": "place", "display_name": "函館市立元町中学校, 元町"}]
    centre, _ = _district_run(monkeypatch, answers)
    assert centre is None


# --- v1.3.0 (the user's call): a flaky network neither ends the run nor loses its progress
# (e2e: one Nominatim read timeout ended a 6-minute source-verify run with nothing saved)

import requests as _requests


class _Status(_Resp):
    def __init__(self, payload, status):
        super().__init__(payload)
        self.status_code = status


def test_a_timeout_is_retried(monkeypatch):
    calls, waits = [], []

    def get(url, params=None, headers=None, timeout=None):
        calls.append(params)
        if len(calls) < 3:
            raise _requests.exceptions.ReadTimeout("slow")
        return _Resp([{"lat": "41.79", "lon": "140.75", "display_name": "五稜郭"}])
    monkeypatch.setattr(G.requests, "get", get)
    monkeypatch.setattr(G, "_sleep", waits.append)
    r = G.geocode("五稜郭")
    assert r.lat == 41.79 and len(calls) == 3 and waits == list(G._RETRY_WAITS)


def test_a_busy_server_is_retried(monkeypatch):
    answers = [_Status([], 503), _Status([], 429), _Status([{"lat": "1", "lon": "2", "display_name": "x"}], 200)]
    monkeypatch.setattr(G.requests, "get", lambda *a, **k: answers.pop(0))
    monkeypatch.setattr(G, "_sleep", lambda s: None)
    assert G.geocode("x").lng == 2.0


def test_a_network_that_stays_down_raises_and_caches_no_miss(monkeypatch):
    def down(*a, **k):
        raise _requests.exceptions.ConnectionError("down")
    monkeypatch.setattr(G.requests, "get", down)
    monkeypatch.setattr(G, "_sleep", lambda s: None)
    cache = {}
    with pytest.raises(_requests.exceptions.ConnectionError):
        G.resolve_place("五稜郭", district="函館市", country="JP", cache=cache)
    assert cache == {}                                  # a network failure is not "not found"


def test_the_run_saves_its_progress_before_a_network_failure(tmp_path, monkeypatch, capsys):
    import json
    import yaml
    from scripts import source_verify_run as svr
    from scripts.paths import artifact_path
    monkeypatch.setattr(svr.time, "sleep", lambda *_: None)

    def resolve(name, district=None, country=None, timeout=10, cache=None, name_roman=None, pace=None, area=False, region=None):
        if name == "二號店":
            raise _requests.exceptions.ReadTimeout("slow")
        cache[f"{name}|seen"] = {"lat": 1, "lng": 2, "source": "nominatim", "display_name": name}
        return G.GeocodeResult(23.48, 120.44, name), "nominatim"
    monkeypatch.setattr(svr, "resolve_place", resolve)
    trip, work = tmp_path / "trips" / "t", tmp_path / "work" / "t"
    (trip / "data").mkdir(parents=True)
    work.mkdir(parents=True)
    cands = [{"id": f"c{i}", "name_local": n, "category": "food",
              "sources": [{"url": f"https://{i}.example/", "lang": "zh-TW"}]} for i, n in enumerate(("一號店", "二號店"))]
    for name, doc in (("trip-brief.yaml", {"destination": {"country": "TW", "local_lang": "zh-TW"}}),
                      ("candidates.yaml", {"candidates": cands})):
        artifact_path(trip, name).write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    assert svr.main([str(trip), "--work-dir", str(work)]) == 1
    saved = json.loads((work / "geocode-cache" / "geocode.json").read_text(encoding="utf-8"))
    assert "一號店|seen" in saved                         # the first candidate's lookups survive
    assert "re-run" in capsys.readouterr().err
