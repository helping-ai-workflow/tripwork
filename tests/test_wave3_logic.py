"""Wave 3 (v0.14.0) pure-logic helpers: hop plausibility floor, booking
lead-time, and the candidates-staleness predicate."""
import pytest


def test_min_plausible_mins_transit_floor():   # TW-056
    from scripts.distance import min_plausible_mins
    assert min_plausible_mins(20, "transit") >= 60   # ~15 km/h door-to-door


def test_classify_hop_flags_implausible_below_floor():   # TW-056
    from scripts.distance import classify_hop
    # 20 km by transit cannot take 45 min; below the floor -> not 'ok'
    assert classify_hop(45, max_hop_mins=60, km=20, mode="transit") == "implausible"
    # a plausible 90-min hop over 20 km clears the floor, but the call site never
    # names a duration_source -> it is an unlabelled agent guess, so TW-066 marks
    # it 'unsourced' rather than silently granting 'ok'.
    assert classify_hop(90, max_hop_mins=120, km=20, mode="transit") == "unsourced"


def test_classify_hop_backward_compatible_without_km():
    from scripts.distance import classify_hop
    assert classify_hop(45, max_hop_mins=60) == "ok"
    assert classify_hop(75, max_hop_mins=60) == "far"


def test_lead_time_missed():   # TW-030
    from scripts.booking import lead_time_missed
    assert lead_time_missed("2026-06-11", "2026-06-18", 30) is True    # only 7 days out, needs 30
    assert lead_time_missed("2026-06-11", "2026-06-18", 5) is False    # 7 days out, needs 5 -> ok
    assert lead_time_missed("2026-06-11", "2026-07-18", 30) is False   # plenty of lead time


def test_candidates_stale_predicate():   # TW-053
    from scripts.orchestration import candidates_stale
    assert candidates_stale(["a", "b", "temple-x"], ["a", "b"]) is True   # temple-x unverified
    assert candidates_stale(["a", "b"], ["a", "b", "extra"]) is False     # full coverage


def test_fingerprint_is_stable_across_key_order_and_yaml_style():   # TW-067
    from scripts.orchestration import input_fingerprint
    a = {"destination": {"city": "嘉義市", "country": "TW"},
         "dates": {"start": "2026-08-29", "end": "2026-08-31"},
         "airline": None, "must_do": ["雞肉飯"]}
    b = {"dates": {"end": "2026-08-31", "start": "2026-08-29"},
         "must_do": ["花磚"], "destination": {"country": "TW", "city": "嘉義市"}}
    proj = ("airline", "dates", "destination")
    assert input_fingerprint(a, proj) == input_fingerprint(b, proj)


def test_fingerprint_changes_when_a_projected_field_changes():   # TW-067
    from scripts.orchestration import input_fingerprint
    a = {"destination": {"city": "嘉義市"}, "dates": {"start": "2026-08-29"}}
    b = {"destination": {"city": "台南市"}, "dates": {"start": "2026-08-29"}}
    proj = ("dates", "destination")
    assert input_fingerprint(a, proj) != input_fingerprint(b, proj)
