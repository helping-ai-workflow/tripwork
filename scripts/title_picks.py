"""The user's title picks, back into the artifacts (v1.1 topic 7, spec §7.3).

The title picker page copies one line, and the plain-text list asks for the same:

    tripwork 標題 H=2 D1=3 D2="自己寫的" D5=+

H is the headline (its stored order), Dn a day (the picker's order, short to long --
scripts/day_titles.py::display_order), a quoted text the user's own words, and `+` a
request for three more. The prefix is optional, full-width letters / digits / signs and
「」 “” quotes are read as their plain forms, and a partial reply touches only the
days it names. Anything else is an error and nothing is written -- including own words
the gate would refuse (the AI-tone scan, e.g. an em dash) and two days ending on the
same title: the user hears it now, not after a gate failure routed to a stage that
cannot change their words. A picked day is marked `theme_picked`, so a picker written
again after 再給我 3 個 keeps it.

CLI: python scripts/title_picks.py <trip-dir> '<reply line>'
Exit 0 written (a `more:` line lists what needs three more) / 2 the reply is not valid.
"""
if __name__ == "__main__" and __package__ in (None, ""):
    # repo root on sys.path, scripts/ shadow dropped (scripts/_cli_bootstrap.py)
    import pathlib as _bootpath, sys as _bootsys
    _bootsys.path.insert(0, str(_bootpath.Path(__file__).resolve().parent))
    import _cli_bootstrap        # noqa: F401  (imported for its side effect)

import re
import unicodedata

from scripts.brief_names import HEADLINE_MAX, _PUNCT
from scripts.day_titles import THEME_MAX, display_order
from scripts.text_hygiene import ai_tone_failures

_QUOTES = {"「": '"', "」": '"', "『": '"', "』": '"', "“": '"', "”": '"', "＂": '"'}
_PREFIX = re.compile(r"\s*tripwork\s*(標題)?", re.I)
_PICK = re.compile(r'\s*([HD])\s*(\d*)\s*=\s*(?:"([^"]*)"|(\+)|(\d+))\s*[,，、]?', re.I)


class PickError(ValueError):
    pass


def _plain(line):
    """Per-character NFKC so positions stay aligned with the original (the user's own
    words are taken from the original, punctuation untouched)."""
    out = []
    for ch in line:
        n = _QUOTES.get(ch) or unicodedata.normalize("NFKC", ch)
        out.append(n if len(n) == 1 else ch)
    return "".join(out)


def parse(line):
    raw = line or ""
    s = _plain(raw)
    pos = 0
    m = _PREFIX.match(s)
    if m:
        pos = m.end()
    out = {"H": None, "days": {}}
    seen = set()
    while True:
        while pos < len(s) and s[pos] in " \t,，、":
            pos += 1
        if pos >= len(s):
            break
        m = _PICK.match(s, pos)
        if not m:
            raise PickError(f"cannot read the reply from {raw[pos:pos + 12]!r} on "
                            '(write it like: D1=3 D2="自己寫的" D5=+)')
        kind, num, quoted, plus, idx = m.groups()
        kind = kind.upper()
        if kind == "H" and num:
            raise PickError("H takes no number (H=2 picks the second headline)")
        if kind == "D" and (not num or int(num) < 1):
            raise PickError("a day is D1, D2, …")
        key = "H" if kind == "H" else int(num)
        if key in seen:
            raise PickError(f"{kind}{num} is picked twice")
        seen.add(key)
        if quoted is not None:
            val = raw[m.start(3):m.end(3)].strip()
            if not val:
                raise PickError(f"{kind}{num}: the quoted title is empty")
        elif plus:
            val = "+"
        else:
            val = int(idx)
            if val < 1:
                raise PickError(f"{kind}{num}: titles are numbered from 1")
        if key == "H":
            out["H"] = val
        else:
            out["days"][key] = val
        pos = m.end()
    if out["H"] is None and not out["days"]:
        raise PickError("the reply picks nothing (write it like: D1=3 D2=1)")
    return out


