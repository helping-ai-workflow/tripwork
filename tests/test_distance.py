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


def test_raising_the_guess_over_the_floor_does_not_buy_ok():
    """TW-066: the dogfood escape hatch, closed.

    An agent told its hop is `implausible` raised 20 min to 31 min and the gate
    went green with no source cited. 31 clears min_plausible_mins(20,'drive')==30,
    so the number alone can no longer be the whole story.
    """
    assert classify_hop(31, km=20, mode="drive",
                        duration_source="agent_estimate") == "unsourced"


def test_sourced_timetable_over_the_floor_is_ok():
    """The over-blocking guard: a sourced estimate above the floor stays usable."""
    assert classify_hop(31, km=20, mode="drive",
                        duration_source="sourced_timetable") == "ok"
    assert classify_hop(31, km=20, mode="drive",
                        duration_source="map_estimate") == "ok"


def test_below_the_floor_is_implausible_whatever_the_source():
    """A cited source does not repeal physics."""
    for src in ("agent_estimate", "map_estimate", "sourced_timetable"):
        assert classify_hop(20, km=20, mode="drive", duration_source=src) == "implausible"


def test_default_source_is_agent_estimate_and_legacy_calls_keep_working():
    """Guard, GREEN at HEAD: back-compat guard, not defect evidence.

    Back-compat: the 2-arg form still classifies on the threshold alone.
    Without km+mode there is no floor to apply, so provenance cannot change the
    answer and the legacy call sites keep their meaning.
    """
    assert classify_hop(30) == "ok"
    assert classify_hop(90) == "far"


def test_routing_schema_accepts_implausible_and_duration_source(tmp_path):
    """TW-066 root cause the defect doc missed: an honest `implausible` was
    schema-invalid, so raising the guess was the only legal move."""
    from scripts.validate_artifact import validate_file

    p = tmp_path / "routing.yaml"
    p.write_text(
        "clusters:\n"
        "  - district: 西區\n"
        "    pois: [a]\n"
        "hops:\n"
        "  - from: 西區\n"
        "    to: 太保市\n"
        "    mins: 20\n"
        "    mode: drive\n"
        "    flag: implausible\n"
        "    duration_source: agent_estimate\n"
        "warnings: []\n",
        encoding="utf-8",
    )
    assert validate_file(str(p))[0] == 0


def test_over_cap_wins_over_unsourced_for_every_duration_source():
    """TW-066 fix-round-1 (Finding 1, project-owner ruling): precedence is
    implausible > far > unsourced > ok.

    Before this fix, `unsourced` returned before `max_hop_mins` was ever
    examined, so an over-cap hop carrying only an unlabelled agent guess was
    silently recorded as `unsourced` -- schema-valid, but NOT a `far`, so the
    stage skipped the "stop and ask whether to keep or replace the POI" halt.
    That is the same silent escape TW-066 exists to close, through a
    different exit. `far` carries a defined user action; `unsourced` only
    routes back for a source, so when both apply, `far` must win.

    Repro (km=20 'drive': floor=min_plausible_mins(20,'drive')==30, so 90 is
    not implausible; max_hop_mins=60, so 90 is over the cap):
    """
    assert classify_hop(90, max_hop_mins=60, km=20, mode="drive",
                        duration_source="agent_estimate") == "far"
    # the sourced twin must agree -- a hop over the cap is over the cap
    # whether or not someone later cites a timetable for it.
    assert classify_hop(90, max_hop_mins=60, km=20, mode="drive",
                        duration_source="sourced_timetable") == "far"


def test_unknown_duration_source_is_rejected():
    """TW-066 fix-round-1 (Finding 3): `DURATION_SOURCES` is not decorative.

    An unrecognized duration_source is rejected outright rather than being
    silently treated as anything-but-agent_estimate (which would take the
    sourced path and skip the `unsourced` safeguard -- exactly the kind of
    silent escape this task exists to close). Matches the codebase's existing
    convention for an unrecognized enum-like string (see
    scripts/photo_adapter.py's `unknown photo backend` ValueError).
    """
    with pytest.raises(ValueError, match="unknown duration_source"):
        classify_hop(90, km=20, mode="drive", duration_source="agent_estmiate")


def test_none_duration_source_defaults_to_agent_estimate():
    """TW-066 fix-round-2: an absent optional field is not a caller bug.

    schemas/routing.schema.json documents an absent `duration_source` as
    `agent_estimate` -- and every hop written before this field existed has
    it absent. The natural way to read an optional YAML field,
    `hop.get('duration_source')`, yields `None`, and Part 2's
    `rederive_hops` will do exactly that against pre-TW-066 artifacts. `None`
    must classify identically to the explicit `agent_estimate` call -- assert
    they agree rather than hard-coding the string twice, so this test cannot
    drift out of sync with whatever `agent_estimate` currently means.
    """
    assert (classify_hop(45, km=20, mode="drive", duration_source=None)
            == classify_hop(45, km=20, mode="drive", duration_source="agent_estimate"))


def test_unrecognised_duration_source_still_raises_alongside_none_handling():
    """Guard: special-casing `None` must not widen the net for real typos.

    Only the literal absence (`None`) gets the schema's documented default;
    any other unrecognised string -- including one that merely looks close,
    like a stray capitalisation -- still raises.
    """
    with pytest.raises(ValueError, match="unknown duration_source"):
        classify_hop(45, km=20, mode="drive", duration_source="Agent_Estimate")
