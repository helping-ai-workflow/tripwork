"""Canonical itinerary.yaml -> self-contained one-page HTML. Offline, inline CSS,
elder-friendly large font, mobile RWD. Card-style layout (v0.17.0): gradient hero
with a date-span + lodging-flow line derived from the itinerary, a per-day overview
table, an emoji legend, rounded shadowed day-cards with a day-number badge and a
lodging maps link, slot-coloured rows, and orange-bordered inline 備案 (alternative)
rows. POI names are Maps links (reuses gmaps_links.maps_url, inheriting the D1
name-search fix). Every emitted href is an https Maps URL so run_html_gate accepts
it; nothing is invented — hero meta / overview / lodging-flow are derived only from
fields present in itinerary.yaml (Source-Verified-First). (dogfood D4)
"""
from scripts.render.gmaps_links import maps_url

# Security: all five HTML-significant chars are escaped.
# Ampersand MUST be replaced first so the entity suffixes we add (&lt; etc.)
# are not themselves double-escaped on a second pass.
_ESCAPE_PAIRS = [
    ("&", "&amp;"),   # FIRST — prevents double-escaping
    ("<", "&lt;"),
    (">", "&gt;"),
    ('"', "&quot;"),
    ("'", "&#39;"),
]


def _html_escape(text: object) -> str:
    """Escape HTML-significant characters. Ampersand-first to avoid double-escaping."""
    out = str(text)
    for ch, rep in _ESCAPE_PAIRS:
        out = out.replace(ch, rep)
    return out


# slot -> emoji. Unknown slots (e.g. legacy "lunch") fall back to a neutral dot so
# the renderer never crashes on out-of-enum data.
_SLOT_EMOJI = {
    "meal": "🍽",
    "visit": "📍",
    "activity": "🎯",
    "move": "🚆",
    "lodging": "🏨",
}
_SLOT_DEFAULT_EMOJI = "•"

# Inline 備案 / 加碼 rows are flagged in the canonical text with a leading ▸.
_ALT_MARKER = "▸"

