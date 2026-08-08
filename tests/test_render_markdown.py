# tests/test_render_markdown.py
from scripts.render.markdown import render_day_table, md_escape

def test_day_table_links_pois():
    day = {"label": "Day 4", "rows": [
        {"time": "13:30", "slot": "meal", "poi_id": "odari", "text": "醬蟹"},
        {"time": "18:20", "slot": "activity", "text": "夜景"},
    ]}
    poi_map = {"odari": {"name_local": "오다리집", "name_display": "烏達里家"}}
    md = render_day_table(day, poi_map)
    assert "### Day 4" in md
    assert "| 13:30 |" in md
    assert "[烏達里家](https://www.google.com/maps/search/?api=1&query=" in md
    assert "夜景" in md  # row with no POI still renders

def test_day_table_header_row_present():
    md = render_day_table({"label": "Day 1", "rows": []}, {})
    assert "| 時段 | 行程 |" in md

def test_md_escape_escapes_dollar_and_pipe():
    assert md_escape("$180-260") == "\\$180-260"
    assert md_escape("a|b") == "a\\|b"
    assert md_escape("x") == "x"  # plain text untouched

def test_day_table_escapes_price_in_free_text():
    day = {"label": "Day 1", "rows": [{"time": "12:00", "slot": "meal", "text": "午餐 $180-260"}]}
    md = render_day_table(day, {})
    assert "\\$180-260" in md
    assert "$180" not in md.replace("\\$180", "")  # no bare $ remains

def test_day_table_appends_official_source_link():
    day = {"label": "Day 1", "rows": [{"time": "13:00", "slot": "meal", "poi_id": "ferg", "text": "漢堡"}]}
    poi_map = {"ferg": {
        "name_local": "Fergburger", "name_display": "Fergburger",
        "sources": [
            {"url": "https://review.example", "lang": "en"},
            {"url": "https://fergburger.com", "lang": "en", "official": True},
        ],
    }}
    md = render_day_table(day, poi_map)
    assert "[Fergburger](https://www.google.com/maps/search/?api=1&query=Fergburger)" in md
    assert "· [官網](https://fergburger.com)" in md  # official, not the review url

def test_day_table_falls_back_to_first_source_when_no_official():
    day = {"label": "Day 1", "rows": [{"time": "13:00", "slot": "meal", "poi_id": "x", "text": "漢堡"}]}
    poi_map = {"x": {"name_local": "X", "name_display": "X",
                     "sources": [{"url": "https://only.example", "lang": "en"}]}}
    md = render_day_table(day, poi_map)
    assert "· [官網](https://only.example)" in md

def test_day_table_no_source_link_when_poi_has_no_sources():
    day = {"label": "Day 1", "rows": [{"time": "13:00", "slot": "activity", "poi_id": "y", "text": "夜景"}]}
    poi_map = {"y": {"name_local": "Y", "name_display": "Y"}}
    md = render_day_table(day, poi_map)
    assert "官網" not in md

def test_day_table_unresolvable_poi_id_renders_text_only():
    day = {"label": "Day 1", "rows": [{"time": "13:00", "slot": "meal", "poi_id": "ghost", "text": "午餐"}]}
    md = render_day_table(day, {})
    assert "午餐" in md
    assert "官網" not in md


def test_markdown_move_row_directions_link():   # G2
    day = {"label": "D1", "rows": [
        {"slot": "move", "text": "午後抵達", "from": "函館空港", "to": "函館駅"},
    ]}
    md = render_day_table(day, {})
    assert "[🚆 函館空港→函館駅](https://www.google.com/maps/dir/?api=1&origin=" in md
    assert "travelmode" not in md
    assert "午後抵達" in md

def test_markdown_move_row_without_from_to_plain():   # G2 backward-compat
    day = {"label": "D1", "rows": [{"slot": "move", "text": "機場接駁"}]}
    md = render_day_table(day, {})
    assert "maps/dir" not in md
    assert "機場接駁" in md

def test_markdown_move_row_poi_still_links_poi():   # G2 — move w/o endpoints but w/ poi → poi link
    day = {"label": "D1", "rows": [{"slot": "move", "poi_id": "p", "text": "搭巴士"}]}
    md = render_day_table(day, {"p": {"name_local": "JR函館駅", "name_display": "JR函館駅"}})
    assert "maps/dir" not in md
    assert "[JR函館駅](https://www.google.com/maps/search/" in md

def test_markdown_move_row_with_poi_shows_poi_link_and_official():   # review finding-2
    # a move row with from/to AND a poi_id must STILL surface the poi name + official
    # source, so the export-gate bookable check can locate the row (no silent evasion).
    day = {"label": "D1", "rows": [
        {"slot": "move", "poi_id": "stn", "text": "搭特急", "from": "札幌", "to": "函館"}]}
    poi = {"name_local": "JR函館駅", "name_display": "JR函館駅",
           "sources": [{"url": "https://jrhokkaido.co.jp", "official": True}]}
    md = render_day_table(day, {"stn": poi})
    assert "[🚆 札幌→函館](https://www.google.com/maps/dir/" in md   # directions chip still leads
    assert "JR函館駅" in md                                          # poi name present
    assert "· [官網](https://jrhokkaido.co.jp)" in md               # official source link present


def test_poi_cell_source_url_escapes_paren():   # TW-022
    from scripts.render.markdown import render_day_table
    day = {"label": "D", "rows": [{"time": "12:00", "slot": "meal", "poi_id": "x", "text": "t"}]}
    poi_map = {"x": {"name_local": "x", "name_display": "x",
                     "sources": [{"url": "https://e.example/a(b)c", "official": True}]}}
    md = render_day_table(day, poi_map)
    assert "(b)" not in md.split("官網")[1][:40]   # ')' in url must not break the link


