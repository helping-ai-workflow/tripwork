"""Assemble the single self-contained reader page (spec §6).

Every interaction works with no script (radio / checkbox / <details> / in-page anchors
and :target / :has()): LINE and the iPhone Files app preview the page with no
JavaScript. The one script (centre.py) only glides the chosen stop to centre on the
desktop. Pages switch on one `pg` radio group; a day's stops, chips and 來源 are
anchors, so the URL fragment is the one open stop (v1.1 §8.1); the theme is a checkbox
driving the toggle bubble.
"""
import html as _html
import re
from types import SimpleNamespace

from scripts.render.heading import trip_title
from scripts.render.reader import calendar
from scripts.render.reader.assets import ICON_DIR, _FONTS, font_faces, icon
from scripts.render.reader.centre import CENTRE_JS
from scripts.render.reader.publish import PUBLISH_JS
from scripts.render.reader.day import day_page
from scripts.render.reader.home import advisory_screen, checklist_screen, home, lodging_screen
from scripts.render.reader.maps import OSM_COPYRIGHT, nav_css as map_nav_css
from scripts.render.reader.text import esc, to_date
from scripts.render.reader.theme import CSS

def licence_notice():
    """v1.1 TW-D3 (the user's pick A): the notices live in the file, not on screen. OFL
    FAQ 1.10 / 1.12: a font embedded in a document needs no licence text; ISC (Lucide)
    wants its copyright and permission notice in every copy. Both are read from the
    licence files the plugin ships, so the comment cannot drift from them. Photos and
    map tiles are credited next to each."""
    ofl = (_FONTS / "OFL.txt").read_text(encoding="utf-8")
    fonts = ofl.split("\n-----", 1)[0].split("\n", 1)[1].strip()      # the header, minus its title
    # the header points at the licence body below it in OFL.txt; the comment carries no body
    fonts = fonts.replace("This license is copied below, and is also available with a FAQ at:",
                          "The licence and its FAQ:")
    isc = (ICON_DIR / "LICENSE").read_text(encoding="utf-8").strip()
    note = (f"Fonts embedded in this page (subset to the characters it uses):\n{fonts}\n\n"
            f"Icons: Lucide (https://lucide.dev)\n{isc}\n\n"
            f"Photos and map tiles: credited next to each; map data {OSM_COPYRIGHT}\n")
    if "--" in note:
        raise ValueError("a shipped licence text would end the page's notice comment early")
    return f"<!--\n{note}-->"
_FONT_EXTRA = "0123456789:：–—・、。，（）()/→←‹›↺＋·約分小時晚間項禁止限制須知"


def _context(itinerary, poi_map, brief, accommodations, advisory, legs, maps=None, cost=None):
    days = [d for d in itinerary.get("days") or [] if isinstance(d, dict)]
    dates = []
    for d in days:
        try:
            dates.append(to_date(d.get("date")))
        except (TypeError, ValueError):
            dates.append(dates[-1] if dates else to_date("2000-01-01"))
    brief = brief or {}
    ctx = SimpleNamespace(
        itinerary=itinerary, days=days, dates=dates, poi_map=poi_map or {}, brief=brief,
        accommodations=accommodations or {"stops": []}, legs=legs or {"legs": []},
        advisory_items=[a for a in (advisory or {}).get("items") or [] if isinstance(a, dict)],
        checklist=list(itinerary.get("checklist") or []),
        local_lang=((brief.get("destination") or {}).get("local_lang")),
        maps=maps if isinstance(maps, dict) else None, map_images={},
        cost=cost if isinstance(cost, dict) else None)
    ctx.areas = calendar.day_areas({"days": days}, ctx.accommodations)
    return ctx


def _nav_css(pages):
    rules = [".page{display:none}"]
    rules += [f'body:has(#pg-{p}:checked) .page[data-pg="{p}"]{{display:block}}' for p in pages]
    # H1c2: a day opened with its calendar put away (theme.py) is the same page
    rules += [f'body:has(#pg-{p}f:checked) .page[data-pg="{p}"]{{display:block}}' for p in pages if p.startswith("d")]
    return "".join(rules)


def render_reader(itinerary, poi_map, *, brief=None, accommodations=None, advisory=None, legs=None,
                  maps=None, cost=None, build="check"):
    if build not in ("check", "publish"):
        raise ValueError(f"unknown build: {build!r}")
    ctx = _context(itinerary or {}, poi_map, brief, accommodations, advisory, legs, maps, cost)
    pages = ["home", "lodging", "advisory", "checklist"] + [f"d{i}" for i in range(1, len(ctx.days) + 1)]
    # each day has a second radio, pg-dNf: the day opened with its small calendar put away --
    # the phone's stepper takes it once the calendar is mostly away (H1c2, theme.py), so a
    # put-away calendar stays away from day to day with no script (LINE / Files run none)
    radios = "".join(f'<input autocomplete="off" type="radio" class="pgr" name="pg" id="pg-{p}"{" checked" if p == "home" else ""}>'
                     + (f'<input autocomplete="off" type="radio" class="pgr pgf" name="pg" id="pg-{p}f">' if p.startswith("d") else "")
                     for p in pages)
    body = (f'<input autocomplete="off" type="checkbox" id="theme">{radios}'
            f'{home(ctx)}{lodging_screen(ctx)}{advisory_screen(ctx)}{checklist_screen(ctx)}'
            f'{"".join(day_page(ctx, i) for i in range(1, len(ctx.days) + 1))}'
            f'<label class="bubble" for="theme" aria-label="切換深色／淺色">'
            f'<span class="moon">{icon("moon")}</span><span class="sun">{icon("sun")}</span></label>')
    text = _html.unescape(re.sub(r"<[^>]+>", "", body)) + _FONT_EXTRA
    title = trip_title(ctx.brief, itinerary)
    maps_css = "".join(map_nav_css(ctx, i, d) for i, d in enumerate(ctx.days, start=1))
    images = "".join(f'.{cls}{{background-image:url("{data}")}}' for data, cls in ctx.map_images.items())
    css = font_faces("".join(sorted(set(text)))) + CSS + _nav_css(pages) + maps_css + images
    return ('<!doctype html>' + licence_notice() + '<html lang="zh-Hant"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{esc(title)}</title><style>{css}</style></head><body>{body}'
            f'<script>{CENTRE_JS}</script>'
            + (f'<script>{PUBLISH_JS}</script>' if build == "publish" else "") + '</body></html>')
