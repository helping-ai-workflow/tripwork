---
name: export-artifact
description: Use when gate-report status is pass and the itinerary must be exported. Produces trips/<slug>/<stem>.md.
---

# export-artifact

Render the verified itinerary into deliverables at the top of `trips/<slug>/`. Run only when `gate-report.yaml` status is `pass`. The markdown deliverable is `trips/<slug>/<stem>.md`, where `<stem>` is `{dates.start} {short_name} {N天M夜}` (e.g. `2026-05-12 東京 3天2夜`); take every deliverable path from `scripts/paths.py::deliverable_paths(trip_dir, brief)` — md and html share the stem. It is the only markdown copy of the itinerary.

## Adapters

1. **markdown** — Render the whole file with `scripts/render/markdown.py::render_markdown_page(itin, poi_map, cost, brief=brief)` — the brief's headline and dates line head the page (`itinerary.title` is retired). It is a pure function of its inputs, so re-export overwrites the deliverable unconditionally — never hand-assemble sections around the day tables, and never surgically replace one table inside an existing file. It builds each day's table via `render_day_table` (do NOT hand-author table rows — hand-authoring is how naked `$` and dead-text names leaked before) and appends the 備案 / 出發前檢查清單 / 費用估算 sections exactly when the days' `alternatives` (or a pre-v1.0 `itin["contingency"]`) / `itin["checklist"]` / `cost` carry data — never a template with holes. Output `trips/<slug>/<stem>.md`. The renderer makes the POI name the maps link, appends a primary source link (`官網`), and escapes free text so prices like `\$120` cannot trigger KaTeX. The result is re-validated by `export-gate`.
2. **gmaps-links** — `scripts/render/gmaps_links.py` builds each link from `name_local` (best for taxi/Maps). Shared by markdown + Notion.
3. **html** — `scripts/render/html_page.py::render_html_page(itin, poi_map, brief=…, accommodations=…, advisory=…, legs=…, cost=…)` (cost.yaml feeds the home's 旅程與費用 card) -> `trips/<slug>/<stem>.html`. The v1.0 reader: one self-contained, offline page (fonts and photos embedded), usable without any script (Quick Look runs none); on a phone the page holds still and only the day's list card scrolls, on a desktop (≥1024 px) the same page lays out as a big-calendar home and per-day dashboards, stops, map chips and 來源 open by in-page anchors, and one fixed script glides the chosen stop to centre on the desktop — a home with the KUSO headline, the stamp calendar and the 住宿 / 入境規定 / 行前清單 screens, and one page per day with the move chain, one stop open at a time, per-stop alternatives and named sources. Pass the brief, accommodations, advisory and legs: without them the home and sub-screens render empty. Each day has a map card; for real map images first run `python scripts/day_maps.py trips/<slug>` (needs the `[maps]` extra and the network; it writes `trips/<slug>/data/day-maps.yaml`) and pass that document as `maps=` — without it every day draws a schematic. Renders from `itinerary.yaml` like the other adapters; the result is re-validated by `export-gate`.
**Notion (not a tracked adapter).** To put the itinerary in Notion, paste the **gated**
`trips/<slug>/<stem>.md` into a Notion page via the consumer's Notion MCP — there is no
separate Notion adapter, deliverable, or gate. The md is already validated by `export-gate`,
so the pasted content inherits that hygiene; the plugin core never imports an MCP client.

## POI pool for rendering

Build the `poi_map` the renderers consume as **verified-pois + each overnight stop's chosen
lodging** — `scripts/gate.py::poi_pool(pois, accommodations)` (verified-pois wins each field
on a shared id, lodging-only fields such as `booking` are kept) so a
`day.lodging` id resolves to the hotel's name/link instead of rendering a blank `—`. This is
the same pool `itinerary-synthesis` and `itinerary-gate` build; never copy hotels into
canonical `verified-pois.yaml`.

## Photo enrichment (owned here, opt-in)

This stage OWNS `trips/<slug>/data/verified-pois-media.yaml`; within the plugin
`scripts/photo_adapter.py` is its only writer. Never hand-author media entries — a hand-written
`photo_source: google` entry ships a permanently non-distributable deliverable, and the adapter's
`google` backend is BLOCKED for exactly that reason (no display-surface licence). An entry
already in the side-file (e.g. one the user's own script wrote) is the user's: the adapter keeps
it as is and fills only the POIs without one — delete an entry to have it fetched again.

Run it only when the user asked for photos on this trip (`trip-brief.yaml`
`preferences.photos: true`); otherwise skip — no side-file, deliverable unchanged.

    python scripts/photo_adapter.py trips/<slug> --backend wiki

It looks up the POI's Wikidata image (the `image` statement of the entity within 1 km of the verified coordinates)
first, then the geo-filtered Openverse/Commons search, and shrinks each photo to ≤ 640 px.

Exit 0 written / 1 schema self-check failed (nothing written) / 2 missing input or
`--backend google`.

Then overlay it onto the poi_map **before any `render_*` call**. `apply_media` is
**non-mutating — you MUST capture its return**:

    poi_map = apply_media(poi_map, load_media("trips/<slug>/data/verified-pois-media.yaml"))

from `scripts/media_merge.py`.

**Never write media into canonical `verified-pois.yaml`** — `source-verify` wholesale-rewrites
it every run and would clobber it. The side-file is the only persistence; the overlay is
render-time only (`export-gate` re-applies it itself when gating, and rejects an
unattributed photo or an unsafe `<img src>`).

## Publish for family (optional)

Run only when the user asks to share the trip (family, friends). It makes a second reader —
the same page plus phone gestures, behind a password — and puts it on Cloudflare Pages:

    TRIPWORK_PUBLISH_PASSWORD=<password> python scripts/publish.py build trips/<slug> --share-base https://<project>.pages.dev/
    python scripts/publish.py deploy trips/<slug> --project <project> --confirm

Ask the user for the password (or let `build` prompt); never write it to a file. `build` keeps
only the locked page (`trips/<slug>/publish/<code>/index.html`) and prints a share link that
opens without typing the password — show it to the user, never save it. Needs Node 18+.
The first time, if `deploy` says it is not logged in, ask the user to run `! npx wrangler login`;
agree on the project name with the user (`<project>.pages.dev`).

Before `deploy`, stop and ask the user: show the project name, the URL and that the page goes on the internet behind a password. Deploy only after an explicit yes.

Return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/data/itinerary.yaml` (canonical) + `verified-pois.yaml` + optional `verified-pois-media.yaml` (photo side-file) + `gate-report.yaml` (status pass). All adapters render from `itinerary.yaml`; the photo side-file, when present, is overlaid onto the poi_map via `scripts/media_merge.py` before render; Notion runs only after `export-gate` passes. |
| Output | `trips/<slug>/<stem>.md` (+ `<stem>.html`) + optional `verified-pois-media.yaml` (photo side-file, written by `scripts/photo_adapter.py`) + optional `trips/<slug>/publish/` (the locked publish page, `scripts/publish.py`). |
| Stop condition | `gate-report` status != pass → do not export; return upstream. Before `publish.py deploy` → stop for the user's explicit yes (it publishes to the internet). |
| Next stage | `tripwork:orchestrator` (which routes to `export-gate`). |
