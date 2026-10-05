"""Stage-selection oracle: prints the next tripwork stage for a trip dir.

Implements the orchestrator SKILL's Stage Selection rules 0-16 (the SKILL prose
is the spec; this script is its executable form). ADVISORY ORACLE ONLY — it
suggests; stop-on-confirmation, slug binding (rule 0.5) and user interaction
stay with the agent. It does not read stage-state.yaml (v1).

Usage: python <plugin>/scripts/tripwork.py next <slug>
Output (stdout, YAML): {next: tripwork:<skill>|complete|stop-and-ask, reason: str}
"""
if __name__ == "__main__":
    raise SystemExit("moved in tripwork 2.0: python <plugin>/scripts/tripwork.py next <slug>")


import argparse
import pathlib

import yaml

from scripts.paths import (artifact_path, deliverable_paths, is_legacy_layout,
                           report_path)
from scripts.orchestration import (ADVISORY_PROJECTION, EXPORT_DELIVERABLES,
                                    EXPORT_GATE_INPUTS, GATE_INPUTS,
                                    REQUIRED_DELIVERABLE, candidates_stale,
                                    input_fingerprint, route_gate_failures)
from scripts.validate_artifact import validate_file

# (artifact, producing stage, rule tag) in pipeline order — advisory moved to
# rule 1.5 (D4: a banned regulation must surface before any research is spent).
_CHAIN = [
    ("trip-brief.yaml", "tripwork:trip-brief", "rule 1"),
    ("advisory.yaml", "tripwork:travel-advisory", "rule 1.5"),
    ("candidates.yaml", "tripwork:destination-research", "rule 2"),
    ("verified-pois.yaml", "tripwork:source-verify", "rule 3"),
    ("routing.yaml", "tripwork:routing-audit", "rule 4"),
    ("accommodations.yaml", "tripwork:accommodation-research", "rule 5"),
    ("legs.yaml", "tripwork:inter-stop-legs", "rule 6"),
    ("calendar.yaml", "tripwork:calendar-check", "rule 7"),
    ("seasonal.yaml", "tripwork:seasonal-advisory", "rule 8"),
    ("transit.yaml", "tripwork:transit-detail", "rule 9"),
    ("cost.yaml", "tripwork:cost-rollup", "rule 10"),
]


def _load(path):
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (FileNotFoundError, yaml.YAMLError):
        return {}
    # A truncated report can parse as a bare YAML scalar; degrade to {} so it
    # flows into the unreadable/invalid-report branch instead of crashing.
    return doc if isinstance(doc, dict) else {}


def _ready(path):
    return path.is_file() and validate_file(path)[0] == 0


def _newer(a, b):
    return a.stat().st_mtime > b.stat().st_mtime


def gate_report_stale(trip_dir, work_dir):
    """What makes work/<slug>/gate-report.yaml unusable: ["gate-report.yaml"] when it
    does not exist, else every GATE_INPUTS artifact newer than it (rule 13; `export`
    refuses on the same answer)."""
    t, w = pathlib.Path(trip_dir), pathlib.Path(work_dir)
    gr = report_path(w, "gate-report.yaml")
    if not gr.is_file():
        return ["gate-report.yaml"]
    return [n for n in GATE_INPUTS if artifact_path(t, n).is_file() and _newer(artifact_path(t, n), gr)]


