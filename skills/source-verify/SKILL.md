---
name: source-verify
description: Use when candidates.yaml exists and each candidate must be verified before it can enter the itinerary. Iron-rule gate. Produces verified-pois.yaml.
---

# source-verify — Source-Verified-First gate

This is an iron-rule gate. Apply the **Source-Verified-First** discipline to every candidate. Only candidates that pass all three gates get `verify_status: verified` and may flow downstream.

## Gates (logic in `scripts/verify.py::classify_candidate`)

Gates are evaluated in strict order — Gate 0 fires before Gate 1, Gate 1 before Gate 2, Gate 2 before Gate 3.

0. **Operating** (Gate 0, checked first) — the place must still be open for business. A permanently/temporarily closed (defunct) venue -> `rejected`. Determine it from Google Maps ('永久停業' / 'Permanently closed' / 'Temporarily closed') or an official-site 404, and pass `operating=False` to `classify_candidate`. A defunct POI that has two sources and geocodes would otherwise sail through as `verified` — Gate 0 stops that.
1. **Multi-source** (Gate 1) — >= 2 independent sources, at least one in the destination's local language. Fewer/wrong language -> `unverified`. This gate precedes geocode so a single-source candidate is never misclassified as `rejected`.

**Source `official` flag.** When a source is the POI's own official site / official booking page, mark that source `official: true`. export-gate requires a bookable POI's row to carry its official link, and the renderer labels the primary link `官網` — without the flag a non-official aggregator link is mislabelled and the bookable check has nothing to match.
2. **Geocode** (Gate 2) — resolve the place with `scripts/geocode.py::resolve_place` (structured Nominatim query first, then free-text fallback; <= 1 req/s, set User-Agent). **Query by `name_local`** (the destination-language name recorded on the candidate), not an English display name — live Nominatim mis-resolves English descriptor suffixes (e.g. `"Togetsukyo Bridge"` returns nothing while `渡月橋` resolves). Append the district/city for disambiguation but keep the core name local. This matches export's `name_local`-based maps links. Record `geocode.geocode_source`. **D7:** a real place Nominatim cannot resolve degrades to `unverified` (recorded for manual confirmation) — never silently `rejected`. Pass a per-trip cache (`work/<slug>/geocode-cache/geocode.json` via `scripts/geocode_cache.py`) as `resolve_place(..., cache=cache)` — load it once at the start and save it at the end so re-runs skip already-resolved and known-miss lookups.
3. **Region match + cross-source conflict** (Gate 3) — evaluated only after Gates 1 & 2 pass. Detect cross-source disagreement on rating/hours/address and signal it to `classify_candidate` via the `conflict_detected=True` argument (computed by this skill); on conflict -> `conflicting` + `conflict_note`, and **stop and ask the user** which source to trust. Geocoded point must also fall within the claimed district (`scripts/geocode.py::in_region`, region radius defaults to 5 km and is overridable via `trip-brief.routing.region_radius_km`); outside -> `conflicting`, record `conflict_note`.

## Record closure days + hours

While verifying opening hours, record each POI's `closed_days` (the per-POI closure axis consumed by synthesis via `scripts/calendar.py::poi_closed_on`). Values: weekday names (`tuesday`) for fixed weekly closures, ISO dates (`2026-05-25`) for one-off closures, or the token `public_holiday` when a place shuts on any public holiday. Closures come from the same cross-source hours check — a POI's stated regular closing day (e.g. a palace closed Tuesdays, a small shop closed on holidays) belongs here, not invented.

Also record the intra-day `hours` object (consumed by synthesis via `scripts/hours.py::closing_status`): `close`, and where applicable `last_order` (restaurant L.O.) / `last_entry` (sight last admission), plus `typical_visit_mins` (how long a visit needs). These come from the same verified sources — never guess a closing time.

## Output

Write all candidates into `trips/<slug>/verified-pois.yaml` (schema: `schemas/verified-pois.schema.json`) carrying their `verify_status` (and `closed_days` when known). Downstream stages read ONLY `verify_status: verified`. Never silently drop a candidate — `rejected`/`conflicting`/`unverified` stay recorded with their reason. **Every non-`verified` POI must carry a non-empty `status_reason`** (the schema enforces this; `verified` POIs instead require `geocode` + >= 2 sources). A non-`verified` POI may omit `geocode` and carry a single source — that is how a Nominatim miss (D7) or single-source candidate is recorded without fabricating coordinates or padding a second source. If a `must_do` item fails, stop and tell the user explicitly.

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
| Writing a POI with no `geocode` as verified | No coordinates → `unverified` (D7: recorded for manual confirmation), never written as `verified`. |
| Ignoring a region mismatch | Coordinates outside claimed district → `conflicting` + `conflict_note`, stop. |
