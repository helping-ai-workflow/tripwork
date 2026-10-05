"""OSM Nominatim geocoding wrapper. No API key; respects usage policy."""
import re
import unicodedata
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

def geocode(query, timeout=10, countrycodes=None, feature_type=None):
    """Resolve a place name to coordinates. Returns GeocodeResult or None.

    `countrycodes` (ISO 3166-1 alpha-2, e.g. 'jp') keeps the search inside one country;
    `feature_type` is Nominatim's featureType ('settlement' for a district or town).
    Caller is responsible for rate limiting (Nominatim policy: <= 1 req/s).
    """
    params = {"q": query, "format": "json", "limit": 1}
    if countrycodes:
        params["countrycodes"] = countrycodes
    if feature_type:
        params["featureType"] = feature_type
    resp = requests.get(
        NOMINATIM_URL,
        params=params,
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

def geocode_country(country, timeout=10):
    """The ISO 3166-1 alpha-2 code ('jp') Nominatim gives a country name in any language
    ('日本', 'Japan', '台灣'), or None. Caller rate-limits."""
    resp = requests.get(NOMINATIM_URL,
                        params={"q": country, "featureType": "country", "addressdetails": 1,
                                "format": "json", "limit": 1},
                        headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    code = ((data[0].get("address") or {}).get("country_code") if data else None) or ""
    return code.lower() if re.fullmatch(r"[A-Za-z]{2}", code) else None


def country_code(country, timeout=10, cache=None, pace=None):
    """`country` as an alpha-2 code: kept as is when it already is one, else looked up
    once (geocode_country) and remembered in the per-trip cache, a miss included."""
    if not country or not str(country).strip():
        return None
    if re.fullmatch(r"[A-Za-z]{2}", str(country).strip()):
        return str(country).strip().lower()
    key = cache_key(country, "@country", None)
    if cache is not None:
        hit, value = cache_get(cache, key)
        if hit:
            return value.get("country_code") if isinstance(value, dict) else None
    code = geocode_country(country, timeout=timeout)
    if pace is not None:
        pace()
    if cache is not None:
        cache_put(cache, key, {"country_code": code} if code else None)
    return code


def resolve_place(name, district=None, country=None, timeout=10, cache=None,
                  name_roman=None, pace=None, area=False):
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
    Every free-text tier is kept inside `country` (Nominatim `countrycodes`, the code
    looked up once per trip cache): a bare name otherwise matches a namesake abroad.
    `area=True` looks up a district or town, not a venue: no street-slot query, the
    free-text tiers ask for a settlement, and the cache keeps it apart from a venue
    of the same name.
    `pace` is a zero-argument callback invoked once after EVERY request this
    function actually issues — never on a cache hit, never on a tier that was
    not reached. Nominatim's policy is <= 1 req/s, and a hard-to-resolve POI
    walks all five tiers above, so a caller that sleeps once per CALL paces one
    request and bursts the other four. That is what
    scripts/source_verify_run.py::_rate_limited_resolve did until v0.33.0, and
    TW-068 made that driver the SKILL-mandated bulk path over a whole
    candidates.yaml — the consequence is an IP block on a free public service.
    Pass `pace=lambda: time.sleep(delay)`; the default `None` is a no-op, so
    callers that do their own pacing are unaffected.
    """
    def _paced(fetch, *args, **kwargs):
        out = fetch(*args, **kwargs)
        if pace is not None:
            pace()
        return out

    if not name or not str(name).strip():
        raise ValueError("resolve_place requires a non-empty place name "
                         "(a blank name_local would silently geocode the city itself)")
    key = cache_key(name, district, country, area=area) if cache is not None else None
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

    result = None if area else _paced(geocode_structured, name, city=district, country=country,
                                      timeout=timeout)
    source = "nominatim_structured"
    if result is None:
        cc = country_code(country, timeout=timeout, cache=cache, pace=pace)
        attempts = [" ".join(p for p in (name, district, country) if p), name]
        if name_roman:
            attempts.append(" ".join(p for p in (name_roman, district, country) if p))
            attempts.append(name_roman)
        for q in attempts:
            if not q or not str(q).strip():
                continue
            result = _paced(geocode, q, timeout=timeout, countrycodes=cc,
                            feature_type="settlement" if area else None)
            if result is not None:
                break
        source = "nominatim" if result is not None else None

    if cache is not None:
        cache_put(cache, key, None if result is None else
                  {"lat": result.lat, "lng": result.lng,
                   "display_name": result.display_name, "source": source})

    return (result, source) if result is not None else (None, None)

_DASH = str.maketrans({c: "-" for c in "－−ー‐–—―"})
_KANJI_CHOME = re.compile(r"^(.*?)([一二三四五六七八九十]+丁目)")
_FIRST_NUMBER = re.compile(r"^(.*?[^\d\s-])(\d+)(?:丁目|-|番|$)")


def address_variants(address, country_code=None):
    """The strings an address is looked up as, finest first. Nominatim resolves a Japanese
    address to its 丁目 at best (probed 2026-10-05: `浅草2-3-1` never resolves, `浅草2丁目`
    does), so for Japan: the address without building / floor, its 丁目 (the first number,
    when it is a 丁目 -- 20 or less; a larger one is a 番地), then the town. Elsewhere: the
    address, then without a trailing house number (`…路100號2樓` -> `…路`)."""
    s = unicodedata.normalize("NFKC", str(address or "")).translate(_DASH).strip()
    if not s:
        return []
    out = []
    if (country_code or "").lower() == "jp":
        s = re.split(r"\s", s)[0]                                   # building / floor follow a space
        m = _KANJI_CHOME.match(s)
        if m:
            out = [s, m.group(1) + m.group(2), m.group(1)]
        else:
            m = _FIRST_NUMBER.match(s)
            whole = re.match(r"^.*?\d[\d\-番地号丁目]*", s)
            out = [whole.group(0) if whole else s]
            if m:
                if int(m.group(2)) <= 20:
                    out.append(f"{m.group(1)}{int(m.group(2))}丁目")
                out.append(m.group(1))
    else:
        out = [s]
        m = re.match(r"^(.*?\D)\s*\d+\s*(?:號|号|번지|번)", s)
        if m and m.group(1).strip():
            out.append(m.group(1).strip())
    seen = []
    for v in out:
        if v and v not in seen:
            seen.append(v)
    return seen


def address_point(address, country=None, timeout=10, cache=None, pace=None):
    """A reference point for a venue from its sourced street address: the first of
    address_variants() Nominatim resolves inside the trip's country -> (GeocodeResult,
    variant), or (None, None). A 丁目 / town point is a few hundred metres wide: it checks
    a name lookup and stands in when there is none, it is not the venue. Each variant is
    cached (misses too) under its own key; `pace` runs after every issued request."""
    if not str(address or "").strip():
        return None, None
    cc = country_code(country, timeout=timeout, cache=cache, pace=pace)
    for v in address_variants(address, cc):
        key = cache_key(v, None, country, kind="address") if cache is not None else None
        if cache is not None:
            hit, value = cache_get(cache, key)
            if hit:
                if value:
                    return GeocodeResult(value["lat"], value["lng"], value.get("display_name", "")), v
                continue
        r = geocode(v, timeout=timeout, countrycodes=cc)
        if pace is not None:
            pace()
        if cache is not None:
            cache_put(cache, key, None if r is None else
                      {"lat": r.lat, "lng": r.lng, "display_name": r.display_name, "source": "nominatim_address"})
        if r is not None:
            return r, v
    return None, None


def address_is_fine(address, variant, country_code=None):
    """True when `variant` is finer than the address's town: the address itself or its 丁目
    (Japan), the address itself elsewhere. A town (or road) point is kilometres wide -- too
    coarse to judge a name lookup (e2e 2026-10-05: one dropped a correct hit 2.9 km from its
    town centre)."""
    vs = address_variants(address, country_code)
    return bool(vs) and variant in vs and (len(vs) == 1 or variant != vs[-1])


ADDRESS_MATCH_KM = 2.0      # an address point is its 丁目 / town: closer than this is the same place


def pick_point(name_hit, name_source, address_hit):
    """The coordinate a venue stands on, from its name lookup and its sourced address
    point (address_point): the name hit when it is within ADDRESS_MATCH_KM of the address
    (or there is no address point) -- exact; else the address point, `nominatim_address`
    -- approximate (a name hit farther away is a namesake). (None, None) when neither."""
    if address_hit is not None and name_hit is not None and \
            haversine_km(name_hit.lat, name_hit.lng, address_hit.lat, address_hit.lng) > ADDRESS_MATCH_KM:
        name_hit = None
    if name_hit is not None:
        return name_hit, name_source
    if address_hit is not None:
        return address_hit, "nominatim_address"
    return None, None


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
