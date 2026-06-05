---
name: trip-brief
description: Use when a new travel request arrives and the trip parameters must be captured before research begins. Produces trip-brief.yaml.
---

# trip-brief

Capture the trip into `trips/<slug>/trip-brief.yaml` (schema: `schemas/trip-brief.schema.json`).

## Capture

- `dates.start` / `dates.end`
- `members` (note elderly/children for downstream energy considerations)
- `base` (lodging name + district — the routing baseline)
- `must_do` (named experiences the user requires)
- `constraints` (budget, mobility, dietary)
- `preferences` (free-form object)
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

## Ingest sources

Accept a free-text brief, or — if the user points at a Notion page — read it via the consumer's Notion MCP and extract the fields. Do not invent values; ask for anything missing that the pipeline needs.

## Output

Write `trips/<slug>/trip-brief.yaml`, validate against the schema, then return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | A free-text brief or a Notion page reference; user answers for missing fields. |
| Output | `trips/<slug>/trip-brief.yaml` (schema-valid). |
| Stop condition | A pipeline-required field is missing and the user has not supplied it → ask. |
| Next stage | `tripwork:orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Inventing dates/lodging the user did not give | Never fabricate; ask for anything the pipeline needs. |
| Treating a Notion claim as ground truth | trip-brief only captures intent; locations are still verified later. |
