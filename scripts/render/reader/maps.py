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


def day_points(ctx, i, day):
    """[(segment index, point)] in chain order. A point is a dict with key (view name),
    target node (d<N>-<key>), chip text, poi, kind and tag text. Long moves (leg_index) start a new
    segment; stops with no geocode are not points."""
    rows = [r for r in day.get("rows") or [] if isinstance(r, dict)]
    start = ctx.poi_map.get(ctx.days[i - 2].get("lodging")) if i > 1 and ctx.days[i - 2].get("lodging") else None
    end = ctx.poi_map.get(day.get("lodging")) if day.get("lodging") else None
    hotels = {id(x) for x in (start, end) if x}
    pts, seg = [], 0
    if start and _geo(start):
        pts.append((seg, {"key": "start", "radio": f"d{i}-start", "chip": "出發", "poi": start,
                          "kind": "lodging", "tag": "出發"}))
    for j, r in enumerate(rows):
        if r.get("slot") == "move":
            if r.get("leg_index") is not None:
                seg += 1
            continue
        p = ctx.poi_map.get(r.get("poi_id"))
        if not p or id(p) in hotels or not _geo(p):
            continue
        pts.append((seg, {"key": f"s{j}", "radio": f"d{i}-s{j}", "chip": r.get("time") or _name(p),
                          "poi": p, "kind": r.get("slot") or "visit", "tag": r.get("time") or _name(p)}))
    if end and _geo(end):
        pts.append((seg, {"key": "end", "radio": f"d{i}-end", "chip": "回家", "poi": end,
                          "kind": "lodging", "tag": "回家"}))
    return pts


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
    segs = {}
    for s, pt in points:
        segs.setdefault(s, []).append(pt)
    return [pts for _, pts in sorted(segs.items()) if len(pts) >= 2]


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


def _pins(pts, bbox, w, h, hl=None, merged=False, credit=False):
    """Dots and their time labels. A label is bare text with a white halo (v1.1, the
    user's pick on the design board: no pill, no leader line) set in the nearest spot
    that overlaps no other label, no dot, and not the corner credit."""
    s = w / PHONE_W
    marks = []
    hotel_drawn = False
    for pt in pts:
        lat, lng = _geo(pt["poi"])
        x, y = project(lat, lng, bbox, w, h)
        x, y = round(min(max(x, MARGIN), w - MARGIN), 1), round(min(max(y, MARGIN), h - MARGIN), 1)
        tag = pt["tag"]
        if pt["kind"] == "lodging" and merged:
            if hotel_drawn:
                continue
            hotel_drawn, tag = True, "出發・回家"
        marks.append((pt, x, y, tag))
    r = 7 * s
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
        cls = f'pin k-{esc(pt["kind"])}{" hl" if hl and pt["key"] in hl else ""}'
        out.append(f'<g class="{cls}" data-poi="{esc(pt["poi"].get("id"))}">'
                   f'<circle cx="{x}" cy="{y}" r="{round(r, 1)}" class="pt"/>'
                   f'<g transform="translate({round(tx, 1)},{round(ty, 1)}) scale({round(s, 2)})">'
                   f'<text y="5" class="tl">{esc(tag)}</text></g></g>')
    return "".join(out)


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


def _frame(ctx, zid, pts, image, bbox, hl=None, merged=False):
    if image:
        w, h = image["width"], image["height"]
        base = f'<span class="mimg {image_class(ctx, image["data"])}"></span>'
        svg_cls = "pins"
    else:
        bbox = _schematic_bbox(pts)
        w, h = _schematic_size(bbox)
        lines = "".join(f"M{x} 0V{h}" for x in range(80, w, 80)) + "".join(f"M0 {y}H{w}" for y in range(80, h, 80))
        base = ""
        svg_cls = "grid"
        pins_bg = f'<rect class="gbg" width="{w}" height="{h}"/><path class="gline" d="{lines}"/>'
    svg_inner = (pins_bg if not image else "") + _pins(pts, bbox, w, h, hl, merged, credit=bool(image))
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
    merged = bool(points and points[0][1]["key"] == "start" and points[-1][1]["key"] == "end"
                  and points[0][1]["poi"] is points[-1][1]["poi"])
    used_tiles = False

    def seg_image(k):
        entry = side[k] if k < len(side) else None
        ok = entry and _image(entry.get("image")) and isinstance(entry.get("bbox"), dict)
        if ok and isinstance(entry.get("poi_ids"), list):         # written for these stops?
            ok = set(entry["poi_ids"]) == {p["poi"].get("id") for p in segs[k]}
        ok = ok and inside(segs[k], entry["bbox"])
        return (entry["image"], entry["bbox"], entry.get("closeups") or {}) if ok else (None, None, {})

    order = [("all", "全圖")] + [(p["key"], p["chip"]) for _, p in points]
    chips = "".join(f'<a class="chip c-d{i}-{k}{" hotel" if k in ("start", "end") else ""}" href="#{target(i, k)}">'
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
                frames.append(f'<div class="seg">{_frame(ctx, zid, pts, image, bbox, merged=merged)}</div>')
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
                frames.append(f'<div class="seg">{_frame(ctx, zid, [pt], close["image"], close["bbox"], hl={key})}</div>')
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
