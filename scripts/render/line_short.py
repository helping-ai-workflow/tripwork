"""Canonical itinerary.yaml -> LINE-friendly short plain text. No links, elder-friendly."""

DIVIDER = "━━━━━━━━━━━━━"
_SLOT_EMOJI = {"meal": "🍽", "activity": "🎯", "visit": "📍", "move": "🚆", "lodging": "🏨"}

def render_line_short(itin):
    lines = [itin.get("title", "行程"), ""]
    for day in itin.get("days", []):
        lines.append(DIVIDER)
        lines.append(day.get("label", ""))
        lines.append(DIVIDER)
        for row in day.get("rows", []):
            time = row.get("time", "")
            emoji = _SLOT_EMOJI.get(row.get("slot", ""), "")
            text = row.get("text", "")
            prefix = f"{time} " if time else ""
            piece = f"{emoji} {text}".strip()
            lines.append(f"{prefix}{piece}".strip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
