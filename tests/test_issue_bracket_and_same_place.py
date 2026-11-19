"""#28 one bracket at most; #27 a move row that goes nowhere gets no A->A route.
Both call the shipped renderers / gate (CLAUDE.md: guards call their subject)."""
from scripts.gate import gloss_notices, same_place_notices, address_notices, summary_notice
from scripts.render.centroid import _label
from scripts.render.gmaps_links import link_markdown, poi_label
from scripts.render.markdown import render_day_table


def test_a_plain_name_gets_its_gloss_in_one_bracket():
    assert poi_label({"name_display": "函館朝市", "name_zh": "函館早市"}) == "函館朝市（函館早市）"


def test_a_name_with_a_note_merges_the_gloss_into_that_bracket():
    p = {"name_display": "サンプルプレイス（車站直結購物中心）", "name_zh": "Sample Place 購物中心"}
    assert poi_label(p) == "サンプルプレイス（車站直結購物中心・Sample Place 購物中心）"
    assert "）（" not in link_markdown(dict(p, id="x"))
    assert _label(p) == poi_label(p)          # the centroid line says the same


def test_a_kana_note_keeps_the_gloss_rather_than_dropping_it():
    p = {"name_display": "サンプルストア(やきとり弁当)", "name_zh": "烤雞串便當店"}
    assert poi_label(p) == "サンプルストア（やきとり弁当・烤雞串便當店）"


def test_a_gloss_already_in_the_note_is_not_repeated():
    p = {"name_display": "サンプル（示意餐廳）", "name_zh": "示意餐廳"}
    assert poi_label(p) == "サンプル（示意餐廳）"


def test_no_gloss_or_same_gloss_leaves_the_name():
    assert poi_label({"name_display": "Tokyo Tower"}) == "Tokyo Tower"
    assert poi_label({"name_display": "東京", "name_zh": "東京"}) == "東京"


def _itin(rows):
    return {"days": [{"date": "2030-01-02", "label": "D1", "rows": rows}]}


def test_a_same_place_move_row_links_the_place_not_a_route():
    rows = [{"time": "09:35", "slot": "move", "mode": "none", "from": "示意駅", "to": "示意駅",
             "text": "劃位"},
            {"time": "10:00", "slot": "move", "mode": "rail", "from": "示意駅", "to": "サンプル駅",
             "text": "特急"}]
    md = render_day_table(_itin(rows)["days"][0], {})
    lines = [l for l in md.splitlines() if l.startswith("| 09:35") or l.startswith("| 10:00")]
    assert "maps/dir/" not in lines[0] and "maps/search/" in lines[0] and "→" not in lines[0]
    assert "maps/dir/" in lines[1]


def test_a_same_ends_row_without_mode_none_also_gets_no_route():
    rows = [{"time": "09:35", "slot": "move", "mode": "walk", "from": "示意駅 ", "to": "示意駅",
             "text": "站內"}]
    assert "maps/dir/" not in render_day_table(_itin(rows)["days"][0], {})


def test_the_gate_summarises_same_place_rows_in_one_line():
    rows = [{"time": "09:35", "slot": "move", "mode": "none", "text": "劃位"},
            {"time": "12:00", "slot": "move", "mode": "walk", "from": "A", "to": "A", "text": "x"},
            {"time": "13:00", "slot": "move", "mode": "walk", "from": "A", "to": "B", "text": "y"}]
    out = same_place_notices(_itin(rows))
    assert len(out) == 1 and out[0].startswith("2 ") and "transfer" in out[0]
    assert "13:00" not in out[0]


def test_the_gate_summarises_noted_names_in_one_line():
    by_id = {"a": {"name_display": "サンプル（說明）", "name_zh": "示意"},
             "b": {"name_display": "サンプル二（說明）", "name_zh": "示意二"},
             "c": {"name_display": "サンプル三（說明）"},             # no name_zh: nothing doubles
             "d": {"name_display": "Plain", "name_zh": "平"}}
    rows = [{"slot": "sight", "poi_id": k} for k in by_id]
    out = gloss_notices(_itin(rows), by_id)
    assert len(out) == 1 and out[0].startswith("2 ") and "a, b" in out[0]


def test_missing_addresses_are_one_line():
    by_id = {"a": {}, "b": {}, "c": {"address_local": "示意 1-1"}}
    out = address_notices(_itin([{"slot": "sight", "poi_id": k} for k in by_id]), by_id)
    assert len(out) == 1 and "a, b" in out[0] and "c" not in out[0].split(":")[1].split("--")[0]


def test_summary_notice_says_nothing_when_nothing_is_missing():
    assert summary_notice("x", []) == []
