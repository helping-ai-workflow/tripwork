"""The mobile home (N1) and its three sub-screens (spec §6.1)."""
import datetime

from scripts.checklist import KINDS
from scripts.render.centroid import centroid_items, centroid_note
from scripts.render.gmaps_links import maps_url
from scripts.render.heading import dates_line, trip_title
from scripts.render.reader import month_calendar
from scripts.render.reader.assets import icon
from scripts.render.reader.text import esc, md, md_wd

RISK = {"banned": ("禁止", "risk-banned"), "restricted": ("限制", "risk-restricted"),
        "info": ("須知", "risk-info")}


def _name(p):
    return (p or {}).get("name_zh") or (p or {}).get("name_display") or (p or {}).get("name_local") or ""


def navb(p, slot_icon="bed-double"):
    if not p:
        return ""
    return (f'<a class="navb" href="{esc(maps_url(p))}" target="_blank" rel="noopener">'
            f'{icon(slot_icon)}導航</a>')


def lodging_runs(ctx):
    """[(poi, first night date, nights, colour class, area)] in trip order."""
    runs = []
    for (d, day), (area, cls) in zip(zip(ctx.dates, ctx.days), ctx.areas):
        lid = day.get("lodging")
        if not lid:
            continue
        if runs and runs[-1]["id"] == lid:
            runs[-1]["n"] += 1
        else:
            runs.append({"id": lid, "d": d, "n": 1, "cls": cls, "area": area})
    return runs


SYMBOL = {"JPY": "¥", "TWD": "NT$", "USD": "US$", "EUR": "€", "KRW": "₩", "CNY": "CN¥", "HKD": "HK$"}


def _money(cur, n):
    try:
        v = round(float(n))
    except (TypeError, ValueError):
        return ""
    return f"{SYMBOL.get(cur, (cur or '') + ' ')}{v:,}"


def trip_card(ctx):
    """v1.1 topic 6 (picks C2 + S): each stay in its stamp colour with its nights, lodging
    and that stay's cost (cost line items name their poi_id), then transport and the total;
    many stays scroll inside the fixed card (theme.py). No stay, no card; no cost.yaml,
    the route alone."""
    runs = lodging_runs(ctx)
    if not runs:
        return ""
    cost = ctx.cost or {}
    cur = cost.get("currency")
    # one line item per stay, in trip order: a hotel stayed at twice (函館 -> 大沼 -> 函館)
    # has two items, and each stay takes its own (review I1)
    by_poi = {}
    for li in cost.get("line_items") or []:
        if isinstance(li, dict) and li.get("category") == "lodging" and li.get("poi_id"):
            by_poi.setdefault(li["poi_id"], []).append(li.get("amount"))
    rows = []
    for r in runs:
        queue = by_poi.get(r["id"]) or []
        amt = f'<em>{_money(cur, queue.pop(0))}</em>' if queue else ""
        rows.append(f'<li class="{r["cls"]}"><b>{esc(r["area"])}</b>{amt}'
                    f'<span>{r["n"]} 晚・{esc(_name(ctx.poi_map.get(r["id"])))}</span></li>')
    if ctx.areas and ctx.areas[-1][0] == "返程":
        rows.append('<li class="r0"><b>返程</b></li>')
    foot = ""
    if cost:
        cat = cost.get("by_category") or {}
        use_pass = (cost.get("pass_break_even") or {}).get("use_pass")
        if "transport" in cat:
            foot += (f'<p class="tt"><span>交通{"（含周遊券）" if use_pass else ""}</span>'
                     f'<em>{_money(cur, cat["transport"])}</em></p>')
        foot += f'<p class="tt sum"><span>合計</span><em>{_money(cur, cost.get("total"))}</em></p>'
        foot += f'<p class="tn">估算，{"餐飲等以每日零用計" if "incidental" in cat else "不含餐飲、門票"}</p>'
    return (f'<section class="trip"><h3>{"旅程與費用" if cost else "旅程"}</h3>'
            f'<ol>{"".join(rows)}</ol>{foot}</section>')


def _dates(ctx):
    """The desktop breaks the dates line at its 「・」 (v1.1 topic 6); the phone keeps one line."""
    a, sep, b = dates_line(ctx.brief, ctx.itinerary).partition("・")
    if not sep:
        return esc(a)
    return f'<span class="dl">{esc(a)}</span><span class="dsep">・</span><span class="dl">{esc(b)}</span>'


def home(ctx):
    title = trip_title(ctx.brief, ctx.itinerary)
    tiles = [("pg-lodging", "bed-double", "住宿", f"{len({r['id'] for r in lodging_runs(ctx)})} 間"),
             ("pg-advisory", "stamp", "入境規定", f"{len(ctx.advisory_items)} 項"),
             ("pg-checklist", "list-checks", "行前清單", f"{len(checklist_items(ctx))} 項")]
    # v1.1 topic 6: the month card is its own panel -- the desktop's big calendar, zoomed
    # x1.9, each day's theme on its stamp ring; the phone keeps its order (theme.py)
    rings = [d.get("theme") or d.get("label") or "" for d in ctx.days]
    tiles_html = "".join(f'<label class="tile" for="{pg}">{icon(ic)}<b>{t}</b><small>{n}</small></label>'
                         for pg, ic, t, n in tiles)
    return (f'<section class="page home" data-pg="home"><div class="hwrap"><div class="hside">'
            f'<div class="ttl"><h1 class="headline">{esc(title)}</h1>'
            f'<p class="dates">{_dates(ctx)}</p></div>'
            f'<div class="tiles">{tiles_html}</div>{trip_card(ctx)}</div>'
            f'<div class="hcal">{month_calendar.months(ctx.dates, ctx.areas, rings)}</div></div></section>')


