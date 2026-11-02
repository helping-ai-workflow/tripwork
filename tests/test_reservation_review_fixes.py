"""Whole-branch review findings, each pinned by a test that failed before its fix."""
import base64
import pathlib

import pytest

from scripts import reservation as R
from scripts.export_gate import reservation_leak_failures, run_html_gate
from scripts.gate import run_gate
from scripts.orchestration import route_gate_failures
from scripts.render.html_page import render_html_page
from scripts.render.markdown import render_markdown_page
from tests import mech_fixtures as M
from tests import reservation_fixture as F

ROOT = pathlib.Path(__file__).resolve().parents[1]


# C1 -- the leak check reads what a person sees, not embedded base64 (fonts, map images)
def test_leak_check_ignores_base64_payloads():
    res = {"reservations": [{"date": "2026-05-13", "poi_id": "kappo", "status": "booked", "ref": "K7Q2PX"}]}
    blob = base64.b64encode(b"\x00" * 3 + b"Q2PX" * 50).decode()
    html = (f'<style>@font-face{{src:url(data:font/woff2;base64,Q2PX{blob})}}</style>'
            f'<div style="background-image:url(&quot;data:image/png;base64,AAQ2PXAA&quot;)"></div>'
            f'<p>訂位編號 ••••PX</p>')
    assert reservation_leak_failures(html, res) == []
    assert reservation_leak_failures(html + "<p>K7Q2PX</p>", res)          # a real leak still fails
    assert reservation_leak_failures("<p>••Q2PX</p>", res)                  # and so does a longer tail


def test_leak_check_needs_a_boundary_around_a_tail():
    res = {"reservations": [{"date": "2026-05-13", "poi_id": "kappo", "status": "booked", "ref": "RSV-58213"}]}
    assert reservation_leak_failures("<p>電話 0358213999</p>", res) == []   # digits inside a longer number


# I1 -- the published family page is leak-checked too
def test_publish_passes_reservations_to_the_html_gate():
    src = (ROOT / "scripts" / "publish.py").read_text(encoding="utf-8")
    start = src.index("run_html_gate(")
    call = src[start:src.index("\n    if ", start)]
    assert 'reservations=kwargs["reservations"]' in call, call


# I2 -- a hand-edited file: typed YAML values, a typo, a missing date
def _gate(res, itin=None):
    pois, i = M.build_gate_inputs()
    return run_gate(pois, itin or i, advisory={"items": []}, **M.rederive_kwargs(), reservations=res)


def test_unquoted_yaml_date_still_matches():
    import datetime
    res = {"reservations": [{"date": datetime.date(2026, 8, 1), "poi_id": "poi-1", "status": "booked"}]}
    assert _gate(res)["status"] == "pass", _gate(res)["failures"]


@pytest.mark.parametrize("bad", [
    {"date": "2026-08-01", "poi_id": "poi-1", "status": "Booked"},
    {"poi_id": "poi-1", "status": "booked"},
    {"date": "2026-08-01", "poi_id": "poi-1", "status": "booked", "time": 1140},
])
def test_an_invalid_file_fails_the_gate_and_routes_to_its_writer(bad):
    r = _gate({"reservations": [dict(bad, ref="K7Q2PX")]})
    f = [x for x in r["failures"] if x.startswith("reservation file invalid:")]
    assert f and route_gate_failures(f) == "tripwork:record-reservation"
    assert not any("K7Q2PX" in x for x in r["failures"])                    # never echo the number


def test_md_does_not_crash_on_an_unknown_status():
    res = {"reservations": [{"date": "2026-05-13", "poi_id": "kappo", "status": "Booked"}]}
    render_markdown_page(F.itinerary(), F.poi_map(), legs=F.legs(), reservations=res)


# I3 -- the traveller's details route back to the stage that writes them
def test_detail_text_failures_route_to_record_reservation():
    res = {"reservations": [{"date": "2026-08-01", "poi_id": "poi-1", "status": "booked",
                             "details": [{"label": "取票", "value": "みどりの窓口"}]}]}
    f = [x for x in _gate(res)["failures"] if "gloss" in x]
    assert f and all(x.startswith("reservation details: ") for x in f)
    assert route_gate_failures(f) == "tripwork:record-reservation"


# I5 -- an old 預約 line without poi_id is never hidden by a date coincidence
def test_a_line_without_poi_id_is_not_hidden_by_a_shared_due():
    pm = F.poi_map()
    pm["kappo"]["booking"] = {"required": True, "opens_at": "2026-04-13 10:00"}
    itin = F.itinerary()
    itin["checklist"] = [{"kind": "預約", "task": "新幹線劃位", "due": "2026-04-13 10:00", "due_is_hard": True}]
    assert "新幹線劃位" in [i["task"] for i in R.visible_checklist(itin, F.legs(), F.reservations(), pm)]


# I6 -- the migration note tells a trip with flights what the new gate check needs
def test_changelog_migration_names_the_flight_arrive_check():
    top = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").split("\n## ")[1]
    mig = top[top.index("### Migration"):]
    assert "arrive" in mig and "flight" in mig


# re-graded minor 7 -- U1 renamed 入境規定 everywhere the user reads or the agent copies
@pytest.mark.parametrize("path", ["skills/tripwork-export-artifact/SKILL.md", "skills/itinerary-synthesis/SKILL.md"])
def test_no_old_name_left(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    assert "入境規定" not in text.replace("出入境規定", "")


# re-graded minor 6 -- every fixed string the reader adds passes the text checks (spec §7)
def test_fixed_reader_strings_pass_the_text_checks():
    from scripts.render.reader import bookings as B
    from scripts.text_hygiene import ai_tone_failures, jargon_failures, kana_gloss_failures
    fixed = "\n".join(["・建議，可換別家", "建議", *B.EMPTY.values(), *R.LABEL.values(), "訂位", "待訂", "出入境規定"])
    assert ai_tone_failures(fixed) == [] and kana_gloss_failures(fixed) == [] and jargon_failures(fixed, []) == []
