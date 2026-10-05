"""v2.0.0 spec §3 (round-1 #19, round-2 #9/#11): the page password is asked in the
conversation and handed to that one run; it reaches staticrypt through the child's
environment (never its argv), overriding any STATICRYPT_PASSWORD the shell already
holds; without a password and without a terminal `publish` exits 2 instead of a
getpass traceback."""
import getpass
import subprocess

import pytest

from scripts import publish as P
from scripts.render.publish.lock import STATICRYPT
from tests.test_publish_cli import LOCKED, _trip


class EnvFake:
    """subprocess.run stand-in that keeps each call's argv AND env."""

    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kw):
        import pathlib
        self.calls.append((list(argv), dict(kw.get("env") or {})))
        if "--share" in argv:
            return subprocess.CompletedProcess(argv, 0, argv[argv.index("--share") + 1] + "#staticrypt_pwd=deadbeef\n", "")
        src = pathlib.Path(argv[argv.index(STATICRYPT) + 1])
        out = pathlib.Path(argv[argv.index("-d") + 1])
        out.mkdir(parents=True, exist_ok=True)
        (out / src.name).write_text(LOCKED, encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, "", "")


def _no_getpass(*a, **k):
    raise AssertionError("getpass must not be called without a terminal")


def test_no_password_without_a_terminal(tmp_path, monkeypatch, capsys):
    t = _trip(tmp_path)
    monkeypatch.delenv("TRIPWORK_PUBLISH_PASSWORD", raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr(getpass, "getpass", _no_getpass)
    monkeypatch.setattr(P, "_run", EnvFake())
    assert P.main(["build", str(t)]) == 2
    err = capsys.readouterr().err
    assert "ask the user for one in the conversation" in err
    assert "TRIPWORK_PUBLISH_PASSWORD=" in err and "tripwork.py publish" in err
    assert "Traceback" not in err


def test_tty_uses_getpass(tmp_path, monkeypatch):
    t = _trip(tmp_path)
    monkeypatch.delenv("TRIPWORK_PUBLISH_PASSWORD", raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    asked = []
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": asked.append(prompt) or "密碼")
    fake = EnvFake()
    monkeypatch.setattr(P, "_run", fake)
    assert P.main(["build", str(t)]) == 0
    assert asked


@pytest.mark.parametrize("outer", [None, "other-password"])
def test_password_never_on_argv(tmp_path, monkeypatch, outer):
    t = _trip(tmp_path)
    monkeypatch.setenv("TRIPWORK_PUBLISH_PASSWORD", "旅行密碼")
    if outer:
        monkeypatch.setenv("STATICRYPT_PASSWORD", outer)
    fake = EnvFake()
    monkeypatch.setattr(P, "_run", fake)
    assert P.main(["build", str(t), "--share-base", "https://tripwork-demo.pages.dev/"]) == 0
    sr = [(a, e) for a, e in fake.calls if STATICRYPT in a]
    assert len(sr) == 2                                   # encrypt + share link
    for argv, env in sr:
        assert "旅行密碼" not in argv and "-p" not in argv
        assert env.get("STATICRYPT_PASSWORD") == "旅行密碼"


def test_lock_args_take_no_password():
    from scripts.render.publish import lock
    import inspect
    assert "password" not in inspect.signature(lock.staticrypt_args).parameters
    assert "password" not in inspect.signature(lock.staticrypt_share_args).parameters
    env = lock.staticrypt_env("x")
    assert env["STATICRYPT_PASSWORD"] == "x" and "PATH" in env
