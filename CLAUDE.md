# tripwork — repo conventions for contributors (human + AI agent)

tripwork is a Source-Verified-First travel-planning pipeline plugin. The
pipeline, iron rules, and stage contracts live in `skills/`; pure decision
logic lives in `scripts/` with unit tests in `tests/`. This file carries the
contribution conventions that are NOT derivable from the code — chiefly the
README-freshness contract.

## Privacy: the repo never carries a user's trip (mandatory)

This repository is public. Its first incarnation shipped one user's trips: README
screenshots of a trip still ahead (hotels, dates, costs), test fixtures copying its
hotels and dates, defect reports and corpus tests naming their trips. It was rebuilt
from one clean commit (2026-10-03). A trip says when someone is away from home, where
they sleep and who they travel with -- treat every workspace trip as private.

- **Never commit anything from a consumer workspace** (`trips/`, `work/`, a rendered
  reader, a defect report about a real trip, a design-board preview of one). Defect
  reports and dogfood notes stay in the workspace; a PR describes the defect in general
  terms ("a consumer trip").
- **Examples, fixtures, screenshots are made up.** Use public landmarks, placeholder
  hotels (`示意`, `サンプル`, `.example` URLs) and dates that are no one's trip. README shots
  come from `docs/images/readme/demo_trip.py`. Never copy a hotel, address, member,
  date or cost from a workspace trip into the repo, not even "temporarily".
- **The test corpus is de-identified.** `tests/corpus/trip-a..` are real trips with slugs
  renamed, members `成員N`, hotels and home endpoints replaced and YAML comments dropped.
  A new corpus trip goes through the same treatment, and its free text is read line by
  line before it is committed (one trip carried two home addresses).
- **Mechanical guard:** `tests/test_privacy.py`. Everywhere (CI too): no tracked path
  under `trips/`, `work/`, `docs/specs/`, `docs/superpowers/`, `.design-board/`; images
  only under `assets/icons/` and `docs/images/readme/`; no e-mail address but
  placeholders; the corpus keeps its de-identified shape. Where a consumer workspace
  exists (`TRIPWORK_WORKSPACE`, default `../tripwork-workspace`): every identifying string
  of its trips -- slugs, the hotels stayed at, members, home endpoints, the dates of trips
  still ahead -- is derived from the workspace and must appear in no tracked file. The
  list is never written into the repo. Run the full `pytest` before every PR.
- `git add -A` / `git add .` can sweep an untracked workspace file into a commit: stage
  paths by name.

## Plugin-internal change checklist (mandatory)

The following changes MUST update `README.md` in the **same PR** (the relevant
narrative section, not just a CHANGELOG bullet):

- `skills/` — a flow/stage skill added / renamed / removed
- `schemas/` — an artifact schema added, or a field that changes user-visible
  behaviour (e.g. `closed_days`, a new gate output)
- Pipeline stage order or branching changed (e.g. inserting `calendar-check`
  between `routing-audit` and `itinerary-synthesis`)
- Export adapters changed (markdown / gmaps / html / notion)
- An iron rule or stop-on-confirmation condition added or changed

**Mechanical guard:** `tests/test_readme_freshness.py` fails when README drifts
— every flow skill must be mentioned, the `calendar-check` stage must appear in
the workflow diagram, and no obsolete name may reappear. It runs in the
standard `pytest` sweep on every PR. (`using-tripwork` is the agent-facing meta
skill and is intentionally excluded — it is not a user-facing pipeline stage.)

**Narrative correctness** (does the README explain the new stage well? is the
mermaid placed correctly?) is human-review territory — the freshness test only
checks mention coverage.

This rule applies to AI agent contributors as well as humans. A PR that touches
the categories above without a README update will fail the freshness test and
be rejected.

## README writing convention (mandatory)

