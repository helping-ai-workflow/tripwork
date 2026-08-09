"""source-verify batch driver: verify every candidate in one trip in one run.

gate.py, export_gate.py, next_stage.py and validate_artifact.py all ship a CLI.
verify.py shipped decision logic only (`verify_poi` / `classify_candidate`), so
the orchestration around it — rate limiting, the geocode cache, resolving each
claimed district's centroid once, official-domain flagging, writing the file —
landed on every consumer, once per trip. Each hand-written driver was a fresh
chance to drop a keyword argument and silently disable a gate (TW-068).

Usage: python scripts/source_verify_run.py <trip-dir> --work-dir <work/<slug>>
       [--offline] [--official-domain SUFFIX ...]

Reads <trip-dir>/trip-brief.yaml + <trip-dir>/candidates.yaml, resolves each
candidate's coordinates (Nominatim via scripts/geocode.py, cached under
<work-dir>/geocode-cache/geocode.json), classifies each candidate through
scripts/verify.py::verify_poi, and writes <trip-dir>/verified-pois.yaml.

--offline skips every Nominatim call and every rate-limit sleep — every
candidate is written unresolved (geocode gates fail honestly), which is what
makes this CLI reachable in tests without a network.

Exit codes (mirrors scripts/gate.py's CLI convention): 0 written and
schema-valid / 1 written but schema-invalid / 2 bad invocation or missing
required input.
"""
if __name__ == "__main__" and __package__ in (None, ""):
    # Drop the auto-added scripts/ dir (it shadows stdlib `calendar` with
    # scripts/calendar.py) and put the repo root on sys.path so `from scripts.X
    # import ...` resolves. See scripts/_cli_bootstrap.py for the full account.
    # Must precede every other import: the shadow breaks `import requests` too.
    import pathlib as _bootpath, sys as _bootsys
    _bootsys.path.insert(0, str(_bootpath.Path(__file__).resolve().parent))
    import _cli_bootstrap        # noqa: F401  (imported for its side effect)

import sys as _sys

import argparse
import datetime
import pathlib
import sys
import time

import yaml

from scripts.geocode import in_region, resolve_place
from scripts.geocode_cache import load_cache, save_cache
from scripts.validate_artifact import validate_file
from scripts.verify import NO_RESOLVED_NAME, is_official_url, verify_poi

# Nominatim usage policy: <= 1 request/second (skills/source-verify/SKILL.md
# Gate 2). Only paid when a lookup actually reaches the network — a cache hit
# never sleeps, so a re-run over an already-resolved trip stays fast.
NOMINATIM_DELAY_S = 1.0

DEFAULT_REGION_RADIUS_KM = 5.0


def _verify_one(poi, geocoded, in_region_flag, local_lang, resolved_name, today):
    """All six inputs are positional so a future edit cannot silently drop one.

    Gate 2b now refuses outright when resolved_name is absent (0.32.0), and Gate
    2c now refuses when geocode_source is absent (this release, Task 0). Gate 1b
    (scripts/verify.py:170-172) is the one that still no-ops SILENTLY when
    local_lang is absent — no error, no warning, just a gate that stops running:
    `if local_lang is not None and local_lang not in langs: return "unverified",
    ...` simply never executes when local_lang is None, and classify_candidate
    falls through to Gate 2 as if the local-language requirement never existed.
    Positional arguments are what stop a future edit from re-creating the
    silent-skip for any of them.
    """
    return verify_poi(poi, geocoded, in_region_flag, local_lang=local_lang,
                      conflict_detected=False, resolved_name=resolved_name,
                      today=today)


def _load_yaml_file(path):
    with pathlib.Path(path).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _flag_official(source, extra_suffixes):
    """Set sources[].official from is_official_url when the research stage
    did not already record it explicitly. Never overrides an explicit flag."""
    if "official" in source:
        return dict(source)
    out = dict(source)
    out["official"] = is_official_url(source.get("url"), extra_suffixes=extra_suffixes)
    return out


def _rate_limited_resolve(name, district, country, cache, name_roman=None):
    """resolve_place wrapper that sleeps NOMINATIM_DELAY_S after every request
    that actually reached the network — never after a cache hit.

    PER REQUEST, not per call (I5). resolve_place walks up to five tiers on a
    hard-to-resolve POI (scripts/geocode.py's resolution order) and this used to
    sleep once for the whole call, so four of those five requests went out back
    to back against a <= 1 req/s policy. Sleeping here for a cache hit was
    already excluded by a `was_hit` pre-check; the `pace` callback expresses the
    same guarantee one level down, where it can see how many requests were
    really issued, and drops the duplicate cache_get that pre-check needed.
    """
    return resolve_place(name, district=district, country=country, cache=cache,
                         name_roman=name_roman,
                         pace=lambda: time.sleep(NOMINATIM_DELAY_S))


