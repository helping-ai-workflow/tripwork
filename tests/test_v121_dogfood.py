"""v1.2.1: defects a consumer trip found in v1.2.0 (non-browser half; the reader's card
edges and the title picker's copy are in tests_browser/). Examples are made up or
public places -- never the trip's own."""
import pytest

from scripts import geocode as G


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


def _nominatim(answers):
    """A fake requests.get: records every query's params; `answers(params)` gives the JSON."""
    seen = []

    def get(url, params=None, headers=None, timeout=None):
        seen.append(dict(params or {}))
        return _Resp(answers(params or {}))
    return get, seen


def _country(params):
    return params.get("featureType") == "country"


# --- 2. free-text fallbacks stay inside the trip's country --------------------------

def test_free_text_fallbacks_stay_in_the_trips_country(monkeypatch):
    def answers(p):
        if _country(p):
            return [{"lat": "36", "lon": "138", "display_name": "日本", "address": {"country_code": "jp"}}]
        return []                                      # the venue is found nowhere
    get, seen = _nominatim(answers)
    monkeypatch.setattr(G.requests, "get", get)
    G.resolve_place("ゆめ食堂", district="函館市", country="日本", name_roman="Yume Shokudo")
    free = [p for p in seen if "q" in p and not _country(p)]
    assert len(free) == 4                              # the four free-text tiers
    assert all(p.get("countrycodes") == "jp" for p in free), free


def test_the_country_code_is_looked_up_once_per_trip_cache(monkeypatch):
    get, seen = _nominatim(lambda p: [{"lat": "36", "lon": "138", "display_name": "日本",
                                       "address": {"country_code": "jp"}}] if _country(p) else [])
    monkeypatch.setattr(G.requests, "get", get)
    cache = {}
    G.resolve_place("ゆめ食堂", district="函館市", country="日本", cache=cache)
    G.resolve_place("つき食堂", district="函館市", country="日本", cache=cache)
    assert sum(1 for p in seen if _country(p)) == 1


def test_a_country_nominatim_cannot_name_leaves_the_search_open(monkeypatch):
    get, seen = _nominatim(lambda p: [])
    monkeypatch.setattr(G.requests, "get", get)
    G.resolve_place("ゆめ食堂", district="函館市", country="どこか")
    assert [p for p in seen if "q" in p and not _country(p)]
    assert not any("countrycodes" in p for p in seen)


def test_a_structured_hit_needs_no_country_lookup(monkeypatch):
    get, seen = _nominatim(lambda p: [{"lat": "41.79", "lon": "140.75", "display_name": "五稜郭"}])
    monkeypatch.setattr(G.requests, "get", get)
    r, source = G.resolve_place("五稜郭", district="函館市", country="日本")
    assert source == "nominatim_structured" and len(seen) == 1


# --- 3. a district centroid is the district, not a building named after it ----------

def _district(monkeypatch, display, district="小樽市堺町"):
    from scripts import source_verify_run as svr
    monkeypatch.setattr(svr, "_rate_limited_resolve",
                        lambda name, d, c, cache, name_roman=None, area=False:
                        (G.GeocodeResult(43.19, 141.0, display), "nominatim"))
    return svr._district_centroid(district, "日本", {}, False, {})


def test_a_building_named_after_the_district_is_not_its_centroid(monkeypatch):
    assert _district(monkeypatch, "小樽市立堺町中学校, 堺町, 小樽市, 北海道, 日本") is None


def test_the_district_itself_is_its_centroid(monkeypatch):
    assert _district(monkeypatch, "堺町, 小樽市, 北海道, 日本") == (43.19, 141.0)


def test_a_district_is_looked_up_as_a_place_not_a_venue(monkeypatch):
    from scripts import source_verify_run as svr
    monkeypatch.setattr(svr.time, "sleep", lambda *_: None)

    def answers(p):
        if _country(p):
            return [{"lat": "36", "lon": "138", "display_name": "日本", "address": {"country_code": "jp"}}]
        if p.get("featureType") == "settlement":
            return [{"lat": "43.19", "lon": "141.0", "display_name": "堺町, 小樽市, 北海道, 日本"}]
        return [{"lat": "43.2", "lon": "141.1", "display_name": "小樽市立堺町中学校, 堺町, 小樽市"}]
    get, seen = _nominatim(answers)
    monkeypatch.setattr(G.requests, "get", get)
    cache = {G.cache_key("小樽市堺町", None, "日本"): {"lat": 43.2, "lng": 141.1, "source": "nominatim",
                                                      "display_name": "小樽市立堺町中学校, 堺町, 小樽市"}}
    # a venue lookup cached under the same name must not stand in for the district
    assert svr._district_centroid("小樽市堺町", "日本", cache, False, {}) == (43.19, 141.0)
    assert not any("street" in p for p in seen)        # no venue (street-slot) query for a district
    assert all(p.get("countrycodes") == "jp" for p in seen if p.get("featureType") == "settlement")


# --- 4. classify_leg's tuple is written as the leg's status --------------------------

def test_the_legs_skill_says_classify_leg_returns_a_pair():
    import pathlib
    text = (pathlib.Path(__file__).resolve().parent.parent / "skills" / "inter-stop-legs" / "SKILL.md").read_text(encoding="utf-8")
    run = text[text.index("Run `classify_leg("):]
    para = run[:run.index("\n\n")]
    assert "(status, reason)" in para and "`status`" in para


def test_every_skill_that_runs_classify_leg_says_it_returns_a_pair():
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parent.parent / "skills"
    for f in sorted(root.glob("*/SKILL.md")):
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"[Rr](?:e-)?(?:un|-run) `(?:scripts/legs\.py::)?classify_leg", text):
            para = text[m.start():text.find("\n\n", m.start())]
            assert "(status, reason)" in para, (f.parent.name, para[:120])


def test_classify_leg_still_returns_status_and_reason():
    from scripts.legs import classify_leg
    assert classify_leg({"mode": "drive", "duration_mins": 30}) == ("ok", "")


# --- 6. a pun swaps characters for ones that sound the same --------------------------

def test_a_homophone_pun_reworks_its_riff():
    from scripts.brief_names import riff_overlap_ok
    assert riff_overlap_ok("沖沖沖", "衝衝衝")                 # 沖 and 衝 are both ㄔㄨㄥ


def test_a_title_that_neither_keeps_nor_echoes_the_riff_still_fails():
    from scripts.brief_names import riff_overlap_ok
    assert not riff_overlap_ok("看海吃冰", "衝衝衝")
    assert not riff_overlap_ok("衝衝衝", "衝衝衝")              # the riff itself is no rework


def test_day_titles_use_the_same_rule():
    from scripts import day_titles
    from scripts.brief_names import riff_overlap_ok
    assert day_titles.riff_overlap_ok is riff_overlap_ok
