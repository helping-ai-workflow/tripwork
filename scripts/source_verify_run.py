"""source-verify batch driver: verify every candidate in one trip in one run.

gate.py, export_gate.py, next_stage.py and validate_artifact.py all ship a CLI.
verify.py shipped decision logic only (`verify_poi` / `classify_candidate`), so
the orchestration around it — rate limiting, the geocode cache, resolving each
claimed district's centroid once, official-domain flagging, writing the file —
landed on every consumer, once per trip. Each hand-written driver was a fresh
chance to drop a keyword argument and silently disable a gate (TW-068).

Usage: python <plugin>/scripts/tripwork.py verify <slug>
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
if __name__ == "__main__":
    raise SystemExit("moved in tripwork 2.0: python <plugin>/scripts/tripwork.py verify <slug>")


import argparse
import datetime
import pathlib
import re
import sys
import time

import requests
import yaml

from scripts.geocode import (address_is_fine, address_point, country_code, in_region, pick_point,
                             place_point, resolve_place)
from scripts.paths import artifact_path
from scripts.geocode_cache import load_cache, save_cache
from scripts.validate_artifact import validate_file
from scripts.verify import NO_RESOLVED_NAME, is_official_url, verify_poi

# Nominatim usage policy: <= 1 request/second (skills/source-verify/SKILL.md
# Gate 2). Only paid when a lookup actually reaches the network — a cache hit
# never sleeps, so a re-run over an already-resolved trip stays fast.
NOMINATIM_DELAY_S = 1.0

DEFAULT_REGION_RADIUS_KM = 5.0

# Fields this driver writes itself on every run. Everything else a verified-pois
# record can hold but a candidate cannot (name_zh, gmaps_place_id, hours,
# closed_days, the legacy photo fields) is recorded by a later overlay, so a re-run
# keeps it (TW-090) -- see _carried_keys().
DRIVER_COMPUTED = ("district", "geocode", "resolved_name", "status_reason", "conflict_note",
                   "verify_status")


def _carried_keys():
    """verified-pois fields a candidate cannot carry and this driver does not compute,
    read from the two schemas so a field added to either is covered."""
    import json
    root = pathlib.Path(__file__).resolve().parent.parent / "schemas"
    item = lambda name, key: json.loads((root / name).read_text(encoding="utf-8"))[
        "properties"][key]["items"]["properties"]
    return sorted(set(item("verified-pois.schema.json", "pois"))
                  - set(item("candidates.schema.json", "candidates")) - set(DRIVER_COMPUTED))


def _carry_over(poi, prior, cand):
    """Keep what an overlay recorded on the previous run (TW-090): carried fields the
    new record lacks, and a source's `official` flag for the same URL -- unless the
    candidate itself states `official` for that URL (research's word wins)."""
    if not prior:
        return poi
    stated = {s.get("url") for s in cand.get("sources") or [] if "official" in s}
    for key in _carried_keys():
        if key not in poi and key in prior:
            poi[key] = prior[key]
    official = {s.get("url") for s in prior.get("sources") or [] if s.get("official")}
    for s in poi.get("sources") or []:
        if s.get("url") in official and s.get("url") not in stated:
            s["official"] = True
    return poi


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


def _rate_limited_address(address, country, cache):
    """geocode.address_point, paced per request like _rate_limited_resolve ->
    (point or None, fine): fine when the point is the address or its 丁目, not its town."""
    pace = lambda: time.sleep(NOMINATIM_DELAY_S)
    ref, variant = address_point(address, country=country, cache=cache, pace=pace)
    fine = ref is not None and address_is_fine(address, variant, country_code(country, cache=cache, pace=pace))
    return ref, fine


def _rate_limited_resolve(name, district, country, cache, name_roman=None, area=False):
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
                         name_roman=name_roman, area=area,
                         pace=lambda: time.sleep(NOMINATIM_DELAY_S))


_VARIANTS = str.maketrans({"區": "区", "縣": "県", "鄉": "郷"})
_UPPER_UNIT = re.compile(r"^.+?[都道府県市郡]")
_LOCAL_UNIT = re.compile(r"^.+?[区町村郷鎮]")


def district_key(district):
    """The place a district names below its city -- what a centroid's display_name
    must contain to have landed there (TW-092): '小樽市堺町' -> '堺町',
    '札幌市中央区北3条西2丁目' -> '中央区', '嘉義市西區' -> '西区'. Parentheses are
    dropped ('堺町（小樽市）' -> '堺町'); a name with no CJK unit is its first
    comma part, casefolded."""
    s = re.sub(r"[（(][^）)]*[）)]", "", str(district or "")).strip().translate(_VARIANTS)
    if not re.search(r"[\u3400-\u9fff]", s):
        return s.split(",")[0].strip().casefold()
    last = s
    while (m := _UPPER_UNIT.match(s)) and m.end() < len(s):
        last, s = m.group(0), s[m.end():]
    if not s:
        return last
    m = _LOCAL_UNIT.match(s)
    return m.group(0) if m else s


