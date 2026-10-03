"""v1.0 P1 — rederive_moves：用兩端座標重算每日移動（spec §4.1）。
期望值一律呼叫 shipped 的 haversine_km / rederive.move_floor_mins 算，不寫死數字。"""
from scripts.distance import haversine_km
from scripts.rederive import _move_segments, move_floor_mins, rederive_moves, run_rederivation

A = {"lat": 41.7960, "lng": 140.7570}
B = {"lat": 41.7700, "lng": 140.7300}
BY_ID = {"a": {"geocode": A}, "b": {"geocode": B}, "h": {"geocode": A}, "nogeo": {}}
STRAIGHT = haversine_km(A["lat"], A["lng"], B["lat"], B["lng"])


def _mv(**kw):
    row = {"slot": "move", "text": "移動", "mode": "taxi", "km": round(STRAIGHT * 1.4, 1),
           "mins": int(move_floor_mins(STRAIGHT, "taxi")) + 10,
           "basis": "estimated", "estimate_method": "直線乘 1.4"}
    row.update(kw)
    return row


def _two_days(rows, lodging="b"):
    """Day 1 ends at lodging h (same point as a); day 2 is the day under test."""
    return {"days": [
        {"date": "2026-10-12", "lodging": "h", "rows": [{"slot": "move", "mode": "none"}]},
        {"date": "2026-10-13", "lodging": lodging, "rows": rows}]}


def _stop(pid):
    return {"slot": "visit", "time": "10:00", "poi_id": pid, "text": "參觀"}


NONE = {"slot": "move", "mode": "none"}


def test_segments_carry_their_endpoints():
    itin = _two_days([dict(NONE), _stop("a"), _mv(), _stop("b"), dict(NONE)])
    segs = [(d, j, len(run), f, t) for d, j, run, f, t in _move_segments(itin)]
    assert segs == [("2026-10-12", 0, 1, None, "h"),
                    ("2026-10-13", 0, 1, "h", "a"),
                    ("2026-10-13", 2, 1, "a", "b"),
                    ("2026-10-13", 4, 1, "b", "b")]


def test_an_honest_estimate_passes():
    out = rederive_moves(_two_days([dict(NONE), _stop("a"), _mv(), _stop("b"), dict(NONE)]), BY_ID)
    assert (out.mismatches, out.missing) == ([], [])
    assert out.compared == out.found == 3        # h->a, a->b, b->b; the D1 arrival run is external


def test_a_same_place_none_move_passes_and_a_far_one_does_not():
    out = rederive_moves(_two_days([dict(NONE), _stop("b"), dict(NONE)]), BY_ID)
    # h(=A) -> b is NOT the same place: recording it as none is a mismatch...
    assert len(out.mismatches) == 1 and out.mismatches[0].startswith("move rederive mismatch: ")
    # ...while the b -> lodging b tail (0 km) is fine
    assert "rows 2-2" not in out.mismatches[0]


def test_km_below_the_straight_line_is_a_mismatch():
    rows = [dict(NONE), _stop("a"), _mv(km=round(STRAIGHT * 0.5, 2)), _stop("b"), dict(NONE)]
    out = rederive_moves(_two_days(rows), BY_ID)
    assert len(out.mismatches) == 1 and "km" in out.mismatches[0]


def test_mins_below_the_physical_floor_is_a_mismatch():
    too_fast = int(move_floor_mins(STRAIGHT, "walk")) // 2
    rows = [dict(NONE), _stop("a"), _mv(mode="walk", mins=too_fast), _stop("b"), dict(NONE)]
    out = rederive_moves(_two_days(rows), BY_ID)
    assert len(out.mismatches) == 1 and "min" in out.mismatches[0]


def test_an_endpoint_without_geocode_is_unrederivable():
    rows = [dict(NONE), _stop("a"), _mv(), _stop("nogeo"), dict(NONE)]
    out = rederive_moves(_two_days(rows, lodging="nogeo"), BY_ID)
    assert out.missing and all(m.startswith("move rederive missing: ") for m in out.missing)


def test_a_multi_leg_run_is_summed():
    walk = _mv(mode="walk", km=1.0, mins=12)
    bus = _mv(mode="bus", km=round(STRAIGHT * 1.2, 1), mins=int(move_floor_mins(STRAIGHT, "bus")) + 5)
    out = rederive_moves(_two_days([dict(NONE), _stop("a"), walk, bus, _stop("b"), dict(NONE)]), BY_ID)
    assert (out.mismatches, out.missing) == ([], [])
    too_fast = dict(bus, mins=0.5)      # 0.5 + 0.5 min is under the bus floor for ~3.7 km
    out = rederive_moves(_two_days([dict(NONE), _stop("a"), dict(walk, mins=0.5), too_fast,
                                    _stop("b"), dict(NONE)]), BY_ID)
    assert len(out.mismatches) == 1


def test_a_run_with_a_leg_index_is_left_to_rederive_legs():
    rows = [dict(NONE), _stop("a"), {"slot": "move", "leg_index": 0}, _stop("b"), dict(NONE)]
    out = rederive_moves(_two_days(rows), BY_ID)
    assert out.found == 2          # h->a and b->b only


def test_the_arrival_run_of_day_one_is_not_examined():
    itin = {"days": [{"date": "2026-10-12", "lodging": "b", "rows": [_mv(), _stop("a"), _mv()]}]}
    out = rederive_moves(itin, BY_ID)
    assert out.found == 1          # a -> lodging b only


def test_a_string_km_is_not_compared_and_does_not_raise():
    rows = [dict(NONE), _stop("a"), _mv(km="5"), _stop("b"), dict(NONE)]
    out = rederive_moves(_two_days(rows), BY_ID)
    assert out.found == 3 and out.compared == 2 and out.mismatches == []


def test_run_rederivation_reports_move_mismatches_on_verdicts_match():
    rows = [dict(NONE), _stop("a"), _mv(km=0.1), _stop("b"), dict(NONE)]
    res = run_rederivation(_two_days(rows), BY_ID, legs={"legs": []},
                           routing={"clusters": [], "hops": []},
                           cost={"currency": "JPY", "line_items": [], "total": 0},
                           accommodations={"stops": []})
    match = next(c for c in res["checks"] if c["name"] == "verdicts_match")
    assert match["passed"] is False
    assert any(f.startswith("move rederive mismatch: ") for f in res["failures"])
