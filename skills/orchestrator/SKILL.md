---
name: orchestrator
description: Use when a tripwork stage has completed and the next stage must be selected, or when a travel-planning request must be routed into the pipeline.
---

# tripwork Orchestrator

Coordinate the staged pipeline. This skill owns stage transitions; individual stage skills return here to choose the next step.

## Inputs

Pipeline artifacts under `trips/<slug>/`, in stage order: `trip-brief.yaml`,
`advisory.yaml`, `candidates.yaml`, `verified-pois.yaml`, `routing.yaml`,
`accommodations.yaml`, `legs.yaml`, `calendar.yaml`, `seasonal.yaml`,
`transit.yaml`, `cost.yaml`, `itinerary.yaml`, `itinerary.md`, `exports/<slug>-itinerary.md`,
`gate-report.yaml`, `export-gate-report.yaml`. Orchestrator state:
`work/<slug>/stage-state.yaml`.

## Definitions

- **ready** (used by rules 4-15): a `trips/<slug>/<artifact>.yaml` that exists, is
  schema-valid, and — for verified-pois — contains ≥ 1 `verify_status: verified` item.
- **stale** (rule 3): at least one `candidates.yaml` candidate id is absent from
  `verified-pois.yaml` `pois[]` (or `candidates.yaml` is newer than `verified-pois.yaml`).
  Re-verify only the missing/changed ids, reusing the geocode cache. Predicate:
  `scripts/orchestration.py::candidates_stale`.
- **input fingerprint** (rule 11): a content hash of an upstream artifact's projected
  fields — `scripts/orchestration.py::input_fingerprint` (CLI:
  `python scripts/input_fingerprint.py <trip-brief.yaml> <projection>`). The producing
  stage records it as `input_fingerprints["<upstream>.yaml"]` on the derived artifact,
  so staleness reflects real content changes, not incidental file edits/mtimes.
- **report staleness** (rules 13 & 15): unlike rule 11, `gate-report.yaml` /
  `export-gate-report.yaml` staleness is a plain MTIME comparison against every artifact the respective CLI actually opens —
  `scripts/orchestration.py::GATE_INPUTS` / `EXPORT_GATE_INPUTS` — plus, for rule 15,
  every deliverable export_gate.py judges, `scripts/orchestration.py::EXPORT_DELIVERABLES`
  (md AND html; html is compared only once it exists — rule 14 requires only the
  md) — not just the itinerary/deliverable alone. Re-running a gate is cheap, so mtime is
  fine at the report tier. Do NOT extend mtime staleness to the RESEARCH-tier artifacts:
  there a naive mtime rule fires on a substantial fraction of the dependency edges and
  starts a non-terminating re-run cascade. That tier is covered by rule 3's
  `candidates_stale` and rule 11's input fingerprint only; `scripts/orchestration.py::_DEPS`
  / `deps_stale` is a general content-based, fail-open predicate that the router does not
  call (see its docstring).

## Stage Selection

**Run the oracle first.** Execute
`python scripts/next_stage.py trips/<slug> --work-dir work/<slug>` and follow
its `next`/`reason` output; the numbered rules below are the SPECIFICATION that
script implements (tests: `tests/test_next_stage.py`). The script does NOT
handle slug binding (rule 0.5) or stop-on-confirmation — those stay with you.
A `next: stop-and-ask` output is rule 15's non-retryable branch: halt and ask.
After fixing DATA for a rule-13.5 accommodation-class failure (lodging/facility),
just re-run the oracle — the fixing stage rewrites its own artifact with a newer
mtime than `gate-report.yaml`, and rule 13 (see below) notices that on its own.
Do not delete `gate-report.yaml` by hand.

0. If `work/.preflight-completed` is absent → run `tripwork:workspace-shape-preflight` first.
0.5. **Bind `<slug>` first.** A new request must allocate a `<slug>` that does **not**
   already exist under `trips/`; a resumed request must name or confirm exactly one
   existing `trips/<slug>/`. Never apply rules 1-16 across different `trips/<slug>/` dirs.
1. No trip-brief.yaml -> run `tripwork:trip-brief`.
1.5. **(rule 1.5)** trip-brief ready, no advisory.yaml -> run `tripwork:travel-advisory`.
   A `banned` regulation (e.g. an entry restriction) must surface BEFORE any
   research stage spends work on the destination.
2. No candidates.yaml -> run `tripwork:destination-research`.
3. candidates exist but verified-pois.yaml **stale** (see Definitions) or missing -> run `tripwork:source-verify`.
4. verified-pois **ready**, no routing.yaml -> run `tripwork:routing-audit`.
5. routing ready, no accommodations.yaml -> run `tripwork:accommodation-research`.
6. accommodations ready, no legs.yaml -> run `tripwork:inter-stop-legs`.
7. legs ready, no calendar.yaml -> run `tripwork:calendar-check`.
8. calendar ready, no seasonal.yaml -> run `tripwork:seasonal-advisory`.
9. seasonal ready, no transit.yaml -> run `tripwork:transit-detail`.
10. transit ready, no cost.yaml -> run `tripwork:cost-rollup`.
11. cost ready, and advisory.yaml **stale relative to trip-brief.yaml** -> re-run
    `tripwork:travel-advisory`. Staleness is an **input fingerprint** comparison
    (see Definitions): it fires when the brief's current fingerprint differs
    from advisory.yaml's recorded `input_fingerprints["trip-brief.yaml"]` — i.e.
    destination/dates/airline actually changed, not just any edit to the brief (an
    unrelated must_do edit does not re-trigger this stage). **Fallback only:**
    when advisory.yaml carries no recorded fingerprint, rule 11 falls back to comparing file mtimes —
    advisory older than the brief. The itinerary is deliberately NOT the staleness
    anchor: synthesis rewrites it every run and would loop advisory.
