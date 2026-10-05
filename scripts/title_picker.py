"""The title picker (v1.1 topic 7, spec §7.3, the user's design on the board).

itinerary-synthesis stops at `day_title_pick` with six candidates a day; this writes
work/<slug>/挑標題.html -- one offline page, any browser, any agent:

- the headline on top: its candidates (the brief's pick preselected), 再給我 3 個, or
  the user's own words;
- one column per day, left to right: the day's stamp, whose ring shows the line as it
  is tapped (centred at the top and turning with the stamp, as on the reader's desktop
  home), the candidates short to long with a 注音 rhyme tag where the halves rhyme,
  再給我 3 個, or the user's own words;
- a bar at the bottom with every pick; the button reads 還差 N 天 until each day has
  one, then copies the reply line for scripts/title_picks.py.

The page is a work file, not a deliverable: it may run a script and export-gate never
sees it. With scripts off it is still a numbered list the user can answer by hand,
the same list text_list() prints for the conversation.

CLI: python <plugin>/scripts/tripwork.py picker <slug>
"""
if __name__ == "__main__":
    raise SystemExit("moved in tripwork 2.0: python <plugin>/scripts/tripwork.py picker <slug>")

import html
import json

from scripts.day_titles import THEME_MAX, display_order, rhyme_label
from scripts.brief_names import HEADLINE_MAX
from scripts.render.reader.month_calendar import TILT, day_areas
from scripts.render.reader.text import md_wd, to_date

PAGE_NAME = "挑標題.html"
REPLY_HINT = ('回覆格式：tripwork 標題 D1=3 D2=1 …（每天一個號碼；H=2 換大標題；D3=+ 再給我 3 個；'
              'D2="自己寫的" 用自己的字）')

