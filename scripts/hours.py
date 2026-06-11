"""Opening-hours buffer logic — intra-day scheduling safety.

Day-granularity closure lives in calendar.py; this module answers the
finer question synthesis must also ask: given a scheduled arrival time, is
there enough buffer before the place stops admitting (last order / last
entry) and before it closes? Pure functions, unit-testable, mirroring the
verify.py / distance.py / calendar.py split.
"""
import re

_HHMM = re.compile(r"^\d{1,2}:\d{2}$")


def to_minutes(hhmm):
    """'21:30' -> 1290 (minutes since midnight).

    Accepts an int (PyYAML parses an unquoted sexagesimal `21:30` as 1290 already)
    or an 'HH:MM' string; anything else raises with an actionable message so an
    unquoted/garbled time surfaces at the stage instead of crashing deep in scheduling.
    """
    if isinstance(hhmm, int) and not isinstance(hhmm, bool):
        return hhmm
    if not isinstance(hhmm, str) or not _HHMM.match(hhmm):
        raise ValueError(
            f"expected 'HH:MM' time string, got {hhmm!r} — quote times in YAML ('21:30')")
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def closing_status(start, close, last_call=None, need_mins=0):
    """Classify a scheduled arrival against a POI's closing window.

    Args:
        start:     arrival/visit-start time 'HH:MM'.
        close:     closing time 'HH:MM'.
        last_call: latest time you may be seated/admitted (restaurant last
                   order, sight last entry); defaults to `close`. Clamped to
                   `close` if given later than it.
        need_mins: minutes needed at the POI before close (dwell). Synthesis
                   passes max(global min_buffer floor, POI typical_visit_mins
                   or a category default).

    Returns (status, reason) where status is one of:
        'ok'              — fits with enough buffer.
        'tight'           — admitted in time but < need_mins before close.
        'after_last_call' — arrives after last order / last entry.
        'closed'          — arrives at or after closing.

    Same-day hours only; overnight windows (close past midnight) are out of
    scope here and should be handled as a special case by synthesis.
    """
    s = to_minutes(start)
    c = to_minutes(close)
    # Overnight window: a close in the small hours (e.g. 02:00) is next-day. Extend it
    # past midnight so an evening arrival isn't falsely reported 'closed'. (TW-047)
    overnight = c < s and c <= 5 * 60
    if overnight:
        c += 24 * 60
    if last_call:
        lc_raw = to_minutes(last_call)
        if overnight and lc_raw <= 5 * 60:
            lc_raw += 24 * 60
        lc = min(lc_raw, c)
    else:
        lc = c

    if s >= c:
        return "closed", f"scheduled {start} is at/after closing {close}"
    if s > lc:
        last = last_call or close
        return "after_last_call", f"scheduled {start} is after last order/entry {last}"
    if (c - s) < need_mins:
        return "tight", f"only {c - s} min before closing {close}; needs >= {need_mins}"
    return "ok", ""
