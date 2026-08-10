"""End-to-end consumer-fixture closure for v0.33.0 (CLAUDE.md pre-ship gate, step 7).

ONE fixture trip that carries all eleven v0.33.0 exit-criterion defect
TRIGGER SHAPES at the same time, driven through BOTH real CLIs from a foreign
cwd, with one named assertion per defect. Defect 1's outcome changed under
TW-072 (v0.34.0 Task 2, Gate 2c accepted a sourced business_status as an
existence proof) and again under Task 6 (Gate 2c retired outright, subsumed
by Gate 0 — see scripts/verify.py::classify_candidate's old call site) —
poi-fallback still carries the trigger shape (cluster_fallback geocode, no
official source, no gmaps_place_id) but the fixture's pre-existing sourced
business_status clears Gate 0 directly, so it correctly verifies rather than
refuses, with no separate existence-proof gate involved at all any more. See
test_defect_01's docstring below for the full account; the mechanism it
originally proved (a cluster_fallback POI with NO proof at all must not
verify) is still covered at the unit level, now through the real entry point
(verify_poi) rather than a classify_candidate bypass.

Why both CLIs. The eleven defects do not all live at the same layer, and a
single `gate.py` run does not exercise both:

  WRITE TIME  (scripts/source_verify_run.py -> scripts/verify.py::verify_poi)
      defects 1-3. verify_poi decides a POI's `verify_status` at the moment the
      artifact is written. gate.py never re-runs it -- it consumes the
      `verify_status` already recorded in verified-pois.yaml. A closure that ran
      only gate.py and claimed all eleven close would pass while proving
      nothing about these three.

  GATE TIME   (scripts/gate.py -> rederive.py / text_hygiene.py)
      defects 4-11. These are properties of the FINISHED artifact set and are
      caught by run_gate's named checks (verdicts_match, verdicts_rederivable,
      no_ai_tone, home_legs_rendered).

The boundary is asserted in both directions, not just described:
test_layer_boundary_gate_does_not_catch_the_write_time_defects pins that
gate.py reports nothing about defect 2's POI even though it is scheduled, while
test_defect_02 shows verify_poi refuses that same POI dict read back off disk.

Both CLIs run via subprocess with an ABSOLUTE script path and cwd set outside
the repo. In-process imports would not catch a delivery-path defect: on this
very branch a task broke gate.py and export_gate.py outright by adding an
import that reached `requests`, because scripts/calendar.py shadows the stdlib
`calendar` module whenever scripts/ is on sys.path -- invisible to every
in-process test, fatal to every consumer.

The write-time run is network-free WITHOUT --offline: the per-trip geocode
cache is pre-seeded (scripts/geocode.py::resolve_place returns on a cache hit,
including a cached miss, before touching Nominatim, and
source_verify_run._rate_limited_resolve skips its sleep on a hit). --offline
could not be used here: it returns before any geocode is built, so it can
produce neither a cluster_fallback coordinate (defect 1) nor any geocode at all.
"""
import datetime
import json
import pathlib
import subprocess
import sys
import tempfile
import types

import pytest
import yaml

from scripts.distance import min_plausible_mins
from scripts.geocode_cache import cache_key
from scripts.orchestration import route_gate_failures
from scripts.rederive import MAX_HOP_MINS, hop_km
from scripts.validate_artifact import validate_file
from scripts.verify import NO_RESOLVED_NAME, verify_poi

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_VERIFY_CLI = ROOT / "scripts" / "source_verify_run.py"
GATE_CLI = ROOT / "scripts" / "gate.py"

SLUG = "2026-09-e2e-closure"
COUNTRY = "TW"
DISTRICT = "嘉義市"
LOCAL_LANG = "zh"

# Deliberately NOT the repo and NOT the trip dir: the CLIs must work from a cwd
# that has no relationship to either.
FOREIGN_CWD = tempfile.gettempdir()

EM_DASH = "—"        # U+2014, the character _AI_EM_DASH flags
HOURS_AS_OF = "2026-08-01"


# ---------------------------------------------------------------------------
# fixture trip
# ---------------------------------------------------------------------------

