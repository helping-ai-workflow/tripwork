---
name: export-gate
description: Use when tripwork-export-artifact has produced trips/<slug>/<stem>.md and the rendered deliverable must be validated before the pipeline completes. Produces export-gate-report.yaml.
---

# export-gate — mechanical post-export check

Validates the **rendered deliverable** `trips/<slug>/<stem>.md`.
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
  display-surface ToS clearance. **This is NOT a hard fail:** it is a labelling
  decision re-rendering can never fix, so it sets the report's `distributable: false`
  (a clean terminal "personal variant complete" state) while `status` stays `pass`. A
  distributable export reports `distributable: true`.

The html deliverable `trips/<slug>/<stem>.html` is validated by
`scripts/export_gate.py::run_html_gate` (structure/format only: non-empty, at least
`min_days` day-cards, every `href` an `http(s)://` URL or an in-page `#` link to an id on
the page, no `<script>` except the reader's own centring script matched by sha256 and no other active content, every
`<img src>` and stylesheet `url()` an embedded `data:` URL, plus the photo checks above).
Its checks appear in the report prefixed `html_` (the full list is `run_html_gate`'s `checks`); among
them `scripts_whitelisted`, `img_src_offline` (an `https://` image fails), `licences_present` (the
font and icon notices, in the comment that opens the file — not on screen), `expandables_are_details`,
`legs_have_mode_icon` and `map_attribution_present` (every map built from tiles carries the
plain OpenStreetMap credit as text; a link is not required).

- `media_landed` (html) — when a `verified-pois-media.yaml` side-file is present, its
  entry count is checked against the rendered HTML. If that count is > 0 but the
  rendered HTML shows **no photo** (no `<img>` and no reader photo), the gate fails ("media side-file present but rendered
  deliverable has 0 photos") — catching a dropped `apply_media` return that silently shipped
  a photoless page.

## Output

Run `python <plugin>/scripts/tripwork.py export-gate <slug>` — the CLI reads the same inputs
`export` renders from (`scripts/trip_inputs.py`: verified-pois + chosen lodgings + the photo overlay),
gates both the md and html deliverables, and writes
`work/<slug>/export-gate-report.yaml` (schema: `schemas/gate-report.schema.json`
— reused; same status/checks/failures shape, plus the optional `distributable` + `retryable`
flags). On `status: fail`, the report's **`retryable`** tells the orchestrator how to react:
`retryable: true` (a defect in the source text — naked `$`, a kana run without its
reading, internal jargon) → back to `itinerary-synthesis` to fix that text in the
artifact, then gate and export again — **never edit the rendered deliverable**: `export`
is a fixed program and would write the defect back; `retryable: false` (the only
failures are upstream DATA defects — a photo with no attribution, a bookable POI with no
official source — or `repeat_of_previous: true`, the same failures back after the source
was fixed once, likely a plugin render defect) → **stop and ask the user**, do NOT loop. A `status: pass` report with `distributable: false` is a **clean terminal
personal variant** (google-photo HTML): the orchestrator completes it as "complete —
non-distributable, 勿散布", it does NOT re-export loop.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/<stem>.md` (named from `trips/<slug>/data/trip-brief.yaml`'s `short_name` via `scripts/paths.py::deliverable_paths`) + the MERGED pois (`trips/<slug>/data/verified-pois.yaml` overlaid with `trips/<slug>/data/accommodations.yaml`'s chosen lodgings and optional `trips/<slug>/data/verified-pois-media.yaml` via `scripts/media_merge.py::apply_media`), plus optional `trips/<slug>/data/itinerary.yaml` (for `min_days`), so the photo / distributability checks see the same photos the deliverable rendered. |
| Output | `work/<slug>/export-gate-report.yaml` (`status` pass/fail + failures). |
| Stop condition | `status: fail` + `retryable: true` → return to `itinerary-synthesis` to fix the source text (never edit the rendered deliverable); `retryable: false` → stop and ask the user (`nonretryable_export_fail`): fix the data, or report a repeated failure as a plugin defect. |
| Next stage | `tripwork:tripwork-orchestrator` (pipeline complete on pass). |
