"""The itinerary gate reads reservations.yaml: every entry must match one row, the
traveller's details go through the same text checks, and a booked place satisfies
its own opens_at reminder."""
from scripts.gate import run_gate
from scripts.orchestration import route_gate_failures
from tests import mech_fixtures as M


def _gate(itin=None, pois=None, **kw):
    p, i = M.build_gate_inputs()
    return run_gate(pois or p, itin or i, advisory={"items": []}, **M.rederive_kwargs(), **kw)


def _res(*entries):
    return {"reservations": list(entries)}


LUNCH = {"date": "2026-08-01", "poi_id": "poi-1", "status": "booked", "ref": "RSV-58213",
         "details": [{"label": "人數", "value": "3 位"}]}


def test_matching_reservation_passes():
    r = _gate(reservations=_res(LUNCH))
    assert r["status"] == "pass", r["failures"]
    assert {"name": "reservations_match", "passed": True} in r["checks"]


def test_orphan_fails_and_routes_to_record_reservation():
    r = _gate(reservations=_res(dict(LUNCH, date="2026-08-02")))
    assert r["status"] == "fail"
    assert any(f.startswith("reservation has no row: 2026-08-02") for f in r["failures"]), r["failures"]
    assert {"name": "reservations_match", "passed": False} in r["checks"]
    assert route_gate_failures(r["failures"]) == "tripwork:record-reservation"


def test_no_reservations_file_changes_nothing():
    plain = _gate()
    assert plain == _gate(reservations=None)
    assert not any(c["name"] == "reservations_match" for c in plain["checks"])


def test_kana_in_details_needs_gloss():
    bare = dict(LUNCH, details=[{"label": "取票", "value": "みどりの窓口"}])
    assert any("no （中文）gloss" in f for f in _gate(reservations=_res(bare))["failures"])
    glossed = dict(LUNCH, details=[{"label": "取票", "value": "みどりの窓口（綠色窗口）"}])
    assert _gate(reservations=_res(glossed))["status"] == "pass"


def test_ref_is_not_text_scanned():
    weird = dict(LUNCH, ref="ガイド-0001")          # kana in a booking number is not prose
    assert _gate(reservations=_res(weird))["status"] == "pass"


def test_booked_poi_satisfies_its_opens_at():
    pois, itin = M.build_gate_inputs()
    for p in pois:
        if p["id"] == "poi-1":
            p["booking"] = {"required": True, "opens_at": "2026-07-01 10:00",
                            "opens_at_source": "https://official.example/poi-1"}
    itin["checklist"] = [c for c in itin["checklist"] if not (isinstance(c, dict) and c.get("due_is_hard"))]
    todo = _gate(itin, pois, reservations=_res(dict(LUNCH, status="todo")))
    assert any(f.startswith("booking not in checklist:") for f in todo["failures"])
    booked = _gate(itin, pois, reservations=_res(LUNCH))
    assert not any(f.startswith("booking not in checklist:") for f in booked["failures"]), booked["failures"]
