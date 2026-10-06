"""v2.1.0 closure: one made-up domestic trip runs every consumer defect D3-D10 through the
shipped commands in order, then a survey reaches its list page and upgrades to a trip.
Nominatim is a fake that records every query; the places, hotel and addresses are 示意."""
import datetime
import sys

import pytest
import yaml
from bs4 import BeautifulSoup

from scripts import geocode as G
from scripts import source_verify_run as svr
from scripts.paths import artifact_path, deliverable_paths
from tests.cli_helpers import run_main
from tests.mech_fixtures import advisory, write_artifact

TODAY = datetime.date.today().isoformat()
CENTRE = (25.1360, 121.5060)
STATUS = {"status": "OPERATIONAL", "source_url": "https://status.example/", "as_of": TODAY}


class _Resp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def _hit(name, at, **kw):
    return {"lat": str(at[0]), "lon": str(at[1]), "display_name": name, **kw}


def nominatim(params):
    q, street = params.get("q", ""), params.get("street")
    if params.get("featureType") == "country":
        raise AssertionError("Taiwan needs no country lookup (D4)")
    if params.get("featureType") == "settlement" and q.startswith("中西區"):
        return [_hit("中西區, 臺南市, 臺灣", CENTRE)]
    if q == "臺南市中西區示意路":                                          # D5: the road, its 村里
        return [_hit("示意路, 示意里, 中西區, 臺南市, 臺灣", (25.1366, 121.5071),
                     address={"road": "示意路", "suburb": "示意里", "city_district": "中西區"})]
    if q == "示意麵店":                                                   # D6: a namesake 13 km off
        return [_hit("示意麵店, 信義區, 臺南市, 臺灣", (25.0300, 121.5600))]
    if street or q:
        return []
    return []


def _cand(cid, name, sources, **kw):
    return {"id": cid, "name_local": name, "name_display": name, "category": kw.pop("category", "restaurant"),
            "claimed_district": "中西區", "business_status": STATUS, "sources": sources, **kw}


BRIEF = {"slug": "t", "dates": {"start": "2030-01-07", "end": "2030-01-08"},
         "destination": {"country": "台灣", "city": "臺南市中西區", "local_lang": "zh"},
         "members": [{"name": "成員1"}], "base": {"name": "示意旅館", "district": "中西區"},
         "must_do": [], "constraints": [], "preferences": {}, "short_name": "府城",
         "home_origin": "示意車站", "home_return": "示意車站",
         "home_origin_point": {"name": "示意車站", "lat": 25.0478, "lng": 121.5170, "geocode_source": "nominatim"},
         "home_return_point": {"name": "示意車站", "lat": 25.0478, "lng": 121.5170, "geocode_source": "nominatim"}}
CANDIDATES = {"candidates": [
    _cand("road", "示意小館", [{"url": "https://road.example.tw/", "lang": "zh"},
                              {"url": "https://guide.example/road", "lang": "zh", "site": "示意指南"}],
          address_local="臺南市中西區示意路100號"),
    _cand("namesake", "示意麵店", [{"url": "https://noodle.example.tw/", "lang": "zh"},
                                  {"url": "https://blog.example/noodle", "lang": "zh"}]),
    _cand("bare", "示意咖啡", [{"url": "https://cafe.example/", "lang": "zh"},
                              {"url": "https://blog.example/cafe", "lang": "zh"}]),
]}


@pytest.fixture
def trip(tmp_path, monkeypatch):
    root = tmp_path
    t, w = root / "trips" / "t", root / "work" / "t"
    w.mkdir(parents=True)
    (root / "work" / ".preflight-completed").touch()
    write_artifact(artifact_path(t, "trip-brief.yaml"), BRIEF)
    write_artifact(artifact_path(t, "candidates.yaml"), CANDIDATES)
    monkeypatch.setattr(svr.time, "sleep", lambda *_: None)
    seen = []
    monkeypatch.setattr(G.requests, "get", lambda url, params=None, **kw: (seen.append(dict(params or {})),
                                                                          _Resp(nominatim(dict(params or {}))))[1])
    return t, w, seen


