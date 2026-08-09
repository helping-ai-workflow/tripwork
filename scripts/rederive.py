"""Verdict re-derivation — recompute every recorded mechanical verdict from the
inputs the artifact carries, and prove the inputs are there to recompute it with.

tripwork owns a shelf of pure decision functions (classify_leg, classify_hop,
sum_costs, closing_status). Until now nothing ran them against a FINISHED
artifact: the agent was trusted to call them and transcribe the answer. Dogfood
2026-08 showed what that buys — routing.yaml hop flags typed by hand, a
gate-report with 13 green checks, and a user catching the errors by eye.

Three axes, all emitted as named checks with an examined:N count:
  verdicts_match        — recorded verdict == recomputed verdict
  verdicts_rederivable  — every verdict-bearing record carries the inputs needed
  verdicts_rule_current — the recorded verdict was produced under rules still
                          in force, not ones a later release superseded
                          (rederive_pois only, TW-070)

A record whose inputs are MISSING is a verdicts_rederivable FAILURE, never a
skip. A skipped record is indistinguishable from a green one, which is the exact
defect class this module exists to close (cf. scripts/gate.py:151-155, where an
absent advisory is a failure rather than a skipped check).

Lodging coverage is partial, and deliberately not papered over. rederive_lodging
re-derives classify_candidate's Gates 1/2/2b/2c for every accommodations.yaml
candidate. Gate 0 (operating) is NOT re-derived: accommodations.schema.json
carries no business_status field, so there is nothing to read, and closing it is
a TW-063-sized change deferred to v0.34.0. Gates 3a/3b (conflict_detected,
in_claimed_region) are NOT re-derived either: both are computed by the agent at
research time and the artifact records neither, so the permissive values are
passed and a region mismatch or cross-source conflict on a hotel is invisible
to this module. Do not read "lodging reaches the gates" as "all six gates run
on lodging" — only Gates 1/2/2b/2c do.

What this proves and what it does not: re-derivation proves a verdict follows
from the recorded numbers. It never proves the numbers are real. min_plausible_mins
is computed over agent-authored cluster centroids that TW-062 shows can be
fictions; sum_costs proves the total follows from the line items, never that a
line item is a real price.
"""
from scripts.cost import sum_costs
from scripts.distance import classify_hop, haversine_km
from scripts.hours import closing_status
from scripts.legs import classify_leg
from scripts.verify import NO_RESOLVED_NAME, _parse_iso, classify_candidate, name_matches, verify_poi

# Plugin defaults, overridable only from trip-brief. Deliberately NOT recorded
# per-record: a per-leg threshold would let an agent widen the cap to clear its
# own verdict.
MAX_SINGLE_DRIVE_MINS = 300
MAX_HOP_MINS = 60
COST_TOL = 0.005
MIN_BUFFER_MINS = 30
DEFAULT_VISIT_MINS = 60

# The artifact spelling of verify.NO_RESOLVED_NAME. The sentinel itself is an
# object() and cannot be serialised; the schema declares this literal. (TW-071)
NO_RESULT_SENTINEL = "NO_RESULT"


class Outcome:
    """(mismatch failures, missing-input failures, superseded-rule failures,
    records found, records compared)."""

    __slots__ = ("mismatches", "missing", "superseded", "found", "compared")

    def __init__(self):
        self.mismatches, self.missing, self.superseded = [], [], []
        self.found = self.compared = 0

    def merge(self, other):
        self.mismatches += other.mismatches
        self.missing += other.missing
        self.superseded += other.superseded
        self.found += other.found
        self.compared += other.compared
        return self


def _brief_num(trip_brief, section, key, default):
    return ((trip_brief or {}).get(section) or {}).get(key, default)


def hop_km(routing, hop):
    """Great-circle km between a hop's endpoints via routing.clusters[].centroid.

    None when either endpoint has no centroid. run_rederivation turns None into a
    FAILURE rather than passing km=None to classify_hop, which would silently
    disable the plausibility floor (scripts/distance.py:34).
    """
    cents = {c.get("district"): c.get("centroid")
             for c in (routing or {}).get("clusters") or [] if c.get("centroid")}
    a, b = cents.get(hop.get("from")), cents.get(hop.get("to"))
    if not a or not b:
        return None
    return haversine_km(a["lat"], a["lng"], b["lat"], b["lng"])


