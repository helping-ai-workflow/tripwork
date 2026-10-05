"""v1.0 release e2e closure (spec §7, 8-step gate step 7): the tour in
tests/e2e_v1_fixture.py -- a month boundary, a hotel change on a long move, a last
day with no lodging -- and a one-day trip go through the real CLIs in pipeline order:
itinerary gate → export (md + html with the photo side-file, assembled as the
export-artifact skill says) → day_maps (injected tiles) → html again with the maps →
export gate → next_stage. Every v1.0 surface is asserted on the delivered page.
Routing, calendar, seasonal, transit and cost come from mech_fixtures' base trip and
are thin (one cluster, no line items): this closure is about the reader data, not the
routing or cost stages, which have their own e2e files."""
import io
import pathlib

import pytest
import yaml
from bs4 import BeautifulSoup

from scripts.gate import poi_pool, run_gate
from scripts.paths import artifact_path, deliverable_paths, report_path, work_dir_for
from scripts.media_merge import apply_media, load_media
from scripts.render.heading import dates_line, trip_title
from scripts.render.html_page import render_html_page
from scripts.render.markdown import render_markdown_page
from tests import e2e_v1_fixture as F
from tests import mech_fixtures as M
from tests import reader_fixture as R
from tests.cli_helpers import run_main

ROOT = pathlib.Path(__file__).resolve().parent.parent
# 朝市 is on D1 and D2 of the tour: its photo must be embedded once (the P7 corpus defect)
PHOTO = "data:image/png;base64,UEhPVE8tQVNBSUNISQ=="
MEDIA = {"media": {"hak-asaichi": {"photo": {"data": PHOTO, "width": 640, "height": 480},
                                   "photo_attribution": {"author": "Wiki 使用者", "license": "CC-BY-SA-4.0",
                                                         "source_url": "https://commons.example/asaichi"},
                                   "photo_source": "wikimedia"}}}
V1_GATE_CHECKS = ("day_chain_complete", "moves_recorded", "alternatives_valid", "day_theme_valid",
                  "checklist_structured", "sources_complete", "lodging_area_labelled", "brief_names_valid")
HTML_CHECKS = ("scripts_whitelisted", "img_src_offline", "licences_present", "expandables_are_details",
               "legs_have_mode_icon", "map_attribution_present")


def _cli(script, *args):
    return run_main("scripts." + script.removesuffix(".py"), args)



def _brief(src):
    b = M.trip_brief()
    b.update(slug=src["slug"], dates=src["dates"], destination=src["destination"])
    return b


def _tile(z, x, y):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (256, 256), ((x * 67) % 256, (y * 131) % 256, 180)).save(buf, "PNG")
    return buf.getvalue()


def _trip(tmp_path, itin, brief, accommodations, legs, slug):
    t, w = M.build_full_trip(tmp_path, slug=slug)
    cands = {"candidates": [{k: p[k] for k in ("id", "name_local", "name_display", "category")}
                            | {"sources": [{"url": p["sources"][0]["url"], "lang": "ja"}]} for p in F.pois()]}
    for name, doc in (("trip-brief.yaml", brief), ("candidates.yaml", cands),
                      ("verified-pois.yaml", {"pois": F.pois()}),
                      ("accommodations.yaml", accommodations), ("legs.yaml", legs),
                      ("advisory.yaml", R.ADVISORY), ("itinerary.yaml", itin),
                      ("verified-pois-media.yaml", MEDIA)):
        M.write_artifact(artifact_path(t, name), doc)
    for p in t.glob("*.*"):                               # the base trip's deliverables
        p.unlink()
    return t, w


def _export(t, maps=None):
    """export-artifact's md + html, from the artifacts on disk, assembled as its
    skill says: poi_pool(verified-pois, accommodations), overlaid with the photo side-file."""
    def load(name):
        return yaml.safe_load(artifact_path(t, name).read_text(encoding="utf-8"))
    brief, acc, itin = load("trip-brief.yaml"), load("accommodations.yaml"), load("itinerary.yaml")
    poi_map = poi_pool(load("verified-pois.yaml")["pois"], acc)
    poi_map = apply_media(poi_map, load_media(artifact_path(t, "verified-pois-media.yaml")))
    paths = deliverable_paths(t, brief)
    paths["md"].write_text(render_markdown_page(itin, poi_map, load("cost.yaml"), brief=brief), encoding="utf-8")
    html = render_html_page(itin, poi_map, brief=brief, accommodations=acc, advisory=load("advisory.yaml"),
                            legs=load("legs.yaml"), maps=maps, cost=load("cost.yaml"))
    paths["html"].write_text(html, encoding="utf-8")
    return html


def _run(t, w):
    assert _cli("gate", t).returncode == 0, _cli("gate", t).stdout
    rep = yaml.safe_load(report_path(w, "gate-report.yaml").read_text(encoding="utf-8"))
    checks = {c["name"]: c["passed"] for c in rep["checks"]}
    assert all(checks[n] is True for n in V1_GATE_CHECKS), checks
    return rep


@pytest.fixture
def tour(tmp_path):
    t, w = _trip(tmp_path, F.tour(), _brief(F.tour_brief()), F.accommodations(), F.LEGS, "2026-10-hokkaido")
    _run(t, w)
    _export(t)
    pytest.importorskip("PIL")      # the [maps] extra; CI installs it with [dev]
    from scripts.day_maps import build
    maps = build(t, w, fetch=_tile)
    html = _export(t, maps=maps)
    r = _cli("export_gate", t)
    assert r.returncode == 0, r.stdout + r.stderr
    rep = yaml.safe_load(report_path(w, "export-gate-report.yaml").read_text(encoding="utf-8"))
    checks = {c["name"]: c["passed"] for c in rep["checks"]}
    assert all(checks[f"html_{n}"] is True for n in HTML_CHECKS + ("media_landed",)), checks  # merge_reports prefixes html_
    return t, w, maps, BeautifulSoup(html, "html.parser")


