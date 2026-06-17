"""Render-time overlay of the photo side-file onto poi_map.

The photo adapter (backend wiki/google) writes media to a SEPARATE side-file,
`trips/<slug>/verified-pois-media.yaml`, keyed by poi_id. It is never written into
canonical `verified-pois.yaml` because `source-verify` wholesale-rewrites that file
on every run (skills/source-verify/SKILL.md) and would clobber any inline media.

At export, the agent overlays the side-file onto the poi_map it assembled from
verified-pois.yaml, BEFORE calling render_day_table / render_html_page:

    poi_map = apply_media(poi_map, load_media("trips/<slug>/verified-pois-media.yaml"))

File-lifecycle discipline (graceful-absent load) mirrors scripts/geocode_cache.py;
the merge is a pure, non-mutating dict overlay.
"""
import yaml

# The only POI keys the side-file is allowed to contribute. Any other key in a
# media entry is ignored — the canonical poi shape stays authoritative.
_MEDIA_KEYS = ("photo", "photo_attribution", "photo_source")


def load_media(path):
    """Load a verified-pois-media side-file.

    Returns the parsed doc, or ``{}`` when the file is absent or empty/corrupt
    (mirrors geocode_cache.load_cache — a missing side-file is the default
    `backend=none` case and must not be an error).
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (FileNotFoundError, OSError, UnicodeDecodeError, yaml.YAMLError):
        return {}
    # A valid-YAML-but-non-dict side-file (e.g. a list) must degrade to {} so the
    # downstream apply_media(...).get("media") never crashes (mirrors geocode_cache).
    return data if isinstance(data, dict) else {}


def apply_media(poi_map, media_doc):
    """Overlay photo media from a side-file doc onto poi_map.

    Returns a NEW ``{poi_id: poi}`` dict in which each poi is a shallow copy with
    ``photo`` / ``photo_attribution`` / ``photo_source`` overlaid when the side-file
    has an entry for that id. Inputs are NEVER mutated — the canonical
    verified-pois.yaml that produced poi_map must stay clobber-free. POIs with no
    matching media entry are returned as plain copies; unknown media-entry keys are
    ignored.
    """
    media = (media_doc or {}).get("media") or {}
    out = {}
    for pid, poi in (poi_map or {}).items():
        merged = dict(poi)
        entry = media.get(pid)
        if isinstance(entry, dict):
            for key in _MEDIA_KEYS:
                if key in entry:
                    merged[key] = entry[key]
        out[pid] = merged
    return out
