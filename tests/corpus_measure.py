"""語料量測的唯一來源 —— 量測端與斷言端共用這一份，不留第二份實作可漂移。

TW-074：在這個模組之前，每個數字以 literal 形式住在測試裡，所以一次**合法的**語料變動
（消費端拿某個 release 出貨的機制把自己的資料修對）會讓 8 個 guard 轉紅，而 plugin 一行
缺陷都沒有。那些 literal 描述的是語料在某一天的長相，不是 plugin 的行為。

CONDITIONAL：沒有消費端語料時整組 skip（見 mech_fixtures.CORPUS）。這些 guard 不在 CI 跑。
"""
import collections
import copy
import datetime
import json
import pathlib

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
    # business_status to reach classify_candidate in the first place. A
    # candidate that has not (yet) picked up a sourced business_status --
    # 2026-07-sun-moon-lake's d2-6 was the first observed case, at Task 6
    # time -- lands in lodging_verdict_superseded below instead of here; how
    # many of today's corpus candidates fall into that bucket is read from
    # tests/corpus-baseline.json's gate_aggregate.super_lodging (regenerable
    # via `python -m tests.corpus_measure --write`), not pinned in this
    # comment. The marker is kept, unfired, as a live regression guard: a
    # future corpus update that adds a sourced-but-wrong business_status
    # would need this class again, and a silently absent marker would let
    # _classify swallow it into "unattributed".
    ("lodging_verify_status_mismatch", "but classify_candidate re-derives"),
    # POI axis (TW-070) and lodging axis (v0.34.0 Task 6) each get their own
    # marker, discriminated by each message's own tail -- both share "was
    # produced under superseded rules" as a common substring (see above), but
    # POI's ends "...re-run source-verify for this POI" and lodging's ends
    # "...re-run accommodation-research for this candidate". One marker per
    # axis covers BOTH `superseded` sub-shapes (a business_status that is not
    # the sourced form at all, or one that IS that dict shape but unusable --
    # see scripts/rederive.py::rederive_pois / rederive_lodging's
    # docstrings), because either sub-shape routes through the same tail.
    # Which sub-shape any given corpus hit actually is, and how many hits
    # land in `superseded` at all (`super_poi` / `super_lodging`), is read
    # from tests/corpus-baseline.json's `gate_aggregate` below, not asserted
    # here. This module carries no marker for a `missing` or `mismatch` hit
    # on either axis because none has been observed in the corpus yet, not
    # because none can ever occur -- if a future corpus update produces one,
    # _classify's assert surfaces it as an unattributed failure instead of
    # silently absorbing it.
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


# --------------------------------------------------------------------------
# Baseline: the regenerable snapshot of every corpus-dependent number.
# --------------------------------------------------------------------------

BASELINE = pathlib.Path(__file__).resolve().parent / "corpus-baseline.json"


def load_baseline():
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def _axis_ids(report):
    """兩條 verdict 軸各自在 failure 字串裡指名的 id。切法與
    test_the_three_verdict_axes_partition_their_failures 原本的一致。"""
    poi_ids = {f.split("'")[1] for f in report["failures"] if f.startswith("pois[")}
    lodging_ids = {f.split("'")[3] for f in report["failures"]
                   if f.startswith("accommodations ")}
    return poi_ids, lodging_ids


def _measure_trip(trip):
    a = load_trip(trip)
    report = gate(a)
    poi_ids, lodging_ids = _axis_ids(report)
    terminated, history = drain(trip)
    return {
        "status": report["status"],
        "total": len(report["failures"]),
        "classes": classify(report["failures"]),
        # 每個 check 的 passed 直接記下來。不要在測試那端從 class 計數反推
        # ——class 與 check 不是一對一（poi_no_hours 也落在 rederivable 軸），
        # 反推出來的推導本身就是一份手搭副本（TW-083）。
        "checks_passed": {c["name"]: bool(c["passed"]) for c in report["checks"]},
        "poi_axis_findings": len(poi_ids),
        "lodging_axis_findings": len(lodging_ids),
        "drain_terminated": terminated,
        "drain_rounds": len(history),
    }


