"""v1.0 P1 — 每日移動鏈、備案、每日短主題（spec §4.1 / §4.4 / §4.8）。"""
import pytest

from scripts.day_chain import (alternative_failures, alternative_line, chain_failures,
                               legacy_failures, move_record_failures, theme_failures)
from scripts.gate import run_gate
from tests.mech_fixtures import build_gate_inputs, rederive_kwargs

DATE = "2026-10-13"


def _mv(**kw):
    row = {"slot": "move", "text": "移動", "mode": "walk", "mins": 10, "km": 0.6,
           "basis": "estimated", "estimate_method": "步行 4.5 km/h 估算"}
    row.update(kw)
    return {k: v for k, v in row.items() if v is not None}


def _stop(pid, slot="visit", time="10:00"):
    return {"slot": slot, "time": time, "poi_id": pid, "text": "參觀"}


def _day(rows, **kw):
    d = {"date": DATE, "rows": rows}
    d.update(kw)
    return d


# ---- chain structure -------------------------------------------------------

def test_a_complete_chain_has_no_failures():
    itin = {"days": [_day([_mv(), _stop("a"), _mv(), _stop("b"), _mv()])]}
    assert chain_failures(itin) == []


def test_a_day_that_does_not_start_with_a_move_breaks_the_chain():
    f = chain_failures({"days": [_day([_stop("a"), _mv()])]})
    assert any(x.startswith(f"day chain broken: {DATE} row 0 ") for x in f), f


def test_a_day_that_does_not_end_with_a_move_breaks_the_chain():
    f = chain_failures({"days": [_day([_mv(), _stop("a")])]})
    assert any(x.startswith(f"day chain broken: {DATE} row 1 ") for x in f), f


def test_two_adjacent_stops_break_the_chain():
    f = chain_failures({"days": [_day([_mv(), _stop("a"), _stop("b"), _mv()])]})
    assert any("rows 1 and 2 are adjacent stops" in x for x in f), f


def test_consecutive_moves_are_a_legal_multi_leg_transfer():
    rows = [_mv(), _mv(mode="rail"), _stop("a"), _mv()]
    assert chain_failures({"days": [_day(rows)]}) == []


def test_a_stop_without_poi_id_is_a_failure():
    row = {"slot": "meal", "time": "12:00", "text": "山麓食堂 午餐"}
    f = chain_failures({"days": [_day([_mv(), row, _mv()])]})
    assert f == [f"chain node without poi: {DATE} row 1 has no poi_id"]


def test_an_empty_day_is_a_broken_chain():
    f = chain_failures({"days": [_day([])]})
    assert f == [f"day chain broken: {DATE} has no rows"]


# ---- move records ----------------------------------------------------------

def test_a_move_without_mode_is_incomplete():
    f = move_record_failures({"days": [_day([_mv(mode=None)])]})
    assert f == [f"move record incomplete: {DATE} row 0 has no mode"]


def test_mode_none_needs_nothing_else():
    row = {"slot": "move", "text": "同一個地方", "mode": "none"}
    assert move_record_failures({"days": [_day([row])]}) == []


def test_missing_mins_and_km_are_named():
    f = move_record_failures({"days": [_day([_mv(mins=None, km=None)])]})
    assert f == [f"move record incomplete: {DATE} row 0 lacks mins, km"]


def test_a_sourced_move_needs_its_source_url():
    f = move_record_failures({"days": [_day([_mv(basis="sourced", estimate_method=None)])]})
    assert f == [f"move record incomplete: {DATE} row 0 lacks source_url"]


def test_an_estimated_move_needs_its_method():
    f = move_record_failures({"days": [_day([_mv(estimate_method=None)])]})
    assert f == [f"move record incomplete: {DATE} row 0 lacks estimate_method"]


def test_a_leg_index_move_inherits_its_fields_from_legs_yaml():
    row = {"slot": "move", "text": "特急北斗", "leg_index": 0}
    assert move_record_failures({"days": [_day([row])]}) == []


# ---- legacy shapes ---------------------------------------------------------

def test_trip_level_contingency_is_retired():
    f = legacy_failures({"contingency": [{"trigger": "雨", "fallback": "室內"}], "days": []})
    assert len(f) == 1 and f[0].startswith("legacy contingency: ")


