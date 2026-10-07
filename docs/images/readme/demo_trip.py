"""The README's screenshots: a made-up 3-day Tokyo trip (示意), rendered by the shipped reader.

Never a user's real trip (their plans are private). Only public landmarks; the hotel and
every source URL are placeholders and the hours are illustrative. The day maps are drawn
from real OpenStreetMap tiles (scripts/day_maps.py: its User-Agent, cache and one request a
second), so the credit shows on every map. The photos come from the plugin's own photo step
(scripts/photo_adapter.py --backend wiki: Wikidata first, licence-checked, credited). The
shared page's lock screen is the shipped template, locked by the real staticrypt (needs
Node) with a made-up password.

The tape sheet (today's tape on the shared page's calendar: every pattern in every colour) is
drawn by the shipped stylesheet from scripts/render/reader/tapes.py, light and dark; it needs
no network, so it can be re-taken alone.

    pip install -e ".[dev,browser,maps]"
    python docs/images/readme/demo_trip.py            # writes docs/images/readme/*.jpg and tapes*.png
    python docs/images/readme/demo_trip.py --tapes    # only tapes.png / tapes-dark.png
"""
import copy
import io
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tests import mech_fixtures as M                     # noqa: E402
from tests import reader_fixture as R                    # noqa: E402
from tests.reader_fixture import _closing, _mv, _poi, _src, _stop   # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent
OPEN_STOP = "section[data-pg=d2] .stop:has(.bp)"           # D2's first stop with a photo


def poi(pid, local, zh, cat, lat, lng, hours, district, intro=None, address=None):
    p = _poi(pid, local, zh, cat, lat, lng, hours, intro=intro, district=district)
    if address:
        p["address_local"] = address
    return p


POIS = [
    poi("senso-ji", "浅草寺", "淺草寺", "sight", 35.7148, 139.7967,
        {"close": "17:00", "last_entry": "16:45", "typical_visit_mins": 60, "as_of": "2026-04-01"},
        "淺草", intro="東京最古老的寺院，從雷門走仲見世通到本堂。", address="東京都台東区浅草2-3-1"),
    poi("nakamise", "仲見世通り", "仲見世通", "food", 35.7116, 139.7964,
        {"close": "19:00", "last_order": "18:30", "typical_visit_mins": 45, "as_of": "2026-04-01"},
        "淺草", intro="雷門到寶藏門之間約 90 家小店，人形燒、炸饅頭邊走邊吃。"),
    poi("ueno-park", "上野恩賜公園", "上野恩賜公園", "sight", 35.7156, 139.7745,
        {"close": "23:00", "last_entry": "22:30", "typical_visit_mins": 60, "as_of": "2026-04-01"},
        "上野"),
    poi("tnm", "東京国立博物館", "東京國立博物館", "sight", 35.7188, 139.7765,
        {"close": "17:00", "last_entry": "16:30", "typical_visit_mins": 120, "as_of": "2026-04-01"},
        "上野", intro="日本最大的博物館，本館看日本美術。"),
    poi("ameyoko", "アメ横", "阿美橫町", "food", 35.7101, 139.7746,
        {"close": "20:00", "last_order": "19:30", "typical_visit_mins": 60, "as_of": "2026-04-01"},
        "上野", intro="高架橋下的市場街，海鮮丼、水果串、乾貨。"),
    poi("skytree", "東京スカイツリー", "東京晴空塔", "sight", 35.7101, 139.8107,
        {"close": "22:00", "last_entry": "21:00", "typical_visit_mins": 90, "as_of": "2026-04-01"},
        "押上", intro="高 634 m，天望甲板 350 m。", address="東京都墨田区押上1-1-2"),
    poi("asakusa-tic", "浅草文化観光センター", "淺草文化觀光中心", "sight", 35.7107, 139.7966,
        {"close": "20:00", "last_entry": "19:45", "typical_visit_mins": 30, "as_of": "2026-04-01"},
        "淺草", intro="8 樓免費展望台，看得到晴空塔與仲見世。"),
]

HOTEL = copy.deepcopy(R.LODGING)
HOTEL.update({"id": "demo-hotel", "name_local": "浅草サンプルホテル", "name_display": "浅草サンプルホテル",
              "name_zh": "淺草示意飯店", "resolved_name": "浅草サンプルホテル",
              "geocode": {"lat": 35.7113, "lng": 139.7953, "geocode_source": "nominatim"}})
