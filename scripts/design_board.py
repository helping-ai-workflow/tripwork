"""The design board: visual choices in front of the user, with any AI agent.

A YAML of topics in, one offline HTML page out -- the reader's warm paper look, its fonts
embedded, every preview inline -- written to `.design-board/` (git never tracks it, so a
preview may show a real trip). The user opens it in a browser, picks a card per topic
(radios: a pick works with no script), adds a note, and 「複製選擇」 gives one line to
paste back to whichever agent asked. An agent that can also publish pages (a Claude
artifact) may publish the same file; the local file is the board.

    python scripts/design_board.py board.yaml [-o out.html]

YAML:
    title: 照片與 README
    intro: 一句說明（選填）
    topics:
      - id: photos                     # a short slug: the line says photos=P1
        question: 景點照片從哪裡找？
        recommend: P1
        why: 推薦的理由
        options:
          - key: P1                    # shown on the card; unique within the topic
            title: Wikidata 代表圖
            note: 一句說明（選填）
            image: shots/p1.png        # a file next to the YAML, or
            images:                    # several, side by side, each captioned, or
              - {image: a.png, caption: ① 收起}
            html: "<p>…</p>"           # an HTML preview (exactly one of the three)
"""
import argparse
import base64
import html as _html
import mimetypes
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
# run as a file, Python puts scripts/ first on sys.path, where scripts/calendar.py shadows the
# standard library's calendar (the font subsetter needs the real one): drop it, use the root
if sys.path and pathlib.Path(sys.path[0] or ".").resolve() == pathlib.Path(__file__).resolve().parent:
    sys.path.pop(0)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

UI_TEXT = "樣式看板「」：；（）已選題還沒選複製選擇已複製，貼回對話請手動複製下面那行我推薦補充（選填）推薦代號例如=0123456789"

CSS = """
:root{%(light)s;--f-body:system-ui,-apple-system,"PingFang TC","Noto Sans TC","Microsoft JhengHei",sans-serif;--f-round:'ZenEmb','GenSenEmb',var(--f-body);color-scheme:light}
@media (prefers-color-scheme:dark){:root{%(dark)s;color-scheme:dark}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 var(--f-body)}
.board{max-width:1230px;margin:0 auto;padding:24px 16px 160px;display:grid;gap:36px}
.top h1{font:700 22px/1.3 var(--f-round);margin:0 0 4px;text-wrap:balance}
.top p{margin:0;color:var(--mut);font-size:14px;max-width:62ch}
.ns{margin-top:8px!important;color:var(--ink)!important;background:var(--card);box-shadow:0 0 0 1px var(--rule);border-radius:12px;padding:10px 12px}
.topic{display:grid;gap:14px}
.topic h2{font:700 18px/1.4 var(--f-round);margin:0}
.rec{margin:0;font-size:13px;background:var(--card);box-shadow:0 0 0 1px var(--rule);border-radius:12px;padding:10px 12px;max-width:62ch}
.rec b{color:var(--move);font-family:var(--f-round)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%%,300px),1fr));gap:16px;align-items:start}
.card{position:relative;display:grid;gap:10px;min-width:0;border-radius:16px;padding:12px;background:var(--card);box-shadow:0 0 0 1px var(--rule);cursor:pointer;-webkit-tap-highlight-color:transparent}
.card input{position:absolute;opacity:0;width:1px;height:1px;margin:0;pointer-events:none}
.card:has(input:checked){box-shadow:0 0 0 2px var(--move)}
.card:has(input:focus-visible){outline:2px solid var(--ink);outline-offset:3px}
.ch{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.ch .k{font:700 18px/1 var(--f-round);color:var(--ink);border:1.5px solid var(--rule);border-radius:999px;padding:3px 10px}
.card:has(input:checked) .k{background:var(--move);border-color:var(--move);color:var(--card)}
.ch .t{font-weight:700}
.ch .r{font-size:12px;font-weight:700;color:var(--move)}
.ch .n{flex-basis:100%%;font-size:13px;color:var(--mut)}
.pv{display:block;min-width:0}
.pv img{display:block;width:100%%;height:auto;border-radius:10px;box-shadow:0 0 0 1px var(--rule)}
.seq{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);gap:8px}.seq figure{margin:0;display:grid;gap:4px}.seq figcaption{font-size:12px;color:var(--mut);text-align:center}
.foot{display:grid;gap:6px;max-width:62ch}
.foot label{font-size:13px;color:var(--mut)}
textarea{font:inherit;font-size:14px;min-height:56px;border-radius:12px;border:1px solid var(--rule);background:var(--card);color:var(--ink);padding:10px}
textarea:focus-visible,#copy:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.bar{position:fixed;left:0;right:0;bottom:0;background:var(--card);box-shadow:0 -1px 0 var(--rule);padding:10px 16px calc(10px + env(safe-area-inset-bottom,0px))}
.bar .in{max-width:1230px;margin:0 auto;display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px}
.sum{margin:0;font-size:14px;color:var(--mut)}
#copy{margin-left:auto;font:700 15px var(--f-body);border-radius:999px;padding:10px 20px;border:0;background:var(--ink);color:var(--card);cursor:pointer}
#copy[disabled]{opacity:.4;cursor:default}
.line{flex-basis:100%%;margin:0;font-size:13px;color:var(--ink);overflow-wrap:anywhere;user-select:all;-webkit-user-select:all}
.line:empty{display:none}
"""

