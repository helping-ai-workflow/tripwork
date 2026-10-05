"""C1: the fingerprint CLI must run where it is actually invoked — a consumer
workspace, never the plugin repo root.

skills/travel-advisory/SKILL.md once told agents to compute the fingerprint via
`python -c "... from scripts.orchestration import ..."`, which only resolves inside
the plugin repo; in a consumer workspace it raised ModuleNotFoundError and the
agent silently omitted `input_fingerprints`. v2.0.0: the instruction is
`python <plugin>/scripts/tripwork.py fingerprint <slug> advisory`.

This test proves it the way the defect manifested: as a SUBPROCESS of the real
entry point, launched from a consumer workspace that is NOT the repo root.
"""
import pathlib

import yaml

from tests.cli_helpers import run_tripwork


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
    # A stand-in consumer workspace: NOT the plugin repo root, and with no
    # `scripts` package of its own.
    consumer_workspace = tmp_path / "consumer-workspace"
    brief_path = consumer_workspace / "trips" / "kyoto" / "data" / "trip-brief.yaml"
    brief_path.parent.mkdir(parents=True)
    brief_path.write_text(yaml.safe_dump(brief, allow_unicode=True), encoding="utf-8")

    result = run_tripwork(consumer_workspace, "fingerprint", "kyoto", "advisory")

    assert result.returncode == 0, (
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    expected = input_fingerprint(brief, ADVISORY_PROJECTION)
    assert result.stdout.strip() == expected


def test_cli_rejects_unknown_projection(tmp_path):
    brief_path = tmp_path / "trips" / "kyoto" / "data" / "trip-brief.yaml"
    brief_path.parent.mkdir(parents=True)
    brief_path.write_text(yaml.safe_dump({"destination": "Kyoto"}), encoding="utf-8")
    result = run_tripwork(tmp_path, "fingerprint", "kyoto", "bogus")
    assert result.returncode != 0
