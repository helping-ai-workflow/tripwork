"""The shared full-trip fixture must be schema-valid end-to-end (via the D1 CLI)."""
import pathlib

from scripts.validate_artifact import validate_file
from tests.mech_fixtures import build_full_trip

ARTIFACTS = ["trip-brief.yaml", "advisory.yaml", "candidates.yaml",
             "verified-pois.yaml", "routing.yaml", "accommodations.yaml",
             "legs.yaml", "calendar.yaml", "seasonal.yaml", "transit.yaml",
             "cost.yaml", "itinerary.yaml"]


def test_every_fixture_artifact_validates(tmp_path):
    t, w = build_full_trip(tmp_path)
    bad = []
    for name in ARTIFACTS:
        code, msgs = validate_file(t / name)
        if code != 0:
            bad.append(f"{name}: {msgs}")
    assert not bad, "\n".join(bad)


def test_fixture_layout(tmp_path):
    t, w = build_full_trip(tmp_path)
    slug = t.name
    assert (t / "exports" / f"{slug}-itinerary.md").is_file()
    assert (t / "exports" / f"{slug}-itinerary.html").is_file()
    assert (w.parent / ".preflight-completed").is_file()
