"""Canonical itinerary.yaml -> LINE-friendly short plain text. No links, elder-friendly."""

DIVIDER = "━━━━━━━━━━━━━"
_SLOT_EMOJI = {"meal": "🍽", "activity": "🎯", "visit": "📍", "move": "🚆", "lodging": "🏨"}

LINE_LIMIT = 5000  # LINE single-message character cap

def _day_block(day):
    lines = [DIVIDER, day.get("label", ""), DIVIDER]
    for row in day.get("rows", []):
        time = row.get("time", "")
        emoji = _SLOT_EMOJI.get(row.get("slot", ""), "")
        text = row.get("text", "")
        prefix = f"{time} " if time else ""
        lines.append(f"{prefix}{f'{emoji} {text}'.strip()}".strip())
    return "\n".join(lines)

def render_line_short(itin):
    parts = [itin.get("title", "行程"), ""]
    for day in itin.get("days", []):
        parts.append(_day_block(day))
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"

def chunk_line_messages(itin, limit=LINE_LIMIT):
    """Render the itinerary as a list of LINE messages, each <= `limit` chars,
    split at day boundaries so no message exceeds LINE's send cap. (TW-049)

    A single day larger than `limit` becomes its own (over-limit) chunk rather than
    being silently dropped — the caller surfaces it; days are never split mid-row.
    """
    title = itin.get("title", "行程")
    chunks, cur = [], title
    for day in itin.get("days", []):
        block = "\n\n" + _day_block(day)
        if len(cur) + len(block) > limit and cur.strip():
            chunks.append(cur.rstrip() + "\n")
            cur = title + " (續)" + block
        else:
            cur += block
    if cur.strip():
        chunks.append(cur.rstrip() + "\n")
    return chunks
