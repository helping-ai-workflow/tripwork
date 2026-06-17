"""Pluggable POI photo adapter. Backends {none (default), wiki, google}.

Boundary principle (the ToS-safety property): safety comes from a data-vs-mechanism
split + key-at-runtime, NOT from where the code lives.
  - The MECHANISM (backend dispatch, license whitelist, base64 encode) ships
    in-plugin and is generic.
  - The DATA (a specific licensed image, a specific API key) is supplied at runtime
    by the operator, who owns the ToS relationship.

  - backend=none   : ships enabled; fetches nothing (default — existing trips unchanged).
  - backend=wiki   : Wikimedia Commons + Openverse; CC-only; safe to distribute.
  - backend=google : key-gated AND its output is marked non-distributable by the
    export gate; BLOCKED pending a display-surface ToS resolution — not implemented
    here (fetch_media_entry returns None).

Mirrors scripts/geocode.py discipline: a descriptive User-Agent, caller-supplied
per-source rate limiting (Nominatim/Commons policy <= 1 req/s), a per-trip cache, and
a name_local-first query + geocode location-match (does NOT contradict the
source-verify name_local rule). Landmark-only.

photo_source mapping (schema enum {wikimedia, openverse, google}): the `wiki` backend
resolves to source `wikimedia` (Commons) or `openverse`; the `commons` searcher emits
`wikimedia`, the `openverse` searcher emits `openverse`.
"""
import base64
import os
import re
import time

import requests
import yaml

from scripts.geocode import in_region

USER_AGENT = "tripwork/0.2 (https://github.com/helping-ai-workflow/tripwork)"
BACKENDS = ("none", "wiki", "google")

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
OPENVERSE_API = "https://api.openverse.org/v1/images/"

# Categories that should NOT get a generic landmark photo (a restaurant/hotel photo
# from Commons is rarely OF the actual venue). Landmark-only is a design constraint.
_NON_LANDMARK = ("restaurant", "cafe", "bar", "food", "izakaya", "diner",
                 "lodging", "hotel", "ryokan", "hostel", "accommodation", "inn")


# --------------------------------------------------------------------------- #
# License whitelist (hard). NC / ND rejected unconditionally.
# --------------------------------------------------------------------------- #

def license_allowed(license_str):
    """True only for the hard CC whitelist {CC0, PD, CC-BY, CC-BY-SA}.

    NC and ND are rejected unconditionally. CC-BY-SA is kept: share-alike binds the
    IMAGE, not the plugin code (which stays MIT), and the rendered attribution caption
    + source link satisfy SA's attribution+link terms. An unrecognised or empty
    license is REJECTED (conservative).
    """
    if not license_str:
        return False
    parts = [p for p in str(license_str).strip().upper()
             .replace("_", "-").replace(" ", "-").split("-") if p]
    if {"NC", "ND", "NONCOMMERCIAL", "NODERIVATIVES", "NODERIVS"} & set(parts):
        return False
    if "CC0" in parts or "PD" in parts or ("PUBLIC" in parts and "DOMAIN" in parts):
        return True
    if "CC" in parts and "BY" in parts:
        attrs = {p for p in parts if p in ("BY", "SA", "NC", "ND")}
        return attrs <= {"BY", "SA"}
    return False


# --------------------------------------------------------------------------- #
# Rate limiting (caller-supplied, per source; mirrors the Nominatim <=1 req/s rule).
# --------------------------------------------------------------------------- #

class RateLimiter:
    """Enforce a minimum interval between calls. Injectable clock/sleep for tests."""

    def __init__(self, min_interval=1.0, sleep=time.sleep, clock=time.monotonic):
        self.min_interval = min_interval
        self._sleep = sleep
        self._clock = clock
        self._last = None

    def wait(self):
        if self.min_interval <= 0:
            return
        if self._last is not None:
            elapsed = self._clock() - self._last
            if elapsed < self.min_interval:
                self._sleep(self.min_interval - elapsed)
        self._last = self._clock()


def _wait(rate_limiter):
    if rate_limiter is not None:
        rate_limiter.wait()


# --------------------------------------------------------------------------- #
# Source searchers -> candidate dicts.
# A candidate: {source, image_url, thumb_url, license, author, source_url, lat, lng}
# --------------------------------------------------------------------------- #

def _strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _normalize_openverse_license(code):
    if not code:
        return ""
    c = str(code).strip().lower()
    if c == "cc0":
        return "CC0"
    if c in ("pdm", "pd"):
        return "PD"
    return "CC-" + c.upper()   # by -> CC-BY, by-sa -> CC-BY-SA, by-nc -> CC-BY-NC


def _search_openverse(query, rate_limiter, max_results):
    _wait(rate_limiter)
    resp = requests.get(
        OPENVERSE_API,
        params={"q": query, "license": "cc0,pdm,by,by-sa", "page_size": max_results},
        headers={"User-Agent": USER_AGENT}, timeout=15,
    )
    resp.raise_for_status()
    out = []
    for r in (resp.json() or {}).get("results", []):
        image_url = r.get("url")
        source_url = r.get("foreign_landing_url") or r.get("url")
        if not (image_url and source_url and str(source_url).startswith("https://")):
            continue
        out.append({
            "source": "openverse",
            "image_url": image_url,
            "thumb_url": r.get("thumbnail"),
            "license": _normalize_openverse_license(r.get("license")),
            "author": r.get("creator") or "Unknown",
            "source_url": source_url,
            "lat": None, "lng": None,
        })
    return out