def apply(itinerary, brief, picks):
    """Write the picks; all-or-nothing. Returns {"days": [n asking for more], "headline": bool}."""
    days = (itinerary or {}).get("days") or []
    writes, more = [], {"days": [], "headline": False}
    for n, v in sorted(picks["days"].items()):
        if n > len(days):
            raise PickError(f"D{n}: the trip has {len(days)} days")
        d = days[n - 1]
        if v == "+":
            more["days"].append(n)
        elif isinstance(v, str):
            if len(v) > THEME_MAX:
                raise PickError(f"D{n}: your title is {len(v)} characters (max {THEME_MAX}, punctuation counts)")
            if ai_tone_failures(v):
                raise PickError(f"D{n}: your title uses a mark the reader does not allow (an em dash, a "
                                f"stock phrase …); please rewrite it")
            writes.append(("own", d, v))
        else:
            cands = d.get("theme_candidates") or []
            if v > len(cands):
                raise PickError(f"D{n}={v}: that day has {len(cands)} titles")
            writes.append(("pick", d, cands[display_order(cands)[v - 1]]))
    h = picks.get("H")
    if h == "+":
        more["headline"] = True
    elif isinstance(h, str):
        if len(_PUNCT.sub("", h)) > HEADLINE_MAX:
            raise PickError(f"H: your headline is over {HEADLINE_MAX} characters (punctuation not counted)")
        if ai_tone_failures(h):
            raise PickError("H: your headline uses a mark the reader does not allow (an em dash, a "
                            "stock phrase …); please rewrite it")
        writes.append(("head", brief, {"text": h, "user_written": True}))
    elif isinstance(h, int):
        cands = (brief or {}).get("headline_candidates") or []
        if h > len(cands):
            raise PickError(f"H={h}: there are {len(cands)} headlines")
        writes.append(("head", brief, {"text": cands[h - 1]["text"]}))
    final = [(d.get("theme") or "").strip() for d in days]
    changed = set()
    for kind, target, v in writes:
        if kind != "head":
            k = next(i for i, d in enumerate(days) if d is target)
            final[k] = v if kind == "own" else v["text"]
            changed.add(k)
    for k in sorted(changed, reverse=True):
        other = [j for j, t in enumerate(final) if t == final[k] and j != k]
        if other:
            raise PickError(f"D{k + 1}: same title as D{other[0] + 1}; each day needs its own")
    for n in more["days"]:
        days[n - 1].pop("theme_picked", None)           # asked for more: the day is open again
    for kind, target, v in writes:
        if kind != "head":
            target["theme_picked"] = True
        if kind == "head":
            target["headline"] = v
        elif kind == "own":
            target["theme"], target["theme_user_written"] = v, True
            target.pop("theme_refs", None)
        else:
            target["theme"], target["theme_refs"] = v["text"], list(v.get("refs") or [])
            target.pop("theme_user_written", None)
    return more


def main(argv):
    import argparse
    import pathlib
    import sys

    import yaml

    from scripts.paths import artifact_path

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("trip_dir")
    ap.add_argument("reply")
    args = ap.parse_args(argv)
    trip = pathlib.Path(args.trip_dir)
    ip, bp = artifact_path(trip, "itinerary.yaml"), artifact_path(trip, "trip-brief.yaml")
    itin = yaml.safe_load(ip.read_text(encoding="utf-8"))
    brief = yaml.safe_load(bp.read_text(encoding="utf-8"))
    import copy
    i0, b0 = copy.deepcopy(itin), copy.deepcopy(brief)
    try:
        more = apply(itin, brief, parse(args.reply))
    except PickError as exc:
        print(f"title picks: {exc} — nothing written", file=sys.stderr)
        return 2
    # an artifact the reply did not change keeps its bytes and mtime (rule 11's mtime
    # fallback would otherwise call its dependants stale)
    if itin != i0:
        ip.write_text(yaml.safe_dump(itin, allow_unicode=True, sort_keys=False), encoding="utf-8")
    if brief != b0:
        bp.write_text(yaml.safe_dump(brief, allow_unicode=True, sort_keys=False), encoding="utf-8")
    asks = [f"D{n}" for n in more["days"]] + (["H"] if more["headline"] else [])
    print("title picks: written" + (f"\nmore: {' '.join(asks)}" if asks else ""))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
