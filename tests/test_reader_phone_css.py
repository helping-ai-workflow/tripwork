"""v1.1 phone stylesheet: parsed rules with their @media context, never substring needles."""
from tests.css_rules import has

PHONE = dict(media="max")


def test_the_phone_page_never_scrolls_and_only_the_list_card_does():
    assert has("html", "overflow:hidden", **PHONE) or has("body", "overflow:hidden", **PHONE)
    assert has(".page.day", "height:100dvh", **PHONE) and has(".page.home", "height:100dvh", **PHONE)
    assert has(".plist", "overflow-y:auto", **PHONE) and has(".plist", "min-height:120px", **PHONE)
    assert has(".page.home", "overflow-y:auto", **PHONE)       # review I2: a home taller than a short screen
    # an open map row shrinks and scrolls in itself before it may push the list card off a
    # small, locked screen (found on the real trip-e at 360x640)
    assert has(".pmap", "flex:0 1 auto", **PHONE) and has(".pmap", "overflow-y:auto", **PHONE)
    assert not has(".pcal", "display:contents")


def test_header_row_is_a_three_column_grid_and_the_toggle_sits_top_right():
    assert has(".ymrow", "grid-template-columns:1fr auto 1fr")
    assert has(".bubble", "top:calc(9px + env(safe-area-inset-top,0px))", **PHONE)


def test_selected_day_glows_e2():
    assert has(".mini .stamp.cur", "0 0 12px 3px color-mix(in srgb,var(--c) 70%,transparent)")


def test_phone_map_card_drops_prev_next_and_legend_and_scrolls_chips():
    assert has(".pmap .mnav", "display:none", **PHONE) and has(".pmap .lgd", "display:none", **PHONE)
    assert has(".pmap .chips", "overflow-x:auto", **PHONE) and has(".pmap .chips", "flex-wrap:nowrap", **PHONE)
    assert has(".pmap .mframe.cover", "aspect-ratio:4/3", **PHONE)


def test_photo_fullscreen_is_css_only():
    assert has(".bp:has(.pz:checked)", "position:fixed")


def test_anchor_controls_do_not_look_like_links():
    # v1.1 §8.1 turned stop headers, chips and prev/next into anchors; a default underline
    # showed on the chips (seen in WebKit on the desktop)
    for sel in ("a.hd", "a.chip", ".mnav a"):
        assert has(sel, "text-decoration:none"), sel


def test_the_stamps_second_ring_is_outside_the_circle():
    """v1.1 stamp pick A: the inner ring (an inset box-shadow) cut through the date and
    area name at 30 px; the second ring is now an outline outside the border."""
    from tests.css_rules import rules
    assert has(".stamp", "outline-offset:1.5px")
    inset = [(sels, body) for _m, sels, body in rules() if any(".stamp" in s for s in sels) and "inset" in body]
    assert inset == [], inset


def test_the_chip_row_fades_by_its_scroll_position():
    """v1.1 (user pick S3): a scroll-driven mask on the phone's chip row, with a static
    right-edge fade where scroll timelines are unsupported."""
    assert has(".pmap .chips", "animation-timeline:scroll(x self)", supports="animation-timeline")
    assert has(".pmap .chips", "mask-image:linear-gradient(to right,#000 calc(100% - 32px),transparent)", **PHONE)


def test_tapped_controls_neither_flash_nor_select():
    """iPhone report: tapping a stamp showed a grey box and could select its text."""
    for sel in ("label", "summary", "a.hd", "a.chip", ".vsum"):
        assert has(sel, "-webkit-tap-highlight-color:transparent") and has(sel, "user-select:none"), sel
        assert has(sel, "-webkit-touch-callout:none"), sel
