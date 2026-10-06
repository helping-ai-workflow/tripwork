"""OSM Nominatim geocoding wrapper. No API key; respects usage policy."""
import re
import time
import unicodedata
from dataclasses import dataclass
import requests
from scripts.distance import haversine_km
from scripts.geocode_cache import cache_key, cache_get, cache_put

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# v1.3.0: a flaky network is retried, not fatal (e2e: one read timeout ended a 6-minute
# source-verify run). Waits between the three tries; tests replace _sleep.
_RETRY_WAITS = (2, 5)
_RETRY_STATUS = {429, 502, 503, 504}
_sleep = time.sleep


def _get(params, timeout):
    """requests.get on Nominatim, retried after a timeout, a dropped connection or a busy
    server (429 / 502 / 503 / 504). The last failure is raised, so a caller never takes a
    network failure for "not found" (and caches no miss)."""
    for wait in (*_RETRY_WAITS, None):
        try:
            resp = requests.get(NOMINATIM_URL, params=params, headers={"User-Agent": USER_AGENT},
                                timeout=timeout)
            if getattr(resp, "status_code", 200) not in _RETRY_STATUS or wait is None:
                return resp
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if wait is None:
                raise
        _sleep(wait)
USER_AGENT = "tripwork/0.2 (https://github.com/helping-ai-workflow/tripwork)"

@dataclass
class GeocodeResult:
    lat: float
    lng: float
    display_name: str
    address: dict | None = None      # Nominatim's addressdetails, when asked for (v2.1.0 D5)


def _results(params, timeout, details):
    if details:
        params["addressdetails"] = 1
    resp = _get(params, timeout)
    resp.raise_for_status()
    return [GeocodeResult(lat=float(d["lat"]), lng=float(d["lon"]), display_name=d.get("display_name", ""),
                          address=d.get("address") if details else None)
            for d in resp.json() or []]


def geocode_many(query, timeout=10, countrycodes=None, feature_type=None, limit=5, details=False):
    """Up to `limit` results of one free-text query, best first ([] when none).

    `countrycodes` (ISO 3166-1 alpha-2, e.g. 'jp') keeps the search inside one country;
    `feature_type` is Nominatim's featureType ('settlement' for a district or town);
    `details` asks for each result's address parts. Caller rate-limits (<= 1 req/s).
    """
    params = {"q": query, "format": "json", "limit": limit}
    if countrycodes:
        params["countrycodes"] = countrycodes
    if feature_type:
        params["featureType"] = feature_type
    return _results(params, timeout, details)


def geocode(query, timeout=10, countrycodes=None, feature_type=None):
    """The first result of geocode_many (one requested), or None."""
    out = geocode_many(query, timeout=timeout, countrycodes=countrycodes, feature_type=feature_type, limit=1)
    return out[0] if out else None

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

def geocode_structured_many(name, city=None, country=None, timeout=10, limit=5, details=False):
    """Nominatim structured query — higher hit-rate for small venues than free text.
    Up to `limit` results, best first. Caller rate-limits (<= 1 req/s)."""
    params = {"format": "json", "limit": limit}
    if name:
        params["street"] = name      # venue name in the 'street' slot (Nominatim idiom)
    if city:
        params["city"] = city
    if country:
        params["country"] = country
    return _results(params, timeout, details)


def geocode_structured(name, city=None, country=None, timeout=10):
    """The first result of geocode_structured_many (one requested), or None."""
    out = geocode_structured_many(name, city=city, country=country, timeout=timeout, limit=1)
    return out[0] if out else None


BARE_NAME_TIERS = (3, 5)             # resolve_place tiers that query the name alone


def accept(result, tier, name_local, name_roman=None, region=None):
    """Whether one resolve_place result counts (v2.1.0 D6): its name matches the venue's
    local or roman name, and a bare-name tier's hit lies inside `region` =
    (lat, lng, radius_km) -- with no region, a bare-name hit never counts. A precise
    tier's hit outside the region still counts: the venue may have moved, and Gate 3b
    asks the user."""
    if not (name_matches(name_local, result.display_name)
            or (name_roman and name_matches(name_roman, result.display_name))):
        return False
    if tier in BARE_NAME_TIERS:
        return region is not None and in_region(result.lat, result.lng, *region)
    return True

def geocode_country(country, timeout=10):
    """The ISO 3166-1 alpha-2 code ('jp') Nominatim gives a country name in any language
    ('日本', 'Japan', '台灣'), or None. Caller rate-limits."""
    resp = _get({"q": country, "featureType": "country", "addressdetails": 1, "format": "json", "limit": 1},
                timeout)
    resp.raise_for_status()
    data = resp.json()
    code = ((data[0].get("address") or {}).get("country_code") if data else None) or ""
    return code.lower() if re.fullmatch(r"[A-Za-z]{2}", code) else None


