"""Write trips/<slug>/data/day-maps.yaml: each day's map images from OpenStreetMap
tiles (spec §6.5). Optional -- needs the [maps] extra (Pillow) and the network; the
reader draws a schematic without it.

    python <plugin>/scripts/tripwork.py maps <slug> [--offline]

Segments and points come from the reader itself (scripts/render/reader/maps.py::
day_points / _segments), so the images line up with the pins the reader draws.
Per segment: one 4:3 overview at the largest zoom (<= 15) that fits every point in
<= 1400 px, plus a 640x480 (also 4:3) z16 close-up per point, JPEG q70 (~40 KB each).

OSM tile usage policy: an identifying User-Agent that carries NO personal data
(program name + repo URL), every tile cached under work/<slug>/tile-cache/, and at
least one second between network requests.
"""
if __name__ == "__main__":
    raise SystemExit("moved in tripwork 2.0: python <plugin>/scripts/tripwork.py maps <slug>")

import argparse
import base64
import io
import math
import pathlib
import sys
import time

import yaml

USER_AGENT = "tripwork-day-maps/1.0 (+https://github.com/helping-ai-workflow/tripwork)"
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
ATTRIBUTION = "© OpenStreetMap contributors"
MAX_W, MAX_Z, CLOSE_Z, CLOSE_W, CLOSE_H, PAD, QUALITY = 1400, 15, 16, 640, 480, 60, 70


def _world(lat, lng, z):
    n = 256 * 2 ** z
    y = (1 - math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) / math.pi) / 2 * n
    return (lng + 180) / 360 * n, y


def _latlng(x, y, z):
    n = 256 * 2 ** z
    lng = x / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lng


def _network_fetch(z, x, y):
    import requests
    r = requests.get(TILE_URL.format(z=z, x=x, y=y), headers={"User-Agent": USER_AGENT}, timeout=20)
    r.raise_for_status()
    time.sleep(1.0)
    return r.content


def _not_cached(z, x, y):
    # --offline reads the cache only; a missing tile must not become a grey map that
    # still carries the tile credit and passes the export gate.
    raise LookupError(f"tile {z}/{x}/{y} is not in the cache; run once without --offline")


def _cached(fetch, cache_dir):
    def get(z, x, y):
        p = pathlib.Path(cache_dir) / str(z) / str(x) / f"{y}.png"
        if p.is_file():
            return p.read_bytes()
        data = fetch(z, x, y)
        if data:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        return data
    return get


