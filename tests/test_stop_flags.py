"""One vocabulary for every stop-on-confirmation, shared by the orchestrator, the
stages and the stage-state read-back.

Before this, three hand-kept lists described the same halts and had drifted: the
orchestrator's Stop-on-Confirmation paragraph (11 kinds), using-tripwork's iron-rule
row (5), and each stage's own Stage Contract row — five stage halts were in no
orchestrator list at all. And because `stage-state.yaml` flags were free text, the
consumer corpus recorded the same halt as `unfilled_overnight_stop` in one trip and
`unfilled_stop_pick` in another, so the read-back (which matches on
(stage, flag, subject)) cannot recognise a decision already made.

`scripts/orchestration.py::STOP_FLAGS` is now the single list; every guard below
reads it rather than keeping a copy.
"""
import re

import pytest

from tests.test_skill_prose_hygiene import SKILLS, _contract_row, _skill

# Stages that ask the user something but are NOT pipeline halts the orchestrator
# records. A literal because it is a judgement about each skill, not pipeline
# state any shipped constant holds:
# - trip-brief: its questions ARE the stage (the brief is being written); nothing
#   downstream exists yet to halt.
# - workspace-shape-preflight: runs before the orchestrator (rule 0) and writes
#   no trip state.
# - orchestrator: its Stop condition relays the table's halts; it has none of its own.
NON_PIPELINE_ASKS = {"trip-brief", "workspace-shape-preflight", "orchestrator"}

TABLE_ROW = re.compile(r"^\|\s*`(tripwork:[a-z-]+)`\s*\|\s*`([a-z_]+)`\s*\|.+\|\s*$", re.M)


def _stop_flags():
    from scripts.orchestration import STOP_FLAGS
    return STOP_FLAGS


def _orchestrator_table():
    body = _skill("orchestrator")
    start = body.index("## Stop-on-Confirmation")
    end = body.index("\n## ", start + 1)
    rows = TABLE_ROW.findall(body[start:end])
    assert rows, "Stop-on-Confirmation must be a `| stage | flag | halt when |` table"
    return [(stage.split(":", 1)[1], flag) for stage, flag in rows]


def test_stop_flags_are_well_formed():
    flags = _stop_flags()
    assert len(set(flags)) == len(flags), "duplicate (stage, flag)"
    stages = {p.name for p in SKILLS.iterdir()}
    for stage, flag in flags:
        assert stage in stages, stage
        assert re.fullmatch(r"[a-z]+(_[a-z]+)*", flag), flag


def test_orchestrator_table_is_exactly_stop_flags():
    assert _orchestrator_table() == list(_stop_flags())


@pytest.mark.parametrize("stage", sorted(p.name for p in SKILLS.iterdir()))
def test_each_stage_stop_condition_names_its_flags(stage):
    own = [f for s, f in _stop_flags() if s == stage]
    if not own:
        return
    row = _contract_row(_skill(stage), "Stop condition")
    named = set(re.findall(r"`([a-z_]+)`", row))
    missing = [f for f in own if f not in named]
    assert not missing, f"{stage} Stop condition does not name {missing}: {row!r}"


def test_every_asking_stage_is_registered():
    registered = {s for s, _ in _stop_flags()}
    for skill in sorted(p.name for p in SKILLS.iterdir()):
        text = _skill(skill)
        if "| Stop condition |" not in text:
            continue
        row = _contract_row(text, "Stop condition")
        if re.search(r"\bask\b", row) and skill not in NON_PIPELINE_ASKS:
            assert skill in registered, (
                f"{skill} halts to ask the user but has no STOP_FLAGS entry: {row!r}")


def test_using_tripwork_points_at_the_table_instead_of_copying_it():
    text = _skill("using-tripwork")
    assert "Stop-on-Confirmation" in text
    copied = [f for _, f in _stop_flags() if f"`{f}`" in text]
    assert not copied, f"using-tripwork keeps its own copy of {copied}"


def test_readback_requires_the_table_flag_verbatim():
    body = _skill("orchestrator")
    section = body[body.index("**Read-back before re-asking.**"):]
    section = section[:section.index("\n## ")]
    assert "verbatim" in section and "flag" in section


def test_rule_15_stop_and_ask_is_a_registered_flag(tmp_path):
    """next_stage.py emits `stop-and-ask` itself for rule 15; that halt must have a
    flag to record it under like every other."""
    from tests.test_skill_prose_hygiene import _data_defect, _next, _full
    import subprocess, sys
    from tests.test_skill_prose_hygiene import ROOT
    t, w = _full(tmp_path)
    _data_defect(t)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "export_gate.py"), str(t)],
                   capture_output=True, text=True)
    assert _next(t, w)["next"] == "stop-and-ask"
    assert any(s == "export-gate" for s, _ in _stop_flags())
