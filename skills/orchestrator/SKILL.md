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
- `trips/<slug>/advisory.yaml`
- `trips/<slug>/itinerary.md`
- `work/<slug>/stage-state.yaml`

## Stage Selection

0. If `work/.preflight-completed` is absent → run `tripwork:workspace-shape-preflight` first.
1. No trip-brief.yaml -> run `trip-brief`.
2. No candidates.yaml -> run `destination-research`.
3. candidates exist but verified-pois.yaml stale/missing -> run `source-verify`.
4. verified-pois ready, no routing.yaml -> run `routing-audit`.
5. routing ready, no itinerary.md -> run `itinerary-synthesis`.
6. itinerary exists, no advisory.yaml -> run `travel-advisory`.
7. advisory ready -> run `itinerary-gate`.
8. gate-report status==pass -> run `export-artifact`.

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
