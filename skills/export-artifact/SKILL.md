---
name: export-artifact
description: Use when gate-report status is pass and the itinerary must be exported. Produces exports/<slug>-itinerary.md.
---

# export-artifact

Render the verified itinerary into deliverables under `trips/<slug>/exports/`. Run only when `gate-report.yaml` status is `pass`. The markdown deliverable is `trips/<slug>/exports/<slug>-itinerary.md` — a slug-prefixed name so an editor tab never confuses it with the synthesis intermediate `trips/<slug>/itinerary.md` (D3).

## Adapters

1. **markdown** — Render the whole file with `scripts/render/markdown.py::render_markdown_page(itin, poi_map, cost)`. It is a pure function of its inputs, so re-export overwrites the deliverable unconditionally — never hand-assemble sections around the day tables, and never surgically replace one table inside an existing file. It builds each day's table via `render_day_table` (do NOT hand-author table rows — hand-authoring is how naked `$` and dead-text names leaked before) and appends the 備案 / 出發前檢查清單 / 費用估算 sections exactly when `itin["contingency"]` / `itin["checklist"]` / `cost` carry data — never a template with holes. Output `exports/<slug>-itinerary.md`. The renderer makes the POI name the maps link, appends a primary source link (`官網`), and escapes free text so prices like `\$120` cannot trigger KaTeX. The result is re-validated by `export-gate`.
2. **gmaps-links** — `scripts/render/gmaps_links.py` builds each link from `name_local` (best for taxi/Maps). Shared by markdown + Notion.
3. **line-short** — `scripts/render/line_short.py::render_line_short` -> `exports/line-short.txt`. Plain text, emoji-delimited, elder-friendly, no URLs.
4. **html** — `scripts/render/html_page.py::render_html_page` -> `exports/<slug>-itinerary.html`. A self-contained one-page HTML deliverable (inline CSS, no external assets, offline-viewable): per-day cards, each POI name a maps link, the 備案 / Contingency section, the pre-trip checklist, large font and mobile-RWD layout. Renders from `itinerary.yaml` like the other adapters; the result is re-validated by `export-gate`.
**Notion (not a tracked adapter).** To put the itinerary in Notion, paste the **gated**
`exports/<slug>-itinerary.md` into a Notion page via the consumer's Notion MCP — there is no
separate Notion adapter, deliverable, or gate. The md is already validated by `export-gate`,
so the pasted content inherits that hygiene; the plugin core never imports an MCP client.

## POI pool for rendering (P4)

Build the `poi_map` the renderers consume as **verified-pois + each overnight stop's chosen
lodging** — fold in `scripts/gate.py::chosen_lodging_pois(accommodations)` so a
`day.lodging` id resolves to the hotel's name/link instead of rendering a blank `—`. This is
the same pool `itinerary-synthesis` and `itinerary-gate` build; never copy hotels into
canonical `verified-pois.yaml`.

## Photo enrichment (owned here, opt-in)

This stage OWNS `trips/<slug>/verified-pois-media.yaml`; `scripts/photo_adapter.py` is its
ONLY writer. Never hand-author media entries — a hand-written `photo_source: google` entry
ships a permanently non-distributable deliverable, and the adapter's `google` backend is
BLOCKED for exactly that reason (no display-surface licence).

Run it only when the user asked for photos on this trip (`trip-brief.yaml`
`preferences.photos: true`); otherwise skip — no side-file, deliverable unchanged.

    python scripts/photo_adapter.py trips/<slug> --backend wiki

Exit 0 written / 1 schema self-check failed (nothing written) / 2 missing input or
`--backend google`.

Then overlay it onto the poi_map **before any `render_*` call**. `apply_media` is
**non-mutating — you MUST capture its return**:

    poi_map = apply_media(poi_map, load_media("trips/<slug>/verified-pois-media.yaml"))

from `scripts/media_merge.py`.

**Never write media into canonical `verified-pois.yaml`** — `source-verify` wholesale-rewrites
it every run and would clobber it. The side-file is the only persistence; the overlay is
render-time only (`export-gate` re-applies it itself when gating, and rejects an
unattributed photo or an unsafe `<img src>`).

Return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/itinerary.yaml` (canonical) + `verified-pois.yaml` + optional `verified-pois-media.yaml` (photo side-file) + `gate-report.yaml` (status pass). All adapters render from `itinerary.yaml`; the photo side-file, when present, is overlaid onto the poi_map via `scripts/media_merge.py` before render; Notion runs only after `export-gate` passes. |
| Output | `trips/<slug>/exports/<slug>-itinerary.md` (+ `line-short.txt` + `<slug>-itinerary.html`) + optional `verified-pois-media.yaml` (photo side-file, written by `scripts/photo_adapter.py`). |
| Stop condition | `gate-report` status != pass → do not export; return upstream. |
| Next stage | `tripwork:orchestrator` (which routes to `export-gate`). |
