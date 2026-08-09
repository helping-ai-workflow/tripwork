"""Every `python scripts/<x>.py` entrypoint must use the ONE shared sys.path
bootstrap (final v0.33.0 whole-branch review).

Task 9 fixed a real crash: `scripts/calendar.py` shadows the stdlib `calendar`
module for the CLI entrypoints, because Python auto-prepends the script's own
directory to `sys.path`. `http.cookiejar` does `from calendar import timegm`, so
any CLI whose import graph reaches `requests` died on its first line with
"cannot import name 'timegm' from 'calendar'". The fix was then copy-pasted into
four files while `next_stage.py` and `input_fingerprint.py` kept an older shape
that added the repo root WITHOUT dropping `scripts/` — the same landmine, armed,
waiting for either to gain an import that reaches `requests`. The ledger's CARRY
line predicted exactly that recurrence.

Structure alone is not the proof, so this file checks three independent things:
the six entrypoints all route through `scripts/_cli_bootstrap.py`
(test_every_cli_entrypoint_uses_the_shared_bootstrap), each one actually RUNS
from a foreign cwd (test_every_cli_entrypoint_starts_from_a_foreign_cwd) and
under `python -P` (test_every_cli_entrypoint_starts_under_isolated_mode), and
the shadow is really gone from sys.path afterwards in both modes
(test_the_shadow_stays_disarmed_in_both_modes). A test that imported the modules
as `scripts.X` could not see this class of defect at all — the `__main__` guard
means the broken path never executes under import.
"""
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

# Every module in scripts/ with a `if __name__ == "__main__"` entrypoint.
ENTRYPOINTS = ("gate.py", "export_gate.py", "photo_adapter.py",
               "source_verify_run.py", "next_stage.py", "input_fingerprint.py",
               "validate_artifact.py", "bump_version.py")

# The two that do not need the bootstrap, with the reason recorded so a future
# reader does not "fix" them: neither imports anything from `scripts.`, so
# neither needs the repo root on sys.path.
NO_BOOTSTRAP_NEEDED = {"validate_artifact.py", "bump_version.py"}


def _entrypoints_needing_bootstrap():
    return [n for n in ENTRYPOINTS if n not in NO_BOOTSTRAP_NEEDED]


def test_the_exempt_entrypoints_really_have_no_scripts_imports():
    """Pins the exemption above rather than trusting it. If either file ever
    grows a `from scripts.X import ...`, it needs the bootstrap and this fails
    instead of the CLI dying in a consumer's terminal."""
    for name in sorted(NO_BOOTSTRAP_NEEDED):
        text = (SCRIPTS / name).read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import) scripts\b", text, re.M), name


@pytest.mark.parametrize("name", _entrypoints_needing_bootstrap())
def test_every_cli_entrypoint_uses_the_shared_bootstrap(name):
    """One implementation, six call sites. Re-inlining the block (or keeping the
    old repo-root-only shape) fails here."""
    text = (SCRIPTS / name).read_text(encoding="utf-8")
    assert "import _cli_bootstrap" in text, f"{name} does not use the shared bootstrap"
    # The two-line preamble that makes the bare import above resolve under
    # `python -P` / PYTHONSAFEPATH=1, where Python does not auto-add the
    # script's directory. Without it every CLI dies with ModuleNotFoundError
    # on its first line (test_every_cli_entrypoint_starts_under_isolated_mode).
    assert "_bootsys.path.insert" in text, f"{name} lacks the -P-safe preamble"
    # The POLICY must not be re-inlined: only _cli_bootstrap decides what comes
    # OFF the path. The preamble only puts scripts/ on so the import resolves.
    assert "path.remove" not in text, f"{name} still hand-rolls the path fix"
    assert "parent.parent" not in text.split("import _cli_bootstrap")[0], \
        f"{name} re-implements the repo-root insert instead of delegating it"


