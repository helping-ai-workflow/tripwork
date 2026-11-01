"""export-gate: no deliverable may carry a reservation number in full (or more of it
than the mask shows). The injection test removes the mask in the shipped renderers and
watches both gates go red -- the guard calls its subject, it does not rebuild it."""
import pytest

from scripts import reservation
from scripts.export_gate import _DATA_DEFECT_MARKERS, run_export_gate, run_html_gate
from scripts.render.html_page import render_html_page
from scripts.render.markdown import render_markdown_page
from tests import reservation_fixture as F

POIS = list(F.poi_map().values())


def _leaks(report):
    return [f for f in report["failures"] if "reservation number leaked" in f]


def test_masked_deliverables_pass():
    res = F.reservations()
    md = render_markdown_page(F.itinerary(), F.poi_map(), legs=F.legs(), reservations=res)
    html = render_html_page(F.itinerary(), F.poi_map(), legs=F.legs(), reservations=res)
    assert _leaks(run_export_gate(md, POIS, min_days=3, reservations=res)) == []
    assert _leaks(run_html_gate(html, POIS, min_days=3, reservations=res)) == []


def test_a_full_number_fails_without_printing_it():
    res = F.reservations()
    f = _leaks(run_export_gate("# x\n\n### D1\n\n預約編號 RSV-58213\n", POIS, reservations=res))
    assert f == ["full reservation number leaked into the deliverable: 2026-05-13 kappo"]
    assert "58213" not in f[0]
    assert any(m in f[0] for m in _DATA_DEFECT_MARKERS)                 # a plugin defect: stop and ask


def test_more_digits_than_the_mask_allows_fail():
    res = F.reservations()
    assert _leaks(run_export_gate("# x\n\n### D1\n\n••58213\n", POIS, reservations=res))


@pytest.mark.parametrize("build", ["check", "publish"])
def test_injected_unmasked_renderers_go_red(monkeypatch, build):
    monkeypatch.setattr(reservation, "mask_ref", lambda ref: str(ref))
    res = F.reservations()
    md = render_markdown_page(F.itinerary(), F.poi_map(), legs=F.legs(), reservations=res)
    html = render_html_page(F.itinerary(), F.poi_map(), legs=F.legs(), reservations=res, build=build)
    assert _leaks(run_export_gate(md, POIS, reservations=res))
    assert _leaks(run_html_gate(html, POIS, reservations=res))
