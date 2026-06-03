import pytest
from scripts.geocode import geocode, GeocodeResult, in_region

class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
    def json(self):
        return self._payload
    def raise_for_status(self):
        if self.status_code != 200:
            raise RuntimeError("http error")

def test_geocode_success(mocker):
    mocker.patch("scripts.geocode.requests.get",
                 return_value=_FakeResp([{"lat": "37.5636", "lon": "126.9869",
                                          "display_name": "Myeongdong, Seoul"}]))
    r = geocode("오다리집 명동")
    assert isinstance(r, GeocodeResult)
    assert r.lat == pytest.approx(37.5636)
    assert r.lng == pytest.approx(126.9869)

def test_geocode_no_results_returns_none(mocker):
    mocker.patch("scripts.geocode.requests.get", return_value=_FakeResp([]))
    assert geocode("nonexistent place xyz") is None

def test_in_region_true():
    # point near 명동, region centroid near 명동, within 5km
    assert in_region(37.5636, 126.9869, 37.5600, 126.9850, radius_km=5.0) is True

def test_in_region_false_cross_district():
    # 강남 point vs 잠실 region centroid -> far apart, outside radius
    assert in_region(37.4979, 127.0276, 37.5133, 127.1000, radius_km=3.0) is False

def test_in_region_radius_is_configurable():
    # a point ~4km away: inside default 5km, outside a tight 2km
    from scripts.geocode import in_region
    assert in_region(37.5400, 127.0000, 37.5040, 127.0000, radius_km=5.0) is True
    assert in_region(37.5400, 127.0000, 37.5040, 127.0000, radius_km=2.0) is False
