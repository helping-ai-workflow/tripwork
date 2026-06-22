"""Structural guards for the version-less alt-platform descriptors (opencode, pi)."""
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_opencode_install_and_plugin_present():
    assert (ROOT / ".opencode" / "INSTALL.md").is_file()
    assert (ROOT / ".opencode" / "plugins" / "tripwork.js").is_file()
    assert not (ROOT / ".opencode" / "plugin.json").exists()


def test_opencode_plugin_registers_tripwork_skills():
    js = (ROOT / ".opencode" / "plugins" / "tripwork.js").read_text(encoding="utf-8")
    assert "using-tripwork" in js
    assert "../../skills" in js


def test_pi_extension_registers_tripwork_skills():
    ts = (ROOT / ".pi" / "extensions" / "tripwork.ts").read_text(encoding="utf-8")
    assert "using-tripwork" in ts
    assert "skillPaths" in ts


def test_package_json_wires_main_and_pi():
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert pkg["main"] == ".opencode/plugins/tripwork.js"
    assert pkg["pi"]["extensions"] == ["./.pi/extensions/tripwork.ts"]
    assert pkg["pi"]["skills"] == ["./skills"]
