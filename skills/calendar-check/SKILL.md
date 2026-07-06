---
name: calendar-check
description: Use when trip-brief.yaml is ready and the destination's public-holiday calendar overlapping the trip dates must be established before synthesis. Produces calendar.yaml.
---

# calendar-check

Establish the destination's public-holiday calendar for the trip date range so synthesis can schedule around crowds and closures. Produces `trips/<slug>/calendar.yaml` (schema: `schemas/calendar.schema.json`).

Two closure axes feed synthesis. This stage owns the **trip-wide** axis (public holidays); the **per-POI** axis (fixed weekly/holiday closures) is recorded on `verified-pois.yaml` by `source-verify`.

## Method

- Read `dates.start`/`dates.end` and the destination from `trip-brief.yaml`.
- Use the consumer harness `WebSearch`; prefer the **official** government holiday calendar (e.g. a national gazette / government portal), in the local language.
- List every public holiday that falls within the trip range, **including substitute/observed holidays** (e.g. a Sunday holiday's Monday make-up day — these draw weekend-level crowds).
- For each holiday record `date`, `name_local`, `name_display`, `type`, and `impact`:
  - `crowds: true` — major attractions/markets are packed (treat like a weekend).
  - `closures: true` — government offices, banks, or many small shops shut.
- Each holiday needs >= 1 **official** source. For date facts one official source suffices;
  `travel-advisory`'s regulation items additionally need a corroborating source — do not
  conflate the two bars.
- **Trip-year coverage.** The official source must explicitly state the **trip year's**
  dates — last year's calendar is not evidence for this year. If the trip-year calendar is
  not yet published, mark affected entries `provisional: true` (schema field) and surface
  them to the user as a re-check-before-travel item.

## Output

Write `trips/<slug>/calendar.yaml`, then validate it:
`python scripts/validate_artifact.py trips/<slug>/calendar.yaml`
(exit 0 required before returning). Return to `tripwork:orchestrator`. Crowd/closure logic for synthesis lives in `scripts/calendar.py` (`is_high_crowd`, `holiday_on`, `poi_closed_on`).

## Stop-on-Confirmation

If a public holiday with `closures: true` overlaps a day a `must_do` item can only be done on → surface it and ask the user before synthesis proceeds.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/trip-brief.yaml` (destination + `dates`). |
| Output | `trips/<slug>/calendar.yaml` (public holidays in range with `impact` + official source). |
| Stop condition | A `closures: true` holiday blocks the only feasible day for a `must_do` → ask user. |
| Next stage | `tripwork:orchestrator`. |