`README.md` is **user-facing for non-engineers**. Screenshots of the reader (the demo trip),
plain-language value and copy-paste prompts come first; plugin-internal vocabulary
stays in the collapsed 開發者資訊 `<details>` (the workflow diagram and step table
live there since the user's README rewrite, 2026-10-03: "flowchart 不重要").

| Section | Purpose | What goes here | What must NOT go here |
|---|---|---|---|
| Opening + hero shots | Show it in one look | one-line pitch, 3 phone screenshots, the iron rule in one plain paragraph | skill names, schema field names |
| 它幫你解決什麼痛點 | Sell the value in plain language | pain → fix table | skill names, schema field names |
| 三步開始 | install → 起手式 → answer + pick titles | `claude plugin` commands, one copy-paste prompt, the picker screenshot, update command | pipeline internals |
| 你會拿到什麼 | Deliverables, shown | phone + desktop screenshots, what each screen does; md / checklist / lodging / cost / photos | how they are rendered |
| 招牌規則 + 何時停下來問你 | Iron rule + stop conditions | Source-Verified-First; grouped stop list, the full list in `<details>` | gate/script names |
| 常見問題 / 開發者資訊 | FAQ + collapsed dev sections | FAQ; in `<details>`: the mermaid + step table, the dogfood cases, `pip install` / pytest / geocode policy | dev jargon outside `<details>` |

Screenshots live in `docs/images/readme/` and come from a **made-up demo trip**, never a
user's real one (their plans are private -- the user's call, 2026-10-03, after the first
README showed their trip): `python docs/images/readme/demo_trip.py` renders a fictional
3-day Tokyo trip (public landmarks, a placeholder hotel, no photos) with the shipped
reader and re-takes every shot. The same goes for file-name examples and any sample in
README / docs prose. The title picker is shown on the desktop, where it is used.

Hard rules:

- The mermaid in 開發者資訊 is the only main-pipeline diagram. Keep it in sync with
  the orchestrator stage order (`tests/test_readme_freshness.py` checks it).
- Skill names appear in the diagram + step table and the dev `<details>`, not in
  the selling prose above.
- **Mermaid node line-length cap.** GitHub renders mermaid client-side and
  **clips any node line wider than ~26 character-units at the right edge** —
  language-agnostic (a pure-ASCII line like `Markdown / Maps / LINE / Notion`
  clips too; 1 CJK char ≈ 2 units). The `%%{init:{flowchart:{htmlLabels:true}}}%%`
  directive does **not** fix it (GitHub caps regardless). The only reliable fix
  is to break every node label into short `<br/>` lines: **≤ ~8 CJK chars or
  ≤ ~16 ASCII chars per line.** Skill-name tokens (≤25 chars) are safe unbroken.
  This is not reproducible with local `mermaid-cli` (local Chrome has CJK fonts
  and does not clip) — verify on GitHub web, not locally. (History: v0.11.1
  tried htmlLabels and failed on GitHub; v0.11.2 fixed it by wrapping.)

## Every plugin update must check README (mandatory)

When opening any PR that touches `skills/` / `schemas/` / pipeline-stage code /
export adapters / iron rules, walk the README and answer:

1. Does the mermaid (開發者資訊) still match the orchestrator stage order? (Did a
   stage move, get inserted, or produce a new artifact file?)
2. Does the step table need a new skill row, or an updated description?
3. Does the 痛點表 / stop-condition list need a new row? (Did a new
   stop-on-confirmation or user-visible behaviour land?)
4. Did the reader's look change? Then re-take the screenshots:
   `python docs/images/readme/demo_trip.py`.
5. Does the FAQ / a dev `<details>` need a new line? (New schema field, script,
   or export behaviour worth a mention?)

PR descriptions touching the categories above must include a one-line
"README check: ✅ diagram/stop list still match" OR a "README update bundled in this PR"
pointer.

## Visual work: frontend-design first, measure before and after (mandatory)

Any change to something people see — the reader (CSS in `scripts/render/reader/`, a new
control), the title picker page, a password page, the README screenshots, a mockup or a
"quick" prototype for the user — follows this order, with any AI agent. It is written down
because skipping it has cost the user a round of review again and again: a 4 px card
misalignment, stamp lines too thin, desktop calendar text too small, a hide-on-scroll
prototype whose motion felt wrong, and a day stepper drawn 34 px tall inside a 25.6 px
title line.

