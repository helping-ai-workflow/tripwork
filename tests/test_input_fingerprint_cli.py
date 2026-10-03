"""C1: the fingerprint CLI must run where it is actually invoked — a consumer
workspace, never the plugin repo root.

skills/travel-advisory/SKILL.md used to instruct agents to compute the
fingerprint via `python -c "import yaml,sys; from scripts.orchestration
import ..."`. That import only resolves when the current working directory's
`scripts/` package happens to be the plugin's — true only inside the plugin
repo itself. In the one place this is ever actually run (a consumer
workspace, whose own `scripts/` directory is unrelated to the plugin's), it
raises ModuleNotFoundError, so the agent silently omits `input_fingerprints`
and rule 11 falls back to mtime forever. The fix follows every other script
instruction in this plugin: `python scripts/<file>.py <args>`, invocable with
a path prefix to the plugin regardless of cwd.

This test proves the fix the way the defect actually manifested: as a
SUBPROCESS, launched from a cwd that is NOT the repo root. An in-process
import test cannot catch this class of defect (it would already have
`scripts` on sys.path).
"""
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "input_fingerprint.py"


def test_cli_runs_from_a_non_repo_root_cwd_and_matches_in_process(tmp_path):
    from scripts.orchestration import ADVISORY_PROJECTION, input_fingerprint

    brief = {
        "destination": "Kyoto",
        "dates": {"start": "2026-05-01", "end": "2026-05-03"},
        "airline": "JAL",
        "travellers": 2,
        # a field NOT in ADVISORY_PROJECTION -- must not affect the fingerprint,
        # and its presence is what would catch a CLI that hashed the whole doc
        # instead of projecting it first.
        "must_do": ["嵐山竹林"],
    }
    brief_path = tmp_path / "trip-brief.yaml"
    brief_path.write_text(yaml.safe_dump(brief, allow_unicode=True), encoding="utf-8")

    # A stand-in consumer workspace: NOT the plugin repo root, and with no
    # `scripts` package of its own. If the CLI relied on cwd, or on `scripts`
    # already being importable some other way, this reproduces the exact
    # ModuleNotFoundError the `python -c` instruction it replaces raised
    # everywhere except the plugin root.
    consumer_workspace = tmp_path / "consumer-workspace"
    consumer_workspace.mkdir()

    result = subprocess.run(
        [sys.executable, str(CLI), str(brief_path), "advisory"],
        capture_output=True, text=True, cwd=str(consumer_workspace),
    )

    assert result.returncode == 0, (
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    expected = input_fingerprint(brief, ADVISORY_PROJECTION)
    assert result.stdout.strip() == expected


def test_cli_rejects_unknown_projection(tmp_path):
    brief_path = tmp_path / "trip-brief.yaml"
    brief_path.write_text(yaml.safe_dump({"destination": "Kyoto"}), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(CLI), str(brief_path), "bogus"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
