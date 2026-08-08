"""Verdict re-derivation — recompute every recorded mechanical verdict from the
inputs the artifact carries, and prove the inputs are there to recompute it with.

tripwork owns a shelf of pure decision functions (classify_leg, classify_hop,
sum_costs, closing_status). Until now nothing ran them against a FINISHED
artifact: the agent was trusted to call them and transcribe the answer. Dogfood
2026-08 showed what that buys — routing.yaml hop flags typed by hand, a
gate-report with 13 green checks, and a user catching the errors by eye.

Two orthogonal axes, both emitted as named checks with an examined:N count:
  verdicts_match        — recorded verdict == recomputed verdict
  verdicts_rederivable  — every verdict-bearing record carries the inputs needed

A record whose inputs are MISSING is a verdicts_rederivable FAILURE, never a
skip. A skipped record is indistinguishable from a green one, which is the exact
defect class this module exists to close (cf. scripts/gate.py:151-155, where an
absent advisory is a failure rather than a skipped check).

What this proves and what it does not: re-derivation proves a verdict follows
from the recorded numbers. It never proves the numbers are real. min_plausible_mins
is computed over agent-authored cluster centroids that TW-062 shows can be
fictions; sum_costs proves the total follows from the line items, never that a
line item is a real price.
"""
from scripts.cost import sum_costs
from scripts.distance import classify_hop, haversine_km
from scripts.legs import classify_leg

# Plugin defaults, overridable only from trip-brief. Deliberately NOT recorded
# per-record: a per-leg threshold would let an agent widen the cap to clear its
# own verdict.
MAX_SINGLE_DRIVE_MINS = 300
MAX_HOP_MINS = 60
COST_TOL = 0.005


class Outcome:
    """(mismatch failures, missing-input failures, records found, records compared)."""

    __slots__ = ("mismatches", "missing", "found", "compared")

    def __init__(self):
        self.mismatches, self.missing = [], []
        self.found = self.compared = 0

    def merge(self, other):
        self.mismatches += other.mismatches
        self.missing += other.missing
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
             for c in (routing or {}).get("clusters", []) if c.get("centroid")}
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
            if got == "unsourced":
                got = "ok"
        out.compared += 1
        rec = hop.get("flag")
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


def run_rederivation(itinerary, by_id, *, legs=None, routing=None, cost=None,
                     trip_brief=None):
    """Return {"checks": [verdicts_match, verdicts_rederivable], "failures": [...]}.

    `examined` is deliberately two different numbers: rederivable.examined counts
    every verdict-bearing record found, match.examined only the subset with
    complete inputs. Their difference is how many records the input gaps hid.
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
    return {
        "checks": [
            {"name": "verdicts_match", "passed": not total.mismatches,
             "examined": total.compared},
            {"name": "verdicts_rederivable", "passed": not total.missing,
             "examined": total.found},
        ],
        "failures": total.mismatches + total.missing,
    }
