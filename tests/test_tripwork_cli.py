"""v2.0.0 spec §1: scripts/tripwork.py -- the single entry point.

Dispatch is checked against each target module's own `main` (a recorder swapped in
for it), so the guard measures the shipped dispatcher, not a copy of its table.
"""
import ast
import importlib
import os
import pathlib
import shutil
import subprocess
import sys

import pytest
import yaml

from tests import mech_fixtures as M

ROOT = pathlib.Path(__file__).resolve().parents[1]
SLUG = M.SLUG


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """A consumer workspace with one complete v1.0 trip; cwd is its root."""
    M.build_full_trip(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _tw():
    return importlib.import_module("scripts.tripwork")


def _record(monkeypatch, mod, code=0):
    calls = []
    m = importlib.import_module(mod)

    def fake(argv):
        calls.append(list(argv))
        return code
    monkeypatch.setattr(m, "main", fake)
    return calls


# (tripwork argv, [(module, argv handed to its main)]) -- spec §1's command table.
CASES = [
    (["next", SLUG], [("scripts.next_stage", [f"trips/{SLUG}", "--work-dir", f"work/{SLUG}"])]),
    (["verify", SLUG, "--offline", "--official-domain", "x.example"],
     [("scripts.source_verify_run", [f"trips/{SLUG}", "--work-dir", f"work/{SLUG}",
                                     "--offline", "--official-domain", "x.example"])]),
    (["gate", SLUG], [("scripts.gate", [f"trips/{SLUG}", "--work-dir", f"work/{SLUG}"])]),
    (["export-gate", SLUG], [("scripts.export_gate", [f"trips/{SLUG}", "--work-dir", f"work/{SLUG}"])]),
    (["export", SLUG], [("scripts.export", [f"trips/{SLUG}", "--work-dir", f"work/{SLUG}"])]),
    (["maps", SLUG, "--offline"], [("scripts.day_maps", [f"trips/{SLUG}", "--work-dir", f"work/{SLUG}", "--offline"])]),
    (["photos", SLUG], [("scripts.photo_adapter", [f"trips/{SLUG}", "--backend", "wiki"])]),
    (["photos", SLUG, "--backend", "none"], [("scripts.photo_adapter", [f"trips/{SLUG}", "--backend", "none"])]),
    (["photos", SLUG, "--dry-run"], [("scripts.photo_adapter", [f"trips/{SLUG}", "--backend", "wiki", "--dry-run"])]),
    (["picker", SLUG], [("scripts.title_picker", [f"trips/{SLUG}", "--work-dir", f"work/{SLUG}"])]),
    (["picker", SLUG, "H=1"], [("scripts.title_picks", [f"trips/{SLUG}", "H=1"])]),
    (["validate", SLUG, "itinerary"], [("scripts.validate_artifact", [f"trips/{SLUG}/data/itinerary.yaml"])]),
    (["validate", SLUG, "cost.yaml"], [("scripts.validate_artifact", [f"trips/{SLUG}/data/cost.yaml"])]),
    (["fingerprint", SLUG, "advisory"],
     [("scripts.input_fingerprint", [f"trips/{SLUG}/data/trip-brief.yaml", "advisory"])]),
    (["publish", SLUG, "--share-base", "https://p.pages.dev/"],
     [("scripts.publish", ["build", f"trips/{SLUG}", "--share-base", "https://p.pages.dev/"])]),
    (["deploy", SLUG, "--project", "p", "--confirm"],
     [("scripts.publish", ["deploy", f"trips/{SLUG}", "--project", "p", "--confirm"])]),
    (["migrate"], [("scripts.migrate_v1", ["trips"])]),
    (["migrate", "--apply"], [("scripts.migrate_v1", ["trips", "--apply"])]),
    (["migrate", SLUG, "--apply"], [("scripts.migrate_v1", [f"trips/{SLUG}", "--apply"])]),
    ([f"gate", f"trips/{SLUG}/"], [("scripts.gate", [f"trips/{SLUG}", "--work-dir", f"work/{SLUG}"])]),
]


@pytest.mark.parametrize("argv,expected", CASES, ids=[" ".join(c[0]) for c in CASES])
def test_dispatch_argv(ws, monkeypatch, argv, expected):
    recorders = {mod: _record(monkeypatch, mod) for mod, _ in expected}
    assert _tw().main(argv) == 0
    for mod, args in expected:
        assert recorders[mod] == [args]


def test_validate_without_a_name_runs_every_artifact(ws, monkeypatch):
    from scripts.paths import data_dir
    calls = _record(monkeypatch, "scripts.validate_artifact")
    assert _tw().main(["validate", SLUG]) == 0
    expect = sorted(f"trips/{SLUG}/data/{p.name}" for p in data_dir(ws / "trips" / SLUG).glob("*.yaml"))
    assert sorted(c[0] for c in calls) == expect and len(expect) >= 10


def test_validate_exit_is_the_worst(ws, monkeypatch):
    m = importlib.import_module("scripts.validate_artifact")
    monkeypatch.setattr(m, "main", lambda argv: 1 if argv[0].endswith("cost.yaml") else 0)
    assert _tw().main(["validate", SLUG]) == 1


def test_dispatch_uses_the_module_attribute(ws, monkeypatch):
    tw = _tw()                                            # imported BEFORE the swap
    calls = _record(monkeypatch, "scripts.gate", code=7)
    assert tw.main(["gate", SLUG]) == 7 and len(calls) == 1


@pytest.mark.parametrize("bad", ["..", "/abs", "a/b", "", ".", "-h", "-x", "a\\b"])
def test_slug_rules(ws, monkeypatch, capsys, bad):
    calls = _record(monkeypatch, "scripts.gate")
    if bad == "-h":                                       # gate -h is help, not a slug
        assert _tw().main(["gate", bad]) == 0
    else:
        assert _tw().main(["gate", bad]) == 2
    assert calls == []


def test_no_trips_dir(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert _tw().main(["gate", SLUG]) == 2
    assert "run tripwork.py from the workspace root" in capsys.readouterr().err


def test_missing_trip_folder(ws, capsys):
    assert _tw().main(["gate", "nosuch"]) == 2
    assert "no trip folder trips/nosuch" in capsys.readouterr().err


def test_next_on_a_new_slug(ws, capsys):
    assert _tw().main(["next", "brand-new"]) == 0
    assert yaml.safe_load(capsys.readouterr().out)["next"] == "tripwork:trip-brief"
    (ws / "work" / ".preflight-completed").unlink()
    assert _tw().main(["next", "brand-new"]) == 0
    assert yaml.safe_load(capsys.readouterr().out)["next"] == "tripwork:workspace-shape-preflight"


@pytest.mark.parametrize("argv", [["-h"], ["--help"]])
def test_top_level_help_lists_every_command(ws, capsys, argv):
    assert _tw().main(argv) == 0
    out = capsys.readouterr().out
    for name in _tw().COMMANDS:
        assert name in out


@pytest.mark.parametrize("argv", [["next", "-h"], ["gate", "-h"], ["gate", SLUG, "-h"], ["publish", SLUG, "--help"]])
def test_command_help_does_not_dispatch(ws, monkeypatch, capsys, argv):
    mod = {"next": "scripts.next_stage", "gate": "scripts.gate", "publish": "scripts.publish"}[argv[0]]
    calls = _record(monkeypatch, mod)
    assert _tw().main(argv) == 0
    out = capsys.readouterr().out
    assert f"tripwork.py {argv[0]}" in out and "python scripts/" not in out
    assert calls == []


def test_unknown_command(ws, capsys):
    assert _tw().main(["frobnicate", SLUG]) == 2


def test_no_command(ws, capsys):
    assert _tw().main([]) == 2


def _run_both(tw_argv, mod, long_argv, capsys):
    a = _tw().main(tw_argv)
    out_a = capsys.readouterr().out
    b = importlib.import_module(mod).main(long_argv)
    out_b = capsys.readouterr().out
    return (a, out_a), (b, out_b)


@pytest.mark.parametrize("cmd,mod,long_argv", [
    ("next", "scripts.next_stage", [f"trips/{SLUG}", "--work-dir", f"work/{SLUG}"]),
    ("validate", "scripts.validate_artifact", [f"trips/{SLUG}/data/itinerary.yaml"]),
    ("gate", "scripts.gate", [f"trips/{SLUG}", "--work-dir", f"work/{SLUG}"]),
    ("export-gate", "scripts.export_gate", [f"trips/{SLUG}", "--work-dir", f"work/{SLUG}"]),
    ("picker", "scripts.title_picker", [f"trips/{SLUG}", "--work-dir", f"work/{SLUG}"]),
])
def test_real_runs_match_direct_calls(ws, capsys, cmd, mod, long_argv):
    tw_argv = [cmd, SLUG] + (["itinerary"] if cmd == "validate" else [])
    report = {"gate": "gate-report.yaml", "export-gate": "export-gate-report.yaml"}.get(cmd)
    (a, out_a), (b, out_b) = _run_both(tw_argv, mod, long_argv, capsys)
    assert (a, out_a) == (b, out_b)
    if report:
        first = (ws / "work" / SLUG / report).read_bytes()
        _tw().main(tw_argv)
        assert (ws / "work" / SLUG / report).read_bytes() == first


def test_starts_from_a_copy_without_editable_install(tmp_path):
    repo = tmp_path / "repo"
    for d in ("scripts", "schemas", "assets"):
        shutil.copytree(ROOT / d, repo / d, ignore=shutil.ignore_patterns("__pycache__"))
    wsdir = tmp_path / "ws"
    M.build_full_trip(wsdir)
    from tests.test_entrypoints import no_editable_env
    env = {**no_editable_env(), "TRIPWORK_DEBUG_IMPORT": "1"}
    r = subprocess.run([sys.executable, "-S", "-P", str(repo / "scripts" / "tripwork.py"), "next", SLUG],
                       cwd=wsdir, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr[-800:]
    loaded = [ln for ln in r.stderr.splitlines() if ln.startswith("tripwork: scripts from ")]
    assert loaded and loaded[0].endswith(str(repo / "scripts")), r.stderr[-800:]
    assert r.stdout.startswith("next: tripwork:")      # the oracle ran (this fixture has no gate report yet)


def test_no_parameter_copies():
    tree = ast.parse((ROOT / "scripts" / "tripwork.py").read_text(encoding="utf-8"))
    own = {"command", "slug", "rest"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "add_argument":
            first = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else None
            assert first in own, f"tripwork.py declares a target script's flag: {first!r}"