CSS = """
:root{%(light)s;color-scheme:light;--f-body:system-ui,-apple-system,"PingFang TC","Noto Sans TC","Microsoft JhengHei",sans-serif;--f-round:'ZenEmb','GenSenEmb',var(--f-body)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--f-body)}input,button,textarea{font-family:var(--f-body)}
/* the user's check (pick L2): one sheet that does not scroll -- the cards scroll inside */
html,body{height:100%%;overflow:hidden}body{display:flex;flex-direction:column}
main{flex:1;min-height:0;display:flex;flex-direction:column;width:100%%;max-width:1240px;margin:0 auto;padding:14px 16px 8px}
h1{flex:none;font:700 22px var(--f-round);margin:0 0 6px}
.days{flex:1;min-height:0;display:flex;flex-direction:column}
.days h2{flex:none;font:700 15px var(--f-round);margin:0 0 8px;color:var(--mut)}
.row{flex:1;min-height:0;display:flex;align-items:stretch;gap:12px;overflow-x:auto;scroll-snap-type:x mandatory;padding:2px 2px 4px;scrollbar-width:none}.row::-webkit-scrollbar{display:none}
.card{flex:0 0 230px;min-height:0;overflow:hidden;scroll-snap-align:start;border-radius:16px;background:var(--card);box-shadow:0 0 0 1px var(--rule);padding:12px;display:flex;flex-direction:column;gap:6px}
.card .lines{flex:1;min-height:0;overflow-y:auto;display:flex;flex-direction:column;gap:6px;padding:2px 0;scrollbar-width:none}.card .lines::-webkit-scrollbar{display:none}
.card .opt,.card .own{flex:none}
.hcard .hd{font:700 15px var(--f-round);color:var(--mut);text-align:center;margin:6px 0 8px}
.hcard .opt span{white-space:normal;line-height:1.35}
/* the fades the reader already uses: the desktop trip card's (vertical) and the time chips' (sideways) */
@property --ft{syntax:'<length>';inherits:false;initial-value:0px}@property --fb{syntax:'<length>';inherits:false;initial-value:0px}
@property --fl{syntax:'<length>';inherits:false;initial-value:0px}@property --fr{syntax:'<length>';inherits:false;initial-value:0px}
@keyframes listfade{0%%{--ft:0px;--fb:var(--fz)}8%%{--ft:var(--fz)}92%%{--fb:var(--fz)}100%%{--ft:var(--fz);--fb:0px}}
@keyframes rowfade{0%%{--fl:0px;--fr:var(--fz)}8%%{--fl:var(--fz)}92%%{--fr:var(--fz)}100%%{--fl:var(--fz);--fr:0px}}
.card .lines{--fz:40px;animation:listfade linear both;animation-timeline:scroll(y self);-webkit-mask-image:linear-gradient(transparent,#000 var(--ft),#000 calc(100%% - var(--fb)),transparent);mask-image:linear-gradient(transparent,#000 var(--ft),#000 calc(100%% - var(--fb)),transparent)}
.row,.strip{--fz:32px;animation:rowfade linear both;animation-timeline:scroll(x self);-webkit-mask-image:linear-gradient(to right,transparent,#000 var(--fl),#000 calc(100%% - var(--fr)),transparent);mask-image:linear-gradient(to right,transparent,#000 var(--fl),#000 calc(100%% - var(--fr)),transparent)}
.strip{scrollbar-width:none}.strip::-webkit-scrollbar{display:none}
.seal{--c:var(--r1);position:relative;width:110px;height:110px;margin:0 auto;display:grid;place-items:center}
.st{--c:var(--r1);width:58px;height:58px;border-radius:50%%;border:3px solid var(--c);outline:2px solid var(--c);outline-offset:3px;color:var(--c);display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:var(--f-round);background:color-mix(in srgb,var(--c) 10%%,var(--bg));transform:rotate(var(--t))}
.st b{font-size:20px;line-height:1}.st small{font-size:11px;font-weight:700}
.r2{--c:var(--r2)}.r3{--c:var(--r3)}.r4{--c:var(--r4)}.r0{--c:var(--r0)}.st.r0,.mini i.r0{border-style:dashed;outline-style:dashed}
.ring{position:absolute;inset:0;width:110px;height:110px;pointer-events:none;overflow:visible;transform:rotate(var(--t))}.ring text{font:700 11px var(--f-round);fill:var(--c)}
.dl{text-align:center;font-size:13px;color:var(--mut);margin:0 0 4px}.dl b{color:var(--ink);font-family:var(--f-round)}
.opt{position:relative;display:block}.opt input{position:absolute;opacity:0}
.opt span{display:flex;align-items:center;gap:6px;font:700 15px var(--f-round);padding:7px 10px;border-radius:10px;box-shadow:0 0 0 1px var(--rule) inset;cursor:pointer;white-space:nowrap}
.opt i{font:500 11px var(--f-body);font-style:normal;color:var(--mut);min-width:1.2em}
.opt .rm{margin-left:auto;font-style:normal;font-size:11px;font-weight:700;padding:1px 6px;border-radius:999px;background:color-mix(in srgb,var(--move) 18%%,transparent);color:var(--move)}
.opt input:checked+span{background:var(--ink);color:var(--bg);box-shadow:none}.opt input:checked+span i{color:inherit}
.opt input:checked+span .rm{background:rgba(255,255,255,.2);color:inherit}
.opt input:focus-visible+span{outline:2px solid var(--move);outline-offset:2px}
.mb span{border:1.5px dashed var(--move);color:var(--move);box-shadow:none;justify-content:center;font-size:13px}
.own{font:inherit;font-size:13px;border-radius:10px;border:1px solid var(--rule);padding:7px 10px;background:var(--bg);color:var(--ink);width:100%%}
.bar{flex:none;background:var(--card);box-shadow:0 -1px 0 var(--rule);padding:10px 16px 12px}
.bar .in{max-width:1240px;margin:0 auto;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px 16px;align-items:center}
.bar .hn{font:700 17px var(--f-round);grid-column:1/-1;display:flex;gap:10px;align-items:baseline;margin:0}.bar .hn small{font:500 12px var(--f-body);color:var(--mut)}
.strip{display:flex;gap:10px;overflow-x:auto;padding:3px;margin:-3px}
.mini{flex:0 0 112px;display:grid;grid-template-columns:30px minmax(0,1fr);gap:6px;align-items:center;font-size:12px;line-height:1.3}
/* the bar's stamp is the reader's day-page mini stamp (theme.py .stamp + .pcal .mini .stamp): 30 px,
   lines 1.5 / 1 @ 1.5, date 12, area 7, the day's tilt and colour */
.mini i{--c:var(--r1);width:30px;height:30px;border-radius:50%%;border:1.5px solid var(--c);outline:1px solid var(--c);outline-offset:1.5px;color:var(--c);display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:var(--f-round);font-style:normal;background:color-mix(in srgb,var(--c) 10%%,var(--bg));transform:rotate(var(--t))}
.mini i b{font-size:12px;font-weight:700;line-height:1}.mini i small{font-size:7px;font-weight:700;line-height:1.2}
.mini i.r2{--c:var(--r2)}.mini i.r3{--c:var(--r3)}.mini i.r4{--c:var(--r4)}.mini i.r0{--c:var(--r0)}
.mini span.no{color:var(--mut)}
.bar button{font:700 15px var(--f-round);border:0;border-radius:999px;padding:11px 20px;background:var(--ink);color:var(--bg);cursor:pointer}
.bar button[disabled]{opacity:.4;cursor:default}
.bar .line{grid-column:1/-1;margin:0;font-size:13px;line-height:15px;color:var(--ink);border-radius:10px;border:1px solid var(--rule);padding:7px 10px;background:var(--bg);overflow-wrap:anywhere;-webkit-user-select:all;user-select:all}
.bar .line b,.mini .mm b,.hn b{font-weight:inherit}.mini em{font-style:normal}
.bar .nsb{grid-column:1/-1;margin:-2px 0 0;font-size:12px;color:var(--mut)}
/* the widest line -- 13 characters and a rhyme tag -- needs 264 px of text box (measured in
   both engines) + 24 px padding: desktop cards are 292 px; the phone's 78vw is 304 px */
@media (min-width:641px){.card{flex-basis:292px}}
@media (max-width:640px){.card{flex-basis:78vw}.bar .in{grid-template-columns:1fr}.bar button{justify-self:stretch}}
"""

