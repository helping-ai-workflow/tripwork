"""v2.0.0 consumer report D1 + D2 (folded into 2.0.0 by the user).

D1: one trip is one Pages project -- `deploy` uploads that trip's locked page only.
D2: what source-verify writes for a place with an address must pass its own schema
(v1.3.0 recorded geocode.query.address, which the schema did not allow; its tests
checked the dict, never the artifact).
"""
import pytest
import yaml

from scripts import publish as P
from tests.test_publish_cli import Fake, _trip
from tests.test_v130_address import FAR, HAKODATE, _run


def test_deploy_uploads_only_this_trip(tmp_path):
    a, b = _trip(tmp_path, "2026-05-demo"), _trip(tmp_path, "2026-06-demo")
    P.build(a, "pw", run=Fake())
    P.build(b, "pw", run=Fake())
    fake = Fake()
    res = P.deploy(a, "tripwork-demo", confirm=True, run=fake)
    assert fake.uploaded == [f"{P.publish_code(a)}/index.html"]
    assert res["url"] == f"https://tripwork-demo.pages.dev/{P.publish_code(a)}/"


def test_deploy_ignores_another_trips_unlocked_page(tmp_path):
    """Another trip's page is not this deploy's business, locked or not."""
    a, b = _trip(tmp_path, "2026-05-demo"), _trip(tmp_path, "2026-06-demo")
    P.build(a, "pw", run=Fake())
    other = P.build(b, "pw", run=Fake())["page"]
    other.write_text("<!doctype html><title>plain</title>", encoding="utf-8")
    fake = Fake()
    P.deploy(a, "tripwork-demo", confirm=True, run=fake)
    assert fake.uploaded == [f"{P.publish_code(a)}/index.html"]


def _validate_pois(tmp_path, poi):
    from scripts.validate_artifact import validate_file
    from tests.test_rederive import _poi_rec
    rec = _poi_rec(geocode=poi)
    f = tmp_path / "verified-pois.yaml"
    f.write_text(yaml.safe_dump({"pois": [rec]}, allow_unicode=True), encoding="utf-8")
    return validate_file(str(f))


@pytest.mark.parametrize("name_hit", [FAR, None], ids=["address-overrides-a-namesake", "address-only"])
def test_a_place_with_an_address_writes_a_schema_valid_geocode(tmp_path, monkeypatch, name_hit):
    (geo, *_), _ = _run(monkeypatch, name_hit, HAKODATE)
    assert geo["query"]["address"]                      # the shipped lookup records it
    code, msgs = _validate_pois(tmp_path, geo)
    assert code == 0, msgs
