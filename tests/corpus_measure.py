"""語料量測的唯一來源 —— 量測端與斷言端共用這一份，不留第二份實作可漂移。

TW-074：在這個模組之前，每個數字以 literal 形式住在測試裡，所以一次**合法的**語料變動
（消費端拿某個 release 出貨的機制把自己的資料修對）會讓 8 個 guard 轉紅，而 plugin 一行
缺陷都沒有。那些 literal 描述的是語料在某一天的長相，不是 plugin 的行為。

CONDITIONAL：沒有消費端語料時整組 skip（見 mech_fixtures.CORPUS）。這些 guard 不在 CI 跑。
"""
import collections
import copy
import datetime

from scripts.gate import poi_pool, run_gate
from scripts.orchestration import route_gate_failures
from tests.mech_fixtures import CORPUS, CORPUS_TRIPS, load_trip

# One marker per failure class the four clean trips actually produce. Asserting
# the classes PARTITION the failures (no leftovers) is what makes the per-trip
# counts below meaningful: a new class cannot hide inside an unchecked
# remainder.
CLASSES = (
    ("hop_no_duration_source", "no duration_source"),
    ("poi_no_hours", "carries neither hours.close"),
    ("row_no_closing_status", "no recorded closing_status"),
    ("lodging_no_resolved_name", "no resolved_name"),
    ("lodging_no_geocode_source", "no geocode.geocode_source"),
    # Narrowed from the bare "recorded verify_status" (v0.34.0, TW-070): the
    # POI/lodging superseded messages ALSO contain that phrase ("...: recorded
    # verify_status 'verified' was produced under superseded rules ..."), so
    # the bare marker would double-match every superseded record and break
    # _classify's exactly-one invariant. "but classify_candidate re-derives"
    # is unique to rederive_lodging's own MISMATCH message (as opposed to its
    # superseded message, which never reaches classify_candidate at all).
    #
    # v0.34.0 Task 6 retired this class from the corpus entirely: it fires
    # only when a lodging candidate reaches classify_candidate AND its
    # recorded verdict does not match, which now requires a sourced
    # business_status to reach classify_candidate in the first place. None of
    # the 18 real lodging candidates carry one, so all 18 (including the one
    # that used to land here, 2026-07-sun-moon-lake's d2-6) now land in
    # lodging_verdict_superseded below instead. The marker is kept, unfired,
    # as a live regression guard: a future corpus update that adds a sourced-
    # but-wrong business_status would need this class again, and a silently
    # absent marker would let _classify swallow it into "unattributed".
    ("lodging_verify_status_mismatch", "but classify_candidate re-derives"),
    # POI axis (TW-070) and lodging axis (v0.34.0 Task 6) each get their own
    # marker, discriminated by each message's own tail -- both share "was
    # produced under superseded rules" as a common substring (see above), but
    # POI's ends "...re-run source-verify for this POI" and lodging's ends
    # "...re-run accommodation-research for this candidate". Every corpus hit
    # on EITHER axis today is the SAME subtype -- a bare-string or absent
    # business_status, superseded by TW-063's/TW-072's sourced object form
    # (105 of 127 POI records, 18 of 18 lodging candidates, across these four
    # trips; see scripts/rederive.py::rederive_pois / rederive_lodging's
    # docstrings). No corpus hit today is the 'missing' or 'mismatch'
    # subtype on either axis, so this module carries no marker for them -- if
    # a future corpus update produces one, _classify's assert surfaces it as
    # an unattributed failure instead of silently absorbing it.
    ("poi_verdict_superseded", "re-run source-verify for this POI"),
    ("lodging_verdict_superseded", "re-run accommodation-research for this candidate"),
    ("ai_tone", "AI-tone "),
)


def gate(a):
    b = a["brief"]
    return run_gate(a["pois"]["pois"], a["itinerary"],
                    accommodations=a["accommodations"],
                    facility_needs=b.get("facility_needs"), calendar=a["calendar"],
                    advisory=a["advisory"], must_do=b.get("must_do"), legs=a["legs"],
                    routing=a["routing"], cost=a["cost"], trip_brief=b)


