"""#35: a shop inside a building takes the building's coordinate (and approximateness)
and, lacking its own, the building's address plus its floor. Placeholder places."""
from scripts import source_verify_run as svr
from tests.test_issue25_verify_keeps import POINT, _prior, _trip
from tests.test_source_verify_cli import _candidate


def _building(source="nominatim"):
    cand = dict(_candidate("store", "示意百貨", claimed_district="港区"), address_local="港区示意1-1",
                address_source="https://store.example/access")
    prior = _prior(cand, {"name": "示意百貨", "district": "港区"},
                   address_local="港区示意1-1", address_source="https://store.example/access")
    prior["geocode"]["geocode_source"] = source
    prior["resolved_name"] = "示意百貨, 港区"
    return cand, prior


def _shop(**kw):
    return dict(_candidate("shop", "示意菓子 示意百貨店", claimed_district="港区"), inside="store",
                floor="B1", floor_source="https://store.example/floor", **kw)


def test_a_shop_takes_its_building_s_point_and_address(tmp_path):
    b, prior = _building()
    trip, work = _trip(tmp_path, [_shop(), b], [prior])          # the shop comes first: order-free
    code, msgs, _o, pois = svr.run(str(trip), str(work), offline=True)
    shop = {p["id"]: p for p in pois}["shop"]
    assert code == 0, msgs
    assert shop["verify_status"] == "verified", shop.get("status_reason")
    assert (shop["geocode"]["lat"], shop["geocode"]["parent"]) == (POINT["lat"], "store")
    assert shop["geocode"]["geocode_source"] == "nominatim"
    assert shop["address_local"] == "港区示意1-1 B1" and shop["floor"] == "B1"


def test_an_approximate_building_keeps_its_shops_approximate(tmp_path):
    b, prior = _building("cluster_fallback")
    trip, work = _trip(tmp_path, [b, _shop()], [prior])
    shop = {p["id"]: p for p in svr.run(str(trip), str(work), offline=True)[3]}["shop"]
    assert shop["geocode"]["geocode_source"] == "cluster_fallback"


def test_a_shop_in_an_unverified_building_stays_unverified(tmp_path):
    b, _prior_b = _building()
    trip, work = _trip(tmp_path, [b, _shop()], [])                # offline, no prior: building unresolved
    shop = {p["id"]: p for p in svr.run(str(trip), str(work), offline=True)[3]}["shop"]
    assert shop["verify_status"] == "unverified" and "inside store" in shop["status_reason"]


def test_a_shop_s_own_address_wins(tmp_path):
    b, prior = _building()
    trip, work = _trip(tmp_path, [b, _shop(address_local="港区示意1-1 地下1階")], [prior])
    shop = {p["id"]: p for p in svr.run(str(trip), str(work), offline=True)[3]}["shop"]
    assert shop["address_local"] == "港区示意1-1 地下1階"
