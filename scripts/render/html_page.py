"""The HTML deliverable. Since v1.0 this is the reader in scripts/render/reader/
(spec §6); this module keeps the long-standing entrypoint and signature so
export-artifact and existing callers do not change shape."""
import html as _html

from scripts.render.reader import render_reader


def _html_escape(text: object) -> str:
    """Escape trip text for HTML (kept for callers of the pre-v1.0 helper)."""
    return _html.escape("" if text is None else str(text), quote=True)


def render_html_page(itin: dict, poi_map: dict, *, brief=None, accommodations=None,
                     advisory=None, legs=None, maps=None, cost=None, build="check") -> str:
    """Render the self-contained reader page. `poi_map` is verified-pois + chosen
    lodgings + the media overlay (scripts/media_merge.py::apply_media); pass the
    brief, accommodations, advisory and legs so the home page, stamp calendar and
    sub-screens have their data (absent ones render as empty sections); `maps` is the
    day-maps side-file (scripts/day_maps.py), without which each day draws a schematic;
    `cost` is cost.yaml, which feeds the home's 旅程與費用 card. `build='publish'` adds the publish page's script (spec §1)."""
    return render_reader(itin, poi_map, brief=brief, accommodations=accommodations,
                         advisory=advisory, legs=legs, maps=maps, cost=cost, build=build)
