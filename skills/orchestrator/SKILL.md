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
- `trips/<slug>/transit.yaml`
- `trips/<slug>/cost.yaml`
- `trips/<slug>/advisory.yaml`
- `trips/<slug>/itinerary.md`
- `trips/<slug>/exports/<slug>-itinerary.md`
- `trips/<slug>/gate-report.yaml`
- `trips/<slug>/export-gate-report.yaml`
- `work/<slug>/stage-state.yaml`

## Definitions

- **ready** (used by rules 4-15): a `trips/<slug>/<artifact>.yaml` that exists, is
  schema-valid, and — for verified-pois — contains ≥ 1 `verify_status: verified` item.
- **stale** (rule 3): at least one `candidates.yaml` candidate id is absent from
  `verified-pois.yaml` `pois[]` (or `candidates.yaml` is newer than `verified-pois.yaml`).
  Re-verify only the missing/changed ids, reusing the geocode cache. Predicate:
  `scripts/orchestration.py::candidates_stale`.

## Stage Selection

0. If `work/.preflight-completed` is absent → run `tripwork:workspace-shape-preflight` first.
0.5. **Bind `<slug>` first.** A new request must allocate a `<slug>` that does **not**
   already exist under `trips/`; a resumed request must name or confirm exactly one
   existing `trips/<slug>/`. Never apply rules 1-16 across different `trips/<slug>/` dirs.
1. No trip-brief.yaml -> run `tripwork:trip-brief`.
2. No candidates.yaml -> run `tripwork:destination-research`.
3. candidates exist but verified-pois.yaml **stale** (see Definitions) or missing -> run `tripwork:source-verify`.
4. verified-pois **ready**, no routing.yaml -> run `tripwork:routing-audit`.
5. routing ready, no accommodations.yaml -> run `tripwork:accommodation-research`.
6. accommodations ready, no legs.yaml -> run `tripwork:inter-stop-legs`.
7. legs ready, no calendar.yaml -> run `tripwork:calendar-check`.
8. calendar ready, no seasonal.yaml -> run `tripwork:seasonal-advisory`.
9. seasonal ready, no transit.yaml -> run `tripwork:transit-detail`.
10. transit ready, no cost.yaml -> run `tripwork:cost-rollup`.
11. cost ready, and advisory.yaml absent **or stale relative to itinerary.md** (advisory
    older than itinerary, or written by a standalone invocation) -> run `tripwork:travel-advisory`.
12. advisory ready, no itinerary.md -> run `tripwork:itinerary-synthesis`.
13. itinerary exists, and no gate-report.yaml **or itinerary.md newer than gate-report.yaml** -> run `tripwork:itinerary-gate`.
13.5. **gate-report.yaml status==fail** -> route by failure class, invalidating the stale
    gate-report (and the artifact being regenerated): no-meal / unknown-POI / non-verified /
    geocode / closed-day / must_do / advisory-surface failures -> run `tripwork:itinerary-synthesis`
    (regenerate itinerary.yaml + itinerary.md); lodging / facility failures -> run
    `tripwork:accommodation-research`. Then re-run rule 13.
14. gate-report status==pass, no exports/<slug>-itinerary.md -> run `tripwork:export-artifact`.
15. export deliverable exists, no export-gate-report.yaml -> run `tripwork:export-gate`. If
    `export-gate-report` status==fail (a genuine render defect — naked `$`, broken link,
    missing photo) -> delete the stale export-gate-report and return to
    `tripwork:export-artifact` to re-render. A non-distributable label is NOT a fail (see
    rule 16), so it never triggers this loop. (P7)
16. **export-gate-report status==pass -> pipeline complete.** Report the deliverables
    (`exports/<slug>-itinerary.md`, maps links, LINE text, optional Notion) and stop. If the
    report also carries `distributable: false` (a personal / google-photo variant), report
    it as **complete — non-distributable (勿散布)**: a terminal state, NOT something to
    re-export or "fix". (P7)

After each stage completes, re-invoke this skill to pick the next stage.

## Stop-on-Confirmation

Halt and ask the user when a stage reports: cross-source conflict, hop flagged `far` or
`implausible`, booking lead-time missed (owned by `tripwork:itinerary-synthesis` via
`scripts/booking.py::lead_time_missed`), a regulation tagged `banned` (restricted/info are
surfaced, not halted), must-do verification failure, an unfilled overnight stop needing a
lodging pick or a missing required facility, an arrival after a lodging's reception close
with no late check-in, a `blocking` seasonal hazard, a leg flagged `drive_too_long` /
`missed_last_service` (including the synthesis-time re-check once the departure is known),
or the cost estimate over a set budget.

**Read-back before re-asking.** Before halting on any of the above, consult
`work/<slug>/stage-state.yaml` (schema: `schemas/stage-state.schema.json`): skip any
confirmation whose `(stage, flag, subject)` tuple already carries a recorded `decision`.
Record every new decision there before continuing.

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
