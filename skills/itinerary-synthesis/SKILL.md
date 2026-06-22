---
name: itinerary-synthesis
description: Use when verified-pois + routing + accommodations + legs + calendar + seasonal + transit + cost + advisory are ready and a day-by-day itinerary must be produced. Produces itinerary.yaml (canonical) + itinerary.md (rendered).
---

# itinerary-synthesis

Compose the canonical `trips/<slug>/itinerary.yaml` from verified POIs and routing clusters, then render `trips/<slug>/itinerary.md` from it.

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
- **must_do coverage (P5).** `trip-brief.must_do` entries are free-text themes
  (e.g. `日月潭遊湖賞景`), NOT POI ids. For each theme, decide which scheduled verified
  POI(s) satisfy it and record the mapping in `itinerary.yaml` under
  `must_do_coverage: {theme: [poi_id, …]}`. `itinerary-gate` passes a theme when ≥1 of its
  mapped ids is actually scheduled — a theme with no covering scheduled POI is a gate fail.
  (An entry that is itself a scheduled POI id self-covers, so legacy id-based must_do still
  works.) If a theme cannot be covered by any verified POI → stop and ask the user.

## Calendar-awareness (reads `calendar.yaml` + each POI's `closed_days`)

Logic in `scripts/calendar.py` (`poi_closed_on`, `is_high_crowd`, `holiday_on`).

- **Hard-avoid closures.** Never place a POI on a day `poi_closed_on(poi, date, calendar)` returns closed (weekly fixed day, one-off date, or `public_holiday`). Move it to an open trip day or fall back to its contingency. If a `must_do` POI is closed on **every** feasible trip day → stop and ask the user.
- **Holiday/weekend crowd handling.** For any day `is_high_crowd(date, calendar)` is true (weekend, or a public holiday flagged `crowds`): label the day with the holiday name, advise an earlier start + off-peak dining, and steer crowd-fragile spots (small shops, queue-heavy restaurants) onto calmer days. Do not silently leave them on the packed day.
- Push holiday facts + any closure-driven reschedule into the **備案 / Contingency** and **Pre-trip checklist** sections.

## Closing-buffer check (reads each POI's `hours`)

Day-granularity closure (above) is not enough — a place open on the chosen day can still be reached too late. For every scheduled item with a start time and a POI carrying `hours`, run `scripts/hours.py::closing_status(start, close, last_call, need_mins)` where `last_call` = `last_order` (meals) or `last_entry` (sights), and `need_mins` = `max(trip-brief.scheduling.min_buffer_mins (default 30), hours.typical_visit_mins or trip-brief.scheduling.default_visit_mins (default 60))`.

- `after_last_call` / `closed` → never schedule there at that time; move the item earlier or to another day. If a `must_do` POI cannot fit before its last order/entry on **any** feasible slot/day → stop and ask the user.
- `tight` → keep but flag the thin buffer and prefer an earlier slot; note it in the day row.
- Overnight hours (close past midnight) are not handled by `closing_status` — treat as a manual special case.

## Transit comfort (reads `transit.yaml`)

- For a scheduled intra-city move or POI arrival whose time is `in_peak` (via
  `scripts/transit.py::in_peak` against `peak_windows`) **and** `members` include elders /
  children, advise shifting off-peak or note the rush-hour crush — never silently leave a
  luggage-laden group in the peak.
- For a POI with a `walks` entry where `scripts/transit.py::walk_too_far(mins,
  trip-brief.routing.max_walk_mins or 15)` is true, flag it (suggest a taxi from the station,
  or note the walk so an elder can plan).
- Push the `ic_card` advice and any long-walk notes into the **Pre-trip checklist /
  Contingency**.

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
  **Pre-trip checklist / Contingency**.
- `drive_too_long` is depart-independent and already resolved in `inter-stop-legs`; do not
  re-judge it. **`missed_last_service` MUST be re-checked here**, because the planned
  departure is only known at scheduling time: when you place each travel-day transit move,
  set its now-known `depart` on the leg and re-run `scripts/legs.py::classify_leg` (or
  `misses_last_service`). A `missed_last_service` result at synthesis time is a
  stop-on-confirmation — depart earlier, move to the next day, or change mode.

## Seasonal awareness (reads `seasonal.yaml`)

