"""POI -> Google Maps search link. Pure string transform, no network."""
from urllib.parse import quote

BASE = "https://www.google.com/maps/search/?api=1&query="

# Chars with markdown meaning inside a [label]; backslash first so added escapes
# are not re-escaped.
_LABEL_ESCAPE = ["\\", "[", "]", "|", "$", "`"]

def _esc_label(text):
    out = str(text)
    for ch in _LABEL_ESCAPE:
        out = out.replace(ch, "\\" + ch)
    return out

def _query_name(poi):
    return poi.get("name_local") or poi.get("name_display") or poi.get("id", "")

def maps_url(poi):
    """Build a Google Maps query URL.

    Prefers the verified coordinates (coordinate-pinned: `query=lat,lng`) so a
    name-collision can't land the user on the wrong place; falls back to
    `name_local + district` (district disambiguates), then bare name. (TW-048)
    """
    geo = poi.get("geocode") or {}
    lat, lng = geo.get("lat"), geo.get("lng")
    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        return BASE + quote(f"{lat},{lng}")
    name = _query_name(poi)
    district = poi.get("district")
    query = f"{name} {district}" if district else name
    return BASE + quote(query)

def link_markdown(poi):
    """Markdown link: [display name](maps url). Label is escaped so a scraped name
    containing `]`/`|`/`$` cannot break the markdown. (TW-022)"""
    label = poi.get("name_display") or poi.get("name_local") or poi.get("id", "")
    return f"[{_esc_label(label)}]({maps_url(poi)})"
