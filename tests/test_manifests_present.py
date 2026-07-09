"""Smoke: the 5 new per-agent manifests exist, parse, and carry tripwork metadata."""
import json, pathlib, subprocess
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

def _codex_hook_commands() -> list[str]:
    data = json.loads((ROOT / "hooks/hooks-codex.json").read_text(encoding="utf-8"))
    return [
        h["command"]
        for entries in data["hooks"].values()
        for entry in entries
        for h in entry["hooks"]
    ]

def test_codex_hook_commands_are_plugin_root_anchored():
    # Codex runs hook commands via `$SHELL -lc` with cwd = the session
    # workspace, NOT the plugin root — a `./hooks/...` relative path exits 127
    # on every real install. Codex exports CLAUDE_PLUGIN_ROOT (and PLUGIN_ROOT)
    # to hook processes, so the command must anchor on it, like hooks.json.
    cmds = _codex_hook_commands()
    assert cmds, "hooks-codex.json declares no commands"
    for cmd in cmds:
        assert "${CLAUDE_PLUGIN_ROOT}" in cmd, f"not plugin-root-anchored: {cmd}"
        assert "./hooks/" not in cmd, f"cwd-relative path breaks on Codex: {cmd}"

def test_codex_hook_command_executes_from_foreign_cwd(tmp_path):
    # e2e closure: simulate Codex's exec model — shell -lc, cwd far away from
    # the plugin root, CLAUDE_PLUGIN_ROOT in env — and require the SessionStart
    # command to succeed and emit the Claude-format hook JSON.
    for cmd in _codex_hook_commands():
        proc = subprocess.run(
            ["bash", "-lc", cmd],
            cwd=tmp_path,
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": str(tmp_path),
                "CLAUDE_PLUGIN_ROOT": str(ROOT),
            },
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, (
            f"hook command failed from foreign cwd (rc={proc.returncode}): "
            f"{cmd}\nstderr: {proc.stderr}"
        )
        assert "hookSpecificOutput" in proc.stdout, (
            f"hook did not emit SessionStart JSON: {proc.stdout!r}"
        )

def test_package_json_wires_opencode_and_pi():
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert pkg["main"] == ".opencode/plugins/tripwork.js"
    assert pkg["pi"]["extensions"] == ["./.pi/extensions/tripwork.ts"]
    assert pkg["pi"]["skills"] == ["./skills"]
