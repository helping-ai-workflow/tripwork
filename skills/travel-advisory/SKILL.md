---
name: travel-advisory
description: Use when an itinerary needs entry/customs/battery regulation verification for the destination + airline + travel date, or when invoked standalone to check a regulation. Produces advisory.yaml.
---

# travel-advisory — Source-Verified-First for hard facts

Regulations can harm travellers if wrong, so the **Source-Verified-First** rule is applied here even more strictly than to POIs.

## Method

- Research using the **source ladder** in `tripwork:using-tripwork` (WebSearch, else WebFetch against an official page, else a search HTML endpoint for discovery only); prefer local-language official sources.
- Each item needs >= 1 **official** source (airline notice, government entry portal) plus a corroborating source.
- Record `effective_date` for every rule (regulations change — e.g. battery rules with staged effective dates).
- If the travel date precedes a rule's `effective_date`, set `not_yet_in_effect: true`.
- Tag `risk`: `info` | `restricted` | `banned`.

## Output

Write `trips/<slug>/advisory.yaml` (schema: `schemas/advisory.schema.json`) **only when routed in by the orchestrator (Stage Selection rule 1.5, or the rule 11 staleness re-check)**. In that pipeline mode, then validate it:
`python scripts/validate_artifact.py trips/<slug>/advisory.yaml`
(exit 0 required before returning). Any `restricted`/`banned` item -> surface prominently and feed it into the synthesis checklist. Stop and require user acknowledgement for `banned` items.

Record `input_fingerprints: {"trip-brief.yaml": <fp>}` where `<fp>` is the stdout of
`python scripts/input_fingerprint.py trips/<slug>/trip-brief.yaml advisory` (prefix the
path with the plugin root if your cwd is the consumer workspace, same as every other
script instruction in this plugin). Without it, rule 11 falls back to comparing file
timestamps and re-runs this stage after any unrelated edit to the brief.

**Standalone mode (ad-hoc regulation question).** When invoked directly (not via the orchestrator), do **NOT** write `trips/<slug>/advisory.yaml` — that file is the pipeline artifact, and writing it out of band lets the orchestrator's rule 11 treat the stage as already done and skip the real gate. Answer inline, or write `work/<slug>/advisory-adhoc.yaml` instead.

Return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/trip-brief.yaml` (destination, airline, dates). Standalone use also allowed. |
| Output | `trips/<slug>/advisory.yaml` (rules with `effective_date` + `risk`). |
| Stop condition | A `banned` item exists (`banned_item`) → require explicit user acknowledgement. |
| Next stage | `tripwork:orchestrator`. |

## Red Flags

- "This regulation is well-known, no need to cite" → cite an official source; rules change.
- "No date needed" → every rule records `effective_date`; flag `not_yet_in_effect`.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Citing only a blog/aggregator | Need >= 1 official source (airline notice / government portal). |
| Burying a `banned` item in a table | Surface prominently + push into the checklist + stop for acknowledgement. |
