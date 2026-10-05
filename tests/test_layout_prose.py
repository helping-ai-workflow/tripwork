"""v1.0 P3 — no skill or README still points at the pre-v1.0 paths."""
import re

from scripts.paths import REPORTS, artifact_names
from tests.test_skill_prose_hygiene import SKILLS, _skill

ROOT_ARTIFACT = re.compile(r"trips/<slug>/([a-z-]+\.yaml)")
# P3 review M2: generic spellings of "an artifact at the trip root"
ROOT_GENERIC = re.compile(r"trips/<slug>/(<artifact>\.yaml|\*\.yaml)")


def test_skills_name_artifacts_under_data_and_reports_under_work():
    for p in sorted(SKILLS.iterdir()):
        body = _skill(p.name)
        for name in ROOT_ARTIFACT.findall(body):
            assert name not in artifact_names() and name not in REPORTS, (p.name, name)
        assert "exports/<slug>-itinerary" not in body, p.name
        assert not ROOT_GENERIC.search(body), (p.name, ROOT_GENERIC.search(body).group(0))


def test_readme_describes_the_v1_layout():
    from tests.test_readme_freshness import README as text     # already the README's text
    assert "data/" in text and "tripwork.py migrate" in text
    assert "exports/<slug>-itinerary" not in text
