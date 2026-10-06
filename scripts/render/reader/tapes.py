"""Today's tape (v2.2): during the trip the home calendar's stamp for today wears a strip of
paper tape, a different one each day.

The tape is picked here, when the page is rendered: a pattern cycle and a colour cycle, each
shuffled once per trip (seeded by the trip's title and first day), so a day shows the same
tape on every device and every reload, every pattern has a day before one comes back, and a
pairing does not come back for 18 days. A tape never takes the colour of the stamp it sits on.
Its tilt and its torn ends come from the same seed, so a pattern that comes back still differs.

Each home stamp carries its day's tape as classes (tp-<pattern> tc-<colour> tt<tear>) and its
tilt (--tr); PUBLISH_JS marks today's stamp .today and css() paints only that one. The colours
are the reader's own tokens, so the dark theme swaps them with the rest of the page."""
import hashlib
import random
from collections import namedtuple

Tape = namedtuple("Tape", "pattern colour tilt tear")

PATTERNS = {"S": "條紋", "D": "圓點", "G": "格紋", "X": "斜條紋", "L": "細格線", "W": "波浪邊",
            "R": "菱格", "Q": "點點＋條紋", "E": "邊線"}
COLOURS = {"sun": "紅", "sat": "藍", "r2": "綠", "r4": "芥末", "plan": "橘", "activity": "紫"}
AVOID = {"r1": "sat", "r2": "r2", "r3": "sun", "r4": "r4"}      # a stamp's area colour -> the tape colour too close to it
TILT = (-44.0, -32.0)
TEARS = 6


def day_tapes(title, first_day, stamp_classes):
    """One Tape per day; stamp_classes are the days' area classes (r0..r4)."""
    seed = int(hashlib.sha256(f"tripwork-tape:{title}|{first_day.isoformat()}".encode()).hexdigest()[:12], 16)
    r = random.Random(seed)
    pats, cols = list(PATTERNS), list(COLOURS)
    r.shuffle(pats)
    r.shuffle(cols)
    out = []
    for i, cls in enumerate(stamp_classes):
        q = random.Random(seed + 7919 * (i + 1))
        j = i
        while cols[j % len(cols)] == AVOID.get(cls):
            j += 1
        out.append(Tape(pats[i % len(pats)], cols[j % len(cols)], round(q.uniform(*TILT), 1), q.randrange(TEARS)))
    return out


def outline(length, width, seed):
    """The strip's outline, its short ends torn: an SVG path in a length x width box."""
    r = random.Random(seed)
    right = [(length - r.uniform(0, width * .18), width * k / 6) for k in range(1, 6)]
    left = [(r.uniform(0, width * .18), width * (1 - k / 6)) for k in range(1, 6)]
    pts = [(0, 0), (length, 0)] + right + [(length, width), (0, width)] + left
    return "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in pts) + " Z"


def _mask(k):
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 22' preserveAspectRatio='none'>"
           f"<path d='{outline(64, 22, 19 + 101 * k)}'/></svg>")
    return "url(\"data:image/svg+xml," + svg.replace("<", "%3C").replace(">", "%3E") + "\")"


def _ink(a):
    # --tk scales every ink amount (1 by default; the dark theme's value is set in css())
    return f"color-mix(in srgb,var(--tc) calc({a}% * var(--tk,1)),transparent)"


_DOT = "var(--tdot)"                                          # the dots' paper colour (css())
_U = lambda k: f"calc(var(--u) * {k})"                       # noqa: E731  (a length in tape units)

# each pattern's paper; --u is 1px on the phone and grows with the desktop stamp
_PAPER = {
    "S": f"repeating-linear-gradient(0deg,{_ink(42)} 0 {_U(1.4)},{_ink(22)} {_U(1.4)} {_U(2.8)})",
    "D": f"radial-gradient(circle,{_DOT} {_U(1.12)},transparent {_U(1.36)}) 0 0/{_U(4)} {_U(4)},{_ink(42)}",
    "G": (f"linear-gradient(90deg,{_ink(30)} 50%,transparent 0) 0 0/{_U(4)} {_U(4)},"
          f"linear-gradient(0deg,{_ink(30)} 50%,transparent 0) 0 0/{_U(4)} {_U(4)},{_ink(12)}"),
    "X": f"repeating-linear-gradient(45deg,{_ink(45)} 0 {_U(1.4)},{_ink(16)} {_U(1.4)} {_U(3.08)})",
    "L": (f"repeating-linear-gradient(0deg,{_ink(55)} 0 {_U(.5)},transparent {_U(.5)} {_U(3)}),"
          f"repeating-linear-gradient(90deg,{_ink(55)} 0 {_U(.5)},transparent {_U(.5)} {_U(3)}),{_ink(14)}"),
    "W": f"radial-gradient(circle at 50% 0,{_ink(50)} {_U(1.6)},transparent {_U(1.75)}) 0 0/{_U(3.4)} {_U(3.4)},{_ink(20)}",
    "R": f"conic-gradient(from 45deg,{_ink(40)} 25%,{_ink(16)} 0 50%,{_ink(40)} 0 75%,{_ink(16)} 0) 0 0/{_U(4)} {_U(4)}",
    "Q": (f"radial-gradient(circle,{_DOT} {_U(.88)},transparent {_U(1.12)}) 0 0/{_U(4)} {_U(4)},"
          f"repeating-linear-gradient(90deg,{_ink(42)} 0 {_U(2)},{_ink(26)} {_U(2)} {_U(4)})"),
    "E": f"linear-gradient(0deg,{_ink(55)} 0 18%,{_ink(14)} 18% 82%,{_ink(55)} 82%)",
}
# the strip: 32 x 11 at 13,13 from the stamp's centre on the phone; on the desktop it scales
# with the stamp (--s, theme.py), 70 x 23 at 32,32 for the 65 px stamp
PAINT = "background:var(--tape);-webkit-mask:var(--tm) center/100% 100% no-repeat;mask:var(--tm) center/100% 100% no-repeat"


def css():
    rules = [".page.home .stamp,.tape-swatch{--tdot:color-mix(in srgb,var(--card) 85%,transparent)}",
             ".page.home .stamp{--u:1px;--tl:32px;--tw:11px;--to:13px}",
             # dark: half-clear ink on a dark page loses its colour -- deeper ink, light dots (the user's pick D3)
             (":root:has(#theme:checked) :is(.page.home .stamp,.tape-swatch){--tk:1.7;"
              "--tdot:color-mix(in srgb,var(--ink) 60%,transparent)}"),
             ".page.home .stamp.today{position:relative}",
             (".page.home .stamp.today::before{content:'';position:absolute;left:calc(50% + var(--to) - var(--tl) / 2);"
              "top:calc(50% + var(--to) - var(--tw) / 2);width:var(--tl);height:var(--tw);rotate:var(--tr,-38deg);"
              f"pointer-events:none;z-index:2;{PAINT}}}"),
             (".tape-swatch{display:block;width:var(--tl);height:var(--tw);" + PAINT + "}"),
             ("@media (min-width:1024px){.page.home .hcal .stamp{--u:calc(var(--s) * 2.2 / 65);--tl:calc(var(--s) * 70 / 65);"
              "--tw:calc(var(--s) * 23 / 65);--to:calc(var(--s) * 32 / 65)}}")]
    rules += [f".tp-{p}{{--tape:{v}}}" for p, v in _PAPER.items()]
    rules += [f".tc-{c}{{--tc:var(--{c})}}" for c in COLOURS]
    rules += [f".tt{k}{{--tm:{_mask(k)}}}" for k in range(TEARS)]
    return "".join(rules)
