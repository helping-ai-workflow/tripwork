"""export-artifact's renderer: write trips/<slug>/<stem>.md and <stem>.html (v2.0.0).

    python <plugin>/scripts/tripwork.py export <slug>

Renders from scripts/trip_inputs.py::trip_inputs -- the same inputs publish renders
from and export-gate judges against -- so nothing is assembled by hand. Refuses,
writing nothing, when the trip is still in the pre-v1.0 layout (exit 2, migrate
first), when an input is missing (exit 2), or when work/<slug>/gate-report.yaml is
missing, not a pass, or older than an artifact the gate reads (exit 1, run the gate
first). Both files are rendered in memory and written only if both succeed.
"""
if __name__ == "__main__":
    raise SystemExit("moved in tripwork 2.0: python <plugin>/scripts/tripwork.py export <slug>")

import argparse
import pathlib
import sys

import yaml

from scripts.next_stage import gate_report_stale
from scripts.paths import deliverable_paths, is_legacy_layout, report_path, work_dir_for
from scripts.render.html_page import render_html_page
from scripts.render.markdown import render_markdown_page
from scripts.trip_inputs import TripInputError, trip_inputs

_TOOL = "python <plugin>/scripts/tripwork.py"


def _refuse(code, msg):
    print(msg, file=sys.stderr)
    return code


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("trip_dir")
    ap.add_argument("--work-dir", default=None)
    args = ap.parse_args(argv)
    t = pathlib.Path(args.trip_dir)
    w = pathlib.Path(args.work_dir) if args.work_dir else work_dir_for(t)
    slug = t.name

    if is_legacy_layout(t):
        return _refuse(2, f"pre-v1.0 trip layout — run `{_TOOL} migrate {slug}` (dry run), "
                          f"then with --apply, and export again")
    try:
        itin, poi_map, kwargs, _ = trip_inputs(t)
    except TripInputError as exc:
        return _refuse(2, str(exc))
    try:
        paths = deliverable_paths(t, kwargs["brief"] or {})
    except (KeyError, TypeError, ValueError) as exc:
        return _refuse(2, f"trip-brief has no usable short_name/dates to name the deliverables: {exc!r}")

    stale = gate_report_stale(t, w)
    if stale:
        what = ("there is no gate report" if stale == ["gate-report.yaml"]
                else f"the gate report is older than {', '.join(stale)}")
        return _refuse(1, f"{what} — run `{_TOOL} gate {slug}` first")
    status = (yaml.safe_load(report_path(w, "gate-report.yaml").read_text(encoding="utf-8")) or {}).get("status")
    if status != "pass":
        return _refuse(1, f"the gate did not pass (status: {status}) — fix what "
                          f"`{_TOOL} gate {slug}` lists, then export")

    md = render_markdown_page(itin, poi_map, kwargs["cost"], brief=kwargs["brief"])
    html = render_html_page(itin, poi_map, build="check", **kwargs)
    paths["md"].write_text(md, encoding="utf-8")
    paths["html"].write_text(html, encoding="utf-8")
    print(f"md: {paths['md']}")
    print(f"html: {paths['html']}")
    return 0
