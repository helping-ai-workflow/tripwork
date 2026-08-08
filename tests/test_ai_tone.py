"""AI-tone: writing-humanizer distilled to a mechanical, measured gate.

Every pattern here was measured against the 5 real canonical itineraries in
/home/user/hp_workspace/tripwork-workspace/trips/ and carries ZERO false
positives there. EXCLUDED_PATTERNS records what was cut and the measured FP that
cut it, so the lexicon cannot drift into folklore.
"""
import pathlib

import pytest

from scripts.text_hygiene import ai_tone_failures

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _kinds(failures):
    return {f.split(":")[0].replace("AI-tone ", "") for f in failures}


def test_em_dash_is_flagged():
    """31 of 32 canonical hits. Verbatim from 2026-08-chiayi/itinerary.yaml."""
    out = ai_tone_failures("抵嘉義先吃午餐——阿宏師火雞肉飯（光華總店）")
    assert "em_dash" in _kinds(out)
    assert "阿宏師" in out[0]


def test_range_separators_are_not_flagged():
    """The narrowing that makes em_dash safe: real itineraries use U+2013 and
    U+FF5E for ranges. Flagging those would fail every opening-hours line."""
    assert ai_tone_failures("故宮南院 09:00–18:00；毎日11:30～14:00") == []


def test_markdown_bold_and_bold_label_are_distinguished():
    """1 of 32 canonical hits, from 2026-08-chiayi's checklist. Canonical text is
    plain — markdown there is both an AI tell and a layering leak."""
    assert "markdown_bold" in _kinds(ai_tone_failures("收客20:00；**假日不接受訂位** → 建議 18:00 前到"))
    assert "bold_label" in _kinds(ai_tone_failures("- **颱風/大雨**：戶外改室內"))


def test_decorative_emoji_flagged_but_rating_star_and_hazard_sign_exempt():
    """The wide U+2600-27BF range had 6 measured FPs: ★ is a rating unit
    ('Google 4.4★') and ⚠ is a functional hazard marker."""
    assert "decorative_emoji" in _kinds(ai_tone_failures("🚀 出發！✅ 已訂房"))
    assert ai_tone_failures("Google 4.4★ 近 7 千則") == []
    assert ai_tone_failures("⚠ 山路夜間視線差") == []


@pytest.mark.parametrize("text,kind", [
    ("此外，園區內有免費停車。", "slop_word"),
    ("在當今快節奏的時代，旅行成為一種必需。", "slop_template"),
    ("這裡的景色令人嘆為觀止。", "promo_cliche"),
    ("這座廟宇為當地信仰奠定了基礎。", "meaning_stamp"),
    ("希望這對您有幫助！", "chatbot_residue"),
])
def test_zero_hit_lexicons_still_fire_on_their_target(text, kind):
    """These four lexicons measured 0 TP and 0 FP on real canonical data. They
    ship as regression locks, not as fixes — the CHANGELOG says so."""
    assert kind in _kinds(ai_tone_failures(text))


def test_real_place_name_lists_are_never_flagged():
    """rule_of_three was DROPPED: 21 canonical hits, 21 false positives. Verbatim
    corpus lines that must stay clean."""
    for line in ("戶外點（清水地熱、望龍埤、外澳沙灘）排上午",
                 "室內冷氣、常設展豐富、園區水景",
                 "湖景火鍋＋養生足湯＋七彩琉璃光"):
        assert ai_tone_failures(line) == [], line


def test_measured_false_positive_excerpts_stay_clean():
    """One verbatim corpus excerpt per excluded pattern."""
    for line in ("8 人合菜首選：荔枝木悶烤甕窯雞",
                 "這是你指定必訪的一站",
                 "民宿『享受一下』已訂",
                 "礁溪免費足湯泡腳放鬆",
                 "三貂角燈塔小教堂、展示館",
                 "週一營業，作為回程前最後一餐嘉義雞肉飯",
                 "雷雨或強風遊湖船與纜車可能臨時停駛"):
        assert ai_tone_failures(line) == [], line


EXCLUDED_PATTERNS = [
    ("模式10 三段式法則", "rule_of_three", "戶外點（清水地熱、望龍埤、外澳沙灘）排上午", 21),
    ("模式16 表情符號 寬版 U+2600-27BF", "[☀-➿]", "Google 4.4★ 近 7 千則", 6),
    ("模式4 宣傳語 首選/必訪", "首選|必訪|必遊|必吃", "8 人合菜首選：荔枝木悶烤甕窯雞", 5),
    ("模式4 宣傳語 享受/體驗/放鬆", "享受|體驗|放鬆", "民宿『享受一下』已訂", 3),
    ("模式22 過度限定", "可能|似乎|或許", "雷雨或強風遊湖船與纜車可能臨時停駛", 3),
    ("模式7 AI 詞彙 展示/展現", "展示|展現", "三貂角燈塔小教堂、展示館", 1),
    ("模式8 繫動詞迴避", "作為|擁有|設有", "週一營業，作為回程前最後一餐嘉義雞肉飯", 1),
    ("模式7 AI 詞彙 提升/增強/格局", "提升|增強|培養|獲得|格局|關鍵|寶貴|無縫", "格局是住宿文案的房型用語", 0),
    ("模式27 意義蓋章 象徵著/見證了", "象徵著|標誌著|見證了|體現了", "古蹟正當地見證了一個時代", 0),
    ("模式12 虛假範圍 從X到Y", "從.{1,12}到.{1,12}", "行程本身就是一個從 A 到 B 的序列", 0),
]


