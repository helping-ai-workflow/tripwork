"""Itinerary-gate: mechanical structural + verification-status checks.

Consumes the canonical itinerary dict (schemas/itinerary.schema.json) — NOT an
LLM-reconstructed days list. Every referenced POI must be verified+geocoded; no
POI may be scheduled on a closed day; every must_do must be covered; every
banned/restricted advisory item must be surfaced. Content correctness of the
sources themselves is source-verify's job; this gate checks the assembled plan.
"""
if __name__ == "__main__" and __package__ in (None, ""):
    # Drop the auto-added scripts/ dir (it shadows stdlib `calendar` with
    # scripts/calendar.py) and put the repo root on sys.path so `from scripts.X
    # import ...` resolves. See scripts/_cli_bootstrap.py for the full account.
    # Must precede every other import: the shadow breaks `import requests` too.
    import pathlib as _bootpath, sys as _bootsys
    _bootsys.path.insert(0, str(_bootpath.Path(__file__).resolve().parent))
    import _cli_bootstrap        # noqa: F401  (imported for its side effect)

import sys as _sys

from scripts.facilities import stop_meets_required
from scripts.calendar import poi_closed_on
from scripts.rederive import run_rederivation
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
    """The id->POI map `run_gate` actually resolves rows against: verified-pois
    plus each stop's chosen lodging folded in (P4), verified-pois winning on an
    id collision.

    Extracted so nothing can rebuild it a DIFFERENT way and then claim to have
    measured the gate. That is exactly how C1 shipped: the corpus guard at
    tests/test_rederive.py rebuilt `by_id` from verified-pois alone, putting 58
    rows in closing scope while the shipped gate put 63 there — the 5-row delta
    was the whole defect, and the guard could not see it because it was
    measuring a different pool. Call this; do not re-implement the fold.

    ⚠ KNOWN DIVERGENCE, surfaced not fixed (v0.35.0 follow-up). export_gate's
    poi_map builds the same fold with the OPPOSITE precedence — a dict
    comprehension over `pois + chosen_lodging_pois(...)`, so the lodging record
    wins an id collision instead of losing it. Two trips have ids in BOTH files
    and so resolve to a different record in the gate than in the renderer:
    2026-07-sun-moon-lake (`lealea`, `d2-2`) and hokkaido-7d
    (`lodge-toya-nonokaze`, `sap-mitsui-garden`, `hak-lavista-bay`). The gate
    verifies the verified-pois record (category / district / gmaps_place_id);
    the renderer renders the accommodations candidate (booking / cost /
    facilities).

    The concrete risk in flipping export to match is NARROWER than the
    divergence, and lands on hokkaido-7d only: export_gate:182 keys its
    bookable-link check on `booking.required`, and only hokkaido-7d's
    `sap-mitsui-garden` and `hak-lavista-bay` set it. sun-moon-lake's two
    candidates carry a bare `booking: {url}` with no `required`, so that check
    never fires on them either way. (hokkaido-7d is one of the trips excluded
    from the schema-clean four (tests/mech_fixtures.py::CORPUS_TRIPS), which
    is why no corpus guard covers this today.) Each precedence is defensible
    for its own job; unifying them needs its own design and is NOT simply
    "call poi_pool here too".
    """
    by_id = {p["id"]: p for p in pois}
    for lp in chosen_lodging_pois(accommodations):
        by_id.setdefault(lp["id"], lp)
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
    any real trip (e.g. chiayi's leg endpoint '三重（新北）' vs its row '三重') —
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
    newline-joined so the per-line kana scan treats each field independently."""
    parts = [itinerary.get("title", "")]
    parts.extend(itinerary.get("checklist", []))
    for d in itinerary.get("days", []):
        parts.append(d.get("label", ""))
        for row in d.get("rows", []):
            parts.append(row.get("text", ""))
            parts.append(row.get("from", ""))
            parts.append(row.get("to", ""))
    for c in itinerary.get("contingency") or []:
        parts.extend(x for x in (c.get("trigger"), c.get("fallback"), c.get("note")) if x)
    return " \n ".join(p for p in parts if p)

def run_gate(pois, itinerary, accommodations=None, facility_needs=None,
             calendar=None, advisory=None, must_do=None,
             legs=None, routing=None, cost=None, trip_brief=None):
    """Return a gate-report dict: {status, checks, failures}.

    Args:
        pois:       verified-pois list.
        itinerary:  canonical itinerary dict ({title, checklist, days:[{date,label,rows,lodging}]}).
        calendar:   optional calendar dict; when given, the closed-day check runs.
        advisory:   optional advisory dict; when given, banned/restricted items must be surfaced.
        must_do:    optional list of POI ids that MUST be scheduled.
    """
    # P4: fold each stop's chosen lodging into the POI pool so a `day.lodging` /
    # lodging-row id referencing a hotel resolves natively (verified-pois win on id
    # collision). The renderers assemble poi_map the same way (chosen_lodging_pois),
    # and every test that wants to measure THIS pool must call poi_pool (C1).
    by_id = poi_pool(pois, accommodations)
    days = itinerary.get("days", [])
    referenced = _referenced_ids(days)

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

    # P5: must_do entries are thematic free-text (e.g. "日月潭遊湖賞景"), NOT POI ids.
    # An entry is covered when (a) it is itself a scheduled POI id (id-based
    # back-compat), or (b) itinerary.must_do_coverage maps it to >=1 scheduled POI id.
    # The agent (synthesis) authors the theme->ids mapping; the gate checks coverage.
    must_do_check = must_do is not None
    if must_do_check:
        coverage = itinerary.get("must_do_coverage", {}) or {}
        for entry in must_do:
            covered = (entry in referenced
                       or any(cid in referenced for cid in coverage.get(entry, [])))
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

    # TW-069 fix round 1: a `kind: home` leg's verdict is re-derived (below) and
    # its fare is summed (cost-rollup), but neither of those proves it ever
    # reached the reader — this is the mechanical form of that render-side gap.
    home_leg_failures = _home_legs_rendered_failures(itinerary, legs)
    failures.extend(home_leg_failures)

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

    return {"status": "pass" if not failures else "fail", "checks": checks, "failures": failures}


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
    """CLI: python scripts/gate.py <trip-dir> — run the itinerary gate over the
    canonical artifacts in <trip-dir> and write <trip-dir>/gate-report.yaml.
    Exit 0 pass / 1 fail / 2 missing/invalid required or optional artifact."""
    import argparse
    import pathlib
    import sys
    import yaml

    ap = argparse.ArgumentParser(description=main.__doc__)
    ap.add_argument("trip_dir")
    args = ap.parse_args(argv)
    d = pathlib.Path(args.trip_dir)

    def opt(name):
        try:
            return _load_yaml_file(d / name)
        except FileNotFoundError:
            return None
        except yaml.YAMLError as exc:
            raise _MalformedOptionalArtifact(f"{name}: {exc!r}") from exc

    try:
        pois = _load_yaml_file(d / "verified-pois.yaml")["pois"]
        if not isinstance(pois, list):
            raise TypeError("verified-pois.yaml 'pois' is not a list")
        itinerary = _load_yaml_file(d / "itinerary.yaml")
        brief = opt("trip-brief.yaml") or {}
        accommodations = opt("accommodations.yaml")
        calendar = opt("calendar.yaml")
        advisory = opt("advisory.yaml")
        legs = opt("legs.yaml")
        routing = opt("routing.yaml")
        cost = opt("cost.yaml")
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
    )
    (d / "gate-report.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    print(f"gate: {report['status']} ({len(report['failures'])} failures)")
    for f in report["failures"]:
        print(f"  - {f}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv[1:]))
