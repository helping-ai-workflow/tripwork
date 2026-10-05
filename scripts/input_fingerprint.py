"""CLI: print the content fingerprint of a projected upstream artifact.

`skills/travel-advisory/SKILL.md`'s "Record `input_fingerprints`" step used to
compute this value via `python -c "import yaml,sys; from scripts.orchestration
import input_fingerprint, ADVISORY_PROJECTION; ..."`. That only resolves when
the current working directory's `scripts/` package happens to be the
plugin's — true inside the plugin repo, never in the one place the
instruction is actually executed: a consumer workspace, whose own `scripts/`
is unrelated to the plugin's. There it raises ModuleNotFoundError, silently,
end to end (the agent has no CLI-shaped fallback and just omits the field).

Every script instruction in this plugin is `python <plugin>/scripts/tripwork.py
<command> <slug>`, invocable regardless of cwd — a `python -c` import cannot be.
This module is the `fingerprint` command's target.

Usage: python <plugin>/scripts/tripwork.py fingerprint <slug> <projection>
Prints the fingerprint to stdout. <projection> selects which fields are
hashed (scripts/orchestration.py::input_fingerprint); the only one defined
today is `advisory` (ADVISORY_PROJECTION = destination/dates/airline, rule 11's
staleness anchor).
"""
if __name__ == "__main__":
    raise SystemExit("moved in tripwork 2.0: python <plugin>/scripts/tripwork.py fingerprint <slug> advisory")

import sys as _sys

import argparse
import pathlib

import yaml

from scripts.orchestration import ADVISORY_PROJECTION, input_fingerprint

# Named projections a caller may request. Keyed by a stable short name so the
# SKILL.md instruction and this CLI cannot drift out of sync with which tuple
# ADVISORY_PROJECTION (or any future projection) actually is.
PROJECTIONS = {
    "advisory": ADVISORY_PROJECTION,
}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("trip_brief", help="path to trips/<slug>/data/trip-brief.yaml")
    ap.add_argument("projection", choices=sorted(PROJECTIONS),
                     help="which projection to hash")
    args = ap.parse_args(argv)
    p = pathlib.Path(args.trip_brief)
    if not p.is_file():
        print(f"no such file: {p}", file=_sys.stderr)
        return 2
    try:
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"YAML parse error in {p}: {exc}", file=_sys.stderr)
        return 2
    print(input_fingerprint(doc, PROJECTIONS[args.projection]))
    return 0
