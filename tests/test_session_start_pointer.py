"""Guard: session-start injects the Tier-1 routing pointer.

The hook must emit valid JSON on stdout whose additionalContext carries the
"enter the pipeline, never from memory" imperative (Tier-1 routing nudge).
It must NOT inline the full using-tripwork body (that stays lazy-loaded).
"""
import json
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "session-start"


def _run_claude():
    env = {k: v for k, v in os.environ.items() if k not in ("CURSOR_PLUGIN_ROOT", "COPILOT_CLI")}
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO)
    out = subprocess.check_output(["bash", str(HOOK)], env=env, text=True)
    return out


def test_stdout_is_valid_json_with_additional_context():
    data = json.loads(_run_claude())
    ctx = data["hookSpecificOutput"]["additionalContext"]
    assert ctx.strip(), "additionalContext must be non-empty"


def test_pointer_carries_routing_imperative():
    ctx = json.loads(_run_claude())["hookSpecificOutput"]["additionalContext"]
    assert "tripwork:tripwork-orchestrator" in ctx
    assert "tripwork:tripwork-workspace-shape-preflight" in ctx
    assert "memory" in ctx           # "never ... from model memory"
    assert "Source-Verified-First" in ctx
    assert "tripwork:using-tripwork" in ctx


def test_pointer_pins_resume_clause():
    # The resume clause is the load-bearing warm-resume mitigation: it stops an
    # agent from free-drafting the rest of an in-progress trip on a "continue"
    # prompt. Pin it directly so a regression that drops it cannot slip through
    # on the incidental substring overlap of the other assertions.
    ctx = json.loads(_run_claude())["hookSpecificOutput"]["additionalContext"]
    assert "resuming" in ctx, "resume clause missing — warm-resume free-draft mitigation must stay"
    assert "re-enter tripwork:tripwork-orchestrator" in ctx


def test_pointer_is_tier1_not_full_body():
    # Tier-1 pointer, not the full using-tripwork body: reject the body's
    # section headings so a future accidental full-body inject fails here.
    ctx = json.loads(_run_claude())["hookSpecificOutput"]["additionalContext"]
    assert "## Iron Rules" not in ctx
    assert "## Stage Contract" not in ctx
    assert len(ctx) < 700, f"pointer should be ~80 tokens, got {len(ctx)} chars"


# --- v2.0.0 spec §2: the pointer tells the agent where tripwork.py is ----------------

def _run_with(env_over, drop=("CURSOR_PLUGIN_ROOT", "COPILOT_CLI", "CLAUDE_PLUGIN_ROOT")):
    env = {k: v for k, v in os.environ.items() if k not in drop}
    env.update(env_over)
    return subprocess.check_output(["bash", str(HOOK)], env=env, text=True)


def test_pointer_names_tripwork_py_from_the_host_root(tmp_path):
    root = tmp_path / 'odd "dir" \\ with space'
    root.mkdir()
    ctx = json.loads(_run_with({"CLAUDE_PLUGIN_ROOT": str(root)}))["hookSpecificOutput"]["additionalContext"]
    assert f'python "{root}/scripts/tripwork.py" <command> <slug>' in ctx


def test_pointer_falls_back_to_the_hook_directory():
    out = _run_with({})
    ctx = json.loads(out)["additionalContext"]
    assert f'"{REPO}/scripts/tripwork.py"' in ctx


def test_pointer_stays_short_apart_from_the_path():
    ctx = json.loads(_run_claude())["hookSpecificOutput"]["additionalContext"]
    assert len(ctx.replace(str(REPO), "<root>")) < 700
