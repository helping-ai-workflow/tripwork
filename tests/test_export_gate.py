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

def test_export_gate_fail_empty_deliverable():   # TW-015
    r = run_export_gate("", [], min_days=3)
    assert r["status"] == "fail"
    assert any("empty" in f.lower() for f in r["failures"])
    assert _names("deliverable_has_content", r) is False

def test_export_gate_fail_too_few_day_sections():   # TW-015
    r = run_export_gate(CLEAN, [BOOKABLE], min_days=3)   # CLEAN has 1 day
    assert r["status"] == "fail"
    assert any("too few day" in f.lower() for f in r["failures"])
    assert _names("deliverable_has_content", r) is False

def test_export_gate_pass_when_min_days_met():   # TW-015
    md = "# 行程\n" + "".join(f"### Day {i}\n| a | [x](https://a) |\n" for i in range(1, 4))
    r = run_export_gate(md, [], min_days=3)
    assert _names("deliverable_has_content", r) is True

def test_export_gate_min_days_optional_backward_compat():
    r = run_export_gate(CLEAN, [BOOKABLE])   # no min_days -> content check still present, passes
    assert _names("deliverable_has_content", r) is True

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


# ── D3: japanese_glossed ──────────────────────────────────────────────────────

# Minimal valid skeleton: has a "### " heading so deliverable_has_content passes.
_KANA_BASE = "### Day 1\n\n| 時段 | 行程 |\n|---|---|\n"

def test_kana_no_gloss_fails():
    """Katakana on a line without a （...）paren must hard-fail."""
    md = _KANA_BASE + "| 12:00 | ジンギスカン 好吃 |\n"
    r = run_export_gate(md, [])
    assert r["status"] == "fail", r["failures"]
    assert any("gloss" in f or "japanese" in f.lower() for f in r["failures"]), r["failures"]

def test_kana_with_fullwidth_paren_passes():
    """Katakana + （中文 gloss）on same line → no gloss failure."""
    md = _KANA_BASE + "| 12:00 | ジンギスカン（成吉思汗烤羊肉）好吃 |\n"
    r = run_export_gate(md, [])
    assert not any("gloss" in f or "japanese" in f.lower() for f in r["failures"]), r["failures"]

def test_han_only_no_false_positive():
    """Pure Han/Chinese characters must NOT trigger the gloss check."""
    md = _KANA_BASE + "| 12:00 | 午餐 |\n"
    r = run_export_gate(md, [])
    assert not any("gloss" in f or "japanese" in f.lower() for f in r["failures"]), r["failures"]

def test_japanese_glossed_check_present():
    """A check named 'japanese_glossed' must always appear in the report."""
    md = _KANA_BASE + "| 12:00 | 午餐 |\n"
    r = run_export_gate(md, [])
    names = [c["name"] for c in r["checks"]]
    assert "japanese_glossed" in names

# ── PR4: photo attribution presence + distributability (markdown gate) ──

def _photo_poi(over=None):
    p = {"id": "p1", "photo": {"url": "https://upload.wikimedia.org/x.jpg"},
         "photo_attribution": {"author": "A", "license": "CC0", "source_url": "https://a.example"},
         "photo_source": "wikimedia"}
    if over:
        p.update(over)
    return p

def test_md_photo_without_attribution_fails():
    pois = [{"id": "p1", "photo": {"data": "data:image/png;base64,iVB"}}]
    r = run_export_gate(CLEAN, pois)
    assert r["status"] == "fail"
    assert _names("photo_has_attribution", r) is False

def test_md_photo_with_attribution_passes():
    r = run_export_gate(CLEAN, [_photo_poi()])
    assert _names("photo_has_attribution", r) is True
    assert _names("no_nondistributable_photo_source", r) is True

def test_md_whitespace_attribution_fails():   # step-8 hardening: bare truthiness bypass
    pois = [{"id": "p1", "photo": {"url": "https://x/y.jpg"},
             "photo_attribution": {"author": "  ", "license": "\t", "source_url": " "},
             "photo_source": "wikimedia"}]
    r = run_export_gate(CLEAN, pois)
    assert r["status"] == "fail"
    assert _names("photo_has_attribution", r) is False

