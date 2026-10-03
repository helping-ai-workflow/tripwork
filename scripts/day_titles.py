"""Day-title candidates (v1.1 topic 7, spec §7.1).

itinerary-synthesis proposes six titles a day, each one shape x one twist; the user
picks (stop `day_title_pick`). Whether a title is funny or poetic is the user's call.
What is checked here is what can be checked mechanically: each candidate's form, the
day's mix (scene / twist / skeleton / length quotas), the rhyme on Taiwan readings
(scripts/zhuyin.py), and what may not repeat across the trip. The user's picks only
draw notices.

Messages never quote a candidate's text: it is free text, and free text in a routed
failure message can hijack gate routing (v1.0 P1 final review, I3).
"""
import collections
import math
import re

from scripts import zhuyin
from scripts.brief_names import riff_overlap_ok
from scripts.text_hygiene import ai_tone_failures

THEME_MAX = 13                       # characters, punctuation included (ring: 13 px ~ 250°)
SIX = 6
SHAPES = ("couplet", "sentence", "triple", "question", "chiasmus", "anadiplosis", "number", "onomatopoeia")
WORDPLAY = {"chiasmus", "anadiplosis", "number", "onomatopoeia"}   # the shape is the play; twist optional
SIGNATURE = WORDPLAY                                                # at most 2 days each
TWISTS = ("rhyme", "pun", "contrast", "exaggerate", "pov", "swap", "double_meaning", "turn")
RIFF_TWISTS = {"pun", "swap", "double_meaning"}
# 有畫面: a sensory scene word (spec list, extendable) ...
IMAGERY = set("光燈夜霧煙湖海雪風香暖冷山河港月星雲晨湯影色浪潮霜火水霞雨露泉林花橋岸")
# ... closing on the scene, not on an act or a particle, and not chatty
BAD_END = set("嗎了吃看呢吧啊喝買走去來做玩飽痛碎")
COLLOQUIAL = ("還要", "繼續", "得先", "什麼", "一下", "東西", "然後")
PARTICLES = set("了的啦呢嗎吧啊呀")
# trip-wide keywords (nouns other than place names) that may appear on at most 2 days;
# a lexicon because naming nouns in free text is not mechanical -- extend it as trips need.
# Roots: a word that contains one counts as it (螃蟹 is 蟹, 烤羊 and 羊肉 are 羊).
KEYWORDS = ("蟹", "行李", "熊", "啤酒", "拉麵", "壽司", "海鮮", "羊", "牛奶", "冰淇淋", "咖啡", "伴手禮",
            "便當", "纜車", "火車", "飛機", "溫泉", "丼", "夜景", "甜點", "布丁", "起司", "哈密瓜",
            "玉米", "馬鈴薯", "生蠔", "海膽", "鮭魚", "餃子", "咖哩")
_SEP = re.compile(r"[，、；：,;:]")
_END = re.compile(r"[。！？!?…～~]+$")
_NUM = re.compile(r"[一二三四五六七八九十百千萬兩0-9０-９]")
S = "day theme invalid: "


def _t(c):
    return c.get("text").strip() if isinstance(c, dict) and isinstance(c.get("text"), str) else ""


def segments(text):
    return [s for s in _SEP.split(_END.sub("", text or "")) if s]


def skeleton(text):
    """whole / two / three / question (spec 骨架)."""
    if (text or "").rstrip().endswith(("？", "?")):
        return "question"
    n = len(segments(text))
    return "whole" if n <= 1 else "two" if n == 2 else "three"


def size(text):
    n = len(text)
    return "short" if n <= 7 else "mid" if n <= 10 else "long" if n <= THEME_MAX else "over"


def _end_key(seg):
    i = len(seg) - 1
    while i >= 0 and seg[i] in PARTICLES:
        i -= 1
    if i < 0:
        return None
    zy = zhuyin.reading(seg, i)
    return zhuyin.syllable_key(zy) if zy else None


def rhyme(text):
    """(rhyme group, tone) when the last two segments end alike on Taiwan readings."""
    segs = segments(text)
    if len(segs) < 2:
        return None
    a, b = _end_key(segs[-2]), _end_key(segs[-1])
    return a if a and a == b else None