# One state per day: a candidate number, "+", or the user's own words (quotes removed:
# the reply line quotes them). The line is title_picks.parse()'s input.
JS = r"""
document.documentElement.classList.add('js');
const DAYS=%(days)d,H0=%(h0)s;const pick={},txt={};let H=null,HT=%(ht)s;
const strip=s=>s.replace(/["“”「」『』＂]/g,'').trim();
// the reply line; `shown` keeps a day not picked yet as D3=? (the line is on screen from the start)
function line(shown){let s='tripwork 標題';if(H!==null)s+=' H='+(typeof H==='string'&&H!=='+'?'"'+H+'"':H);
 for(let i=1;i<=DAYS;i++){const v=pick[i];if(v===undefined){if(shown)s+=' D'+i+'=?';continue}s+=' D'+i+'='+(typeof v==='string'&&v!=='+'?'"'+v+'"':v)}return s}
function paint(){document.querySelectorAll('.mini').forEach(m=>{const i=m.dataset.i,s=m.querySelector('span');s.textContent=txt[i]||'還沒選';s.className=txt[i]?'':'no'});
 document.getElementById('hn').textContent=HT;const n=Object.keys(pick).length,b=document.getElementById('copy');
 b.disabled=n<DAYS;b.textContent=n<DAYS?'還差 '+(DAYS-n)+' 天':'複製選擇';document.getElementById('line').textContent=line(true);}
function setDay(i,v,t){if(v===null){delete pick[i];delete txt[i]}else{pick[i]=v;txt[i]=t}
 const tp=document.querySelector('.col[data-i="'+i+'"] textPath');if(tp)tp.textContent=(v===null||v==='+')?'':t;paint()}
document.querySelectorAll('input[name=h]').forEach(r=>r.addEventListener('change',()=>{H=+r.value===H0?null:+r.value;HT=r.dataset.t;
 document.getElementById('h-more').checked=false;document.getElementById('h-own').value='';paint()}));
document.getElementById('h-more').addEventListener('change',e=>{if(e.target.checked){H='+';document.querySelectorAll('input[name=h]').forEach(r=>r.checked=false);document.getElementById('h-own').value=''}
 else{H=null;const r=document.querySelector('input[name=h][value="'+H0+'"]');if(r){r.checked=true;HT=r.dataset.t}}paint()});
document.getElementById('h-own').addEventListener('input',e=>{const v=strip(e.target.value);if(v){H=v;HT=v;document.querySelectorAll('input[name=h]').forEach(r=>r.checked=false);document.getElementById('h-more').checked=false}
 else{H=null;const r=document.querySelector('input[name=h][value="'+H0+'"]');if(r){r.checked=true;HT=r.dataset.t}}paint()});
document.querySelectorAll('.col').forEach(c=>{const i=c.dataset.i,more=c.querySelector('.mb input'),own=c.querySelector('.own');
 c.querySelectorAll('input[type=radio]').forEach(r=>r.addEventListener('change',()=>{more.checked=false;own.value='';setDay(i,+r.value,r.dataset.t)}));
 more.addEventListener('change',()=>{if(more.checked){c.querySelectorAll('input[type=radio]').forEach(r=>r.checked=false);own.value='';setDay(i,'+','再給我 3 個')}else setDay(i,null)});
 own.addEventListener('input',()=>{const v=strip(own.value);c.querySelectorAll('input[type=radio]').forEach(r=>r.checked=false);more.checked=false;setDay(i,v||null,v)});});
// copy synchronously inside the click (a file:// page may never settle the async clipboard
// promise); the async API only as a fallback; the line stays on screen to copy by hand
// a page written again keeps the days already picked: read them back into the state
document.querySelectorAll('.col').forEach(c=>{const i=c.dataset.i,r=c.querySelector('input[type=radio]:checked'),own=c.querySelector('.own');
 if(r){pick[i]=+r.value;txt[i]=r.dataset.t}else if(strip(own.value)){pick[i]=strip(own.value);txt[i]=pick[i]}
 const tp=c.querySelector('textPath');if(tp&&txt[i])tp.textContent=txt[i];});
document.getElementById('copy').addEventListener('click',()=>{const s=line(),b=document.getElementById('copy');
 // the line is selected either way: a preview that blocks the copy while reporting success
 // leaves it one ⌘C / Ctrl+C away
 const sel=()=>{try{getSelection().selectAllChildren(document.getElementById('line'))}catch(e){}};
 const done=()=>{b.textContent='已複製，貼回對話';sel()},hand=()=>{b.textContent='請手動複製下面那行';sel()};
 const t=document.createElement('textarea');t.value=s;t.setAttribute('readonly','');t.style.cssText='position:fixed;opacity:0';
 document.body.appendChild(t);t.select();let ok=false;try{ok=document.execCommand('copy')}catch(e){}t.remove();
 if(ok)done();else if(navigator.clipboard)navigator.clipboard.writeText(s).then(done,hand);else hand();});
paint();
"""


