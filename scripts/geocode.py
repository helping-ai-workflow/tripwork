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
