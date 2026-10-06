"""Itinerary-gate: mechanical structural + verification-status checks.

Consumes the canonical itinerary dict (schemas/itinerary.schema.json) — NOT an
LLM-reconstructed days list. Every referenced POI must be verified+geocoded; no
POI may be scheduled on a closed day; every must_do must be covered; every
banned/restricted advisory item must be surfaced. Content correctness of the
sources themselves is source-verify's job; this gate checks the assembled plan.
"""
if __name__ == "__main__":
    raise SystemExit("moved in tripwork 2.0: python <plugin>/scripts/tripwork.py gate <slug>")


from scripts.brief_names import headline_failures, name_failures
from scripts.checklist import checklist_failures, checklist_texts
from scripts.day_chain import (alternative_failures, chain_failures, legacy_failures,
                               move_record_failures, theme_failures)
from scripts.day_titles import pick_notices
from scripts.facilities import stop_meets_required
from scripts.trip_calendar import poi_closed_on
from scripts.verify import official_source_url
from scripts.rederive import run_rederivation
from scripts.source_records import area_label_failures, source_record_failures
from scripts.text_hygiene import (ai_tone_failures, jargon_failures,
                                   kana_gloss_failures, kana_name_without_gloss)

def chosen_lodging_pois(accommodations):
    """Each overnight stop's chosen lodging as a POI-shaped dict, so the gate AND the
    renderers can resolve a `day.lodging` / lodging-row id natively — without the
    consumer merging hotels into canonical verified-pois.yaml. (P4)

    The chosen candidate is returned verbatim (it already carries id / name_local /
    name_display / geocode / verify_status / sources). Stops with no chosen lodging,
    or whose chosen id is not among the stop's candidates, contribute nothing.
    Both gate.run_gate and the export poi_map assembly fold this in."""
    out = []
    for stop in (accommodations or {}).get("stops", []):
        chosen_id = stop.get("chosen")
        if not chosen_id:
            continue
        chosen = next((c for c in stop.get("candidates", []) if c.get("id") == chosen_id), None)
        if chosen is not None:
            out.append(chosen)
    return out

def poi_pool(pois, accommodations):
    """The id->POI map every stage resolves rows against: verified-pois plus each
    stop's chosen lodging folded in (P4). The gate, export-gate, the renderers
    (export-artifact) and day_maps all call this -- one pool, one record per id.

    When an id is in both files, the record is the lodging candidate overlaid by
    the verified-pois record field by field (TW-091): verified-pois wins every field
    it has (identity, sources, geocode -- what the gate verifies), and fields only
    the lodging carries (booking, cost, facilities -- what the renderer shows)
    survive. Until v1.1 the gate kept the verified record whole while export-gate
    and export-artifact let the lodging record win, so one id meant two records:
    trip-e's `sap-hotel` failed export-gate on a "first official
    source" that only the other record had.

    Extracted so nothing can rebuild it a DIFFERENT way and then claim to have
    measured the gate (v0.33.0 C1: a guard rebuilt `by_id` from verified-pois
    alone, 58 rows against the gate's 63). Call this; do not re-implement the fold.
    """
    by_id = {p["id"]: p for p in pois}
    for lp in chosen_lodging_pois(accommodations):
        mine = by_id.get(lp["id"])
        by_id[lp["id"]] = lp if mine is None else {**lp, **mine}
    return by_id


def _referenced_ids(days):
    ids = set()
    for d in days:
        for row in d.get("rows", []):
            pid = row.get("poi_id")
            if pid:
                ids.add(pid)
        if d.get("lodging"):
            ids.add(d["lodging"])
    return ids

def _alternative_ids(days):
    """poi_ids of every per-day alternative (v1.0 §4.4). Kept OUT of
    _referenced_ids on purpose: a fallback place is verified, geocoded and
    closed-day checked like any stop, but it is not SCHEDULED -- counting it
    toward must_do coverage would let a must_do sit only in a rain plan and
    pass (v1.0 P1 final review, C2)."""
    return {a["poi_id"] for d in days for a in d.get("alternatives") or []
            if isinstance(a, dict) and isinstance(a.get("poi_id"), str) and a["poi_id"]}


def _day_has_meal(day):
    return any(r.get("slot") == "meal" for r in day.get("rows", []))