def rederive_legs(legs, *, max_single_drive_mins=MAX_SINGLE_DRIVE_MINS):
    out = Outcome()
    if legs is None:
        out.missing.append("legs.yaml absent — classify_leg verdicts are not re-derivable")
        return out
    for i, lg in enumerate(legs.get("legs") or []):
        out.found += 1
        frm, to = lg.get("from", "?"), lg.get("to", "?")
        mode = lg.get("mode")
        if mode == "drive" and lg.get("duration_mins") is None:
            out.missing.append(
                f"legs[{i}] {frm}->{to}: mode 'drive' carries no duration_mins — "
                f"classify_leg is not re-derivable")
            continue
        if mode != "drive" and not (lg.get("depart") and lg.get("last_service")) \
                and not lg.get("last_service_exempt"):
            out.missing.append(
                f"legs[{i}] {frm}->{to}: mode {mode!r} carries neither "
                f"depart+last_service nor last_service_exempt — classify_leg cannot "
                f"re-derive 'missed_last_service', so a recorded 'ok' is vacuous")
            continue
        got, reason = classify_leg(lg, max_single_drive_mins)
        out.compared += 1
        rec = lg.get("status")
        if rec != got:
            out.mismatches.append(
                f"legs[{i}] {frm}->{to}: recorded status {rec!r} but classify_leg "
                f"re-derives {got!r} ({reason or 'no reason'})")
    return out


def rederive_hops(routing, *, max_hop_mins=MAX_HOP_MINS):
    """Re-derive every routing hop's flag, and close the km/mode omission escape.

    `classify_hop`'s floor and provenance branches both sit behind km+mode, which
    are optional — omitting either skips both checks with no error and no warning
    (scripts/distance.py:69 records that escape as deliberately deferred to this
    release). At the artifact level this function IS the closure: a hop with no
    `mode`, or an endpoint with no cluster centroid, cannot be recomputed and is a
    verdicts_rederivable FAILURE. The legacy two-argument call form stays legal so
    the ~47 existing distance tests keep their meaning.
    """
    out = Outcome()
    if routing is None:
        out.missing.append("routing.yaml absent — classify_hop verdicts are not re-derivable")
        return out
    cents = {c.get("district") for c in (routing.get("clusters") or []) if c.get("centroid")}
    for hop in routing.get("hops") or []:
        out.found += 1
        frm, to = hop.get("from", "?"), hop.get("to", "?")
        mode = hop.get("mode")
        if not mode:
            out.missing.append(
                f"routing hop {frm}->{to}: no mode — min_plausible_mins has no speed "
                f"floor to apply and classify_hop degrades to a threshold-only compare")
            continue
        km = hop_km(routing, hop)
        if km is None:
            missing_end = frm if frm not in cents else to
            out.missing.append(
                f"routing hop {frm}->{to}: endpoint {missing_end!r} has no cluster "
                f"centroid — the min_plausible_mins floor cannot be recomputed")
            continue
        ds = hop.get("duration_source")
        got = classify_hop(hop.get("mins"), max_hop_mins, km=km, mode=mode,
                           duration_source=ds, source_url=hop.get("source_url"))
        rec = hop.get("flag")
        if ds is None:
            # Provenance is an INPUT and it is absent. Per this module's own axis
            # split that is a verdicts_rederivable failure, never a skip; per the
            # transition rule duration_source is optional in
            # schemas/routing.schema.json and required by the gate.
            #
            # The match comparison then runs provenance-BLIND. classify_hop's
            # precedence is implausible > far > unsourced > ok, so `unsourced` is
            # reachable ONLY after the floor and the cap have both been cleared:
            # folding it back to `ok` is provably the sole outcome the absent
            # field could have changed, and no physics or feasibility verdict is
            # masked by doing so.
            #
            # Measured at fd053dd: all 19 hops across the four schema-clean trips
            # omit duration_source — they predate TW-066. Without this split every
            # one reports a verdicts_match failure, putting 19 legacy-provenance
            # findings on the axis reserved for "the recorded verdict is wrong".
            out.missing.append(
                f"routing hop {frm}->{to}: no duration_source — classify_hop's "
                f"provenance branch is not re-derivable (record agent_estimate / "
                f"map_estimate / sourced_timetable, plus source_url when it is not "
                f"an agent estimate)")
            # Fix round 1, one-liner 1: the fold is asymmetric. A hop recorded
            # flag:'unsourced' with no duration_source is CORRECTLY recorded
            # (absent means agent_estimate, which classifies 'unsourced') --
            # only fold got back to 'ok' when the recorded verdict ISN'T
            # already 'unsourced'. Folding unconditionally would rewrite a
            # correct 'unsourced' into a false mismatch against 'ok', on the
            # axis reserved for wrong verdicts -- backwards from the fold's
            # purpose.
            if got == "unsourced" and rec != "unsourced":
                got = "ok"
        out.compared += 1
        if rec != got:
            out.mismatches.append(
                f"routing hop {frm}->{to}: recorded flag {rec!r} but classify_hop "
                f"re-derives {got!r}")
    return out


