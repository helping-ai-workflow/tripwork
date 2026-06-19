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
    rep = run_gate([], {"days": days}, accommodations=None, advisory={"items": []})
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


def test_d5_grid_layout_e2e():
    """G1/G3/G4/G5 closure: one day exercising the grid, the in-cell .altbox 備案
    (with NO thumbnail even though its poi has a photo), the look-ahead dashed grouping,
    and the boxed lodging line — and the whole page still round-trips run_html_gate."""
    import re
    photo = {"data": "data:image/jpeg;base64,/9j/FULL",
             "thumb": {"data": "data:image/jpeg;base64,/9j/TH"}}
    attr = {"author": "A", "license": "CC0", "source_url": "https://a.example"}
    visit = {"id": "v", "name_display": "五稜郭", "name_zh": "五稜郭",
             "geocode": {"lat": 41.79, "lng": 140.75}, "photo": photo,
             "photo_attribution": attr, "photo_source": "wikimedia"}
    lodge = {"id": "lo", "name_display": "乃の風", "name_zh": "乃之風",
             "geocode": {"lat": 42.55, "lng": 140.78}, "photo": photo,
             "photo_attribution": attr, "photo_source": "wikimedia"}
    pmap = {"v": visit, "lo": lodge}
    itin = {"title": "北海道", "days": [{
        "date": "2026-07-01", "label": "D1｜函館", "lodging": "lo",
        "rows": [
            {"slot": "move", "text": "機場 → 函館"},
            {"time": "10:00", "slot": "visit", "poi_id": "v", "text": "五稜郭塔"},
            {"slot": "activity", "poi_id": "v", "text": "▸ 備案｜強風改五稜郭夜景"},
            {"slot": "meal", "text": "晚餐｜海鮮"},
        ]}]}
    html = render_html_page(itin, pmap)

    # G1 grid + no emoji column
    assert "grid-template-columns:48px 1fr 64px" in html
    assert 'class="emo"' not in html
    # G5 boxed lodging + right-aligned lodge thumb
    assert "background:#f0f9fb" in html
    lodge_seg = html.split('class="lodge"', 1)[1].split("</div>", 1)[0]
    assert 'class="thumb"' in lodge_seg
    # G3 in-cell altbox 備案 with empty thumb cell and NO <img> in that <li>
    alt_li = re.search(r'<li class="altrow[^"]*">.*?</li>', html, re.S).group(0)
    assert '<span class="bd"><span class="altbox">' in alt_li
    assert alt_li.endswith('<span class="thcol"></span></li>')
    assert "<img" not in alt_li               # alt row never gets a thumbnail
    # G4 dashed grouping over [move, visit, alt, meal]
    classes = re.findall(r'<li class="([^"]*)">', html)
    assert "dashed" in classes[0]             # move→visit  (real→real)
    assert "dashed" not in classes[1]         # visit→alt   (real→alt)
    assert "dashed" in classes[2]             # alt→meal    (alt→real)
    assert "dashed" not in classes[3]         # meal→last
    # whole page still passes the export gate
    assert run_html_gate(html, list(pmap.values()), min_days=1)["status"] == "pass"
