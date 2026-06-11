---
name: transit-detail
description: Use when verified-pois are ready and the destination's intra-city transit comfort details (commuter peak windows, IC card, station-to-POI walks) must be established before synthesis. No-key research, advisory only. Produces transit.yaml.
---

# transit-detail — intra-city transit comfort

Research the destination's intra-city transit details that affect a group travelling with
elders / luggage. Produces `trips/<slug>/transit.yaml` (schema: `schemas/transit.schema.json`).
Everything is **advisory** — this stage never stops the pipeline.

## Research (no API key)

Use the consumer harness `WebSearch`; prefer local-language / operator sources.

- **peak_windows** — the commuter rush-hour windows (e.g. ~07:30–09:30 and ~17:30–19:30).
  Record `label`, `start`, `end`, optional `note`, and ≥ 1 `sources` (operator/official).
  Synthesis flags moves that fall in these via `scripts/transit.py::in_peak`.
- **ic_card** — the destination's stored-value card (Suica / ICOCA / PASMO / T-money /
  Octopus / EZ-Link / …): `name`, `where_to_buy`, `top_up`, `covers`, optional `note`, and
  ≥ 1 `sources` (operator site or a reputable guide). Omit `ic_card` for a cash-only destination.
- **walks** — for each transit-reached POI in `verified-pois.yaml`, the nearest `station`
  (required) and the `mins` on foot (the "last 500 m"), optional `note`, and ≥ 1 `sources`.
  Research from maps / official station info; never invent a distance or an unsourced walk.
  Synthesis flags long walks via `scripts/transit.py::walk_too_far`.

## Output

Write `transit.yaml` (validate against the schema). A walk-everywhere / cash-only trip
writes empty `peak_windows` / `walks` and no `ic_card`. Return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/trip-brief.yaml` (destination, members) + `trips/<slug>/verified-pois.yaml`. |
| Output | `trips/<slug>/transit.yaml` (peak_windows + ic_card + per-POI walks). |
| Stop condition | None — advisory only. |
| Next stage | `tripwork:orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Inventing a station-walk distance | Research it from maps / station info; never guess. |
| Citing no source for the IC card | `ic_card` needs ≥ 1 source (operator site / reputable guide). |
| Stopping the pipeline on a peak/walk flag | This stage is advisory; synthesis surfaces the flags, never blocks. |