def _write_yaml(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")
    return path


def _sourced_status():
    """Gate 0's object form. `as_of` is computed at build time, not hard-coded:
    verify.OPERATING_MAX_AGE_DAYS rejects a signal older than 90 days, so a
    literal date would silently turn every Gate-0-clearing POI in this fixture
    into a Gate 0 refusal 90 days after this file was written -- and the whole
    module would then fail for a reason that has nothing to do with any of the
    eleven defects."""
    return {"status": "OPERATIONAL",
            "source_url": "https://places.example/api/v1/place",
            "as_of": datetime.date.today().isoformat()}


def _trip_brief():
    return {
        "slug": SLUG,
        "destination": {"country": COUNTRY, "city": "Chiayi", "local_lang": LOCAL_LANG},
        "dates": {"start": "2026-09-01", "end": "2026-09-02"},
        "members": [{"name": "A"}],
        "base": {"name": "嘉義車站", "district": DISTRICT},
        "must_do": [],
        "constraints": [],
        "preferences": {},
    }


def _candidates():
    """Five candidates. Three resolve cleanly; two carry a write-time defect.

    Defect 2 is NOT authored here -- source_verify_run structurally cannot
    produce it (`_geocode_candidate` always writes geocode_source alongside the
    coordinate). It is created below by deleting that one field from poi-legacy's
    driver-written geocode: the shape a hand-rolled consumer driver produces
    when it writes geocode data outside source_verify_run and never sets
    geocode_source. Not a hypothetical -- real consumer data has carried this
    shape -- but how many corpus POIs carry it today is not pinned in this
    fixture's docstring; it drifts as consumers re-run source-verify.
    """
    ok = _sourced_status()

    def cand(pid, name, category, status, urls):
        return {"id": pid, "name_local": name, "name_display": name,
                "category": category, "claimed_district": DISTRICT,
                "business_status": status,
                "sources": [{"url": u, "lang": "zh"} for u in urls]}

    return {"candidates": [
        cand("poi-market", "文化路夜市", "food", ok,
             ["https://guide.example/market", "https://blog.example/market"]),
        cand("poi-museum", "嘉義市立美術館", "sight", ok,
             ["https://guide.example/museum", "https://blog.example/museum"]),
        cand("poi-legacy", "檜意森活村", "sight", ok,
             ["https://guide.example/hinoki", "https://blog.example/hinoki"]),
        # DEFECT 1: no Nominatim hit for the venue (seeded as a cached miss), so
        # the driver falls back to the district centroid. Neither source is on an
        # official domain and candidates.schema.json has no gmaps_place_id, so
        # has_existence_proof() is False.
        cand("poi-fallback", "番路山產店", "food", ok,
             ["https://guide.example/shanchan", "https://blog.example/shanchan"]),
        # DEFECT 3: the legacy bare-string form. Self-attested, so Gate 0 refuses.
        cand("poi-bare", "老楊食堂", "food", "OPERATIONAL",
             ["https://guide.example/laoyang", "https://blog.example/laoyang"]),
    ]}


def _geocode_cache():
    """Pre-seeded per-trip cache: every lookup the driver makes is a hit, so the
    run reaches no network and pays no rate-limit sleep. A cached None is a HIT
    that means 'known miss' (scripts/geocode_cache.py), which is what makes
    poi-fallback take the cluster_fallback branch deterministically."""
    def hit(lat, lng, display):
        return {"lat": lat, "lng": lng, "display_name": display, "source": "nominatim"}

    return {
        cache_key(DISTRICT, None, COUNTRY): hit(23.48, 120.44, "嘉義市, 臺灣"),
        cache_key("文化路夜市", DISTRICT, COUNTRY):
            hit(23.479, 120.443, "文化路夜市, 東區, 嘉義市, 臺灣"),
        cache_key("嘉義市立美術館", DISTRICT, COUNTRY):
            hit(23.477, 120.441, "嘉義市立美術館, 西區, 嘉義市, 臺灣"),
        cache_key("檜意森活村", DISTRICT, COUNTRY):
            hit(23.484, 120.450, "檜意森活村, 東區, 嘉義市, 臺灣"),
        cache_key("番路山產店", DISTRICT, COUNTRY): None,          # defect 1
        cache_key("老楊食堂", DISTRICT, COUNTRY):
            hit(23.481, 120.442, "老楊食堂, 東區, 嘉義市, 臺灣"),
    }


# hours the source-verify SKILL records on the POI after the driver has written
# it (scripts/source_verify_run.py::_build_poi does not carry hours). Without
# them rederive_closing has no `close` to recompute against and every scheduled
# row becomes a verdicts_rederivable failure instead of the ONE verdicts_match
# mismatch defect 11 is about.
HOURS = {
    "poi-market": {"close": "22:00", "last_order": "21:30",
                   "typical_visit_mins": 60, "as_of": HOURS_AS_OF},
    # DEFECT 11's input: a 17:30 `visit` row reads last_entry, which is 17:00.
    "poi-museum": {"close": "18:00", "last_entry": "17:00",
                   "typical_visit_mins": 60, "as_of": HOURS_AS_OF},
    "poi-legacy": {"close": "21:00", "last_order": "20:30",
                   "typical_visit_mins": 60, "as_of": HOURS_AS_OF},
}


def _routing():
    """Three clusters, three hops -- one hop per provenance/omission defect.

    Every centroid is real enough for haversine_km to produce a usable distance;
    the exact floors are recomputed inside the tests rather than asserted as
    literals, so a change to _SPEED_FLOOR_KMH surfaces as a failing arithmetic
    assertion instead of a silently-wrong fixture.
    """
    return {
        "clusters": [
            {"district": DISTRICT, "pois": ["poi-market", "poi-museum", "poi-legacy"],
             "centroid": {"lat": 23.48, "lng": 120.44}},
            {"district": "民雄", "pois": [], "centroid": {"lat": 23.66, "lng": 120.44}},
            {"district": "竹崎", "pois": [], "centroid": {"lat": 23.53, "lng": 120.55}},
        ],
        "hops": [
            # DEFECT 6: an agent_estimate hop OVER the plausibility floor and
            # UNDER the cap -- the only window in which classify_hop's provenance
            # branch decides the verdict. Recorded `ok`; re-derives `unsourced`.
            {"from": DISTRICT, "to": "民雄", "mins": 45, "flag": "ok",
             "mode": "drive", "duration_source": "agent_estimate"},
            # DEFECT 7: no duration_source at all -> rederivable failure; the
            # match comparison then runs provenance-blind, so `ok` still matches.
            {"from": "民雄", "to": "竹崎", "mins": 40, "flag": "ok", "mode": "drive"},
            # DEFECT 8: no mode -> no speed floor -> not re-derivable AND not
            # compared. This is the single record that separates the two
            # `examined` counts.
            {"from": DISTRICT, "to": "竹崎", "mins": 50, "flag": "ok",
             "duration_source": "agent_estimate"},
        ],
        "warnings": [],
    }


def _legs():
    src = [{"url": "https://freeway.gov.tw/route", "official": True}]
    return {"legs": [
        {"from": "台北", "to": DISTRICT, "kind": "inter_stop", "mode": "drive",
         "duration_mins": 200, "status": "ok", "sources": src},
        # DEFECT 5: a `kind: home` leg. Its classify_leg verdict is re-derived and
        # its fare would be summed, but no itinerary row carries leg_index 1.
        {"from": DISTRICT, "to": "台北", "kind": "home", "mode": "drive",
         "duration_mins": 210, "status": "ok", "sources": src},
    ]}


def _accommodations():
    """DEFECT 4: one lodging candidate that is cluster_fallback with no existence
    proof AND no resolved_name, recorded `verified`. It closes on BOTH axes --
    the absent resolved_name on verdicts_rederivable, the wrong recorded status
    on verdicts_match."""
    return {"stops": [{
        "district": DISTRICT, "nights": 1, "chosen": "hotel-fallback",
        "candidates": [{
            "id": "hotel-fallback", "name_local": "嘉義小旅館",
            "name_display": "嘉義小旅館", "facilities": [],
            "geocode": {"lat": 23.48, "lng": 120.44,
                        "geocode_source": "cluster_fallback"},
            "sources": [{"url": "https://guide.example/hotel", "lang": "zh"},
                        {"url": "https://blog.example/hotel", "lang": "zh"}],
            "verify_status": "verified",
        }],
    }]}


def _itinerary():
    return {
        "title": "嘉義兩日",
        "checklist": ["battery: 備用鋰電池只能隨身攜帶"],
        # DEFECT 10: a contingency block. It reaches the canonical hygiene scan
        # only because gate._itinerary_text folds contingency in -- before
        # v0.33.0 this text was invisible to every scan while render_markdown_page
        # printed it verbatim. Its AI-tone hit is a bold_label, deliberately a
        # DIFFERENT kind from defect 9's em_dash so the two cannot be confused.
        "contingency": [
            {"trigger": "**雨天**：戶外行程取消", "fallback": "改去嘉義市立美術館"},
        ],
        "days": [
            {"date": "2026-09-01",
             "rows": [
                 # DEFECT 9: an em-dash in a row text.
                 {"time": "12:00", "slot": "meal", "poi_id": "poi-market",
                  "text": f"午餐{EM_DASH}先吃火雞肉飯", "closing_status": "ok"},
                 # DEFECT 11: recorded ok, but 17:30 is after last_entry 17:00.
                 {"time": "17:30", "slot": "visit", "poi_id": "poi-museum",
                  "text": "看常設展", "closing_status": "ok"},
             ],
             "lodging": "hotel-fallback"},
            {"date": "2026-09-02",
             "rows": [
                 {"time": "12:00", "slot": "meal", "poi_id": "poi-legacy",
                  "text": "午餐", "closing_status": "ok"},
             ]},
        ],
    }


def _cost():
    items = [{"category": "lodging", "label": "嘉義小旅館 1 晚", "amount": 2400},
             {"category": "transport", "label": "國道來回油資", "amount": 1600}]
    return {"currency": "TWD", "line_items": items,
            "total": sum(i["amount"] for i in items),
            "by_category": {"lodging": 2400, "transport": 1600},
            "as_of": "2026-08-01", "estimate_note": "estimate"}


def _advisory():
    return {"items": [{
        "topic": "battery", "rule": "備用鋰電池只能隨身攜帶",
        "effective_date": "2026-01-01", "risk": "restricted",
        "sources": [{"url": "https://gov.example/battery", "official": True},
                    {"url": "https://airline.example/battery", "official": False}],
    }]}


def _run_cli(cli, *args):
    """Absolute script path, foreign cwd. Never `python -m`, never cwd=repo."""
    return subprocess.run([sys.executable, str(cli), *[str(a) for a in args]],
                          cwd=FOREIGN_CWD, capture_output=True, text=True)


def _build_closure(root):
    trip = root / "trips" / SLUG
    work = root / "work" / SLUG
    _write_yaml(trip / "trip-brief.yaml", _trip_brief())
    _write_yaml(trip / "candidates.yaml", _candidates())
    cache_path = work / "geocode-cache" / "geocode.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(_geocode_cache(), ensure_ascii=False),
                          encoding="utf-8")

    # ---- layer 1: WRITE TIME -------------------------------------------------
    sv = _run_cli(SOURCE_VERIFY_CLI, trip, "--work-dir", work)
    written = yaml.safe_load((trip / "verified-pois.yaml").read_text(encoding="utf-8"))
    write_time_pois = {p["id"]: p for p in written["pois"]}

    # ---- finish the artifact the way the stage does --------------------------
    # The driver's verdicts are preserved VERBATIM (including the two refusals);
    # only the fields source_verify_run does not own are added.
    finished = yaml.safe_load(yaml.safe_dump(written))       # deep copy
    for poi in finished["pois"]:
        if poi["id"] in HOURS:
            poi["hours"] = dict(HOURS[poi["id"]])
    # DEFECT 2: drop the one field a hand-rolled driver forgets. Everything else
    # about poi-legacy -- including its `verified` status -- is what the real
    # driver just wrote, so this is a one-field differential and nothing else.
    legacy = next(p for p in finished["pois"] if p["id"] == "poi-legacy")
    legacy["geocode"].pop("geocode_source")
    _write_yaml(trip / "verified-pois.yaml", finished)

    _write_yaml(trip / "routing.yaml", _routing())
    _write_yaml(trip / "legs.yaml", _legs())
    _write_yaml(trip / "accommodations.yaml", _accommodations())
    _write_yaml(trip / "cost.yaml", _cost())
    _write_yaml(trip / "calendar.yaml", {"holidays": []})
    _write_yaml(trip / "advisory.yaml", _advisory())
    _write_yaml(trip / "itinerary.yaml", _itinerary())

    # ---- layer 2: GATE TIME --------------------------------------------------
    gate = _run_cli(GATE_CLI, trip)

    # Everything the tests assert against is re-read FROM DISK, never from the
    # in-memory dicts that built it: the deliverable is the artifact set a
    # consumer would have, not the objects this module happens to hold.
    def load(name):
        return yaml.safe_load((trip / name).read_text(encoding="utf-8"))

    report = load("gate-report.yaml")
    return types.SimpleNamespace(
        trip=trip, work=work, sv=sv, gate=gate, report=report,
        write_time_pois=write_time_pois,
        finished_pois={p["id"]: p for p in load("verified-pois.yaml")["pois"]},
        routing=load("routing.yaml"),
        itinerary=load("itinerary.yaml"),
        checks={c["name"]: c for c in report["checks"]},
        failures=report["failures"],
    )


