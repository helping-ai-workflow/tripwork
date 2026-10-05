"""The inputs every deliverable is rendered from and judged against (v2.0.0).

`trip_inputs(trip_dir)` is the one place the itinerary, the POI pool (verified-pois
+ each stop's chosen lodging, scripts/gate.py::poi_pool) with the photo side-file
overlaid, and the reader's other artifacts are read. `export` renders from it,
`publish` renders the family page from it and `export-gate` judges the deliverables
against it -- three callers, one assembly, so what is gated is what was rendered.
"""
import yaml

from scripts.gate import poi_pool
from scripts.media_merge import apply_media, load_media
from scripts.paths import artifact_path


class TripInputError(Exception):
    """The trip folder lacks what the deliverables are rendered from (exit 2)."""


def _load(trip_dir, name, required=False):
    path = artifact_path(trip_dir, name)
    try:
        with open(path, encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
    except FileNotFoundError:
        if required:
            raise TripInputError(f"missing {path}") from None
        return None
    except yaml.YAMLError as exc:
        raise TripInputError(f"malformed {path}: {exc}") from None
    if required and not doc:
        raise TripInputError(f"empty {path}")
    return doc


def trip_inputs(trip_dir):
    """(itinerary, poi_map, render kwargs, media count). kwargs carries brief,
    accommodations, advisory, legs, maps (day-maps.yaml) and cost."""
    itin = _load(trip_dir, "itinerary.yaml", required=True)
    pois = _load(trip_dir, "verified-pois.yaml", required=True).get("pois") or []
    acc = _load(trip_dir, "accommodations.yaml")
    media = load_media(artifact_path(trip_dir, "verified-pois-media.yaml"))
    poi_map = apply_media(dict(poi_pool(pois, acc)), media)       # non-mutating: keep the return
    kwargs = {"brief": _load(trip_dir, "trip-brief.yaml"), "accommodations": acc,
              "advisory": _load(trip_dir, "advisory.yaml"), "legs": _load(trip_dir, "legs.yaml"),
              "maps": _load(trip_dir, "day-maps.yaml"), "cost": _load(trip_dir, "cost.yaml")}
    return itin, poi_map, kwargs, len((media or {}).get("media") or {})