def _e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def _days(itinerary, accommodations):
    days = [d for d in (itinerary or {}).get("days") or [] if isinstance(d, dict)]
    return days, day_areas({"days": days}, accommodations)


def _opt(name, value, text, number, mark="", checked=False):
    return (f'<label class="opt"><input type="radio" name="{name}" value="{value}" data-t="{_e(text)}"'
            f'{" checked" if checked else ""}><span><i>{number}</i>{_e(text)}{mark}</span></label>')


OWN = "（你寫的字）"


def _states(scope, n_opts, more, own, headline=False):
    """{piece: [CSS condition, ...]} for one pick while the page runs no script. Without a
    script a tap cannot clear the other inputs, so precedence comes from what the page
    started with (the checked / value attributes) against what the user did since: words
    typed into an empty box, then 再給我 3 個, then a newly tapped line, then the words the
    page started with, then the line it started on, else nothing yet (?). The headline
    joins the line only when it changes (the script's H), so it has no start-up pieces."""
    radio = f"{scope} input[type=radio]"
    lines = lambda attr: [(f"v{n}", f'{radio}[value="{n}"]:checked{attr}') for n in range(1, n_opts + 1)]
    # tiers, highest first; each is ([(piece, condition)], the condition the whole tier holds on)
    tiers = [([("o", f"{own}:not([value]):not(:placeholder-shown)")], None),
             ([("m", f"{more}:checked")], None),
             (lines(":not([checked])"), f"{radio}:checked:not([checked])")]
    if not headline:
        tiers += [([("o", f"{own}[value]:not(:placeholder-shown)")], None),
                  (lines("[checked]"), f"{radio}:checked[checked]")]
    out, above = {}, []
    for pieces, whole in tiers:
        for key, c in pieces:
            out.setdefault(key, []).append("html:not(.js)" + f":has({c})" + "".join(f":not(:has({h}))" for h in above))
        above.append(whole or pieces[0][1])
    if not headline:
        out["q"] = ["html:not(.js)" + "".join(f":not(:has({h}))" for h in
                                               (f"{own}:not(:placeholder-shown)", f"{more}:checked", f"{radio}:checked"))]
    return out


