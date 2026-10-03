"""Ship-gate: all 8 version-bearing manifests + CHANGELOG top must agree.

Runs in CI on every PR so a forgotten bump in any one file fails the build
instead of shipping a split version across agent runtimes.
"""
import json, pathlib, re
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
_CHANGELOG_TOP = re.compile(r"^##\s*(\d+\.\d+\.\d+)", re.MULTILINE)
_TOML_VERSION = re.compile(r'^version\s*=\s*"(\d+\.\d+\.\d+)"', re.MULTILINE)


def _changelog_top():
    m = _CHANGELOG_TOP.search((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    assert m, "CHANGELOG.md has no '## X.Y.Z' heading"
    return m.group(1)


def _json_version(rel, accessor):
    return accessor(json.loads((ROOT / rel).read_text(encoding="utf-8")))


def _toml_version(rel):
    m = _TOML_VERSION.search((ROOT / rel).read_text(encoding="utf-8"))
    assert m, f"{rel} has no version"
    return m.group(1)


# (rel_path, callable(root_relative)->version)
_MANIFESTS = {
    ".claude-plugin/plugin.json": lambda: _json_version(".claude-plugin/plugin.json", lambda d: d["version"]),
    ".claude-plugin/marketplace.json": lambda: _json_version(".claude-plugin/marketplace.json", lambda d: d["plugins"][0]["version"]),
    "pyproject.toml": lambda: _toml_version("pyproject.toml"),
    "package.json": lambda: _json_version("package.json", lambda d: d["version"]),
    ".cursor-plugin/plugin.json": lambda: _json_version(".cursor-plugin/plugin.json", lambda d: d["version"]),
    ".codex-plugin/plugin.json": lambda: _json_version(".codex-plugin/plugin.json", lambda d: d["version"]),
    ".kimi-plugin/plugin.json": lambda: _json_version(".kimi-plugin/plugin.json", lambda d: d["version"]),
    "gemini-extension.json": lambda: _json_version("gemini-extension.json", lambda d: d["version"]),
}


@pytest.mark.parametrize("rel_path,getter", list(_MANIFESTS.items()))
def test_manifest_version_matches_changelog_top(rel_path, getter):
    assert (ROOT / rel_path).is_file(), f"version-bearing manifest {rel_path} is missing"
    version = getter()
    top = _changelog_top()
    assert version == top, (
        f"{rel_path} declares {version!r} but CHANGELOG top is {top!r}; "
        f"run `python scripts/bump_version.py {top}` to resync.")


def test_shipped_version_bump_config_carries_previous():
    """F12 (v0.35.0 review): nothing pinned that the REAL, shipped
    `.version-bump.json` carries a `previous` field -- every existing
    `previous`-related test (tests/test_bump_version.py) exercises a
    synthetic `_mini_repo` fixture, not this repo's actual config. TW-078's
    second `--audit` scan (the one that catches a manifest stuck at the
    PREVIOUS version, never bumped at all) is silently SKIPPED whenever
    `previous` is absent (`scripts/bump_version.py`'s
    "Stale-manifest scan SKIPPED" branch) -- deleting the key from the real
    file would quietly turn that scan off with the whole suite staying
    green, since no test reads the real file's own `previous` key. `current`
    must also match the CHANGELOG top, tying this to the same live version
    every other assertion in this file checks."""
    cfg = json.loads((ROOT / ".version-bump.json").read_text(encoding="utf-8"))
    assert "previous" in cfg, (
        "the shipped .version-bump.json has no `previous` field -- "
        "TW-078's stale-manifest --audit scan is silently SKIPPED")
    assert re.fullmatch(r"\d+\.\d+\.\d+", cfg["previous"] or ""), (
        f"`previous` is not a bare X.Y.Z version: {cfg.get('previous')!r}")
    assert cfg["previous"] != cfg["current"], (
        "`previous` must not equal `current` -- bump() guards against this "
        "exact clobber (see its own comment on re-running at the same version)")
    assert cfg.get("current") == _changelog_top(), (
        f".version-bump.json `current` is {cfg.get('current')!r} but "
        f"CHANGELOG top is {_changelog_top()!r}")