def next_stage(trip_dir, work_dir):
    t = pathlib.Path(trip_dir)
    w = pathlib.Path(work_dir)

    # rule 0 — preflight stamp lives at the work ROOT, not work/<slug>/
    if not (w.parent / ".preflight-completed").is_file():
        return ("tripwork:workspace-shape-preflight",
                "rule 0: work/.preflight-completed missing")

    # rule 0.7 (v1.0) -- a pre-v1.0 trip keeps its artifacts at the trip root.
    # Every rule below reads data/, so running on the old layout would look like
    # "no trip-brief.yaml" and restart the pipeline over a finished trip.
    if is_legacy_layout(t):
        return ("stop-and-ask",
                "rule 0.7: pre-v1.0 trip layout — run `python <plugin>/scripts/tripwork.py "
                f"migrate {t.name}` (dry run), then with --apply, and resume")

    for name, skill, rule in _CHAIN:
        p = artifact_path(t, name)
        if not p.is_file():
            return skill, f"{rule}: no {name}"
        if name == "verified-pois.yaml":
            if not _ready(p) or not any(
                    q.get("verify_status") == "verified"
                    for q in _load(p).get("pois") or []):
                return skill, (f"{rule}: verified-pois not ready "
                               "(schema-invalid or 0 verified)")
            cand = artifact_path(t, "candidates.yaml")
            cand_ids = [c.get("id") for c in _load(cand).get("candidates") or []]
            ver_ids = [q.get("id") for q in _load(p).get("pois") or []]
            if candidates_stale(cand_ids, ver_ids) or _newer(cand, p):
                return skill, f"{rule}: verified-pois stale w.r.t. candidates"
        elif not _ready(p):
            return skill, f"{rule}: {name} exists but is not schema-valid"

    # rule 11 — advisory freshness anchors on the BRIEF's destination/dates/airline,
    # compared by CONTENT not mtime. The old whole-file mtime compare made every
    # must_do edit re-run travel-advisory, and the only way to satisfy it was to
    # rewrite a byte-identical advisory — training the agent to touch files to
    # clear an oracle, which is exactly what rules 13 and 15 must not tolerate.
    adv = _load(artifact_path(t, "advisory.yaml"))
    brief_doc = _load(artifact_path(t, "trip-brief.yaml"))
    recorded = (adv.get("input_fingerprints") or {}).get("trip-brief.yaml")
    if recorded is None:
        # No fingerprint: this advisory predates the mechanism. Rule 11 is the
        # gate that surfaces a `banned` regulation, so fall back to mtime rather
        # than fail open.
        if _newer(artifact_path(t, "trip-brief.yaml"), artifact_path(t, "advisory.yaml")):
            return ("tripwork:travel-advisory",
                    "rule 11: advisory has no input fingerprint and the brief is newer")
    elif recorded != input_fingerprint(brief_doc, ADVISORY_PROJECTION):
        return ("tripwork:travel-advisory",
                "rule 11: advisory stale (destination/dates/airline changed since it ran)")

    # rule 12 — marker is the CANONICAL itinerary.yaml (not the derived .md)
    itin = artifact_path(t, "itinerary.yaml")
    if not itin.is_file():
        return "tripwork:itinerary-synthesis", "rule 12: no itinerary.yaml"
    if not _ready(itin):
        return ("tripwork:itinerary-synthesis",
                "rule 12: itinerary.yaml exists but is not schema-valid")

    # rule 13 — the gate report must be newer than EVERY artifact the gate reads.
    # Comparing against itinerary.yaml alone let a re-verify that demoted a
    # scheduled POI leave the oracle reporting 'complete' on a report that never
    # saw it. This fires for real on the live corpus, not just a hypothetical
    # (see skills/orchestrator/SKILL.md's rule 13 note for a named example).
    gr = report_path(w, "gate-report.yaml")
    stale_inputs = gate_report_stale(t, w)
    if stale_inputs:
        named = [n for n in stale_inputs if n != "gate-report.yaml"]
        why = f" ({', '.join(named)} newer)" if named else ""
        return ("tripwork:itinerary-gate", f"rule 13: gate-report missing or stale{why}")

    # rule 13.5
    report = _load(gr)
    if report.get("status") not in ("pass", "fail"):
        return ("tripwork:itinerary-gate",
                "rule 13: gate-report unreadable/invalid — re-run the gate")
    if report.get("status") == "fail":
        target = route_gate_failures(report.get("failures") or [])
        return target, f"rule 13.5: gate fail routes to {target}"

    # rule 14 — the required deliverable is named explicitly (REQUIRED_DELIVERABLE),
    # not positionally picked from EXPORT_DELIVERABLES: the HTML deliverable is
    # optional in shipped semantics (export_gate.py only reads it `if
    # html_path.is_file()`), so a `deliverables[0]` index would silently change
    # which file rule 14 requires if EXPORT_DELIVERABLES' declaration order ever
    # changed.
    try:
        paths = deliverable_paths(t, brief_doc)
    except (KeyError, TypeError, ValueError):
        return ("tripwork:trip-brief",
                "rule 14: trip-brief has no usable short_name/dates to name the deliverables")
    deliverables = [paths[k] for k in EXPORT_DELIVERABLES]
    md = paths[REQUIRED_DELIVERABLE]
    if not md.is_file():
        return "tripwork:export-artifact", "rule 14: no export deliverable"

    # rule 15 — same widening as rule 13: the export-gate report must be newer
    # than EVERY deliverable export_gate.py judges (md + html, TW-077) AND
    # every artifact export_gate.py reads.
    egr = report_path(w, "export-gate-report.yaml")
    stale_deliverables = [d.name for d in deliverables
                          if d.is_file() and egr.is_file() and _newer(d, egr)]
    stale_inputs = [n for n in EXPORT_GATE_INPUTS
                    if artifact_path(t, n).is_file() and _newer(artifact_path(t, n), egr)] \
        if egr.is_file() else []
    if not egr.is_file() or stale_deliverables or stale_inputs:
        names = list(stale_deliverables) + stale_inputs
        why = f" ({', '.join(names)} newer)" if names else ""
        return ("tripwork:export-gate", f"rule 15: export-gate-report missing or stale{why}")
    ereport = _load(egr)
    if ereport.get("status") not in ("pass", "fail"):
        return ("tripwork:export-gate",
                "rule 15: export-gate-report unreadable/invalid — "
                "re-run the gate")
    if ereport.get("status") == "fail":
        if ereport.get("retryable", True):
            return ("tripwork:itinerary-synthesis",
                    "rule 15: retryable render defect — fix the source text the "
                    "export-gate names, then gate and export again")
        if ereport.get("repeat_of_previous"):
            return ("stop-and-ask",
                    "rule 15: the same export-gate failure came back after the source was "
                    "fixed once — likely a plugin render defect; report it")
        return ("stop-and-ask",
                "rule 15: non-retryable data defect — fix the data "
                "(attribution / official source), then re-verify")

    # rule 16
    reason = "rule 16: export-gate pass — pipeline complete"
    if ereport.get("distributable") is False:
        reason += " — non-distributable (勿散布)"
    return "complete", reason


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("trip_dir", help="trips/<slug> directory")
    ap.add_argument("--work-dir", required=True, help="work/<slug> directory")
    args = ap.parse_args(argv)
    nxt, reason = next_stage(args.trip_dir, args.work_dir)
    print(yaml.safe_dump({"next": nxt, "reason": reason},
                         allow_unicode=True, sort_keys=False), end="")
    return 0
