"""A flight leg carries its local arrival time (`arrive`): depart + duration lands in the
departure time zone, so the reader would show a wrong landing time without it."""
import json
import pathlib

import jsonschema
import pytest

from scripts.gate import run_gate
from scripts.orchestration import route_gate_failures
from tests import mech_fixtures as M
from tests.reservation_fixture import LEGS

SCHEMA = json.loads((pathlib.Path(__file__).resolve().parent.parent / "schemas/legs.schema.json").read_text())


def _flight(**over):
    leg = dict(LEGS["legs"][0])
    leg.update(over)
    return leg


def _failures(leg):
    pois, itin = M.build_gate_inputs()
    r = run_gate(pois, itin, advisory={"items": []}, **M.rederive_kwargs(legs={"legs": [leg]}))
    return [f for f in r["failures"] if "arrive" in f]


def test_flight_without_arrive_fails_and_routes_to_legs():
    leg = _flight()
    leg.pop("arrive")
    f = _failures(leg)
    assert f == ["legs[0] flight has no arrive (local arrival time at 羽田空港)"]
    assert route_gate_failures(f) == "tripwork:inter-stop-legs"


def test_flight_with_arrive_passes():
    assert _failures(_flight()) == []


def test_rail_without_arrive_is_fine():
    leg = dict(LEGS["legs"][1])
    assert "arrive" not in leg and _failures(leg) == []


def test_schema_arrive_is_hh_mm():
    jsonschema.validate({"legs": [_flight()]}, SCHEMA)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"legs": [_flight(arrive="1300")]}, SCHEMA)