# The ways a trip brief names Taiwan (casefolded). A literal because the user plans
# domestic trips most, and the map service does not read every variant ('臺灣').
TW_COUNTRY_NAMES = {"台灣": "tw", "臺灣": "tw", "taiwan": "tw", "中華民國": "tw", "roc": "tw"}


def country_code(country, timeout=10, cache=None, pace=None, offline=False):
    """`country` as an alpha-2 code. Looked up in order (v2.1.0 D4): Taiwan's names
    (TW_COUNTRY_NAMES), an alpha-2 code kept as is, the per-trip cache, then Nominatim
    once (geocode_country), remembered in the cache, a miss included. `offline` stops
    before the network (None). A network error propagates: it is not a miss."""
    if not country or not str(country).strip():
        return None
    name = str(country).strip()
    if name.casefold() in TW_COUNTRY_NAMES:
        return TW_COUNTRY_NAMES[name.casefold()]
    if re.fullmatch(r"[A-Za-z]{2}", name):
        return name.lower()
    key = cache_key(country, "@country", None)
    if cache is not None:
        hit, value = cache_get(cache, key)
        if hit:
            return value.get("country_code") if isinstance(value, dict) else None
    if offline:
        return None
    code = geocode_country(country, timeout=timeout)
    if pace is not None:
        pace()
    if cache is not None:
        cache_put(cache, key, {"country_code": code} if code else None)
    return code


