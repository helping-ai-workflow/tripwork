---
name: source-verify
description: Use when candidates.yaml exists and each candidate must be verified before it can enter the itinerary. Iron-rule gate. Produces verified-pois.yaml.
---

# source-verify — Source-Verified-First gate

This is an iron-rule gate. Apply the **Source-Verified-First** discipline to every candidate. Only candidates that pass all three gates get `verify_status: verified` and may flow downstream.

## Three gates (logic in `scripts/verify.py::classify_candidate`)

Gates are evaluated in strict order — Gate 1 fires before Gate 2, Gate 2 before Gate 3.

1. **Multi-source** (Gate 1, checked first) — >= 2 independent sources, at least one in the destination's local language. Fewer/wrong language -> `unverified`. This gate precedes geocode so a single-source candidate is never misclassified as `rejected`.
2. **Geocode** (Gate 2) — resolve the place with `scripts/geocode.py::geocode` (OSM Nominatim, <= 1 req/s, set User-Agent). **Query by `name_local`** (the destination-language name recorded on the candidate), not an English display name — live Nominatim mis-resolves English descriptor suffixes (e.g. `"Togetsukyo Bridge"` returns nothing while `渡月橋` resolves). Append the district/city for disambiguation but keep the core name local. This matches export's `name_local`-based maps links. No result -> `rejected`.
3. **Region match + cross-source conflict** (Gate 3) — evaluated only after Gates 1 & 2 pass. Detect cross-source disagreement on rating/hours/address and signal it to `classify_candidate` via the `conflict_detected=True` argument (computed by this skill); on conflict -> `conflicting` + `conflict_note`, and **stop and ask the user** which source to trust. Geocoded point must also fall within the claimed district (`scripts/geocode.py::in_region`, region radius defaults to 5 km and is overridable via `trip-brief.routing.region_radius_km`); outside -> `conflicting`, record `conflict_note`.

## Record closure days + hours

While verifying opening hours, record each POI's `closed_days` (the per-POI closure axis consumed by synthesis via `scripts/calendar.py::poi_closed_on`). Values: weekday names (`tuesday`) for fixed weekly closures, ISO dates (`2026-05-25`) for one-off closures, or the token `public_holiday` when a place shuts on any public holiday. Closures come from the same cross-source hours check — a POI's stated regular closing day (e.g. a palace closed Tuesdays, a small shop closed on holidays) belongs here, not invented.

Also record the intra-day `hours` object (consumed by synthesis via `scripts/hours.py::closing_status`): `close`, and where applicable `last_order` (restaurant L.O.) / `last_entry` (sight last admission), plus `typical_visit_mins` (how long a visit needs). These come from the same verified sources — never guess a closing time.

## Output

Write all candidates into `trips/<slug>/verified-pois.yaml` (schema: `schemas/verified-pois.schema.json`) carrying their `verify_status` (and `closed_days` when known). Downstream stages read ONLY `verify_status: verified`. Never silently drop a candidate — `rejected`/`conflicting`/`unverified` stay recorded with their reason. If a `must_do` item fails, stop and tell the user explicitly.

Return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/candidates.yaml` + `trips/<slug>/trip-brief.yaml`. |
| Output | `trips/<slug>/verified-pois.yaml` with per-POI `verify_status` + reasons. |
| Stop condition | Cross-source conflict, or a `must_do` item fails verification → ask user. |
| Next stage | `tripwork:orchestrator`. |

## Red Flags

- "One good review is enough" → no; >= 2 independent sources, >= 1 local-language.
- "The name sounds like it's in that district" → geocode it; never assume region.
- "I'll drop the ones that didn't verify" → never silently drop; record status + reason.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Writing a POI with no `geocode` | Geocode-required; no coordinates → `rejected`, not written as verified. |
| Ignoring a region mismatch | Coordinates outside claimed district → `conflicting` + `conflict_note`, stop. |
