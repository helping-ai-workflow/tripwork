"""Export-gate: mechanical checks on the rendered deliverable markdown.

Format/structure only. Catches the four export-layer defect classes the upstream
itinerary-gate (which runs on the pre-link intermediate) cannot see:
naked $, broken links, name-not-a-link, and bookable POIs missing an official
source link. Output shape matches itinerary-gate: {status, checks, failures}
(reuses schemas/gate-report.schema.json).
"""
import sys as _sys
import pathlib as _pathlib
if __name__ == "__main__" and __package__ in (None, ""):
    # run as `python scripts/export_gate.py`: make `from scripts.X import ...`
    # resolve. Also drop the auto-added scripts/ dir from sys.path -- it
    # shadows the stdlib `calendar` module with scripts/calendar.py for any
    # bare `import calendar` downstream (main()'s `from scripts.gate import
    # chosen_lodging_pois` now transitively imports `requests`, whose
    # http.cookiejar does `from calendar import timegm`). See scripts/gate.py
    # for the fuller account.
    _here = str(_pathlib.Path(__file__).resolve().parent)
    if _here in _sys.path:
        _sys.path.remove(_here)
    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent.parent))

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

# Sentinel returned by main()'s opt() helper when an optional artifact exists
# but fails to parse as YAML — distinct from None (absent), so callers can
# tell "malformed" apart from "not provided" and exit 2 instead of proceeding
# with a garbage value.
_MALFORMED = object()

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
        failures.extend(_maps_link_failures(_HREF.findall(html_text)))
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
        {"name": "maps_link_resolvable_form",
         "passed": not any("Google Maps link" in f for f in failures)},
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
            "retryable": _is_retryable(failures),
            "checks": checks, "failures": failures}


def _find_rows(md_text, names):
    """All markdown TABLE rows (lines starting '|') containing any POI name.

    Restricting to table rows means a `### Day` heading that merely names the POI no
    longer shadows the real scheduled row; collecting ALL matching rows means a POI
    appearing on several days passes if any of its rows carries the official link. (TW-044)
    """
    return [line for line in md_text.splitlines()
            if line.lstrip().startswith("|") and any(name and name in line for name in names)]


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
    """CLI: python scripts/export_gate.py <trip-dir> — gate the rendered
    deliverables (md + optional html) against the MERGED pois (verified-pois +
    chosen lodgings + media overlay, all assembled here) and write
    <trip-dir>/export-gate-report.yaml. Exit 0 pass / 1 fail / 2 missing input."""
    import argparse
    import pathlib
    import sys
    import yaml

    from scripts.gate import chosen_lodging_pois
    from scripts.media_merge import apply_media, load_media

    ap = argparse.ArgumentParser(description=main.__doc__)
    ap.add_argument("trip_dir")
    args = ap.parse_args(argv)
    d = pathlib.Path(args.trip_dir)
    slug = d.resolve().name
    md_path = d / "exports" / f"{slug}-itinerary.md"
    if not md_path.is_file():
        print(f"missing deliverable: {md_path}", file=sys.stderr)
        return 2

    def opt(name):
        try:
            with open(d / name, encoding="utf-8") as fh:
                return yaml.safe_load(fh)
        except FileNotFoundError:
            return None
        except yaml.YAMLError as exc:
            print(f"malformed optional artifact {name}: {exc!r}",
                  file=sys.stderr)
            return _MALFORMED

    pois_doc = opt("verified-pois.yaml")
    if pois_doc is _MALFORMED:
        return 2
    if not pois_doc:
        print("missing verified-pois.yaml", file=sys.stderr)
        return 2
    accommodations_doc = opt("accommodations.yaml")
    if accommodations_doc is _MALFORMED:
        return 2
    poi_map = {p["id"]: p for p in
               (pois_doc.get("pois") or []) + chosen_lodging_pois(accommodations_doc)}
    media_doc = load_media(d / "verified-pois-media.yaml")
    media_count = len((media_doc or {}).get("media") or {})
    poi_map = apply_media(poi_map, media_doc)      # NON-mutating: capture return
    merged_pois = list(poi_map.values())

    itin = opt("itinerary.yaml")
    if itin is _MALFORMED:
        return 2
    itin = itin or {}
    min_days = len(itin.get("days") or []) or None

    md_report = run_export_gate(md_path.read_text(encoding="utf-8"),
                                merged_pois, min_days=min_days)
    html_path = d / "exports" / f"{slug}-itinerary.html"
    html_report = None
    if html_path.is_file():
        html_report = run_html_gate(html_path.read_text(encoding="utf-8"),
                                    merged_pois, min_days=min_days,
                                    media_count=media_count)
    report = merge_reports(md_report, html_report)
    (d / "export-gate-report.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    print(f"export-gate: {report['status']} "
          f"(retryable={report['retryable']}, distributable={report['distributable']})")
    for f in report["failures"]:
        print(f"  - {f}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv[1:]))