JS = """(()=>{const TITLE=%(title)s,IDS=%(ids)s,el=s=>document.querySelector(s);
const line=()=>{const parts=[];IDS.forEach(id=>{const r=el('input[name="'+id+'"]:checked');if(!r)return;
 const n=(el('#note-'+id).value||'').trim();parts.push(id+'='+r.value+(n?'（'+n+'）':''))});
 return parts.length?'樣式看板「'+TITLE+'」：'+parts.join('；'):''};
const paint=()=>{const n=IDS.filter(id=>el('input[name="'+id+'"]:checked')).length,b=el('#copy');
 el('#sum').textContent=n?'已選 '+n+' / '+IDS.length+' 題':'還沒選';b.disabled=!n;b.textContent='複製選擇';el('#line').textContent=''};
// only the topics' own radios and notes repaint: WebKit fires change on the copy helper's
// textarea as it is removed, which wiped the line just made
document.addEventListener('change',e=>{if(e.target.type==='radio')paint()});
document.addEventListener('input',e=>{if(e.target.id&&e.target.id.startsWith('note-'))paint()});
// copy synchronously inside the click (a file:// page may never settle the async clipboard
// promise); the async API only as a fallback; the line stays on screen to copy by hand
el('#copy').addEventListener('click',()=>{const s=line(),b=el('#copy');el('#line').textContent=s;
 const done=()=>{b.textContent='已複製，貼回對話'},hand=()=>{b.textContent='請手動複製下面那行'};
 const t=document.createElement('textarea');t.value=s;t.setAttribute('readonly','');t.style.cssText='position:fixed;opacity:0';
 document.body.appendChild(t);t.select();let ok=false;try{ok=document.execCommand('copy')}catch(e){}t.remove();
 if(ok)done();else if(navigator.clipboard)navigator.clipboard.writeText(s).then(done,hand);else hand()});
paint()})();"""


def _e(s):
    return _html.escape(str(s or ""), quote=True)


def _load(spec_path):
    spec_path = pathlib.Path(spec_path)
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    topics = spec.get("topics") or []
    if not spec.get("title") or not topics:
        raise ValueError(f"{spec_path}: a board needs a title and at least one topic")
    seen_ids = set()
    for t in topics:
        tid = str(t.get("id") or "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", tid) or tid in seen_ids:
            raise ValueError(f"topic id {tid!r}: lower-case letters, digits and '-', unique")
        seen_ids.add(tid)
        opts = t.get("options") or []
        if len(opts) < 2:
            raise ValueError(f"topic {tid}: at least two options")
        keys = []
        for o in opts:
            k = str(o.get("key") or "")
            if not k or k in keys:
                raise ValueError(f"topic {tid}: duplicate key {k}" if k else f"topic {tid}: an option has no key")
            keys.append(k)
            if sum(bool(o.get(x)) for x in ("image", "images", "html")) != 1:
                raise ValueError(f"topic {tid} option {k}: give exactly one of image / images / html")
            for img in [o.get("image")] + [i.get("image") for i in o.get("images") or []]:
                if img and not (spec_path.parent / img).is_file():
                    raise ValueError(f"topic {tid} option {k}: image not found: {img}")
        if str(t.get("recommend") or "") not in keys:
            raise ValueError(f"topic {tid} recommends {t.get('recommend')}, which is not one of {keys}")
    return spec


