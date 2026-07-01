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

def test_md_google_photo_source_is_terminal_nondistributable():
    # P7 (MIGRATED): a google photo is a clean terminal non-distributable state —
    # status stays 'pass' (no re-export loop), distributable flag is False.
    r = run_export_gate(CLEAN, [_photo_poi({"photo_source": "google"})])
    assert r["status"] == "pass", r["failures"]
    assert r["distributable"] is False
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


def test_export_gate_bookable_on_move_row_not_evaded():   # review finding-2
    # a verified booking.required POI scheduled on a move row with from/to must NOT slip
    # past the bookable-official-source check: the move cell must surface the poi name so
    # _find_rows locates it, and the official link must be present to pass.
    from scripts.render.markdown import render_day_table
    bookable = {"id": "trn", "name_local": "特急北斗", "name_display": "特急北斗",
                "verify_status": "verified", "booking": {"required": True},
                "sources": [{"url": "https://jr.example", "official": True}]}
    day = {"label": "D1", "rows": [
        {"slot": "move", "poi_id": "trn", "text": "預訂", "from": "札幌", "to": "函館"}]}
    ok_md = render_day_table(day, {"trn": bookable})
    assert run_export_gate(ok_md, [bookable])["status"] == "pass", \
        run_export_gate(ok_md, [bookable])["failures"]
    # strip the official flag → the official link disappears → gate MUST fail (not evade)
    no_off = {**bookable, "sources": [{"url": "https://review.example", "official": False}]}
    bad_md = render_day_table(day, {"trn": no_off})
    r = run_export_gate(bad_md, [no_off])
    assert r["status"] == "fail"
    assert _names("bookable_has_official_source", r) is False


# ── D2 (2026-07-01 gmaps-deadlink): maps_link_resolvable_form ─────────────────
# links_well_formed is scheme-only, so the 0.23.0 dead `maps/place/?q=place_id:<id>`
# form (still https://) passed the gate green while 38 links were dead. The gate now
# asserts every www.google.com/maps link is a resolvable canonical form.

_DEAD_MAPS = "https://www.google.com/maps/place/?q=place_id:ChIJ_abc123"

def _maps_row(url):
    return f"### Day 1\n\n| 時段 | 行程 |\n|---|---|\n| 09:00 | [大通公園]({url}) |\n"

def test_export_gate_fails_on_dead_maps_place_id_link():
    r = run_export_gate(_maps_row(_DEAD_MAPS), [])
    assert r["status"] == "fail"
    assert _names("maps_link_resolvable_form", r) is False
    assert any("place_id" in f for f in r["failures"])

def test_export_gate_dead_maps_link_is_retryable():
    # a dead maps link is re-render-fixable (the incident: re-render under 0.24.0 fixed
    # all 38) — so it must stay retryable, NOT be mistaken for an un-fixable data defect.
    r = run_export_gate(_maps_row(_DEAD_MAPS), [])
    assert r["retryable"] is True

def test_export_gate_passes_canonical_maps_search_link():
    r = run_export_gate(_maps_row("https://www.google.com/maps/search/?api=1&query=Sapporo"), [])
    assert _names("maps_link_resolvable_form", r) is True

def test_export_gate_passes_canonical_maps_dir_link():
    url = "https://www.google.com/maps/dir/?api=1&origin=A&destination=B"
    r = run_export_gate(_maps_row(url), [])
    assert _names("maps_link_resolvable_form", r) is True

def test_export_gate_fails_empty_maps_search_query():
    # maps_url({}) / a nameless POI renders an empty query -> resolves to nothing
    r = run_export_gate(_maps_row("https://www.google.com/maps/search/?api=1&query="), [])
    assert r["status"] == "fail"
    assert _names("maps_link_resolvable_form", r) is False
    assert any("empty search query" in f for f in r["failures"])

def test_export_gate_fails_whitespace_maps_search_query():
    r = run_export_gate(_maps_row("https://www.google.com/maps/search/?api=1&query=%20%20%20"), [])
    assert r["status"] == "fail"
    assert _names("maps_link_resolvable_form", r) is False

def test_export_gate_allows_resolvable_place_share_link():
    # a POI official source that IS a real, resolvable /maps/place/<name>/@ share link
    # must NOT be rejected — it is not the dead ?q=place_id: form. (adversarial-verify FP)
    url = "https://www.google.com/maps/place/Kinosaki+Onsen/@35.6,134.8,15z"
    r = run_export_gate(_maps_row(url), [])
    assert _names("maps_link_resolvable_form", r) is True

def test_export_gate_allows_maps_viewport_link():
    # /maps/@lat,lng is a resolvable viewport link, not a dead form -> not flagged
    r = run_export_gate(_maps_row("https://www.google.com/maps/@43.06,141.35,15z"), [])
    assert _names("maps_link_resolvable_form", r) is True

def test_export_gate_non_maps_host_link_not_flagged():
    # an official-source (non-maps) https link must NOT be touched by the maps-form check
    r = run_export_gate(_maps_row("https://milford.example/tickets"), [])
    assert _names("maps_link_resolvable_form", r) is True

def test_export_gate_maps_form_check_present():
    r = run_export_gate(CLEAN, [])
    assert "maps_link_resolvable_form" in [c["name"] for c in r["checks"]]
    # CLEAN uses a canonical /maps/search link -> the check passes
    assert _names("maps_link_resolvable_form", r) is True


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
