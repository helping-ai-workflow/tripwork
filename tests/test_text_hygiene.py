"""Shared content-hygiene helpers (scripts/text_hygiene.py) used by BOTH the canonical
itinerary-gate (gate.py) and the render-layer export gates (export_gate.py).

jargon_failures  — internal (poi-id) tokens / literal must_do leaked into user-facing text.
kana_gloss_failures — an untranslated kana run on a line with no （中文）gloss.
"""
from scripts.text_hygiene import jargon_failures, kana_gloss_failures, kana_name_without_gloss


class TestJargon:
    def test_poi_id_token(self):
        f = jargon_failures("夜景(hak-goryokaku)好看", [{"id": "hak-goryokaku"}])
        assert any("hak-goryokaku" in x and "leaked" in x for x in f)

    def test_must_do(self):
        assert any("must_do" in x for x in jargon_failures("會席 must_do", []))

    def test_clean(self):
        assert jargon_failures("乾淨的文字", [{"id": "x"}]) == []

    def test_romaji_no_false_positive(self):
        # an id-shaped romaji parenthetical NOT in the poi id set must NOT flag.
        assert jargon_failures("烤肉(grilled-lamb)", [{"id": "hak-goryokaku"}]) == []

    def test_backslash_escaped_must_do(self):
        # markdown md_escape rewrites must_do -> must\_do; the probe still catches it.
        assert any("must_do" in x for x in jargon_failures("會席 must\\_do", []))

    def test_backslash_escaped_underscore_id(self):
        assert any("hak-yam_yakei" in x
                   for x in jargon_failures("(hak-yam\\_yakei)", [{"id": "hak-yam_yakei"}]))

    def test_substring_id_no_false_positive(self):
        # id "p1" must not flag a token "(p10)" — the closing paren prevents it.
        assert jargon_failures("看點(p10)", [{"id": "p1"}]) == []


class TestKanaGloss:
    def test_ungloss_kana_fails(self):
        assert any("gloss" in x for x in kana_gloss_failures("ジンギスカン 好吃"))

    def test_glossed_kana_ok(self):
        assert kana_gloss_failures("ジンギスカン（成吉思汗）") == []

    def test_han_only_no_false_positive(self):
        # pure Han/Chinese (incl. 会) must NOT trigger — Han overlaps ZH/JP.
        assert kana_gloss_failures("午餐 蟹会席") == []

    def test_per_line_catches_one_bad_line(self):
        text = "好的（gloss）\nスタバ no gloss\n乾淨的中文"
        assert any("gloss" in x for x in kana_gloss_failures(text))

    def test_empty(self):
        assert kana_gloss_failures("") == []


class TestKanaNameGuard:
    """A verified POI whose name_display carries kana must have a non-empty name_zh, so its
    render label (name_display（name_zh）) is glossed. Forward data-quality guard."""

    def test_verified_kana_no_zh_flagged(self):
        assert kana_name_without_gloss({"verify_status": "verified", "name_display": "だるま"}) is True

    def test_verified_kana_with_zh_ok(self):
        assert kana_name_without_gloss(
            {"verify_status": "verified", "name_display": "だるま", "name_zh": "達摩"}) is False

    def test_verified_han_only_ok(self):
        assert kana_name_without_gloss({"verify_status": "verified", "name_display": "五稜郭"}) is False

    def test_unverified_kana_exempt(self):
        assert kana_name_without_gloss({"verify_status": "unverified", "name_display": "だるま"}) is False

    def test_whitespace_zh_flagged(self):
        assert kana_name_without_gloss(
            {"verify_status": "verified", "name_display": "だるま", "name_zh": "  "}) is True

    def test_empty_name_display_kana_local_flagged(self):   # review finding
        # renderers fall back name_display -> name_local; an empty name_display with a kana
        # name_local still renders bare kana, so the guard keys on the rendered name.
        assert kana_name_without_gloss(
            {"verify_status": "verified", "name_display": "", "name_local": "すすきの"}) is True

    def test_han_display_kana_local_ok(self):
        # non-empty Han name_display is the rendered name; name_local kana is not shown.
        assert kana_name_without_gloss(
            {"verify_status": "verified", "name_display": "五稜郭", "name_local": "ごりょうかく"}) is False
