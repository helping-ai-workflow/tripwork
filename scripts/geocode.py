"""OSM Nominatim geocoding wrapper. No API key; respects usage policy."""
import re
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

def name_matches(query_name, display_name):
    """True if a resolved place plausibly corresponds to the queried venue. (P2)

    Conservative containment check: the queried name is compared against the venue
    token of the resolved ``display_name`` (the part before the first comma). A
    match requires one string to contain the other after stripping whitespace — so
    ``日月潭文武廟`` matches ``文武廟, 日月潭, 南投`` (core ``文武廟`` ⊂ query) but
    ``星月大地`` does NOT match the renamed neighbour ``星月驛站, 后里`` (neither
    contains the other). Deliberately strict about declaring a match: a name that
    cannot be confirmed returns False so the caller flags ``conflicting`` rather
    than trusting a wrong-but-plausible top hit. Avoids the real-data false
    positives a fuzzy / NER matcher produces."""
    def _norm(s):
        return re.sub(r"\s+", "", str(s or ""))
    q = _norm(query_name)
    core = _norm(str(display_name or "").split(",")[0])
    if not q or not core:
        return False
    return core in q or q in core

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

def resolve_place(name, district=None, country=None, timeout=10, cache=None, name_roman=None):
    """Multi-tier resolve (structured query first, then free-text fallbacks) with an
    optional per-trip cache.

    When `cache` (a dict) is given, a hit — including a cached miss (None) — returns
    without touching Nominatim; otherwise the result (or None) is stored in `cache`.
    Returns (GeocodeResult, source) where source is 'nominatim_structured' or
    'nominatim'; (None, None) if nothing resolves. `cache=None` is the original behaviour.

    Resolution order (P3 — famous CJK POIs miss the street-slot structured query and
    the combined free-text query, but resolve on the bare name or the English/roman
    name; first hit wins):
      1. structured query (venue name in the Nominatim 'street' slot)
      2. free-text '<name> <district> <country>'
      3. free-text '<name>' (bare core name)
      4. free-text '<name_roman> <district> <country>' (when name_roman given)
      5. free-text '<name_roman>'                       (when name_roman given)
    Caller still rate-limits (Nominatim policy <= 1 req/s); this may issue up to
    five requests on a hard-to-resolve POI, so space them.
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
        attempts = [" ".join(p for p in (name, district, country) if p), name]
        if name_roman:
            attempts.append(" ".join(p for p in (name_roman, district, country) if p))
            attempts.append(name_roman)
        for q in attempts:
            if not q or not str(q).strip():
                continue
            result = geocode(q, timeout=timeout)
            if result is not None:
                break
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
    if any two of {lon, long, lng} are present AND disagree — a silent mismatch
    would corrupt routing/distance/links (dogfood D1).

    Agreeing duplicates (same value) collapse cleanly to 'lng'.
    """
    if geocode is None:
        return None
    out = dict(geocode)
    # Collect all longitude values present across the three possible keys.
    lng_values = {k: out.pop(k) for k in ("lon", "long", "lng") if k in out}
    distinct = set(lng_values.values())
    if len(distinct) > 1:
        raise ValueError(
            f"conflicting longitude keys: {lng_values!r}")
    if distinct:
        out["lng"] = distinct.pop()
    return out
