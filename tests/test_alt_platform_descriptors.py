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


# --- v2.0.0 spec §2: OpenCode / Pi inject the tripwork.py path -------------------------

def test_opencode_injects_the_tripwork_py_path():
    """Runs the plugin under node (no skip: Node >= 18 is a dev requirement)."""
    import subprocess
    js = (ROOT / ".opencode" / "plugins" / "tripwork.js").as_uri()
    probe = (f"const m = await import({json.dumps(js)});"
             "const p = await m.TripworkPlugin();"
             "const out = {messages: [{info: {role: 'user'}, parts: [{type: 'text', text: 'hi'}]}]};"
             "await p['experimental.chat.messages.transform']({}, out);"
             "console.log(out.messages[0].parts[0].text);")
    r = subprocess.run(["node", "--input-type=module", "-e", probe], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert f"{ROOT}/scripts/tripwork.py" in r.stdout


def test_pi_names_the_tripwork_py_path():
    # Literal source check because CI's Node 20 cannot run a .ts extension.
    ts = (ROOT / ".pi" / "extensions" / "tripwork.ts").read_text(encoding="utf-8")
    assert 'resolve(packageRoot, "scripts", "tripwork.py")' in ts