def _day_has_lodging(day):
    """Return True if the day has a non-empty lodging field OR a row with slot=='lodging'."""
    if day.get("lodging"):
        return True
    return any(r.get("slot") == "lodging" for r in day.get("rows", []))

def _home_legs_rendered_failures(itinerary, legs):
    """Every `kind: home` leg in legs.yaml must be referenced by at least one
    itinerary row's `leg_index` — otherwise its classify_leg verdict is checked
    (rederive_legs) and its fare is summed (cost-rollup) while nothing ever put
    it in front of the reader. (TW-069 fix round 1, Important 1)

    Deliberately its OWN check, not folded into verdicts_match/verdicts_rederivable:
    neither axis fits — this is "a consumed input never reached the deliverable",
    not "a recorded verdict is wrong" (verdicts_match) or "an input is missing"
    (verdicts_rederivable). A `legs=None` (legs.yaml absent) means there are no
    home legs to look for, so the first loop finds nothing; the SECOND loop
    still runs with n_legs == 0, so a row carrying a `leg_index` is reported as
    a dangling reference. That is deliberate and correct — a row pointing at leg
    0 of a file that is not there IS wrong — and it co-occurs with rederive_legs'
    "legs.yaml absent", which wins _ROUTES priority, so it adds detail rather
    than mis-routing.

    A non-integer `leg_index` is a gate FAILURE, never an exception. The schema
    forbids one, but `main()`'s `opt()` deliberately does not schema-validate
    (that is what lets a dirty trip get a routed, fixable failure instead of
    exit 2), so a hand-authored `leg_index: "0"` reaches this code verbatim and
    used to raise TypeError straight out of run_gate — which main() does not
    catch, so the CLI died with a traceback and the consumer got no failure list
    at all.

    Endpoints are matched by INDEX, never by string: the corpus shows a leg's
    `from`/`to` and the itinerary row that renders it are NOT the same string in
    any real trip (e.g. chiayi's leg endpoint '板橋（新北）' vs its row '板橋') —
    matching by name would be a false-positive machine the moment anyone records
    `kind: home`.

    Failure messages deliberately avoid the substring 'legs[' (scripts/rederive.py
    uses it for missing-input messages that legitimately route to
    tripwork:inter-stop-legs via scripts/orchestration.py's `_ROUTES`) — an
    unrendered home leg is a SYNTHESIS defect (nothing wrong with legs.yaml
    itself), so it must fall through to itinerary-synthesis instead.
    """
    legs_list = (legs or {}).get("legs") or []
    home_indices = [i for i, lg in enumerate(legs_list) if lg.get("kind") == "home"]
    referenced, malformed = set(), []
    for di, d in enumerate(itinerary.get("days", [])):
        for j, row in enumerate(d.get("rows", [])):
            li = row.get("leg_index")
            if li is None:
                continue
            # bool is an int subclass; `leg_index: true` is not an index.
            if isinstance(li, int) and not isinstance(li, bool):
                referenced.add(li)
            else:
                malformed.append((di, j, type(li).__name__))
    # The malformed VALUE is deliberately not interpolated, and the position is
    # given as ordinals rather than the day's `date`: this string is routed by
    # substring match in scripts/orchestration.py::_ROUTES, so any trip-authored
    # text inside it lets the itinerary decide where its own failure goes.
    # Reproduced before this was tightened: `leg_index: "legs.yaml absent"`
    # routed to inter-stop-legs and `"cost.total"` to cost-rollup. Same
    # principle the no_ai_tone comment below states for check truth. The type
    # name is a Python builtin, never trip content.
    failures = [
        f"itinerary day {di} row {j}: leg_index is a {tname}, not an integer — "
        f"synthesis must reference a recorded leg by its position in legs.yaml"
        for di, j, tname in malformed]
    for i in home_indices:
        if i not in referenced:
            lg = legs_list[i]
            frm, to = lg.get("from", "?"), lg.get("to", "?")
            failures.append(
                f"home leg {i} ({frm}->{to}) has no move row — synthesis must "
                f"render it on the day it applies to")
    n_legs = len(legs_list)
    for li in sorted(referenced):
        if li < 0 or li >= n_legs:
            failures.append(
                f"itinerary row leg_index {li} does not match any recorded leg "
                f"— synthesis must reference a real index")
    return failures


# (artifact, its list of records) whose schema demands an official source (v2.1.0 §5)
_OFFICIAL_RECORDS = (("advisory", "items"), ("calendar", "holidays"), ("seasonal", "items"), ("legs", "legs"))