def rhyme_label(text):
    r = rhyme(text)
    return f"{r[0]}韻" if r else ""


def is_scene(text):
    core = _END.sub("", text)
    return (bool(IMAGERY & set(core)) and bool(core) and core[-1] not in BAD_END
            and not any(w in core for w in COLLOQUIAL))


def _shape_ok(shape, text):
    segs = segments(text)
    if shape == "question":
        return skeleton(text) == "question"
    if shape == "sentence":
        return len(segs) == 1 and skeleton(text) != "question"
    if shape == "couplet":
        return len(segs) == 2
    if shape == "triple":
        return len(segs) == 3
    if shape == "chiasmus":
        return len(segs) == 2 and segs[0] != segs[1] and collections.Counter(segs[0]) == collections.Counter(segs[1])
    if shape == "anadiplosis":
        return len(segs) >= 2 and any(x[-1] == y[0] for x, y in zip(segs, segs[1:]))
    if shape == "number":
        return bool(_NUM.search(text))
    if shape == "onomatopoeia":
        return _onomatopoeia(text) is not None
    return False


def _onomatopoeia(text):
    """The first character of a doubled sound (AA, ABAB), or None."""
    for i in range(len(text) - 1):
        if text[i] == text[i + 1] and not _SEP.match(text[i]):
            return text[i]
        if i + 3 < len(text) and text[i:i + 2] == text[i + 2:i + 4]:
            return text[i]
    return None


def display_order(cands):
    """Indices in the order the picker and the text list number them: the first six short
    to long, then each later batch of three short to long -- so asking for more never
    renumbers what the user has already seen."""
    n = len(cands)
    first = sorted(range(min(SIX, n)), key=lambda k: (len(_t(cands[k])), k))
    rest = []
    for s in range(SIX, n, 3):
        rest += sorted(range(s, min(s + 3, n)), key=lambda k: (len(_t(cands[k])), k))
    return first + rest


def _one(date, k, c, nodes):
    out = []
    text = _t(c)
    if not text:
        return [S + f"{date} candidate {k} has no text"]
    if len(text) > THEME_MAX:
        out.append(S + f"{date} candidate {k} is {len(text)} chars (max {THEME_MAX})")
    shape, twist = c.get("shape"), c.get("twist")
    if shape not in SHAPES:
        out.append(S + f"{date} candidate {k} shape is not one of {', '.join(SHAPES)}")
    elif not _shape_ok(shape, text):
        out.append(S + f"{date} candidate {k} is not a{'n' if shape[0] in 'aeiou' else ''} {shape}")
    if twist is None:
        if shape not in WORDPLAY:
            out.append(S + f"{date} candidate {k} has no twist (only {', '.join(sorted(WORDPLAY))} may go without)")
    elif twist not in TWISTS:
        out.append(S + f"{date} candidate {k} twist is not one of {', '.join(TWISTS)}")
    elif twist == "rhyme" and rhyme(text) is None:
        out.append(S + f"{date} candidate {k} is labelled rhyme but its last two halves do not end in the "
                       f"same rhyme and tone on Taiwan readings (or a reading is unknown)")
    elif twist in RIFF_TWISTS:
        riff = c.get("riff_on").strip() if isinstance(c.get("riff_on"), str) else ""
        if not riff:
            out.append(S + f"{date} candidate {k} has no riff_on ({twist} reworks a known line)")
        elif not riff_overlap_ok(text, riff):
            out.append(S + f"{date} candidate {k} does not rework its riff_on")
    if ai_tone_failures(text):
        # the scan's own message quotes the text; this one must not (routing, see above)
        out.append(S + f"{date} candidate {k} fails the AI tone scan")
    refs = c.get("refs")
    if not isinstance(refs, list) or not refs or any(not isinstance(r, str) or r not in nodes for r in refs):
        out.append(S + f"{date} candidate {k} refs must name stops of that day")
    return out


