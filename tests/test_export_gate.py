from scripts.export_gate import run_export_gate

# A booking-required verified POI used by the bookable check.
BOOKABLE = {
    "id": "milford", "name_local": "Milford Sound", "name_display": "Milford Sound",
    "verify_status": "verified", "booking": {"required": True},
    "sources": [{"url": "https://milford.example", "lang": "en", "official": True}],
}

CLEAN = (
    "### Day 1\n\n| 時段 | 行程 |\n|---|---|\n"
    "| 09:00 | [Milford Sound](https://www.google.com/maps/search/?api=1&query=Milford) "
    "· [官網](https://milford.example) 郵輪 \\$120 |\n"
)

def _names(check, report):
    return next(c["passed"] for c in report["checks"] if c["name"] == check)

def test_clean_passes():
    r = run_export_gate(CLEAN, [BOOKABLE])
    assert r["status"] == "pass", r["failures"]

def test_naked_dollar_fails():
    dirty = CLEAN.replace("\\$120", "$120")
    r = run_export_gate(dirty, [BOOKABLE])
    assert r["status"] == "fail"
    assert _names("no_naked_dollar", r) is False

def test_malformed_link_fails():
    dirty = CLEAN.replace("(https://milford.example)", "()")
    r = run_export_gate(dirty, [BOOKABLE])
    assert r["status"] == "fail"
    assert _names("links_well_formed", r) is False

def test_standalone_map_token_fails():
    dirty = (
        "### Day 1\n\n| 時段 | 行程 |\n|---|---|\n"
        "| 09:00 | Milford Sound [地圖](https://maps.example) "
        "· [官網](https://milford.example) 郵輪 \\$120 |\n"
    )
    r = run_export_gate(dirty, [BOOKABLE])
    assert r["status"] == "fail"
    assert _names("poi_name_is_link", r) is False

def test_bookable_missing_official_source_fails():
    dirty = (
        "### Day 1\n\n| 時段 | 行程 |\n|---|---|\n"
        "| 09:00 | [Milford Sound](https://www.google.com/maps/search/?api=1&query=Milford) "
        "郵輪 \\$120 |\n"
    )
    r = run_export_gate(dirty, [BOOKABLE])
    assert r["status"] == "fail"
    assert _names("bookable_has_official_source", r) is False
