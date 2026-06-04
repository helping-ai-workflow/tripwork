"""Itinerary day -> Markdown table.

All free text passes through md_escape so a price like $180 cannot trigger KaTeX
math mode in a markdown preview, and a stray | cannot break the table cell.
Generated link markup ([name](url)) is never escaped — only free text is.
"""
from scripts.render.gmaps_links import link_markdown

# Chars with markdown / KaTeX meaning in free text. `|` would also break a table
# cell. Backslash is escaped first so the escapes we add are not re-escaped.
_ESCAPE = ["\\", "`", "*", "_", "<", "|", "$"]

def md_escape(text):
    """Backslash-escape markdown/KaTeX-active chars in free text."""
    out = str(text)
    for ch in _ESCAPE:
        out = out.replace(ch, "\\" + ch)
    return out

def render_day_table(day):
    lines = [f"### {md_escape(day.get('label', ''))}", "", "| 時段 | 行程 |", "|---|---|"]
    for row in day.get("rows", []):
        time = md_escape(row.get("time", ""))
        text = row.get("text", "")
        poi = row.get("poi")
        cell = f"{link_markdown(poi)} {md_escape(text)}".strip() if poi else md_escape(text)
        lines.append(f"| {time} | {cell} |")
    return "\n".join(lines) + "\n"
