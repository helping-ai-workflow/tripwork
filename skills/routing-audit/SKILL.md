---
name: routing-audit
description: Use when verified-pois.yaml is ready and inter-POI distances + cross-region feasibility must be checked before synthesis. Produces routing.yaml.
---

# routing-audit

Cluster verified POIs by district and assess movement feasibility. Produces `trips/<slug>/routing.yaml` (schema: `schemas/routing.schema.json`).

## Steps

1. Read `verify_status: verified` POIs from `verified-pois.yaml`.
2. Group by `district`; mark the cluster containing `trip-brief.base.district` as `is_base: true`.
3. For each planned inter-district hop, estimate travel minutes (subway/taxi) and classify with `scripts/distance.py::classify_hop` using `trip-brief.routing.max_hop_mins` (default 60). Use `haversine_km` as a sanity bound. For region-in-range checks, the region radius defaults to 5 km and is overridable via `trip-brief.routing.region_radius_km`.
4. Emit `warnings` for any claim/geo mismatch surfaced in verified-pois `conflict_note` (e.g. a POI the brief placed in the base district that geocoded elsewhere).

## Stop-on-Confirmation

Any hop flagged `far` -> stop and ask the user whether to keep or replace the POI. Do not silently reorder around it.

Return to `tripwork:orchestrator`.

## Stage Contract

| Field | Value |
|---|---|
| Input | `trips/<slug>/verified-pois.yaml` + `trips/<slug>/trip-brief.yaml`. |
| Output | `trips/<slug>/routing.yaml` (clusters, hops, warnings). |
| Stop condition | A hop flagged `far` → ask user keep-or-replace. |
| Next stage | `tripwork:orchestrator`. |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Routing a non-verified POI | Only `verify_status: verified` POIs enter clusters. |
| Hardcoding the 60-min threshold | Read `trip-brief.routing.max_hop_mins`; default 60 only if unset. |
