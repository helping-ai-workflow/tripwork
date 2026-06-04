"""End-to-end calendar closure: a single fixture exercising both axes at once.

Mirrors the real Seoul case — a public holiday (Buddha's Birthday + its
Monday substitute, high crowd) and a POI with a fixed weekly closure
(Gyeongbokgung closed Tuesdays). Asserts synthesis-stage logic would:
  - hard-avoid scheduling the POI on its closed day,
  - allow it on open days,
  - flag the holiday day as high-crowd.
"""
import pathlib, json, yaml
import jsonschema
from scripts.calendar import poi_closed_on, is_high_crowd
from scripts.hours import closing_status

SCHEMAS = pathlib.Path(__file__).resolve().parent.parent / "schemas"
FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "e2e-trip"


def _load(p):
    return yaml.safe_load(open(p, encoding="utf-8"))


def test_calendar_fixture_schema_valid():
    schema = json.load(open(SCHEMAS / "calendar.schema.json"))
    jsonschema.validate(_load(FIX / "calendar.yaml"), schema)


def test_holiday_day_is_high_crowd():
    cal = _load(FIX / "calendar.yaml")
    assert is_high_crowd("2026-05-25", cal) is True   # substitute holiday Monday


def test_closed_poi_not_scheduled_on_closed_day():
    cal = _load(FIX / "calendar.yaml")
    pois = {p["id"]: p for p in _load(FIX / "verified-pois-calendar.yaml")["pois"]}
    gbg = pois["gyeongbokgung"]
    # Tue 2026-05-26 — closed; must be hard-avoided by synthesis
    closed, reason = poi_closed_on(gbg, "2026-05-26", cal)
    assert closed is True and "tuesday" in reason.lower()


def test_closed_poi_open_on_holiday_day():
    cal = _load(FIX / "calendar.yaml")
    pois = {p["id"]: p for p in _load(FIX / "verified-pois-calendar.yaml")["pois"]}
    gbg = pois["gyeongbokgung"]
    closed, _ = poi_closed_on(gbg, "2026-05-25", cal)   # Mon holiday, open
    assert closed is False


def _pois():
    return {p["id"]: p for p in _load(FIX / "verified-pois-calendar.yaml")["pois"]}


def test_buffer_late_restaurant_slot_after_last_order():
    # Scheduling Hwangsaengga at 20:45 — past its 20:30 last order -> must reschedule
    h = _pois()["hwangsaengga"]["hours"]
    status, _ = closing_status("20:45", h["close"], last_call=h["last_order"],
                               need_mins=h["typical_visit_mins"])
    assert status == "after_last_call"


def test_buffer_late_sight_slot_after_last_entry():
    # Gyeongbokgung at 16:50 — past 17:00 last entry? no, 16:50 < 17:00 but only
    # 70 min before 18:00 close vs 90 needed -> tight, synthesis warns / moves earlier
    h = _pois()["gyeongbokgung"]["hours"]
    status, _ = closing_status("16:50", h["close"], last_call=h["last_entry"],
                               need_mins=h["typical_visit_mins"])
    assert status == "tight"


def test_buffer_good_slot_ok():
    h = _pois()["hwangsaengga"]["hours"]
    status, _ = closing_status("18:30", h["close"], last_call=h["last_order"],
                               need_mins=h["typical_visit_mins"])
    assert status == "ok"