def rederive_cost(cost):
    out = Outcome()
    if cost is None:
        out.missing.append("cost.yaml absent — sum_costs verdicts are not re-derivable")
        return out
    out.found += 1
    # scripts/cost.py:22 returns a DICT {"by_category": ..., "total": ...}, not a
    # 2-tuple. Unpacking it as a pair silently binds the two KEY STRINGS, and the
    # comparison below then reads `rec == "total"` — int vs str, mismatching on
    # every trip. Measured: with the correct read, 4 of 4 clean trips MATCH.
    summed = sum_costs(cost.get("line_items") or [])
    by_cat, total = summed["by_category"], summed["total"]
    out.compared += 1
    rec = cost.get("total")
    same = rec == total if isinstance(rec, int) and isinstance(total, int) \
        else abs((rec or 0) - total) <= COST_TOL
    if not same:
        out.mismatches.append(
            f"cost.total recorded {rec} but sum_costs(line_items) re-derives {total}")
    # by_category is the ONLY field whose absence is not a failure: `total` is the
    # load-bearing verdict and is already re-derived from required inputs, so this
    # is a strictly-additional cross-check.
    for cat, amt in (cost.get("by_category") or {}).items():
        got = by_cat.get(cat)
        if got is None or abs(amt - got) > COST_TOL:
            out.mismatches.append(
                f"cost.by_category[{cat!r}] recorded {amt} but sum_costs re-derives {got}")
    return out


def _last_call_for(slot, hours):
    """meal -> last_order; everything else -> last_entry.
    Transcribed verbatim from skills/itinerary-synthesis/SKILL.md:43, where the
    rule has lived as prose with no enforcement."""
    return hours.get("last_order") if slot == "meal" else hours.get("last_entry")


def _need_mins(hours, min_buffer_mins, default_visit_mins):
    """max(min_buffer, typical_visit_mins or default). Also from SKILL.md:43."""
    return max(min_buffer_mins,
               hours.get("typical_visit_mins") or default_visit_mins)


