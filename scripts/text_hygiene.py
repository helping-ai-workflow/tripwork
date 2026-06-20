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
    """A verified POI whose `name_display` carries kana but has no non-empty `name_zh` — its
    render label (`name_display（name_zh）`) would be bare kana a Chinese reader can't read.
    Forward data-quality guard: `name_display` is schema-required so it is always the rendered
    name; pure-Han names are readable and exempt; non-verified POIs are never rendered."""
    return bool(poi.get("verify_status") == "verified"
                and _KANA.search(poi.get("name_display") or "")
                and not (poi.get("name_zh") or "").strip())
