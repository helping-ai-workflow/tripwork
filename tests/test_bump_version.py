"""Unit tests for scripts/bump_version.py — the cross-platform manifest bumper."""
import json, importlib.util, pathlib, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUMP_PY = ROOT / "scripts" / "bump_version.py"
_spec = importlib.util.spec_from_file_location("bump_version", BUMP_PY)
bump_version = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bump_version)


def _mini_repo(tmp_path):
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / "a.json").write_text('{\n  "version": "1.0.0",\n  "d": "x→y"\n}\n', encoding="utf-8")
    (tmp_path / ".claude-plugin" / "marketplace.json").write_text(
        '{\n  "plugins": [\n    { "name": "tripwork", "version": "1.0.0" }\n  ]\n}\n')
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "tripwork"\nversion = "1.0.0"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 1.0.0 — first\n")
    (tmp_path / "CLAUDE.md").write_text("Behaviour added in v1.0.0.\n")  # excluded historical ref
    (tmp_path / ".version-bump.json").write_text(json.dumps({
        "files": [
            {"path": "a.json", "type": "json", "key": "version"},
            {"path": ".claude-plugin/marketplace.json", "type": "json", "key": "plugins.0.version"},
            {"path": "pyproject.toml", "type": "toml", "key": "version"},
            {"path": "CHANGELOG.md", "type": "changelog", "heading": "## {version}"},
        ],
        "audit": {"exclude": ["CHANGELOG.md", "CLAUDE.md", ".version-bump.json"]},
        "current": "1.0.0", "next": "1.1.0",
    }, indent=2))
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
    cfg = json.loads((repo / ".version-bump.json").read_text())
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
