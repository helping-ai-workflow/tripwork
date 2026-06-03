import pytest
from scripts.distance import haversine_km, classify_hop

def test_haversine_known_distance():
    # 명동 (37.5636,126.9869) -> 잠실 (37.5133,127.1000) ~ 10-11 km
    d = haversine_km(37.5636, 126.9869, 37.5133, 127.1000)
    assert 9.0 < d < 12.0

def test_haversine_zero():
    assert haversine_km(37.5, 127.0, 37.5, 127.0) == pytest.approx(0.0, abs=1e-6)

def test_classify_hop_ok_under_threshold():
    assert classify_hop(30, max_hop_mins=60) == "ok"

def test_classify_hop_far_over_threshold():
    assert classify_hop(75, max_hop_mins=60) == "far"

def test_classify_hop_boundary_inclusive():
    assert classify_hop(60, max_hop_mins=60) == "ok"