def _own_place(name):
    """A result's own name below its city, whole: '嘉義市西區' -> '西区', but
    '嘉義市西區國民小學' -> '西区国民小学' (district_key would cut it to '西区')."""
    s = re.sub(r"[（(][^）)]*[）)]", "", str(name or "")).strip().translate(_VARIANTS)
    if not re.search(r"[\u3400-\u9fff]", s):
        return s.casefold()
    while (m := _UPPER_UNIT.match(s)) and m.end() < len(s):
        s = s[m.end():]
    return s


def _landed_in(district, display_name):
    """The result IS the district: its own name (display_name's first part, below its
    city) is the district -- with its unit (函館 -> 函館市), one of its numbered blocks
    (堺町一丁目), or its deepest part (壮瞥町昭和新山 -> 昭和新山). A school or office named after the district, or one that only lies in
    it, is not its centroid."""
    own = _own_place(str(display_name or "").split(",")[0])
    key = district_key(district)
    if re.fullmatch(re.escape(key) + r"(?:[都道府県市郡区町村郷鎮]|[0-9０-９一二三四五六七八九十]+丁目)?", own):
        return True
    # the district's deepest part: '壮瞥町昭和新山' landed on '昭和新山'
    whole = _own_place(district)
    return len(own) >= 2 and whole.endswith(own)


def _district_fallback(district, country, cache):
    """A district the settlement lookup missed (v1.3.0): OSM may hold it only as its 丁目
    or tag it neighbourhood (e2e: three of a trip's districts). A plain query for a place of
    that name, then (Japan) its first 丁目, paced -- only a result that is the district
    (_landed_in), never a building or stop named after it. None when neither lands."""
    pace = lambda: time.sleep(NOMINATIM_DELAY_S)
    tries = [district]
    if country_code(country, cache=cache, pace=pace) == "jp" and re.search(r"[\u3400-\u9fff]", district):
        tries.append(district + "一丁目")
    for q in tries:
        r = place_point(q, country=country, cache=cache, pace=pace)
        if r is not None and _landed_in(district, r.display_name):
            return r
    return None


def _district_centroid(district, country, cache, offline, district_centroids):
    """Resolve one claimed district's centroid once per run, reusing the same
    per-trip cache resolve_place uses for POIs (skills/source-verify/SKILL.md
    Gate 3). Returns (lat, lng) or None; memoised in district_centroids so a
    second candidate in the same district never re-queries.

    A result whose display_name does not name the district (district_key) is
    refused (TW-092: '小樽市堺町' resolved to a museum in 色内, 0.75 km off): a
    wrong centroid would pass the region check and stand in as a venue's
    coordinate. The district is looked up as a place (area=True: a settlement,
    no street-slot venue query), and only a result whose own name is the district
    counts -- a school named after the district is not it (v1.2.1). Refused means None -- region unconfirmed, honestly unverified --
    and `district_query` is how the candidate supplies a lookup string that lands."""
    if not district:
        return None
    if district in district_centroids:
        return district_centroids[district]
    centroid = None
    if not offline:
        result, _source = _rate_limited_resolve(district, None, country, cache, area=True)
        if result is not None and _landed_in(district, result.display_name):
            centroid = (result.lat, result.lng)
        else:
            r = _district_fallback(district, country, cache)
            if r is not None:
                centroid = (r.lat, r.lng)
    district_centroids[district] = centroid
    return centroid


def _lookup_query(cand):
    """The strings a candidate is geocoded with (recorded as geocode.query)."""
    q = {"name": cand.get("name_local") or cand.get("name_display") or "",
         # TW-092: district_query is the geocode string; claimed_district stays the
         # readable name the deliverable shows and links with (_build_poi)
         "district": cand.get("district_query") or cand.get("claimed_district") or ""}
    if cand.get("name_roman"):
        q["name_roman"] = cand["name_roman"]
    if cand.get("address_local"):                     # v1.3.0: the address checks the name lookup
        q["address"] = cand["address_local"]
    return q


