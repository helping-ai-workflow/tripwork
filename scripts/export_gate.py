"""Export-gate: mechanical checks on the rendered deliverable markdown.

Format/structure only. Catches the four export-layer defect classes the upstream
itinerary-gate (which runs on the pre-link intermediate) cannot see:
naked $, broken links, name-not-a-link, and bookable POIs missing an official
source link. Output shape matches itinerary-gate: {status, checks, failures}
(reuses schemas/gate-report.schema.json).
"""
import re

# A $ NOT immediately preceded by a backslash (i.e. not already escaped as \$).
_NAKED_DOLLAR = re.compile(r"(?<!\\)\$")
# Markdown link: [label](target)
_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
# Standalone map-token labels that mean the POI name was left as dead text.
_MAP_TOKENS = {"地圖", "地图", "Map", "map"}
# Hiragana (U+3040-309F) + Katakana (U+30A0-30FF): scripts a Chinese reader
# cannot read. Han is excluded — it overlaps JP/ZH and would false-positive.
_KANA = re.compile(r"[぀-ヿ]+")
_HAS_PAREN = re.compile(r"[（(][^（()）]*[）)]")

def run_export_gate(md_text, pois, min_days=None):
    """Return {status, checks, failures} for a rendered itinerary markdown.

    Args:
        md_text:  full text of exports/<slug>-itinerary.md
        pois:     list of verified-pois dicts (verify_status, booking, sources, names)
        min_days: optional int; fail if fewer than this many '### ' day sections
                  (or if the deliverable is empty). Guards against an export that
                  rendered to nothing or got truncated. (TW-015)
    """
    failures = []

    stripped = (md_text or "").strip()
    if not stripped:
        failures.append("deliverable is empty")
    elif min_days is not None:
        n_days = len(re.findall(r"(?m)^###\s", md_text))
        if n_days < min_days:
            failures.append(f"too few day sections: {n_days} < {min_days}")

    if _NAKED_DOLLAR.search(md_text):
        failures.append("naked '$' found; prices must be escaped as '\\$'")

    for label, target in _LINK.findall(md_text):
        t = target.strip()
        if not t or not re.match(r"https?://", t):
            failures.append(f"malformed link target for '[{label}]': '{target}'")
        if label.strip() in _MAP_TOKENS:
            failures.append(f"standalone map token '[{label}]'; POI name must be the link")

    for line in md_text.splitlines():
        if _KANA.search(line) and not _HAS_PAREN.search(line):
            term = _KANA.search(line).group(0)
            failures.append(
                f"untranslated Japanese '{term}' has no （中文）gloss on its line")

    for p in pois:
        if p.get("verify_status") != "verified":
            continue
        if not (p.get("booking") or {}).get("required"):
            continue
        official = next(
            (s.get("url") for s in (p.get("sources") or []) if s.get("official")), None
        )
        names = [n for n in (p.get("name_display"), p.get("name_local")) if n]
        rows = _find_rows(md_text, names)
        if not rows:
            continue  # POI not scheduled into this deliverable; not this gate's concern
        if not official or not any(official in r for r in rows):
            failures.append(
                f"bookable POI '{p.get('id')}' row missing official source link"
            )

    checks = [
        {"name": "deliverable_has_content",
         "passed": not any("empty" in f or "too few day" in f for f in failures)},
        {"name": "no_naked_dollar",
         "passed": not any("naked '$'" in f for f in failures)},
        {"name": "links_well_formed",
         "passed": not any("malformed link" in f for f in failures)},
        {"name": "poi_name_is_link",
         "passed": not any("standalone map token" in f for f in failures)},
        {"name": "bookable_has_official_source",
         "passed": not any("official source link" in f for f in failures)},
        {"name": "japanese_glossed",
         "passed": not any("no （中文）gloss" in f for f in failures)},
    ]
    return {"status": "pass" if not failures else "fail",
            "checks": checks, "failures": failures}

_HREF = re.compile(r'href="([^"]*)"')
_DAY_CARD = re.compile(r'class="day-card"')

def run_html_gate(html_text, pois, min_days=None):
    """Validate a rendered one-page HTML deliverable. Structure/format only:
    non-empty, >= min_days day-cards, every href is http(s), no raw <script>.
    Output shape matches run_export_gate. (dogfood D4)
    """
    failures = []
    stripped = (html_text or "").strip()
    if not stripped:
        failures.append("deliverable is empty")
    else:
        n_days = len(_DAY_CARD.findall(html_text))
        if min_days is not None and n_days < min_days:
            failures.append(f"too few day cards: {n_days} < {min_days}")
        for href in _HREF.findall(html_text):
            if not re.match(r"https?://", href):
                failures.append(f"non-http href in deliverable: '{href}'")
        if "<script" in html_text.lower():
            failures.append("raw <script> in deliverable (data not escaped)")
    checks = [
        {"name": "deliverable_has_content",
         "passed": not any("empty" in f or "too few day" in f for f in failures)},
        {"name": "links_well_formed",
         "passed": not any("href" in f for f in failures)},
        {"name": "no_raw_script",
         "passed": not any("<script>" in f for f in failures)},
    ]
    return {"status": "pass" if not failures else "fail",
            "checks": checks, "failures": failures}


def _find_rows(md_text, names):
    """All markdown TABLE rows (lines starting '|') containing any POI name.

    Restricting to table rows means a `### Day` heading that merely names the POI no
    longer shadows the real scheduled row; collecting ALL matching rows means a POI
    appearing on several days passes if any of its rows carries the official link. (TW-044)
    """
    return [line for line in md_text.splitlines()
            if line.lstrip().startswith("|") and any(name and name in line for name in names)]
