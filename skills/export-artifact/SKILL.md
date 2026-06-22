---
name: export-artifact
description: Use when gate-report status is pass and the itinerary must be exported. Produces markdown, Google Maps links, LINE short text, and a self-contained HTML one-pager.
---

# export-artifact

Render the verified itinerary into deliverables under `trips/<slug>/exports/`. Run only when `gate-report.yaml` status is `pass`. The markdown deliverable is `trips/<slug>/exports/<slug>-itinerary.md` — a slug-prefixed name so an editor tab never confuses it with the synthesis intermediate `trips/<slug>/itinerary.md` (D3).

## Adapters

1. **markdown** — every day table MUST be produced by `scripts/render/markdown.py::render_day_table` (do NOT hand-author table rows — hand-authoring is how naked `$` and dead-text names leaked before). Output `exports/<slug>-itinerary.md`. The renderer makes the POI name the maps link, appends a primary source link (`官網`), and escapes free text so prices like `\$120` cannot trigger KaTeX. The result is re-validated by `export-gate`.
2. **gmaps-links** — `scripts/render/gmaps_links.py` builds each link from `name_local` (best for taxi/Maps). Shared by markdown + Notion.
3. **line-short** — `scripts/render/line_short.py::render_line_short` -> `exports/line-short.txt`. Plain text, emoji-delimited, elder-friendly, no URLs.
4. **html** — `scripts/render/html_page.py::render_html_page` -> `exports/<slug>-itinerary.html`. A self-contained one-page HTML deliverable (inline CSS, no external assets, offline-viewable): per-day cards, each POI name a maps link, the pre-trip checklist, large font and mobile-RWD layout. Renders from `itinerary.yaml` like the other adapters; the result is re-validated by `export-gate`.
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

## Photo enrichment (optional)

When `trips/<slug>/verified-pois-media.yaml` exists (written by the photo adapter under
backend `wiki`/`google`; absent under the default backend `none`), overlay it onto the
poi_map **before any `render_*` call**. `apply_media` is **non-mutating — you MUST capture
its return** (a dropped return renders 0 photos silently; export-gate's `media_landed`
check (P8) catches it, but capture it correctly in the first place):

`poi_map = apply_media(poi_map, load_media("trips/<slug>/verified-pois-media.yaml"))`
from `scripts/media_merge.py`.

This merges `photo` / `photo_attribution` / `photo_source` onto each POI by `poi_id`. It
is a render-time overlay only — **never write media back into canonical
`verified-pois.yaml`**, which `source-verify` wholesale-rewrites on every run and would
clobber it. A photo without attribution or an unsafe `<img src>` is rejected by
`export-gate`; `photo_source: google` marks the deliverable non-distributable (a clean
terminal personal variant, not a failure — see export-gate P7).

Return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/itinerary.yaml` (canonical) + `verified-pois.yaml` + optional `verified-pois-media.yaml` (photo side-file) + `gate-report.yaml` (status pass). All adapters render from `itinerary.yaml`; the photo side-file, when present, is overlaid onto the poi_map via `scripts/media_merge.py` before render; Notion runs only after `export-gate` passes. |
| Output | `trips/<slug>/exports/<slug>-itinerary.md` (+ line-short.txt + `<slug>-itinerary.html`). |
| Stop condition | `gate-report` status != pass → do not export; return upstream. |
| Next stage | `tripwork:orchestrator` (which routes to `export-gate`). |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Exporting before the gate passes | Run only on `gate-report.yaml` status `pass`. |
| Building maps links from the display name | Use `name_local` for accurate taxi/Maps lookup. |