def _image(path):
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(pathlib.Path(path).read_bytes()).decode('ascii')}"


def build(spec_path):
    """The board page for a YAML spec, as one self-contained HTML string."""
    from scripts.render.reader.assets import font_faces
    from scripts.render.reader.theme import WARM_DARK, WARM_LIGHT

    spec_path = pathlib.Path(spec_path)
    spec = _load(spec_path)
    sections = []
    for t in spec["topics"]:
        tid = t["id"]
        cards = []
        for o in t["options"]:
            k = str(o["key"])
            rec = k == str(t["recommend"])
            if o.get("image"):
                pv = f'<img src="{_image(spec_path.parent / o["image"])}" alt="{_e(o.get("title"))}">'
            elif o.get("images"):
                pv = '<span class="seq">' + "".join(
                    f'<figure><img src="{_image(spec_path.parent / i["image"])}" alt="{_e(i.get("caption"))}">'
                    f'<figcaption>{_e(i.get("caption"))}</figcaption></figure>' for i in o["images"]) + "</span>"
            else:
                pv = str(o["html"])
            rec_attr = ' data-rec="1"' if rec else ""
            rec_tag = '<span class="r">推薦</span>' if rec else ""
            note = f'<span class="n">{_e(o.get("note"))}</span>' if o.get("note") else ""
            cards.append(
                f'<label class="card" data-key="{_e(k)}"{rec_attr}>'
                f'<input type="radio" name="{tid}" value="{_e(k)}">'
                f'<span class="ch"><span class="k">{_e(k)}</span><span class="t">{_e(o.get("title"))}</span>'
                f'{rec_tag}{note}</span><span class="pv">{pv}</span></label>')
        sections.append(
            f'<section class="topic" data-topic="{tid}"><h2>{_e(t.get("question"))}</h2>'
            f'<p class="rec">我推薦 <b>{_e(t["recommend"])}</b>：{_e(t.get("why"))}</p>'
            f'<div class="cards">{"".join(cards)}</div>'
            f'<div class="foot"><label for="note-{tid}">補充（選填）</label>'
            f'<textarea id="note-{tid}" rows="2"></textarea></div></section>')
    first = spec["topics"][0]
    intro = f'<p>{_e(spec.get("intro"))}</p>' if spec.get("intro") else ""
    body = (f'<main class="board"><header class="top"><h1>{_e(spec["title"])}</h1>{intro}'
            f'<noscript><p class="ns">這個瀏覽器沒有執行網頁程式：選好之後，直接在對話裡回覆每題的代號'
            f'（例如 {_e(first["id"])}={_e(first["recommend"])}）。</p></noscript></header>'
            f'{"".join(sections)}</main>'
            f'<div class="bar"><div class="in"><p class="sum" id="sum">還沒選</p>'
            f'<button type="button" id="copy" disabled>複製選擇</button><p class="line" id="line"></p></div></div>')
    glyphs = _html.unescape(re.sub(r"<[^>]+>", "", body)) + UI_TEXT
    import json
    js = JS % {"title": json.dumps(spec["title"], ensure_ascii=False), "ids": json.dumps([t["id"] for t in spec["topics"]])}
    return ('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{_e(spec["title"])}</title><style>{font_faces("".join(sorted(set(glyphs))))}'
            f'{CSS % {"light": WARM_LIGHT, "dark": WARM_DARK}}</style></head>'
            f'<body>{body}<script>{js}</script></body></html>')


def default_output(root, spec_path):
    """`.design-board/<spec name>.html` under the repo root: git never tracks it."""
    return pathlib.Path(root) / ".design-board" / (pathlib.Path(spec_path).stem + ".html")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build an offline design board from a YAML spec.")
    ap.add_argument("spec")
    ap.add_argument("-o", "--output")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.output) if a.output else default_output(ROOT, a.spec)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(a.spec), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
