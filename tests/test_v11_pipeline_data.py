"""v1.1 topic 5 — the pipeline data defects of the trip-e v1.0 dogfood report
(the v1.0 dogfood report): TW-085, TW-088 .. TW-093.
Expected values come from the shipped helpers (haversine_km, poi_pool, the schemas),
never from literals copied out of them."""
import copy
import datetime
import json
import pathlib

import pytest
import yaml

from scripts.distance import haversine_km

ROOT = pathlib.Path(__file__).resolve().parent.parent


# --- TW-088: a rail / ferry hop has its own speed floor ---------------------------

# The report's five JR Hokkaido hops (mins from the 令和8年10月号 timetable; km is the
# report's centroid straight line) -- the defect's own evidence, so literals.
RAIL_HOPS = [("函館→洞爺", 160, 88.1), ("洞爺→札幌", 165, 70.1), ("函館→大沼", 50, 23.5),
             ("札幌→登別", 115, 65.5), ("札幌→小樽", 50, 31.6)]


def _hop(mins, km, mode="rail"):
    from scripts.distance import classify_hop
    return classify_hop(mins, 240, km=km, mode=mode, duration_source="sourced_timetable",
                        source_url="https://www.jrhokkaido.co.jp/")


@pytest.mark.parametrize("name,mins,km", RAIL_HOPS)
def test_a_timetabled_rail_hop_is_plausible(name, mins, km):
    assert _hop(mins, km) == "ok", name


def test_an_impossible_rail_hop_is_still_implausible():
    assert _hop(20, 88.1) == "implausible"            # 函館→洞爺 in 20 min


def test_every_move_mode_has_a_hop_speed_floor():
    """The hop table (distance.py) and the move table (rederive.py) cover the same
    modes, so a mode added to one cannot fall back to 15 km/h in the other."""
    from scripts.distance import _SPEED_FLOOR_KMH
    from scripts.rederive import _MOVE_MAX_KMH
    missing = sorted(set(_MOVE_MAX_KMH) - set(_SPEED_FLOOR_KMH))
    assert missing == [], missing


# --- TW-089: a district-centroid endpoint is not an exact coordinate --------------

CENTRE = {"lat": 42.5440, "lng": 140.8640, "geocode_source": "cluster_fallback"}     # 昭和新山 centroid
ROPEWAY = {"lat": 42.5480, "lng": 140.8530, "geocode_source": "nominatim"}            # ropeway line point


def _walk_day(by_id):
    from scripts.rederive import rederive_moves
    stop = lambda pid: {"slot": "visit", "time": "12:00", "poi_id": pid, "text": "x"}
    itin = {"days": [{"date": "2026-10-14", "rows": [
        stop("a"), {"slot": "move", "mode": "walk", "km": 0.05, "mins": 2,
                    "basis": "estimated", "estimate_method": "同一棟建物"}, stop("b")]}]}
    return rederive_moves(itin, by_id)


def test_a_move_from_a_district_centroid_is_not_judged_by_the_straight_line():
    assert haversine_km(CENTRE["lat"], CENTRE["lng"], ROPEWAY["lat"], ROPEWAY["lng"]) > 0.5
    out = _walk_day({"a": {"geocode": CENTRE}, "b": {"geocode": ROPEWAY}})
    assert out.mismatches == [] and out.missing == []
    assert out.found == 1 and out.compared == 0      # found, honestly not compared


def test_a_move_between_exact_points_is_still_judged():
    exact = dict(CENTRE, geocode_source="nominatim_structured")
    out = _walk_day({"a": {"geocode": exact}, "b": {"geocode": ROPEWAY}})
    assert out.compared == 1 and out.mismatches, "exact endpoints must still fail 0.05 km"


# --- TW-085: a taxi leg --------------------------------------------------------------

def test_the_legs_schema_accepts_taxi():
    s = json.loads((ROOT / "schemas" / "legs.schema.json").read_text(encoding="utf-8"))
    assert "taxi" in s["properties"]["legs"]["items"]["properties"]["mode"]["enum"]


