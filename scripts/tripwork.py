"""The single entry point for every tripwork script (v2.0.0).

    python <plugin>/scripts/tripwork.py <command> <slug> [more arguments]

Run it from the workspace root (the folder holding trips/). It fills in the
conventional arguments -- trips/<slug>, --work-dir work/<slug> -- and calls the
target script's own main(); everything after the slug goes to that script
unchanged, so no flag of any script is declared here a second time.

Exit codes are the target's: 0 pass / 1 fail / 2 usage error.
"""
import importlib
import pathlib
import sys

USAGE = {
    "next": ("<slug>", "print the next pipeline stage (the orchestrator's oracle)"),
    "verify": ("<slug> [--offline] [--regeocode] [--official-domain SUFFIX ...]",
               "source-verify: write data/verified-pois.yaml from data/candidates.yaml"),
    "gate": ("<slug>", "itinerary gate: write work/<slug>/gate-report.yaml"),
    "export": ("<slug>", "render the md + html deliverables (needs a fresh passing gate)"),
    "export-gate": ("<slug>", "export gate: write work/<slug>/export-gate-report.yaml"),
    "maps": ("<slug> [--offline]", "day maps from OpenStreetMap tiles: data/day-maps.yaml"),
    "photos": ("<slug> [--backend none|wiki] [--dry-run]",
               "licensed landmark photos into data/verified-pois-media.yaml (default --backend wiki)"),
    "picker": ("<slug> ['<reply>']", "write the title picker page; with a reply, apply the picks"),
    "validate": ("<slug> [artifact]", "schema-check one artifact, or every one in data/"),
    "fingerprint": ("<slug> <projection>", "print the input fingerprint of trip-brief.yaml (projection: advisory)"),
    "publish": ("<slug> [--share-base URL]",
                "build the locked family page (password: TRIPWORK_PUBLISH_PASSWORD='…' prefix, asked each time)"),
    "deploy": ("<slug> --project NAME --confirm", "upload the locked pages to Cloudflare Pages (after the user's yes)"),
    "migrate": ("[<slug>] [--apply]", "move pre-v1.0 trips to the v1.0 layout (dry run without --apply)"),
}


class UsageError(Exception):
    """A bad invocation of tripwork.py itself (exit 2)."""


def _trip(slug):
    return f"trips/{slug}"


def _work(slug):
    return f"work/{slug}"


def _validate(slug, rest):
    if rest and not rest[0].startswith("-"):
        name = rest[0] if rest[0].endswith(".yaml") else rest[0] + ".yaml"
        return [("scripts.validate_artifact", [f"{_trip(slug)}/data/{name}", *rest[1:]])]
    from scripts.paths import is_legacy_layout
    if is_legacy_layout(_trip(slug)):
        raise UsageError(f"pre-v1.0 trip layout — run `python <plugin>/scripts/tripwork.py migrate {slug}` "
                         f"(dry run), then with --apply")
    data = pathlib.Path(_trip(slug)) / "data"
    found = sorted(data.glob("*.yaml"))
    if not found:
        raise UsageError(f"no artifacts in {_trip(slug)}/data to validate")
    return [("scripts.validate_artifact", [f"{_trip(slug)}/data/{p.name}", *rest]) for p in found]


def _picker(slug, rest):
    if rest and not rest[0].startswith("-"):
        return [("scripts.title_picks", [_trip(slug), *rest])]
    return [("scripts.title_picker", [_trip(slug), "--work-dir", _work(slug), *rest])]


def _photos(slug, rest):
    backend = [] if any(a == "--backend" or a.startswith("--backend=") for a in rest) else ["--backend", "wiki"]
    return [("scripts.photo_adapter", [_trip(slug), *backend, *rest])]


def _with_work(module):
    return lambda slug, rest: [(module, [_trip(slug), "--work-dir", _work(slug), *rest])]


