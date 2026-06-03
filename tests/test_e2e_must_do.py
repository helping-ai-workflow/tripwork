import pathlib, yaml
import pytest
from scripts.verify import classify_candidate

FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "e2e-trip"

GEO = {
    "한방삼계탕": {"geocoded": True, "in_claimed_region": False},
    "고봉삼계탕": {"geocoded": True, "in_claimed_region": True},
    "오다리집":   {"geocoded": True, "in_claimed_region": True},
}

def _classify_all():
    cands = yaml.safe_load(open(FIX / "candidates.yaml", encoding="utf-8"))["candidates"]
    out = {}
    for c in cands:
        key = c["name_local"]
        if key not in GEO:
            pytest.fail(f"no GEO entry for candidate '{key}'")
        status, _ = classify_candidate(c, local_lang="ko", **GEO[key])
        out[c["id"]] = status
    return out

def unmet_must_dos(must_do_ids, statuses):
    """Return must_do POI ids that did not reach 'verified' — must be surfaced, not dropped."""
    return [pid for pid in must_do_ids if statuses.get(pid) != "verified"]

def test_must_do_failure_is_surfaced_not_dropped():
    statuses = _classify_all()
    # user marked the (hallucinated) hanbang-samgyetang as a must-do
    must_do = ["hanbang-samgyetang", "odarijip"]
    unmet = unmet_must_dos(must_do, statuses)
    assert "hanbang-samgyetang" in unmet      # surfaced
    assert "odarijip" not in unmet            # verified must-do is fine

def test_all_verified_must_dos_yield_empty_unmet():
    statuses = _classify_all()
    assert unmet_must_dos(["odarijip"], statuses) == []
