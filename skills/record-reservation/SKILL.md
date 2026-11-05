---
name: record-reservation
description: Use when the traveller shares a booking confirmation or says something is booked, or a gate failure names a reservation. Produces reservations.yaml.
---

# record-reservation — the traveller's own bookings

Write what the traveller has booked into `trips/<slug>/data/reservations.yaml` (schema:
`schemas/reservations.schema.json`). This stage is the **only writer** of that file:
itinerary-synthesis, the gates and the renderers read it and never change it, so re-planning
the trip can never drop a booking silently. The reader's 交通 / 餐廳 screens, the stop cards,
the 住宿 screen, the md deliverable and the 行前清單 all come from it.

A booking is the traveller's own fact, not a claim about the world: it needs **no web source**
(Source-Verified-First applies to schedules, hours and rules — the flight's timetable on its leg
still carries the airline's official source; the seat and booking number here do not).

## When

- The traveller pastes a confirmation e-mail / screenshot text, or says "訂好了 …", "這餐不用訂",
  "晚餐自己找", at any point — before or after export.
- The itinerary gate fails with a `reservation …` message (the orchestrator routes it here).

## Steps

1. Read the plan first: `itinerary.yaml`, `legs.yaml`, `verified-pois.yaml`. A reservation must
   point at something the plan already has.
2. One entry per booked thing, in the traveller's words where it is free text:
   - a stop (meal, ticket): `date` + `poi_id` (add `time` only when the same place appears twice
     that day);
   - a move (flight, train, bus): `date` + `from` + `to`, spelled exactly as the move row or its
     leg spells them;
   - a stay: `date` (the check-in date) + `lodging` (the lodging POI id).
3. `status`: `booked` 已訂 · `todo` 還要訂 · `none` 不用訂 (go as planned, buy on the spot) ·
   `self` 自理 (a meal the traveller picks themselves; the listed place is only a suggestion —
   meals only).
4. `ref` holds the booking number exactly as given. It stays in the workspace; every renderer
   masks it (`scripts/reservation.py::mask_ref`) and export-gate fails a deliverable that shows
   it. Never repeat a full number back in chat either — quote the masked form.
5. `details`: `{label, value}` pairs the family will want on the road — 座位, 人數, 套餐, 取票,
   取消期限, 入住. A Japanese term in a value carries its （中文）gloss, like any other text.
   The first two details show on the day's move row (and in the md day table), so put what
   the family needs on the platform first -- 車次 / 航班, then 座位.
   Quote dates and times in YAML (`date: "YYYY-MM-DD"`).
6. When a 預約 checklist item points at the place or leg just booked, give it the `poi_id` /
   `leg_index` it lacks, so the item hides once booked. Do not add 「已訂…」 checklist lines: the
   reservation itself is what the reader shows.
7. Validate: `python <plugin>/scripts/tripwork.py validate <slug> reservations`, then run the
   itinerary gate (`python <plugin>/scripts/tripwork.py gate <slug>`): every entry must match
   exactly one row. Return to `tripwork:tripwork-orchestrator`, which re-exports.

## When an entry does not match

`reservation has no row: …` means the plan dropped something the traveller already booked.
Never delete the entry and never move it to another place on your own: ask (`booked_place_dropped`)
— "5/13 押上示意割烹已經訂好，但新行程沒有這一站。要把它排回去，還是你要去取消訂位？" Put it back
→ itinerary-synthesis re-plans with it fixed in place. Cancelled → remove the entry. Record the
decision in `work/<slug>/stage-state.yaml`.

`reservation matches several rows` → add the entry's `time`. `reservation duplicates another`
→ two entries point at one row: keep the one the traveller confirms. `reservation self is for
meals only` → use `none` or `booked` instead.

## Stage Contract

| Field | Value |
|---|---|
| Input | The traveller's confirmation text or words + `trips/<slug>/data/itinerary.yaml` + `trips/<slug>/data/legs.yaml` + `trips/<slug>/data/verified-pois.yaml`. |
| Output | `trips/<slug>/data/reservations.yaml` (the traveller's bookings; numbers kept in full here only). |
| Stop condition | A booked entry matches no row of the plan (`booked_place_dropped`) → ask the user: put it back, or they cancel the booking. |
| Next stage | `tripwork:tripwork-orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Writing 「已訂 SA 101」 into the itinerary checklist | Record it here; the reader lists it under 交通 and the checklist line disappears by itself. |
| Re-planning around a dropped booking without asking | Ask (`booked_place_dropped`); the traveller may have to cancel it. |
| Echoing the full booking number in chat | Quote the masked form (`••••PX`). |
| Spelling `from` / `to` differently from the move row | Copy them from the row or its leg; a mismatch reads as a dropped booking. |
