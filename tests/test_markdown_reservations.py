"""md deliverable: 「## 交通」「## 餐廳」, the stay and ticket reservations inline, the
derived / hidden checklist and the one centroid line -- every number masked."""
from scripts import reservation as R
from scripts.export_gate import run_export_gate
from scripts.render.markdown import render_markdown_page
from tests import reservation_fixture as F


def _md(res="fixture", checklist=None, pm=None):
    itin = F.itinerary()
    if checklist is not None:
        itin["checklist"] = checklist
    return render_markdown_page(itin, pm or F.poi_map(), legs=F.legs(),
                                reservations=F.reservations() if res == "fixture" else res)


def _section(md, head):
    start = md.index(f"## {head}\n")
    return md[start:md.index("\n## ", start + 3)]


def test_rows_listing_is_shared():
    moves = R.reservation_rows(F.itinerary(), F.legs(), F.reservations(), F.poi_map(), "move")
    assert [m["title"] for m in moves] == ["示意航空 SA 101", "京急線直通淺草線", "淺草線直通京急線", "示意航空 SA 102"]
    assert moves[0]["time"] == "08:50" and moves[0]["sub"] == "桃園機場 08:50 → 羽田空港 13:00"
    meals = R.reservation_rows(F.itinerary(), F.legs(), F.reservations(), F.poi_map(), "meal")
    assert [m["title"] for m in meals] == ["淺草示意居酒屋", "上野示意洋食", "押上示意割烹"]   # the ticket is not a meal


def test_sections_sit_between_the_days_and_contingency():
    md = _md()
    assert md.index("## 交通") < md.index("## 餐廳") < md.index("## 出發前檢查清單")
    assert md.rindex("|") < md.index("## 交通")              # after the last day table


def test_section_lines():
    t = _section(_md(), "交通")
    assert "- **5/12（二）**" in t
    assert ("  - 08:50 示意航空 SA 101，桃園機場 08:50 → 羽田空港 13:00：**已訂**"
            "（訂位編號 ••••PX；座位 32A・32B・32C；行李 每人託運 23 kg）") in t
    m = _section(_md(), "餐廳")
    assert "  - 13:00 上野示意洋食，炸豬排午餐：**還要訂**（怎麼訂 官網開放前 30 天線上預約；人數 3 位）" in m
    assert "**自理**" in m and "###" not in t + m


def test_stay_and_ticket_inline():
    md = _md()
    assert "**宿**：" in md and "（已訂・訂房編號 ••••3907・15:00 起・三人房，含早餐）" in md
    sky = next(l for l in md.splitlines() if l.startswith("| 17:00"))
    assert sky.endswith("（已訂・預約編號 ••••30X1・17:00 入場・3 張） |")
    kappo = next(l for l in md.splitlines() if l.startswith("| 19:00"))
    assert "••••" not in kappo                                  # meals have their own section


def test_checklist_uses_the_reservation_rules():
    cl = _section(_md(checklist=[{"kind": "預約", "task": "晴空塔線上預約時段票", "poi_id": "skytree"}]) + "\n## ",
                  "出發前檢查清單")
    assert "晴空塔線上預約時段票" not in cl
    assert "- 訂上野示意洋食 13:00，3 位" in cl


def test_one_centroid_line():
    pm = F.poi_map()
    for pid in ("kappo", "izakaya"):
        pm[pid]["geocode"]["geocode_source"] = "cluster_fallback"
    md = _md(pm=pm)
    assert md.count("地圖只標到區域中心") == 1 and "地圖座標是所在區域的中心點，不是它本身的位置" not in md


def test_no_reservations_no_sections():
    md = _md(res=None)
    assert "## 交通" not in md and "## 餐廳" not in md and "••••" not in md


def test_no_full_number_and_export_gate_passes():
    md = _md()
    assert not any(ref in md for ref in F.REFS)
    assert run_export_gate(md, list(F.poi_map().values()), min_days=3)["failures"] == []
