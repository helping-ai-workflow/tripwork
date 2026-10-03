"""v1.0 P4 — export-gate's HTML checks judge the new reader (spec §6.10)."""
import pytest

from scripts.export_gate import run_html_gate
from scripts.render.reader import render_reader
from tests.reader_fixture import itinerary, poi_map, reader_kwargs


def _html():
    return render_reader(itinerary(), poi_map(), **reader_kwargs())


def _gate(html, **kw):
    return run_html_gate(html, list(poi_map().values()), **{"min_days": 3, "media_count": 1, **kw})


def _check(rep, name):
    return {c["name"]: c["passed"] for c in rep["checks"]}[name]


def test_the_reader_passes():
    rep = _gate(_html())
    assert rep["status"] == "pass", rep["failures"]


@pytest.mark.parametrize("mutate,check", [
    (lambda h: h.replace("</body>", "<script>x()</script></body>"), "scripts_whitelisted"),
    (lambda h: h.replace('url("data:image/', 'url("https://img.example/x.png?', 1), "img_src_offline"),
    (lambda h: h.replace("ISC License", "", 1), "licences_present"),
    (lambda h: h.replace("</body>", '<div class="x"><span class="cv"></span></div></body>'),
     "expandables_are_details"),
    (lambda h: h.replace(" m-walk", "", 1), "legs_have_mode_icon"),
])
def test_each_check_goes_red_on_its_defect(mutate, check):
    rep = _gate(mutate(_html()))
    assert _check(rep, check) is False, rep["failures"]


def test_too_few_day_pages_fail():
    assert _check(_gate(_html(), min_days=4), "deliverable_has_content") is False


def test_map_tiles_need_their_attribution():
    from tests.test_reader_maps import side_file
    html = render_reader(itinerary(), poi_map(), maps=side_file(), **reader_kwargs())
    assert _check(_gate(html), "map_attribution_present") is True
    stripped = html.replace('<p class="attr">© OpenStreetMap contributors</p>', "")
    assert _check(_gate(stripped), "map_attribution_present") is False


def test_every_map_card_with_tiles_carries_the_credit():
    from tests.test_reader_maps import side_file
    html = render_reader(itinerary(), poi_map(), maps=side_file(days=("2026-10-13", "2026-10-14")),
                         **reader_kwargs())
    assert _check(_gate(html), "map_attribution_present") is True
    one_gone = html.replace('<p class="attr">© OpenStreetMap contributors</p>', "", 1)
    assert _check(_gate(one_gone), "map_attribution_present") is False


def test_a_remote_url_in_the_stylesheet_is_not_offline():
    html = _html().replace("</style>", ".x{background:url(https://img.example/a.png)}</style>", 1)
    assert _check(_gate(html), "img_src_offline") is False


def test_the_centring_script_is_admitted_by_its_hash():
    from scripts.render.reader.centre import CENTRE_JS
    html = _html()
    assert f"<script>{CENTRE_JS}</script>" in html
    assert _check(_gate(html), "scripts_whitelisted") is True


def test_a_modified_centring_script_fails():
    from scripts.render.reader.centre import CENTRE_JS
    assert "smooth" in CENTRE_JS                                    # the mutation must actually change it
    html = _html().replace(CENTRE_JS, CENTRE_JS.replace("smooth", "smoot", 1))
    assert _check(_gate(html), "scripts_whitelisted") is False


@pytest.mark.parametrize("tag", ['<script src="https://x.example/a.js"></script>',
                                 '<script type="module">x()</script>', "<SCRIPT>x()</SCRIPT>"])
def test_any_other_script_shape_fails(tag):
    assert _check(_gate(_html().replace("</body>", tag + "</body>")), "scripts_whitelisted") is False


def test_an_inline_event_handler_is_script_too():
    html = _html().replace('<label class="bubble"', '<label onclick="x()" class="bubble"', 1)
    assert _check(_gate(html), "scripts_whitelisted") is False


@pytest.mark.parametrize("inject", [
    '<svg/onload=x()></svg>', '<img/onerror=x() src="data:image/png;base64,AA==">',
    '<iframe srcdoc="&lt;script&gt;x()&lt;/script&gt;"></iframe>', '<iframe src="javascript:x()"></iframe>',
    '<object data="data:text/html,x"></object>', '<embed src="data:text/html,x">',
    "<a href='javascript:x()'>a</a>", "<a href=javascript:x()>a</a>",
    '<form action="javascript:x()"></form>', '<meta http-equiv="refresh" content="0;url=https://x.example/">',
    '<base href="https://x.example/">', "<script>x()",
])
def test_active_content_outside_the_whitelist_fails(inject):
    rep = _gate(_html().replace("</body>", inject + "</body>", 1))
    assert _check(rep, "scripts_whitelisted") is False, inject


def test_text_that_merely_looks_like_a_handler_passes():
    html = _html().replace('aria-label="五稜郭公園"', 'aria-label="五稜郭公園 onigiri= stall"', 1)
    assert "onigiri= stall" in html
    assert _check(_gate(html), "scripts_whitelisted") is True


def test_a_tiled_frame_without_its_credit_fails():
    from tests.test_reader_maps import side_file
    html = render_reader(itinerary(), poi_map(), maps=side_file(), **reader_kwargs())
    assert _check(_gate(html), "map_attribution_present") is True
    from scripts.export_gate import _OSM_TEXT
    one_gone = html.replace(_OSM_TEXT, "", 1)
    assert one_gone != html and _check(_gate(one_gone), "map_attribution_present") is False
    # review I5: the OSMF attribution guidelines do not accept the abbreviation
    abbreviated = html.replace(_OSM_TEXT, _OSM_TEXT.replace("© OpenStreetMap<", "© OSM<"))
    assert abbreviated != html and _check(_gate(abbreviated), "map_attribution_present") is False
    # the user check (2026-10-02) made every credit plain text: no link is required
    # (tests/test_v11_user_check.py::test_the_gate_wants_the_credit_text_not_a_link)


def test_an_in_page_link_must_land_on_a_target():
    """v1.1 §8.1: stops, chips and 來源 are in-page anchors; one pointing nowhere is broken."""
    html = _html()
    assert 'href="#t-d2-s1"' in html and _check(_gate(html), "links_well_formed") is True
    broken = html.replace('id="t-d2-s1"', 'id="t-d2-moved"', 1)
    assert _check(_gate(broken), "links_well_formed") is False


def test_an_expand_marker_in_an_anchor_toggle_is_allowed_elsewhere_not():
    html = _html()
    assert 'class="vsum vopen"' in html and _check(_gate(html), "expandables_are_details") is True
    stray = html.replace("</body>", '<a href="https://x.example/"><span class="cv"></span></a></body>', 1)
    assert _check(_gate(stray), "expandables_are_details") is False