def official_search_failures(advisory=None, calendar=None, seasonal=None, legs=None):
    """A record whose only official sources are search engine results pages has no
    official source (v2.1.0 §5). One failure per record, prefixed by its artifact --
    `<artifact> official source ` -- which _ROUTES sends to the stage that writes it.
    The legs message never contains 'legs[' (rederive's own marker)."""
    docs = {"advisory": advisory, "calendar": calendar, "seasonal": seasonal, "legs": legs}
    out = []
    for name, key in _OFFICIAL_RECORDS:
        for i, rec in enumerate((docs[name] or {}).get(key) or []):
            if not isinstance(rec, dict):
                continue
            flagged = [s["url"] for s in rec.get("sources") or []
                       if isinstance(s, dict) and s.get("official") and s.get("url")]
            if flagged and official_source_url(rec) is None:
                out.append(f"{name} official source is a search results page: {key} #{i} ({flagged[0]}) "
                           "— record the page it links to")
    return out


def _itinerary_text(itinerary):
    """Every authored free-text field a renderer surfaces: title + checklist + each day
    label + each row text + each move row's from/to endpoints + each contingency
    trigger/fallback/note. Kept a SUPERSET of what the renderers emit so the canonical
    hygiene scan (and the advisory-topic surfacing check) sees everything — line-short
    renders the title + labels verbatim and has no gate of its own, and from/to endpoints
    render into md/html, so omitting any of these would let a leak there ship unchecked.
    contingency is the largest single source of bold-label list items in the corpus
    (TW-069) — until it reaches this function it is invisible to the jargon, kana and
    AI-tone scans, even though render_markdown_page renders it verbatim. Parts are
    newline-joined so the per-line kana scan treats each field independently.
    v1.0 also scans each day's `theme`, each per-day alternative's trigger/fallback,
    and a structured checklist item's task/detail/origin/link labels."""
    parts = [itinerary.get("title", "")]
    for item in itinerary.get("checklist") or []:
        parts.extend(checklist_texts(item))
    for d in itinerary.get("days", []):
        parts.append(d.get("label", ""))
        parts.append(d.get("theme", ""))
        for row in d.get("rows", []):
            parts.append(row.get("text", ""))
            parts.append(row.get("from", ""))
            parts.append(row.get("to", ""))
        for a in d.get("alternatives") or []:
            if isinstance(a, dict):
                parts.extend(x for x in (a.get("trigger"), a.get("fallback")) if x)
    for c in itinerary.get("contingency") or []:
        parts.extend(x for x in (c.get("trigger"), c.get("fallback"), c.get("note")) if x)
    return " \n ".join(p for p in parts if isinstance(p, str) and p)