12. advisory ready, no itinerary.yaml -> run `tripwork:itinerary-synthesis`.
    (The canonical `itinerary.yaml` is the marker, not the derived `itinerary.md`.)
13. itinerary.yaml exists, and no gate-report.yaml **or itinerary.yaml newer than gate-report.yaml**
    -> run `tripwork:itinerary-gate`. gate-report.yaml must actually be
    newer than EVERY artifact `scripts/gate.py::main` reads — `GATE_INPUTS` (verified-pois /
    trip-brief / accommodations / calendar / advisory / legs / routing / cost), not itinerary.yaml
    alone — see **report staleness** in Definitions. A re-verify that only demotes a scheduled
    POI's `verify_status` never touches itinerary.yaml, so an itinerary-only anchor would let
    such a report stand as "complete" though the gate never saw the demotion.
13.5. **gate-report.yaml status==fail** -> route by failure class, invalidating the stale
    gate-report (and the artifact being regenerated). A re-derivation failure names a field
    only its PRODUCING stage can write — synthesis cannot add `km` to a routing hop, and it
    cannot add `hours.close` to a POI — so every class routes to the stage that owns the
    file. The executable form is `_ROUTES` in `scripts/orchestration.py`, matched in this
    order (`tests/test_deps_table.py::test_rule_13_5_targets_match_the_routes_table` pins
    this list against it):

    | # | Failure class | Route to |
    |---|---|---|
    | 1 | chosen / required-facility lodging failures, and `rederive_lodging`'s `accommodations stop …` / `accommodations.yaml absent` | `tripwork:accommodation-research` |
    | 2 | `legs[…]` re-derivation failures, `legs.yaml absent` | `tripwork:inter-stop-legs` |
    | 3 | `routing hop …` re-derivation failures, `routing.yaml absent` | `tripwork:routing-audit` |
    | 4 | `cost.total` / `cost.by_category` mismatches, `cost.yaml absent` | `tripwork:cost-rollup` |
    | 5 | a scheduled POI `carries neither hours.close nor hours.no_fixed_close` | `tripwork:source-verify` |
    | 6 | AI-tone hits | `tripwork:itinerary-synthesis` |
    | — | everything else (no-meal / unknown-POI / non-verified / geocode / closed-day / must_do / advisory-surface / no-resolved-lodging / unrendered home leg / missing `closing_status`) | `tripwork:itinerary-synthesis` |

    Row 5 is **not** a synthesis defect even though the gate reads it off an itinerary row:
    `hours` lives in `verified-pois.yaml` and only source-verify writes that file. Routing it
    to synthesis made the loop non-terminating — synthesis rewrites the itinerary, the same
    rows re-fail, forever. It sits LAST among the producing-stage rows because
    `verified-pois.yaml` is an upstream of routing / accommodations / legs / cost in `_DEPS`,
    so re-running it invalidates all four; fix the cheaper downstream classes first.

    Then re-run rule 13.
14. gate-report status==pass, no exports/<slug>-itinerary.md -> run `tripwork:export-artifact`.
15. export deliverable (md) exists, and no export-gate-report.yaml **or any of
    `EXPORT_DELIVERABLES`** (md — required by rule 14; html, compared only once it exists)
    **or any of `EXPORT_GATE_INPUTS`** (itinerary / verified-pois / accommodations /
    verified-pois-media) **is newer than export-gate-report.yaml** -> run
    `tripwork:export-gate` — see **report staleness** in Definitions.
    On `export-gate-report` status==fail, branch on `retryable`:
    - **retryable==true** (a render-fixable defect — naked `$`, broken link, 0 rendered
      photos) -> delete the stale export-gate-report and return to `tripwork:export-artifact`
      to re-render.
    - **retryable==false** (an upstream DATA defect re-render cannot fix — a photo with no
      attribution, a bookable POI with no official source) -> **STOP and ask the user to fix
      the data** (add the attribution / mark the official source), then re-verify. Do NOT
      loop export-artifact on it.
    A non-distributable label is NOT a fail (see rule 16), so it never triggers this loop.
16. **export-gate-report status==pass -> pipeline complete.** Report the deliverables
    (`exports/<slug>-itinerary.md`, maps links, LINE text, optional Notion) and stop. If the
    report also carries `distributable: false` (a personal / google-photo variant), report
    it as **complete — non-distributable (勿散布)**: a terminal state, NOT something to
    re-export or "fix".

After each stage completes, re-invoke this skill to pick the next stage.

## Stop-on-Confirmation

Halt and ask the user when a stage reports: cross-source conflict, hop flagged `far` or
`implausible`, booking lead-time missed (owned by `tripwork:itinerary-synthesis` via
`scripts/booking.py::lead_time_missed`), a regulation tagged `banned` (restricted/info are
surfaced, not halted), must-do verification failure, an unfilled overnight stop needing a
lodging pick or a missing required facility, an arrival after a lodging's reception close
with no late check-in, a `blocking` seasonal hazard, a leg flagged `drive_too_long` /
`missed_last_service` (including the synthesis-time re-check once the departure is known),
the cost estimate over a set budget, or an **export-gate fail that is non-retryable**
(`retryable: false` — an upstream data defect re-render can't fix; see rule 15).

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