def _sub(pg, title, body):
    """A phone screen; on the desktop the same markup is a V2 overlay over the big
    calendar (spec §6.7): the dimmed background and ✕ both go back to the home."""
    return (f'<section class="page sub ov" data-pg="{pg}"><label class="ovbg" for="pg-home" aria-label="關閉"></label>'
            f'<div class="ovbox"><div class="ph"><h2>{title}</h2><label class="back" for="pg-home">‹ 總覽</label>'
            f'<label class="ovx" for="pg-home">✕ 關閉</label></div><div class="pb"><div class="ft" aria-hidden="true"></div>'
            f'{body}<div class="fb" aria-hidden="true"></div></div></div></section>')


def lodging_screen(ctx):
    rows = []
    for r in lodging_runs(ctx):
        p = ctx.poi_map.get(r["id"])
        out = r["d"] + datetime.timedelta(days=r["n"])
        rows.append(f'<div class="lrow {r["cls"]}"><span class="dot"></span><div class="lt"><b>{esc(_name(p) or "住宿資料待補")}</b>'
                    f'<small>{esc(r["area"])}・{md(r["d"])} → {md(out)}・{r["n"]} 晚</small></div>{navb(p)}</div>')
    return _sub("lodging", "住宿", "".join(rows) or '<p class="empty">這趟沒有過夜住宿。</p>')


def advisory_screen(ctx):
    items = []
    for it in ctx.advisory_items:
        label, cls = RISK.get(it.get("risk"), ("須知", "risk-info"))
        title = it.get("title") or it.get("topic") or ""
        do = str(it.get("action") or it.get("rule") or "").replace("**", "")
        detail = str(it.get("detail") or "").replace("**", "")
        srcs = it.get("sources") if isinstance(it.get("sources"), list) else []
        links = "".join(f'<a href="{esc(s.get("url"))}" target="_blank" rel="noopener">'
                        f'{esc(_host(s.get("url")))}{"・官方" if s.get("official") else ""} ↗</a>'
                        for s in srcs if isinstance(s, dict) and s.get("url"))
        det = f'<p class="det">{esc(detail)}</p>' if detail and detail != do else ""
        items.append(f'<details class="adv {cls}"><summary><span class="tl2"><span class="rk">{label}</span>'
                     f'<b>{esc(title)}</b></span><span class="do qbar">{esc(do)}</span><span class="cv"></span></summary>'
                     f'<p class="act qbar">{esc(do)}</p>{det}{f"<p class=lnk>{links}</p>" if links else ""}</details>')
    return _sub("advisory", "入境規定", "".join(items) or '<p class="empty">沒有需要特別注意的入境規定。</p>')


def _host(url):
    import re
    return re.sub(r"^https?://(www\.)?([^/]+).*", r"\2", str(url or ""))


def checklist_items(ctx):
    """The itinerary's checklist (pre-v1.0 string items read as 出發前確認) plus one
    出發前確認 line per scheduled POI or lodging whose coordinate is a district
    centroid (scripts/render/centroid.py) -- the disclosure every renderer carries."""
    items = [it if isinstance(it, dict) else {"kind": "出發前確認", "task": str(it)} for it in ctx.checklist]
    items += [{"kind": "出發前確認", "task": centroid_note(p)}
              for p in centroid_items({"days": ctx.days}, ctx.poi_map)]
    return items


def checklist_screen(ctx):
    groups = []
    items = checklist_items(ctx)
    for kind in KINDS:
        rows = [it for it in items if it.get("kind") == kind]
        if not rows:
            continue
        out = []
        for it in rows:
            due = it.get("due")
            badge = f'<span class="due{" hard" if it.get("due_is_hard") else ""}">{esc(due)}</span>' if due else ""
            org = f'<span class="origin">{esc(it["origin"])}</span>' if it.get("origin") else ""
            head = f'<span class="tk">{esc(it.get("task"))}</span><span class="meta">{badge}{org}</span>'
            links = [l for l in it.get("links") or [] if isinstance(l, dict) and l.get("url")]
            if not it.get("detail") and not links:
                out.append(f'<div class="ci">{head}</div>')
                continue
            lk = "".join(f'<a href="{esc(l["url"])}" target="_blank" rel="noopener">{esc(l.get("label") or _host(l["url"]))} ↗</a>'
                         for l in links)
            det = f'<p>{esc(it["detail"])}</p>' if it.get("detail") else ""
            out.append(f'<details class="ci"><summary>{head}<span class="cv"></span></summary>{det}'
                       f'{f"<p class=lnk>{lk}</p>" if lk else ""}</details>')
        groups.append(f'<div class="ckg"><h3>{kind}</h3><span class="n">{len(rows)}</span>{"".join(out)}</div>')
    return _sub("checklist", "行前清單", "".join(groups) or '<p class="empty">目前沒有待辦事項。</p>')