def test_md_google_photo_source_non_distributable_fails():
    r = run_export_gate(CLEAN, [_photo_poi({"photo_source": "google"})])
    assert r["status"] == "fail"
    assert _names("no_nondistributable_photo_source", r) is False

def test_md_photo_checks_present():
    r = run_export_gate(CLEAN, [])
    names = [c["name"] for c in r["checks"]]
    assert "photo_has_attribution" in names
    assert "no_nondistributable_photo_source" in names


# ── G6: no internal jargon (poi-id tokens / must_do) in user-facing text ──

_JARGON_BASE = "### Day 1\n\n| 時段 | 行程 |\n|---|---|\n"
_JARGON_POIS = [{"id": "hak-goryokaku"}, {"id": "lodge-toya-nonokaze"}, {"id": "sap-keio-plaza"}]

def test_export_gate_fails_on_leaked_poi_id():
    # the confirmed Hokkaido leak: an internal poi_id smuggled into row text.
    md = _JARGON_BASE + "| 18:00 | 改五稜郭タワー（五稜郭塔）(hak-goryokaku) 展望夜景 |\n"
    r = run_export_gate(md, _JARGON_POIS)
    assert r["status"] == "fail"
    assert _names("no_internal_jargon", r) is False
    assert any("hak-goryokaku" in f and "leaked" in f for f in r["failures"])

def test_export_gate_fails_on_must_do():
    md = _JARGON_BASE + "| 19:00 | 蟹会席（螃蟹會席）must_do |\n"
    r = run_export_gate(md, [])
    assert r["status"] == "fail"
    assert _names("no_internal_jargon", r) is False
    assert any("must_do" in f for f in r["failures"])

def test_export_gate_clean_passes_jargon():
    r = run_export_gate(CLEAN, [BOOKABLE])
    assert _names("no_internal_jargon", r) is True

def test_export_gate_no_false_positive_on_romaji():
    # a romaji parenthetical of id-like shape (word-word) that is NOT a poi id must NOT
    # trip the check — literal-id keying off the authoritative id set, zero false positive.
    md = _JARGON_BASE + "| 13:00 | 成吉思汗烤肉(grilled-lamb) 好吃 |\n"
    r = run_export_gate(md, _JARGON_POIS)
    assert _names("no_internal_jargon", r) is True

def test_export_gate_jargon_check_present():
    r = run_export_gate(CLEAN, [])
    assert "no_internal_jargon" in [c["name"] for c in r["checks"]]

def test_export_gate_catches_md_escaped_must_do():
    # markdown.md_escape turns must_do -> must\_do; the gate scans the RENDERED md and
    # must still catch the escaped form (else a real synthesis leak ships silently).
    from scripts.render.markdown import render_day_table
    md = render_day_table({"label": "D1", "rows": [{"slot": "meal", "text": "會席 must_do"}]}, {})
    assert "must\\_do" in md                        # confirm the escaped form is what ships
    assert _names("no_internal_jargon", run_export_gate(md, [])) is False

def test_export_gate_catches_md_escaped_underscore_poi_id():
    from scripts.render.markdown import render_day_table
    md = render_day_table({"label": "D1", "rows": [{"slot": "visit", "text": "夜景(hak-yam_yakei)"}]}, {})
    assert "(hak-yam\\_yakei)" in md                 # underscore escaped in the md target
    assert _names("no_internal_jargon", run_export_gate(md, [{"id": "hak-yam_yakei"}])) is False


def test_find_row_ignores_heading_uses_table_row():   # TW-044
    bookable = {"id": "milford", "name_local": "Milford Sound", "name_display": "Milford Sound",
                "verify_status": "verified", "booking": {"required": True},
                "sources": [{"url": "https://milford.example", "official": True}]}
    # heading names the POI (no link); the actual TABLE row lacks the official link
    md = ("### Day 1 — Milford Sound\n\n| 時段 | 行程 |\n|---|---|\n"
          "| 09:00 | [Milford Sound](https://www.google.com/maps/search/?api=1&query=Milford) 郵輪 |\n")
    r = run_export_gate(md, [bookable])
    assert r["status"] == "fail"
    assert any("official source link" in f for f in r["failures"])
