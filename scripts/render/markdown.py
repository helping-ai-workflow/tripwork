"""Itinerary day -> Markdown table.

All free text passes through md_escape so a price like $180 cannot trigger KaTeX
math mode in a markdown preview, and a stray | cannot break the table cell.
Generated link markup ([name](url)) is never escaped — only free text is.
"""
from scripts.render.gmaps_links import link_markdown, dir_url

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

def _move_cell(frm, to, text, poi=None):
    """Move row with endpoints: a directions link LEADS the cell (mirrors _poi_cell's
    link-first ordering). When the row ALSO resolves a poi, the poi maps link + official
    source follow — so a bookable poi scheduled on a move row still surfaces its name and
    official link for the export gate's bookable check (no silent evasion). Then the text.
    Labels are escaped free text; generated link targets (dir_url / maps_url) are not. (G2)"""
    parts = [f"[🚆 {md_escape(frm)}→{md_escape(to)}]({dir_url(frm, to)})"]
    if poi:
        parts.append(link_markdown(poi))
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
        frm, to = row.get("from"), row.get("to")
        if row.get("slot") == "move" and frm and to:
            cell = _move_cell(frm, to, text, poi)   # G2: directions link at cell start
        elif poi:
            cell = _poi_cell(poi, text)
        else:
            cell = md_escape(text)
        lines.append(f"| {time} | {cell} |")
    return "\n".join(lines) + "\n"


def _amount(n):
    """Format a cost number with thousands separators. Integral values (5000 or
    5000.0) render without a decimal point; anything else keeps its fraction."""
    if float(n) == int(n):
        return f"{int(n):,}"
    return f"{n:,}"


def render_markdown_page(itin, poi_map, cost=None):
    """Canonical itinerary.yaml -> the full markdown deliverable page.

    HTML has render_html_page and LINE has render_line_short; until now markdown's
    highest-level function was render_day_table, so every consumer hand-assembled
    the 費用估算 / 備案 / 出發前檢查清單 sections around the day tables. A full
    re-render then silently dropped them, and export-gate had no way to tell the
    file was not reproducible from itinerary.yaml. This is the page-level
    entrypoint: a pure function of {itin, poi_map, cost} that emits every section
    exactly when its data exists, never a template with holes for a human to fill.

    Section order (each omitted entirely when its data is absent):
      # {title}
      per day: render_day_table(...) + "**宿**：" lodging line (only when
        day["lodging"] resolves in poi_map — never falls back to the raw id;
        see the docstring warning below)
      ## 備案 / Contingency  (itin["contingency"])
      ## 出發前檢查清單       (itin["checklist"])
      ## 費用估算（估算非報價） (cost, when given)

    The lodging line must never fall back to the raw id when it does not resolve —
    a hand-rolled consumer renderer once did `if not poi: return f"**宿**：{lid}"`,
    leaking an internal POI id into user-facing text (exactly the class
    scripts/text_hygiene.py::jargon_failures exists to catch).

    Deliberately NOT emitted, unlike render_html_page: the overview table, the
    emoji legend, and the footer. Omitting the overview table is not just a style
    choice — export_gate._find_rows treats every markdown line starting with '|'
    as a scheduled row, so an overview table would inject phantom rows into the
    gate's view of the deliverable.

    Args:
        itin:    Canonical itinerary dict — {title, days, contingency, checklist}.
        poi_map: {poi_id: poi_dict}, resolving row poi_id AND day.lodging.
        cost:    Optional canonical cost dict ({currency, as_of, total, line_items}).
    """
    lines = [f"# {md_escape(itin.get('title', ''))}", ""]

    for day in itin.get("days", []):
        lines.append(render_day_table(day, poi_map).rstrip())
        lines.append("")
        poi = poi_map.get(day.get("lodging"))
        if poi:
            lines.append(f"**宿**：{_poi_cell(poi, '')}")
            lines.append("")

    contingency = itin.get("contingency")
    if contingency:
        lines.append("## 備案 / Contingency")
        lines.append("")
        for c in contingency:
            trigger = md_escape(c.get("trigger", ""))
            fallback = md_escape(c.get("fallback", ""))
            note = c.get("note")
            note_part = f"（{md_escape(note)}）" if note else ""
            lines.append(f"- **{trigger}**{note_part}：{fallback}")
        lines.append("")

    checklist = itin.get("checklist")
    if checklist:
        lines.append("## 出發前檢查清單")
        lines.append("")
        for item in checklist:
            lines.append(f"- {md_escape(item)}")
        lines.append("")

    if cost:
        lines.append("## 費用估算（估算非報價）")
        lines.append("")
        lines.append(f"| 項目 | 明細 | 金額 ({md_escape(cost.get('currency', ''))}) |")
        lines.append("|---|---|---|")
        for item in cost.get("line_items", []):
            category = md_escape(item.get("category", ""))
            label = md_escape(item.get("label", ""))
            lines.append(f"| {category} | {label} | {_amount(item.get('amount', 0))} |")
        lines.append(f"| **合計** | | **{_amount(cost.get('total', 0))}** |")
        lines.append("")
        lines.append(f"_as\\_of {md_escape(cost.get('as_of', ''))}。估算值非報價。_")

    # rstrip + single trailing "\n": several branches above can end on a blank
    # "" section-separator (e.g. when cost is absent), which "\n".join already
    # renders as a trailing newline of its own — normalising here is what keeps
    # the page ending in exactly one "\n" regardless of which sections fired.
    return "\n".join(lines).rstrip("\n") + "\n"
