"""The 交通 and 餐廳 sub-screens (reservations.yaml): what is booked, by date, with its
status pill; the details (the number masked) open with no script, like the checklist.
Listing and wording come from scripts/reservation.py, which the md page uses too."""
from scripts import reservation as R
from scripts.render.reader.assets import MODE_ICON, icon
from scripts.render.reader.text import esc, md_wd, to_date

EMPTY = {"move": "這趟沒有記下長途交通的訂位。", "meal": "這趟沒有記下餐廳。"}
UNIT = {"move": "段", "meal": "餐"}


def pill(status):
    return f'<span class="bk bk-{esc(status)}">{esc(R.LABEL.get(status, ""))}</span>'


def rows(ctx, kind):
    return R.reservation_rows({"days": ctx.days}, ctx.legs, ctx.reservations, ctx.poi_map, kind)


def tile_note(ctx, kind):
    """'4 段' / '3 餐・1 待訂' -- the tile's small line (markup: the 待訂 part is coloured)."""
    rs = rows(ctx, kind)
    todo = sum(1 for e in rs if e["status"] == "todo")
    return f"{len(rs)} {UNIT[kind]}" + (f'<i class="todo">・{todo} 待訂</i>' if todo else "")


def _entry(e, kind):
    mode = e["row"].get("mode")
    ic = icon(MODE_ICON.get(mode, "train-front")) if kind == "move" else icon("utensils")
    sub = e["sub"] + ("・建議，可換別家" if e["status"] == "self" else "")
    head = (f'<span class="bh"><span class="bt">{esc(e["time"])}</span>{ic}'
            f'<b class="bn">{esc(e["title"])}</b>{pill(e["status"])}</span>'
            f'<small class="bs">{esc(sub)}</small>')
    if not e["details"]:
        return f'<div class="ci bkrow">{head}</div>'
    dl = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in e["details"])
    return (f'<details class="ci bkrow"><summary>{head}<span class="cv"></span></summary>'
            f'<dl class="bd">{dl}</dl></details>')


def screen(ctx, kind):
    from scripts.render.reader.home import _sub
    out, last = [], None
    for e in rows(ctx, kind):
        if e["date"] != last:
            out.append(f'<h3 class="bkd">{esc(md_wd(to_date(e["date"])))}</h3>')
            last = e["date"]
        out.append(_entry(e, kind))
    pg, title = ("transport", "交通") if kind == "move" else ("meals", "餐廳")
    return _sub(pg, title, "".join(out) or f'<p class="empty">{EMPTY[kind]}</p>')


def transport_screen(ctx):
    return screen(ctx, "move")


def meals_screen(ctx):
    return screen(ctx, "meal")


# the approved look (design board): the reader's own tokens only. Shared rules here; the
# phone's 3 + 2 tile grid sits in the phone media block (the desktop keeps one per row).
CSS = """
.bkd{font:700 15px var(--f-round);margin:14px 2px 6px}.bkd:first-child,.ft+.bkd{margin-top:4px}
.bkrow summary,div.ci.bkrow{gap:2px}div.ci.bkrow{padding:10px 34px 10px 12px}
.bh{display:flex;align-items:center;gap:6px;min-width:0}
.bt{flex:none;width:42px;font:700 14px var(--f-round);font-variant-numeric:tabular-nums;color:var(--mut)}
.bh .lu{position:relative;top:1px;width:16px;height:16px;color:var(--mut)}
.bn{flex:1 1 auto;min-width:0;font:700 15px var(--f-round);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bs{display:block;padding-left:48px;font-size:13px;color:var(--mut)}
.bk{flex:none;font:700 12px var(--f-round);line-height:18px;padding:0 8px;border-radius:999px;border:1.5px solid currentColor}
/* a CJK name's ink sits below its line box's middle: the pill and the icon drop 1 px to its ink
   (measured: 1.5 px high in WebKit, 1.2 in Chromium; the user's OK on the board) */
.bh .bk{position:relative;top:1px}
.bk-booked{color:var(--card);background:var(--ink);border-color:var(--ink)}.bk-none{color:var(--mut);border-color:var(--rule)}
.bk-todo{color:var(--plan)}.bk-self{color:var(--opt)}
.bd{display:grid;grid-template-columns:auto minmax(0,1fr);gap:4px 12px;margin:2px 12px 14px 60px;font-size:13.5px;line-height:1.6}
.bd dt{font:700 12px/1.8 var(--f-round);color:var(--mut)}.bd dd{margin:0;overflow-wrap:anywhere}
.tile small .todo{font-style:normal;color:var(--plan);font-weight:700}
.stop.sug{--k:var(--opt)}
.sgt{display:inline-block;margin-right:6px;font:700 11px var(--f-round);line-height:16px;padding:0 6px;border-radius:999px;color:var(--opt);border:1.5px solid var(--opt);vertical-align:1px}
.lbk{display:flex;align-items:center;gap:6px;margin-top:4px;font-size:12.5px;color:var(--mut)}
.lbk .bk{font-size:11px;line-height:16px;padding:0 6px}
@media (max-width:1023px){.tiles{grid-template-columns:repeat(6,1fr)}.tiles .tile{grid-column:span 2}
/* the user's pick C: the phone home stays one screen. 住宿 / 交通 / 餐廳 (used on the road) keep the
   tall tile; 出入境規定 / 行前清單 take the desktop's bar (45 px), and when the screen is still short
   the 旅程與費用 card gives up height first and scrolls inside itself -- its text never draws
   outside the card (the user's call; a floor for the stay list is left to a later version) */
.tiles .tile:nth-child(n+4){grid-column:span 3;flex-direction:row;justify-content:center;gap:8px;padding:12px}
.tiles .tile:nth-child(n+4) small{margin-left:4px}
.page.home .hwrap{height:100%;min-height:0}.page.home .ttl,.page.home .hcal,.page.home .tiles{flex:none}
.page.home .trip{flex:0 1 auto;min-height:0;overflow-y:auto}}
"""
