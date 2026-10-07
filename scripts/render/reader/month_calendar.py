"""The stamp calendar (spec §6.2): 7 columns Sun–Sat, trip days as slightly rotated
double-ring stamps coloured by that night's area, the last day a dashed 返程,
other days grey and not clickable."""
import calendar as _cal
import datetime

from scripts.render.reader.text import WEEKDAYS, esc

TILT = (-6, 4, -3, 7, -5, 3, -7, 5)


def area_classes(accommodations):
    """area_label -> r1/r2/r3/r4 in the order the stops appear (same area, same colour)."""
    out = {}
    for stop in (accommodations or {}).get("stops") or []:
        label = stop.get("area_label")
        if isinstance(label, str) and label and label not in out:
            out[label] = f"r{len(out) % 4 + 1}"
    return out


def day_areas(itinerary, accommodations):
    """[(area text, colour class)] per day. The last day without lodging is 返程."""
    by_chosen = {s.get("chosen"): s.get("area_label") for s in (accommodations or {}).get("stops") or []}
    colours = area_classes(accommodations)
    days = itinerary.get("days") or []
    out = []
    for i, d in enumerate(days):
        label = by_chosen.get(d.get("lodging"))
        if label:
            out.append((label, colours.get(label, "r1")))
        elif i == len(days) - 1:
            out.append(("返程", "r0"))
        else:
            out.append(("移動", "r0"))
    return out


def month_title(dates):
    """'2026 年 11 月'; across months '2026 年 10～11 月'; across years
    '2026 年 12 月～2027 年 1 月' (spec v1.1 §6.2). Home card and day header both call this."""
    if not dates:
        return ""
    ds = sorted(dates)
    a, b = ds[0], ds[-1]
    if (a.year, a.month) == (b.year, b.month):
        return f"{a.year} 年 {a.month} 月"
    if a.year == b.year:
        return f"{a.year} 年 {a.month}～{b.month} 月"
    return f"{a.year} 年 {a.month} 月～{b.year} 年 {b.month} 月"


def _day_label(d, plain=False):
    """The 1st of a month reads M/1, so a calendar that crosses months shows where; a
    whole-month grid (plain) keeps its own 1st as '1'."""
    return f"{d.month}/1" if d.day == 1 and not plain else str(d.day)


RING_BOX = 140
# desktop home stamp (theme.py): 65 px wide, outline 2 px at 3 px -> the outer ring's
# outside edge is 64.6/2 + 3 + 2 = 37.3 px from the centre; the theme's em box sits 3 px out
RING_R = 40.3
RING_MAX = 15                      # 13 px glyphs; about 300 degrees of this ring


def ring_text(text):
    text = (text or "").strip()
    return text if len(text) <= RING_MAX else text[:RING_MAX - 1] + "…"


def ring_svg(i, text):
    """The day's theme around its stamp (v1.1 topic 6, the user's pick): centred at the
    top, the stamp's colour, turning with the stamp (it sits inside the rotated label).
    Shown on the desktop home only (theme.py)."""
    text = ring_text(text)
    if not text:
        return ""
    c, r = RING_BOX / 2, RING_R
    return (f'<svg class="ring" viewBox="0 0 {RING_BOX} {RING_BOX}" aria-hidden="true">'
            f'<defs><path id="rg-d{i}" d="M{c:g},{c + r:g} a{r:g},{r:g} 0 1,1 0,-{2 * r:g} a{r:g},{r:g} 0 1,1 0,{2 * r:g}"/></defs>'
            f'<text dominant-baseline="text-after-edge"><textPath href="#rg-d{i}" startOffset="50%" text-anchor="middle">'
            f'{esc(text)}</textPath></text></svg>')


def stamp(i, date, area, cls, cur=False, plain=False, ring="", tape=None):
    m1 = date.day == 1 and not plain
    extra = (" cur" if cur else "") + (" m1" if m1 else "")
    # the home calendar's stamps carry their day's tape (tapes.py); the page script shows today's
    extra += f" tp-{tape.pattern} tc-{tape.colour} tt{tape.tear}" if tape else ""
    tr = f";--tr:{tape.tilt:.1f}deg" if tape else ""
    return (f'<label class="stamp {cls}{extra}" for="pg-d{i}" style="--t:{TILT[(i - 1) % len(TILT)]}deg{tr}">'
            f'<b>{_day_label(date, plain)}</b><small>{esc(area)}</small>{ring_svg(i, ring) if ring else ""}</label>')


