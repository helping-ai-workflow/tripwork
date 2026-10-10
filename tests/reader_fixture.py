"""v1.0 P4 reader fixture: a three-day, hokkaido-shaped trip in the full v1.0 shape.

D1 函館空港 → 朝市 (lunch) → 示意飯店
D2 示意飯店 → 朝市 → 五稜郭 (photo) → 函館山 (備案: 五稜郭塔) → 示意飯店 dinner → (none)
D3 示意飯店 → 朝市 → 函館空港

Closing verdicts are computed with the shipped scripts/hours.py::closing_status and
the builder asserts the whole fixture passes the real gate: a fixture the gate
rejects would be testing the renderer on data the pipeline never emits.
"""
import copy
import datetime

from scripts.hours import closing_status
from tests.mech_fixtures import brief_name_fields

TODAY = datetime.date.today().isoformat()
PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
       "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def _src(url, lang, site, note, official=False, site_local=None):
    s = {"url": url, "lang": lang, "site": site, "note": note}
    if official:
        s["official"] = True
    if site_local:
        s["site_local"] = site_local
    return s


def _poi(pid, name_local, name_zh, category, lat, lng, hours, intro=None, **extra):
    p = {"id": pid, "name_local": name_local, "name_display": name_local, "name_zh": name_zh,
         "category": category, "district": "函館",
         "sources": [_src(f"https://official.example/{pid}", "ja", f"{name_zh}官網", "營業時間與票價",
                          official=True, site_local=f"{name_local}公式"),
                     _src(f"https://guide.example/{pid}", "zh", "旅遊指南", "交通方式")],
         "verify_status": "verified",
         "geocode": {"lat": lat, "lng": lng, "geocode_source": "nominatim"},
         "resolved_name": name_local,
         "business_status": {"status": "OPERATIONAL", "source_url": f"https://official.example/{pid}",
                             "as_of": TODAY},
         "hours": hours}
    if intro:
        p["intro"], p["intro_source"] = intro, f"https://official.example/{pid}"
    p.update(extra)
    return p


POIS = [
    _poi("hak-asaichi", "函館朝市", "函館朝市", "food", 41.7735, 140.7266,
         {"close": "14:00", "last_order": "13:30", "typical_visit_mins": 60, "as_of": "2026-09-01"},
         intro="函館車站旁的早市，約 250 家店。"),
    _poi("hak-goryokaku", "五稜郭公園", "五稜郭公園", "sight", 41.7969, 140.7570,
         {"close": "18:00", "last_entry": "17:30", "typical_visit_mins": 90, "as_of": "2026-09-01"}),
    _poi("hak-yama", "函館山", "函館山", "sight", 41.7594, 140.7045,
         {"close": "22:00", "last_entry": "21:30", "typical_visit_mins": 90, "as_of": "2026-09-01"},
         intro="山頂展望台，夜景與香港、拿坡里並稱。"),
    _poi("hak-tower", "五稜郭タワー", "五稜郭塔", "sight", 41.7946, 140.7539,
         {"close": "19:00", "last_entry": "18:50", "typical_visit_mins": 45, "as_of": "2026-09-01"}),
]

LODGING = {
    "id": "hak-hotel", "name_local": "サンプルホテル函館", "name_display": "サンプルホテル函館",
    "name_zh": "函館示意飯店", "facilities": [],
    "geocode": {"lat": 41.7697, "lng": 140.7196, "geocode_source": "nominatim"},
    "resolved_name": "サンプルホテル函館",
    "business_status": {"status": "OPERATIONAL", "source_url": "https://hotel.example/", "as_of": TODAY},
    "sources": [_src("https://hotel.example/", "ja", "示意飯店官網", "房型與入住", official=True,
                     site_local="サンプル公式"),
                _src("https://guide.example/samplebay", "zh", "旅遊指南", "位置")],
    "verify_status": "verified",
}

ACCOMMODATIONS = {"stops": [{"district": "函館", "area_label": "函館", "nights": 2,
                             "chosen": "hak-hotel", "candidates": [LODGING]}]}

ADVISORY = {"items": [
    {"topic": "肉製品", "rule": "所有肉製品禁止攜入日本", "effective_date": "2020-01-01",
     "risk": "banned",
     "sources": [{"url": "https://www.maff.go.jp/aqs/", "official": True},
                 {"url": "https://www.koryu.or.jp/", "official": False}]},
    {"topic": "電壓", "rule": "日本電壓 100V，台灣電器多可直接使用", "effective_date": "2020-01-01",
     "risk": "info",
     "sources": [{"url": "https://www.jnto.go.jp/", "official": True},
                 {"url": "https://guide.example/volt", "official": False}]},
]}

