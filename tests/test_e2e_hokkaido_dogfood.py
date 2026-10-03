from bs4 import BeautifulSoup
from urllib.parse import unquote
from scripts.verify import normalize_and_validate_poi
from scripts.gate import run_gate
from scripts.export_gate import run_export_gate, run_html_gate
from scripts.render.html_page import render_html_page
from scripts.render.gmaps_links import maps_url
from tests.mech_fixtures import rederive_kwargs, upgrade_to_v1

def _q(u):
    return unquote(u.split("query=", 1)[1])

def test_d1_lon_normalised_and_name_search():
    poi = {"id": "lv", "name_local": "ザ・レイクビュー TOYA 示の風", "name_display": "示の風",
           "name_zh": "示之風度假村", "district": "洞爺湖温泉",
           "geocode": {"lat": 42.55, "lon": 140.78, "geocode_source": "cluster_fallback"}}
    out, reason = normalize_and_validate_poi(poi)
    assert reason is None
    assert out["geocode"]["lng"] == 140.78 and "lon" not in out["geocode"]
    assert _q(maps_url(out)) == "ザ・レイクビュー TOYA 示の風 洞爺湖温泉"  # name search, not coords/town

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
    """G1/G3/G4/G5 closure, carried into the v1.0 reader: the pre-v1.0 grid, dashed
    grouping and boxed lodging line are retired with that layout (spec §6.3). What
    the closure protected still holds: the stop shows its embedded photo exactly
    once, the lodging is the day's anchor with a navigation button, and the page
    round-trips run_html_gate."""
    import re
    photo = {"data": "data:image/jpeg;base64,/9j/FULL",
             "thumb": {"data": "data:image/jpeg;base64,/9j/TH"}}
    attr = {"author": "A", "license": "CC0", "source_url": "https://a.example"}
    visit = {"id": "v", "name_display": "五稜郭", "name_zh": "五稜郭",
             "geocode": {"lat": 41.79, "lng": 140.75}, "photo": photo,
             "photo_attribution": attr, "photo_source": "wikimedia"}
    lodge = {"id": "lo", "name_display": "示の風", "name_zh": "示之風",
             "geocode": {"lat": 42.55, "lng": 140.78}, "photo": photo,
             "photo_attribution": attr, "photo_source": "wikimedia"}
    pmap = {"v": visit, "lo": lodge}
    itin = {"title": "北海道", "days": [{
        "date": "2026-07-01", "label": "D1｜函館", "lodging": "lo",
        "rows": [
            {"slot": "move", "mode": "taxi", "mins": 20, "km": 8, "text": "機場 → 函館"},
            {"time": "10:00", "slot": "visit", "poi_id": "v", "text": "五稜郭塔"},
            {"slot": "move", "mode": "walk", "mins": 10, "km": 0.6},
        ]}]}
    html = render_html_page(itin, pmap)
    assert html.count("data:image/jpeg;base64,/9j/FULL") == 1 and html.count('class="bpi ') == 1
    assert "回到 示之風" in html and 'class="anchor"' in html
    assert run_html_gate(html, list(pmap.values()), min_days=1)["status"] == "pass"


def test_d6_jargon_gate_e2e():
    """G6 closure: a deliverable carrying ALL the confirmed Hokkaido internal-jargon
    leaks ((hak-goryokaku), (lodge-toya-hotel), (sap-keio-plaza), must_do) is rejected
    by BOTH the markdown and HTML gates via no_internal_jargon; a clean one passes both."""
    from scripts.render.markdown import render_day_table

    def _jargon_passed(rep):
        return next(c["passed"] for c in rep["checks"] if c["name"] == "no_internal_jargon")

    pois = [{"id": "hak-goryokaku"}, {"id": "lodge-toya-hotel"}, {"id": "sap-keio-plaza"}]
    leaks = ("hak-goryokaku", "lodge-toya-hotel", "sap-keio-plaza", "must_do")
    dirty_day = {"label": "D1｜函館", "rows": [
        {"slot": "visit", "text": "改五稜郭タワー（五稜郭塔）(hak-goryokaku) 展望夜景"},
        {"slot": "lodging", "text": "投宿 示の風（示之風）(lodge-toya-hotel)"},
        {"slot": "meal", "text": "蟹会席（螃蟹會席）must_do"},
        {"slot": "visit", "text": "京王廣場(sap-keio-plaza)"},
    ]}

    md = render_day_table(dirty_day, {})
    md_rep = run_export_gate(md, pois)
    assert md_rep["status"] == "fail" and _jargon_passed(md_rep) is False
    for tok in leaks:
        assert any(tok in f and "leaked" in f for f in md_rep["failures"]), f"md {tok}"

    html = render_html_page({"title": "北海道", "days": [{"date": "2026-07-01", **dirty_day}]}, {})
    html_rep = run_html_gate(html, pois, min_days=1)
    assert html_rep["status"] == "fail" and _jargon_passed(html_rep) is False
    for tok in leaks:
        assert any(tok in f and "leaked" in f for f in html_rep["failures"]), f"html {tok}"

    # a clean deliverable (no id tokens, no must_do) passes both gates' jargon check.
    clean_day = {"label": "D1", "rows": [{"slot": "meal", "text": "蟹會席 至少一晚溫泉旅館"}]}
    assert _jargon_passed(run_export_gate(render_day_table(clean_day, {}), pois)) is True
    clean_html = render_html_page({"title": "T", "days": [{"date": "2026-07-01", **clean_day}]}, {})
    assert _jargon_passed(run_html_gate(clean_html, pois, min_days=1)) is True