HOTEL["sources"] = [_src("https://hotel.example/", "ja", "示意飯店官網", "房型", official=True),
                    _src("https://guide.example/hotel", "zh", "旅遊指南", "位置")]
ACC = {"stops": [{"district": "淺草", "area_label": "淺草", "nights": 2, "chosen": "demo-hotel",
                  "candidates": [HOTEL]}]}

COST = {"currency": "JPY", "as_of": "2026-04-01", "estimate_note": "估算",
        "line_items": [{"category": "lodging", "label": "示意飯店 2 晚", "amount": 52000, "poi_id": "demo-hotel"}],
        "by_category": {"lodging": 52000, "transport": 6400}, "total": 58400}


def six(lines, ref):
    shapes = [("sentence", "pov"), ("couplet", "rhyme"), ("question", "exaggerate"),
              ("sentence", "turn"), ("triple", "contrast"), ("couplet", "pov")]
    return [{"text": t, "shape": s, "twist": w, "refs": [ref]} for t, (s, w) in zip(lines, shapes)]


def itinerary():
    by_id = {p["id"]: p for p in POIS + [HOTEL]}
    days = [
        {"date": "2026-05-12", "lodging": "demo-hotel", "theme": "雷門下的第一口", "theme_refs": ["senso-ji"],
         "theme_candidates": six(["雷門下的第一口", "燈籠在等，人形燒在燙", "淺草寺會不會太熱鬧？",
                                  "逛完本堂才想起要吃", "雷門、香爐、人形燒", "仲見世，在數我們的零錢"], "senso-ji"),
         "rows": [_mv("rail", 20, 45, basis="sourced", text="京急線直通淺草線",
                      source_url="https://rail.example/keikyu", **{"from": "羽田空港"}),
                  {"slot": "lodging", "time": "13:30", "poi_id": "demo-hotel", "text": "放行李"},
                  _mv("walk", 0.5, 8),
                  _stop("visit", "14:00", "senso-ji", "雷門 → 本堂，抽一支籤"),
                  _mv("walk", 0.4, 6),
                  _stop("meal", "15:30", "nakamise", "人形燒、炸饅頭當下午茶"),
                  _mv("walk", 0.3, 5, text="走回飯店")]},
        {"date": "2026-05-13", "lodging": "demo-hotel", "theme": "上野一整天，晚上看塔",
         "theme_refs": ["tnm", "skytree"],
         "theme_candidates": six(["上野一整天，晚上看塔", "博物館的午後，高塔的夜", "晴空塔看得到我們嗎？",
                                  "吃完阿美橫才去看塔", "國寶、海鮮丼、夜景", "高塔在遠方，數著我們的腳步"], "tnm"),
         "alternatives": [{"kind": "備案", "applies_to": "skytree", "trigger": "雲太低看不到景",
                           "fallback": "改上淺草文化觀光中心 8 樓免費展望台", "poi_id": "asakusa-tic"}],
         "rows": [_mv("rail", 2.5, 12, basis="sourced", text="銀座線 淺草 → 上野", source_url="https://rail.example/ginza"),
                  _stop("visit", "09:30", "ueno-park", "不忍池邊散步"),
                  _mv("walk", 0.6, 10),
                  _stop("visit", "10:45", "tnm", "本館看日本美術"),
                  _mv("walk", 1.0, 15),
                  _stop("meal", "13:00", "ameyoko", "海鮮丼午餐"),
                  _mv("rail", 6, 25, basis="sourced", text="銀座線＋淺草線到押上", source_url="https://rail.example/oshiage"),
                  _stop("visit", "17:00", "skytree", "看夕陽轉夜景"),
                  _mv("taxi", 2.5, 10, text="計程車回飯店")]},
        {"date": "2026-05-14", "theme": "最後再逛一圈淺草", "theme_refs": ["nakamise"],
         "theme_candidates": six(["最後再逛一圈淺草", "早上的門，最後的燒", "人形燒還買得下嗎？",
                                  "行李都收好了才想再吃", "早餐、伴手禮、機場", "淺草，在後照鏡裡揮手"], "nakamise"),
         "rows": [_mv("walk", 0.3, 5),
                  _stop("meal", "09:30", "nakamise", "早上的仲見世，買伴手禮"),
                  _mv("rail", 20, 45, basis="sourced", text="淺草線直通京急線",
                      source_url="https://rail.example/keikyu", to="羽田空港")]},
    ]
    for d in days:
        _closing(d["rows"], by_id)
    checklist = [
        {"kind": "預約", "task": "晴空塔線上預約時段票", "due": "2026-05-05", "due_is_hard": True,
         "origin": "D2・5/13", "detail": "日落前後的時段最先賣完。",
         "links": [{"label": "tokyo-skytree.jp", "url": "https://www.tokyo-skytree.jp/"}]},
        {"kind": "出發前確認", "task": "確認東京國立博物館當天開館", "due": "出發前"},
        {"kind": "打包", "task": "不帶任何肉製品入境"},
    ]
    return {"title": "東京三天", "checklist": checklist, "days": days}


