"""A made-up 3-day Tokyo trip with every kind of reservation, shared by the reservation tests.

Public landmarks, placeholder venues (示意), fictional flight numbers and booking numbers.
Two home legs (a flight and the airport line), one booked dinner, one dinner left open
(自理), one lunch still to book, a booked hotel and a booked tower ticket.
"""
import copy

from tests.reader_fixture import _mv, _poi, _stop

POIS = [
    _poi("kappo", "押上サンプル割烹", "押上示意割烹", "food", 35.7098, 139.8120,
         {"close": "22:00", "last_order": "21:00", "typical_visit_mins": 90, "as_of": "2026-04-01"}),
    _poi("izakaya", "浅草サンプル居酒屋", "淺草示意居酒屋", "food", 35.7125, 139.7960,
         {"close": "23:00", "last_order": "22:30", "typical_visit_mins": 90, "as_of": "2026-04-01"}),
    _poi("yoshoku", "上野サンプル洋食", "上野示意洋食", "food", 35.7105, 139.7750,
         {"close": "21:00", "last_order": "20:30", "typical_visit_mins": 60, "as_of": "2026-04-01"}),
    _poi("skytree", "東京スカイツリー", "東京晴空塔", "sight", 35.7101, 139.8107,
         {"close": "22:00", "last_entry": "21:00", "typical_visit_mins": 90, "as_of": "2026-04-01"}),
    _poi("demo-hotel", "浅草サンプルホテル", "淺草示意飯店", "lodging", 35.7113, 139.7953,
         {"close": "23:59", "typical_visit_mins": 60, "as_of": "2026-04-01"}),
]

LEGS = {"legs": [
    {"from": "桃園機場", "to": "羽田空港", "kind": "home", "mode": "flight", "status": "ok",
     "service": "示意航空 SA 101", "depart": "08:50", "arrive": "13:00", "duration_mins": 190, "km": 2190,
     "sources": [{"url": "https://air.example/sa101", "official": True}]},
    {"from": "羽田空港", "to": "淺草", "kind": "home", "mode": "rail", "status": "ok",
     "service": "京急線直通淺草線", "duration_mins": 45, "km": 20,
     "sources": [{"url": "https://rail.example/keikyu", "official": True}]},
    {"from": "羽田空港", "to": "桃園機場", "kind": "home", "mode": "flight", "status": "ok",
     "service": "示意航空 SA 102", "depart": "14:30", "arrive": "17:20", "duration_mins": 170, "km": 2190,
     "sources": [{"url": "https://air.example/sa102", "official": True}]},
]}


def itinerary():
    return {"title": "東京三天", "checklist": [], "days": [
        {"date": "2026-05-12", "lodging": "demo-hotel", "rows": [
            dict(_mv("flight", 2190, 190, basis="sourced", text="示意航空 SA 101",
                     source_url="https://air.example/sa101"), leg_index=0, time="08:50"),
            dict(_mv("rail", 20, 45, basis="sourced", text="京急線直通淺草線",
                     source_url="https://rail.example/keikyu"), leg_index=1),
            {"slot": "lodging", "time": "13:30", "poi_id": "demo-hotel", "text": "放行李"},
            _stop("meal", "18:30", "izakaya", "居酒屋晚餐")]},
        {"date": "2026-05-13", "lodging": "demo-hotel", "rows": [
            _stop("meal", "13:00", "yoshoku", "炸豬排午餐"),
            _stop("visit", "17:00", "skytree", "看夕陽轉夜景"),
            _stop("meal", "19:00", "kappo", "會席晚餐"),
            _mv("taxi", 2.5, 10, text="計程車回飯店")]},
        {"date": "2026-05-14", "rows": [
            dict(_mv("rail", 20, 45, basis="sourced", text="淺草線直通京急線",
                     source_url="https://rail.example/keikyu"), **{"from": "淺草", "to": "羽田空港"}),
            dict(_mv("flight", 2190, 170, basis="sourced", text="示意航空 SA 102",
                     source_url="https://air.example/sa102"), leg_index=2, time="14:30")]},
    ]}


RESERVATIONS = {"reservations": [
    {"date": "2026-05-12", "from": "桃園機場", "to": "羽田空港", "status": "booked", "ref": "K7Q2PX",
     "details": [{"label": "座位", "value": "32A・32B・32C"}, {"label": "行李", "value": "每人託運 23 kg"}]},
    {"date": "2026-05-12", "from": "羽田空港", "to": "淺草", "status": "none",
     "details": [{"label": "付款", "value": "刷 IC 卡，不用買票"}]},
    {"date": "2026-05-12", "lodging": "demo-hotel", "status": "booked", "ref": "HB48213907",
     "details": [{"label": "入住", "value": "15:00 起"}, {"label": "房型", "value": "三人房，含早餐"}]},
    {"date": "2026-05-12", "poi_id": "izakaya", "status": "self",
     "details": [{"label": "備註", "value": "這餐自己決定吃哪家，這家是推薦，換別家也可以"}]},
    {"date": "2026-05-13", "poi_id": "yoshoku", "status": "todo",
     "details": [{"label": "怎麼訂", "value": "官網開放前 30 天線上預約"}, {"label": "人數", "value": "3 位"}]},
    {"date": "2026-05-13", "poi_id": "skytree", "status": "booked", "ref": "TK7730X1",
     "details": [{"label": "時段", "value": "17:00 入場"}, {"label": "張數", "value": "3 張"}]},
    {"date": "2026-05-13", "poi_id": "kappo", "status": "booked", "ref": "RSV-58213",
     "details": [{"label": "人數", "value": "3 位"}, {"label": "套餐", "value": "會席套餐"},
                 {"label": "取消", "value": "5/10 前免費取消"}]},
    {"date": "2026-05-14", "from": "淺草", "to": "羽田空港", "status": "none"},
    {"date": "2026-05-14", "from": "羽田空港", "to": "桃園機場", "status": "booked", "ref": "M3R8TZ",
     "details": [{"label": "座位", "value": "41A・41B・41C"}]},
]}

REFS = ("K7Q2PX", "HB48213907", "TK7730X1", "RSV-58213", "M3R8TZ")


def poi_map():
    return {p["id"]: copy.deepcopy(p) for p in POIS}


def reservations():
    return copy.deepcopy(RESERVATIONS)


def legs():
    return copy.deepcopy(LEGS)