def test_a_taxi_leg_is_judged_like_a_drive():
    from scripts.legs import classify_leg
    from scripts.rederive import rederive_legs
    assert classify_leg({"mode": "taxi", "duration_mins": 400}, 300)[0] == "drive_too_long"
    out = rederive_legs({"legs": [{"from": "函館空港", "to": "サンプル", "mode": "taxi",
                                   "duration_mins": 30, "status": "ok"}]})
    assert (out.missing, out.mismatches, out.compared) == ([], [], 1)


def test_a_taxi_leg_reads_taxi_in_the_reader():
    """Already right before v1.1 (MODE_LABEL has taxi): the defect was the legs schema
    refusing `taxi`. Kept as the regression guard for the label the user saw."""
    from bs4 import BeautifulSoup
    from scripts.render.reader.day import leg
    html = leg({"slot": "move", "leg_index": 0, "mode": "taxi"},
               [{"mode": "taxi", "duration_mins": 30, "service": "計程車 2 台"}])
    assert BeautifulSoup(html, "html.parser").select_one(".ltx b").get_text() == "計程車 30 分"


# --- TW-090: re-running source-verify keeps what the driver does not produce -------

def _carried_fields():
    """verified-pois fields a candidate cannot carry and the driver does not compute."""
    from scripts.source_verify_run import DRIVER_COMPUTED
    v = json.loads((ROOT / "schemas" / "verified-pois.schema.json").read_text(encoding="utf-8"))
    c = json.loads((ROOT / "schemas" / "candidates.schema.json").read_text(encoding="utf-8"))
    vp = v["properties"]["pois"]["items"]["properties"]
    cp = c["properties"]["candidates"]["items"]["properties"]
    return sorted(set(vp) - set(cp) - set(DRIVER_COMPUTED))


def test_a_rerun_keeps_the_fields_only_an_overlay_recorded(tmp_path):
    from scripts import source_verify_run as svr
    from scripts.paths import artifact_path
    trip, work = tmp_path / "trip", tmp_path / "work"
    (trip / "data").mkdir(parents=True); work.mkdir()
    url = "https://www.hakodate-asaichi.com/"
    cand = {"id": "asaichi", "name_local": "函館朝市", "name_display": "函館朝市", "category": "market",
            "claimed_district": "函館市若松町", "sources": [{"url": url, "lang": "ja"}]}
    prior = {"id": "asaichi", "name_local": "函館朝市", "name_display": "函館朝市", "category": "market",
             "district": "函館市若松町", "name_zh": "函館早市", "gmaps_place_id": "ChIJ-asaichi",
             "hours": [{"days": "daily", "open": "06:00", "close": "14:00"}],
             "closed_days": [], "sources": [{"url": url, "lang": "ja", "official": True}],
             "verify_status": "verified"}
    for name, doc in (("trip-brief.yaml", {"destination": {"country": "JP", "local_lang": "ja"}}),
                      ("candidates.yaml", {"candidates": [cand]}),
                      ("verified-pois.yaml", {"pois": [prior]})):
        artifact_path(trip, name).write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    _code, _msgs, _out, pois = svr.run(str(trip), str(work), offline=True)
    got = pois[0]
    carried = _carried_fields()
    assert {"name_zh", "gmaps_place_id", "hours", "closed_days"} <= set(carried), carried
    for k in carried:
        if k in prior:
            assert got.get(k) == prior[k], k
    assert got["sources"][0].get("official") is True


def test_a_first_run_has_nothing_to_carry_and_research_keeps_its_word(tmp_path):
    from scripts import source_verify_run as svr
    from scripts.paths import artifact_path
    trip, work = tmp_path / "trip", tmp_path / "work"
    (trip / "data").mkdir(parents=True); work.mkdir()
    url = "https://blog.example/asaichi"
    cand = {"id": "asaichi", "name_local": "函館朝市", "name_display": "函館朝市", "category": "market",
            "sources": [{"url": url, "lang": "ja", "official": False}]}
    for name, doc in (("trip-brief.yaml", {"destination": {"country": "JP", "local_lang": "ja"}}),
                      ("candidates.yaml", {"candidates": [cand]})):
        artifact_path(trip, name).write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    assert svr.run(str(trip), str(work), offline=True)[3][0]["id"] == "asaichi"     # no prior file
    artifact_path(trip, "verified-pois.yaml").write_text(yaml.safe_dump({"pois": [
        {"id": "asaichi", "sources": [{"url": url, "official": True}]}]}), encoding="utf-8")
    assert svr.run(str(trip), str(work), offline=True)[3][0]["sources"][0]["official"] is False