def test_an_inline_triangle_row_is_a_legacy_alternative():
    row = {"slot": "activity", "poi_id": "a", "text": "▸ 備案(雨)｜改室內"}
    f = legacy_failures({"days": [_day([_mv(), row, _mv()])]})
    assert f == [f"legacy alternative row: {DATE} row 1 is an inline ▸ alternative "
                 f"— move it to days[].alternatives"]


def test_legacy_shapes_fail_with_routed_messages_not_exceptions():
    """Review Focus 3：v0.36 的真實形狀（純文字 checklist、contingency、▸ 列、沒有移動欄位）
    餵給 run_gate 只能產生失敗，不能丟例外。"""
    pois, itin = build_gate_inputs()
    itin["checklist"] = ["護照效期"]
    itin["contingency"] = [{"trigger": "雨", "fallback": "室內"}]
    itin["days"][0]["rows"] = [
        {"slot": "meal", "time": "12:00", "poi_id": "poi-1", "text": "午餐"},
        {"slot": "activity", "poi_id": "poi-1", "text": "▸ 備案(雨)｜改室內"},
        {"slot": "move", "text": "回飯店", "from": "五稜郭", "to": "函館"},
    ]
    rep = run_gate(pois, itin, advisory={"items": []}, **rederive_kwargs())
    assert rep["status"] == "fail"
    for prefix in ("day chain broken: ", "legacy contingency: ", "legacy alternative row: ",
                   "move record incomplete: ", "checklist item invalid: "):
        assert any(f.startswith(prefix) for f in rep["failures"]), prefix


# ---- alternatives ----------------------------------------------------------

def _alt(**kw):
    a = {"kind": "備案", "applies_to": "a", "trigger": "纜車停駛",
         "fallback": "改五稜郭塔夜景", "poi_id": "alt1"}
    a.update(kw)
    return {k: v for k, v in a.items() if v is not None}


def _alt_day(*alts):
    return {"days": [_day([_mv(), _stop("a"), _mv()], alternatives=list(alts))]}


def test_a_valid_alternative_passes():
    assert alternative_failures(_alt_day(_alt())) == []


def test_applies_to_must_name_a_stop_on_that_day():
    f = alternative_failures(_alt_day(_alt(applies_to="zzz")))
    assert f == [f"alternative invalid: {DATE} #0 applies_to is not a stop on that day"]


def test_an_alternative_needs_a_poi_id():
    f = alternative_failures(_alt_day(_alt(poi_id=None)))
    assert f == [f"alternative invalid: {DATE} #0 has no poi_id (fallback places must be verified)"]


def test_kind_must_be_one_of_two():
    f = alternative_failures(_alt_day(_alt(kind="plan-b")))
    assert f == [f"alternative invalid: {DATE} #0 kind must be 備案 or 選項"]


def test_trigger_and_fallback_are_required():
    f = alternative_failures(_alt_day(_alt(trigger="", fallback=None)))
    assert f == [f"alternative invalid: {DATE} #0 lacks trigger",
                 f"alternative invalid: {DATE} #0 lacks fallback"]


def test_run_gate_verifies_an_alternatives_place_like_any_stop():
    pois, itin = build_gate_inputs()
    itin["days"][0]["alternatives"] = [_alt(applies_to="poi-1", poi_id="ghost")]
    rep = run_gate(pois, itin, advisory={"items": []}, **rederive_kwargs())
    assert "day references unknown POI 'ghost'" in rep["failures"]


def test_alternative_line_renders_kind_trigger_and_fallback():
    assert alternative_line(_alt()) == "備案（纜車停駛）：改五稜郭塔夜景"


# ---- day theme -------------------------------------------------------------

def _themed(theme="早市的蟹，山頂的夜", refs=("a",), date=DATE, own=False):
    from tests.title_fixture import six                  # v1.1 topic 7: the theme is one of six
    cands = six(0, ["a"])
    cands[1] = {"text": "早市的蟹，山頂的夜", "shape": "couplet", "twist": "rhyme", "refs": ["a"]}
    d = _day([_mv(), _stop("a"), _mv()], theme=theme, theme_refs=list(refs), theme_candidates=cands)
    d["date"] = date
    if own:
        d["theme_user_written"] = True
    return d


def test_a_valid_theme_passes():
    assert theme_failures({"days": [_themed()]}) == []


def test_a_missing_theme_is_a_failure():
    d = _themed()
    d.pop("theme")
    assert theme_failures({"days": [d]}) == [f"day theme invalid: {DATE} has no theme"]


