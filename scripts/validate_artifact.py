"""Runtime schema validator CLI for tripwork trip artifacts.

Every stage SKILL's "validate against the schema" step runs this instead of
improvising jsonschema glue. Exit codes: 0 pass / 1 schema fail / 2 usage error
(missing file, YAML parse error, unmapped basename without --schema).
"""
import argparse
import json
import pathlib
import sys

import jsonschema
import yaml

SCHEMAS = pathlib.Path(__file__).resolve().parent.parent / "schemas"

SCHEMA_BY_BASENAME = {
    "trip-brief.yaml": "trip-brief.schema.json",
    "candidates.yaml": "candidates.schema.json",
    "verified-pois.yaml": "verified-pois.schema.json",
    "verified-pois-media.yaml": "verified-pois-media.schema.json",
    "routing.yaml": "routing.schema.json",
    "accommodations.yaml": "accommodations.schema.json",
    "legs.yaml": "legs.schema.json",
    "calendar.yaml": "calendar.schema.json",
    "seasonal.yaml": "seasonal.schema.json",
    "transit.yaml": "transit.schema.json",
    "cost.yaml": "cost.schema.json",
    "advisory.yaml": "advisory.schema.json",
    "itinerary.yaml": "itinerary.schema.json",
    "gate-report.yaml": "gate-report.schema.json",
    "export-gate-report.yaml": "gate-report.schema.json",  # shared shape
    "stage-state.yaml": "stage-state.schema.json",
}


def validate_file(artifact_path, schema_path=None):
    """Validate one YAML artifact. Returns (exit_code, messages)."""
    p = pathlib.Path(artifact_path)
    if not p.is_file():
        return 2, [f"no such file: {p}"]
    if schema_path is None:
        name = SCHEMA_BY_BASENAME.get(p.name)
        if name is None:
            return 2, [f"unknown artifact basename '{p.name}'; pass --schema explicitly"]
        schema_path = SCHEMAS / name
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return 2, [f"YAML parse error in {p}: {exc}"]
    schema = json.loads(pathlib.Path(schema_path).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        return 1, [
            f"{'/'.join(str(x) for x in e.absolute_path) or '.'}: {e.message}"
            for e in errors
        ]
    return 0, [f"PASS {p}"]


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("artifact", help="path to a trips/<slug>/*.yaml artifact")
    ap.add_argument("--schema", default=None, help="explicit schema path override")
    args = ap.parse_args(argv)
    code, msgs = validate_file(args.artifact, args.schema)
    stream = sys.stdout if code == 0 else sys.stderr
    for m in msgs:
        print(m, file=stream)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
