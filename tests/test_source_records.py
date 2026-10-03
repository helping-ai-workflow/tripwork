"""v1.0 P1 — 來源 site/note/site_local（§4.2）與住宿 area_label（§4.6）。
by_id 一律呼叫 shipped 的 poi_pool 取得，不自己拼。"""
from scripts.gate import poi_pool
from scripts.source_records import area_label_failures, source_record_failures

GOOD_JA = {"url": "https://a.example", "lang": "ja", "site": "函館朝市官網",
           "site_local": "函館朝市公式", "note": "營業時間"}
GOOD_ZH = {"url": "https://b.example", "lang": "zh-TW", "site": "旅遊指南", "note": "交通"}


def _pool(poi_sources, lodging_sources=None):
    pois = [{"id": "p", "sources": poi_sources}]
    acc = {"stops": [{"district": "函館", "chosen": "h",
                      "candidates": [{"id": "h", "sources": lodging_sources or [GOOD_ZH]}]}]}
    return poi_pool(pois, acc), {"p"}


def test_complete_sources_pass():
    by_id, poi_ids = _pool([GOOD_JA, GOOD_ZH])
    assert source_record_failures(by_id, poi_ids, {"p", "h"}) == []


def test_missing_site_and_note_are_named():
    by_id, poi_ids = _pool([{"url": "https://c.example", "lang": "zh"}])
    assert source_record_failures(by_id, poi_ids, {"p"}) == [
        "POI source record incomplete: 'p' sources[0] lacks site, note"]


def test_a_foreign_language_source_needs_site_local():
    src = dict(GOOD_JA)
    src.pop("site_local")
    by_id, poi_ids = _pool([src])
    assert source_record_failures(by_id, poi_ids, {"p"}) == [
        "POI source record incomplete: 'p' sources[0] lacks site_local"]


def test_a_lodging_source_gets_the_lodging_prefix():
    by_id, poi_ids = _pool([GOOD_ZH], lodging_sources=[{"url": "https://h.example", "lang": "zh"}])
    assert source_record_failures(by_id, poi_ids, {"h"}) == [
        "lodging source record incomplete: 'h' sources[0] lacks site, note"]


def test_an_unreferenced_poi_is_not_checked():
    by_id, poi_ids = _pool([{"url": "https://c.example", "lang": "zh"}])
    assert source_record_failures(by_id, poi_ids, set()) == []


def test_area_label():
    assert area_label_failures({"stops": [{"district": "函館", "area_label": "函館"}]}) == []
    assert area_label_failures({"stops": [{"district": "函館"}]}) == [
        "lodging area label missing: stops[0] needs a 2–4 character area_label"]
    assert area_label_failures({"stops": [{"district": "函館", "area_label": "函館市中心區"}]}) == [
        "lodging area label missing: stops[0] needs a 2–4 character area_label"]
