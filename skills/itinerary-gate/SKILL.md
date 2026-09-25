---
name: itinerary-gate
description: Use when itinerary.yaml + advisory.yaml are ready and the plan must be validated before export. Produces gate-report.yaml.
---

# itinerary-gate — mechanical plan check

Reads the **canonical `itinerary.yaml`** (never re-builds a day structure from the rendered
`.md`). Content correctness of each source is `source-verify`'s job; this gate checks the
assembled plan obeys the iron rules. Run `python scripts/gate.py trips/<slug>` — the CLI loads
the canonical artifacts itself, folds each stop's chosen lodging, runs `run_gate`, and
writes `trips/<slug>/gate-report.yaml` (exit 0 pass / 1 fail).

## Checks (logic in `scripts/gate.py::run_gate`)

- `referenced_pois_verified` — every `poi_id` (and each day's `lodging`) referenced by the
  itinerary is `verify_status: verified` in verified-pois. A `conflicting`/`unverified` POI
  fails the gate even though it has a geocode.
- `referenced_pois_geocoded` — every referenced POI has a non-null `geocode`.
- `referenced_pois_glossed` — every referenced POI whose name carries a kana run also
  carries a `name_zh` gloss (`scripts/text_hygiene.py::kana_name_without_gloss`). The POI-level
  twin of `japanese_glossed` below, which scans the itinerary's free text.
- `days_have_meals` — every day has at least one `slot: meal` row.
- `overnight_days_have_lodging` — **ALWAYS-ON**, derived from `itinerary.yaml` alone
  (independent of accommodations.yaml): every non-final day must resolve a place to
  sleep — either a day-level `lodging` field or a `slot: "lodging"` row. A genuinely
  lodging-less night (e.g. an overnight transit) is expressed as a `slot: "lodging"`
  row describing the transit, so the night-transit case still satisfies the floor.
- `no_closed_day_violation` (when `calendar` passed) — no POI is scheduled on a day it is
  closed (`scripts/calendar.py::poi_closed_on`).
- `must_do_covered` (when `must_do` passed) — every `trip-brief` must_do id is scheduled.
- `advisory_present` — **ALWAYS-ON** safety floor: `advisory` is a **mandatory** input.
  An absent advisory **fails the gate** ("advisory absent — …"). Because the
  banned/restricted list lives only inside `advisory.yaml`, a missing advisory means the
  gate cannot verify those items are surfaced, so it must not silently pass. An advisory
  that ran but flagged nothing is passed as `{"items": []}` and clears this floor.
- `advisory_items_surfaced` (when `advisory` present) — every `risk: banned`/`restricted`
  advisory `topic` appears in the itinerary `checklist` or a row text. (Reached only once
  `advisory_present` confirms an advisory exists.)
- `no_internal_jargon` / `japanese_glossed` — **ALWAYS-ON content hygiene** over the
  canonical text (`checklist` + every row `text`): no internal `(poi-id)` token or literal
  `must_do` may leak, and every inline kana run must carry a （中文）gloss. This is the
  PRIMARY content guard — blocking a leak here keeps every renderer (md / html / line-short /
  Notion-via-md) clean at the source, including renderers with no gate of their own. The
  same checks also run render-side in `export-gate` (md/html) as defense-in-depth.
- `no_ai_tone` — **ALWAYS-ON**, same canonical text as the two checks above
  (`scripts/text_hygiene.py::ai_tone_failures`): slop words, sentence templates, promo
  clichés and meaning-stamp phrases. A hit routes back to `itinerary-synthesis`.
- `home_legs_rendered` — **ALWAYS-ON**: every `kind: home` leg in `legs.yaml` must be
  referenced by an itinerary row's `leg_index` (`scripts/gate.py::_home_legs_rendered_failures`,
  matched by index, never by name) — otherwise its `classify_leg` verdict is checked and its
  fare summed while nothing ever shows it to the reader.
- `verdicts_match` / `verdicts_rederivable` — **ALWAYS-ON** verdict re-derivation
  (`scripts/rederive.py::run_rederivation`): every recorded mechanical verdict (closing
  status, hop classification, lodging verify_status, …) is recomputed from the inputs the
  artifact itself carries. `verdicts_match` fails when a recorded verdict disagrees with the
  recomputation; `verdicts_rederivable` fails when a record is missing the inputs needed to
  re-derive it at all — a provenance gap, not a wrong verdict. A failure names the field only
  its producing stage can write, so `scripts/orchestration.py::route_gate_failures` routes it
  there, not back to synthesis by default.
- `overnight_stops_have_lodging` / `required_facilities_met` (when `accommodations` passed) —
  every overnight stop has a `chosen` lodging meeting `trip-brief.facility_needs.required`.

(Periodic-facility coverage is advisory and surfaced by `itinerary-synthesis`, not gated
here. The accommodation/calendar/must_do checks run only when their input is present;
`advisory` is the exception — it is mandatory and its absence is a gate failure.)

## Output

Write `trips/<slug>/gate-report.yaml` (schema: `schemas/gate-report.schema.json`). If `status: fail`, list each failure and return to the responsible upstream stage via `tripwork:orchestrator`. Only `status: pass` permits `export-artifact`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/itinerary.yaml` + `trips/<slug>/verified-pois.yaml` + `trips/<slug>/accommodations.yaml` + `trips/<slug>/calendar.yaml` + `trips/<slug>/advisory.yaml` + `trips/<slug>/legs.yaml` + `trips/<slug>/routing.yaml` + `trips/<slug>/cost.yaml` + `trips/<slug>/trip-brief.yaml` (must_do). |
| Output | `trips/<slug>/gate-report.yaml` (`status` pass/fail + failures). |
| Stop condition | `status: fail` → return to the responsible upstream stage. |
| Next stage | `tripwork:orchestrator` (which routes to `export-artifact` only on pass). |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Re-judging content correctness here | Structure only; content is `source-verify`'s job. |
| Passing despite a missing geocode | Geocode presence is a hard structural check. |