@pytest.fixture(scope="module")
def closure(tmp_path_factory):
    return _build_closure(tmp_path_factory.mktemp("v033-closure"))


def _one(failures, marker):
    """Exactly one failure carrying `marker`; returns it. Exactly-one matters:
    a defect that produces its message twice, or whose message a second defect
    also produces, is not a defect that closed with its OWN named failure."""
    hits = [f for f in failures if marker in f]
    assert len(hits) == 1, f"expected exactly one failure containing {marker!r}, got {hits}"
    return hits[0]


# ---------------------------------------------------------------------------
# the two CLIs actually run from a foreign cwd
# ---------------------------------------------------------------------------

def test_write_time_cli_runs_from_a_foreign_cwd(closure):
    """source_verify_run.py, absolute path, cwd outside the repo. Guards the
    class-4 delivery defect: scripts/calendar.py shadows stdlib `calendar`, and
    this CLI's import chain reaches `requests` (verify -> geocode)."""
    assert closure.sv.returncode == 0, closure.sv.stderr + closure.sv.stdout
    assert "source-verify: wrote" in closure.sv.stdout
    # Proof the run reached no network: resolve_place only calls cache_put after
    # a lookup that MISSED the cache, so an unchanged cache means every lookup
    # was served locally. (A network run would also have paid 6 seconds of
    # NOMINATIM_DELAY_S, which is why this fixture cannot be allowed to drift
    # into hitting Nominatim unnoticed.)
    saved = json.loads((closure.work / "geocode-cache" / "geocode.json")
                       .read_text(encoding="utf-8"))
    assert saved == _geocode_cache()
    # write-time verdicts: 4 clean, 1 refused. poi-fallback flips to verified
    # under TW-072 (v0.34.0) — see test_defect_01's docstring below for why
    # that is the corrected outcome, not a regression of Defect 1's fix.
    assert {p: closure.write_time_pois[p]["verify_status"]
            for p in sorted(closure.write_time_pois)} == {
        "poi-bare": "unverified", "poi-fallback": "verified",
        "poi-legacy": "verified", "poi-market": "verified", "poi-museum": "verified"}


