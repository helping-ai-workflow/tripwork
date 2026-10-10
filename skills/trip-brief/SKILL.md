---
name: trip-brief
description: Use when the tripwork orchestrator has routed a new travel request and the trip parameters must be captured before research begins. Produces trip-brief.yaml.
---

# trip-brief

> **Step 0 — preflight + slug guard (before writing anything).** If
> `work/.preflight-completed` is absent, invoke `tripwork:tripwork-workspace-shape-preflight` first and
> write **no** files. Then bind `<slug>`: derive it as `<yyyy-mm>-<destination>` (e.g.
> `2026-06-seoul`) from the trip dates + destination, and **confirm it with the user**. If the
> derived `trips/<slug>/` already exists, stop and ask (resume that trip, or pick a new slug) —
> never reuse or overwrite another trip's directory.

Capture the trip into `trips/<slug>/data/trip-brief.yaml` (schema: `schemas/trip-brief.schema.json`).

## Capture

- **Survey** (`mode: survey`): the user wants a verified list, not a trip. Required
  then: `slug`, `short_name`, `destination` (the area goes in `city`), `categories` (what to
  look for); `dates` optional (with dates the list marks each day a place is closed). To
  upgrade, add the trip fields (dates, members, base, must_do, ...) and remove `mode`; verified
  places carry over. A business status is good for 90 days: a list left longer asks for a
  fresh check of the stale ones when it is upgraded.
- `destination` (required: `{country, city, local_lang}`) — `country` may be a two-letter code
  (JP); a name no lookup knows stops verify. `local_lang` (ISO-639; Chinese with its region:
  zh-TW / zh-HK / zh-CN / zh-SG / zh-MY, never a bare zh) drives
  source-verify's local-language gate; `country`/`city` anchor geocoding and advisory lookup.
- `airline` (optional) — needed by travel-advisory for carrier-specific battery/baggage rules.
- `dates.start` / `dates.end` (ISO `YYYY-MM-DD`)
- `members` (note elderly/children for downstream energy considerations)
- `base` (lodging name + district — the routing baseline)
- `must_do` (named experiences the user requires)
- `constraints` (budget, mobility, dietary)
- `preferences` (free-form object)
- `home_origin` / `home_return` (optional; where the trip leaves from and returns to — the
  home legs' endpoints). For the map, also ask for **a shop or landmark near home** (never the
  home address: the point is drawn on the first and last day's map, shared copies included),
  look it up like any place, and record `home_origin_point` / `home_return_point`
  (`{name, lat, lng, geocode_source}`). A brief with only the strings draws no home; ask for the
  landmark the next time the brief is touched.
- `routing.max_hop_mins` (optional; default 60 applied downstream)
- `overnight_stops` (optional; ordered list of `{district, nights, lodging?}`). Capture
  for multi-point trips (a self-drive tour sleeps in several towns). A single-base trip
  omits it — the lone `base` is then the only overnight stop; the first stop usually
  equals `base`. `lodging` is optional per stop: present → it will be verified;
  absent → `accommodation-research` will recommend candidates for the user to pick.
- `facility_needs` (optional; `{required: [token], periodic: [{facility, max_gap_nights}]}`).
  `required` facilities must be at every stop (hard); `periodic` facilities need only
  recur within a cadence (soft). Facilities are an open vocabulary; common tokens to
  ask about: `parking`, `laundry`, `kitchen`, `elevator`, `breakfast`, `family_room`,
  `crib`, `wifi`, `heating`. When `members` note elderly, suggest asking about
  `elevator`/`accessible`; with infants/children, suggest `family_room`/`crib` — a
  suggestion to raise with the user, not an auto-added requirement.
- `transport` (optional; e.g. `self_drive` / `public` / `mixed`). A hint for downstream
  stages — `self_drive` enables `seasonal-advisory`'s after-dark driving-leg flag (and,
  later, drive-leg checks). Omit for trips where driving conditions do not apply.
