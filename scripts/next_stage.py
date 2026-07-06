"""Stage-selection oracle: prints the next tripwork stage for a trip dir.

Implements the orchestrator SKILL's Stage Selection rules 0-16 (the SKILL prose
is the spec; this script is its executable form). ADVISORY ORACLE ONLY — it
suggests; stop-on-confirmation, slug binding (rule 0.5) and user interaction
stay with the agent. It does not read stage-state.yaml (v1).

Usage: python scripts/next_stage.py <trip-dir> --work-dir <work/<slug>>
Output (stdout, YAML): {next: tripwork:<skill>|complete|stop-and-ask, reason: str}
"""
import sys as _sys
import pathlib as _pathlib
if __name__ == "__main__" and __package__ in (None, ""):
    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent.parent))

import argparse
import pathlib

import yaml

from scripts.orchestration import candidates_stale, route_gate_failures
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
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (FileNotFoundError, yaml.YAMLError):
        return {}


def _ready(path):
    return path.is_file() and validate_file(path)[0] == 0


def _newer(a, b):
    return a.stat().st_mtime > b.stat().st_mtime


def next_stage(trip_dir, work_dir):
    t = pathlib.Path(trip_dir)
    w = pathlib.Path(work_dir)
    slug = t.resolve().name

    # rule 0 — preflight stamp lives at the work ROOT, not work/<slug>/
    if not (w.parent / ".preflight-completed").is_file():
        return ("tripwork:workspace-shape-preflight",
                "rule 0: work/.preflight-completed missing")

    for name, skill, rule in _CHAIN:
        p = t / name
        if not p.is_file():
            return skill, f"{rule}: no {name}"
        if name == "verified-pois.yaml":
            if not _ready(p) or not any(
                    q.get("verify_status") == "verified"
                    for q in _load(p).get("pois") or []):
                return skill, (f"{rule}: verified-pois not ready "
                               "(schema-invalid or 0 verified)")
            cand = t / "candidates.yaml"
            cand_ids = [c.get("id") for c in _load(cand).get("candidates") or []]
            ver_ids = [q.get("id") for q in _load(p).get("pois") or []]
            if candidates_stale(cand_ids, ver_ids) or _newer(cand, p):
                return skill, f"{rule}: verified-pois stale w.r.t. candidates"
        elif not _ready(p):
            return skill, f"{rule}: {name} exists but is not schema-valid"

    # rule 11 — advisory freshness anchor is the BRIEF (destination/dates/airline
    # changes invalidate regulations); deliberately NOT the itinerary, which is
    # rewritten by every synthesis run and would loop advisory research.
    if _newer(t / "trip-brief.yaml", t / "advisory.yaml"):
        return ("tripwork:travel-advisory",
                "rule 11: advisory stale (trip-brief re-written after it)")

    # rule 12 — marker is the CANONICAL itinerary.yaml (not the derived .md)
    itin = t / "itinerary.yaml"
    if not itin.is_file():
        return "tripwork:itinerary-synthesis", "rule 12: no itinerary.yaml"
    if not _ready(itin):
        return ("tripwork:itinerary-synthesis",
                "rule 12: itinerary.yaml exists but is not schema-valid")

    # rule 13
    gr = t / "gate-report.yaml"
    if not gr.is_file() or _newer(itin, gr):
        return ("tripwork:itinerary-gate",
                "rule 13: gate-report missing or older than itinerary.yaml")

    # rule 13.5
    report = _load(gr)
    if report.get("status") == "fail":
        target = route_gate_failures(report.get("failures") or [])
        return target, f"rule 13.5: gate fail routes to {target}"

    # rule 14
    md = t / "exports" / f"{slug}-itinerary.md"
    if not md.is_file():
        return "tripwork:export-artifact", "rule 14: no export deliverable"

    # rule 15
    egr = t / "export-gate-report.yaml"
    if not egr.is_file() or _newer(md, egr):
        return ("tripwork:export-gate",
                "rule 15: export-gate-report missing or older than deliverable")
    ereport = _load(egr)
    if ereport.get("status") == "fail":
        if ereport.get("retryable", True):
            return ("tripwork:export-artifact",
                    "rule 15: retryable render defect — re-render")
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


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv[1:]))
