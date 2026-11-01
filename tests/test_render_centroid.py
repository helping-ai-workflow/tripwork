"""A `cluster_fallback` coordinate is the district centroid, not the venue. The
deliverable must say so for every scheduled POI and every night's lodging that
carries one.

This used to be a sentence in source-verify asking the agent to tell the user. The
consumer corpus showed it was never done: trip-c schedules verified
`cluster_fallback` POIs and trip-b chose two `cluster_fallback`
lodgings, and neither deliverable says a word. So the renderers now emit the
disclosure from the data, via `scripts/render/centroid.py`.
"""
import pytest

from scripts.render.html_page import render_html_page
from scripts.render.markdown import render_markdown_page
from scripts.text_hygiene import jargon_failures, kana_gloss_failures


def _poi(pid, name, source, zh=None):
    p = {"id": pid, "name_display": name, "name_local": name, "verify_status": "verified",
         "geocode": {"lat": 25.0, "lng": 121.9, "geocode_source": source},
         "sources": [{"url": f"https://example.com/{pid}"}]}
    if zh:
        p["name_zh"] = zh
    return p


POIS = {
    "centroid-poi": _poi("centroid-poi", "噴水雞肉飯", "cluster_fallback"),
    "exact-poi": _poi("exact-poi", "文化路夜市", "nominatim"),
    "kana-poi": _poi("kana-poi", "すし処", "cluster_fallback", zh="壽司店"),
    "unscheduled": _poi("unscheduled", "沒排進去的點", "cluster_fallback"),
    "centroid-inn": _poi("centroid-inn", "觀止飯店", "cluster_fallback"),
}

ITIN = {
    "title": "測試行程",
    "days": [
        {"date": "2026-10-01", "label": "D1", "lodging": "centroid-inn", "rows": [
            {"time": "12:00", "slot": "lunch", "poi_id": "centroid-poi", "text": "午餐"},
            {"time": "18:00", "slot": "dinner", "poi_id": "exact-poi", "text": "晚餐"},
        ]},
        {"date": "2026-10-02", "label": "D2", "lodging": "centroid-inn", "rows": [
            {"time": "12:00", "slot": "lunch", "poi_id": "centroid-poi", "text": "再吃一次"},
            {"time": "15:00", "slot": "sight", "poi_id": "kana-poi", "text": "點心"},
        ]},
    ],
}


def _disclosed(poi):
    from scripts.render.centroid import centroid_note
    return centroid_note(poi)


def test_centroid_items_are_scheduled_or_lodging_in_first_use_order():
    from scripts.render.centroid import centroid_items
    assert [p["id"] for p in centroid_items(ITIN, POIS)] == [
        "centroid-poi", "centroid-inn", "kana-poi"]


def _line(itin=ITIN):
    from scripts.render.centroid import merged_line
    return merged_line(itin, POIS)


LABELS = {"centroid-poi": "噴水雞肉飯", "centroid-inn": "觀止飯店", "kana-poi": "すし処（壽司店）",
          "exact-poi": "文化路夜市", "unscheduled": "沒排進去的點"}


def test_markdown_discloses_every_centroid_in_one_line():
    """One line for all of them (a trip with ten small restaurants otherwise fills
    出發前確認 with ten copies of the same warning); each place is still named, once."""
    md = render_markdown_page(ITIN, POIS)
    line = _line()
    assert md.count(line) == 1 and md.count("地圖只標到") == 1
    for pid in ("centroid-poi", "centroid-inn", "kana-poi"):
        assert line.count(LABELS[pid]) == 1, pid
    for pid in ("exact-poi", "unscheduled"):
        assert LABELS[pid] not in line, pid


def test_html_discloses_each_centroid_once():
    out = render_html_page(ITIN, POIS)
    for pid in ("centroid-poi", "centroid-inn", "kana-poi"):
        note = _disclosed(POIS[pid])
        assert out.count(note) == 1, (pid, note)
    for pid in ("exact-poi", "unscheduled"):
        assert _disclosed(POIS[pid]) not in out, pid


def test_disclosure_renders_without_an_authored_checklist():
    itin = dict(ITIN, checklist=[])
    assert _line(itin) in render_markdown_page(itin, POIS)
    assert _disclosed(POIS["centroid-inn"]) in render_html_page(itin, POIS)


def test_disclosure_follows_the_authored_checklist():
    itin = dict(ITIN, checklist=["帶悠遊卡"])
    md = render_markdown_page(itin, POIS)
    assert md.count("## 出發前檢查清單") == 1
    assert md.index("帶悠遊卡") < md.index(_line(itin))


def test_no_centroid_no_extra_section():
    """Control, green before and after the fix: with no centroid anywhere the
    renderer must not invent an empty checklist section."""
    pois = {k: dict(v, geocode=dict(v["geocode"], geocode_source="nominatim"))
            for k, v in POIS.items()}
    md = render_markdown_page(ITIN, pois)
    assert "## 出發前檢查清單" not in md


def test_disclosure_passes_the_export_text_hygiene():
    md = render_markdown_page(ITIN, POIS)
    # Without this the test is vacuous: no disclosure text, nothing to fail on.
    assert LABELS["kana-poi"] in _line() and _line() in md
    assert jargon_failures(md, list(POIS.values())) == []
    assert kana_gloss_failures(md) == []
