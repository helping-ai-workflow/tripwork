"""Guard: using-tripwork body carries the Pipeline tree, not a duplicate roster.

The Pipeline tree already lists every stage + order + output artifact. A second
'## Quick Reference' task->skill table repeats that roster. using-tripwork is
force-loaded into every Gemini session (GEMINI.md @import) and lazy-loaded on
Claude, so the duplicate is pure redundant load. Mirror of paperwork's
test_using_paperwork_quick_ref_no_dispatch_roster.
"""
from pathlib import Path

BODY = (Path(__file__).resolve().parents[1]
        / "skills" / "using-tripwork" / "SKILL.md").read_text(encoding="utf-8")


def test_pipeline_tree_retained():
    # The canonical stage map (with output artifacts + calendar-check) stays.
    assert "## Pipeline" in BODY
    assert "orchestrator" in BODY
    assert "calendar-check" in BODY


def test_no_quick_reference_roster_table():
    # The duplicate task->skill roster must be gone.
    assert "## Quick Reference" not in BODY, (
        "using-tripwork still has the Quick Reference roster — it duplicates "
        "the Pipeline tree; remove the table, keep the tree."
    )
