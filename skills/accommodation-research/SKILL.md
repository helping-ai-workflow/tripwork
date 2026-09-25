---
name: accommodation-research
description: Use when routing.yaml is ready and lodging must be established per overnight stop before synthesis. Produces accommodations.yaml.
---

# accommodation-research — lodging per overnight stop

Establish verified lodging for every `trip-brief.overnight_stops` entry (a single-base
trip has one stop, derived from `base`). Produces `trips/<slug>/accommodations.yaml`
(schema: `schemas/accommodations.schema.json`). Applies **Source-Verified-First** to
every candidate, exactly like `source-verify`.

## Dual mode (per stop — keyed on whether the stop carries `lodging`)

- **filled** (`overnight_stops[i].lodging` given) → verify + enrich that hotel; set
  `chosen` to it. Never override the user's booking.
- **unfilled** → research **N = 3** verified candidates using the **source ladder** in
  `tripwork:using-tripwork` (WebSearch, else WebFetch against an official or booking page,
  else a search HTML endpoint for discovery only), including local-language queries; leave
  `chosen: null` and **stop and ask the user to pick**.
  List all unfilled stops' options at once — do not interrupt per stop.

## Verification (reuse `scripts/verify.py::classify_candidate`)

`itinerary-gate` **re-derives** every candidate's `verify_status` from the
recorded `sources`, `geocode.geocode_source`, `resolved_name` and
`business_status` — if the artifact doesn't carry the field, the gate fails and
routes back here.

- **Operating (Gate 0):** record a chosen candidate's `business_status`
  in the **sourced object form** — `{status, source_url, as_of}`, `status` from
  the Google Places vocabulary (`OPERATIONAL` / `CLOSED_TEMPORARILY` /
  `CLOSED_PERMANENTLY`) — the identical shape and identical routes
  `source-verify`'s own Gate 0 documents (Places API `businessStatus`; the
  hotel's own recent dated post or official page; or a phone confirmation
  recorded as `source_url: tel:<number>`). A bare hand-typed string is
  **self-attested and is not a signal** — `rederive_lodging` treats it exactly
  like an absent field, and `itinerary-gate` routes back here asking for the
  sourced form. A **sourced but CLOSED** value demotes the candidate to
  `rejected` — a closed hotel is never treated as open. When no route is available,
  leave the candidate `unverified` with a `status_reason`; that is the honest
  outcome, not a defect.
- ≥2 independent sources, ≥1 local-language (Gate 1).
- **`name_zh` (Chinese gloss):** capture a `name_zh` on each candidate; the render
  layer shows `name_display（name_zh）`. **REQUIRED when the candidate's `name_display`
  contains kana** (e.g. 駅前ホテル) — the schema rejects a verified kana-named candidate
  without it, and `itinerary-gate` fails the folded lodging (`no name_zh gloss`). Pure-Han
  names (駅前旅館) are exempt. Same discipline as `source-verify`'s POI gloss.
- **Geocode (D7, no API key):** resolve by `scripts/geocode.py::resolve_place(name_local,
  district, country)` — structured Nominatim query first, free-text fallback. On
  NO_RESULT, fall back to the stop's cluster `centroid` from `routing.yaml`
  (`geocode.geocode_source: cluster_fallback`). **The centroid fallback needs no
  existence proof beyond Gate 0 above (subsumed by it — see `source-verify`'s
  `cluster_fallback` paragraph):** a sourced `business_status` is itself independent
  evidence the hotel exists, so nothing further is asked of a `cluster_fallback`
  geocode specifically. Record `geocode_source` either way — an absent value is
  a refusal on its own, independent of Gate 0.
  Pass the per-trip cache (`work/<slug>/geocode-cache/geocode.json` via
  `scripts/geocode_cache.py`) as `resolve_place(..., cache=cache)` — re-runs then skip
  already-resolved and known-miss hotel lookups. **When the user manually confirms a hotel
  or requests re-verification, delete that hotel's `cache_key` entry from the cache first**
  so a stale negative cache cannot permanently suppress the re-query. **Record
  `resolved_name`** on every candidate — the geocoder's returned `display_name` — so
  Gate 2b (name match) can be re-derived from the artifact instead of trusting
  whatever the agent typed.
- **Region:** a hotel that *does* geocode but lands outside the stop district
  (`scripts/geocode.py::in_region`) → `conflicting` + stop and ask. Centroid fallback is
  trivially in-region.

## Cost (for the rollup)

Record each candidate's numeric `cost` (amount + currency + `basis: per_night | total`)
from the booking / official source, alongside the human-readable `price_band`. `amount`
is the price **per room**; when a stop needs more than one room, record `cost.rooms` so
`cost-rollup` multiplies correctly (default 1).
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

Write `trips/<slug>/accommodations.yaml`, then validate it:
`python scripts/validate_artifact.py trips/<slug>/accommodations.yaml`
(exit 0 required before returning). Never silently drop a
candidate — `conflicting`/`rejected`/`unverified` stay recorded with their reason. Return
to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/routing.yaml` (clusters + centroids) + `trips/<slug>/trip-brief.yaml`. |
| Output | `trips/<slug>/accommodations.yaml` (per-stop candidates + chosen, each candidate carrying `resolved_name` for gate re-derivation). |
| Stop condition | Unfilled stop needs a pick; a required facility is missing; a hotel geocodes outside its stop; arrival is after reception close → ask user. |
| Next stage | `tripwork:orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Overriding a user-provided hotel | Filled `lodging` is verified in place, not replaced. |
| Rejecting a real hotel Nominatim can't pin | Fall back to the cluster centroid — but the fallback is not what keeps it `verified`. Gate 0 is: record the sourced `business_status` (`{status, source_url, as_of}`) and `geocode_source: cluster_fallback`. Without a sourced `business_status` the candidate is `unverified`, centroid or not. |
| Reading the centroid fallback as "the location is verified" | It is not. The coordinate is the district midpoint, not the hotel's position — verification says the hotel EXISTS, not that the pin is right. Tell the user which candidates sit on a centroid so arrival timing and walk distances get checked by hand. |
| Guessing facilities | Record only facilities stated by a verified source. |