def classify(failures):
    seen = collections.Counter()
    for f in failures:
        hits = [name for name, marker in CLASSES if marker in f]
        assert len(hits) == 1, f"failure matches {hits} classes, expected 1: {f}"
        seen[hits[0]] += 1
    return dict(seen)


# --------------------------------------------------------------------------
# rule 13.5 drain: route, grant the routed stage its BEST possible fix, re-gate.
# --------------------------------------------------------------------------

def _fix_source_verify(a):
    """Records the closing times it left absent (SKILL.md's "go back and find
    the hours"), and re-verifies every POI (TW-070, v0.34.0): a sourced
    business_status + geocode_source + resolved_name -- what a real
    source-verify re-run records -- then RECOMPUTES verify_status from those
    inputs and overwrites the recorded value, the same "recompute and
    overwrite" pattern _fix_legs/_fix_routing already use for their own
    mismatch classes.

    Scoped to every POI, not just the ones this round's report flagged
    'superseded': a POI recorded 'unverified'/'conflicting' for the CORRECT
    reason (Gate 0 never established, since business_status was absent) would
    otherwise still match on this round and only surface its real verdict
    after business_status is sourced -- exactly what a real re-run does in one
    visit, not one field at a time. as_of is computed at CALL time, never a
    literal (OPERATING_MAX_AGE_DAYS is 90) -- and `today=` is threaded through
    the SAME value into `verify_poi`, so Gate 0's own recency check reads the
    identical era as the `as_of` just written, not wall-clock underneath a
    synthetic date. (Gate 2c, which used to read this same anchor via
    classify_candidate, is retired as of v0.34.0 Task 6 -- there is no second
    gate left for `today` to reach.)
    """
    from scripts.verify import verify_poi
    today = datetime.date.today().isoformat()
    for p in a["pois"]["pois"]:
        h = p.setdefault("hours", {})
        if not h.get("close") and not h.get("no_fixed_close"):
            h["close"], h["as_of"] = "18:00", "2026-08-01"
        if not isinstance(p.get("business_status"), dict):
            p["business_status"] = {"status": "OPERATIONAL",
                                    "source_url": "https://places.example/v1/place",
                                    "as_of": today}
        g = p.setdefault("geocode", {})
        g.setdefault("geocode_source", "nominatim")
        if "resolved_name" not in p:
            p["resolved_name"] = p.get("name_local") or p.get("name_display")
        _, status, _note = verify_poi(p, geocoded=bool(p.get("geocode")),
                                      in_claimed_region=True,
                                      resolved_name=p["resolved_name"], today=today)
        p["verify_status"] = status


def _fix_routing(a):
    from scripts.distance import classify_hop
    from scripts.rederive import hop_km
    r = a["routing"] or {}
    known = {c.get("district") for c in r.get("clusters") or [] if c.get("centroid")}
    for hop in r.get("hops") or []:
        hop.setdefault("mode", "drive")
        hop["duration_source"] = "sourced_timetable"
        hop["source_url"] = "https://example.gov.tw/timetable"
        for end in ("from", "to"):
            if hop.get(end) not in known:
                r.setdefault("clusters", []).append(
                    {"district": hop.get(end), "pois": [],
                     "centroid": {"lat": 24.7, "lng": 121.7}})
                known.add(hop.get(end))
    for hop in r.get("hops") or []:
        hop["flag"] = classify_hop(hop.get("mins"), 60, km=hop_km(r, hop),
                                   mode=hop.get("mode"),
                                   duration_source=hop.get("duration_source"),
                                   source_url=hop.get("source_url"))


def _fix_legs(a):
    from scripts.legs import classify_leg
    for lg in (a["legs"] or {}).get("legs") or []:
        if lg.get("mode") == "drive":
            lg.setdefault("duration_mins", 60)
        else:
            lg["last_service_exempt"] = True
        lg["status"] = classify_leg(lg, 300)[0]