def test_gate_cli_runs_from_a_foreign_cwd_and_exits_one(closure):
    """gate.py, absolute path, cwd outside the repo. Exit 1 = gate FAIL (not 2,
    which would mean a missing/invalid artifact and would prove nothing)."""
    assert closure.gate.returncode == 1, closure.gate.stderr + closure.gate.stdout
    assert closure.report["status"] == "fail"
    assert validate_file(closure.trip / "gate-report.yaml")[0] == 0


def test_all_eleven_defects_are_present_in_the_same_trip_on_disk(closure):
    """The premise of this module: ONE trip carries all eleven at once. Asserted
    on the artifact set as written, before any question of who catches what --
    if a future edit quietly drops a defect from the fixture, the per-defect test
    would still pass (the failure it looks for would simply be gone from a
    smaller list) but this one goes red."""
    pois, itin = closure.finished_pois, closure.itinerary
    hops = {(h["from"], h["to"]): h for h in closure.routing["hops"]}
    lodging = yaml.safe_load(
        (closure.trip / "accommodations.yaml").read_text(encoding="utf-8")
    )["stops"][0]["candidates"][0]
    legs = yaml.safe_load(
        (closure.trip / "legs.yaml").read_text(encoding="utf-8"))["legs"]

    assert pois["poi-fallback"]["geocode"]["geocode_source"] == "cluster_fallback"   # 1
    assert not any(s.get("official") for s in pois["poi-fallback"]["sources"])       # 1
    assert "geocode_source" not in pois["poi-legacy"]["geocode"]                     # 2
    assert isinstance(pois["poi-bare"]["business_status"], str)                      # 3
    assert (lodging["geocode"]["geocode_source"], "resolved_name" in lodging) \
        == ("cluster_fallback", False)                                               # 4
    assert legs[1]["kind"] == "home"                                                 # 5
    assert hops[(DISTRICT, "民雄")]["duration_source"] == "agent_estimate"           # 6
    assert "duration_source" not in hops[("民雄", "竹崎")]                            # 7
    assert "mode" not in hops[(DISTRICT, "竹崎")]                                     # 8
    assert EM_DASH in itin["days"][0]["rows"][0]["text"]                             # 9
    assert itin["contingency"]                                                       # 10
    assert itin["days"][0]["rows"][1]["closing_status"] == "ok" \
        and pois["poi-museum"]["hours"]["last_entry"] == "17:00"                     # 11