def _district_centroid(district, country, cache, offline, district_centroids):
    """Resolve one claimed district's centroid once per run, reusing the same
    per-trip cache resolve_place uses for POIs (skills/source-verify/SKILL.md
    Gate 3). Returns (lat, lng) or None; memoised in district_centroids so a
    second candidate in the same district never re-queries."""
    if not district:
        return None
    if district in district_centroids:
        return district_centroids[district]
    centroid = None
    if not offline:
        result, _source = _rate_limited_resolve(district, None, country, cache)
        if result is not None:
            centroid = (result.lat, result.lng)
    district_centroids[district] = centroid
    return centroid


def _geocode_candidate(cand, country, cache, offline, district_centroids, radius_km):
    """Resolve one candidate's coordinates. Returns (geocode_dict_or_None,
    geocoded, in_region_flag, resolved_name, region_checked).

    --offline never calls resolve_place and never sleeps: every candidate comes
    back unresolved, so the geocode gates fail honestly instead of silently
    passing on data that was never checked.

    geocode_dict, when present, always carries geocode_source
    ('nominatim_structured' / 'nominatim' / 'cluster_fallback') — Task 0 made an
    absent value a Gate 2c refusal, so a POI this function actually geocoded
    must never come back without it.

    region_checked is False whenever there was no district centroid to compare
    against at all — no claimed_district recorded (destination-research
    SKILL.md sanctions omitting it when no source states a location), or its
    own centroid lookup missed. classify_candidate's `in_claimed_region`
    parameter (scripts/verify.py) is a plain bool with no tri-state, so this
    function must never hand it a bare False that actually means "unknown" —
    Gate 3b (scripts/verify.py:221-222) would report that as a genuine region
    mismatch, which is false: no comparison ever ran. So in_region_flag comes
    back True in that case (nothing to disprove); the caller (run()) reads
    region_checked and downgrades an otherwise-'verified' result to an honest
    'unverified' — mirroring Gate 2b's name_match=None and Gate 2c's
    GEOCODE_SOURCE_MISSING, which the same driver bug (Important finding 1,
    fix round 1) had reintroduced for this gate alone.
    """
    if offline:
        return None, False, False, None, False

    name_local = cand.get("name_local") or cand.get("name_display") or ""
    district = cand.get("claimed_district") or ""
    name_roman = cand.get("name_roman")

    centroid = _district_centroid(district, country, cache, offline, district_centroids)
    region_checked = centroid is not None

    result, source = _rate_limited_resolve(name_local, district, country, cache,
                                           name_roman=name_roman)
    if result is not None:
        geo = {"lat": result.lat, "lng": result.lng, "geocode_source": source}
        in_region_flag = (in_region(result.lat, result.lng, centroid[0], centroid[1], radius_km)
                          if region_checked else True)
        return geo, True, in_region_flag, result.display_name, region_checked

    # Nominatim found nothing for the venue itself. Falling back to the
    # district centroid is NOT a general-purpose escape (SKILL.md Gate 2) —
    # classify_candidate's Gate 2 sub-check still requires an independent
    # existence proof (official source / gmaps_place_id) before a
    # cluster_fallback POI can reach 'verified'; this function only records
    # where the coordinate came from, it does not decide whether that is
    # enough. The centroid is the district's own point, so it is in-region by
    # construction (region_checked=True: the centroid *is* the comparison
    # point); there is no resolved display_name to compare a venue name
    # against, so NO_RESOLVED_NAME records "the lookup ran and found nothing to
    # compare" (distinct from None, which means the lookup never ran at all).
    if centroid is not None:
        geo = {"lat": centroid[0], "lng": centroid[1], "geocode_source": "cluster_fallback"}
        return geo, True, True, NO_RESOLVED_NAME, True

    return None, False, False, NO_RESOLVED_NAME, False


def _build_poi(cand, official_domains):
    poi = {
        "id": cand.get("id"),
        "name_local": cand.get("name_local", ""),
        "name_display": cand.get("name_display", ""),
        "category": cand.get("category", ""),
        "district": cand.get("claimed_district", ""),
        "sources": [_flag_official(s, tuple(official_domains)) for s in cand.get("sources", [])],
    }
    if cand.get("name_roman"):
        poi["name_roman"] = cand["name_roman"]
    if cand.get("business_status") is not None:
        poi["business_status"] = cand["business_status"]
    return poi