def test_a_theme_over_13_chars_is_a_failure():
    f = theme_failures({"days": [_themed(theme="早市的蟹，山頂的夜，還有溫泉", own=True)]})
    assert f == [f"day theme invalid: {DATE} theme is 14 chars (max 13)"]


def test_theme_refs_must_be_stops_on_that_day():
    f = theme_failures({"days": [_themed(refs=("zzz",))]})
    assert f == [f"day theme invalid: {DATE} theme_refs has 1 entries that are not stops on that day"]


def test_empty_theme_refs_is_a_failure():
    f = theme_failures({"days": [_themed(refs=())]})
    assert f == [f"day theme invalid: {DATE} has no theme_refs"]


def test_theme_refs_that_is_not_a_list_is_a_failure():
    d = _themed()
    d["theme_refs"] = "a"
    assert theme_failures({"days": [d]}) == [f"day theme invalid: {DATE} theme_refs is not a list"]


def test_the_theme_is_scanned_for_ai_tone():
    pois, itin = build_gate_inputs()
    itin["days"][0]["theme"] = "五稜郭——午餐"
    rep = run_gate(pois, itin, advisory={"items": []}, **rederive_kwargs())
    assert {c["name"]: c["passed"] for c in rep["checks"]}["no_ai_tone"] is False


def test_two_days_cannot_share_a_theme():
    f = theme_failures({"days": [_themed(date="2026-10-13"), _themed(date="2026-10-14")]})
    # the two days also share their candidates, which topic 7 reports separately
    assert "day theme invalid: 2026-10-14 repeats the theme of 2026-10-13" in f
    assert all(m.startswith("day theme invalid: 2026-10-14 ") for m in f), f


# ---- run_gate wiring: every new check exists, and goes red on its own bug ---

NEW_CHECKS = {"day_chain_complete", "moves_recorded", "alternatives_valid", "day_theme_valid",
              "checklist_structured", "sources_complete", "lodging_area_labelled",
              "brief_names_valid"}


def _gate(pois, itin, **over):
    kw = rederive_kwargs(**over)
    return run_gate(pois, itin, advisory={"items": []}, **kw)


def test_the_clean_fixture_passes_every_new_check():
    pois, itin = build_gate_inputs()
    rep = _gate(pois, itin)
    assert rep["status"] == "pass", rep["failures"]
    assert NEW_CHECKS <= {c["name"] for c in rep["checks"]}


def _drop_head_move(pois, itin, over):
    itin["days"][0]["rows"].pop(0)


def _drop_mode(pois, itin, over):
    itin["days"][0]["rows"][0].pop("mode")


def _bad_alternative(pois, itin, over):
    itin["days"][0]["alternatives"] = [_alt(applies_to="zzz", poi_id="poi-1")]


def _drop_theme(pois, itin, over):
    itin["days"][0].pop("theme")


def _free_text_checklist(pois, itin, over):
    itin["checklist"] = ["護照效期"]


def _drop_site(pois, itin, over):
    pois[0]["sources"][0].pop("site")


def _stop_without_area_label(pois, itin, over):
    over["accommodations"] = {"stops": [{"district": "函館", "nights": 1, "chosen": None,
                                         "candidates": []}]}


def _brief_without_short_name(pois, itin, over):
    brief = rederive_kwargs()["trip_brief"]
    brief.pop("short_name")
    over["trip_brief"] = brief


@pytest.mark.parametrize("inject,check", [
    (_drop_head_move, "day_chain_complete"),
    (_drop_mode, "moves_recorded"),
    (_bad_alternative, "alternatives_valid"),
    (_drop_theme, "day_theme_valid"),
    (_free_text_checklist, "checklist_structured"),
    (_drop_site, "sources_complete"),
    (_stop_without_area_label, "lodging_area_labelled"),
    (_brief_without_short_name, "brief_names_valid"),
])
def test_each_new_check_goes_red_on_the_bug_it_names(inject, check):
    """CLAUDE.md (c)：注入 check 名字所說的那個 bug，那個 check 必須變紅。"""
    pois, itin = build_gate_inputs()
    over = {}
    inject(pois, itin, over)
    rep = _gate(pois, itin, **over)
    by_name = {c["name"]: c["passed"] for c in rep["checks"]}
    assert by_name[check] is False, rep["failures"]
