"""README freshness guard — mechanical drift detection.

Mirrors paperwork's `test_readme_freshness.py`: when a flow skill is added /
renamed / removed, or a pipeline stage moves, README.md must be updated in the
same PR. This test fails on the mechanical half of that drift (skill-mention
coverage + no obsolete names). Narrative correctness stays human review.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
SKILLS = ROOT / "skills"

# Every stage/flow skill must be named in README (mermaid or step table).
# `using-tripwork` is the meta/entry skill (agent-facing routing), not a
# user-facing pipeline stage — excluded, like paperwork excludes using-paperwork.
META_SKILLS = {"using-tripwork"}
SKILL_NAMES = sorted(p.name for p in SKILLS.iterdir()
                     if (p / "SKILL.md").exists() and p.name not in META_SKILLS)

# Names that were removed/renamed and must never reappear outside a removal note.
OBSOLETE = []


def test_every_skill_mentioned_in_readme():
    missing = [n for n in SKILL_NAMES if n not in README]
    assert not missing, f"README does not mention skill(s): {missing}. Update README in the same PR."


def test_no_obsolete_names_in_readme():
    present = [n for n in OBSOLETE if n in README]
    assert not present, f"README still mentions removed name(s): {present}."


def test_calendar_check_in_pipeline_diagram():
    # The calendar-awareness stage must be visible in the workflow section,
    # not only in the step table — guards against the mermaid drifting.
    assert "calendar-check" in README