def _measure_gate_aggregate():
    found = compared = examined_rule_current = 0
    super_poi = super_lodging = 0
    match_failed = []
    for trip in CORPUS_TRIPS:
        report = gate(load_trip(trip))
        checks = {c["name"]: c for c in report["checks"]}
        found += checks["verdicts_rederivable"]["examined"]
        compared += checks["verdicts_match"]["examined"]
        examined_rule_current += checks["verdicts_rule_current"]["examined"]
        classes = classify(report["failures"])
        super_poi += classes.get("poi_verdict_superseded", 0)
        super_lodging += classes.get("lodging_verdict_superseded", 0)
        if not checks["verdicts_match"]["passed"]:
            match_failed.append(trip)
    return {"found": found, "compared": compared,
            "examined_rule_current": examined_rule_current,
            "super_poi": super_poi, "super_lodging": super_lodging,
            "match_failed": match_failed}


def _measure_rederive_axes():
    import yaml

    from scripts.rederive import (Outcome, rederive_closing, rederive_lodging,
                                  run_rederivation)

    def _checks(res):
        return {c["name"]: c for c in res["checks"]}

    # --- verdicts_match 軸：legs / hops / cost --------------------------------
    legs_seen = hops_seen = costs_seen = compared = 0
    per_trip_match = {}
    for trip in CORPUS_TRIPS:
        d = CORPUS / trip
        legs = yaml.safe_load((d / "legs.yaml").read_text(encoding="utf-8"))
        routing = yaml.safe_load((d / "routing.yaml").read_text(encoding="utf-8"))
        cost = yaml.safe_load((d / "cost.yaml").read_text(encoding="utf-8"))
        brief = yaml.safe_load((d / "trip-brief.yaml").read_text(encoding="utf-8"))
        res = run_rederivation({"days": []}, {}, legs=legs, routing=routing,
                               cost=cost, trip_brief=brief)
        legs_seen += len(legs.get("legs") or [])
        hops_seen += len(routing.get("hops") or [])
        costs_seen += 1
        compared += _checks(res)["verdicts_match"]["examined"]
        # 逐趟記，不要 AND 起來——理由與 per_trip_rederivable / per_trip_match_passed
        # 相同：今天四趟全 True 只是語料現狀，不是不變量，聚合會讓未來任何一趟走樣
        # 都看不見。這一支餵給 tests/test_rederive.py:253
        # test_real_trips_have_zero_verdicts_match_failures 逐趟的
        # `assert c["verdicts_match"]["passed"] is True` 斷言。
        per_trip_match[trip] = bool(_checks(res)["verdicts_match"]["passed"])
    match = {"legs_seen": legs_seen, "hops_seen": hops_seen,
             "costs_seen": costs_seen, "compared": compared,
             "per_trip_passed": per_trip_match}

    # --- verdicts_rederivable 軸：legs / hops / cost --------------------------
    total_missing = provenance_missing = 0
    per_trip_rederivable = {}
    for trip in CORPUS_TRIPS:
        d = CORPUS / trip
        res = run_rederivation(
            {"days": []}, {},
            legs=yaml.safe_load((d / "legs.yaml").read_text(encoding="utf-8")),
            routing=yaml.safe_load((d / "routing.yaml").read_text(encoding="utf-8")),
            cost=yaml.safe_load((d / "cost.yaml").read_text(encoding="utf-8")),
            trip_brief=yaml.safe_load((d / "trip-brief.yaml").read_text(encoding="utf-8")),
            accommodations={"stops": []})
        total_missing += len(res["failures"])
        provenance_missing += sum("no duration_source" in f for f in res["failures"])
        # 逐趟記，不要 AND 起來——chiayi 今天就與另外三趟不同（True vs False），
        # 聚合會把它蓋掉，正是這個量測要防的「一類靜默清空」。
        per_trip_rederivable[trip] = bool(_checks(res)["verdicts_rederivable"]["passed"])
    rederivable = {"total_missing": total_missing,
                   "provenance_missing": provenance_missing,
                   "per_trip_passed": per_trip_rederivable}

    # --- 住宿軸 ---------------------------------------------------------------
    found = 0
    superseded, other = [], []
    per_trip_lodging_match = {}
    for trip in CORPUS_TRIPS:
        d = CORPUS / trip
        acc = yaml.safe_load((d / "accommodations.yaml").read_text(encoding="utf-8"))
        brief = yaml.safe_load((d / "trip-brief.yaml").read_text(encoding="utf-8"))
        res = run_rederivation({"days": []}, {}, legs={"legs": []},
                               routing={"clusters": [], "hops": []},
                               cost={"currency": "TWD", "line_items": [], "total": 0},
                               trip_brief=brief, accommodations=acc)
        # 住宿軸的分母要用住宿那條軸自己的函式，且 local_lang 的取法與
        # scripts/rederive.py:657-659 的 shipped 呼叫逐字相同（TW-083）。
        # 不可以用 _checks(res)["verdicts_rederivable"]["examined"] —— 那是
        # total.found，等於 rederive_lodging.found + rederive_cost.found，
        # 每趟多 1（cost 軸自己那筆 found，跟住宿軸無關；兩個 found 都會隨
        # 語料變動，差值不在此釘死，見 tests/corpus-baseline.json）。
        found += rederive_lodging(
            acc,
            local_lang=((brief or {}).get("destination") or {}).get("local_lang")).found
        superseded.extend(f for f in res["failures"] if "superseded rules" in f)
        other.extend(f for f in res["failures"] if "superseded rules" not in f)
        # 逐趟記，不要 AND 起來——理由與上面 per_trip_rederivable 相同：今天四趟
        # 全 True 只是語料現狀，不是不變量，聚合會讓未來任何一趟走樣都看不見。
        per_trip_lodging_match[trip] = bool(_checks(res)["verdicts_match"]["passed"])
    lodging = {
        "found": found,
        "superseded": len(superseded),
        "other": len(other),
        "missing_geocode_source": sum("no geocode.geocode_source" in f for f in other),
        "missing_resolved_name": sum("no resolved_name" in f for f in other),
        "superseded_ids": sorted({f.split("'")[3] for f in superseded}),
        "per_trip_match_passed": per_trip_lodging_match,
    }

    # --- closing 軸 -----------------------------------------------------------
    total = Outcome()
    rows_total = has_time_no_pid = unresolved_pid = lodging_rows = 0
    no_hours_at_all = hours_but_no_close = no_closing_status = 0
    for trip in CORPUS_TRIPS:
        d = CORPUS / trip
        itin = yaml.safe_load((d / "itinerary.yaml").read_text(encoding="utf-8"))
        pois = yaml.safe_load((d / "verified-pois.yaml").read_text(encoding="utf-8"))
        acc = yaml.safe_load((d / "accommodations.yaml").read_text(encoding="utf-8"))
        by_id = poi_pool(pois.get("pois") or [], acc)
        for day in itin.get("days") or []:
            for row in day.get("rows") or []:
                rows_total += 1
                t, pid = row.get("time"), row.get("poi_id")
                if t and not pid:
                    has_time_no_pid += 1
                elif t and pid and pid not in by_id:
                    unresolved_pid += 1
                elif t and pid and row.get("slot") == "lodging":
                    lodging_rows += 1
                elif t and pid:
                    hours = by_id[pid].get("hours") or {}
                    if not hours:
                        no_hours_at_all += 1
                    elif not hours.get("close") and not hours.get("no_fixed_close"):
                        hours_but_no_close += 1
                    elif "closing_status" not in row:
                        no_closing_status += 1
        total.merge(rederive_closing(itin, by_id))
    # C1 的回歸鎖（tests/test_rederive.py:881-892）也是語料相依的，一併量。
    folded_only = 0
    unfolded = Outcome()
    for trip in CORPUS_TRIPS:
        d = CORPUS / trip
        itin = yaml.safe_load((d / "itinerary.yaml").read_text(encoding="utf-8"))
        pois = yaml.safe_load((d / "verified-pois.yaml").read_text(encoding="utf-8"))
        acc = yaml.safe_load((d / "accommodations.yaml").read_text(encoding="utf-8"))
        bare = {p["id"]: p for p in pois.get("pois") or []}
        folded_only += len(set(poi_pool(pois.get("pois") or [], acc)) - set(bare))
        unfolded.merge(rederive_closing(itin, bare))

    closing = {"rows_total": rows_total, "has_time_no_pid": has_time_no_pid,
               "unresolved_pid": unresolved_pid, "lodging_rows": lodging_rows,
               "no_hours_at_all": no_hours_at_all,
               "hours_but_no_close": hours_but_no_close,
               "no_closing_status": no_closing_status,
               "in_scope": total.found,
               # 這三個是 tests/test_rederive.py:858-860 的斷言，本 plan 撰寫時
               # 實測為 46 / 0 / 10，而 code 裡寫的是 56 / 0 / 0 —— 少了它們，
               # Task 4 不可能全綠。missing + compared == in_scope。
               "missing": len(total.missing),
               "mismatches": len(total.mismatches),
               "compared": total.compared,
               # C1 回歸鎖（:891-892）
               "folded_only": folded_only,
               "unfolded_found": unfolded.found}

    return {"match": match, "rederivable": rederivable,
            "lodging": lodging, "closing": closing}


