---
name: using-tripwork
description: Use when starting any travel-planning workflow with tripwork, before any pipeline stage runs.
---

# Using tripwork

tripwork is a staged, orchestrator-driven pipeline for building source-verified travel itineraries.

**Entry point:** Always start with `tripwork:tripwork-workspace-shape-preflight` (first time in a cwd) then `tripwork:tripwork-orchestrator`. Never jump directly to synthesis or export.

## The Workspace Layout

A workspace is the folder holding `trips/` and `work/`: each trip lives in `trips/<slug>/` (its artifacts in `trips/<slug>/data/`) and its rebuildable state in `work/<slug>/`; the layout is fixed: `tripwork.py` runs from that folder and fills in exactly these paths — so the target repo's `CLAUDE.md` may add conventions of its own but cannot move these folders.

## Running the scripts

Every script runs through one entry point, from the workspace root (the folder holding `trips/`):

    python <plugin>/scripts/tripwork.py <command> <slug> [arguments]

`python <plugin>/scripts/tripwork.py -h` lists the commands (`next`, `verify`, `gate`, `export`,
`export-gate`, `maps`, `photos`, `picker`, `validate`, `fingerprint`, `publish`, `deploy`,
`migrate`). `<plugin>` is the tripwork install folder; take the first of these you have:

1. **Claude Code:** the "Base directory for this skill: …/skills/<name>" line shown when a tripwork
   skill loads — `<plugin>` is two folders up from it.
2. The `tripwork scripts: python "…/scripts/tripwork.py"` line the session start injected
   (Claude Code, Cursor, Codex, OpenCode, Pi) or GEMINI.md names (Gemini:
   `~/.gemini/extensions/tripwork/`). Kimi installs plugins under
   `$KIMI_CODE_HOME/plugins/managed/<id>/`.
3. Claude Code's install record: `installPath` of `tripwork@tripwork` in
   `${CLAUDE_CONFIG_DIR:-~/.claude}/plugins/installed_plugins.json` (prefer the project-scope entry
   whose `projectPath` is the workspace).

Never pick a folder by globbing a plugin cache — several versions sit there side by side. If none
of the above gives a path, ask the user where tripwork is installed.

## Pipeline

The orchestrator's Stage Selection is canonical for order and predicates; this tree mirrors it.

```
tripwork-workspace-shape-preflight  (entry gate — first invocation only)
  └─ tripwork-orchestrator
       ├─ trip-brief            → trip-brief.yaml
       ├─ travel-advisory (gate)→ advisory.yaml (entry/customs/battery — before research)
       ├─ destination-research  → candidates.yaml (untrusted pool)
       ├─ source-verify  (gate) → verified-pois.yaml
       ├─ routing-audit         → routing.yaml
       ├─ accommodation-research→ accommodations.yaml
       ├─ inter-stop-legs       → legs.yaml (city-to-city feasibility)
       ├─ calendar-check        → calendar.yaml (public holidays in trip range)
       ├─ seasonal-advisory     → seasonal.yaml (weather/daylight hazards)
       ├─ transit-detail        → transit.yaml (peak windows / IC card / walks)
       ├─ cost-rollup           → cost.yaml (estimate vs budget)
       ├─ itinerary-synthesis   → itinerary.yaml (canonical)
       ├─ itinerary-gate        → gate-report.yaml (pass)
       ├─ tripwork-export-artifact → trips/<slug>/<stem>.md (md / gmaps / line / notion)
       └─ export-gate           → export-gate-report.yaml (pass = pipeline complete)
```

## Iron Rules

| Rule | Why |
|---|---|
| Source-Verified-First | Every POI/restaurant/address/opening-hour/regulation needs >= 2 independent sources (>= 1 local-language) AND a geocode that falls in its claimed region before it reaches the itinerary. Enforced by `source-verify` + `travel-advisory`. |
| No unsourced fact | Every fact entering an artifact needs a source **fetched during this run**; model recall is never a source, because opening hours, prices, holidays and regulations all go stale. Use the **source ladder**: (1) `WebSearch`; (2) `WebFetch` against an official or local-authority page; (3) `WebFetch` against a search engine's HTML endpoint **for discovery only** — it may supply candidate URLs, never the fact itself, which must still be read from the page in (2). **HALT only when every route is unavailable**, and say which ones you tried. Applies to every research stage (destination-research, source-verify, accommodation-research, calendar-check, seasonal-advisory, transit-detail, cost-rollup, travel-advisory). |
| Only verified flows downstream | `itinerary-synthesis` reads only `verify_status: verified`. `conflicting`/`rejected`/`unverified` stay recorded but never enter the plan — including the places offered to the user to choose from (restaurants, sights, lodgings): only verified ones, never a candidate whose operating status is unknown. |
| Calendar-aware scheduling | Synthesis hard-avoids scheduling a POI on a closed day and flags holiday/weekend crowd days. Logic in `scripts/trip_calendar.py`. |
| Closing-buffer-aware scheduling | Synthesis checks every timed slot via `scripts/hours.py::closing_status`: never schedules past last order/entry, flags thin buffers, and stops if a `must_do` cannot fit. |
| Gate ≠ content correct | `itinerary-gate` passing means structure is valid; content correctness is guaranteed upstream by `source-verify`. |
| Stop on confirmation | Every halt in `tripwork:tripwork-orchestrator`'s Stop-on-Confirmation table (cross-source conflict, a `far` hop, a `banned` regulation, a failed `must_do`, an over-budget estimate, …) → stop and ask the user. Never silently drop content. |
| Invoke orchestrator to advance | After any stage completes, re-invoke `tripwork:tripwork-orchestrator` to determine the next stage. |
| Preflight before pipeline | First invocation in a cwd is gated by `tripwork-workspace-shape-preflight`; the `work/.preflight-completed` stamp must exist before the orchestrator advances. |

## Workspace

- `trips/<slug>/` — living docs (version-controlled by the consumer)
- `work/<slug>/` — rebuildable state + research cache (gitignored)

## Stage Contract

| Field | Value |
|---|---|
| Input | Any travel-planning request (new or resumed). |
| Output | Control passes to `tripwork:tripwork-orchestrator`. No trip artifact is written by this skill. |
| Stop condition | Agent has invoked `tripwork:tripwork-orchestrator`. Every subsequent stage decision belongs to the orchestrator. |
| Next stage | `tripwork:tripwork-orchestrator` — always. There is no alternative entry point. |