def test_every_fixture_artifact_is_schema_valid(closure):
    """The fixture must be a legal trip, not a malformed one. A schema-invalid
    artifact would let a defect 'close' for the wrong reason."""
    for name in ("trip-brief.yaml", "candidates.yaml", "verified-pois.yaml",
                 "routing.yaml", "legs.yaml", "accommodations.yaml", "cost.yaml",
                 "calendar.yaml", "advisory.yaml", "itinerary.yaml",
                 "gate-report.yaml"):
        code, msgs = validate_file(closure.trip / name)
        assert code == 0, f"{name}: {msgs}"


# ---------------------------------------------------------------------------
# WRITE TIME — defects 1-3, caught by verify_poi as the artifact is written
# ---------------------------------------------------------------------------

def test_defect_01_cluster_fallback_now_verifies_via_sourced_business_status(closure):
    """Defect 1 / write time / verify.py Gate 2c — migrated for TW-072 (v0.34.0).

    ORIGINAL (v0.33.0, TW-062): the real driver produced the cluster_fallback
    coordinate (no Nominatim hit for the venue, district centroid used
    instead) with no official source and no gmaps_place_id, and Gate 2c
    refused it for lack of an existence proof independent of the coordinate.

    WHY THIS FIXTURE NOW VERIFIES, CORRECTLY: poi-fallback has always carried
    a sourced business_status (`_sourced_status()`) — every candidate in this
    module does, because that is the only way `verify_poi`'s Gate 0 can
    establish `operating=True` at all; there is no other route through the
    real CLI. TW-072 adds that SAME sourced business_status as Gate 2c's third
    accepted proof, because a dated, sourced statement that the venue is
    operating is independent evidence that it exists, which is what Gate 2c
    claims to test. So `operating_from_status` now backs both Gate 0 and Gate
    2c off the identical field — a POI cannot clear Gate 0 through the real
    driver without simultaneously supplying Gate 2c's proof. The specific
    "no official source, no place_id" combination that stayed unverified in
    v0.33.0 is exactly the keyless asymmetry TW-072 closes, and this fixture
    demonstrating that flip IS the corrected behaviour, not a Gate 2c
    regression.

    UPDATED for v0.34.0 Task 6: TW-072's finding above — that Gate 0 and
    Gate 2c could no longer disagree — is exactly why Gate 2c is RETIRED
    outright in Task 6, not left as a dead branch. There is no live Gate 2c
    left to "still refuse" a proof-less POI; that safety property now lives
    entirely at Gate 0 (a bare-string or absent business_status refuses
    through the real driver, full stop). The unit-level regression for a
    genuinely proof-less cluster_fallback POI moved with it: tests/
    test_verify.py::test_cluster_fallback_with_a_bare_string_business_
    status_is_still_unverified pins the SAME claim through the real entry
    point (verify_poi), with no classify_candidate bypass needed any more —
    there is no retired-branch bypass left to demonstrate.
    """
    poi = closure.write_time_pois["poi-fallback"]
    assert poi["geocode"]["geocode_source"] == "cluster_fallback"
    assert not any(s.get("official") for s in poi["sources"])
    assert poi["verify_status"] == "verified"
    assert "status_reason" not in poi
    # and it re-verifies when re-checked from the FINISHED artifact on disk.
    _, status, note = verify_poi(closure.finished_pois["poi-fallback"],
                                 geocoded=True, in_claimed_region=True,
                                 local_lang=LOCAL_LANG,
                                 resolved_name=NO_RESOLVED_NAME)
    assert (status, note) == ("verified", "")