def _quotas(date, first):
    out = []
    texts = [_t(c) for c in first]
    if sum(is_scene(t) for t in texts) < 3:
        out.append(S + f"{date} fewer than 3 candidates paint a scene and end on it")
    if sum(isinstance(c, dict) and c.get("twist") in TWISTS for c in first) < 3:
        out.append(S + f"{date} fewer than 3 candidates use a twist")
    over = sorted(s for s, n in collections.Counter(skeleton(t) for t in texts).items() if n > 2)
    if over:
        out.append(S + f"{date} the {', '.join(over)} skeleton is used more than twice")
    sizes = collections.Counter(size(t) for t in texts)
    if any(sizes[s] != 2 for s in ("short", "mid", "long")):
        out.append(S + f"{date} lengths are not 2 short (≤7), 2 mid (8–10), 2 long (11–13)")
    return out


def candidate_failures(itinerary):
    from scripts.day_chain import node_poi_ids
    out, kw_days, shape_days, ono = [], collections.defaultdict(set), collections.defaultdict(set), {}
    trip_lines = {}                                    # text -> first date: a line may not sit on two days
    for d in (itinerary or {}).get("days") or []:
        date = d.get("date", "?")
        cands = d.get("theme_candidates")
        if cands is None:
            continue                                   # theme_failures says so, once
        if not isinstance(cands, list) or len(cands) < SIX:
            out.append(S + f"{date} has {len(cands) if isinstance(cands, list) else 0} candidates "
                           f"(6 candidates required)")
            cands = cands if isinstance(cands, list) else []
        nodes = node_poi_ids(d)
        seen = {}
        for k, c in enumerate(cands):
            if not isinstance(c, dict):
                out.append(S + f"{date} candidate {k} is not a record")
                continue
            out += _one(date, k, c, nodes)
            text = _t(c)
            if text in seen:
                out.append(S + f"{date} candidate {k} repeats candidate {seen[text]}")
            elif trip_lines.get(text, date) != date:
                out.append(S + f"{date} candidate {k} repeats a candidate of {trip_lines[text]}")
            seen.setdefault(text, k)
            trip_lines.setdefault(text, date)
            for w in KEYWORDS:
                if w in text:
                    kw_days[w].add(date)
            if c.get("shape") in SIGNATURE:
                shape_days[c["shape"]].add(date)
            if c.get("shape") == "onomatopoeia":
                o = _onomatopoeia(text)
                if o:
                    ono.setdefault(o, []).append(date)
        if len(cands) >= SIX:
            out += _quotas(date, cands[:SIX])
    for w, days in sorted(kw_days.items()):
        if len(days) > 2:
            out.append(S + f"keyword {w} appears in the candidates of {len(days)} days (max 2)")
    for s, days in sorted(shape_days.items()):
        if len(days) > 2:
            out.append(S + f"shape {s} is used on {len(days)} days (max 2)")
    for o, dates in ono.items():
        if len(dates) > 1:
            out.append(S + f"onomatopoeia on {', '.join(sorted(set(dates)))} starts with the same sound")
    return out


def picked(day):
    """The candidate the day's theme was picked from, or None (user-written / not found)."""
    if day.get("theme_user_written"):
        return None
    theme = (day.get("theme") or "").strip()
    for c in day.get("theme_candidates") or []:
        if isinstance(c, dict) and _t(c) == theme:
            return c
    return None


def pick_notices(itinerary):
    """The user's picks never fail; two patterns are worth a word (spec §7.1)."""
    days = [d for d in (itinerary or {}).get("days") or [] if isinstance(d, dict) and d.get("theme")]
    out = []
    names = {"whole": "one-sentence", "two": "two-part", "three": "three-part", "question": "question"}
    for a, b in zip(days, days[1:]):
        sa, sb = skeleton(a["theme"]), skeleton(b["theme"])
        if sa == sb:
            out.append(f"day titles: {a.get('date')} and {b.get('date')} both have the {names[sa]} skeleton")
    twists = collections.Counter((picked(d) or {}).get("twist") for d in days)
    cap = math.ceil(len(days) / 3)
    for tw, n in sorted((t, n) for t, n in twists.items() if t):
        if n > cap:
            out.append(f"day titles: twist {tw} is picked on {n} days (more than {cap})")
    return out
