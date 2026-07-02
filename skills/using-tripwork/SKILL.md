---
name: using-tripwork
description: Use when starting any travel-planning workflow with tripwork, before any pipeline stage runs.
---

# Using tripwork

tripwork is a staged, orchestrator-driven pipeline for building source-verified travel itineraries.

**Entry point:** Always start with `tripwork:workspace-shape-preflight` (first time in a cwd) then `tripwork:orchestrator`. Never jump directly to synthesis or export.

## File Paths Are Target-Repo Convention

Example paths throughout these skills (`trips/<slug>/`, `work/<slug>/`) reflect the target repo's convention. The authoritative layout is defined in the target repo's `CLAUDE.md`, not in plugin skills. Plugin scripts accept explicit paths as arguments and do not hardcode layout.

## Pipeline

The orchestrator's Stage Selection is canonical for order and predicates; this tree mirrors it.

```
workspace-shape-preflight  (entry gate — first invocation only)
  └─ orchestrator
       ├─ trip-brief            → trip-brief.yaml
       ├─ destination-research  → candidates.yaml (untrusted pool)
       ├─ source-verify  (gate) → verified-pois.yaml
       ├─ routing-audit         → routing.yaml
       ├─ accommodation-research→ accommodations.yaml
       ├─ inter-stop-legs       → legs.yaml (city-to-city feasibility)
       ├─ calendar-check        → calendar.yaml (public holidays in trip range)
       ├─ seasonal-advisory     → seasonal.yaml (weather/daylight hazards)
       ├─ transit-detail        → transit.yaml (peak windows / IC card / walks)
       ├─ cost-rollup           → cost.yaml (estimate vs budget)
       ├─ travel-advisory (gate)→ advisory.yaml (entry/customs/battery)
       ├─ itinerary-synthesis   → itinerary.yaml (canonical) + itinerary.md
       ├─ itinerary-gate        → gate-report.yaml (pass)
       ├─ export-artifact       → exports/<slug>-itinerary.md (md / gmaps / line / notion)
       └─ export-gate           → export-gate-report.yaml (pass = pipeline complete)
```

## Iron Rules

| Rule | Why |
|---|---|
| Source-Verified-First | Every POI/restaurant/address/opening-hour/regulation needs >= 2 independent sources (>= 1 local-language) AND a geocode that falls in its claimed region before it reaches the itinerary. Enforced by `source-verify` + `travel-advisory`. |
| No search, no fact | If the `WebSearch` tool is unavailable or a query cannot be completed, **HALT the stage and tell the user** — never substitute model memory. A fact with no fetched source this run is not verified; opening hours, prices, holidays and regulations all go stale and model recall is unsafe for them. Applies to every research stage (destination-research, source-verify, accommodation-research, calendar-check, seasonal-advisory, transit-detail, cost-rollup, travel-advisory). |
| Only verified flows downstream | `itinerary-synthesis` reads only `verify_status: verified`. `conflicting`/`rejected`/`unverified` stay recorded but never enter the plan. |
| Calendar-aware scheduling | `calendar-check` records public holidays in the trip range; `source-verify` records per-POI `closed_days`. Synthesis hard-avoids scheduling a POI on a closed day and flags holiday/weekend crowd days. Logic in `scripts/calendar.py`. |
| Closing-buffer-aware scheduling | `source-verify` records each POI's intra-day `hours` (close / last_order / last_entry / typical_visit_mins). Synthesis checks every timed slot via `scripts/hours.py::closing_status`: never schedules past last order/entry, flags thin buffers, and stops if a `must_do` cannot fit. |
| Gate ≠ content correct | `itinerary-gate` passing means structure is valid; content correctness is guaranteed upstream by `source-verify`. |
| Stop on confirmation | Cross-source conflict, hop flagged `far`, booking lead-time missed, regulation `banned`, or must-do verification failure → stop and ask the user. Never silently drop content. |
| Invoke orchestrator to advance | After any stage completes, re-invoke `tripwork:orchestrator` to determine the next stage. |
| Preflight before pipeline | First invocation in a cwd is gated by `workspace-shape-preflight`; the `work/.preflight-completed` stamp must exist before the orchestrator advances. |

## Quick Reference

| Task | Skill |
|---|---|
| Validate/bootstrap workspace | `tripwork:workspace-shape-preflight` |
| New trip request | `tripwork:orchestrator` |
| Capture trip parameters | `tripwork:trip-brief` |
| Gather candidate POIs | `tripwork:destination-research` |
| Verify candidates | `tripwork:source-verify` |
| Check cross-region feasibility | `tripwork:routing-audit` |
| Pick lodging for overnight stops | `tripwork:accommodation-research` |
| Check city-to-city legs | `tripwork:inter-stop-legs` |
| Establish trip-range public holidays | `tripwork:calendar-check` |
| Check seasonal/weather hazards | `tripwork:seasonal-advisory` |
| Establish intra-city transit comfort | `tripwork:transit-detail` |
| Roll up cost vs budget | `tripwork:cost-rollup` |
| Check entry/customs/battery rules | `tripwork:travel-advisory` |
| Build day-by-day plan | `tripwork:itinerary-synthesis` |
| Validate structure before export | `tripwork:itinerary-gate` |
| Render deliverables | `tripwork:export-artifact` |
| Validate the rendered deliverable | `tripwork:export-gate` |

## Workspace

- `trips/<slug>/` — living docs (version-controlled by the consumer)
- `work/<slug>/` — rebuildable state + research cache (gitignored)

## Stage Contract

| Field | Value |
|---|---|
| Input | Any travel-planning request (new or resumed). |
| Output | Control passes to `tripwork:orchestrator`. No trip artifact is written by this skill. |
| Stop condition | Agent has invoked `tripwork:orchestrator`. Every subsequent stage decision belongs to the orchestrator. |
| Next stage | `tripwork:orchestrator` — always. There is no alternative entry point. |
