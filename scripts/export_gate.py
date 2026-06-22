"""Export-gate: mechanical checks on the rendered deliverable markdown.

Format/structure only. Catches the four export-layer defect classes the upstream
itinerary-gate (which runs on the pre-link intermediate) cannot see:
naked $, broken links, name-not-a-link, and bookable POIs missing an official
source link. Output shape matches itinerary-gate: {status, checks, failures}
(reuses schemas/gate-report.schema.json).
"""
import re

# Format-agnostic content hygiene (jargon / kana-gloss) lives in scripts.text_hygiene so
# the canonical itinerary-gate and these render gates share ONE implementation. These
# calls are render-layer defense-in-depth; the canonical gate is the primary guard.
from scripts.text_hygiene import jargon_failures, kana_gloss_failures

# A $ NOT immediately preceded by a backslash (i.e. not already escaped as \$).
_NAKED_DOLLAR = re.compile(r"(?<!\\)\$")
# Markdown link: [label](target)
_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
# Standalone map-token labels that mean the POI name was left as dead text.
_MAP_TOKENS = {"地圖", "地图", "Map", "map"}

def _photo_failures(pois):
    """Photo ATTRIBUTION presence (cross-axis matrix F4), shared by BOTH gates: a POI
    carrying a `photo` MUST also carry a non-empty `photo_attribution`
    (author + license + source_url). Returns a list of failure strings.

    Distributability (F5) is split out into _has_nondistributable (P7): a
    `photo_source == "google"` photo is intrinsically non-distributable — a LABELLING
    decision that re-rendering can never fix — so it sets the deliverable's
    `distributable: false` (a clean terminal for the personal variant) instead of
    failing the gate, which would make the orchestrator re-export-loop forever.
    """
    out = []
    for p in (pois or []):
        if p.get("photo"):
            attr = p.get("photo_attribution") or {}
            # strip() before the truthiness test: a whitespace-only field is
            # effectively blank and must not satisfy the mandatory-attribution guard.
            if not (str(attr.get("author") or "").strip()
                    and str(attr.get("license") or "").strip()
                    and str(attr.get("source_url") or "").strip()):
                out.append(f"photo POI '{p.get('id')}' missing attribution")
    return out


def _has_nondistributable(pois):
    """True if any POI carries a non-distributable photo source (google). (P7)

    This is a labelling decision, NOT a render defect: it drives the deliverable's
    `distributable` flag (a personal/google-photo variant is a clean terminal state),
    never the pass/fail channel the orchestrator loops on."""
    return any(p.get("photo_source") == "google" for p in (pois or []))


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

    failures.extend(kana_gloss_failures(md_text))
    failures.extend(jargon_failures(md_text, pois))

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

    failures.extend(_photo_failures(pois))

    # P7: non-distributable is a clean terminal label, not a fail. status reflects
    # only genuine (re-render-fixable) defects; distributable carries the labelling.
    nondistributable = _has_nondistributable(pois)

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
        {"name": "no_internal_jargon",
         "passed": not any("leaked into user-facing" in f for f in failures)},
        {"name": "photo_has_attribution",
         "passed": not any("missing attribution" in f for f in failures)},
        {"name": "no_nondistributable_photo_source",
         "passed": not nondistributable},
    ]
    return {"status": "pass" if not failures else "fail",
            "distributable": not nondistributable,
            "checks": checks, "failures": failures}

_HREF = re.compile(r'href="([^"]*)"')
_DAY_CARD = re.compile(r'class="day-card"')
# <img ... src="..."> — captures the src so the gate can whitelist its scheme.
# run_html_gate's _HREF inspector is href-only and structurally blind to src=
# (cross-axis matrix OOS-1), so a dedicated matcher is required. Double-quoted
# to match the renderer's attribute style.
_IMG_SRC = re.compile(r'<img\b[^>]*\bsrc="([^"]*)"', re.IGNORECASE)
# An <img src> is safe only as an inline base64 image or an https URL — no http,
# no javascript:, no data: of a non-image type. (security #6)
_SAFE_IMG_SRC = re.compile(r'(?i)^(data:image/|https://)')

def run_html_gate(html_text, pois, min_days=None, media_count=0):
    """Validate a rendered one-page HTML deliverable. Structure/format only:
    non-empty, >= min_days day-cards, every href is http(s), no raw <script>.
    Output shape matches run_export_gate. (dogfood D4)

    P8: when `media_count` (the number of entries in the verified-pois-media side-file
    the export-gate skill loaded) is > 0 but the rendered HTML contains zero <img>,
    the deliverable is failed — this catches the apply_media footgun where the caller
    dropped the (non-mutating) return value, silently rendering 0 photos while the
    gate's own merged pois still carry them. Callers with no side-file omit media_count.
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
        for src in _IMG_SRC.findall(html_text):
            if not _SAFE_IMG_SRC.match(src):
                failures.append(f"unsafe <img src>: '{src}'")
        failures.extend(jargon_failures(html_text, pois))
    failures.extend(_photo_failures(pois))

    # P8: a present media side-file that produced no <img> means the overlay was lost
    # (dropped apply_media return) — fail so it does not silently ship photoless.
    if media_count and not _IMG_SRC.findall(html_text or ""):
        failures.append(
            f"media side-file present ({media_count} entries) but rendered "
            f"deliverable has 0 photos")

    # P7: non-distributable is a clean terminal label, not a re-render-looping fail.
    nondistributable = _has_nondistributable(pois)

    checks = [
        {"name": "deliverable_has_content",
         "passed": not any("empty" in f or "too few day" in f for f in failures)},
        {"name": "links_well_formed",
         "passed": not any("href" in f for f in failures)},
        {"name": "no_raw_script",
         "passed": not any("<script>" in f for f in failures)},
        {"name": "img_src_safe",
         "passed": not any("unsafe <img src>" in f for f in failures)},
        {"name": "no_internal_jargon",
         "passed": not any("leaked into user-facing" in f for f in failures)},
        {"name": "photo_has_attribution",
         "passed": not any("missing attribution" in f for f in failures)},
        {"name": "no_nondistributable_photo_source",
         "passed": not nondistributable},
        {"name": "media_landed",
         "passed": not any("has 0 photos" in f for f in failures)},
    ]
    return {"status": "pass" if not failures else "fail",
            "distributable": not nondistributable,
            "checks": checks, "failures": failures}


def _find_rows(md_text, names):
    """All markdown TABLE rows (lines starting '|') containing any POI name.

    Restricting to table rows means a `### Day` heading that merely names the POI no
    longer shadows the real scheduled row; collecting ALL matching rows means a POI
    appearing on several days passes if any of its rows carries the official link. (TW-044)
    """
    return [line for line in md_text.splitlines()
            if line.lstrip().startswith("|") and any(name and name in line for name in names)]
