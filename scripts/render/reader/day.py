"""The mobile day page (spec §6.3): header with the mini stamp calendar, the day's
theme, and the chain — anchor, stop, move, stop, …, anchor — with one stop open at
a time (the URL fragment names it, v1.1 §8.1), alternatives under their stop, and sources."""
import re

from scripts.render.gmaps_links import maps_url
from scripts.render.reader import month_calendar
from scripts.render.reader.assets import MODE_ICON, SLOT_ICON, icon
from scripts.render.reader.home import _name, navb
from scripts.render.reader.maps import DATA_IMAGE, day_points, image_class, map_card, target
from scripts.render.reader.text import dur, esc, hhmm, lang_label, minutes, move_summary, number

MODE_LABEL = {"walk": "步行", "rail": "電車", "bus": "巴士", "taxi": "計程車", "drive": "開車",
              "ferry": "渡輪", "flight": "飛機", "ropeway": "纜車"}
GAP_MINS = 20


def _is_move(r):
    return r.get("slot") == "move"


def _stay(p):
    return number(((p or {}).get("hours") or {}).get("typical_visit_mins"))


def _first_clause(text):
    return re.split(r"[；;。\n]", str(text or ""), maxsplit=1)[0].strip()


def _hours(p, slot):
    h = (p or {}).get("hours") or {}
    if h.get("no_fixed_close"):
        return "無固定關門時間"
    if not h.get("close"):
        return ""
    tail = ""
    if slot == "meal" and h.get("last_order"):
        tail = f"（L.O. {h['last_order']}）"
    elif h.get("last_entry"):
        tail = f"（最後入場 {h['last_entry']}）"
    elif h.get("last_order"):
        tail = f"（L.O. {h['last_order']}）"
    return f"至 {h['close']}{tail}"


def sources(p, tid=None):
    srcs = [s for s in (p or {}).get("sources") or [] if isinstance(s, dict) and s.get("url")]
    if not srcs:
        return ""
    srcs = sorted(srcs, key=lambda s: not s.get("official"))
    names = [s.get("site") or re.sub(r"^https?://(www\.)?([^/]+).*", r"\2", s["url"]) for s in srcs]
    items = []
    for s, name in zip(srcs, names):
        otag = '<span class="otag">官方</span>' if s.get("official") else ""
        local = f'<span class="sl">{esc(s["site_local"])}</span>' if s.get("site_local") else ""
        note = f'<p class="sd">{esc(s["note"])}</p>' if s.get("note") else ""
        items.append(f'<li><a class="sh" href="{esc(s["url"])}" target="_blank" rel="noopener">'
                     f'<span class="snm">{esc(name)}</span>{otag}<span class="lg">{lang_label(s.get("lang"))}</span></a>'
                     f'{local}<span class="su">{esc(s["url"])}</span>{note}</li>')
    head = f'{icon("book-open")}<span class="nms">{esc("、".join(names))}</span><span class="cv"></span>'
    if tid is None:                    # outside a stop (no anchor to return to): a plain toggle
        return f'<details class="ver"><summary>{head}</summary><ul>{"".join(items)}</ul></details>'
    # an anchor pair: opening targets the list (its stop stays open because it holds the
    # target); closing targets the stop again -- no script, so it works in Quick Look
    return (f'<div class="ver" id="{tid}-src"><a class="vsum vopen" href="#{tid}-src">{head}</a>'
            f'<a class="vsum vclose" href="#{tid}">{head}</a><ul class="vlist">{"".join(items)}</ul></div>')


def _photo(ctx, p):
    ph = (p or {}).get("photo") or {}
    data = ph.get("data") if isinstance(ph, dict) else None
    if not (isinstance(data, str) and DATA_IMAGE.fullmatch(data)):
        return ""                      # offline page: only embedded base64 images
    attr = p.get("photo_attribution") or {}
    credit = "・".join(esc(x) for x in (attr.get("author"), attr.get("license")) if x)
    src = attr.get("source_url")
    credit = (f'<a href="{esc(src)}" target="_blank" rel="noopener">{credit}</a>'
              if isinstance(src, str) and src.startswith("https://") else credit)
    # a CSS background, one rule per distinct image (page.py): a stop visited on
    # several days carries its photo once, as the map images do. Tapping it opens it
    # fullscreen through its own checkbox, like the map (v1.1 §7; no script).
    ctx.photo_n = getattr(ctx, "photo_n", 0) + 1
    pid = f"pz-{ctx.photo_n}"
    return (f'<figure class="bp"><input autocomplete="off" type="checkbox" class="ck pz" id="{pid}">'
            f'<label class="bpz" for="{pid}"><span class="bpi {image_class(ctx, data)}" role="img" '
            f'aria-label="{esc(_name(p))}"></span></label>'
            f'<label class="zbg" for="{pid}" aria-hidden="true"></label>'
            f'<figcaption>{icon("camera")} {credit}</figcaption>'
            f'<div class="zbar"><span class="zc">{credit}</span><label class="zx" for="{pid}">✕ 關閉</label></div></figure>')


