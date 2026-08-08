"""Unit tests for scripts/legs.py — inter-stop leg feasibility classification."""
from scripts.legs import drive_too_long, misses_last_service, classify_leg
from scripts.validate_artifact import validate_file


def test_drive_too_long_boundary():
    assert drive_too_long(300, 300) is False   # equal is OK
    assert drive_too_long(301, 300) is True
    assert drive_too_long(240, 300) is False


def test_drive_too_long_custom_max():
    assert drive_too_long(200, 180) is True
    assert drive_too_long(180, 180) is False


def test_misses_last_service():
    assert misses_last_service("21:30", "21:00") is True
    assert misses_last_service("20:30", "21:00") is False
    assert misses_last_service("21:00", "21:00") is False  # equal makes it


def test_classify_drive_leg():
    assert classify_leg({"mode": "drive", "duration_mins": 360}, 300)[0] == "drive_too_long"
    assert classify_leg({"mode": "drive", "duration_mins": 240}, 300)[0] == "ok"


def test_classify_transit_leg():
    late = {"mode": "rail", "depart": "22:00", "last_service": "21:00"}
    assert classify_leg(late)[0] == "missed_last_service"
    fine = {"mode": "rail", "depart": "20:00", "last_service": "21:00"}
    assert classify_leg(fine)[0] == "ok"


def test_classify_transit_without_times_is_ok():
    assert classify_leg({"mode": "rail"})[0] == "ok"


def test_classify_drive_leg_without_duration_raises():   # TW-010
    import pytest
    with pytest.raises(ValueError):
        classify_leg({"mode": "drive", "from": "Tekapo", "to": "Te Anau"}, 300)
    with pytest.raises(ValueError):
        classify_leg({"mode": "drive", "duration_mins": None}, 300)


def test_classify_transit_mode_misses_last_service():   # TW-026
    status, _ = classify_leg({"mode": "transit", "depart": "21:45", "last_service": "21:30"})
    assert status == "missed_last_service"


def test_misses_last_service_after_midnight():   # TW-021
    from scripts.legs import misses_last_service
    # last service 00:30 (next-day small hours), planned depart 23:50 -> still catches it
    assert misses_last_service("23:50", "00:30") is False
    # planned depart 01:00 after a 00:30 last service -> missed
    assert misses_last_service("01:00", "00:30") is True


def test_legs_schema_accepts_kind_home(tmp_path):
    """TW-065: three trips invented three shapes because none was legal.

    2026-09-northeast-coast wrote legs: [] and hand-wrote 1,300 into cost.yaml;
    2026-07-sun-moon-lake added 3 home legs; 2026-08-chiayi added 2 in violation
    of the SKILL. All three numbers were reasonable and no two were the same shape.

    Brief defect: the brief's fixture used `fare: 1000` but legs.schema.json's
    `fare` is an object ({amount, currency}), same as every other leg's fare —
    fixed here to match the existing (unchanged) fare shape.
    """
    p = tmp_path / "legs.yaml"
    p.write_text(
        "legs:\n"
        "  - from: 三重\n"
        "    to: 嘉義市\n"
        "    kind: home\n"
        "    mode: drive\n"
        "    duration_mins: 190\n"
        "    fare:\n"
        "      amount: 1000\n"
        "      currency: TWD\n"
        "    status: ok\n"
        "    sources:\n"
        "      - url: https://www.freeway.gov.tw/\n"
        "        official: true\n",
        encoding="utf-8",
    )
    assert validate_file(str(p))[0] == 0


def test_trip_brief_accepts_home_origin_and_home_return(tmp_path):
    """The chiayi trip left from 三重 and returned to 新竹 — different endpoints,
    so one 'home' field cannot express it.

    Brief defect: the brief's fixture omitted trip-brief.schema.json's other
    required top-level fields (members, base, must_do, constraints,
    preferences) — unrelated to TW-065, but required regardless. Added here
    with minimal filler so the only thing under test is home_origin/home_return.
    """
    p = tmp_path / "trip-brief.yaml"
    p.write_text(
        "slug: 2026-08-chiayi\n"
        "destination:\n"
        "  country: TW\n"
        "  city: 嘉義市\n"
        "  local_lang: zh\n"
        "dates:\n"
        "  start: '2026-08-29'\n"
        "  end: '2026-08-31'\n"
        "members:\n"
        "  - name: traveller\n"
        "base:\n"
        "  name: 嘉義市住宿\n"
        "  district: 嘉義市西區\n"
        "must_do: []\n"
        "constraints: []\n"
        "preferences: {}\n"
        "home_origin: 三重\n"
        "home_return: 新竹\n"
        "overnight_stops:\n"
        "  - district: 嘉義市西區\n"
        "    nights: 2\n",
        encoding="utf-8",
    )
    assert validate_file(str(p))[0] == 0


def test_classify_leg_treats_a_home_leg_like_any_other_drive():
    """Guard, GREEN at HEAD (regression guard): scripts/legs.py:43-52 is
    kind-agnostic and must stay that way. The defect was never in
    classify_leg — it was that the leg had nowhere legal to exist, so the
    function never saw it."""
    status, reason = classify_leg(
        {"mode": "drive", "kind": "home", "duration_mins": 301}, 300)
    assert status == "drive_too_long"
    assert "301" in reason


def test_single_base_with_no_home_endpoints_may_still_be_empty(tmp_path):
    """Guard, GREEN at HEAD (back-compat guard): tests/mech_fixtures.py:114-115.
    The home-leg feature must not make legs mandatory for every trip."""
    p = tmp_path / "legs.yaml"
    p.write_text("legs: []\n", encoding="utf-8")
    assert validate_file(str(p))[0] == 0
