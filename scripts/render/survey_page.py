"""The survey's list page (v2.1.0 §10): every verified place as the reader's own stop card
(the user's pick P1 on the design board), grouped like `tripwork.py table`'s presets, the
score in the column where a trip shows the time. Reads verified-pois and the brief only --
no itinerary -- and needs no script: a card opens by its in-page anchor, as in the reader."""
import html as _html
import re

from scripts import survey_table as st
from scripts.render.reader.assets import font_faces, icon
from scripts.render.reader.day import address, card, sources
from scripts.render.reader.page import _FONT_EXTRA, _context, licence_notice
from scripts.render.reader.text import esc
from scripts.render.reader.theme import CSS

# (heading, which rows, card slot): the table's presets, then the places neither shows
GROUPS = (("吃的", "吃的", "meal"), ("景點", "景點", "visit"), ("住的", "住的", "lodging"), ("其他", "其他", "visit"))

PAGE_CSS = (".sv{max-width:480px;margin:0 auto;padding:0 0 40px}.sh1{padding:20px 26px 8px}"
            ".sh1 h1{font:700 26px var(--f-round);margin:2px 0 0}.sh1 .k{margin:0;color:var(--mut);font-size:13px}"
            ".sv .list{margin:0 26px}"
            ".sg{display:flex;align-items:baseline;gap:8px;margin:18px 26px 8px;font:700 17px var(--f-round)}"
            ".sg span{color:var(--mut);font-size:13px}")


def _rows(pois, group):
    if group in ("吃的", "景點"):
        return st.rows_for(pois, group)
    if group == "住的":
        return [p for p in st.rows_for(pois, None) if st.CATEGORY_GROUP.get(str(p.get("category"))) == "住的"]
    shown = {id(p) for g in ("吃的", "景點", "住的") for p in _rows(pois, g)}
    return [p for p in st.rows_for(pois, None) if id(p) not in shown]


def _place(ctx, n, p, slot, dates, calendar, lang):
    tid = f"p{n}"
    r = p.get("rating") if isinstance(p.get("rating"), dict) else {}
    score, count = (str(r["score"]), f'{r["count"]} 則' if r.get("count") is not None else "") \
        if r.get("score") is not None else ("—", "無評分")
    hours, closed = st.hours_text(p.get("hours")), st.closed_text(p, dates, calendar)
    one = "・".join(x for x in (hours, closed) if x)
    head = (f'<span class="t"><b>{esc(score)}</b><small>{esc(count)}</small></span>'
            f'<span class="nm"><span class="n">{esc(p.get("name_display") or p.get("name_local") or "")}</span>'
            f'<span class="one">{esc(one)}</span></span>')
    rows = []
    if p.get("intro"):
        rows.append(("介紹", esc(p["intro"])))
    if hours:
        rows.append(("營業", esc(hours)))
    if closed:
        rows.append(("公休", esc(closed)))
    if r.get("score") is not None:
        warn = st.FIELDS["評分警訊"](p, {})
        rows.append(("評分", esc(f'{r["score"]}（{r.get("platform") or ""}，{count}'
                                  + (f"・{warn}" if warn else "") + "）")))
    sheet = ""
    if p.get("address_local"):
        dd, sheet = address(tid, p, lang)
        rows.append(("地址", dd))
    src = sources(p, tid)
    if src:
        rows.append(("來源", src))
    return card(ctx, tid, slot, p.get("id"), head, rows, sheet, p)


def render(pois, brief, calendar=None):
    brief = brief or {}
    ctx = _context({"days": []}, {p.get("id"): p for p in pois if isinstance(p, dict)}, brief, None, None, None)
    dates = st._dates(brief)
    lang = esc(((brief.get("destination") or {}).get("local_lang")) or "")
    body, n = [], 0
    for heading, group, slot in GROUPS:
        rows = _rows(pois, group)
        if not rows:
            continue
        cards = []
        for p in rows:
            n += 1
            cards.append(_place(ctx, n, p, slot, dates, calendar, lang))
        body.append(f'<h2 class="sg">{heading}<span>{len(rows)}</span></h2><div class="list">{"".join(cards)}</div>')
    city = (brief.get("destination") or {}).get("city") or ""
    main = (f'<main class="sv"><header class="sh1"><p class="k">只蒐集・{esc(city)}</p>'
            f'<h1>{esc(brief.get("short_name") or "")} 清單</h1></header>{"".join(body)}</main>')
    page = (f'<input autocomplete="off" type="checkbox" id="theme">{main}'
            f'<label class="bubble" for="theme" aria-label="切換深色／淺色">'
            f'<span class="moon">{icon("moon")}</span><span class="sun">{icon("sun")}</span></label>')
    text = _html.unescape(re.sub(r"<[^>]+>", "", page)) + _FONT_EXTRA
    css = font_faces("".join(sorted(set(text)))) + CSS + PAGE_CSS
    return ('<!doctype html>' + licence_notice() + '<html lang="zh-Hant"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{esc(brief.get("short_name") or "")} 清單</title><style>{css}</style></head>'
            f'<body>{page}</body></html>')
