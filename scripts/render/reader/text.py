"""Small text helpers shared by the reader's screens."""
import datetime
import html

WEEKDAYS = "日一二三四五六"
LANG = {"ja": "日文", "ko": "韓文", "en": "英文", "zh": "中文"}


def esc(value):
    return html.escape("" if value is None else str(value), quote=True)


def to_date(iso):
    return datetime.date.fromisoformat(str(iso))


def weekday(d):
    return WEEKDAYS[(d.weekday() + 1) % 7]


def md(d):
    return f"{d.month}/{d.day}"


def md_wd(d):
    return f"{d.month}/{d.day}（{weekday(d)}）"


def minutes(hhmm):
    """'HH:MM' -> minutes after midnight, or None."""
    try:
        h, m = str(hhmm).split(":")
        return int(h) * 60 + int(m)
    except (TypeError, ValueError):
        return None


def hhmm(total):
    total = int(round(total))
    return f"{total // 60 % 24:02d}:{total % 60:02d}"


def dur(mins):
    mins = int(round(mins))
    if mins < 60:
        return f"{mins} 分"
    return f"{mins // 60} 小時" + (f" {mins % 60} 分" if mins % 60 else "")


def lang_label(lang):
    """A display label for a language code; always safe to drop into HTML."""
    lang = lang.lower() if isinstance(lang, str) else ""
    return esc(LANG.get(lang.split("-")[0], lang.upper() or "外文"))


def number(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


# How a move reads in the 移動列 and the map card's 路線列: one format for both, the
# distance in brackets (v1.1, the user's pick of four on the design board).
def move_summary(label, mins, km):
    """'計程車 30 分（9.7 km）'; the bracket only when the distance is known."""
    head = f"{label} {mins:g} 分" if mins is not None else label
    return f'<b>{esc(head)}</b>' + (f'<span class="lkm">（{km:g} km）</span>' if km is not None else "")
