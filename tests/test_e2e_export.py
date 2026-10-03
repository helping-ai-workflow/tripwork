"""E2E closure for v0.5.0 export integrity (spec §5 / CLAUDE.md step-7 fixture).

Renders a real day via render_day_table, runs export-gate on the result, and
asserts a clean render passes; a single fixture exhibiting all four defects at
once fails all four checks.
"""
from scripts.render.markdown import render_day_table
from scripts.export_gate import run_export_gate

BOOKABLE = {
    "id": "milford", "name_local": "Milford Sound", "name_display": "Milford Sound",
    "verify_status": "verified", "booking": {"required": True},
    "sources": [
        {"url": "https://review.example", "lang": "en"},
        {"url": "https://milford.example", "lang": "en", "official": True},
    ],
}

def test_rendered_day_passes_export_gate():
    day = {"label": "Day 1", "rows": [
        {"time": "09:00", "slot": "activity", "poi_id": "milford", "text": "郵輪 $120"},
    ]}
    md = render_day_table(day, {"milford": BOOKABLE})
    report = run_export_gate(md, [BOOKABLE])
    assert report["status"] == "pass", report["failures"]
    # name is the maps link, official source appended, price escaped
    assert "[Milford Sound](https://www.google.com/maps/search/?api=1&query=" in md
    assert "· [官網](https://milford.example)" in md
    assert "\\$120" in md and "$120" not in md.replace("\\$120", "")

def test_all_four_defects_fixture_fails_all_checks():
    dirty = (
        "### Day 1\n\n| 時段 | 行程 |\n|---|---|\n"
        # naked $ (D4), standalone 地圖 token + dead-text name (D5),
        # empty link target (D6), no official source on a bookable POI (D2)
        "| 09:00 | Milford Sound [地圖]() 郵輪 $120 |\n"
    )
    report = run_export_gate(dirty, [BOOKABLE])
    failed = {c["name"] for c in report["checks"] if not c["passed"]}
    assert failed == {
        "no_naked_dollar", "links_well_formed",
        "poi_name_is_link", "bookable_has_official_source",
    }, report
    assert report["status"] == "fail"
