"""Itinerary day -> Markdown table, embedding gmaps links for rows with a POI."""
from scripts.render.gmaps_links import link_markdown

def render_day_table(day):
    lines = [f"### {day.get('label', '')}", "", "| 時段 | 行程 |", "|---|---|"]
    for row in day.get("rows", []):
        time = row.get("time", "")
        text = row.get("text", "")
        poi = row.get("poi")
        cell = f"{link_markdown(poi)} {text}".strip() if poi else text
        lines.append(f"| {time} | {cell} |")
    return "\n".join(lines) + "\n"
