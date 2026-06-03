"""POI -> Google Maps search link. Pure string transform, no network."""
from urllib.parse import quote

BASE = "https://www.google.com/maps/search/?api=1&query="

def _query_name(poi):
    return poi.get("name_local") or poi.get("name_display") or poi.get("id", "")

def maps_url(poi):
    """Build a Google Maps search URL, preferring the local-language name."""
    return BASE + quote(_query_name(poi))

def link_markdown(poi):
    """Markdown link: [display name](maps url)."""
    label = poi.get("name_display") or poi.get("name_local") or poi.get("id", "")
    return f"[{label}]({maps_url(poi)})"