def test_the_bootstrap_drops_the_scripts_dir_as_well_as_adding_the_root():
    """Both halves, checked on the module itself. Adding the repo root alone is
    the shape that shipped in next_stage.py and input_fingerprint.py: imports
    resolve, and the `calendar` shadow stays armed."""
    text = (SCRIPTS / "_cli_bootstrap.py").read_text(encoding="utf-8")
    assert "sys.path[:] = [p for p in sys.path if p != _here]" in text, \
        ("the removal must filter ALL occurrences: each caller's -P preamble "
         "adds a SECOND copy of scripts/ in normal mode, and list.remove would "
         "drop only one, leaving the `calendar` shadow armed")
    assert "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))" in text


@pytest.mark.parametrize("name", _entrypoints_needing_bootstrap())
def test_every_cli_entrypoint_starts_from_a_foreign_cwd(name, tmp_path):
    """The behavioural half. Run each CLI with `--help` from a cwd that is NOT
    the repo, by absolute path — the documented invocation shape. A shadowed
    `calendar` kills the process during import, long before argparse runs, so
    `--help` exiting 0 with a usage banner is a genuine end-to-end proof that
    the import graph resolved.

    `next_stage.py` and `input_fingerprint.py` are the two this release newly
    protects; they are in the same parametrize rather than a separate test so
    the evidence is identical for all six.
    """
    proc = subprocess.run([sys.executable, str(SCRIPTS / name), "--help"],
                          cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode == 0, (name, proc.returncode, proc.stderr)
    assert "usage:" in proc.stdout.lower(), (name, proc.stdout[:200])
    assert "calendar" not in proc.stderr, (name, proc.stderr)


@pytest.mark.parametrize("name", _entrypoints_needing_bootstrap())
def test_every_cli_entrypoint_starts_under_isolated_mode(name, tmp_path):
    """`python -P` / PYTHONSAFEPATH=1 suppresses the auto-added script directory.
    The shared helper lives IN that directory, so extracting it initially broke
    every CLI here with `ModuleNotFoundError: No module named '_cli_bootstrap'` —
    a regression against the pre-extraction shape, which used a plain inline
    `sys.path.insert` and never needed to import anything. Each caller's
    two-line preamble restores it.

    -P is an undocumented invocation with no known consumer, but it is a mode a
    security-conscious operator reaches for precisely BECAUSE this repo has a
    stdlib-shadowing module in its script directory."""
    proc = subprocess.run([sys.executable, "-P", str(SCRIPTS / name), "--help"],
                          cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode == 0, (name, proc.stderr)
    assert "ModuleNotFoundError" not in proc.stderr, (name, proc.stderr)


def test_the_shadow_stays_disarmed_in_both_modes(tmp_path):
    """The load-bearing half of the -P fix, checked by BEHAVIOUR not by reading.

    In normal mode the preamble adds a second `scripts/` entry beside Python's
    own, so the helper must remove BOTH — one survivor is enough to re-shadow
    stdlib `calendar` and kill any CLI that reaches `requests`. Asserts zero
    survivors and that `calendar` resolves to the stdlib, in both modes."""
    probe = (
        "import runpy, sys, pathlib\n"
        f"here = str(pathlib.Path(r'{SCRIPTS}').resolve())\n"
        "sys.argv = ['gate.py']\n"
        "try:\n"
        f"    runpy.run_path(r'{SCRIPTS / 'gate.py'}', run_name='__main__')\n"
        "except SystemExit:\n"
        "    pass\n"
        "print(sum(1 for p in sys.path if p == here), __import__('calendar').__file__)\n")
    for args in ([], ["-P"]):
        proc = subprocess.run([sys.executable, *args, "-c", probe],
                              cwd=tmp_path, capture_output=True, text=True)
        assert proc.returncode == 0, (args, proc.stderr)
        survivors, calendar_file = proc.stdout.strip().splitlines()[-1].split(maxsplit=1)
        assert survivors == "0", (args, proc.stdout)
        assert str(SCRIPTS) not in calendar_file, (args, calendar_file)