def run_gate(pois, itinerary, accommodations=None, facility_needs=None,
             calendar=None, advisory=None, must_do=None,
             legs=None, routing=None, cost=None, trip_brief=None, seasonal=None):
    """Return a gate-report dict: {status, checks, failures}.

    Args:
        pois:       verified-pois list.
        itinerary:  canonical itinerary dict ({title, checklist, days:[{date,label,rows,lodging}]}).
        calendar:   optional calendar dict; when given, the closed-day check runs.
        advisory:   optional advisory dict; when given, banned/restricted items must be surfaced.
        must_do:    optional list of POI ids that MUST be scheduled.
    """
    # P4: fold each stop's chosen lodging into the POI pool so a `day.lodging` /
    # lodging-row id referencing a hotel resolves natively (verified-pois win each
    # field on an id collision, TW-091). export-gate and the renderers call the same
    # poi_pool, and every test that wants to measure THIS pool must call it (C1).
    by_id = poi_pool(pois, accommodations)
    days = itinerary.get("days", [])
    scheduled = _referenced_ids(days)
    referenced = scheduled | _alternative_ids(days)

    failures = []

    for pid in sorted(referenced):
        p = by_id.get(pid)
        if p is None:
            failures.append(f"day references unknown POI '{pid}'")
            continue
        if p.get("verify_status") != "verified":
            failures.append(f"day references non-verified POI '{pid}' ({p.get('verify_status')})")
        if p.get("geocode") is None:
            failures.append(f"POI '{pid}' missing geocode")
        if kana_name_without_gloss(p):
            failures.append(f"POI '{pid}' has a kana name but no name_zh gloss")

    for d in days:
        if not _day_has_meal(d):
            failures.append(f"day {d.get('date', '?')} has no meal")

    # Always-on lodging floor: every non-final day must have resolved lodging.
    # Final day = departure day, no overnight needed.
    for d in days[:-1]:
        if not _day_has_lodging(d):
            failures.append(f"day {d.get('date', '?')} has no resolved lodging")

    closed_check = calendar is not None
    if closed_check:
        for d in days:
            date = d.get("date", "?")
            for row in d.get("rows", []):
                pid = row.get("poi_id")
                p = by_id.get(pid) if pid else None
                if p is None:
                    continue
                closed, reason = poi_closed_on(p, date, calendar)
                if closed:
                    failures.append(f"POI '{pid}' scheduled on closed day {date}: {reason}")
            for a in d.get("alternatives") or []:
                pid = a.get("poi_id") if isinstance(a, dict) else None
                p = by_id.get(pid) if isinstance(pid, str) else None
                if p is None:
                    continue
                closed, reason = poi_closed_on(p, date, calendar)
                if closed:
                    failures.append(f"alternative POI '{pid}' falls on a closed day {date}: {reason}")

    # P5: must_do entries are thematic free-text (e.g. "日月潭遊湖賞景"), NOT POI ids.
    # An entry is covered when (a) it is itself a scheduled POI id (id-based
    # back-compat), or (b) itinerary.must_do_coverage maps it to >=1 scheduled POI id.
    # The agent (synthesis) authors the theme->ids mapping; the gate checks coverage.
    must_do_check = must_do is not None
    if must_do_check:
        coverage = itinerary.get("must_do_coverage", {}) or {}
        for entry in must_do:
            covered = (entry in scheduled
                       or any(cid in scheduled for cid in coverage.get(entry, [])))
            if not covered:
                failures.append(
                    f"must_do '{entry}' not covered by any scheduled POI")

    # Mandatory-safety-artifact-presence floor (D2-class): an absent advisory is a
    # GATE FAILURE, not a skip. The banned/restricted list lives ONLY inside
    # advisory.yaml — if it is absent we cannot derive what is banned, so the gate
    # cannot verify banned/restricted items are surfaced. Treat as a safety fail.
    advisory_check = advisory is not None
    if not advisory_check:
        failures.append(
            "advisory absent — mandatory safety gate cannot verify "
            "banned/restricted items are surfaced")
    if advisory_check:
        text = _itinerary_text(itinerary)
        for item in advisory.get("items", []):
            if item.get("risk") in ("banned", "restricted"):
                topic = item.get("topic", "")
                if topic and topic not in text:
                    failures.append(
                        f"advisory item '{topic}' ({item.get('risk')}) not surfaced in itinerary")

    if accommodations is not None:
        required = (facility_needs or {}).get("required", [])
        for stop in accommodations.get("stops", []):
            where = stop.get("district", "?")
            chosen_id = stop.get("chosen")
            if chosen_id is None:
                failures.append(f"overnight stop '{where}' has no chosen lodging")
                continue
            chosen = next((c for c in stop.get("candidates", []) if c.get("id") == chosen_id), None)
            if chosen is None:
                failures.append(f"overnight stop '{where}' chosen lodging '{chosen_id}' not in candidates")
                continue
            ok, missing = stop_meets_required(chosen.get("facilities", []), required)
            if not ok:
                failures.append(f"chosen lodging at '{where}' missing required facility: {', '.join(missing)}")

    # Canonical content hygiene (always-on): the PRIMARY guard against an internal
    # (poi-id)/must_do token or an ungloss kana run leaking into user-facing text. Runs on
    # the unescaped canonical text (checklist + every row text), so blocking it here keeps
    # EVERY downstream renderer — md / html / line-short / notion-via-md — clean at the
    # source, including renderers that have no gate of their own. (defense-in-depth copies
    # also live in export_gate for the rendered md/html.)
    hygiene_text = _itinerary_text(itinerary)
    failures.extend(jargon_failures(hygiene_text, pois))
    failures.extend(kana_gloss_failures(hygiene_text))
    ai_tone = ai_tone_failures(hygiene_text)
    failures.extend(ai_tone)

    # v1.0 (spec §4): reader data. Each list is kept for a direct-return check
    # below, same reasoning as no_ai_tone: several of these messages carry POI
    # ids, so a substring scan over the merged list would be trip-content-dependent.
    chain = chain_failures(itinerary) + legacy_failures(itinerary)
    moves = move_record_failures(itinerary)
    alts = alternative_failures(itinerary)
    themes = theme_failures(itinerary)
    checklist_f = checklist_failures(itinerary, by_id, referenced)
    sources_f = source_record_failures(by_id, {p.get("id") for p in pois}, referenced)
    area_f = area_label_failures(accommodations) if accommodations is not None else []
    brief_f = (name_failures(trip_brief) + headline_failures(trip_brief)
               if trip_brief is not None else [])
    failures.extend(chain + moves + alts + themes + checklist_f + sources_f + area_f + brief_f)

    # TW-069 fix round 1: a `kind: home` leg's verdict is re-derived (below) and
    # its fare is summed (cost-rollup), but neither of those proves it ever
    # reached the reader — this is the mechanical form of that render-side gap.
    home_leg_failures = _home_legs_rendered_failures(itinerary, legs)
    failures.extend(home_leg_failures)
    official_f = official_search_failures(advisory=advisory, calendar=calendar, seasonal=seasonal, legs=legs)
    failures.extend(official_f)

    # Verdict re-derivation (v0.33.0). Every recorded mechanical verdict is
    # recomputed from the inputs the artifact itself carries. Emits its own two
    # checks rather than folding into the substring-matched list below, because a
    # re-derivation failure names the producing stage and must route there.
    rd = run_rederivation(itinerary, by_id, legs=legs, routing=routing,
                          cost=cost, trip_brief=trip_brief,
                          accommodations=accommodations, pois=pois)
    failures.extend(rd["failures"])

    checks = [
        {"name": "referenced_pois_verified",
         "passed": not any("non-verified POI" in f or "unknown POI" in f for f in failures)},
        {"name": "referenced_pois_geocoded",
         "passed": not any("missing geocode" in f or "unknown POI" in f for f in failures)},
        {"name": "referenced_pois_glossed",
         "passed": not any("no name_zh gloss" in f for f in failures)},
        {"name": "days_have_meals",
         "passed": not any("no meal" in f for f in failures)},
        {"name": "overnight_days_have_lodging",
         "passed": not any("no resolved lodging" in f for f in failures)},
        {"name": "advisory_present",
         "passed": not any("advisory absent" in f for f in failures)},
        {"name": "no_internal_jargon",
         "passed": not any("leaked into user-facing" in f for f in failures)},
        {"name": "japanese_glossed",
         "passed": not any("no （中文）gloss" in f for f in failures)},
        # `passed` reads the direct return value, not a substring scan of the
        # merged failures list like the other thirteen checks — eight of them
        # literally above this line, the remaining five appended conditionally
        # below (no_closed_day_violation, must_do_covered, advisory_items_surfaced,
        # overnight_stops_have_lodging, required_facilities_met). AI-tone snippets embed
        # arbitrary trip text, so a substring scan would be the only check in this
        # file whose truth depends on trip content.
        {"name": "no_ai_tone", "passed": not ai_tone},
        # Same direct-return-value style as no_ai_tone (not a substring scan):
        # home_leg_failures' messages deliberately share no fixed marker with any
        # other check's messages (see _home_legs_rendered_failures's docstring on
        # the 'legs[' routing trap), so a substring scan here would be fragile by
        # construction.
        {"name": "home_legs_rendered", "passed": not home_leg_failures},
        {"name": "day_chain_complete", "passed": not chain},
        {"name": "moves_recorded", "passed": not moves},
        {"name": "alternatives_valid", "passed": not alts},
        {"name": "day_theme_valid", "passed": not themes},
        {"name": "checklist_structured", "passed": not checklist_f},
        {"name": "sources_complete", "passed": not sources_f},
        {"name": "official_sources_not_search", "passed": not official_f},
    ]
    checks.extend(rd["checks"])
    if closed_check:
        checks.append({"name": "no_closed_day_violation",
                       "passed": not any("closed day" in f for f in failures)})
    if must_do_check:
        checks.append({"name": "must_do_covered",
                       "passed": not any("not covered by any scheduled POI" in f for f in failures)})
    if advisory_check:
        checks.append({"name": "advisory_items_surfaced",
                       "passed": not any("not surfaced in itinerary" in f for f in failures)})
    if accommodations is not None:
        checks.append({"name": "overnight_stops_have_lodging",
                       "passed": not any("no chosen lodging" in f or "not in candidates" in f for f in failures)})
        checks.append({"name": "required_facilities_met",
                       "passed": not any("missing required facility" in f for f in failures)})
        checks.append({"name": "lodging_area_labelled", "passed": not area_f})
    if trip_brief is not None:
        checks.append({"name": "brief_names_valid", "passed": not brief_f})

    report = {"status": "pass" if not failures else "fail", "checks": checks, "failures": failures}
    # v1.1 topic 7: the user's day-title picks never fail; two patterns get a word
    notices = address_notices(itinerary, by_id) + pick_notices(itinerary)
    if notices:
        report["notices"] = notices
    return report


