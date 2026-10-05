"""v2.0.0 rules that live only in prose (spec §3, §5b, §5d, R2-1).

Each guard asserts one fixed key phrase. They are literals because the rule
sentences exist only in the SKILL prose -- there is no shipped constant to call
(guard rule (b)). Deleting any rule sentence turns its test red.
"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _skill(name):
    return (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("skill,phrase", [
    ("destination-research", "never ask the user to choose between places from candidates.yaml"),
    ("accommodation-research", "every candidate offered for the pick"),
    ("routing-audit", "replacement options must be verified"),
    ("using-tripwork", "including the places offered to the user to choose from"),
    ("source-verify", "keep every traveller write-up in sources"),
    ("export-artifact", "tripwork.py export"),
    ("export-gate", "never edit the rendered deliverable"),
    ("orchestrator", "never edit the rendered deliverable"),
])
def test_rule_phrase_present(skill, phrase):
    assert phrase in _skill(skill)


def test_v13_two_travellers_rule_is_gone():
    assert "count as two" not in _skill("source-verify")


@pytest.mark.parametrize("call", ["render_markdown_page(", "render_html_page(", "apply_media("])
def test_export_artifact_has_no_hand_rendering(call):
    assert call not in _skill("export-artifact")


def test_password_text():
    s = _skill("export-artifact")
    assert "or let" not in s
    assert "TRIPWORK_PUBLISH_PASSWORD=" in s and "process list" in s
    assert "CLOUDFLARE_API_TOKEN" in s


def test_travel_advisory_has_no_plugin_root_prefix_note():
    assert "prefix the" not in _skill("travel-advisory")


def test_using_tripwork_says_where_the_plugin_is():
    s = _skill("using-tripwork")
    assert "Base directory for this skill" in s and "scripts/tripwork.py" in s