CHECKLIST = [
    {"kind": "預約", "task": "確認函館山纜車營運", "due": "2026-11-02", "due_is_hard": True,
     "origin": "D2・10/13", "detail": "年度整備可能延長，行前一週查官網。",
     "links": [{"label": "334.co.jp", "url": "https://334.co.jp/"}]},
    {"kind": "出發前確認", "task": "確認抵達航班", "due": "出發前"},
    {"kind": "打包", "task": "不帶任何肉製品入境"},
]

MEDIA = {"hak-goryokaku": {"photo": {"data": PNG, "width": 1, "height": 1},
                           "photo_attribution": {"author": "Wiki 使用者", "license": "CC-BY-SA-4.0",
                                                 "source_url": "https://commons.example/goryokaku"},
                           "photo_source": "wikimedia"}}


def _mv(mode, km=None, mins=None, basis="estimated", **kw):
    r = {"slot": "move", "text": kw.pop("text", "移動"), "mode": mode}
    if mode != "none":
        r.update(km=km, mins=mins, basis=basis)
        if basis == "estimated":
            r["estimate_method"] = "直線距離乘 1.4 估算"
        else:
            r["source_url"] = kw.pop("source_url", "https://bus.example/timetable")
    r.update(kw)
    return r


def _stop(slot, time, pid, text):
    return {"slot": slot, "time": time, "poi_id": pid, "text": text}


def _closing(rows, by_id):
    for r in rows:
        p = by_id.get(r.get("poi_id"))
        if r.get("time") and p and r["slot"] != "lodging":
            h = p["hours"]
            last = h.get("last_order") if r["slot"] == "meal" else h.get("last_entry")
            r["closing_status"] = closing_status(r["time"], h["close"], last,
                                                 max(30, h.get("typical_visit_mins") or 60))[0]
    return rows


def itinerary():
    by_id = {p["id"]: p for p in POIS}
    days = [
        {"date": "2026-10-12", "lodging": "hak-hotel", "theme": "落地先吃朝市",
         "theme_refs": ["hak-asaichi"],
         "rows": [_mv("taxi", 9, 25, text="機場搭計程車", **{"from": "函館空港"}),
                  _stop("meal", "12:00", "hak-asaichi", "朝市海鮮丼午餐；推薦活烏賊"),
                  _mv("walk", 0.9, 12, text="走回飯店")]},
        {"date": "2026-10-13", "lodging": "hak-hotel", "theme": "早市的蟹，山頂的夜",
         "theme_refs": ["hak-asaichi", "hak-yama"],
         "alternatives": [{"kind": "備案", "applies_to": "hak-yama", "trigger": "纜車停駛",
                           "fallback": "改上五稜郭塔看夜景", "poi_id": "hak-tower"}],
         "rows": [_mv("walk", 0.9, 12),
                  _stop("meal", "08:00", "hak-asaichi", "朝市蟹早餐"),
                  _mv("taxi", 7, 20),
                  _stop("visit", "10:00", "hak-goryokaku", "五稜郭公園散步"),
                  _mv("bus", 8, 30, basis="sourced", text="函館巴士"),
                  _stop("visit", "17:00", "hak-yama", "搭纜車上山看夜景"),
                  _mv("taxi", 3, 10),
                  {"slot": "lodging", "time": "19:30", "poi_id": "hak-hotel", "text": "飯店晚餐"},
                  _mv("none", text="晚餐就在飯店")]},
        {"date": "2026-10-14", "theme": "最後一碗海鮮丼", "theme_refs": ["hak-asaichi"],
         "rows": [_mv("walk", 0.9, 12),
                  _stop("meal", "08:00", "hak-asaichi", "最後一次朝市"),
                  _mv("taxi", 9, 25, text="前往機場", to="函館空港")]},
    ]
    for d in days:
        _closing(d["rows"], by_id)
    from tests.title_fixture import add_titles          # v1.1 topic 7
    return add_titles({"title": "函館三天", "checklist": copy.deepcopy(CHECKLIST), "days": days})


def brief():
    return {"slug": "2026-11-hakodate", "dates": {"start": "2026-10-12", "end": "2026-10-14"},
            "destination": {"country": "JP", "city": "函館", "local_lang": "ja"},
            "members": [{"name": "A"}], "base": {"name": "示意飯店", "district": "函館"},
            "must_do": [], "constraints": [], "preferences": {}, **brief_name_fields()}


def poi_map():
    """verified-pois + chosen lodging + media overlay, as tripwork-export-artifact assembles it."""
    from scripts.gate import poi_pool
    from scripts.media_merge import apply_media
    pm = poi_pool(copy.deepcopy(POIS), copy.deepcopy(ACCOMMODATIONS))
    return apply_media(pm, {"media": copy.deepcopy(MEDIA)})


def reader_kwargs():
    return {"brief": brief(), "accommodations": copy.deepcopy(ACCOMMODATIONS),
            "advisory": copy.deepcopy(ADVISORY), "legs": {"legs": []}}