def stop(ctx, i, j, row, p, local_lang):
    slot = row.get("slot") or "visit"
    tid = target(i, f"s{j}")
    start = minutes(row.get("time"))
    stay = _stay(p)
    leave = f'<small>– {hhmm(start + stay)}</small>' if start is not None and stay else ""
    head = (f'<span class="t"><b>{esc(row.get("time") or "")}</b>{leave}</span>'
            f'<span class="nm"><span class="n">{esc(_name(p) or row.get("text"))}</span>'
            f'<span class="one">{esc(_first_clause(row.get("text")))}</span></span>')
    rows = []
    if stay:
        rows.append(("停留", f"約 {dur(stay)}（建議）"))
    if p and p.get("intro"):
        rows.append(("介紹", esc(p["intro"])))
    opening = _hours(p, slot)
    if opening:
        rows.append(("營業", esc(opening)))
    lang = esc(local_lang if isinstance(local_lang, str) else "")
    if p and p.get("name_local") and p["name_local"] != _name(p):
        rows.append((lang_label(local_lang), f'<span lang="{lang}">{esc(p["name_local"])}</span>'))
    sheet = ""
    if p and p.get("address_local"):
        dd, sheet = address(tid, p, lang)
        rows.append(("地址", dd))
    if row.get("text"):
        rows.append(("安排", esc(row["text"])))
    src = sources(p, tid)
    if src:
        rows.append(("來源", src))
    return card(ctx, tid, slot, row.get("poi_id"), head, rows, sheet, p)


def address(tid, p, lang):
    """(dd, sheet): a place's address, and a big-print sheet to hand a taxi driver --
    TW-096 (the user's pick A2): an in-page target, so it opens with no script; closing
    returns to the stop, which stays open. A tap anywhere on the sheet closes it."""
    dd = (f'<span lang="{lang}">{esc(p["address_local"])}</span>'
          f'<a class="drvbtn" href="#{tid}-drv">給司機看</a>')
    sheet = (f'<div class="drv" id="{tid}-drv"><a class="drvbg" href="#{tid}" aria-label="關閉"></a>'
             f'<a class="drvx" href="#{tid}">✕ 關閉</a>'
             f'<p class="drvn" lang="{lang}">{esc(p.get("name_local") or _name(p))}</p>'
             f'<p class="drva" lang="{lang}">{esc(p["address_local"])}</p>'
             f'<p class="drvh">把手機轉給司機看</p></div>')
    return dd, sheet


def card(ctx, tid, slot, poi_id, head, rows, sheet, p):
    """The stop card: a head that opens it, the details (rows of (label, html)), the
    place's 導航 button. Shared by a day's stops and a survey's list (v2.1.0)."""
    dl = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
    nav = (f'<a class="navb" href="{esc(maps_url(p))}" target="_blank" rel="noopener">'
           f'{icon(SLOT_ICON.get(slot, "map-pin"))}導航</a>') if p else ""
    # the stop is the anchor target; "-x" is a 1 px target inside it that means "closed,
    # but stay here" (spec v1.1 §8.1: one :target at a time = one stop open at a time)
    return (f'<div class="stop s-{esc(slot)}" id="{tid}" data-poi="{esc(poi_id or "")}">'
            f'<span class="tx" id="{tid}-x"></span>'
            f'<div class="c3"><a class="hd hd-open" href="#{tid}">{head}</a>'
            f'<a class="hd hd-close" href="#{tid}-x">{head}</a>'
            f'<div class="in">{_photo(ctx, p)}<dl>{dl}</dl>{sheet}</div></div>{nav}</div>')


def _leg_fields(row, legs):
    """(mode, mins, km) of one move row; a leg_index row reads its legs.yaml leg."""
    li = row.get("leg_index")
    if isinstance(li, int) and not isinstance(li, bool) and 0 <= li < len(legs):
        lg = legs[li]
        return lg.get("mode"), number(lg.get("duration_mins")), number(lg.get("km"))
    return row.get("mode"), number(row.get("mins")), number(row.get("km"))