# --- TW-091: one POI pool for the gate, the export gate and the renderers ----------

def test_the_pool_keeps_lodging_only_fields_and_verified_wins_the_rest():
    from scripts.gate import poi_pool
    verified = {"id": "h", "name_local": "サンプルイン", "category": "lodging",
                "sources": [{"url": "https://x.example/sapporo/access/", "official": True}]}
    lodging = {"id": "h", "name_local": "サンプルイン", "booking": {"required": True},
               "facilities": ["大浴場"],
               "sources": [{"url": "https://x.example/sapporo/facility/", "official": True}]}
    rec = poi_pool([verified], {"stops": [{"chosen": "h", "candidates": [lodging]}]})["h"]
    assert rec["name_local"] == "サンプルイン" and rec["sources"] == verified["sources"]
    assert rec["booking"] == {"required": True} and rec["facilities"] == ["大浴場"]


def test_the_export_gate_resolves_a_shared_id_as_the_renderer_does(tmp_path):
    """The report's sap-hotel: the same id in verified-pois and as a chosen
    lodging, each with a different first official source. The markdown is rendered
    from poi_pool (export-artifact's fold); the export gate must judge that record."""
    import subprocess
    import sys
    from scripts.paths import artifact_path, deliverable_paths, report_path, work_dir_for
    from scripts.render.markdown import render_markdown_page
    from scripts.gate import poi_pool
    from tests import mech_fixtures as M
    t, _w = M.build_full_trip(tmp_path)
    acc = M.accommodations()
    hotel = acc["stops"][0]["candidates"][0]
    hotel["booking"] = {"required": True}
    hotel["sources"][0]["url"] = "https://hotel.example/sapporo/facility/"
    pois = M.verified_pois()
    twin = copy.deepcopy(hotel)
    twin.pop("booking")
    twin["sources"][0]["url"] = "https://hotel.example/sapporo/access/"
    pois["pois"].append(twin)
    M.write_artifact(artifact_path(t, "accommodations.yaml"), acc)
    M.write_artifact(artifact_path(t, "verified-pois.yaml"), pois)
    pool = poi_pool(pois["pois"], acc)
    brief = M.trip_brief()
    deliverable_paths(t, brief)["md"].write_text(
        render_markdown_page(M.itinerary(), pool, M.cost(), brief=brief), encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "export_gate.py"), str(t)],
                       capture_output=True, text=True)
    rep = yaml.safe_load(report_path(work_dir_for(t), "export-gate-report.yaml").read_text(encoding="utf-8"))
    assert not [f for f in rep["failures"] if "official source link" in f], rep["failures"]


# --- TW-092: a district centroid must land in that district; geocode text apart ----

def test_the_district_key_is_the_place_below_the_city():
    from scripts.source_verify_run import district_key
    assert district_key("小樽市堺町") == "堺町"
    assert district_key("堺町（小樽市）") == "堺町"
    assert district_key("札幌市中央区北3条西2丁目") == "中央区"
    assert district_key("嘉義市西區") == "西区"
    assert district_key("函館") == "函館"
    assert district_key("Queenstown") == "queenstown"


def _centroid(monkeypatch, display):
    from scripts import source_verify_run as svr
    from scripts.geocode import GeocodeResult
    monkeypatch.setattr(svr, "_rate_limited_resolve",
                        lambda name, d, c, cache, name_roman=None, area=False: (GeocodeResult(43.19, 141.0, display), "nominatim"))
    return svr._district_centroid("小樽市堺町", "JP", {}, False, {})


def test_a_centroid_that_landed_elsewhere_is_refused(monkeypatch):
    assert _centroid(monkeypatch, "小樽市立 小樽美術館, 色内一丁目, 小樽市, 北海道, 日本") is None


