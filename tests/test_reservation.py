import pathlib

import pytest
import yaml

from scripts import reservation as R
from scripts.validate_artifact import validate_file
from tests import reservation_fixture as F


@pytest.mark.parametrize("ref,out", [("K7Q2PX", "••••PX"), ("RSV-58213", "••••8213"), ("ABCD", "••••"),
                                     ("K7Q2P", "••••P"), ("ABCDEFGHIJ", "••••GHIJ"), ("", "••••")])
def test_mask_ref(ref, out):
    assert R.mask_ref(ref) == out


def _validate(tmp_path, doc):
    p = tmp_path / "reservations.yaml"
    p.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return validate_file(p)[0]


def test_schema_accepts_the_fixture(tmp_path):
    assert _validate(tmp_path, F.reservations()) == 0


@pytest.mark.parametrize("bad", [
    {"date": "2026-05-13", "poi_id": "kappo", "lodging": "demo-hotel", "status": "booked"},   # two shapes
    {"date": "2026-05-13", "from": "淺草", "status": "booked"},                                # from without to
    {"date": "2026-05-13", "poi_id": "kappo", "status": "maybe"},                              # unknown status
    {"date": "5/13", "poi_id": "kappo", "status": "booked"},                                   # bad date
])
def test_schema_rejects(tmp_path, bad):
    assert _validate(tmp_path, {"reservations": [bad]}) == 1


def _match(itin=None, res=None):
    return R.match(itin or F.itinerary(), F.legs(), res or F.reservations(), F.poi_map())


def test_match_every_kind():
    pairs, failures = _match()
    assert failures == []
    got = {(p["kind"], p["date"], p["day"], p["row"]) for p in pairs}
    assert ("move", "2026-05-12", 0, 0) in got          # by leg_index
    assert ("move", "2026-05-14", 2, 0) in got          # by the row's own from/to
    assert ("lodging", "2026-05-12", 0, None) in got
    assert ("stop", "2026-05-13", 1, 2) in got          # kappo
    assert len(pairs) == len(F.RESERVATIONS["reservations"])


def test_match_orphan():
    itin = F.itinerary()
    itin["days"][1]["rows"] = [r for r in itin["days"][1]["rows"] if r.get("poi_id") != "kappo"]
    _, failures = _match(itin)
    assert failures == ["reservation has no row: 2026-05-13 押上示意割烹"]


def test_match_ambiguous_needs_time():
    itin = F.itinerary()
    itin["days"][1]["rows"].append({"slot": "meal", "time": "21:00", "poi_id": "kappo", "text": "宵夜"})
    _, failures = _match(itin)
    assert failures[0].startswith("reservation matches several rows: 2026-05-13 押上示意割烹")
    assert "time" in failures[0]
    res = F.reservations()
    next(r for r in res["reservations"] if r.get("poi_id") == "kappo")["time"] = "19:00"
    assert _match(itin, res)[1] == []


def test_match_two_on_one_row():
    res = F.reservations()
    res["reservations"].append({"date": "2026-05-13", "poi_id": "kappo", "status": "todo"})
    _, failures = _match(res=res)
    assert failures == ["reservation duplicates another on the same row: 2026-05-13 押上示意割烹"]


def test_self_only_on_meals():
    res = F.reservations()
    next(r for r in res["reservations"] if r.get("poi_id") == "skytree")["status"] = "self"
    _, failures = _match(res=res)
    assert failures == ["reservation self is for meals only: 2026-05-13 東京晴空塔"]


def test_no_reservations_is_nothing():
    assert R.match(F.itinerary(), F.legs(), None, F.poi_map()) == ([], [])


def test_summary_and_detail_pairs_mask_the_ref():
    hotel = next(r for r in F.RESERVATIONS["reservations"] if r.get("lodging"))
    assert R.summary(hotel, "lodging") == "已訂・訂房編號 ••••3907・15:00 起・三人房，含早餐"
    flight = F.RESERVATIONS["reservations"][0]
    assert R.detail_pairs(flight, "move") == [("訂位編號", "••••PX"), ("座位", "32A・32B・32C"),
                                              ("行李", "每人託運 23 kg")]
    assert R.summary({"status": "none"}, "move") == "不用訂"


def test_texts_skip_ref():
    joined = "\n".join(R.texts(F.reservations()))
    assert "會席套餐" in joined and "人數" in joined
    assert not any(ref in joined for ref in F.REFS)
