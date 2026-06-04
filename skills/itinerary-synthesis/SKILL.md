---
name: itinerary-synthesis
description: Use when verified-pois.yaml + routing.yaml are ready and a day-by-day itinerary must be produced. Produces itinerary.md.
---

# itinerary-synthesis

Compose `trips/<slug>/itinerary.md` from verified POIs and routing clusters.

## Rules

- Use ONLY `verify_status: verified` POIs. Pulling a non-verified POI is a gate violation.
- Keep cross-region hops within `max_hop_mins`; cluster base-district days together to conserve energy when members include elderly/children.
- Each day: a table of time-slot rows. Each restaurant/POI row carries its POI id so export can attach a maps link.

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

## Required derived sections

1. **備案 / Contingency** — for each fragile point (booking-required restaurant, outdoor activity), a fallback. Derived inline; not a separate skill.
2. **Pre-trip checklist** — auto-extract from verified-pois `booking.required==true` (with `lead_time`) plus passport/visa basics. List every booking that needs advance action.

## Output

Write `itinerary.md`, return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/verified-pois.yaml` + `trips/<slug>/routing.yaml` + `trips/<slug>/calendar.yaml`. |
| Output | `trips/<slug>/itinerary.md` (day tables + contingency + checklist sections). |
| Stop condition | A `must_do` item has no verified POI to place, is closed on every feasible trip day, or cannot fit before its last order/entry on any feasible slot → ask user. |
| Next stage | `tripwork:orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Placing a non-verified POI | Synthesis reads only `verify_status: verified`. |
| Hand-listing bookings for the checklist | Derive from `booking.required==true`; do not retype. |
| Omitting fallbacks for booking-required meals | Every fragile point needs a contingency line. |
