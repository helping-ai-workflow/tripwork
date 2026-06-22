---
name: cost-rollup
description: Use when accommodations + legs are ready and the trip's big-ticket costs must be summed and compared to the budget before synthesis. No-key estimate. Produces cost.yaml.
---

# cost-rollup — trip-cost estimate

Sum the structured big-ticket costs and compare them to the budget. Produces
`trips/<slug>/cost.yaml` (schema: `schemas/cost.schema.json`). Everything is an
**estimate** with an `as_of` date — never a precise quote (prices are volatile).

## Budget scope (P6)

`trip-brief.budget` is the **whole-trip** cap: lodging (per-room × rooms × nights) +
transport + daily incidentals — i.e. exactly the `sum_costs` grand `total` this stage
computes. It is NOT lodging-only. `over_budget` compares the grand total against it.

## Gather (from upstream artifacts — no re-research)

- Accommodation: each chosen lodging's `cost` from `accommodations.yaml`, via
  `scripts/cost.py::lodging_line_amount(cost, nights, rooms)` — `cost.amount` is **per
  room**, so this multiplies by `cost.rooms` (default 1) and, for `basis == "per_night"`,
  by the stop's `nights`. A multi-room stop must set `cost.rooms` or it is under-costed. (P6)
- Transport: each leg's `fare` from `legs.yaml`, and the trip-level `pass` option.
- Incidental: `trip-brief.daily_incidental.amount × days` (a user-supplied allowance,
  honestly an estimate).

## Currency (no FX API)

Pick one **primary currency** (usually the destination's). Convert minor-currency items
with a **researched approximate rate** (consumer `WebSearch` for a widely-cited / official
rate near the trip dates); record `fx_rate` + `source_currency` on the converted line
item. If `trip-brief.home_currency` differs, add an advisory `fx_note` for the total.

## Compute (logic in `scripts/cost.py`)

- `pass_break_even(covered_fares, pass.price.amount, travellers=len(trip-brief.members))` —
  if the pass is cheaper than paying the covered legs individually, recommend it and use the
  pass price for those legs (record `pass_break_even` with `use_pass` + `saving`). **Pass the
  head count** so the group totals are right — fares and the pass are both per-person, so a
  multi-traveller trip is otherwise under-counted (the decision is the same, the magnitude is
  not). (F2)
- `incidental_total(daily, days)` → an `incidental` line item.
- `sum_costs(line_items)` → `total` (+ per-category subtotals).
- When `trip-brief.budget` is set, `over_budget(total, budget.amount)`. **If over → stop
  and ask** (drop / downgrade something, or accept); record the decision in
  `work/<slug>/stage-state.yaml`. No budget → no comparison.

## Output

Write `cost.yaml` with `as_of` + `estimate_note`. A trip with no numeric costs still writes
a best-effort (possibly empty) `cost.yaml`. Return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/trip-brief.yaml` (budget, daily_incidental, home_currency, dates) + `trips/<slug>/accommodations.yaml` + `trips/<slug>/legs.yaml`. |
| Output | `trips/<slug>/cost.yaml` (line items + total + budget compare + pass break-even). |
| Stop condition | The estimated total exceeds a set `budget` → ask user. |
| Next stage | `tripwork:orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Re-researching prices already on the artifacts | Read `cost` / `fare` / `pass` from upstream; only aggregate here. |
| Presenting the total as exact | It is an estimate with an `as_of` date; prices vary. |
| Pricing every meal and ticket | Out of scope; use the `daily_incidental` allowance instead. |