def leg(row, legs):
    """The 移動列: mode, minutes and distance, nothing else (v1.1, user: no note, no 估
    mark, no route button -- every stop already has its own 導航)."""
    mode, mins, km = _leg_fields(row, legs)
    if mode == "none":
        return '<div class="leg zero"><span class="lico">·</span><span class="ltx">同一個地方，不用移動</span></div>'
    ic = icon(MODE_ICON[mode], f"lu m-{mode}") if mode in MODE_ICON else '<span class="lico">·</span>'
    return f'<div class="leg">{ic}<span class="ltx">{move_summary(MODE_LABEL.get(mode, "移動"), mins, km)}</span></div>'


def alternative(alt, poi_map, sid=""):
    kind = alt.get("kind") if alt.get("kind") in ("備案", "選項") else "備案"
    p = poi_map.get(alt.get("poi_id")) if isinstance(alt.get("poi_id"), str) else None
    mark = "↺" if kind == "備案" else "＋"
    hours = _hours(p, "visit")
    nav = (f'<a class="navb" href="{esc(maps_url(p))}" target="_blank" rel="noopener">'
           f'{icon("map-pin")}導航</a>') if p else ""
    return (f'<details class="altrow k{kind}" data-stop="{esc(sid)}"><summary><span class="ai">{mark}</span>'
            f'<span class="at"><b>{kind}</b>{esc(alt.get("trigger"))}</span><span class="cv"></span></summary>'
            f'<div class="ab"><p>{esc(alt.get("fallback"))}</p>'
            f'{f"<p>{esc(_name(p))}・{esc(hours)}</p>" if p and hours else ""}{nav}</div></details>')


def _end_place(row, legs, key):
    """A move row's `from` / `to`, or its legs.yaml leg's when the row is a leg_index row."""
    if row.get(key):
        return row[key]
    li = row.get("leg_index")
    if isinstance(li, int) and not isinstance(li, bool) and 0 <= li < len(legs):
        return legs[li].get(key)
    return None


def _ends(ctx, i, day):
    """((head text, POI, icon), (tail text, POI, icon)), from lodging or else the first /
    last move's endpoint. An endpoint that is only a name (the airport, TW-084) gets a
    name-only record, so it still has a navigation button."""
    legs = (ctx.legs or {}).get("legs") or []
    rows = [r for r in day.get("rows") or [] if isinstance(r, dict)]
    prev_lodge = ctx.days[i - 2].get("lodging") if i > 1 else None
    head_p = ctx.poi_map.get(prev_lodge) if prev_lodge else None
    first_from = next((v for r in rows if _is_move(r) and (v := _end_place(r, legs, "from"))), None)
    tail_p = ctx.poi_map.get(day.get("lodging")) if day.get("lodging") else None
    last_to = next((v for r in reversed(rows) if _is_move(r) and (v := _end_place(r, legs, "to"))), None)
    if head_p:
        head = (f"從 {_name(head_p)} 出發", head_p, "bed-double")
    else:
        head = (f"從 {first_from or '抵達地點'} 出發", {"name_local": first_from} if first_from else None, "map-pin")
    if tail_p:
        tail = (f"回到 {_name(tail_p)}", tail_p, "bed-double")
    else:
        tail = (f"前往 {last_to or '下一站'}", {"name_local": last_to} if last_to else None, "map-pin")
    return head, tail


def _anchor(end, aid):
    text, p, ic = end
    return f'<div class="anchor" id="{aid}"><div><b>{esc(text)}</b></div>{navb(p, ic)}</div>'


def chain(ctx, i, day):
    legs = (ctx.legs or {}).get("legs") or []
    rows = [r for r in day.get("rows") or [] if isinstance(r, dict)]
    alts = {}
    for a in day.get("alternatives") or []:
        if isinstance(a, dict) and isinstance(a.get("applies_to"), str):
            alts.setdefault(a["applies_to"], []).append(a)
    head, tail = _ends(ctx, i, day)
    # the map's home points land on the list's ends (v2.1.0 D10): with no hotel at that
    # end, the end row is the trip leaving or reaching home; a last day that ends at a
    # hotel gets home's own row after it
    ends = {p["key"]: p for _, p in day_points(ctx, i, day)}
    head_id = target(i, "home-start" if "home-start" in ends and "start" not in ends else "start")
    out = [f'<span class="tx" id="{target(i, "all")}"></span>', _anchor(head, head_id)]
    prev_leave, travel, placed = None, 0, set()
    for j, r in enumerate(rows):
        if _is_move(r):
            out.append(leg(r, legs))
            travel += _leg_fields(r, legs)[1] or 0
            continue
        p = ctx.poi_map.get(r.get("poi_id"))
        start = minutes(r.get("time"))
        if prev_leave is not None and start is not None:
            gap = start - (prev_leave + travel)
            if gap >= GAP_MINS:
                out.append(f'<div class="gap">空檔 {dur(gap)}</div>')
            elif gap < 0:
                out.append(f'<div class="tight">時間偏緊：預計 {hhmm(prev_leave + travel)} 才到</div>')
        out.append(stop(ctx, i, j, r, p, ctx.local_lang))
        pid = r.get("poi_id")
        if pid in alts and pid not in placed:
            out.extend(alternative(a, ctx.poi_map, target(i, f"s{j}")) for a in alts[pid])
            placed.add(pid)
        stay = _stay(p)
        # no stay time -> no departure time -> no gap claim for the next stop
        prev_leave = start + stay if start is not None and stay else None
        travel = 0
    if "home-end" in ends and "end" not in ends:
        out.append(_anchor(tail, target(i, "home-end")))
    else:
        out.append(_anchor(tail, target(i, "end")))
        if "home-end" in ends:
            home = ends["home-end"]["poi"]
            out.append(_anchor((f"回到 {_name(home)}", home, "map-pin"), target(i, "home-end")))
    return f'<div class="list">{"".join(out)}</div>'