def brief():
    heads = ["雷門下吃到撐", "為了人形燒走遍淺草", "晴空塔看我們吃午餐", "淺草吃不停",
             "東京三天胖三斤", "上野的午餐很有料"]
    return {"slug": "2026-05-tokyo-demo", "dates": {"start": "2026-05-12", "end": "2026-05-14"},
            "destination": {"country": "JP", "city": "東京", "local_lang": "ja"},
            "members": [{"name": "A"}, {"name": "B"}, {"name": "C"}],
            "base": {"name": "淺草示意飯店", "district": "淺草"},
            "must_do": [], "constraints": [], "preferences": {}, "short_name": "東京",
            "headline": {"text": heads[0]},
            "headline_candidates": [{"text": t, "device": "pov", "refs": []} for t in heads]}


def render(root):
    from scripts.day_maps import build
    from scripts.paths import artifact_path
    from scripts.render.reader import render_reader
    from scripts.title_picker import page as picker_page
    t, w = M.build_full_trip(root, slug="2026-05-tokyo-demo")
    itin, b = itinerary(), brief()
    for name, doc in (("trip-brief.yaml", b), ("verified-pois.yaml", {"pois": POIS}),
                      ("accommodations.yaml", ACC), ("legs.yaml", {"legs": []}),
                      ("itinerary.yaml", itin), ("cost.yaml", COST)):
        M.write_artifact(artifact_path(t, name), doc)
    maps = build(t, w)                                     # real OSM tiles, cached, 1 req/s
    from scripts import photo_adapter
    from scripts.media_merge import apply_media, load_media
    if photo_adapter.main([str(t), "--backend", "wiki"]) != 0:           # Wikidata first, then search
        raise SystemExit("photo_adapter failed")
    pm = apply_media({p["id"]: p for p in POIS + [HOTEL]},
                     load_media(artifact_path(t, "verified-pois-media.yaml")))
    reader = root / "reader.html"
    reader.write_text(render_reader(itin, pm, brief=b, accommodations=ACC, advisory=R.ADVISORY,
                                    legs={"legs": []}, maps=maps, cost=COST), encoding="utf-8")
    picker = root / "picker.html"
    picker.write_text(picker_page(itin, b, ACC), encoding="utf-8")
    return reader, picker, lock(root, reader)