def test_defect_02_geocode_with_no_geocode_source(closure):
    """Defect 2 / write time / verify.py's GEOCODE_SOURCE_MISSING sentinel.

    One-field differential against the driver's own output: poi-legacy is
    identical in every respect except that geocode_source was deleted, which
    is what a hand-rolled consumer driver produces (see _candidates' own
    docstring for why this is a real shape, not a contrived one)."""
    poi = closure.finished_pois["poi-legacy"]
    assert "geocode_source" not in poi["geocode"]
    _, status, note = verify_poi(poi, geocoded=True, in_claimed_region=True,
                                 local_lang=LOCAL_LANG,
                                 resolved_name="檜意森活村, 東區, 嘉義市, 臺灣")
    assert status == "unverified"
    assert "geocode_source not recorded" in note

    # Differential: restore the one field the driver wrote and the same POI is
    # verified. Without this the assertion above could be satisfied by any
    # unrelated gate refusing first.
    restored = dict(poi, geocode=dict(poi["geocode"], geocode_source="nominatim"))
    _, status2, _note2 = verify_poi(restored, geocoded=True, in_claimed_region=True,
                                    local_lang=LOCAL_LANG,
                                    resolved_name="檜意森活村, 東區, 嘉義市, 臺灣")
    assert status2 == "verified"


def test_defect_03_bare_string_business_status(closure):
    """Defect 3 / write time / verify.py Gate 0 via operating_from_status."""
    poi = closure.write_time_pois["poi-bare"]
    assert poi["business_status"] == "OPERATIONAL"        # the bare string survives
    assert poi["verify_status"] == "unverified"
    assert "business_status is self-attested" in poi["status_reason"]
    _, status, note = verify_poi(closure.finished_pois["poi-bare"],
                                 geocoded=True, in_claimed_region=True,
                                 local_lang=LOCAL_LANG,
                                 resolved_name="老楊食堂, 東區, 嘉義市, 臺灣")
    assert (status, "business_status is self-attested" in note) == ("unverified", True)


# ---------------------------------------------------------------------------
# GATE TIME — defects 4-11, caught by gate.py over the finished artifact
# ---------------------------------------------------------------------------

def test_defect_04_lodging_cluster_fallback_no_proof_no_resolved_name(closure):
    """Defect 4 / gate time / rederive_lodging, on BOTH axes.

    verdicts_rederivable names the absent resolved_name; verdicts_rule_current
    (not verdicts_match -- migrated for the Gate 2c retirement, 2026-08-09 user
    ruling, v0.34.0 Task 6) names the recorded `verified` produced before
    business_status existed.

    Before Task 6, hotel-fallback's cluster_fallback geocode with no existence
    proof reached classify_candidate's Gate 2c directly and re-derived
    'unverified' there -- a verdicts_match mismatch. Gate 2c is retired now:
    Step 4 threads a real Gate 0 into rederive_lodging, and this fixture
    (deliberately unchanged since v0.33.0 -- it still carries no
    business_status at all) is caught one gate earlier, before Gate 2c would
    ever have run on it. It lands in `superseded`, not `mismatches` -- the
    same bucket a POI in the identical shape (a bare or absent business_status)
    already used on the POI axis (rederive_pois).

    The marker is scoped to "candidate 'hotel-fallback':", not the bare
    "recorded verify_status" the pre-v0.34.0 version of this test used:
    TW-070's POI axis now ALSO produces a "recorded verify_status ... but
    verify_poi re-derives ..." message for poi-legacy (a different defect,
    see test_layer_boundary_gate_does_not_catch_the_write_time_defects), and
    the bare marker would match both, breaking _one()'s exactly-one
    guarantee for a reason that has nothing to do with lodging."""
    missing = _one(closure.failures, "no resolved_name")
    assert "candidate 'hotel-fallback'" in missing
    assert "Gate 2b (name match) is not re-derivable" in missing

    superseded = _one(closure.failures, "candidate 'hotel-fallback': recorded verify_status")
    assert "was produced under superseded rules" in superseded
    assert "business_status is not the sourced" in superseded


