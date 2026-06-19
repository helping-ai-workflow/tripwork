import pathlib
import re
import pytest

SKILLS = pathlib.Path(__file__).resolve().parent.parent / "skills"

EXPECTED = [
    "using-tripwork", "orchestrator", "trip-brief", "destination-research",
    "source-verify", "routing-audit", "accommodation-research", "inter-stop-legs",
    "calendar-check", "seasonal-advisory", "transit-detail", "cost-rollup",
    "itinerary-synthesis", "travel-advisory", "itinerary-gate", "export-artifact",
    "export-gate", "workspace-shape-preflight",
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

def test_export_gate_runs_on_merged_pois():   # D8: photo checks need post-apply_media pois
    # The gate's photo_has_attribution + no_nondistributable_photo_source checks see a
    # `photo`/`photo_source` only on the MERGED pois (apply_media output). Feeding it the
    # canonical verified-pois.yaml (which never carries photos, per PR6) makes those
    # checks spin. The SKILL must document the media overlay before the gate.
    text = (SKILLS / "export-gate" / "SKILL.md").read_text(encoding="utf-8")
    assert "verified-pois-media" in text
    assert "apply_media" in text or "media_merge" in text

def test_entry_skill_has_iron_rules_and_quick_reference():
    text = (SKILLS / "using-tripwork" / "SKILL.md").read_text(encoding="utf-8")
    assert "## Iron Rules" in text
    assert "## Quick Reference" in text
    assert "Source-Verified-First" in text

def test_iron_rule_skills_state_source_verified_first():
    for name in ["source-verify", "travel-advisory"]:
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        assert "Source-Verified-First" in text, f"{name} must state the iron rule"

def test_export_skill_documents_notion_as_md_paste_not_adapter():
    # 0.20.0: Notion is no longer a tracked adapter/deliverable — the agent pastes the
    # gated md via MCP, so it inherits export-gate hygiene with no separate gate.
    text = (SKILLS / "export-artifact" / "SKILL.md").read_text(encoding="utf-8")
    assert "Notion" in text
    assert "not a tracked adapter" in text
    assert "MCP" in text

def test_synthesis_documents_move_from_to():   # G2 — authoring contract must drive the feature
    # G2 added optional row.from/row.to that the renderers turn into an A→B directions chip.
    # The synthesis SKILL must instruct the author to populate them on move rows, else the
    # chip never fires on real data (feature dead-on-arrival).
    text = (SKILLS / "itinerary-synthesis" / "SKILL.md").read_text(encoding="utf-8")
    assert "from" in text and "to" in text
    assert "move" in text and "directions" in text.lower()

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

def test_accommodation_research_documents_geocode_cache():
    text = (SKILLS / "accommodation-research" / "SKILL.md").read_text(encoding="utf-8")
    assert "geocode-cache" in text

def test_trip_brief_documents_max_walk_mins():
    text = (SKILLS / "trip-brief" / "SKILL.md").read_text(encoding="utf-8")
    assert "max_walk_mins" in text

def test_synthesis_documents_transit():
    text = (SKILLS / "itinerary-synthesis" / "SKILL.md").read_text(encoding="utf-8")
    assert "transit.yaml" in text
    assert "in_peak" in text or "walk_too_far" in text

def test_orchestrator_wires_transit_detail():
    text = (SKILLS / "orchestrator" / "SKILL.md").read_text(encoding="utf-8")
    assert "transit-detail" in text


# ---- Wave 3 (v0.14.0) flow + contract guards ----

def _orch():
    return (SKILLS / "orchestrator" / "SKILL.md").read_text(encoding="utf-8")

def test_tw054_orchestrator_namespaces_skill_names():
    text = _orch()
    dirnames = {p.name for p in SKILLS.iterdir() if p.is_dir()}
    bare = [n for n in dirnames if re.search(r"(?<!:)`" + re.escape(n) + r"`", text)]
    assert not bare, f"bare (un-namespaced) skill names in orchestrator: {bare}"

def test_tw053_orchestrator_defines_stale_and_ready():
    text = _orch()
    assert "candidate id" in text and "absent from" in text  # stale predicate
    assert re.search(r"\*\*ready\*\*", text)                  # ready defined once

def test_tw027_slug_binding_before_trip_brief():
    text = _orch()
    bind = text.find("Bind `<slug>`")
    first_rule = text.find("No trip-brief.yaml")
    assert 0 <= bind < first_rule, "slug-binding rule must precede the trip-brief rule"
    tb = (SKILLS / "trip-brief" / "SKILL.md").read_text(encoding="utf-8")
    assert "<yyyy-mm>-<destination>" in tb and "already exists" in tb

def test_tw029_orchestrator_fail_routing_and_terminal():
    text = _orch()
    assert "status==fail" in text and "itinerary-synthesis" in text and "accommodation-research" in text
    assert "newer than gate-report.yaml" in text
    assert "pipeline complete" in text

def test_tw031_halt_list_reception_and_banned_only():
    text = _orch()
    assert re.search(r"reception", text) and re.search(r"late check.?in", text)
    assert "`banned`" in text
    assert "regulation risk" not in text

def test_tw055_orchestrator_readback_rule():
    text = _orch()
    assert "stage-state.yaml" in text and "decision" in text
    assert "before" in text.lower() and "re-ask" in text.lower().replace("re-asking", "re-ask")

def test_tw035_travel_advisory_standalone_no_write():
    text = (SKILLS / "travel-advisory" / "SKILL.md").read_text(encoding="utf-8")
    assert "Standalone" in text and "advisory-adhoc.yaml" in text
    assert _orch().find("stale relative to itinerary.md") > 0

def test_tw036_trip_brief_preflight_guard_before_write():
    text = (SKILLS / "trip-brief" / "SKILL.md").read_text(encoding="utf-8")
    guard = text.find("preflight-completed")
    write = text.find("trips/<slug>/trip-brief.yaml")
    assert 0 <= guard < write, "preflight guard must precede the first write"
    fm = _frontmatter(text)
    assert "orchestrator has routed" in fm
    assert "when a new travel request arrives" not in fm

def test_tw026_synthesis_rechecks_missed_last_service():
    text = (SKILLS / "itinerary-synthesis" / "SKILL.md").read_text(encoding="utf-8")
    # the blanket prohibition must be gone for missed_last_service; re-check instructed
    assert "MUST be re-checked here" in text
    assert "classify_leg" in text or "misses_last_service" in text

def test_tw037_using_tripwork_pipeline_full_order():
    text = (SKILLS / "using-tripwork" / "SKILL.md").read_text(encoding="utf-8")
    block = re.search(r"```\n(.*?)```", text, re.DOTALL).group(1)
    order = ["trip-brief", "destination-research", "source-verify", "routing-audit",
             "accommodation-research", "inter-stop-legs", "calendar-check",
             "seasonal-advisory", "transit-detail", "cost-rollup", "travel-advisory",
             "itinerary-synthesis", "itinerary-gate", "export-artifact", "export-gate"]
    positions = [block.find(n) for n in order]
    assert all(p >= 0 for p in positions), f"missing stages: {[n for n,p in zip(order,positions) if p<0]}"
    assert positions == sorted(positions), "using-tripwork pipeline order diverges from orchestrator"


# ---- Wave 4 (v0.15.0) research-discipline + adapter prose guards ----

def _skill(name):
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")

def test_tw024_websearch_unavailable_halts():
    t = _skill("using-tripwork")
    assert "WebSearch" in t and "HALT" in t and "never substitute model memory" in t

def test_tw025_notion_is_gated_md_paste_not_adapter():
    # 0.20.0: Notion is no longer a post-gate write-back adapter. The itinerary reaches
    # Notion by pasting the already-gated md via MCP — no page-id bookkeeping, no adapter.
    t = _skill("export-artifact")
    assert "gated" in t and "Notion" in t and "MCP" in t
    assert ".notion-page-id" not in t   # the old adapter bookkeeping is gone

def test_tw032_independent_and_conflict_defined():
    t = _skill("source-verify")
    assert "root domain" in t and "material factual disagreement" in t

def test_tw033_hours_recency_as_of():
    t = _skill("source-verify")
    assert "hours.as_of" in t and ("12 months" in t or "recency" in t.lower())

def test_tw051_centroid_existence_proof():
    t = _skill("accommodation-research")
    assert "existence proof" in t and "official" in t

def test_tw052_calendar_trip_year_provisional():
    t = _skill("calendar-check")
    assert "trip year" in t and "provisional" in t

def test_tw057_cache_invalidation_on_reverify():
    t = _skill("source-verify")
    assert "cache_key" in t and "re-verif" in t.lower()

def test_tw058_gate3_district_centroid():
    t = _skill("source-verify")
    assert "claimed district once" in t and "in_region" in t

def test_tw061_calendar_no_same_rigor():
    t = _skill("calendar-check")
    assert "same rigor" not in t
    assert "corroborating source" in t

def test_tw039_trip_brief_cache_lifecycle():
    t = _skill("trip-brief")
    assert "geocode-cache" in t and "destination or dates" in t and "rebuildable" in t
