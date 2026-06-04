"""Ship-gate: plugin.json / marketplace.json / CHANGELOG versions must agree.

Mirrors the release-flow halt condition "version files disagree → that's a
release-flow bug, halt before merging". Runs in CI on every PR so a forgotten
bump in any one file fails the build instead of shipping a split version.
"""
import json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _plugin_version():
    return json.load(open(ROOT / ".claude-plugin" / "plugin.json"))["version"]


def _marketplace_version():
    mk = json.load(open(ROOT / ".claude-plugin" / "marketplace.json"))
    return mk["plugins"][0]["version"]


def _changelog_top_version():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"^##\s*(\d+\.\d+\.\d+)", text, re.MULTILINE)
    assert m, "CHANGELOG.md has no '## X.Y.Z' heading"
    return m.group(1)


def test_plugin_and_marketplace_versions_match():
    assert _plugin_version() == _marketplace_version(), \
        "plugin.json and marketplace.json versions disagree"


def test_changelog_top_matches_plugin_version():
    assert _changelog_top_version() == _plugin_version(), \
        "CHANGELOG top heading does not match plugin.json version"