def _confirmed_geocode(prior, cand):
    """The previous run's coordinate when it is still the answer (TW-097): the POI was
    `verified` and is looked up with the same strings. A verified coordinate may be a
    decision made after a 'conflicting' stop (trip-e: "一番館" geocodes to a
    Nara restaurant, so the POI was confirmed on its district centroid with a place
    id); looking it up again only re-asks the question that decision answered. A
    record written before geocode.query existed is matched on its own name_local /
    name_roman / district (the district may be the readable name or the lookup one)."""
    if not prior or prior.get("verify_status") != "verified":
        return None
    geo = prior.get("geocode") or {}
    if not geo.get("geocode_source") or geo.get("lat") is None or geo.get("lng") is None:
        return None
    now = _lookup_query(cand)
    if "query" in geo:
        same = geo["query"] == now
    else:
        same = (prior.get("name_local") == cand.get("name_local")
                and prior.get("name_roman") == cand.get("name_roman")
                and prior.get("district", "") in (now["district"], cand.get("claimed_district") or ""))
    return dict(geo, query=now) if same else None


def _geocode_candidate(cand, country, cache, offline, district_centroids, radius_km, kept=None):
    """Resolve one candidate's coordinates. Returns (geocode_dict_or_None,
    geocoded, in_region_flag, resolved_name, region_checked).

    --offline never calls resolve_place and never sleeps: every candidate comes
    back unresolved, so the geocode gates fail honestly instead of silently
    passing on data that was never checked.

    geocode_dict, when present, always carries geocode_source
    ('nominatim_structured' / 'nominatim' / 'nominatim_address' / 'cluster_fallback') — Task 0 made an
    absent value a refusal (the GEOCODE_SOURCE_MISSING sentinel,
    scripts/verify.py::classify_candidate's Gate 2), so a POI this function
    actually geocoded must never come back without it.

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
    'unverified' — mirroring Gate 2b's name_match=None and Gate 2's
    GEOCODE_SOURCE_MISSING sentinel, which the same driver bug (Important
    finding 1, fix round 1) had reintroduced for this gate alone. (That
    sentinel is unrelated to, and survives, Gate 2c's later v0.34.0
    retirement — see classify_candidate's old call site.)
    """
    if offline:
        return None, False, False, None, False

    query = _lookup_query(cand)
    name_local, district, name_roman = query["name"], query["district"], query.get("name_roman")

    if kept is not None:
        # TW-097: the confirmed coordinate stands; the region is checked again, so a
        # district_query that now lands still counts. A centroid coordinate is
        # in-region by construction, as in the fallback branch below.
        resolved = kept.pop("resolved_name", None)
        resolved = NO_RESOLVED_NAME if resolved in (None, "NO_RESULT") else resolved
        if kept.get("geocode_source") == "cluster_fallback":
            return kept, True, True, resolved, True
        centroid = _district_centroid(district, country, cache, offline, district_centroids)
        inside = (in_region(kept["lat"], kept["lng"], centroid[0], centroid[1], radius_km)
                  if centroid is not None else True)
        return kept, True, inside, resolved, centroid is not None

    centroid = _district_centroid(district, country, cache, offline, district_centroids)
    region_checked = centroid is not None

    result, source = _rate_limited_resolve(name_local, district, country, cache,
                                           name_roman=name_roman)
    # v1.3.0: the venue's sourced address checks the name lookup. A name hit far from the
    # address is a namesake (a bare-name tier found the same name elsewhere): dropped. With
    # no name hit left, the address point (its 丁目 or town) stands in, recorded as
    # nominatim_address -- approximate, disclosed like a centroid, a coordinate-only hit.
    # An address point only counts when it is fine (the address or its 丁目, not the town)
    # and lies in the claimed district: a full-text address can match far away (e2e
    # 2026-10-05: 1285 km and 58 km off), and without a district centre nothing confirms it.
    if query.get("address"):
        ref, fine = _rate_limited_address(query["address"], country, cache)
        if ref is not None and not (region_checked and fine
                                    and in_region(ref.lat, ref.lng, centroid[0], centroid[1], radius_km)):
            ref = None
        point, kind = pick_point(result, source, ref)
        if kind == "nominatim_address":
            geo = {"lat": point.lat, "lng": point.lng, "geocode_source": kind, "query": query}
            in_region_flag = (in_region(point.lat, point.lng, centroid[0], centroid[1], radius_km)
                              if region_checked else True)
            return geo, True, in_region_flag, NO_RESOLVED_NAME, region_checked
        result = point
    if result is not None:
        geo = {"lat": result.lat, "lng": result.lng, "geocode_source": source, "query": query}
        in_region_flag = (in_region(result.lat, result.lng, centroid[0], centroid[1], radius_km)
                          if region_checked else True)
        return geo, True, in_region_flag, result.display_name, region_checked

    # Nominatim found nothing for the venue itself. Falling back to the
    # district centroid records WHERE the coordinate came from; it does not
    # decide whether that is enough to verify. Through v0.33.0 that decision
    # was classify_candidate's own Gate 2 cluster_fallback sub-check, which
    # required an independent existence proof (official source /
    # gmaps_place_id) before a cluster_fallback POI could reach 'verified'.
    # That sub-check is RETIRED as of v0.34.0 (Gate 2c subsumed by Gate 0 --
    # see scripts/verify.py::classify_candidate's old call site): a sourced
    # business_status is itself an existence proof, so a POI that clears
    # Gate 0 already carries it, and the separate check became unreachable.
    # The centroid is the district's own point, so it is in-region by
    # construction (region_checked=True: the centroid *is* the comparison
    # point); there is no resolved display_name to compare a venue name
    # against, so NO_RESOLVED_NAME records "the lookup ran and found nothing to
    # compare" (distinct from None, which means the lookup never ran at all).
    if centroid is not None:
        geo = {"lat": centroid[0], "lng": centroid[1], "geocode_source": "cluster_fallback", "query": query}
        return geo, True, True, NO_RESOLVED_NAME, True

    return None, False, False, NO_RESOLVED_NAME, False


