# Changelog

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
