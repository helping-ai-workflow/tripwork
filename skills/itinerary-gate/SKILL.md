---
name: itinerary-gate
description: Use when itinerary.yaml + advisory.yaml are ready and the plan must be validated before export. Mechanical gate. Produces gate-report.yaml.
---

# itinerary-gate — mechanical plan check

Reads the **canonical `itinerary.yaml`** (never re-builds a day structure from the rendered
`.md`). Content correctness of each source is `source-verify`'s job; this gate checks the
assembled plan obeys the iron rules. Call
`run_gate(verified_pois, itinerary, accommodations=…, facility_needs=…, calendar=…, advisory=…, must_do=…)`.

## Checks (logic in `scripts/gate.py::run_gate`)

- `referenced_pois_verified` — every `poi_id` (and each day's `lodging`) referenced by the
  itinerary is `verify_status: verified` in verified-pois. A `conflicting`/`unverified` POI
  fails the gate even though it has a geocode.
- `referenced_pois_geocoded` — every referenced POI has a non-null `geocode`.
- `days_have_meals` — every day has at least one `slot: meal` row.
- `no_closed_day_violation` (when `calendar` passed) — no POI is scheduled on a day it is
  closed (`scripts/calendar.py::poi_closed_on`).
- `must_do_covered` (when `must_do` passed) — every `trip-brief` must_do id is scheduled.
- `advisory_items_surfaced` (when `advisory` passed) — every `risk: banned`/`restricted`
  advisory `topic` appears in the itinerary `checklist` or a row text.
- `overnight_stops_have_lodging` / `required_facilities_met` (when `accommodations` passed) —
  every overnight stop has a `chosen` lodging meeting `trip-brief.facility_needs.required`.

(Periodic-facility coverage is advisory and surfaced by `itinerary-synthesis`, not gated
here. The accommodation/calendar/advisory/must_do checks run only when their input is present.)

## Output

Write `trips/<slug>/gate-report.yaml` (schema: `schemas/gate-report.schema.json`). If `status: fail`, list each failure and return to the responsible upstream stage via `tripwork:orchestrator`. Only `status: pass` permits `export-artifact`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/itinerary.yaml` + `trips/<slug>/verified-pois.yaml` + `trips/<slug>/accommodations.yaml` + `trips/<slug>/calendar.yaml` + `trips/<slug>/advisory.yaml` + `trip-brief` must_do. |
| Output | `trips/<slug>/gate-report.yaml` (`status` pass/fail + failures). |
| Stop condition | `status: fail` → return to the responsible upstream stage. |
| Next stage | `tripwork:orchestrator` (which routes to `export-artifact` only on pass). |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Re-judging content correctness here | Structure only; content is `source-verify`'s job. |
| Passing despite a missing geocode | Geocode presence is a hard structural check. |
