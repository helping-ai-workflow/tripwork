"""The day map card (spec §6.5 / §6.8).

Chips in arrangement C (全圖 / 出發 / each stop's time / 回家) are labels for the
day's anchors (v1.1 §8.1: chips and stops jump to the same :target), so choosing a chip and opening a stop are one gesture;
出發 / 回家 / 全圖 jump to the day's start / end / top targets. Each selection shows one view: the
overview, a stop's close-up (or the overview with that stop highlighted), the
hotel. Tapping a view's frame toggles a checkbox that makes the view fullscreen
(tap again or on the dark area to close; pinch zoom is the browser's own).

Images come from the day-maps side-file (scripts/day_maps.py); pins are never
stored there -- each POI's geocode is projected through the image's bbox here,
so a moved POI never leaves a stale pin. Without an image the card draws an SVG
grid schematic. Neither draws a visiting-order line.
"""
import hashlib
import math
import re

from scripts.render.reader.assets import icon
from scripts.render.reader.home import _name
from scripts.render.reader.text import esc, number

MARGIN = 28                       # px kept free at the image edge for a clamped pin
OSM_COPYRIGHT = "https://www.openstreetmap.org/copyright"   # named in the licence comment only
# user check (2026-10-02): the credit is plain text everywhere (its copyright link was
# tapped by accident); the zoom bar opens the live map of the area being viewed -- Google
# Maps since 2026-10-03 (the user's call; the tiles, and so the credit, stay OSM's)
LIVE_VIEW = (390, 600)               # px the live map is fitted to: a phone screen


def live_url(bboxes):
    """Google Maps centred on the boxes, at the closest zoom that shows them whole on a
    phone (Web Mercator: 256 px tiles, the same zoom levels Google uses)."""
    n = max(b["north"] for b in bboxes)
    s = min(b["south"] for b in bboxes)
    e = max(b["east"] for b in bboxes)
    w = min(b["west"] for b in bboxes)
    merc = lambda lat: math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    dx, dy = math.radians(e - w) or 1e-9, (merc(n) - merc(s)) or 1e-9
    z = min(math.log2(LIVE_VIEW[0] * 2 * math.pi / (256 * dx)), math.log2(LIVE_VIEW[1] * 2 * math.pi / (256 * dy)))
    z = max(2, min(18, math.floor(z)))
    return f"https://www.google.com/maps/@{(n + s) / 2:.5f},{(e + w) / 2:.5f},{z}z"
PHONE_W = 360                     # a tag is ~24 px tall at this display width
SCHEMATIC_W = 640


