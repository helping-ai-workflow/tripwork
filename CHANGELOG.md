# Changelog

## 0.20.0 — canonical content-hygiene gate (protects every renderer) + Notion de-adapted

0.19.0 added the `no_internal_jargon` check to the md + html export gates but left
`line_short.py` un-gated and `run_html_gate` without a kana-gloss check — a cross-axis gap
(the same content checks lived per-renderer and were missed for two of three text
deliverables). This release moves the **format-agnostic** content checks to the canonical
layer so a leak is blocked at the source, before any renderer runs.

- **Canonical content hygiene (`scripts/gate.py::run_gate`).** `no_internal_jargon` +
  `japanese_glossed` now run (always-on) over `_itinerary_text` (the unescaped `checklist` +
  every row `text`). Blocking a leak here keeps **every** renderer clean by construction —
  md, html, line-short.txt (which has no gate of its own), and a Notion page pasted from the
  md — and future renderers too. This is the PRIMARY guard; the `export-gate` md/html copies
  stay as render-layer defense-in-depth.
- **Shared `scripts/text_hygiene.py`.** `jargon_failures(text, pois)` + `kana_gloss_failures
  (text)` lifted into one module imported by both `gate.py` and `export_gate.py` (imports
  only `re` → no cycle); single implementation, no drift. Behaviour identical (messages
  unchanged); the jargon scan keeps the backslash-stripped probe so md-escaped leaks
  (`must\_do`, `(hak-yam\_yakei)`) are still caught render-side.
- **`line_short.py` gap closed at the source.** It keeps its deterministic
  `chunk_line_messages` (LINE 5000-char cap, day-boundary split) + no-URL discipline and
  needs no gate of its own — the canonical guard guarantees its input is clean. (Resolves
  the v0.19.0 "line_short follow-up".)
- **Notion de-adapted.** `export-artifact` no longer documents a Notion write-back adapter /
  graceful-skip / page-id bookkeeping. To put the itinerary in Notion, paste the gated
  `exports/<slug>-itinerary.md` via the consumer's Notion MCP — content = md = already
  validated. No code referenced a Notion path (it was always skill-only).

Scope note (deliberately deferred): `run_html_gate` still has no `bookable_has_official_
source` check — the HTML renderer emits no official-source links to check (only maps chips),
so gating it would require adding official-link *rendering* to the one-pager (a different
check family — link-completeness, not content-hygiene; md already enforces it). Tracked as a
separate future item, not bundled here.

