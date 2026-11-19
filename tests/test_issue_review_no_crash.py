"""Hand-edited values in the 2026-11-18 review's new fields never crash the gate (the
gate CLI does not schema-validate). The gate may pass or fail; it must not raise."""
import pytest

from scripts.gate import run_gate
from tests.test_v1_p1_review_fixes import build_gate_inputs, rederive_kwargs

ODD = [
    lambda p, i: i.__setitem__("venue_notices", "x"),
    lambda p, i: i.__setitem__("venue_notices", ["x", {"venue": 5, "checked": 3, "items": ["y", {"affects": [1, {}]}]}]),
    lambda p, i: i["days"][0]["rows"].insert(1, {"slot": "transfer", "place": 5, "security": "yes", "text": "x"}),
    lambda p, i: i["days"][0]["rows"][0].update(mins_max="65", check_in_close_mins="60", mode="flight"),
    lambda p, i: i["days"][0]["rows"][0].update(board_at=5, board_at_en=["x"], route_en=3, mode="rail"),
    lambda p, i: p[0].update(security_zone=["airside"], inside=5),
]


@pytest.mark.parametrize("mutate", ODD)
def test_odd_values_do_not_crash_the_gate(mutate):
    pois, itin = build_gate_inputs()
    mutate(pois, itin)
    rep = run_gate(pois, itin, advisory={"items": []}, **rederive_kwargs())
    assert rep["status"] in ("pass", "fail")


@pytest.mark.parametrize("value", [["x"], [{"date": "2030-01-01", "status": "cancel", "cancel_by": 5}]])
def test_odd_cancel_entries_do_not_crash(value):
    from scripts import reservation
    reservation.cancel_notices({"reservations": value})
    reservation.to_cancel({"reservations": value})
