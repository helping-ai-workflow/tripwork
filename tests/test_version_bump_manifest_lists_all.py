"""`.version-bump.json` must declare exactly the 8 canonical version-bearing files."""
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent

_CANONICAL = {
    ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
    "pyproject.toml", "package.json", ".cursor-plugin/plugin.json",
    ".codex-plugin/plugin.json", ".kimi-plugin/plugin.json", "gemini-extension.json",
}

def test_version_bump_lists_exactly_canonical_eight():
    cfg = json.loads((ROOT / ".version-bump.json").read_text(encoding="utf-8"))
    declared = {e["path"] for e in cfg["files"] if e.get("type") in ("json", "toml")}
    assert declared == _CANONICAL, (
        f"version-bump json/toml entries must equal the canonical 8; "
        f"missing={_CANONICAL - declared}, extra={declared - _CANONICAL}")
