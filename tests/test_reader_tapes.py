"""v2.2 today's tape (scripts/render/reader/tapes.py): the home calendar's stamp for today wears
a strip of paper tape, a different one each day. The pick is made when the page is rendered --
a seeded shuffle per trip -- so a day shows the same tape on every device and every reload,
and the page script only says which day is today."""
import datetime
import re

import pytest

from scripts.render.reader import render_reader, tapes
from tests import reader_fixture as R

FIRST = datetime.date(2026, 10, 12)


def _classes(n, cls="r1"):
    return [cls] * n


def test_the_same_trip_gets_the_same_tapes():
    a = tapes.day_tapes("示意之旅", FIRST, _classes(12))
    assert a == tapes.day_tapes("示意之旅", FIRST, _classes(12))
    assert a != tapes.day_tapes("另一趟", FIRST, _classes(12))
    assert a != tapes.day_tapes("示意之旅", FIRST + datetime.timedelta(days=1), _classes(12))


def test_every_pattern_has_a_day_before_one_comes_back():
    days = tapes.day_tapes("示意之旅", FIRST, _classes(2 * len(tapes.PATTERNS)))
    n = len(tapes.PATTERNS)
    assert sorted(d.pattern for d in days[:n]) == sorted(tapes.PATTERNS)
    assert [d.pattern for d in days[n:]] == [d.pattern for d in days[:n]]


def test_no_pairing_comes_back_within_the_two_cycles():
    n = len(tapes.PATTERNS) * len(tapes.COLOURS) // 3          # 9 and 6: 18 days
    days = tapes.day_tapes("示意之旅", FIRST, _classes(n, "r0"))
    assert len({(d.pattern, d.colour) for d in days}) == n


@pytest.mark.parametrize("cls", ["r1", "r2", "r3", "r4"])
def test_a_tape_never_takes_its_stamps_colour(cls):
    days = tapes.day_tapes("示意之旅", FIRST, _classes(30, cls))
    assert all(d.colour != tapes.AVOID[cls] for d in days)
    assert len({d.colour for d in days}) == len(tapes.COLOURS) - 1     # the other five all get a turn


def test_tilt_and_tear_vary_by_day():
    days = tapes.day_tapes("示意之旅", FIRST, _classes(12))
    assert all(tapes.TILT[0] <= d.tilt <= tapes.TILT[1] for d in days)
    assert len({d.tilt for d in days}) > 6
    assert len({d.tear for d in days}) > 1


def test_every_token_a_tape_uses_is_a_reader_colour():
    from scripts.render.reader.theme import WARM_DARK, WARM_LIGHT
    for tok in list(tapes.COLOURS) + ["card"]:
        assert f"--{tok}:" in WARM_LIGHT and f"--{tok}:" in WARM_DARK, tok


def test_the_home_stamps_carry_their_days_tape():
    """Each home stamp names its day's tape (pattern, colour, tear) and its tilt; the day
    pages' mini calendars carry none."""
    html = render_reader(R.itinerary(), R.poi_map(), **R.reader_kwargs())
    days_at = html.index('<section class="page day"')
    stamps = re.findall(r'<label class="stamp ([^"]*tp-[^"]*)" for="pg-d(\d+)" style="([^"]*)"', html[:days_at])
    assert [int(i) for _, i, _ in stamps] == list(range(1, len(R.itinerary()["days"]) + 1))
    from scripts.render.reader import page as P
    ctx = P._context(R.itinerary(), R.poi_map(), *[R.reader_kwargs().get(k) for k in
                     ("brief", "accommodations", "advisory", "legs", "maps", "cost")])
    from scripts.render.reader.home import trip_title
    want = tapes.day_tapes(trip_title(ctx.brief, ctx.itinerary), ctx.dates[0], [c for _, c in ctx.areas])
    for (cls, i, style), t in zip(stamps, want):
        assert {f"tp-{t.pattern}", f"tc-{t.colour}", f"tt{t.tear}"} <= set(cls.split()), (i, cls)
        assert f"--tr:{t.tilt:.1f}deg" in style
    assert "tp-" not in html[days_at:]


def test_the_tape_css_paints_today_only():
    css = tapes.css()
    assert ".page.home .stamp.today::before" in css
    for p in tapes.PATTERNS:
        assert f".tp-{p}{{" in css
    for c in tapes.COLOURS:
        assert f".tc-{c}{{--tc:var(--{c})}}" in css


def test_the_dark_theme_deepens_the_ink_and_lightens_the_dots():
    css = tapes.css()
    assert ":root:has(#theme:checked) :is(.page.home .stamp,.tape-swatch){--tk:1.7;" in css
    assert "--tdot:color-mix(in srgb,var(--ink) 60%,transparent)" in css
    assert "calc(42% * var(--tk,1))" in tapes._PAPER["S"]                # every ink amount follows --tk
