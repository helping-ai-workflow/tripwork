"""Export-gate: mechanical checks on the rendered deliverable markdown.

Format/structure only. Catches the four export-layer defect classes the upstream
itinerary-gate (which runs on the pre-link intermediate) cannot see:
naked $, broken links, name-not-a-link, and bookable POIs missing an official
source link. Output shape matches itinerary-gate: {status, checks, failures}
(reuses schemas/gate-report.schema.json).
"""
if __name__ == "__main__":
    raise SystemExit("moved in tripwork 2.0: python <plugin>/scripts/tripwork.py export-gate <slug>")


import hashlib
import re
from urllib.parse import unquote

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


# D2 (2026-07-01 gmaps-deadlink): maps-link resolvable-form gate. links_well_formed
# above is scheme-only, so the 0.23.0 dead `maps/place/?q=place_id:<id>` form (still
# https://) passed BOTH gates green while 38 links were dead. This makes the maps_url
# docstring ban mechanical. It is render-fixable (re-render under the fixed maps_url),
# so it carries no DATA_DEFECT_MARKER and stays retryable.
#
# Design — a PRECISE dead-form BLOCKLIST, not a canonical allow-list. "Is an arbitrary
# Google Maps URL resolvable?" is not regex-decidable: Google has many valid shapes
# (`/maps/place/<name>/@lat,lng` share links, `/maps/@`, path-style dir). An allow-list
# false-positives on those — a POI whose official-source URL is a real, resolvable
# `/maps/place/<name>/@` share link is rendered verbatim as `[官網](…)` (markdown.py:36)
# and would wrongly fail the gate, blocking a valid export (adversarial verify,
# 2026-07-01). So reject ONLY forms proven dead/unresolvable and leave every other maps
# link untouched. maps_url / dir_url (the only navigation-link producers) are separately
# unit-locked to the canonical form (tests/test_render_gmaps.py), so gate-level
# allow-listing of navigation links was redundant.
_MAPS_HOST = "www.google.com/maps"
# The banned single-param deep-link form Google does not resolve (the D1 regression).
# 0.23.0 emitted it via `quote("place_id:<id>", safe="")`, so the colon is percent-encoded
# to %3A in the real URL (and in the 76 real consumer dead links). The dead-form test
# therefore matches against `unquote(t)` (below), NOT the raw target — else `%3A` slips
# past this literal-colon marker.
_MAPS_DEAD = "/maps/place/?q=place_id:"
# A /maps/search link whose query is empty / whitespace-only resolves to nothing — e.g.
# maps_url({}) or a whitespace-only POI name (gmaps_links.py:18,48). Capture the query
# value (up to & or end) so it can be percent-decoded and stripped.
_MAPS_SEARCH_QUERY = re.compile(
    r"^https?://www\.google\.com/maps/search/\?api=1&query=([^&]*)")


def _maps_link_failures(targets):
    """Failure strings for any www.google.com/maps link that is provably dead or
    unresolvable: the D1 `maps/place/?q=place_id:` deep-link form, or a `/maps/search`
    link whose query is empty / whitespace-only. Every OTHER maps form — including a
    resolvable `/maps/place/<name>/@lat,lng` share link cited as an official source —
    passes untouched.

    `&amp;` is normalised first so an html-escaped href in a real rendered page
    (`?api=1&amp;query=`) is matched correctly. Every message carries the substring
    'Google Maps link' so the per-check pass/fail computation can key off it."""
    out = []
    for t in targets:
        t = (t or "").strip().replace("&amp;", "&")
        if _MAPS_HOST not in t:
            continue
        # unquote so the percent-encoded colon (place_id%3A, the real 0.23.0 output) is
        # caught, not just a literal colon. A resolvable /maps/place/<name>/@ share link
        # never decodes to `/maps/place/?q=place_id:`, so the FP guard is unaffected.
        if _MAPS_DEAD in unquote(t):
            out.append(
                f"dead Google Maps link (maps/place/?q=place_id: does not resolve): '{t}'")
            continue
        m = _MAPS_SEARCH_QUERY.match(t)
        if m and not unquote(m.group(1)).strip():
            out.append(
                f"unresolvable Google Maps link (empty search query): '{t}'")
    return out


