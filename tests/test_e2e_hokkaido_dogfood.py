from urllib.parse import unquote
from scripts.verify import normalize_and_validate_poi
from scripts.gate import run_gate
from scripts.export_gate import run_export_gate, run_html_gate
from scripts.render.html_page import render_html_page
from scripts.render.gmaps_links import maps_url

def _q(u):
    return unquote(u.split("query=", 1)[1])

def test_d1_lon_normalised_and_name_search():
    poi = {"id": "lv", "name_local": "ザ・レイクビュー TOYA 乃の風", "name_display": "乃の風",
           "name_zh": "乃之風度假村", "district": "洞爺湖温泉",
           "geocode": {"lat": 42.55, "lon": 140.78, "geocode_source": "cluster_fallback"}}
    out, reason = normalize_and_validate_poi(poi)
    assert reason is None
    assert out["geocode"]["lng"] == 140.78 and "lon" not in out["geocode"]
    assert _q(maps_url(out)) == "ザ・レイクビュー TOYA 乃の風 洞爺湖温泉"  # name search, not coords/town

def test_d1_town_name_rejected():
    poi = {"id": "bad", "name_local": "洞爺湖温泉", "district": "洞爺湖温泉",
           "geocode": {"lat": 42.55, "lng": 140.78}}
    _, reason = normalize_and_validate_poi(poi)
    assert reason is not None

def test_d2_five_lodgingless_nights_fail():
    days = [{"date": f"2026-07-0{i}", "rows": [{"slot": "meal", "text": "m"}]} for i in range(1, 7)]
    days.append({"date": "2026-07-07", "rows": [{"slot": "meal", "text": "m"}]})  # final day
    rep = run_gate([], {"days": days}, accommodations=None)
    assert rep["status"] == "fail"
    assert sum("no resolved lodging" in f for f in rep["failures"]) == 6  # days 1-6 overnight

def test_d3_ungloss_kana_fails_export_gate():
    # ジンギスカン is katakana (kana) with no （中文）gloss on its line -> hard-fail.
    # (Han-only terms like 馬車鉄道 are intentionally NOT flagged: Han overlaps ZH/JP.)
    md = "### D1\n\n| 時段 | 行程 |\n|---|---|\n| 12:00 | ジンギスカン |\n"
    rep = run_export_gate(md, [])
    assert rep["status"] == "fail"
    assert any("no （中文）gloss" in f for f in rep["failures"])
    # control: the same term WITH a gloss passes the japanese_glossed check
    md_ok = "### D1\n\n| 時段 | 行程 |\n|---|---|\n| 12:00 | ジンギスカン（成吉思汗烤肉） |\n"
    ok = run_export_gate(md_ok, [])
    assert not any("no （中文）gloss" in f for f in ok["failures"])

def test_d4_html_export_round_trips_gate():
    itin = {"title": "北海道", "days": [{"date": "2026-07-01", "label": "D1",
             "rows": [{"slot": "visit", "poi_id": "p", "text": "ジンギスカン（成吉思汗）"}]}]}
    pmap = {"p": {"id": "p", "name_display": "だるま", "name_local": "だるま",
                  "name_zh": "達摩", "district": "札幌", "geocode": {"lat": 43.0, "lng": 141.3}}}
    html = render_html_page(itin, pmap)
    assert run_html_gate(html, list(pmap.values()), min_days=1)["status"] == "pass"
