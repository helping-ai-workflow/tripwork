"""Itinerary day -> Markdown table.

All free text passes through md_escape so a price like $180 cannot trigger KaTeX
math mode in a markdown preview, and a stray | cannot break the table cell.
Generated link markup ([name](url)) is never escaped — only free text is.
"""
from scripts.render.gmaps_links import link_markdown

# Chars with markdown / KaTeX meaning in free text. `|` would also break a table
# cell. Backslash is escaped first so the escapes we add are not re-escaped.
_ESCAPE = ["\\", "`", "*", "_", "<", "|", "$", "[", "]"]

def md_escape(text):
    """Backslash-escape markdown/KaTeX-active chars in free text."""
    out = str(text)
    for ch in _ESCAPE:
        out = out.replace(ch, "\\" + ch)
    return out

def _primary_source_url(poi):
    """Official source url if any source is flagged official, else the first url, else None."""
    sources = poi.get("sources") or []
    for s in sources:
        if s.get("official"):
            return s.get("url")
    return sources[0].get("url") if sources else None

def _safe_url(url):
    """Percent-encode the two chars that would break a markdown link target. (TW-022)"""
    return url.replace(")", "%29").replace(" ", "%20")

def _poi_cell(poi, text):
    parts = [link_markdown(poi)]
    url = _primary_source_url(poi)
    if url:
        parts.append(f"· [官網]({_safe_url(url)})")
    escaped = md_escape(text)
    if escaped:
        parts.append(escaped)
    return " ".join(parts)

def render_day_table(day, poi_map):
    """Render one canonical itinerary.yaml day -> markdown table.

    Args:
        day:      {label, rows:[{time, slot, poi_id, text}]}
        poi_map:  {poi_id: verified-poi dict} for resolving row poi_id -> link.
    """
    lines = [f"### {md_escape(day.get('label', ''))}", "", "| 時段 | 行程 |", "|---|---|"]
    for row in day.get("rows", []):
        time = md_escape(row.get("time", ""))
        text = row.get("text", "")
        pid = row.get("poi_id")
        poi = poi_map.get(pid) if pid else None
        cell = _poi_cell(poi, text) if poi else md_escape(text)
        lines.append(f"| {time} | {cell} |")
    return "\n".join(lines) + "\n"