def _merc(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def project(lat, lng, bbox, w, h):
    """(x, y) pixels of a coordinate inside an image spanning `bbox` (Web Mercator)."""
    x = (lng - bbox["west"]) / (bbox["east"] - bbox["west"]) * w
    top, bottom = _merc(bbox["north"]), _merc(bbox["south"])
    y = (top - _merc(lat)) / (top - bottom) * h
    return x, y


def _geo(p):
    g = (p or {}).get("geocode") or {}
    lat, lng = number(g.get("lat")), number(g.get("lng"))
    return (lat, lng) if lat is not None and lng is not None else None


# Map labels of the day's two ends (v2.1.0 D10: home is drawn, so 回家 now means home; the
# hotel is 旅館 at either end). The user's pick on the design board (H1).
LABELS = {"home_start": "出發", "home_end": "回家", "home_merged": "出發・回家",
          "hotel_start": "旅館", "hotel_end": "旅館", "hotel_merged": "旅館"}
HOME_IDS = ("home-origin", "home-return")


def home_poi(brief, which):
    """The brief's home point as a POI-shaped record the map draws (v2.1.0 D10), or None.
    `which` is 'origin' or 'return'; ids are HOME_IDS, never a POI's (the schema refuses them)."""
    pt = (brief or {}).get(f"home_{which}_point")
    if not isinstance(pt, dict) or number(pt.get("lat")) is None or number(pt.get("lng")) is None:
        return None
    return {"id": HOME_IDS[0] if which == "origin" else HOME_IDS[1], "name_display": pt.get("name") or "",
            "geocode": {"lat": pt["lat"], "lng": pt["lng"], "geocode_source": pt.get("geocode_source")}}


def _home_leg_far(ctx, leg):
    """A home leg longer than routing.max_hop_mins (the same <= as classify_hop), or with no
    duration, puts home on a map of its own."""
    from scripts.rederive import MAX_HOP_MINS
    limit = ((ctx.brief or {}).get("routing") or {}).get("max_hop_mins") or MAX_HOP_MINS
    mins = number(leg.get("duration_mins"))
    return mins is None or mins > limit


def _home_leg(ctx, r):
    legs = (ctx.legs or {}).get("legs") or []
    li = r.get("leg_index")
    if isinstance(li, int) and not isinstance(li, bool) and 0 <= li < len(legs) \
            and isinstance(legs[li], dict) and legs[li].get("kind") == "home":
        return legs[li]
    return None


def day_points(ctx, i, day):
    """[(segment index, point)] in chain order. A point is a dict with key (view name),
    target node (d<N>-<key>), chip text, poi, kind and tag text. Long moves (leg_index) start a new
    segment; stops with no geocode are not points. The first day starts at home and the
    last day ends there when the brief records the point (home_origin_point /
    home_return_point): a home leg within max_hop_mins keeps it on the stops' map, a longer
    one gives it a map of its own -- the leg touching home decides for a chain of them."""
    rows = [r for r in day.get("rows") or [] if isinstance(r, dict)]
    start = ctx.poi_map.get(ctx.days[i - 2].get("lodging")) if i > 1 and ctx.days[i - 2].get("lodging") else None
    end = ctx.poi_map.get(day.get("lodging")) if day.get("lodging") else None
    hotels = {id(x) for x in (start, end) if x}
    home_start = home_poi(ctx.brief, "origin") if i == 1 else None
    home_end = home_poi(ctx.brief, "return") if i == len(ctx.days) else None
    if home_start and home_end and _geo(home_start) == _geo(home_end):
        home_end = home_start                                     # a day trip from home: one point
    home_rows = [r for r in rows if r.get("slot") == "move" and _home_leg(ctx, r)]
    far_start = _home_leg_far(ctx, _home_leg(ctx, home_rows[0])) if home_rows else False
    far_end = _home_leg_far(ctx, _home_leg(ctx, home_rows[-1])) if home_rows else False
    merged = home_start is not None and home_start is home_end
    pts, seg = [], 0
    if home_start:
        label = LABELS["home_merged" if merged else "home_start"]
        pts.append((seg, {"key": "home-start", "radio": f"d{i}-home-start", "chip": label, "poi": home_start,
                          "kind": "home", "tag": label}))
    if start and _geo(start):
        pts.append((seg, {"key": "start", "radio": f"d{i}-start", "chip": LABELS["hotel_start"], "poi": start,
                          "kind": "lodging", "tag": LABELS["hotel_start"]}))
    for j, r in enumerate(rows):
        if r.get("slot") == "move":
            if r.get("leg_index") is not None:
                before_stops = len(pts) <= bool(home_start)
                if home_start and before_stops and r is home_rows[0]:
                    seg += far_start          # the leg leaving home decides whether home joins
                elif home_end and not before_stops and r is home_rows[-1]:
                    seg += far_end            # the leg reaching home decides
                else:
                    seg += 1                  # every other long move starts a new map, as before
            continue
        p = ctx.poi_map.get(r.get("poi_id"))
        if not p or id(p) in hotels or not _geo(p):
            continue
        pts.append((seg, {"key": f"s{j}", "radio": f"d{i}-s{j}", "chip": r.get("time") or _name(p),
                          "poi": p, "kind": r.get("slot") or "visit", "tag": r.get("time") or _name(p)}))
    if end and _geo(end):
        pts.append((seg, {"key": "end", "radio": f"d{i}-end", "chip": LABELS["hotel_end"], "poi": end,
                          "kind": "lodging", "tag": LABELS["hotel_end"]}))
    if home_end:
        label = LABELS["home_merged" if merged else "home_end"]
        pts.append((seg, {"key": "home-end", "radio": f"d{i}-home-end", "chip": label, "poi": home_end,
                          "kind": "home", "tag": label}))
    # #38 M3: the stops are numbered in the day's order (ends -- hotel, home -- are not)
    n = 0
    for _, p in pts:
        if p["kind"] not in ("lodging", "home"):
            n += 1
            p["no"] = n
        b = _building(p)
        if b:                                                   # #35: its building's name
            p["building"] = _name(ctx.poi_map.get(b)) or ""
    return pts


# #38 M4 (user's pick, 2026-11-18): an end of the day -- the hotel, home -- this far from
# the stops is left out of the overview and drawn as an arrow at its edge, so a day trip's
# 1.5 km street is not shrunk into a corner of a 35 km frame
FAR_RATIO, FAR_KM = 3, 10


def far_ends(pts):
    """Keys of the segment's ends lying over FAR_KM from the stops' centre AND over
    FAR_RATIO times the stops' own spread. scripts/day_maps.py frames the overview
    without them; the reader draws them as edge arrows."""
    from scripts.distance import haversine_km
    stops = [p for p in pts if p.get("kind") not in ("lodging", "home")]
    ends = [p for p in pts if p.get("kind") in ("lodging", "home")]
    if not stops or not ends:
        return set()
    g = [_geo(p["poi"]) for p in stops]
    spread = max((haversine_km(*a, *b) for a in g for b in g), default=0.0)
    c = (sum(x for x, _ in g) / len(g), sum(y for _, y in g) / len(g))
    return {p["key"] for p in ends
            if (d := haversine_km(*_geo(p["poi"]), *c)) > FAR_KM and d > FAR_RATIO * spread}


def _km_from(p, pts):
    from scripts.distance import haversine_km
    g = [_geo(q["poi"]) for q in pts]
    c = (sum(x for x, _ in g) / len(g), sum(y for _, y in g) / len(g))
    return haversine_km(*_geo(p["poi"]), *c)


def view_of_row(ctx, i, day):
    """{d<N>-s<J>: view key} for every stop row on the day, so a stop the map cannot
    show (no geocode) still selects something sensible (the overview), and the hotel
    dinner lights 回家 (spec §6.8)."""
    rows = [r for r in day.get("rows") or [] if isinstance(r, dict)]
    keys = {pt["key"] for _, pt in day_points(ctx, i, day)}
    start = ctx.days[i - 2].get("lodging") if i > 1 else None
    out = {}
    for j, r in enumerate(rows):
        if r.get("slot") == "move":
            continue
        pid = r.get("poi_id")
        if f"s{j}" in keys:
            out[f"d{i}-s{j}"] = f"s{j}"
        elif pid and pid == day.get("lodging") and "end" in keys:
            out[f"d{i}-s{j}"] = "end"
        elif pid and pid == start and "start" in keys:
            out[f"d{i}-s{j}"] = "start"
        else:
            out[f"d{i}-s{j}"] = "all"
    return out


def _segments(points):
    """The day's maps: points grouped by segment. A segment of one is dropped (its stop gets
    a close-up instead), except home's own (v2.1.0 D10: a far home is a small map)."""
    segs = {}
    for s, pt in points:
        segs.setdefault(s, []).append(pt)
    return [pts for _, pts in sorted(segs.items())
            if len(pts) >= 2 or (len(pts) == 1 and pts[0].get("kind") == "home")]


def _schematic_bbox(pts):
    lats = [_geo(p["poi"])[0] for p in pts]
    lngs = [_geo(p["poi"])[1] for p in pts]
    dlat, dlng = max(max(lats) - min(lats), 0.004), max(max(lngs) - min(lngs), 0.004)
    return {"north": max(lats) + dlat * 0.15, "south": min(lats) - dlat * 0.15,
            "east": max(lngs) + dlng * 0.15, "west": min(lngs) - dlng * 0.15}


def _schematic_size(bbox):
    xs = bbox["east"] - bbox["west"]
    ys = math.degrees(_merc(bbox["north"]) - _merc(bbox["south"]))
    h = int(SCHEMATIC_W * ys / xs) if xs else SCHEMATIC_W
    return SCHEMATIC_W, max(320, min(h, 800))


def _label_w(text):
    """Width of a 14 px bold label in tag units (~phone px), measured on the reader's
    font in WebKit and Chromium (the wider of the two): digits and ':' 7, other Latin
    8, CJK 14; +3 a side for the white halo. A stop with no time is labelled by name."""
    return sum(14 if ord(c) > 0x2000 else 7 if c.isdigit() or c == ":" else 8 for c in text) + 6


_RINGS = (22, 34, 48, 64, 82, 104)      # tag units from the dot, nearest first


def _spot(x, y, tw, s, w, h, taken):
    """Nearest free spot for a tw-wide label around (x, y): rings outward, 16 angles
    each (stretched sideways, labels are wide); None when the frame is full."""
    hh = 20
    for ring in _RINGS:
        for a in range(16):
            ang = -math.pi / 2 + a * math.pi / 8
            tx = x + math.cos(ang) * ring * s * (1.6 if abs(math.cos(ang)) > .5 else 1)
            ty = y + math.sin(ang) * ring * s
            box = (tx - tw * s / 2, ty - hh * s / 2, tx + tw * s / 2, ty + hh * s / 2)
            if box[0] < 0 or box[1] < 0 or box[2] > w or box[3] > h:
                continue
            if any(box[0] < o[2] and o[0] < box[2] and box[1] < o[3] and o[1] < box[3] for o in taken):
                continue
            return tx, ty, box
    return None


def _groups(marks):
    """Marks drawn on one spot (#38 M5 / #35): [[index, ...], ...] for every spot held
    by more than one -- a shared fallback coordinate, or shops inside one building."""
    spots = {}
    for k, (_pt, x, y, _tag) in enumerate(marks):
        spots.setdefault((round(x), round(y)), []).append(k)
    return [ks for ks in spots.values() if len(ks) > 1]


def _building(pt):
    return ((pt["poi"].get("geocode") or {}).get("parent") or pt["poi"].get("inside")) if pt.get("poi") else None


def _edge(pt, bbox, w, h, s, km):
    """#38 M4: an arrow at the frame's edge pointing at a far end, with its name and
    distance -- '旅館 約 31 km'."""
    lat, lng = _geo(pt["poi"])
    x, y = project(lat, lng, bbox, w, h)
    cx, cy = w / 2, h / 2
    dx, dy = x - cx, y - cy
    if not dx and not dy:
        return ""
    inset = 16 * s
    t = min((cx - inset) / abs(dx) if dx else math.inf, (cy - inset) / abs(dy) if dy else math.inf)
    ex, ey = cx + dx * t, cy + dy * t
    ang = math.degrees(math.atan2(dy, dx))
    label = f"{pt['tag']} 約 {round(km)} km"
    lx, ly = ex - dx * (40 * s / math.hypot(dx, dy)), ey - dy * (40 * s / math.hypot(dx, dy))
    lw = _label_w(label) * s / 2
    lx = min(max(lx, lw + 4 * s), w - lw - 4 * s)
    return (f'<g class="pin edge k-{esc(pt["kind"])}" data-poi="{esc(pt["poi"].get("id"))}">'
            f'<path class="ea" d="M0 -{8 * s:.1f}L{12 * s:.1f} 0L0 {8 * s:.1f}Z" '
            f'transform="translate({ex:.1f},{ey:.1f}) rotate({ang:.1f})"/>'
            f'<g transform="translate({lx:.1f},{ly:.1f}) scale({round(s, 2)})"><text y="5" class="tl">{esc(label)}</text></g></g>')


def _pins(pts, bbox, w, h, hl=None, merged=False, credit=False, edges=(), route=True):
    """Dots and their time labels. A label is bare text with a white halo (v1.1, the
    user's pick on the design board: no pill, no leader line) set in the nearest spot
    that overlaps no other label, no dot, and not the corner credit. #38: each stop's dot
    carries its number and a dashed line joins them in order (M3); dots on one spot are
    fanned out round a dashed ring (M5), or, all in one building, drawn as one '×N' dot
    (#35); a far end is an edge arrow (M4)."""
    s = w / PHONE_W
    marks = []
    drawn = set()
    for pt in pts:
        lat, lng = _geo(pt["poi"])
        x, y = project(lat, lng, bbox, w, h)
        x, y = round(min(max(x, MARGIN), w - MARGIN), 1), round(min(max(y, MARGIN), h - MARGIN), 1)
        tag = pt["tag"]
        if pt["kind"] in ("lodging", "home") and merged:
            if id(pt["poi"]) in drawn:
                continue
            drawn.add(id(pt["poi"]))
            tag = LABELS["home_merged" if pt["kind"] == "home" else "hotel_merged"]
        marks.append((pt, x, y, tag))
    r = (9 if any(p.get("no") for p, *_ in marks) else 7) * s
    rings, drop = [], set()
    for ks in _groups(marks):
        b = {_building(marks[k][0]) for k in ks}
        x0, y0 = marks[ks[0]][1], marks[ks[0]][2]
        if len(b) == 1 and None not in b:                     # #35: one building, one dot
            nos = [marks[k][0].get("no") for k in ks if marks[k][0].get("no")]
            pt0 = marks[ks[0]][0]
            span = f" {min(nos)}–{max(nos)}" if len(nos) > 1 else ""
            marks[ks[0]] = (dict(pt0, no=None, many=len(ks)), x0, y0, f"{pt0.get('building') or pt0['tag']}{span}")
            drop.update(ks[1:])
            continue
        rr = (r * 1.6) if len(ks) <= 6 else r * 2.2           # M5: fan out, approximate
        for n, k in enumerate(ks):
            a = -math.pi / 2 + 2 * math.pi * n / len(ks)
            pt, _x, _y, tag = marks[k]
            marks[k] = (pt, round(x0 + math.cos(a) * rr, 1), round(y0 + math.sin(a) * rr, 1), tag)
        rings.append(f'<circle class="apx" cx="{x0}" cy="{y0}" r="{round(rr + r + 3 * s, 1)}"/>')
    marks = [m for k, m in enumerate(marks) if k not in drop]
    line = ""
    seq = [(x, y) for p, x, y, _ in marks if p.get("no") or p.get("many")]
    if route and len(seq) > 1:
        line = '<path class="seqline" d="M' + "L".join(f"{x} {y}" for x, y in seq) + '"/>'
    taken = [(x - r, y - r, x + r, y + r) for _, x, y, _ in marks]
    if credit:
        taken.append((w - 96 * s, h - 24 * s, w, h))      # "© OpenStreetMap", bottom right
    out = []
    for pt, x, y, tag in marks:
        tw = _label_w(tag)
        spot = _spot(x, y, tw, s, w, h, taken)
        if spot:
            tx, ty, box = spot
            taken.append(box)
        else:                                               # nowhere free: above the dot
            tx, ty = min(max(x, tw * s / 2), w - tw * s / 2), max(y - 22 * s, 10 * s)
        cls = (f'pin k-{esc(pt["kind"])}{" hl" if hl and pt["key"] in hl else ""}'
               f'{" dim" if hl and pt["key"] not in hl else ""}')
        big = r * 1.35 if pt.get("many") else r
        inner = (str(pt["no"]) if pt.get("no") else f'×{pt["many"]}' if pt.get("many") else "")
        no = (f'<text x="{x}" y="{y}" class="no" style="font-size:{round(11 * s, 1)}px">{esc(inner)}</text>'
              if inner else "")
        out.append(f'<g class="{cls}" data-poi="{esc(pt["poi"].get("id"))}">'
                   f'<circle cx="{x}" cy="{y}" r="{round(big, 1)}" class="pt"/>{no}'
                   f'<g transform="translate({round(tx, 1)},{round(ty, 1)}) scale({round(s, 2)})">'
                   f'<text y="5" class="tl">{esc(tag)}</text></g></g>')
    seen = set()
    edges = [(p, km) for p, km in edges if id(p["poi"]) not in seen and not seen.add(id(p["poi"]))]
    far = "".join(_edge(p, bbox, w, h, s, km) for p, km in edges)
    return line + "".join(rings) + "".join(out) + far


DATA_IMAGE = re.compile(r"data:image/(png|jpeg|webp|gif);base64,[A-Za-z0-9+/]+={0,2}")


def _image(img):
    """The side-file image when it is safe to put inside a stylesheet url(): an
    embedded base64 image and nothing else (no quote, brace or </style> can ride in)."""
    ok = (isinstance(img, dict) and isinstance(img.get("data"), str) and DATA_IMAGE.fullmatch(img["data"])
          and all(isinstance(img.get(k), int) and not isinstance(img.get(k), bool) and img[k] > 0
                  for k in ("width", "height")))
    return img if ok else None


def inside(pts, bbox, slack=1e-6):
    """Every point lies within bbox. A point outside means the image was made for a
    different set of stops (the itinerary moved on after day_maps.py ran): the reader
    then draws the schematic rather than clamp a pin onto the wrong street."""
    try:
        n, s, e, w = (float(bbox[k]) for k in ("north", "south", "east", "west"))
    except (KeyError, TypeError, ValueError):
        return False
    return all(s - slack <= lat <= n + slack and w - slack <= lng <= e + slack
               for lat, lng in (_geo(p["poi"]) for p in pts))


def image_class(ctx, data):
    """One CSS class per distinct image: a hotel close-up shown on every day, an
    overview reused by several views, or a stop's photo on two days is embedded once
    (page.py writes the rules)."""
    images = ctx.__dict__.setdefault("map_images", {})
    if data not in images:
        images[data] = f"mi-{hashlib.sha256(data.encode()).hexdigest()[:12]}"
    return images[data]


COVER_TOLERANCE = 0.03       # within 3 % of 4:3, an image fills the phone's 4:3 frame (spec v1.1 §3.1)


def target(i, key):
    """The in-page anchor a stop / chip / 出發 / 回家 / 全圖 jumps to (spec v1.1 §8.1): the
    browser's own fragment scroll brings it into the list card and :target decides what
    is open and which map view shows -- no script, so it works in Quick Look."""
    return {"all": f"t-d{i}-top"}.get(key, f"t-d{i}-{key}")


def _frame(ctx, zid, pts, image, bbox, hl=None, merged=False, edges=()):
    if image:
        w, h = image["width"], image["height"]
        base = f'<span class="mimg {image_class(ctx, image["data"])}"></span>'
        svg_cls = "pins"
    else:
        bbox = _schematic_bbox(pts)
        edges = ()                                        # a schematic shows every point
        w, h = _schematic_size(bbox)
        lines = "".join(f"M{x} 0V{h}" for x in range(80, w, 80)) + "".join(f"M0 {y}H{w}" for y in range(80, h, 80))
        base = ""
        svg_cls = "grid"
        pins_bg = f'<rect class="gbg" width="{w}" height="{h}"/><path class="gline" d="{lines}"/>'
    svg_inner = (pins_bg if not image else "") + _pins(pts, bbox, w, h, hl, merged, credit=bool(image),
                                                       edges=edges)
    # the image and its pins share one canvas (preserveAspectRatio none), so a squeezed
    # or cropped frame distorts / crops both alike, never apart. A 4:3 image may be
    # cover-cropped by the phone's full-width 4:3 frame; any other ratio is shown whole
    # (an old side-file must not lose an edge pin). Every tiled frame names its source.
    cover = bool(image) and abs((w / h) / (4 / 3) - 1) <= COVER_TOLERANCE
    # plain text: tapping the small map zooms it; the link lives in the zoom bar (v1.1 topic 6)
    credit = '<span class="attrmini">© OpenStreetMap</span>' if image else ""
    return (f'<label class="mframe{" cover" if cover else ""}" for="{zid}" data-w="{w}" '
            f'style="aspect-ratio:{w}/{h};--ar:{w}/{h}"><span class="mcanvas">{base}'
            f'<svg class="{svg_cls}" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">'
            f'{svg_inner}</svg></span>{credit}</label>')


def _shared_close(ctx, pid):
    """A stop's close-up from anywhere in the side-file: the shared `closeups` (a stop
    alone in its segment, scripts/day_maps.py) first, then any day's entries -- the
    hotel left by a long train is usually some other day's 回家 (trip-e D3 / D4)."""
    maps = ctx.maps or {}
    pools = [maps.get("closeups") or {}]
    for entries in (maps.get("days") or {}).values():
        pools += [e.get("closeups") or {} for e in entries or [] if isinstance(e, dict)]
    return next((pool[pid] for pool in pools if isinstance(pool, dict) and isinstance(pool.get(pid), dict)), None)


def map_card(ctx, i, day):
    points = day_points(ctx, i, day)
    if not points:
        return ""
    date = str(day.get("date"))
    side = [e for e in ((ctx.maps or {}).get("days") or {}).get(date) or [] if isinstance(e, dict)]
    segs = _segments(points)
    merged = bool(points and points[0][1]["key"] in ("start", "home-start")
                  and points[-1][1]["key"] in ("end", "home-end")
                  and points[0][1]["poi"] is points[-1][1]["poi"])
    used_tiles = False

    def seg_image(k):
        entry = side[k] if k < len(side) else None
        ok = entry and _image(entry.get("image")) and isinstance(entry.get("bbox"), dict)
        if ok and isinstance(entry.get("poi_ids"), list):         # written for these stops?
            ok = set(entry["poi_ids"]) == {p["poi"].get("id") for p in segs[k]}
        # a far end is outside the image by design (#38 M4) -- but only one the image was
        # made without and that is still far; one that came closer must be inside it
        far = set(entry.get("far") or []) & far_ends(segs[k]) if ok else set()
        ok = ok and inside([p for p in segs[k] if p["key"] not in far], entry["bbox"])
        return (entry["image"], entry["bbox"], entry.get("closeups") or {}) if ok else (None, None, {})

    order = [("all", "全圖")] + [(p["key"], p["chip"]) for _, p in points]
    chips = "".join(f'<a class="chip c-d{i}-{k}{" hotel" if k in ("start", "end") else " home" if k.startswith("home") else ""}" href="#{target(i, k)}">'
                    f'{esc(label)}</a>' for k, label in order)
    views = []
    for n, (key, _label) in enumerate(order):
        prev_key, next_key = order[n - 1][0], order[(n + 1) % len(order)][0]
        zid = f"z-d{i}-{key}"
        frames, boxes = [], []
        if key == "all":
            for k, pts in enumerate(segs):
                image, bbox, _ = seg_image(k)
                used_tiles |= bool(image)
                boxes += [bbox] if image and isinstance(bbox, dict) else []
                far = set((side[k] or {}).get("far") or []) & far_ends(pts) if image else set()
                near = [p for p in pts if p["key"] not in far]
                edges = [(p, _km_from(p, near)) for p in pts if p["key"] in far]
                frames.append(f'<div class="seg">{_frame(ctx, zid, near, image, bbox, merged=merged, edges=edges)}</div>')
        else:
            k = next((k for k, pts in enumerate(segs) if any(p["key"] == key for p in pts)), None)
            pt = next(p for _, p in points if p["key"] == key)
            image, bbox, closeups = seg_image(k) if k is not None else (None, None, {})
            close = closeups.get(pt["poi"].get("id")) if isinstance(closeups, dict) else None
            if not (isinstance(close, dict) and _image(close.get("image"))):
                close = _shared_close(ctx, pt["poi"].get("id"))
            if (isinstance(close, dict) and _image(close.get("image"))
                    and isinstance(close.get("bbox"), dict) and inside([pt], close["bbox"])):
                used_tiles = True
                boxes.append(close["bbox"])
                # #38 M2: the day's other stops inside this close-up, dimmed, so the next
                # one's direction and distance show
                near = [p for p in (segs[k] if k is not None else []) if p is not pt
                        and p["kind"] not in ("lodging", "home") and inside([p], close["bbox"])]
                frames.append(f'<div class="seg">{_frame(ctx, zid, [pt] + near, close["image"], close["bbox"], hl={key})}</div>')
            else:
                pts = segs[k] if k is not None else [pt]
                used_tiles |= bool(image)
                boxes += [bbox] if image and isinstance(bbox, dict) else []
                frames.append(f'<div class="seg">{_frame(ctx, zid, pts, image, bbox, hl={key}, merged=merged)}</div>')
        # v1.1 topic 6 (Z1-a + close rule A): the zoomed view closes on the map, the dark
        # layer (.zbg) or ✕; only the live-map link, shown when this view drew tiles, leaves
        frames_html = "".join(frames)
        ar = re.search(r"--ar:(\d+/\d+)", frames_html)
        bar = ((f'<a class="zlink" href="{live_url(boxes)}" target="_blank" rel="noopener">在 Google Maps 開這裡 ↗</a>'
                if boxes else "") + f'<label class="zx" for="{zid}">✕ 關閉</label>')
        style = f' style="--ar:{ar.group(1)}"' if ar else ""        # no nested quotes: CI runs 3.11
        views.append(f'<div class="mv mv-d{i}-{key}"{style}>'
                     f'<input type="checkbox" class="ck zck" id="{zid}" autocomplete="off">'
                     f'<label class="zbg" for="{zid}" aria-hidden="true"></label>{frames_html}<div class="zbar">{bar}</div>'
                     f'<div class="mnav"><a class="prev" href="#{target(i, prev_key)}">‹ 上一個</a>'
                     f'<a class="next" href="#{target(i, next_key)}">下一個 ›</a></div></div>')
    legend = "".join(f'<li><b>{esc(p["chip"])}</b>{esc(_name(p["poi"]))}</li>' for _, p in points)
    attr = (f'<p class="attr">{esc(ctx.maps.get("attribution"))}</p>'
            if used_tiles and ctx.maps else "")
    return (f'<details class="mapc"><summary>{icon("map", "lu big")}<span>地圖</span><span class="cv"></span></summary>'
            f'<div class="chips">{chips}</div><div class="views">{"".join(views)}</div>'
            f'<ul class="lgd">{legend}</ul>{attr}</details>')


def nav_css(ctx, i, day):
    """Which map view shows and which chip is lit (the map half of §6.8), driven by the
    page's :target (v1.1 §8.1). A stop "holds" the target when it is the target or holds
    it (its 來源); its closed marker (.tx) does not count. No target -> the overview."""
    points = day_points(ctx, i, day)
    if not points:
        return ""
    page = f'.page.day[data-pg="d{i}"]'
    lit = "{background:var(--ink);color:var(--bg);border-color:var(--ink)}"
    rules = [f'{page}:not(:has(.plist :target:not(.tx))) .mv-d{i}-all{{display:var(--mvd,block)}}'
             f'{page}:not(:has(.plist :target:not(.tx))) .c-d{i}-all{lit}']
    views = {p["key"]: p["key"] for _, p in points}
    views.update({rid.split("-", 1)[1]: key for rid, key in view_of_row(ctx, i, day).items()})
    for node, key in views.items():
        tid = target(i, node)
        held = f'{page}:has(#{tid}:target,#{tid} :target:not(.tx))'     # never :has() in :has()
        rules.append(f"{held} .mv-d{i}-{key}{{display:var(--mvd,block)}}{held} .c-d{i}-{key}{lit}")
    return "".join(rules)
