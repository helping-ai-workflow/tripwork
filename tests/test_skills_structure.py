import pathlib
import re
import pytest

SKILLS = pathlib.Path(__file__).resolve().parent.parent / "skills"

EXPECTED = [
    "using-tripwork", "orchestrator", "trip-brief", "destination-research",
    "source-verify", "routing-audit", "accommodation-research", "inter-stop-legs",
    "calendar-check", "seasonal-advisory", "cost-rollup", "itinerary-synthesis",
    "travel-advisory", "itinerary-gate", "export-artifact", "export-gate",
    "workspace-shape-preflight",
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

def test_orchestrator_wires_export_gate_after_export():
    text = (SKILLS / "orchestrator" / "SKILL.md").read_text(encoding="utf-8")
    assert "export-gate" in text, "orchestrator must route to export-gate after export-artifact"

def test_export_artifact_uses_slug_named_deliverable():
    text = (SKILLS / "export-artifact" / "SKILL.md").read_text(encoding="utf-8")
    assert "<slug>-itinerary.md" in text, "deliverable must be renamed to avoid intermediate clash (D3)"
    assert "render_day_table" in text, "day table must go through the renderer, not hand-authoring (D5)"

def test_trip_brief_documents_overnight_stops_and_facilities():
    text = (SKILLS / "trip-brief" / "SKILL.md").read_text(encoding="utf-8")
    assert "overnight_stops" in text
    assert "facility_needs" in text

def test_trip_brief_documents_transport():
    text = (SKILLS / "trip-brief" / "SKILL.md").read_text(encoding="utf-8")
    assert "transport" in text

def test_routing_audit_documents_centroid():
    text = (SKILLS / "routing-audit" / "SKILL.md").read_text(encoding="utf-8")
    assert "centroid" in text

def test_source_verify_documents_geocode_degrade():
    text = (SKILLS / "source-verify" / "SKILL.md").read_text(encoding="utf-8")
    assert "resolve_place" in text or "structured" in text
    assert "unverified" in text  # geocode-fail degrades, not rejected

def test_source_verify_documents_geocode_cache():
    text = (SKILLS / "source-verify" / "SKILL.md").read_text(encoding="utf-8")
    assert "geocode-cache" in text

def test_synthesis_documents_lodging_and_coverage():
    text = (SKILLS / "itinerary-synthesis" / "SKILL.md").read_text(encoding="utf-8")
    assert "accommodations" in text
    assert "coverage_gaps" in text

def test_itinerary_gate_documents_lodging_checks():
    text = (SKILLS / "itinerary-gate" / "SKILL.md").read_text(encoding="utf-8")
    assert "overnight_stops_have_lodging" in text
    assert "required_facilities_met" in text

def test_orchestrator_wires_accommodation_research():
    text = (SKILLS / "orchestrator" / "SKILL.md").read_text(encoding="utf-8")
    assert "accommodation-research" in text

def test_synthesis_documents_seasonal():
    text = (SKILLS / "itinerary-synthesis" / "SKILL.md").read_text(encoding="utf-8")
    assert "seasonal" in text
    assert "after_dark" in text or "after-dark" in text

def test_orchestrator_wires_seasonal_advisory():
    text = (SKILLS / "orchestrator" / "SKILL.md").read_text(encoding="utf-8")
    assert "seasonal-advisory" in text

def test_trip_brief_documents_leg_mode():
    text = (SKILLS / "trip-brief" / "SKILL.md").read_text(encoding="utf-8")
    assert "leg_mode" in text
    assert "max_single_drive_mins" in text

def test_synthesis_documents_legs():
    text = (SKILLS / "itinerary-synthesis" / "SKILL.md").read_text(encoding="utf-8")
    assert "legs.yaml" in text
    assert "last_service" in text or "pass_advice" in text

def test_orchestrator_wires_inter_stop_legs():
    text = (SKILLS / "orchestrator" / "SKILL.md").read_text(encoding="utf-8")
    assert "inter-stop-legs" in text

def test_trip_brief_documents_budget():
    text = (SKILLS / "trip-brief" / "SKILL.md").read_text(encoding="utf-8")
    assert "budget" in text
    assert "daily_incidental" in text

def test_accommodation_research_records_numeric_cost():
    text = (SKILLS / "accommodation-research" / "SKILL.md").read_text(encoding="utf-8")
    assert "numeric `cost`" in text or "`cost` (amount" in text

def test_inter_stop_legs_records_fare():
    text = (SKILLS / "inter-stop-legs" / "SKILL.md").read_text(encoding="utf-8")
    assert "`fare`" in text
    assert "pass" in text  # the trip-level pass option

def test_synthesis_documents_cost_summary():
    text = (SKILLS / "itinerary-synthesis" / "SKILL.md").read_text(encoding="utf-8")
    assert "cost.yaml" in text

def test_orchestrator_wires_cost_rollup():
    text = (SKILLS / "orchestrator" / "SKILL.md").read_text(encoding="utf-8")
    assert "cost-rollup" in text
