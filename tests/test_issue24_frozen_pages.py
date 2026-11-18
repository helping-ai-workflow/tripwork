"""#24: a trip keeps its older pages frozen next to the current one. Every external
command goes through the Fake runner of test_publish_cli; the online check through a
fake fetch -- nothing is deployed."""
import hashlib

import pytest
import yaml

from scripts import publish as P
from tests.test_publish_cli import Fake, _trip


def _online(fake):
    """A fetch that serves what the fake wrangler uploaded."""
    def fetch(url):
        code = url.rstrip("/").rsplit("/", 1)[-1]
        return fake.texts[f"{code}/index.html"].encode("utf-8")
    return fetch


def _two_pages(tmp_path):
    t = _trip(tmp_path)
    P.build(t, "pw", run=Fake())
    old = P.publish_code(t)
    new = P.new_code(t)
    P.build(t, "pw2", run=Fake())
    return t, old, new


def test_new_code_freezes_the_current_page_and_records_its_sha(tmp_path):
    t, old, new = _two_pages(tmp_path)
    assert new != old and P.publish_code(t) == new
    codes = {e["code"]: e for e in P.page_codes(t)}
    page = t / "publish" / old / "index.html"
    assert codes[old]["frozen"] and codes[old]["sha256"] == hashlib.sha256(page.read_bytes()).hexdigest()
    assert codes[new]["frozen"] is False


def test_deploy_uploads_the_current_and_every_frozen_page(tmp_path):
    t, old, new = _two_pages(tmp_path)
    before = (t / "publish" / old / "index.html").read_bytes()
    fake = Fake()
    res = P.deploy(t, "tripwork-demo", confirm=True, run=fake, fetch=_online(fake))
    assert fake.uploaded == sorted([f"{old}/index.html", f"{new}/index.html"])
    assert fake.texts[f"{old}/index.html"].encode("utf-8") == before        # byte for byte, not rebuilt
    assert res["url"].endswith(f"/{new}/") and res["frozen"][0].endswith(f"/{old}/")


def test_a_frozen_page_changed_on_disk_stops_the_deploy(tmp_path):
    t, old, _new = _two_pages(tmp_path)
    (t / "publish" / old / "index.html").write_text(P._LOCKED + " rebuilt", encoding="utf-8")
    fake = Fake()
    with pytest.raises(P.PublishError, match="changed on disk"):
        P.deploy(t, "tripwork-demo", confirm=True, run=fake, fetch=_online(fake))
    assert not any("deploy" in c for c in fake.calls)


def test_a_frozen_page_that_differs_online_stops_after_the_deploy(tmp_path):
    t, _old, _new = _two_pages(tmp_path)
    with pytest.raises(P.PublishError, match="differs"):
        P.deploy(t, "tripwork-demo", confirm=True, run=Fake(), fetch=lambda url: b"something else")


def test_an_unlisted_page_on_disk_stops_the_deploy_rather_than_deleting_it(tmp_path):
    # a trip whose older page was deployed by hand: no codes.yaml yet
    t = _trip(tmp_path)
    P.build(t, "pw", run=Fake())
    (t / "publish" / "zz000000").mkdir()
    (t / "publish" / "zz000000" / "index.html").write_text(P._LOCKED, encoding="utf-8")
    fake = Fake()
    with pytest.raises(P.PublishError, match="zz000000"):
        P.deploy(t, "tripwork-demo", confirm=True, run=fake, fetch=_online(fake))
    assert not any("deploy" in c for c in fake.calls)
    P.freeze(t, "zz000000")                                  # adopt it
    res = P.deploy(t, "tripwork-demo", confirm=True, run=fake, fetch=_online(fake))
    assert "zz000000/index.html" in fake.uploaded and res["frozen"]


def test_retire_takes_a_page_off_and_the_unconfirmed_deploy_says_so(tmp_path):
    t, old, new = _two_pages(tmp_path)
    with pytest.raises(P.PublishError, match="only a frozen page"):
        P.retire(t, new)                                     # never the current page
    P.retire(t, old)
    with pytest.raises(P.PublishError, match=f"REMOVE {old}"):
        P.deploy(t, "tripwork-demo", run=Fake())
    fake = Fake()
    res = P.deploy(t, "tripwork-demo", confirm=True, run=fake, fetch=_online(fake))
    assert fake.uploaded == [f"{new}/index.html"] and res["removed"][0].endswith(f"/{old}/")


def test_a_trip_with_one_page_deploys_as_before(tmp_path):
    t = _trip(tmp_path)
    P.build(t, "pw", run=Fake())
    fake = Fake()
    res = P.deploy(t, "tripwork-demo", confirm=True, run=fake, fetch=lambda u: pytest.fail("no fetch"))
    assert fake.uploaded == [f"{P.publish_code(t)}/index.html"] and res["frozen"] == []
    assert not (t / "publish" / "codes.yaml").exists()


def test_the_cli_freezes_and_retires_without_a_password(tmp_path, monkeypatch):
    monkeypatch.delenv("TRIPWORK_PUBLISH_PASSWORD", raising=False)
    t = _trip(tmp_path)
    P.build(t, "pw", run=Fake())
    code = P.publish_code(t)
    assert P.main(["build", str(t), "--freeze", code]) == 0
    assert yaml.safe_load((t / "publish" / "codes.yaml").read_text())["codes"][0]["frozen"] is True
    assert P.main(["build", str(t), "--retire", "nosuch00"]) == 1