def _next(t, w):
    r = run_main("scripts.next_stage", [str(t), "--work-dir", str(w)])
    assert r.returncode == 0, r.stderr
    return yaml.safe_load(r.stdout)


def _load(t, name):
    return yaml.safe_load(artifact_path(t, name).read_text(encoding="utf-8"))


def test_the_consumer_trip_closes_d3_to_d10(trip, monkeypatch, capsys):
    t, w, seen = trip
    # D3: a bare zh is refused at rule 1, by name of the five regions
    out = _next(t, w)
    assert out["next"] == "tripwork:trip-brief" and "zh-TW / zh-HK" in out["reason"]
    # D3: migrate tags the brief (台灣 -> zh-TW) and every source its URL proves
    assert run_main("scripts.migrate_v1", [str(t), "--work-root", str(t.parent.parent / "work"), "--apply"]).returncode == 0
    assert _load(t, "trip-brief.yaml")["destination"]["local_lang"] == "zh-TW"
    langs = {c["id"]: [s["lang"] for s in c["sources"]] for c in _load(t, "candidates.yaml")["candidates"]}
    assert langs == {"road": ["zh-TW", "zh"], "namesake": ["zh-TW", "zh"], "bare": ["zh", "zh"]}
    assert _next(t, w)["next"] == "tripwork:travel-advisory"
    # verify (D3-D6 together)
    assert svr.main([str(t), "--work-dir", str(w)]) in (0, 1)
    assert not [p for p in seen if p.get("featureType") == "country"]                    # D4
    pois = {p["id"]: p for p in _load(t, "verified-pois.yaml")["pois"]}
    assert pois["road"]["geocode"]["geocode_source"] == "nominatim_road"                 # D5
    assert pois["road"]["verify_status"] == "verified"
    assert pois["namesake"]["geocode"]["geocode_source"] == "cluster_fallback"           # D6
    assert pois["namesake"]["geocode"]["lat"] == CENTRE[0]
    assert pois["bare"]["verify_status"] == "unverified" and "標 zh、沒有地區" in pois["bare"]["status_reason"]

    # D7 / D9 / D10: the deliverables from these places, a hotel with its place id, home legs
    pid = "ChIJ0000000000000000000000"
    hotel = {"id": "hotel", "name_local": "示意旅館", "name_display": "示意旅館", "category": "lodging",
             "verify_status": "verified", "gmaps_place_id": pid,
             "geocode": {"lat": 25.1370, "lng": 121.5080, "geocode_source": "nominatim"},
             "sources": [{"url": "https://hotel.example/", "lang": "zh-TW", "site": "示意旅館網"}]}
    legs = {"legs": [{"from": "示意車站", "to": "府城", "mode": "rail", "kind": "home", "duration_mins": 35},
                     {"from": "府城", "to": "示意車站", "mode": "rail", "kind": "home", "duration_mins": 35}]}
    itin = {"title": "府城", "days": [
        {"date": "2030-01-07", "label": "D1", "lodging": "hotel",
         "rows": [{"slot": "move", "leg_index": 0, "text": "捷運"},
                  {"time": "12:00", "slot": "meal", "poi_id": "road", "text": "午餐"}]},
        {"date": "2030-01-08", "label": "D2",
         "rows": [{"time": "10:00", "slot": "meal", "poi_id": "namesake", "text": "早午餐"},
                  {"slot": "move", "leg_index": 1, "text": "捷運"}]}]}
    pm = {**pois, "hotel": hotel}
    from scripts.render.markdown import MODE_MARK, render_markdown_page
    md = render_markdown_page(itin, pm, brief=_load(t, "trip-brief.yaml"), legs=legs)
    assert not any(s.get("official") for p in pois.values() for s in p["sources"])
    assert "· [example.tw](https://road.example.tw/)" in md and "官網" not in md     # D7: no 官網 without one
    assert f"[{MODE_MARK['rail']} 示意車站→府城]" in md                                    # D7: the leg's mode
    from scripts.render.gmaps_links import maps_url
    assert f"query_place_id={pid}" in maps_url(hotel)                                   # D9
    from scripts.render.reader import render_reader
    from scripts.render.reader.maps import LABELS
    soup = BeautifulSoup(render_reader(itin, pm, brief=_load(t, "trip-brief.yaml"), legs=legs), "html.parser")
    d1 = [c.get_text() for c in soup.select('section[data-pg="d1"] .mapc .chips a.chip')]
    d2 = [c.get_text() for c in soup.select('section[data-pg="d2"] .mapc .chips a.chip')]
    assert d1[1] == LABELS["home_start"] and LABELS["hotel_end"] in d1                   # D10
    assert d2[-1] == LABELS["home_end"]

    # D8: no font package -> the picker's list still prints, one line, exit 2
    from scripts import title_picker
    from scripts.render.reader import assets
    monkeypatch.setitem(sys.modules, "fontTools", None)
    monkeypatch.setitem(sys.modules, "fontTools.subset", None)
    monkeypatch.setitem(sys.modules, "fontTools.ttLib", None)
    assets.font_faces.cache_clear()
    write_artifact(artifact_path(t, "itinerary.yaml"), itin)
    capsys.readouterr()
    assert title_picker.main([str(t), "--work-dir", str(w)]) == 2
    o, e = capsys.readouterr()
    assert "D1" in o and assets.FONT_PACKAGE_MESSAGE in e and "Traceback" not in e
    assets.font_faces.cache_clear()


