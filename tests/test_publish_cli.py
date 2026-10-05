"""v1.2 spec section 3: scripts/publish.py -- build the publish page, encrypt it with
staticrypt, deploy to Cloudflare Pages only after confirmation. Every external command
goes through a fake `run`: no node, no network, nothing deployed."""
import pathlib
import subprocess

import pytest

from scripts import publish as P
from scripts.render.publish.lock import STATICRYPT

LOCKED = "<!doctype html><title>locked</title><script>const staticryptConfig = {};</script>ENCRYPTED"


def _trip(root, slug="2026-05-demo"):
    from scripts.paths import artifact_path
    from tests import mech_fixtures as M
    from tests import reader_fixture as R
    t, _ = M.build_full_trip(root, slug=slug)
    M.write_artifact(artifact_path(t, "itinerary.yaml"), R.itinerary())
    M.write_artifact(artifact_path(t, "verified-pois.yaml"), {"pois": list(R.poi_map().values())})
    return t


class Fake:
    """Stands in for subprocess.run: staticrypt writes a locked page, wrangler answers."""

    def __init__(self, logged_in=True, projects=("tripwork-demo",)):
        self.calls, self.logged_in, self.projects, self.uploaded = [], logged_in, list(projects), None
        self.envs = []

    def __call__(self, argv, **kw):
        self.calls.append(list(argv))
        self.envs.append(dict(kw.get("env") or {}))
        if STATICRYPT in argv and "--share" in argv:      # staticrypt only prints the link then
            return subprocess.CompletedProcess(argv, 0, argv[argv.index("--share") + 1] + "#staticrypt_pwd=deadbeef\n", "")
        if STATICRYPT in argv:
            src = pathlib.Path(argv[argv.index(STATICRYPT) + 1])
            out = pathlib.Path(argv[argv.index("-d") + 1])
            out.mkdir(parents=True, exist_ok=True)
            (out / src.name).write_text(LOCKED, encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0, "", "")
        if "whoami" in argv:
            if not self.logged_in:
                raise subprocess.CalledProcessError(1, argv, "", "You are not authenticated.")
            return subprocess.CompletedProcess(argv, 0, "You are logged in", "")
        if argv[-2:] == ["project", "list"]:
            return subprocess.CompletedProcess(argv, 0, "\n".join(f"│ {p} │ {p}.pages.dev │" for p in self.projects), "")
        if "create" in argv:
            self.projects.append(argv[argv.index("create") + 1])
            return subprocess.CompletedProcess(argv, 0, "", "")
        if "deploy" in argv:
            site = pathlib.Path(argv[argv.index("deploy") + 1])
            self.uploaded = sorted(str(p.relative_to(site)) for p in site.rglob("*") if p.is_file())
            self.texts = {str(p.relative_to(site)): p.read_text(encoding="utf-8") for p in site.rglob("*") if p.is_file()}
            return subprocess.CompletedProcess(argv, 0, "Deployment complete! https://1a2b3c.tripwork-demo.pages.dev\n", "")
        raise AssertionError(f"unexpected command {argv}")


def _files(t):
    return sorted(str(p.relative_to(t / "publish")) for p in (t / "publish").rglob("*") if p.is_file())


def test_build_writes_only_the_encrypted_page(tmp_path):
    t = _trip(tmp_path)
    out = P.build(t, "旅行密碼", run=Fake())["page"]
    assert out.read_text(encoding="utf-8") == LOCKED
    assert out.parent.parent == t / "publish" and len(out.parent.name) == 8
    assert _files(t) == sorted(["code.txt", f"{out.parent.name}/index.html"])


def test_the_code_is_stable(tmp_path):
    t = _trip(tmp_path)
    code = P.publish_code(t)
    assert code == P.publish_code(t) and len(code) == 8 and code.isalnum() and code == code.lower()


def test_rebuilds_keep_the_salt(tmp_path):
    # a new salt on every build would break the share links already sent
    t = _trip(tmp_path)
    fake = Fake()
    P.build(t, "pw", run=fake)
    P.build(t, "pw", run=fake)
    P.build(t, "pw", run=fake, share_base="https://tripwork-demo.pages.dev/")
    salts = [c[c.index("-s") + 1] for c in fake.calls if STATICRYPT in c]
    assert len(salts) == 4 and len(set(salts)) == 1 and len(salts[0]) == 32    # the share link's too


def test_build_failure_leaves_no_plaintext(tmp_path):
    t = _trip(tmp_path)

    def boom(argv, **kw):
        raise subprocess.CalledProcessError(1, argv, "", "npx: not found")
    with pytest.raises(P.PublishError, match="npx: not found"):
        P.build(t, "pw", run=boom)
    assert not any(p.suffix == ".html" for p in (t / "publish").rglob("*"))


def test_a_missing_node_is_a_clear_error(tmp_path):
    t = _trip(tmp_path)

    def nonode(argv, **kw):
        raise FileNotFoundError("npx")
    with pytest.raises(P.PublishError, match="Node"):
        P.build(t, "pw", run=nonode)


def test_the_rendered_page_is_the_publish_build(tmp_path):
    from scripts.render.reader.publish import PUBLISH_JS
    t = _trip(tmp_path)
    seen = {}
    fake = Fake()

    def run(argv, **kw):
        if STATICRYPT in argv:
            seen["html"] = pathlib.Path(argv[argv.index(STATICRYPT) + 1]).read_text(encoding="utf-8")
        return fake(argv, **kw)
    P.build(t, "pw", run=run)
    assert PUBLISH_JS in seen["html"]


