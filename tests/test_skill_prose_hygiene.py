"""Skill prose must state the CURRENT rule, and must agree with the code it describes.

Two defect families, both found by the 2026-09-25 prompt audit:

1. Cross-reference drift — a skill describes another stage's behaviour and the
   description went stale while the code moved on:
   - inter-stop-legs said the precise rail-pass break-even was "deferred to B3",
     while cost-rollup already computes it (`scripts/cost.py::pass_break_even`).
   - export-gate's Stage Contract said every `status: fail` re-renders, while its
     own Output section and `scripts/next_stage.py` rule 15 stop and ask on a
     `retryable: false` fail.
   Both guards below obtain the truth by CALLING the shipped code (the function
   name from the imported function; the rule-15 outcome from `next_stage.py`
   run over a fixture), not from a hand-kept copy.

2. Release history inside the prompt — version stamps ("v0.34.0"), "no longer" /
   "any more" narration, and bare incident tags ("(P7)", "TW-069") tell the
   agent how the rule came to be instead of what the rule is. The CHANGELOG
   carries that history. `D7` is NOT a tag: it is the name of an outcome
   ("a Nominatim miss degrades to unverified") that several skills use as a term.
"""
import pathlib
import re
import subprocess
import sys

import pytest
import yaml

from scripts.cost import pass_break_even
from tests.mech_fixtures import write_artifact
from tests.test_next_stage import _bump, _full, _next

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"


def _skill(name):
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def _contract_row(text, field):
    m = re.search(rf"^\|\s*{re.escape(field)}\s*\|(.+)\|\s*$", text, re.M)
    assert m, f"Stage Contract has no {field!r} row"
    return m.group(1)


# ---- family 1: cross-reference drift -------------------------------------

def test_inter_stop_legs_points_at_the_shipped_break_even_owner():
    text = _skill("inter-stop-legs")
    # The owner is named by the function itself, so a rename breaks this guard.
    assert pass_break_even.__name__ in text, (
        "inter-stop-legs must name cost-rollup's pass_break_even as the owner of "
        "the precise rail-pass calculation")
    assert pass_break_even.__name__ in _skill("cost-rollup")
    assert not re.search(r"break-even[^|\n]*\b(deferred|is B\d)", text), (
        "inter-stop-legs still says the break-even is deferred to a future phase")


def _render_defect(t):
    """A naked '$' in the md deliverable: a defect re-rendering fixes."""
    md = t / "exports" / f"{t.name}-itinerary.md"
    md.write_text(md.read_text(encoding="utf-8") + "\n門票 $120\n", encoding="utf-8")


def _data_defect(t):
    """A rendered photo with no attribution: a defect only the data can fix."""
    write_artifact(t / "verified-pois-media.yaml", {"media": {"poi-1": {
        "photo": "https://img.example/goryokaku.jpg", "photo_source": "wiki"}}})
    html = t / "exports" / f"{t.name}-itinerary.html"
    html.write_text(html.read_text(encoding="utf-8")
                    + '<img src="https://img.example/goryokaku.jpg">', encoding="utf-8")


@pytest.mark.parametrize("defect", [_render_defect, _data_defect],
                         ids=["render-defect", "data-defect"])
def test_export_gate_stop_condition_matches_rule_15(tmp_path, defect):
    # Both the report and the routing decision come from the shipped CLIs:
    # scripts/export_gate.py writes export-gate-report.yaml, scripts/next_stage.py
    # (rule 15) decides what happens next. The SKILL row must say the same.
    t, w = _full(tmp_path)
    defect(t)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "export_gate.py"), str(t)],
                       capture_output=True, text=True)
    assert r.returncode == 1, r.stdout + r.stderr
    report = yaml.safe_load((t / "export-gate-report.yaml").read_text(encoding="utf-8"))
    assert report["status"] == "fail"
    outcome = _next(t, w)["next"]

    row = _contract_row(_skill("export-gate"), "Stop condition")
    key = f"retryable: {str(report['retryable']).lower()}"
    assert key in row, f"export-gate Stop condition must cover `{key}`: {row!r}"
    clause = row[row.index(key):].split(";")[0]
    if outcome == "stop-and-ask":
        assert "stop" in clause and "ask" in clause, (outcome, clause)
    else:
        assert outcome.split(":", 1)[1] in clause, (outcome, clause)


def test_the_two_defects_cover_both_retryable_values(tmp_path):
    """Without this, a fixture drift that made both defects retryable would leave
    the `retryable: false` clause of the row unguarded."""
    seen = set()
    for i, defect in enumerate((_render_defect, _data_defect)):
        t, _ = _full(tmp_path / str(i))
        defect(t)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "export_gate.py"), str(t)],
                       capture_output=True, text=True)
        seen.add(yaml.safe_load(
            (t / "export-gate-report.yaml").read_text(encoding="utf-8"))["retryable"])
    assert seen == {True, False}


# ---- family 2: release history in prompt text ----------------------------

PROMPT_FILES = sorted(SKILLS.rglob("*.md")) + [ROOT / "hooks" / "session-start"]

HISTORY = [
    ("version stamp", re.compile(r"\bv?\d+\.\d+\.\d+\b")),
    ("'no longer' narration", re.compile(r"\bno longer\b", re.I)),
    ("'any more' narration", re.compile(r"\bany more\b", re.I)),
    ("'legacy pre-' narration", re.compile(r"\blegacy pre-", re.I)),
    ("incident tag", re.compile(r"\b(?:TW-\d+|[PFIC]\d+(?:-twin)?)\b")),
]


def test_prompt_files_exist():
    assert len(PROMPT_FILES) > len(list(SKILLS.iterdir())), PROMPT_FILES


@pytest.mark.parametrize("path", PROMPT_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_prompt_text_states_the_rule_not_its_history(path):
    hits = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for label, pat in HISTORY:
            for m in pat.finditer(line):
                hits.append(f"{path.relative_to(ROOT)}:{n}: {label} {m.group(0)!r}")
    assert not hits, "\n".join(hits)
