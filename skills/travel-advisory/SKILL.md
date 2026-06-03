---
name: travel-advisory
description: Use when an itinerary needs entry/customs/battery regulation verification for the destination + airline + travel date. Iron-rule gate. Produces advisory.yaml. Can also be invoked standalone to check regulations.
---

# travel-advisory — Source-Verified-First for hard facts

Regulations can harm travellers if wrong, so the **Source-Verified-First** rule is applied here even more strictly than to POIs.

## Method

- Use the consumer harness `WebSearch`; prefer local-language official sources.
- Each item needs >= 1 **official** source (airline notice, government entry portal) plus a corroborating source.
- Record `effective_date` for every rule (regulations change — e.g. battery rules with staged effective dates).
- If the travel date precedes a rule's `effective_date`, set `not_yet_in_effect: true`.
- Tag `risk`: `info` | `restricted` | `banned`.

## Output

Write `trips/<slug>/advisory.yaml` (schema: `schemas/advisory.schema.json`). Any `restricted`/`banned` item -> surface prominently and feed it into the synthesis checklist. Stop and require user acknowledgement for `banned` items.

Return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/trip-brief.yaml` (destination, airline, dates). Standalone use also allowed. |
| Output | `trips/<slug>/advisory.yaml` (rules with `effective_date` + `risk`). |
| Stop condition | A `banned` item exists → require explicit user acknowledgement. |
| Next stage | `tripwork:orchestrator`. |

## Red Flags

- "This regulation is well-known, no need to cite" → cite an official source; rules change.
- "No date needed" → every rule records `effective_date`; flag `not_yet_in_effect`.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Citing only a blog/aggregator | Need >= 1 official source (airline notice / government portal). |
| Burying a `banned` item in a table | Surface prominently + push into the checklist + stop for acknowledgement. |
