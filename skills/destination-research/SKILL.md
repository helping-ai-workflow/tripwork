---
name: destination-research
description: Use when trip-brief.yaml exists and candidate POIs/restaurants must be gathered before verification. Produces candidates.yaml.
---

# destination-research

Gather a *candidate pool* into `trips/<slug>/data/candidates.yaml` (schema: `schemas/candidates.schema.json`). This stage is breadth-first and explicitly NOT trusted — verification happens later.

## Method

- Gather candidates using the **source ladder** in `tripwork:using-tripwork` (WebSearch, else WebFetch against an official page, else a search HTML endpoint for discovery only). Record the URL you actually fetched on every candidate.
- For each topic in `must_do` + standard categories (food, sights, shopping), search broadly.
  A survey brief (`mode: survey`) searches its `categories` instead of the standard ones.
  Always record the `must_do` topics you searched in candidates.yaml's top-level
  `must_do_searched` — `[]` when there were none (a survey has none; the oracle asks for it);
  when an upgraded brief adds a topic, append candidates for it (keep the existing ones) and
  add it to that list.
- **Always include local-language queries** (e.g. Korean for Korea) — local sources surface places international sources miss, and a local source is required to pass `source-verify`.
- **Run two tracks for every topic.** The **local track**: destination-language queries
  (official sites, local review and listing sites). The **Taiwan track**: Traditional-Chinese
  queries for write-ups by Taiwanese travellers (blogs, trip reports) — where they actually went,
  what they liked, the local name and address they give. Record a Taiwan page like any source,
  with `lang: zh-TW`. A place found only on Taiwan pages stays a candidate until a local-language
  source is found (it cannot pass `source-verify` without one). A local name or street address a
  Taiwan page gives is a claim: record it (`name_local`; `address_local` with `address_source`
  pointing at that page) for `source-verify` to check.
- **Record what each source is.** Every `sources[]` entry carries `site` (the site's name in
  Chinese — translate a foreign one), `site_local` for a non-Chinese source (the site's own
  name), and `note` (one line: what this page says that matters). The v1.0 reader prints them
  as the source list; `source_verify_run.py` copies them into verified-pois unchanged.
- Record every source URL with its `lang` — Chinese with its region (`zh-TW`, `zh-HK`, `zh-CN`,
  `zh-SG`, `zh-MY`), never a bare `zh`: a source without a region is not a local-language source.
  Capture `claimed_district` when a source states a location, but treat it as a claim, not a fact.
- **Rating (optional):** when a source states one, record `rating: {platform, score, count,
  source_url, as_of}` on the candidate. With the consumer's Google key, the workspace's own
  script records Google's (the plugin never calls Google; asking Places for rating /
  userRatingCount bills that call at the Enterprise tier — about $35 per 1000, first 1000 a
  month free by third-party pricing; check Google's own price list); without one, another
  platform's (Tabelog, 愛食記 …); with neither, leave it out. A missing rating never stops or
  demotes a place. When a high score sits against clear complaints in the write-ups you
  collected, say so in `rating.note`.
- When a dated source states the venue is currently operating, record the sourced `business_status` object form (`{status, source_url, as_of}`) — a bare string (`business_status: OPERATIONAL`) is schema-valid but self-attested, and will leave the POI `unverified` at `source-verify`'s Gate 0.

## Caching

Write raw search results under `work/<slug>/research-cache/` to avoid repeat queries on re-runs.

## Output

Write `trips/<slug>/data/candidates.yaml`, then validate it:
`python <plugin>/scripts/tripwork.py validate <slug> candidates`
(exit 0 required before returning). Return to `tripwork:tripwork-orchestrator`. Do NOT assign `verify_status` here — that is `source-verify`'s job.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/data/trip-brief.yaml`. |
| Output | `trips/<slug>/data/candidates.yaml` (untrusted pool) + `work/<slug>/research-cache/`. |
| Stop condition | None — breadth-first gathering; trust decisions belong to `source-verify`. |
| Next stage | `tripwork:tripwork-orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Skipping local-language queries | A local source is required to pass verification; always search in the destination language. |
| Assigning `verify_status` here | This stage only gathers; verification is `source-verify`. |
| Recording a `claimed_district` as fact | It is a claim; geocode confirms it later. |
| Asking the user to pick a restaurant or sight from what you just found | never ask the user to choose between places from candidates.yaml: a candidate may have closed for good. Finish gathering, let `source-verify` run, and offer only `verified` POIs; say how many were left out because their operating status could not be found. |
