"""Itinerary dict -> LINE-friendly short plain text. No links, elder-friendly."""

DIVIDER = "━━━━━━━━━━━━━"

def render_line_short(itin):
    lines = [itin.get("title", "行程"), ""]
    for day in itin.get("days", []):
        lines.append(DIVIDER)
        lines.append(day.get("label", ""))
        lines.append(DIVIDER)
        for it in day.get("items", []):
            time = it.get("time", "")
            emoji = it.get("emoji", "")
            text = it.get("text", "")
            prefix = f"{time} " if time else ""
            piece = f"{emoji} {text}".strip()
            lines.append(f"{prefix}{piece}".strip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
