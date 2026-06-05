---
name: orchestrator
description: Use when a tripwork stage has completed and the next stage must be selected, or when a travel-planning request must be routed into the pipeline. Owns all stage transitions and stop-on-confirmation.
---

# tripwork Orchestrator

Coordinate the staged pipeline. This skill owns stage transitions; individual stage skills return here to choose the next step.

## Inputs

- `trips/<slug>/trip-brief.yaml`
- `trips/<slug>/candidates.yaml`
- `trips/<slug>/verified-pois.yaml`
- `trips/<slug>/routing.yaml`
- `trips/<slug>/accommodations.yaml`
- `trips/<slug>/legs.yaml`
- `trips/<slug>/calendar.yaml`
- `trips/<slug>/seasonal.yaml`
- `trips/<slug>/cost.yaml`
- `trips/<slug>/advisory.yaml`
- `trips/<slug>/itinerary.md`
- `trips/<slug>/exports/<slug>-itinerary.md`
- `trips/<slug>/export-gate-report.yaml`
- `work/<slug>/stage-state.yaml`

## Stage Selection

0. If `work/.preflight-completed` is absent → run `tripwork:workspace-shape-preflight` first.
1. No trip-brief.yaml -> run `trip-brief`.
2. No candidates.yaml -> run `destination-research`.
3. candidates exist but verified-pois.yaml stale/missing -> run `source-verify`.
4. verified-pois ready, no routing.yaml -> run `routing-audit`.
5. routing ready, no accommodations.yaml -> run `accommodation-research`.
6. accommodations ready, no legs.yaml -> run `inter-stop-legs`.
7. legs ready, no calendar.yaml -> run `calendar-check`.
8. calendar ready, no seasonal.yaml -> run `seasonal-advisory`.
9. seasonal ready, no cost.yaml -> run `cost-rollup`.
10. cost ready, no itinerary.md -> run `itinerary-synthesis`.
11. itinerary exists, no advisory.yaml -> run `travel-advisory`.
12. advisory ready -> run `itinerary-gate`.
13. gate-report status==pass, no exports/<slug>-itinerary.md -> run `export-artifact`.
14. export deliverable exists, no export-gate-report.yaml -> run `export-gate`. If `export-gate-report` status==fail -> return to `export-artifact` to re-render.

After each stage completes, re-invoke this skill to pick the next stage.

## Stop-on-Confirmation

Halt and ask the user when a stage reports: cross-source conflict, hop flagged `far`, booking lead-time missed, regulation risk, or must-do verification failure. Record the decision in `work/<slug>/stage-state.yaml` before continuing.

## Stage Contract

| Field | Value |
|---|---|
| Input | Any of the `trips/<slug>/*.yaml` living docs + `work/<slug>/stage-state.yaml`. |
| Output | Selects and invokes the next stage skill. Writes only `stage-state.yaml`. |
| Stop condition | A stage reports a confirmation flag → halt, record, ask user. |
| Next stage | Whichever stage the selection rules pick; re-invoked after each stage. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| A stage skill jumps to the next stage itself | Only the orchestrator transitions stages; stage skills return here. |
| Advancing past a `far` hop or conflict without asking | Stop-on-confirmation is mandatory; record the decision first. |
