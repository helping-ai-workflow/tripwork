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

def test_backend_google_blocked_raises():
    # MIGRATED (Task 6): HEAD silently returned None; that silence is what let
    # 78 hand-written google entries reach 5 real trips undetected. The
    # backend now refuses loudly instead.
    with pytest.raises(ValueError, match="google"):
        fetch_media_entry(_LANDMARK, "google")

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


# ---- Task 6: photo enrichment gets an owner (CLI + loud google refusal) ----

import subprocess
import sys
from scripts.paths import artifact_path, deliverable_paths, report_path, work_dir_for

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_google_backend_refuses_instead_of_returning_an_empty_result():
    """HEAD returns {'media': {}} — a silent empty result with no refusal and no
    error. That silence is what let 78 hand-written google entries into 5 real
    trips and made all 5 deliverables permanently non-distributable."""
    with pytest.raises(ValueError, match="google"):
        build_media([{"id": "p1", "name_display": "花磚"}], "google")


def test_write_media_sidefile_refuses_to_leave_an_invalid_file_on_disk(tmp_path):
    """HEAD writes the file and only then fails validation, so an invalid
    side-file survives to be read by the export gate."""
    p = tmp_path / "verified-pois-media.yaml"
    with pytest.raises(ValueError):
        write_media_sidefile(str(p), {"media": {"poi-1": {}}})
    assert not p.exists()


def test_cli_refuses_google_with_exit_2_and_writes_nothing(tmp_path):
    trip = tmp_path / "trip"; artifact_path(trip, "x").parent.mkdir(parents=True)
    (artifact_path(trip, "verified-pois.yaml")).write_text("pois: []\n", encoding="utf-8")
    r = subprocess.run([sys.executable, "scripts/photo_adapter.py", str(trip),
                        "--backend", "google"], cwd=str(ROOT), capture_output=True, text=True)
    assert r.returncode == 2
    assert not (artifact_path(trip, "verified-pois-media.yaml")).exists()


def test_cli_missing_input_exits_2(tmp_path):
    r = subprocess.run([sys.executable, "scripts/photo_adapter.py",
                        str(tmp_path / "nope"), "--backend", "wiki"],
                       cwd=str(ROOT), capture_output=True, text=True)
    assert r.returncode == 2


def test_backend_none_is_a_noop_that_exits_zero(tmp_path):
    trip = tmp_path / "trip"; artifact_path(trip, "x").parent.mkdir(parents=True)
    (artifact_path(trip, "verified-pois.yaml")).write_text("pois: []\n", encoding="utf-8")
    r = subprocess.run([sys.executable, "scripts/photo_adapter.py", str(trip),
                        "--backend", "none"], cwd=str(ROOT), capture_output=True, text=True)
    assert r.returncode == 0


# ---- a failed download is not the end (measured 2026-10-04: Openverse answered 424 on
# thumbnails for 12 of 23 landmarks of a real trip, and each one aborted its POI) ----

import requests as _requests


class _Fail(_Resp):
    def __init__(self, status=424):
        super().__init__(status=status)

    def raise_for_status(self):
        raise _requests.HTTPError(f"{self.status_code} Client Error")


def test_a_failed_thumbnail_keeps_the_full_image(mocker):
    mocker.patch("scripts.photo_adapter.requests.get", side_effect=[_ov([_OV_RESULT]), _IMG_FULL, _Fail()])
    entry = fetch_media_entry(_LANDMARK, "wiki", sources=("openverse",))
    assert entry and entry["photo"]["data"].startswith("data:image/jpeg;base64,")
    assert "thumb" not in entry["photo"]


def test_a_failed_download_tries_the_next_candidate(mocker):
    second = {**_OV_RESULT, "url": "https://ov.example/2.jpg", "thumbnail": "https://ov.example/2t.jpg",
              "creator": "Second", "foreign_landing_url": "https://openverse.org/i/2"}
    mocker.patch("scripts.photo_adapter.requests.get",
                 side_effect=[_ov([_OV_RESULT, second]), _Fail(), _IMG_FULL, _IMG_THUMB])
    entry = fetch_media_entry(_LANDMARK, "wiki", sources=("openverse",))
    assert entry and entry["photo_attribution"]["author"] == "Second"


def test_one_failed_poi_does_not_stop_the_rest(mocker):
    other = {**_LANDMARK, "id": "p2", "name_local": "Senso-ji"}
    mocker.patch("scripts.photo_adapter.requests.get",
                 side_effect=[_ov([_OV_RESULT]), _Fail(500), _ov([_OV_RESULT]), _IMG_FULL, _IMG_THUMB])
    doc = build_media([_LANDMARK, other], "wiki", sources=("openverse",))
    assert list(doc["media"]) == ["p2"]


def test_build_media_keeps_existing_entries_and_does_not_look_them_up(mocker):
    from scripts import photo_adapter as pa
    seen = []
    mocker.patch.object(pa, "fetch_media_entry", side_effect=lambda poi, *a, **k: seen.append(poi["id"]) or {"photo": {"data": "data:image/png;base64,AA=="}, "photo_attribution": {"author": "a", "license": "CC0", "source_url": "https://x.example/1"}, "photo_source": "wikimedia"})
    mine = {"photo": {"data": "data:image/jpeg;base64,BB=="}, "photo_attribution": {"author": "me", "license": "personal", "source_url": "https://y.example/2"}, "photo_source": "google"}
    pois = [{"id": "a", "name_local": "A", "category": "sight"}, {"id": "b", "name_local": "B", "category": "sight"}]
    doc = pa.build_media(pois, "wiki", existing={"a": mine})
    assert doc["media"]["a"] == mine
    assert seen == ["b"]