def test_a_centroid_inside_its_district_is_kept(monkeypatch):
    assert _centroid(monkeypatch, "堺町, 小樽市, 北海道, 日本") == (43.19, 141.0)


def test_district_query_geocodes_while_district_stays_for_reading(tmp_path, monkeypatch):
    from scripts import source_verify_run as svr
    from scripts.geocode import GeocodeResult
    from scripts.paths import artifact_path
    asked = []

    def fake(name, district=None, country=None, timeout=10, cache=None, name_roman=None, pace=None, area=False):
        asked.append((name, district))
        if name == "堺町（小樽市）":
            return GeocodeResult(43.1935, 141.0035, "堺町, 小樽市, 北海道, 日本"), "nominatim"
        if name == "北一硝子三号館":
            return GeocodeResult(43.1930, 141.0040, "北一硝子三号館, 堺町, 小樽市"), "nominatim_structured"
        return None, None
    monkeypatch.setattr(svr.time, "sleep", lambda *_: None)
    monkeypatch.setattr(svr, "resolve_place", fake)
    trip, work = tmp_path / "trip", tmp_path / "work"
    (trip / "data").mkdir(parents=True); work.mkdir()
    cand = {"id": "kitaichi", "name_local": "北一硝子三号館", "name_display": "北一硝子三號館",
            "category": "shop", "claimed_district": "小樽市堺町", "district_query": "堺町（小樽市）",
            "sources": [{"url": "https://kitaichiglass.co.jp/", "lang": "ja"}]}
    for name, doc in (("trip-brief.yaml", {"destination": {"country": "JP", "local_lang": "ja"}}),
                      ("candidates.yaml", {"candidates": [cand]})):
        artifact_path(trip, name).write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    _code, msgs, _out, pois = svr.run(str(trip), str(work), offline=False)
    assert ("堺町（小樽市）", None) in asked and ("小樽市堺町", None) not in asked
    assert pois[0]["district"] == "小樽市堺町"                       # links and display keep it
    assert pois[0]["geocode"]["geocode_source"] == "nominatim_structured"


# --- TW-093: a peak window can be scoped to weekdays and areas ---------------------

PEAK = [{"label": "札幌圏 朝ラッシュ", "start": "07:20", "end": "09:00",
         "days": ["mon", "tue", "wed", "thu", "fri"], "areas": ["札幌"]}]
SUN = datetime.date(2026, 11, 15)
FRI = datetime.date(2026, 11, 13)


def test_a_scoped_peak_fires_only_on_its_days_and_areas():
    from scripts.transit import in_peak
    assert in_peak("08:40", PEAK, date=FRI, area="札幌") is True
    assert in_peak("09:00", PEAK, date=SUN, area="札幌") is False         # Sunday
    assert in_peak("08:30", PEAK, date=FRI, area="函館") is False         # not 札幌


def test_an_unscoped_peak_and_an_unknown_context_behave_as_before():
    from scripts.transit import in_peak
    plain = [{"label": "x", "start": "07:30", "end": "09:30"}]
    assert in_peak("08:00", plain, date=SUN, area="函館") is True
    assert in_peak("08:00", PEAK) is True                                 # no date/area given: cannot exclude


def test_the_transit_schema_accepts_scoped_windows():
    from scripts.validate_artifact import validate_file
    doc = {"peak_windows": [dict(PEAK[0], sources=[{"url": "https://www.mlit.go.jp/"}])], "walks": []}
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / "transit.yaml"
        f.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
        code, msgs = validate_file(str(f))
    assert code == 0, msgs


def test_a_taxi_leg_needs_a_measured_duration_like_a_drive(tmp_path):
    """Cross-axis (TW-085): the schema's 'a drive carries duration_mins' rule covers
    every road mode the leg rules treat as a drive (scripts/legs.py::ROAD_MODES)."""
    from scripts.legs import ROAD_MODES
    from scripts.validate_artifact import validate_file
    for mode in ROAD_MODES:
        for dur in (None, 30):
            leg = {"from": "a", "to": "b", "mode": mode, "status": "ok",
                   "sources": [{"url": "https://x.example/", "official": True}]}
            if dur:
                leg["duration_mins"] = dur
            f = tmp_path / f"{mode}-{dur}" / "legs.yaml"
            f.parent.mkdir()
            f.write_text(yaml.safe_dump({"legs": [leg]}), encoding="utf-8")
            code, msgs = validate_file(str(f))
            if dur:
                assert code == 0, (mode, msgs)
            else:
                assert any("'duration_mins' is a required property" in m for m in msgs), (mode, msgs)


