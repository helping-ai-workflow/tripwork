"""v1.0 P1 — 每個新失敗訊息導向能寫那個欄位的 stage。訊息一律由 shipped 函式產生。"""
import pytest

from scripts.brief_names import headline_failures, name_failures
from scripts.checklist import checklist_failures
from scripts.day_chain import (alternative_failures, chain_failures, legacy_failures,
                               move_record_failures, theme_failures)
from scripts.orchestration import route_gate_failures
from scripts.rederive import rederive_moves
from scripts.source_records import area_label_failures, source_record_failures

D = "2026-08-01"
FAR = {"a": {"geocode": {"lat": 41.80, "lng": 140.75}},
       "b": {"geocode": {"lat": 41.70, "lng": 140.60}}, "n": {}}


def _far_none(lodging="b"):
    return {"days": [{"date": "2026-07-31", "lodging": "a", "rows": [{"slot": "move", "mode": "none"}]},
                     {"date": D, "lodging": lodging, "rows": [{"slot": "move", "mode": "none"}]}]}


CASES = [
    (lambda: chain_failures({"days": [{"date": D, "rows": [{"slot": "meal", "poi_id": "p"}]}]}),
     "tripwork:itinerary-synthesis"),
    (lambda: chain_failures({"days": [{"date": D, "rows": [
        {"slot": "move", "mode": "none"}, {"slot": "meal"}, {"slot": "move", "mode": "none"}]}]}),
     "tripwork:itinerary-synthesis"),
    (lambda: move_record_failures({"days": [{"date": D, "rows": [{"slot": "move"}]}]}),
     "tripwork:itinerary-synthesis"),
    (lambda: rederive_moves(_far_none(), FAR).mismatches, "tripwork:itinerary-synthesis"),
    (lambda: rederive_moves(_far_none("n"), FAR).missing, "tripwork:itinerary-synthesis"),
    (lambda: legacy_failures({"contingency": [{"trigger": "t", "fallback": "f"}], "days": []}),
     "tripwork:itinerary-synthesis"),
    (lambda: legacy_failures({"days": [{"date": D, "rows": [{"slot": "activity", "text": "▸ 備案"}]}]}),
     "tripwork:itinerary-synthesis"),
    (lambda: alternative_failures({"days": [{"date": D, "rows": [], "alternatives": [{}]}]}),
     "tripwork:itinerary-synthesis"),
    (lambda: theme_failures({"days": [{"date": D, "rows": []}]}), "tripwork:itinerary-synthesis"),
    (lambda: checklist_failures({"checklist": ["x"]}, {}, set()), "tripwork:itinerary-synthesis"),
    (lambda: checklist_failures({"checklist": []}, {"p": {"booking": {"opens_at": "2026-10-17"}}}, {"p"}),
     "tripwork:itinerary-synthesis"),
    (lambda: source_record_failures({"p": {"sources": [{"url": "https://x", "lang": "zh"}]}}, {"p"}, {"p"}),
     "tripwork:source-verify"),
    (lambda: source_record_failures({"h": {"sources": [{"url": "https://x", "lang": "zh"}]}}, set(), {"h"}),
     "tripwork:accommodation-research"),
    (lambda: area_label_failures({"stops": [{"district": "A"}]}), "tripwork:accommodation-research"),
    (lambda: name_failures({"dates": {"start": "2026-08-01", "end": "2026-08-02"}}),
     "tripwork:trip-brief"),
    (lambda: headline_failures({}), "tripwork:trip-brief"),
]


@pytest.mark.parametrize("make,stage", CASES)
def test_every_new_failure_routes_to_its_producing_stage(make, stage):
    failures = make()
    assert failures, "the builder must produce a real failure"
    assert route_gate_failures(failures) == stage