def _head():
    return "".join(f'<span class="wd{" sun" if k == 0 else " sat" if k == 6 else ""}">{w}</span>'
                   for k, w in enumerate(WEEKDAYS))


def _off(date, k, plain=False):
    return f'<span class="off{" sun" if k == 0 else " sat" if k == 6 else ""}">{_day_label(date, plain)}</span>'


def _cells(week, trip, cur, month=None, rings=None, tapes=None):
    """A week of cells. With `month` the grid is that month alone: other months' days are
    blank and its own 1st reads '1'."""
    plain = month is not None
    out = []
    for k, x in enumerate(week):
        if month is not None and x.month != month:
            out.append("<span></span>")          # the other month draws its own days
        elif x in trip:
            i, area, cls = trip[x]
            out.append(stamp(i, x, area, cls, cur == i, plain, (rings[i - 1] if rings and i <= len(rings) else ""),
                             tapes[i - 1] if tapes and i <= len(tapes) else None))
        else:
            out.append(_off(x, k, plain))
    return "".join(out)


def _trip_weeks(dates, min_rows=5, max_before=2):
    """Sundays of the weeks drawn for a trip across months: first -> last trip week,
    padded to `min_rows` alternating after / before (before capped at `max_before`).
    A run with more than two empty weeks (a typo'd year, review I3) keeps only the trip
    weeks, unpadded -- as mini() and desktop.big_calendar() do."""
    held = sorted({d - datetime.timedelta(days=(d.weekday() + 1) % 7) for d in dates})
    start, end = held[0], held[-1]
    weeks = [start + datetime.timedelta(days=7 * n) for n in range((end - start).days // 7 + 1)]
    if len(weeks) - len(held) > 2:
        return held
    before, after_turn = 0, True
    while len(weeks) < min_rows:
        if after_turn or before >= max_before:
            weeks.append(weeks[-1] + datetime.timedelta(days=7))
        else:
            weeks.insert(0, weeks[0] - datetime.timedelta(days=7))
            before += 1
        after_turn = not after_turn
    return weeks


def months(dates, areas, rings=None, tapes=None):
    """One card (spec v1.1 §6.2): a single-month trip draws its whole month; a trip
    across months draws continuous weeks. The card title is month_title()."""
    if not dates:
        return ""
    trip = {d: (i, a, c) for i, (d, (a, c)) in enumerate(zip(dates, areas), start=1)}
    if len({(d.year, d.month) for d in dates}) <= 1:
        d0 = dates[0]
        weeks = _cal.Calendar(firstweekday=6).monthdatescalendar(d0.year, d0.month)
        body = "".join(_cells(w, trip, None, d0.month, rings, tapes) for w in weeks)
    else:
        weeks = _trip_weeks(dates)
        body = "".join(_cells([s + datetime.timedelta(days=k) for k in range(7)], trip, None, rings=rings, tapes=tapes)
                       for s in weeks)
    # --wk: the desktop sizes its stamps from the row height (theme.py, review I3)
    return (f'<div class="months"><div class="month"><h3>{esc(month_title(dates))}</h3>'
            f'<div class="g" style="--wk:{len(weeks)}">{_head()}{body}</div></div></div>')


def weeks(dates):
    """The weeks (Sunday first) that hold trip days: the day pages' mini calendar rows."""
    starts = sorted({d - datetime.timedelta(days=(d.weekday() + 1) % 7) for d in dates})
    return [[s + datetime.timedelta(days=k) for k in range(7)] for s in starts]


def mini(dates, areas, cur):
    """Only the weeks that hold trip days, across a month boundary (day pages)."""
    trip = {d: (i, a, c) for i, (d, (a, c)) in enumerate(zip(dates, areas), start=1)}
    weeks_ = weeks(dates)
    return f'<div class="mini"><div class="g">{_head()}{"".join(_cells(w, trip, cur) for w in weeks_)}</div></div>'