def test_defect_05_home_leg_never_rendered(closure):
    """Defect 5 / gate time / gate.py::_home_legs_rendered_failures."""
    f = _one(closure.failures, "home leg")
    assert f.startswith("home leg 1 (嘉義市->台北)")
    assert "has no move row" in f
    assert closure.checks["home_legs_rendered"]["passed"] is False
    # the failure must NOT route to inter-stop-legs (the 'legs[' marker trap)
    assert route_gate_failures([f]) == "tripwork:itinerary-synthesis"


def test_defect_06_agent_estimate_hop_over_the_plausibility_floor(closure):
    """Defect 6 / gate time / rederive_hops -> verdicts_match.

    The hop clears the floor and the cap, so classify_hop's provenance branch is
    the only thing left to decide the verdict: an agent_estimate is `unsourced`.
    The floor arithmetic is recomputed here rather than asserted as a literal."""
    routing = closure.routing
    hop = routing["hops"][0]
    km = hop_km(routing, hop)
    floor = min_plausible_mins(km, hop["mode"])
    assert floor < hop["mins"] <= MAX_HOP_MINS, (
        f"fixture no longer isolates the provenance branch: km={km}, floor={floor}")

    f = _one(closure.failures, "recorded flag 'ok' but classify_hop")
    assert f.startswith("routing hop 嘉義市->民雄")
    assert "re-derives 'unsourced'" in f
    assert closure.checks["verdicts_match"]["passed"] is False


def test_defect_07_hop_with_no_duration_source(closure):
    """Defect 7 / gate time / rederive_hops -> verdicts_rederivable.

    Provenance-blind on the match axis by design, so this hop contributes a
    rederivable failure and NO match failure."""
    f = _one(closure.failures, "no duration_source")
    assert f.startswith("routing hop 民雄->竹崎")
    assert "provenance branch is not re-derivable" in f
    # "re-derives", not "classify_hop": the rederivable message above names
    # classify_hop too, so grepping for that would make this vacuous.
    assert not [x for x in closure.failures if "民雄->竹崎" in x and "re-derives" in x]
    assert closure.checks["verdicts_rederivable"]["passed"] is False


def test_defect_08_hop_with_no_mode(closure):
    """Defect 8 / gate time / rederive_hops -> verdicts_rederivable.

    Also the ONE record that is found but never compared, which is what makes the
    two examined counts differ (see the examined-count test)."""
    f = _one(closure.failures, "no mode")
    assert f.startswith("routing hop 嘉義市->竹崎")
    assert "min_plausible_mins has no speed floor to apply" in f


def test_defect_09_em_dash_in_a_row_text(closure):
    """Defect 9 / gate time / text_hygiene.ai_tone_failures -> no_ai_tone."""
    f = _one(closure.failures, "AI-tone em_dash")
    assert EM_DASH in f
    assert "先吃火雞肉飯" in f          # the snippet comes from the row text
    assert closure.checks["no_ai_tone"]["passed"] is False


def test_defect_10_contingency_block_reaches_the_hygiene_scan(closure):
    """Defect 10 / gate time / gate._itinerary_text folds contingency in.

    The proof that contingency is scanned is that its text -- and only its text
    -- produces this failure: no row text, label, title or checklist item in the
    fixture carries a bold label."""
    f = _one(closure.failures, "AI-tone bold_label")
    assert "雨天" in f
    itin = closure.itinerary
    assert "**雨天**：" in itin["contingency"][0]["trigger"]
    scanned = [r["text"] for d in itin["days"] for r in d["rows"]]
    scanned += itin["checklist"] + [itin["title"]]
    assert not [s for s in scanned if "**" in s]


def test_defect_11_closing_status_disagrees_with_its_pois_hours(closure):
    """Defect 11 / gate time / rederive_closing -> verdicts_match."""
    f = _one(closure.failures, "recorded closing_status")
    assert f.startswith("itinerary day 2026-09-01 row 1 (poi 'poi-museum' @ 17:30)")
    assert "'ok' but hours.closing_status re-derives 'after_last_call'" in f
    assert "after last order/entry 17:00" in f


# ---------------------------------------------------------------------------
# cross-defect properties
# ---------------------------------------------------------------------------

def test_the_two_rederivation_axes_report_different_examined_counts(closure):
    """rederivable.examined counts every verdict-bearing record FOUND; match
    .examined counts only the subset with complete enough inputs to recompute.
    A fixture where they agree cannot demonstrate the axes are distinct.

    15 found  = 2 legs + 3 hops + 1 cost + 3 timed POI rows + 1 lodging candidate
                + 5 verified-pois.yaml records (v0.34.0, TW-070: rederive_pois
                examines the WHOLE pois list -- poi-market, poi-museum,
                poi-legacy, poi-fallback, poi-bare -- not only the three rows
                the itinerary schedules).
    13 compared (was 14 pre-Task-6) = the same minus TWO records that never
                reach a comparison: defect 8's mode-less hop (rederive_hops
                abandons it before out.compared, unchanged) AND hotel-fallback
                (v0.34.0 Task 6: no business_status at all routes it to
                `superseded` before rederive_lodging ever calls
                classify_candidate -- there is no `operating` value to compare
                with). All 5 POI-axis records ARE still compared (including
                poi-legacy's mismatch -- a wrong verdict is still a completed
                comparison, only a genuinely absent input or a superseded
                record skips it)."""
    rederivable = closure.checks["verdicts_rederivable"]["examined"]
    match = closure.checks["verdicts_match"]["examined"]
    assert (rederivable, match) == (15, 13)
    assert rederivable - match == 2