def test_build_refuses_a_page_the_html_gate_fails(tmp_path, monkeypatch):
    t = _trip(tmp_path)
    monkeypatch.setattr(P, "run_html_gate", lambda *a, **k: {"status": "fail", "failures": ["a stray <script>"]})
    fake = Fake()
    with pytest.raises(P.PublishError, match="stray"):
        P.build(t, "pw", run=fake)
    assert not any(STATICRYPT in c for c in fake.calls)


def test_the_share_link_is_returned_never_written(tmp_path):
    # the link carries a password-equivalent hash; publish/ is what gets uploaded
    t = _trip(tmp_path)
    res = P.build(t, "pw", run=Fake(), share_base="https://tripwork-demo.pages.dev/")
    code = P.publish_code(t)
    assert res["share"] == f"https://tripwork-demo.pages.dev/{code}/#staticrypt_pwd=deadbeef"
    assert not any("deadbeef" in p.read_text(encoding="utf-8") for p in (t / "publish").rglob("*") if p.is_file())


def test_password_never_lands_in_the_trip(tmp_path):
    t = _trip(tmp_path)
    P.build(t, "旅行密碼", run=Fake())
    assert not any("旅行密碼" in p.read_text(encoding="utf-8", errors="ignore") for p in tmp_path.rglob("*") if p.is_file())


def test_deploy_refuses_without_confirm(tmp_path):
    t = _trip(tmp_path)
    P.build(t, "pw", run=Fake())
    fake = Fake()
    with pytest.raises(P.PublishError, match="--confirm"):
        P.deploy(t, "tripwork-demo", run=fake)
    assert fake.calls == []


def test_deploy_uploads_this_trips_locked_page_and_nothing_else(tmp_path):
    # v2.0.0 (consumer report D1): one trip is one Pages project, so the site is this
    # trip's locked page only -- never the other trips under the same trips/ folder
    a, b = _trip(tmp_path, "2026-05-demo"), _trip(tmp_path, "2026-06-demo")
    P.build(a, "pw", run=Fake())
    P.build(b, "pw", run=Fake())
    fake = Fake()
    res = P.deploy(a, "tripwork-demo", confirm=True, run=fake)
    assert fake.uploaded == [f"{P.publish_code(a)}/index.html"]
    wr = [c for c in fake.calls if "deploy" in c][0]
    assert wr[:4] == ["npx", "--yes", "wrangler@3", "pages"] and wr[wr.index("--project-name") + 1] == "tripwork-demo"
    assert res["url"] == f"https://tripwork-demo.pages.dev/{P.publish_code(a)}/"


def test_deploy_refuses_a_page_that_is_not_locked(tmp_path):
    t = _trip(tmp_path)
    page = P.build(t, "pw", run=Fake())["page"]
    page.write_text("<!doctype html><title>plain</title>", encoding="utf-8")
    fake = Fake()
    with pytest.raises(P.PublishError, match="not encrypted"):
        P.deploy(t, "tripwork-demo", confirm=True, run=fake)
    assert not any("deploy" in c for c in fake.calls)


def test_deploy_without_a_build_asks_for_one(tmp_path):
    t = _trip(tmp_path)
    with pytest.raises(P.PublishError, match="tripwork.py publish"):
        P.deploy(t, "tripwork-demo", confirm=True, run=Fake())


def test_deploy_needs_a_login(tmp_path):
    t = _trip(tmp_path)
    P.build(t, "pw", run=Fake())
    fake = Fake(logged_in=False)
    with pytest.raises(P.PublishError, match="wrangler login"):
        P.deploy(t, "tripwork-demo", confirm=True, run=fake)
    assert not any("deploy" in c for c in fake.calls)


def test_deploy_creates_a_missing_project(tmp_path):
    t = _trip(tmp_path)
    P.build(t, "pw", run=Fake())
    fake = Fake(projects=())
    P.deploy(t, "tripwork-new", confirm=True, run=fake)
    create = [c for c in fake.calls if "create" in c][0]
    assert create[create.index("create") + 1] == "tripwork-new"
    assert [c for c in fake.calls if "deploy" in c]


def test_cli_build_reads_the_password_from_the_environment(tmp_path, monkeypatch, capsys):
    t = _trip(tmp_path)
    fake = Fake()
    monkeypatch.setenv("TRIPWORK_PUBLISH_PASSWORD", "旅行密碼")
    monkeypatch.setattr(P, "_run", fake)
    assert P.main(["build", str(t), "--share-base", "https://tripwork-demo.pages.dev/"]) == 0
    assert {e.get("STATICRYPT_PASSWORD") for c, e in zip(fake.calls, fake.envs) if STATICRYPT in c} == {"旅行密碼"}
    assert not [c for c in fake.calls if "-p" in c or "旅行密碼" in c]
    out = capsys.readouterr().out
    assert "#staticrypt_pwd=deadbeef" in out


def test_cli_exit_codes(tmp_path, monkeypatch):
    t = _trip(tmp_path)
    monkeypatch.setattr(P, "_run", Fake())
    monkeypatch.setenv("TRIPWORK_PUBLISH_PASSWORD", "pw")
    assert P.main(["build", str(tmp_path / "nope")]) == 2
    assert P.main(["deploy", str(t), "--project", "tripwork-demo"]) == 1      # no --confirm
