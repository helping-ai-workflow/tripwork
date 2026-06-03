---
name: itinerary-gate
description: Use when itinerary.md + advisory.yaml are ready and structure must be validated before export. Mechanical gate. Produces gate-report.yaml.
---

# itinerary-gate — mechanical structure check

Structure only. Content correctness is guaranteed upstream by `source-verify`; this gate does NOT re-judge content.

## Checks (logic in `scripts/gate.py::run_gate`)

- Every POI referenced by an itinerary day exists in verified-pois and has a `geocode`.
- Every day has at least one meal.

## Output

Write `trips/<slug>/gate-report.yaml` (schema: `schemas/gate-report.schema.json`). If `status: fail`, list each failure and return to the responsible upstream stage via `tripwork:orchestrator`. Only `status: pass` permits `export-artifact`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/itinerary.md` + `trips/<slug>/verified-pois.yaml`. |
| Output | `trips/<slug>/gate-report.yaml` (`status` pass/fail + failures). |
| Stop condition | `status: fail` → return to the responsible upstream stage. |
| Next stage | `tripwork:orchestrator` (which routes to `export-artifact` only on pass). |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Re-judging content correctness here | Structure only; content is `source-verify`'s job. |
| Passing despite a missing geocode | Geocode presence is a hard structural check. |
