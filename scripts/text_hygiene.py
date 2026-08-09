"""Format-agnostic content-hygiene checks shared by the canonical itinerary-gate
(`scripts/gate.py`) and the render-layer export gates (`scripts/export_gate.py`).

These operate on user-facing free text — a canonical row text / checklist item, or a
rendered deliverable — and are deliberately renderer-independent so a new deliverable
cannot re-open a hole. The canonical gate is the PRIMARY guard (it runs on the unescaped
itinerary text and so protects every renderer — md / html / line-short / notion-via-md —
at the source); the export-gate calls are render-layer defense-in-depth.

Imports only `re`, so both `gate.py` and `export_gate.py` can depend on it with no cycle.
"""
import re

# Internal token that must never reach user-facing prose: synthesis sometimes copies the
# structured `must_do` flag name into row text.
_MUST_DO = re.compile(r"must_do")
# Hiragana (U+3040-309F) + Katakana (U+30A0-30FF): scripts a Chinese reader cannot read.
# Han is excluded — it overlaps JP/ZH and would false-positive.
_KANA = re.compile(r"[぀-ヿ]+")
_HAS_PAREN = re.compile(r"[（(][^（()）]*[）)]")


def jargon_failures(text, pois):
    """Internal-jargon leaks: an internal poi_id token like ``(hak-goryokaku)`` or the
    literal ``must_do`` in user-facing text. Keyed off the AUTHORITATIVE poi id set — a
    loose ``\\(\\w+-\\w+\\)`` pattern would false-positive on legitimate romaji
    parentheticals, so only ``(<id>)`` for an id that actually exists is flagged (zero
    false positive). The scan runs over a backslash-stripped probe so a markdown-escaped
    leak (``must\\_do``, ``(hak-yam\\_yakei)``) is caught on the md axis too. Returns a
    list of failure strings (empty = clean)."""
    out = []
    probe = (text or "").replace("\\", "")
    for pid in [p.get("id") for p in (pois or []) if p.get("id")]:
        if f"({pid})" in probe:
            out.append(f"internal poi-id token ({pid}) leaked into user-facing text")
    if _MUST_DO.search(probe):
        out.append("internal token must_do leaked into user-facing text")
    return out


def kana_gloss_failures(text):
    """A kana run on a line with no （中文）gloss on the same line — an inline Japanese
    term left untranslated for the reader. Scans per line, so it works on a single
    canonical row text and on a multi-line rendered deliverable alike. Returns a list of
    failure strings (empty = clean)."""
    out = []
    for line in str(text or "").splitlines():
        if _KANA.search(line) and not _HAS_PAREN.search(line):
            term = _KANA.search(line).group(0)
            out.append(f"untranslated Japanese '{term}' has no （中文）gloss on its line")
    return out


def kana_name_without_gloss(poi):
    """A verified POI whose RENDERED name carries kana but has no non-empty `name_zh` — its
    label (`name（中文）`) would be bare kana a Chinese reader can't read. The rendered name is
    `name_display or name_local` — the same fallback the renderers use (gmaps_links.link_markdown,
    html_page._poi_label), so an empty `name_display` with a kana `name_local` is still caught.
    Forward data-quality guard; pure-Han names are readable and exempt; non-verified POIs are
    never rendered."""
    rendered = poi.get("name_display") or poi.get("name_local") or ""
    return bool(poi.get("verify_status") == "verified"
                and _KANA.search(rendered)
                and not (poi.get("name_zh") or "").strip())


# ---------------------------------------------------------------------------
# AI-tone — writing-humanizer distilled to a mechanical gate. Every pattern was
# measured against the 5 real canonical itineraries and carries ZERO false
# positives there; the patterns that did not survive that measurement are pinned
# in tests/test_ai_tone.py::EXCLUDED_PATTERNS with the FP count that cut each.
# Canonical layer ONLY — render/html_page.py:300 emits a bare em-dash as the
# empty-lodging filler, so gating rendered output would gate the renderer.
# ---------------------------------------------------------------------------

# 模式13 破折號. U+2014, U+2015, and the box-drawing run synthesis sometimes emits.
# Deliberately NOT U+2013 (–) or U+FF5E (～): those are the range separators real
# itineraries use for dates and opening hours ("09:00–18:00", "毎日11:30～").
_AI_EM_DASH = re.compile(r"[—―]+|─{2,}")

# 模式14/15/28 粗體. Canonical row text and checklist items are PLAIN TEXT, so
# markdown emphasis there is both an AI tell and a layering leak.
_AI_BOLD = re.compile(r"\*\*([^*\n]+)\*\*[:：]?|__([^_\n]+)__[:：]?")

# 模式16 表情符號. Pictographic planes plus the three dingbats AI uses as bullets.
# Deliberately EXCLUDES the wide U+2600-27BF range: ★ (U+2605) is a rating unit
# ("Google 4.4★") and ⚠ (U+26A0) is a functional hazard marker. Both measured.
_AI_EMOJI = re.compile("[\U0001F300-\U0001FAFF]|[✅❌✨]")

# 模式7 + zh-tw-slop-list. Discourse markers and contentless abstractions with no
# travel-domain meaning, so none can collide with a place name, dish or hazard.
_AI_SLOP_WORDS = (
    "此外", "值得一提的是", "不容忽視的是", "眾所周知", "總而言之", "綜上所述",
    "至關重要", "深入探討", "不可磨滅", "錯綜複雜", "賦能", "賦予力量",
    "織錦", "畫卷", "充滿活力", "相得益彰", "淋漓盡致",
)