def rederive_closing(itinerary, by_id, *, min_buffer_mins=MIN_BUFFER_MINS,
                     default_visit_mins=DEFAULT_VISIT_MINS):
    """Re-derive each timed row's closing_status.

    Scope: rows carrying BOTH a `time` and a `poi_id` that resolves in by_id,
    EXCEPT `slot: lodging` rows. Move rows and free-text meals (31 of 94 in the
    corpus) have no closing verdict to make and are not counted in `examined`.

    Why lodging is out of scope (C1, the final v0.33.0 whole-branch review).
    `run_gate` folds each stop's chosen lodging into `by_id` (the P4 rule,
    scripts/gate.py::poi_pool), so a timed lodging row resolves and this
    function used to demand `hours.close` or `hours.no_fixed_close` from it.
    There is nowhere legal to answer: schemas/accommodations.schema.json's
    candidate items are `additionalProperties: false` and declare no `hours`, so
    adding one fails validate_artifact with "Additional properties are not
    allowed ('hours' was unexpected)". The demand shipped unsatisfiable on 5 real
    consumer rows (2026-06-yilan 2, 2026-08-chiayi 3) whose only escape was
    deleting the row's `time` — destroying the arrival information.

    The cut is on `slot`, not on "did this id come only from the accommodations
    fold": 2 further corpus lodging rows (2026-07-sun-moon-lake `lealea`, `d2-2`)
    resolve through verified-pois.yaml because the consumer copied the hotels
    there, and they carry no `hours` either. A fold-membership cut would leave
    those two demanding a closing time from a hotel.

    Nothing is lost. The arrival-vs-reception check for lodging is a separate,
    already-shipped mechanism reading a field that DOES exist on the lodging
    schema: `scripts/facilities.py::reception_ok` against
    `reception: {close, late_checkin}`, owned by accommodation-research
    (skills/accommodation-research/SKILL.md:73-74) with its own stop condition.
    What this function transcribes is the visit/meal rule
    (skills/itinerary-synthesis/SKILL.md's `last_order` / `last_entry` plus a
    `need_mins` buffer), which has no meaning for a check-in — and none at all
    for chiayi's two CHECKOUT rows. Re-deriving `reception_ok` is a v0.34.0
    follow-up; it is a different verdict on a different field, not this one.

    hours.no_fixed_close is a recorded CLAIM, not a skip: an open-air place
    genuinely has no closing time, and demanding a fake 23:59 would then flow
    into the need_mins arithmetic as if it meant something.
    """
    out = Outcome()
    for day in (itinerary or {}).get("days") or []:
        date = day.get("date", "?")
        for j, row in enumerate(day.get("rows") or []):
            t, pid = row.get("time"), row.get("poi_id")
            if not t or not pid or pid not in (by_id or {}):
                continue
            if row.get("slot") == "lodging":
                continue
            out.found += 1
            hours = (by_id[pid].get("hours") or {})
            where = f"itinerary day {date} row {j} (poi {pid!r} @ {t})"
            if not hours.get("close") and not hours.get("no_fixed_close"):
                out.missing.append(
                    f"{where}: POI carries neither hours.close nor "
                    f"hours.no_fixed_close — closing_status is not re-derivable")
                continue
            if "closing_status" not in row:
                out.missing.append(
                    f"{where}: no recorded closing_status — the closing-buffer "
                    f"verdict is not re-derivable")
                continue
            if hours.get("no_fixed_close"):
                got, reason = "ok", ""
            else:
                got, reason = closing_status(
                    t, hours["close"], _last_call_for(row.get("slot"), hours),
                    _need_mins(hours, min_buffer_mins, default_visit_mins))
            out.compared += 1
            if row["closing_status"] != got:
                out.mismatches.append(
                    f"{where}: recorded closing_status {row['closing_status']!r} but "
                    f"hours.closing_status re-derives {got!r} ({reason or 'no reason'})")
    return out


