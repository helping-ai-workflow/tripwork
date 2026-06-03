---
name: export-artifact
description: Use when gate-report status is pass and the itinerary must be exported. Produces markdown, Google Maps links, LINE short text, and optional Notion write-back.
---

# export-artifact

Render the verified itinerary into deliverables under `trips/<slug>/exports/`. Run only when `gate-report.yaml` status is `pass`.

## Adapters

1. **markdown** — `scripts/render/markdown.py::render_day_table` per day -> `exports/itinerary.md`. Restaurant/POI rows embed Google Maps links.
2. **gmaps-links** — `scripts/render/gmaps_links.py` builds each link from `name_local` (best for taxi/Maps). Shared by markdown + Notion.
3. **line-short** — `scripts/render/line_short.py::render_line_short` -> `exports/line-short.txt`. Plain text, emoji-delimited, elder-friendly, no URLs.
4. **notion** — write back to a Notion page via the consumer's Notion MCP. This is driven by this skill, not a bundled script (the plugin core never imports an MCP client).

## Notion graceful skip

If the Notion MCP is not available in the session, log that Notion write-back was skipped and that all other exports completed; do NOT fail the export stage. Record the page id in `exports/.notion-page-id` on success.

Return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/itinerary.md`, `verified-pois.yaml`, and `gate-report.yaml` (status pass). |
| Output | `trips/<slug>/exports/` (markdown + line-short.txt; optional Notion page). |
| Stop condition | `gate-report` status != pass → do not export; return upstream. |
| Next stage | `tripwork:orchestrator` (pipeline complete). |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Exporting before the gate passes | Run only on `gate-report.yaml` status `pass`. |
| Failing the whole stage when Notion MCP is absent | Graceful-skip Notion; finish the other adapters. |
| Building maps links from the display name | Use `name_local` for accurate taxi/Maps lookup. |