# F1 (P7-twin): failure substrings that re-rendering CANNOT fix — they are upstream
# DATA defects (a photo with no attribution, a bookable POI with no official source).
# A fail whose only failures are these is non-retryable: the orchestrator must halt and
# ask the user to fix the data, NOT loop export-artifact (which re-renders the same defect).
_DATA_DEFECT_MARKERS = ("missing attribution", "official source link")


def _is_retryable(failures):
    """True when re-rendering could plausibly change the outcome: there are no failures
    (a pass), or at least one failure is a render-fixable defect (not a pure data defect)."""
    return (not failures) or any(
        not any(m in f for m in _DATA_DEFECT_MARKERS) for f in failures)


def run_export_gate(md_text, pois, min_days=None):
    """Return {status, checks, failures} for a rendered itinerary markdown.

    Args:
        md_text:  full text of the markdown deliverable (trips/<slug>/<stem>.md)
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

    failures.extend(_maps_link_failures(t for _, t in _LINK.findall(md_text)))
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
        {"name": "maps_link_resolvable_form",
         "passed": not any("Google Maps link" in f for f in failures)},
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
            "retryable": _is_retryable(failures),
            "checks": checks, "failures": failures}

_HREF = re.compile(r'href="([^"]*)"')
# v1.0 reader (spec §6): one <section class="page day"> per trip day.
_DAY_PAGE = re.compile(r'<section class="page day"')
# <img ... src="..."> — captures the src so the gate can whitelist its scheme.
# run_html_gate's _HREF inspector is href-only and structurally blind to src=
# (cross-axis matrix OOS-1), so a dedicated matcher is required. Double-quoted
# to match the renderer's attribute style.
_IMG_SRC = re.compile(r'<img\b[^>]*\bsrc="([^"]*)"', re.IGNORECASE)
# An <img src> is safe only as an inline base64 image or an https URL — no http,
# no javascript:, no data: of a non-image type. (security #6)
# v1.0: the page opens offline in Quick Look, so an image must be embedded.
_SAFE_IMG_SRC = re.compile(r'(?i)^data:image/')
_LICENCES = ("SIL Open Font License", "ISC License")
# v1.1 TW-D3: the notices open the file as a comment, not a footer on screen
_NOTICE = re.compile(r"<!doctype html>\s*<!--(.*?)-->", re.S | re.I)
# v1.1 user check: every OpenStreetMap credit is plain text (the user: a copyright link
# gets tapped by accident); the zoom bar's live-map link is a feature, not the credit
_OSM_TEXT = '<span class="attrmini">© OpenStreetMap</span>'
_OSM_CARD = re.compile(r'<p class="attr">[^<]*OpenStreetMap')
# v1.0 P5: map images are CSS backgrounds (one rule per distinct image), fonts are
# @font-face data: -- any url() in the page must be embedded too.
_CSS_URL = re.compile(r'url\(\s*["\']?([^"\')]*)')
_SCRIPT = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.S | re.I)
_ACTIVE_TAGS = frozenset({"iframe", "frame", "frameset", "object", "embed", "applet", "base", "form"})
_SCRIPT_URL = re.compile(r"(?i)^\s*(javascript|vbscript|data:text/html)")


def _script_hashes():
    # call the shipped constant, never a copied hash (CLAUDE.md "guards call their subject")
    # the two shipped constants: the centring script (every build) and the publish page's
    from scripts.render.reader.centre import CENTRE_JS
    from scripts.render.reader.publish import PUBLISH_JS
    return frozenset({hashlib.sha256(CENTRE_JS.encode()).hexdigest(),
                      hashlib.sha256(PUBLISH_JS.encode()).hexdigest()})


_SCRIPT_SHA256 = _script_hashes()
_SAFE_CSS_URL = re.compile(r'(?i)^data:(image|font)/')
_MAP_FRAME = re.compile(r'<label class="mframe[^"]*"[^>]*>.*?</label>', re.S)
_MAP_CARD = re.compile(r'<details class="mapc">.*?</details>', re.S)


class _ReaderScan(__import__("html.parser").parser.HTMLParser):
    """Structure facts the regexes cannot see: a ⌄ (.cv) outside a <summary>, and a
    move row (.leg, not .zero) with no m-<mode> icon."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.cv_outside, self.legs, self.legs_without_mode = [], 0, 0, 0
        self._leg_depth, self._leg_has_mode = None, False
        self.active = 0        # active content outside the one whitelisted <script>

    def handle_starttag(self, tag, attrs):
        cls = (dict(attrs).get("class") or "").split()
        # v1.0 P6: judged on parsed attributes (a quoted " onigiri=" in alt text is not a
        # handler; <svg/onload=…> is) -- handlers, embedding tags, refresh, script URLs
        if (tag in _ACTIVE_TAGS or (tag == "meta" and any(k == "http-equiv" for k, _ in attrs))
                or any(k.startswith("on") or _SCRIPT_URL.match(v or "") for k, v in attrs)):
            self.active += 1
        if tag == "span" and "cv" in cls and "summary" not in self.stack:
            self.cv_outside += 1
        if tag == "div" and "leg" in cls and "zero" not in cls and self._leg_depth is None:
            self._leg_depth, self._leg_has_mode = len(self.stack), False
            self.legs += 1
        if tag == "svg" and self._leg_depth is not None and any(c.startswith("m-") for c in cls):
            self._leg_has_mode = True
        if tag not in ("img", "input", "meta", "br", "path", "circle", "rect", "line", "polyline",
                       "polygon", "ellipse"):
            # v1.1 §8.1: an in-page anchor toggle (来源 open/close) is an expandable too
            href = dict(attrs).get("href") or ""
            self.stack.append("summary" if tag == "a" and href.startswith("#t-") else tag)

    def handle_endtag(self, tag):
        names = {tag, "summary"} if tag == "a" else {tag}
        if names & set(self.stack):
            while self.stack and self.stack.pop() not in names:
                pass
        if self._leg_depth is not None and len(self.stack) <= self._leg_depth:
            if not self._leg_has_mode:
                self.legs_without_mode += 1
            self._leg_depth = None