def run(trip_dir, work_dir, offline=False, official_domains=()):
    """Verify every candidate in trip_dir/candidates.yaml and write
    trip_dir/verified-pois.yaml. Returns (exit_code, pois)."""
    trip_dir = pathlib.Path(trip_dir)
    work_dir = pathlib.Path(work_dir)

    brief = _load_yaml_file(trip_dir / "trip-brief.yaml") or {}
    candidates = (_load_yaml_file(trip_dir / "candidates.yaml") or {}).get("candidates")
    if not isinstance(candidates, list):
        raise TypeError("candidates.yaml 'candidates' is not a list")

    destination = brief.get("destination") or {}
    country = destination.get("country")
    local_lang = destination.get("local_lang")
    radius_km = (brief.get("routing") or {}).get("region_radius_km") or DEFAULT_REGION_RADIUS_KM

    work_dir.mkdir(parents=True, exist_ok=True)
    cache_path = work_dir / "geocode-cache" / "geocode.json"
    cache = load_cache(str(cache_path))

    district_centroids = {}
    today = datetime.date.today()
    pois = []

    for cand in candidates:
        poi = _build_poi(cand, official_domains)
        geo, geocoded, in_region_flag, resolved_name, region_checked = _geocode_candidate(
            cand, country, cache, offline, district_centroids, radius_km)
        if geo is not None:
            poi["geocode"] = geo

        normalised, status, note = _verify_one(
            poi, geocoded, in_region_flag, local_lang, resolved_name, today)

        # Important finding 1 (fix round 1): _geocode_candidate hands
        # classify_candidate in_region_flag=True whenever region_checked is
        # False (nothing to disprove), so an absent/unresolvable
        # claimed_district never collapses into a false 'conflicting'. That
        # also means classify_candidate could return 'verified' without the
        # region ever actually being confirmed — downgrade that specific case
        # here, honestly, rather than upstream (verify.py's in_claimed_region
        # is a plain bool with no tri-state to express "unknown" itself).
        if status == "verified" and not region_checked:
            status = "unverified"
            note = ("region membership unconfirmed: no claimed_district was "
                    "recorded, or its centroid could not be resolved, so the "
                    "geocoded coordinate was never compared against a claimed "
                    "region — record a claimed_district, or confirm the "
                    "venue's district manually")

        normalised["verify_status"] = status
        if note:
            normalised["status_reason"] = note
            if status == "conflicting":
                normalised["conflict_note"] = note
        pois.append(normalised)

    save_cache(str(cache_path), cache)

    out_path = trip_dir / "verified-pois.yaml"
    out_path.write_text(
        yaml.safe_dump({"pois": pois}, allow_unicode=True, sort_keys=False),
        encoding="utf-8")

    code, msgs = validate_file(str(out_path))
    return code, msgs, out_path, pois


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trip_dir", help="trips/<slug> directory")
    ap.add_argument("--work-dir", required=True, help="work/<slug> directory")
    ap.add_argument("--offline", action="store_true",
                    help="skip Nominatim entirely: no network calls, no rate-limit sleeps")
    ap.add_argument("--official-domain", action="append", default=[], metavar="SUFFIX",
                    dest="official_domains",
                    help="extra domain suffix this trip's venues should be flagged "
                         "official for (repeatable)")
    args = ap.parse_args(argv)

    try:
        code, msgs, out_path, pois = run(
            args.trip_dir, args.work_dir, offline=args.offline,
            official_domains=args.official_domains)
    except (FileNotFoundError, KeyError, TypeError, yaml.YAMLError, OSError) as exc:
        print(f"missing/invalid required input: {exc!r}", file=sys.stderr)
        return 2

    if code == 2:
        # validate_file's own usage-error class (unresolvable schema, bad YAML
        # it just wrote) — surface distinctly from a plain schema failure.
        for m in msgs:
            print(m, file=sys.stderr)
        return 2

    stream = sys.stdout if code == 0 else sys.stderr
    for m in msgs:
        print(m, file=stream)
    from collections import Counter
    counts = dict(Counter(p["verify_status"] for p in pois))
    print(f"source-verify: wrote {out_path} ({len(pois)} POIs) {counts}")
    return 0 if code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv[1:]))