def test_excluded_patterns_are_absent_from_the_lexicon():
    """Governance pin: a future contributor cannot silently re-add a pattern that
    was measured to false-positive. Re-adding one means editing this list and
    facing its FP count.

    Asserts against the module's lexicon OBJECTS (`_AI_SLOP_WORDS`, `_AI_PROMO`,
    `_AI_CHATBOT` as literal sets; `_AI_SLOP_TEMPLATES`, `_AI_MEANING_STAMP`, and
    the compiled regexes as pattern-string sets), not the module's source text.
    Two traps rule out the more obvious "pattern not in src" check:

    1. scripts/text_hygiene.py's own comments NAME the excluded words -- "首選/
       必訪/必吃/坐落於/享受/體驗/放鬆 are NOT here -- every one was measured as
       real usage in the corpus." A source-substring check fails on the very
       documentation that explains the exclusion.
    2. A shipped pattern may legitimately CONTAIN an excluded word as a
       sub-string of a larger, different pattern: `關鍵` is excluded as a
       standalone slop word, while `發揮[^\\n。]{0,6}(?:關鍵|重要)作用` ships as a
       meaning stamp. Source-substring matching would flag that as a violation
       when it is correct -- the excluded THING is the bare word as a
       standalone trigger, not every string containing it.

    An earlier version of this test guarded with `"|" not in pattern`, which
    silently exempted alternation patterns from the check entirely -- 7 of the
    10 EXCLUDED_PATTERNS entries, including the three highest measured FP
    counts after rule_of_three (首選|必訪|必遊|必吃, 5 FP; 享受|體驗|放鬆, 3 FP;
    可能|似乎|或許, 3 FP). Only 3 of 10 were ever actually pinned. A governance
    check that cannot fail is indistinguishable from one that passed -- the
    exact defect class this release exists to close. This version checks every
    alternation BRANCH of every excluded pattern against the literal sets, and
    every excluded pattern whole against the regex-pattern-string sets, so all
    10 entries are live.
    """
    from scripts import text_hygiene as th

    literals = set(th._AI_SLOP_WORDS) | set(th._AI_PROMO) | set(th._AI_CHATBOT)
    regexes = ({p for p, _ in th._AI_SLOP_TEMPLATES}
               | {p for p, _ in th._AI_MEANING_STAMP}
               | {th._AI_EM_DASH.pattern, th._AI_BOLD.pattern, th._AI_EMOJI.pattern})

    for label, pattern, _excerpt, _fp in EXCLUDED_PATTERNS:
        assert pattern not in regexes, f"{label} was excluded but ships as a regex"
        for branch in (b for b in pattern.split("|") if b):
            assert branch not in literals, (
                f"{label}: '{branch}' was excluded but is a lexicon literal")


def test_gate_reports_no_ai_tone_and_fails_on_an_em_dash():
    """The HEAD-observable half: today run_gate returns 'pass' on this itinerary.

    Deviation from the task brief's literal call: the brief's Step 1 listing
    calls run_gate(pois, itin, **rederive_kwargs()) with no `advisory` kwarg.
    scripts/gate.py's advisory_check treats advisory=None as an unconditional
    "advisory absent" failure (verified: every other rederive_kwargs() call
    site in this suite passes advisory={"items": []} alongside it -- test_gate.py
    :47/:387, test_orchestration.py:117). Without it, run_gate returns 'fail'
    on the UNMUTATED itinerary too (confirmed empirically at HEAD, before this
    task's changes: {'day references unknown POI', "advisory absent"}), so the
    docstring's claim would be false and the test would not isolate the
    AI-tone check as the cause of the flip. Adding advisory={"items": []} here
    makes the claim true and matches the established pattern.
    """
    from scripts.gate import run_gate
    from tests.mech_fixtures import build_gate_inputs, rederive_kwargs
    pois, itin = build_gate_inputs()
    itin["days"][0]["rows"][0]["text"] = "午餐——阿宏師火雞肉飯"
    rep = run_gate(pois, itin, advisory={"items": []}, **rederive_kwargs())
    names = {c["name"] for c in rep["checks"]}
    assert "no_ai_tone" in names
    assert rep["status"] == "fail"
    assert any("AI-tone em_dash" in f for f in rep["failures"])