def test_a_survey_lists_then_upgrades(trip):
    t, w, _seen = trip
    write_artifact(artifact_path(t, "trip-brief.yaml"),
                   {"slug": "t", "mode": "survey", "short_name": "府城散步",
                    "destination": {"country": "台灣", "city": "臺南市中西區", "local_lang": "zh-TW"},
                    "categories": ["吃的"]})
    cands = yaml.safe_load(yaml.safe_dump(CANDIDATES))
    for c in cands["candidates"]:
        for s in c["sources"]:
            s["lang"] = "zh-TW"
    write_artifact(artifact_path(t, "candidates.yaml"), cands)
    out = _next(t, w)                                                         # the oracle wants the record
    assert out["next"] == "tripwork:destination-research" and "must_do_searched" in out["reason"]
    cands["must_do_searched"] = []                                            # research records it
    write_artifact(artifact_path(t, "candidates.yaml"), cands)
    assert svr.main([str(t), "--work-dir", str(w)]) in (0, 1)
    assert _next(t, w)["next"] == "tripwork:export-artifact"                     # survey: the list page
    from scripts import survey_table
    assert survey_table.main([str(t), "--page"]) == 0
    brief = _load(t, "trip-brief.yaml")
    page = deliverable_paths(t, brief)["html"]
    assert page.name == "府城散步 清單.html" and "示意小館" in page.read_text(encoding="utf-8")
    assert _next(t, w) == {"next": "complete", "reason": "survey：清單完成"}
    # the upgrade: the trip fields, a new must_do; verified places carry over
    up = {k: v for k, v in brief.items() if k != "mode"}
    up.update({"dates": {"start": "2030-01-07", "end": "2030-01-08"}, "members": [{"name": "成員1"}],
               "base": {"name": "示意旅館", "district": "中西區"}, "must_do": ["泡溫泉"],
               "constraints": [], "preferences": {}})
    write_artifact(artifact_path(t, "trip-brief.yaml"), up)
    assert _next(t, w)["next"] == "tripwork:travel-advisory"                     # rule 1.5 picks up
    write_artifact(artifact_path(t, "advisory.yaml"), advisory())
    out = _next(t, w)
    assert out["next"] == "tripwork:destination-research" and "泡溫泉" in out["reason"]
