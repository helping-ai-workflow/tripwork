"""The trip's heading, shared by every deliverable (spec §4.5): the brief's KUSO
headline, then `short_name N天M夜・start – end`. itinerary.title is retired; it is
read only as the fallback for a pre-v1.0 itinerary rendered without a brief."""
from scripts.brief_names import trip_length_label


def trip_title(brief, itinerary):
    headline = (brief or {}).get("headline")
    text = headline.get("text") if isinstance(headline, dict) else None
    return text or (brief or {}).get("short_name") or (itinerary or {}).get("title") or "行程"


def _dates(itinerary):
    from scripts.render.reader.text import to_date      # lazy: the reader package imports this module
    out = []
    for d in (itinerary or {}).get("days") or []:
        try:
            out.append(to_date(d.get("date")))
        except (AttributeError, TypeError, ValueError):
            continue
    return out


def dates_line(brief, itinerary):
    brief = brief or {}
    try:
        length = trip_length_label(brief)
    except (KeyError, TypeError, ValueError, AttributeError):
        length = ""
    head = " ".join(x for x in (brief.get("short_name") or "", length) if x)
    from scripts.render.reader.text import md_wd
    dates = _dates(itinerary)
    span = f"{md_wd(dates[0])} – {md_wd(dates[-1])}" if dates else ""
    return "・".join(x for x in (head, span) if x)
