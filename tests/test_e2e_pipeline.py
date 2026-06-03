import pathlib, yaml, json
import jsonschema
from scripts.verify import classify_candidate
from scripts.distance import classify_hop
from tests.e2e_fixtures import GEO, E2E_FIX as FIX

SCHEMAS = pathlib.Path(__file__).resolve().parent.parent / "schemas"

def _load(p):
    return yaml.safe_load(open(p, encoding="utf-8"))

def test_bug1_hallucinated_location_flagged_conflicting():
    cands = {c["name_local"]: c for c in _load(FIX / "candidates.yaml")["candidates"]}
    c = cands["한방삼계탕"]
    status, note = classify_candidate(c, local_lang="ko", **GEO["한방삼계탕"])
    assert status == "conflicting"
    assert "region" in note.lower()

def test_bug2_single_source_flagged_unverified():
    cands = {c["name_local"]: c for c in _load(FIX / "candidates.yaml")["candidates"]}
    c = cands["고봉삼계탕"]
    status, note = classify_candidate(c, local_lang="ko", **GEO["고봉삼계탕"])
    assert status == "unverified"

def test_control_poi_verified():
    cands = {c["name_local"]: c for c in _load(FIX / "candidates.yaml")["candidates"]}
    c = cands["오다리집"]
    status, note = classify_candidate(c, local_lang="ko", **GEO["오다리집"])
    assert status == "verified"

def test_only_verified_reaches_itinerary():
    cands = _load(FIX / "candidates.yaml")["candidates"]
    verified = []
    for c in cands:
        status, _ = classify_candidate(c, local_lang="ko", **GEO[c["name_local"]])
        if status == "verified":
            verified.append(c["id"])
    assert verified == ["odarijip"]  # the two bugs are excluded

def test_far_hop_flagged():
    assert classify_hop(75, max_hop_mins=60) == "far"

def test_expected_verified_pois_fixture_is_schema_valid():
    schema = json.load(open(SCHEMAS / "verified-pois.schema.json"))
    jsonschema.validate(_load(FIX / "verified-pois.yaml"), schema)
