"""v2.1.0 §10: `tripwork.py table` prints verified places as a Markdown table, with the
fields the user names or a preset; hours carry an opening time (spec #21, the user's A)."""
import json
import os
import pathlib

import pytest
import yaml

from scripts import survey_table as st
from scripts.paths import artifact_path
from tests.mech_fixtures import CORPUS_TRIPS, corpus_dir

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_hours_open_close_last_order():
    assert st.hours_text({"open": "11:00", "close": "21:00", "last_order": "20:30"}) == "11:00–21:00（最後點餐 20:30）"


def test_hours_last_entry():
    assert st.hours_text({"open": "09:00", "close": "17:00", "last_entry": "16:30"}) == "09:00–17:00（最後入場 16:30）"


def test_hours_without_open():
    assert st.hours_text({"close": "21:00"}) == "～21:00"


def test_hours_no_fixed_close():
    assert st.hours_text({"no_fixed_close": True}) == "全天開放"


def test_hours_missing():
    assert st.hours_text(None) == "" and st.hours_text({}) == ""


def _poi(**kw):
    base = {"id": "p", "name_display": "示意食堂", "name_local": "示意食堂", "category": "restaurant",
            "district": "示意區", "verify_status": "verified",
            "sources": [{"url": "https://a.example/p", "lang": "zh-TW"}]}
    return {**base, **kw}


DATES = ["2030-01-07", "2030-01-08"]           # a Monday and a Tuesday


def test_table_blank_cells_for_missing_hours():
    row = st.render_table([_poi()], ["名稱", "營業時間", "公休日"], {"dates": {"start": DATES[0], "end": DATES[1]}})
    assert row.splitlines()[-1] == "| 示意食堂 |  |  |"


def test_closed_day_marked_with_dates():
    assert st.closed_text(_poi(closed_days=["tuesday"]), DATES, None) == "1/8（二）公休"


def test_closed_days_without_dates():
    assert st.closed_text(_poi(closed_days=["tuesday", "public_holiday"]), None, None) == "週二、國定假日公休"


def test_public_holiday_without_calendar_says_unchecked():
    assert st.closed_text(_poi(closed_days=["public_holiday"]), DATES, None) == "國定假日公休（這幾天是否假日未查）"


def test_public_holiday_with_calendar():
    cal = {"holidays": [{"date": DATES[0], "name_display": "示意節"}]}
    assert st.closed_text(_poi(closed_days=["public_holiday"]), DATES, cal) == "1/7（一）公休（示意節）"


def test_food_preset_excludes_hotels_includes_dessert():
    pois = [_poi(id=c, name_display=c, category=c) for c in ("dessert", "breakfast", "drink", "lodging", "sight")]
    names = st.rows_for(pois, "吃的")
    assert [p["category"] for p in names] == ["breakfast", "dessert", "drink"]
    assert [p["category"] for p in st.rows_for(pois, "景點")] == ["sight"]


def _categories(paths):
    out = set()
    for f in paths:
        for p in (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("pois") or []:
            if isinstance(p, dict) and p.get("category"):
                out.add(str(p["category"]))
    return out


def test_every_corpus_category_has_a_group():
    seen = _categories(corpus_dir(t) / "verified-pois.yaml" for t in CORPUS_TRIPS)
    assert seen - set(st.CATEGORY_GROUP) == set()


def test_every_workspace_category_has_a_group():
    ws = pathlib.Path(os.environ.get("TRIPWORK_WORKSPACE", ROOT.parent / "tripwork-workspace")) / "trips"
    if not ws.is_dir():
        pytest.skip("no consumer workspace")
    seen = _categories(ws.glob("*/**/verified-pois.yaml"))
    assert seen - set(st.CATEGORY_GROUP) == set()


def test_only_verified_places_are_listed():
    pois = [_poi(id="a", name_display="甲"), _poi(id="b", name_display="乙", verify_status="unverified")]
    assert [p["id"] for p in st.rows_for(pois, None)] == ["a"]


def test_sorted_by_rating_then_name():
    pois = [_poi(id="a", name_display="B 小館"), _poi(id="b", name_display="A 小館"),
            _poi(id="c", name_display="丙", rating={"platform": "示意評分", "score": 4.5, "count": 80,
                                                    "source_url": "https://r.example/c", "as_of": "2030-01-01"})]
    assert [p["id"] for p in st.rows_for(pois, None)] == ["c", "b", "a"]


def test_unknown_field_is_a_usage_error(tmp_path, capsys):
    t = _trip(tmp_path)
    assert st.main([str(t), "座位數"]) == 2
    assert "座位數" in capsys.readouterr().err


def _trip(tmp_path):
    t = tmp_path / "trips" / "t"
    for name, doc in (("trip-brief.yaml", {"slug": "t", "mode": "survey", "short_name": "示意清單",
                                           "destination": {"country": "TW", "city": "示意區", "local_lang": "zh-TW"},
                                           "categories": ["吃的"]}),
                      ("verified-pois.yaml", {"pois": [_poi(hours={"open": "11:00", "close": "21:00"})]})):
        p = artifact_path(t, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return t


def test_main_prints_the_food_preset(tmp_path, capsys):
    assert st.main([str(_trip(tmp_path)), "吃的"]) == 0
    out = capsys.readouterr().out
    assert "| 名稱 |" in out and "11:00–21:00" in out


def test_main_out_writes_the_file(tmp_path):
    out = tmp_path / "清單.md"
    assert st.main([str(_trip(tmp_path)), "名稱", "營業時間", "--out", str(out)]) == 0
    assert "11:00–21:00" in out.read_text(encoding="utf-8")


def test_table_help_lists_usage(capsys):
    from scripts import tripwork
    assert tripwork.main(["table", "-h"]) == 0
    assert "table" in capsys.readouterr().out


def test_hours_open_in_schema():
    s = json.loads((ROOT / "schemas" / "verified-pois.schema.json").read_text(encoding="utf-8"))
    assert s["properties"]["pois"]["items"]["properties"]["hours"]["properties"]["open"] == {"type": "string"}