def rederive_lodging(accommodations, *, local_lang=None):
    """Re-derive each lodging candidate's verify_status.

    accommodation-research calls classify_candidate directly and passes none of
    the arguments Part 1 added, so `operating`, `name_match` and `geocode_source`
    all take their permissive defaults and TW-062/TW-063 never applied to hotels.
    Re-derivation is the mechanical form: it reads what the artifact recorded
    rather than what the SKILL asked the agent to pass.

    Two gates are deliberately NOT re-derived here, and neither absence is
    silent:

      Gate 0 (operating) — schemas/accommodations.schema.json has no
      business_status field, so there is nothing to read. Closing it is a
      TW-063-sized change deferred to v0.34.0; `operating=True` here matches the
      permissive value the stage already uses, so this task changes nothing about
      it either way.

      Gates 3a/3b (conflict_detected, in_claimed_region) — both are computed by
      the agent at research time and the artifact records neither. Passing the
      permissive values is the only honest option; it means a region mismatch or
      a cross-source conflict is invisible to this function.

    Missing inputs go to the rederivable axis and the match comparison then runs
    BLIND to them, exactly as rederive_hops does for an absent duration_source —
    so a field that is new in this release cannot demote a candidate merely by
    being new.
    """
    out = Outcome()
    if accommodations is None:
        out.missing.append(
            "accommodations.yaml absent — classify_candidate verdicts are not re-derivable")
        return out
    for stop in accommodations.get("stops") or []:
        district = stop.get("district", "?")
        for cand in stop.get("candidates") or []:
            out.found += 1
            where = f"accommodations stop {district!r} candidate {cand.get('id', '?')!r}"
            gs = (cand.get("geocode") or {}).get("geocode_source")
            if not gs:
                out.missing.append(
                    f"{where}: no geocode.geocode_source — Gate 2c (centroid "
                    f"existence proof) is not re-derivable")
            resolved = cand.get("resolved_name")
            if not resolved:
                out.missing.append(
                    f"{where}: no resolved_name — Gate 2b (name match) is not "
                    f"re-derivable")
                name_match = True          # blind, per the docstring
            else:
                queried = cand.get("name_local") or cand.get("name_display") or ""
                name_match = name_matches(queried, resolved)
            got, note = classify_candidate(
                cand, geocoded=True, in_claimed_region=True, local_lang=local_lang,
                conflict_detected=False, operating=True, name_match=name_match,
                geocode_source=gs or "")
            out.compared += 1
            rec = cand.get("verify_status")
            if rec != got:
                out.mismatches.append(
                    f"{where}: recorded verify_status {rec!r} but classify_candidate "
                    f"re-derives {got!r} ({note})")
    return out


def _verify_status_of(poi, local_lang, resolved, as_of):
    """verify_poi against the record's own era. `as_of` None means there is no
    era to anchor to, in which case the verdict is superseded anyway and the
    date never reaches a comparison that matters."""
    return verify_poi(dict(poi), geocoded=bool(poi.get("geocode")),
                      in_claimed_region=True, local_lang=local_lang,
                      resolved_name=resolved, today=as_of)[1:]


def rederive_pois(pois, *, local_lang=None):
    """Re-derive each POI's recorded verify_status.

    The sixth axis, and the one 0.33.0 left out: verify_poi is the sole
    gatekeeper of the iron rule "only verified flows downstream", and the
    function whose rules changed most across 0.32.0 and 0.33.0 (Gate 0's sourced
    object, Gate 2b's refusal on an absent resolved_name, Gate 2c's existence
    proof). Three rules changed and no recorded verdict was ever re-examined.

    Scope is verified-pois records ONLY. Lodging candidates have their own axis
    (rederive_lodging) and must not be counted twice — so this takes the `pois`
    LIST, never gate.py's folded `by_id` pool.

    THE CLOCK IS ANCHORED TO THE ARTIFACT, not to wall-clock. The question asked
    is "was this verdict correct when it was written", using the record's own
    business_status.as_of era. OPERATING_MAX_AGE_DAYS is 90, so once consumers
    migrate to the object form — which is exactly what this release asks of them
    — a wall-clock read would turn a trip's gate red 91 days after verification
    with no artifact change. That is the calendar-driven class the 0.33.0
    CHANGELOG cited when deferring R5. Recency is a real concern and gets its own
    named signal in a later version; it is not silently dropped.

    Two gates are NOT re-derived here, and neither absence is silent: the
    artifact records neither `in_claimed_region` nor `conflict_detected`, so the
    permissive values are passed and Gates 3a/3b are invisible to this axis.
    Recording them was considered and rejected — each new agent-authored field is
    another self-attestation, which is the defect family this programme exists to
    shrink.

    Buckets are FIRST-APPLICABLE, in this order, so one record produces at most
    one failure and the consumer is pointed at the one thing to fix first:

      superseded  — the recorded verdict cannot stand because the rules that
                    produced it were superseded (today: a bare-string or absent
                    business_status, superseded by TW-063's object form)
      missing     — an input needed to recompute is absent from the artifact
                    (today: no resolved_name recorded at all)
      mismatches  — every input is present and the verdict does not follow

    The bucket is decided from the RECORDED INPUTS, never by string-matching
    verify_poi's note. 0.33.0's final review found a trip-authored value
    interpolated into a routed message could steer routing; a classifier that
    greps its own error strings has the same shape.
    """
    out = Outcome()
    for poi in pois or []:
        rec = poi.get("verify_status")
        if rec is None:
            continue
        out.found += 1
        pid = poi.get("id", "?")
        bs = poi.get("business_status")
        sourced = isinstance(bs, dict)
        as_of = _parse_iso(bs.get("as_of")) if sourced else None
        recorded_name = poi.get("resolved_name")
        resolved = (NO_RESOLVED_NAME if recorded_name == NO_RESULT_SENTINEL
                    else recorded_name)
        got, _note = _verify_status_of(poi, local_lang, resolved, as_of)
        if got == rec:
            out.compared += 1
            continue
        if not sourced:
            out.superseded.append(
                f"pois[{pid!r}]: recorded verify_status {rec!r} was produced under "
                f"superseded rules — business_status is not the sourced "
                f"{{status, source_url, as_of}} form, so the verdict cannot stand "
                f"today; re-run source-verify for this POI")
            continue
        if resolved is None:
            out.missing.append(
                f"pois[{pid!r}]: no resolved_name recorded — Gate 2b (name match) "
                f"is not re-derivable; record the geocoder's display_name, or "
                f"NO_RESULT to state the lookup ran and found none")
            continue
        out.compared += 1
        out.mismatches.append(
            f"pois[{pid!r}]: recorded verify_status {rec!r} but verify_poi "
            f"re-derives {got!r} from the inputs this artifact carries")
    return out


