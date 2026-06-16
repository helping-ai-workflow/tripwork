"""Canonical itinerary.yaml -> self-contained one-page HTML. Offline, inline CSS,
elder-friendly large font, mobile RWD. POI names are Maps links (reuses
gmaps_links.maps_url, inheriting the D1 name-search fix). (dogfood D4)
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


_STYLE = (
    "*{box-sizing:border-box}"
    "body{font-family:system-ui,'Noto Sans CJK TC',sans-serif;"
    "font-size:18px;line-height:1.6;margin:0;padding:16px;color:#1a1a1a;background:#faf8f4}"
    "h1{font-size:1.6em}"
    ".day-card{background:#fff;border:1px solid #e0d8c8;border-radius:12px;"
    "padding:16px;margin:16px 0;box-shadow:0 1px 4px rgba(0,0,0,.06)}"
    ".day-card h2{margin:0 0 8px;font-size:1.2em;color:#8a5a00}"
    ".row{padding:6px 0;border-top:1px solid #f0ebe0}"
    ".time{font-weight:600;color:#555}"
    "a{color:#0a6}"
    ".checklist{background:#fff;border-radius:12px;padding:16px;margin:16px 0}"
    "@media(max-width:480px){body{font-size:17px;padding:10px}}"
)


def _poi_label(poi: dict) -> str:
    """Build display label: 'name_display（name_zh）' or just name_display."""
    base = poi.get("name_display") or poi.get("name_local") or poi.get("id", "")
    zh = poi.get("name_zh")
    return f"{base}（{zh}）" if zh and zh != base else base


def _row_html(row: dict, poi_map: dict) -> str:
    time = _html_escape(row.get("time", ""))
    pid = row.get("poi_id")
    poi = poi_map.get(pid) if pid else None
    text = _html_escape(row.get("text", ""))

    if poi:
        # URL is already percent-encoded by maps_url; escape for HTML attribute
        url_escaped = _html_escape(maps_url(poi))
        label_escaped = _html_escape(_poi_label(poi))
        link = f'<a href="{url_escaped}">{label_escaped}</a>'
        body = f"{link} {text}".strip()
    else:
        body = text

    t = f'<span class="time">{time}</span> ' if time else ""
    return f'<div class="row">{t}{body}</div>'


def _day_html(day: dict, poi_map: dict) -> str:
    label = _html_escape(day.get("label") or day.get("date", ""))
    rows = "".join(_row_html(r, poi_map) for r in day.get("rows", []))
    return f'<div class="day-card"><h2>{label}</h2>{rows}</div>'


def render_html_page(itin: dict, poi_map: dict) -> str:
    """Render a complete, self-contained HTML page from an itinerary dict.

    Args:
        itin:    Canonical itinerary dict — {title, checklist:[], days:[{date,label,rows:[...]}]}
        poi_map: {poi_id: poi_dict} for resolving POI ids in rows.

    Returns:
        Complete HTML string with inline CSS.  No external assets.  Works offline.
    """
    title = _html_escape(itin.get("title", "行程"))
    days = "".join(_day_html(d, poi_map) for d in itin.get("days", []))

    checklist = itin.get("checklist") or []
    cl = ""
    if checklist:
        items = "".join(f"<li>{_html_escape(c)}</li>" for c in checklist)
        cl = f'<div class="checklist"><h2>行前清單</h2><ul>{items}</ul></div>'

    return (
        f'<!DOCTYPE html>\n'
        f'<html lang="zh-Hant">'
        f'<head>'
        f'<meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{title}</title>'
        f'<style>{_STYLE}</style>'
        f'</head>'
        f'<body>'
        f'<h1>{title}</h1>'
        f'{days}'
        f'{cl}'
        f'</body>'
        f'</html>\n'
    )
