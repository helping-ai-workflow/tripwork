---
name: export-gate
description: Use when export-artifact has produced exports/<slug>-itinerary.md and the rendered deliverable must be validated before the pipeline completes. Mechanical post-export gate. Produces export-gate-report.yaml.
---

# export-gate — mechanical post-export check

Validates the **rendered deliverable** `trips/<slug>/exports/<slug>-itinerary.md`.
Upstream `itinerary-gate` runs on the pre-link synthesis intermediate and cannot
see render-layer defects; this gate closes that gap. Format/structure only —
content correctness is guaranteed upstream by `source-verify`.

## Checks (logic in `scripts/export_gate.py::run_export_gate`)

- `no_naked_dollar` — no unescaped `$` (prices must be `\$`); a bare `$...$` pair
  triggers KaTeX math mode and breaks the preview.
- `links_well_formed` — every `[label](target)` target is a non-empty `http(s)://` URL.
- `poi_name_is_link` — no standalone `[地圖]` / `[Map]` token; the POI name itself
  is the link.
- `bookable_has_official_source` — every `booking.required` verified POI present in
  the file carries an official source link on its row.
- `japanese_glossed` — a kana run on a line must carry a （中文）gloss; an inline
  Japanese term left untranslated for the reader is a hard fail.

The html deliverable `exports/<slug>-itinerary.html` is validated by
`scripts/export_gate.py::run_html_gate` (structure/format only: non-empty, at least
`min_days` day-cards, every `href` an `http(s)://` URL, no raw `<script>`).

## Output

Write `trips/<slug>/export-gate-report.yaml` (schema: `schemas/gate-report.schema.json`
— reused; same status/checks/failures shape). On `status: fail`, list each failure
and return to `export-artifact` via `tripwork:orchestrator` to re-render.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/exports/<slug>-itinerary.md` + `trips/<slug>/verified-pois.yaml`. |
| Output | `trips/<slug>/export-gate-report.yaml` (`status` pass/fail + failures). |
| Stop condition | `status: fail` → return to `export-artifact` to re-render. |
| Next stage | `tripwork:orchestrator` (pipeline complete on pass). |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Re-judging POI content here | Format/structure only; content is `source-verify`'s job. |
| Passing despite a bare `$` in a price | `no_naked_dollar` is a hard check; escape as `\$`. |