def test_layer_boundary_gate_does_not_catch_the_write_time_defects(closure):
    """Retired-and-rewritten by v0.34.0 (TW-070), exactly as this test's own
    prior version instructed: 'If a future release teaches the gate to
    re-verify POIs, this test goes red and should be rewritten, not deleted.'
    rederive_pois now re-examines the WHOLE verified-pois.yaml list (not only
    scheduled rows), so poi-legacy's defect-2 gap -- recorded 'verified' with
    geocode_source absent -- is now ALSO caught at gate time, closing the
    boundary this test used to pin as permanently open.

    Defect 2 still closes FIRST at write time (test_defect_02): a fresh
    source-verify run over this exact shape refuses the POI before 'verified'
    is ever recorded. What TW-070 adds is the second line of defense this
    fixture's own scenario needs -- a driver wrote 'verified', then a field
    was deleted by hand (a corpus-measured shape, not a contrived one -- see
    _candidates' own docstring) -- and that hand-edited artifact no
    longer slips past the gate silently. It surfaces as exactly one POI-axis
    failure and routes to the SAME destination write-time refusal would have:
    tripwork:source-verify (scripts/orchestration.py's `pois[` marker)."""
    from scripts.orchestration import route_gate_failures

    assert closure.finished_pois["poi-legacy"]["verify_status"] == "verified"
    assert "poi-legacy" in {r["poi_id"] for d in closure.itinerary["days"]
                            for r in d["rows"] if r.get("poi_id")}
    poi_legacy_failures = [f for f in closure.failures if "poi-legacy" in f]
    assert len(poi_legacy_failures) == 1
    assert poi_legacy_failures[0].startswith("pois['poi-legacy']")
    assert route_gate_failures(poi_legacy_failures) == "tripwork:source-verify"
    # the failure names the record, never the missing field by name -- the
    # SAME discipline test_defect_02's write-time note already follows.
    assert not [f for f in closure.failures if "geocode_source" in f]
    # and the two write-time-refused POIs are simply absent from the plan, so
    # the gate has no reason to mention them either.
    assert not [f for f in closure.failures
                if "poi-fallback" in f or "poi-bare" in f]


def test_no_unattributed_gate_failure(closure):
    """Every gate failure belongs to exactly one of the eight gate-time defects,
    or to the new gate-time echo of write-time defect 2 (v0.34.0, TW-070 --
    see test_layer_boundary_gate_does_not_catch_the_write_time_defects).
    Without this, a fixture could close all eleven while also emitting
    failures nobody looked at -- and a later regression would hide inside
    that noise."""
    markers = {
        "defect 2 (gate-time echo, TW-070)": "pois['poi-legacy']",
        "defect 4 (rederivable)": "no resolved_name",
        "defect 4 (match)": "candidate 'hotel-fallback': recorded verify_status",
        "defect 5": "home leg",
        "defect 6": "recorded flag 'ok' but classify_hop",
        "defect 7": "no duration_source",
        "defect 8": "no mode",
        "defect 9": "AI-tone em_dash",
        "defect 10": "AI-tone bold_label",
        "defect 11": "recorded closing_status",
    }
    attributed = {f for m in markers.values() for f in closure.failures if m in f}
    assert set(closure.failures) == attributed, (
        f"unattributed gate failures: {set(closure.failures) - attributed}")
    assert len(closure.failures) == len(markers)


def test_failing_checks_are_exactly_the_v033_mechanisms_plus_rule_current(closure):
    """The eight gate-time defects must land on their OWN checks and leave every
    legacy check green -- otherwise the fixture is failing the gate for reasons
    other than the eleven.

    Five names, not the original four (renamed from
    test_failing_checks_are_exactly_the_four_v033_mechanisms): v0.34.0's Task 6
    threads a real Gate 0 into rederive_lodging, and hotel-fallback (defect 4's
    fixture, deliberately unchanged since v0.33.0 -- it carries no
    business_status at all) now lands in `superseded` rather than
    `mismatches`, so verdicts_rule_current joins the failing list alongside
    the original four. This is not a new, unattributed failure -- defect 4
    already accounted for hotel-fallback's one gate failure (see
    test_defect_04_lodging_cluster_fallback_no_proof_no_resolved_name and
    test_no_unattributed_gate_failure below); only the check NAME it fails
    under moved, from verdicts_match to verdicts_rule_current."""
    failed = sorted(c["name"] for c in closure.report["checks"] if not c["passed"])
    assert failed == ["home_legs_rendered", "no_ai_tone",
                      "verdicts_match", "verdicts_rederivable",
                      "verdicts_rule_current"]
