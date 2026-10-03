"""Unit tests for scripts/bump_version.py — the cross-platform manifest bumper."""
import json, importlib.util, pathlib, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUMP_PY = ROOT / "scripts" / "bump_version.py"
_spec = importlib.util.spec_from_file_location("bump_version", BUMP_PY)
bump_version = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bump_version)


def _mini_repo(tmp_path, current="1.0.0", previous=None):
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / "a.json").write_text(f'{{\n  "version": "{current}",\n  "d": "x→y"\n}}\n', encoding="utf-8")
    (tmp_path / ".claude-plugin" / "marketplace.json").write_text(
        f'{{\n  "plugins": [\n    {{ "name": "tripwork", "version": "{current}" }}\n  ]\n}}\n')
    (tmp_path / "pyproject.toml").write_text(f'[project]\nname = "tripwork"\nversion = "{current}"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(f"# Changelog\n\n## {current} — first\n")
    (tmp_path / "CLAUDE.md").write_text(f"Behaviour added in v{current}.\n")  # excluded historical ref
    cfg = {
        "files": [
            {"path": "a.json", "type": "json", "key": "version"},
            {"path": ".claude-plugin/marketplace.json", "type": "json", "key": "plugins.0.version"},
            {"path": "pyproject.toml", "type": "toml", "key": "version"},
            {"path": "CHANGELOG.md", "type": "changelog", "heading": "## {version}"},
        ],
        "audit": {"exclude": ["CHANGELOG.md", "CLAUDE.md", ".version-bump.json"]},
        "current": current, "next": bump_version.next_minor(current),
    }
    if previous is not None:
        cfg["previous"] = previous
    (tmp_path / ".version-bump.json").write_text(json.dumps(cfg, indent=2))
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    return tmp_path


def test_next_minor():
    assert bump_version.next_minor("0.23.1") == "0.24.0"
    assert bump_version.next_minor("1.9.4") == "1.10.0"

def test_read_write_nested_json(tmp_path):
    repo = _mini_repo(tmp_path)
    mk = repo / ".claude-plugin" / "marketplace.json"
    assert bump_version.read_key(mk, "plugins.0.version") == "1.0.0"
    bump_version.write_key(mk, "plugins.0.version", "2.0.0")
    assert bump_version.read_key(mk, "plugins.0.version") == "2.0.0"

def test_read_write_toml(tmp_path):
    repo = _mini_repo(tmp_path)
    pp = repo / "pyproject.toml"
    assert bump_version.read_toml_version(pp) == "1.0.0"
    bump_version.write_toml_version(pp, "2.0.0")
    assert bump_version.read_toml_version(pp) == "2.0.0"

def test_check_in_sync_then_drift(tmp_path):
    repo = _mini_repo(tmp_path)
    assert bump_version.check(repo) == 0
    (repo / "a.json").write_text('{\n  "version": "0.3.0"\n}\n')
    assert bump_version.check(repo) == 1

def test_bump_moves_all_and_current(tmp_path):
    repo = _mini_repo(tmp_path)
    assert bump_version.bump(repo, "2.0.0") == 0
    assert bump_version.read_key(repo / "a.json", "version") == "2.0.0"
    assert bump_version.read_toml_version(repo / "pyproject.toml") == "2.0.0"
    cfg = json.loads((repo / ".version-bump.json").read_text(encoding="utf-8"))
    assert cfg["current"] == "2.0.0" and cfg["next"] == "2.1.0"

def test_audit_clean_and_flags_stray(tmp_path):
    repo = _mini_repo(tmp_path)
    assert bump_version.audit(repo) == 0  # v1.0.0 in CLAUDE.md is excluded
    (repo / "stray.json").write_text('{ "version": "1.0.0" }\n')
    subprocess.run(["git", "add", "stray.json"], cwd=repo, check=True)
    assert bump_version.audit(repo) == 1

def test_bump_preserves_non_ascii(tmp_path):
    repo = _mini_repo(tmp_path)
    bump_version.bump(repo, "2.0.0")
    raw = (repo / "a.json").read_text(encoding="utf-8")
    assert "→" in raw and "\\u2192" not in raw

def test_audit_flags_an_undeclared_manifest_left_at_the_previous_version(tmp_path):
    """TW-078：漏宣告的 manifest 不會被 bump 寫到，所以它停在舊版號 —— 那正是 audit
    只 grep 新版號時看不見的那一格。"""
    repo = _mini_repo(tmp_path, current="1.0.0", previous="0.9.0")
    (repo / ".newide-plugin").mkdir()
    (repo / ".newide-plugin" / "plugin.json").write_text(
        '{"name": "tripwork", "version": "0.9.0"}\n', encoding="utf-8")
    subprocess.run(["git", "add", "-N", ".newide-plugin/plugin.json"], cwd=repo, check=True)
    assert bump_version.audit(repo) == 1

def test_audit_does_not_flag_prose_mentioning_the_previous_version(tmp_path):
    """CHANGELOG/README/skills prose legitimately mentions old versions forever —
    the stale-manifest scan must not fire on non-manifest files, or --audit
    would be noisy at every release and get turned off."""
    repo = _mini_repo(tmp_path, current="1.0.0", previous="0.9.0")
    (repo / "NOTES.md").write_text("Behaviour before 0.9.0 was different.\n", encoding="utf-8")
    subprocess.run(["git", "add", "NOTES.md"], cwd=repo, check=True)
    assert bump_version.audit(repo) == 0

def test_audit_skips_stale_scan_when_previous_is_absent(tmp_path):
    """An older checkout of .version-bump.json may not have `previous` yet —
    absence must mean 'skip the second scan', not crash."""
    repo = _mini_repo(tmp_path, current="1.0.0", previous=None)
    (repo / ".newide-plugin").mkdir()
    (repo / ".newide-plugin" / "plugin.json").write_text(
        '{"name": "tripwork", "version": "0.9.0"}\n', encoding="utf-8")
    subprocess.run(["git", "add", "-N", ".newide-plugin/plugin.json"], cwd=repo, check=True)
    assert bump_version.audit(repo) == 0

def test_audit_prints_skip_notice_when_previous_absent_even_when_clean(tmp_path, capsys):
    """Fix round 1 finding 3: a scan that silently does not run must not read
    byte-identical to a verified-clean repo. When `previous` is absent, the skip
    notice must appear unconditionally — including on the otherwise 'All clear'
    path, not only when something else happens to be flagged — so a reader can
    never mistake 'the scan did not run' for 'the scan ran and found nothing'."""
    repo = _mini_repo(tmp_path, current="1.0.0", previous=None)
    rc = bump_version.audit(repo)
    out = capsys.readouterr().out
    assert rc == 0
    assert "SKIPPED" in out
    assert "All clear" in out

def test_bump_same_version_twice_does_not_collapse_previous(tmp_path):
    """Fix round 1 finding 2: retrying bump() with an unchanged version (e.g. a
    later release-flow step failed and the operator reruns with the same X.Y.Z)
    must not advance `previous` — that would collapse the one-release lookback
    window the stale-manifest scan depends on, even though no release happened."""
    repo = _mini_repo(tmp_path, current="1.0.0", previous="0.9.0")
    assert bump_version.bump(repo, "2.0.0") == 0
    cfg = json.loads((repo / ".version-bump.json").read_text(encoding="utf-8"))
    assert cfg["previous"] == "1.0.0" and cfg["current"] == "2.0.0"
    # Re-run with the SAME version — simulates a retry, not a real release.
    assert bump_version.bump(repo, "2.0.0") == 0
    cfg2 = json.loads((repo / ".version-bump.json").read_text(encoding="utf-8"))
    assert cfg2["previous"] == "1.0.0"  # unchanged — must NOT have become "2.0.0"
    assert cfg2["current"] == "2.0.0"

def test_bump_returns_nonzero_when_undeclared_manifest_stuck_at_previous_version(tmp_path):
    """Fix round 1 finding 1(b): the one-hop detection window is acceptable only
    because bump() already ends with `return audit(root)`, so bumping past a
    manifest stuck at the version being bumped FROM makes the bump command
    itself exit non-zero — the operator cannot silently walk past it. Locks in
    the claim the coordinator asked to be verified, not just asserted."""
    repo = _mini_repo(tmp_path, current="1.0.0", previous="0.9.0")
    (repo / ".newide-plugin").mkdir()
    (repo / ".newide-plugin" / "plugin.json").write_text(
        '{"name": "tripwork", "version": "1.0.0"}\n', encoding="utf-8")
    subprocess.run(["git", "add", "-N", ".newide-plugin/plugin.json"], cwd=repo, check=True)
    # Bumping 1.0.0 -> 2.0.0 makes `previous` become "1.0.0", which is exactly
    # what the undeclared manifest is still stuck at.
    assert bump_version.bump(repo, "2.0.0") == 1