def test_d8_canonical_hygiene_protects_all_renderers_e2e():
    """0.20.0: content hygiene (jargon + kana-gloss) now runs at the CANONICAL gate
    (run_gate), so a leak is blocked BEFORE any renderer runs. A dirty canonical
    itinerary fails run_gate on both checks; the cleaned one passes. (Its line-short
    half went with the LINE text, retired in v1.1.)"""
    import datetime

    from scripts.gate import run_gate

    pois = [{"id": "hak-goryokaku", "verify_status": "verified",
            "geocode": {"lat": 41.8, "lng": 140.7, "geocode_source": "nominatim"},
            "resolved_name": "NO_RESULT",
            # sourced business_status (TW-070, v0.34.0): run_gate now threads
            # `pois` into rederive_pois, so this record must re-derive its own
            # recorded 'verified' for `rc` (the clean/pass branch) below. as_of
            # computed at call time, never a literal.
            "business_status": {"status": "OPERATIONAL",
                                "source_url": "https://source.example/hak-goryokaku",
                                "as_of": datetime.date.today().isoformat()},
            "sources": [{"url": "https://a.example/hak-goryokaku", "lang": "zh"},
                        {"url": "https://b.example/hak-goryokaku", "lang": "en"}]}]
    dirty = {"title": "北海道", "days": [{"date": "2026-07-01", "label": "D1", "rows": [
        {"slot": "meal", "poi_id": "hak-goryokaku", "text": "午餐(hak-goryokaku) must_do"},   # jargon
        {"slot": "visit", "poi_id": "hak-goryokaku", "text": "スタバ 喝咖啡"},                  # ungloss kana (paren-free line)
    ]}]}
    r = run_gate(pois, dirty, advisory={"items": []})
    assert r["status"] == "fail"
    assert {"name": "no_internal_jargon", "passed": False} in r["checks"]
    assert {"name": "japanese_glossed", "passed": False} in r["checks"]

    clean = {"title": "北海道", "days": [{"date": "2026-07-01", "label": "D1", "rows": [
        {"slot": "meal", "poi_id": "hak-goryokaku", "text": "午餐"},
        {"slot": "visit", "poi_id": "hak-goryokaku", "text": "夜景 スターバックス（星巴克）"},
    ]}]}
    upgrade_to_v1(pois, clean)     # v1.0 reader data: chain, theme, source records
    rc = run_gate(pois, clean, advisory={"items": []}, **rederive_kwargs())
    assert rc["status"] == "pass", rc["failures"]


def test_d7_move_directions_e2e():
    """G2 closure: a move row with from/to renders an A→B directions chip in BOTH the
    HTML and the markdown deliverables (no &travelmode), both pass their gates; a move
    row WITHOUT from/to falls back to plain text (backward-compat, no fabricated link)."""
    from scripts.render.markdown import render_day_table

    poi = {"id": "v", "name_display": "五稜郭", "name_zh": "五稜郭", "name_local": "五稜郭",
           "geocode": {"lat": 41.79, "lng": 140.75}}
    day = {"date": "2026-07-01", "label": "D1｜函館", "rows": [
        {"slot": "move", "mode": "rail", "mins": 20, "km": 7, "text": "午後抵達",
         "from": "函館空港", "to": "函館駅"},
        {"time": "10:00", "slot": "visit", "poi_id": "v", "text": "五稜郭塔"},
        {"slot": "move", "mode": "walk", "mins": 10, "text": "步行接駁"},   # no from/to → fallback
    ]}
    pmap = {"v": poi}

    # v1.0 reader (spec §6.3): a move row is mode + minutes; navigation lives on each
    # stop's 導航 button, so the HTML carries no A→B directions chip any more.
    html = render_html_page({"title": "北海道", "days": [day]}, pmap)
    assert "從 函館空港 出發" in html and "travelmode" not in html
    # v1.1 (user): a 移動列 is mode + minutes + distance; its note is not shown
    legs = [l.get_text(" ", strip=True) for l in BeautifulSoup(html, "html.parser").select(".leg")]
    assert legs[0].startswith("電車 20 分") and "7 km" in legs[0] and legs[1].startswith("步行 10 分")
    assert "午後抵達" not in html and "步行接駁" not in html
    assert run_html_gate(html, list(pmap.values()), min_days=1)["status"] == "pass"

    md = render_day_table(day, pmap)
    assert "[🚆 函館空港→函館駅](https://www.google.com/maps/dir/?api=1&origin=" in md
    assert "[五稜郭（五稜郭）](https://www.google.com/maps/search/" not in md  # zh==display: no gloss
    assert "[五稜郭](https://www.google.com/maps/search/" in md               # point poi link
    assert "步行接駁" in md and "travelmode" not in md
    assert run_export_gate(md, list(pmap.values()))["status"] == "pass"
