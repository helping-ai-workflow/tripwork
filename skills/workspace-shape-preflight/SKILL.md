---
name: workspace-shape-preflight
description: Use when the tripwork pipeline is about to run its first stage in a cwd with no work/.preflight-completed stamp.
---

# workspace-shape-preflight

The first pipeline invocation in any cwd is gated here. It validates that the trip workspace matches tripwork's expected shape before the orchestrator advances to trip-brief.

## When To Use

- A travel-planning request arrives and `work/.preflight-completed` does not exist.
- Skip entirely once the stamp exists.

## Checks

1. Confirm a writable `trips/` location (per the target repo CLAUDE.md convention) and a `work/` location for rebuildable state.
2. If the cwd already contains unrelated files (brownfield), do NOT write anything until the user confirms the chosen `trips/<slug>/` and `work/<slug>/` paths.
3. On a blank workspace, propose the default layout and ask for confirmation.

## Stamp

After the user confirms the layout, write `work/.preflight-completed` (empty file). The orchestrator checks for this stamp and skips preflight when present.

## Stop-on-Confirmation

Always stop and ask before creating directories in a non-empty cwd. Never overwrite existing files.

## Stage Contract

| Field | Value |
|---|---|
| Input | A travel-planning request in a cwd with no `work/.preflight-completed` stamp. |
| Output | Confirmed workspace layout + `work/.preflight-completed` stamp. |
| Stop condition | Non-empty/brownfield cwd, or any layout ambiguity → ask the user before writing. |
| Next stage | `tripwork:orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Writing dirs into a brownfield cwd without asking | Stop-on-confirmation: confirm paths first. |
| Re-running preflight every invocation | Skip when `work/.preflight-completed` exists. |
