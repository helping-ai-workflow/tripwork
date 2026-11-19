"""#37 transfer points, #32 platform facts, #22 official English names. Placeholder
places; every check calls the shipped chain / gate / renderer."""
from scripts import day_chain
from scripts.gate import run_gate
from scripts.rederive import _move_segments
from scripts.render.markdown import render_day_table
from scripts.transfer import (TRANSFER_WAIT_WARN_MINS, bare_joins, machine_line, move_facts,
                              transfer_notices, transfer_warnings, wait_mins, missing_en_notices,
                              bare_transit_notices)


def mv(time, mins, mode="rail", **kw):
    return dict({"slot": "move", "time": time, "mins": mins, "km": 10, "mode": mode,
                 "basis": "estimated", "estimate_method": "示意", "text": "移動"}, **kw)


def day(rows, date="2030-01-02"):
    return {"days": [{"date": date, "rows": rows}]}


STOP = {"slot": "visit", "poi_id": "a", "text": "看"}


def test_a_transfer_names_the_wait():
    rows = [mv("10:00", 47, "bus"), {"slot": "transfer", "place": "示意駅", "platform": "3番線", "text": "買便當"},
            mv("11:05", 85)]
    assert wait_mins(rows, 1) == 18
    md = render_day_table({"label": "D1", "rows": rows}, {})
    assert "**示意駅（3番線・等 18 分）**" in md and "買便當" in md


def test_a_long_bare_wait_warns_and_every_bare_join_is_one_notice():
    rows = [STOP, mv("10:00", 47, "bus"), mv("11:05", 85), mv("12:30", 5, "walk"), STOP]
    it = day(rows)
    assert [g for *_x, g in bare_joins(it)] == [18, 0]
    assert len(transfer_notices(it)) == 1 and transfer_notices(it)[0].startswith("2 ")
    w = transfer_warnings(it)
    assert len(w) == 1 and "(18 min)" in w[0] and "12:30" not in w[0]
    assert TRANSFER_WAIT_WARN_MINS == 15


def test_a_wait_of_exactly_fifteen_is_not_a_warning():
    assert transfer_warnings(day([mv("10:00", 45, "bus"), mv("11:00", 85)])) == []


def test_a_join_next_to_a_flight_is_left_to_the_airport_check():
    assert bare_joins(day([mv("08:40", 50, "drive"), mv("12:00", 210, "flight")])) == []


def test_a_transfer_between_moves_keeps_the_chain_and_the_run_whole():
    rows = [mv("09:00", 10, "walk"), STOP, mv("10:00", 47, "bus"),
            {"slot": "transfer", "place": "示意駅", "text": "等車"}, mv("11:05", 85), dict(STOP, poi_id="b"),
            mv("15:00", 10, "walk")]
    assert day_chain.chain_failures(day(rows)) == []
    runs = [(len(run), frm, to) for _d, _j, run, frm, to in _move_segments(day(rows))]
    assert (2, "a", "b") in runs                         # the transfer is inside the run


def test_a_transfer_must_sit_between_two_moves_and_name_its_place():
    rows = [mv("09:00", 10, "walk"), STOP, {"slot": "transfer", "text": "x"}, mv("10:00", 5), STOP,
            mv("11:00", 5)]
    f = day_chain.chain_failures(day(rows))
    assert any(m.startswith("transfer without place") for m in f)
    assert any(m.startswith("transfer misplaced") for m in f)


def test_platform_facts_render_with_official_english():
    row = mv("10:00", 85, board_at="示意駅 10番線", board_at_en="Sample", route="特急サンプル11号",
             route_en="Sample 11", alight_at="サンプル駅", alight_at_en="Example", pay="周遊券")
    assert move_facts(row)[0] == ("上車", "示意駅 10番線（Sample）")
    assert machine_line(row) == "Sample → Example，Sample 11"
    md = render_day_table({"label": "D1", "rows": [dict(row, **{"from": "示意駅", "to": "サンプル駅"})]}, {})
    assert "車次 特急サンプル11号（Sample 11）" in md and "付款 周遊券" in md


def test_the_machine_line_joins_a_booked_rail_tail():
    row = dict(mv("10:00", 85, board_at_en="Sample", alight_at_en="Example"), **{"from": "A", "to": "B"})
    md = render_day_table({"label": "D1", "rows": [row]}, {}, tickets={0: "已訂"})
    assert "售票機上選：Sample → Example" in md


def test_english_and_silent_rows_are_one_notice_each():
    it = day([mv("10:00", 85), mv("13:00", 30, "bus", text=" "),
              mv("15:00", 85, board_at_en="A", alight_at_en="B")])
    assert len(missing_en_notices(it)) == 1 and missing_en_notices(it)[0].startswith("1 ")
    assert len(bare_transit_notices(it)) == 1 and "13:00" in bare_transit_notices(it)[0]
