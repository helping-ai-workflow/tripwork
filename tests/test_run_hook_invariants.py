"""hooks/run-hook.cmd must ship LF-normalised and executable (git mode 100755).

CRLF breaks the polyglot wrapper's bash branch (`session-start\\r: not found`);
a missing +x bit makes the SessionStart exec fail with EACCES. Both are real
regressions seen in sibling plugins (chipwork v0.7.4/v0.7.5).
"""
import subprocess
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]


def test_gitattributes_forces_lf_for_cmd():
    text = (REPO / ".gitattributes").read_text(encoding="utf-8")
    assert "*.cmd text eol=lf" in text
    assert "*.cmd text eol=crlf" not in text


def test_run_hook_cmd_is_lf_in_index():
    out = subprocess.check_output(
        ["git", "-C", str(REPO), "ls-files", "--eol", "hooks/run-hook.cmd"], text=True)
    assert "i/lf" in out, f"run-hook.cmd index must be i/lf, got:\n{out}"


def test_run_hook_cmd_is_executable_in_index():
    out = subprocess.check_output(
        ["git", "-C", str(REPO), "ls-files", "--stage", "hooks/run-hook.cmd"], text=True)
    assert out.split()[0] == "100755", f"run-hook.cmd must be git mode 100755, got: {out.split()[0]}"


def test_session_start_is_executable_in_index():
    out = subprocess.check_output(
        ["git", "-C", str(REPO), "ls-files", "--stage", "hooks/session-start"], text=True)
    assert out.split()[0] == "100755", f"hooks/session-start must be git mode 100755, got: {out.split()[0]}"