def _build_poi(cand, official_domains, resolved_name):
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
    # v1.0 P2: carried through so a re-verify does not wipe them (research
    # records them on the candidate; this driver rebuilds verified-pois from
    # candidates on every run).
    for key in ("intro", "intro_source", "booking", "address_local", "address_source"):
        if cand.get(key) is not None:
            poi[key] = cand[key]
    if resolved_name is NO_RESOLVED_NAME:
        poi["resolved_name"] = "NO_RESULT"
    elif resolved_name:
        poi["resolved_name"] = resolved_name
    return poi


def run(trip_dir, work_dir, offline=False, official_domains=(), regeocode=False):
    """Verify every candidate in trip_dir/data/candidates.yaml and write
    trip_dir/data/verified-pois.yaml (scripts/paths.py). Returns (exit_code, pois)."""
    trip_dir = pathlib.Path(trip_dir)
    work_dir = pathlib.Path(work_dir)

    brief = _load_yaml_file(artifact_path(trip_dir, "trip-brief.yaml")) or {}
    candidates = (_load_yaml_file(artifact_path(trip_dir, "candidates.yaml")) or {}).get("candidates")
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
    prior_path = artifact_path(trip_dir, "verified-pois.yaml")
    prior_doc = (_load_yaml_file(prior_path) if prior_path.is_file() else None) or {}
    prior = {p.get("id"): p for p in (prior_doc.get("pois") or []) if isinstance(p, dict)}

    # v1.3.0: the cache is saved even when a failure (a network that outlasts the retries,
    # Ctrl+C) leaves the loop, so it costs one re-run, not the run's progress
    try:
        for cand in candidates:
            old = prior.get(cand.get("id"))
            kept = None if regeocode else _confirmed_geocode(old, cand)
            if kept is not None:
                kept["resolved_name"] = old.get("resolved_name")
            geo, geocoded, in_region_flag, resolved_name, region_checked = _geocode_candidate(
                cand, country, cache, offline, district_centroids, radius_km, kept=kept)
            poi = _carry_over(_build_poi(cand, official_domains, resolved_name),
                              prior.get(cand.get("id")), cand)
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
    finally:
        save_cache(str(cache_path), cache)

    out_path = artifact_path(trip_dir, "verified-pois.yaml")
    out_path.parent.mkdir(parents=True, exist_ok=True)
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
    ap.add_argument("--regeocode", action="store_true",
                    help="look every POI up again, even one whose coordinate a previous run "
                         "verified with the same lookup strings (TW-097)")
    ap.add_argument("--official-domain", action="append", default=[], metavar="SUFFIX",
                    dest="official_domains",
                    help="extra domain suffix this trip's venues should be flagged "
                         "official for (repeatable)")
    args = ap.parse_args(argv)

    try:
        code, msgs, out_path, pois = run(
            args.trip_dir, args.work_dir, offline=args.offline,
            official_domains=args.official_domains, regeocode=args.regeocode)
    except requests.exceptions.RequestException as exc:
        # before OSError: requests' errors are OSErrors, and a network failure is not a
        # missing input (v1.3.0). The geocode cache already holds what was looked up.
        print(f"Nominatim could not be reached after retries ({exc.__class__.__name__}); "
              "the lookups so far are saved -- re-run to continue", file=sys.stderr)
        return 1
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
