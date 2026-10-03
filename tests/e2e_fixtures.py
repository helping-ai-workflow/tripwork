"""Shared e2e-trip fixture truth for the bug-attack tests.

Single source of truth for the e2e fixture directory and the mocked geocode
results, consumed by test_e2e_pipeline.py and test_e2e_must_do.py. Keeping
these here prevents the two test modules from drifting out of sync when the
e2e candidates fixture changes.
"""
import pathlib

E2E_FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "e2e-trip"

# Geocode results the source-verify skill would obtain, mocked here as known
# truth for the three planted e2e candidates.
GEO = {
    "한방삼계탕": {"geocoded": True, "in_claimed_region": False},   # 강남, not 잠실 (hallucination)
    "고봉삼계탕": {"geocoded": True, "in_claimed_region": True},
    "오다리집":   {"geocoded": True, "in_claimed_region": True},
}
