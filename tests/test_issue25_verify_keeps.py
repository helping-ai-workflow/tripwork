"""#25: a re-run in a fresh container (no geocode cache) must not downgrade what an
earlier run verified. Placeholder places only; every case runs the shipped driver."""
import pathlib

import yaml

from scripts import source_verify_run as svr
from scripts.geocode import GeocodeResult
from scripts.paths import artifact_path
from tests.test_source_verify_cli import _candidate, _stub_resolve_place

POINT = {"lat": 35.6586, "lng": 139.7454, "geocode_source": "nominatim"}


def _trip(tmp_path, cands, priors, itinerary_ids=()):
    trip, work = tmp_path / "trip", tmp_path / "work"
    (trip / "data").mkdir(parents=True)
    work.mkdir(exist_ok=True)
    days = [{"date": "2030-01-02", "rows": [{"slot": "sight", "poi_id": i} for i in itinerary_ids]}]
    for name, doc in (("trip-brief.yaml", {"destination": {"country": "JP", "local_lang": "zh-TW"}}),
                      ("candidates.yaml", {"candidates": cands}),
                      ("verified-pois.yaml", {"pois": priors}),
                      ("itinerary.yaml", {"days": days})):
        artifact_path(trip, name).write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return trip, work


def _prior(cand, query, **extra):
    p = dict(cand, district=cand.get("claimed_district", ""), resolved_name="示意塔, 港区",
             geocode=dict(POINT, query=query), verify_status="verified", **extra)
    p.pop("claimed_district", None)
    p.pop("address_local", None)
    return p


def _read(trip):
    return yaml.safe_load(artifact_path(trip, "verified-pois.yaml").read_text(encoding="utf-8"))["pois"]


def test_a_query_recorded_before_address_existed_still_matches(tmp_path):
    cand = dict(_candidate("tower", "示意塔", claimed_district="港区"), address_local="港区芝公園4-2-8")
    prior = _prior(cand, {"name": "示意塔", "district": "港区"})          # no `address` key yet
    trip, work = _trip(tmp_path, [cand], [prior], ["tower"])
    code, msgs, _o, pois = svr.run(str(trip), str(work), offline=True)
    assert code == 0, msgs
    assert pois[0]["verify_status"] == "verified" and pois[0]["geocode"]["lat"] == POINT["lat"]


def test_no_centroid_this_time_keeps_the_previous_region_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr(svr.time, "sleep", lambda *_: None)
    monkeypatch.setattr(svr, "resolve_place", _stub_resolve_place({}))     # every lookup misses
    monkeypatch.setattr(svr, "_district_fallback", lambda *a: None)
    cand = _candidate("tower", "示意塔", claimed_district="港区")
    trip, work = _trip(tmp_path, [cand], [_prior(cand, {"name": "示意塔", "district": "港区"})])
    code, msgs, _o, pois = svr.run(str(trip), str(work), offline=False)
    assert code == 0, msgs
    assert pois[0]["verify_status"] == "verified", pois[0].get("status_reason")


def test_a_kept_centroid_that_now_disagrees_still_downgrades(tmp_path, monkeypatch):
    monkeypatch.setattr(svr.time, "sleep", lambda *_: None)
    monkeypatch.setattr(svr, "resolve_place", _stub_resolve_place(
        {"港区": (GeocodeResult(34.69, 135.50, "港区, 大阪市"), "nominatim")}))
    monkeypatch.setattr(svr, "_district_fallback", lambda *a: None)
    cand = _candidate("tower", "示意塔", claimed_district="港区")
    trip, work = _trip(tmp_path, [cand], [_prior(cand, {"name": "示意塔", "district": "港区"})])
    _code, _msgs, _o, pois = svr.run(str(trip), str(work), offline=False)
    assert pois[0]["verify_status"] == "conflicting"


def test_sourced_fields_the_candidate_no_longer_states_are_kept_and_named(tmp_path):
    cand = _candidate("tower", "示意塔", claimed_district="港区")
    status = cand.pop("business_status")
    booking = {"required": True, "url": "https://tower.example/book"}
    prior = _prior(dict(cand, business_status=status), {"name": "示意塔", "district": "港区"},
                   booking=booking, name_roman="Sample Tower")
    trip, work = _trip(tmp_path, [cand], [prior])
    code, msgs, _o, pois = svr.run(str(trip), str(work), offline=True)
    assert pois[0]["business_status"] == status and pois[0]["booking"] == booking
    assert pois[0]["name_roman"] == "Sample Tower"
    note = " ".join(msgs)
    assert "tower.business_status" in note and "tower.booking" in note, msgs


def test_only_verifies_the_named_candidates_and_keeps_the_rest(tmp_path):
    old = _candidate("tower", "示意塔", claimed_district="港区")
    prior = _prior(old, {"name": "changed earlier", "district": "港区"}, gmaps_place_id="ChIJ-x")
    new = _candidate("cafe", "サンプル喫茶", claimed_district="港区")
    unseen = _candidate("shop", "サンプル商店", claimed_district="港区")
    trip, work = _trip(tmp_path, [old, new, unseen], [prior], ["tower"])
    code, msgs, _o, pois = svr.run(str(trip), str(work), offline=True, only=["cafe"])
    by = {p["id"]: p for p in _read(trip)}
    assert by["tower"] == prior                       # untouched, though its lookup changed
    assert by["shop"]["verify_status"] == "unverified" and "--only" in by["shop"]["status_reason"]
    assert by["cafe"]["verify_status"] == "unverified"  # offline: looked at, honestly unresolved


def test_a_scheduled_poi_that_would_lose_verified_stops_the_run(tmp_path):
    cand = _candidate("tower", "示意塔", claimed_district="港区")
    prior = _prior(cand, {"name": "an older name", "district": "港区"})   # lookup changed
    trip, work = _trip(tmp_path, [cand], [prior], ["tower"])
    before = artifact_path(trip, "verified-pois.yaml").read_text(encoding="utf-8")
    code, msgs, _o, _p = svr.run(str(trip), str(work), offline=True)
    assert code == svr.STOPPED_DOWNGRADE and "tower" in " ".join(msgs)
    assert artifact_path(trip, "verified-pois.yaml").read_text(encoding="utf-8") == before
    code2, _m, _o, _p = svr.run(str(trip), str(work), offline=True, allow_downgrade=True)
    assert code2 == 0 and _read(trip)[0]["verify_status"] == "unverified"


def test_an_unscheduled_downgrade_is_written(tmp_path):
    cand = _candidate("tower", "示意塔", claimed_district="港区")
    trip, work = _trip(tmp_path, [cand], [_prior(cand, {"name": "an older name", "district": "港区"})])
    code, msgs, _o, _p = svr.run(str(trip), str(work), offline=True)
    assert code == 0, msgs and _read(trip)[0]["verify_status"] == "unverified"


def test_the_cli_stops_with_its_own_exit_code(tmp_path):
    from tests.cli_helpers import run_main
    cand = _candidate("tower", "示意塔", claimed_district="港区")
    trip, work = _trip(tmp_path, [cand], [_prior(cand, {"name": "an older name", "district": "港区"})],
                       ["tower"])
    rc = svr.main([str(trip), "--work-dir", str(work), "--offline"])
    assert rc == svr.STOPPED_DOWNGRADE
