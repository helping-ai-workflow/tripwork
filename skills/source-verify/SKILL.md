---
name: source-verify
description: Use when candidates.yaml exists and each candidate must be verified before it can enter the itinerary. Iron-rule gate. Produces verified-pois.yaml.
---

# source-verify — Source-Verified-First gate

This is an iron-rule gate. Apply the **Source-Verified-First** discipline to every candidate. Only candidates that pass all three gates get `verify_status: verified` and may flow downstream.

## Gates (logic in `scripts/verify.py::classify_candidate`)

Call `scripts/verify.py::verify_poi(...)` as the one-call entrypoint: it runs
`normalize_and_validate_poi` first (geocode key fix + name_local discipline below),
then delegates to `classify_candidate`. The normalisation step (a) renames legacy
geocode keys `lon`/`long` to `lng`, and (b) **rejects** a POI whose `name_local`
equals its `district` — `name_local` must be the venue's real name, not the area
(this catches the cluster_fallback town-name bug). A rejecting pre-check flips the
result to `rejected` before the gates below run.

Capture a `name_zh` (Chinese gloss) on the POI here; the render layer shows it as
`name_display（name_zh）` so the deliverable stays reader-friendly. **`name_zh` is REQUIRED
when the POI's rendered name (`name_display`, else `name_local`) contains kana
(hiragana/katakana)** — without it the maps-link label renders as bare kana a Chinese reader
cannot read. (`name_display` must be non-empty.) A verified kana-named POI lacking
`name_zh` is rejected by the schema and fails `itinerary-gate` (`referenced_pois_glossed`).
Pure-Han names (e.g. 五稜郭) need no gloss; non-verified POIs are exempt (never rendered).

Gates are evaluated in strict order — Gate 0 fires before Gate 1, Gate 1 before Gate 2, Gate 2 before Gate 3.

0. **Operating** (Gate 0, checked first) — the place must still be open for business. Record a **sourced** `business_status` on the POI (Google Places vocabulary: `OPERATIONAL` / `CLOSED_TEMPORARILY` / `CLOSED_PERMANENTLY`), obtained from Google Maps ('永久停業' / 'Permanently closed' / 'Temporarily closed') or an official-site 404. `verify_poi` reads it and ENFORCES Gate 0: a CLOSED value -> `rejected`; an **absent / unknown signal -> `unverified` (never a silent `verified`)** — operating is no longer defaulted to open. A defunct POI with two sources and a geocode would otherwise sail through as `verified`; Gate 0 stops that. (P1) **While the POI's Google Maps card is open for this operating check, also record its `gmaps_place_id`** — it is free at that point and lets export build a canonical `maps/place/?q=place_id:` deep-link to the exact place; without it the maps link degrades to a name search. (P9 coverage / F3)
1. **Multi-source** (Gate 1) — >= 2 **independent** sources, at least one in the destination's local language. Pass `trip-brief.destination.local_lang` as `classify_candidate(..., local_lang=...)`. **Independent** = different operating entities: a different **root domain** AND not one merely quoting the other (one aggregator + one official site qualifies; two pages of the same site do not — `classify_candidate` counts distinct domains, not raw list length). Fewer/wrong language -> `unverified`. This gate precedes geocode so a single-source candidate is never misclassified as `rejected`.

**Source `official` flag.** When a source is the POI's own official site / official booking page, mark that source `official: true`. export-gate requires a bookable POI's row to carry its official link, and the renderer labels the primary link `官網` — without the flag a non-official aggregator link is mislabelled and the bookable check has nothing to match.
2. **Geocode** (Gate 2) — resolve the place with `scripts/geocode.py::resolve_place` (structured Nominatim query first, then free-text fallbacks; <= 1 req/s, set User-Agent). **Query by `name_local`** (the destination-language name recorded on the candidate), not an English display name — live Nominatim mis-resolves English descriptor suffixes (e.g. `"Togetsukyo Bridge"` returns nothing while `渡月橋` resolves). Append the district/city for disambiguation but keep the core name local. **Pass `name_roman` as `resolve_place(..., name_roman=...)`** so a famous CJK landmark the street-slot query misses (日月潭文武廟, 九族文化村, 向山遊客中心 …) still resolves first-pass via its English / bare-core name instead of degrading to `unverified` (P3). This matches export's `name_local`-based maps links. Record `geocode.geocode_source`. **Name-match confirmation (P2):** pass the resolved place's `display_name` back as `verify_poi(..., resolved_name=...)` — if it does not correspond to the queried venue (a renamed nearby place / name drift, e.g. querying 星月大地 but Nominatim returns 星月驛站) the POI is `conflicting` ('name mismatch'), never `verified`. **D7:** a real place Nominatim cannot resolve degrades to `unverified` (recorded for manual confirmation) — never silently `rejected`. Pass a per-trip cache (`work/<slug>/geocode-cache/geocode.json` via `scripts/geocode_cache.py`) as `resolve_place(..., cache=cache)` — load it once at the start and save it at the end so re-runs skip already-resolved and known-miss lookups.
3. **Region match + cross-source conflict** (Gate 3) — evaluated only after Gates 1 & 2 pass. A **conflict** is a *material factual disagreement* between independent sources — opening hours, closed day, or address differ in a way that changes the plan (a star-rating decimal difference is not material). Signal it via `conflict_detected=True`; on conflict -> `conflicting` + `conflict_note`, and **stop and ask the user** which source to trust. For the region check, resolve each **claimed district once** via `scripts/geocode.py::resolve_place(district, city, country)` using the same per-trip cache, record the district centroid (e.g. under `work/<slug>/`), and pass it to `scripts/geocode.py::in_region` (radius defaults to 5 km, overridable via `trip-brief.routing.region_radius_km`); a POI outside -> `conflicting`, record `conflict_note`.

## Record closure days + hours

While verifying opening hours, record each POI's `closed_days` (the per-POI closure axis consumed by synthesis via `scripts/calendar.py::poi_closed_on`). Values: weekday names (`tuesday`) for fixed weekly closures, ISO dates (`2026-05-25`) for one-off closures, or the token `public_holiday` when a place shuts on any public holiday. Closures come from the same cross-source hours check — a POI's stated regular closing day (e.g. a palace closed Tuesdays, a small shop closed on holidays) belongs here, not invented.

Also record the intra-day `hours` object (consumed by synthesis via `scripts/hours.py::closing_status`): `close`, and where applicable `last_order` (restaurant L.O.) / `last_entry` (sight last admission), plus `typical_visit_mins` (how long a visit needs). These come from the same verified sources — never guess a closing time. **Recency:** hours / `closed_days` must come from the official page or a source dated within the last 12 months; record `hours.as_of` (the date the hours were stated) so stale opening times can be re-checked rather than silently driving minute-level scheduling.

**Cache invalidation on re-verify.** When the user manually confirms a place or asks to re-verify, delete that POI's `cache_key` entry from `work/<slug>/geocode-cache/geocode.json` before re-running — otherwise a cached miss (D7 negative cache) permanently suppresses the re-query.

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
