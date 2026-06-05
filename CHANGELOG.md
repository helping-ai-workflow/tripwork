# Changelog

## 0.7.0 — 2026-06-05

Seasonal/weather advisory + no-key daylight.

- New `seasonal-advisory` stage (`skills/seasonal-advisory/`): no-key seasonal/weather
  hazard research (official sources: road authority / met service / parks) into
  `seasonal.yaml` (`schemas/seasonal.schema.json`). Two-tier severity — `blocking`
  stops on confirmation (closed pass), `advisory`/`info` flow to the synthesis checklist
  (chains, gear, short daylight). Wired as orchestrator stage 7 (B2).
- `scripts/season.py`: no-key solar-geometry daylight — `daylight_hours`,
  `approx_sunset`, `after_dark`. Per overnight stop's sunset is computed and, for
  `self_drive` trips, after-dark driving legs are flagged for an earlier start.
- `trip-brief` schema gains optional `transport` (e.g. `self_drive`).
- `itinerary-synthesis` consumes `seasonal.yaml` (advisories + daylight into the
  checklist). No `itinerary-gate` change — `blocking` stops at the stage, like
  `travel-advisory` `banned`.

## 0.6.0 — 2026-06-05

Accommodation layer + no-key geocode resilience.

- New `accommodation-research` stage (`skills/accommodation-research/`): per overnight
  stop, verify a user-provided hotel or recommend N=3 verified candidates (stop-to-pick).
  Produces `accommodations.yaml` (`schemas/accommodations.schema.json`). Wired as
  orchestrator stage 5 (D1).
- `trip-brief` schema: `overnight_stops` (ordered, per-stop optional `lodging`) +
  `facility_needs` (`required` hard / `periodic` soft). `base` retained, coexists (D1).
- D7 no-key geocode: `scripts/geocode.py::resolve_place` (structured Nominatim query
  then free-text), `cluster_centroid`; a real place Nominatim cannot pin degrades to
  `unverified` (`scripts/verify.py`) instead of `rejected`; accommodations fall back to
  the stop's cluster centroid (`geocode_source: cluster_fallback`) and stay verified.
  `verified-pois`/`routing` schemas gain `geocode_source` / cluster `centroid`.
- Facilities (`scripts/facilities.py`): `stop_meets_required`, `coverage_gaps`
  (periodic cadence, advisory), `reception_ok` (late-arrival lock-out, reuses
  `hours.py`). `itinerary-gate` adds `overnight_stops_have_lodging` +
  `required_facilities_met`; lodging rows reuse the v0.5.0 renderer + export-gate.

## 0.5.0 — 2026-06-04

Export integrity — the rendered deliverable is now contract-checked.

- `scripts/render/markdown.py`: `md_escape` backslash-escapes `\ $ _ * | < ` `` ` `` in all free
  text (prices like `\$120` no longer trigger KaTeX math mode and break previews,
  D4); each POI row appends a primary `官網` source link (D2); the POI name remains
  the maps link (D5).
- `verified-pois` schema: `sources[]` gains optional `official` (marks the
  official-site source for the deliverable link, D2).
- New `export-gate` stage (`scripts/export_gate.py` + `skills/export-gate/`): a
  mechanical post-export gate on `exports/<slug>-itinerary.md` checking
  `no_naked_dollar`, `links_well_formed`, `poi_name_is_link`,
  `bookable_has_official_source`. Reuses `gate-report.schema.json`. Wired as
  orchestrator stage 10; `fail` returns to `export-artifact` (D6).
- `export-artifact`: deliverable renamed `exports/<slug>-itinerary.md` (no longer
  clashes with the synthesis intermediate, D3); day tables must go through
  `render_day_table`.

## 0.4.0 — 2026-06-04

Closing-buffer awareness (intra-day scheduling safety).

- `scripts/hours.py`: `closing_status(start, close, last_call, need_mins)`
  classifies a scheduled arrival as `ok` / `tight` / `after_last_call` /
  `closed` against a POI's closing window.
- `verified-pois` schema gains per-POI `hours` (`close` / `last_order` /
  `last_entry` / `typical_visit_mins`), recorded by `source-verify`.
- `trip-brief` schema gains optional `scheduling`
  (`min_buffer_mins` default 30, `default_visit_mins` default 60).
- `itinerary-synthesis` never schedules a slot past last order/entry, flags
  thin buffers, and stops if a `must_do` cannot fit before close on any slot.
- day-granularity calendar closure (v0.3.0) now complemented by time-of-day
  buffer — a place open on the chosen day can still be reached too late.

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