def _mirrors(day_texts, h_texts, h0):
    """A page that runs no script (the Claude Code app's HTML preview, LINE, iPhone Files)
    still taps the radios, so the reply line, each day's mini and the headline follow the
    taps in CSS: every possible piece is in the page, and only the one the picks name is
    shown. Hidden pieces are display:none, so selecting the line copies exactly the reply.
    Returns (line html, {day: mini html}, headline html, css)."""
    css = ["html:not(.js) .line b,html:not(.js) .mm b,html:not(.js) .hm b{display:none}",
           ".js .mm,.js .hm{display:none}", "html:not(.js) #copy{display:none}"]
    parts, minis = [], {}
    for i, texts in enumerate(day_texts, start=1):
        st = _states(f'.col[data-i="{i}"]', len(texts), f'.col[data-i="{i}"] .mb input', f'.col[data-i="{i}"] .own')
        parts.append(f'<span class="d{i}"><b class="q"> D{i}=?</b>'
                     + "".join(f'<b class="v{n}"> D{i}={n}</b>' for n in range(1, len(texts) + 1))
                     + f'<b class="m"> D{i}=+</b><b class="o"> D{i}="{OWN}"</b></span>')
        minis[i] = ('<em class="mm">' + "".join(f'<b class="v{n}">{_e(t)}</b>' for n, t in enumerate(texts, start=1))
                    + '<b class="m">再給我 3 個</b><b class="o">自己寫的</b></em>')
        for k, conds in st.items():
            for cond in conds:
                css.append(f'{cond} .line .d{i}>.{k},{cond} .mini[data-i="{i}"] .mm>.{k}{{display:inline}}')
                if k != "q":
                    css.append(f'{cond} .mini[data-i="{i}"] .no{{display:none}}')
    # the headline joins the line only when it changes (the script's H): a radio other than
    # the one the page started on (its checked attribute), 再給我 3 個, or own words
    hst = _states(".hcard", len(h_texts), "#h-more", "#h-own", headline=True)
    hpart = ('<span class="h">' + "".join(f'<b class="v{n}"> H={n}</b>' for n in range(1, len(h_texts) + 1))
             + f'<b class="m"> H=+</b><b class="o"> H="{OWN}"</b></span>')
    hmirror = ('<span class="hm">' + "".join(f'<b class="v{n}">{_e(t)}</b>' for n, t in enumerate(h_texts, start=1))
               + '<b class="m">再給我 3 個</b><b class="o">自己寫的</b></span>')
    for k, conds in hst.items():
        for cond in conds:
            css.append(f"{cond} .line .h>.{k},{cond} .hm>.{k}{{display:inline}}")
            css.append(f"{cond} #hn{{display:none}}")
    return "tripwork 標題" + hpart + "".join(parts), minis, hmirror, "\n".join(css)