_STYLE = (
    ":root{--bg:#faf6f0;--card:#fff;--ink:#2b2622;--mut:#7a6f64;--line:#e7ddd0;"
    "--accent:#c2410c;--accent2:#0e7490;--alt:#fff7ed;--altline:#fdba74}"
    "*{box-sizing:border-box}"
    "html,body{overflow-x:hidden}"   # backstop: clip any residual horizontal overflow
    "body{margin:0;background:var(--bg);color:var(--ink);"
    "font-family:system-ui,-apple-system,'Noto Sans CJK TC','Noto Sans TC',"
    "'Microsoft JhengHei',sans-serif;line-height:1.7;font-size:18px}"
    ".wrap{max-width:860px;margin:0 auto;padding:24px 18px 64px}"
    "header.hero{background:linear-gradient(135deg,#c2410c,#ea580c);color:#fff;"
    "border-radius:18px;padding:26px 24px;box-shadow:0 8px 24px rgba(194,65,12,.25)}"
    "header.hero h1{margin:0 0 12px;font-size:1.5em;line-height:1.3}"
    ".meta{display:flex;flex-wrap:wrap;gap:8px 18px;font-size:.85em;opacity:.96}"
    ".flow{margin:14px 0 0;font-size:.85em;opacity:.96}"
    "h2.sec{font-size:1.15em;margin:32px 0 12px;padding-left:10px;"
    "border-left:5px solid var(--accent)}"
    "table.ov{width:100%;border-collapse:collapse;background:var(--card);"
    "border-radius:12px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.05);font-size:.85em}"
    "table.ov th,table.ov td{padding:9px 11px;text-align:left;"
    "border-bottom:1px solid var(--line);vertical-align:top;word-break:break-word}"
    "table.ov th{background:#f3e9dc;font-weight:700}"
    "table.ov td.d{font-weight:800;color:var(--accent);white-space:nowrap}"
    "table.ov tr:last-child td{border-bottom:none}"
    ".legend{font-size:.82em;color:var(--mut);margin:10px 0 0}"
    ".altchip{background:var(--alt);border:1px solid var(--altline);border-radius:5px;padding:0 6px}"
    ".day-card{background:var(--card);border-radius:16px;padding:18px 20px;margin:16px 0;"
    "box-shadow:0 2px 12px rgba(0,0,0,.06)}"
    ".day-card h2{margin:0 0 10px;font-size:1.1em;display:flex;align-items:center;gap:10px}"
    ".dnum{background:var(--accent);color:#fff;width:30px;height:30px;border-radius:50%;"
    "display:inline-flex;align-items:center;justify-content:center;font-size:.8em;flex:none}"
    ".lodge{font-size:.82em;color:var(--accent2);margin:-2px 0 10px;font-weight:600}"
    ".lodge a{color:var(--accent2)}"
    "ul.rows{list-style:none;margin:0;padding:0}"
    "li.row{display:flex;gap:10px;padding:8px 0;border-bottom:1px dashed var(--line);"
    "align-items:baseline}"
    "li.row:last-child{border-bottom:none}"
    ".t{flex:none;width:52px;font-weight:700;color:var(--accent2);font-size:.82em}"
    ".emo{flex:none;width:22px;text-align:center}"
    # flex children default to min-width:auto and will not shrink — a long JP map
    # label would force horizontal page overflow on phones. min-width:0 + wrapping
    # lets the body shrink and break instead.
    ".bd{flex:1;min-width:0;overflow-wrap:anywhere}"
    "a.map{display:inline-block;background:#ecfeff;color:#0e7490;border:1px solid #a5f3fc;"
    "border-radius:7px;padding:1px 7px;font-size:.78em;text-decoration:none;"
    "word-break:break-word;max-width:100%;margin-left:4px}"
    ".row.slot-meal .t{color:#c2410c}"
    ".row.slot-visit .t{color:#0e7490}"
    ".row.slot-activity .t{color:#7c3aed}"
    ".row.slot-move .t{color:#2563eb}"
    ".row.slot-lodging .t{color:#059669}"
    "li.row.alt{background:var(--alt);border:1px solid var(--altline);border-radius:10px;"
    "padding:8px 12px;margin:6px 0}"
    "li.row.alt .bd{font-size:.92em;color:#9a3412}"
    ".chk{background:var(--card);border-radius:14px;padding:16px 20px 16px 40px;"
    "box-shadow:0 2px 10px rgba(0,0,0,.05)}"
    ".chk li{margin:6px 0}"
    "footer{text-align:center;color:var(--mut);font-size:.78em;margin-top:30px}"
    # POI photo: right-aligned 60px square thumb + pure-CSS checkbox-hack lightbox.
    # .ph is the last flex child of li.row (margin-left:auto pins it to the right edge).
    # Attribution = thumb title (hover) + lightbox caption — no row caption. The hidden
    # checkbox + label[for] toggle the overlay (no <script>, no #anchor). (D8/D9)
    ".ph{flex:none;align-self:flex-start;margin-left:auto}"
    ".phck{position:absolute;width:1px;height:1px;opacity:0;pointer-events:none}"
    ".thumbwrap{cursor:zoom-in;margin-left:auto}"
    "img.thumb{width:60px;height:60px;object-fit:cover;border-radius:8px;"
    "border:1px solid var(--line);display:block}"
    ".lb{display:none}"
    ".phck:checked~.lb{display:flex;position:fixed;inset:0;z-index:50;"
    "background:rgba(0,0,0,.82);align-items:center;justify-content:center;"
    "padding:24px;cursor:zoom-out}"
    # lightbox: vertical column so the caption is always centred directly under the
    # image (a landscape .lbimg otherwise drifted the inline caption to the right). (D9)
    ".lbbox{max-width:94vw;max-height:94vh;display:flex;flex-direction:column;"
    "align-items:center}"
    ".lbimg{display:block;max-width:94vw;max-height:80vh;border-radius:8px}"
    ".lbcap{color:#fff;font-size:.82em;margin:8px 0 0;overflow-wrap:anywhere;"
    "text-align:center}"
    ".lbcap a{color:#7dd3fc}"
    "@media(max-width:480px){body{font-size:17px}.wrap{padding:14px 12px 40px}"
    "header.hero{padding:18px 16px}.t{width:46px}}"
)


def _poi_label(poi: dict) -> str:
    """Build display label: 'name_display（name_zh）' or just name_display."""
    base = poi.get("name_display") or poi.get("name_local") or poi.get("id", "")
    zh = poi.get("name_zh")
    return f"{base}（{zh}）" if zh and zh != base else base


def _short_name(poi: dict) -> str:
    """Compact name for the hero lodging-flow line and the overview 住宿 column —
    the zh gloss when present (shortest, reader-friendly), else the display name."""
    return (
        poi.get("name_zh")
        or poi.get("name_display")
        or poi.get("name_local")
        or poi.get("id", "")
    )


def _slot_emoji(slot: str) -> str:
    return _SLOT_EMOJI.get(slot, _SLOT_DEFAULT_EMOJI)


def _is_alt(text: str) -> bool:
    return str(text).lstrip().startswith(_ALT_MARKER)


def _map_link(poi: dict, label: str) -> str:
    """`<a href=... class="map">` — href FIRST so it is a well-formed https Maps URL
    that run_html_gate's href check accepts and the maps-link assertion still matches."""
    url = _html_escape(maps_url(poi))  # already percent-encoded by maps_url
    return f'<a href="{url}" class="map" target="_blank">{label}</a>'


