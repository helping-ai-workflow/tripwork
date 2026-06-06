"""Per-trip geocode cache — pure dict ops + thin JSON file I/O.

resolve_place consults this so re-runs skip already-resolved (and known-miss)
Nominatim lookups. A cached miss is stored as None (negative caching); cache_get
returns (hit, value) so a cached None is a HIT that short-circuits the network.
"""
import json
import os


def cache_key(name, district=None, country=None):
    """Normalized lookup key: lower-cased, stripped, '|'-joined; None parts -> ''."""
    return "|".join((p or "").strip().lower() for p in (name, district, country))


def cache_get(cache, key):
    """Return (hit, value). hit=True when key is present (value may be None for a
    cached miss — still a hit). hit=False when the key is absent."""
    if key in cache:
        return True, cache[key]
    return False, None


def cache_put(cache, key, value):
    """Store value (a {lat,lng,display_name,source} dict, or None for a miss)."""
    cache[key] = value


def load_cache(path):
    """Read the JSON cache dict from `path`; {} if the file is absent."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_cache(path, cache):
    """Write the cache dict to `path` as JSON, creating parent dirs."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
