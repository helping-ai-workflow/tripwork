"""OSM Nominatim geocoding wrapper. No API key; respects usage policy."""
from dataclasses import dataclass
import requests
from scripts.distance import haversine_km

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "tripwork/0.2 (https://github.com/helping-ai-workflow/tripwork)"

@dataclass
class GeocodeResult:
    lat: float
    lng: float
    display_name: str

def geocode(query, timeout=10):
    """Resolve a place name to coordinates. Returns GeocodeResult or None.

    Caller is responsible for rate limiting (Nominatim policy: <= 1 req/s).
    """
    resp = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return None
    top = data[0]
    return GeocodeResult(lat=float(top["lat"]), lng=float(top["lon"]),
                         display_name=top.get("display_name", ""))

def in_region(lat, lng, region_lat, region_lng, radius_km=5.0):
    """True if (lat,lng) is within radius_km of a region centroid."""
    return haversine_km(lat, lng, region_lat, region_lng) <= radius_km

def geocode_structured(name, city=None, country=None, timeout=10):
    """Nominatim structured query — higher hit-rate for small venues than free text.

    Caller rate-limits (Nominatim policy: <= 1 req/s).
    """
    params = {"format": "json", "limit": 1}
    if name:
        params["street"] = name      # venue name in the 'street' slot (Nominatim idiom)
    if city:
        params["city"] = city
    if country:
        params["country"] = country
    resp = requests.get(NOMINATIM_URL, params=params,
                        headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return None
    top = data[0]
    return GeocodeResult(lat=float(top["lat"]), lng=float(top["lon"]),
                         display_name=top.get("display_name", ""))

def resolve_place(name, district=None, country=None, timeout=10):
    """Two-tier resolve: structured query first, free-text fallback.

    Returns (GeocodeResult, source) where source is 'nominatim_structured' or
    'nominatim'; (None, None) if neither resolves.
    """
    r = geocode_structured(name, city=district, country=country, timeout=timeout)
    if r is not None:
        return r, "nominatim_structured"
    q = " ".join(p for p in (name, district, country) if p)
    r = geocode(q, timeout=timeout)
    if r is not None:
        return r, "nominatim"
    return None, None

def cluster_centroid(points):
    """Mean (lat, lng) of a non-empty list of (lat, lng) tuples; None if empty."""
    if not points:
        return None
    n = len(points)
    return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n)