def _measure_counterfactual():
    """把 `tripwork:source-verify` 這一組從 _ROUTES 拿掉之後，yilan 的 drain 固定點。

    用明示的 save/restore 而不是 monkeypatch：這個函式要能在 pytest 之外被
    --write 呼叫。try/finally 保證還原，否則同一個 process 裡後續的量測全都是錯的。
    """
    import scripts.orchestration as orchestration

    original = orchestration._ROUTES
    try:
        orchestration._ROUTES = tuple(
            g for g in original if g[1] != "tripwork:source-verify")
        terminated, history = drain("2026-06-yilan")
    finally:
        orchestration._ROUTES = original
    return {"yilan_without_source_verify_terminated": terminated,
            "yilan_without_source_verify_fixed_point": history[-1]}


# --------------------------------------------------------------------------
# measure_corpus(): every axis, in one call.
# --------------------------------------------------------------------------

def measure_corpus():
    """語料相依的每一個數字，全部經由 shipped code 量一次。

    回傳值是純 JSON 可序列化的計數與識別名 —— 沒有 display name、日期、URL 或座標，
    所以這份輸出可以進 public repo，而語料本身不行。（candidate id 會出現在
    superseded_ids，那些 id 已逐字存在於 tests/test_rederive.py 的既有註解裡。）
    """
    return {
        "corpus_trips": list(CORPUS_TRIPS),
        "per_trip": {t: _measure_trip(t) for t in CORPUS_TRIPS},
        "gate_aggregate": _measure_gate_aggregate(),
        "rederive_axes": _measure_rederive_axes(),
        "counterfactual": _measure_counterfactual(),
    }


def _write():
    BASELINE.write_text(
        json.dumps(measure_corpus(), indent=2, ensure_ascii=False,
                   sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {BASELINE}")


if __name__ == "__main__":
    import sys
    if "--write" not in sys.argv:
        print(__doc__)
        print("usage: python -m tests.corpus_measure --write")
        raise SystemExit(2)
    if not CORPUS.is_dir():
        print(f"error: corpus not found at {CORPUS}", file=sys.stderr)
        raise SystemExit(1)
    _write()