1. **Load `frontend-design:frontend-design` before designing**, every time, including
   prototypes and board previews. Follow its process (plan → review → build → critique).
2. **Measure first.** Read the computed values of what the new element sits next to —
   font size, line height, the size and border of neighbouring components — in WebKit at
   390 px (phone) and Chromium at 1366 px (desktop). Design from those numbers, not from
   memory of the stylesheet.
3. **Fit the measured box.** A control in a text line is no taller than that line's
   existing components and shares their centre; a larger tap target grows invisibly
   (`::after`), not the drawn shape. Reuse the reader's tokens, type and glyphs
   (`‹ ›`, `--rule`, `--mut`, ZenEmb) instead of inventing new ones.
4. **Measure after — the ink, not the boxes.** Render it, measure heights, edges and
   centres against step 2, and screenshot both widths before showing anyone. Alignment is
   judged on the glyphs' ink (pixel rows in a high-DPR screenshot), not on element boxes:
   a CJK title's ink does not sit in the middle of its line box, so two boxes can share a
   centre (0 px) while the pill reads 1.5 px high. For Latin text inside a control, centre
   on the capitals and digits (a descender like `y` is not part of the optical centre).
   State the numbers per engine; WebKit (the iPhone) decides when the engines differ.
   Measure each glyph group on its own colour and keep borders out of the sample (a pill's
   rounded ends run through its arrows' columns and once read as "arrows 0.0 px" while
   they sat 1.75 px low). When a number and the screenshot disagree, the screenshot wins:
   find the measuring bug before showing anything. A control that should read as part of
   a text line is as tall as that line's ink, not its line box.