def run_html_gate(html_text, pois, min_days=None, media_count=0):
    """Validate a rendered one-page HTML deliverable. Structure/format only:
    non-empty, >= min_days day-cards, every href is http(s), no <script> but the reader's two shipped constants.
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
        n_days = len(_DAY_PAGE.findall(html_text))
        if min_days is not None and n_days < min_days:
            failures.append(f"too few day pages: {n_days} < {min_days}")
        ids = set(re.findall(r'\sid="([^"]+)"', html_text))
        for href in _HREF.findall(html_text):
            if href.startswith("#"):
                # v1.1 §8.1: an in-page anchor is fine when it lands somewhere
                if href[1:] not in ids:
                    failures.append(f"non-http href in deliverable: in-page link to a missing target '{href[:60]}'")
            elif not re.match(r"https?://", href):
                failures.append(f"non-http href in deliverable: '{href}'")
        failures.extend(_maps_link_failures(_HREF.findall(html_text)))
        # v1.0 P6 (spec §6.10): the only scripts allowed are the reader's own shipped
        # constants (centring, publish), byte for byte -- no attributes, no src, no inline handlers.
        scan = _ReaderScan()
        scan.feed(html_text)
        scripts = _SCRIPT.findall(html_text)
        if (len(scripts) != html_text.lower().count("<script")
                or any(attrs.strip() or hashlib.sha256(body.encode()).hexdigest() not in _SCRIPT_SHA256
                       for attrs, body in scripts)
                or scan.active):
            failures.append("script not on the whitelist in deliverable")
        for src in _IMG_SRC.findall(html_text):
            if not _SAFE_IMG_SRC.match(src):
                failures.append(f"non-embedded <img src>: '{src[:80]}'")
        foot = _NOTICE.match(html_text)
        missing = [l for l in _LICENCES if not foot or l not in foot.group(1)]
        if foot and not missing:
            # the whole notice, as the shipped licence files give it (ISC wants the
            # copyright and permission notice itself, not the licence's name)
            from scripts.render.reader.page import licence_notice
            if " ".join(foot.group(1).split()) != " ".join(licence_notice()[4:-3].split()):
                missing = ["the notice the shipped licence files give"]
        if missing:
            failures.append(f"licence notice missing: {', '.join(missing)}")
        if scan.cv_outside:
            failures.append(f"{scan.cv_outside} expand marker(s) outside a <details> summary")
        if scan.legs_without_mode:
            failures.append(f"{scan.legs_without_mode} move row(s) without a mode icon")
        for url in _CSS_URL.findall(html_text):
            if not _SAFE_CSS_URL.match(url):
                failures.append(f"non-embedded url() in stylesheet: '{url[:80]}'")
        # v1.1: every frame drawn from tiles carries the credit itself (the phone hides the
        # card-level line); the card-level line must still name OpenStreetMap (v1.0 P5)
        for frame in _MAP_FRAME.findall(html_text):
            if 'class="mimg ' in frame and _OSM_TEXT not in frame:
                failures.append("map tiles shown without their attribution")
                break
        else:
            for card in _MAP_CARD.findall(html_text):
                if 'class="mimg ' in card and not _OSM_CARD.search(card):
                    failures.append("map tiles shown without their attribution")
                    break
        failures.extend(jargon_failures(html_text, pois))
    failures.extend(_photo_failures(pois))

    # P8: a present media side-file that produced no <img> means the overlay was lost
    # (dropped apply_media return) — fail so it does not silently ship photoless.
    # v1.0 P7: the reader embeds each distinct photo once as a CSS background and
    # marks every shown photo with class "bpi"; an <img> still counts
    if media_count and not (_IMG_SRC.findall(html_text or "") or 'class="bpi ' in (html_text or "")):
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
        {"name": "maps_link_resolvable_form",
         "passed": not any("Google Maps link" in f for f in failures)},
        {"name": "scripts_whitelisted",
         "passed": not any("script not on the whitelist" in f for f in failures)},
        {"name": "img_src_offline",
         "passed": not any("non-embedded" in f for f in failures)},
        {"name": "licences_present",
         "passed": not any("licence notice missing" in f for f in failures)},
        {"name": "expandables_are_details",
         "passed": not any("expand marker" in f for f in failures)},
        {"name": "legs_have_mode_icon",
         "passed": not any("without a mode icon" in f for f in failures)},
        {"name": "map_attribution_present",
         "passed": not any("map tiles shown without" in f for f in failures)},
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
            "retryable": _is_retryable(failures),
            "checks": checks, "failures": failures}


# render_markdown_page's day-level lodging line ("**宿**：<poi cell>") — not
# table-formatted, so the '|'-prefixed scan below cannot see it on its own.
_LODGING_LINE_PREFIX = "**宿**："


def _find_rows(md_text, names):
    """Every markdown line that represents a SCHEDULED itinerary row for any of
    the given POI names: a day-table row ('|'-prefixed, inside a '### ' day
    section) or a render_markdown_page '**宿**：' lodging line.

    Restricting table rows to '### '-opened sections (TW-069 fix round 1) closes
    TWO defects render_markdown_page (Task 4) made reachable, in opposite
    directions:

      - FALSE NEGATIVE: the lodging line is not '|'-prefixed, so the old
        table-only scan never found a bookable lodging POI referenced ONLY
        there — `rows` came back empty and the check silently skipped it
        ("POI not scheduled into this deliverable"), even though it WAS
        scheduled, just not on a table row. Fixed by matching the lodging
        line's own literal prefix, independent of table structure.

      - FALSE POSITIVE: the new '## 費用估算' cost table's '|'-prefixed rows
        CAN legitimately repeat a POI's name inside an upstream-authored
        cost.yaml line-item label (e.g. a lodging line item "示品酒店嘉義
        （2晚）" contains the hotel's name "示品酒店嘉義") — the old scan
        counted that as a scheduled row, so a correctly-linked lodging POI
        FAILED the gate on the cost row's account (a cost row never carries a
        maps/official link) even though its real lodging line carried the
        link fine. Fixed STRUCTURALLY, not by excluding names: a '|' row only
        counts while scanning is inside a day — a '### ' heading opens that
        window, ANY '## ' heading closes it (whatever that section is
        called) — so the cost table, which lives under its own '## ' heading,
        is never eligible regardless of what its labels say. This does not
        depend on a POI's name being absent from a cost label, which is
        upstream-authored content this gate does not control.

    A '### ' heading that merely NAMES a POI (TW-044) is still excluded either
    way — it is never itself a '|'-prefixed or lodging-prefixed line.
    """
    rows = []
    in_day = False
    for line in md_text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("### "):
            in_day = True
            continue
        if stripped.startswith("## "):
            in_day = False
            continue
        if stripped.startswith(_LODGING_LINE_PREFIX):
            if any(name and name in line for name in names):
                rows.append(line)
            continue
        if in_day and stripped.startswith("|") and any(name and name in line for name in names):
            rows.append(line)
    return rows


def merge_reports(md_report, html_report):
    """Combine md + html gate reports into the single export-gate-report.
    html check names are prefixed `html_`, html failures prefixed `html: `;
    retryable is recomputed over the MERGED failures (substring markers are
    prefix-safe), distributable is the AND of both labels."""
    if html_report is None:
        return md_report
    failures = md_report["failures"] + [f"html: {f}" for f in html_report["failures"]]
    checks = md_report["checks"] + [
        {"name": f"html_{c['name']}", "passed": c["passed"]}
        for c in html_report["checks"]]
    return {
        "status": "pass" if not failures else "fail",
        "distributable": md_report["distributable"] and html_report["distributable"],
        "retryable": _is_retryable(failures),
        "checks": checks,
        "failures": failures,
    }


def main(argv):
    """CLI: python <plugin>/scripts/tripwork.py export-gate <slug> — gate the rendered
    deliverables (md + optional html) against the MERGED pois (verified-pois +
    chosen lodgings + media overlay, all assembled here) and write
    work/<slug>/export-gate-report.yaml (paths from scripts/paths.py).
    Exit 0 pass / 1 fail / 2 missing input."""
    import argparse
    import pathlib
    import sys
    import yaml

    ap = argparse.ArgumentParser(description=main.__doc__)
    from scripts.paths import artifact_path, deliverable_paths, report_path, work_dir_for

    ap.add_argument("trip_dir")
    ap.add_argument("--work-dir", default=None)
    args = ap.parse_args(argv)
    d = pathlib.Path(args.trip_dir)
    w = pathlib.Path(args.work_dir) if args.work_dir else work_dir_for(d)
    try:
        with open(artifact_path(d, "trip-brief.yaml"), encoding="utf-8") as fh:
            paths = deliverable_paths(d, yaml.safe_load(fh) or {})
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
        print(f"trip-brief has no usable short_name/dates to name the deliverables: {exc!r}",
              file=sys.stderr)
        return 2
    md_path = paths["md"]
    if not md_path.is_file():
        print(f"missing deliverable: {md_path}", file=sys.stderr)
        return 2

    from scripts.trip_inputs import TripInputError, trip_inputs
    try:
        itin, poi_map, _, media_count = trip_inputs(d)       # the renderers' own inputs
    except TripInputError as exc:
        print(exc, file=sys.stderr)
        return 2
    merged_pois = list(poi_map.values())
    min_days = len(itin.get("days") or []) or None

    md_report = run_export_gate(md_path.read_text(encoding="utf-8"),
                                merged_pois, min_days=min_days)
    html_path = paths["html"]
    html_report = None
    if html_path.is_file():
        html_report = run_html_gate(html_path.read_text(encoding="utf-8"),
                                    merged_pois, min_days=min_days,
                                    media_count=media_count)
    report = merge_reports(md_report, html_report)
    w.mkdir(parents=True, exist_ok=True)
    report_path(w, "export-gate-report.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    print(f"export-gate: {report['status']} "
          f"(retryable={report['retryable']}, distributable={report['distributable']})")
    for f in report["failures"]:
        print(f"  - {f}")
    return 0 if report["status"] == "pass" else 1
