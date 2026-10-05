---
name: itinerary-synthesis
description: Use when verified-pois + routing + accommodations + legs + calendar + seasonal + transit + cost + advisory are ready and a day-by-day itinerary must be produced. Produces itinerary.yaml.
---

# itinerary-synthesis

Compose the canonical `trips/<slug>/data/itinerary.yaml` from verified POIs and routing clusters. The markdown deliverable is rendered from it later by `tripwork:export-artifact`; synthesis writes no markdown.

## Rules

- Use ONLY `verify_status: verified` POIs. Pulling a non-verified POI is a gate violation.
- Keep cross-region hops within `max_hop_mins`; cluster base-district days together to conserve energy when members include elderly/children.
- Each day: a table of time-slot rows. Each restaurant/POI row carries its POI id so export can attach a maps link.
- **Japanese gloss discipline.** Any inline Japanese term in a row text or checklist
  item MUST be written as `日文（中文）` — keep the original for source-verify
  traceability, add a Chinese gloss for the reader. This is what satisfies
  `export-gate`'s `japanese_glossed` check (an unglossed kana run is a hard fail).
- **Content hygiene.** Row text and checklist items are user-facing prose. NEVER embed
  an internal `poi_id` token (e.g. `(hak-goryokaku)`) — the `poi_id` belongs in the
  structured `row.poi_id` field only, which export uses to build the maps link. NEVER
  write the literal `must_do` in user-facing text; express it as plain prose (e.g.
  至少一晚溫泉旅館含會席). This is what satisfies `export-gate`'s `no_internal_jargon`
  check (a leaked id token or `must_do` is a hard fail).
- **Prose style.** Row text and checklist items are read by a person, not filled into a template — see [references/prose-style.md](references/prose-style.md) for the judgment calls (三項並列、節奏、具體 vs 空泛). The mechanical patterns (破折號、粗體、裝飾性 emoji、AI 套語) are enforced by `scripts/text_hygiene.py::ai_tone_failures` as `itinerary-gate`'s `no_ai_tone` check, and a hit routes straight back here.
- **must_do coverage.** `trip-brief.must_do` entries are free-text themes
  (e.g. `日月潭遊湖賞景`), NOT POI ids. For each theme, decide which scheduled verified
  POI(s) satisfy it and record the mapping in `itinerary.yaml` under
  `must_do_coverage: {theme: [poi_id, …]}`. `itinerary-gate` passes a theme when ≥1 of its
  mapped ids is actually scheduled — a theme with no covering scheduled POI is a gate fail.
  (An entry that is itself a scheduled POI id self-covers, so legacy id-based must_do still
  works.) If a theme cannot be covered by any verified POI → stop and ask the user.

## Day chain (v1.0 reader)

Each day's `rows` is one chain: **last night's lodging (day 1: the arrival point) → first
stop → … → last stop → tonight's lodging (last day: the departure point)**.

- Row 0 and the last row are `slot: move`. Between any two stops there is at least one move
  row (several in a row = a multi-leg transfer). A midday return to the hotel is a stop.
- Every stop row (any non-move row) carries a verified `poi_id` — a meal "somewhere near the
  ropeway" is not a stop until source-verify has verified the place. The reader gives every
  row a navigation button; no place, no button.
