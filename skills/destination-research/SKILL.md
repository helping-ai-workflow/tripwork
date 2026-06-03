---
name: destination-research
description: Use when trip-brief.yaml exists and candidate POIs/restaurants must be gathered before verification. Produces candidates.yaml.
---

# destination-research

Gather a *candidate pool* into `trips/<slug>/candidates.yaml` (schema: `schemas/candidates.schema.json`). This stage is breadth-first and explicitly NOT trusted — verification happens later.

## Method

- Use the consumer harness `WebSearch` tool. The plugin bundles no search engine.
- For each topic in `must_do` + standard categories (food, sights, shopping), search broadly.
- **Always include local-language queries** (e.g. Korean for Korea) — local sources surface places international sources miss, and a local source is required to pass `source-verify`.
- Record every source URL with its `lang`. Capture `claimed_district` when a source states a location, but treat it as a claim, not a fact.

## Caching

Write raw search results under `work/<slug>/research-cache/` to avoid repeat queries on re-runs.

## Output

Write `candidates.yaml`, validate, return to `tripwork:orchestrator`. Do NOT assign `verify_status` here — that is `source-verify`'s job.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/trip-brief.yaml`. |
| Output | `trips/<slug>/candidates.yaml` (untrusted pool) + `work/<slug>/research-cache/`. |
| Stop condition | None — breadth-first gathering; trust decisions belong to `source-verify`. |
| Next stage | `tripwork:orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Skipping local-language queries | A local source is required to pass verification; always search in the destination language. |
| Assigning `verify_status` here | This stage only gathers; verification is `source-verify`. |
| Recording a `claimed_district` as fact | It is a claim; geocode confirms it later. |
