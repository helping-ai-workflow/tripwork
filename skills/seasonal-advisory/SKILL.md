---
name: seasonal-advisory
description: Use when calendar.yaml is ready and the destination's seasonal/weather hazards over the trip dates must be established before synthesis. No-key, Source-Verified-First. Produces seasonal.yaml.
---

# seasonal-advisory — seasonal/weather hazards + daylight

Establish the seasonal/weather hazards (driving conditions, heat, typhoon/monsoon, etc.)
for the destination over the trip dates, and compute daylight for each overnight stop.
Produces `trips/<slug>/seasonal.yaml` (schema: `schemas/seasonal.schema.json`). Mirrors
`calendar-check`: an official-source environmental advisory, **not** an iron-rule gate.

## Method (no API key)

- Use the consumer harness `WebSearch`; prefer **official** local-language sources: the
  national road authority (e.g. NZTA road conditions), the met service, and the parks /
  alpine authority (e.g. DOC alpine warnings). The plugin bundles no weather API — this is
  climatological/official-source research, the same model as `calendar-check`.
- Record each hazard as an `items[]` entry: `hazard` (open vocabulary — `road_closure`,
  `chains_required`, `heat`, `typhoon`, `monsoon`, `altitude`, …), `note`, `severity`,
  optional `applies_to` / `effective_window`, and `sources` (≥ 1 **official**).

## Two-tier severity

- **`blocking` (hard)** — a hazard that makes a planned leg/stop infeasible (an alpine
  pass officially closed in the trip window between two overnight stops). → **stop and ask
  the user** before synthesis (same pattern as a routing `far` hop or a `travel-advisory`
  `banned` item). Record the decision in `work/<slug>/stage-state.yaml`.
- **`advisory` / `info` (soft)** — chains often required, carry warm gear, short daylight,
  heat/hydration, typhoon-season flexibility. → fed into the synthesis checklist /
  contingency; never blocks.

## Daylight (computed, `scripts/season.py`)

For each overnight stop, compute `approx_sunset(date, lat)` using the stop's latitude
(`routing.yaml` cluster `centroid` or `accommodations.yaml` chosen-lodging geocode), and
record it in `daylight[]`. When `trip-brief.transport` indicates self-drive, flag any
driving leg whose estimated arrival is `after_dark(arrival, date, lat)` — emit an
`advisory` item ("leg arrives after sunset; start earlier") and set
`daylight[].after_dark_arrival: true`. The computation is approximate (local solar time,
~±15-20 min); present it as guidance, not an exact time.

## Output

Write `seasonal.yaml`, validate, return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/trip-brief.yaml` (destination, dates, transport) + `trips/<slug>/routing.yaml` + `trips/<slug>/accommodations.yaml`. |
| Output | `trips/<slug>/seasonal.yaml` (hazard `items` + per-stop `daylight`). |
| Stop condition | A `blocking` hazard makes a leg/stop infeasible → ask user. |
| Next stage | `tripwork:orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Citing a weather blog for a road closure | Need ≥ 1 official source (road authority / met service / parks). |
| Presenting `approx_sunset` as exact | It is a no-key approximation (~±15-20 min); guidance only. |
| Hard-failing on a `chains_required` advisory | Only `blocking` stops; `advisory`/`info` go to the checklist. |
