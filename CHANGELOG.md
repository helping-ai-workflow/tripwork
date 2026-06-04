# Changelog

## 0.3.0 — 2026-06-04

Calendar-awareness feature + geocode-query hardening.

- new `calendar-check` stage → `calendar.yaml`: destination public holidays
  (incl. substitute days) overlapping the trip range, each with crowds/closures
  impact and ≥1 official source (schema: `schemas/calendar.schema.json`).
- `verified-pois` schema gains per-POI `closed_days` (weekday / ISO date /
  `public_holiday` token), recorded by `source-verify` from the hours check.
- `scripts/calendar.py`: `weekday_of` / `holiday_on` / `is_high_crowd` /
  `poi_closed_on` decision logic.
- `itinerary-synthesis` hard-avoids scheduling a POI on a closed day (must_do
  closed on every feasible day → stop-and-ask) and flags holiday/weekend
  crowd days with earlier-start / off-peak advice.
- pipeline reordered: `routing-audit → calendar-check → itinerary-synthesis`.
- `source-verify` Gate 2 geocodes by `name_local` (English descriptor
  suffixes mis-resolve on live Nominatim, e.g. "Togetsukyo Bridge" → none).
- README rewritten in Traditional Chinese for non-engineer users (install
  flow, plain-language pipeline, holiday-awareness, dogfood examples).
- `CLAUDE.md` repo conventions (paperwork-style): mandatory README-freshness
  contract + writing convention + per-PR README check.
- `tests/test_readme_freshness.py` mechanical guard: every flow skill mentioned,
  `calendar-check` present in the workflow diagram, no obsolete names.
- `.github/workflows/ci.yml`: full hermetic pytest on every push/PR.
- `tests/test_version_consistency.py`: plugin.json / marketplace.json / CHANGELOG
  versions must agree (release-flow split-version guard).

## 0.2.0 — 2026-06-03

Hardening release: 5 known-issue fixes + workspace-shape-preflight entry-gate skill.

- advisory schema requires ≥1 official source (M1)
- candidates schema requires name_local + sources (M2)
- itinerary-gate checks meals + activities + visits POI references (M4)
- configurable region radius via trip-brief.routing.region_radius_km (M5)
- e2e must-do verification-failure closure test (M3)
- workspace-shape-preflight entry-gate skill (P1)

## 0.1.0 — 2026-06-03

Initial release.

- Orchestrator-driven staged pipeline (10 skills).
- Iron rule: Source-Verified-First (multi-source + geocode + region match).
- source-verify three-gate classification; routing-audit cross-region flags.
- itinerary-synthesis with contingency + pre-trip checklist sections.
- travel-advisory for entry/customs/battery regulations.
- itinerary-gate mechanical structure check.
- export adapters: markdown, Google Maps links, LINE short, Notion (graceful skip).
- Geocoding via OSM Nominatim.
