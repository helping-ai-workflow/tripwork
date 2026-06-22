"""Smoke: the 5 new per-agent manifests exist, parse, and carry tripwork metadata."""
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent

_NEW = [".cursor-plugin/plugin.json", ".codex-plugin/plugin.json",
        ".kimi-plugin/plugin.json", "gemini-extension.json", "package.json"]

def test_all_new_manifests_parse_and_name_tripwork():
    for rel in _NEW:
        p = ROOT / rel
        assert p.is_file(), f"missing manifest {rel}"
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["name"] == "tripwork", f"{rel} name != tripwork"

def test_cursor_and_codex_wire_hooks():
    cur = json.loads((ROOT / ".cursor-plugin/plugin.json").read_text(encoding="utf-8"))
    cdx = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    assert cur["hooks"] == "./hooks/hooks-cursor.json"
    assert cdx["hooks"] == "./hooks/hooks-codex.json"

def test_package_json_wires_opencode_and_pi():
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert pkg["main"] == ".opencode/plugins/tripwork.js"
    assert pkg["pi"]["extensions"] == ["./.pi/extensions/tripwork.ts"]
    assert pkg["pi"]["skills"] == ["./skills"]