def _attribution_caption(poi: dict) -> str:
    """Visible, escaped photo attribution — author / license + a source link.
    Mandatory whenever a photo is shown (the schema photo=>attribution rule and the
    export gate both enforce its presence; this is what renders it)."""
    attr = poi.get("photo_attribution") or {}
    author = _html_escape(attr.get("author", ""))
    lic = _html_escape(attr.get("license", ""))
    bits = f"📷 {author}".rstrip()
    if lic:
        bits += f" / {lic}"
    src = attr.get("source_url")
    if src:
        bits += f' · <a href="{_html_escape(src)}" target="_blank">來源</a>'
    return bits


def _attribution_text(poi: dict) -> str:
    """Plain-text attribution (author / license) for the thumb's title/hover — NO
    markup (a title attribute can't carry a link; the clickable 來源 lives in the
    lightbox caption). Keeps CC attribution reachable without a row caption that
    blows the 60px thumb's column."""
    attr = poi.get("photo_attribution") or {}
    parts = [p for p in (attr.get("author"), attr.get("license")) if p]
    return "📷 " + " / ".join(parts) if parts else "📷"


def _photo_src(obj: dict) -> str:
    """A photo / thumb dict -> its src: inline base64 (data:) preferred, else https url."""
    return obj.get("data") or obj.get("url") or ""


def _photo_html(poi: dict, uid: str) -> str:
    """POI photo: right-aligned 60px thumb + pure-CSS checkbox-hack lightbox. Attribution
    is on the thumb ``title`` (hover) and in the lightbox caption — no row caption.
    Returns "" when the POI has no photo.

    Pure CSS: a labelled ``<input type=checkbox>`` drives the lightbox — NO ``<script>``,
    NO ``href``/``#anchor`` toggle — so run_html_gate's no-raw-script + href checks stay
    satisfied. Every ``<img src>`` is a ``data:image/`` or ``https`` URL (gate img-src
    whitelist) and ALL caption text is ``_html_escape``'d: the gate only catches a literal
    ``<script>``, so escaping at the render layer is the real XSS defence. ``uid`` makes the
    checkbox id unique per call site (one POI can be both a row and the day's lodging)."""
    photo = poi.get("photo")
    if not photo:
        return ""
    full = _photo_src(photo)
    if not full:
        return ""
    thumb = _photo_src(photo.get("thumb") or {}) or full
    alt = _html_escape(_poi_label(poi))
    cap = _attribution_caption(poi)
    cb = "ph-" + _html_escape(str(uid))
    full_e = _html_escape(full)
    thumb_e = _html_escape(thumb)
    title = _html_escape(_attribution_text(poi))
    return (
        f'<span class="ph">'
        f'<input type="checkbox" id="{cb}" class="phck" aria-hidden="true">'
        f'<label class="thumbwrap" for="{cb}">'
        f'<img class="thumb" src="{thumb_e}" alt="{alt}" title="{title}" loading="lazy"></label>'
        f'<label class="lb" for="{cb}"><span class="lbbox">'
        f'<img class="lbimg" src="{full_e}" alt="{alt}">'
        f'<span class="lbcap">{cap}</span></span></label>'
        f'</span>'
    )


def _date_span(days: list) -> str:
    """First–last itinerary date as YYYY/MM/DD, derived only from days[].date.

    Escaped here: this value is interpolated into the hero meta span, and
    run_html_gate only catches a literal <script> — an <img onerror=> smuggled
    through an unvalidated date would otherwise pass the gate. (security #1)
    """
    dates = [d.get("date") for d in days if d.get("date")]
    if not dates:
        return ""
    first = _html_escape(str(dates[0]).replace("-", "/"))
    last = _html_escape(str(dates[-1]).replace("-", "/"))
    return first if first == last else f"{first}–{last}"


def _lodging_flow(days: list, poi_map: dict) -> str:
    """🏨 distinct consecutive overnight stays with ×count, derived from per-day
    lodging. Omitted entirely when no lodging id resolves (no invention)."""
    runs: list = []
    for d in days:
        pid = d.get("lodging")
        poi = poi_map.get(pid) if pid else None
        if not poi:
            continue
        name = _short_name(poi)
        if runs and runs[-1][0] == name:
            runs[-1][1] += 1
        else:
            runs.append([name, 1])
    if not runs:
        return ""
    parts = [f"{_html_escape(name)} ×{n}" for name, n in runs]
    return f'<div class="flow">🏨 住宿：{" → ".join(parts)}</div>'


def _hero_html(itin: dict, poi_map: dict) -> str:
    title = _html_escape(itin.get("title", "行程"))
    days = itin.get("days", [])
    meta_bits = []
    span = _date_span(days)
    if span:
        meta_bits.append(f"<span>📅 {span}</span>")
    if days:
        meta_bits.append(f"<span>🗓 共 {len(days)} 天</span>")
    meta = f'<div class="meta">{"".join(meta_bits)}</div>' if meta_bits else ""
    flow = _lodging_flow(days, poi_map)
    return f'<header class="hero"><h1>{title}</h1>{meta}{flow}</header>'


