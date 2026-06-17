"""Tests for scripts/photo_adapter.py — pluggable CC photo adapter (backend=wiki).

Network is mocked (pytest-mock) by patching scripts.photo_adapter.requests.get,
mirroring test_geocode.py. No real HTTP, no real sleeping.
"""
import json
import pathlib

import pytest

from scripts.photo_adapter import (
    USER_AGENT, RateLimiter, license_allowed, fetch_media_entry, build_media,
    write_media_sidefile, _select_candidate,
)

SCHEMAS = pathlib.Path(__file__).resolve().parent.parent / "schemas"


class _Resp:
    def __init__(self, *, json_data=None, content=b"", content_type="application/json", status=200):
        self._json = json_data
        self.content = content
        self.headers = {"Content-Type": content_type}
        self.status_code = status

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")


_OV_RESULT = {
    "url": "https://ov.example/full.jpg",
    "thumbnail": "https://ov.example/thumb.jpg",
    "license": "by-sa",
    "creator": "Jane",
    "foreign_landing_url": "https://openverse.org/i/1",
}
_IMG_FULL = _Resp(content=b"\xff\xd8\xff\xff FULLBYTES", content_type="image/jpeg")
_IMG_THUMB = _Resp(content=b"\xff\xd8\xff\xff THUMBYTES", content_type="image/jpeg")

def _ov(results):
    return _Resp(json_data={"results": results})

_LANDMARK = {"id": "p1", "name_local": "Tokyo Tower", "category": "landmark",
             "geocode": {"lat": 35.6586, "lng": 139.7454}}


# ---- license whitelist ----

@pytest.mark.parametrize("lic", ["CC0", "CC0-1.0", "PD", "Public Domain",
                                  "CC-BY", "CC BY 4.0", "CC-BY-SA", "CC BY-SA 4.0"])
def test_license_allowed_accepts_clean_cc(lic):
    assert license_allowed(lic) is True

@pytest.mark.parametrize("lic", ["CC-BY-NC", "CC BY-NC 4.0", "CC-BY-ND", "CC-BY-NC-SA",
                                  "CC BY-NC-ND 4.0", "All rights reserved", "", None])
def test_license_allowed_rejects_nc_nd_and_unknown(lic):
    assert license_allowed(lic) is False


# ---- backend dispatch ----

def test_backend_none_returns_none():
    assert fetch_media_entry(_LANDMARK, "none") is None

def test_backend_google_blocked_returns_none():
    assert fetch_media_entry(_LANDMARK, "google") is None

def test_unknown_backend_raises():
    with pytest.raises(ValueError):
        fetch_media_entry(_LANDMARK, "flickr")

def test_wiki_no_name_returns_none():
    assert fetch_media_entry({"id": "p"}, "wiki") is None


# ---- location match ----

def test_select_candidate_rejects_far_geotag():
    cands = [{"source": "openverse", "license": "CC0", "image_url": "https://x",
              "thumb_url": None, "author": "A", "source_url": "https://s",
              "lat": 0.0, "lng": 0.0}]
    assert _select_candidate(cands, {"lat": 35.0, "lng": 139.0}, 5.0) is None

def test_select_candidate_accepts_near_geotag():
    cands = [{"source": "openverse", "license": "CC0", "image_url": "https://x",
              "thumb_url": None, "author": "A", "source_url": "https://s",
              "lat": 35.001, "lng": 139.001}]
    assert _select_candidate(cands, {"lat": 35.0, "lng": 139.0}, 5.0) is not None

def test_select_candidate_accepts_no_coords():
    cands = [{"source": "openverse", "license": "CC-BY", "image_url": "https://x",
              "thumb_url": None, "author": "A", "source_url": "https://s",
              "lat": None, "lng": None}]
    assert _select_candidate(cands, {"lat": 35.0, "lng": 139.0}, 5.0) is not None


# ---- end-to-end wiki fetch (mocked) ----

