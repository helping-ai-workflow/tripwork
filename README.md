# tripwork

Source-Verified-First travel-planning pipeline plugin (Claude Code / agent skills).

## Iron Rule

No POI, restaurant, address, opening-hour, or regulation reaches your itinerary
until it is cross-checked against >= 2 independent sources (>= 1 local-language)
and geocoded into its claimed region.

## Pipeline

`trip-brief -> destination-research -> source-verify -> routing-audit ->
itinerary-synthesis -> travel-advisory -> itinerary-gate -> export-artifact`

## Outputs

Markdown itinerary (with Google Maps links), LINE-friendly short text, and
optional Notion write-back.

## Install

Add the helping-ai-workflow marketplace, then `/plugin install tripwork`.

## Geocoding

Uses OSM Nominatim (no API key). Respect its usage policy (<= 1 req/s).

## Development

`pip install -e ".[dev]" && pytest`