# 模式9/29/30 + zh-tw-slop-list sentence templates. (pattern, human label).
_AI_SLOP_TEMPLATES = (
    (r"在當今[^\n。，]{0,10}的時代", "在當今…的時代"),
    (r"隨著[^\n。，]{0,12}的(?:快速|不斷)?(?:發展|進步)", "隨著…的發展"),
    (r"不僅[^\n。]{0,20}(?:更是|而且更)", "不僅…更是"),
    (r"不只是[^\n。]{0,20}(?:更是|而是)", "不只是…而是"),
    (r"讓我們一起", "讓我們一起"),
    (r"本(?:文|節)將(?:探討|分析|介紹)", "本文將探討"),
    (r"接下來(?:我們)?(?:來看|將看到)", "接下來我們來看"),
    (r"的重要性不言而喻", "…的重要性不言而喻"),
    (r"(?:願我們|讓我們都能)", "願我們…（升華呼告）"),
    (r"歷史將(?:會)?記住", "歷史將會記住"),
)

# 模式4 宣傳語言. ONLY fixed four-character-or-longer superlatives that can never
# be a proper name nor a functional recommendation. 首選/必訪/必吃/坐落於/享受/
# 體驗/放鬆 are NOT here — every one was measured as real usage in the corpus.
_AI_PROMO = (
    "嘆為觀止", "美不勝收", "如詩如畫", "人間仙境", "舉世聞名", "聞名遐邇",
    "名不虛傳", "洗滌心靈", "不虛此行", "此生必去", "無與倫比", "美輪美奐",
    "流連忘返", "驚豔絕倫", "獨特的魅力", "深厚的文化底蘊", "豐富的文化底蘊",
)

# 模式27 意義蓋章. Only the contentless stamps. 象徵著/標誌著/見證了/體現了 are
# deliberately absent — a heritage site legitimately 見證了 an era, and 檜意森活村
# and 奉天宮 are exactly that.
_AI_MEANING_STAMP = (
    (r"奠定了?[^\n。]{0,6}基礎", "奠定…基礎"),
    (r"具有[^\n。]{0,8}重要(?:意義|地位|價值)", "具有重要意義"),
    (r"發揮[^\n。]{0,6}(?:關鍵|重要)作用", "發揮關鍵作用"),
    (r"提供了[^\n。]{0,8}重要(?:框架|參考|借鑑)", "提供重要框架"),
)

# 模式18/20 chatbot 對話殘留.
_AI_CHATBOT = (
    "希望這對您有幫助", "希望這對你有幫助", "希望對您有幫助", "希望對你有幫助",
    "請讓我知道", "如果您需要", "如果你還需要", "以上就是為您", "很高興為您",
)

_AI_WS = re.compile(r"\s+")


def _ai_snippet(text, start, end, pad=12):
    """±12-char whitespace-collapsed context, so a failure is locatable inside a
    2000-char joined canonical text without dumping the whole field."""
    s, e = max(0, start - pad), min(len(text), end + pad)
    return _AI_WS.sub(" ", text[s:e]).strip()


def ai_tone_failures(text):
    """Mechanical AI-tone patterns in user-facing itinerary prose.

    Runs on the CANONICAL joined text only. The render layer is deliberately NOT
    gated: render/html_page.py:300 emits a bare em-dash as the empty-lodging cell
    filler and the renderers emit decorative slot icons, so a render-layer scan
    would fail on the renderers' own output (measured: 278 emoji + 62 bold-label
    hits across 19 rendered files vs 0 of each across the 5 canonical ones).

    Returns a list of failure strings (empty = clean), one per occurrence,
    deduped on the full message — matching jargon_failures / kana_gloss_failures.
    """
    t = str(text or "")
    out, seen = [], set()

    def add(kind, desc, start, end):
        msg = f"AI-tone {kind}: {desc}; found '{_ai_snippet(t, start, end)}'"
        if msg not in seen:
            seen.add(msg)
            out.append(msg)

    for m in _AI_EM_DASH.finditer(t):
        add("em_dash", "em-dash used as a connector; use 、/，/：or split the sentence",
            m.start(), m.end())
    for m in _AI_BOLD.finditer(t):
        inner = m.group(1) or m.group(2) or ""
        if m.group(0).rstrip().endswith(("：", ":")) or inner.rstrip().endswith(("：", ":")):
            add("bold_label", "bold label + colon list item; write it as a plain sentence",
                m.start(), m.end())
        else:
            add("markdown_bold", "markdown emphasis in canonical prose; emphasise by "
                                 "sentence structure, not bold", m.start(), m.end())
    for m in _AI_EMOJI.finditer(t):
        add("decorative_emoji", "decorative emoji in itinerary prose", m.start(), m.end())
    for w in _AI_SLOP_WORDS:
        for m in re.finditer(re.escape(w), t):
            add("slop_word", f"AI filler word '{w}'", m.start(), m.end())
    for pat, label in _AI_SLOP_TEMPLATES:
        for m in re.finditer(pat, t):
            add("slop_template", f"AI sentence template '{label}'", m.start(), m.end())
    for w in _AI_PROMO:
        for m in re.finditer(re.escape(w), t):
            add("promo_cliche", f"promotional cliche '{w}'; state the concrete fact instead",
                m.start(), m.end())
    for pat, label in _AI_MEANING_STAMP:
        for m in re.finditer(pat, t):
            add("meaning_stamp", f"meaning-stamp closer '{label}'; delete it or write the "
                                 "concrete consequence", m.start(), m.end())
    for w in _AI_CHATBOT:
        for m in re.finditer(re.escape(w), t):
            add("chatbot_residue", f"chatbot conversational residue '{w}'", m.start(), m.end())
    return out