def address_notices(itinerary, by_id):
    """v1.1 TW-096: a scheduled stop or chosen lodging with no address_local -- its 給司機看
    sheet is not shown. A notice, never a failure (the user: 不合適不硬放 -- an area like
    a hot-spring street, or a market whose official address is an office, has none)."""
    out = []
    for pid in sorted(_referenced_ids((itinerary or {}).get("days") or [])):
        p = by_id.get(pid)
        if p is not None and not p.get("address_local"):
            out.append(f"no address for {pid} — 給司機看 not shown "
                       f"(record address_local from an official source if it has one)")
    return out


def _load_yaml_file(path):
    import yaml
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class _MalformedOptionalArtifact(Exception):
    """Raised by main()'s opt() helper when an OPTIONAL artifact exists but is
    not valid YAML — caught alongside the required-artifact errors so a
    corrupt optional file exits 2 (usage error) instead of raising a raw
    traceback."""


def main(argv):
    """CLI: python <plugin>/scripts/tripwork.py gate <slug> — run the itinerary
    gate over the canonical artifacts in <trip-dir>/data/ and write
    work/<slug>/gate-report.yaml (paths from scripts/paths.py).
    Exit 0 pass / 1 fail / 2 missing/invalid required or optional artifact."""
    import argparse
    import pathlib
    import sys
    import yaml

    ap = argparse.ArgumentParser(description=main.__doc__)
    from scripts.paths import artifact_path, report_path, work_dir_for

    ap.add_argument("trip_dir")
    ap.add_argument("--work-dir", default=None)
    args = ap.parse_args(argv)
    d = pathlib.Path(args.trip_dir)
    w = pathlib.Path(args.work_dir) if args.work_dir else work_dir_for(d)

    def opt(name):
        try:
            return _load_yaml_file(artifact_path(d, name))
        except FileNotFoundError:
            return None
        except yaml.YAMLError as exc:
            raise _MalformedOptionalArtifact(f"{name}: {exc!r}") from exc

    try:
        pois = _load_yaml_file(artifact_path(d, "verified-pois.yaml"))["pois"]
        if not isinstance(pois, list):
            raise TypeError("verified-pois.yaml 'pois' is not a list")
        itinerary = _load_yaml_file(artifact_path(d, "itinerary.yaml"))
        brief = opt("trip-brief.yaml") or {}
        accommodations = opt("accommodations.yaml")
        calendar = opt("calendar.yaml")
        advisory = opt("advisory.yaml")
        legs = opt("legs.yaml")
        routing = opt("routing.yaml")
        cost = opt("cost.yaml")
        seasonal = opt("seasonal.yaml")
    except (FileNotFoundError, KeyError, TypeError, yaml.YAMLError,
            _MalformedOptionalArtifact) as exc:
        print(f"missing/invalid required or optional artifact: {exc!r}",
              file=sys.stderr)
        return 2

    report = run_gate(
        pois, itinerary,
        accommodations=accommodations,
        facility_needs=brief.get("facility_needs"),
        calendar=calendar,
        advisory=advisory,
        must_do=brief.get("must_do"),
        legs=legs,
        routing=routing,
        cost=cost,
        trip_brief=brief,
        seasonal=seasonal,
    )
    w.mkdir(parents=True, exist_ok=True)
    report_path(w, "gate-report.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    print(f"gate: {report['status']} ({len(report['failures'])} failures)")
    for f in report["failures"]:
        print(f"  - {f}")
    for n in report.get("notices") or []:                 # never change the status
        print(f"  notice: {n}")
    return 0 if report["status"] == "pass" else 1
