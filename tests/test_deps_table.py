"""_DEPS is DERIVED from the Stage Contract Input rows, not authored beside them."""
import glob
import re

from scripts.orchestration import (_DEPS, GATE_INPUTS, EXPORT_GATE_INPUTS,
                                    WHOLE_DOC, deps_stale, input_fingerprint)

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
INPUT_ROW = re.compile(r"^\|\s*Input\s*\|(.+)\|\s*$", re.M)

# MEASURED 2026-08-09, and this is why the pattern is not the obvious one:
# 18 skills carry a `| Input |` row, but only TWO of them write bare backticked
# basenames. The other 16 write PATHS — `trips/<slug>/verified-pois.yaml` — and a
# naive r"`([a-z-]+\.yaml)`" matches none of those, because the backtick is
# followed by `trips/`. An earlier draft used exactly that pattern, which would
# have made _declared_inputs return an EMPTY SET for 16 of 18 skills while the
# `assert m` above still passed. The equality test below would then have gone red
# in a way an implementer could "fix" by emptying _DEPS — deleting the mechanism
# instead of building it. Strip an optional leading path.
ARTIFACT = re.compile(r"`(?:[^`]*/)?([a-z-]+\.yaml)`")


def _declared_inputs(skill):
    body = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    m = INPUT_ROW.search(body)
    assert m, f"{skill} has no Stage Contract Input row"
    return set(ARTIFACT.findall(m.group(1)))


def test_gate_skill_input_row_names_every_artifact_the_cli_opens():
    """Red at HEAD: itinerary-gate's Input row under-declares what gate.py reads,
    which is exactly why rule 13's staleness anchor was wrong."""
    assert _declared_inputs("itinerary-gate") >= set(GATE_INPUTS)


def test_export_gate_skill_input_row_names_every_artifact_the_cli_opens():
    assert _declared_inputs("export-gate") >= set(EXPORT_GATE_INPUTS)


def test_deps_rows_match_the_producing_skills_input_rows():
    """The load-bearing guard: edit the table without editing the row, or the row
    without the table, and this fails."""
    owners = {"advisory.yaml": "travel-advisory", "candidates.yaml": "destination-research",
              "verified-pois.yaml": "source-verify", "routing.yaml": "routing-audit",
              "accommodations.yaml": "accommodation-research", "legs.yaml": "inter-stop-legs",
              "calendar.yaml": "calendar-check", "seasonal.yaml": "seasonal-advisory",
              "transit.yaml": "transit-detail", "cost.yaml": "cost-rollup",
              "itinerary.yaml": "itinerary-synthesis"}
    for artifact, skill in owners.items():
        assert set(_DEPS.get(artifact, {})) == _declared_inputs(skill), artifact


def test_every_skill_with_an_input_row_is_covered():
    """A new stage skill cannot be added without appearing in _DEPS."""
    known = set(_DEPS) | {"trip-brief.yaml", "gate-report.yaml", "export-gate-report.yaml"}
    for path in sorted(glob.glob(f"{SKILLS}/*/SKILL.md")):
        body = open(path, encoding="utf-8").read()
        m = INPUT_ROW.search(body)
        if not m or "yaml" not in m.group(1):
            continue
        skill = path.rsplit("/", 2)[-2]
        if skill in ("orchestrator", "using-tripwork", "export-artifact",
                     "itinerary-gate", "export-gate"):
            continue
        produced = [a for a, s in {
            "advisory.yaml": "travel-advisory", "candidates.yaml": "destination-research",
            "verified-pois.yaml": "source-verify", "routing.yaml": "routing-audit",
            "accommodations.yaml": "accommodation-research", "legs.yaml": "inter-stop-legs",
            "calendar.yaml": "calendar-check", "seasonal.yaml": "seasonal-advisory",
            "transit.yaml": "transit-detail", "cost.yaml": "cost-rollup",
            "itinerary.yaml": "itinerary-synthesis"}.items() if s == skill]
        assert produced and produced[0] in known, skill


# ---- deps_stale itself: _DEPS' structure is pinned above, but the predicate's
# runtime behaviour (fail-open, content-mismatch detection) had no direct test
# anywhere — it isn't wired into next_stage.py's rule chain yet (that's future
# work; see itinerary-synthesis's Input row note), so nothing else exercises it.

def test_deps_stale_fails_open_when_no_fingerprint_was_recorded():
    """An artifact with no input_fingerprints predates the mechanism and must
    never be called stale — this is what keeps the research tier from
    reproducing the 37/174 mtime cascade."""
    docs = {"candidates.yaml": {"candidates": []}, "trip-brief.yaml": {"destination": "A"}}
    assert deps_stale(docs.get, "candidates.yaml") == []


def test_deps_stale_detects_a_real_content_change():
    old_brief = {"destination": "A"}
    docs = {
        "candidates.yaml": {"candidates": [], "input_fingerprints": {
            "trip-brief.yaml": input_fingerprint(old_brief, WHOLE_DOC)}},
        "trip-brief.yaml": {"destination": "B"},   # changed since candidates.yaml recorded it
    }
    assert deps_stale(docs.get, "candidates.yaml") == ["trip-brief.yaml"]


def test_deps_stale_clean_when_the_recorded_fingerprint_still_matches():
    brief = {"destination": "A"}
    docs = {
        "candidates.yaml": {"candidates": [], "input_fingerprints": {
            "trip-brief.yaml": input_fingerprint(brief, WHOLE_DOC)}},
        "trip-brief.yaml": brief,
    }
    assert deps_stale(docs.get, "candidates.yaml") == []


def test_deps_stale_projection_ignores_unprojected_field_changes():
    """advisory.yaml's projection is ADVISORY_PROJECTION (airline/dates/
    destination) — a must_do-only edit to trip-brief must not show up as a
    stale upstream, mirroring rule 11's own fingerprint discipline."""
    from scripts.orchestration import ADVISORY_PROJECTION
    old_brief = {"destination": "A", "dates": {}, "airline": None, "must_do": []}
    docs = {
        "advisory.yaml": {"items": [], "input_fingerprints": {
            "trip-brief.yaml": input_fingerprint(old_brief, ADVISORY_PROJECTION)}},
        "trip-brief.yaml": {**old_brief, "must_do": ["雞肉飯"]},
    }
    assert deps_stale(docs.get, "advisory.yaml") == []
