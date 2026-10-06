"""trip-brief naming rules for the v1.0 reader (spec §4.5, §5.2).

short_name feeds the deliverable filename (`{start} {short_name} {length}`, ≤22
chars so the iPhone Files list does not truncate it); headline is the KUSO home
title, chosen by the user from six candidates, one per device (v1.1 topic 7;
more come in batches of three when the user asks). Whether a headline is FUNNY is not mechanical -- the user's pick is the
check. This module only rejects what is mechanically wrong: missing, too long,
no anchor in must_do, a riff that does not rework its original, AI tone.
"""
import datetime
import re

from scripts.text_hygiene import ai_tone_failures

STEM_MAX = 22
HEADLINE_MAX = 14
# v1.1 topic 7: 雙關 (double_meaning) replaces 老梗 (meme), as for the day titles
DEVICES = ("swap", "pun", "contrast", "exaggerate", "pov", "double_meaning")
RIFF_DEVICES = {"swap", "pun", "double_meaning"}
HEADLINE_N = 6
_SAFE = re.compile(r"^[぀-ヿ㐀-鿿A-Za-z0-9 ]+$")
_PUNCT = re.compile(r"[\s，、。！？!?,.・：:；;「」『』（）()…~〜\-—]")
N = "trip-brief name invalid: "
H = "trip-brief headline invalid: "


def _text(v):
    return v.strip() if isinstance(v, str) else ""


def _dates(brief):
    d = (brief or {}).get("dates") or {}
    return (datetime.date.fromisoformat(str(d.get("start"))),
            datetime.date.fromisoformat(str(d.get("end"))))


def trip_length_label(brief):
    start, end = _dates(brief)
    n = (end - start).days + 1
    if n == 1:
        return brief.get("day_label") or "一日遊"
    return f"{n}天{n - 1}夜"


def is_survey(brief):
    """A survey brief (v2.1.0 §10): collect and verify places, no itinerary."""
    return (brief or {}).get("mode") == "survey"


def deliverable_stem(brief):
    if is_survey(brief):                   # a list has no dates to lead its file name
        return f"{brief['short_name']} 清單"
    return f"{brief['dates']['start']} {brief['short_name']} {trip_length_label(brief)}"


def must_do_names(brief):
    out = []
    for m in (brief or {}).get("must_do") or []:
        if isinstance(m, str):
            out.append(m)
        elif isinstance(m, dict) and m.get("name"):
            out.append(m["name"])
    return out


def _sounds(ch):
    """A character's syllables without tone (沖 and 衝 both give ㄔㄨㄥ)."""
    from scripts.zhuyin import readings
    return {r.translate(_TONELESS) for r in readings(ch)}


_TONELESS = str.maketrans("", "", "ˊˇˋ˙")


def riff_overlap_ok(text, riff):
    """The title reworks the line it riffs on: at least half of the riff's characters
    are kept, or swapped for one that sounds the same -- a pun (沖沖沖 <- 衝衝衝)."""
    chars = set(_PUNCT.sub("", riff or ""))
    if not chars or text == riff:
        return False
    heard = set().union(*(_sounds(c) for c in set(text))) if text else set()
    kept = {c for c in chars if c in text or _sounds(c) & heard}
    return 2 * len(kept) >= len(chars)


def name_failures(brief):
    brief = brief or {}
    out = []
    try:
        start, end = _dates(brief)
    except (AttributeError, TypeError, ValueError):
        if not (is_survey(brief) and not brief.get("dates")):
            return [N + "dates are not valid ISO dates"]
        start = end = None                 # a survey without dates names its list only
    sn = brief.get("short_name")
    if not (isinstance(sn, str) and sn.strip()):
        out.append(N + "short_name missing")
    else:
        if not 2 <= len(sn) <= 8:
            out.append(N + f"short_name is {len(sn)} chars (2–8)")
        if not _SAFE.match(sn):
            out.append(N + "short_name has characters a filename cannot carry")
    dl = brief.get("day_label")
    if dl is not None:
        if start != end:
            out.append(N + "day_label is only for a same-day trip")
        elif not (isinstance(dl, str) and 2 <= len(dl) <= 6 and _SAFE.match(dl)):
            out.append(N + "day_label must be 2–6 filename-safe characters")
    if not out:
        stem = deliverable_stem(brief)
        if len(stem) > STEM_MAX:
            out.append(N + f"deliverable name is {len(stem)} chars (max {STEM_MAX})")
    return out


def headline_failures(brief):
    brief = brief or {}
    head = brief.get("headline") or {}
    text = _text(head.get("text")) if isinstance(head, dict) else ""
    if not text:
        return [H + "headline missing"]
    out = []
    cands = brief.get("headline_candidates")
    cands = cands if isinstance(cands, list) else []
    if len(cands) < HEADLINE_N:
        out.append(H + f"{len(cands)} candidates recorded ({HEADLINE_N} required)")
    if not all(isinstance(c, dict) for c in cands):
        out.append(H + "a candidate is not a record")
        cands = [c for c in cands if isinstance(c, dict)]
    devices = [c.get("device") if isinstance(c.get("device"), str) else None for c in cands]
    if any(dv not in DEVICES for dv in devices):
        out.append(H + "a candidate's device is not one of the six")
    if len(cands) >= HEADLINE_N and sorted(map(str, devices[:HEADLINE_N])) != sorted(DEVICES):
        out.append(H + "the first 6 candidates must use each of the six devices once")
    names = set(must_do_names(brief))
    for k, c in enumerate(cands):
        ct = _text(c.get("text"))
        if not ct:
            out.append(H + f"candidate {k} has no text")
            continue
        visible = len(_PUNCT.sub("", ct))
        if visible > HEADLINE_MAX:
            out.append(H + f"candidate {k} is {visible} chars (max {HEADLINE_MAX})")
        refs = c.get("refs") if isinstance(c.get("refs"), list) else []
        if names and (not refs or any(r not in names for r in refs)):
            out.append(H + f"candidate {k} refs must name must_do entries")
        if c.get("device") in RIFF_DEVICES:
            riff = _text(c.get("riff_on"))
            if not riff:
                out.append(H + f"candidate {k} has no riff_on")
            elif not riff_overlap_ok(ct, riff):
                out.append(H + f"candidate {k} does not rework its riff_on")
        if ai_tone_failures(ct):
            out.append(H + f"candidate {k} fails the AI tone scan")
    if not head.get("user_written") and text not in {_text(c.get("text")) for c in cands}:
        out.append(H + "chosen headline is neither a candidate nor marked user_written")
    return out
