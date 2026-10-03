"""Migrate pre-v1.0 trip folders to the v1.0 layout (spec §5.3).

    python scripts/migrate_v1.py <trips-root | trips/<slug>> [--work-root DIR] [--apply]

Dry run by default: prints every move and every note, touches nothing. --apply
performs them. Idempotent, and it finishes a half-done migration: a trip is done
only when no artifact is left at its root. Nothing is deleted or overwritten --
old deliverables (exports/, the root itinerary.md, an old report whose work/ copy
already exists) go to data/legacy-exports/, renamed when two share a name.

It moves files; it does not rewrite them. Inline `▸` rows and a trip-level
`contingency` are LISTED, not converted: attaching a ▸ row by its position is the
signal spec §4.4 names as wrong (trip-e D5), while the v1.0 gate's `legacy …`
classes route both to itinerary-synthesis, which reads the text. short_name,
headline and themes are likewise left to the stages that write them.
"""
if __name__ == "__main__" and __package__ in (None, ""):
    import pathlib as _bootpath, sys as _bootsys
    _bootsys.path.insert(0, str(_bootpath.Path(__file__).resolve().parent))
    import _cli_bootstrap        # noqa: F401

import argparse
import pathlib
import shutil
import sys

import yaml

from scripts.paths import LEGACY_EXPORTS, REPORTS, data_dir, is_legacy_layout, work_dir_for

_TRIANGLE_MARK = "▸"


def plan_trip(trip_dir, work_root=None):
    """([(action, src, dst)], [note]) for one trip; empty when already v1.
    work_root defaults to the workspace's work/ (scripts/paths.py::work_dir_for)."""
    t = pathlib.Path(trip_dir)
    if not is_legacy_layout(t) and not (t / "exports").is_dir():
        return [], []
    moves, notes, taken = [], [], set()
    legacy = data_dir(t) / LEGACY_EXPORTS

    def unique(dst, prefix=""):
        """Never two moves onto one path and never onto an existing file."""
        dst = dst.with_name(prefix + dst.name) if prefix and (dst in taken or dst.exists()) else dst
        n = 2
        while dst in taken or dst.exists():
            dst = dst.with_name(f"{dst.stem.rsplit('-', 1)[0] if n > 2 else dst.stem}-{n}{dst.suffix}")
            n += 1
        taken.add(dst)
        return dst

    for p in sorted(t.iterdir()):
        if p.is_file():
            if p.name in REPORTS:
                work = pathlib.Path(work_root) / t.name if work_root else work_dir_for(t)
                if (work / p.name).exists():      # never overwrite: keep the old one aside
                    moves.append(("move", p, unique(legacy / p.name)))
                    notes.append(f"{p.name}: work/ already has one — the trip copy is kept "
                                 f"under data/{LEGACY_EXPORTS}/")
                else:
                    moves.append(("move", p, unique(work / p.name)))
            elif p.name == "itinerary.md":
                moves.append(("move", p, unique(legacy / p.name)))
            else:
                dst = data_dir(t) / p.name
                moves.append(("move", p, unique(dst) if not dst.exists() else
                              unique(legacy / p.name, "root-")))
        elif p.name == "exports" and p.is_dir():
            for q in sorted(p.iterdir()):
                moves.append(("move", q, unique(legacy / f"exports-{q.name}")))
            moves.append(("rmdir", p, None))
    brief = _load(t / "trip-brief.yaml") or _load(data_dir(t) / "trip-brief.yaml")
    if not (brief or {}).get("short_name"):
        notes.append("trip-brief has no short_name/headline — the gate routes the next run "
                     "to trip-brief, which proposes them for you to confirm")
    itin = _load(t / "itinerary.yaml") or _load(data_dir(t) / "itinerary.yaml")
    n_tri = sum(1 for d in (itin.get("days") or []) for r in (d.get("rows") or [])
                if isinstance(r, dict) and str(r.get("text") or "").lstrip().startswith(_TRIANGLE_MARK))
    if n_tri or itin.get("contingency"):
        what = [f"{n_tri} inline ▸ row(s)"] if n_tri else []
        what += ["a trip-level contingency"] if itin.get("contingency") else []
        notes.append(f"{' and '.join(what)} kept as-is — the next gate run routes them to "
                     f"itinerary-synthesis, which rewrites them as per-stop alternatives")
    return moves, notes


def _load(path):
    try:
        return yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}


def _show(path, trip):
    """A path relative to the trips root when it lives under it (data/ moves),
    else as-is (work/ moves)."""
    try:
        return str(pathlib.Path(path).resolve().relative_to(pathlib.Path(trip).resolve().parent))
    except ValueError:
        return str(path)


def _apply(moves):
    for action, src, dst in moves:
        if action == "move":
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        elif action == "rmdir":
            src.rmdir()


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("trips_root")
    ap.add_argument("--work-root", default=None)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    root = pathlib.Path(args.trips_root)
    work_root = pathlib.Path(args.work_root) if args.work_root else None
    trips = [root] if is_legacy_layout(root) or (root / "data").is_dir() else \
        sorted(p for p in root.iterdir() if p.is_dir())
    for t in trips:
        moves, notes = plan_trip(t, work_root)
        if not moves:
            print(f"{t.name}: already v1.0 — skipped")
            continue
        print(f"{t.name}:")
        for action, src, dst in moves:
            print(f"  {action} {_show(src, t)}" + (f" -> {_show(dst, t)}" if dst else ""))
        for n in notes:
            print(f"  note: {n}")
        if args.apply:
            _apply(moves)
    if not args.apply:
        print("dry run — nothing changed; re-run with --apply (paths move under data/)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
