"""End-to-end closure for reservations (pre-ship gate step 7): one made-up trip with every
kind of booking runs through the shipped gate, both renderers and both export gates, then a
re-plan drops a booked dinner and the gate stops it -- with reservations.yaml untouched."""

import yaml
from bs4 import BeautifulSoup

from scripts.export_gate import run_export_gate, run_html_gate
from scripts.gate import run_gate
from scripts.orchestration import route_gate_failures
from scripts.render.html_page import render_html_page
from scripts.render.markdown import render_markdown_page
from tests import mech_fixtures as M
from tests import reservation_fixture as F

SKY = {"kind": "預約", "task": "晴空塔線上預約時段票", "due": "2026-05-05", "due_is_hard": True, "poi_id": "skytree"}


def _trip():
    itin = F.itinerary()
    itin["checklist"] = [SKY]
    return itin


def test_every_defect_closes_on_one_trip():
    itin, pm, legs, res = _trip(), F.poi_map(), F.legs(), F.reservations()
    md = render_markdown_page(itin, pm, legs=legs, reservations=res)
    html = render_html_page(itin, pm, legs=legs, reservations=res)
    pois = list(pm.values())
    assert run_export_gate(md, pois, min_days=3, reservations=res)["failures"] == []
    assert run_html_gate(html, pois, min_days=3, reservations=res)["failures"] == []
    s = BeautifulSoup(html, "html.parser")
    assert [t["for"] for t in s.select("section.page.home label.tile")] == [
        "pg-lodging", "pg-transport", "pg-meals", "pg-advisory", "pg-checklist"]
    assert "••••PX" in s.select_one('section[data-pg="transport"]').get_text()
    assert [b.get_text() for b in s.select('section[data-pg="meals"] .bk')] == ["自理", "還要訂", "已訂"]
    cl = s.select_one('section[data-pg="checklist"]').get_text()
    assert "晴空塔線上預約時段票" not in cl and "訂上野示意洋食 13:00，3 位" in cl
    assert "## 交通" in md and "## 餐廳" in md and "••••3907" in md
    assert not any(ref in md + html for ref in F.REFS)


def test_dropping_a_booked_place_stops_and_leaves_the_file_alone(tmp_path):
    res = F.reservations()
    path = tmp_path / "reservations.yaml"
    path.write_text(yaml.safe_dump(res, allow_unicode=True), encoding="utf-8")
    before = path.read_bytes()
    itin = _trip()
    itin["days"][1]["rows"] = [r for r in itin["days"][1]["rows"] if r.get("poi_id") != "kappo"]

    r = run_gate(list(F.poi_map().values()), itin, advisory={"items": []},
                 **M.rederive_kwargs(legs=F.legs()), reservations=yaml.safe_load(path.read_text(encoding="utf-8")))
    dropped = [f for f in r["failures"] if f.startswith("reservation has no row")]
    assert dropped == ["reservation has no row: 2026-05-13 押上示意割烹"]
    assert route_gate_failures(dropped) == "tripwork:record-reservation"
    assert path.read_bytes() == before