def test_the_fixtures_pass_the_real_gate():
    # tests/reader_fixture.py claims this for itself; nothing asserted it before v1.0 P7
    kw = dict(advisory=R.ADVISORY, routing={"hops": []}, cost={"items": []})
    for pois, itin, acc, legs, brief in (
            (R.POIS, R.itinerary(), R.ACCOMMODATIONS, {"legs": []}, R.brief()),
            (F.pois(), F.tour(), F.accommodations(), F.LEGS, F.tour_brief()),
            (F.pois(), F.day_trip(), {"stops": []}, {"legs": []}, F.day_trip_brief())):
        rep = run_gate(pois, itin, accommodations=acc, legs=legs, trip_brief=brief, **kw)
        assert rep["status"] == "pass", rep["failures"]


def test_the_tour_reaches_complete(tour):
    t, w, _maps, _soup = tour
    r = _cli("next_stage", t, "--work-dir", w)
    assert yaml.safe_load(r.stdout)["next"] == "complete", r.stdout


def test_the_hotel_change_day_splits_its_map_and_names_both_hotels(tour):
    _t, _w, maps, soup = tour
    assert len(maps["days"]["2026-10-31"]) == 2                      # 函館 segment + 洞爺 segment
    d2 = soup.select_one('section.page.day[data-pg="d2"]')
    assert len(d2.select(".mv-d2-all .seg")) == 2 and d2.select(".mv-d2-all .mimg")
    assert d2.select(".mapc .route") == []                            # user check: no 路線列
    areas = [s.select_one("small").get_text() for s in soup.select(".hcal .stamp")]
    assert areas[0] != areas[1]                                      # the two nights' areas
    stays = [li.select_one("span").get_text() for li in soup.select(".hside .trip ol > li") if li.select_one("span")]
    assert "函館示意飯店" in stays[0] and "示之風度假村" in stays[1]   # the 旅程 card names both hotels
    # the export-artifact skill passes cost=: the card is 旅程與費用 with the run's total (review I5)
    card = soup.select_one(".hside .trip")
    total = yaml.safe_load(artifact_path(_t, "cost.yaml").read_text(encoding="utf-8"))["total"]
    assert card.select_one("h3").get_text() == "旅程與費用"
    assert card.select_one(".tt.sum em").get_text() == f"¥{round(total):,}"
    lodging = [b.get_text() for b in soup.select('[data-pg="lodging"] .lrow b')]
    assert lodging == ["函館示意飯店", "示之風度假村"]


def test_the_month_boundary_is_one_card_and_one_run_of_weeks(tour):
    _t, _w, _maps, soup = tour
    # v1.1 §6.2: one card titled with the month range (was one card per month)
    assert [h.get_text() for h in soup.select(".home .months h3")] == ["2026 年 10～11 月"]
    assert soup.select_one('.home .month label.stamp[for="pg-d3"] b').get_text() == "11/1"
    stamps = soup.select(".hcal .stamp")
    assert [s["for"] for s in stamps] == ["pg-d1", "pg-d2", "pg-d3", "pg-d4"]
    assert all(s.select_one("svg.ring") for s in stamps)


def test_the_last_day_returns_and_has_no_hotel_pins(tour):
    _t, _w, _maps, soup = tour
    assert soup.select(".hcal .stamp")[-1].select_one("small").get_text() == "返程"
    d4 = soup.select_one('section.page.day[data-pg="d4"]')
    assert [c.get_text() for c in d4.select(".mapc .chips a.chip")][-1] != "回家"


def test_a_day_trip_has_no_lodging_anywhere(tmp_path):
    t, w = _trip(tmp_path, F.day_trip(), _brief(F.day_trip_brief()), {"stops": []}, {"legs": []},
                 "2026-11-hakodate-day")
    _run(t, w)
    soup = BeautifulSoup(_export(t), "html.parser")
    assert _cli("export_gate", t).returncode == 0
    assert soup.select_one('.hside label[for="pg-lodging"] small').get_text() == "0 間"
    assert soup.select_one('[data-pg="lodging"] .empty')
    assert soup.select_one(".hcal .stamp small").get_text() == "返程"
    chips = [c.get_text() for c in soup.select('section.page.day[data-pg="d1"] .mapc .chips a.chip')]
    assert "出發" not in chips and "回家" not in chips


def test_a_photo_on_two_days_is_embedded_once_and_lands(tour):
    t, _w, _maps, soup = tour
    html = deliverable_paths(t, yaml.safe_load(artifact_path(t, "trip-brief.yaml").read_text()))["html"].read_text()
    assert len(soup.select('.stop[data-poi="hak-asaichi"] figure.bp .bpi')) == 2
    assert html.count(PHOTO) == 1


def test_every_deliverable_is_headed_by_the_headline(tour):
    t, _w, _maps, soup = tour
    brief = yaml.safe_load(artifact_path(t, "trip-brief.yaml").read_text(encoding="utf-8"))
    itin = yaml.safe_load(artifact_path(t, "itinerary.yaml").read_text(encoding="utf-8"))
    paths = deliverable_paths(t, brief)
    head, sub = trip_title(brief, itin), dates_line(brief, itin)
    assert head == brief["headline"]["text"] and sub.startswith(brief["short_name"])
    assert paths["md"].read_text(encoding="utf-8").splitlines()[0] == f"# {head}"
    assert soup.select_one("h1.headline").get_text() == head
