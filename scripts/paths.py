"""The v1.0 trip folder layout (spec §5.1) -- the ONE place trip paths are decided.

    trips/<slug>/<stem>.md | .html            deliverables (stem = deliverable_stem)
    trips/<slug>/data/                        every artifact, the media side-file, PDFs
    work/<slug>/                              gate reports, stage-state, geocode cache

Every CLI and every test gets a path from here; nothing re-joins the strings.
"""
import pathlib

from scripts.brief_names import deliverable_stem

DATA = "data"
LEGACY_EXPORTS = "legacy-exports"
REPORTS = ("gate-report.yaml", "export-gate-report.yaml")
DELIVERABLE_SUFFIXES = {"md": ".md", "html": ".html"}   # v1.1: the LINE .txt is retired


def data_dir(trip_dir):
    return pathlib.Path(trip_dir) / DATA


def artifact_path(trip_dir, name):
    return data_dir(trip_dir) / name


def work_dir_for(trip_dir):
    t = pathlib.Path(trip_dir).resolve()
    return t.parent.parent / "work" / t.name


def report_path(work_dir, name):
    return pathlib.Path(work_dir) / name


def deliverable_paths(trip_dir, brief):
    """{md, html, line} under the trip folder. Raises KeyError / ValueError / TypeError
    when the brief has no usable dates + short_name -- callers route that to trip-brief."""
    stem = deliverable_stem(brief)
    t = pathlib.Path(trip_dir)
    return {k: t / f"{stem}{suffix}" for k, suffix in DELIVERABLE_SUFFIXES.items()}


def artifact_names():
    """Every trip artifact basename: the validator's table minus the work-side files."""
    from scripts.validate_artifact import SCHEMA_BY_BASENAME
    return tuple(n for n in SCHEMA_BY_BASENAME if n not in REPORTS and n != "stage-state.yaml")


def is_legacy_layout(trip_dir):
    """True while ANY artifact still sits at the trip root -- a pre-v1.0 trip, a
    half-finished migration, or a consumer script still writing there. data/
    existing does not mean done (P3 review I1)."""
    t = pathlib.Path(trip_dir)
    return any((t / n).is_file() for n in artifact_names())