def _headline_current(brief):
    cands = (brief or {}).get("headline_candidates") or []
    now = ((brief or {}).get("headline") or {}).get("text")
    for k, c in enumerate(cands, start=1):
        if isinstance(c, dict) and c.get("text") == now:
            return k
    return 0


def page(itinerary, brief, accommodations=None):
    from scripts.render.reader.assets import font_faces
    from scripts.render.reader.theme import WARM_LIGHT

    days, areas = _days(itinerary, accommodations)
    brief = brief or {}
    h0 = _headline_current(brief)
    hcands = [c for c in brief.get("headline_candidates") or [] if isinstance(c, dict)]
    hl = "".join(_opt("h", k, c.get("text"), k, checked=(k == h0)) for k, c in enumerate(hcands, start=1))
    # the user's pick L2: the headline is the first card of the row, the days follow
    hcard = (f'<section class="card hcard"><p class="hd">整趟大標題</p><div class="lines">{hl}</div>'
             '<label class="opt mb"><input type="checkbox" id="h-more"><span>＋ 再給我 3 個</span></label>'
             f'<input class="own" id="h-own" type="text" placeholder="或自己寫（{HEADLINE_MAX} 字內）" maxlength="{HEADLINE_MAX + 6}"></section>')
    cols, minis, day_texts = [], [], []
    r = 29 + 3 + 3 + 2 + 3                                  # stamp half + border + offset + outline + gap
    for i, (d, (area, cls)) in enumerate(zip(days, areas), start=1):
        date = to_date(d.get("date"))
        cands = d.get("theme_candidates") or []
        # each day starts on its current title (the user's check: the page must show it) --
        # one of its lines, or the user's own words back in their box
        kept = (d.get("theme") or "").strip()
        own = kept if kept and d.get("theme_user_written") else ""
        own_attr = ' value="%s"' % _e(own) if own else ""            # no nested quotes: CI runs 3.11
        items, texts = [], []
        for n, k in enumerate(display_order(cands), start=1):
            text = cands[k].get("text") if isinstance(cands[k], dict) else ""
            texts.append(text)
            tag = rhyme_label(text)
            items.append(_opt(f"d{i}", n, text, n, f'<em class="rm">{tag}</em>' if tag else "",
                              checked=bool(kept) and not own and text == kept))
        tilt = TILT[(i - 1) % len(TILT)]
        ring = (f'<svg class="ring" viewBox="0 0 110 110" aria-hidden="true"><defs><path id="pr{i}" '
                f'd="M55,{55 + r} a{r},{r} 0 1,1 0,-{2 * r} a{r},{r} 0 1,1 0,{2 * r}"/></defs>'
                f'<text dominant-baseline="text-after-edge"><textPath href="#pr{i}" startOffset="50%" '
                f'text-anchor="middle"></textPath></text></svg>')
        cols.append(f'<section class="card col" data-i="{i}"><div class="seal {cls}" style="--t:{tilt}deg">'
                    f'<span class="st {cls}"><b>{date.day}</b><small>{_e(area)}</small></span>{ring}</div>'
                    f'<p class="dl"><b>D{i}</b> {md_wd(date)}</p><div class="lines">{"".join(items)}</div>'
                    f'<label class="opt mb"><input type="checkbox"><span>＋ 再給我 3 個</span></label>'
                    f'<input class="own" type="text" placeholder="或自己寫（{THEME_MAX} 字內）" maxlength="{THEME_MAX}"'
                    f'{own_attr}></section>')
        day_texts.append(texts)
        minis.append((i, cls, date.day, area, tilt))
    line, mm, hmirror, mcss = _mirrors(day_texts, [c.get("text") or "" for c in hcands], h0)
    minis = [f'<div class="mini" data-i="{i}"><i class="{cls}" style="--t:{tilt}deg"><b>{day}</b><small>{_e(area)}</small></i>'
             f'<span class="no">還沒選</span>{mm[i]}</div>' for i, cls, day, area, tilt in minis]
    htext = hcands[h0 - 1].get("text") if h0 else ((brief.get("headline") or {}).get("text") or "")
    body = (f'<main><h1>挑標題</h1>'
            f'<section class="days"><h2>大標題和每天的標題（左右滑動看其他天）</h2>'
            f'<div class="row">{hcard}{"".join(cols)}</div></section></main>'
            f'<div class="bar"><div class="in"><p class="hn"><span id="hn">{_e(htext)}</span>{hmirror}<small>大標題</small></p>'
            f'<div class="strip">{"".join(minis)}</div><button type="button" id="copy" disabled>還差 {len(days)} 天</button>'
            f'<p class="line" id="line">{line}</p>'
            '<noscript><p class="nsb">長按這行選取整行，複製後貼回對話</p></noscript></div></div>')
    glyphs = html.unescape(body) + "還沒選還差天複製選擇已複製，貼回對話請手動複製下面那行再給我個tripwork標題HD=+\"0123456789"
    js = JS % {"days": len(days), "h0": h0, "ht": json.dumps(htext, ensure_ascii=False)}
    return (f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>挑標題</title>'
            f'<style>{font_faces("".join(sorted(set(glyphs))))}{CSS % {"light": WARM_LIGHT}}{mcss}</style></head>'
            f'<body>{body}<script>{js}</script></body></html>')