def lock(root, reader):
    """The shared page's lock screen: the reader locked with the shipped template."""
    from scripts.render.publish.lock import lock_template, staticrypt_args, staticrypt_env
    d = root / "lock"
    d.mkdir()
    (d / "template.html").write_text(lock_template(), encoding="utf-8")
    (d / "index.html").write_text(reader.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(["npx", "--yes", *staticrypt_args(d / "template.html", d / "out", d / "index.html")],
                   cwd=d, check=True, capture_output=True, env=staticrypt_env("東京三天"))
    return d / "out" / "index.html"


def shoot(reader, picker, locked):
    from PIL import Image
    from playwright.sync_api import sync_playwright

    def save(pg, name, w):
        im = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
        im.save(OUT / f"{name}.jpg", quality=86, optimize=True, progressive=True)
        print(name, im.size)

    with sync_playwright() as p:
        wk = p.webkit.launch()                             # the phone: WebKit, as on an iPhone
        pg = wk.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        pg.goto(reader.as_uri()); pg.wait_for_timeout(400)
        save(pg, "phone-home", 540)
        # every day shot shows a stop opened -- the trip's first stop with a photo -- so the
        # first look at the repo shows what a stop holds
        pg.evaluate("document.getElementById('pg-d2').checked=true"); pg.wait_for_timeout(300)
        pg.evaluate(f"location.hash='#'+document.querySelector('{OPEN_STOP}').id"); pg.wait_for_timeout(900)
        save(pg, "phone-day", 540)
        pg.evaluate("location.hash=''")
        pg.evaluate("document.getElementById('pg-d1').checked=true"); pg.wait_for_timeout(300)
        sid = pg.evaluate("document.querySelector('section[data-pg=d1] .stop:has(.drvbtn)').id")
        pg.evaluate(f"location.hash='#{sid}'"); pg.wait_for_timeout(900)
        save(pg, "phone-stop", 540)
        pg.evaluate(f"location.hash=document.querySelector('#{sid} .drvbtn').getAttribute('href')")
        pg.wait_for_timeout(400)
        save(pg, "phone-driver", 540)
        pg.evaluate("location.hash=''")
        pg.evaluate("document.getElementById('pg-d2').checked=true;document.querySelector('section[data-pg=d2] .mapc').open=true")
        pg.wait_for_timeout(500)
        save(pg, "phone-map", 540)
        pg.goto(locked.as_uri()); pg.wait_for_selector(".lock", state="visible"); pg.wait_for_timeout(300)
        save(pg, "phone-lock", 540)
        pg.close()
        wk.close()
        cr = p.chromium.launch()
        pg = cr.new_page(viewport={"width": 1440, "height": 860}, device_scale_factor=1.5)
        pg.goto(reader.as_uri()); pg.wait_for_timeout(500)
        save(pg, "desktop-home", 1440)
        pg.evaluate("document.getElementById('pg-d2').checked=true"); pg.wait_for_timeout(500)
        pg.evaluate(f"location.hash='#'+document.querySelector('{OPEN_STOP}').id"); pg.wait_for_timeout(1200)
        save(pg, "desktop-day", 1440)
        pg.goto(picker.as_uri()); pg.wait_for_timeout(500)       # the title picker: used on a computer
        save(pg, "desktop-picker", 1440)
        cr.close()


def tape_sheet(dark=False):
    """Every tape pattern (rows) in every colour (columns), each strip drawn by the reader's own
    rules -- the stylesheet, tapes.css(), the theme switch -- as today's stamp wears it."""
    import html
    from scripts.render.reader import tapes
    from scripts.render.reader.assets import font_faces
    from scripts.render.reader.theme import CSS
    names = "".join(tapes.PATTERNS.values()) + "".join(tapes.COLOURS.values())
    strip = lambda p, c, k: (f'<span class="tape-swatch tp-{p} tc-{c} tt{k}" '
                             f'style="--u:2.2px;--tl:70px;--tw:23px"></span>')
    cells = ["<span></span>"] + [f"<b>{html.escape(n)}</b>" for n in tapes.COLOURS.values()]
    for i, (p, name) in enumerate(tapes.PATTERNS.items()):
        cells.append(f"<span>{html.escape(name)}</span>")
        cells += [strip(p, c, (i + j) % tapes.TEARS) for j, c in enumerate(tapes.COLOURS)]
    sheet = (".sheet{display:inline-grid;grid-template-columns:auto repeat(6,82px);gap:12px 8px;align-items:center;"
             "justify-items:center;padding:18px 22px;background:var(--card);font:700 14px var(--f-round);color:var(--mut)}"
             ".sheet>span:nth-child(7n+1){justify-self:start;padding-right:6px}body{margin:0;background:var(--card)}")
    theme = '<input type="checkbox" id="theme" checked hidden>' if dark else ""
    return (f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><style>{font_faces(names)}{CSS}{tapes.css()}{sheet}</style></head>'
            f'<body>{theme}<div class="sheet">{"".join(cells)}</div></body></html>')


def shoot_tapes(root):
    from PIL import Image
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        wk = p.webkit.launch()
        for dark, name in ((False, "tapes"), (True, "tapes-dark")):
            f = root / f"{name}.html"
            f.write_text(tape_sheet(dark), encoding="utf-8")
            pg = wk.new_page(viewport={"width": 760, "height": 600}, device_scale_factor=2)
            pg.goto(f.as_uri()); pg.wait_for_timeout(300)
            im = Image.open(io.BytesIO(pg.locator(".sheet").screenshot())).convert("RGB")
            im.save(OUT / f"{name}.png", optimize=True)
            print(name, im.size)
            pg.close()
        wk.close()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as d:
        if "--tapes" not in sys.argv:
            shoot(*render(pathlib.Path(d)))
        shoot_tapes(pathlib.Path(d))