def resolve_place(name, district=None, country=None, timeout=10, cache=None,
                  name_roman=None, pace=None, area=False, region=None):
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
    v2.1.0 (D6): each tier asks for up to 5 results, and a result counts only when
    `accept` says so -- its name matches, and a bare-name tier (3, 5) lands inside
    `region` = (lat, lng, radius_km). A tier with no accepted result is no hit: the
    next tier runs. A cached result is re-checked the same way (the cache records its
    tier); a cache entry written before v2.1.0 (no tier) is looked up once more and
    rewritten. `area=True` lookups (a district's own centre) take the first result,
    unchecked, as before.
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
            cached = _cached_place(value, area, name, name_roman, region)
            if cached is not None:
                return cached

    result, source, tier = None, None, None
    if area:
        cc = country_code(country, timeout=timeout, cache=cache, pace=pace)
        for q in (" ".join(p for p in (name, district, country) if p), name):
            if q and str(q).strip():
                result = _paced(geocode, q, timeout=timeout, countrycodes=cc, feature_type="settlement")
                if result is not None:
                    source = "nominatim"
                    break
    else:
        r = _best(_paced(geocode_structured_many, name, city=district, country=country, timeout=timeout),
                  1, name, name_roman, region)
        if r is not None:
            result, source, tier = r, "nominatim_structured", 1
        if result is None:
            cc = country_code(country, timeout=timeout, cache=cache, pace=pace)
            attempts = [(2, " ".join(p for p in (name, district, country) if p)), (3, name)]
            if name_roman:
                attempts += [(4, " ".join(p for p in (name_roman, district, country) if p)), (5, name_roman)]
            for n, q in attempts:
                if not q or not str(q).strip():
                    continue
                r = _best(_paced(geocode_many, q, timeout=timeout, countrycodes=cc), n, name, name_roman, region)
                if r is not None:
                    result, source, tier = r, "nominatim", n
                    break

    if cache is not None:
        if area:
            cache_put(cache, key, None if result is None else
                      {"lat": result.lat, "lng": result.lng,
                       "display_name": result.display_name, "source": source})
        else:
            cache_put(cache, key, {"v": 2, "miss": True} if result is None else
                      {"v": 2, "lat": result.lat, "lng": result.lng, "display_name": result.display_name,
                       "source": source, "tier": tier, "address": result.address})

    return (result, source) if result is not None else (None, None)


def _best(results, tier, name, name_roman, region):
    """The result one tier keeps: of those `accept` passes, the first inside `region` --
    a chain's branch in the claimed district beats an earlier one elsewhere -- else the
    first accepted (a precise hit elsewhere may have moved; Gate 3b asks). None if none."""
    ok = [r for r in results if accept(r, tier, name, name_roman, region)]
    if region is not None:
        inside = next((r for r in ok if in_region(r.lat, r.lng, *region)), None)
        if inside is not None:
            return inside
    return ok[0] if ok else None


def _cached_place(value, area, name, name_roman, region):
    """A cache hit resolve_place may return, or None to look up again. A district's
    centre (area) is trusted as before (TW-019: only a well-formed geocoder answer). A
    venue entry must be v2.1.0's shape and pass `accept` for its recorded tier; an older
    entry, a miss included, is looked up once more."""
    if area:
        if value is None:
            return None, None
        if (isinstance(value.get("lat"), (int, float)) and isinstance(value.get("lng"), (int, float))
                and value.get("source") in ("nominatim", "nominatim_structured")):
            return GeocodeResult(value["lat"], value["lng"], value.get("display_name", "")), value["source"]
        return None
    if not isinstance(value, dict) or value.get("v") != 2:
        return None
    if value.get("miss"):
        return None, None
    if not (isinstance(value.get("lat"), (int, float)) and isinstance(value.get("lng"), (int, float))
            and value.get("source") in ("nominatim", "nominatim_structured")):
        return None
    r = GeocodeResult(value["lat"], value["lng"], value.get("display_name", ""), value.get("address"))
    return (r, value["source"]) if accept(r, value.get("tier"), name, name_roman, region) else None


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
    details = cc == "tw"                  # v2.1.0 D5: a Taiwanese road point names its 村里
    for v in address_variants(address, cc):
        key = cache_key(v, None, country, kind="address") if cache is not None else None
        if cache is not None:
            hit, value = cache_get(cache, key)
            if hit and not (details and value and "address" not in value):   # pre-2.1.0: once more
                if value:
                    return GeocodeResult(value["lat"], value["lng"], value.get("display_name", ""),
                                         value.get("address")), v
                continue
        found = geocode_many(v, timeout=timeout, countrycodes=cc, limit=1, details=details)
        r = found[0] if found else None
        if pace is not None:
            pace()
        if cache is not None:
            cache_put(cache, key, None if r is None else
                      {"lat": r.lat, "lng": r.lng, "display_name": r.display_name, "source": "nominatim_address",
                       **({"address": r.address} if details else {})})
        if r is not None:
            return r, v
    return None, None


_COUNTY_DISTRICT = re.compile(r"^(.+?[縣市])(.+?[區鄉鎮市])")


def county_district(address):
    """'臺南市中西區' from a Taiwanese address, or None: the prefix a 村里 is looked up under
    (里 names repeat across the island)."""
    m = _COUNTY_DISTRICT.match(unicodedata.normalize("NFKC", str(address or "")).strip())
    return m.group(1) + m.group(2) if m else None


def village_of(address):
    """The 村 / 里 a Nominatim result lies in, from its address parts, or None."""
    for k in ("neighbourhood", "city_district", "suburb", "quarter"):
        v = (address or {}).get(k)
        if isinstance(v, str) and v.endswith(("里", "村")):
            return v
    return None


def village_point(county_dist, village, country=None, timeout=10, cache=None, pace=None):
    """The centre of `village` under `county_dist` ('臺南市中西區示意里'): the first result
    that is a boundary or a place -- not a building named after it -- or None. Cached under
    cache_key(kind="village"); `pace` after an issued request."""
    q = f"{county_dist}{village}"
    key = cache_key(q, None, country, kind="village") if cache is not None else None
    if cache is not None:
        hit, value = cache_get(cache, key)
        if hit:
            return GeocodeResult(value["lat"], value["lng"], value.get("display_name", "")) if value else None
    cc = country_code(country, timeout=timeout, cache=cache, pace=pace)
    params = {"q": q, "format": "json", "limit": 5}
    if cc:
        params["countrycodes"] = cc
    resp = _get(params, timeout)
    if pace is not None:
        pace()
    resp.raise_for_status()
    top = next((d for d in resp.json() or [] if d.get("class") in ("boundary", "place")), None)
    out = GeocodeResult(float(top["lat"]), float(top["lon"]), top.get("display_name", "")) if top else None
    if cache is not None:
        cache_put(cache, key, None if out is None else
                  {"lat": out.lat, "lng": out.lng, "display_name": out.display_name, "source": "village_centroid"})
    return out


def place_point(query, country=None, timeout=10, cache=None, pace=None):
    """The first result of a plain free-text query (no featureType) that is a place in
    OSM's sense (class place: a quarter, neighbourhood, town ...), inside the trip's country;
    None otherwise. A district the settlement lookup misses (OSM has only its 丁目, or tags it
    neighbourhood) is found this way, while a parking lot or bus stop named after it is not.
    Cached under cache_key(kind="place"); `pace` after every issued request."""
    if not str(query or "").strip():
        return None
    key = cache_key(query, None, country, kind="place") if cache is not None else None
    if cache is not None:
        hit, value = cache_get(cache, key)
        if hit:
            return GeocodeResult(value["lat"], value["lng"], value.get("display_name", "")) if value else None
    cc = country_code(country, timeout=timeout, cache=cache, pace=pace)
    params = {"q": query, "format": "json", "limit": 5}
    if cc:
        params["countrycodes"] = cc
    resp = _get(params, timeout)
    if pace is not None:
        pace()
    resp.raise_for_status()
    top = next((d for d in resp.json() or [] if d.get("class") == "place"), None)
    out = GeocodeResult(float(top["lat"]), float(top["lon"]), top.get("display_name", "")) if top else None
    if cache is not None:
        cache_put(cache, key, None if out is None else
                  {"lat": out.lat, "lng": out.lng, "display_name": out.display_name, "source": "nominatim"})
    return out


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