from scripts.render.markdown import render_markdown_page

ITIN = {
    "title": "嘉義 3 天 2 夜自駕",
    "days": [{"date": "2026-08-29", "label": "週六·三重出發 → 嘉義",
              "lodging": "zhaopin-hotel",
              "rows": [{"time": "11:30", "slot": "meal", "poi_id": "ahong",
                        "text": "在地排隊名店"}]}],
    "contingency": [
        {"trigger": "颱風/大雨", "fallback": "戶外改室內：南院常設展廳、花磚"},
        {"trigger": "阿宏師撲空", "note": "來源標週一二休",
         "fallback": "改噴水雞肉飯小雅旗艦店"},
    ],
    "checklist": ["訂房｜兆品酒店嘉義，2 晚 1 房"],
}
POIS = {
    "ahong": {"id": "ahong", "name_display": "阿宏師火雞肉飯", "district": "嘉義市東區",
              "sources": [{"url": "https://blog.example.tw/a", "official": True}]},
    "zhaopin-hotel": {"id": "zhaopin-hotel", "name_display": "兆品酒店嘉義",
                      "district": "嘉義市西區", "sources": []},
}
COST = {"currency": "TWD", "as_of": "2026-08-07", "total": 12700,
        "line_items": [{"category": "lodging", "label": "兆品酒店嘉義（2晚）", "amount": 5000},
                       {"category": "transport", "label": "三重→嘉義 油資+國道", "amount": 1000}]}


def test_render_markdown_page_is_idempotent():
    a = render_markdown_page(ITIN, POIS, COST)
    b = render_markdown_page(ITIN, POIS, COST)
    assert a == b
    assert a.endswith("\n") and not a.endswith("\n\n")


def test_every_section_is_emitted_and_data_driven():
    out = render_markdown_page(ITIN, POIS, COST)
    assert "# 嘉義 3 天 2 夜自駕" in out
    assert "### 週六·三重出發 → 嘉義" in out
    assert "**宿**：" in out and "兆品酒店嘉義" in out
    assert "## 備案 / Contingency" in out
    assert "颱風/大雨" in out and "戶外改室內" in out
    assert "（來源標週一二休）" in out          # note rendered when present
    assert "## 出發前檢查清單" in out and "兆品酒店嘉義，2 晚 1 房" in out
    assert "## 費用估算" in out and "12,700" in out and "2026-08-07" in out


def test_sections_are_omitted_when_their_data_is_absent():
    """Proves the page is data-driven, not a template with holes."""
    bare = {"title": "t", "days": ITIN["days"]}
    out = render_markdown_page(bare, POIS, None)
    assert "## 備案" not in out
    assert "## 出發前檢查清單" not in out
    assert "## 費用估算" not in out


def test_output_passes_the_export_gate():
    # run_export_gate's `pois` arg is a LIST of poi dicts (its docstring, and every
    # other call site in the suite, e.g. test_e2e_hokkaido_dogfood.py:194) — NOT
    # the {poi_id: poi_dict} map render_markdown_page's poi_map wants. The brief's
    # draft passed POIS (the map) to both; fixed here to list(POIS.values()).
    from scripts.export_gate import run_export_gate
    rep = run_export_gate(render_markdown_page(ITIN, POIS, COST), list(POIS.values()), min_days=1)
    assert rep["status"] == "pass", rep["failures"]


def test_itinerary_schema_accepts_contingency(tmp_path):
    from scripts.validate_artifact import validate_file
    p = tmp_path / "itinerary.yaml"
    p.write_text(
        "days:\n"
        "  - date: '2026-08-29'\n"
        "    rows: []\n"
        "contingency:\n"
        "  - trigger: 颱風/大雨\n"
        "    fallback: 戶外改室內\n",
        encoding="utf-8",
    )
    assert validate_file(str(p))[0] == 0


def test_contingency_text_reaches_the_canonical_hygiene_scan():
    """The technical reason the AI-tone gate is bound to TW-069: without this,
    the contingency block — the largest single source of bold-label list items in
    the corpus — is invisible to every canonical check."""
    from scripts.gate import _itinerary_text
    text = _itinerary_text({"days": [], "contingency": [
        {"trigger": "颱風", "fallback": "改室內——南院常設展"}]})
    assert "颱風" in text and "南院常設展" in text


def test_home_leg_move_row_carries_its_own_endpoints():   # TW-069 Step 5b
    """A `kind: home` leg's classify_leg verdict is already re-derived (run_gate)
    and its fare already summed (cost-rollup), but until itinerary-synthesis places
    it as a first-class move row nothing puts it in front of the reader — the
    remaining gap is purely about rendering, not about legs-awareness. This proves
    the render side of that gap is closed: once a day's row carries the home leg's
    OWN endpoints (day 1 for the outbound leg, the last day for the return leg, per
    the updated SKILL.md), it renders as an A→B directions link, not text-buried."""
    home_leg = {"from": "三重", "to": "嘉義市", "kind": "home", "mode": "drive",
                "duration_mins": 190, "status": "ok"}
    day1 = {"label": "Day 1", "rows": [
        {"slot": "move", "from": home_leg["from"], "to": home_leg["to"],
         "text": "自駕南下"},
    ]}
    md = render_day_table(day1, {})
    assert f"[🚆 {home_leg['from']}→{home_leg['to']}]" in md
    assert "自駕南下" in md
