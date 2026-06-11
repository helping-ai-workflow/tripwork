---
name: routing-audit
description: Use when verified-pois.yaml is ready and inter-POI distances + cross-region feasibility must be checked before synthesis. Produces routing.yaml.
---

# routing-audit

Cluster verified POIs by district and assess movement feasibility. Produces `trips/<slug>/routing.yaml` (schema: `schemas/routing.schema.json`).

## Steps

1. Read `verify_status: verified` POIs from `verified-pois.yaml`.
2. Group by `district`; mark the cluster containing `trip-brief.base.district` as `is_base: true`. Compute each cluster's `centroid` (mean of member POI geocodes via `scripts/geocode.py::cluster_centroid`) — `accommodation-research` uses it as the no-key geocode fallback for hotels Nominatim cannot pin.
3. For each planned inter-district hop, estimate travel minutes (subway/taxi) and classify with `scripts/distance.py::classify_hop(mins, max_hop_mins, km=haversine_km(...), mode=...)`. Passing `km`+`mode` enables the physical-plausibility floor: an estimate below `scripts/distance.py::min_plausible_mins(km, mode)` (urban transit ≈ 15 km/h door-to-door) returns `implausible` — re-estimate the hop or cite a timetable rather than trusting a too-fast guess. Use `trip-brief.routing.max_hop_mins` (default 60). For region-in-range checks, the region radius defaults to 5 km and is overridable via `trip-brief.routing.region_radius_km`.
4. Emit `warnings` for any claim/geo mismatch surfaced in verified-pois `conflict_note` (e.g. a POI the brief placed in the base district that geocoded elsewhere).

## Stop-on-Confirmation

Any hop flagged `far` -> stop and ask the user whether to keep or replace the POI. Do not silently reorder around it. A hop flagged `implausible` (estimate below the physical floor) -> do not record it; re-estimate or cite a sourced timetable first.

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