5. **The user chooses, on a design board any agent can make.** Visual and wording choices
   go to the user as rendered previews, each with a recommendation; never decide one
   silently. Write a YAML of topics and run `python scripts/design_board.py board.yaml`:
   it writes one offline page to `.design-board/` (git never tracks it, so a preview may
   show the user's own trip there). Give the user the file path; they open it in a
   browser, pick a card per topic (each shows its key, e.g. `L2`), add a note, and
   「複製選擇」 gives one line to paste back, e.g. `樣式看板「…」：photos=P1；pill=T25b（…）`.
   An agent that can publish pages (a Claude artifact) may publish the same file as well;
   the local file is the board. Record the pick in the PR description.

## Guards must call their subject, not rebuild it (mandatory)

Across three releases the dominant defect in this repo has been a guard that
stays green while no longer testing what it claims. The cause is always the
same: the guard rebuilt a copy of the thing it was supposed to measure, and
the two copies drifted silently. Every instance below is real:

- v0.33.0 C1 — a corpus guard hand-built `by_id` from verified-pois alone (58
  rows) while the shipped gate used `scripts/gate.py::poi_pool` (63 rows); the
  5-row delta was the whole defect and the guard could not see it.
- v0.34.0 — `test_gate_does_not_re_derive_a_chosen_lodging_on_both_axes` was
  inert because `rederive_kwargs()`'s default `accommodations={"stops": []}`
  folds nothing. Proven by injecting the exact bug it names and watching it
  stay green.
- v0.35.0 TW-074 — corpus figures lived as literals inside tests, so when the
  consumer fixed their data using the mechanism v0.34.0 shipped, 8 guards went
  red with no plugin defect anywhere.
- v0.35.0 TW-076 — `tests/test_schema_symmetry.py`'s allowlist had grown to 45
  names, 12 of them record fields, leaving `rederive_legs` and `rederive_hops`
  with zero fields under guard. Injecting TW-071's original deadlock left the
  whole suite green.
- v0.35.0 TW-079 — the README mermaid order guard compared README to a
  hand-kept literal list instead of `scripts/next_stage.py::_CHAIN`.

What follows from this:

(a) A guard obtains pipeline state by **calling** the shipped function or
    constant — e.g. `scripts/gate.py::poi_pool`, `scripts/next_stage.py::_CHAIN`,
    `scripts/orchestration.py::GATE_INPUTS` / `EXPORT_GATE_INPUTS` /
    `EXPORT_DELIVERABLES`, `tests/corpus_measure.py::measure_corpus` — never by
    hand-assembling an equivalent.
(b) When there is no importable source, a literal is allowed, but the comment
    must say *this is a literal because X* so the boundary is visible instead
    of silent. Worked example: `tests/test_readme_freshness.py`'s
    `_PIPELINE_ORDER` derives its first 11 stages from `_CHAIN` and states why
    the trailing 4 (rule branches 12-16, no shipped sequence constant to call)
    stay literal.
(c) Before trusting a new guard, inject the bug it names and confirm the guard
    goes red. In this repo that check has never once been wasted — it caught
    TW-076's blindness above and proved TW-074's baseline rewrite had not
    hollowed the guards out.
(d) Measurements of an external dataset (the consumer corpus) must not be
    literals in tests. Use `tests/corpus-baseline.json`, regenerated by
    `python -m tests.corpus_measure --write`, and commit the regenerated diff
    in the same PR for human review.

## Dev environment (every machine, before the first test run)

A missing piece does not always fail loudly: without the system libraries WebKit
errors only once a test reaches it, and without a workspace the privacy check of
real trips is skipped while the run still looks green. Set up a new machine in this
order (Ubuntu / WSL; macOS skips the `sudo` line):

```bash
python3 -m venv .venv                 # gitignored; Ubuntu >= 23.04 refuses a system-wide pip install (PEP 668)
.venv/bin/python -m pip install -e ".[dev,browser,maps]"
.venv/bin/python -m playwright install chromium webkit                # browsers, no sudo
sudo .venv/bin/python -m playwright install-deps chromium webkit      # system libraries via apt
```

- The `sudo` line asks for the user's password, so an agent cannot run it: tell the
  user to run it in a separate terminal tab, that the password prompt shows nothing
  while typing, and to report back when it ends without an `E:` line. Symptom when it
  was skipped: `Host system is missing dependencies to run browsers` from a WebKit test.
- Unit sweep: `.venv/bin/python -m pytest -q`. Browser suite:
  `.venv/bin/python -m pytest tests_browser -q`. WebKit is the iPhone engine: a
  Chromium-only run never counts as a browser pass.
- `TRIPWORK_WORKSPACE` (default `../tripwork-workspace`) must point at the consumer
  workspace for `tests/test_privacy.py` to compare real trips; where none exists that
  test reports `skipped`, not passed.
- Python >= 3.11 (`pyproject.toml`; CI runs 3.11).

## Pre-ship gate

This repo follows the user's 8-step plugin pre-ship gate (TDD red→green,
full pytest green, e2e fixture closure, matrix re-review) before any
`OK 更新 plugin` release. README freshness is part of step 9 ship artifacts.

## Release flow — version bump

A version bump moves **8** version-bearing manifests plus the CHANGELOG, all in
the release commit. Run them in one shot:

    python scripts/bump_version.py <X.Y.Z>

then hand-author the `## X.Y.Z — <desc>` CHANGELOG entry. The 8 manifests:
`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `pyproject.toml`,
`package.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`,
`.kimi-plugin/plugin.json`, `gemini-extension.json`. All must equal the CHANGELOG
top heading. Mechanical guards: `tests/test_version_consistency.py` (every
manifest == CHANGELOG top), `tests/test_version_bump_manifest_lists_all.py`
(`.version-bump.json` lists exactly the 8), and `scripts/bump_version.py --audit`
(no stray undeclared file carries the version). The version-less `.opencode/`
and `.pi/` descriptors are not bumped.

Touching any manifest, hook, or alt-platform descriptor must pass the
cross-platform gates (`test_version_consistency`, `test_bump_version`,
`test_alt_platform_descriptors`, `test_run_hook_invariants`,
`test_agent_context_files`).
