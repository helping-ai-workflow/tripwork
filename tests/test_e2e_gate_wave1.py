"""Cross-defect closure for the v0.12.0 iron-rule wave (8-step gate, step 7).

A single itinerary that violates four iron rules at once must make run_gate fail
EVERY corresponding check — proving the per-defect unit fixes also hold under
cross-defect interaction. 2026-06-12 is a Friday.
"""
from scripts.gate import run_gate

POIS = [
    {"id": "verified_meal", "verify_status": "verified", "geocode": {"lat": 37.5, "lng": 127.0}},
    # conflicting POI that still carries a geocode — the planted hallucination shape (TW-002)
    {"id": "conflicting_sight", "verify_status": "conflicting", "geocode": {"lat": 37.5, "lng": 127.1}},
    # verified but closed on Fridays — scheduled on a Friday (TW-018)
    {"id": "friday_closed", "verify_status": "verified", "geocode": {"lat": 37.5, "lng": 127.2},
     "closed_days": ["friday"]},
    # a must_do that the itinerary never schedules (TW-038)
    {"id": "must_see", "verify_status": "verified", "geocode": {"lat": 37.5, "lng": 127.3}},
]

ITIN = {
    "title": "wave1 attack",
    "checklist": [],  # banned advisory topic deliberately NOT surfaced (TW-034)
    "days": [
        {"date": "2026-06-12", "label": "Day 1", "rows": [
            {"time": "12:00", "slot": "meal", "poi_id": "verified_meal", "text": "lunch"},
            {"time": "14:00", "slot": "visit", "poi_id": "conflicting_sight", "text": "sight"},
            {"time": "16:00", "slot": "activity", "poi_id": "friday_closed", "text": "palace"},
        ]},
    ],
}

CALENDAR = {"holidays": []}
ADVISORY = {"items": [{"topic": "spare lithium battery", "rule": "carry-on only",
                       "effective_date": "2026-01-01", "risk": "banned",
                       "sources": [{"url": "https://airline", "official": True}]}]}


def test_wave1_gate_closes_all_four_defects():
    r = run_gate(POIS, ITIN, calendar=CALENDAR, advisory=ADVISORY, must_do=["must_see"])
    assert r["status"] == "fail"
    failed = {c["name"] for c in r["checks"] if not c["passed"]}
    assert {"referenced_pois_verified", "no_closed_day_violation",
            "must_do_covered", "advisory_items_surfaced"} <= failed, r["failures"]
    blob = " | ".join(r["failures"])
    assert "conflicting_sight" in blob and "conflicting" in blob   # TW-002
    assert "friday_closed" in blob and "closed day" in blob        # TW-018
    assert "must_see" in blob                                      # TW-038
    assert "spare lithium battery" in blob                         # TW-034


def test_wave1_clean_itinerary_passes_every_check():
    pois = [{"id": "m", "verify_status": "verified", "geocode": {"lat": 37.5, "lng": 127.0}}]
    itin = {"title": "ok", "checklist": ["spare lithium battery: carry-on only"],
            "days": [{"date": "2026-06-12", "label": "Day 1",
                      "rows": [{"time": "12:00", "slot": "meal", "poi_id": "m", "text": "lunch"}]}]}
    r = run_gate(pois, itin, calendar=CALENDAR, advisory=ADVISORY, must_do=["m"])
    assert r["status"] == "pass", r["failures"]
    assert all(c["passed"] for c in r["checks"])
