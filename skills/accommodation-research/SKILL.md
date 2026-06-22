---
name: accommodation-research
description: Use when routing.yaml is ready and lodging must be established per overnight stop before synthesis. Researches/verifies accommodation (dual mode) with a no-key geocode fallback. Produces accommodations.yaml.
---

# accommodation-research — lodging per overnight stop

Establish verified lodging for every `trip-brief.overnight_stops` entry (a single-base
trip has one stop, derived from `base`). Produces `trips/<slug>/accommodations.yaml`
(schema: `schemas/accommodations.schema.json`). Applies **Source-Verified-First** to
every candidate, exactly like `source-verify`.

## Dual mode (per stop — keyed on whether the stop carries `lodging`)

- **filled** (`overnight_stops[i].lodging` given) → verify + enrich that hotel; set
  `chosen` to it. Never override the user's booking.
- **unfilled** → research **N = 3** verified candidates (consumer `WebSearch`, include
  local-language queries); leave `chosen: null` and **stop and ask the user to pick**.
  List all unfilled stops' options at once — do not interrupt per stop.

## Verification (reuse `scripts/verify.py::classify_candidate`)

- ≥2 independent sources, ≥1 local-language (Gate 1).
- **Geocode (D7, no API key):** resolve by `scripts/geocode.py::resolve_place(name_local,
  district, country)` — structured Nominatim query first, free-text fallback. On
  NO_RESULT, fall back to the stop's cluster `centroid` from `routing.yaml`
  (`geocode.geocode_source: cluster_fallback`). **The centroid fallback keeps the hotel
  `verified` ONLY with an existence proof** — at least one source is the hotel's own
  official page or a booking-platform listing (`official: true` / `booking.url`). Without
  that proof a Nominatim-unresolvable name may not be a real hotel → degrade to `unverified`
  with a `status_reason`, never a silent `verified`. Record `geocode_source` either way.
  Pass the per-trip cache (`work/<slug>/geocode-cache/geocode.json` via
  `scripts/geocode_cache.py`) as `resolve_place(..., cache=cache)` — re-runs then skip
  already-resolved and known-miss hotel lookups. **When the user manually confirms a hotel
  or requests re-verification, delete that hotel's `cache_key` entry from the cache first**
  so a stale negative cache cannot permanently suppress the re-query.
- **Region:** a hotel that *does* geocode but lands outside the stop district
  (`scripts/geocode.py::in_region`) → `conflicting` + stop and ask. Centroid fallback is
  trivially in-region.

## Cost (for the rollup)

Record each candidate's numeric `cost` (amount + currency + `basis: per_night | total`)
from the booking / official source, alongside the human-readable `price_band`. `amount`
is the price **per room**; when a stop needs more than one room, record `cost.rooms` so
`cost-rollup` multiplies correctly (default 1). (P6)
`cost-rollup` (a later stage) sums these — do not compute totals here.

## Facilities (Source-Verified-First — from sources, never guessed)

Record each candidate's `facilities` (open vocabulary: `parking`, `laundry`, `kitchen`,
`elevator`, `breakfast`, `family_room`, `crib`, `wifi`, `heating`, …) from official /
booking sources.

- **required (hard)** — `trip-brief.facility_needs.required`. Recommend-mode filters to
  candidates having all required tokens; verify-mode flags a user hotel missing one via
  `scripts/facilities.py::stop_meets_required` → stop and ask.
- **reception (hard)** — record `reception: {close, late_checkin}`. Estimated arrival at
  the stop vs `reception.close` is checked with `scripts/facilities.py::reception_ok`
  (reuses `hours.py`). Arrival after close with no late check-in → stop and ask.
- **periodic (soft)** — `facility_needs.periodic` is a trip-level coverage check computed
  by `itinerary-synthesis` (`scripts/facilities.py::coverage_gaps`); advisory only, never
  blocks here.

## Output

Write `accommodations.yaml` (validate against the schema). Never silently drop a
candidate — `conflicting`/`rejected`/`unverified` stay recorded with their reason. Return
to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/routing.yaml` (clusters + centroids) + `trips/<slug>/trip-brief.yaml`. |
| Output | `trips/<slug>/accommodations.yaml` (per-stop candidates + chosen). |
| Stop condition | Unfilled stop needs a pick; a required facility is missing; a hotel geocodes outside its stop; arrival is after reception close → ask user. |
| Next stage | `tripwork:orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Overriding a user-provided hotel | Filled `lodging` is verified in place, not replaced. |
| Rejecting a real hotel Nominatim can't pin | Fall back to the cluster centroid; keep it `verified`. |
| Guessing facilities | Record only facilities stated by a verified source. |