def test_the_candidates_schema_declares_district_query(tmp_path):
    from scripts.validate_artifact import validate_file
    s = json.loads((ROOT / "schemas" / "candidates.schema.json").read_text(encoding="utf-8"))
    assert s["properties"]["candidates"]["items"]["properties"]["district_query"]["type"] == "string"


# --- TW-097: a re-run keeps a confirmed coordinate --------------------------------
# trip-e: Nominatim answers "一番館" with a Nara restaurant; the POI was confirmed
# on its district centroid (place id as proof). A plain re-run re-geocoded it to Nara
# and turned it 'conflicting' -- six such POIs, already so at fe278dd.

CENTROID = {"lat": 42.5425, "lng": 140.8643, "geocode_source": "cluster_fallback"}


def _ichibankan_run(tmp_path, monkeypatch, prior_status="verified", district="壮瞥町昭和新山", **kw):
    from scripts import source_verify_run as svr
    from scripts.geocode import GeocodeResult
    from scripts.paths import artifact_path
    from tests.test_source_verify_cli import _candidate, _stub_resolve_place
    monkeypatch.setattr(svr.time, "sleep", lambda *_: None)
    monkeypatch.setattr(svr, "resolve_place", _stub_resolve_place({
        "壮瞥町昭和新山": (GeocodeResult(42.5425, 140.8643, "昭和新山, 壮瞥町, 北海道"), "nominatim"),
        "一番館": (GeocodeResult(34.6900, 135.7140, "一番館, 奈良市, 奈良県"), "nominatim")}))
    trip, work = tmp_path / "trip", tmp_path / "work"
    (trip / "data").mkdir(parents=True); work.mkdir()
    cand = _candidate("toya-ichibankan", "一番館", claimed_district=district)
    prior = dict(cand, district="壮瞥町昭和新山", geocode=dict(CENTROID), resolved_name="NO_RESULT",
                 gmaps_place_id="ChIJ-ichibankan", verify_status=prior_status)
    prior.pop("claimed_district")
    # local_lang matches _candidate's zh source, so only the geocode decides the status
    for name, doc in (("trip-brief.yaml", {"destination": {"country": "日本", "local_lang": "zh"}}),
                      ("candidates.yaml", {"candidates": [cand]}), ("verified-pois.yaml", {"pois": [prior]})):
        artifact_path(trip, name).write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    code, msgs, _out, pois = svr.run(str(trip), str(work), offline=False, **kw)
    assert code == 0, msgs                               # the written file (geocode.query included) validates
    return pois[0]


def test_a_rerun_keeps_a_confirmed_coordinate(tmp_path, monkeypatch):
    poi = _ichibankan_run(tmp_path, monkeypatch)
    assert {k: poi["geocode"][k] for k in CENTROID} == CENTROID and poi["resolved_name"] == "NO_RESULT"
    assert poi["geocode"]["query"] == {"name": "一番館", "district": "壮瞥町昭和新山"}
    assert poi["verify_status"] == "verified", poi.get("status_reason")


def test_an_unconfirmed_coordinate_is_looked_up_again(tmp_path, monkeypatch):
    poi = _ichibankan_run(tmp_path, monkeypatch, prior_status="conflicting")
    assert poi["geocode"]["lat"] == 34.69 and poi["verify_status"] == "conflicting"


def test_a_changed_lookup_input_is_looked_up_again(tmp_path, monkeypatch):
    poi = _ichibankan_run(tmp_path, monkeypatch, district="壮瞥町")
    assert poi["geocode"]["lat"] == 34.69


def test_regeocode_asks_for_a_fresh_lookup(tmp_path, monkeypatch):
    poi = _ichibankan_run(tmp_path, monkeypatch, regeocode=True)
    assert poi["geocode"]["lat"] == 34.69 and poi["verify_status"] == "conflicting"
