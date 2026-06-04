import pathlib
import re
import pytest

SKILLS = pathlib.Path(__file__).resolve().parent.parent / "skills"

EXPECTED = [
    "using-tripwork", "orchestrator", "trip-brief", "destination-research",
    "source-verify", "routing-audit", "calendar-check", "itinerary-synthesis",
    "travel-advisory", "itinerary-gate", "export-artifact", "workspace-shape-preflight",
]

def _frontmatter(md_text):
    m = re.match(r"^---\n(.*?)\n---\n", md_text, re.DOTALL)
    return m.group(1) if m else None

# Stage skills (everything except the entry skill) must carry a paperwork-style
# Stage Contract table.
STAGE_SKILLS = [n for n in EXPECTED if n != "using-tripwork"]

@pytest.mark.parametrize("name", EXPECTED)
def test_skill_exists_with_frontmatter(name):
    p = SKILLS / name / "SKILL.md"
    assert p.exists(), f"missing skill {name}"
    fm = _frontmatter(p.read_text(encoding="utf-8"))
    assert fm is not None, f"{name} missing frontmatter"
    assert re.search(r"^name:\s*" + re.escape(name) + r"\s*$", fm, re.MULTILINE), f"{name} frontmatter name mismatch"
    assert re.search(r"^description:\s*\S", fm, re.MULTILINE), f"{name} missing description"

@pytest.mark.parametrize("name", STAGE_SKILLS)
def test_stage_skill_has_stage_contract(name):
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    assert "## Stage Contract" in text, f"{name} missing Stage Contract table"
    # Stage Contract must declare the four paperwork fields
    for field in ("Input", "Output", "Stop condition", "Next stage"):
        assert field in text, f"{name} Stage Contract missing '{field}'"

def test_entry_skill_has_iron_rules_and_quick_reference():
    text = (SKILLS / "using-tripwork" / "SKILL.md").read_text(encoding="utf-8")
    assert "## Iron Rules" in text
    assert "## Quick Reference" in text
    assert "Source-Verified-First" in text

def test_iron_rule_skills_state_source_verified_first():
    for name in ["source-verify", "travel-advisory"]:
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        assert "Source-Verified-First" in text, f"{name} must state the iron rule"

def test_export_skill_documents_notion_graceful_skip():
    text = (SKILLS / "export-artifact" / "SKILL.md").read_text(encoding="utf-8")
    assert "graceful" in text.lower() or "skip" in text.lower()
    assert "Notion" in text

def test_source_verify_geocode_uses_name_local():
    # Gate 2 geocode query must use name_local: live Nominatim mis-resolves
    # English descriptor suffixes (e.g. "Togetsukyo Bridge" -> no result while
    # "渡月橋" resolves). Keeps verify consistent with export's name_local usage.
    text = (SKILLS / "source-verify" / "SKILL.md").read_text(encoding="utf-8")
    assert "name_local" in text, "source-verify Gate 2 must geocode by name_local"


def test_preflight_documents_stamp_and_gate():
    text = (SKILLS / "workspace-shape-preflight" / "SKILL.md").read_text(encoding="utf-8")
    assert "preflight-completed" in text  # stamp file name
    assert "orchestrator" in text          # gates the orchestrator
