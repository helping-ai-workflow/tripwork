---
name: inter-stop-legs
description: Use when overnight stops are established and the mode-aware legs between them (rail/drive/bus/flight) must be researched and feasibility-checked before synthesis. Produces legs.yaml.
---

# inter-stop-legs — city-to-city legs between overnight stops

Build one leg for each pair of consecutive `trip-brief.overnight_stops`. Produces
`trips/<slug>/legs.yaml` (schema: `schemas/legs.schema.json`). Applies
**Source-Verified-First** to the timetable facts (a wrong last-service time strands the
traveller). A single-base trip (no `overnight_stops` sequence, or length ≤ 1) has no legs;
write an empty `legs` list and return.

## Mode selection (per leg)

The leg INTO stop `i` (from stop `i-1`) uses `overnight_stops[i].leg_mode` if set, else the
trip-level `trip-brief.transport`. If neither is set, assume the destination's most likely
public mode and note the assumption.

## Research (no timetable API)

Use the consumer harness `WebSearch`; prefer **official** local-language sources (rail
operator timetable e.g. JR / Korail, intercity bus operator, road authority). `mode` is one
of `drive | rail | bus | flight | ferry` (schema-enforced enum — never a freeform label like
"self_drive"). A `drive` leg MUST carry a measured `duration_mins` (the schema requires it and
`scripts/legs.py::classify_leg` raises rather than defaulting an unmeasured drive to feasible).
Record `duration_mins`, and per mode:
- **transit** (rail/bus/flight) — `service` (e.g. "Nozomi 21"), `reserved` (seat needed/
  recommended), `transfers`, `depart` (planned same-day departure, when a same-day move is
  scheduled), `last_service` (last train/bus), and a text `pass_advice` (is a rail/regional
  pass likely worth it given the leg count — a research-based judgement, **not** a precise
  fare calc; precise break-even is deferred to B3).
- **drive** — `duration_mins`.

Also record the numeric **cost** for the rollup: each leg's `fare` (amount + currency) and,
when a regional/rail pass applies, a trip-level `pass` object (`name`, `price`, `covers`).
`cost-rollup` computes the precise pass break-even from these — `pass_advice` stays as the
human-readable note.

## Feasibility (logic in `scripts/legs.py::classify_leg`)

Run `classify_leg(leg, trip-brief.routing.max_single_drive_mins or 300)`:
- `drive_too_long` — a single-day drive over the maximum (default 300 min) → **stop and
  ask** (split across two days / add a midpoint overnight).
- `missed_last_service` — a planned same-day departure later than the last train/bus →
  **stop and ask** (depart earlier / go next day / change mode).
Both stops mirror a routing `far` hop / a `seasonal` `blocking` item; record the decision
in `work/<slug>/stage-state.yaml` before continuing.

## Output

Write `legs.yaml`, validate, return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/trip-brief.yaml` (overnight_stops, transport, leg_mode, routing.max_single_drive_mins) + `trips/<slug>/routing.yaml` + `trips/<slug>/accommodations.yaml`. |
| Output | `trips/<slug>/legs.yaml` (mode-aware legs + feasibility status). |
| Stop condition | A `drive_too_long` or `missed_last_service` leg → ask user. |
| Next stage | `tripwork:orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Citing a blog for a last-service time | Need >= 1 official source (operator timetable). |
| Computing a precise rail-pass saving | v0.8.0 gives a text `pass_advice`; precise break-even is B3. |
| Modelling intra-city subway hops here | This stage owns only inter-stop legs; intra-city stays in routing-audit. |
