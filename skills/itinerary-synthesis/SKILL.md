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
| Stop condition | A `must_do` item has no verified POI to place, or a `must_do` POI is closed on every feasible trip day → ask user. |
| Next stage | `tripwork:orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Placing a non-verified POI | Synthesis reads only `verify_status: verified`. |
| Hand-listing bookings for the checklist | Derive from `booking.required==true`; do not retype. |
| Omitting fallbacks for booking-required meals | Every fragile point needs a contingency line. |
