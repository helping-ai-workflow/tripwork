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

def run_export_gate(md_text, pois):
    """Return {status, checks, failures} for a rendered itinerary markdown.

    Args:
        md_text: full text of exports/<slug>-itinerary.md
        pois:    list of verified-pois dicts (verify_status, booking, sources, names)
    """
    failures = []

    if _NAKED_DOLLAR.search(md_text):
        failures.append("naked '$' found; prices must be escaped as '\\$'")

    for label, target in _LINK.findall(md_text):
        t = target.strip()
        if not t or not re.match(r"https?://", t):
            failures.append(f"malformed link target for '[{label}]': '{target}'")
        if label.strip() in _MAP_TOKENS:
            failures.append(f"standalone map token '[{label}]'; POI name must be the link")

    for p in pois:
        if p.get("verify_status") != "verified":
            continue
        if not (p.get("booking") or {}).get("required"):
            continue
        official = next(
            (s.get("url") for s in (p.get("sources") or []) if s.get("official")), None
        )
        names = [n for n in (p.get("name_display"), p.get("name_local")) if n]
        row = _find_row(md_text, names)
        if row is None:
            continue  # POI not scheduled into this deliverable; not this gate's concern
        if not official or official not in row:
            failures.append(
                f"bookable POI '{p.get('id')}' row missing official source link"
            )

    checks = [
        {"name": "no_naked_dollar",
         "passed": not any("naked '$'" in f for f in failures)},
        {"name": "links_well_formed",
         "passed": not any("malformed link" in f for f in failures)},
        {"name": "poi_name_is_link",
         "passed": not any("standalone map token" in f for f in failures)},
        {"name": "bookable_has_official_source",
         "passed": not any("official source link" in f for f in failures)},
    ]
    return {"status": "pass" if not failures else "fail",
            "checks": checks, "failures": failures}

def _find_row(md_text, names):
    """First markdown line containing any of the POI names, else None."""
    for line in md_text.splitlines():
        if any(name and name in line for name in names):
            return line
    return None