def _overview_html(days: list, poi_map: dict) -> str:
    """Per-day overview table: 日 / 行程 / 住宿. All columns come straight from
    days[] — no region/highlight columns are fabricated."""
    if not days:
        return ""
    rows = []
    for i, d in enumerate(days, start=1):
        label = _html_escape(d.get("label") or d.get("date", ""))
        pid = d.get("lodging")
        poi = poi_map.get(pid) if pid else None
        lodge = _html_escape(_short_name(poi)) if poi else "—"
        rows.append(f'<tr><td class="d">D{i}</td><td>{label}</td><td>{lodge}</td></tr>')
    body = "".join(rows)
    return (
        '<h2 class="sec">行程總覽</h2>'
        '<table class="ov"><tr><th>日</th><th>行程</th><th>住宿</th></tr>'
        f"{body}</table>"
    )


_LEGEND = (
    '<p class="legend">🍽 餐食　📍 景點　🎯 活動　🚆 移動　🏨 住宿　／　'
    '<span class="altchip">▸ 橘框＝當日備案</span></p>'
)


def _row_html(row: dict, poi_map: dict, uid: str = "") -> str:
    slot = row.get("slot", "")
    text_raw = row.get("text", "")
    alt = _is_alt(text_raw)
    emoji = _slot_emoji(slot)

    time = _html_escape(row.get("time", ""))
    t = f'<span class="t">{time}</span>' if time else '<span class="t empty"></span>'

    text = _html_escape(text_raw)
    pid = row.get("poi_id")
    poi = poi_map.get(pid) if pid else None
    if poi:
        chip = _map_link(poi, f"🗺️ {_html_escape(_poi_label(poi))}")
        body = f"{text} {chip}".strip()
        photo = _photo_html(poi, uid)   # right-aligned thumb: a sibling AFTER .bd
    else:
        body = text
        photo = ""

    cls = "row alt" if alt else f"row slot-{_html_escape(slot)}"
    return (
        f'<li class="{cls}">{t}<span class="emo">{emoji}</span>'
        f'<span class="bd">{body}</span>{photo}</li>'
    )


def _day_html(day: dict, poi_map: dict, idx: int) -> str:
    label = _html_escape(day.get("label") or day.get("date", ""))

    lodge = ""
    pid = day.get("lodging")
    poi = poi_map.get(pid) if pid else None
    if poi:
        link = _map_link(poi, _html_escape(_poi_label(poi)))
        lodge = f'<div class="lodge">🏨 住宿：{link}</div>' + _photo_html(poi, f"d{idx}-lodge")

    rows = "".join(
        _row_html(r, poi_map, f"d{idx}-r{j}") for j, r in enumerate(day.get("rows", []))
    )
    return (
        f'<section class="day-card"><h2><span class="dnum">{idx}</span>{label}</h2>'
        f'{lodge}<ul class="rows">{rows}</ul></section>'
    )


def render_html_page(itin: dict, poi_map: dict) -> str:
    """Render a complete, self-contained HTML page from an itinerary dict.

    Args:
        itin:    Canonical itinerary dict — {title, checklist:[], days:[{date,label,lodging,rows:[...]}]}
        poi_map: {poi_id: poi_dict} for resolving POI ids in rows AND day lodging.

    Returns:
        Complete HTML string with inline CSS.  No external assets.  Works offline.
    """
    title = _html_escape(itin.get("title", "行程"))
    days = itin.get("days", [])

    hero = _hero_html(itin, poi_map)
    overview = _overview_html(days, poi_map)
    day_cards = "".join(_day_html(d, poi_map, i) for i, d in enumerate(days, start=1))

    checklist = itin.get("checklist") or []
    cl = ""
    if checklist:
        items = "".join(f"<li>{_html_escape(c)}</li>" for c in checklist)
        cl = f'<h2 class="sec">✅ 行前清單</h2><div class="chk"><ul>{items}</ul></div>'

    return (
        f'<!DOCTYPE html>\n'
        f'<html lang="zh-Hant">'
        f'<head>'
        f'<meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{title}</title>'
        f'<style>{_STYLE}</style>'
        f'</head>'
        f'<body><div class="wrap">'
        f'{hero}'
        f'{overview}'
        f'{_LEGEND}'
        f'<h2 class="sec">每日行程</h2>'
        f'{day_cards}'
        f'{cl}'
        f'<footer>景點 / 住宿均經 source-verify 驗證（≥2 來源含在地語）。本頁離線可開。</footer>'
        f'</div></body>'
        f'</html>\n'
    )