def test_user_agent_header_sent(mocker):
    get = mocker.patch("scripts.photo_adapter.requests.get",
                       side_effect=[_ov([_OV_RESULT]), _IMG_FULL, _IMG_THUMB])
    fetch_media_entry(_LANDMARK, "wiki", sources=("openverse",))
    assert get.call_args_list
    for call in get.call_args_list:
        assert call.kwargs["headers"]["User-Agent"] == USER_AGENT

def test_base64_two_sizes(mocker):
    mocker.patch("scripts.photo_adapter.requests.get",
                 side_effect=[_ov([_OV_RESULT]), _IMG_FULL, _IMG_THUMB])
    entry = fetch_media_entry(_LANDMARK, "wiki", sources=("openverse",))
    assert entry["photo"]["data"].startswith("data:image/jpeg;base64,")
    assert entry["photo"]["thumb"]["data"].startswith("data:image/jpeg;base64,")
    assert entry["photo_source"] == "openverse"
    assert entry["photo_attribution"]["license"] == "CC-BY-SA"
    assert entry["photo_attribution"]["author"] == "Jane"
    assert entry["photo_attribution"]["source_url"] == "https://openverse.org/i/1"

def test_nc_licensed_candidate_rejected_no_download(mocker):
    nc = {**_OV_RESULT, "license": "by-nc"}
    get = mocker.patch("scripts.photo_adapter.requests.get", side_effect=[_ov([nc])])
    assert fetch_media_entry(_LANDMARK, "wiki", sources=("openverse",)) is None
    assert get.call_count == 1   # search only; never downloaded the rejected image

def test_cache_short_circuits_network(mocker):
    get = mocker.patch("scripts.photo_adapter.requests.get",
                       side_effect=[_ov([_OV_RESULT]), _IMG_FULL, _IMG_THUMB])
    cache = {}
    e1 = fetch_media_entry(_LANDMARK, "wiki", sources=("openverse",), cache=cache)
    n = get.call_count
    e2 = fetch_media_entry(_LANDMARK, "wiki", sources=("openverse",), cache=cache)
    assert get.call_count == n   # no new network on the cache hit
    assert e2 == e1


# ---- rate limit ----

def test_rate_limiter_waits_between_calls():
    sleeps, clk = [], [0.0]
    rl = RateLimiter(min_interval=1.0, sleep=sleeps.append, clock=lambda: clk[0])
    rl.wait()   # first call — no sleep
    rl.wait()   # elapsed 0 < 1 -> must sleep ~1
    assert sleeps and sleeps[0] == pytest.approx(1.0, abs=0.01)

def test_rate_limiter_no_sleep_when_interval_elapsed():
    sleeps, clk = [], [0.0]
    rl = RateLimiter(min_interval=1.0, sleep=sleeps.append, clock=lambda: clk[0])
    rl.wait()
    clk[0] = 2.0      # 2s later -> no wait needed
    rl.wait()
    assert sleeps == []


# ---- build_media + side-file write (ties to PR1 schema + PR6 loader) ----

def test_build_media_writes_schema_valid_sidefile(mocker, tmp_path):
    import jsonschema
    mocker.patch("scripts.photo_adapter.requests.get",
                 side_effect=[_ov([_OV_RESULT]), _IMG_FULL, _IMG_THUMB])
    doc = build_media([_LANDMARK], "wiki", sources=("openverse",))
    assert "p1" in doc["media"]
    schema = json.load(open(SCHEMAS / "verified-pois-media.schema.json"))
    jsonschema.validate(doc, schema)   # must not raise

    path = tmp_path / "verified-pois-media.yaml"
    write_media_sidefile(path, doc)
    from scripts.media_merge import load_media
    assert load_media(path)["media"]["p1"]["photo_source"] == "openverse"

def test_build_media_skips_non_landmark(mocker):
    get = mocker.patch("scripts.photo_adapter.requests.get")
    doc = build_media([{"id": "r1", "name_local": "壽司", "category": "restaurant"}], "wiki")
    assert doc["media"] == {}
    get.assert_not_called()