Migration note: the canonical kana check is stricter than the old md-only check (which a
POI-link's `（gloss）` on the same line could mask), so an existing `itinerary.yaml` with
ungloss kana in a **checklist** item or row `text` will now fail `itinerary-gate` until the
synthesis author adds the （中文）gloss — the documented gloss discipline, now enforced at
the source. (e.g. the dogfood `hokkaido-7d` checklist `かに将軍` / `ラビスタ函館ベイ` need glossing.)

## 0.19.0 — 3-col grid itinerary layout + move directions links + content-hygiene gate

The native HTML/markdown renderer adopts the consumer's hand-built one-pager layout
(G1–G5), adds structured move-row directions links (G2), and grows a mechanical gate that
stops internal jargon from reaching user-facing deliverables (G6). Verified to reproduce
the visual baseline (`trips/hokkaido-7d/exports/hokkaido-7d-itinerary.html`) structurally
on real data. Backward-compatible: trips without `from`/`to` render exactly as before.

- **G1 — 3-column grid (`_STYLE`, `_row_html`, `_photo_html`).** Rows render as a CSS grid
  `48px 1fr 64px` (時間 | 說明 | 縮圖) with an always-present reserved `.thcol` thumb cell,
  so photo-less rows still column-align. The separate `.emo` column is gone (the slot emoji
  folds into the 說明 cell); the thumb lives in `.thcol` / `.lodge` instead of a
  `margin-left:auto` flex sibling.
- **G2 — move directions chip + chip-at-start (`gmaps_links.dir_url`, `_row_chip_body`,
  `markdown._move_cell`).** New optional `row.from`/`row.to` schema fields
  (`additionalProperties:false` intact, keyword-safe via `row.get()`); `dir_url` builds
  `maps/dir/?api=1&origin=…&destination=…` with **no** `&travelmode` (user picks
  car/transit). The maps chip moves to the START of the 說明 cell with the slot emoji
  (dropping the literal 🗺️); a move row with endpoints leads with an A→B directions chip in
  both HTML and markdown. A move row without `from`/`to` is unchanged (no fabricated link).
  A move row that *also* carries a `poi_id` keeps the POI maps link + official source after
  the directions chip (so a bookable POI on a move row still satisfies the export-gate
  bookable-official-source check) and suppresses the now-mismatched thumbnail. The
  `itinerary-synthesis` SKILL output contract documents the `from`/`to` row fields so the
  synthesis author actually populates them.
- **G3 — 備案 as in-cell `.altbox` (`_STYLE`, `_row_html`).** A `▸` 備案 row is a full-width
  orange `.altbox` INSIDE the 說明 cell with an empty time cell and an empty thumb cell
  (never a thumbnail, even when its POI carries a photo) — superseding 0.18.4's whole-row
  `li.row.alt` box.
- **G4 — look-ahead dashed grouping (`_day_html`).** The dashed row separator is opt-in per
  `dashed = (not last) and not next_is_alt`: real→alt none, alt→alt none, alt→real dashed,
  real→real dashed, *→last none. This carries 0.18.4's 備案-binds-to-slot intent forward
  (the `↳` attach connector + `_attached_flags` + `.row.alt.attached` are removed).
- **G5 — lodging box (`_STYLE`).** The `.lodge` line is a light-blue rounded card
  (`background:#f0f9fb`); its thumb is right-aligned via `.lodge .thumb{margin-left:auto}`.
- **G6 — `no_internal_jargon` gate (`export_gate._jargon_failures`, `itinerary-synthesis`
  SKILL).** `run_export_gate` (md) and `run_html_gate` (html) hard-fail on a leaked internal
  `(poi-id)` token or the literal `must_do`, keyed off the authoritative POI id set (literal
  `(<id>)` match → zero false positive on legitimate romaji parentheticals). The scan runs
  over a backslash-stripped probe so a markdown-escaped leak (`must\_do`, `(hak-yam\_yakei)`)
  is still caught. Authoring rule documented in the synthesis skill.

Known follow-up (out of scope): `scripts/render/line_short.py` has no gate, so a `must_do` /
`(poi-id)` leak in `line-short.txt` still ships — closing it needs a new `run_line_gate`
(`run_export_gate` is md/html-only).

## 0.18.4 — D11 slot-level 備案 visually bound to the slot it replaces

Pure CSS/markup polish (`scripts/render/html_page.py`); no gate or schema change.

A `▸` alternative (備案) row used to render as a standalone orange box separated by the
same dashed border as every other row, so it was unclear which slot it replaced. Now a
**mid-day** alt-run is attached to the slot above it.

- **Attach rule (`_attached_flags` + `_day_html`).** A maximal run of consecutive alt
  rows is *attached* iff it is sandwiched between a real row **both before and after**
  (a fallback for the preceding slot). The attached alt gets `class="row alt attached"`
  and the real row above gets `has-alt`; a **trailing** run (day-tail 本日備案, e.g.
  「備案(乃の風訂不到)」) or a **leading** run stays an independent box. Consecutive alts
  bind to the same parent.
- **Connector styling (`_STYLE`).** `.row.alt.attached` drops its top border + top
  radius, indents to the `.bd` column (`margin-left:62px`), and shows a `↳` `::before`
  connector; the parent real row drops its dashed separator (`.row.has-alt`) so the pair
  reads as “↳ if … then …”.

Note: the slot-vs-day distinction is positional only — a mid-itinerary day-level note
(e.g. a luggage-transfer line) still attaches to the row above it; cleanly separating
those would need a synthesis-level day-scope marker (out of this render-only scope).

## 0.18.3 — D10 lodging thumbnail alignment

Pure CSS/markup polish (`scripts/render/html_page.py`); no gate or schema change.

- **Lodging thumbnail right-aligned, consistent with row thumbs.** `_day_html` previously
  emitted the lodging `_photo_html` as a sibling **after** the `.lodge` `</div>`, landing
  in the non-flex `.day-card` where `.ph{margin-left:auto}` was a no-op — so the lodging
  thumb hung at the left while every row thumb sat at the right. The photo is now nested
  **inside** the `.lodge` div, and `.lodge` is a flex row
  (`display:flex;align-items:center;flex-wrap:wrap;gap:6px`), so its thumb pins to the
  right edge like the rest.

## 0.18.2 — D9 photo caption layout: thumb-title attribution + centred lightbox caption

Pure CSS/markup polish on the photo caption (`scripts/render/html_page.py`); no gate
or schema change.

- **Row caption removed.** `_photo_html` no longer emits a `<span class="phcap">` under
  the thumbnail. The duplicate caption (already shown in the lightbox) was stretching
  the 60px thumb's column to ~170px. Attribution now rides on the thumbnail's **`title`
  attribute** (visible on hover, plain-text `📷 author / license`, `_html_escape`'d) plus
  the lightbox caption — so CC attribution stays reachable without occupying the row.
- **Lightbox caption centred.** `.lbbox` is now a vertical flex column
  (`display:flex;flex-direction:column;align-items:center`) and `.lbimg` is
  `display:block`, so `.lbcap` sits centred directly under the image. Previously
  `text-align:center` on an inline image/caption pushed a landscape image's caption to
  the right.

## 0.18.1 — D8 photo polish: right-aligned thumbnail + gate-on-merged-pois

Visual + correctness polish on the 0.18.0 photo enrichment.

- **🖼️ Right-aligned thumbnail (`scripts/render/html_page.py`).** The POI photo was a
  168×120 block stacked under each row's text. It is now a **60×60 square thumbnail
  (`object-fit:cover`) pinned to the right edge of the row**: `_row_html` emits the
  `.ph` block as the last flex child of `<li class="row">` (a sibling **after** `.bd`,
  not nested inside it) and `.ph`/`.thumbwrap` carry `margin-left:auto`. The pure-CSS
  checkbox lightbox and the mandatory attribution caption are unchanged.
- **🚦 Export-gate runs on the MERGED pois (`skills/export-gate/SKILL.md`).** The gate's
  `photo_has_attribution` + `no_nondistributable_photo_source` checks only see a
  `photo`/`photo_source` on the side-file-merged pois. The Stage Contract previously fed
  the gate the canonical `verified-pois.yaml` (which never carries photos, by design),
  so those checks spun against nothing. The contract now requires overlaying
  `verified-pois-media.yaml` via `scripts/media_merge.py::apply_media` (the same overlay
  `export-artifact` applies before render) before invoking the gate; the photo checks
  and the `<img src>` whitelist are now documented in the Checks list.

## 0.18.0 — opt-in CC photo enrichment + place_id deep-link + img-src/attribution gate

Adds **optional, license-clean, attributed POI photos** to the HTML one-pager (plus
a Google-Maps `place_id` deep-link upgrade), behind a pluggable photo adapter whose
**default backend is `none`** — nothing changes for existing trips. Photos are
provenanced, CC-whitelisted, durable across re-verify (stored in a side-file, never
in the wholesale-rewritten canonical yaml), and gate-enforced. Delivered as a delta
on 0.17.0 under the 8-step pre-ship gate (TDD red→green, full pytest green, a single
cross-defect e2e fixture, an 8-agent adversarial matrix re-review).

**Boundary principle (ToS safety):** the *mechanism* (adapter dispatch, license
whitelist, base64 encode, gate) ships in-plugin and is generic; the *data* (a
licensed image, an API key) is supplied at runtime by the operator who owns the ToS
relationship. `backend=none` ships enabled; `backend=wiki` is CC-only and safe to
distribute; `backend=google` is BLOCKED (no display-surface ToS clearance / no
personal-cache exception) **and** its output is marked non-distributable by the gate.

- **🗺️ Maps `place_id` deep-link.** `scripts/render/gmaps_links.py::maps_url` appends
  `&query_place_id=<id>` (fully percent-encoded, `safe=''`) when a POI carries the new
  optional `gmaps_place_id`, in both the name-search and `pin_exact` branches — the
  visible `query` (name or coords) is left intact. Both markdown + HTML adapters inherit
  it from the shared builder.
- **🖼️ Photo schema fields.** `schemas/verified-pois.schema.json` gains optional
  `gmaps_place_id`, `photo` (`{url|data, width?, height?, thumb?}`; `url` pinned
  `^https://`, `data` pinned `^data:image/`), `photo_attribution`
  (`{author, license, source_url}`, all required + non-empty when present), and
  `photo_source` (enum `{wikimedia, openverse, google}`). A new `allOf` conditional
  enforces **photo ⇒ photo_attribution**. None are added to `required`; the line-330
  POI seal still rejects typo keys.
- **🗄️ Durable side-file + render-time merge.** A new
  `schemas/verified-pois-media.schema.json` governs `trips/<slug>/verified-pois-media.yaml`
  (keyed by `poi_id`, own `additionalProperties:false` seal). `scripts/media_merge.py`
  overlays it onto the poi_map at export (`apply_media` is a pure, non-mutating, key-
  whitelisted overlay; `load_media` degrades to `{}` on absent/corrupt/non-dict). Media
  is **never** written into canonical `verified-pois.yaml` (source-verify rewrites it
  wholesale). `export-artifact` SKILL prose wires the overlay in before render.
- **📷 Photo render: thumb + pure-CSS lightbox + mandatory caption.**
  `scripts/render/html_page.py` renders a `data:`/`https` thumbnail, a **pure-CSS
  checkbox-hack lightbox** (no `<script>`, no `href`/`#anchor` toggle), and a
  **mandatory, `_html_escape`'d attribution caption** (author / license + source link).
  Checkbox ids are unique per call site (a POI can be both a row and the day's lodging).
- **🚦 Export-gate hardening (`scripts/export_gate.py`).** `run_html_gate` adds an
  `<img src>` whitelist (`data:image/` or `https://` only — the gate was previously
  `href`-only and structurally blind to `src=`). Both gates add **photo ⇒ non-empty
  (stripped) attribution** and **`photo_source=google` ⇒ non-distributable** checks
  (`img_src_safe`, `photo_has_attribution`, `no_nondistributable_photo_source`), so
  the distributability guard ships even though no google backend exists yet.
- **🧩 Pluggable CC photo adapter (`scripts/photo_adapter.py`, `backend=wiki`).**
  Wikimedia Commons + Openverse client; **hard license whitelist** `{CC0, PD, CC-BY,
  CC-BY-SA}` rejecting NC/ND; 2-size base64 (thumb + full); descriptive User-Agent on
  every request; caller-supplied per-source `RateLimiter` (mirrors the Nominatim
  ≤1 req/s discipline); per-trip cache; `name_local`-first query + geocode location-
  match; landmark-only. CC-BY-SA is kept (share-alike binds the image, not the MIT
  plugin code; the rendered caption + source link satisfy its terms).
- **Adversarial-review hardening (step 8).** Stripped whitespace-only attribution
  before the gate truthiness test; `load_media` now guards non-dict YAML + broadens
  its `except` to `OSError`/`UnicodeDecodeError` (mirroring `geocode_cache`);
  `apply_media` ignores a non-dict media entry.

README: §3 deliverables gains a plain-language photo bullet; the §2 step-table
`export-artifact` row notes the optional photo overlay; the 開發者資訊 `<details>`
documents the adapter/side-file/schema/gate. No new pipeline stage → §2 mermaid
unchanged (render-time, in-stage feature).

## 0.17.0 — card-style HTML one-pager + mobile RWD fail-safe + XSS hardening

The `html` export adapter (`scripts/render/html_page.py`) is rewritten from a
plain card list into a magazine-style one-pager, modelled on the hokkaido-7d
dogfood deliverable. Everything new is derived strictly from `itinerary.yaml`
fields — nothing is fabricated (Source-Verified-First): the advisory `warn`
box from the hand-authored reference is intentionally omitted because that data
is not in the itinerary dict.

- **🎨 Card-style layout.** Gradient hero with a date-span (from `days[].date`)
  and a 🏨 lodging-flow line (distinct consecutive overnight stays with ×count,
  resolved from per-day `lodging`); a per-day overview table (日 / 行程 / 住宿);
  an emoji legend; rounded shadowed `.day-card`s with a day-number badge and a
  lodging maps link; per-slot row colouring (meal / visit / activity / move /
  lodging); and orange-bordered inline 備案 rows (a row whose `text` starts `▸`).
  The `lodging` field — previously ignored by every renderer — is now surfaced
  as a maps-linked line and in the overview/hero (HTML adapter only).
- **📱 Mobile RWD fail-safe.** Flex rows default to `min-width:auto` and will not
  shrink, so a long Japanese map label forced a horizontal page overflow on
  phones. Fixed with `html,body{overflow-x:hidden}` (backstop),
  `.bd{min-width:0;overflow-wrap:anywhere}`, an `a.map` that wraps
  (`word-break:break-word;max-width:100%`, no more `white-space:nowrap`), and
  `word-break:break-word` on overview table cells (the one long-content element
  outside the flex fix).
- **🔒 XSS hardening.** `_date_span` was the sole interpolation point left
  unescaped; a crafted `day.date` (e.g. `<img src=x onerror=…>`) reached the
  hero verbatim **and passed `run_html_gate`**, whose only markup guard is a
  literal `<script>` substring check. `_date_span` now escapes, matching the
  discipline applied to every other field. (Surfaced by an adversarial review.)
- **Gate compatibility unchanged.** Every emitted `href` is an https Maps URL
  (href-first attribute order) and exactly one `class="day-card"` is emitted per
  day, so `export-gate` / `run_html_gate` still pass; the markdown / gmaps /
  line / Notion adapters are untouched. README §3 deliverable copy updated.

## 0.16.0 — hokkaido-7d dogfood defects (D1-D4)

Four defects surfaced by a real Hokkaido 7-day dogfood run, plus a cross-cutting
audit of the false-pass shape that produced two of them.

- **D1 🔴 Google Maps links — name-search-first.** `maps_url` now returns
  `query=<name_local> <district>` so Google resolves a labelled place card,
  reversing the TW-048 coord-first default that produced unnamed pins for area
  POIs (onsen districts, parks, markets). Coordinate pinning is now opt-in via
  `geocode.pin_exact: true`. Source-verify gained `normalize_and_validate_poi`,
  which normalises legacy `lon`/`long` geocode keys to `lng` and **rejects**
  `name_local == district` (the `cluster_fallback` town-name bug, where a POI's
  name was silently overwritten by its area).
- **D2 🟠 itinerary-gate false-pass — overnight lodging floor.** New always-on
  `overnight_days_have_lodging` check derived from `itinerary.yaml`: every
  non-final day must resolve lodging (a `lodging` field or a `slot:"lodging"`
  row), independent of whether `accommodations.yaml` was passed. Previously the
  lodging check was gated behind the optional `accommodations` arg, so an
  itinerary with no overnight rows passed silently.
- **D3 🟡 Japanese gloss.** New optional `name_zh` schema field and render label
  `name_display（name_zh）`; new hard-fail export-gate `japanese_glossed` — any
  line carrying kana (hiragana/katakana) without a `（中文）` gloss fails
  (Han is excluded to avoid ZH/JP false-positives). Itinerary-synthesis must
  author inline Japanese terms as `日文（中文）`.
- **D4 🟡 HTML export adapter.** New `scripts/render/html_page.py` renders a
  self-contained, offline, elder-friendly one-page `exports/<slug>-itinerary.html`
  (inline CSS, mobile RWD, Maps links inheriting the D1 name-search fix),
  validated by the new `run_html_gate`.
- **D2-class advisory fix 🔴 itinerary-gate — advisory presence enforced.** New
  always-on `advisory_present` safety floor: `advisory` is now a **mandatory**
  gate input. An absent advisory **fails the gate** ("advisory absent — …")
  instead of silently skipping the banned/restricted surfacing check. Unlike the
  D2 lodging floor (derivable from `itinerary.yaml`), the banned/restricted list
  lives *only* inside `advisory.yaml`, so absence cannot be reconstructed — the
  only safe response is failure. An advisory that ran but flagged nothing passes
  as `{"items": []}`. The per-item `advisory_items_surfaced` loop is unchanged
  and now runs only once `advisory_present` confirms an advisory exists. This
  closes the D2-class false-pass hole for the 🔴 safety gate.
- **Cross-cutting audit.** The "optional-input → skipped-check" false-pass shape
  (root of D1+D2) was swept across `scripts/`. The advisory sibling is fixed
  above; the remaining two out-of-scope instances in `gate.py` — the **calendar
  and must_do** checks, each gated behind their optional arg — are flagged for
  **v0.17.0 follow-up**, NOT fixed here.

## 0.15.0 — 2026-06-11

Research discipline + script robustness + adapter fidelity (Wave 4, final wave of the
2026-06-11 agentic-robustness audit) — 25 defects closed.

- **Script edge-cases:** `cost.sum_costs` raises on a non-numeric `amount` (no silent
  zero); `hours.to_minutes` rejects a non-`HH:MM` value (no crash deep in scheduling)
  and `closing_status` handles overnight (past-midnight) windows; `legs.misses_last_service`
  handles a small-hours last service; `geocode.resolve_place` rejects an empty name;
  `season.approx_sunset` accepts `lng`+`utc_offset_hours` for a civil-time correction.
  (TW-014, TW-020, TW-047, TW-021, TW-045, TW-050)
- **Cache integrity:** `geocode_cache.load_cache` tolerates a corrupt/non-dict file
  (renames to `.corrupt`, returns `{}`), `save_cache` is atomic (temp + `os.replace`),
  and `resolve_place` validates a cache hit's shape/source before trusting it. (TW-046,
  TW-019)
- **Export-adapter fidelity:** link labels escape `]`/`|`/`$`, source URLs percent-encode
  `)`; Google-Maps links are coordinate-pinned (or district-disambiguated); export-gate's
  bookable check scans table rows (not a heading) across all of a POI's rows; LINE output
  chunks at day boundaries under the 5000-char cap. (TW-022, TW-048, TW-044, TW-049)
- **Research discipline:** source independence is by distinct domain (`verify.py`);
  "no search, no fact" halts a research stage when WebSearch is unavailable; conflict and
  independence are defined operationally; hours carry an `as_of` recency; calendar requires
  trip-year coverage (`provisional` field); hotel centroid-fallback needs an existence
  proof; Gate 3 resolves the claimed-district centroid; negative-cache entries are
  invalidated on manual re-verify; Notion write-back runs only post-gate. (TW-023, TW-024,
  TW-032, TW-033, TW-052, TW-051, TW-058, TW-057, TW-025, TW-039, TW-061)
- **Tests:** a cross-stage closure fixture (verify→gate→render→export-gate) and README
  mermaid stage-coverage/order guards. (TW-059, TW-060)

## 0.14.0 — 2026-06-11

Flow + skill-contract hardening (Wave 3 of the 2026-06-11 agentic-robustness audit) —
12 defects closed. Makes the orchestrator's routing predicates explicit and gives
every halt condition an owning, testable stage.

- **Orchestrator routing made explicit:** `stale` (rule 3) and `ready` are now defined
  predicates (`scripts/orchestration.py::candidates_stale`); stage names are
  `tripwork:`-namespaced (no paperwork collision); a fail-routing rule (13.5) maps
  gate failure classes to owning stages; rule 13 re-runs the gate when itinerary is
  newer; a terminal rule declares the pipeline complete on export-gate pass. (TW-053,
  TW-054, TW-029)
- **Slug binding (rule 0.5):** a new trip allocates an unused `<slug>`; a resume names
  one existing `trips/<slug>/`; file-existence rules never apply across trips.
  trip-brief derives `<yyyy-mm>-<destination>` and stops on collision. (TW-027)
- **Halt list synced with what stages emit:** adds reception-after-close (no late
  check-in), scopes the regulation halt to `banned` only, and adds a stage-state
  read-back rule so a recorded decision is not re-asked. (TW-031, TW-055)
- **stage-state.yaml schema** (`schemas/stage-state.schema.json`) — decisions are now a
  validated, re-readable record. (TW-055)
- **Owned halts:** `booking lead-time missed` is owned by itinerary-synthesis via
  `scripts/booking.py::lead_time_missed`; `missed_last_service` is re-checked at
  synthesis once the departure is known (no longer suppressed). (TW-030, TW-026)
- **Hop plausibility floor:** `scripts/distance.py::min_plausible_mins` flags an
  `implausible` hop estimate below a physical speed floor (urban transit ≈ 15 km/h);
  routing-audit re-estimates rather than trusting a too-fast guess. (TW-056)
- **travel-advisory standalone mode** must not overwrite the pipeline `advisory.yaml`
  (writes `work/<slug>/advisory-adhoc.yaml`); orchestrator rule 11 treats a stale
  advisory as re-runnable. (TW-035)
- **trip-brief** is orchestrator-routed, guards on the preflight stamp before writing,
  and **using-tripwork** regenerates the full 17-stage pipeline tree. (TW-036, TW-037)

## 0.13.0 — 2026-06-11

Schema strictness (Wave 2 of the 2026-06-11 agentic-robustness audit) — 10 defects
closed. Tightens every artifact schema so a hallucinating agent's malformed output
is rejected at validation instead of flowing downstream silently.

- **`additionalProperties: false`** on every object schema across the 13 files — a
  typo'd key (e.g. `close_days` for `closed_days`) is now rejected instead of
  silently vanishing. (TW-013)
- **Source URLs** must match `^https?://` everywhere a `url` field appears; a bare
  token like `"airline"` no longer validates. (TW-008)
- **Coordinates** bounded: `lat ∈ [-90, 90]`, `lng ∈ [-180, 180]` in verified-pois /
  accommodations / routing — swapped or placeholder coordinates rejected. (TW-043)
- **ISO date pattern** (`^\d{4}-\d{2}-\d{2}$`) on calendar / trip-brief / seasonal
  date fields, so non-ISO dates can't silently disable date-equality logic. (TW-007)
- **advisory** requires `risk` and ≥2 sources; **calendar** holiday requires `impact`
  with `crowds`/`closures`; **cost** requires `as_of` + `estimate_note` (adds
  `fx_as_of`/`fx_source`); **legs** `fare`/`pass.price` require `amount`+`currency`;
  **transit** walks/peak_windows require sources (walk requires `station`). (TW-006,
  TW-040, TW-041, TW-042)
- **legs.mode** constrained to `drive|rail|bus|flight|ferry`; a `drive` leg requires
  `duration_mins` (schema if/then) and `scripts/legs.py::classify_leg` raises instead
  of defaulting an unmeasured drive to feasible. (TW-010)
- **trip-brief** requires a `destination` object (`country`/`city`/`local_lang`) and
  an optional `airline`, consumed by source-verify and travel-advisory. (TW-011)

## 0.12.0 — 2026-06-11

Iron-rule mechanization (Wave 1 of the 2026-06-11 agentic-robustness audit) — 14
defects closed. The itinerary becomes a canonical structured artifact so the gate
validates an artifact instead of an LLM-reconstructed dict, and travel-advisory
moves before synthesis so banned/restricted regulations shape the plan.

- **Keystone — canonical `itinerary.yaml`** (`schemas/itinerary.schema.json`, new).
  `itinerary-synthesis` now emits `itinerary.yaml` (`days[].rows[]` with `poi_id`,
  `slot`, `time`, `text` + optional `checklist`) as the single source of truth;
  `itinerary.md`, LINE and Maps exports all render from it. `scripts/gate.py::run_gate`
  consumes the structured itinerary, not a reconstructed days list. (TW-003, TW-017)
- **itinerary-gate now checks verification status.** A `conflicting`/`unverified`
  POI with a geocode no longer passes; `geocode: null` is caught. New checks:
  `referenced_pois_verified`, `no_closed_day_violation`, `must_do_covered`,
  `advisory_items_surfaced`. (TW-002, TW-018, TW-038, TW-034)
- **travel-advisory runs before itinerary-synthesis.** advisory.yaml now feeds the
  synthesis checklist and the gate; banned/restricted items must be surfaced.
  README §2 mermaid + step table reordered. (TW-028, TW-034)
- **source-verify Gate 0 (operating status).** A permanently/temporarily closed
  (defunct) POI is `rejected` instead of passing as `verified`. (TW-005)
- **Schema strictness:** `verified-pois` requires `geocode` + ≥2 sources only when
  `verify_status: verified` (non-verified require a non-empty `status_reason`);
  `closed_days` constrained to canonical weekday / ISO-date / `public_holiday`
  tokens, normalized in `poi_closed_on`; `gate-report` rejects `status: pass` with
  failures or empty checks. (TW-012, TW-001, TW-009)
- **export-gate** fails an empty or too-few-days deliverable; the `official` source
  flag is now authored by source-verify so the bookable-link check is enforceable.
  (TW-015, TW-016)

## 0.11.2 — 2026-06-09

Docs — wrap README pipeline mermaid node labels to stop GitHub CJK clipping.

- `README.md` §2 flowchart: the 0.11.1 `htmlLabels` directive did not stop the
  clip on GitHub (GitHub measures CJK glyph advance too narrow at render time,
  sizing node boxes by the Latin skill-name line while the wider CJK detail line
  overflows and the trailing characters are clipped). Re-flow every node's detail
  into shorter `<br/>`-separated lines so no single CJK line exceeds the box
  width. All label text preserved verbatim — only line breaks added.

## 0.11.1 — 2026-06-09

Docs — fix README pipeline mermaid clipping CJK node labels on GitHub.

- `README.md` §2 flowchart: add `%%{init: {'flowchart':{'htmlLabels':true}}}%%`
  directive so node labels render via foreignObject (browser box-model layout)
  instead of SVG `<text>` width estimation. GitHub's client-side width measure
  undercounts CJK glyph advance (treats them as Latin half-width before the web
  font loads), sizing node boxes too narrow and clipping trailing characters.
  No label text changed — every character preserved.

## 0.11.0 — 2026-06-06

Transit polish — intra-city comfort for elderly / luggage trips.

- New `transit-detail` stage (`skills/transit-detail/`): researches the destination's
  commuter **peak windows**, an **IC-card** advisory (Suica / ICOCA / T-money / …), and
  per-POI **station-to-POI walk** notes into `transit.yaml`
  (`schemas/transit.schema.json`). Wired as orchestrator stage 9. All advisory — no
  stop-on-confirmation, no `itinerary-gate` change.
- `scripts/transit.py`: pure `in_peak` (is a move in a rush-hour window?) + `walk_too_far`
  (is a station-to-POI walk over the comfortable max?).
- `trip-brief` schema gains `routing.max_walk_mins` (default 15).
- `itinerary-synthesis` consumes `transit.yaml`: off-peak advice for groups with elders /
  children, a taxi/flag for long walks, and the IC-card + walk notes into the checklist.
  No-key research, same model as calendar / seasonal.

## 0.10.0 — 2026-06-06

Geocode cache (faster re-runs, less Nominatim load).

- New `scripts/geocode_cache.py`: a per-trip on-disk cache (`cache_key`, `cache_get`,
  `cache_put`, `load_cache`, `save_cache`). `cache_get` returns `(hit, value)` so a cached
  miss (`None`, negative caching) short-circuits the network.
- `scripts/geocode.py::resolve_place` gains an optional `cache=None` param: a hit (including
  a cached miss) returns without touching Nominatim; otherwise the result (or `None`) is
  stored. `cache=None` preserves the original behaviour.
- `source-verify` and `accommodation-research` pass a per-trip cache
  (`work/<slug>/geocode-cache/geocode.json`) so re-runs skip already-resolved and known-miss
  lookups. No pipeline / schema / orchestrator change.

## 0.9.0 — 2026-06-05

Trip-cost rollup (big-ticket estimate + budget compare).

- New `cost-rollup` stage (`skills/cost-rollup/`): sums accommodation + inter-city
  transport + rail pass + a daily-incidental allowance into `cost.yaml`
  (`schemas/cost.schema.json`), computes a precise rail-pass break-even, and compares the
  total to `trip-brief.budget` (over → stop-on-confirmation). Wired as orchestrator
  stage 9 (B3). Everything is a no-key estimate with an `as_of` date.
- `scripts/cost.py`: pure aggregation — `sum_costs`, `incidental_total`,
  `pass_break_even`, `over_budget`.
- Numeric cost recorded upstream: `accommodations` candidates gain `cost`
  (amount/currency/basis); `legs` gain per-leg `fare` + a trip-level `pass` option;
  `trip-brief` gains `budget` / `daily_incidental` / `home_currency`.
- `itinerary-synthesis` renders a cost-summary block (breakdown, total, budget status,
  pass recommendation, FX note). No `itinerary-gate` change. Cross-currency uses a
  researched approximate rate (no FX API); per-meal/per-POI pricing stays out of scope.

## 0.8.0 — 2026-06-05

Mode-aware inter-stop legs (transit + self-drive parity).

- New `inter-stop-legs` stage (`skills/inter-stop-legs/`): one mode-aware leg per pair of
  consecutive overnight stops, researched from official sources into `legs.yaml`
  (`schemas/legs.schema.json`). Transit legs carry `service` / `reserved` / `transfers` /
  `last_service` / `pass_advice`; drive legs carry `duration_mins`. Wired as orchestrator
  stage 6 (B1).
- `scripts/legs.py`: pure feasibility — `drive_too_long`, `misses_last_service`,
  `classify_leg`. A single-day drive over `routing.max_single_drive_mins` (default 300) or
  a planned same-day departure past the last service → stop-on-confirmation, like a
  routing `far` hop. No `itinerary-gate` change.
- `trip-brief` schema: `overnight_stops[].leg_mode` (per-leg mode override of the
  trip-level `transport`) + `routing.max_single_drive_mins`.
- `itinerary-synthesis` renders the inter-city move per travel day and pushes reserved /
  pass / last-service notes into the checklist. Single-base trips have an empty `legs`
  list (no behaviour change). Precise rail-pass break-even is deferred to B3.

## 0.7.0 — 2026-06-05

Seasonal/weather advisory + no-key daylight.

- New `seasonal-advisory` stage (`skills/seasonal-advisory/`): no-key seasonal/weather
  hazard research (official sources: road authority / met service / parks) into
  `seasonal.yaml` (`schemas/seasonal.schema.json`). Two-tier severity — `blocking`
  stops on confirmation (closed pass), `advisory`/`info` flow to the synthesis checklist
  (chains, gear, short daylight). Wired as orchestrator stage 7 (B2).
- `scripts/season.py`: no-key solar-geometry daylight — `daylight_hours`,
  `approx_sunset`, `after_dark`. Per overnight stop's sunset is computed and, for
  `self_drive` trips, after-dark driving legs are flagged for an earlier start.
- `trip-brief` schema gains optional `transport` (e.g. `self_drive`).
- `itinerary-synthesis` consumes `seasonal.yaml` (advisories + daylight into the
  checklist). No `itinerary-gate` change — `blocking` stops at the stage, like
  `travel-advisory` `banned`.

## 0.6.0 — 2026-06-05

Accommodation layer + no-key geocode resilience.

- New `accommodation-research` stage (`skills/accommodation-research/`): per overnight
  stop, verify a user-provided hotel or recommend N=3 verified candidates (stop-to-pick).
  Produces `accommodations.yaml` (`schemas/accommodations.schema.json`). Wired as
  orchestrator stage 5 (D1).
- `trip-brief` schema: `overnight_stops` (ordered, per-stop optional `lodging`) +
  `facility_needs` (`required` hard / `periodic` soft). `base` retained, coexists (D1).
- D7 no-key geocode: `scripts/geocode.py::resolve_place` (structured Nominatim query
  then free-text), `cluster_centroid`; a real place Nominatim cannot pin degrades to
  `unverified` (`scripts/verify.py`) instead of `rejected`; accommodations fall back to
  the stop's cluster centroid (`geocode_source: cluster_fallback`) and stay verified.
  `verified-pois`/`routing` schemas gain `geocode_source` / cluster `centroid`.
- Facilities (`scripts/facilities.py`): `stop_meets_required`, `coverage_gaps`
  (periodic cadence, advisory), `reception_ok` (late-arrival lock-out, reuses
  `hours.py`). `itinerary-gate` adds `overnight_stops_have_lodging` +
  `required_facilities_met`; lodging rows reuse the v0.5.0 renderer + export-gate.

## 0.5.0 — 2026-06-04

Export integrity — the rendered deliverable is now contract-checked.

- `scripts/render/markdown.py`: `md_escape` backslash-escapes `\ $ _ * | < ` `` ` `` in all free
  text (prices like `\$120` no longer trigger KaTeX math mode and break previews,
  D4); each POI row appends a primary `官網` source link (D2); the POI name remains
  the maps link (D5).
- `verified-pois` schema: `sources[]` gains optional `official` (marks the
  official-site source for the deliverable link, D2).
- New `export-gate` stage (`scripts/export_gate.py` + `skills/export-gate/`): a
  mechanical post-export gate on `exports/<slug>-itinerary.md` checking
  `no_naked_dollar`, `links_well_formed`, `poi_name_is_link`,
  `bookable_has_official_source`. Reuses `gate-report.schema.json`. Wired as
  orchestrator stage 10; `fail` returns to `export-artifact` (D6).
- `export-artifact`: deliverable renamed `exports/<slug>-itinerary.md` (no longer
  clashes with the synthesis intermediate, D3); day tables must go through
  `render_day_table`.

## 0.4.0 — 2026-06-04

Closing-buffer awareness (intra-day scheduling safety).

- `scripts/hours.py`: `closing_status(start, close, last_call, need_mins)`
  classifies a scheduled arrival as `ok` / `tight` / `after_last_call` /
  `closed` against a POI's closing window.
- `verified-pois` schema gains per-POI `hours` (`close` / `last_order` /
  `last_entry` / `typical_visit_mins`), recorded by `source-verify`.
- `trip-brief` schema gains optional `scheduling`
  (`min_buffer_mins` default 30, `default_visit_mins` default 60).
- `itinerary-synthesis` never schedules a slot past last order/entry, flags
  thin buffers, and stops if a `must_do` cannot fit before close on any slot.
- day-granularity calendar closure (v0.3.0) now complemented by time-of-day
  buffer — a place open on the chosen day can still be reached too late.

## 0.3.0 — 2026-06-04

Calendar-awareness feature + geocode-query hardening.

- new `calendar-check` stage → `calendar.yaml`: destination public holidays
  (incl. substitute days) overlapping the trip range, each with crowds/closures
  impact and ≥1 official source (schema: `schemas/calendar.schema.json`).
- `verified-pois` schema gains per-POI `closed_days` (weekday / ISO date /
  `public_holiday` token), recorded by `source-verify` from the hours check.
- `scripts/calendar.py`: `weekday_of` / `holiday_on` / `is_high_crowd` /
  `poi_closed_on` decision logic.
- `itinerary-synthesis` hard-avoids scheduling a POI on a closed day (must_do
  closed on every feasible day → stop-and-ask) and flags holiday/weekend
  crowd days with earlier-start / off-peak advice.
- pipeline reordered: `routing-audit → calendar-check → itinerary-synthesis`.
- `source-verify` Gate 2 geocodes by `name_local` (English descriptor
  suffixes mis-resolve on live Nominatim, e.g. "Togetsukyo Bridge" → none).
- README rewritten in Traditional Chinese for non-engineer users (install
  flow, plain-language pipeline, holiday-awareness, dogfood examples).
- `CLAUDE.md` repo conventions (paperwork-style): mandatory README-freshness
  contract + writing convention + per-PR README check.
- `tests/test_readme_freshness.py` mechanical guard: every flow skill mentioned,
  `calendar-check` present in the workflow diagram, no obsolete names.
- `.github/workflows/ci.yml`: full hermetic pytest on every push/PR.
- `tests/test_version_consistency.py`: plugin.json / marketplace.json / CHANGELOG
  versions must agree (release-flow split-version guard).

## 0.2.0 — 2026-06-03

Hardening release: 5 known-issue fixes + workspace-shape-preflight entry-gate skill.

- advisory schema requires ≥1 official source (M1)
- candidates schema requires name_local + sources (M2)
- itinerary-gate checks meals + activities + visits POI references (M4)
- configurable region radius via trip-brief.routing.region_radius_km (M5)
- e2e must-do verification-failure closure test (M3)
- workspace-shape-preflight entry-gate skill (P1)

## 0.1.0 — 2026-06-03

Initial release.

- Orchestrator-driven staged pipeline (10 skills).
- Iron rule: Source-Verified-First (multi-source + geocode + region match).
- source-verify three-gate classification; routing-audit cross-region flags.
- itinerary-synthesis with contingency + pre-trip checklist sections.
- travel-advisory for entry/customs/battery regulations.
- itinerary-gate mechanical structure check.
- export adapters: markdown, Google Maps links, LINE short, Notion (graceful skip).
- Geocoding via OSM Nominatim.
