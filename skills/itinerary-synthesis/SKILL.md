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

## Required derived sections

1. **備案 / Contingency** — for each fragile point (booking-required restaurant, outdoor activity), a fallback. Derived inline; not a separate skill.
2. **Pre-trip checklist** — auto-extract from verified-pois `booking.required==true` (with `lead_time`) plus passport/visa basics. List every booking that needs advance action.

## Output

Write `itinerary.md`, return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/verified-pois.yaml` + `trips/<slug>/routing.yaml`. |
| Output | `trips/<slug>/itinerary.md` (day tables + contingency + checklist sections). |
| Stop condition | A `must_do` item has no verified POI to place → ask user. |
| Next stage | `tripwork:orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Placing a non-verified POI | Synthesis reads only `verify_status: verified`. |
| Hand-listing bookings for the checklist | Derive from `booking.required==true`; do not retype. |
| Omitting fallbacks for booking-required meals | Every fragile point needs a contingency line. |