def day_page(ctx, i):
    day = ctx.days[i - 1]
    theme = day.get("theme") or day.get("label") or ""
    # one DOM, two layouts: the phone stacks .pcal / .pmap / .plist and only .plist
    # scrolls (spec v1.1 §3); the desktop lays the same three out as the dashboard.
    # The date line is gone: the glowing stamp gives the date, its column the weekday,
    # its small text the area, and "Day N" the day number (v1.1 §3).
    # v1.1 topic 6 (pick D2): the desktop shows the title at the top of the list; the
    # phone keeps it in its fixed header -- two copies, one shown per width (theme.py)
    # the user's check (pick S1; T25b: 25.5 px): on the phone the Day chip steps to the
    # neighbouring days -- labels for the day radios, so no script; the ends are dimmed
    n = len(ctx.days)
    prev = (f'<label for="pg-d{i - 1}" aria-label="前一天">‹</label>' if i > 1
            else '<span class="off" aria-hidden="true">‹</span>')
    nxt = (f'<label for="pg-d{i + 1}" aria-label="後一天">›</label>' if i < n
           else '<span class="off" aria-hidden="true">›</span>')
    # H1c2: the phone's arrows each carry two overlapping labels, to the neighbour opened as
    # usual (.so) or with its calendar put away (.sf); the list's scroll shows one (theme.py)
    def both(k, arrow, word):
        return (f'<span class="sw"><label class="so" for="pg-d{k}" aria-label="{word}">{arrow}</label>'
                f'<label class="sf" for="pg-d{k}f" aria-label="{word}">{arrow}</label></span>')
    pprev = both(i - 1, "‹", "前一天") if i > 1 else prev
    pnxt = both(i + 1, "›", "後一天") if i < n else nxt
    title = (f'<h2 class="dh"><span class="dht">{esc(theme)}</span>'
             f'<span class="dstep">{pprev}<span class="dn">Day {i}</span>{pnxt}</span></h2>')
    # pick F1: the desktop's list title steps too, at the row's right end like the phone's
    list_title = (f'<h2 class="dh dh-list"><span class="dht">{esc(theme)}</span>'
                  f'<span class="dstep dstep-d">{prev}<span class="dn">Day {i}</span>{nxt}</span></h2>')
    # the phone folds the mini calendar away by its own height: --wk weeks (theme.py --fold)
    return (f'<section class="page day" data-pg="d{i}" data-date="{ctx.dates[i - 1].isoformat()}" style="--wk:{len(month_calendar.weeks(ctx.dates))}">'
            f'<div class="dash"><div class="pcal">'
            f'<div class="ymrow"><label class="back" for="pg-home">‹ 總覽</label>'
            f'<b class="ym"><label class="unf" for="pg-d{i}" aria-label="展開月曆"></label>'
            f'{esc(month_calendar.month_title(ctx.dates))}</b><span></span></div>'
            f'{month_calendar.mini(ctx.dates, ctx.areas, i)}{title}</div>'
            f'<div class="pmap">{map_card(ctx, i, day)}</div>'
            # H1c: the phone list card's top edge (its clipped top has no outline of its own)
            # and foot fade, drawn beside it so they do not scroll (theme.py)
            f'<div class="lcap" aria-hidden="true"></div>'
            f'<div class="plist">{list_title}{chain(ctx, i, day)}<div class="fb" aria-hidden="true"></div></div>'
            f'<div class="lfoot" aria-hidden="true"></div></div></section>')