- Push every `advisory` / `info` hazard item (chains, warm gear, heat/hydration, short
  daylight) into the **Pre-trip checklist / Contingency**.
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
- **Build the render `poi_map` as verified-pois + each stop's chosen lodging (P4).** Fold
  in `scripts/gate.py::chosen_lodging_pois(accommodations)` so a `day.lodging` id resolves
  natively — otherwise the lodging renders as a blank `—`. This is the same pool the
  `itinerary-gate` builds (it folds accommodations automatically) and that `export-artifact`
  must reuse; do NOT copy hotels into canonical `verified-pois.yaml`.
- **Periodic-facility coverage (advisory):** for each `trip-brief.facility_needs.periodic`
  entry, build the ordered stop list `[{nights, has_facility}]` from each stop's chosen
  lodging and run `scripts/facilities.py::coverage_gaps(stops, max_gap_nights)`. Any
  reported gap is pushed into the **Pre-trip checklist / Contingency** as advice (e.g.
  "no laundry for 3 nights between Tekapo and Te Anau") — it never blocks the pipeline.

## Advisory-awareness (reads `advisory.yaml`)

travel-advisory runs **before** synthesis, so its rules shape the itinerary, not a footnote after it.

- `risk: banned` item → never schedule anything that relies on it; surface its `topic` + `rule`
  in the `checklist` (e.g. "spare lithium battery: carry-on only — none in checked baggage").
- `risk: restricted` item → keep, but surface its `topic` + constraint in the `checklist`.
- Every `banned`/`restricted` item's `topic` MUST appear in the `itinerary.yaml` `checklist`
  (or a day row text) — `scripts/gate.py::run_gate(..., advisory=...)` fails the gate otherwise.

## Required derived sections

1. **備案 / Contingency** — for each fragile point (booking-required restaurant, outdoor activity), a fallback. Derived inline; not a separate skill.
2. **Pre-trip checklist** — auto-extract from verified-pois `booking.required==true` (with `lead_time` / `lead_time_days`) plus passport/visa basics. List every booking that needs advance action. For each booking carrying `lead_time_days`, run `scripts/booking.py::lead_time_missed(today, trip-brief.dates.start, lead_time_days)`; a `True` (the trip is too soon to still book in time) is a **booking lead-time missed** stop-on-confirmation.

## Output

Write `trips/<slug>/itinerary.yaml` as the **canonical** artifact (schema:
`schemas/itinerary.schema.json`) — `{title, checklist, must_do_coverage, days:[{date, label,
rows:[{time, slot, poi_id, text, from, to}], lodging}]}`. Include `must_do_coverage`
(theme → covering scheduled POI ids, P5) whenever `trip-brief.must_do` is non-empty. Each row references a POI by `poi_id` (matching a
`verify_status: verified` id in `verified-pois.yaml`); `slot ∈ meal|activity|visit|move|lodging`.
For a `slot: move` row, put the two endpoints in the optional structured `from` / `to` fields
(e.g. `from: 函館空港`, `to: 函館駅`) — **not** buried in `text`. Export builds an A→B Google Maps
**directions** link from them; a move row that leaves `from` / `to` empty renders as plain text
with no directions link. (`from` / `to` are optional and backward-compatible.)
Then render `trips/<slug>/itinerary.md` from it via `scripts/render/markdown.py::render_day_table(day, poi_map)`.

`itinerary.gate`, LINE / Google-Maps / Notion exports all read `itinerary.yaml` — never
re-build a day structure from the rendered `.md`. The `.md` is a derived view, not a source.

Return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/verified-pois.yaml` + `trips/<slug>/routing.yaml` + `trips/<slug>/accommodations.yaml` + `trips/<slug>/legs.yaml` (empty list if single-base) + `trips/<slug>/calendar.yaml` + `trips/<slug>/seasonal.yaml` + `trips/<slug>/transit.yaml` + `trips/<slug>/cost.yaml` + `trips/<slug>/advisory.yaml`. |
| Output | `trips/<slug>/itinerary.yaml` (canonical) + `trips/<slug>/itinerary.md` (rendered: day tables + contingency + checklist sections). |
| Stop condition | A `must_do` item has no verified POI to place, is closed on every feasible trip day, or cannot fit before its last order/entry on any feasible slot; a booking whose **lead-time missed** (`lead_time_missed` True); or a travel-day move that re-checks `missed_last_service` at its now-known departure → ask user. |
| Next stage | `tripwork:orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Placing a non-verified POI | Synthesis reads only `verify_status: verified`. |
| Hand-listing bookings for the checklist | Derive from `booking.required==true`; do not retype. |
| Omitting fallbacks for booking-required meals | Every fragile point needs a contingency line. |