COMMANDS = {
    "next": _with_work("scripts.next_stage"),
    "verify": _with_work("scripts.source_verify_run"),
    "gate": _with_work("scripts.gate"),
    "export": _with_work("scripts.export"),
    "export-gate": _with_work("scripts.export_gate"),
    "maps": _with_work("scripts.day_maps"),
    "photos": _photos,
    "picker": _picker,
    "validate": _validate,
    "fingerprint": lambda slug, rest: [("scripts.input_fingerprint", [f"{_trip(slug)}/data/trip-brief.yaml", *rest])],
    "publish": lambda slug, rest: [("scripts.publish", ["build", _trip(slug), *rest])],
    "deploy": lambda slug, rest: [("scripts.publish", ["deploy", _trip(slug), *rest])],
    "migrate": lambda slug, rest: [("scripts.migrate_v1", [_trip(slug) if slug else "trips", *rest])],
}


def resolve_slug(raw):
    """`trips/<slug>/` or `<slug>` -> `<slug>`; anything that is not one plain path
    segment (empty, `.`, `..`, a separator, an absolute path, a leading `-`) is refused."""
    s = raw[len("trips/"):] if raw.startswith("trips/") else raw
    s = s.rstrip("/")
    if (not s or s in (".", "..") or "/" in s or "\\" in s or s.startswith("-")
            or pathlib.PurePath(s).is_absolute()):
        raise UsageError(f"not a trip slug: {raw!r} (give the folder name under trips/)")
    return s


def _table():
    lines = ["usage: python <plugin>/scripts/tripwork.py <command> <slug> [arguments]",
             "run it from the workspace root (the folder with trips/)", ""]
    lines += [f"  {name:<12} {args}\n  {'':<12} {what}" for name, (args, what) in USAGE.items()]
    return "\n".join(lines)


def _command_help(cmd):
    args, what = USAGE[cmd]
    return f"usage: python <plugin>/scripts/tripwork.py {cmd} {args}\n\n{what}"


def _call(module, argv, cmd):
    mod = importlib.import_module(module)
    saved = sys.argv[0]
    sys.argv[0] = f"tripwork.py {cmd}"                  # argparse names the command, not the file
    try:
        return mod.main(argv)
    except SystemExit as exc:                           # argparse usage errors
        return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    finally:
        sys.argv[0] = saved


def main(argv):
    if not argv:
        print(_table(), file=sys.stderr)
        return 2
    if "-h" in argv or "--help" in argv:
        print(_command_help(argv[0]) if argv[0] in COMMANDS else _table())
        return 0
    cmd, rest = argv[0], list(argv[1:])
    if cmd not in COMMANDS:
        print(f"unknown command {cmd!r}\n\n{_table()}", file=sys.stderr)
        return 2
    try:
        if cmd != "next" and not pathlib.Path("trips").is_dir():
            raise UsageError("no trips/ here — run tripwork.py from the workspace root (the folder with trips/)")
        if cmd == "migrate":
            slug = resolve_slug(rest.pop(0)) if rest and not rest[0].startswith("-") else None
        else:
            if not rest:
                raise UsageError(f"{cmd} needs a <slug>\n\n{_command_help(cmd)}")
            slug = resolve_slug(rest.pop(0))
        # `next` alone may name a trip that does not exist yet: a new request binds a
        # fresh slug (orchestrator rule 0.5) and the oracle routes it to rule 0 / 1.
        if slug and cmd != "next" and not pathlib.Path(_trip(slug)).is_dir():
            raise UsageError(f"no trip folder {_trip(slug)}")
        calls = COMMANDS[cmd](slug, rest)
    except UsageError as exc:
        print(f"tripwork.py: {exc}", file=sys.stderr)
        return 2
    codes = [_call(module, args, cmd) for module, args in calls]
    return max(codes, default=0)


def _fix_sys_path():
    """Python put this file's directory first on sys.path; that directory is a package,
    not a module root, so take every copy of it out and put the repo root first --
    `from scripts.X import ...` then resolves from any cwd, with or without -P."""
    here = pathlib.Path(__file__).resolve().parent
    sys.path[:] = [p for p in sys.path if pathlib.Path(p or ".").resolve() != here]
    sys.path.insert(0, str(here.parent))


if __name__ == "__main__":
    _fix_sys_path()
    import os
    if os.environ.get("TRIPWORK_DEBUG_IMPORT"):
        import scripts
        print(f"tripwork: scripts from {pathlib.Path(scripts.__file__).resolve().parent}", file=sys.stderr)
    raise SystemExit(main(sys.argv[1:]))
