"""Guard: skill descriptions stay lean (always-on preload ceiling).

Every skill's frontmatter `description` loads into the system prompt of every
session (the skill-discovery list). This is tripwork's only always-on preload
on Claude Code. Cap each description at DESC_CEILING chars to prevent regrowth,
and require the "Use when" trigger prefix so the field stays a triggering
condition rather than a what-it-does summary.
"""
from pathlib import Path
import re

SKILLS = Path(__file__).resolve().parents[1] / "skills"
DESC_CEILING = 210


def _description(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8")
    m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
    assert m, f"{skill_md} has no description field"
    return m.group(1).strip()


def test_every_description_within_ceiling_and_use_when():
    offenders = []
    for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
        name = skill_md.parent.name
        desc = _description(skill_md)
        if len(desc) > DESC_CEILING:
            offenders.append(f"{name}: {len(desc)} > {DESC_CEILING} chars")
        if not desc.startswith("Use when"):
            offenders.append(f"{name}: must start with 'Use when'")
    assert not offenders, "description hygiene violations:\n" + "\n".join(offenders)
