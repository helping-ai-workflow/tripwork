"""#29 A': a place whose own address names the claimed district is in it beyond the
5 km radius, up to REGION_CAP_KM from the district's centre. Placeholder venue names;
the geography is public (a city centre and a point 9 km out)."""
import yaml

from scripts import geocode
from scripts import source_verify_run as svr
from scripts.geocode import GeocodeResult, REGION_CAP_KM, in_claimed
from scripts.paths import artifact_path
from tests.test_source_verify_cli import _candidate, _stub_resolve_place

CITY = (43.7707, 142.3650)                     # a city centre
EDGE = (43.7680, 142.4790)                     # ~9.2 km east, still inside the city
FAR = (43.4300, 142.3650)                      # ~38 km south


def _run(tmp_path, monkeypatch, point, display):
    monkeypatch.setattr(svr.time, "sleep", lambda *_: None)
    monkeypatch.setattr(svr, "resolve_place", _stub_resolve_place({
        "旭川市": (GeocodeResult(*CITY, "旭川市, 上川総合振興局, 北海道, 日本"), "nominatim"),
        "サンプル動物園": (GeocodeResult(*point, display), "nominatim")}))
    monkeypatch.setattr(svr, "_district_fallback", lambda *a: None)
    trip, work = tmp_path / "trip", tmp_path / "work"
    (trip / "data").mkdir(parents=True)
    cand = _candidate("zoo", "サンプル動物園", claimed_district="旭川市")
    for name, doc in (("trip-brief.yaml", {"destination": {"country": "JP", "local_lang": "zh-TW"}}),
                      ("candidates.yaml", {"candidates": [cand]})):
        artifact_path(trip, name).write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return svr.run(str(trip), str(work), offline=False)[3][0]


def test_a_venue_on_the_city_edge_named_in_the_city_passes(tmp_path, monkeypatch):
    poi = _run(tmp_path, monkeypatch, EDGE, "サンプル動物園, 倉沼, 東旭川町倉沼, 旭川市, 上川総合振興局, 北海道, 日本")
    assert poi["verify_status"] == "verified", poi.get("status_reason")


def test_the_same_distance_in_another_town_is_still_outside(tmp_path, monkeypatch):
    poi = _run(tmp_path, monkeypatch, EDGE, "サンプル動物園, 東川町, 上川郡, 北海道, 日本")
    assert poi["verify_status"] == "conflicting"


def test_beyond_the_cap_a_named_city_does_not_save_it(tmp_path, monkeypatch):
    poi = _run(tmp_path, monkeypatch, FAR, "サンプル動物園, 旭川市, 上川総合振興局, 北海道, 日本")
    assert poi["verify_status"] == "conflicting"


def test_the_venue_s_own_name_is_not_an_address_part():
    assert not svr.named_in("旭川市", "旭川市, 東川町, 北海道")         # part 0 is the venue
    assert svr.named_in("札幌市中央区北3条西2丁目", "サンプル, 北3条西2丁目, 中央区, 札幌市")
    assert svr.named_in("台東縣池上鄉", "示意, 池上鄉, 臺東縣, 臺灣")


def test_in_claimed_keeps_the_radius_and_adds_the_cap():
    named = lambda dn: "旭川市" in dn
    assert in_claimed(*CITY, "x, 東川町", (*CITY, 5.0, named))            # inside the radius
    assert in_claimed(*EDGE, "x, 旭川市", (*CITY, 5.0, named))
    assert not in_claimed(*EDGE, "x, 東川町", (*CITY, 5.0, named))
    assert not in_claimed(*FAR, "x, 旭川市", (*CITY, 5.0, named))
    assert not in_claimed(*EDGE, "x, 旭川市", (*CITY, 5.0))                # no name test: radius only
    assert REGION_CAP_KM == 30.0


def test_a_bare_name_lookup_on_the_city_edge_is_accepted():
    r = GeocodeResult(*EDGE, "サンプル動物園, 東旭川町倉沼, 旭川市, 北海道")
    region = (*CITY, 5.0, lambda dn: svr.named_in("旭川市", dn))
    assert geocode.accept(r, geocode.BARE_NAME_TIERS[0], "サンプル動物園", region=region)
    assert not geocode.accept(r, geocode.BARE_NAME_TIERS[0], "サンプル動物園", region=(*CITY, 5.0))