def _search_commons(query, rate_limiter, max_results):
    _wait(rate_limiter)
    resp = requests.get(
        COMMONS_API,
        params={
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": "6",
            "gsrlimit": max_results, "prop": "imageinfo",
            "iiprop": "url|extmetadata", "iiurlwidth": 1280,
        },
        headers={"User-Agent": USER_AGENT}, timeout=15,
    )
    resp.raise_for_status()
    pages = ((resp.json() or {}).get("query") or {}).get("pages") or {}
    out = []
    for page in pages.values():
        ii = (page.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata") or {}
        image_url = ii.get("url")
        source_url = ii.get("descriptionurl")
        if not (image_url and source_url and str(source_url).startswith("https://")):
            continue
        out.append({
            "source": "wikimedia",
            "image_url": image_url,
            "thumb_url": ii.get("thumburl"),
            "license": (meta.get("LicenseShortName") or {}).get("value", ""),
            "author": _strip_html((meta.get("Artist") or {}).get("value", "")) or "Unknown",
            "source_url": source_url,
            "lat": None, "lng": None,
        })
    return out


_SEARCHERS = {"openverse": _search_openverse, "commons": _search_commons}


def _select_candidate(cands, geo, radius_km):
    """First license-clean, location-matched candidate. A geotagged candidate must be
    within radius_km of the POI geocode; an un-geotagged candidate is trusted on the
    name_local query match (landmark-only)."""
    lat0, lng0 = (geo or {}).get("lat"), (geo or {}).get("lng")
    have_geo = isinstance(lat0, (int, float)) and isinstance(lng0, (int, float))
    for c in cands:
        if not license_allowed(c.get("license")):
            continue
        clat, clng = c.get("lat"), c.get("lng")
        if isinstance(clat, (int, float)) and isinstance(clng, (int, float)) and have_geo:
            if not in_region(clat, clng, lat0, lng0, radius_km):
                continue   # geotagged but wrong place
        return c
    return None


# --------------------------------------------------------------------------- #
# Image download -> base64 (2-size).
# --------------------------------------------------------------------------- #

def _to_data_uri(content, content_type):
    return f"data:{content_type};base64,{base64.b64encode(content).decode('ascii')}"


def _fetch_image(url, rate_limiter):
    _wait(rate_limiter)
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
    resp.raise_for_status()
    ctype = (resp.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip()
    if not ctype.startswith("image/"):
        return None
    return _to_data_uri(resp.content, ctype)


def _download_entry(cand, rate_limiter):
    if not (cand.get("source_url") and str(cand["source_url"]).startswith("https://")):
        return None
    full = _fetch_image(cand["image_url"], rate_limiter)
    if full is None:
        return None
    photo = {"data": full}
    thumb_url = cand.get("thumb_url")
    if thumb_url and thumb_url != cand["image_url"]:
        thumb = _fetch_image(thumb_url, rate_limiter)
        if thumb is not None:
            photo["thumb"] = {"data": thumb}
    author = cand.get("author") or "Unknown"
    lic = cand.get("license") or ""
    if not lic:
        return None
    return {
        "photo": photo,
        "photo_attribution": {
            "author": author,
            "license": lic,
            "source_url": cand["source_url"],
        },
        "photo_source": "openverse" if cand["source"] == "openverse" else "wikimedia",
    }


# --------------------------------------------------------------------------- #
# Public API.
# --------------------------------------------------------------------------- #

def _is_landmark(poi):
    cat = str(poi.get("category", "")).lower()
    return not any(tok in cat for tok in _NON_LANDMARK)


def fetch_media_entry(poi, backend="none", *, sources=("openverse", "commons"),
                      radius_km=5.0, rate_limiters=None, max_results=8, cache=None):
    """Resolve a license-clean, location-matched landmark photo for one POI.

    Returns a media entry {photo, photo_attribution, photo_source} or None (no clean
    match / backend none|google). `rate_limiters` is an optional {source: RateLimiter}
    (callers SHOULD pass one per source in production — Commons/Openverse policy).
    `cache` is an optional dict keyed by poi id, storing the entry or None (negative
    cache), mirroring geocode.resolve_place.
    """
    if backend == "none":
        return None
    if backend == "google":
        return None   # BLOCKED: no display-surface ToS clearance / no personal-cache exception
    if backend != "wiki":
        raise ValueError(f"unknown photo backend: {backend!r}")

    name = poi.get("name_local") or poi.get("name_display")
    if not name or not str(name).strip():
        return None

    key = poi.get("id") or str(name)
    if cache is not None and key in cache:
        return cache[key]

    geo = poi.get("geocode") or {}
    rate_limiters = rate_limiters or {}
    entry = None
    for src in sources:
        searcher = _SEARCHERS.get(src)
        if not searcher:
            continue
        try:
            cands = searcher(str(name), rate_limiters.get(src), max_results)
        except requests.RequestException:
            continue
        cand = _select_candidate(cands, geo, radius_km)
        if cand:
            entry = _download_entry(cand, rate_limiters.get(src))
            if entry:
                break

    if cache is not None:
        cache[key] = entry
    return entry


def build_media(pois, backend="none", *, landmark_only=True, **kw):
    """Build a verified-pois-media side-file doc {"media": {poi_id: entry}} for POIs.

    Landmark-only by default (skips restaurant/hotel-type categories). Each POI is
    resolved via fetch_media_entry; only successful matches are recorded.
    """
    media = {}
    for poi in pois or []:
        pid = poi.get("id")
        if not pid:
            continue
        if landmark_only and not _is_landmark(poi):
            continue
        entry = fetch_media_entry(poi, backend, **kw)
        if entry:
            media[pid] = entry
    return {"media": media}


def write_media_sidefile(path, doc):
    """Atomically write a media side-file as YAML (mirrors geocode_cache.save_cache)."""
    parent = os.path.dirname(str(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, allow_unicode=True, sort_keys=True)
    os.replace(tmp, path)
