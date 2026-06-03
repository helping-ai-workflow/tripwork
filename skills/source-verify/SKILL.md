---
name: source-verify
description: Use when candidates.yaml exists and each candidate must be verified before it can enter the itinerary. Iron-rule gate. Produces verified-pois.yaml.
---

# source-verify — Source-Verified-First gate

This is an iron-rule gate. Apply the **Source-Verified-First** discipline to every candidate. Only candidates that pass all three gates get `verify_status: verified` and may flow downstream.

## Three gates (logic in `scripts/verify.py::classify_candidate`)

Gates are evaluated in strict order — Gate 1 fires before Gate 2, Gate 2 before Gate 3.

1. **Multi-source** (Gate 1, checked first) — >= 2 independent sources, at least one in the destination's local language. Fewer/wrong language -> `unverified`. This gate precedes geocode so a single-source candidate is never misclassified as `rejected`.
2. **Geocode** (Gate 2) — resolve the place name with `scripts/geocode.py::geocode` (OSM Nominatim, <= 1 req/s, set User-Agent). No result -> `rejected`.
3. **Region match + cross-source conflict** (Gate 3) — evaluated only after Gates 1 & 2 pass. Detect cross-source disagreement on rating/hours/address and signal it to `classify_candidate` via the `conflict_detected=True` argument (computed by this skill); on conflict -> `conflicting` + `conflict_note`, and **stop and ask the user** which source to trust. Geocoded point must also fall within the claimed district (`scripts/geocode.py::in_region`); outside -> `conflicting`, record `conflict_note`.

## Output

Write all candidates into `trips/<slug>/verified-pois.yaml` (schema: `schemas/verified-pois.schema.json`) carrying their `verify_status`. Downstream stages read ONLY `verify_status: verified`. Never silently drop a candidate — `rejected`/`conflicting`/`unverified` stay recorded with their reason. If a `must_do` item fails, stop and tell the user explicitly.

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
