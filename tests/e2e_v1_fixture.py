"""v1.0 release e2e fixture (spec §7, 8-step gate step 7): the reader fixture grown
into the trips that exercise every v1.0 surface at once --

    tour()      4 days across a month boundary (10/30 → 11/2) with a hotel change:
                D1 函館 → 示意飯店; D2 函館 → 特急北斗 → 洞爺 (long move, new hotel);
                D3 洞爺; D4 洞爺 → 返程
    day_trip()  one day, no lodging at all

Both are built from tests/reader_fixture.py's POIs and helpers, and each builder is
checked against the real gate by tests/test_e2e_v1_release.py -- a fixture the gate
rejects would test the reader on data the pipeline never emits.
"""
import copy

from tests import reader_fixture as R
from tests.reader_fixture import _closing, _mv, _stop

TOYA_POIS = [
    R._poi("toya-lake", "洞爺湖", "洞爺湖", "sight", 42.6010, 140.8500,
           {"close": "17:00", "last_entry": "16:30", "typical_visit_mins": 90, "as_of": "2026-09-01"},
           intro="火山口湖，湖中有中島。", district="洞爺湖温泉"),
    R._poi("toya-museum", "洞爺湖ビジターセンター", "洞爺湖遊客中心", "sight", 42.5660, 140.8190,
           {"close": "17:00", "last_entry": "16:30", "typical_visit_mins": 45, "as_of": "2026-09-01"},
           district="洞爺湖温泉"),
    R._poi("toya-wakasaimo", "わかさいも本舗 洞爺湖本店", "若狹芋本舖", "food", 42.5648, 140.8230,
           {"close": "18:00", "last_order": "17:30", "typical_visit_mins": 45, "as_of": "2026-09-01"},
           district="洞爺湖温泉"),
]

TOYA_HOTEL = copy.deepcopy(R.LODGING)
TOYA_HOTEL.update({"id": "toya-hotel", "name_local": "サンプルリゾート洞爺",
                   "name_display": "示の風", "name_zh": "示之風度假村",
                   "geocode": {"lat": 42.5652, "lng": 140.8215, "geocode_source": "nominatim"},
                   "resolved_name": "サンプルリゾート洞爺"})
TOYA_HOTEL["sources"] = [R._src("https://toyasample.example/", "ja", "示之風官網", "房型", official=True,
                                site_local="示の風公式"),
                         R._src("https://guide.example/toyasample", "zh", "旅遊指南", "位置")]

LEGS = {"legs": [{"from": "函館", "to": "洞爺", "mode": "rail", "duration_mins": 110,
                  "service": "特急北斗", "status": "ok", "depart": "10:00", "last_service": "18:30",
                  "sources": [{"url": "https://jr.example/hokuto", "official": True}]}]}


def accommodations():
    hak = copy.deepcopy(R.ACCOMMODATIONS["stops"][0])
    hak["nights"] = 1
    return {"stops": [hak, {"district": "洞爺湖温泉", "area_label": "洞爺", "nights": 2,
                            "chosen": "toya-hotel", "candidates": [copy.deepcopy(TOYA_HOTEL)]}]}


def pois():
    return copy.deepcopy(R.POIS) + copy.deepcopy(TOYA_POIS)


def tour():
    by_id = {p["id"]: p for p in pois()}
    days = [
        {"date": "2026-10-30", "lodging": "hak-hotel", "theme": "落地先吃朝市",
         "theme_refs": ["hak-asaichi"],
         "rows": [_mv("taxi", 9, 25, text="機場搭計程車", **{"from": "函館空港"}),
                  _stop("meal", "12:00", "hak-asaichi", "朝市海鮮丼午餐"),
                  _mv("taxi", 7, 20),
                  _stop("visit", "14:00", "hak-goryokaku", "五稜郭公園散步"),
                  _mv("taxi", 7, 20, text="回飯店")]},
        {"date": "2026-10-31", "lodging": "toya-hotel", "theme": "朝市的蟹，湖畔的風",
         "theme_refs": ["hak-asaichi", "toya-lake"],
         "alternatives": [{"kind": "備案", "applies_to": "toya-lake", "trigger": "下雨",
                           "fallback": "改去遊客中心看火山展示", "poi_id": "toya-museum"}],
         "rows": [_mv("walk", 0.9, 12),
                  _stop("meal", "08:00", "hak-asaichi", "朝市蟹早餐"),
                  {"slot": "move", "text": "特急北斗", "leg_index": 0},
                  _stop("visit", "13:00", "toya-lake", "湖畔散步"),
                  _mv("taxi", 5, 12, text="到飯店")]},
        {"date": "2026-11-01", "lodging": "toya-hotel", "theme": "火山口的一天",
         "theme_refs": ["toya-museum"],
         "rows": [_mv("walk", 0.5, 8),
                  _stop("visit", "10:00", "toya-museum", "看火山展示"),
                  _mv("walk", 0.5, 8),
                  _stop("meal", "12:00", "toya-wakasaimo", "午餐吃點心"),
                  _mv("walk", 0.5, 8, text="回飯店")]},
        {"date": "2026-11-02", "theme": "再見洞爺湖", "theme_refs": ["toya-lake"],
         "rows": [_mv("walk", 0.5, 8),
                  _stop("meal", "08:00", "toya-wakasaimo", "早餐"),
                  _mv("taxi", 5, 12),
                  _stop("visit", "09:30", "toya-lake", "最後看一眼湖"),
                  _mv("taxi", 8, 20, text="前往洞爺站", to="洞爺站")]},
    ]
    for d in days:
        _closing(d["rows"], by_id)
    from tests.title_fixture import add_titles          # v1.1 topic 7
    return add_titles({"title": "函館洞爺四天", "checklist": copy.deepcopy(R.CHECKLIST), "days": days})


def tour_brief():
    b = R.brief()
    b.update(slug="2026-10-hokkaido", dates={"start": "2026-10-30", "end": "2026-11-02"})
    return b


def day_trip():
    by_id = {p["id"]: p for p in pois()}
    day = {"date": "2026-10-15", "theme": "一天吃遍函館", "theme_refs": ["hak-asaichi"],
           "rows": [_mv("walk", 0.5, 8, **{"from": "函館駅"}),
                    _stop("meal", "08:00", "hak-asaichi", "朝市早餐"),
                    _mv("taxi", 7, 20),
                    _stop("visit", "10:00", "hak-goryokaku", "五稜郭公園"),
                    _mv("taxi", 7, 20, text="回車站", to="函館駅")]}
    _closing(day["rows"], by_id)
    from tests.title_fixture import add_titles
    return add_titles({"title": "函館一日", "checklist": copy.deepcopy(R.CHECKLIST[2:]), "days": [day]})


def day_trip_brief():
    b = R.brief()
    b.update(slug="2026-11-hakodate-day", dates={"start": "2026-10-15", "end": "2026-10-15"})
    return b