def run_rederivation(itinerary, by_id, *, legs=None, routing=None, cost=None,
                     trip_brief=None, accommodations=None, pois=None):
    """Return {"checks": [verdicts_match, verdicts_rederivable,
    verdicts_rule_current], "failures": [...]}.

    `examined` is deliberately two different numbers: rederivable.examined counts
    every verdict-bearing record found, match.examined only the subset with
    complete inputs. Their difference is how many records the input gaps hid.

    verdicts_rule_current.examined is deliberately the POI axis's OWN found
    count, not total.found: total.found also carries legs/hops/cost/closing/
    lodging records, none of which can ever land in `superseded` (only
    rederive_pois populates that bucket), so reusing total.found here would
    inflate the denominator with records this check cannot possibly speak to.
    """
    total = Outcome()
    total.merge(rederive_legs(
        legs, max_single_drive_mins=_brief_num(trip_brief, "routing",
                                               "max_single_drive_mins",
                                               MAX_SINGLE_DRIVE_MINS)))
    total.merge(rederive_hops(
        routing, max_hop_mins=_brief_num(trip_brief, "routing", "max_hop_mins",
                                         MAX_HOP_MINS)))
    total.merge(rederive_cost(cost))
    total.merge(rederive_closing(
        itinerary, by_id,
        min_buffer_mins=_brief_num(trip_brief, "scheduling", "min_buffer_mins",
                                   MIN_BUFFER_MINS),
        default_visit_mins=_brief_num(trip_brief, "scheduling", "default_visit_mins",
                                      DEFAULT_VISIT_MINS)))
    total.merge(rederive_lodging(
        accommodations,
        local_lang=((trip_brief or {}).get("destination") or {}).get("local_lang")))
    poi_outcome = rederive_pois(
        pois, local_lang=((trip_brief or {}).get("destination") or {}).get("local_lang"))
    total.merge(poi_outcome)
    return {
        "checks": [
            {"name": "verdicts_match", "passed": not total.mismatches,
             "examined": total.compared},
            {"name": "verdicts_rederivable", "passed": not total.missing,
             "examined": total.found},
            # Third axis, 0.34.0. A verdict produced under superseded rules is
            # neither wrong-on-its-inputs nor missing-an-input; folding it into
            # either would misreport 105 of 127 corpus records. examined uses
            # poi_outcome.found (see docstring), not total.found.
            {"name": "verdicts_rule_current", "passed": not total.superseded,
             "examined": poi_outcome.found},
        ],
        "failures": total.mismatches + total.missing + total.superseded,
    }
