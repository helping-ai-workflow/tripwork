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


# --- D5: trigger artifacts must be REAL data dependencies -------------------
# A description's trigger clause ("Use when X.yaml is ready ...") must cite only
# artifacts the skill actually consumes (Stage Contract Input row). Ordering
# belongs to the orchestrator, never to a trigger. Limitation: only
# `.yaml`-suffixed citations are checked — bare English words like "calendar"
# or "transit" are ambiguous and stay human-review territory.
ARTIFACT_REF = re.compile(
    r"\b(trip-brief|candidates|verified-pois|verified-pois-media|routing|"
    r"accommodations|legs|calendar|seasonal|transit|cost|advisory|itinerary|"
    r"gate-report)\.yaml\b")
META_SKILLS = {"using-tripwork", "orchestrator", "workspace-shape-preflight"}


def _input_row(text: str) -> str:
    m = re.search(r"^\|\s*Input\s*\|(.+)\|\s*$", text, re.MULTILINE)
    return m.group(1) if m else ""


def test_trigger_artifacts_are_stage_contract_inputs():
    offenders = []
    for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
        name = skill_md.parent.name
        if name in META_SKILLS:
            continue
        text = skill_md.read_text(encoding="utf-8")
        trigger = _description(skill_md).split("Produces")[0]
        inp = _input_row(text)
        for stem in ARTIFACT_REF.findall(trigger):
            if stem not in inp:
                offenders.append(
                    f"{name}: trigger cites {stem}.yaml, not in Stage Contract Input")
    assert not offenders, "\n".join(offenders)


def test_calendar_check_trigger_matches_real_inputs():   # D5 pin
    desc = _description(SKILLS / "calendar-check" / "SKILL.md")
    assert "trip-brief.yaml" in desc
    assert "verified-pois" not in desc and "routing" not in desc


def test_seasonal_advisory_trigger_matches_real_inputs():   # D5 pin
    desc = _description(SKILLS / "seasonal-advisory" / "SKILL.md")
    assert "routing.yaml" in desc and "accommodations.yaml" in desc
    assert "calendar" not in desc