- `overnight_stops[].leg_mode` (optional per stop) + `routing.max_single_drive_mins`
  (optional; default 300 = 5h). `leg_mode` overrides the trip-level `transport` for the leg
  **into** that stop (from the previous stop) — capture it for mixed trips (e.g. rail
  between cities, a rented car for one segment).
- `budget` (optional `{amount, currency}`) + `daily_incidental` (optional `{amount,
  currency}`) + `home_currency` (optional). `budget` is the structured trip budget
  `cost-rollup` compares against. `daily_incidental` is the
  user's per-day allowance for food / tickets / local transport — an estimate, not
  researched per item. `home_currency` drives an FX advisory note on the total.
- `routing.max_walk_mins` (optional; default 15). The comfortable station-to-POI walk
  ceiling. Lower it for frail elders.

## Trip names (v1.0 reader)

Two names, two jobs. Rules live in `scripts/brief_names.py`; `itinerary-gate` checks them
(`brief_names_valid`) and routes a failure (`trip-brief name invalid` /
`trip-brief headline invalid`) straight back here.

- `short_name` — 2–8 filename-safe characters (CJK, kana, Latin, digits, space): the place,
  optionally plus a short theme (`東京`, `海邊露營烤肉`). It becomes the deliverable name
  `{dates.start} {short_name} {N天M夜}`, which must stay ≤22 characters
  (`scripts/brief_names.py::deliverable_stem`) — so on a multi-day trip `short_name` is at most 6
  characters (at most 5 for a trip of 10 days or more). Propose one and confirm it with the user.
- `day_label` — only for a same-day trip: 2–6 characters replacing the default 一日遊
  (e.g. `展覽晚餐`). Never on a multi-day trip.
- `headline` — the home-page title, and it must be KUSO (playful). Propose six
  `headline_candidates`, each `{text, device, riff_on?, refs}`, one per device of
  [references/kuso-headlines.md](references/kuso-headlines.md). `refs` names the
  `must_do` entries the joke rests on (funny, never invented); `swap` / `pun` / `double_meaning`
  also record `riff_on`, the familiar phrase being reworked. Then **stop and ask the user to
  pick one or write their own** (`headline_pick`); if they ask for more, append three more
  candidates. Record the pick as `headline: {text}`; a title the user writes themselves is
  `headline: {text, user_written: true}` — keep every candidate either way. The day-title
  picker (itinerary-synthesis) offers the headline once more at its top.

**A names-only re-run.** When the gate routes here only for `trip-brief name invalid` /
`trip-brief headline invalid` on an existing brief, fill only `short_name` / `day_label` /
`headline` / `headline_candidates`. Do not re-ask the other fields and do not touch the
geocode cache — the destination and dates did not change.

## Ingest sources

Accept a free-text brief, or — if the user points at a Notion page — read it via the consumer's Notion MCP and extract the fields. Do not invent values; ask for anything missing that the pipeline needs.

## Cache lifecycle on re-brief

When re-writing `trip-brief.yaml` for an existing `<slug>` whose **destination or dates
changed**, delete `work/<slug>/geocode-cache/` first — it is rebuildable by definition, and
a cache keyed on the old destination would otherwise hand stale coordinates to the re-run.

## Output

Write `trips/<slug>/data/trip-brief.yaml`, then validate it:
`python <plugin>/scripts/tripwork.py validate <slug> trip-brief`
(exit 0 required before returning). Return to `tripwork:tripwork-orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | A free-text brief or a Notion page reference; user answers for missing fields. |
| Output | `trips/<slug>/data/trip-brief.yaml` (schema-valid). |
| Stop condition | A pipeline-required field is missing and the user has not supplied it → ask. Six headline candidates are ready (`headline_pick`) → ask the user to pick one or write their own. |
| Next stage | `tripwork:tripwork-orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Treating a Notion claim as ground truth | trip-brief only captures intent; locations are still verified later. |
