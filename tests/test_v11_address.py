"""v1.1 topic 3 — TW-096: an opened stop shows its address in the local language, with
a 「給司機看」 button that opens a big-print sheet of the local name and address (the
user's pick A2 on the design board). No script: the sheet is an in-page anchor target."""
import copy
import json
import pathlib

import yaml
from bs4 import BeautifulSoup

from scripts.render.reader import render_reader
from tests.reader_fixture import itinerary, poi_map, reader_kwargs

ROOT = pathlib.Path(__file__).resolve().parent.parent
ADDR = "函館市若松町9-19"
SRC = "https://www.hakodate-asaichi.com/"


def _pm(**over):
    pm = copy.deepcopy(poi_map())
    # name_zh differs from name_local, so the 日文 row shows (as on trip-e)
    pm["hak-asaichi"].update(name_zh="函館早市", address_local=ADDR, address_source=SRC, **over)
    return pm


def _stop(pm=None):
    s = BeautifulSoup(render_reader(itinerary(), pm or _pm(), **reader_kwargs()), "html.parser")
    return s, s.select_one('section[data-pg="d2"] .stop[data-poi="hak-asaichi"]')


def test_an_opened_stop_shows_its_address_with_a_driver_button():
    _s, st = _stop()
    dts = [dt.get_text() for dt in st.select(".in dl > dt")]
    assert "地址" in dts and dts.index("地址") == dts.index("日文") + 1      # right under 日文
    dd = st.select(".in dl > dd")[dts.index("地址")]
    assert dd.select_one("span[lang]")["lang"] == "ja" and dd.select_one("span[lang]").get_text() == ADDR
    btn = dd.select_one("a.drvbtn")
    assert btn.get_text() == "給司機看" and btn["href"] == f'#{st["id"]}-drv'


def test_the_driver_sheet_is_big_print_local_name_and_address_and_closes_back_to_the_stop():
    _s, st = _stop()
    sheet = st.select_one(f'#{st["id"]}-drv')
    assert sheet is not None and "drv" in sheet["class"]
    assert [p.get_text() for p in sheet.select("[lang=ja]")] == ["函館朝市", ADDR]
    assert sheet.select_one("a.drvx")["href"] == f'#{st["id"]}'                # closing keeps the stop open


def test_no_address_means_no_row_and_no_sheet():
    _s, st = _stop(copy.deepcopy(poi_map()))
    assert "地址" not in [dt.get_text() for dt in st.select(".in dl > dt")] and not st.select(".drv, .drvbtn")


def test_a_lodging_shows_its_address_too():
    pm = copy.deepcopy(poi_map())
    pm["hak-hotel"].update(address_local="函館市豊川町12-6", address_source="https://dormy-hotels.com/")
    s = BeautifulSoup(render_reader(itinerary(), pm, **reader_kwargs()), "html.parser")
    st = s.select_one('section[data-pg="d2"] .stop[data-poi="hak-hotel"]')      # D2's timed hotel row
    assert st.select_one("a.drvbtn") and "函館市豊川町12-6" in st.select_one(".drv").get_text()


def test_the_page_with_addresses_passes_the_export_gate():
    from scripts.export_gate import run_html_gate
    pm = _pm()
    html = render_reader(itinerary(), pm, **reader_kwargs())
    rep = run_html_gate(html, list(pm.values()), min_days=1)
    assert rep["status"] == "pass", rep["failures"]


def test_the_schemas_take_an_address_and_its_source():
    for name, path in (("verified-pois.schema.json", ("pois",)), ("candidates.schema.json", ("candidates",))):
        s = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
        props = s["properties"][path[0]]["items"]["properties"]
        assert props["address_local"]["type"] == "string" and props["address_source"]["type"] == "string", name
    acc = json.loads((ROOT / "schemas" / "accommodations.schema.json").read_text(encoding="utf-8"))
    cand = acc["properties"]["stops"]["items"]["properties"]["candidates"]["items"]["properties"]
    assert "address_local" in cand and "address_source" in cand


def test_source_verify_carries_the_address_from_the_candidate(tmp_path):
    from scripts import source_verify_run as svr
    from scripts.paths import artifact_path
    trip, work = tmp_path / "trip", tmp_path / "work"
    (trip / "data").mkdir(parents=True); work.mkdir()
    cand = {"id": "asaichi", "name_local": "函館朝市", "name_display": "函館朝市", "category": "market",
            "address_local": ADDR, "address_source": SRC, "sources": [{"url": SRC, "lang": "ja"}]}
    for name, doc in (("trip-brief.yaml", {"destination": {"country": "JP", "local_lang": "ja"}}),
                      ("candidates.yaml", {"candidates": [cand]})):
        artifact_path(trip, name).write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    code, msgs, _o, pois = svr.run(str(trip), str(work), offline=True)
    assert (pois[0].get("address_local"), pois[0].get("address_source")) == (ADDR, SRC)
    assert code == 0, msgs


# --- the LINE short text is retired (user, 2026-10-01: the HTML reader does the job) ---

def test_there_is_no_line_short_deliverable():
    import importlib.util
    from scripts.paths import DELIVERABLE_SUFFIXES
    assert set(DELIVERABLE_SUFFIXES) == {"md", "html"}
    assert importlib.util.find_spec("scripts.render.line_short") is None
    for skill in ("tripwork-export-artifact", "tripwork-orchestrator"):
        text = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        assert "line_short" not in text and ".txt" not in text and "LINE text" not in text, skill


# --- a stop with no address: noticed, never blocked (user: 不合適不硬放) ---

def test_a_missing_address_is_a_notice_not_a_failure():
    from scripts.gate import run_gate
    from tests import mech_fixtures as M
    pois = M.verified_pois()["pois"]
    kw = M.rederive_kwargs(accommodations=M.accommodations())
    kw["advisory"] = M.advisory()
    rep = run_gate(pois, M.itinerary(), **kw)
    assert rep["status"] == "pass", rep["failures"]
    noticed = " ".join(rep.get("notices") or [])
    # the lodging lives only in accommodations: a verified-pois-only lookup (the v0.33.0
    # C1 shape) would silently skip it
    assert "poi-1" in noticed and "hotel-1" in noticed and "address" in noticed
    for p in pois:
        p["address_local"], p["address_source"] = "函館市五稜郭町44", "https://example.org/"
    for s in kw["accommodations"]["stops"]:
        for c in s["candidates"]:
            c["address_local"], c["address_source"] = "函館市若松町1", "https://example.org/"
    rep2 = run_gate(pois, M.itinerary(), **kw)
    assert rep2["status"] == "pass", rep2["failures"]
    assert not [n for n in rep2.get("notices") or [] if "address" in n], rep2.get("notices")


def test_the_gate_report_schema_takes_notices(tmp_path):
    from scripts.validate_artifact import validate_file
    f = tmp_path / "gate-report.yaml"
    f.write_text(yaml.safe_dump({"status": "pass", "checks": [{"name": "x", "passed": True}], "failures": [],
                                 "notices": ["no address for poi-1 (給司機看 not shown)"]}), encoding="utf-8")
    assert validate_file(str(f))[0] == 0, validate_file(str(f))[1]


def test_the_markdown_row_carries_the_address():
    from scripts.render.markdown import _poi_cell
    cell = _poi_cell({"name_local": "函館朝市", "address_local": ADDR}, "早餐")
    assert f"· 地址 {ADDR} · 早餐" in cell
    assert "地址" not in _poi_cell({"name_local": "函館朝市"}, "早餐")