def _fix_accommodation(a):
    """Records what a real accommodation-research re-run would (I2, v0.33.0),
    plus a sourced business_status (v0.34.0 Task 6): a lodging candidate can
    now land in `superseded` exactly like a POI can, and re-running
    accommodation-research is the only stage that can supply the field. as_of
    is computed at CALL time, never a literal (OPERATING_MAX_AGE_DAYS is 90)."""
    today = datetime.date.today().isoformat()
    for stop in (a["accommodations"] or {}).get("stops") or []:
        for c in stop.get("candidates") or []:
            g = c.setdefault("geocode", {"lat": 24.7, "lng": 121.7})
            g["geocode_source"] = "nominatim"
            c["resolved_name"] = c.get("name_local") or c.get("name_display")
            if not isinstance(c.get("business_status"), dict):
                c["business_status"] = {"status": "OPERATIONAL",
                                        "source_url": "https://places.example/v1/place",
                                        "as_of": today}
            srcs = c.setdefault("sources", [])
            while len({s.get("url", "").split("/")[2] for s in srcs if s.get("url")}) < 2:
                srcs.append({"url": f"https://s{len(srcs)}.example/x", "lang": "zh"})


def _fix_cost(a):
    from scripts.cost import sum_costs
    if a["cost"] is not None:
        summed = sum_costs(a["cost"].get("line_items") or [])
        a["cost"]["total"] = summed["total"]
        if "by_category" in a["cost"]:
            a["cost"]["by_category"] = summed["by_category"]


def _strip_tone(text):
    from scripts.text_hygiene import ai_tone_failures
    out = "".join(ch for ch in (text or "") if ch not in "—*")
    return out if not ai_tone_failures(out) else "行程"


def _fix_synthesis(a):
    """Rewrites the itinerary: a closing_status per in-scope row, a row for
    every home leg, tone-clean text, a meal on every day."""
    from scripts.hours import closing_status
    from scripts.rederive import _last_call_for, _need_mins
    by = poi_pool(a["pois"]["pois"], a["accommodations"])
    legs_list = (a["legs"] or {}).get("legs") or []
    days = a["itinerary"].get("days") or []
    for d in days:
        for row in d.get("rows") or []:
            for key in ("text", "from", "to"):
                if row.get(key):
                    row[key] = _strip_tone(row[key])
            t, pid = row.get("time"), row.get("poi_id")
            if not t or not pid or pid not in by or row.get("slot") == "lodging":
                row.pop("closing_status", None)
                continue
            hours = by[pid].get("hours") or {}
            if hours.get("no_fixed_close"):
                row["closing_status"] = "ok"
            elif hours.get("close"):
                row["closing_status"] = closing_status(
                    t, hours["close"], _last_call_for(row.get("slot"), hours),
                    _need_mins(hours, 30, 60))[0]
    a["itinerary"]["title"] = _strip_tone(a["itinerary"].get("title"))
    a["itinerary"]["checklist"] = [_strip_tone(c)
                                   for c in a["itinerary"].get("checklist") or []]
    for c in a["itinerary"].get("contingency") or []:
        for key in ("trigger", "fallback", "note"):
            if c.get(key):
                c[key] = _strip_tone(c[key])
    if days:
        for i, lg in enumerate(legs_list):
            if lg.get("kind") == "home":
                days[0].setdefault("rows", []).append(
                    {"slot": "move", "text": "移動", "leg_index": i})
    for d in days:
        if not any(r.get("slot") == "meal" for r in d.get("rows") or []):
            d.setdefault("rows", []).append({"slot": "meal", "text": "用餐"})


FIX = {"tripwork:source-verify": _fix_source_verify,
        "tripwork:routing-audit": _fix_routing,
        "tripwork:inter-stop-legs": _fix_legs,
        "tripwork:accommodation-research": _fix_accommodation,
        "tripwork:cost-rollup": _fix_cost,
        "tripwork:itinerary-synthesis": _fix_synthesis}


def drain(trip, max_rounds=10):
    """Returns (terminated, per-round failure counts)."""
    a = copy.deepcopy(load_trip(trip))
    history = []
    for _ in range(max_rounds):
        report = gate(a)
        history.append(len(report["failures"]))
        if report["status"] == "pass":
            return True, history
        FIX[route_gate_failures(report["failures"])](a)
    return False, history