- Every move row without a `leg_index` records `mode` (`walk` / `rail` / `bus` / `taxi` /
  `drive` / `ferry` / `flight` / `ropeway` / `none`), `mins`, `km`, and `basis`: `sourced`
  with `source_url`, or `estimated` with `estimate_method` (the gate re-derives an estimate from the two stops' coordinates).
  `mode: none` needs nothing else — use it when both ends are the same place, e.g. breakfast
  at the hotel or dinner at the 飯店 you sleep in. An inter-stop leg from `legs.yaml` keeps
  its `leg_index` and takes its fields from there.
- `itinerary-gate` re-derives every move with a POI at both ends
  (`scripts/rederive.py::rederive_moves`): `km` may not be shorter than the straight line and
  `mins` may not beat `scripts/rederive.py::move_floor_mins` for the mode. Record the real
  number — a timetable or a route engine — never a guess raised until it passes.

## Alternatives and options (v1.0 reader)

Fallbacks hang under the stop they belong to, in `days[].alternatives`:
`{kind: 備案 | 選項, applies_to: <that stop's poi_id>, trigger, fallback, poi_id}`.
The fallback place is a stop like any other — its `poi_id` must be verified; if it is not,
send it to source-verify first. Never write inline `▸ 備案(…)｜…` rows, and never a trip-level
`contingency` list; `itinerary-gate` fails both (`legacy …`). An alternative is a place;
advice (a holiday, an IC card, a laundry gap, a seasonal hazard) goes to the checklist or the
row text, never into `alternatives`. A fallback place closed on that day fails the gate too.

## Day theme (v1.0 reader)

Each day records six `theme_candidates` — short lines, each one shape × one twist, ≤13 characters
with punctuation (`早市的蟹，山頂的夜`) — and `theme`, the one the user picks (`theme_refs`: the
`poi_id`s of that day's stops it rests on). A line may paint a picture; it may not invent anything
the day does not hold. No two days share a theme. Rules, quotas and the pick flow:
[references/day-titles.md](references/day-titles.md); style: [references/prose-style.md](references/prose-style.md) §四.
Once the candidates are written, **stop and let the user pick** (`day_title_pick`) with the title
picker page.

## Calendar-awareness (reads `calendar.yaml` + each POI's `closed_days`)

Logic in `scripts/calendar.py` (`poi_closed_on`, `is_high_crowd`, `holiday_on`).

- **Hard-avoid closures.** Never place a POI on a day `poi_closed_on(poi, date, calendar)` returns closed (weekly fixed day, one-off date, or `public_holiday`). Move it to an open trip day or fall back to its alternative. If a `must_do` POI is closed on **every** feasible trip day → stop and ask the user.
- **Holiday/weekend crowd handling.** For any day `is_high_crowd(date, calendar)` is true (weekend, or a public holiday flagged `crowds`): label the day with the holiday name, advise an earlier start + off-peak dining, and steer crowd-fragile spots (small shops, queue-heavy restaurants) onto calmer days. Do not silently leave them on the packed day.
- Push holiday facts + any closure-driven reschedule into the **Pre-trip checklist**.

## Closing-buffer check (reads each POI's `hours`)

Day-granularity closure (above) is not enough — a place open on the chosen day can still be reached too late. For every scheduled item with a start time and a POI carrying `hours`, run `scripts/hours.py::closing_status(start, close, last_call, need_mins)` where `last_call` = `last_order` (meals) or `last_entry` (sights), and `need_mins` = `max(trip-brief.scheduling.min_buffer_mins (default 30), hours.typical_visit_mins or trip-brief.scheduling.default_visit_mins (default 60))`.

- `after_last_call` / `closed` → never schedule there at that time; move the item earlier or to another day. If a `must_do` POI cannot fit before its last order/entry on **any** feasible slot/day → stop and ask the user.
- `tight` → keep but flag the thin buffer and prefer an earlier slot; note it in the day row.
- Overnight hours (close past midnight) are not handled by `closing_status` — treat as a manual special case.
- Record the verdict on the row as `closing_status`. `itinerary-gate` re-derives it from the POI's `hours` and fails when the recorded value disagrees.

## Transit comfort (reads `transit.yaml`)

- For a scheduled intra-city move or POI arrival whose time is `in_peak` (via
  `scripts/transit.py::in_peak(time, peak_windows, date=<the day>, area=<the POI's district>)`,
  so a window scoped to weekdays or an area does not fire elsewhere) **and** `members` include elders /
  children, advise shifting off-peak or note the rush-hour crush — never silently leave a
  luggage-laden group in the peak.
- For a POI with a `walks` entry where `scripts/transit.py::walk_too_far(mins,
  trip-brief.routing.max_walk_mins or 15)` is true, flag it (suggest a taxi from the station,
  or note the walk so an elder can plan).
- Push the `ic_card` advice and any long-walk notes into the **Pre-trip checklist**.

## Cost summary (reads `cost.yaml`)

- Render a **cost-summary block** in the deliverable: the per-category breakdown
  (accommodation / transport / pass / incidental), the `total`, the budget status, the
  rail-pass recommendation (`pass_break_even`), and any `fx_note`. Mark it clearly an
  **estimate** with its `as_of` date.
- An over-budget total is already resolved (stop-on-confirmation in `cost-rollup`) before
  synthesis runs; do not re-judge it here.

## Inter-city moves (reads `legs.yaml`)

- On a travel day (a day that moves between overnight stops), render the inter-city move as
  a first-class row: transit → the `service` + `reserved` + `transfers` + `duration_mins`;
  drive → the `duration_mins`. Do not bury the move inside a generic note. Record the move's
  two endpoints in the row's structured `from` / `to` fields so export renders an A→B
  directions link; keep `service` / `reserved` / `transfers` / `duration_mins` in the row
  `text`, not the endpoints.
- Push `reserved`-seat reminders, `pass_advice`, and `last_service` notes into the
  **Pre-trip checklist**.
- `drive_too_long` is depart-independent and already resolved in `inter-stop-legs`; do not
  re-judge it. **`missed_last_service` MUST be re-checked here**, because the planned
  departure is only known at scheduling time: when you place each travel-day transit move,
  set its now-known `depart` on the leg and re-run `scripts/legs.py::classify_leg` (or
  `misses_last_service`); `classify_leg` returns a pair `(status, reason)` -- write `status` into
  the leg's `status`. A `missed_last_service` result at synthesis time is a
  stop-on-confirmation — depart earlier, move to the next day, or change mode.
- **A `kind: home` leg is not between two overnight stops, so the rule above never places
  it.** `itinerary-gate` already re-derives its `classify_leg` verdict and
  `cost-rollup` already sums its fare, so an unrendered home leg is checked and paid for
  while staying invisible to the reader. Render it as a `move` row too: the outbound leg
  on **day 1**, the return leg on the **last day**. The row's `from` / `to` are the leg's
  own endpoints (which trace back to `trip-brief.home_origin` / `home_return`) — never
  re-derive them from the base district. **Set the row's `leg_index` to that leg's index
  in `legs.yaml`'s `legs` array.** This is not optional decoration: `itinerary-gate`'s
  `home_legs_rendered` check fails whenever a `kind: home` leg has no row referencing it
  by `leg_index` — matching is by index, never by name, because a leg's recorded
  `from`/`to` and the row text that describes it are not required to be the same string
  (e.g. a leg endpoint like `板橋（新北）` vs a row's `板橋`).

## Seasonal awareness (reads `seasonal.yaml`)

- Push every `advisory` / `info` hazard item (chains, warm gear, heat/hydration, short
  daylight) into the **Pre-trip checklist**.
- For any `daylight[]` entry with `after_dark_arrival: true`, advise an earlier start on
  that day and note the approximate sunset time on the day row (it is a no-key
  approximation — present it as guidance, not an exact time).
- `blocking` hazards are already resolved (stop-on-confirmation in `seasonal-advisory`)
  before synthesis runs; do not re-judge them here.

## Lodging placement (reads `accommodations.yaml`)

- Fill each day's `宿 <hotel>` from the overnight stop's `chosen` lodging. Render it via
  the existing `scripts/render/markdown.py::render_day_table` (the lodging dict is
  POI-shaped: `name_local` / `name_display` / `sources`), so the hotel name becomes the
  maps link and a primary `官網` / booking link is appended — no new renderer.
- **Build the render `poi_map` as verified-pois + each stop's chosen lodging.** Call
  `scripts/gate.py::poi_pool(pois, accommodations)` so a `day.lodging` id resolves
  natively — otherwise the lodging renders as a blank `—`. This is the same pool the
  `itinerary-gate` builds (it folds accommodations automatically) and that `export-artifact`
  must reuse; do NOT copy hotels into canonical `verified-pois.yaml`.
- **Periodic-facility coverage (advisory):** for each `trip-brief.facility_needs.periodic`
  entry, build the ordered stop list `[{nights, has_facility}]` from each stop's chosen
  lodging and run `scripts/facilities.py::coverage_gaps(stops, max_gap_nights)`. Any
  reported gap is pushed into the **Pre-trip checklist** as advice (e.g.
  "no laundry for 3 nights between Tekapo and Te Anau") — it never blocks the pipeline.

## Advisory-awareness (reads `advisory.yaml`)

travel-advisory runs **before** synthesis, so its rules shape the itinerary, not a footnote after it.

- `risk: banned` item → never schedule anything that relies on it; surface its `topic` + `rule`
  in the `checklist` (e.g. "spare lithium battery: carry-on only — none in checked baggage").
- `risk: restricted` item → keep, but surface its `topic` + constraint in the `checklist`.
- Every `banned`/`restricted` item's `topic` MUST appear in the `itinerary.yaml` `checklist`
  (or a day row text) — `scripts/gate.py::run_gate(..., advisory=...)` fails the gate otherwise.

## Required derived sections

1. **備案 / 選項** — for each fragile point (booking-required restaurant, outdoor activity,
   weather-exposed ride), a fallback in `days[].alternatives` on the stop it affects (see
   *Alternatives and options* above). Derived inline; not a separate skill.
2. **Pre-trip checklist** — structured items `{kind, task, due?, due_is_hard?, origin?,
   detail?, links?}` with `kind` one of 預約 / 出發前確認 / 打包. `due` is an absolute date
   (`YYYY-MM-DD[ HH:MM]`) when `due_is_hard: true`, otherwise relative text (出發前、行前 1 週).
   `origin` says where the item came from (`D6・10/17`, `入境規定`). Every stop or alternative POI with
   `booking.opens_at` gets a 預約 item with `due` = that time and `due_is_hard: true`. An item
   is an action to tick off; do not restate a stop's opening hours or transport — those
   already live on the day. Packing items that repeat an entry rule may stay (reinforcement).
   Quote `due` (and `opens_at`) in YAML — `due: "2026-10-17 08:00"`; an unquoted date parses as
   a date object and fails the schema.
   Do not write location notes for approximate coordinates here; the renderers append one per
   scheduled POI or lodging whose geocode is `cluster_fallback` or `nominatim_address`
   (`scripts/render/centroid.py`).
   Auto-extract from verified-pois `booking.required==true` (with `lead_time` /
   `lead_time_days`) plus passport/visa basics. For each booking carrying `lead_time_days`,
   run `scripts/booking.py::lead_time_missed(today, trip-brief.dates.start, lead_time_days)`;
   a `True` is a **booking lead-time missed** stop-on-confirmation.

## Output

Write `trips/<slug>/data/itinerary.yaml` as the **canonical** artifact (schema:
`schemas/itinerary.schema.json`) — `{checklist, must_do_coverage,
days:[{date, label, theme, theme_refs, alternatives, rows:[{time, slot, poi_id, text, from,
to, mode, mins, km, basis, …}], lodging}]}`. Include `must_do_coverage` (theme → covering
scheduled POI ids) whenever `trip-brief.must_do` is non-empty. Write no `title`: every deliverable is headed by trip-brief's `headline`. Each row references a POI by `poi_id` (matching a
`verify_status: verified` id in `verified-pois.yaml`); `slot ∈ meal|activity|visit|move|lodging`.
For a `slot: move` row, put the two endpoints in the optional structured `from` / `to` fields
(e.g. `from: 函館空港`, `to: 函館駅`) — **not** buried in `text`. Export builds an A→B Google Maps
**directions** link from them; a move row that leaves `from` / `to` empty renders as plain text
with no directions link. (`from` / `to` are optional and backward-compatible.)
`tripwork:export-artifact` renders the markdown deliverable from it via
`scripts/render/markdown.py::render_markdown_page(itin, poi_map, cost, brief=brief)` — the page-level
entrypoint that assembles every day's `render_day_table(day, poi_map)` plus the 備案 / 出發前
檢查清單 / 費用估算 sections in one pass; never hand-assemble those sections around the day
tables.

`itinerary.gate`, the HTML / Google-Maps / Notion exports all read `itinerary.yaml` — never
re-build a day structure from the rendered `.md`. The `.md` is a derived view, not a source.

Validate the canonical artifact: `python scripts/validate_artifact.py trips/<slug>/data/itinerary.yaml`
(exit 0 required before returning). Return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | verified-pois + routing + accommodations + legs (empty only if no inter-stop moves and no home endpoints) + calendar + seasonal + transit + cost + advisory — all nine trip artifacts, read but deliberately NOT individually tracked as `_DEPS` edges (`scripts/orchestration.py`): re-synthesis is the expensive branch, so this artifact's own freshness is decided by rule 13's report-tier check instead of a research-tier content diff — see `deps_stale`'s docstring. |
| Output | `trips/<slug>/data/itinerary.yaml` (canonical). |
| Stop condition | A `must_do` theme has no verified POI to cover it (`must_do_uncovered`), is closed on every feasible trip day (`must_do_closed_every_day`), or cannot fit before its last order/entry on any feasible slot (`must_do_after_last_call`); a booking whose **lead-time missed** (`lead_time_missed`); or a travel-day move that re-checks `missed_last_service` at its now-known departure → ask user. Six title candidates a day are written (`day_title_pick`) → give the user the title picker (`scripts/title_picker.py`) and apply their reply (`scripts/title_picks.py`). |
| Next stage | `tripwork:orchestrator`. |
