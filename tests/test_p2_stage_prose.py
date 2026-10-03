"""v1.0 P2 — every producing stage tells the agent to write the fields the P1
gate now requires. Vocabulary is read from the shipped constants, never copied."""
import re

from scripts.brief_names import DEVICES, HEADLINE_MAX, RIFF_DEVICES
from scripts.checklist import KINDS
from scripts.day_chain import ALT_KINDS, MOVE_MODES, THEME_MAX
from scripts.orchestration import STOP_FLAGS
from tests.test_skill_prose_hygiene import SKILLS, _contract_row, _skill


def _has(body, token):
    """A backticked token counts when the field name appears inside any code span
    (`booking.opens_at`, `{kind, applies_to, …}`); a plain token is a substring."""
    if not token.startswith("`"):
        return token in body
    name = token.strip("`")
    return re.search(rf"`[^`\n]*(?<![\w]){re.escape(name)}(?![\w])[^`\n]*`", body) is not None


def _ref(skill, name):
    return (SKILLS / skill / "references" / name).read_text(encoding="utf-8")


# ---- trip-brief ------------------------------------------------------------

def test_trip_brief_captures_short_name_and_day_label():
    body = _skill("trip-brief")
    for token in ("`short_name`", "`day_label`", "scripts/brief_names.py"):
        assert _has(body, token), token


def test_trip_brief_proposes_three_headlines_and_halts_for_the_pick():
    body = _skill("trip-brief")
    for token in ("`headline`", "`headline_candidates`", "`riff_on`", "`refs`",
                  "references/kuso-headlines.md"):
        assert _has(body, token), token
    assert ("trip-brief", "headline_pick") == STOP_FLAGS[0]
    assert "`headline_pick`" in _contract_row(body, "Stop condition")


def test_trip_brief_records_user_written():
    assert _has(_skill("trip-brief"), "`user_written: true`")


def test_trip_brief_names_the_names_only_rerun():
    body = _skill("trip-brief")
    assert "trip-brief name invalid" in body and "trip-brief headline invalid" in body
    assert re.search(r"only .*`short_name`.*`headline`", body, re.S)


def test_kuso_reference_lists_every_device_and_its_riff_rule():
    ref = _ref("trip-brief", "kuso-headlines.md")
    for d in DEVICES:
        assert f"`{d}`" in ref, d
    for d in RIFF_DEVICES:
        assert re.search(rf"`{d}`[^\n]*riff_on", ref), d
    assert f"{HEADLINE_MAX}" in ref


# ---- destination-research / source-verify -----------------------------------

def test_destination_research_records_site_fields():
    body = _skill("destination-research")
    for token in ("`site`", "`site_local`", "`note`"):
        assert _has(body, token), token


def test_source_verify_records_site_intro_and_opens_at():
    body = _skill("source-verify")
    for token in ("`site`", "`site_local`", "`note`", "`intro`", "`intro_source`",
                  "`opens_at`", "`opens_at_source`"):
        assert _has(body, token), token


# ---- accommodation-research ---------------------------------------------------

def test_accommodation_research_records_area_label_and_site_fields():
    body = _skill("accommodation-research")
    for token in ("`area_label`", "`site`", "`note`"):
        assert _has(body, token), token


# ---- itinerary-synthesis --------------------------------------------------------

def test_synthesis_names_every_move_mode_and_none_rule():
    body = _skill("itinerary-synthesis")
    for m in MOVE_MODES:
        assert _has(body, f"`{m}`"), m
    for token in ("`mins`", "`km`", "`basis`", "`estimate_method`", "`source_url`",
                  "scripts/rederive.py::move_floor_mins"):
        assert _has(body, token), token
    assert re.search(r"`mode: none`.{0,200}(旅館|飯店|hotel)", body, re.S)


def test_synthesis_alternatives_need_verified_places():
    body = _skill("itinerary-synthesis")
    for k in ALT_KINDS:
        assert k in body
    for token in ("`alternatives`", "`applies_to`", "`poi_id`"):
        assert _has(body, token), token
    assert "Write it into the canonical `contingency` list" not in body
    assert "▸" not in body or "never" in body[body.index("▸") - 200:body.index("▸") + 200].lower()


def test_synthesis_writes_theme_and_structured_checklist():
    body = _skill("itinerary-synthesis")
    for token in ("`theme`", "`theme_refs`", "`due_is_hard`", "`opens_at`", "`origin`"):
        assert _has(body, token), token
    for k in KINDS:
        assert k in body, k


def test_prose_style_covers_the_day_theme():
    ref = _ref("itinerary-synthesis", "prose-style.md")
    assert _has(ref, "`theme`") and f"{THEME_MAX}" in ref
    assert "contingency[]" not in ref


def test_no_skill_still_instructs_trip_level_contingency():
    for p in sorted(SKILLS.iterdir()):
        body = _skill(p.name)
        assert "canonical `contingency` list" not in body, p.name


# ---- P2 final-review fixes ---------------------------------------------------

def test_advice_is_not_routed_into_alternatives():
    """I1: alternatives hold verified fallback PLACES; advice (holidays, IC card,
    laundry gaps, seasonal hazards) belongs in the checklist."""
    for skill in ("itinerary-synthesis", "seasonal-advisory"):
        assert "(or the affected stop's `alternatives`)" not in _skill(skill), skill
        assert "the affected stop's alternatives;" not in _skill(skill), skill


def test_booking_items_cover_alternatives_too():
    """I2: the gate checks opens_at on stops AND alternatives."""
    body = _skill("itinerary-synthesis")
    assert re.search(r"stop or alternative\s+POI\s+with\s+`booking\.opens_at`", body)


def test_headline_refs_are_must_do_names_only():
    """I3: refs may only name must_do entries; with no must_do write refs: []."""
    ref = _ref("trip-brief", "kuso-headlines.md")
    assert "限制條件" not in ref
    assert "`refs: []`" in ref


def test_theme_length_counts_punctuation():
    """M1 re-graded: theme_failures uses len(theme), punctuation included."""
    ref = _ref("itinerary-synthesis", "prose-style.md")
    assert re.search(rf"{THEME_MAX} 字[^\n]*標點", ref)


def test_short_name_states_its_real_maximum():
    """M2 re-graded: a multi-day stem is `YYYY-MM-DD <name> N天M夜` <= 22 chars, so
    the real maximum is 6 (5 for a trip of 10+ days)."""
    body = _skill("trip-brief")
    assert re.search(r"`short_name`.{0,600}at most 6", body, re.S)


def test_checklist_dates_are_quoted():
    """M7 re-graded: an unquoted YAML date parses as a date and fails the schema."""
    assert re.search(r"quote `due`", _skill("itinerary-synthesis"), re.I)
