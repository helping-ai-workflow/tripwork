"""OSM Nominatim geocoding wrapper. No API key; respects usage policy."""
from dataclasses import dataclass
import requests
from scripts.distance import haversine_km
from scripts.geocode_cache import cache_key, cache_get, cache_put

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

def resolve_place(name, district=None, country=None, timeout=10, cache=None):
    """Two-tier resolve (structured query first, free-text fallback) with an
    optional per-trip cache.

    When `cache` (a dict) is given, a hit — including a cached miss (None) — returns
    without touching Nominatim; otherwise the result (or None) is stored in `cache`.
    Returns (GeocodeResult, source) where source is 'nominatim_structured' or
    'nominatim'; (None, None) if neither resolves. `cache=None` is the original behaviour.
    """
    if not name or not str(name).strip():
        raise ValueError("resolve_place requires a non-empty place name "
                         "(a blank name_local would silently geocode the city itself)")
    key = cache_key(name, district, country) if cache is not None else None
    if cache is not None:
        hit, value = cache_get(cache, key)
        if hit:
            # TW-019: trust a cache hit only if it is well-formed and from a real
            # geocoder; otherwise treat as a miss and re-query.
            if value is None:
                return None, None
            if (isinstance(value.get("lat"), (int, float))
                    and isinstance(value.get("lng"), (int, float))
                    and value.get("source") in ("nominatim", "nominatim_structured")):
                return (GeocodeResult(value["lat"], value["lng"], value.get("display_name", "")),
                        value["source"])

    result = geocode_structured(name, city=district, country=country, timeout=timeout)
    source = "nominatim_structured"
    if result is None:
        q = " ".join(p for p in (name, district, country) if p)
        result = geocode(q, timeout=timeout)
        source = "nominatim" if result is not None else None

    if cache is not None:
        cache_put(cache, key, None if result is None else
                  {"lat": result.lat, "lng": result.lng,
                   "display_name": result.display_name, "source": source})

    return (result, source) if result is not None else (None, None)

def cluster_centroid(points):
    """Mean (lat, lng) of a non-empty list of (lat, lng) tuples; None if empty."""
    if not points:
        return None
    n = len(points)
    return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n)

def normalize_geocode_keys(geocode):
    """Canonicalise legacy longitude keys ('lon'/'long') to 'lng'.

    Returns a new dict (input not mutated); None passes through. Raises ValueError
    if a legacy key and 'lng' are both present AND disagree — a silent mismatch
    would corrupt routing/distance/links (dogfood D1).
    """
    if geocode is None:
        return None
    out = dict(geocode)
    legacy = out.pop("lon", None)
    if "long" in out:
        legacy = out.pop("long")
    if legacy is not None:
        if "lng" in out and out["lng"] != legacy:
            raise ValueError(
                f"conflicting longitude: legacy={legacy} vs lng={out['lng']}")
        out["lng"] = legacy
    return out