def test_existing_entry_without_photo_is_still_kept(mocker):
    from scripts import photo_adapter as pa
    mocker.patch.object(pa, "fetch_media_entry", side_effect=AssertionError("must not look up a provided POI"))
    odd = {"photo_source": "google", "note": "user left this"}
    doc = pa.build_media([{"id": "a", "name_local": "A", "category": "sight"}], "wiki", existing={"a": odd})
    assert doc["media"]["a"] == odd


def test_cli_merges_into_the_existing_sidefile(tmp_path, mocker):
    from scripts import photo_adapter as pa
    from scripts.paths import artifact_path
    import yaml
    trip = tmp_path / "trips" / "t"
    (trip / "data").mkdir(parents=True)
    artifact_path(trip, "verified-pois.yaml").write_text(yaml.safe_dump({"pois": [
        {"id": "a", "name_local": "A", "category": "sight"}, {"id": "b", "name_local": "B", "category": "sight"}]}), encoding="utf-8")
    mine = {"photo": {"data": "data:image/jpeg;base64,BB=="}, "photo_attribution": {"author": "me", "license": "CC0", "source_url": "https://y.example/2"}, "photo_source": "wikimedia"}
    artifact_path(trip, "verified-pois-media.yaml").write_text(yaml.safe_dump({"media": {"a": mine}}), encoding="utf-8")
    mocker.patch.object(pa, "fetch_media_entry", return_value={"photo": {"data": "data:image/png;base64,AA=="}, "photo_attribution": {"author": "x", "license": "CC0", "source_url": "https://x.example/1"}, "photo_source": "wikimedia"})
    assert pa.main([str(trip), "--backend", "wiki"]) == 0
    media = yaml.safe_load(artifact_path(trip, "verified-pois-media.yaml").read_text(encoding="utf-8"))["media"]
    assert media["a"] == mine and "b" in media


WD_SEARCH = {"search": [{"id": "Q1"}, {"id": "Q2"}]}
WD_ENTITIES = {"entities": {
    "Q1": {"claims": {"P625": [{"mainsnak": {"datavalue": {"value": {"latitude": 40.0, "longitude": 140.0}}}}],
                      "P18": [{"mainsnak": {"datavalue": {"value": "Far.jpg"}}}]}},
    "Q2": {"claims": {"P625": [{"mainsnak": {"datavalue": {"value": {"latitude": 35.7101, "longitude": 139.8107}}}}],
                      "P18": [{"mainsnak": {"datavalue": {"value": "Skytree.jpg"}}}]}}}}
WD_FILE = {"query": {"pages": {"1": {"imageinfo": [{"url": "https://upload.wikimedia.org/o.jpg", "thumburl": "https://upload.wikimedia.org/t.jpg",
    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Skytree.jpg",
    "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}, "Artist": {"value": "<a>Someone</a>"}}}]}}}}


def _wd_get(mocker):
    from scripts import photo_adapter as pa
    def fake(url, params=None, **kw):
        r = mocker.Mock(); r.raise_for_status = lambda: None
        if "wikidata" in url and params.get("action") == "wbsearchentities":
            r.json = lambda: WD_SEARCH
        elif "wikidata" in url:
            r.json = lambda: WD_ENTITIES
        else:
            # the file page echoes the requested title, so picking the far entity is visible
            title = params["titles"].split(":", 1)[1]
            doc = json.loads(json.dumps(WD_FILE))
            doc["query"]["pages"]["1"]["imageinfo"][0]["descriptionurl"] = "https://commons.wikimedia.org/wiki/File:" + title
            r.json = lambda: doc
        return r
    return mocker.patch.object(pa.requests, "get", side_effect=fake)


def test_wikidata_picks_the_entity_within_1km_and_reads_p18(mocker):
    from scripts import photo_adapter as pa
    _wd_get(mocker)
    cands = pa._search_wikidata("東京スカイツリー", None, 5, geo={"lat": 35.7100, "lng": 139.8107})
    assert len(cands) == 1
    c = cands[0]
    assert c["source"] == "wikimedia" and c["license"] == "CC BY-SA 4.0" and c["author"] == "Someone"
    assert c["image_url"] == "https://upload.wikimedia.org/t.jpg"
    assert c["source_url"] == "https://commons.wikimedia.org/wiki/File:Skytree.jpg"


def test_wikidata_without_coordinates_returns_nothing(mocker):
    from scripts import photo_adapter as pa
    _wd_get(mocker)
    assert pa._search_wikidata("東京スカイツリー", None, 5, geo={}) == []


def test_wikidata_is_tried_before_the_searches(mocker):
    from scripts import photo_adapter as pa
    order = []
    for name in ("wikidata", "openverse", "commons"):
        mocker.patch.dict(pa._SEARCHERS, {name: (lambda n: lambda *a, **k: order.append(n) or [])(name)})
    pa.fetch_media_entry({"id": "x", "name_local": "X", "geocode": {"lat": 1, "lng": 2}}, "wiki")
    assert order == ["wikidata", "openverse", "commons"]


def test_lang_of_reads_the_script():
    from scripts.photo_adapter import _lang_of
    assert _lang_of("東京スカイツリー") == "ja"
    assert _lang_of("경복궁") == "ko"
    assert _lang_of("日月潭") == "zh"
    assert _lang_of("Eiffel Tower") == "en"
