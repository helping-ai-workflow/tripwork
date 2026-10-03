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


# ---- TW-064 fix-round-1: alt-platform mirrors must not regress to the retired,
# tool-bound framing of the "no unsourced fact" iron rule ----------------------
#
# GEMINI.md, .kimi-plugin/plugin.json, .opencode/plugins/tripwork.js, and
# .pi/extensions/tripwork.ts each hand-author their own "tool mapping" note
# that restates the using-tripwork iron rule for their harness's vocabulary
# (Gemini's grounded search, Kimi's web-search tool, OpenCode's web-search
# tool, Pi's web-search tool). skills/using-tripwork/SKILL.md is the single
# canonical source for the rule itself; these four are documentation mirrors
# of it, not copies maintained independently on purpose. TW-064 moved the
# canonical rule from a single-tool HALT ("No search, no fact" / "never
# substitute model memory") to a three-rung source ladder — but the mirrors
# were edited by hand and three of the four regressed at first pass. GEMINI.md
# is the most dangerous instance: it @-includes the corrected skill body
# directly, then nine lines later tells the agent to HALT on one tool's
# absence with no fetch-tool route at all — the exact scenario TW-064 exists
# to prevent, reproduced by the mirror meant to describe it.
#
# Two deliberate design choices so this guard does not itself rot:
# 1. The negative assertions pin the RETIRED strings by name, not today's
#    replacement sentence. A retired label/phrase is a fixed historical
#    string — pinning it can never go stale, whereas pinning the current
#    sentence would break the next time the canonical wording is legitimately
#    revised (this is the same reasoning the Task 5 report used for
#    test_iron_rule_halts_on_provenance_not_on_a_tool_name).
# 2. The positive assertions only require each mirror to still name both
#    consumer-harness tokens the ladder is built from (`WebSearch` and
#    `WebFetch`) and the word "ladder" — the concept name, not a specific
#    sentence — so a future wording tweak to the canonical rule does not
#    desync this guard from reality the way test_gemini_md_includes_using_tripwork's
#    bare `"WebSearch" in text` check silently did here (true before AND
#    after the regression, so it never caught it).
_LADDER_MIRRORS = (
    "GEMINI.md",
    ".kimi-plugin/plugin.json",
    ".opencode/plugins/tripwork.js",
    ".pi/extensions/tripwork.ts",
)
_RETIRED_LABEL = "No search, no fact"
_RETIRED_PHRASE = "never substitute model memory"


def test_agent_context_mirrors_do_not_quote_the_retired_rule():
    for rel in _LADDER_MIRRORS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert _RETIRED_LABEL not in text, \
            f"{rel} still quotes the retired rule label {_RETIRED_LABEL!r}"
        assert _RETIRED_PHRASE not in text, \
            f"{rel} still quotes the retired phrase {_RETIRED_PHRASE!r}"


def test_agent_context_mirrors_name_the_ladder_not_one_tool():
    for rel in _LADDER_MIRRORS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "WebSearch" in text, f"{rel} must still name WebSearch (ladder rung 1)"
        assert "WebFetch" in text, f"{rel} must name WebFetch (ladder rungs 2/3)"
        assert "ladder" in text, f"{rel} must point at the source ladder, not a single tool"