def text_list(itinerary, brief, accommodations=None):
    """The same choices as plain text, for the conversation (spec §7.3: 純文字保底)."""
    days, areas = _days(itinerary, accommodations)
    brief = brief or {}
    h0 = _headline_current(brief)
    out = ["大標題" + ("（目前是 %d）" % h0 if h0 else "")]
    for k, c in enumerate(brief.get("headline_candidates") or [], start=1):
        out.append(f"  {k}. {c.get('text', '')}")
    for i, (d, (area, _cls)) in enumerate(zip(days, areas), start=1):
        out.append(f"D{i} {md_wd(to_date(d.get('date')))} {area}")
        cands = d.get("theme_candidates") or []
        for n, k in enumerate(display_order(cands), start=1):
            text = cands[k].get("text", "")
            tag = rhyme_label(text)
            out.append(f"  {n}. {text}" + (f"（{tag}）" if tag else ""))
    out.append(REPLY_HINT)
    return "\n".join(out)


def main(argv):
    import argparse
    import pathlib

    import yaml

    from scripts.paths import artifact_path, work_dir_for

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("trip_dir")
    ap.add_argument("--work-dir", default=None)
    args = ap.parse_args(argv)
    trip = pathlib.Path(args.trip_dir)
    work = pathlib.Path(args.work_dir) if args.work_dir else work_dir_for(trip)

    def load(name, required=True):
        p = artifact_path(trip, name)
        if not p.exists() and not required:
            return None
        return yaml.safe_load(p.read_text(encoding="utf-8"))

    itin, brief = load("itinerary.yaml"), load("trip-brief.yaml")
    acc = load("accommodations.yaml", required=False)
    work.mkdir(parents=True, exist_ok=True)
    out = work / PAGE_NAME
    out.write_text(page(itin, brief, acc), encoding="utf-8")
    print(f"title picker: {out}")
    print(text_list(itin, brief, acc))
    return 0
