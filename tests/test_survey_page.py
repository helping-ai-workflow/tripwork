"""v2.1.0 §10: the survey's list page -- the reader's own stop card per place (the user's
pick P1), the score where a trip shows the time; no itinerary needed, no script needed."""
import pathlib

import pytest
import yaml
from bs4 import BeautifulSoup

from scripts import survey_table as st
from scripts.export_gate import html_safety_failures, run_html_gate
from scripts.paths import artifact_path, deliverable_paths
from scripts.render import survey_page as sp

BRIEF = {"slug": "t", "mode": "survey", "short_name": "府城散步",
         "destination": {"country": "台灣", "city": "臺南市中西區", "local_lang": "zh-TW"}, "categories": ["吃的"]}


def _poi(pid, name, cat, **kw):
    p = {"id": pid, "name_display": name, "name_local": name, "category": cat, "district": "中西區",
         "verify_status": "verified", "hours": {"open": "10:00", "close": "18:00"},
         "geocode": {"lat": 25.13, "lng": 121.50, "geocode_source": "nominatim"},
         "sources": [{"url": f"https://{pid}.example/", "lang": "zh-TW", "site": "示意官網", "official": True}]}
    p.update(kw)
    return p


POIS = [_poi("c", "示意咖啡", "cafe", rating={"platform": "Google", "score": 4.8, "count": 17,
                                              "source_url": "https://r.example/c", "as_of": "2030-01-01"}),
        _poi("m", "赤崁樓", "museum", closed_days=["monday"], intro="公共浴場",
             address_local="臺南市中西區示意路2號"),
        _poi("u", "示意未查", "cafe", verify_status="unverified")]


def _soup(pois=POIS, brief=BRIEF):
    return BeautifulSoup(sp.render(pois, brief), "html.parser")


def test_groups_follow_the_table_presets():
    s = _soup()
    assert [h.get_text(" ", strip=True) for h in s.select("h2.sg")] == ["吃的 1", "景點 1"]
    assert [x.select_one(".n").get_text() for x in s.select(".stop")] == ["示意咖啡", "赤崁樓"]


def test_the_score_sits_where_a_trip_shows_the_time():
    head = _soup().select(".stop")[0].select_one(".t")
    assert head.select_one("b").get_text() == "4.8" and head.select_one("small").get_text() == "17 則"
    head = _soup().select(".stop")[1].select_one(".t")
    assert head.select_one("b").get_text() == "—" and head.select_one("small").get_text() == "無評分"


def test_the_one_line_and_the_details_use_the_table_text():
    stops = _soup().select(".stop")
    assert stops[1].select_one(".one").get_text() == "10:00–18:00・週一公休"
    dl = {dt.get_text(): dd.get_text(" ", strip=True) for dt, dd in zip(stops[1].select("dt"), stops[1].select("dd"))}
    assert dl["營業"] == st.hours_text(POIS[1]["hours"]) and dl["公休"] == "週一公休" and dl["介紹"] == "公共浴場"
    assert "停留" not in dl and "安排" not in dl
    assert stops[1].select_one(".drvbtn")                          # the address keeps its taxi sheet
    dl0 = {dt.get_text(): dd.get_text(" ", strip=True) for dt, dd in zip(stops[0].select("dt"), stops[0].select("dd"))}
    assert dl0["評分"] == "4.8（Google，17 則・評論少）"


def test_with_dates_the_closed_days_are_marked():
    brief = dict(BRIEF, dates={"start": "2030-01-07", "end": "2030-01-08"})      # a Monday and a Tuesday
    assert _soup(brief=brief).select(".stop")[1].select_one(".one").get_text() == "10:00–18:00・1/7（一）公休"


def test_the_page_is_safe_and_needs_no_itinerary(tmp_path):
    t = tmp_path / "trips" / "t"
    for name, doc in (("trip-brief.yaml", BRIEF), ("verified-pois.yaml", {"pois": POIS})):
        p = artifact_path(t, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    assert st.main([str(t), "--page"]) == 0
    page = deliverable_paths(t, BRIEF)["html"]
    assert page.name == "府城散步 清單.html" and html_safety_failures(page.read_text(encoding="utf-8")) == []


def test_a_bad_short_name_stops_the_page(tmp_path, capsys):
    t = tmp_path / "trips" / "t"
    bad = dict(BRIEF, short_name="名/字")
    for name, doc in (("trip-brief.yaml", bad), ("verified-pois.yaml", {"pois": POIS})):
        p = artifact_path(t, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    assert st.main([str(t), "--page"]) == 2
    assert "short_name" in capsys.readouterr().err


def test_html_safety_flags_script_and_bad_href():
    assert html_safety_failures('<a href="javascript:alert(1)">x</a>')
    assert html_safety_failures("<script>alert(1)</script>")
    from scripts.render.reader.page import licence_notice
    assert html_safety_failures("<!doctype html>" + licence_notice() + '<a href="https://ok.example/">x</a>') == []


def test_run_html_gate_calls_the_same_safety_check(monkeypatch):
    import scripts.export_gate as eg
    monkeypatch.setattr(eg, "html_safety_failures", lambda html: ["SENTINEL"])
    assert "SENTINEL" in run_html_gate("<html><body><section class='page day'></section></body></html>", [])["failures"]


def test_page_refuses_a_planned_trip_and_keeps_its_reader(tmp_path, capsys):
    """Final review: on a trip brief the html deliverable is the reader; --page must not
    overwrite it."""
    from tests import mech_fixtures as M
    t, _w = M.build_full_trip(tmp_path)
    brief = yaml.safe_load(artifact_path(t, "trip-brief.yaml").read_text(encoding="utf-8"))
    reader = deliverable_paths(t, brief)["html"]
    before = reader.read_bytes()
    assert st.main([str(t), "--page"]) == 2
    assert reader.read_bytes() == before and "survey" in capsys.readouterr().err