def _render(get, z, left, top, w, h):
    from PIL import Image
    img = Image.new("RGB", (w, h), (225, 225, 220))
    n = 2 ** z
    for tx in range(int(left // 256), int((left + w) // 256) + 1):
        for ty in range(int(top // 256), int((top + h) // 256) + 1):
            if not 0 <= ty < n:
                continue
            data = get(z, tx % n, ty)
            if not data:
                continue
            tile = Image.open(io.BytesIO(data)).convert("RGB")
            img.paste(tile, (int(tx * 256 - left), int(ty * 256 - top)))
    return img


def _image(img):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=QUALITY, optimize=True)
    return {"data": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(),
            "width": img.width, "height": img.height}


def _bbox(z, left, top, w, h):
    north, west = _latlng(left, top, z)
    south, east = _latlng(left + w, top + h, z)
    return {"north": north, "south": south, "east": east, "west": west}


def _overview(get, geos):
    """The segment's overview at the largest zoom (<= MAX_Z) that fits, always 4:3 (at
    least 480x360) so the phone's full-width 4:3 frame never crops a pin (spec v1.1 §9)."""
    for z in range(MAX_Z, 1, -1):
        px = [_world(lat, lng, z) for lat, lng in geos]
        xs, ys = [p[0] for p in px], [p[1] for p in px]
        span_w, span_h = max(xs) - min(xs) + 2 * PAD, max(ys) - min(ys) + 2 * PAD
        w = math.ceil(max(span_w, span_h * 4 / 3, 480))
        h = math.ceil(w * 3 / 4)
        if w <= MAX_W and h <= MAX_W:
            left = (max(xs) + min(xs)) / 2 - w / 2
            top = (max(ys) + min(ys)) / 2 - h / 2
            return {"image": _image(_render(get, z, left, top, w, h)), "bbox": _bbox(z, left, top, w, h)}
    raise ValueError("points span more than the world")


def _closeup(get, lat, lng):
    cx, cy = _world(lat, lng, CLOSE_Z)
    left, top = cx - CLOSE_W / 2, cy - CLOSE_H / 2
    return {"image": _image(_render(get, CLOSE_Z, left, top, CLOSE_W, CLOSE_H)),
            "bbox": _bbox(CLOSE_Z, left, top, CLOSE_W, CLOSE_H)}


def build(trip_dir, work_dir=None, fetch=None, offline=False):
    """Build and write the side-file; returns the document."""
    from scripts.gate import poi_pool
    from scripts.paths import artifact_path, work_dir_for
    from scripts.render.reader.maps import _geo, _segments, day_points
    from scripts.render.reader.page import _context

    t = pathlib.Path(trip_dir)
    w = pathlib.Path(work_dir) if work_dir else work_dir_for(t)

    def load(name):
        p = artifact_path(t, name)
        return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.is_file() else {}

    pois = load("verified-pois.yaml").get("pois") or []
    acc = load("accommodations.yaml") or {"stops": []}
    ctx = _context(load("itinerary.yaml"), poi_pool(pois, acc), load("trip-brief.yaml"),
                   acc, None, load("legs.yaml") or {"legs": []})
    base = _not_cached if offline else (fetch or _network_fetch)
    get = _cached(base, w / "tile-cache")
    days, lone = {}, {}
    for i, day in enumerate(ctx.days, start=1):
        entries = []
        points = day_points(ctx, i, day)
        in_segment = {id(p) for pts in _segments(points) for p in pts}
        for _, p in points:          # a segment of one (hotel, then a long train) builds no entry
            if id(p) not in in_segment and p["poi"].get("id"):
                lone.setdefault(p["poi"]["id"], p["poi"])
        for pts in _segments(points):
            entry = _overview(get, [_geo(p["poi"]) for p in pts])
            # the stops this image was made for: the reader falls back to its schematic
            # when the itinerary has moved on since (maps.py::map_card)
            entry["poi_ids"] = sorted({p["poi"].get("id") for p in pts if p["poi"].get("id")})
            entry["closeups"] = {}
            for p in pts:
                pid = p["poi"].get("id")
                if pid and pid not in entry["closeups"]:
                    entry["closeups"][pid] = _closeup(get, *_geo(p["poi"]))
            entries.append(entry)
        if entries:
            days[str(day.get("date"))] = entries
    doc = {"attribution": ATTRIBUTION, "days": days}
    # its close-up then lives in the shared map, unless some day's entry already has it
    have = {pid for entries in days.values() for e in entries for pid in e["closeups"]}
    shared = {pid: _closeup(get, *_geo(poi)) for pid, poi in lone.items() if pid not in have}
    if shared:
        doc["closeups"] = shared
    out = artifact_path(t, "day-maps.yaml")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return doc


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("trip_dir")
    ap.add_argument("--work-dir", default=None)
    ap.add_argument("--offline", action="store_true", help="no network: cached tiles only, fail on a missing one")
    args = ap.parse_args(argv)
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("day_maps needs Pillow: pip install 'tripwork[maps]'", file=sys.stderr)
        return 2
    try:
        doc = build(args.trip_dir, args.work_dir, offline=args.offline)
    except LookupError as e:
        print(f"day_maps: {e}", file=sys.stderr)
        return 1
    n = sum(len(v) for v in doc["days"].values())
    print(f"day-maps: {len(doc['days'])} day(s), {n} map(s)")
    return 0
