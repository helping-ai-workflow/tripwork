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
- `no_internal_jargon` — no internal `(poi-id)` token or literal `must_do` in the rendered
  text. **Content hygiene (`japanese_glossed` + `no_internal_jargon`) is primarily enforced
  at the canonical layer in `itinerary-gate`** (over the unescaped row text/checklist, so it
  protects every renderer); these render-side copies are defense-in-depth.
- `photo_has_attribution` — any POI carrying a `photo` must also carry a non-empty
  `photo_attribution` (author + license + source_url).
- `no_nondistributable_photo_source` — a POI carrying `photo_source: google` has no
  display-surface ToS clearance. **This is NOT a hard fail (P7):** it is a labelling
  decision re-rendering can never fix, so it sets the report's `distributable: false`
  (a clean terminal "personal variant complete" state) while `status` stays `pass`. A
  distributable export reports `distributable: true`.

The html deliverable `exports/<slug>-itinerary.html` is validated by
`scripts/export_gate.py::run_html_gate` (structure/format only: non-empty, at least
`min_days` day-cards, every `href` an `http(s)://` URL, no raw `<script>`, every
`<img src>` a `data:image/` or `https://` URL, plus the photo checks above).

- `media_landed` (html, P8) — when a `verified-pois-media.yaml` side-file is present, pass
  its entry count as `run_html_gate(..., media_count=N)`. If `media_count > 0` but the
  rendered HTML has **0 `<img>`**, the gate fails ("media side-file present but rendered
  deliverable has 0 photos") — catching a dropped `apply_media` return that silently shipped
  a photoless page. Omit `media_count` when there is no side-file.

**Both gates require the MERGED pois.** Load `verified-pois.yaml` and overlay
`verified-pois-media.yaml` via `scripts/media_merge.py::apply_media` (the same overlay
`export-artifact` applies before render), then pass the result as the `pois` argument.
The canonical `verified-pois.yaml` never carries `photo`/`photo_source` (by design —
`source-verify` rewrites it wholesale), so feeding it alone makes the photo +
distributability checks spin against nothing.

## Output

Write `trips/<slug>/export-gate-report.yaml` (schema: `schemas/gate-report.schema.json`
— reused; same status/checks/failures shape, plus the optional `distributable` flag).
On `status: fail` (a genuine render defect), list each failure and return to
`export-artifact` via `tripwork:orchestrator` to re-render. A `status: pass` report with
`distributable: false` is a **clean terminal personal variant** (google-photo HTML): the
orchestrator completes it as "complete — non-distributable, 勿散布", it does NOT re-export
loop. (P7)

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/exports/<slug>-itinerary.md` + the MERGED pois (`verified-pois.yaml` overlaid with optional `verified-pois-media.yaml` via `scripts/media_merge.py::apply_media`), so the photo / distributability checks see the same photos the deliverable rendered. |
| Output | `trips/<slug>/export-gate-report.yaml` (`status` pass/fail + failures). |
| Stop condition | `status: fail` → return to `export-artifact` to re-render. |
| Next stage | `tripwork:orchestrator` (pipeline complete on pass). |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Re-judging POI content here | Format/structure only; content is `source-verify`'s job. |
| Passing despite a bare `$` in a price | `no_naked_dollar` is a hard check; escape as `\$`. |
| Feeding the gate the canonical `verified-pois.yaml` (no photos) | Overlay `verified-pois-media.yaml` via `apply_media` first; otherwise `photo_has_attribution` / `no_nondistributable_photo_source` spin against photo-less pois. |
