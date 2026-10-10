---
name: tripwork-export-artifact
description: Use when gate-report status is pass and the itinerary must be exported. Produces trips/<slug>/<stem>.md.
---

# tripwork-export-artifact

Render the verified itinerary into deliverables at the top of `trips/<slug>/`. Run only when `gate-report.yaml` status is `pass`. The markdown deliverable is `trips/<slug>/<stem>.md`, where `<stem>` is `{dates.start} {short_name} {N天M夜}` (e.g. `2026-05-12 東京 3天2夜`); every deliverable path comes from `scripts/paths.py::deliverable_paths(trip_dir, brief)` — md and html share the stem. It is the only markdown copy of the itinerary.

## Export

    python <plugin>/scripts/tripwork.py export <slug>

One command writes both deliverables — never write the rendering Python yourself. It reads the
artifacts through `scripts/trip_inputs.py` (the same inputs `publish` renders from and
`export-gate` judges against): `itinerary.yaml`, the POI pool (verified-pois + each overnight
stop's chosen lodging, so a `day.lodging` id resolves to the hotel), the photo side-file
overlaid, and the brief, accommodations, advisory, legs, cost and day maps. It renders both
pages in memory and writes them only together. It refuses, writing nothing, when the trip is
still in the pre-v1.0 layout (exit 2: run `tripwork.py migrate <slug>`), when an input is
missing (exit 2), or when `work/<slug>/gate-report.yaml` is missing, not `pass`, or older than
an artifact the gate reads (exit 1: run `tripwork.py gate <slug>` first). Re-export overwrites
both files: they are pure functions of the artifacts, so never edit a rendered deliverable —
fix the artifact and export again.

What it writes:

1. **markdown** — `trips/<slug>/<stem>.md`: the brief's headline and dates line, every day's
   table from the renderer's `render_day_table` — never hand-author table rows; that is how
   naked `$` and dead-text names leaked before — (the POI name is the Google Maps link, built from `name_local`; a primary source
   link — `官網` for an official source, else the source's site name; a move row's link leads
   with its mode's emoji; free text escaped so prices like `\$120` cannot trigger KaTeX), and the 備案 /
   出發前檢查清單 / 費用估算 sections exactly when the days' `alternatives` / the checklist /
   `cost.yaml` carry data.
2. **html** — `trips/<slug>/<stem>.html`: the v1.0 reader. One self-contained, offline page
   (fonts and photos embedded), usable without any script (Quick Look runs none); on a phone
   the page holds still and only the day's list card scrolls, on a desktop (≥1024 px) the same
   page lays out as a big-calendar home and per-day dashboards — a home with the KUSO
   headline, the stamp calendar, the 旅程與費用 card and the 住宿 / 入境規定 / 行前清單
   screens, and one page per day with the move chain, one stop open at a time, per-stop
   alternatives and named sources. Each day has a map card: for real map images run
   `python <plugin>/scripts/tripwork.py maps <slug>` first (needs the `[maps]` extra and the
   network; it writes `trips/<slug>/data/day-maps.yaml`, which `export` then uses) — without it
   every day draws a schematic.

Both are re-validated by `export-gate`.

**Notion (not a tracked adapter).** To put the itinerary in Notion, paste the **gated**
`trips/<slug>/<stem>.md` into a Notion page via the consumer's Notion MCP — there is no
separate Notion adapter, deliverable, or gate. The md is already validated by `export-gate`,
so the pasted content inherits that hygiene; the plugin core never imports an MCP client.

## Survey: the list page

A survey brief (`mode: survey`) has no itinerary and no gate; it ends with its list page:

    python <plugin>/scripts/tripwork.py table <slug> --page

It writes `trips/<slug>/<short_name> 清單.html` from verified-pois and the brief (the same
stop cards as the reader, grouped 吃的 / 景點 / 住的 / 其他, best rated first) and refuses
(exit 2) when the brief cannot name it or the page fails the shipped HTML safety check. Then
tell the user the page's path and that `tripwork.py table <slug> 吃的` (or 景點, or the
fields they name) prints the same places as a table.

## Photo enrichment (owned here, opt-in)

This stage OWNS `trips/<slug>/data/verified-pois-media.yaml`; within the plugin
`scripts/photo_adapter.py` is its only writer. Never hand-author media entries — a hand-written
`photo_source: google` entry ships a permanently non-distributable deliverable, and the adapter's
`google` backend is BLOCKED for exactly that reason (no display-surface licence). An entry
already in the side-file (e.g. one the user's own script wrote) is the user's: the adapter keeps
it as is and fills only the POIs without one — delete an entry to have it fetched again. So the
order is: the user's own photos first, then this command for the rest.

Run it only when the user asked for photos on this trip (`trip-brief.yaml`
`preferences.photos: true`); otherwise skip — no side-file, deliverable unchanged. Run it
before `export`:

    python <plugin>/scripts/tripwork.py photos <slug>

It looks up the POI's Wikidata image (the `image` statement of the entity within 1 km of the
verified coordinates) first, then the geo-filtered Openverse/Commons search, and shrinks each
photo to ≤ 640 px (landmarks only; restaurants and lodgings are skipped).

Exit 0 written / 1 schema self-check failed (nothing written) / 2 missing input or
`--backend google`.

**Never write media into canonical `verified-pois.yaml`** — `source-verify` wholesale-rewrites
it every run and would clobber it. The side-file is the only persistence; `export` overlays it
at render time (and `export-gate` judges the same overlay, rejecting an unattributed photo or
an unsafe `<img src>`).

## Publish for family (optional)

Run only when the user asks to share the trip (family, friends). It makes a second reader —
the same page plus phone gestures, behind a password — and puts it on Cloudflare Pages:

    TRIPWORK_PUBLISH_PASSWORD='<password>' python <plugin>/scripts/tripwork.py publish <slug> --share-base https://<project>.pages.dev/
    python <plugin>/scripts/tripwork.py deploy <slug> --project <project> --confirm

Ask the user for the password in the conversation **each time**, and pass it only as the
`TRIPWORK_PUBLISH_PASSWORD='…'` prefix of that one command. Never put it in a file, an
`export`, a shell profile, `.env` or the cloud environment's variables. Say so plainly: the
prefix keeps it out of every file, but it stays in the conversation and, while the command
runs, in this computer's process list. If the user would rather not type it into the
conversation, they can run the same command (without the prefix) in their own terminal, and
it asks for the password without echoing it. `publish` keeps only the locked page
(`trips/<slug>/publish/<code>/index.html`) and prints a share link that opens without typing
the password — show it to the user, never save it. Needs Node 18+.

Logging in to Cloudflare, the first time `deploy` says it is not logged in:

- on the user's own computer — ask them to run `! npx wrangler login` (it opens a browser);
- in a Claude Code cloud environment there is no browser — the user adds `CLOUDFLARE_API_TOKEN`
  (a token limited to *Cloudflare Pages: Edit*) to the environment's variables; anyone who uses
  that environment can read it, and it is not the page password.

One trip is one Pages project: `deploy` uploads this trip's page only and a deploy replaces the whole site, so agree on a project name for THIS trip with the user (`<project>.pages.dev`) — never reuse another trip's project.

Before `deploy`, stop and ask the user: show the project name, the URL and that the page goes on the internet behind a password. Deploy only after an explicit yes.

Return to `tripwork:tripwork-orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/data/itinerary.yaml` (canonical) + `verified-pois.yaml` + optional `verified-pois-media.yaml` (photo side-file) + `day-maps.yaml` + `gate-report.yaml` (status pass, fresh). `tripwork.py export` reads them all through `scripts/trip_inputs.py`; Notion runs only after `export-gate` passes. |
| Output | `trips/<slug>/<stem>.md` (+ `<stem>.html`) + optional `verified-pois-media.yaml` (photo side-file, written by `scripts/photo_adapter.py`) + optional `trips/<slug>/publish/` (the locked publish page, `scripts/publish.py`). |
| Stop condition | `gate-report` status != pass → do not export; return upstream. Before `tripwork.py deploy` → stop for the user's explicit yes (it publishes to the internet). |
| Next stage | `tripwork:tripwork-orchestrator` (which routes to `export-gate`). |
