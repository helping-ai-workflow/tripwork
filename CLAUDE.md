# tripwork — repo conventions for contributors (human + AI agent)

tripwork is a Source-Verified-First travel-planning pipeline plugin. The
pipeline, iron rules, and stage contracts live in `skills/`; pure decision
logic lives in `scripts/` with unit tests in `tests/`. This file carries the
contribution conventions that are NOT derivable from the code — chiefly the
README-freshness contract.

## Plugin-internal change checklist (mandatory)

The following changes MUST update `README.md` in the **same PR** (the relevant
narrative section, not just a CHANGELOG bullet):

- `skills/` — a flow/stage skill added / renamed / removed
- `schemas/` — an artifact schema added, or a field that changes user-visible
  behaviour (e.g. `closed_days`, a new gate output)
- Pipeline stage order or branching changed (e.g. inserting `calendar-check`
  between `routing-audit` and `itinerary-synthesis`)
- Export adapters changed (markdown / gmaps / line / notion)
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

`README.md` is **user-facing for non-engineers**. Plain-language value and
copy-paste prompts come first; plugin-internal vocabulary stays in the workflow
diagram / step table and the collapsed 開發者資訊 `<details>`, never in the
opening prose.

| Section | Purpose | What goes here | What must NOT go here |
|---|---|---|---|
| 這是給誰用的 / 痛點表 | Sell the value in plain language | "不用會寫程式", pain → fix table | skill names, schema field names |
| §1 快速開始 | 起手式 + install + update | one copy-paste prompt, `claude plugin` commands | pipeline internals |
| §2 完整跑一次會發生什麼 | The one mermaid + plain step table | skill names, ⛔ gate markers, artifact files | code-level detail |
| §3 你會拿到什麼 | Deliverables | md / gmaps / LINE / Notion outputs | how they are rendered |
| §4 招牌規則 + 何時停下來問你 | Iron rule + stop conditions in plain language | Source-Verified-First, stop-on-confirmation list | gate/script names |
| §5 實測範例 | Dogfood proof | real geocoded cases, gate-fires-correctly evidence | — |
| 常見問題 / 開發者資訊 | FAQ + collapsed dev section | API-key/Notion FAQ; `pip install` / pytest / geocode policy inside `<details>` | dev jargon outside `<details>` |

Hard rules:

- The §2 mermaid is the only main-pipeline diagram. Keep it in sync with the
  orchestrator stage order.
- Skill names appear in §2 (diagram + step table) and the dev `<details>`, not
  in the §1 / §3 / §4 selling prose.
- **§2 mermaid node line-length cap.** GitHub renders mermaid client-side and
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

1. Does the §2 mermaid still match the orchestrator stage order? (Did a stage
   move, get inserted, or produce a new artifact file?)
2. Does the §2 step table need a new skill row, or an updated description?
3. Does the 痛點表 / §4 stop-condition list need a new row? (Did a new
   stop-on-confirmation or user-visible behaviour land?)
4. Does §5 / FAQ / dev `<details>` need a new line? (New schema field, script,
   or export behaviour worth a mention?)

PR descriptions touching the categories above must include a one-line
"README check: ✅ §2/§4 still match" OR a "README update bundled in this PR"
pointer.

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
