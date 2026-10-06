"""v2.1.0 §3 (D5): a Taiwanese address Nominatim resolves only to its road stands in when no
name lookup is accepted -- the road point inside the district, else its 村里's centre --
approximate, disclosed, and never a veto on a name hit. Made-up addresses, fake Nominatim."""
import pytest

from scripts import geocode as G
from scripts import source_verify_run as svr
from scripts.render.centroid import APPROX_SOURCES, centroid_note

HERE = (25.1360, 121.5060)                    # the claimed district's centre
ADDR = "臺南市中西區示意路100號"
ROAD = "臺南市中西區示意路"
FAR = (25.0300, 121.5600)                     # ~13 km away


class _Resp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def _hit(name, at, **kw):
    return {"lat": str(at[0]), "lon": str(at[1]), "display_name": name, **kw}


@pytest.fixture
def run(monkeypatch):
    """run(answer, cand=None) -> (geo, resolved, region_checked), recording queries."""
    monkeypatch.setattr(svr.time, "sleep", lambda *_: None)
    monkeypatch.setattr(svr, "_district_centroid", lambda *a, **kw: HERE)
    seen = []

    def go(answer, cand=None, centroid=HERE):
        monkeypatch.setattr(svr, "_district_centroid", lambda *a, **kw: centroid)

        def get(url, params=None, headers=None, timeout=None):
            seen.append(dict(params or {}))
            return _Resp(answer(dict(params or {})))
        monkeypatch.setattr(G.requests, "get", get)
        c = cand or {"name_local": "示意小館", "claimed_district": "中西區", "address_local": ADDR}
        geo, _g, _inr, resolved, checked = svr._geocode_candidate(c, "TW", {}, False, {}, 5.0)
        return geo, resolved, checked
    go.seen = seen
    return go


ROAD_HIT = _hit("示意路, 示意里, 中西區, 臺南市, 臺灣", (25.1365, 121.5070),
                address={"road": "示意路", "suburb": "示意里", "city_district": "中西區", "city": "臺南市"})


def test_road_point_used_only_when_every_tier_fails(run):
    geo, _, _ = run(lambda p: [_hit("示意小館, 中西區", (25.1362, 121.5061))] if p.get("street") == "示意小館"
                    else [ROAD_HIT] if p.get("q") == ROAD else [])
    assert geo["geocode_source"] == "nominatim_structured"


def test_road_point_in_district_becomes_nominatim_road(run):
    geo, resolved, checked = run(lambda p: [ROAD_HIT] if p.get("q") == ROAD else [])
    assert geo["geocode_source"] == "nominatim_road" and (geo["lat"], geo["lng"]) == (25.1365, 121.5070)
    assert checked is True


def test_road_point_outside_district_falls_to_village(run):
    far_road = dict(ROAD_HIT, lat=str(FAR[0]), lon=str(FAR[1]))
    geo, _, _ = run(lambda p: [far_road] if p.get("q") == ROAD else
                    [_hit("示意里", (25.1370, 121.5050), **{"class": "boundary"})] if p.get("q", "").endswith("示意里")
                    else [])
    assert geo["geocode_source"] == "village_centroid"


def test_village_lookup_uses_county_district_prefix(run):
    far_road = dict(ROAD_HIT, lat=str(FAR[0]), lon=str(FAR[1]))
    run(lambda p: [far_road] if p.get("q") == ROAD else [])
    assert "臺南市中西區示意里" in [p.get("q") for p in run.seen]


def test_namesake_village_in_other_county_rejected(run):
    far_road = dict(ROAD_HIT, lat=str(FAR[0]), lon=str(FAR[1]))
    geo, _, _ = run(lambda p: [far_road] if p.get("q") == ROAD else
                    [_hit("示意里", FAR, **{"class": "boundary"})] if p.get("q", "").endswith("示意里") else [])
    assert geo["geocode_source"] == "cluster_fallback"


def test_village_must_be_a_place_or_boundary(run):
    far_road = dict(ROAD_HIT, lat=str(FAR[0]), lon=str(FAR[1]))
    geo, _, _ = run(lambda p: [far_road] if p.get("q") == ROAD else
                    [_hit("示意里活動中心", (25.1370, 121.5050), **{"class": "amenity"})]
                    if p.get("q", "").endswith("示意里") else [])
    assert geo["geocode_source"] == "cluster_fallback"


def test_no_district_centre_rejects_road_and_village(run):
    geo, _, checked = run(lambda p: [ROAD_HIT] if p.get("q") == ROAD else [], centroid=None)
    assert geo is None and checked is False


def test_road_point_never_vetoes_a_name_hit(run):
    # the name hit is 1.5 km from the road point: kept (a road is kilometres long)
    geo, _, _ = run(lambda p: [_hit("示意小館, 中西區", (25.1500, 121.5100))] if p.get("street") == "示意小館"
                    else [ROAD_HIT] if p.get("q") == ROAD else [])
    assert geo["geocode_source"] == "nominatim_structured" and geo["lat"] == 25.15


def test_only_taiwan_uses_road_points(monkeypatch):
    monkeypatch.setattr(svr.time, "sleep", lambda *_: None)
    monkeypatch.setattr(svr, "_district_centroid", lambda *a, **kw: HERE)
    monkeypatch.setattr(G.requests, "get", lambda url, params=None, **kw: _Resp([ROAD_HIT] if (params or {}).get("q") == ROAD else []))
    geo, *_ = svr._geocode_candidate({"name_local": "示意小館", "claimed_district": "中西區", "address_local": ADDR},
                                     "KR", {}, False, {}, 5.0)
    assert geo["geocode_source"] == "cluster_fallback"


def test_village_of_reads_the_address_parts():
    assert G.village_of({"neighbourhood": "某某社區", "suburb": "示意里"}) == "示意里"
    assert G.village_of({"quarter": "示意村"}) == "示意村"
    assert G.village_of({"suburb": "中西區"}) is None and G.village_of(None) is None


def test_county_district():
    assert G.county_district("臺南市中西區示意路100號") == "臺南市中西區"
    assert G.county_district("宜蘭縣礁溪鄉示意路1號") == "宜蘭縣礁溪鄉"
    assert G.county_district("示意路1號") is None


def test_geocoderesult_three_positional_args_still_work():
    assert G.GeocodeResult(1.0, 2.0, "x").address is None


def test_approx_sources_cover_new_values():
    assert {"nominatim_road", "village_centroid"} <= set(APPROX_SOURCES)


def test_disclosure_wording():
    road = {"name_display": "示意小館", "geocode": {"geocode_source": "nominatim_road"}}
    vill = {"name_display": "示意小館", "geocode": {"geocode_source": "village_centroid"}}
    assert "它地址那條路上的一點" in centroid_note(road)
    assert "它所在村里的中心點" in centroid_note(vill)
