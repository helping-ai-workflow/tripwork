"""v1.0 P1 — 結構化行前清單（spec §4.7）。"""
from scripts.checklist import checklist_failures, checklist_line, checklist_texts
from scripts.gate import run_gate
from scripts.render.html_page import render_html_page
from scripts.render.markdown import render_markdown_page
from tests.mech_fixtures import build_gate_inputs, rederive_kwargs

P = "checklist item invalid: "
BEER = {"kind": "預約", "task": "札幌啤酒博物館導覽預約", "due": "2026-10-17 08:00",
        "due_is_hard": True, "origin": "D6・10/17",
        "detail": "預約開放 10/17 08:00 至前日 15:00",
        "links": [{"label": "sapporobeer.jp 預約頁", "url": "https://www.sapporobeer.jp/"}]}
BY_ID = {"beer": {"booking": {"opens_at": "2026-10-17 08:00"}}}


def test_structured_items_pass():
    itin = {"checklist": [BEER, {"kind": "打包", "task": "防滑保暖鞋"}]}
    assert checklist_failures(itin, BY_ID, {"beer"}) == []


def test_a_free_text_item_fails():
    f = checklist_failures({"checklist": ["護照效期"]}, {}, set())
    assert f == [P + "item 0 is free text — record kind/task/due"]


def test_kind_and_task_are_checked():
    itin = {"checklist": [{"kind": "買東西", "task": ""}]}
    assert checklist_failures(itin, {}, set()) == [
        P + "item 0 kind must be 預約, 出發前確認 or 打包", P + "item 0 has no task"]


def test_a_hard_deadline_must_be_an_absolute_date():
    bad = {"kind": "出發前確認", "task": "查纜車整備", "due": "行前 1 週", "due_is_hard": True}
    assert checklist_failures({"checklist": [bad]}, {}, set()) == [
        P + "item 0 is a hard deadline but due is not an absolute date"]
    ok = dict(bad, due="2026-11-02")
    assert checklist_failures({"checklist": [ok]}, {}, set()) == []


def test_a_referenced_booking_opening_needs_a_hard_dated_reservation_item():
    assert checklist_failures({"checklist": []}, BY_ID, {"beer"}) == [
        "booking not in checklist: POI 'beer' opens reservations at a recorded time "
        "but no hard-dated 預約 item carries it"]


def test_an_unreferenced_booking_opening_is_not_required():
    assert checklist_failures({"checklist": []}, BY_ID, set()) == []


def test_checklist_line():
    assert checklist_line("護照效期") == "護照效期"
    assert checklist_line(BEER) == "札幌啤酒博物館導覽預約（2026-10-17 08:00）"
    assert checklist_line({"kind": "打包", "task": "頭燈"}) == "頭燈"


def test_checklist_texts_feed_the_hygiene_scan():
    assert checklist_texts("護照效期") == ["護照效期"]
    assert checklist_texts(BEER) == ["札幌啤酒博物館導覽預約", "預約開放 10/17 08:00 至前日 15:00",
                                     "D6・10/17", "sapporobeer.jp 預約頁"]
    assert checklist_texts(42) == []


def test_an_advisory_topic_in_a_structured_task_counts_as_surfaced():
    pois, itin = build_gate_inputs()
    itin["checklist"] = [{"kind": "打包", "task": "battery: spare lithium batteries carry-on only"}]
    advisory = {"items": [{"topic": "battery", "risk": "restricted"}]}
    rep = run_gate(pois, itin, advisory=advisory, **rederive_kwargs())
    assert not any("not surfaced" in f for f in rep["failures"]), rep["failures"]


def test_renderers_accept_structured_items():
    pois, itin = build_gate_inputs()
    itin["checklist"] = [BEER]
    poi_map = {p["id"]: p for p in pois}
    assert "札幌啤酒博物館導覽預約" in render_markdown_page(itin, poi_map)
    assert "札幌啤酒博物館導覽預約" in render_html_page(itin, poi_map)


def test_renderers_show_per_day_alternatives():
    pois, itin = build_gate_inputs()
    itin["days"][0]["alternatives"] = [{"kind": "備案", "applies_to": "poi-1",
                                        "trigger": "下大雨", "fallback": "改館內參觀", "poi_id": "poi-1"}]
    poi_map = {p["id"]: p for p in pois}
    assert "改館內參觀" in render_markdown_page(itin, poi_map)
    assert "改館內參觀" in render_html_page(itin, poi_map)
