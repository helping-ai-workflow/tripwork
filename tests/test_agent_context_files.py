"""GEMINI.md @-includes using-tripwork; AGENTS.md resolves to CLAUDE.md."""
import os, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_gemini_md_includes_using_tripwork():
    text = (ROOT / "GEMINI.md").read_text(encoding="utf-8")
    assert "@./skills/using-tripwork/SKILL.md" in text
    assert "WebSearch" in text  # tripwork-specific tool-mapping note present


def test_agents_md_is_symlink_to_claude_md():
    p = ROOT / "AGENTS.md"
    assert p.is_symlink(), "AGENTS.md must be a symlink"
    assert os.readlink(p) == "CLAUDE.md"
    assert p.resolve() == (ROOT / "CLAUDE.md").resolve()
