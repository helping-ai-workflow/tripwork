"""POI -> Google Maps search link. Pure string transform, no network."""
from urllib.parse import quote

BASE = "https://www.google.com/maps/search/?api=1&query="
DIR_BASE = "https://www.google.com/maps/dir/?api=1"

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
    """Build a Google Maps link.

    Name-search-first: returns ``query=<name_local> <district>`` so Google resolves
    a labelled place card for area POIs (onsen districts, parks, markets, canals)
    rather than an unnamed coordinate pin. This deliberately REVERSES the TW-048
    coord-first default (dogfood D1): coordinate pins produced unnamed markers and
    masked corrupt geocode values.

    Coord-pin opt-in: set ``geocode.pin_exact: true`` to force ``query=lat,lng`` —
    reserve for precise venues where the name alone creates an ambiguous match.

    Place-id deep-link (P9): when ``gmaps_place_id`` is present, ``&query_place_id``
    is appended (Maps URLs API form) so Maps resolves the EXACT place. The visible
    ``query`` (name or coords) is left intact in BOTH branches — place_id only
    REFINES the match, it does not replace the query. The 0.23.0 single-param
    ``maps/place/?q=place_id:<id>`` form is a dead link Google does not resolve and
    must not be reintroduced.
    """
    place_id = poi.get("gmaps_place_id")
    suffix = "&query_place_id=" + quote(str(place_id), safe="") if place_id else ""
    geo = poi.get("geocode") or {}
    lat, lng = geo.get("lat"), geo.get("lng")
    if geo.get("pin_exact") and isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        return BASE + quote(f"{lat},{lng}") + suffix
    name = _query_name(poi)
    district = poi.get("district")
    query = f"{name} {district}" if district else name
    return BASE + quote(query) + suffix

def dir_url(origin, destination):
    """A→B Google Maps DIRECTIONS url. No ``&travelmode`` → the user picks car / transit
    (G2). Endpoints are percent-encoded with ``safe=""`` (mirroring ``maps_url``) so the
    result is a well-formed https URL the export gate's href / link-target checks accept,
    and any ``)`` is encoded so a markdown ``](…)`` target cannot break."""
    return (DIR_BASE
            + "&origin=" + quote(str(origin), safe="")
            + "&destination=" + quote(str(destination), safe=""))

def link_markdown(poi):
    """Markdown link: [display name（中文）](maps url). Label escaped so a scraped
    name containing `]`/`|`/`$` cannot break the markdown. (TW-022, dogfood D3)"""
    base = poi.get("name_display") or poi.get("name_local") or poi.get("id", "")
    zh = poi.get("name_zh")
    label = f"{base}（{zh}）" if zh and zh != base else base
    return f"[{_esc_label(label)}]({maps_url(poi)})"
